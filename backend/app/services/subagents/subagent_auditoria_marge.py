"""Subagent Auditor Financer, Post-Obra i Protecció de Marge (BOSS Only)."""

import re
import uuid
from typing import List, Optional, Tuple

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import (
    Article,
    AuditoriaPostObra,
    FacturaLinia,
    FullaPicking,
    LiniaPicking,
    OrdreTreball,
)
from app.services.subagents.base import BaseSubagent
from app.services.subagents.schemas import SCHEMAS_AUDITORIA_MARGE


class SubagentAuditoriaMarge(BaseSubagent):
    id = "subagent_auditoria_marge"
    nom = "Subagent Auditor Financer i de Rendibilitat"
    descripcio = "Especialista en conciliació econòmica post-obra, diners pendents de facturar i fuites de marge."
    allowed_roles = ["BOSS"]  # VETO estricte a ENGINYER, SECRETARIA i OPERARI (RF-20.1)
    tools_schema = SCHEMAS_AUDITORIA_MARGE
    system_prompt = (
        "Ets l'auditor financer sobirà de Direcció de SEVALOR (Rol: BOSS). "
        "Analitza desviacions entre costos d'execució i facturació, calcula imports pendents de facturar "
        "i protegeix el marge comercial. Proporciona xifres precises basades en PostgreSQL sota Zero Mock."
    )

    def can_handle(self, query: str, rol: str) -> bool:
        q = query.lower()
        paraules_clau = [
            "unbilled",
            "no facturat",
            "falta facturar",
            "marge",
            "rendibilitat",
            "desviació",
            "desviacio",
            "reconciliació",
            "reconciliacio",
            "post-obra",
            "leak",
            "merma",
            "cost real",
            "diners",
            "facturacio",
            "facturació",
        ]
        return any(k in q for k in paraules_clau)

    async def execute_tool(
        self, tool_name: str, args: dict, db: AsyncSession, empresa_id: uuid.UUID
    ) -> dict:
        if tool_name == "get_unbilled_money":
            return await self.tool_get_unbilled_money(db, empresa_id, args.get("mes"))
        elif tool_name == "reconcile_post_obra":
            return await self.tool_reconcile_post_obra(db, empresa_id, args.get("codi_ot", ""))
        elif tool_name == "detect_margin_leak":
            return await self.tool_detect_margin_leak(db, empresa_id, args.get("codi_ot", ""))
        return {"error": f"Eina no suportada pel subagent financer: {tool_name}"}

    async def tool_get_unbilled_money(
        self, db: AsyncSession, empresa_id: uuid.UUID, mes: Optional[int] = None
    ) -> dict:
        condicions_ot = [OrdreTreball.empresa_id == empresa_id, OrdreTreball.estat == "TANCADA"]
        if mes:
            condicions_ot.append(func.extract("month", OrdreTreball.data_planificacio) == mes)

        stmt_cost = (
            select(func.sum(LiniaPicking.quantitat_carregada_pick_in * Article.preu_venda))
            .join(FullaPicking, LiniaPicking.picking_id == FullaPicking.id)
            .join(OrdreTreball, FullaPicking.ordre_treball_id == OrdreTreball.id)
            .join(Article, LiniaPicking.article_id == Article.id)
            .where(and_(*condicions_ot))
        )
        res_cost = await db.execute(stmt_cost)
        cost_materials_esperat = res_cost.scalar() or 0.0

        stmt_fact = (
            select(func.sum(FacturaLinia.preu_venda_unitari * FacturaLinia.quantitat))
            .join(OrdreTreball, FacturaLinia.obra_id == OrdreTreball.id)
            .where(and_(*condicions_ot))
        )
        res_fact = await db.execute(stmt_fact)
        facturat_real = res_fact.scalar() or 0.0

        diferencia = float(cost_materials_esperat) - float(facturat_real)

        return {
            "trobat": True,
            "cost_materials_consumit_pvp": float(cost_materials_esperat),
            "facturat_real": float(facturat_real),
            "diner_no_facturat": diferencia,
            "missatge": f"L'anàlisi mostra que el material consumit a preu de venda val {cost_materials_esperat:.2f}€, però només s'ha facturat {facturat_real:.2f}€. Falten per facturar {diferencia:.2f}€.",
        }

    async def tool_reconcile_post_obra(
        self, db: AsyncSession, empresa_id: uuid.UUID, codi_ot: str
    ) -> dict:
        stmt_ot = select(OrdreTreball).where(
            OrdreTreball.empresa_id == empresa_id, OrdreTreball.codi == codi_ot
        )
        res_ot = await db.execute(stmt_ot)
        ot = res_ot.scalar_one_or_none()
        if not ot:
            return {"trobat": False, "missatge": f"No s'ha trobat l'ordre de treball '{codi_ot}'."}

        stmt_aud = select(AuditoriaPostObra).where(
            AuditoriaPostObra.empresa_id == empresa_id, AuditoriaPostObra.ordre_treball_id == ot.id
        )
        res_aud = await db.execute(stmt_aud)
        aud = res_aud.scalar_one_or_none()

        if not aud:
            return {
                "trobat": True,
                "codi_ot": codi_ot,
                "reconciliat": False,
                "missatge": f"L'ordre {codi_ot} no té auditoria post-obra liquidada encara.",
            }

        return {
            "trobat": True,
            "codi_ot": codi_ot,
            "reconciliat": True,
            "desviacio_hores": float(aud.desviacio_hores),
            "desviacio_km": float(aud.desviacio_km),
            "marge_previst": float(aud.marge_previst_percentatge),
            "marge_real": float(aud.marge_real_liquidat_percentatge),
            "alerta_merma": aud.alerta_merma_operativa,
            "missatge": f"Auditoria de {codi_ot}: Desviació hores: {aud.desviacio_hores}h, km: {aud.desviacio_km}km. Marge real liquidat: {aud.marge_real_liquidat_percentatge}%.",
        }

    async def tool_detect_margin_leak(
        self, db: AsyncSession, empresa_id: uuid.UUID, codi_ot: str
    ) -> dict:
        rec = await self.tool_reconcile_post_obra(db, empresa_id, codi_ot)
        if not rec.get("trobat") or not rec.get("reconciliat"):
            return {
                "alerta_merma": False,
                "missatge": f"No hi ha dades per detectar merma a l'ordre {codi_ot}.",
            }

        alerta = rec.get("alerta_merma", False)
        return {
            "alerta_merma": alerta,
            "codi_ot": codi_ot,
            "missatge": (
                f"ALERTA: S'ha detectat consum de material excessiu (>250%) a {codi_ot}."
                if alerta
                else f"Consums dintre dels llindars permesos a {codi_ot}."
            ),
        }

    async def run_sovereign(
        self, pregunta: str, db: AsyncSession, empresa_id: uuid.UUID
    ) -> Tuple[str, Optional[str], Optional[dict], Optional[dict], List[dict]]:
        enllacos: List[dict] = [{"titol": "Control Financer i Marge", "url": "/gestio/economica"}]

        # Mes específic
        mes_match = re.search(r"\b(?:mes|de)\s*(\d{1,2})\b", pregunta, re.IGNORECASE)
        mes = int(mes_match.group(1)) if mes_match and 1 <= int(mes_match.group(1)) <= 12 else None

        tool_name = "get_unbilled_money"
        tool_args = {"mes": mes}
        tool_res = await self.tool_get_unbilled_money(db, empresa_id, mes)

        resposta = tool_res.get("missatge", "Anàlisi financera executada.")
        return resposta, tool_name, tool_args, tool_res, enllacos
