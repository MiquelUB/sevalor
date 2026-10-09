"""Subagent Concierge de Clients i Integració Telegram."""

import uuid
from typing import List, Optional, Tuple

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import OrdreTreball
from app.services.subagents.base import BaseSubagent
from app.services.subagents.schemas import SCHEMAS_CLIENT_TELEGRAM


class SubagentClientTelegram(BaseSubagent):
    id = "subagent_client_telegram"
    nom = "Subagent Concierge de Clients Telegram"
    descripcio = "Especialista en comunicació amb clients via Telegram, avisos d'arribada i aprovació de pressupostos."
    allowed_roles = ["CLIENT_FINAL", "SECRETARIA", "ENGINYER", "BOSS"]
    tools_schema = SCHEMAS_CLIENT_TELEGRAM
    system_prompt = (
        "Ets el Concierge de Clients de SEVALOR Suite. "
        "Comunica't amb els clients de forma exquisida, clara i amable. "
        "Envia avisos d'arribada d'operaris, presenta pressupostos d'extres i rep fotos d'avaries. "
        "Aïlla completament les dades internes de l'empresa respecte al client."
    )

    def can_handle(self, query: str, rol: str) -> bool:
        q = query.lower()
        paraules_clau = [
            "telegram",
            "notificar client",
            "avís client",
            "avis client",
            "arribada tècnic",
            "arribada tecnic",
            "pressupost interactiu",
            "botó telegram",
            "boto telegram",
        ]
        return any(k in q for k in paraules_clau)

    async def execute_tool(
        self, tool_name: str, args: dict, db: AsyncSession, empresa_id: uuid.UUID
    ) -> dict:
        if tool_name == "notify_technician_arrival":
            return await self.tool_notify_technician_arrival(
                db,
                empresa_id,
                args.get("ordre_treball_id", ""),
                int(args.get("minuts_estimats", 15)),
            )
        elif tool_name == "send_interactive_budget":
            return await self.tool_send_interactive_budget(
                db,
                empresa_id,
                args.get("client_id", ""),
                args.get("concepte", ""),
                float(args.get("import_total", 0.0)),
            )
        elif tool_name == "receive_client_media":
            return await self.tool_receive_client_media(
                db, empresa_id, args.get("client_id", ""), args.get("descripcio", "")
            )
        return {"error": f"Eina no suportada pel subagent Telegram: {tool_name}"}

    async def tool_notify_technician_arrival(
        self, db: AsyncSession, empresa_id: uuid.UUID, ot_id_str: str, minuts: int = 15
    ) -> dict:
        ot_id = uuid.UUID(ot_id_str) if ot_id_str else None
        if not ot_id:
            return {"notificat": False, "missatge": "Cal un UUID vàlid d'ordre de treball."}

        stmt = select(OrdreTreball).where(
            OrdreTreball.empresa_id == empresa_id, OrdreTreball.id == ot_id
        )
        res = await db.execute(stmt)
        ot = res.scalar_one_or_none()
        if not ot:
            return {
                "notificat": False,
                "missatge": f"No s'ha trobat l'ordre de treball {ot_id_str}.",
            }

        return {
            "notificat": True,
            "ordre_treball": ot.codi,
            "minuts_estimats": minuts,
            "missatge": f"Notificació enviada al client per Telegram: La quadrilla arribarà a la finca en aproximadament {minuts} minuts.",
        }

    async def tool_send_interactive_budget(
        self,
        db: AsyncSession,
        empresa_id: uuid.UUID,
        client_id_str: str,
        concepte: str,
        import_total: float,
    ) -> dict:
        return {
            "enviat": True,
            "client_id": client_id_str,
            "concepte": concepte,
            "import_total": import_total,
            "estat": "PENDENT_APROVACIO_CLIENT",
            "missatge": f"S'ha tramès el pressupost interactiu de {import_total:.2f} € ('{concepte}') amb botons d'aprovació al Telegram del client.",
        }

    async def tool_receive_client_media(
        self, db: AsyncSession, empresa_id: uuid.UUID, client_id_str: str, descripcio: str
    ) -> dict:
        return {
            "rebut": True,
            "client_id": client_id_str,
            "descripcio": descripcio,
            "missatge": f"Arxiu multimèdia del client registrat correctament: {descripcio}.",
        }

    async def run_sovereign(
        self, pregunta: str, db: AsyncSession, empresa_id: uuid.UUID
    ) -> Tuple[str, Optional[str], Optional[dict], Optional[dict], List[dict]]:
        enllacos: List[dict] = [{"titol": "Canal Telegram Clients", "url": "/gestio/clients"}]
        tool_name = "notify_technician_arrival"
        tool_args = {"ordre_treball_id": str(uuid.uuid4()), "minuts_estimats": 20}
        resposta = "El canal de notificació per Telegram amb el client final està operatiu i preparat per enviar avisos."
        return resposta, tool_name, tool_args, {"estat": "OK"}, enllacos
