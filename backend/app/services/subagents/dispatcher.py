"""Orquestrador Central i Dispatcher Multi-Agent de Sevalor Suite (Copilot v2)."""

import json
import logging
import re
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
from zoneinfo import ZoneInfo

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.network_utils import build_wss_tunnel_uri
from app.models.models import ConsultaXatCopilot, Empresa, Usuari
from app.services.copilot_config_service import get_strict_copilot_config
from app.services.sovereign_storage import SovereignStorageGateway
from app.services.subagents.base import BaseSubagent
from app.services.subagents.subagent_auditoria_marge import SubagentAuditoriaMarge
from app.services.subagents.subagent_client_telegram import SubagentClientTelegram
from app.services.subagents.subagent_flota_despatx import SubagentFlotaDespatx
from app.services.subagents.subagent_general_rag import SubagentGeneralRag
from app.services.subagents.subagent_logistica_estoc import SubagentLogisticaEstoc
from app.services.subagents.subagent_ocr_vision import SubagentOcrVision
from app.services.subagents.subagent_peritatge_camp import SubagentPeritatgeCamp
from app.services.subagents.subagent_planificacio_equip import SubagentPlanificacioEquip
from app.services.vault_tunnel import (
    VaultTunnelError,
    VaultTunnelOfflineError,
    VaultTunnelRemoteError,
    VaultTunnelTimeoutError,
    empresa_target_key,
    vault_tunnel_broker,
)

logger = logging.getLogger("copilot_dispatcher")

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
    "unbilled",
    "no facturat",
    "falta facturar",
]


async def build_isolated_system_prompt(
    db: AsyncSession,
    empresa_id: uuid.UUID,
    primary_subagent_id: str,
    ara_str: str,
    usuari_nom: str,
    usuari_id: str,
    rol_usuari: str,
    empresa_nom: str,
    vertical_efectiva: str,
    context_extra_str: str = "",
) -> Tuple[str, str]:
    """Construeix el system prompt estrictament aïllat per empresa des de copilot_configs (FORCE RLS)."""
    cfg = await get_strict_copilot_config(db, empresa_id)
    if not cfg or not (cfg.system_prompt or "").strip():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="COPILOT_NOT_CONFIGURED: Aquesta empresa no té el prompt configurat a /gestio/copilot/.",
        )

    subagent_prompt = str((cfg.subagent_prompts or {}).get(primary_subagent_id, "") or "").strip()
    rag_prompt = str(cfg.rag_prompt or "").strip()

    parts: List[str] = []
    if subagent_prompt:
        parts.append(subagent_prompt)
    parts.append(f"DIRECTRIUS DE L'EMPRESA ({empresa_nom}):\n{cfg.system_prompt.strip()}")
    if rag_prompt:
        parts.append(f"INSTRUCCIONS RAG DE L'EMPRESA:\n{rag_prompt}")
    parts.append(
        f"DATA I HORA ACTUALS: {ara_str}\n"
        f"USUARI ACTUAL: {usuari_nom} (ID: {usuari_id}, Rol: {rol_usuari})\n"
        f"EMPRESA_ID: {empresa_id} | VERTICAL: {vertical_efectiva}"
    )
    if context_extra_str.strip():
        parts.append(context_extra_str.strip())
    parts.append(
        "INSTRUCCIÓ OBLIGATÒRIA ZERO-HALLUCINATION: Basa les respostes STRICTAMENT en les dades "
        "obtingudes a través de les eines del disc dur d'aquesta empresa. No inventis mai dades."
    )

    return "\n\n".join(parts).strip(), str(cfg.llm_model or "").strip()


class CopilotDispatcher:
    """Orquestrador central de subagents especialitzats amb routing top-2, memòria i context."""

    def __init__(self) -> None:
        self.subagent_marge = SubagentAuditoriaMarge()
        self.subagent_planificacio = SubagentPlanificacioEquip()
        self.subagent_estoc = SubagentLogisticaEstoc()
        self.subagent_flota = SubagentFlotaDespatx()
        self.subagent_perit = SubagentPeritatgeCamp()
        self.subagent_ocr = SubagentOcrVision()
        self.subagent_telegram = SubagentClientTelegram()
        self.subagent_general = SubagentGeneralRag()

        self.subagents: List[BaseSubagent] = [
            self.subagent_marge,
            self.subagent_planificacio,
            self.subagent_flota,
            self.subagent_estoc,
            self.subagent_perit,
            self.subagent_ocr,
            self.subagent_telegram,
            self.subagent_general,
        ]

    def score_subagents(self, query: str, rol: str) -> List[Tuple[BaseSubagent, float]]:
        """Calcula una puntuació d'afinitat per a cada subagent segons la consulta i el rol."""
        q = query.lower()
        scores: Dict[str, float] = {s.id: 0.0 for s in self.subagents}

        # 1. Auditoria Financer / Marge (Boss únicament)
        if any(k in q for k in ["marge", "benefici", "rendibilitat", "facturacio", "facturació", "desviacio", "desviació", "auditoria", "unbilled", "no facturat"]):
            if rol in ("BOSS", "ADMIN"):
                scores["subagent_auditoria_marge"] += 10.0
            else:
                scores["subagent_auditoria_marge"] = -100.0

        # 2. Planificació i Equip
        if any(k in q for k in ["ordre", "ordres", "feina", "feines", "treball", "tasca", "tasques", "equip", "operari", "treballador", "plantilla", "horari", "fitxatge", "fitxatges", "hores", "jornada", "incidencia", "incidència", "avui", "part de treball", "repartiment", "assignada", "assignat", "cens", "quants som"]):
            scores["subagent_planificacio_equip"] += 5.0
        if any(k in q for k in ["plantilla", "total plantilla", "quants som", "treballadors actius", "cens", "quants operaris", "quants treballadors"]):
            scores["subagent_planificacio_equip"] += 8.0
        if re.search(r"\bOT[-\d\w]+\b", query, re.IGNORECASE):
            scores["subagent_planificacio_equip"] += 8.0

        # 3. Flota i Desplaçaments
        if any(k in q for k in ["vehicle", "vehicles", "furgoneta", "furgonetes", "cotxe", "cotxes", "matricula", "matrícula", "itv", "assegurança", "asseguranca", "més a prop", "mes a prop", "aprop", "proxim", "pròxim", "flota", "en ruta", "combustible", "gasoil", "gasolina", "consum", "adblue", "manteniment de vehicle"]):
            scores["subagent_flota_despatx"] += 5.0
        if re.search(r"\b[0-9]{4}[ -]?[A-Z]{3}\b", query.upper()):
            scores["subagent_flota_despatx"] += 8.0

        # 4. Magatzem i Logística
        if any(k in q for k in ["estoc", "stock", "cable", "tub", "tubs", "panell", "inversor", "bateria", "material", "materials", "inventari", "magatzem", "ruptura", "ruptures", "alerta estoc", "replanificar", "reprogramar", "moviment", "moviments", "albarà de proveïdor", "comanda de compra"]):
            if not any(k in q for k in ["extreu", "extreure", "ocr", "digitalitzar", "escanejar"]):
                scores["subagent_logistica_estoc"] += 5.0

        # 5. Peritatge de Camp
        if any(k in q for k in ["garantia", "garanties", "defecte", "anomalia", "fotovoltaica", "inclinacio", "termografia", "peritatge"]):
            scores["subagent_peritatge_camp"] += 5.0

        # 6. OCR i Digitalització
        if any(k in q for k in ["ocr", "digitalitzar", "escanejar", "llegir tiquet", "llegir factura", "llegir albarà", "extreu", "extreure", "línies", "linies"]):
            scores["subagent_ocr_vision"] += 7.0

        # 7. Telegram / Concierge
        if any(k in q for k in ["telegram", "concierge", "xat client", "canal client"]):
            scores["subagent_client_telegram"] += 5.0

        # 8. General RAG / Directori
        if any(k in q for k in ["client", "clients", "finca", "finques", "parcel·la", "parcel·les", "parcela", "sigpac", "eina", "eines", "pressupost", "pressupostos", "protocol", "normativa", "rebt"]):
            scores["subagent_general_rag"] += 4.0

        # Puntuació base mínima de RAG corporatiu
        scores["subagent_general_rag"] += 0.5

        # Mapejar a objectes BaseSubagent
        subagent_map = {s.id: s for s in self.subagents}
        result = [(subagent_map[s_id], score) for s_id, score in scores.items()]
        result.sort(key=lambda x: x[1], reverse=True)
        return result

    def select_subagent(self, query: str, rol: str) -> BaseSubagent:
        """Compatibilitat cap enrere: retorna el subagent principal millor puntuat."""
        scored = self.score_subagents(query, rol)
        return scored[0][0]

    def _get_combined_tools(
        self, primary: BaseSubagent, secondary: Optional[BaseSubagent], rol: str
    ) -> Tuple[List[Dict[str, Any]], Dict[str, BaseSubagent]]:
        """Combina les eines dels top-2 subagents filtrant per rol de seguretat."""
        combined_tools: List[Dict[str, Any]] = []
        tool_name_to_subagent: Dict[str, BaseSubagent] = {}
        seen_names = set()

        candidates = [primary]
        if secondary and secondary.id != primary.id:
            candidates.append(secondary)

        for sub in candidates:
            for tool_item in getattr(sub, "tools_schema", []):
                fn = tool_item.get("function", {})
                name = fn.get("name")
                if not name or name in seen_names:
                    continue

                # Protecció financera (Double-Barrier): no oferir eines financeres a no-BOSS
                if name in ("get_unbilled_money", "get_margin_alert") and rol != "BOSS":
                    continue

                seen_names.add(name)
                combined_tools.append(tool_item)
                tool_name_to_subagent[name] = sub

        return combined_tools, tool_name_to_subagent

    async def _cridar_lm_studio_multi_round(
        self,
        target_key: str,
        model_name: str,
        system_content: str,
        pregunta: str,
        combined_tools: List[Dict[str, Any]],
        tool_name_to_subagent: Dict[str, BaseSubagent],
        primary_subagent: BaseSubagent,
        db: AsyncSession,
        empresa_id: uuid.UUID,
        rol_usuari: str,
        usuari_id: uuid.UUID,
        historial: Optional[List[dict]] = None,
    ) -> Tuple[Optional[str], Optional[str], Optional[dict], Optional[dict], List[dict], BaseSubagent]:
        """Executa un bucle multi-round (fins a 3 rondes) amb LM Studio local via Túnel WSS Únic."""
        messages: List[Dict[str, Any]] = [{"role": "system", "content": system_content}]
        if historial:
            for h in historial[-6:]:
                if isinstance(h, dict) and "role" in h and "content" in h:
                    messages.append({"role": h["role"], "content": str(h["content"])})

        messages.append({"role": "user", "content": pregunta})

        current_messages = list(messages)
        last_tool_name: Optional[str] = None
        last_tool_args: Optional[dict] = None
        last_tool_result: Optional[dict] = None
        active_subagent: BaseSubagent = primary_subagent
        final_answer: Optional[str] = None

        max_rounds = 3
        active_model = model_name
        for round_idx in range(max_rounds):
            payload: Dict[str, Any] = {
                "model": active_model,
                "messages": current_messages,
                "temperature": 0.2,
                "max_tokens": 450,
            }
            if combined_tools:
                payload["tools"] = combined_tools
                payload["tool_choice"] = "auto"

            try:
                res_json = await vault_tunnel_broker.call_llm_chat(
                    target_key, payload, timeout=120.0
                )
            except VaultTunnelRemoteError as exc:
                if round_idx == 0 and exc.status_code in (400, 404):
                    retried = False
                    try:
                        m_res = await vault_tunnel_broker.call_llm_models(target_key, timeout=6.0)
                        loaded = [
                            m.get("id")
                            for m in m_res.get("data", [])
                            if isinstance(m, dict) and m.get("id")
                        ]
                        if loaded and active_model not in loaded:
                            chat_models = [
                                str(m) for m in loaded if "embed" not in str(m).lower()
                            ]
                            active_model = chat_models[0] if chat_models else str(loaded[0])
                            payload["model"] = active_model
                            res_json = await vault_tunnel_broker.call_llm_chat(
                                target_key, payload, timeout=120.0
                            )
                            retried = True
                    except VaultTunnelRemoteError as retry_exc:
                        if retry_exc.status_code == 400 and "tools" in payload:
                            payload.pop("tools", None)
                            payload.pop("tool_choice", None)
                            res_json = await vault_tunnel_broker.call_llm_chat(
                                target_key, payload, timeout=120.0
                            )
                            retried = True
                        else:
                            raise
                    except Exception:
                        pass
                    if not retried:
                        if exc.status_code == 400 and "tools" in payload:
                            payload.pop("tools", None)
                            payload.pop("tool_choice", None)
                            res_json = await vault_tunnel_broker.call_llm_chat(
                                target_key, payload, timeout=120.0
                            )
                        else:
                            raise
                else:
                    raise

            choices = res_json.get("choices", [])
            if not choices:
                break

            msg = choices[0].get("message", {}) or {}
            tool_calls = msg.get("tool_calls") or []

            if not tool_calls:
                final_answer = str(msg.get("content") or "").strip()
                break

            current_messages.append(msg)

            for tc in tool_calls:
                fn_name = tc.get("function", {}).get("name")
                args_str = tc.get("function", {}).get("arguments", "{}")
                try:
                    fn_args = json.loads(args_str) if isinstance(args_str, str) else args_str
                except Exception:
                    fn_args = {}

                target_subagent = tool_name_to_subagent.get(fn_name, primary_subagent)
                active_subagent = target_subagent

                tool_res = await target_subagent.execute_tool(
                    fn_name,
                    fn_args,
                    db,
                    empresa_id,
                    caller_role=rol_usuari,
                    caller_user_id=usuari_id,
                )

                last_tool_name = fn_name
                last_tool_args = fn_args
                last_tool_result = tool_res

                current_messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tc.get("id", f"call_{round_idx}"),
                        "name": fn_name,
                        "content": json.dumps(tool_res, ensure_ascii=False),
                    }
                )

        if not final_answer and last_tool_name:
            payload_synth: Dict[str, Any] = {
                "model": active_model,
                "messages": current_messages,
                "temperature": 0.2,
                "max_tokens": 400,
            }
            try:
                synth_json = await vault_tunnel_broker.call_llm_chat(
                    target_key, payload_synth, timeout=120.0
                )
                synth_choices = synth_json.get("choices", [])
                if synth_choices:
                    final_answer = str(
                        (synth_choices[0].get("message") or {}).get("content") or ""
                    ).strip()
            except VaultTunnelError:
                pass

        return final_answer, last_tool_name, last_tool_args, last_tool_result, [], active_subagent

    async def dispatch(
        self,
        pregunta: str,
        db: AsyncSession,
        empresa_id: uuid.UUID,
        usuari_id: uuid.UUID,
        rol_usuari: str,
        usuari_nom: Optional[str] = None,
        context_id: Optional[str] = None,
        vertical: str = "SEVALOR",
        historial: Optional[List[dict]] = None,
        agent_prompt_system: Optional[str] = None,
        allow_operari: bool = False,
    ) -> Dict[str, Any]:
        """Encamina, audita la seguretat per rol i resol la consulta mitjançant el subagent idoni."""
        t_start = time.perf_counter()
        pregunta_net = pregunta.lower().strip()
        es_timeout = False

        # ── 1. Verificació d'Accés per Rol (Zero-Trust Security Barrier) ────────
        if not allow_operari and rol_usuari in ("OPERARI", "CAPATAZ", "CAP_DE_COLLA"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Copilot no disponible per a operaris",
            )

        # Veto financer per a rols no-BOSS
        es_consulta_financera = any(clau in pregunta_net for clau in PARAULES_CLAU_FINANCERES_VETO)
        if es_consulta_financera and rol_usuari != "BOSS":
            log_denegat = ConsultaXatCopilot(
                empresa_id=empresa_id,
                usuari_id=usuari_id,
                pregunta=pregunta,
                resposta="Consulta no autoritzada per política de rols de seguretat.",
                vertical=vertical,
                denegat_per_rol=True,
            )
            db.add(log_denegat)
            await db.commit()

            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Consulta no autoritzada per política de rols de seguretat",
            )

        # ── 2. Porta Estrica Zero-Storage / Túnel WSS Obligatori (Principi V) ──
        res_emp = await db.execute(select(Empresa).where(Empresa.id == empresa_id))
        empresa = res_emp.scalar_one_or_none()
        await SovereignStorageGateway.autocurar_config_tunel_empresa(db, empresa, commit=True)
        feature_on = bool(empresa and getattr(empresa, "feature_copilot_ia", False))
        node_on = bool(empresa and getattr(empresa, "node_ia_actiu", False))

        if not empresa or not feature_on or not node_on:
            if not empresa:
                motiu = "EMPRESA_NO_TROBADA"
                msg_detall = "Empresa no trobada per executar el Copilot IA local. Zero fallback a Hetzner."
            elif not feature_on:
                motiu = "FEATURE_COPILOT_DESACTIVAT"
                msg_detall = (
                    "El mòdul Copilot IA (feature_copilot_ia) està desactivat a la llicència d'aquesta empresa. "
                    "Activa'l al panell de Superadmin. Zero fallback a Hetzner."
                )
            else:
                motiu = "NODE_IA_INACTIU"
                msg_detall = (
                    "L'ordinador dedicat d'IA local està desactivat (node_ia_actiu=False). "
                    "Contacta amb l'administrador de Sevalor (Superadmin) per activar-lo. Zero fallback a Hetzner."
                )
            logger.warning(
                "Copilot 503 COPILOT_DESACTIVAT (%s) per empresa=%s (trobat=%s, feature_copilot_ia=%s, node_ia_actiu=%s)",
                motiu,
                empresa_id,
                bool(empresa),
                feature_on,
                node_on,
            )
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail={
                    "code": "COPILOT_DESACTIVAT",
                    "motiu": motiu,
                    "message": msg_detall,
                },
            )

        # ── 3. Dades de Context des del Disc Dur Sobirà de l'Empresa ──────────
        config_docs = await SovereignStorageGateway.llegir_entitats_json(
            db, empresa_id, "configuracio"
        )
        emp_cfg = next((c for c in config_docs if str(c.get("id")) == str(empresa_id)), None)
        empresa_nom = (
            (emp_cfg or {}).get("nom")
            or (empresa.nom if empresa and empresa.nom and not str(empresa.nom).startswith("Tenant ") else None)
            or "SEVALOR"
        )
        vertical_efectiva = (
            (emp_cfg or {}).get("vertical")
            or (empresa.vertical if empresa else None)
            or vertical
        )

        # Obtenir nom d'usuari des del disc dur sobirà (zero PII a Hetzner)
        if not usuari_nom or "@" in usuari_nom and usuari_nom.endswith("@sovereign.local"):
            operaris_docs = await SovereignStorageGateway.llegir_entitats_json(
                db, empresa_id, "operaris"
            )
            matched_op = next(
                (o for o in operaris_docs if str(o.get("id")) == str(usuari_id)),
                None,
            )
            if not matched_op:
                matched_op = next(
                    (c for c in config_docs if str(c.get("id")) == str(usuari_id)),
                    None,
                )
            if matched_op:
                usuari_nom = (
                    f"{matched_op.get('nom') or ''} {matched_op.get('cognoms') or ''}".strip()
                    or str(matched_op.get("rol") or rol_usuari)
                )
            else:
                usuari_nom = rol_usuari

        # Timestamp en temps real (Europe/Madrid)
        try:
            ara = datetime.now(ZoneInfo("Europe/Madrid"))
        except Exception:
            ara = datetime.now(timezone.utc)
        dias_setmana = ["Dilluns", "Dimarts", "Dimecres", "Dijous", "Divendres", "Dissabte", "Diumenge"]
        ara_str = f"{ara.strftime('%Y-%m-%d %H:%M')} ({dias_setmana[ara.weekday()]})"

        # Context addicional des del disc dur sobirà (06_ordres_treball/actives_buffer)
        context_extra_str = ""
        if context_id and context_id.strip():
            ctx_clean = context_id.strip()
            ots_docs = await SovereignStorageGateway.llegir_entitats_json(
                db, empresa_id, "ots_actives"
            )
            ot_obj = next((o for o in ots_docs if str(o.get("id")) == ctx_clean), None)
            if ot_obj:
                context_extra_str = (
                    f"\nCONTEXT DE LA FEINA ACTIVA: L'usuari es troba a l'ordre {ot_obj.get('codi', ctx_clean)} "
                    f"('{ot_obj.get('titol', '')}'), estat: {ot_obj.get('estat', 'N/D')}, "
                    f"adreça: {ot_obj.get('adreca') or 'Sense adreça'}."
                )

        # ── 4. Routing Ponderat Top-2 Subagents ────────────────────────────────
        scored = self.score_subagents(pregunta, rol_usuari)
        primary_subagent = scored[0][0]
        secondary_subagent = scored[1][0] if len(scored) > 1 and scored[1][1] > 0.0 else None

        combined_tools, tool_name_to_subagent = self._get_combined_tools(
            primary_subagent, secondary_subagent, rol_usuari
        )

        # ── 5. Verificació Estricta del Túnel WSS Dedicat (abans de validar prompt) ──
        # NORMA CONSTITUCIONAL: Zero fallback a Hetzner. Si el túnel WSS no està connectat -> 503.
        target_key = empresa_target_key(empresa_id)
        if not await vault_tunnel_broker.is_online(target_key):
            logger.warning(
                "Copilot 503 NODE_IA_OFFLINE (TUNEL_OFFLINE) per empresa=%s: agent WSS no connectat.",
                empresa_id,
            )
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail={
                    "code": "NODE_IA_OFFLINE",
                    "motiu": "TUNEL_OFFLINE",
                    "message": (
                        "L'ordinador dedicat de l'empresa no està connectat al túnel WSS de Sevalor. "
                        "Comprova que l'agent estigui encès. Zero fallback a Hetzner."
                    ),
                },
            )

        # ── 6. Injecció Dinàmica de Context i System Prompt Estrictament Aïllat ─
        system_content, configured_llm_model = await build_isolated_system_prompt(
            db=db,
            empresa_id=empresa_id,
            primary_subagent_id=primary_subagent.id,
            ara_str=ara_str,
            usuari_nom=usuari_nom or rol_usuari,
            usuari_id=str(usuari_id),
            rol_usuari=rol_usuari,
            empresa_nom=empresa_nom,
            vertical_efectiva=vertical_efectiva,
            context_extra_str=context_extra_str,
        )

        es_actiu = True
        resposta_ia: Optional[str] = None
        tool_name: Optional[str] = None
        tool_args: Optional[dict] = None
        tool_result: Optional[dict] = None
        selected_subagent: BaseSubagent = primary_subagent

        model_name = configured_llm_model or getattr(settings, "LM_STUDIO_MODEL", "qwen2.5-vl-7b-instruct")
        try:
            (
                resposta_ia,
                tool_name,
                tool_args,
                tool_result,
                _,
                selected_subagent,
            ) = await self._cridar_lm_studio_multi_round(
                target_key=target_key,
                model_name=model_name,
                system_content=system_content,
                pregunta=pregunta,
                combined_tools=combined_tools,
                tool_name_to_subagent=tool_name_to_subagent,
                primary_subagent=primary_subagent,
                db=db,
                empresa_id=empresa_id,
                rol_usuari=rol_usuari,
                usuari_id=usuari_id,
                historial=historial,
            )
        except HTTPException:
            raise
        except VaultTunnelRemoteError as exc:
            logger.warning(
                "Copilot 503 NODE_IA_OFFLINE (%s) per empresa=%s: %s",
                exc.code,
                empresa_id,
                exc.detail,
            )
            motiu_err = "LLM_OFFLINE" if exc.code == "LLM_OFFLINE" else exc.code
            msg_err = (
                "El PC de l'empresa està connectat, però LM Studio/Ollama local no respon a 127.0.0.1:1234. Zero fallback a Hetzner."
                if exc.code == "LLM_OFFLINE"
                else f"{exc.detail} Zero fallback a Hetzner."
            )
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail={
                    "code": "NODE_IA_OFFLINE",
                    "motiu": motiu_err,
                    "message": msg_err,
                },
            ) from exc
        except (VaultTunnelOfflineError, VaultTunnelTimeoutError, VaultTunnelError) as exc:
            logger.warning(
                "Copilot 503 NODE_IA_OFFLINE per empresa=%s (%s): %s",
                empresa_id,
                exc.code,
                exc.detail,
            )
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail={
                    "code": "NODE_IA_OFFLINE",
                    "motiu": "TIMEOUT" if isinstance(exc, VaultTunnelTimeoutError) else "TUNEL_OFFLINE",
                    "message": (
                        "L'ordinador dedicat de l'empresa no està connectat al túnel WSS de Sevalor "
                        "o ha esgotat el temps d'espera. Zero fallback a Hetzner."
                    ),
                },
            ) from exc

        # ── 6. Resolució Final i Grounding Fallback ─────────────────────────────
        enllacos: List[dict] = []

        # Si el model ha utilitzat una eina amb èxit i ha sintetitzat una resposta
        if resposta_ia and tool_name:
            resposta = resposta_ia
        else:
            # Fallback sobirà determinista (Zero Mock) executat pel subagent primari
            try:
                (
                    resp_local,
                    t_name_loc,
                    t_args_loc,
                    t_res_loc,
                    enllacos_loc,
                ) = await primary_subagent.run_sovereign(
                    pregunta,
                    db,
                    empresa_id,
                    caller_role=rol_usuari,
                    caller_user_id=usuari_id,
                )
            except TypeError:
                (
                    resp_local,
                    t_name_loc,
                    t_args_loc,
                    t_res_loc,
                    enllacos_loc,
                ) = await primary_subagent.run_sovereign(
                    pregunta,
                    db,
                    empresa_id,
                )

            # Comprovar si el resultat local aporta informació substantiva
            es_substantiu = bool(
                t_name_loc
                and t_res_loc
                and (
                    t_res_loc.get("trobat")
                    or t_res_loc.get("total", 0) > 0
                    or t_res_loc.get("total_plantilla", 0) > 0
                    or t_res_loc.get("total_operaris", 0) > 0
                    or t_res_loc.get("total_hores", 0) > 0
                    or t_res_loc.get("total_alertes", 0) > 0
                    or t_res_loc.get("total_disponible", 0) > 0
                )
            )

            # Si el model no ha cridat eina però la consulta era operativa, preferir el resultat local
            if es_substantiu or not resposta_ia:
                resposta = resp_local
                tool_name = t_name_loc
                tool_args = t_args_loc
                tool_result = t_res_loc
                enllacos = enllacos_loc
                selected_subagent = primary_subagent
            else:
                resposta = resposta_ia

        # Generar enllaços de navegació ràpida segons l'eina utilitzada
        if tool_name:
            if tool_name in ("get_work_orders", "get_work_order_detail", "get_team_today", "get_timesheet", "get_open_incidents"):
                enllacos.append({"titol": "Ordres de Treball", "url": "/gestio/planificacio"})
            elif tool_name in ("get_real_stock", "get_stock_movements", "get_low_stock_alerts", "get_supplier_docs"):
                enllacos.append({"titol": "Inventari de Magatzem", "url": "/gestio/magatzem"})
            elif tool_name in ("get_vehicle_info", "get_closest_vehicle", "get_fleet_status", "audit_itv_insurance_fleet", "get_vehicle_maintenance", "get_fuel_consumption"):
                enllacos.append({"titol": "Flota de Vehicles", "url": "/gestio/flota"})
            elif tool_name in ("search_clients", "get_client_history"):
                enllacos.append({"titol": "Directori de Clients", "url": "/gestio/clients"})
            elif tool_name == "get_pending_budgets":
                enllacos.append({"titol": "Pressupostos", "url": "/gestio/pressupostos"})
            elif tool_name == "get_warranty_status":
                enllacos.append({"titol": "Auditoria de Garanties", "url": "/gestio/copilot"})
            elif tool_name in ("get_unbilled_money", "get_margin_alert"):
                enllacos.append({"titol": "Control Financer i Marge", "url": "/gestio/economica"})

        elapsed_ms = int((time.perf_counter() - t_start) * 1000)

        # ── 7. Persistència al Disc Sobirà (copilot_feedback) i Auditoria ───────
        try:
            await SovereignStorageGateway.desar_entitat_json(
                db=db,
                empresa_id=empresa_id,
                categoria="copilot_feedback",
                item_id=f"chat_{uuid.uuid4().hex[:12]}",
                dades={
                    "data": datetime.now(timezone.utc).isoformat(),
                    "usuari_id": str(usuari_id) if usuari_id else None,
                    "rol": rol_usuari,
                    "subagent_utilitzat": selected_subagent.id,
                    "tool_utilitzada": tool_name,
                    "pregunta": pregunta,
                    "resposta": resposta,
                    "context_id": context_id,
                },
            )
        except Exception as exc:
            logger.warning("No s'ha pogut desar conversa copilot al disc de l'empresa: %s", exc)

        try:
            val_usuari_id = None
            if usuari_id:
                res_chk = await db.execute(select(Usuari.id).where(Usuari.id == usuari_id))
                if res_chk.scalar_one_or_none():
                    val_usuari_id = usuari_id

            if val_usuari_id:
                consulta_db = ConsultaXatCopilot(
                    empresa_id=empresa_id,
                    usuari_id=val_usuari_id,
                    pregunta=pregunta,
                    resposta=resposta,
                    vertical=vertical,
                    node_ia_actiu=es_actiu,
                    node_ia_url=build_wss_tunnel_uri(empresa_id),
                    temps_inferencia_ms=elapsed_ms,
                    enllacos_relacionats=enllacos,
                    es_error_timeout=es_timeout,
                    denegat_per_rol=False,
                    tool_name=tool_name,
                    tool_args=tool_args,
                    tool_result=tool_result,
                )
                db.add(consulta_db)
                await db.commit()
        except Exception as e:
            logger.warning(f"Error registrant auditoria de consulta copilot: {e}")
            await db.rollback()

        return {
            "resposta": resposta,
            "vertical": vertical,
            "temps_inferencia_ms": elapsed_ms,
            "tool_utilitzada": tool_name,
            "tool_args": tool_args,
            "tool_resultat": tool_result,
            "enllacos": enllacos,
            "subagent_utilitzat": selected_subagent.id,
            "declinat_per_vertical": False,
        }


# Instància singleton exportada per defecte
copilot_dispatcher = CopilotDispatcher()
