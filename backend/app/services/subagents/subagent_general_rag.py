"""Subagent General i RAG Corporatiu (Lectura Exclusiva al Disc Sobirà de l'Empresa)."""

import re
import unicodedata
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.subagents.base import BaseSubagent
from app.services.subagents.schemas import SCHEMAS_GENERAL_RAG

_RE_PREGUNTA_PROCEDIMENT_RAG = re.compile(
    r"(?:\bcom\s+(?:es\s+|s['’]|puc\s+|podem\s+|pots\s+|haig\s+de\s+|he\s+de\s+|"
    r"donar|crear|afegir|registrar|editar|modificar|eliminar|esborrar|fer|configurar|"
    r"pujar|importar|exportar|enviar|aprovar|tancar|generar|consultar|regenerar|"
    r"assignar|consolidar|utilitzar|funciona|obrir|facturar|replanificar)\b|"
    r"\b(?:passos\s+per|on\s+(?:puc|es\s+pot|trobo|est[àa]|es\s+configura|configurar)|"
    r"guia\s+(?:de|del|dels|per)|tutorial|procediment\s+(?:de|per)|manual\s+(?:de|del))\b)",
    re.IGNORECASE,
)

_STOPWORDS_RAG = {
    "com",
    "que",
    "què",
    "per",
    "amb",
    "del",
    "dels",
    "les",
    "els",
    "una",
    "uns",
    "unes",
    "puc",
    "podem",
    "pots",
    "fer",
    "donar",
    "dona",
    "passos",
    "guia",
    "manual",
    "panell",
    "gestio",
    "sevalor",
}


def _norm_rag_text(text: str) -> str:
    """Normalitza minúscules, accents i apòstrofs (`d'alta` -> `alta`) per millorar el matching català."""
    raw = (text or "").lower().replace("’", "'")
    raw = re.sub(r"\b[dlmsnt]'", "", raw)
    nfkd = unicodedata.normalize("NFKD", raw)
    return "".join(ch for ch in nfkd if not unicodedata.combining(ch))

_STOPWORDS_CERCA = {
    "client",
    "clients",
    "directori",
    "cerca",
    "cercar",
    "busca",
    "buscar",
    "finca",
    "finques",
    "parcela",
    "parcel·la",
    "parceles",
    "detall",
    "detalls",
    "sobre",
    "quins",
    "quines",
    "quin",
    "quina",
    "dels",
    "les",
    "els",
    "amb",
    "per",
}


class SubagentGeneralRag(BaseSubagent):
    id = "subagent_general_rag"
    nom = "Subagent General i RAG Corporatiu"
    descripcio = (
        "Especialista en procediments corporatius, fitxa 360° de clients, parcel·les/finques, "
        "eines en custòdia i pressupostos pendents."
    )
    allowed_roles = [
        "BOSS",
        "SECRETARIA",
        "ENGINYER",
        "CAP_DE_MAGATZEM",
        "OPERARI",
        "CAP_DE_COLLA",
        "ADMIN",
    ]
    tools_schema = SCHEMAS_GENERAL_RAG
    system_prompt = (
        "Ets el Copilot Tècnic de SEVALOR Suite. "
        "Tens accés a la base de coneixement corporativa RAG, directori de clients, finques agrícoles, "
        "eines tècniques en custòdia i pressupostos operatius al disc dur dedicat de l'empresa. "
        "Respon sempre en català de forma concisa, professional i fonamentada en dades reals del disc. "
        "Per motius de seguretat financera, no facilitis mai dades econòmiques tret que l'usuari tingui rol de gerència."
    )

    def can_handle(self, query: str, rol: str) -> bool:
        return True

    @staticmethod
    def _extract_search_tokens(text: str) -> List[str]:
        tokens = [
            t
            for t in re.split(r"[\s,;:'\"!?()]+", (text or "").lower().strip())
            if len(t) >= 3 and t not in _STOPWORDS_CERCA
        ]
        return tokens

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
        if tool_name == "get_client_history":
            return await self.tool_get_client_history(
                db, empresa_id, args.get("client_id"), args.get("client_nom")
            )
        if tool_name == "search_clients":
            return await self.tool_search_clients(
                db, empresa_id, args.get("terme", ""), int(args.get("limit", 5))
            )
        if tool_name == "get_finca_detail":
            return await self.tool_get_finca_detail(db, empresa_id, args.get("finca_nom_o_id", ""))
        if tool_name == "get_pending_budgets":
            return await self.tool_get_pending_budgets(
                db,
                empresa_id,
                client_nom=args.get("client_nom"),
                client_id=args.get("client_id"),
                limit=int(args.get("limit", 5)),
                caller_role=caller_role,
            )
        if tool_name == "get_tools_custody":
            return await self.tool_get_tools_custody(
                db,
                empresa_id,
                operari_nom=args.get("operari_nom"),
                operari_nom_o_id=args.get("operari_nom_o_id"),
                limit=int(args.get("limit", 10)),
            )
        return {"error": f"Eina no suportada pel subagent general: {tool_name}"}

    async def tool_get_rag_knowledge(
        self, db: AsyncSession, empresa_id: uuid.UUID, query: str
    ) -> dict:
        norm_query = _norm_rag_text(query)
        totes_paraules = [
            p for p in re.split(r"[\s,;:.!?/()\"'-]+", norm_query) if len(p) >= 3
        ]
        paraules_clau = [p for p in totes_paraules if p not in _STOPWORDS_RAG]
        paraules = paraules_clau or [p for p in totes_paraules if len(p) > 3]
        if not paraules:
            return {"trobat": False, "documents": []}

        tots_docs = await self.search_sovereign_categories(
            db,
            empresa_id,
            categories=("protocols_interns", "manuals_fabricants", "normativa_prl", "copilot_rag_index"),
            query_text=" ".join(paraules),
            limit=40,
        )
        scored_docs: List[Tuple[float, Dict[str, Any]]] = []
        for d in tots_docs:
            preg = str(d.get("pregunta") or d.get("titol") or "")
            resp = str(d.get("resposta") or d.get("contingut") or d.get("resum") or "")
            tags = str(d.get("paraules_clau") or d.get("tags") or "")

            norm_preg = _norm_rag_text(preg)
            norm_tags = _norm_rag_text(tags)
            norm_resp = _norm_rag_text(resp)

            score = 0.0
            matched_tokens = 0
            for p in paraules:
                hit = False
                if p in norm_preg:
                    score += 5.0
                    hit = True
                if p in norm_tags:
                    score += 4.0
                    hit = True
                if p in norm_resp:
                    score += 1.0
                    hit = True
                if hit:
                    matched_tokens += 1

            if score <= 0.0:
                continue

            if matched_tokens == len(paraules) and len(paraules) >= 2:
                score += 6.0
            if norm_query and len(norm_query) >= 6 and (norm_query in norm_preg or norm_query in norm_tags):
                score += 8.0

            scored_docs.append((score, {"pregunta": preg, "resposta": resp, "tags": tags}))

        scored_docs.sort(key=lambda item: item[0], reverse=True)
        documents = [doc for _sc, doc in scored_docs[:5]]
        return {"trobat": len(documents) > 0, "documents": documents}

    async def tool_get_client_history(
        self,
        db: AsyncSession,
        empresa_id: uuid.UUID,
        client_id: Optional[str] = None,
        client_nom: Optional[str] = None,
    ) -> dict:
        clients = await self.read_sovereign_category(db, empresa_id, "clients")
        matched_id: Optional[str] = client_id.strip() if client_id else None

        if matched_id:
            if not any(str(c.get("id")) == matched_id for c in clients):
                # Acceptem ID si hi ha OTs vinculades tot i no tenir fitxa encara
                matched_id = matched_id
        elif client_nom:
            nom_clean = client_nom.strip().lower()
            tokens = self._extract_search_tokens(client_nom)
            coincidents = [
                c
                for c in clients
                if nom_clean in str(c.get("rao_social") or c.get("nom") or "").lower()
                or (
                    tokens
                    and any(t in str(c.get("rao_social") or c.get("nom") or "").lower() for t in tokens)
                )
            ]
            if len(coincidents) > 1:
                exactes = [
                    c
                    for c in coincidents
                    if str(c.get("rao_social") or c.get("nom") or "").strip().lower() == nom_clean
                ]
                if len(exactes) == 1:
                    matched_id = str(exactes[0].get("id"))
                else:
                    return {
                        "trobat": True,
                        "ambigu": True,
                        "candidats": [
                            {"codi": c.get("codi"), "rao_social": c.get("rao_social") or c.get("nom")}
                            for c in coincidents[:5]
                        ],
                        "missatge": (
                            f"S'han trobat {len(coincidents)} clients coincidents amb '{client_nom}'. "
                            "Indica el nom exacte del client."
                        ),
                    }
            elif len(coincidents) == 1:
                matched_id = str(coincidents[0].get("id"))

        if not matched_id:
            return {
                "trobat": False,
                "missatge": f"No s'ha trobat cap client amb '{client_nom or client_id}'.",
            }

        fa_un_any = datetime.now(timezone.utc) - timedelta(days=365)
        ots_tot = await self.read_sovereign_category(db, empresa_id, "ots_actives")
        ots_hist = await self.read_sovereign_category(db, empresa_id, "ots_historic")

        intervencions: List[Dict[str, Any]] = []
        vistes: set[str] = set()
        for o in [*ots_tot, *ots_hist]:
            oid = str(o.get("id") or "")
            if str(o.get("client_id")) != matched_id or oid in vistes:
                continue
            created_raw = o.get("created_at") or o.get("data_planificacio")
            if isinstance(created_raw, str):
                try:
                    dt = datetime.fromisoformat(created_raw.replace("Z", "+00:00"))
                    if dt.tzinfo is None:
                        dt = dt.replace(tzinfo=timezone.utc)
                    if dt < fa_un_any:
                        continue
                except ValueError:
                    pass
            vistes.add(oid)
            intervencions.append(
                {
                    "id": oid,
                    "codi": o.get("codi"),
                    "titol": o.get("titol"),
                    "estat": o.get("estat"),
                }
            )

        return {
            "trobat": True,
            "client_id": matched_id,
            "total_intervencions_365d": len(intervencions),
            "intervencions": intervencions,
        }

    async def tool_search_clients(
        self,
        db: AsyncSession,
        empresa_id: uuid.UUID,
        terme: str,
        limit: int = 5,
    ) -> dict:
        t_clean = (terme or "").strip()
        if not t_clean:
            return {"trobat": False, "clients": [], "missatge": "Cal indicar un terme de cerca."}

        clients = await self.read_sovereign_category(db, empresa_id, "clients")
        t_low = t_clean.lower()
        tokens = self._extract_search_tokens(t_clean)

        coincidents: List[Dict[str, Any]] = []
        for c in clients:
            camps = (
                f"{c.get('rao_social', '')} {c.get('nif', '')} "
                f"{c.get('codi', '')} {c.get('email', '')}"
            ).lower()
            if t_low in camps or (tokens and any(tok in camps for tok in tokens)):
                coincidents.append(
                    {
                        "id": str(c.get("id")),
                        "codi": c.get("codi"),
                        "rao_social": c.get("rao_social"),
                        "nif": c.get("nif"),
                        "telefon": c.get("telefon"),
                        "email": c.get("email"),
                        "actiu": c.get("actiu", True),
                    }
                )
                if len(coincidents) >= limit:
                    break

        return {
            "trobat": len(coincidents) > 0,
            "total": len(coincidents),
            "clients": coincidents,
            "missatge": (
                f"S'han trobat {len(coincidents)} clients coincidents amb '{t_clean}'."
                if coincidents
                else f"No s'ha trobat cap client amb el terme '{t_clean}'."
            ),
        }

    async def tool_get_finca_detail(
        self,
        db: AsyncSession,
        empresa_id: uuid.UUID,
        finca_nom_o_id: str,
    ) -> dict:
        f_clean = (finca_nom_o_id or "").strip()
        finques = await self.read_sovereign_category(db, empresa_id, "finques")
        clients = await self.read_sovereign_category(db, empresa_id, "clients")
        clients_map = {str(c.get("id")): c.get("rao_social") for c in clients if c.get("id")}

        matched: Optional[Dict[str, Any]] = None
        f_low = f_clean.lower()
        tokens = self._extract_search_tokens(f_clean)

        for f in finques:
            fid = str(f.get("id") or "")
            if fid and fid == f_clean:
                matched = f
                break
            nom = str(f.get("nom") or "").lower()
            adreca = str(f.get("adreca") or "").lower()
            blob = f"{nom} {adreca}".strip()
            if f_low in blob or (tokens and any(tok in blob for tok in tokens)):
                matched = f
                break

        if not matched:
            return {
                "trobat": False,
                "missatge": f"No s'ha trobat la finca o parcel·la '{f_clean}'.",
            }

        client_nom = clients_map.get(str(matched.get("client_id"))) or matched.get("client_nom")
        return {
            "trobat": True,
            "finca_id": str(matched.get("id")),
            "nom": matched.get("nom"),
            "client_propietari": client_nom or "Sense client associat",
            "adreca": matched.get("adreca"),
            "latitud": float(matched["latitud"]) if matched.get("latitud") is not None else None,
            "longitud": float(matched["longitud"]) if matched.get("longitud") is not None else None,
            "ref_cadastral": matched.get("ref_cadastral"),
            "superficie_ha": (
                float(matched["superficie_ha"]) if matched.get("superficie_ha") is not None else None
            ),
            "poligon_sigpac": matched.get("poligon_sigpac"),
            "parcel_sigpac": matched.get("parcel_sigpac"),
            "missatge": f"Finca '{matched.get('nom')}' localitzada (Propietari: {client_nom or 'N/D'}).",
        }

    async def tool_get_pending_budgets(
        self,
        db: AsyncSession,
        empresa_id: uuid.UUID,
        client_nom: Optional[str] = None,
        client_id: Optional[str] = None,
        limit: int = 5,
        caller_role: Optional[str] = None,
    ) -> dict:
        pressupostos = await self.read_sovereign_category(db, empresa_id, "pressupostos")
        clients = await self.read_sovereign_category(db, empresa_id, "clients")
        clients_map = {str(c.get("id")): c.get("rao_social") for c in clients if c.get("id")}

        pendents: List[Dict[str, Any]] = []
        filter_c = (client_nom or client_id or "").strip().lower()
        for p in pressupostos:
            if str(p.get("estat", "")).upper() not in ("PENDENT", "EMES", "EN_REVISIO"):
                continue
            cid = str(p.get("client_id") or "")
            cnom = clients_map.get(cid) or p.get("client_nom") or "Sense client"
            if filter_c and filter_c != cid.lower() and filter_c not in str(cnom).lower():
                continue

            item: Dict[str, Any] = {
                "id": str(p.get("id")),
                "numero": p.get("numero"),
                "client": cnom,
                "estat": p.get("estat"),
                "data": p.get("created_at") or p.get("data"),
            }
            if caller_role in ("BOSS", "ADMIN"):
                item["total"] = float(p.get("total") or 0.0)
            pendents.append(item)
            if len(pendents) >= limit:
                break

        return {
            "trobat": len(pendents) > 0,
            "total_pendents": len(pendents),
            "pressupostos": pendents,
            "missatge": (
                f"S'han trobat {len(pendents)} pressupostos pendents d'aprovació."
                if pendents
                else "No hi ha cap pressupost pendent en aquests moments."
            ),
        }

    async def tool_get_tools_custody(
        self,
        db: AsyncSession,
        empresa_id: uuid.UUID,
        operari_nom: Optional[str] = None,
        operari_nom_o_id: Optional[str] = None,
        limit: int = 10,
    ) -> dict:
        eines_raw = await self.read_sovereign_category(db, empresa_id, "magatzem_eines")
        operaris_raw = await self.read_sovereign_category(db, empresa_id, "operaris")
        op_map: Dict[str, str] = {}
        for u in operaris_raw:
            uid = str(u.get("id") or "")
            if uid:
                op_map[uid] = f"{u.get('nom') or ''} {u.get('cognoms') or ''}".strip()

        op_filter = (operari_nom or operari_nom_o_id or "").strip().lower()
        eines: List[Dict[str, Any]] = []
        for e in sorted(eines_raw, key=lambda x: str(x.get("nom") or "")):
            op_id = str(e.get("custodiat_per_operari_id") or "")
            custodi = op_map.get(op_id) or str(e.get("custodiat_per") or "").strip() or "Al magatzem"
            if op_filter:
                if op_filter != op_id.lower() and op_filter not in custodi.lower():
                    continue
            eines.append(
                {
                    "id": str(e.get("id")),
                    "nom": e.get("nom"),
                    "model": e.get("model"),
                    "numero_serie": e.get("numero_serie"),
                    "estat": e.get("estat"),
                    "custodiat_per": custodi,
                    "propera_calibracio": e.get("data_propera_calibracio"),
                }
            )
            if len(eines) >= limit:
                break

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

        # Preguntes d'ajuda / procediment ("com donar d'alta un client", etc.) -> RAG directe
        if _RE_PREGUNTA_PROCEDIMENT_RAG.search(pregunta_lower):
            tool_name = "get_rag_knowledge"
            tool_args_rag: Dict[str, Any] = {"query": pregunta}
            tool_res = await self.tool_get_rag_knowledge(db, empresa_id, pregunta)
            if tool_res.get("trobat"):
                doc = tool_res["documents"][0]
                titol = str(doc.get("pregunta") or "").strip()
                prefix = f"Segons la guia «{titol}»:\n" if titol else ""
                resposta = f"{prefix}{doc['resposta']}"
                return resposta, tool_name, tool_args_rag, tool_res, [{"titol": "Base de Coneixement RAG", "url": "/gestio/copilot"}]
            resposta = (
                "No he trobat cap guia o protocol carregat a la Base de Coneixement RAG per a aquesta consulta. "
                "Pots afegir-hi la documentació d'onboarding des de /gestio/copilot → Base Coneixement RAG."
            )
            return resposta, tool_name, tool_args_rag, tool_res, [{"titol": "Base de Coneixement RAG", "url": "/gestio/copilot"}]

        if any(k in pregunta_lower for k in ["pressupost", "pressupostos", "oferta", "ofertes"]):
            tool_name = "get_pending_budgets"
            tool_args: Dict[str, Any] = {"limit": 5}
            tool_res = await self.tool_get_pending_budgets(db, empresa_id, limit=5, caller_role=caller_role)
            return tool_res.get("missatge", "Consulta de pressupostos completada."), tool_name, tool_args, tool_res, [{"titol": "Pressupostos", "url": "/gestio/pressupostos"}]

        if any(k in pregunta_lower for k in ["finca", "finques", "parcel·la", "parcel·les", "parcela", "sigpac"]):
            tool_name = "get_finca_detail"
            tool_args = {"finca_nom_o_id": pregunta}
            tool_res = await self.tool_get_finca_detail(db, empresa_id, pregunta)
            return tool_res.get("missatge", "Consulta de finques completada."), tool_name, tool_args, tool_res, []

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
            tool_name = "search_clients"
            tool_args = {"terme": pregunta, "limit": 5}
            tool_res = await self.tool_search_clients(db, empresa_id, pregunta, limit=5)
            if tool_res.get("trobat"):
                detalls = ", ".join([f"{c['rao_social']} ({c['nif']})" for c in tool_res["clients"]])
                resposta = f"Clients trobats al disc de l'empresa: {detalls}."
            else:
                resposta = f"No s'ha trobat cap client coincident amb '{pregunta}'."
            return resposta, tool_name, tool_args, tool_res, [{"titol": "Directori de Clients", "url": "/gestio/clients"}]

        tool_name = "get_rag_knowledge"
        tool_args = {"query": pregunta}
        tool_res = await self.tool_get_rag_knowledge(db, empresa_id, pregunta)
        if tool_res.get("trobat"):
            doc = tool_res["documents"][0]
            resposta = f"Segons els protocols tècnics de Sevalor: {doc['resposta']}"
        else:
            resposta = (
                "No he trobat un protocol específic a la base de coneixement del disc de l'empresa per a la teva consulta. "
                "Pots reformular la pregunta o consultar les seccions d'ordres de treball, magatzem o flota."
            )

        return resposta, tool_name, tool_args, tool_res, enllacos
