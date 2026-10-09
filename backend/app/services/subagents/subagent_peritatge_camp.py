"""Subagent de Peritatge Tècnic de Camp, Avaries i Garanties."""

import uuid
from datetime import date, timedelta
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import EinaCustodia, MemorandumTecnicCopilot, OrdreTreball
from app.services.subagents.base import BaseSubagent
from app.services.subagents.schemas import SCHEMAS_PERITATGE_CAMP

TERMINI_GARANTIA_MA_OBRA_DIES = 90


class SubagentPeritatgeCamp(BaseSubagent):
    id = "subagent_peritatge_camp"
    nom = "Subagent Perit Tècnic de Camp"
    descripcio = "Especialista en peritatge d'avaries, garanties vigents de fabricació/mà d'obra i redacció de memoràndums tècnics."
    allowed_roles = ["OPERARI", "CAP_DE_COLLA", "ENGINYER", "BOSS"]
    tools_schema = SCHEMAS_PERITATGE_CAMP
    system_prompt = (
        "Ets el Perit Tècnic de Camp de SEVALOR. "
        "Dictamina sobre el terreny la causa d'avaries, audita si estan en període de garantia oficial "
        "(<90 dies mà d'obra, 2 anys fabricant) i prepara memoràndums tècnics per a validació de l'enginyer. "
        "Respon sempre en català amb rigor professional i tècnic."
    )

    def can_handle(self, query: str, rol: str) -> bool:
        q = query.lower()
        paraules_clau = [
            "garantia",
            "garanties",
            "rma",
            "fabricant",
            "peritatge",
            "avaria",
            "incidència",
            "incidencia",
            "fuita",
            "memorandum",
            "memoràndum",
            "perit",
            "peça trencada",
        ]
        return any(k in q for k in paraules_clau)

    async def execute_tool(
        self, tool_name: str, args: dict, db: AsyncSession, empresa_id: uuid.UUID
    ) -> dict:
        if tool_name == "get_warranty_status":
            return await self.tool_get_warranty_status(
                db,
                empresa_id,
                finca_id=args.get("finca_id"),
                client_id=args.get("client_id"),
                numero_serie=args.get("numero_serie"),
            )
        elif tool_name == "generar_memorandum_tecnic":
            return await self.tool_generar_memorandum_tecnic(
                db,
                empresa_id,
                descripcio=args.get("descripcio_avaria", ""),
                ot_id_str=args.get("ordre_treball_id"),
            )
        return {"error": f"Eina no suportada pel subagent de peritatge: {tool_name}"}

    async def tool_get_warranty_status(
        self,
        db: AsyncSession,
        empresa_id: uuid.UUID,
        finca_id: Optional[str] = None,
        client_id: Optional[str] = None,
        numero_serie: Optional[str] = None,
    ) -> dict:
        f_uuid = uuid.UUID(finca_id) if finca_id else None
        c_uuid = uuid.UUID(client_id) if client_id else None
        avui = date.today()
        fa_un_any = avui - timedelta(days=365)
        alertes = []

        if f_uuid or c_uuid:
            query = (
                select(OrdreTreball)
                .where(
                    OrdreTreball.empresa_id == empresa_id,
                    OrdreTreball.data_planificacio >= fa_un_any,
                )
                .order_by(OrdreTreball.data_planificacio.desc())
            )
            if f_uuid:
                query = query.where(OrdreTreball.finca_id == f_uuid)
            if c_uuid:
                query = query.where(OrdreTreball.client_id == c_uuid)
            ots = (await db.execute(query)).scalars().all()
            if ots:
                darrera = ots[0]
                dies = (avui - darrera.data_planificacio).days
                if dies <= TERMINI_GARANTIA_MA_OBRA_DIES:
                    alertes.append(
                        {
                            "tipus": "GARANTIA_INTERNA_SERVEI",
                            "activa": True,
                            "cost_euros": 0.0,
                            "dies_passats": dies,
                            "missatge": f"Garantia interna de mà d'obra vigent (<90 dies: {dies} dies). Cost 0 € per al client.",
                        }
                    )

        if numero_serie:
            res_eina = await db.execute(
                select(EinaCustodia).where(
                    EinaCustodia.empresa_id == empresa_id,
                    EinaCustodia.numero_serie == numero_serie,
                )
            )
            eina = res_eina.scalar_one_or_none()
            if eina:
                data_compra = eina.created_at.date()
                data_fi = data_compra + timedelta(days=730)
                dies_restants = (data_fi - avui).days
                if dies_restants >= 0:
                    alertes.append(
                        {
                            "tipus": "GARANTIA_FABRICANT",
                            "activa": True,
                            "dies_restants": dies_restants,
                            "missatge": f"Garantia oficial del fabricant vigent fins al {data_fi.isoformat()} ({dies_restants} dies restants).",
                        }
                    )

        return {"trobat": len(alertes) > 0, "garanties": alertes}

    async def tool_generar_memorandum_tecnic(
        self,
        db: AsyncSession,
        empresa_id: uuid.UUID,
        descripcio: str,
        ot_id_str: Optional[str] = None,
    ) -> dict:
        ot_id = uuid.UUID(ot_id_str) if ot_id_str else None
        text_lower = descripcio.lower()

        es_extra = any(
            p in text_lower for p in ["arrel", "roca", "pedra", "extern", "preexistent", "pressio"]
        )
        es_error = any(
            p in text_lower
            for p in ["pala", "error", "oblidat", "descompte", "trencat per nosaltres"]
        )

        if es_extra:
            dictamen = "EXTRA_FACTURABLE"
            motiu = "Dany per causes externes (arrels o terreny rocós). Es proposa com a extra facturable."
            temps = 45
            materials = [
                {"article": "Material reparació dany extern", "quantitat": 1, "unitat": "UT"}
            ]
            cost = 85.50
        elif es_error:
            dictamen = "COST_NO_IMPUTABLE"
            motiu = "Incidència durant l'execució atribuïble a la quadrilla. Cost no imputable al client."
            temps = 30
            materials = [
                {"article": "Material de substitució interna", "quantitat": 1, "unitat": "UT"}
            ]
            cost = 0.00
        else:
            dictamen = "EXTRA_FACTURABLE"
            motiu = "Imprevist no previst al pressupost inicial; requereix feines addicionals."
            temps = 30
            materials = [{"article": "Material reparació bàsica", "quantitat": 1, "unitat": "UT"}]
            cost = 45.00

        memo = MemorandumTecnicCopilot(
            empresa_id=empresa_id,
            ordre_treball_id=ot_id,
            transcripcio_audio=descripcio,
            dictamen_pericial=dictamen,
            motiu_dictamen=motiu,
            estimacio_temps_extra_minuts=temps,
            estimacio_materials_extra=materials,
            cost_estimat_total=cost,
            validat_per_enginyer=False,
            estat="PROPOSTA",
        )
        db.add(memo)
        await db.commit()

        return {
            "trobat": True,
            "memo_id": str(memo.id),
            "dictamen": dictamen,
            "motiu": motiu,
            "cost_estimat": cost,
            "temps_extra_minuts": temps,
            "estat": "PROPOSTA",
            "missatge": f"S'ha generat la proposta de memoràndum {dictamen} ({cost:.2f}€). Pendent de validació de l'enginyer (HITL).",
        }

    async def run_sovereign(
        self, pregunta: str, db: AsyncSession, empresa_id: uuid.UUID
    ) -> Tuple[str, Optional[str], Optional[dict], Optional[dict], List[dict]]:
        enllacos: List[dict] = [{"titol": "Auditoria de Garanties", "url": "/gestio/copilot"}]

        tool_name: Optional[str] = None
        tool_args: Optional[Dict[str, Any]] = None
        tool_res: Optional[dict] = None

        # Si demana generar memoràndum
        if any(
            w in pregunta.lower()
            for w in ["memorandum", "memoràndum", "redacta dictamen", "generar dictamen"]
        ):
            tool_name = "generar_memorandum_tecnic"
            tool_args = {"descripcio_avaria": pregunta}
            tool_res = await self.tool_generar_memorandum_tecnic(db, empresa_id, pregunta)
            return tool_res.get("missatge", ""), tool_name, tool_args, tool_res, enllacos

        # Per defecte: auditar garanties
        tool_name = "get_warranty_status"
        tool_args = {"numero_serie": None}
        tool_res = await self.tool_get_warranty_status(db, empresa_id)

        if tool_res.get("trobat"):
            msg_g = "; ".join([g["missatge"] for g in tool_res["garanties"]])
            resposta = f"Estat de garanties: {msg_g}"
        else:
            resposta = "No hi ha alertes de garantia actives per als elements consultats a la base de dades."

        return resposta, tool_name, tool_args, tool_res, enllacos
