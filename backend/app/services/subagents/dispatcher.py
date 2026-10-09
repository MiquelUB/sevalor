"""Orquestrador Central i Dispatcher Multi-Agent de Sevalor Suite."""

import json
import logging
import time
import uuid
from typing import Any, Dict, List, Optional, Tuple

import httpx
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.models import ConsultaXatCopilot
from app.services.subagents.base import BaseSubagent
from app.services.subagents.subagent_auditoria_marge import SubagentAuditoriaMarge
from app.services.subagents.subagent_client_telegram import SubagentClientTelegram
from app.services.subagents.subagent_flota_despatx import SubagentFlotaDespatx
from app.services.subagents.subagent_general_rag import SubagentGeneralRag
from app.services.subagents.subagent_logistica_estoc import SubagentLogisticaEstoc
from app.services.subagents.subagent_ocr_vision import SubagentOcrVision
from app.services.subagents.subagent_peritatge_camp import SubagentPeritatgeCamp

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
    """Orquestrador central de subagents especialitzats."""

    def __init__(self) -> None:
        self.subagent_marge = SubagentAuditoriaMarge()
        self.subagent_estoc = SubagentLogisticaEstoc()
        self.subagent_flota = SubagentFlotaDespatx()
        self.subagent_perit = SubagentPeritatgeCamp()
        self.subagent_ocr = SubagentOcrVision()
        self.subagent_telegram = SubagentClientTelegram()
        self.subagent_general = SubagentGeneralRag()

        self.subagents: List[BaseSubagent] = [
            self.subagent_marge,
            self.subagent_flota,
            self.subagent_estoc,
            self.subagent_perit,
            self.subagent_ocr,
            self.subagent_telegram,
            self.subagent_general,
        ]

    def select_subagent(self, query: str, rol: str) -> BaseSubagent:
        """Classifica la intenció de l'usuari i retorna el subagent especialitzat idoni."""
        # 1. Auditoria Financer / Marges (Prioritari si demana dades econòmiques)
        if self.subagent_marge.can_handle(query, rol):
            return self.subagent_marge

        # 2. OCR i Digitalització
        if self.subagent_ocr.can_handle(query, rol):
            return self.subagent_ocr

        # 3. Flota i Desplaçaments
        if self.subagent_flota.can_handle(query, rol):
            return self.subagent_flota

        # 4. Peritatge de Camp i Garanties
        if self.subagent_perit.can_handle(query, rol):
            return self.subagent_perit

        # 5. Telegram / Concierge
        if self.subagent_telegram.can_handle(query, rol):
            return self.subagent_telegram

        # 6. Logística i Magatzem
        if self.subagent_estoc.can_handle(query, rol):
            return self.subagent_estoc

        # 7. Fallback: RAG General Corporatiu
        return self.subagent_general

    async def _cridar_lm_studio_subagent(
        self,
        subagent: BaseSubagent,
        pregunta: str,
        vertical: str,
        db: AsyncSession,
        empresa_id: uuid.UUID,
        historial: Optional[List[dict]] = None,
        agent_prompt_system: Optional[str] = None,
    ) -> Tuple[Optional[str], Optional[str], Optional[dict], Optional[dict]]:
        """Invoca el node LM Studio amb l'esquema reduït i el prompt del subagent."""
        lm_url = (
            getattr(settings, "LM_STUDIO_URL", None)
            or getattr(settings, "LMSTUDIO_URL", None)
            or "http://127.0.0.1:1234/v1"
        )
        if not lm_url:
            return None, None, None, None

        base_url = lm_url.rstrip("/")
        endpoint = (
            f"{base_url}/chat/completions"
            if base_url.endswith("/v1")
            else f"{base_url}/v1/chat/completions"
        )

        system_content = f"{subagent.system_prompt} Vertical: {vertical}. "
        if agent_prompt_system:
            system_content += f" Directrius Específiques de l'Empresa: {agent_prompt_system}. "

        messages: List[Dict[str, Any]] = [{"role": "system", "content": system_content}]
        if historial:
            for h in historial:
                if isinstance(h, dict) and "role" in h and "content" in h:
                    messages.append({"role": h["role"], "content": str(h["content"])})

        messages.append({"role": "user", "content": pregunta})

        model_name = getattr(settings, "LM_STUDIO_MODEL", "deepseek-coder-v2-lite-instruct")
        api_key = getattr(settings, "LM_STUDIO_API_KEY", "lm-studio")

        payload = {
            "model": model_name,
            "messages": messages,
            "tools": subagent.tools_schema,
            "tool_choice": "auto" if subagent.tools_schema else "none",
            "temperature": 0.2,
            "max_tokens": 700,
        }

        try:
            async with httpx.AsyncClient(timeout=8.0) as client:
                resp = await client.post(
                    endpoint,
                    json=payload,
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json",
                    },
                )
                if resp.status_code != 200:
                    return None, None, None, None

                res_json = resp.json()
                choices = res_json.get("choices", [])
                if not choices:
                    return None, None, None, None

                msg = choices[0].get("message", {})
                tool_calls = msg.get("tool_calls", [])

                if tool_calls:
                    tc = tool_calls[0]
                    fn_name = tc.get("function", {}).get("name")
                    args_str = tc.get("function", {}).get("arguments", "{}")
                    try:
                        fn_args = json.loads(args_str) if isinstance(args_str, str) else args_str
                    except Exception:
                        fn_args = {}

                    # Execució de l'eina mitjançant el subagent especialitzat
                    tool_res = await subagent.execute_tool(fn_name, fn_args, db, empresa_id)

                    # Síntesi final
                    messages.append(msg)
                    messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": tc.get("id", "call_1"),
                            "name": fn_name,
                            "content": json.dumps(tool_res, ensure_ascii=False),
                        }
                    )

                    payload_synthesis = {
                        "model": model_name,
                        "messages": messages,
                        "temperature": 0.2,
                        "max_tokens": 700,
                    }
                    resp_synth = await client.post(
                        endpoint,
                        json=payload_synthesis,
                        headers={
                            "Authorization": f"Bearer {api_key}",
                            "Content-Type": "application/json",
                        },
                    )
                    if resp_synth.status_code == 200:
                        synth_json = resp_synth.json()
                        synth_choices = synth_json.get("choices", [])
                        if synth_choices:
                            content = synth_choices[0].get("message", {}).get("content", "").strip()
                            if content:
                                return content, fn_name, fn_args, tool_res

                    return None, fn_name, fn_args, tool_res

                content = msg.get("content", "").strip()
                if content:
                    return content, None, None, None

        except Exception as e:
            logger.warning(
                f"Connexió amb LM Studio fallida a {endpoint} (subagent {subagent.id}): {e}"
            )

        return None, None, None, None

    async def dispatch(
        self,
        pregunta: str,
        db: AsyncSession,
        empresa_id: uuid.UUID,
        usuari_id: uuid.UUID,
        rol_usuari: str,
        vertical: str = "SEVALOR",
        historial: Optional[List[dict]] = None,
        agent_prompt_system: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Encamina, audita la seguretat per rol i resol la consulta mitjançant el subagent idoni."""
        t_start = time.perf_counter()
        pregunta_net = pregunta.lower()

        # ── 1. Verificació d'Accés per Rol (Zero-Trust Security Barrier) ────────
        if rol_usuari == "OPERARI":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Copilot no disponible per a operaris",
            )

        # Veto financer per a rols no-BOSS (ENGINYER, SECRETARIA, etc.)
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

        # ── 2. Selecció del Subagent Especialitzat ─────────────────────────────
        selected_subagent = self.select_subagent(pregunta, rol_usuari)

        # ── 3. Intent de Tool Calling amb LM Studio ───────────────────────────
        (
            resposta_ia,
            tool_name,
            tool_args,
            tool_result,
        ) = await self._cridar_lm_studio_subagent(
            subagent=selected_subagent,
            pregunta=pregunta,
            vertical=vertical,
            db=db,
            empresa_id=empresa_id,
            historial=historial,
            agent_prompt_system=agent_prompt_system,
        )

        enllacos: List[dict] = []
        if resposta_ia and tool_name:
            resposta = resposta_ia
            if tool_name == "get_real_stock":
                enllacos.append({"titol": "Inventari de Magatzem", "url": "/gestio/magatzem"})
            elif tool_name in ("get_vehicle_info", "get_closest_vehicle"):
                enllacos.append({"titol": "Flota de Vehicles", "url": "/gestio/flota"})
            elif tool_name == "get_client_history":
                enllacos.append({"titol": "Directori de Clients", "url": "/gestio/clients"})
            elif tool_name == "get_warranty_status":
                enllacos.append({"titol": "Auditoria de Garanties", "url": "/gestio/copilot"})
            elif tool_name == "get_unbilled_money":
                enllacos.append({"titol": "Control Financer i Marge", "url": "/gestio/economica"})
        else:
            # Fallback determinista sobirà local (Zero Mock Data)
            (
                resp_local,
                t_name_loc,
                t_args_loc,
                t_res_loc,
                enllacos_loc,
            ) = await selected_subagent.run_sovereign(pregunta, db, empresa_id)

            if t_name_loc != "get_rag_knowledge" or (t_res_loc and t_res_loc.get("trobat")):
                resposta = resp_local
                tool_name = t_name_loc
                tool_args = t_args_loc
                tool_result = t_res_loc
                enllacos = enllacos_loc
            elif resposta_ia:
                # Pregunta conversacional directa atesa per LM Studio
                resposta = resposta_ia
                tool_name = None
                tool_args = None
                tool_result = None
                enllacos = []
            else:
                resposta = resp_local
                tool_name = t_name_loc
                tool_args = t_args_loc
                tool_result = t_res_loc
                enllacos = enllacos_loc

        elapsed_ms = int((time.perf_counter() - t_start) * 1000)

        # ── 4. Persistència de l'Auditoria a PostgreSQL (Zero Mock) ───────────
        consulta_db = ConsultaXatCopilot(
            empresa_id=empresa_id,
            usuari_id=usuari_id,
            pregunta=pregunta,
            resposta=resposta,
            vertical=vertical,
            temps_inferencia_ms=elapsed_ms,
            enllacos_relacionats=enllacos,
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
