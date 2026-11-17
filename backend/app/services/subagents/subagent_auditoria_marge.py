"""Subagent Auditor Financer, Post-Obra i Protecció de Marge (BOSS Only — Disc Sobirà de l'Empresa)."""

import re
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.subagents.base import BaseSubagent
from app.services.subagents.schemas import SCHEMAS_AUDITORIA_MARGE


def _extract_month(val: Any) -> Optional[int]:
    if not isinstance(val, str) or not val.strip():
        return None
    try:
        return datetime.fromisoformat(val.strip().replace("Z", "+00:00")).month
    except ValueError:
        m = re.match(r"^\d{4}-(\d{2})-\d{2}", val.strip())
        return int(m.group(1)) if m else None


class SubagentAuditoriaMarge(BaseSubagent):
    id = "subagent_auditoria_marge"
    nom = "Subagent Auditor Financer i de Rendibilitat"
    descripcio = (
        "Especialista en conciliació econòmica post-obra, diners pendents de facturar i fuites de marge."
    )
    allowed_roles = ["BOSS"]  # VETO estricte a ENGINYER, SECRETARIA i OPERARI (RF-20.1)
    tools_schema = SCHEMAS_AUDITORIA_MARGE
    system_prompt = (
        "Ets l'auditor financer sobirà de Direcció de SEVALOR (Rol: BOSS). "
        "Analitza desviacions entre costos d'execució i facturació al disc dur de l'empresa, "
        "calcula imports pendents de facturar i protegeix el marge comercial sense cap dada simulada."
    )

    def can_handle(self, query: str, rol: str) -> bool:
        if rol not in ("BOSS", "ADMIN"):
            return False
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
        self,
        tool_name: str,
        args: dict,
        db: AsyncSession,
        empresa_id: uuid.UUID,
        caller_role: Optional[str] = None,
        caller_user_id: Optional[uuid.UUID] = None,
        **kwargs: Any,
    ) -> dict:
        if caller_role and caller_role.upper() not in ("BOSS", "ADMIN"):
            return {
                "trobat": False,
                "denegat_per_rol": True,
                "missatge": "Accés denegat: només Direcció (BOSS) pot accedir a auditories financeres.",
            }
        if tool_name == "get_unbilled_money":
            return await self.tool_get_unbilled_money(db, empresa_id, args.get("mes"))
        if tool_name == "reconcile_post_obra":
            return await self.tool_reconcile_post_obra(db, empresa_id, args.get("codi_ot", ""))
        if tool_name == "detect_margin_leak":
            return await self.tool_detect_margin_leak(db, empresa_id, args.get("codi_ot", ""))
        return {"error": f"Eina no suportada pel subagent financer: {tool_name}"}

    async def _load_ots(self, db: AsyncSession, empresa_id: uuid.UUID) -> List[Dict[str, Any]]:
        act = await self.read_sovereign_category(db, empresa_id, "ots_actives")
        hist = await self.read_sovereign_category(db, empresa_id, "ots_historic")
        vistes: set[str] = set()
        res: List[Dict[str, Any]] = []
        for o in [*act, *hist]:
            oid = str(o.get("id") or o.get("codi") or "")
            if oid and oid in vistes:
                continue
            if oid:
                vistes.add(oid)
            res.append(o)
        return res

    async def tool_get_unbilled_money(
        self, db: AsyncSession, empresa_id: uuid.UUID, mes: Optional[int] = None
    ) -> dict:
        ots = await self._load_ots(db, empresa_id)
        ots_tancades = [
            o
            for o in ots
            if str(o.get("estat") or "").upper() == "TANCADA"
            and (mes is None or _extract_month(o.get("data_planificacio")) == mes)
        ]
        ots_tancades_ids = {str(o.get("id")) for o in ots_tancades if o.get("id")}
        ots_tancades_codis = {str(o.get("codi")) for o in ots_tancades if o.get("codi")}

        articles = await self.read_sovereign_category(db, empresa_id, "magatzem_articles")
        pvp_by_art = {
            str(a.get("id")): float(a.get("preu_venda") or 0.0)
            for a in articles
            if a.get("id")
        }

        pickings = await self.read_sovereign_category(db, empresa_id, "picking")
        cost_materials_esperat = 0.0
        for p in pickings:
            ot_id = str(p.get("ordre_treball_id") or "")
            ot_codi = str(p.get("ordre_treball_codi") or "")
            if ot_id in ots_tancades_ids or ot_codi in ots_tancades_codis:
                qty = float(
                    p.get("quantitat_carregada_pick_in")
                    or p.get("quantitat_retirada")
                    or p.get("quantitat")
                    or 0.0
                )
                raw_pvp = p.get("preu_venda_unitari")
                unit_pvp = (
                    float(raw_pvp)
                    if raw_pvp is not None
                    else pvp_by_art.get(str(p.get("article_id") or ""), 0.0)
                )
                cost_materials_esperat += qty * unit_pvp

        factures = await self.read_sovereign_category(db, empresa_id, "factures_pdf")
        facturat_real = 0.0
        for f in factures:
            linies = f.get("linies")
            if isinstance(linies, list) and linies:
                for lin in linies:
                    if not isinstance(lin, dict):
                        continue
                    obra_id = str(lin.get("obra_id") or lin.get("ordre_treball_id") or f.get("ordre_treball_id") or "")
                    if obra_id in ots_tancades_ids:
                        facturat_real += float(lin.get("preu_venda_unitari") or 0.0) * float(
                            lin.get("quantitat") or 0.0
                        )
            elif str(f.get("ordre_treball_id") or "") in ots_tancades_ids:
                facturat_real += float(f.get("base_imposable") or f.get("total") or 0.0)

        diferencia = round(cost_materials_esperat - facturat_real, 2)
        return {
            "trobat": True,
            "cost_materials_consumit_pvp": round(cost_materials_esperat, 2),
            "facturat_real": round(facturat_real, 2),
            "diner_no_facturat": diferencia,
            "missatge": (
                f"L'anàlisi sobre el disc de l'empresa mostra material consumit a PVP de "
                f"{cost_materials_esperat:.2f}€, facturat real de {facturat_real:.2f}€. "
                f"Pendents de facturar: {diferencia:.2f}€."
            ),
        }

    async def tool_reconcile_post_obra(
        self, db: AsyncSession, empresa_id: uuid.UUID, codi_ot: str
    ) -> dict:
        ots = await self._load_ots(db, empresa_id)
        codi_norm = (codi_ot or "").strip().lower()
        ot = next((o for o in ots if str(o.get("codi") or "").lower() == codi_norm), None)
        if not ot:
            return {"trobat": False, "missatge": f"No s'ha trobat l'ordre de treball '{codi_ot}'."}

        ot_id = str(ot.get("id") or "")
        informes = await self.read_sovereign_category(db, empresa_id, "ots_informes")
        mermes = await self.read_sovereign_category(db, empresa_id, "copilot_mermes_preus")
        aud = next(
            (
                doc
                for doc in [*informes, *mermes]
                if str(doc.get("ordre_treball_id") or "") == ot_id
                or str(doc.get("codi_ot") or "").lower() == codi_norm
            ),
            None,
        )
        if not aud:
            return {
                "trobat": True,
                "codi_ot": codi_ot,
                "reconciliat": False,
                "missatge": f"L'ordre {codi_ot} no té auditoria post-obra liquidada al disc dur.",
            }

        desv_h = float(aud.get("desviacio_hores") or 0.0)
        desv_km = float(aud.get("desviacio_km") or 0.0)
        m_prev = float(aud.get("marge_previst_percentatge") or aud.get("marge_previst") or 0.0)
        m_real = float(aud.get("marge_real_liquidat_percentatge") or aud.get("marge_real") or 0.0)
        alerta_merma = bool(aud.get("alerta_merma_operativa") or aud.get("alerta_merma"))

        return {
            "trobat": True,
            "codi_ot": codi_ot,
            "reconciliat": True,
            "desviacio_hores": desv_h,
            "desviacio_km": desv_km,
            "marge_previst": m_prev,
            "marge_real": m_real,
            "alerta_merma": alerta_merma,
            "missatge": (
                f"Auditoria de {codi_ot}: Desviació hores: {desv_h}h, km: {desv_km}km. "
                f"Marge real liquidat: {m_real}%."
            ),
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

        alerta = bool(rec.get("alerta_merma", False))
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
        self,
        pregunta: str,
        db: AsyncSession,
        empresa_id: uuid.UUID,
        caller_role: Optional[str] = None,
        caller_user_id: Optional[uuid.UUID] = None,
        **kwargs: Any,
    ) -> Tuple[str, Optional[str], Optional[dict], Optional[dict], List[dict]]:
        enllacos: List[dict] = [{"titol": "Control Financer i Marge", "url": "/gestio/economica"}]
        if caller_role and caller_role.upper() not in ("BOSS", "ADMIN"):
            return (
                "Accés denegat: només Direcció (BOSS) pot consultar dades de marge o facturació.",
                None,
                None,
                {"denegat_per_rol": True},
                enllacos,
            )

        ot_match = re.search(r"\bOT[-\d\w]+\b", pregunta, re.IGNORECASE)
        if ot_match and any(k in pregunta.lower() for k in ("marge", "merma", "post-obra", "reconcili", "desviaci")):
            codi_ot = ot_match.group(0).upper()
            tool_name = "reconcile_post_obra"
            tool_args: dict[str, Any] = {"codi_ot": codi_ot}
            tool_res = await self.tool_reconcile_post_obra(db, empresa_id, codi_ot)
            return tool_res.get("missatge", ""), tool_name, tool_args, tool_res, enllacos

        mes_match = re.search(r"\b(?:mes|de)\s*(\d{1,2})\b", pregunta, re.IGNORECASE)
        mes = int(mes_match.group(1)) if mes_match and 1 <= int(mes_match.group(1)) <= 12 else None

        tool_name = "get_unbilled_money"
        tool_args = {"mes": mes}
        tool_res = await self.tool_get_unbilled_money(db, empresa_id, mes)
        resposta = tool_res.get("missatge", "Anàlisi financera executada.")
        return resposta, tool_name, tool_args, tool_res, enllacos
