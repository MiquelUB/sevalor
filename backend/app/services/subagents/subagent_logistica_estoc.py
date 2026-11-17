"""Subagent de Magatzem, Logística i Proveïment (Lectura Exclusiva al Disc Sobirà de l'Empresa)."""

import re
import uuid
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.subagents.base import BaseSubagent
from app.services.subagents.schemas import SCHEMAS_LOGISTICA_ESTOC


class SubagentLogisticaEstoc(BaseSubagent):
    id = "subagent_logistica_estoc"
    nom = "Subagent de Magatzem i Proveïment"
    descripcio = (
        "Especialista en inventari físic, disponibilitat d'articles, alertes de ruptura, moviments i replanificació de material."
    )
    allowed_roles = [
        "CAP_DE_MAGATZEM",
        "ENGINYER",
        "SECRETARIA",
        "BOSS",
        "OPERARI",
        "CAP_DE_COLLA",
        "ADMIN",
    ]
    tools_schema = SCHEMAS_LOGISTICA_ESTOC
    system_prompt = (
        "Ets l'assistent expert en Logística i Magatzem de SEVALOR. "
        "La teva funció és verificar l'estoc real als magatzems al disc dur dedicat de l'empresa, "
        "alertar de ruptures d'inventari, auditar moviments i documents de proveïdors, i consultar "
        "l'estat i custòdia d'eines i maquinària. "
        "Tens dues eines mestres d'inventari: 'get_real_stock' per a materials consumibles (tubs, cables, vàlvules, químics) "
        "i 'get_eines_stock' per a eines, maquinària i equips de treball (trepants, radials, escombres, escales). "
        "Si l'usuari pregunta per eines, maquinària o qui té un equip, utilitza sempre 'get_eines_stock'. "
        "Respon sempre en català de forma concisa, professional i basant-te estrictament en les dades del disc."
    )

    def can_handle(self, query: str, rol: str) -> bool:
        q = query.lower()
        if any(
            ocr_k in q
            for ocr_k in [
                "ocr",
                "tiquet",
                "digitalitzar",
                "escanejar",
                "llegir ocr",
                "extreu",
                "extreure",
                "extracció",
                "extraccio",
                "línies",
                "linies",
            ]
        ):
            return False
        if any(f_k in q for f_k in ["vehicle", "furgoneta", "itv", "quota", "fitxatge", "hores"]):
            return False
        paraules_clau = [
            "estoc",
            "stock",
            "cable",
            "tub",
            "tubs",
            "panell",
            "inversor",
            "bateria",
            "electrovalvula",
            "material",
            "materials",
            "inventari",
            "magatzem",
            "proveïdor",
            "proveidor",
            "replanificar",
            "replanifica",
            "reprogramar",
            "moviment",
            "moviments",
            "ruptura",
            "ruptures",
            "alerta estoc",
            "mancança",
            "albarà de proveïdor",
            "albara proveidor",
            "comanda de compra",
            "eina",
            "eines",
            "trepant",
            "trepants",
            "radial",
            "radials",
            "escombra",
            "escombres",
            "maquinària",
            "maquinaria",
            "escala",
            "escales",
            "martell",
            "serra",
            "calibració",
            "calibracio",
        ]
        return any(k in q for k in paraules_clau)

    @staticmethod
    def _is_article_record(item: Dict[str, Any]) -> bool:
        if item.get("tipus_registre") == "MOVIMENT_ESTOC" or item.get("tipus_moviment"):
            return False
        return bool(item.get("nom") or item.get("referencia_inventari") or item.get("referencia"))

    @staticmethod
    def _calc_article_stock(art: Dict[str, Any]) -> float:
        estocs = art.get("estocs")
        if isinstance(estocs, list) and estocs:
            total = 0.0
            for e in estocs:
                if isinstance(e, dict):
                    fis = float(e.get("quantitat_fisica") or 0.0)
                    res = float(e.get("quantitat_virtual_reservada") or 0.0)
                    total += fis - res
            return total
        if art.get("quantitat_fisica") is not None:
            fis = float(art.get("quantitat_fisica") or 0.0)
            res = float(art.get("quantitat_virtual_reservada") or 0.0)
            return fis - res
        if art.get("estoc_disponible") is not None:
            return float(art.get("estoc_disponible") or 0.0)
        return float(art.get("estoc_real") or 0.0)

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
        if tool_name == "get_real_stock":
            return await self.tool_get_real_stock(db, empresa_id, args.get("article_ref", ""))
        if tool_name == "get_eines_stock":
            return await self.tool_get_eines_stock(db, empresa_id, args.get("terme_cerca", ""))
        if tool_name == "replanificar_ot":
            return await self.tool_replanificar_ot(
                db, empresa_id, args.get("codi_ot", ""), args.get("nova_data", "")
            )
        if tool_name == "check_allocation_safety":
            return await self.tool_check_allocation_safety(
                db, empresa_id, args.get("article_ref", ""), float(args.get("quantitat", 0.0))
            )
        if tool_name == "propose_purchase_order":
            return await self.tool_propose_purchase_order(
                db, empresa_id, args.get("article_ref", ""), float(args.get("quantitat", 0.0))
            )
        if tool_name == "get_stock_movements":
            return await self.tool_get_stock_movements(
                db,
                empresa_id,
                material_id=args.get("material_id"),
                limit=int(args.get("limit", 10)),
            )
        if tool_name == "get_low_stock_alerts":
            return await self.tool_get_low_stock_alerts(
                db,
                empresa_id,
                familia=args.get("familia"),
            )
        if tool_name == "get_supplier_docs":
            return await self.tool_get_supplier_docs(
                db,
                empresa_id,
                proveidor_nom=args.get("proveidor_nom"),
                tipus=args.get("tipus"),
                limit=int(args.get("limit", 5)),
                caller_role=caller_role,
            )
        return {"error": f"Eina no suportada pel subagent de logistica: {tool_name}"}

    async def tool_get_real_stock(
        self, db: AsyncSession, empresa_id: uuid.UUID, article_ref: str
    ) -> dict:
        terme = (article_ref or "").strip().lower()
        stopwords = {
            "material",
            "materials",
            "familia",
            "família",
            "article",
            "articles",
            "d",
            "de",
            "del",
            "dels",
            "la",
            "el",
            "els",
            "les",
            "per",
            "obra",
            "tenim",
            "disposem",
            "quants",
            "queden",
            "queda",
            "al",
            "als",
            "en",
            "i",
            "un",
            "una",
            "uns",
            "unes",
            "hi",
            "ha",
            "quin",
            "quina",
            "quins",
            "quines",
            "estoc",
            "stock",
            "magatzem",
            "inventari",
        }
        words = [w for w in terme.split() if w not in stopwords and len(w) > 1]

        sinonims_map = {
            "tub": ["tub", "canonada", "pe-100", "polietil"],
            "tubs": ["tub", "canonada", "pe-100", "polietil"],
            "canonada": ["tub", "canonada", "pe-100"],
            "canonades": ["tub", "canonada", "pe-100"],
            "tuberia": ["tub", "canonada"],
            "valvula": ["valv", "bermad", "vàlvul"],
            "vàlvula": ["valv", "bermad", "vàlvul"],
            "valvules": ["valv", "bermad", "vàlvul"],
            "vàlvules": ["valv", "bermad", "vàlvul"],
            "electrovalvula": ["valv", "bermad", "electrovàlvul", "electrovalvul"],
            "electrovàlvula": ["valv", "bermad", "electrovàlvul", "electrovalvul"],
            "filtre": ["filtr", "anell"],
            "filtres": ["filtr", "anell"],
            "bomba": ["bomb", "submergibl"],
            "bombes": ["bomb", "submergibl"],
            "aspersor": ["aspers", "sectorial"],
            "aspersors": ["aspers", "sectorial"],
            "cable": ["cabl"],
            "cables": ["cabl"],
        }

        search_tokens = set(words)
        for w in words:
            if w in sinonims_map:
                search_tokens.update(sinonims_map[w])

        raw_records = await self.read_sovereign_category(db, empresa_id, "magatzem_articles")
        tots_articles = [r for r in raw_records if self._is_article_record(r)]

        articles: List[Dict[str, Any]] = []
        if search_tokens:
            for art in tots_articles:
                ref_val = str(art.get("referencia_inventari") or art.get("referencia") or "").lower()
                nom_val = str(art.get("nom") or "").lower()
                fam_val = str(art.get("familia") or "").lower()
                blob = f"{ref_val} {nom_val} {fam_val}"
                if any(tok in blob for tok in search_tokens):
                    articles.append(art)

        es_consulta_generica = not words or any(
            g in terme for g in ("tots", "general", "global", "inventari", "magatzem")
        )
        if not articles and es_consulta_generica:
            articles = [a for a in tots_articles if a.get("actiu", True)][:25]

        if not articles:
            families_disponibles = sorted(
                {str(a.get("familia")) for a in tots_articles if a.get("familia")}
            )
            fam_str = ", ".join(families_disponibles) if families_disponibles else "Cap família registrada"
            return {
                "trobat": False,
                "article_cercat": article_ref,
                "total_disponible": 0.0,
                "articles": [],
                "missatge": (
                    f"No s'ha trobat cap article coincident amb '{article_ref}' al disc dur de l'empresa. "
                    f"Famílies disponibles a l'inventari: {fam_str}."
                ),
            }

        articles_data: List[Dict[str, Any]] = []
        total_disponible_global = 0.0
        for art in articles:
            stock_val = self._calc_article_stock(art)
            total_disponible_global += stock_val
            articles_data.append(
                {
                    "id": str(art.get("id")),
                    "referencia": art.get("referencia_inventari") or art.get("referencia"),
                    "nom": art.get("nom"),
                    "estoc_disponible": stock_val,
                    "unitat_mesura": art.get("unitat_mesura") or "UNITAT",
                    "estoc_minim": float(art.get("estoc_minim") or 0.0),
                    "estoc_optim": float(art.get("estoc_optim") or 0.0),
                    "familia": art.get("familia"),
                }
            )

        return {
            "trobat": True,
            "article_cercat": article_ref,
            "total_disponible": total_disponible_global,
            "articles": articles_data,
        }

    async def tool_replanificar_ot(
        self, db: AsyncSession, empresa_id: uuid.UUID, codi_ot: str, nova_data: str
    ) -> dict:
        ots = await self.read_sovereign_category(db, empresa_id, "ots_actives")
        ot = next(
            (o for o in ots if str(o.get("codi", "")).upper() == codi_ot.strip().upper()),
            None,
        )
        if not ot:
            return {"trobat": False, "missatge": f"No s'ha trobat l'ordre de treball {codi_ot}."}

        return {
            "trobat": True,
            "requires_confirmation": True,
            "action": "confirm_replanificar_ot",
            "payload": {
                "ot_id": str(ot.get("id")),
                "codi_ot": codi_ot,
                "nova_data": nova_data,
                "titol": ot.get("titol"),
            },
            "missatge": (
                f"He preparat la proposta per moure l'ordre {codi_ot} ({ot.get('titol')}) al dia {nova_data}. "
                "Necessito la teva confirmació per executar l'acció."
            ),
        }

    async def tool_check_allocation_safety(
        self, db: AsyncSession, empresa_id: uuid.UUID, article_ref: str, quantitat: float
    ) -> dict:
        st = await self.tool_get_real_stock(db, empresa_id, article_ref)
        if not st.get("trobat") or not st.get("articles"):
            return {
                "segur": False,
                "missatge": f"No s'ha trobat l'article '{article_ref}' per comprovar disponibilitat.",
            }

        art_item = st["articles"][0]
        disponible = art_item["estoc_disponible"]
        minim = art_item["estoc_minim"]
        resultat_post_consum = disponible - quantitat
        es_segur = resultat_post_consum >= minim

        return {
            "trobat": True,
            "segur": es_segur,
            "article": art_item["nom"],
            "disponible_actual": disponible,
            "sollicitat": quantitat,
            "estoc_resultant": resultat_post_consum,
            "estoc_minim": minim,
            "missatge": (
                f"L'assignació és segura (saldo restant: {resultat_post_consum:.1f} >= mínim: {minim:.1f})."
                if es_segur
                else f"Alerta de trencament d'estoc: el consum deixarà {resultat_post_consum:.1f} unitats (mínim exigit: {minim:.1f})."
            ),
        }

    async def tool_propose_purchase_order(
        self, db: AsyncSession, empresa_id: uuid.UUID, article_ref: str, quantitat: float
    ) -> dict:
        st = await self.tool_get_real_stock(db, empresa_id, article_ref)
        if not st.get("trobat") or not st.get("articles"):
            return {
                "proposta_creada": False,
                "missatge": f"No es pot proposar comanda: article '{article_ref}' inexistent.",
            }

        art_data = st["articles"][0]
        proveidors = await self.read_sovereign_category(db, empresa_id, "proveidors")
        prov = next((p for p in proveidors if p.get("actiu", True)), None)
        prov_nom = str(prov.get("rao_social")) if prov and prov.get("rao_social") else "Proveïdor General"

        return {
            "proposta_creada": True,
            "article": art_data["nom"],
            "quantitat_suggerida": quantitat,
            "proveidor_habitual": prov_nom,
            "missatge": (
                f"Proposta de comanda de compra preparada: {quantitat} unitats de '{art_data['nom']}' a {prov_nom}."
            ),
        }

    async def tool_get_stock_movements(
        self,
        db: AsyncSession,
        empresa_id: uuid.UUID,
        material_id: Optional[str] = None,
        limit: int = 10,
    ) -> dict:
        raw_mag = await self.read_sovereign_category(db, empresa_id, "magatzem_articles")
        picking_docs = await self.read_sovereign_category(db, empresa_id, "picking")

        arts_by_id = {
            str(r.get("id")): r
            for r in raw_mag
            if self._is_article_record(r) and r.get("id")
        }

        candidats: List[Dict[str, Any]] = []
        for r in raw_mag:
            if r.get("tipus_registre") == "MOVIMENT_ESTOC" or r.get("tipus_moviment"):
                art = arts_by_id.get(str(r.get("article_id")), {})
                candidats.append(
                    {
                        "id": str(r.get("id")),
                        "article_id": str(r.get("article_id") or ""),
                        "article_nom": r.get("article_nom") or art.get("nom") or "Article",
                        "referencia": r.get("referencia") or art.get("referencia_inventari") or art.get("referencia"),
                        "tipus_moviment": r.get("tipus_moviment") or "MOVIMENT",
                        "quantitat": float(r.get("quantitat") or 0.0),
                        "referencia_document": r.get("referencia_document"),
                        "notes": r.get("notes"),
                        "data": r.get("created_at") or r.get("data"),
                    }
                )
            elif isinstance(r.get("moviments"), list):
                for m in r["moviments"]:
                    if isinstance(m, dict):
                        candidats.append(
                            {
                                "id": str(m.get("id") or r.get("id")),
                                "article_id": str(r.get("id") or ""),
                                "article_nom": r.get("nom"),
                                "referencia": r.get("referencia_inventari") or r.get("referencia"),
                                "tipus_moviment": m.get("tipus_moviment") or "MOVIMENT",
                                "quantitat": float(m.get("quantitat") or 0.0),
                                "referencia_document": m.get("referencia_document"),
                                "notes": m.get("notes"),
                                "data": m.get("created_at") or m.get("data"),
                            }
                        )

        for p in picking_docs:
            art = arts_by_id.get(str(p.get("article_id")), {})
            candidats.append(
                {
                    "id": str(p.get("id")),
                    "article_id": str(p.get("article_id") or ""),
                    "article_nom": p.get("article_nom") or art.get("nom") or "Material Picking",
                    "referencia": p.get("referencia") or art.get("referencia_inventari"),
                    "tipus_moviment": p.get("tipus_moviment") or "SORTIDA_PICKING",
                    "quantitat": float(p.get("quantitat_retirada") or p.get("quantitat_solicitada") or p.get("quantitat") or 0.0),
                    "referencia_document": p.get("ordre_treball_codi") or p.get("referencia_document"),
                    "notes": p.get("notes"),
                    "data": p.get("created_at") or p.get("data"),
                }
            )

        mat_filter = (material_id or "").strip().lower()
        filtrats: List[Dict[str, Any]] = []
        for m in candidats:
            if mat_filter:
                blob = f"{m.get('article_id', '')} {m.get('article_nom', '')} {m.get('referencia', '')}".lower()
                if mat_filter not in blob:
                    continue
            filtrats.append(
                {
                    "id": m["id"],
                    "article_nom": m["article_nom"],
                    "referencia": m["referencia"],
                    "tipus_moviment": m["tipus_moviment"],
                    "quantitat": m["quantitat"],
                    "referencia_document": m["referencia_document"],
                    "notes": m["notes"],
                    "data": m["data"],
                }
            )
            if len(filtrats) >= limit:
                break

        return {
            "trobat": len(filtrats) > 0,
            "total": len(filtrats),
            "moviments": filtrats,
            "missatge": (
                f"S'han trobat {len(filtrats)} moviments recents d'estoc."
                if filtrats
                else "No s'ha trobat cap moviment d'estoc registrat."
            ),
        }

    async def tool_get_low_stock_alerts(
        self,
        db: AsyncSession,
        empresa_id: uuid.UUID,
        familia: Optional[str] = None,
    ) -> dict:
        raw_mag = await self.read_sovereign_category(db, empresa_id, "magatzem_articles")
        articles = [r for r in raw_mag if self._is_article_record(r) and r.get("actiu", True)]
        fam_filter = (familia or "").strip().lower()

        alertes: List[Dict[str, Any]] = []
        for art in articles:
            art_fam = str(art.get("familia") or "")
            if fam_filter and fam_filter not in art_fam.lower():
                continue
            stock_val = self._calc_article_stock(art)
            minim = float(art.get("estoc_minim") or 0.0)
            if stock_val <= minim:
                alertes.append(
                    {
                        "article_id": str(art.get("id")),
                        "referencia": art.get("referencia_inventari") or art.get("referencia"),
                        "nom": art.get("nom"),
                        "familia": art.get("familia"),
                        "estoc_disponible": stock_val,
                        "estoc_minim": minim,
                        "estoc_optim": float(art.get("estoc_optim") or 0.0),
                        "deficit": max(0.0, minim - stock_val),
                        "unitat_mesura": art.get("unitat_mesura") or "UNITAT",
                    }
                )

        return {
            "trobat": len(alertes) > 0,
            "total_alertes": len(alertes),
            "alertes": alertes,
            "missatge": (
                f"S'han detectat {len(alertes)} articles amb risc de ruptura d'estoc (saldo <= mínim)."
                if alertes
                else "Tots els articles tenen nivells d'estoc suficients per sobre del mínim."
            ),
        }

    async def tool_get_supplier_docs(
        self,
        db: AsyncSession,
        empresa_id: uuid.UUID,
        proveidor_nom: Optional[str] = None,
        tipus: Optional[str] = None,
        limit: int = 5,
        caller_role: Optional[str] = None,
    ) -> dict:
        docs: List[Dict[str, Any]] = []
        tipus_filtre = (tipus or "").strip().lower()
        prov_filter = (proveidor_nom or "").strip().lower()

        proveidors = await self.read_sovereign_category(db, empresa_id, "proveidors")
        prov_map = {str(p.get("id")): str(p.get("rao_social") or "") for p in proveidors if p.get("id")}

        if tipus_filtre in ("", "albara", "albarans", "albarà"):
            albarans = await self.read_sovereign_category(db, empresa_id, "albarans")
            for alb in albarans:
                p_nom = (
                    prov_map.get(str(alb.get("proveidor_id")))
                    or str(alb.get("proveidor_nom") or alb.get("proveidor") or "Proveïdor")
                )
                if prov_filter and prov_filter not in p_nom.lower():
                    continue
                docs.append(
                    {
                        "id": str(alb.get("id")),
                        "tipus": "ALBARA",
                        "numero": alb.get("numero_albara") or alb.get("numero"),
                        "proveidor": p_nom,
                        "data": alb.get("data_albara") or alb.get("data"),
                        "estat": alb.get("estat"),
                    }
                )
                if len(docs) >= limit:
                    break

        if tipus_filtre in ("", "factura", "factures") and caller_role in ("BOSS", "ADMIN"):
            factures_prov = await self.read_sovereign_category(db, empresa_id, "factures_proveidors")
            for fac in factures_prov:
                p_nom = (
                    prov_map.get(str(fac.get("proveidor_id")))
                    or str(fac.get("proveidor_nom") or fac.get("proveidor") or "Proveïdor")
                )
                if prov_filter and prov_filter not in p_nom.lower():
                    continue
                docs.append(
                    {
                        "id": str(fac.get("id")),
                        "tipus": "FACTURA",
                        "numero": fac.get("numero_factura") or fac.get("numero"),
                        "proveidor": p_nom,
                        "data": fac.get("data_factura") or fac.get("data"),
                        "estat": fac.get("estat"),
                        "total": float(fac.get("total") or 0.0),
                    }
                )
                if len(docs) >= limit * 2:
                    break

        return {
            "trobat": len(docs) > 0,
            "total_documents": len(docs),
            "documents": docs,
            "missatge": (
                f"S'han trobat {len(docs)} documents de proveïdor."
                if docs
                else "No s'ha trobat cap document de proveïdor amb els criteris indicats."
            ),
        }

    async def tool_get_eines_stock(
        self, db: AsyncSession, empresa_id: uuid.UUID, terme_cerca: Optional[str] = None
    ) -> dict:
        eines_raw = await self.read_sovereign_category(db, empresa_id, "magatzem_eines")
        operaris_raw = await self.read_sovereign_category(db, empresa_id, "operaris")
        op_map = {
            str(u.get("id")): f"{u.get('nom') or ''} {u.get('cognoms') or ''}".strip()
            for u in operaris_raw
            if u.get("id")
        }

        filtre = (terme_cerca or "").strip().lower()
        llista: List[Dict[str, Any]] = []
        for e in eines_raw:
            blob = f"{e.get('nom', '')} {e.get('model', '')} {e.get('numero_serie', '')}".lower()
            if filtre and filtre not in blob:
                continue
            custodi = (
                op_map.get(str(e.get("custodiat_per_operari_id")))
                or str(e.get("custodi") or e.get("custodiat_per") or "").strip()
                or "Cap (Disponible a nau)"
            )
            ubicacio = str(e.get("ubicacio") or e.get("magatzem_nom") or "Nau Central Base")
            es_furgoneta = bool(e.get("es_furgoneta") or e.get("magatzem_tipus") == "FURGONETA")
            llista.append(
                {
                    "id": str(e.get("id")),
                    "nom": e.get("nom"),
                    "model": e.get("model"),
                    "numero_serie": e.get("numero_serie"),
                    "estat": e.get("estat"),
                    "ubicacio": ubicacio,
                    "es_furgoneta": es_furgoneta,
                    "custodi": custodi,
                    "propera_calibracio": e.get("data_propera_calibracio"),
                }
            )

        return {
            "total_trobades": len(llista),
            "eines": llista,
            "resum": (
                f"S'han trobat {len(llista)} eines/equips registrats."
                if llista
                else "No s'ha trobat cap eina o maquinària registrada amb aquest criteri."
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
        enllacos: List[dict] = [{"titol": "Inventari de Magatzem", "url": "/gestio/magatzem"}]

        if any(
            w in pregunta_lower
            for w in ["ruptura", "ruptures", "alerta estoc", "falta estoc", "baix estoc", "sota minim", "sota mínim"]
        ):
            tool_name = "get_low_stock_alerts"
            tool_args: dict[str, Any] = {"familia": None}
            tool_res = await self.tool_get_low_stock_alerts(db, empresa_id)
            if tool_res.get("trobat"):
                detalls = ", ".join(
                    [f"{a['nom']} (disponible: {a['estoc_disponible']}, mínim: {a['estoc_minim']})" for a in tool_res["alertes"][:5]]
                )
                resposta = f"Alerta de magatzem: {tool_res['total_alertes']} articles tenen estoc crític. Principals: {detalls}."
            else:
                resposta = "Tots els materials es troben per sobre del nivell d'estoc mínim de seguretat."
            return resposta, tool_name, tool_args, tool_res, enllacos

        if any(
            w in pregunta_lower
            for w in ["moviment", "moviments", "entrades i sortides", "entrades de material", "sortides de material"]
        ):
            tool_name = "get_stock_movements"
            tool_args = {"material_id": None, "limit": 10}
            tool_res = await self.tool_get_stock_movements(db, empresa_id, limit=10)
            if tool_res.get("trobat"):
                detalls = ", ".join(
                    [f"{m['article_nom']} ({m['tipus_moviment']} {m['quantitat']})" for m in tool_res["moviments"][:4]]
                )
                resposta = f"Últims moviments d'estoc registrats: {detalls}."
            else:
                resposta = "No hi ha constància de moviments recents d'estoc al magatzem."
            return resposta, tool_name, tool_args, tool_res, enllacos

        if any(
            w in pregunta_lower
            for w in ["albarà de proveïdor", "albara de proveidor", "albarans de compra", "albarans de proveïdor", "documents de proveïdor"]
        ):
            tool_name = "get_supplier_docs"
            tool_args = {"proveidor_nom": None, "tipus": "albara", "limit": 5}
            tool_res = await self.tool_get_supplier_docs(
                db, empresa_id, tipus="albara", limit=5, caller_role=caller_role
            )
            return tool_res.get("missatge", "Consulta de documents de proveïdor completada."), tool_name, tool_args, tool_res, enllacos

        if any(w in pregunta_lower for w in ["replanificar", "replanifica", "moure al dia", "passar al dia"]):
            ot_match = re.search(r"\bOT[-\d\w]+\b", pregunta, re.IGNORECASE)
            data_match = re.search(r"\b\d{4}-\d{2}-\d{2}\b", pregunta)
            if ot_match and data_match:
                codi_ot = ot_match.group(0).upper()
                nova_data = data_match.group(0)
                t_args = {"codi_ot": codi_ot, "nova_data": nova_data}
                t_res = await self.tool_replanificar_ot(db, empresa_id, codi_ot, nova_data)
                return t_res.get("missatge", ""), "replanificar_ot", t_args, t_res, enllacos

        paraules_eines = [
            "eina",
            "eines",
            "trepant",
            "trepants",
            "radial",
            "radials",
            "escombra",
            "escombres",
            "maquinària",
            "maquinaria",
            "escala",
            "escales",
            "serra",
            "martell",
            "calibració",
            "calibracio",
            "qui té",
        ]
        if any(w in pregunta_lower for w in paraules_eines):
            tool_name = "get_eines_stock"
            terme_eina = ""
            for pe in ["trepant", "radial", "escombra", "escala", "serra", "martell"]:
                if pe in pregunta_lower:
                    terme_eina = pe
                    break
            tool_args = {"terme_cerca": terme_eina or None}
            tool_res = await self.tool_get_eines_stock(db, empresa_id, terme_eina or None)
            total = tool_res["total_trobades"]
            if total > 0:
                detalls = "; ".join(
                    [
                        f"{e['nom']} ({e['estat']}, Ubicació: {e['ubicacio']}, Custodi: {e['custodi']})"
                        for e in tool_res["eines"][:5]
                    ]
                )
                resposta = f"S'han trobat {total} eines/equips registrats. Detall: {detalls}."
            else:
                resposta = f"No s'ha trobat cap eina o equip registrat per a '{terme_eina or 'la cerca'}'."
            return resposta, tool_name, tool_args, tool_res, enllacos

        raw_mag = await self.read_sovereign_category(db, empresa_id, "magatzem_articles")
        articles_disc = [r for r in raw_mag if self._is_article_record(r)]

        target_ref = ""
        best_match_len = 0
        for art in articles_disc:
            nom_l = str(art.get("nom") or "").lower()
            ref_l = str(art.get("referencia_inventari") or art.get("referencia") or "").lower()
            if nom_l and nom_l in pregunta_lower and len(nom_l) > best_match_len:
                target_ref = str(art.get("nom"))
                best_match_len = len(nom_l)
            elif ref_l and ref_l in pregunta_lower and len(ref_l) > best_match_len:
                target_ref = str(art.get("referencia_inventari") or art.get("referencia"))
                best_match_len = len(ref_l)

        if not target_ref:
            stopwords = {
                "tenim",
                "suficient",
                "per",
                "l'obra",
                "obra",
                "quant",
                "quants",
                "queden",
                "disposem",
                "de",
                "d'",
                "ens",
                "queda",
                "el",
                "la",
                "els",
                "les",
            }
            cleaned = " ".join([w for w in pregunta_lower.split() if w not in stopwords and len(w) > 1])
            target_ref = cleaned or pregunta_lower

        tool_name = "get_real_stock"
        tool_args = {"article_ref": target_ref}
        tool_res = await self.tool_get_real_stock(db, empresa_id, target_ref)

        if tool_res.get("trobat"):
            tot = tool_res["total_disponible"]
            tot_str = f"{int(tot)}" if float(tot).is_integer() else f"{tot:.1f}"
            detalls = ", ".join(
                [
                    f"{a['nom']} ({int(a['estoc_disponible']) if float(a['estoc_disponible']).is_integer() else a['estoc_disponible']} {a['unitat_mesura']})"
                    for a in tool_res["articles"]
                ]
            )
            resposta = (
                f"Segons la consulta en temps real d'inventari al disc de l'empresa (eina get_real_stock), "
                f"disposem de {tot_str} unitats disponibles en total. Detall d'estoc: {detalls}."
            )
        else:
            resposta = f"No s'ha trobat cap registre d'estoc per a '{target_ref}' al disc dur de l'empresa."

        return resposta, tool_name, tool_args, tool_res, enllacos
