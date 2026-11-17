"""Subagent Concierge de Clients i Integració Telegram (Lectura Exclusiva al Disc Sobirà de l'Empresa)."""

import re
import uuid
from typing import Any, List, Optional, Tuple

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.subagents.base import BaseSubagent
from app.services.subagents.schemas import SCHEMAS_CLIENT_TELEGRAM


class SubagentClientTelegram(BaseSubagent):
    id = "subagent_client_telegram"
    nom = "Subagent Concierge de Clients Telegram"
    descripcio = (
        "Especialista en comunicació amb clients via Telegram, avisos d'arribada i aprovació de pressupostos."
    )
    allowed_roles = ["CLIENT_FINAL", "SECRETARIA", "ENGINYER", "BOSS"]
    tools_schema = SCHEMAS_CLIENT_TELEGRAM
    system_prompt = (
        "Ets el Concierge de Clients de SEVALOR Suite. "
        "Comunica't amb els clients de forma exquisida, clara i amable consultant les fitxes del disc dur dedicat de l'empresa. "
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
        self,
        tool_name: str,
        args: dict,
        db: AsyncSession,
        empresa_id: uuid.UUID,
        caller_role: Optional[str] = None,
        caller_user_id: Optional[uuid.UUID] = None,
        **kwargs: Any,
    ) -> dict:
        if tool_name == "notify_technician_arrival":
            return await self.tool_notify_technician_arrival(
                db,
                empresa_id,
                args.get("ordre_treball_id", ""),
                int(args.get("minuts_estimats", 15)),
            )
        if tool_name == "send_interactive_budget":
            return await self.tool_send_interactive_budget(
                db,
                empresa_id,
                args.get("client_id", ""),
                args.get("concepte", ""),
                float(args.get("import_total", 0.0)),
            )
        if tool_name == "receive_client_media":
            return await self.tool_receive_client_media(
                db, empresa_id, args.get("client_id", ""), args.get("descripcio", "")
            )
        return {"error": f"Eina no suportada pel subagent Telegram: {tool_name}"}

    async def tool_notify_technician_arrival(
        self, db: AsyncSession, empresa_id: uuid.UUID, ot_id_str: str, minuts: int = 15
    ) -> dict:
        ot_ref = (ot_id_str or "").strip()
        if not ot_ref:
            return {"notificat": False, "missatge": "Cal un ID o codi vàlid d'ordre de treball."}

        ots = await self.read_sovereign_category(db, empresa_id, "ots_actives")
        ot = next(
            (
                o
                for o in ots
                if str(o.get("id") or "") == ot_ref
                or str(o.get("codi") or "").upper() == ot_ref.upper()
            ),
            None,
        )
        if not ot:
            return {
                "notificat": False,
                "missatge": f"No s'ha trobat l'ordre de treball '{ot_ref}' al disc dur de l'empresa.",
            }

        clients = await self.read_sovereign_category(db, empresa_id, "clients")
        client = next((c for c in clients if str(c.get("id") or "") == str(ot.get("client_id") or "")), None)
        chat_id = client.get("telegram_chat_id") if client else None

        return {
            "notificat": bool(chat_id),
            "ordre_treball": ot.get("codi"),
            "minuts_estimats": minuts,
            "telegram_chat_id_disponible": bool(chat_id),
            "missatge": (
                f"Notificació preparada per al client per Telegram ({ot.get('codi')}): "
                f"La quadrilla arribarà en aproximadament {minuts} minuts."
                if chat_id
                else f"Ordre {ot.get('codi')} localitzada, però el client no té telegram_chat_id vinculat al disc dur."
            ),
        }

    async def tool_send_interactive_budget(
        self,
        db: AsyncSession,
        empresa_id: uuid.UUID,
        client_id_str: str,
        concepte: str,
        import_total: float,
    ) -> dict:
        cid = (client_id_str or "").strip()
        clients = await self.read_sovereign_category(db, empresa_id, "clients")
        client = next((c for c in clients if str(c.get("id") or "") == cid), None)
        if not client:
            return {
                "enviat": False,
                "client_id": cid,
                "missatge": f"No s'ha trobat el client '{cid}' al disc dur de l'empresa.",
            }

        return {
            "enviat": bool(client.get("telegram_chat_id")),
            "client_id": cid,
            "client_nom": client.get("rao_social"),
            "concepte": concepte,
            "import_total": import_total,
            "estat": "PENDENT_APROVACIO_CLIENT" if client.get("telegram_chat_id") else "SENSE_CANAL_TELEGRAM",
            "missatge": (
                f"S'ha preparat el pressupost interactiu de {import_total:.2f} € ('{concepte}') per a {client.get('rao_social')} via Telegram."
                if client.get("telegram_chat_id")
                else f"El client {client.get('rao_social')} no disposa de telegram_chat_id configurat al disc dur."
            ),
        }

    async def tool_receive_client_media(
        self, db: AsyncSession, empresa_id: uuid.UUID, client_id_str: str, descripcio: str
    ) -> dict:
        cid = (client_id_str or "").strip()
        clients = await self.read_sovereign_category(db, empresa_id, "clients")
        client = next((c for c in clients if str(c.get("id") or "") == cid), None)
        if not client:
            return {
                "rebut": False,
                "client_id": cid,
                "missatge": f"No s'ha trobat cap client amb ID '{cid}' al disc dur de l'empresa.",
            }
        return {
            "rebut": True,
            "client_id": cid,
            "client_nom": client.get("rao_social"),
            "descripcio": descripcio,
            "missatge": f"Arxiu multimèdia del client {client.get('rao_social')} registrat: {descripcio}.",
        }

    async def run_sovereign(
        self,
        pregunta: str,
        db: AsyncSession,
        empresa_id: uuid.UUID,
        caller_role: Optional[str] = None,
        caller_user_id: Optional[uuid.UUID] = None,
        **kwargs: Any,
    ) -> Tuple[str, Optional[str], Optional[dict], Optional[dict], List[dict]]:
        enllacos: List[dict] = [{"titol": "Canal Telegram Clients", "url": "/gestio/clients"}]
        ot_match = re.search(r"\bOT[-\d\w]+\b", pregunta, re.IGNORECASE)
        if ot_match:
            codi_ot = ot_match.group(0).upper()
            tool_name = "notify_technician_arrival"
            tool_args: dict[str, Any] = {"ordre_treball_id": codi_ot, "minuts_estimats": 15}
            tool_res = await self.tool_notify_technician_arrival(db, empresa_id, codi_ot, 15)
            return tool_res.get("missatge", ""), tool_name, tool_args, tool_res, enllacos

        clients = await self.read_sovereign_category(db, empresa_id, "clients")
        tg_clients = [c for c in clients if c.get("telegram_chat_id")]
        return (
            f"Canal Telegram de clients connectat al disc de l'empresa ({len(tg_clients)} clients amb Telegram vinculat). "
            "Indica el codi d'OT o client concret per enviar una notificació.",
            None,
            None,
            {"clients_telegram_vinculats": len(tg_clients)},
            enllacos,
        )
