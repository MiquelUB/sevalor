"""Subagent General i RAG Corporatiu (Knowledge Base, Clients, Finques i Eines)."""

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, List, Optional, Tuple

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import (
    Client,
    EinaCustodia,
    FaqCorporativaRag,
    Finca,
    OrdreTreball,
    Pressupost,
    Usuari,
)
from app.services.subagents.base import BaseSubagent
from app.services.subagents.schemas import SCHEMAS_GENERAL_RAG


class SubagentGeneralRag(BaseSubagent):
    id = "subagent_general_rag"
    nom = "Subagent General i RAG Corporatiu"
    descripcio = (
        "Especialista en procediments corporatius, fitxa 360° de clients, parcel·les/finques, "
        "eines en custòdia i pressupostos pendents."
    )
    allowed_roles = ["BOSS", "SECRETARIA", "ENGINYER", "OPERARI", "CAP_DE_COLLA", "ADMIN"]
    tools_schema = SCHEMAS_GENERAL_RAG
    system_prompt = (
        "Ets el Copilot Tècnic de SEVALOR Suite. "
        "Tens accés a la base de coneixement corporativa RAG, directori de clients, finques agrícoles, "
        "eines tècniques en custòdia i pressupostos operatius. "
        "Respon sempre en català de forma concisa, professional i fonamentada en dades reals de l'empresa. "
        "Per motius de seguretat financera, no facilitis mai dades econòmiques tret que l'usuari tingui rol de gerència."
    )

    def can_handle(self, query: str, rol: str) -> bool:
        # Actua com a fallback per a qualsevol consulta tècnica / corporativa
        return True

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
        if tool_name == "get_rag_knowledge":
            return await self.tool_get_rag_knowledge(db, empresa_id, args.get("query", ""))
        elif tool_name == "get_client_history":
            return await self.tool_get_client_history(
                db, empresa_id, args.get("client_id"), args.get("client_nom")
            )
        elif tool_name == "search_clients":
            return await self.tool_search_clients(
                db, empresa_id, args.get("terme", ""), int(args.get("limit", 5))
            )
        elif tool_name == "get_finca_detail":
            return await self.tool_get_finca_detail(db, empresa_id, args.get("finca_nom_o_id", ""))
        elif tool_name == "get_pending_budgets":
            return await self.tool_get_pending_budgets(
                db,
                empresa_id,
                client_id=args.get("client_id"),
                limit=int(args.get("limit", 5)),
                caller_role=caller_role,
            )
        elif tool_name == "get_tools_custody":
            return await self.tool_get_tools_custody(
                db,
                empresa_id,
                operari_nom_o_id=args.get("operari_nom_o_id"),
                limit=int(args.get("limit", 10)),
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

    async def tool_search_clients(
        self,
        db: AsyncSession,
        empresa_id: uuid.UUID,
        terme: str,
        limit: int = 5,
    ) -> dict:
        t_clean = terme.strip()
        if not t_clean:
            return {"trobat": False, "clients": [], "missatge": "Cal indicar un terme de cerca."}

        stmt = (
            select(Client)
            .where(
                Client.empresa_id == empresa_id,
                or_(
                    Client.rao_social.ilike(f"%{t_clean}%"),
                    Client.nif.ilike(f"%{t_clean}%"),
                    Client.codi.ilike(f"%{t_clean}%"),
                    Client.email.ilike(f"%{t_clean}%"),
                ),
            )
            .limit(limit)
        )
        res = await db.execute(stmt)
        clients = res.scalars().all()

        llista = [
            {
                "id": str(c.id),
                "codi": c.codi,
                "rao_social": c.rao_social,
                "nif": c.nif,
                "telefon": c.telefon,
                "email": c.email,
                "actiu": c.actiu,
            }
            for c in clients
        ]
        return {
            "trobat": len(llista) > 0,
            "total": len(llista),
            "clients": llista,
            "missatge": (
                f"S'han trobat {len(llista)} clients coincidents amb '{t_clean}'."
                if llista
                else f"No s'ha trobat cap client amb el terme '{t_clean}'."
            ),
        }

    async def tool_get_finca_detail(
        self,
        db: AsyncSession,
        empresa_id: uuid.UUID,
        finca_nom_o_id: str,
    ) -> dict:
        f_clean = finca_nom_o_id.strip()
        stmt = (
            select(Finca, Client.rao_social)
            .outerjoin(Client, Finca.client_id == Client.id)
            .where(Finca.empresa_id == empresa_id)
        )
        try:
            f_uuid = uuid.UUID(f_clean)
            stmt = stmt.where(Finca.id == f_uuid)
        except (ValueError, AttributeError):
            stmt = stmt.where(
                or_(
                    Finca.nom.ilike(f"%{f_clean}%"),
                    Finca.adreca.ilike(f"%{f_clean}%"),
                )
            )

        res = await db.execute(stmt)
        row = res.first()
        if not row:
            return {
                "trobat": False,
                "missatge": f"No s'ha trobat la finca o parcel·la '{f_clean}'.",
            }

        finca, client_nom = row
        return {
            "trobat": True,
            "finca_id": str(finca.id),
            "nom": finca.nom,
            "client_propietari": client_nom or "Sense client associat",
            "adreca": finca.adreca,
            "latitud": float(finca.latitud) if finca.latitud is not None else None,
            "longitud": float(finca.longitud) if finca.longitud is not None else None,
            "ref_cadastral": finca.ref_cadastral,
            "superficie_ha": float(finca.superficie_ha) if finca.superficie_ha is not None else None,
            "poligon_sigpac": finca.poligon_sigpac,
            "parcel_sigpac": finca.parcel_sigpac,
            "missatge": f"Finca '{finca.nom}' localitzada (Propietari: {client_nom or 'N/D'}).",
        }

    async def tool_get_pending_budgets(
        self,
        db: AsyncSession,
        empresa_id: uuid.UUID,
        client_id: Optional[str] = None,
        limit: int = 5,
        caller_role: Optional[str] = None,
    ) -> dict:
        stmt = (
            select(Pressupost, Client.rao_social)
            .outerjoin(Client, Pressupost.client_id == Client.id)
            .where(
                Pressupost.empresa_id == empresa_id,
                Pressupost.estat.in_(["PENDENT", "EMES", "EN_REVISIO"]),
            )
        )
        if client_id and client_id.strip():
            try:
                c_uuid = uuid.UUID(client_id.strip())
                stmt = stmt.where(Pressupost.client_id == c_uuid)
            except (ValueError, AttributeError):
                stmt = stmt.where(Client.rao_social.ilike(f"%{client_id.strip()}%"))

        stmt = stmt.order_by(Pressupost.created_at.desc()).limit(limit)
        res = await db.execute(stmt)
        rows = res.all()

        budgets = []
        for p, client_nom in rows:
            item = {
                "id": str(p.id),
                "numero": p.numero,
                "client": client_nom or "Sense client",
                "estat": p.estat,
                "data": p.created_at.isoformat() if p.created_at else None,
            }
            # Doble barrera de seguretat financera
            if caller_role in ("BOSS", "ADMIN"):
                item["total"] = float(p.total) if p.total is not None else 0.0
            budgets.append(item)

        return {
            "trobat": len(budgets) > 0,
            "total_pendents": len(budgets),
            "pressupostos": budgets,
            "missatge": (
                f"S'han trobat {len(budgets)} pressupostos pendents d'aprovació."
                if budgets
                else "No hi ha cap pressupost pendent en aquests moments."
            ),
        }

    async def tool_get_tools_custody(
        self,
        db: AsyncSession,
        empresa_id: uuid.UUID,
        operari_nom_o_id: Optional[str] = None,
        limit: int = 10,
    ) -> dict:
        stmt = (
            select(EinaCustodia, Usuari.nom, Usuari.cognoms)
            .outerjoin(Usuari, EinaCustodia.custodiat_per_operari_id == Usuari.id)
            .where(EinaCustodia.empresa_id == empresa_id)
        )
        if operari_nom_o_id and operari_nom_o_id.strip():
            op_clean = operari_nom_o_id.strip()
            try:
                op_uuid = uuid.UUID(op_clean)
                stmt = stmt.where(EinaCustodia.custodiat_per_operari_id == op_uuid)
            except (ValueError, AttributeError):
                stmt = stmt.where(
                    or_(
                        Usuari.nom.ilike(f"%{op_clean}%"),
                        Usuari.cognoms.ilike(f"%{op_clean}%"),
                    )
                )

        stmt = stmt.order_by(EinaCustodia.nom.asc()).limit(limit)
        res = await db.execute(stmt)
        rows = res.all()

        eines = []
        for eina, u_nom, u_cognoms in rows:
            custodi = f"{u_nom or ''} {u_cognoms or ''}".strip() or "Al magatzem"
            eines.append(
                {
                    "id": str(eina.id),
                    "nom": eina.nom,
                    "model": eina.model,
                    "numero_serie": eina.numero_serie,
                    "estat": eina.estat,
                    "custodiat_per": custodi,
                    "propera_calibracio": (
                        eina.data_propera_calibracio.isoformat()
                        if eina.data_propera_calibracio
                        else None
                    ),
                }
            )

        return {
            "trobat": len(eines) > 0,
            "total_eines": len(eines),
            "eines": eines,
            "missatge": (
                f"S'han trobat {len(eines)} eines o equips tècnics."
                if eines
                else "No s'han trobat eines en custòdia per al filtre sol·licitat."
            ),
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
        pregunta_lower = pregunta.lower()
        enllacos: List[dict] = []

        # 1. Salutacions i cortesia bàsica (Greetings)
        salutacions = [
            "hola",
            "bon dia",
            "bona tarda",
            "bona nit",
            "hola!",
            "que tal",
            "què tal",
            "com va",
            "com estàs",
            "com estas",
            "qui ets",
            "ajuda",
            "salutacions",
        ]
        text_net = pregunta_lower.strip().rstrip("!?.,")
        if any(text_net == s or text_net.startswith(s + " ") or text_net.startswith(s + ",") for s in salutacions):
            resposta = (
                "Hola! Sóc el Copilot Tècnic de SEVALOR Suite. "
                "Puc ajudar-te a consultar les ordres de treball i l'equip d'avui, l'estoc real del magatzem, "
                "la flota de vehicles en ruta, la fitxa de clients i parcel·les, o resoldre dubtes tècnics sobre protocols. "
                "En què et puc ajudar avui?"
            )
            return resposta, None, None, None, []

        # 2. Pressupostos pendents
        if any(k in pregunta_lower for k in ["pressupost", "pressupostos", "oferta", "ofertes"]):
            tool_name = "get_pending_budgets"
            tool_args = {"limit": 5}
            tool_res = await self.tool_get_pending_budgets(db, empresa_id, limit=5, caller_role=caller_role)
            return tool_res.get("missatge", "Consulta de pressupostos completada."), tool_name, tool_args, tool_res, [{"titol": "Pressupostos", "url": "/gestio/pressupostos"}]

        # 3. Finques / Parcel·les / Camps
        if any(k in pregunta_lower for k in ["finca", "finques", "parcel·la", "parcel·les", "parcela", "sigpac"]):
            tool_name = "get_finca_detail"
            tool_args = {"finca_nom_o_id": pregunta}
            tool_res = await self.tool_get_finca_detail(db, empresa_id, pregunta)
            return tool_res.get("missatge", "Consulta de finques completada."), tool_name, tool_args, tool_res, []

        # 4. Eines i equips tècnics en custòdia
        if any(k in pregunta_lower for k in ["eina", "eines", "maquinaria", "maquinària", "calibracio", "calibració", "custodia", "custòdia"]):
            tool_name = "get_tools_custody"
            tool_args = {"operari_nom_o_id": None, "limit": 10}
            tool_res = await self.tool_get_tools_custody(db, empresa_id, limit=10)
            if tool_res.get("trobat"):
                detalls = ", ".join([f"{e['nom']} ({e['custodiat_per']})" for e in tool_res["eines"][:4]])
                resposta = f"Eines i equips en custòdia: {detalls}."
            else:
                resposta = "No hi ha constància d'eines assignades en aquest moment."
            return resposta, tool_name, tool_args, tool_res, []

        # 5. Client / Historial / Cerca
        if any(k in pregunta_lower for k in ["historial", "fitxa 360", "360"]):
            terme_client = (
                pregunta.replace("Historial", "")
                .replace("historial", "")
                .replace("fitxa 360", "")
                .replace("Fitxa 360", "")
                .replace("360", "")
                .replace("del client", "")
                .replace("de la", "")
                .replace("del", "")
                .replace("i ", "")
                .strip()
            )
            tool_name = "get_client_history"
            tool_args = {"client_nom": terme_client or pregunta}
            tool_res = await self.tool_get_client_history(
                db, empresa_id, client_nom=tool_args["client_nom"]
            )
            if tool_res.get("trobat"):
                total_int = tool_res.get("total_intervencions_365d", 0)
                resposta = (
                    f"Historial del client: s'han registrat {total_int} intervencions en els darrers 365 dies."
                )
            else:
                resposta = tool_res.get(
                    "missatge", f"No s'ha trobat historial per a '{terme_client}'."
                )
            return resposta, tool_name, tool_args, tool_res, [{"titol": "Fitxa del Client", "url": "/gestio/clients"}]

        if any(k in pregunta_lower for k in ["client", "clients", "directori"]):
            # Cerca de client
            tool_name = "search_clients"
            tool_args = {"terme": pregunta, "limit": 5}
            tool_res = await self.tool_search_clients(db, empresa_id, pregunta, limit=5)
            if tool_res.get("trobat"):
                detalls = ", ".join([f"{c['rao_social']} ({c['nif']})" for c in tool_res["clients"]])
                resposta = f"Clients trobats a la base de dades: {detalls}."
            else:
                resposta = f"No s'ha trobat cap client coincident amb '{pregunta}'."
            return resposta, tool_name, tool_args, tool_res, [{"titol": "Directori de Clients", "url": "/gestio/clients"}]

        # 6. Fallback RAG corporatiu
        tool_name = "get_rag_knowledge"
        tool_args = {"query": pregunta}
        tool_res = await self.tool_get_rag_knowledge(db, empresa_id, pregunta)
        if tool_res.get("trobat"):
            doc = tool_res["documents"][0]
            resposta = f"Segons els protocols tècnics de Sevalor: {doc['resposta']}"
        else:
            resposta = (
                "No he trobat un protocol específic a la base de coneixement per a la teva consulta. "
                "Pots reformular la pregunta o consultar les seccions d'ordres de treball, magatzem o flota."
            )

        return resposta, tool_name, tool_args, tool_res, enllacos
