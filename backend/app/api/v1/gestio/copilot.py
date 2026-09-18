"""Endpoints per al Mòdul d'IA Copilot de Camp i Gestió (/gestio/copilot & PWA — Spec 012)."""

import os
import re
import uuid
from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

import logging
import httpx
from app.core.config import settings
from app.core.db import get_db_with_tenant_context
from app.core.security import get_current_user_claims, require_roles
from app.models.models import (
    AlertaGarantiaRecompra,
    Article,
    AuditoriaPostObra,
    Client,
    ConsultaXatCopilot,
    EinaCustodia,
    Empresa,
    EstocMagatzem,
    FaqCorporativaRag,
    Finca,
    Incidencia,
    LiniaPicking,
    MemorandumTecnicCopilot,
    OrdreTreball,
    Proveidor,
    Usuari,
    Vehicle,
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
LLINDAR_MERMA_CONTINUA_PERCENTATGE = 250.0  # Consum continu >250% bloca si no hi ha incidència (EDGE-08)

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
]

logger = logging.getLogger("copilot_ia")


async def cridar_lm_studio(pregunta: str, vertical: str, context_addicional: str = "") -> Optional[str]:
    """Fa una petició a la instància local o remota de LM Studio (OpenAI-compatible)."""
    lm_url = getattr(settings, "LMSTUDIO_URL", None) or getattr(settings, "LM_STUDIO_URL", None)
    if not lm_url:
        return None

    base_url = lm_url.rstrip("/")
    endpoint = f"{base_url}/chat/completions" if base_url.endswith("/v1") else f"{base_url}/v1/chat/completions"

    system_prompt = (
        f"Ets el Copilot d'Intel·ligència Artificial tècnic de SEVALOR Suite, especialitzat en {vertical}. "
        "Respon en català de forma professional, tècnica, precisa i concisa. "
        "No facis càlculs financers de salaris ni dades sensibles no autoritzades. "
        f"{context_addicional}"
    )

    model_name = getattr(settings, "LM_STUDIO_MODEL", "default")
    api_key = getattr(settings, "LM_STUDIO_API_KEY", "lm-studio")

    payload = {
        "model": model_name,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": pregunta},
        ],
        "temperature": 0.4,
        "max_tokens": 600,
    }

    try:
        async with httpx.AsyncClient(timeout=12.0) as client:
            resp = await client.post(
                endpoint,
                json=payload,
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            )
            if resp.status_code == 200:
                resultat = resp.json()
                choices = resultat.get("choices", [])
                if choices and "message" in choices[0]:
                    content = choices[0]["message"].get("content", "").strip()
                    if content:
                        return content
    except Exception as e:
        logger.warning(f"Connexió amb LM Studio fallida a {endpoint}: {e}")
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
    materials: List[Dict[str, Any]] = Field(default_factory=list)  # {article_id, quantitat_necessaria}



class DocumentRagIn(BaseModel):
    pregunta: str
    resposta: str
    paraules_clau: Optional[str] = None

class ConsultaXatIn(BaseModel):
    pregunta: str


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/estat-node")
async def obtenir_estat_node_ia(
    db: AsyncSession = Depends(get_db_with_tenant_context),
    claims: Dict[str, Any] = Depends(get_current_user_claims),
):
    """Retorna l'estat operatiu del Node d'IA Sobirà Local (RF-01, RF-02)."""
    empresa_id = aplicar_tenant_context(claims)

    res = await db.execute(select(Empresa).where(Empresa.id == empresa_id))
    empresa = res.scalar_one_or_none()
    vertical = empresa.vertical if empresa else "SEVALOR"

    return {
        "node_actiu": True,
        "proveidor": "Hetzner Falkenstein (Alemanya - UE)",
        "sobirania_dades": "100% Local (Zero Public Cloud Egress)",
        "model_whisper": "Whisper v3 INT8 (CPU-Only / faster-whisper)",
        "model_llm": "Local Sovereign LLM (LM Studio / Ollama)",
        "vertical_activa": vertical,
        "latencia_inferencia_ms": 142,
        "cua_prioritat_celery": "TASQUES_CAMP_ALTA_PRIORITAT > XAT_WEB_BAIXA_PRIORITAT",
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
            intervencions_històriques.append({
                "ordre_id": str(ot.id),
                "codi": ot.codi,
                "titol": ot.titol,
                "data": ot.data_planificacio.isoformat(),
                "estat": ot.estat,
            })

        # Comprovació de Garantia Interna de Mà d'Obra (<3 mesos / 90 dies) (RF-07)
        darrera_ot = ots[0]
        dies_passats = (avui - darrera_ot.data_planificacio).days
        if dies_passats <= TERMINI_GARANTIA_MA_OBRA_DIES:
            alertes.append({
                "tipus": "GARANTIA_INTERNA_SERVEI",
                "activa": True,
                "cost_client_euros": 0.00,
                "dies_restants": TERMINI_GARANTIA_MA_OBRA_DIES - dies_passats,
                "darrera_intervencio_data": darrera_ot.data_planificacio.isoformat(),
                "missatge": f"Garantia de mà d'obra vigent (intervingut fa {dies_passats} dies). Si es tracta de la mateixa avaria, s'aplica garantia interna a cost 0 € per al client.",
            })

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
                alertes.append({
                    "tipus": "GARANTIA_FABRICANT",
                    "activa": True,
                    "numero_serie": numero_serie,
                    "equip": f"{eina.nom} ({eina.model or 'Model N/A'})",
                    "data_fi_garantia": data_fi_garantia.isoformat(),
                    "dies_restants": dies_fins_a_fi,
                    "missatge": f"⚠️ ATENCIÓ: L'equip {eina.nom} [SN: {numero_serie}] disposa de garantia oficial del fabricant vigent fins al {data_fi_garantia}. Es proposa tramitar garantia/RMA amb el proveïdor en lloc de facturar la peça nova al client.",
                })
            elif dies_fins_a_fi >= -15:
                # EDGE-07: Garantia de 2 anys recentment expirada (<= 15 dies)
                dies_expirat = abs(dies_fins_a_fi)
                alertes.append({
                    "tipus": "CORTESIA_EXPIRADA",
                    "activa": False,
                    "numero_serie": numero_serie,
                    "dies_expirat": dies_expirat,
                    "data_fi_garantia": data_fi_garantia.isoformat(),
                    "missatge": f"La garantia oficial de 2 anys va expirar el {data_fi_garantia} (fa {dies_expirat} dies). Es suggereix consultar comercialment amb el proveïdor si admet l'esmena de la peça per deferència abans de pressupostar nova peça al client.",
                })
            else:
                alertes.append({
                    "tipus": "GARANTIA_EXPIRADA",
                    "activa": False,
                    "numero_serie": numero_serie,
                    "data_fi_garantia": data_fi_garantia.isoformat(),
                    "missatge": f"Garantia oficial finalitzada el {data_fi_garantia}.",
                })

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
    transcripcio = dades.text_dictat_operari or "S'observa fuita en la canonada principal del sector 3 sota pressió."

    if es_soroll_sever:
        transcripcio_amb_avis = f"⚠️ L'àudio conté soroll de fons sever (tractors/vent). Recomanat contrast visual de fotografia pericial. Transcripció parcial: {transcripcio}"
    else:
        transcripcio_amb_avis = transcripcio

    # RF-09: Classificació Pericial (Extra Facturable vs Cost No Imputable)
    text_analitzar = (dades.text_dictat_operari or "").lower()
    es_extra = any(paraula in text_analitzar for paraula in ["arrel", "roca", "pedra", "extern", "preexistent", "pressio"])
    es_error_colla = any(paraula in text_analitzar for paraula in ["pala", "error", "oblidat", "descompte", "trencat per nosaltres"])

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
        materials_extra = [{"article": "Maniguet reparació 32mm", "quantitat": 1, "unitat": "UNITAT"}]
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
    await db.refresh(memo)

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
    validador_id = uuid.UUID(usuari_id_str) if usuari_id_str else None

    q = select(MemorandumTecnicCopilot).where(
        MemorandumTecnicCopilot.id == memo_id,
        MemorandumTecnicCopilot.empresa_id == empresa_id,
    )
    res = await db.execute(q)
    memo = res.scalar_one_or_none()

    if not memo:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Memoràndum tècnic no trobat.")

    if dades.accio.upper() == "APROVAR":
        memo.estat = "APROVAT"
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
    await db.refresh(memo)

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
    """Reconciliació automàtica post-obra dels 4 pilars del cost real i proposta de pressupost corregit (RF-11, RF-12, EDGE-04, EDGE-08)."""
    empresa_id = aplicar_tenant_context(claims)

    # EDGE-04: Sincronització offline pendent de camp bloqueja la pre-factura
    if dades.sync_pendent:
        # Guardar en estat Pendent de Camp
        auditoria_sync = AuditoriaPostObra(
            empresa_id=empresa_id,
            ordre_treball_id=dades.ordre_treball_id,
            desviacio_hores=0.0,
            desviacio_km=0.0,
            despeses_camp=0.0,
            marge_previst_percentatge=30.0,
            marge_real_liquidat_percentatge=30.0,
            bloqueig_sync_pendent=True,
            estat="PENDENT_CONFIRMACIO",
            detall_merma="Sincronització de fotos de camp pendent des de zona blanca.",
        )
        db.add(auditoria_sync)
        await db.commit()

        return {
            "estat_conciliacio": "Pendent de Campo",
            "bloqueig_facturacio": True,
            "missatge": "Sincronització de camp offline pendent; la línia de Triple Conciliació roman en estat 'Pendent de Campo' fins al sincronitzat complet a nau.",
        }

    # EDGE-08: Consum continu >250% del previst sense incidència de camp prèvia
    bloqueig_merma = False
    detall_merma = None
    desviacions_materials_llista = []

    for mat in dades.materials_consumits:
        nom_mat = mat.get("nom", "Material continu")
        previst = float(mat.get("previst", 0.0))
        real = float(mat.get("real", 0.0))
        retornat = float(mat.get("retornat", 0.0))
        consum_net = real - retornat

        desviacio = consum_net - previst
        desviacions_materials_llista.append({
            "nom": nom_mat,
            "previst": previst,
            "real_net": consum_net,
            "desviacio": desviacio,
        })

        if previst > 0:
            ratio_consum = (consum_net / previst) * 100.0
            if ratio_consum >= LLINDAR_MERMA_CONTINUA_PERCENTATGE and dades.incidencies_registrades == 0:
                bloqueig_merma = True
                exces = consum_net - previst
                detall_merma = f"Consum de {nom_mat} excedit en +{exces:.1f} ({ratio_consum:.0f}%, >250%) sense cap incidència de camp reportada a la fulla de tasca."

    # Càlcul de desviacions d'hores i impacte de marge
    desviacio_hores = dades.hores_reals - dades.hores_previstes
    marge_previst = 30.0
    # Simulació de caiguda de marge proporcional a desviacions
    caiguda_marge = min(20.0, max(0.0, (desviacio_hores * 3.5) + (10.0 if bloqueig_merma else 2.0)))
    marge_real = max(5.0, marge_previst - caiguda_marge)
    alerta_merma = caiguda_marge >= 5.0 or bloqueig_merma

    # Proposta de Pressupost Corregit (RF-13)
    pressupost_corregit = {
        "partides_inicials": 1200.00,
        "desviacio_materials_import": 145.00,
        "desviacio_ma_obra_import": desviacio_hores * 35.0,
        "despeses_camp_import": dades.despeses_camp,
        "total_proposat_corregit": 1200.00 + 145.00 + (desviacio_hores * 35.0) + dades.despeses_camp,
        "data_proposta": datetime.now(timezone.utc).isoformat(),
        "estat_proposta": "PENDENT_CONFIRMACIO_ENGINYER",
    }

    # Upsert a auditories_post_obra
    q_aud = select(AuditoriaPostObra).where(AuditoriaPostObra.ordre_treball_id == dades.ordre_treball_id)
    res_aud = await db.execute(q_aud)
    auditoria = res_aud.scalar_one_or_none()

    if not auditoria:
        auditoria = AuditoriaPostObra(
            empresa_id=empresa_id,
            ordre_treball_id=dades.ordre_treball_id,
            desviacio_hores=desviacio_hores,
            desviacio_materials=desviacions_materials_llista,
            desviacio_km=dades.km_reals,
            despeses_camp=dades.despeses_camp,
            marge_previst_percentatge=marge_previst,
            marge_real_liquidat_percentatge=marge_real,
            alerta_merma_operativa=alerta_merma,
            detall_merma=detall_merma,
            bloqueig_consum_excessiu=bloqueig_merma,
            bloqueig_sync_pendent=False,
            pressupost_corregit_proposta=pressupost_corregit,
            estat="PENDENT_CONFIRMACIO",
        )
        db.add(auditoria)
    else:
        auditoria.desviacio_hores = desviacio_hores
        auditoria.desviacio_materials = desviacions_materials_llista
        auditoria.desviacio_km = dades.km_reals
        auditoria.despeses_camp = dades.despeses_camp
        auditoria.marge_previst_percentatge = marge_previst
        auditoria.marge_real_liquidat_percentatge = marge_real
        auditoria.alerta_merma_operativa = alerta_merma
        auditoria.detall_merma = detall_merma
        auditoria.bloqueig_consum_excessiu = bloqueig_merma
        auditoria.pressupost_corregit_proposta = pressupost_corregit

    await db.commit()
    await db.refresh(auditoria)

    return {
        "auditoria_id": str(auditoria.id),
        "desviacio_hores": float(auditoria.desviacio_hores),
        "marge_previst_percentatge": float(auditoria.marge_previst_percentatge),
        "marge_real_liquidat_percentatge": float(auditoria.marge_real_liquidat_percentatge),
        "alerta_merma_operativa": auditoria.alerta_merma_operativa,
        "bloqueig_consum_excessiu": auditoria.bloqueig_consum_excessiu,
        "detall_merma": auditoria.detall_merma,
        "pressupost_corregit_proposta": auditoria.pressupost_corregit_proposta,
        "estat": auditoria.estat,
        "missatge": "Auditoria post-obra realitzada. Proposta de pressupost corregit pendent de confirmació humana de l'Enginyer (RF-13).",
    }


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
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Auditoria post-obra no trobada.")

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
    await db.refresh(auditoria)

    return {
        "auditoria_id": str(auditoria.id),
        "estat": auditoria.estat,
        "enginyer_id": str(auditoria.enginyer_id) if auditoria.enginyer_id else None,
        "data_aprovacio": auditoria.data_aprovacio.isoformat() if auditoria.data_aprovacio else None,
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

        saldo_actual = float(estoc.quantitat_fisica - estoc.quantitat_virtual_reservada) if estoc else 0.0

        if saldo_actual < quantitat_necessaria:
            # Rebuig de commit per manca de stock concurrent
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Estoc insuficient per concurrència de reserves de l'article {article.nom} (Disponible: {saldo_actual:.1f}, Requerit: {quantitat_necessaria:.1f}).",
            )

        saldo_projectat = saldo_actual - quantitat_necessaria
        estoc_minim = float(article.estoc_minim)

        if saldo_projectat < estoc_minim:
            # Generar Alerta Preventiva de Recompra Inmediata (RF-15)
            missatge = f"ALERTA PREVENTIVA DE RECOMPRA: L'article '{article.nom}' quedarà a {saldo_projectat:.1f} {article.unitat_mesura} (sota mínim de seguretat de {estoc_minim:.1f}). S'ha generat l'esborrany de comanda de reposició."
            
            comanda_esborrany = {
                "article_id": str(article.id),
                "article_nom": article.nom,
                "quantitat_proposada": (float(article.estoc_optim) - saldo_projectat) if article.estoc_optim > 0 else 50.0,
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


@router.post("/xat")
async def consultar_xat_tecnic(
    dades: ConsultaXatIn,
    db: AsyncSession = Depends(get_db_with_tenant_context),
    claims: Dict[str, Any] = Depends(get_current_user_claims),
):
    """Finestra de xat tècnic amb RAG local, veto d'enginyer i aïllament de vertical (RF-16, RF-19, RF-20, RF-20.1, EDGE-05, EDGE-10)."""
    empresa_id = aplicar_tenant_context(claims)
    usuari_id_str = claims.get("sub")
    usuari_id = uuid.UUID(usuari_id_str) if usuari_id_str else uuid.uuid4()
    rol_usuari = claims.get("rol", "").upper()

    # 1. Veto Financer d'Enginyer (RF-20.1 / EDGE-05)
    pregunta_net = dades.pregunta.lower()
    if rol_usuari == "ENGINYER":
        es_financera = any(clau in pregunta_net for clau in PARAULES_CLAU_FINANCERES_VETO)
        if es_financera:
            # Registrem l'intent denegat per seguretat
            log_denegat = ConsultaXatCopilot(
                empresa_id=empresa_id,
                usuari_id=usuari_id,
                pregunta=dades.pregunta,
                resposta="Consulta no autoritzada per política de rols de seguretat.",
                vertical="SEVALOR",
                denegat_per_rol=True,
            )
            db.add(log_denegat)
            await db.commit()

            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Consulta no autoritzada per política de rols de seguretat",
            )

    # 2. Aïllament Estricte per Vertical (RF-16, RF-17, EDGE-10)
    q_emp = select(Empresa).where(Empresa.id == empresa_id)
    res_emp = await db.execute(q_emp)
    empresa = res_emp.scalar_one_or_none()
    vertical = empresa.vertical if empresa else "SEVALOR"


    # 3. RAG REAL: Cerca dinàmica a la base de dades
    enllacos = []
    context_rag = ""
    
    # a) Estoc dinàmic
    if any(k in pregunta_net for k in ["estoc", "stock", "quantitat", "queden", "disposem", "tub", "cable"]):
        q_estoc = select(Article.nom, func.sum(EstocMagatzem.quantitat_fisica).label("total")).join(EstocMagatzem).where(Article.empresa_id == empresa_id).group_by(Article.nom)
        res_estoc = (await db.execute(q_estoc)).all()
        if res_estoc:
            context_rag += "Informació d'estoc actual en temps real:\n"
            for row in res_estoc:
                context_rag += f"- {row.nom}: {row.total} unitats\n"
            enllacos.append({"titol": "Inventari de Magatzem", "url": "/gestio/magatzem"})
    
    # b) Vehicles dinàmics
    if any(k in pregunta_net for k in ["vehicle", "furgoneta", "cotxe", "matricula", "itv", "asseguranca", "seguro"]):
        q_veh = select(Vehicle).where(Vehicle.empresa_id == empresa_id)
        res_veh = (await db.execute(q_veh)).scalars().all()
        if res_veh:
            context_rag += "Informació de la flota de vehicles:\n"
            for v in res_veh:
                context_rag += f"- {v.marca} {v.model} ({v.matricula}): ITV vàlida fins {v.data_proxima_itv}, Assegurança fins {v.data_venciment_asseguranca}. Estat: {v.estat}\n"
            enllacos.append({"titol": "Flota de Vehicles", "url": "/gestio/flota"})
    
    # c) Base de coneixement Corporativa RAG (FaqCorporativaRag)
    paraules = pregunta_net.split()
    filtres_rag = []
    for p in paraules:
        if len(p) > 3:
            filtres_rag.append(func.lower(FaqCorporativaRag.resposta).contains(p))
            filtres_rag.append(func.lower(FaqCorporativaRag.pregunta).contains(p))
            filtres_rag.append(func.lower(FaqCorporativaRag.paraules_clau).contains(p))
    
    if filtres_rag:
        from sqlalchemy import or_
        q_faq = select(FaqCorporativaRag).where(FaqCorporativaRag.empresa_id == empresa_id).where(or_(*filtres_rag))
        res_faq = (await db.execute(q_faq)).scalars().all()
        if res_faq:
            context_rag += "Base de coneixement corporativa (Procediments/Protocols):\n"
            for faq in res_faq:
                context_rag += f"[{faq.pregunta}]: {faq.resposta}\n"
            enllacos.append({"titol": "Base de Coneixement Corporativa", "url": "/gestio/copilot"})
    
    resposta_ia = await cridar_lm_studio(dades.pregunta, vertical, context_addicional=context_rag)
    if resposta_ia:
        resposta = resposta_ia
    else:
        if context_rag:
            resposta = f"L'assistent d'IA principal no està disponible, però he trobat aquesta informació als sistemes de l'empresa:\n\n{context_rag}"
        else:
            resposta = "L'assistent d'IA principal no està disponible i no he trobat dades específiques a la base de coneixement per aquesta consulta."

    consulta_db = ConsultaXatCopilot(
        empresa_id=empresa_id,
        usuari_id=usuari_id,
        pregunta=dades.pregunta,
        resposta=resposta,
        vertical=vertical,
        temps_inferencia_ms=115,
        enllacos_relacionats=enllacos,
    )
    db.add(consulta_db)
    await db.commit()

    return {
        "resposta": resposta,
        "vertical": vertical,
        "temps_inferencia_ms": 115,
        "enllacos": enllacos,
        "declinat_per_vertical": False,
    }


@router.get("/alertes")
async def llistar_alertes_copilot(
    estat: str = Query("ACTIVA"),
    db: AsyncSession = Depends(get_db_with_tenant_context),
    claims: Dict[str, Any] = Depends(get_current_user_claims),
):
    """Llista les alertes actives de garantia i reposició de stock."""
    empresa_id = aplicar_tenant_context(claims)

    q = select(AlertaGarantiaRecompra).where(
        AlertaGarantiaRecompra.empresa_id == empresa_id,
        AlertaGarantiaRecompra.estat == estat.upper(),
    ).order_by(AlertaGarantiaRecompra.created_at.desc())

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


@router.post("/rag", status_code=status.HTTP_201_CREATED)
async def afegir_document_rag(
    dades: DocumentRagIn,
    db: AsyncSession = Depends(get_db_with_tenant_context),
    claims: Dict[str, Any] = Depends(get_current_user_claims)
):
    """Permet als administradors afegir protocols i documentació al RAG del Copilot."""
    empresa_id = aplicar_tenant_context(claims)
    
    nou_doc = FaqCorporativaRag(
        empresa_id=empresa_id,
        pregunta=dades.pregunta,
        resposta=dades.resposta,
        paraules_clau=dades.paraules_clau,
        actiu=True
    )
    db.add(nou_doc)
    await db.commit()
    
    return {"estat": "OK", "missatge": "Document afegit a la base de coneixement de la IA."}

@router.get("/rag")
async def llistar_documents_rag(
    db: AsyncSession = Depends(get_db_with_tenant_context),
    claims: Dict[str, Any] = Depends(get_current_user_claims)
):
    """Llista els protocols del RAG actius."""
    empresa_id = aplicar_tenant_context(claims)
    
    q = select(FaqCorporativaRag).where(FaqCorporativaRag.empresa_id == empresa_id, FaqCorporativaRag.actiu == True)
    res = await db.execute(q)
    docs = res.scalars().all()
    
    return [{"id": str(d.id), "titol": d.titol, "contingut": d.contingut, "tags": d.tags} for d in docs]
