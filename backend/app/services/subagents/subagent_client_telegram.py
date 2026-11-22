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
    allowed_roles = ["CLIENT_FINAL", "SECRETARIA", "ENGINYER", "BOSS", "ADMIN"]
    tools_schema = SCHEMAS_CLIENT_TELEGRAM
    system_prompt = (
        "Ets el Concierge de Clients de SEVALOR Suite. "
        "Comunica't amb els clients de forma exquisida, clara i amable consultant les fitxes del disc dur dedicat de l'empresa. "
        "Prepara avisos d'arribada d'operaris, pressupostos verificats del disc dur i recepció de fotos d'avaries. "
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
                codi_ot=str(args.get("codi_ot") or args.get("ordre_treball_id") or ""),
                minuts_estimats=int(args.get("minuts_estimats", 15)),
            )
        if tool_name == "send_interactive_budget":
            # Seguretat financera (Constitució §2.IV HITL): MAI acceptar import_total ni concepte del LLM
            return await self.tool_send_interactive_budget(
                db,
                empresa_id,
                numero_pressupost=args.get("numero_pressupost") or args.get("pressupost_id"),
                client_nom=args.get("client_nom") or args.get("client_id"),
            )
        if tool_name == "receive_client_media":
            return await self.tool_receive_client_media(
                db,
                empresa_id,
                client_nom=str(args.get("client_nom") or args.get("client_id") or ""),
                descripcio=str(args.get("descripcio") or ""),
            )
        return {"error": f"Eina no suportada pel subagent Telegram: {tool_name}"}

    async def tool_notify_technician_arrival(
        self, db: AsyncSession, empresa_id: uuid.UUID, codi_ot: str, minuts_estimats: int = 15
    ) -> dict:
        ot_ref = (codi_ot or "").strip()
        if not ot_ref:
            return {"trobat": False, "notificat": False, "missatge": "Cal un codi vàlid d'ordre de treball."}

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
                "trobat": False,
                "notificat": False,
                "missatge": f"No s'ha trobat l'ordre de treball '{ot_ref}' al disc dur de l'empresa.",
            }

        clients = await self.read_sovereign_category(db, empresa_id, "clients")
        client = next((c for c in clients if str(c.get("id") or "") == str(ot.get("client_id") or "")), None)
        chat_id = client.get("telegram_chat_id") if client else None

        return {
            "trobat": True,
            "notificat": bool(chat_id),
            "requires_confirmation": bool(chat_id),
            "ordre_treball": ot.get("codi"),
            "minuts_estimats": minuts_estimats,
            "telegram_chat_id_disponible": bool(chat_id),
            "missatge": (
                f"Notificació preparada per al client per Telegram ({ot.get('codi')}): "
                f"La quadrilla arribarà en aproximadament {minuts_estimats} minuts. Pendent de confirmació (HITL)."
                if chat_id
                else f"Ordre {ot.get('codi')} localitzada, però el client no té telegram_chat_id vinculat al disc dur."
            ),
        }

    async def tool_send_interactive_budget(
        self,
        db: AsyncSession,
        empresa_id: uuid.UUID,
        numero_pressupost: Optional[str] = None,
        client_nom: Optional[str] = None,
    ) -> dict:
        """Carrega el pressupost verificat del disc dur (mai importa xifres del LLM) i genera proposta HITL."""
        pres_ref = (numero_pressupost or "").strip().lower()
        cli_ref = (client_nom or "").strip().lower()
        if not pres_ref and not cli_ref:
            return {
                "trobat": False,
                "enviat": False,
                "missatge": "Cal indicar el número de pressupost o el nom del client.",
            }

        pressupostos = await self.read_sovereign_category(db, empresa_id, "pressupostos")
        clients = await self.read_sovereign_category(db, empresa_id, "clients")
        clients_by_id = {str(c.get("id") or ""): c for c in clients if c.get("id")}

        coincidents: List[dict] = []
        for p in pressupostos:
            p_id = str(p.get("id") or "").lower()
            p_num = str(p.get("numero") or "").lower()
            cid = str(p.get("client_id") or "")
            cl = clients_by_id.get(cid)
            cl_nom = str((cl or {}).get("rao_social") or p.get("client_nom") or "").lower()

            if pres_ref and (pres_ref == p_id or pres_ref == p_num or pres_ref in p_num):
                coincidents.append(p)
            elif not pres_ref and cli_ref and (cli_ref == cid.lower() or cli_ref in cl_nom):
                coincidents.append(p)

        if not coincidents:
            return {
                "trobat": False,
                "enviat": False,
                "missatge": (
                    f"No s'ha trobat cap pressupost registrat al disc per a '{numero_pressupost or client_nom}'."
                ),
            }

        if len(coincidents) > 1 and not pres_ref:
            candidats = [
                {
                    "numero": p.get("numero") or p.get("id"),
                    "client": (clients_by_id.get(str(p.get("client_id") or "")) or {}).get("rao_social")
                    or p.get("client_nom"),
                    "estat": p.get("estat"),
                }
                for p in coincidents[:5]
            ]
            return {
                "trobat": True,
                "ambigu": True,
                "enviat": False,
                "candidats": candidats,
                "missatge": (
                    f"S'han trobat {len(coincidents)} pressupostos per a '{client_nom}'. "
                    "Indica el número exacte de pressupost a preparar."
                ),
            }

        pressupost = coincidents[0]
        cid = str(pressupost.get("client_id") or "")
        client = clients_by_id.get(cid)
        cl_nom = str((client or {}).get("rao_social") or pressupost.get("client_nom") or "Client")
        te_tg = bool(client and client.get("telegram_chat_id"))
        import_disc = float(pressupost.get("total") or pressupost.get("import_total") or 0.0)
        concepte_disc = str(
            pressupost.get("titol") or pressupost.get("concepte") or pressupost.get("numero") or "Pressupost"
        )

        return {
            "trobat": True,
            "enviat": False,
            "requires_confirmation": te_tg,
            "pressupost_numero": pressupost.get("numero") or pressupost.get("id"),
            "client_id": cid,
            "client_nom": cl_nom,
            "concepte": concepte_disc,
            "import_total": import_disc,
            "estat": "PENDENT_CONFIRMACIO_HITL" if te_tg else "SENSE_CANAL_TELEGRAM",
            "missatge": (
                f"Proposta preparada per enviar el pressupost {pressupost.get('numero') or pressupost.get('id')} "
                f"('{concepte_disc}', {import_disc:.2f} €) a {cl_nom} via Telegram. Requereix confirmació humana (HITL)."
                if te_tg
                else f"El client {cl_nom} no disposa de telegram_chat_id configurat al disc dur."
            ),
        }

    async def tool_receive_client_media(
        self, db: AsyncSession, empresa_id: uuid.UUID, client_nom: str, descripcio: str = ""
    ) -> dict:
        c_ref = (client_nom or "").strip()
        c_low = c_ref.lower()
        clients = await self.read_sovereign_category(db, empresa_id, "clients")
        coincidents = [
            c
            for c in clients
            if str(c.get("id") or "") == c_ref
            or c_low in str(c.get("rao_social") or c.get("nom") or "").lower()
        ]
        if not coincidents:
            return {
                "trobat": False,
                "rebut": False,
                "client_nom": c_ref,
                "missatge": f"No s'ha trobat cap client coincident amb '{c_ref}' al disc dur de l'empresa.",
            }
        if len(coincidents) > 1:
            return {
                "trobat": True,
                "ambigu": True,
                "rebut": False,
                "candidats": [c.get("rao_social") for c in coincidents[:5]],
                "missatge": f"Hi ha múltiples clients coincidents amb '{c_ref}'. Especifica el nom complet.",
            }
        client = coincidents[0]
        return {
            "trobat": True,
            "rebut": True,
            "client_id": str(client.get("id") or ""),
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
