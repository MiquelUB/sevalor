"""Orquestrador Central i Dispatcher Multi-Agent de Sevalor Suite (Copilot v2)."""

import json
import logging
import re
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
from zoneinfo import ZoneInfo

import httpx
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.models import ConsultaXatCopilot, Empresa, OrdreTreball, Usuari
from app.services.subagents.base import BaseSubagent
from app.services.subagents.subagent_auditoria_marge import SubagentAuditoriaMarge
from app.services.subagents.subagent_client_telegram import SubagentClientTelegram
from app.services.subagents.subagent_flota_despatx import SubagentFlotaDespatx
from app.services.subagents.subagent_general_rag import SubagentGeneralRag
from app.services.subagents.subagent_logistica_estoc import SubagentLogisticaEstoc
from app.services.subagents.subagent_ocr_vision import SubagentOcrVision
from app.services.subagents.subagent_peritatge_camp import SubagentPeritatgeCamp
from app.services.subagents.subagent_planificacio_equip import SubagentPlanificacioEquip

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
        if any(k in q for k in ["ordre", "ordres", "feina", "feines", "treball", "tasca", "tasques", "equip", "operari", "treballador", "plantilla", "horari", "fitxatge", "fitxatges", "hores", "jornada", "incidencia", "incidència", "avui", "part de treball", "repartiment", "assignada", "assignat"]):
            scores["subagent_planificacio_equip"] += 5.0
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
        endpoint: str,
        api_key: str,
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
        """Executa un bucle multi-round (fins a 3 rondes) amb LM Studio."""
        messages: List[Dict[str, Any]] = [{"role": "system", "content": system_content}]
        if historial:
            # Preservar només els últims 6 torns per memòria i context compacte
            for h in historial[-6:]:
                if isinstance(h, dict) and "role" in h and "content" in h:
                    messages.append({"role": h["role"], "content": str(h["content"])})

        messages.append({"role": "user", "content": pregunta})

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

        current_messages = list(messages)
        last_tool_name: Optional[str] = None
        last_tool_args: Optional[dict] = None
        last_tool_result: Optional[dict] = None
        active_subagent: BaseSubagent = primary_subagent
        final_answer: Optional[str] = None

        max_rounds = 3
        # Timeout constitucional de 15 segons (Spec 03 / Spec 012)
        async with httpx.AsyncClient(timeout=14.0) as client:
            for round_idx in range(max_rounds):
                payload = {
                    "model": model_name,
                    "messages": current_messages,
                    "tools": combined_tools if combined_tools else None,
                    "tool_choice": "auto" if combined_tools else "none",
                    "temperature": 0.2,
                    "max_tokens": 450,
                }
                resp = await client.post(endpoint, json=payload, headers=headers)
                if resp.status_code != 200:
                    logger.warning(f"LM Studio status {resp.status_code} a ronda {round_idx}: {resp.text}")
                    break

                res_json = resp.json()
                choices = res_json.get("choices", [])
                if not choices:
                    break

                msg = choices[0].get("message", {})
                tool_calls = msg.get("tool_calls", [])

                if not tool_calls:
                    # El model ha finalitzat la síntesi textual
                    final_answer = msg.get("content", "").strip()
                    break

                # Afegir missatge de l'assistent amb la crida d'eina
                current_messages.append(msg)

                # Execució de cada eina cridada
                for tc in tool_calls:
                    fn_name = tc.get("function", {}).get("name")
                    args_str = tc.get("function", {}).get("arguments", "{}")
                    try:
                        fn_args = json.loads(args_str) if isinstance(args_str, str) else args_str
                    except Exception:
                        fn_args = {}

                    target_subagent = tool_name_to_subagent.get(fn_name, primary_subagent)
                    active_subagent = target_subagent

                    # Executar eina sota context RLS i autorització
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

            # Si s'ha cridat alguna eina però el model no ha sintetitzat en la darrera ronda
            if not final_answer and last_tool_name:
                payload_synth = {
                    "model": model_name,
                    "messages": current_messages,
                    "temperature": 0.2,
                    "max_tokens": 400,
                }
                resp_synth = await client.post(endpoint, json=payload_synth, headers=headers)
                if resp_synth.status_code == 200:
                    synth_json = resp_synth.json()
                    synth_choices = synth_json.get("choices", [])
                    if synth_choices:
                        final_answer = synth_choices[0].get("message", {}).get("content", "").strip()

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

        # ── 2. Dades de Context de Sessió i Empresa ───────────────────────────
        res_emp = await db.execute(select(Empresa).where(Empresa.id == empresa_id))
        empresa = res_emp.scalar_one_or_none()
        empresa_nom = empresa.nom if empresa else "SEVALOR"
        vertical_efectiva = (empresa.vertical if empresa else None) or vertical

        # Obtenir nom d'usuari si no ha estat passat
        if not usuari_nom:
            res_u = await db.execute(select(Usuari).where(Usuari.id == usuari_id))
            u_db = res_u.scalar_one_or_none()
            if u_db:
                usuari_nom = f"{u_db.nom or ''} {u_db.cognoms or ''}".strip() or u_db.email
            else:
                usuari_nom = rol_usuari

        # Timestamp en temps real (Europe/Madrid)
        try:
            ara = datetime.now(ZoneInfo("Europe/Madrid"))
        except Exception:
            ara = datetime.now(timezone.utc)
        dias_setmana = ["Dilluns", "Dimarts", "Dimecres", "Dijous", "Divendres", "Dissabte", "Diumenge"]
        ara_str = f"{ara.strftime('%Y-%m-%d %H:%M')} ({dias_setmana[ara.weekday()]})"

        # Context addicional si hi ha OT activa a la pantalla
        context_extra_str = ""
        if context_id and context_id.strip():
            try:
                ot_uuid = uuid.UUID(context_id.strip())
                res_ot = await db.execute(
                    select(OrdreTreball).where(
                        OrdreTreball.id == ot_uuid, OrdreTreball.empresa_id == empresa_id
                    )
                )
                ot_obj = res_ot.scalar_one_or_none()
                if ot_obj:
                    context_extra_str = (
                        f"\nCONTEXT DE LA FEINA ACTIVA: L'usuari es troba a l'ordre {ot_obj.codi} "
                        f"('{ot_obj.titol}'), estat: {ot_obj.estat}, adreça: {ot_obj.adreca or 'Sense adreça'}."
                    )
            except Exception:
                pass

        # ── 3. Routing Ponderat Top-2 Subagents ────────────────────────────────
        scored = self.score_subagents(pregunta, rol_usuari)
        primary_subagent = scored[0][0]
        secondary_subagent = scored[1][0] if len(scored) > 1 and scored[1][1] > 0.0 else None

        combined_tools, tool_name_to_subagent = self._get_combined_tools(
            primary_subagent, secondary_subagent, rol_usuari
        )

        # ── 4. Injecció Dinàmica de Context al System Prompt ───────────────────
        anti_hallucination = (
            "INSTRUCCIÓ OBLIGATÒRIA ZERO-HALLUCINATION: Basa les respostes STRICTAMENT en les dades "
            "obtingudes a través de les eines de consulta disponibles (ordres de treball, horaris d'equip, "
            "estoc de magatzem, vehicles o clients). Si la pregunta de l'usuari fa referència a informació operativa, "
            "crida SEMPRE l'eina pertinent abans de contestar. No inventis mai matrícules, codis ni xifres. "
            "Si l'eina no troba registres, informa amablement que no s'ha trobat informació a la base de dades."
        )

        system_content = (
            f"{primary_subagent.system_prompt}\n"
            f"DATA I HORA ACTUALS: {ara_str}\n"
            f"USUARI ACTUAL: {usuari_nom} (ID: {usuari_id}, Rol: {rol_usuari})\n"
            f"EMPRESA: {empresa_nom} | VERTICAL: {vertical_efectiva}\n"
            f"{context_extra_str}\n"
            f"{anti_hallucination}\n"
        )
        if empresa and empresa.agent_prompt_system:
            system_content += f"DIRECTRIUS DE L'EMPRESA: {empresa.agent_prompt_system}\n"

        # ── 5. Intent d'Inferència amb LM Studio ──────────────────────────────
        node_url = (
            (empresa.node_ia_url.strip() if (empresa and empresa.node_ia_url and empresa.node_ia_url.strip()) else None)
            or getattr(settings, "LM_STUDIO_URL", None)
            or "http://127.0.0.1:1234/v1"
        )
        es_actiu = (empresa.node_ia_actiu if empresa else False) or bool(getattr(settings, "LM_STUDIO_URL", None))

        resposta_ia: Optional[str] = None
        tool_name: Optional[str] = None
        tool_args: Optional[dict] = None
        tool_result: Optional[dict] = None
        selected_subagent: BaseSubagent = primary_subagent

        if es_actiu and node_url:
            base_url = node_url.rstrip("/")
            endpoint = f"{base_url}/chat/completions" if base_url.endswith("/v1") else f"{base_url}/v1/chat/completions"
            model_name = getattr(settings, "LM_STUDIO_MODEL", "qwen2.5-vl-7b-instruct")
            api_key = getattr(settings, "LM_STUDIO_API_KEY", "lm-studio")

            try:
                (
                    resposta_ia,
                    tool_name,
                    tool_args,
                    tool_result,
                    _,
                    selected_subagent,
                ) = await self._cridar_lm_studio_multi_round(
                    endpoint=endpoint,
                    api_key=api_key,
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
            except httpx.TimeoutException:
                logger.warning(f"Timeout (15s) connectant a LM Studio a {endpoint}. Fallback sobirà activat.")
                es_timeout = True
            except Exception as e:
                logger.warning(f"Error connectant a LM Studio a {endpoint}: {e}")

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

        # ── 7. Persistència de l'Auditoria a PostgreSQL (Zero Mock) ───────────
        consulta_db = ConsultaXatCopilot(
            empresa_id=empresa_id,
            usuari_id=usuari_id,
            pregunta=pregunta,
            resposta=resposta,
            vertical=vertical,
            node_ia_actiu=es_actiu,
            node_ia_url=node_url,
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
