"""Subagent de Magatzem, Logística i Proveïment."""

import re
import uuid
from typing import Any, List, Optional, Tuple

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import (
    AlbaraProveidor,
    Article,
    EstocMagatzem,
    FacturaProveidor,
    MovimentEstoc,
    OrdreTreball,
    Proveidor,
)
from app.services.subagents.base import BaseSubagent
from app.services.subagents.schemas import SCHEMAS_LOGISTICA_ESTOC


class SubagentLogisticaEstoc(BaseSubagent):
    id = "subagent_logistica_estoc"
    nom = "Subagent de Magatzem i Proveïment"
    descripcio = (
        "Especialista en inventari físic, disponibilitat d'articles, alertes de ruptura, moviments i replanificació de material."
    )
    allowed_roles = ["CAP_DE_MAGATZEM", "ENGINYER", "SECRETARIA", "BOSS", "OPERARI", "CAP_DE_COLLA", "ADMIN"]
    tools_schema = SCHEMAS_LOGISTICA_ESTOC
    system_prompt = (
        "Ets l'assistent expert en Logística i Magatzem de SEVALOR. "
        "La teva funció és verificar l'estoc real als magatzems, alertar de ruptures d'inventari, "
        "auditar moviments i documents de proveïdors, i proposar replanificacions. Respon sempre en català "
        "de forma concisa, professional i basant-te estrictament en les dades consultades a la base de dades."
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
        # No capturar consultes de flota ni hores/fitxatges d'equip
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
        if tool_name == "get_real_stock":
            return await self.tool_get_real_stock(db, empresa_id, args.get("article_ref", ""))
        elif tool_name == "replanificar_ot":
            return await self.tool_replanificar_ot(
                db, empresa_id, args.get("codi_ot", ""), args.get("nova_data", "")
            )
        elif tool_name == "check_allocation_safety":
            return await self.tool_check_allocation_safety(
                db, empresa_id, args.get("article_ref", ""), float(args.get("quantitat", 0.0))
            )
        elif tool_name == "propose_purchase_order":
            return await self.tool_propose_purchase_order(
                db, empresa_id, args.get("article_ref", ""), float(args.get("quantitat", 0.0))
            )
        elif tool_name == "get_stock_movements":
            return await self.tool_get_stock_movements(
                db,
                empresa_id,
                material_id=args.get("material_id"),
                limit=int(args.get("limit", 10)),
            )
        elif tool_name == "get_low_stock_alerts":
            return await self.tool_get_low_stock_alerts(
                db,
                empresa_id,
                familia=args.get("familia"),
            )
        elif tool_name == "get_supplier_docs":
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
        terme = article_ref.strip().lower()
        stopwords = {
            "material", "familia", "família", "article", "articles", "d", "de", "del",
            "dels", "la", "el", "els", "les", "per", "obra", "tenim", "disposem", "quants",
            "queden", "queda", "al", "als", "en", "i", "un", "una", "uns", "unes", "hi", "ha"
        }
        words = [w for w in terme.split() if w not in stopwords and len(w) > 1]
        cerca = f"%{' '.join(words) if words else terme}%"
        stmt = select(Article).where(
            Article.empresa_id == empresa_id,
            or_(
                Article.referencia_inventari.ilike(cerca),
                Article.nom.ilike(cerca),
                Article.familia.ilike(cerca),
            ),
        )
        res = await db.execute(stmt)
        articles = res.scalars().all()

        if not articles and words:
            clauses = []
            for p in words:
                clauses.append(Article.referencia_inventari.ilike(f"%{p}%"))
                clauses.append(Article.nom.ilike(f"%{p}%"))
                clauses.append(Article.familia.ilike(f"%{p}%"))
                if p.endswith("s") and len(p) > 2:
                    stem = p[:-1]
                    clauses.append(Article.referencia_inventari.ilike(f"%{stem}%"))
                    clauses.append(Article.nom.ilike(f"%{stem}%"))
                    clauses.append(Article.familia.ilike(f"%{stem}%"))
            stmt_p = select(Article).where(Article.empresa_id == empresa_id, or_(*clauses))
            res_p = await db.execute(stmt_p)
            articles = res_p.scalars().all()

        if not articles:
            return {
                "trobat": False,
                "article_cercat": article_ref,
                "total_disponible": 0.0,
                "articles": [],
                "missatge": f"No s'ha trobat cap article coincident amb '{article_ref}' als magatzems de l'empresa.",
            }

        articles_data = []
        total_disponible_global = 0.0

        for art in articles:
            q_stock = select(
                func.coalesce(
                    func.sum(
                        EstocMagatzem.quantitat_fisica - EstocMagatzem.quantitat_virtual_reservada
                    ),
                    0,
                )
            ).where(EstocMagatzem.article_id == art.id, EstocMagatzem.empresa_id == empresa_id)
            stock_val = float((await db.execute(q_stock)).scalar_one() or 0.0)
            total_disponible_global += stock_val
            articles_data.append(
                {
                    "id": str(art.id),
                    "referencia": art.referencia_inventari,
                    "nom": art.nom,
                    "estoc_disponible": stock_val,
                    "unitat_mesura": art.unitat_mesura,
                    "estoc_minim": float(art.estoc_minim),
                    "estoc_optim": float(art.estoc_optim),
                    "familia": art.familia,
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
        q = select(OrdreTreball).where(
            OrdreTreball.empresa_id == empresa_id, OrdreTreball.codi == codi_ot
        )
        res = await db.execute(q)
        ot = res.scalar_one_or_none()
        if not ot:
            return {"trobat": False, "missatge": f"No s'ha trobat l'ordre de treball {codi_ot}."}

        return {
            "trobat": True,
            "requires_confirmation": True,
            "action": "confirm_replanificar_ot",
            "payload": {
                "ot_id": str(ot.id),
                "codi_ot": codi_ot,
                "nova_data": nova_data,
                "titol": ot.titol,
            },
            "missatge": f"He preparat la proposta per moure l'ordre {codi_ot} ({ot.titol}) al dia {nova_data}. Necessito la teva confirmació per executar l'acció.",
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
        q_prov = select(Proveidor).where(
            Proveidor.empresa_id == empresa_id, Proveidor.actiu.is_(True)
        )
        res_prov = await db.execute(q_prov)
        prov = res_prov.scalars().first()

        return {
            "proposta_creada": True,
            "article": art_data["nom"],
            "quantitat_suggerida": quantitat,
            "proveidor_habitual": prov.rao_social if prov else "Proveïdor General",
            "missatge": f"Proposta de comanda de compra preparada: {quantitat} unitats de '{art_data['nom']}' a {prov.rao_social if prov else 'Proveïdor per defecte'}.",
        }

    async def tool_get_stock_movements(
        self,
        db: AsyncSession,
        empresa_id: uuid.UUID,
        material_id: Optional[str] = None,
        limit: int = 10,
    ) -> dict:
        stmt = (
            select(MovimentEstoc, Article.nom, Article.referencia_inventari)
            .join(Article, MovimentEstoc.article_id == Article.id)
            .where(MovimentEstoc.empresa_id == empresa_id)
        )
        if material_id and material_id.strip():
            mat_clean = material_id.strip()
            try:
                m_uuid = uuid.UUID(mat_clean)
                stmt = stmt.where(MovimentEstoc.article_id == m_uuid)
            except (ValueError, AttributeError):
                terme = f"%{mat_clean}%"
                stmt = stmt.where(
                    or_(
                        Article.referencia_inventari.ilike(terme),
                        Article.nom.ilike(terme),
                    )
                )

        stmt = stmt.order_by(MovimentEstoc.created_at.desc()).limit(limit)
        res = await db.execute(stmt)
        rows = res.all()
        moviments = [
            {
                "id": str(m.id),
                "article_nom": art_nom,
                "referencia": art_ref,
                "tipus_moviment": m.tipus_moviment,
                "quantitat": float(m.quantitat) if m.quantitat is not None else 0.0,
                "referencia_document": m.referencia_document,
                "notes": m.notes,
                "data": m.created_at.isoformat() if m.created_at else None,
            }
            for m, art_nom, art_ref in rows
        ]
        return {
            "trobat": len(moviments) > 0,
            "total": len(moviments),
            "moviments": moviments,
            "missatge": (
                f"S'han trobat {len(moviments)} moviments recents d'estoc."
                if moviments
                else "No s'ha trobat cap moviment d'estoc registrat."
            ),
        }

    async def tool_get_low_stock_alerts(
        self,
        db: AsyncSession,
        empresa_id: uuid.UUID,
        familia: Optional[str] = None,
    ) -> dict:
        stmt_arts = select(Article).where(
            Article.empresa_id == empresa_id,
            Article.actiu.is_(True),
        )
        if familia and familia.strip():
            stmt_arts = stmt_arts.where(Article.familia.ilike(f"%{familia.strip()}%"))

        articles = (await db.execute(stmt_arts)).scalars().all()
        alertes = []
        for art in articles:
            q_stock = select(
                func.coalesce(
                    func.sum(
                        EstocMagatzem.quantitat_fisica - EstocMagatzem.quantitat_virtual_reservada
                    ),
                    0,
                )
            ).where(EstocMagatzem.article_id == art.id, EstocMagatzem.empresa_id == empresa_id)
            stock_val = float((await db.execute(q_stock)).scalar_one() or 0.0)
            minim = float(art.estoc_minim) if art.estoc_minim is not None else 0.0
            if stock_val <= minim:
                alertes.append(
                    {
                        "article_id": str(art.id),
                        "referencia": art.referencia_inventari,
                        "nom": art.nom,
                        "familia": art.familia,
                        "estoc_disponible": stock_val,
                        "estoc_minim": minim,
                        "estoc_optim": float(art.estoc_optim) if art.estoc_optim is not None else 0.0,
                        "deficit": max(0.0, minim - stock_val),
                        "unitat_mesura": art.unitat_mesura,
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
        docs = []
        tipus_filtre = (tipus or "").strip().lower()

        # 1. Albarans de compra
        if tipus_filtre in ("", "albara", "albarans", "albarà"):
            stmt_alb = (
                select(AlbaraProveidor, Proveidor.rao_social)
                .join(Proveidor, AlbaraProveidor.proveidor_id == Proveidor.id)
                .where(AlbaraProveidor.empresa_id == empresa_id)
            )
            if proveidor_nom and proveidor_nom.strip():
                stmt_alb = stmt_alb.where(Proveidor.rao_social.ilike(f"%{proveidor_nom.strip()}%"))
            stmt_alb = stmt_alb.order_by(AlbaraProveidor.created_at.desc()).limit(limit)
            res_alb = await db.execute(stmt_alb)
            for alb, prov_nom in res_alb.all():
                docs.append(
                    {
                        "id": str(alb.id),
                        "tipus": "ALBARA",
                        "numero": alb.numero_albara,
                        "proveidor": prov_nom,
                        "data": alb.data_albara.isoformat() if alb.data_albara else None,
                        "estat": alb.estat,
                    }
                )

        # 2. Factures de proveïdor (només BOSS / ADMIN)
        if tipus_filtre in ("", "factura", "factures") and caller_role in ("BOSS", "ADMIN"):
            stmt_fac = (
                select(FacturaProveidor, Proveidor.rao_social)
                .join(Proveidor, FacturaProveidor.proveidor_id == Proveidor.id)
                .where(FacturaProveidor.empresa_id == empresa_id)
            )
            if proveidor_nom and proveidor_nom.strip():
                stmt_fac = stmt_fac.where(Proveidor.rao_social.ilike(f"%{proveidor_nom.strip()}%"))
            stmt_fac = stmt_fac.order_by(FacturaProveidor.created_at.desc()).limit(limit)
            res_fac = await db.execute(stmt_fac)
            for fac, prov_nom in res_fac.all():
                docs.append(
                    {
                        "id": str(fac.id),
                        "tipus": "FACTURA",
                        "numero": fac.numero_factura,
                        "proveidor": prov_nom,
                        "data": fac.data_factura.isoformat() if fac.data_factura else None,
                        "estat": fac.estat,
                        "total": float(fac.total) if fac.total is not None else 0.0,
                    }
                )

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

        # 1. Alertes de baix estoc / ruptura d'estoc
        if any(
            w in pregunta_lower
            for w in ["ruptura", "ruptures", "alerta estoc", "falta estoc", "baix estoc", "sota minim", "sota mínim"]
        ):
            tool_name = "get_low_stock_alerts"
            tool_args = {"familia": None}
            tool_res = await self.tool_get_low_stock_alerts(db, empresa_id)
            if tool_res.get("trobat"):
                detalls = ", ".join([f"{a['nom']} (disponible: {a['estoc_disponible']}, mínim: {a['estoc_minim']})" for a in tool_res["alertes"][:5]])
                resposta = f"Alerta de magatzem: {tool_res['total_alertes']} articles tenen estoc crític. Principals: {detalls}."
            else:
                resposta = "Tots els materials es troben per sobre del nivell d'estoc mínim de seguretat."
            return resposta, tool_name, tool_args, tool_res, enllacos

        # 2. Moviments recents d'estoc
        if any(
            w in pregunta_lower
            for w in ["moviment", "moviments", "entrades i sortides", "entrades de material", "sortides de material"]
        ):
            tool_name = "get_stock_movements"
            tool_args = {"material_id": None, "limit": 10}
            tool_res = await self.tool_get_stock_movements(db, empresa_id, limit=10)
            if tool_res.get("trobat"):
                detalls = ", ".join([f"{m['article_nom']} ({m['tipus_moviment']} {m['quantitat']})" for m in tool_res["moviments"][:4]])
                resposta = f"Últims moviments d'estoc registrats: {detalls}."
            else:
                resposta = "No hi ha constància de moviments recents d'estoc al magatzem."
            return resposta, tool_name, tool_args, tool_res, enllacos

        # 3. Documents de proveïdor (albarans / comandes de compra)
        if any(
            w in pregunta_lower
            for w in ["albarà de proveïdor", "albara de proveidor", "albarans de compra", "albarans de proveïdor", "documents de proveïdor"]
        ):
            tool_name = "get_supplier_docs"
            tool_args = {"proveidor_nom": None, "tipus": "albara", "limit": 5}
            tool_res = await self.tool_get_supplier_docs(db, empresa_id, tipus="albara", limit=5, caller_role=caller_role)
            return tool_res.get("missatge", "Consulta de documents de proveïdor completada."), tool_name, tool_args, tool_res, enllacos

        # 4. Replanificació d'OT
        if any(
            w in pregunta_lower
            for w in ["replanificar", "replanifica", "moure al dia", "passar al dia"]
        ):
            ot_match = re.search(r"\bOT[-\d\w]+\b", pregunta, re.IGNORECASE)
            data_match = re.search(r"\b\d{4}-\d{2}-\d{2}\b", pregunta)
            if ot_match and data_match:
                codi_ot = ot_match.group(0).upper()
                nova_data = data_match.group(0)
                t_args = {"codi_ot": codi_ot, "nova_data": nova_data}
                t_res = await self.tool_replanificar_ot(db, empresa_id, codi_ot, nova_data)
                return t_res.get("missatge", ""), "replanificar_ot", t_args, t_res, enllacos

        # 5. Estoc físic real d'un article
        stmt_arts = select(Article).where(Article.empresa_id == empresa_id)
        articles_db = (await db.execute(stmt_arts)).scalars().all()

        target_ref = ""
        best_match_len = 0
        for art in articles_db:
            nom_l = art.nom.lower()
            ref_l = art.referencia_inventari.lower()
            if nom_l in pregunta_lower and len(nom_l) > best_match_len:
                target_ref = art.nom
                best_match_len = len(nom_l)
            elif ref_l in pregunta_lower and len(ref_l) > best_match_len:
                target_ref = art.referencia_inventari
                best_match_len = len(ref_l)

        if not target_ref:
            stopwords = [
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
            ]
            cleaned = " ".join(
                [w for w in pregunta_lower.split() if w not in stopwords and len(w) > 1]
            )
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
                f"Segons la consulta en temps real d'inventari a magatzem (eina get_real_stock), "
                f"disposem de {tot_str} unitats disponibles en total. Detall d'estoc: {detalls}."
            )
        else:
            resposta = f"No s'ha trobat cap registre d'estoc per a '{target_ref}' als magatzems de l'empresa."

        return resposta, tool_name, tool_args, tool_res, enllacos
