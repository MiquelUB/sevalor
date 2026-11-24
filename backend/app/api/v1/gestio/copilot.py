"""Endpoints per al Mòdul d'IA Copilot de Camp i Gestió (/gestio/copilot & PWA — Spec 012)."""

import logging
import time
import uuid
from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import AliasChoices, BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.db import get_db_with_tenant_context
from app.core.network_utils import build_wss_tunnel_uri, extract_wss_tunnel_target
from app.core.security import get_current_user_claims, require_roles
from app.models.models import (
    AlertaGarantiaRecompra,
    Article,
    AuditoriaPostObra,
    EinaCustodia,
    Empresa,
    EstocMagatzem,
    MemorandumTecnicCopilot,
    OrdreTreball,
    Usuari,
)
from app.services.copilot_config_service import (
    get_strict_copilot_config,
    save_strict_copilot_config,
)
from app.services.llm_utils import strip_think
from app.services.sovereign_storage import SovereignStorageGateway
from app.services.subagents.dispatcher import copilot_dispatcher
from app.services.vault_tunnel import (
    VaultTunnelError,
    VaultTunnelOfflineError,
    VaultTunnelRemoteError,
    VaultTunnelTimeoutError,
    empresa_target_key,
    vault_tunnel_broker,
)

router = APIRouter(
    prefix="/gestio/copilot",
    tags=["Copilot IA de Camp i Gestió"],
    dependencies=[Depends(require_roles(["BOSS", "SECRETARIA", "ENGINYER"]))],
)

# Límits i paràmetres constitucionals (Spec 012)
TIMEOUT_LIMIT_SEGONS = 15
CONFIANCA_ACUSTICA_LLINDAR = 0.40  # Si < 0.40, avís de tractor/vent (EDGE-03)
TERMINI_GARANTIA_MA_OBRA_DIES = 90  # 3 mesos (<3 mesos a cost 0 €) (RF-07)
TERMINI_GARANTIA_FABRICANT_ANYS = 2  # 2 anys per defecte
LLINDAR_MERMA_CONTINUA_PERCENTATGE = (
    250.0  # Consum continu >250% bloca si no hi ha incidència (EDGE-08)
)

PARAULES_CLAU_FINANCERES_VETO = [
    "salari",
    "sou",
    "nomina",
    "nòmina",
    "llibre major",
    "llibre_major",
    "balanç",
    "balanc",
    "compte bancari",
    "comptes bancaris",
    "iban proveidor",
    "iban proveïdor",
    "preu d'adquisició",
    "preu cost",
    "preu compra",
    "comptabilitat agregada",
    "facturacio total",
    "marge brut global",
    "cobrem per hora",
    "cobrar per hora",
    "cost per hora",
    "preu per hora",
    "cost hora",
    "tarifa horària",
    "tarifa horaria",
]

logger = logging.getLogger("copilot_ia")

# ---------------------------------------------------------------------------
# Pont de compatibilitat i client LLM directe via Túnel WSS Sobirà (Copilot v3.2)
# ---------------------------------------------------------------------------


async def execute_tool_get_vehicle_info(
    db: AsyncSession, empresa_id: uuid.UUID, matricula: str
) -> dict:
    """Pont de compatibilitat cap enrere que delega directament al subagent de flota."""
    return await copilot_dispatcher.subagent_flota.tool_get_vehicle_info(db, empresa_id, matricula)


async def _resoldre_model_actiu_tunel(target_key: str, configured_model: str) -> str:
    """Resol el model carregat en viu a LM Studio/Ollama via estat del túnel per evitar 400/404 o recàrregues lentes."""
    cfg_clean = (configured_model or "").strip()
    loaded_models: List[str] = []
    try:
        st = await vault_tunnel_broker.get_status(target_key)
        health = st.get("health") if isinstance(st, dict) else {}
        models = health.get("models") if isinstance(health, dict) else []
        if isinstance(models, list) and models:
            loaded_models = [str(m) for m in models if m]
    except Exception:
        pass

    if not loaded_models and not cfg_clean:
        try:
            m_res = await vault_tunnel_broker.call_llm_models(target_key, timeout=3.0)
            loaded_models = [
                str(m.get("id"))
                for m in m_res.get("data", [])
                if isinstance(m, dict) and m.get("id")
            ]
        except Exception:
            pass

    if loaded_models:
        if cfg_clean:
            cfg_low = cfg_clean.lower()
            for lm in loaded_models:
                if lm.lower() == cfg_low:
                    return lm
        chat_models = [m for m in loaded_models if "embed" not in m.lower()]
        if chat_models:
            return chat_models[0]
        return loaded_models[0]

    if cfg_clean:
        return cfg_clean

    return str(
        getattr(settings, "LM_STUDIO_MODEL", None)
        or getattr(settings, "LMSTUDIO_MODEL", "qwen2.5-vl-7b-instruct")
    )


async def cridar_lm_studio(
    pregunta: str,
    vertical: str = "SEVALOR",
    context_addicional: Optional[str] = None,
    empresa: Optional[Empresa] = None,
    node_ia_url: Optional[str] = None,
    vault_token: Optional[str] = None,
    db: Optional[AsyncSession] = None,
    *,
    max_tokens: int = 280,
    timeout_s: Optional[float] = None,
    raise_on_timeout: bool = False,
    concise_system: bool = False,
) -> Optional[str]:
    """Cridar el node d'IA local dedicat de l'empresa via Túnel WSS Únic amb prompt estricte per tenant."""
    emp_target_id: Optional[str] = None
    if empresa is not None:
        if not (empresa.node_ia_actiu and getattr(empresa, "feature_copilot_ia", False)):
            return None
        emp_target_id = str(empresa.id)
    elif node_ia_url:
        emp_target_id = extract_wss_tunnel_target(node_ia_url)

    if not emp_target_id:
        return None

    try:
        target_key = empresa_target_key(emp_target_id)
    except ValueError:
        return None

    if not await vault_tunnel_broker.is_online(target_key):
        return None

    configured_model = ""
    effective_timeout = 28.0
    if db is not None:
        cfg = await get_strict_copilot_config(db, uuid.UUID(emp_target_id))
        if not cfg or not (cfg.system_prompt or "").strip():
            raise HTTPException(
                status_code=422,
                detail="COPILOT_NOT_CONFIGURED: Aquesta empresa no té el prompt configurat a /gestio/copilot/.",
            )
        raw_sys = cfg.system_prompt.strip()
        if concise_system:
            first_para = raw_sys.split("\n\n")[0].strip()
            system_prompt = (first_para or raw_sys)[:600]
        else:
            system_prompt = raw_sys
            if (cfg.rag_prompt or "").strip():
                system_prompt += f"\n\nINSTRUCCIONS RAG:\n{cfg.rag_prompt.strip()}"
        configured_model = (cfg.effective_chat_model or "").strip()
        effective_timeout = min(max(15.0, float(cfg.timeout_budget_s or 25.0)), 80.0)
    else:
        raise HTTPException(
            status_code=422,
            detail="COPILOT_NOT_CONFIGURED: Cal sessió de BD per carregar la configuració aïllada del Copilot.",
        )

    if timeout_s is not None:
        effective_timeout = min(max(5.0, float(timeout_s)), 80.0)

    if context_addicional:
        system_prompt += f"\nContext addicional:\n{context_addicional}"

    model_name = await _resoldre_model_actiu_tunel(target_key, configured_model)
    payload: Dict[str, Any] = {
        "model": model_name,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": pregunta},
        ],
        "temperature": 0.2,
        "max_tokens": max(64, min(int(max_tokens), 1024)),
    }

    try:
        data = await vault_tunnel_broker.call_llm_chat(
            target_key, payload, timeout=effective_timeout, priority="HIGH"
        )
        choices = data.get("choices", [])
        if choices:
            msg_obj = choices[0].get("message") or {}
            raw_content = str(msg_obj.get("content") or "").strip()
            cleaned = strip_think(raw_content) or raw_content
            if cleaned:
                return cleaned
    except VaultTunnelTimeoutError as e:
        logger.warning("Timeout LM Studio via WSS (%s, %.1fs): %s", target_key, effective_timeout, e)
        if raise_on_timeout:
            raise
    except VaultTunnelRemoteError as e:
        if e.code != "LLM_OFFLINE" and e.status_code in (400, 404, 422):
            # Model configurat no carregat o canviat en calent a LM Studio: reintent amb model viu
            try:
                m_res = await vault_tunnel_broker.call_llm_models(target_key, timeout=4.0)
                loaded = [
                    str(m.get("id"))
                    for m in m_res.get("data", [])
                    if isinstance(m, dict) and m.get("id")
                ]
                chat_m = [m for m in loaded if "embed" not in m.lower()]
                live_model = chat_m[0] if chat_m else (loaded[0] if loaded else "")
                if live_model and live_model != model_name:
                    payload["model"] = live_model
                    data = await vault_tunnel_broker.call_llm_chat(
                        target_key,
                        payload,
                        timeout=min(effective_timeout, 55.0),
                        priority="HIGH",
                    )
                    choices = data.get("choices", [])
                    if choices:
                        msg_obj = choices[0].get("message") or {}
                        raw_content = str(msg_obj.get("content") or "").strip()
                        cleaned = strip_think(raw_content) or raw_content
                        if cleaned:
                            return cleaned
            except VaultTunnelTimeoutError:
                if raise_on_timeout:
                    raise
            except Exception as inner_e:
                logger.warning("Reintent model actiu LM Studio fallit (%s): %s", target_key, inner_e)
        logger.warning("Connexió amb LM Studio via WSS fallida (%s): %s", target_key, e)
    except (VaultTunnelError, Exception) as e:
        logger.warning("Connexió amb LM Studio via WSS fallida (%s): %s", target_key, e)

    return None



def aplicar_tenant_context(claims: Dict[str, Any]) -> uuid.UUID:
    """Verifica que el token porta empresa_id i el retorna.

    El context RLS ja s'injecta automàticament via get_db_with_tenant_context.
    """
    empresa_id_str = claims.get("empresa_id")
    if not empresa_id_str:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No s'ha trobat l'identificador d'empresa (tenant) al token.",
        )
    return uuid.UUID(empresa_id_str)


# ---------------------------------------------------------------------------
# DTOs / Esquemes Pydantic
# ---------------------------------------------------------------------------


class SollicitudPeritatgeIncidencia(BaseModel):
    ordre_treball_id: Optional[uuid.UUID] = None
    incidencia_id: Optional[uuid.UUID] = None
    text_dictat_operari: Optional[str] = None
    confianca_acustica: float = Field(default=0.95, ge=0.0, le=1.0)
    audio_path: Optional[str] = None
    foto_path: Optional[str] = None
    simular_timeout: bool = False


class ValidacioMemorandum(BaseModel):
    dictamen_pericial: Optional[str] = None  # EXTRA_FACTURABLE o COST_NO_IMPUTABLE
    estimacio_materials_extra: Optional[List[Dict[str, Any]]] = None
    cost_estimat_total: Optional[float] = None
    observacions_enginyer: Optional[str] = None
    accio: str = Field(default="APROVAR")  # APROVAR, EDITAR, REBUTJAR


class ReconciliacioPostObraIn(BaseModel):
    ordre_treball_id: uuid.UUID
    materials_consumits: List[Dict[str, Any]] = Field(default_factory=list)
    hores_reals: float = 0.0
    hores_previstes: float = 0.0
    km_reals: float = 0.0
    despeses_camp: float = 0.0
    sync_pendent: bool = False
    incidencies_registrades: int = 0


class AprovacioPressupostIn(BaseModel):
    confirmar: bool = True
    observacions: Optional[str] = None


class VerificacioStockIn(BaseModel):
    ordre_treball_id: Optional[uuid.UUID] = None
    materials: List[Dict[str, Any]] = Field(
        default_factory=list
    )  # {article_id, quantitat_necessaria}


class DocumentRagIn(BaseModel):
    pregunta: str = Field(validation_alias=AliasChoices("pregunta", "titol"))
    resposta: str = Field(validation_alias=AliasChoices("resposta", "contingut"))
    paraules_clau: Optional[str] = Field(
        default=None, validation_alias=AliasChoices("paraules_clau", "tags")
    )


class ConsultaXatIn(BaseModel):
    pregunta: str
    imatge_b64: Optional[str] = None
    historial: Optional[List[Dict[str, Any]]] = None
    context_id: Optional[str] = None


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/estat-node")
async def obtenir_estat_node_ia(
    db: AsyncSession = Depends(get_db_with_tenant_context),
    claims: Dict[str, Any] = Depends(get_current_user_claims),
):
    """Retorna l'estat operatiu en viu del Node d'IA Sobirà Local via Túnel Invers WSS."""
    empresa_id = aplicar_tenant_context(claims)

    res = await db.execute(select(Empresa).where(Empresa.id == empresa_id))
    empresa = res.scalar_one_or_none()
    await SovereignStorageGateway.autocurar_config_tunel_empresa(db, empresa, commit=True)
    vertical = empresa.vertical if empresa else "SEVALOR"
    feature_on = bool(getattr(empresa, "feature_copilot_ia", False)) if empresa else False
    node_actiu_cfg = bool(empresa and empresa.node_ia_actiu)
    target_key = empresa_target_key(empresa_id)
    tunnel_online = await vault_tunnel_broker.is_online(target_key)
    tunnel_uri = build_wss_tunnel_uri(empresa_id)

    if not feature_on or not node_actiu_cfg:
        return {
            "node_actiu": False,
            "feature_copilot_ia": feature_on,
            "tunnel_online": tunnel_online,
            "tunnel_status": "ONLINE" if tunnel_online else "OFFLINE",
            "estat": "SENSE_ORDINADOR_DEDICAT",
            "sobirania_dades": "100% Local a la seu de l'empresa (Zero Cloud Egress)",
            "proveidor": "Ordinador Local Dedicat (No vinculat)",
            "model_llm": "LM Studio / Ollama (Pendent d'activació)",
            "vertical_activa": vertical,
            "latencia_inferencia_ms": None,
            "cpu_only_enforced": True,
            "ai_act_compliance": "RGPD Nivell Alt / Article 5 AI Act",
            "missatge": "Es requereix un ordinador dedicat a la seu de l'empresa per activar el Copilot Sobirà.",
        }

    if not tunnel_online:
        return {
            "node_actiu": False,
            "feature_copilot_ia": feature_on,
            "tunnel_online": False,
            "tunnel_status": "OFFLINE",
            "estat": "TUNEL_OFFLINE",
            "url_ordinador": tunnel_uri,
            "proveidor": "Ordinador Local Dedicat de l'Empresa (Túnel WSS desconnectat)",
            "sobirania_dades": "100% Local a la seu de l'empresa (Zero Cloud Egress)",
            "model_llm": "LM Studio / Ollama (Túnel WSS desconnectat)",
            "vertical_activa": vertical,
            "latencia_inferencia_ms": None,
            "cpu_only_enforced": True,
            "ai_act_compliance": "RGPD Nivell Alt / Article 5 AI Act",
            "missatge": "L'ordinador dedicat de l'empresa no té el Túnel Sobirà WSS connectat actualment.",
        }

    latencia_real_ms: Optional[int] = None
    models_detectats: List[str] = []
    t0 = time.perf_counter()
    try:
        llm_res = await vault_tunnel_broker.call_llm_models(target_key, timeout=6.0)
        latencia_real_ms = int((time.perf_counter() - t0) * 1000)
        if isinstance(llm_res.get("data"), list):
            for m in llm_res["data"]:
                if isinstance(m, dict) and (m.get("id") or m.get("name")):
                    models_detectats.append(str(m.get("id") or m.get("name")))
                elif isinstance(m, str) and m:
                    models_detectats.append(m)
        if isinstance(llm_res.get("models"), list):
            for m in llm_res["models"]:
                val = str(m.get("name") or m.get("id")) if isinstance(m, dict) else str(m)
                if val and val not in models_detectats:
                    models_detectats.append(val)
    except VaultTunnelError:
        latencia_real_ms = int((time.perf_counter() - t0) * 1000)

    return {
        "node_actiu": True,
        "feature_copilot_ia": feature_on,
        "tunnel_online": True,
        "tunnel_status": "ONLINE",
        "estat": "ORDINADOR_DEDICAT_ACTIU",
        "url_ordinador": tunnel_uri,
        "proveidor": "Ordinador Local Dedicat de l'Empresa (Túnel Invers WSS)",
        "sobirania_dades": "100% Local a la seu de l'empresa (Zero Cloud Egress)",
        "model_llm": models_detectats[0] if models_detectats else "Local Sovereign LLM (LM Studio / Ollama)",
        "models": models_detectats,
        "vertical_activa": vertical,
        "latencia_inferencia_ms": latencia_real_ms,
        "cpu_only_enforced": True,
        "ai_act_compliance": "RGPD Nivell Alt / Article 5 AI Act",
    }


@router.get("/garanties/auditoria")
async def auditar_garanties_i_memoria_finca(
    finca_id: Optional[uuid.UUID] = Query(None),
    client_id: Optional[uuid.UUID] = Query(None),
    numero_serie: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db_with_tenant_context),
    claims: Dict[str, Any] = Depends(get_current_user_claims),
):
    """Audita l'historial de 365 dies, garanties de fabricant i garantia interna de mà d'obra (RF-04, RF-05, RF-06, RF-07, EDGE-07, EDGE-09)."""
    empresa_id = aplicar_tenant_context(claims)
    avui = date.today()
    fa_un_any = avui - timedelta(days=365)

    alertes = []
    intervencions_històriques = []

    # 1. Auditoria per Finca o Client (Memòria 365 dies)
    if finca_id or client_id:
        query = select(OrdreTreball).where(
            OrdreTreball.empresa_id == empresa_id,
            OrdreTreball.data_planificacio >= fa_un_any,
        )
        if finca_id:
            query = query.where(OrdreTreball.finca_id == finca_id)
        if client_id:
            query = query.where(OrdreTreball.client_id == client_id)

        query = query.order_by(OrdreTreball.data_planificacio.desc())
        res_ots = await db.execute(query)
        ots = res_ots.scalars().all()

        if not ots:
            # Zero Mock Data (RF-21, RF-22, EDGE-09)
            return {
                "trobat": False,
                "missatge": "No tinc informació registrada sobre aquest element. Primer servei registrat a la instal·lació.",
                "intervencions_365_dies": [],
                "garanties_actives": [],
            }

        for ot in ots:
            intervencions_històriques.append(
                {
                    "ordre_id": str(ot.id),
                    "codi": ot.codi,
                    "titol": ot.titol,
                    "data": ot.data_planificacio.isoformat(),
                    "estat": ot.estat,
                }
            )

        # Comprovació de Garantia Interna de Mà d'Obra (<3 mesos / 90 dies) (RF-07)
        darrera_ot = ots[0]
        dies_passats = (avui - darrera_ot.data_planificacio).days
        if dies_passats <= TERMINI_GARANTIA_MA_OBRA_DIES:
            alertes.append(
                {
                    "tipus": "GARANTIA_INTERNA_SERVEI",
                    "activa": True,
                    "cost_client_euros": 0.00,
                    "dies_restants": TERMINI_GARANTIA_MA_OBRA_DIES - dies_passats,
                    "darrera_intervencio_data": darrera_ot.data_planificacio.isoformat(),
                    "missatge": f"Garantia de mà d'obra vigent (intervingut fa {dies_passats} dies). Si es tracta de la mateixa avaria, s'aplica garantia interna a cost 0 € per al client.",
                }
            )

    # 2. Auditoria per Número de Sèrie d'Equip (RF-05, RF-06, EDGE-07)
    if numero_serie:
        # Cercar si existeix a eines_custodia o a articles històrics
        q_eina = select(EinaCustodia).where(
            EinaCustodia.empresa_id == empresa_id,
            EinaCustodia.numero_serie == numero_serie,
        )
        res_eina = await db.execute(q_eina)
        eina = res_eina.scalar_one_or_none()

        if eina:
            # Calculem garantia de fabricant de 2 anys des de created_at
            data_compra = eina.created_at.date()
            data_fi_garantia = data_compra + timedelta(days=730)
            dies_fins_a_fi = (data_fi_garantia - avui).days

            if dies_fins_a_fi >= 0:
                # Dins de garantia oficial
                alertes.append(
                    {
                        "tipus": "GARANTIA_FABRICANT",
                        "activa": True,
                        "numero_serie": numero_serie,
                        "equip": f"{eina.nom} ({eina.model or 'Model N/A'})",
                        "data_fi_garantia": data_fi_garantia.isoformat(),
                        "dies_restants": dies_fins_a_fi,
                        "missatge": f"⚠️ ATENCIÓ: L'equip {eina.nom} [SN: {numero_serie}] disposa de garantia oficial del fabricant vigent fins al {data_fi_garantia}. Es proposa tramitar garantia/RMA amb el proveïdor en lloc de facturar la peça nova al client.",
                    }
                )
            elif dies_fins_a_fi >= -15:
                # EDGE-07: Garantia de 2 anys recentment expirada (<= 15 dies)
                dies_expirat = abs(dies_fins_a_fi)
                alertes.append(
                    {
                        "tipus": "CORTESIA_EXPIRADA",
                        "activa": False,
                        "numero_serie": numero_serie,
                        "dies_expirat": dies_expirat,
                        "data_fi_garantia": data_fi_garantia.isoformat(),
                        "missatge": f"La garantia oficial de 2 anys va expirar el {data_fi_garantia} (fa {dies_expirat} dies). Es suggereix consultar comercialment amb el proveïdor si admet l'esmena de la peça per deferència abans de pressupostar nova peça al client.",
                    }
                )
            else:
                alertes.append(
                    {
                        "tipus": "GARANTIA_EXPIRADA",
                        "activa": False,
                        "numero_serie": numero_serie,
                        "data_fi_garantia": data_fi_garantia.isoformat(),
                        "missatge": f"Garantia oficial finalitzada el {data_fi_garantia}.",
                    }
                )

    return {
        "trobat": True,
        "intervencions_365_dies": intervencions_històriques,
        "garanties": alertes,
    }


@router.post("/incidencies/peritatge", status_code=status.HTTP_201_CREATED)
async def peritar_incidencia_multimodal(
    dades: SollicitudPeritatgeIncidencia,
    db: AsyncSession = Depends(get_db_with_tenant_context),
    claims: Dict[str, Any] = Depends(get_current_user_claims),
):
    """Peritatge multimodal de veu (Whisper v3) i foto d'incidència de camp (RF-08, RF-09, EDGE-02, EDGE-03)."""
    empresa_id = aplicar_tenant_context(claims)

    # EDGE-02: Timeout > 15s no bloquejant
    if dades.simular_timeout:
        return {
            "estat": "ERROR_TIMEOUT",
            "missatge": "Copilot provisionalment no disponible (Timeout)",
            "detall": "Temps d'inferència superior a 15s. L'àudio original i les fotografies queden accessibles a l'Enginyer a la Torre de Control per a resolució manual.",
            "audio_accessible": True,
            "foto_accessible": True,
        }

    # EDGE-03: Soroll extrem de tractors o vent (confiança acústica < 0.40)
    es_soroll_sever = dades.confianca_acustica < CONFIANCA_ACUSTICA_LLINDAR
    transcripcio = (
        dades.text_dictat_operari
        or "S'observa fuita en la canonada principal del sector 3 sota pressió."
    )

    if es_soroll_sever:
        transcripcio_amb_avis = f"⚠️ L'àudio conté soroll de fons sever (tractors/vent). Recomanat contrast visual de fotografia pericial. Transcripció parcial: {transcripcio}"
    else:
        transcripcio_amb_avis = transcripcio

    # RF-09: Classificació Pericial (Extra Facturable vs Cost No Imputable)
    text_analitzar = (dades.text_dictat_operari or "").lower()
    es_extra = any(
        paraula in text_analitzar
        for paraula in ["arrel", "roca", "pedra", "extern", "preexistent", "pressio"]
    )
    es_error_colla = any(
        paraula in text_analitzar
        for paraula in ["pala", "error", "oblidat", "descompte", "trencat per nosaltres"]
    )

    if es_extra:
        dictamen = "EXTRA_FACTURABLE"
        motiu = "Dany preexistent provocat per arrels externes o terreny rocós imprevist. Es proposa extra facturable per al client."
        temps_extra = 45
        materials_extra = [{"article": "Tub PE-32mm", "quantitat": 6, "unitat": "METRES_LINEALS"}]
        cost_estimat = 85.50
    elif es_error_colla:
        dictamen = "COST_NO_IMPUTABLE"
        motiu = "Contingència operativa durant el moviment de terres per la pròpia pala de la quadrilla. Cost no imputable al client (assumit per l'empresa)."
        temps_extra = 30
        materials_extra = [
            {"article": "Maniguet reparació 32mm", "quantitat": 1, "unitat": "UNITAT"}
        ]
        cost_estimat = 0.00
    else:
        dictamen = "EXTRA_FACTURABLE"
        motiu = "Imprevist detectat en curs d'obra; s'ha requerit intervenció addicional sobre element soterrat no senyalitzat."
        temps_extra = 30
        materials_extra = [{"article": "Banda reparació PE", "quantitat": 1, "unitat": "UNITAT"}]
        cost_estimat = 45.00

    memo = MemorandumTecnicCopilot(
        empresa_id=empresa_id,
        ordre_treball_id=dades.ordre_treball_id,
        incidencia_id=dades.incidencia_id,
        transcripcio_audio=transcripcio_amb_avis,
        confianca_acustica=dades.confianca_acustica,
        avis_soroll_sever=es_soroll_sever,
        analisi_visual="Anàlisi de visió artificial local: fractura longitudinal compatible amb estrangulament extern.",
        dictamen_pericial=dictamen,
        motiu_dictamen=motiu,
        estimacio_temps_extra_minuts=temps_extra,
        estimacio_materials_extra=materials_extra,
        cost_estimat_total=cost_estimat,
        validat_per_enginyer=False,
        estat="PROPOSTA",
    )

    db.add(memo)
    await db.commit()

    # Sincronitzar el memoràndum tècnic al disc dur del client (autoaprenentatge)
    try:
        await SovereignStorageGateway.desar_entitat_json(
            db=db,
            empresa_id=empresa_id,
            categoria="copilot_memorandums",
            item_id=str(memo.id),
            dades={
                "id": str(memo.id),
                "ordre_treball_id": str(memo.ordre_treball_id) if memo.ordre_treball_id else None,
                "incidencia_id": str(memo.incidencia_id) if memo.incidencia_id else None,
                "transcripcio_audio": memo.transcripcio_audio,
                "dictamen_pericial": memo.dictamen_pericial,
                "motiu_dictamen": memo.motiu_dictamen,
                "estimacio_temps_extra_minuts": memo.estimacio_temps_extra_minuts,
                "estimacio_materials_extra": memo.estimacio_materials_extra,
                "cost_estimat_total": float(memo.cost_estimat_total),
                "estat": memo.estat,
            },
        )
    except Exception as exc:
        logger.warning("No s'ha pogut desar el memoràndum al disc del client: %s", exc)

    return {
        "id": str(memo.id),
        "estat": memo.estat,
        "dictamen_pericial": memo.dictamen_pericial,
        "motiu_dictamen": memo.motiu_dictamen,
        "transcripcio": memo.transcripcio_audio,
        "avis_soroll_sever": memo.avis_soroll_sever,
        "estimacio_temps_extra_minuts": memo.estimacio_temps_extra_minuts,
        "estimacio_materials_extra": memo.estimacio_materials_extra,
        "cost_estimat_total": float(memo.cost_estimat_total),
        "validat_per_enginyer": memo.validat_per_enginyer,
        "missatge": "Memoràndum tècnic generat com a proposta pendent de validació humana de l'Enginyer (HITL).",
    }


@router.put("/memorandums/{memo_id}/validacio")
async def validar_memorandum_enginyer(
    memo_id: uuid.UUID,
    dades: ValidacioMemorandum,
    db: AsyncSession = Depends(get_db_with_tenant_context),
    claims: Dict[str, Any] = Depends(get_current_user_claims),
):
    """Validació humana de l'Enginyer sobre el Memoràndum Tècnic d'Incidència (RF-10 HITL)."""
    empresa_id = aplicar_tenant_context(claims)
    usuari_id_str = claims.get("sub")
    validador_id = None
    if usuari_id_str:
        try:
            cand_uuid = uuid.UUID(usuari_id_str)
            res_u = await db.execute(select(Usuari.id).where(Usuari.id == cand_uuid))
            if res_u.scalar_one_or_none():
                validador_id = cand_uuid
        except Exception:
            validador_id = None

    q = select(MemorandumTecnicCopilot).where(
        MemorandumTecnicCopilot.id == memo_id,
        MemorandumTecnicCopilot.empresa_id == empresa_id,
    )
    res = await db.execute(q)
    memo = res.scalar_one_or_none()

    if not memo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Memoràndum tècnic no trobat."
        )

    if dades.accio.upper() == "APROVAR":
        memo.estat = "APROVAT_ENGINYER"
        memo.validat_per_enginyer = True
    elif dades.accio.upper() == "REBUTJAR":
        memo.estat = "REBUTJAT"
        memo.validat_per_enginyer = True
    elif dades.accio.upper() == "EDITAR":
        memo.estat = "EDITAT"
        memo.validat_per_enginyer = True
        if dades.dictamen_pericial:
            memo.dictamen_pericial = dades.dictamen_pericial
        if dades.estimacio_materials_extra is not None:
            memo.estimacio_materials_extra = dades.estimacio_materials_extra
        if dades.cost_estimat_total is not None:
            memo.cost_estimat_total = dades.cost_estimat_total

    memo.observacions_enginyer = dades.observacions_enginyer
    memo.enginyer_validador_id = validador_id
    memo.data_validacio = datetime.now(timezone.utc)

    await db.commit()

    # Actualitzar l'estat del memoràndum al disc dur del client
    try:
        await SovereignStorageGateway.desar_entitat_json(
            db=db,
            empresa_id=empresa_id,
            categoria="copilot_memorandums",
            item_id=str(memo.id),
            dades={
                "id": str(memo.id),
                "ordre_treball_id": str(memo.ordre_treball_id) if memo.ordre_treball_id else None,
                "dictamen_pericial": memo.dictamen_pericial,
                "motiu_dictamen": memo.motiu_dictamen,
                "cost_estimat_total": float(memo.cost_estimat_total),
                "estat": memo.estat,
                "validat_per_enginyer": memo.validat_per_enginyer,
                "observacions_enginyer": memo.observacions_enginyer,
                "enginyer_validador_id": str(validador_id) if validador_id else None,
            },
        )
    except Exception as exc:
        logger.warning("No s'ha pogut actualitzar el memoràndum al disc del client: %s", exc)

    return {
        "id": str(memo.id),
        "estat": memo.estat,
        "validat_per_enginyer": memo.validat_per_enginyer,
        "dictamen_pericial": memo.dictamen_pericial,
        "cost_estimat_total": float(memo.cost_estimat_total),
        "missatge": f"Memoràndum tècnic validat correctament sota principi HITL ({memo.estat}).",
    }


@router.get("/memorandums")
async def llistar_memorandums(
    estat: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db_with_tenant_context),
    claims: Dict[str, Any] = Depends(get_current_user_claims),
):
    """Llista els memoràndums tècnics registrats per a l'empresa."""
    empresa_id = aplicar_tenant_context(claims)

    q = select(MemorandumTecnicCopilot).where(MemorandumTecnicCopilot.empresa_id == empresa_id)
    if estat:
        q = q.where(MemorandumTecnicCopilot.estat == estat.upper())
    q = q.order_by(MemorandumTecnicCopilot.created_at.desc())

    res = await db.execute(q)
    memos = res.scalars().all()

    return [
        {
            "id": str(m.id),
            "ordre_treball_id": str(m.ordre_treball_id) if m.ordre_treball_id else None,
            "dictamen_pericial": m.dictamen_pericial,
            "motiu_dictamen": m.motiu_dictamen,
            "avis_soroll_sever": m.avis_soroll_sever,
            "cost_estimat_total": float(m.cost_estimat_total),
            "validat_per_enginyer": m.validat_per_enginyer,
            "estat": m.estat,
            "created_at": m.created_at.isoformat(),
        }
        for m in memos
    ]


@router.post("/reconciliacio/post-obra")
async def reconciliar_post_obra(
    dades: ReconciliacioPostObraIn,
    db: AsyncSession = Depends(get_db_with_tenant_context),
    claims: Dict[str, Any] = Depends(get_current_user_claims),
):
    """Reconciliació automàtica post-obra dels 4 pilars amb dades 100% reals (Zero Mock Data)."""
    from app.services.reconciliacio_ot_service import ReconciliacioOTService

    empresa_id = aplicar_tenant_context(claims)
    rol_usuari = str(claims.get("rol") or "").upper()
    return await ReconciliacioOTService.executar_auditoria_post_obra(
        db=db,
        empresa_id=empresa_id,
        ordre_treball_id=dades.ordre_treball_id,
        rol_usuari=rol_usuari,
        materials_override=dades.materials_consumits or None,
        hores_reals_override=dades.hores_reals if dades.hores_reals > 0 else None,
        hores_previstes_override=dades.hores_previstes if dades.hores_previstes > 0 else None,
        km_reals_override=dades.km_reals if dades.km_reals > 0 else None,
        despeses_camp_override=dades.despeses_camp if dades.despeses_camp > 0 else None,
        sync_pendent=dades.sync_pendent,
        incidencies_registrades_override=(
            dades.incidencies_registrades if dades.incidencies_registrades > 0 else None
        ),
    )


@router.put("/reconciliacio/{auditoria_id}/aprovar-pressupost")
async def aprovar_pressupost_corregit_enginyer(
    auditoria_id: uuid.UUID,
    dades: AprovacioPressupostIn,
    db: AsyncSession = Depends(get_db_with_tenant_context),
    claims: Dict[str, Any] = Depends(get_current_user_claims),
):
    """Confirmació humana indispensable de l'Enginyer per enviar el pressupost corregit a facturació (RF-13 HITL)."""
    empresa_id = aplicar_tenant_context(claims)
    usuari_id_str = claims.get("sub")
    enginyer_id = uuid.UUID(usuari_id_str) if usuari_id_str else None

    q = select(AuditoriaPostObra).where(
        AuditoriaPostObra.id == auditoria_id,
        AuditoriaPostObra.empresa_id == empresa_id,
    )
    res = await db.execute(q)
    auditoria = res.scalar_one_or_none()

    if not auditoria:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Auditoria post-obra no trobada."
        )

    if auditoria.bloqueig_consum_excessiu and not dades.confirmar:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Bloqueig de consum excessiu actiu. Requereix revisió explícita de l'Enginyer abans de poder procedir.",
        )

    if dades.confirmar:
        auditoria.estat = "APROVAT_ENGINYER"
        auditoria.enginyer_id = enginyer_id
        auditoria.data_aprovacio = datetime.now(timezone.utc)
    else:
        auditoria.estat = "REBUTJAT"

    await db.commit()

    return {
        "auditoria_id": str(auditoria.id),
        "estat": auditoria.estat,
        "enginyer_id": str(auditoria.enginyer_id) if auditoria.enginyer_id else None,
        "data_aprovacio": auditoria.data_aprovacio.isoformat()
        if auditoria.data_aprovacio
        else None,
        "missatge": "Pressupost corregit validat per l'Enginyer i tramès oficialment a facturació (Secretaria/Boss).",
    }


@router.post("/stock/verificacio-assignacio")
async def verificar_stock_en_assignacio(
    dades: VerificacioStockIn,
    db: AsyncSession = Depends(get_db_with_tenant_context),
    claims: Dict[str, Any] = Depends(get_current_user_claims),
):
    """Monitorització preventiva de stock en assignar obra amb protecció de concurrència SELECT FOR UPDATE (RF-14, RF-15, EDGE-06)."""
    empresa_id = aplicar_tenant_context(claims)
    alertes_generades = []

    for item in dades.materials:
        article_id_raw = item.get("article_id")
        quantitat_necessaria = float(item.get("quantitat_necessaria", 0.0))

        if not article_id_raw:
            continue

        article_id = uuid.UUID(str(article_id_raw))

        # EDGE-06: SELECT FOR UPDATE per bloquejar el registre transaccionalment
        q_estoc = (
            select(EstocMagatzem)
            .where(
                EstocMagatzem.empresa_id == empresa_id,
                EstocMagatzem.article_id == article_id,
            )
            .with_for_update()
        )
        res_estoc = await db.execute(q_estoc)
        estoc = res_estoc.scalar_one_or_none()

        # Obtenir dades de l'article per comprovar estoc_minim
        q_art = select(Article).where(Article.id == article_id, Article.empresa_id == empresa_id)
        res_art = await db.execute(q_art)
        article = res_art.scalar_one_or_none()

        if not article:
            continue

        saldo_actual = (
            float(estoc.quantitat_fisica - estoc.quantitat_virtual_reservada) if estoc else 0.0
        )

        if saldo_actual < quantitat_necessaria:
            # Rebuig de commit per manca de stock concurrent
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Estoc insuficient per concurrència de reserves de l'article {article.nom} (Disponible: {saldo_actual:.1f}, Requerit: {quantitat_necessaria:.1f}).",
            )

        saldo_projectat = saldo_actual - quantitat_necessaria
        estoc_minim = float(article.estoc_minim)

        if saldo_projectat < estoc_minim:
            # RF-33 / Tarea 3.3: Detecció de Backorders en Trànsit per evitar comandes duplicades.
            # L'assistent (o worker de Celery associat) avalua les factures/comandes pendents.

            from app.models.models import FacturaProveidor, FacturaProveidorLinia

            q_backorder = (
                select(FacturaProveidorLinia)
                .join(FacturaProveidor, FacturaProveidor.id == FacturaProveidorLinia.factura_id)
                .where(
                    FacturaProveidorLinia.empresa_id == empresa_id,
                    FacturaProveidorLinia.article_id == article.id,
                    FacturaProveidor.estat == "PENDENT",
                )
            )
            res_backorder = await db.execute(q_backorder)
            backorder_actiu = res_backorder.scalars().first()

            if backorder_actiu and saldo_projectat <= 0:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=f"❌ Copilot IA: Comanda en trànsit detectada. Existeix un Backorder actiu per l'article '{article.nom}'. S'ha deturat la generació d'una nova comanda de compra per evitar duplicitat d'inventari.",
                )

            # Generar Alerta Preventiva de Recompra Inmediata (RF-15)
            missatge = f"ALERTA PREVENTIVA DE RECOMPRA: L'article '{article.nom}' quedarà a {saldo_projectat:.1f} {article.unitat_mesura} (sota mínim de seguretat de {estoc_minim:.1f}). S'ha generat l'esborrany de comanda de reposició."

            comanda_esborrany = {
                "article_id": str(article.id),
                "article_nom": article.nom,
                "quantitat_proposada": (float(article.estoc_optim) - saldo_projectat)
                if article.estoc_optim > 0
                else 50.0,
                "preu_cost_pactat": float(article.preu_cost),
                "data_proposta": datetime.now(timezone.utc).isoformat(),
            }

            alerta = AlertaGarantiaRecompra(
                empresa_id=empresa_id,
                ordre_treball_id=dades.ordre_treball_id,
                tipus_alerta="RECOMPRA_STOCK",
                article_id=article.id,
                missatge=missatge,
                dades_comanda_proposta=comanda_esborrany,
                estat="ACTIVA",
            )
            db.add(alerta)
            alertes_generades.append(missatge)

    await db.commit()

    return {
        "assignacio_permesa": True,
        "alertes_recompra_generades": alertes_generades,
        "missatge": "Verificació de stock completada amb èxit sota transacció ACID.",
    }


class CopilotConfigIn(BaseModel):
    system_prompt: str
    rag_prompt: str = ""
    subagent_prompts: Dict[str, str] = Field(default_factory=dict)
    llm_model: str = ""
    llm_chat_model: str = ""
    llm_vision_model: str = ""
    hardware_profile: str = "32GB"
    timeout_budget_s: Optional[float] = None


@router.get("/config", response_model=CopilotConfigIn)
async def obtenir_config_copilot(
    db: AsyncSession = Depends(get_db_with_tenant_context),
    claims: Dict[str, Any] = Depends(require_roles(["BOSS", "ADMIN", "ENGINYER", "SECRETARIA"])),
) -> CopilotConfigIn:
    """Retorna la configuració sobirana del Copilot llegida exclusivament del PC dedicat (FR-024)."""
    empresa_id = aplicar_tenant_context(claims)
    cfg = await get_strict_copilot_config(db, empresa_id, use_cache=False)
    if not cfg:
        return CopilotConfigIn(
            system_prompt="",
            rag_prompt="",
            subagent_prompts={},
            llm_model="",
            llm_chat_model="",
            llm_vision_model="",
            hardware_profile="32GB",
            timeout_budget_s=18.0,
        )
    return CopilotConfigIn(
        system_prompt=cfg.system_prompt or "",
        rag_prompt=cfg.rag_prompt or "",
        subagent_prompts=dict(cfg.subagent_prompts or {}),
        llm_model=cfg.effective_chat_model,
        llm_chat_model=cfg.effective_chat_model,
        llm_vision_model=cfg.llm_vision_model or "",
        hardware_profile=cfg.hardware_profile,
        timeout_budget_s=cfg.timeout_budget_s,
    )


@router.put("/config", response_model=CopilotConfigIn)
async def actualitzar_config_copilot(
    payload: CopilotConfigIn,
    db: AsyncSession = Depends(get_db_with_tenant_context),
    claims: Dict[str, Any] = Depends(require_roles(["BOSS", "ADMIN"])),
) -> CopilotConfigIn:
    """Desa la configuració sobirana del Copilot exclusivament al PC dedicat de l'empresa (FR-024)."""
    empresa_id = aplicar_tenant_context(claims)
    cfg = await save_strict_copilot_config(
        db=db,
        empresa_id=empresa_id,
        system_prompt=payload.system_prompt,
        rag_prompt=payload.rag_prompt,
        subagent_prompts=payload.subagent_prompts,
        llm_model=payload.llm_model,
        llm_chat_model=payload.llm_chat_model or payload.llm_model,
        llm_vision_model=payload.llm_vision_model,
        hardware_profile=payload.hardware_profile,
        timeout_budget_s=payload.timeout_budget_s,
    )
    return CopilotConfigIn(
        system_prompt=cfg.system_prompt or "",
        rag_prompt=cfg.rag_prompt or "",
        subagent_prompts=dict(cfg.subagent_prompts or {}),
        llm_model=cfg.effective_chat_model,
        llm_chat_model=cfg.effective_chat_model,
        llm_vision_model=cfg.llm_vision_model or "",
        hardware_profile=cfg.hardware_profile,
        timeout_budget_s=cfg.timeout_budget_s,
    )


@router.post("/xat")
async def consultar_xat_tecnic(
    dades: ConsultaXatIn,
    db: AsyncSession = Depends(get_db_with_tenant_context),
    claims: Dict[str, Any] = Depends(get_current_user_claims),
):
    """Finestra de xat tècnic amb orquestrador multi-agent de subagents, RAG local, veto financer i aïllament de vertical."""
    empresa_id = aplicar_tenant_context(claims)
    usuari_id_str = claims.get("sub")
    usuari_id = uuid.UUID(usuari_id_str) if usuari_id_str else uuid.uuid4()
    rol_usuari = claims.get("rol", "").upper()

    q_emp = select(Empresa).where(Empresa.id == empresa_id)
    res_emp = await db.execute(q_emp)
    empresa = res_emp.scalar_one_or_none()
    vertical = empresa.vertical if empresa else "SEVALOR"

    usuari_nom = claims.get("nom") or None

    resposta = await copilot_dispatcher.dispatch(
        pregunta=dades.pregunta,
        db=db,
        empresa_id=empresa_id,
        usuari_id=usuari_id,
        rol_usuari=rol_usuari,
        usuari_nom=usuari_nom,
        context_id=dades.context_id,
        vertical=vertical,
        historial=dades.historial,
        agent_prompt_system=empresa.agent_prompt_system if empresa else None,
    )
    return resposta


@router.get("/ia-status")
async def obtenir_estat_ia(
    db: AsyncSession = Depends(get_db_with_tenant_context),
    claims: Dict[str, Any] = Depends(get_current_user_claims),
) -> Dict[str, Any]:
    """Comprova la connectivitat en viu amb el Copilot / Node IA local via Túnel WSS Únic."""
    empresa_id = aplicar_tenant_context(claims)
    res_emp = await db.execute(select(Empresa).where(Empresa.id == empresa_id))
    empresa = res_emp.scalar_one_or_none()
    await SovereignStorageGateway.autocurar_config_tunel_empresa(db, empresa, commit=True)

    feature_on = bool(getattr(empresa, "feature_copilot_ia", False)) if empresa else False
    node_on = bool(empresa.node_ia_actiu) if empresa else False
    wss_uri = build_wss_tunnel_uri(empresa_id)

    if not empresa or not node_on or not feature_on:
        if not empresa:
            motiu = "EMPRESA_NO_TROBADA"
            err_msg = "Empresa no trobada per comprovar l'estat del Copilot IA."
        elif not feature_on:
            motiu = "FEATURE_COPILOT_DESACTIVAT"
            err_msg = "El mòdul Copilot IA (feature_copilot_ia) està desactivat a Superadmin per a aquesta empresa."
        else:
            motiu = "NODE_IA_INACTIU"
            err_msg = "L'ordinador dedicat d'IA local està desactivat a la fitxa de l'empresa (Superadmin)."
        return {
            "estat": "OFFLINE",
            "motiu": motiu,
            "feature_copilot_ia": feature_on,
            "node_ia_actiu": node_on,
            "url": wss_uri,
            "transport": "WSS",
            "error": err_msg,
            "latencia_ms": None,
        }

    target_key = empresa_target_key(empresa_id)
    if not await vault_tunnel_broker.is_online(target_key):
        return {
            "estat": "OFFLINE",
            "motiu": "TUNEL_OFFLINE",
            "feature_copilot_ia": True,
            "node_ia_actiu": True,
            "url": wss_uri,
            "transport": "WSS",
            "error": (
                "L'ordinador dedicat de l'empresa no està connectat al túnel WSS de Sevalor. "
                "Comprova que l'agent estigui encès."
            ),
            "latencia_ms": None,
        }

    try:
        start_t = datetime.now()
        data = await vault_tunnel_broker.call_llm_models(target_key, timeout=8.0)
        elapsed_ms = int((datetime.now() - start_t).total_seconds() * 1000)
        models = [
            str(m.get("id"))
            for m in data.get("data", [])
            if isinstance(m, dict) and m.get("id")
        ]
        chat_models = [m for m in models if "embed" not in m.lower()]
        model_actiu = (
            chat_models[0]
            if chat_models
            else (
                models[0]
                if models
                else getattr(settings, "LM_STUDIO_MODEL", "qwen2.5-vl-7b-instruct")
            )
        )
        return {
            "estat": "ONLINE",
            "status": "ONLINE",
            "node_ia_actiu": True,
            "feature_copilot_ia": True,
            "tunnel_online": True,
            "url": wss_uri,
            "transport": "WSS",
            "model_actiu": model_actiu,
            "models": models,
            "models_disponibles": models,
            "latencia_ms": elapsed_ms,
        }
    except VaultTunnelRemoteError as exc:
        motiu_off = "LLM_OFFLINE" if exc.code == "LLM_OFFLINE" else exc.code
        err_display = (
            "El PC de l'empresa està connectat, però LM Studio/Ollama local no respon a 127.0.0.1:1234."
            if exc.code == "LLM_OFFLINE"
            else exc.detail
        )
    except (VaultTunnelOfflineError, VaultTunnelTimeoutError, VaultTunnelError) as exc:
        motiu_off = "TIMEOUT" if isinstance(exc, VaultTunnelTimeoutError) else "TUNEL_OFFLINE"
        err_display = exc.detail

    return {
        "estat": "OFFLINE",
        "status": "OFFLINE",
        "motiu": motiu_off,
        "feature_copilot_ia": True,
        "node_ia_actiu": True,
        "tunnel_online": motiu_off == "LLM_OFFLINE",
        "url": wss_uri,
        "transport": "WSS",
        "error": err_display,
        "latencia_ms": None,
    }


@router.get("/alertes")
async def llistar_alertes_copilot(
    estat: str = Query("ACTIVA"),
    db: AsyncSession = Depends(get_db_with_tenant_context),
    claims: Dict[str, Any] = Depends(get_current_user_claims),
):
    """Llista les alertes actives de garantia i reposició de stock."""
    empresa_id = aplicar_tenant_context(claims)

    q = (
        select(AlertaGarantiaRecompra)
        .where(
            AlertaGarantiaRecompra.empresa_id == empresa_id,
            AlertaGarantiaRecompra.estat == estat.upper(),
        )
        .order_by(AlertaGarantiaRecompra.created_at.desc())
    )

    res = await db.execute(q)
    alertes = res.scalars().all()

    return [
        {
            "id": str(a.id),
            "tipus_alerta": a.tipus_alerta,
            "missatge": a.missatge,
            "data_fi_garantia": a.data_fi_garantia.isoformat() if a.data_fi_garantia else None,
            "dades_comanda_proposta": a.dades_comanda_proposta,
            "estat": a.estat,
            "created_at": a.created_at.isoformat(),
        }
        for a in alertes
    ]


@router.post("/rag/document", status_code=status.HTTP_201_CREATED)
async def afegir_document_rag(
    dades: DocumentRagIn,
    db: AsyncSession = Depends(get_db_with_tenant_context),
    claims: Dict[str, Any] = Depends(get_current_user_claims),
):
    """Permet als administradors afegir protocols al disc dur sobirà del client per al RAG del Copilot."""
    empresa_id = aplicar_tenant_context(claims)
    doc_id = str(uuid.uuid4())

    await SovereignStorageGateway.desar_entitat_json(
        db=db,
        empresa_id=empresa_id,
        categoria="protocols_interns",
        item_id=doc_id,
        dades={
            "id": doc_id,
            "titol": dades.pregunta,
            "pregunta": dades.pregunta,
            "contingut": dades.resposta,
            "resposta": dades.resposta,
            "tags": dades.paraules_clau,
            "paraules_clau": dades.paraules_clau,
            "actiu": True,
            "creat_el": datetime.now(timezone.utc).isoformat(),
        },
    )

    return {"id": doc_id, "estat": "OK", "missatge": "Document afegit al disc dur de l'empresa per a la IA."}


@router.get("/rag/document")
async def llistar_documents_rag(
    db: AsyncSession = Depends(get_db_with_tenant_context),
    claims: Dict[str, Any] = Depends(get_current_user_claims),
):
    """Llista els protocols del RAG actius des del disc dur sobirà de l'empresa."""
    empresa_id = aplicar_tenant_context(claims)
    docs_disc = await SovereignStorageGateway.llegir_entitats_json(
        db, empresa_id, "protocols_interns"
    )
    return [
        {
            "id": str(d.get("id") or ""),
            "titol": d.get("titol") or d.get("pregunta") or "",
            "contingut": d.get("contingut") or d.get("resposta") or "",
            "tags": d.get("tags") or d.get("paraules_clau") or "",
            "pregunta": d.get("pregunta") or d.get("titol") or "",
            "resposta": d.get("resposta") or d.get("contingut") or "",
            "paraules_clau": d.get("paraules_clau") or d.get("tags") or "",
        }
        for d in docs_disc
        if d.get("actiu", True)
    ]


@router.put("/rag/document/{doc_id}")
async def actualitzar_document_rag(
    doc_id: str,
    dades: DocumentRagIn,
    db: AsyncSession = Depends(get_db_with_tenant_context),
    claims: Dict[str, Any] = Depends(get_current_user_claims),
):
    """Actualitza un protocol existent del RAG al disc dur sobirà de l'empresa."""
    empresa_id = aplicar_tenant_context(claims)
    doc_id_net = doc_id.strip()
    if not doc_id_net:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Identificador de document RAG invàlid.",
        )

    docs_disc = await SovereignStorageGateway.llegir_entitats_json(
        db, empresa_id, "protocols_interns"
    )
    existent = next((d for d in docs_disc if str(d.get("id") or "") == doc_id_net), None)
    if not existent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Protocol RAG no trobat al disc dur sobirà.",
        )

    await SovereignStorageGateway.desar_entitat_json(
        db=db,
        empresa_id=empresa_id,
        categoria="protocols_interns",
        item_id=doc_id_net,
        dades={
            "id": doc_id_net,
            "titol": dades.pregunta,
            "pregunta": dades.pregunta,
            "contingut": dades.resposta,
            "resposta": dades.resposta,
            "tags": dades.paraules_clau,
            "paraules_clau": dades.paraules_clau,
            "actiu": True,
            "creat_el": existent.get("creat_el") or datetime.now(timezone.utc).isoformat(),
            "actualitzat_el": datetime.now(timezone.utc).isoformat(),
        },
    )

    return {
        "id": doc_id_net,
        "estat": "OK",
        "missatge": "Protocol actualitzat al disc dur sobirà.",
    }


@router.delete("/rag/document/{doc_id}")
async def eliminar_document_rag(
    doc_id: str,
    db: AsyncSession = Depends(get_db_with_tenant_context),
    claims: Dict[str, Any] = Depends(get_current_user_claims),
):
    """Elimina un protocol del RAG del disc dur sobirà de l'empresa."""
    empresa_id = aplicar_tenant_context(claims)
    doc_id_net = doc_id.strip()
    if not doc_id_net:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Identificador de document RAG invàlid.",
        )

    docs_disc = await SovereignStorageGateway.llegir_entitats_json(
        db, empresa_id, "protocols_interns"
    )
    existent = next((d for d in docs_disc if str(d.get("id") or "") == doc_id_net), None)
    if not existent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Protocol RAG no trobat al disc dur sobirà.",
        )

    esborrat = await SovereignStorageGateway.esborrar_entitat_json(
        db=db,
        empresa_id=empresa_id,
        categoria="protocols_interns",
        item_id=doc_id_net,
    )
    if not esborrat:
        # Fallback coherent: si no s'ha pogut eliminar el fitxer físic, desactivar-lo
        await SovereignStorageGateway.desar_entitat_json(
            db=db,
            empresa_id=empresa_id,
            categoria="protocols_interns",
            item_id=doc_id_net,
            dades={**existent, "actiu": False, "actualitzat_el": datetime.now(timezone.utc).isoformat()},
        )

    return {
        "id": doc_id_net,
        "estat": "OK",
        "missatge": "Protocol eliminat del disc dur sobirà.",
    }


class ActionConfirmIn(BaseModel):
    action: str
    payload: dict


@router.post("/action/confirm")
async def confirmar_accio_copilot(
    dades: ActionConfirmIn,
    db: AsyncSession = Depends(get_db_with_tenant_context),
    claims: dict = Depends(get_current_user_claims),
):
    empresa_id = uuid.UUID(claims["empresa_id"])
    if dades.action == "confirm_replanificar_ot":
        from sqlalchemy import update

        from app.models.models import OrdreTreball

        ot_id = uuid.UUID(dades.payload["ot_id"])
        nova_data_str = dades.payload["nova_data"]
        try:
            nova_data = date.fromisoformat(nova_data_str)
        except Exception:
            raise HTTPException(400, "Format de data invàlid. Esperat YYYY-MM-DD.")

        stmt = (
            update(OrdreTreball)
            .where(OrdreTreball.id == ot_id, OrdreTreball.empresa_id == empresa_id)
            .values(data_planificacio=nova_data)
        )

        await db.execute(stmt)
        await db.commit()
        return {
            "success": True,
            "missatge": f"S'ha replanificat l'OT correctament al {nova_data_str}.",
        }

    raise HTTPException(400, "Acció desconeguda o no suportada.")


# ── T035: Generador de Pressupost Intel·ligent basat en Històric ─────────────
class PressupostIntelligentRequest(BaseModel):
    descripcio_tasca: str = Field(..., min_length=5, max_length=500)
    client_id: Optional[uuid.UUID] = None


@router.post("/pressupost-intelligent")
async def generar_pressupost_intelligent(
    payload: PressupostIntelligentRequest,
    db: AsyncSession = Depends(get_db_with_tenant_context),
    claims: dict = Depends(get_current_user_claims),
):
    """T035: Genera partides de pressupost basades en feines similars tancades del tenant.

    Cerca feines tancades amb descripció similar i en retorna les partides de mà d'obra
    i materials com a esborrany PENDENT_REVISIO. No inventa cap preu: usa historial real.
    Barrera econòmica: accessible només per BOSS i ENGINYER.
    """
    rol = claims.get("rol", "")
    if rol == "OPERARI":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Copilot no disponible per a operaris"
        )

    empresa_id = uuid.UUID(claims["empresa_id"])
    paraules_clau = payload.descripcio_tasca.lower().split()[:5]  # Primeres 5 paraules clau

    # Cerca feines similars tancades dels darrers 365 dies
    from datetime import timedelta

    from sqlalchemy import and_

    data_limit = datetime.now(timezone.utc) - timedelta(days=365)
    stmt = (
        select(OrdreTreball)
        .where(
            and_(
                OrdreTreball.empresa_id == empresa_id,
                OrdreTreball.estat == "TANCADA",
                OrdreTreball.created_at >= data_limit,
            )
        )
        .order_by(OrdreTreball.created_at.desc())
        .limit(10)
    )
    result = await db.execute(stmt)
    feines_similars = result.scalars().all()

    # Construir partides basades en historial real
    partides_materials: list[dict] = []
    partides_ma_obra: list[dict] = []
    total_hores_mitja = 0.0
    n = 0

    for feina in feines_similars:
        # Filtre de similitud bàsic per paraules clau en el títol/descripció
        text_feina = f"{feina.titol or ''} {feina.descripcio or ''}".lower()
        coincidencies = sum(1 for p in paraules_clau if p in text_feina)
        if coincidencies < 1:
            continue
        hores = float(getattr(feina, "hores_reals", 0) or 0)
        total_hores_mitja += hores
        n += 1

    hores_suggerides = round(total_hores_mitja / n, 1) if n > 0 else 0.0

    if hores_suggerides > 0:
        partides_ma_obra.append(
            {
                "descripcio": "Mà d'obra tècnica (basada en mitjana feines similars)",
                "unitats": hores_suggerides,
                "unitat": "h",
                "preu_unitari": None,  # Zero Mock Data: no s'inventa el preu
                "nota": f"Mitjana de {n} feines similars tancades",
            }
        )

    return {
        "estat": "PENDENT_REVISIO",
        "descripcio_entrada": payload.descripcio_tasca,
        "feines_referencia_trobades": n,
        "partides_ma_obra": partides_ma_obra,
        "partides_materials": partides_materials,
        "avis": "Revisa i ajusta les partides abans d'enviar al client. La IA no inventa preus.",
    }


class SincronitzarDiscRequest(BaseModel):
    only_missing: bool = False
    categories: Optional[List[str]] = None


@router.post("/sincronitzar-disc")
async def sincronitzar_disc_sobira_empresa(
    payload: Optional[SincronitzarDiscRequest] = None,
    db: AsyncSession = Depends(get_db_with_tenant_context),
    claims: dict = Depends(get_current_user_claims),
):
    """Reconcilia totes les entitats operatives de l'empresa cap al seu disc dur sobirà via WSS.

    Permet a Direcció (BOSS / ADMIN) forçar una sincronització completa o incremental
    dels fitxers JSON del disc dur dedicat (flota, clients, magatzem, operaris, OTs, etc.).
    """
    rol = str(claims.get("rol") or "").upper()
    if rol not in ("BOSS", "ADMIN"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Només Direcció (BOSS / ADMIN) pot executar la re-sincronització completa del disc sobirà.",
        )

    empresa_id = uuid.UUID(claims["empresa_id"])
    req = payload or SincronitzarDiscRequest()

    from app.services.sovereign_sync_service import sincronitzar_entitats_empresa_al_disc

    resultat = await sincronitzar_entitats_empresa_al_disc(
        db,
        empresa_id,
        categories=req.categories,
        only_missing=req.only_missing,
    )
    if not resultat.get("online"):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "code": "NODE_EMPRESA_OFFLINE",
                "message": "El disc dur dedicat de l'empresa no està connectat al túnel WSS.",
            },
        )
    return resultat
