"""Subagent General i RAG Corporatiu (Knowledge Base & Historial 360°)."""

import uuid
from datetime import datetime, timedelta, timezone
from typing import List, Optional, Tuple

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import Client, FaqCorporativaRag, OrdreTreball
from app.services.subagents.base import BaseSubagent
from app.services.subagents.schemas import SCHEMAS_GENERAL_RAG


class SubagentGeneralRag(BaseSubagent):
    id = "subagent_general_rag"
    nom = "Subagent General i RAG Corporatiu"
    descripcio = "Especialista en procediments tècnics corporatius, normatives REBT/agrícoles i historial 360° de clients."
    allowed_roles = ["BOSS", "SECRETARIA", "ENGINYER"]
    tools_schema = SCHEMAS_GENERAL_RAG
    system_prompt = (
        "Ets el Copilot Tècnic de SEVALOR Suite. "
        "Tens accés a la base de coneixement corporativa RAG i a la fitxa 360° dels clients. "
        "Respon sempre en català de forma concisa, professional i fonamentada en els protocols de l'empresa."
    )

    def can_handle(self, query: str, rol: str) -> bool:
        # Actua com a fallback per a qualsevol consulta tècnica / corporativa
        return True

    async def execute_tool(
        self, tool_name: str, args: dict, db: AsyncSession, empresa_id: uuid.UUID
    ) -> dict:
        if tool_name == "get_rag_knowledge":
            return await self.tool_get_rag_knowledge(db, empresa_id, args.get("query", ""))
        elif tool_name == "get_client_history":
            return await self.tool_get_client_history(
                db, empresa_id, args.get("client_id"), args.get("client_nom")
            )
        return {"error": f"Eina no suportada pel subagent general: {tool_name}"}

    async def tool_get_rag_knowledge(
        self, db: AsyncSession, empresa_id: uuid.UUID, query: str
    ) -> dict:
        paraules = [p for p in query.lower().split() if len(p) > 3]
        if not paraules:
            return {"trobat": False, "documents": []}
        filtres = []
        for p in paraules:
            filtres.append(func.lower(FaqCorporativaRag.resposta).contains(p))
            filtres.append(func.lower(FaqCorporativaRag.pregunta).contains(p))
            filtres.append(func.lower(FaqCorporativaRag.paraules_clau).contains(p))
        q_faq = select(FaqCorporativaRag).where(
            FaqCorporativaRag.empresa_id == empresa_id, or_(*filtres)
        )
        docs = (await db.execute(q_faq)).scalars().all()
        return {
            "trobat": len(docs) > 0,
            "documents": [
                {"pregunta": d.pregunta, "resposta": d.resposta, "tags": d.paraules_clau}
                for d in docs
            ],
        }

    async def tool_get_client_history(
        self,
        db: AsyncSession,
        empresa_id: uuid.UUID,
        client_id: Optional[str] = None,
        client_nom: Optional[str] = None,
    ) -> dict:
        c_uuid = uuid.UUID(client_id) if client_id else None
        if not c_uuid and client_nom:
            res_c = await db.execute(
                select(Client).where(
                    Client.empresa_id == empresa_id,
                    Client.rao_social.ilike(f"%{client_nom.strip()}%"),
                )
            )
            cl = res_c.scalars().first()
            if cl:
                c_uuid = cl.id

        if not c_uuid:
            return {
                "trobat": False,
                "missatge": f"No s'ha trobat cap client amb '{client_nom or client_id}'.",
            }

        fa_un_any = datetime.now(timezone.utc) - timedelta(days=365)
        res_ots = await db.execute(
            select(OrdreTreball)
            .where(
                OrdreTreball.client_id == c_uuid,
                OrdreTreball.empresa_id == empresa_id,
                OrdreTreball.created_at >= fa_un_any,
            )
            .order_by(OrdreTreball.created_at.desc())
        )
        ots = res_ots.scalars().all()

        return {
            "trobat": True,
            "client_id": str(c_uuid),
            "total_intervencions_365d": len(ots),
            "intervencions": [
                {"id": str(o.id), "codi": o.codi, "titol": o.titol, "estat": o.estat} for o in ots
            ],
        }

    async def run_sovereign(
        self, pregunta: str, db: AsyncSession, empresa_id: uuid.UUID
    ) -> Tuple[str, Optional[str], Optional[dict], Optional[dict], List[dict]]:
        pregunta_lower = pregunta.lower()
        enllacos: List[dict] = []

        # Client / Historial
        if any(
            k in pregunta_lower
            for k in ["client", "historial", "fitxa 360", "360", "intervencions de"]
        ):
            tool_name = "get_client_history"
            tool_args = {"client_nom": pregunta}
            tool_res = await self.tool_get_client_history(db, empresa_id, client_nom=pregunta)
            enllacos.append({"titol": "Directori de Clients", "url": "/gestio/clients"})
            if tool_res.get("trobat"):
                resposta = f"Historial del client: {tool_res['total_intervencions_365d']} intervencions registrades en els últims 365 dies."
            else:
                resposta = tool_res.get("missatge", "No s'han trobat dades històriques del client.")
            return resposta, tool_name, tool_args, tool_res, enllacos

        # RAG coneixement
        tool_name = "get_rag_knowledge"
        tool_args = {"query": pregunta}
        tool_res = await self.tool_get_rag_knowledge(db, empresa_id, pregunta)
        if tool_res.get("trobat"):
            enllacos.append({"titol": "Base de Coneixement Corporativa", "url": "/gestio/copilot"})
            docs_txt = "\n".join(
                [f"• [{d['pregunta']}]: {d['resposta']}" for d in tool_res["documents"]]
            )
            resposta = (
                f"He trobat aquesta informació a la base de coneixement corporativa:\n\n{docs_txt}"
            )
        else:
            resposta = "No he trobat protocols específics ni dades directes a la base de coneixement corporativa per a aquesta consulta."

        return resposta, tool_name, tool_args, tool_res, enllacos
