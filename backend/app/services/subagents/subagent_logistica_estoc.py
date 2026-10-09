"""Subagent de Magatzem, Logística i Proveïment."""

import re
import uuid
from typing import List, Optional, Tuple

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import Article, EstocMagatzem, OrdreTreball, Proveidor
from app.services.subagents.base import BaseSubagent
from app.services.subagents.schemas import SCHEMAS_LOGISTICA_ESTOC


class SubagentLogisticaEstoc(BaseSubagent):
    id = "subagent_logistica_estoc"
    nom = "Subagent de Magatzem i Proveïment"
    descripcio = (
        "Especialista en inventari físic, disponibilitat d'articles i replanificació de material."
    )
    allowed_roles = ["CAP_DE_MAGATZEM", "ENGINYER", "SECRETARIA", "BOSS"]
    tools_schema = SCHEMAS_LOGISTICA_ESTOC
    system_prompt = (
        "Ets l'assistent expert en Logística i Magatzem de SEVALOR. "
        "La teva funció és verificar l'estoc real als magatzems, alertar de ruptures d'inventari "
        "i proposar replanificacions. Respon sempre en català de forma concisa, professional i "
        "basant-te estrictament en les dades d'estoc consultades a la base de dades."
    )

    def can_handle(self, query: str, rol: str) -> bool:
        q = query.lower()
        if any(
            ocr_k in q
            for ocr_k in ["albarà", "albara", "ocr", "tiquet", "digitalitzar", "escanejar"]
        ):
            return False
        paraules_clau = [
            "estoc",
            "stock",
            "quantitat",
            "queden",
            "queda",
            "disposem",
            "cable",
            "tub",
            "electrovalvula",
            "material",
            "inventari",
            "magatzem",
            "proveïdor",
            "proveidor",
            "replanificar",
            "replanifica",
            "reprogramar",
        ]
        return any(k in q for k in paraules_clau)

    async def execute_tool(
        self, tool_name: str, args: dict, db: AsyncSession, empresa_id: uuid.UUID
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
        return {"error": f"Eina no suportada pel subagent de logistica: {tool_name}"}

    async def tool_get_real_stock(
        self, db: AsyncSession, empresa_id: uuid.UUID, article_ref: str
    ) -> dict:
        terme = article_ref.strip()
        cerca = f"%{terme}%"
        stmt = select(Article).where(
            Article.empresa_id == empresa_id,
            or_(Article.referencia_inventari.ilike(cerca), Article.nom.ilike(cerca)),
        )
        res = await db.execute(stmt)
        articles = res.scalars().all()

        if not articles:
            paraules = [p for p in terme.split() if len(p) > 2]
            if paraules:
                clauses = [
                    or_(Article.referencia_inventari.ilike(f"%{p}%"), Article.nom.ilike(f"%{p}%"))
                    for p in paraules
                ]
                stmt_p = select(Article).where(Article.empresa_id == empresa_id, or_(*clauses))
                res_p = await db.execute(stmt_p)
                articles = res_p.scalars().all()

        if not articles:
            return {
                "trobat": False,
                "article_cercat": article_ref,
                "total_disponible": 0.0,
                "articles": [],
                "missatge": f"No s'ha trobat cap article amb la referència o nom '{article_ref}'.",
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

    async def run_sovereign(
        self, pregunta: str, db: AsyncSession, empresa_id: uuid.UUID
    ) -> Tuple[str, Optional[str], Optional[dict], Optional[dict], List[dict]]:
        pregunta_lower = pregunta.lower()
        enllacos: List[dict] = [{"titol": "Inventari de Magatzem", "url": "/gestio/magatzem"}]

        # Replanificació
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

        # Estoc
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
