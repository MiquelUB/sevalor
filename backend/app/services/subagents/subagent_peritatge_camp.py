"""Subagent de Peritatge Tècnic de Camp, Avaries i Garanties (Disc Sobirà de l'Empresa)."""

import uuid
from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.subagents.base import BaseSubagent
from app.services.subagents.schemas import SCHEMAS_PERITATGE_CAMP

TERMINI_GARANTIA_MA_OBRA_DIES = 90


def _parse_date(val: Any) -> Optional[date]:
    if isinstance(val, date) and not isinstance(val, datetime):
        return val
    if isinstance(val, datetime):
        return val.date()
    if not isinstance(val, str) or not val.strip():
        return None
    try:
        return date.fromisoformat(val.strip()[:10])
    except ValueError:
        return None


class SubagentPeritatgeCamp(BaseSubagent):
    id = "subagent_peritatge_camp"
    nom = "Subagent Perit Tècnic de Camp"
    descripcio = (
        "Especialista en peritatge d'avaries, garanties vigents de fabricació/mà d'obra i redacció de memoràndums tècnics."
    )
    allowed_roles = ["OPERARI", "CAP_DE_COLLA", "ENGINYER", "BOSS", "ADMIN"]
    tools_schema = SCHEMAS_PERITATGE_CAMP
    system_prompt = (
        "Ets el Perit Tècnic de Camp de SEVALOR. "
        "Dictamina sobre el terreny la causa d'avaries, audita si estan en període de garantia oficial "
        "(<90 dies mà d'obra, 2 anys fabricant) i prepara memoràndums tècnics al disc dur dedicat de l'empresa "
        "per a validació de l'enginyer. Respon sempre en català amb rigor professional i sense preus inventats."
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
        self,
        tool_name: str,
        args: dict,
        db: AsyncSession,
        empresa_id: uuid.UUID,
        caller_role: Optional[str] = None,
        caller_user_id: Optional[uuid.UUID] = None,
        **kwargs: Any,
    ) -> dict:
        if tool_name == "get_warranty_status":
            return await self.tool_get_warranty_status(
                db,
                empresa_id,
                finca_nom=args.get("finca_nom"),
                client_nom=args.get("client_nom"),
                finca_id=args.get("finca_id"),
                client_id=args.get("client_id"),
                numero_serie=args.get("numero_serie"),
            )
        if tool_name == "generar_memorandum_tecnic":
            return await self.tool_generar_memorandum_tecnic(
                db,
                empresa_id,
                descripcio_avaria=args.get("descripcio_avaria", ""),
                codi_ot=args.get("codi_ot"),
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
        finca_nom: Optional[str] = None,
        client_nom: Optional[str] = None,
    ) -> dict:
        avui = date.today()
        fa_un_any = avui - timedelta(days=365)
        alertes: List[Dict[str, Any]] = []

        # Resolució d'identificadors humans (`finca_nom`, `client_nom`) a IDs del disc sobirà
        resolved_finca_id = finca_id.strip() if finca_id else None
        resolved_client_id = client_id.strip() if client_id else None

        if not resolved_finca_id and finca_nom and finca_nom.strip():
            f_low = finca_nom.strip().lower()
            finques = await self.read_sovereign_category(db, empresa_id, "finques")
            m_f = next(
                (
                    f
                    for f in finques
                    if str(f.get("id") or "") == finca_nom.strip()
                    or f_low in str(f.get("nom") or "").lower()
                ),
                None,
            )
            if m_f and m_f.get("id"):
                resolved_finca_id = str(m_f["id"])

        if not resolved_client_id and client_nom and client_nom.strip():
            c_low = client_nom.strip().lower()
            clients = await self.read_sovereign_category(db, empresa_id, "clients")
            m_c = next(
                (
                    c
                    for c in clients
                    if str(c.get("id") or "") == client_nom.strip()
                    or c_low in str(c.get("rao_social") or c.get("nom") or "").lower()
                ),
                None,
            )
            if m_c and m_c.get("id"):
                resolved_client_id = str(m_c["id"])

        if resolved_finca_id or resolved_client_id:
            ots_act = await self.read_sovereign_category(db, empresa_id, "ots_actives")
            ots_hist = await self.read_sovereign_category(db, empresa_id, "ots_historic")
            candidates: List[Dict[str, Any]] = []
            for o in [*ots_act, *ots_hist]:
                if resolved_finca_id and str(o.get("finca_id") or "") != resolved_finca_id:
                    continue
                if resolved_client_id and str(o.get("client_id") or "") != resolved_client_id:
                    continue
                d_plan = _parse_date(o.get("data_planificacio") or o.get("created_at"))
                if d_plan and d_plan >= fa_un_any:
                    candidates.append({**o, "_d_plan": d_plan})

            candidates.sort(key=lambda x: x["_d_plan"], reverse=True)
            if candidates:
                darrera = candidates[0]
                dies = (avui - darrera["_d_plan"]).days
                if dies <= TERMINI_GARANTIA_MA_OBRA_DIES:
                    alertes.append(
                        {
                            "tipus": "GARANTIA_INTERNA_SERVEI",
                            "activa": True,
                            "cost_euros": 0.0,
                            "dies_passats": dies,
                            "missatge": (
                                f"Garantia interna de mà d'obra vigent (<90 dies: {dies} dies). "
                                "Cost 0 € per al client."
                            ),
                        }
                    )

        if numero_serie:
            sn_clean = numero_serie.strip().lower()
            eines = await self.read_sovereign_category(db, empresa_id, "magatzem_eines")
            eina = next(
                (e for e in eines if str(e.get("numero_serie") or "").strip().lower() == sn_clean),
                None,
            )
            if eina:
                data_compra = _parse_date(eina.get("data_compra") or eina.get("created_at"))
                if data_compra:
                    data_fi = data_compra + timedelta(days=730)
                    dies_restants = (data_fi - avui).days
                    if dies_restants >= 0:
                        alertes.append(
                            {
                                "tipus": "GARANTIA_FABRICANT",
                                "activa": True,
                                "dies_restants": dies_restants,
                                "missatge": (
                                    f"Garantia oficial del fabricant vigent fins al {data_fi.isoformat()} "
                                    f"({dies_restants} dies restants)."
                                ),
                            }
                        )

        return {"trobat": len(alertes) > 0, "garanties": alertes}

    async def tool_generar_memorandum_tecnic(
        self,
        db: AsyncSession,
        empresa_id: uuid.UUID,
        descripcio_avaria: str,
        ot_id_str: Optional[str] = None,
        codi_ot: Optional[str] = None,
    ) -> dict:
        resolved_ot_id = ot_id_str
        if not resolved_ot_id and codi_ot and codi_ot.strip():
            ots = await self.read_sovereign_category(db, empresa_id, "ots_actives")
            c_up = codi_ot.strip().upper()
            m_ot = next(
                (o for o in ots if str(o.get("codi") or "").upper() == c_up or str(o.get("id") or "") == codi_ot.strip()),
                None,
            )
            resolved_ot_id = str(m_ot.get("id")) if m_ot and m_ot.get("id") else codi_ot.strip()

        descripcio = descripcio_avaria
        ot_id_str = resolved_ot_id
        text_lower = (descripcio or "").lower()

        es_extra = any(
            p in text_lower for p in ["arrel", "roca", "pedra", "extern", "preexistent", "pressio"]
        )
        es_error = any(
            p in text_lower
            for p in ["pala", "error", "oblidat", "descompte", "trencat per nosaltres"]
        )

        # Cercar materials reals al catàleg del disc dur de l'empresa sense preus hardcodejats
        articles_disc = await self.read_sovereign_category(db, empresa_id, "magatzem_articles")
        materials: List[Dict[str, Any]] = []
        cost_calculat = 0.0
        for art in articles_disc:
            nom_art = str(art.get("nom") or "").strip()
            if nom_art and any(tok in text_lower for tok in nom_art.lower().split() if len(tok) >= 4):
                pvp = float(art.get("preu_venda") or 0.0)
                materials.append(
                    {
                        "article": nom_art,
                        "quantitat": 1,
                        "unitat": art.get("unitat_mesura") or "UT",
                        "preu_unitari": pvp if pvp > 0 else None,
                    }
                )
                cost_calculat += pvp

        if es_error:
            dictamen = "COST_NO_IMPUTABLE"
            motiu = "Incidència durant l'execució atribuïble a la quadrilla. Cost no imputable al client."
            cost_estimat: Optional[float] = 0.0
        elif es_extra:
            dictamen = "EXTRA_FACTURABLE"
            motiu = "Dany per causes externes (arrels o terreny rocós). Es proposa com a extra facturable."
            cost_estimat = round(cost_calculat, 2) if cost_calculat > 0 else None
        else:
            dictamen = "EXTRA_FACTURABLE"
            motiu = "Imprevist no previst al pressupost inicial; requereix validació tècnica i econòmica."
            cost_estimat = round(cost_calculat, 2) if cost_calculat > 0 else None

        memo_id = str(uuid.uuid4())
        memo_payload: Dict[str, Any] = {
            "id": memo_id,
            "ordre_treball_id": ot_id_str,
            "transcripcio_audio": descripcio,
            "dictamen_pericial": dictamen,
            "motiu_dictamen": motiu,
            "estimacio_materials_extra": materials,
            "cost_estimat_total": cost_estimat,
            "validat_per_enginyer": False,
            "estat": "PROPOSTA",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        await self.save_sovereign_entity(
            db, empresa_id, "copilot_memorandums", memo_id, memo_payload
        )

        cost_txt = (
            f"{cost_estimat:.2f}€ (segons catàleg)"
            if cost_estimat is not None
            else "pendent de valoració econòmica per l'enginyer"
        )
        return {
            "trobat": True,
            "memo_id": memo_id,
            "dictamen": dictamen,
            "motiu": motiu,
            "materials_detectats": materials,
            "cost_estimat": cost_estimat,
            "estat": "PROPOSTA",
            "missatge": (
                f"S'ha desat la proposta de memoràndum {dictamen} al disc dur de l'empresa "
                f"(cost {cost_txt}). Pendent de validació humana de l'enginyer (HITL)."
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
        enllacos: List[dict] = [{"titol": "Auditoria de Garanties", "url": "/gestio/copilot"}]

        if any(
            w in pregunta.lower()
            for w in ["memorandum", "memoràndum", "redacta dictamen", "generar dictamen"]
        ):
            tool_name = "generar_memorandum_tecnic"
            tool_args: dict[str, Any] = {"descripcio_avaria": pregunta}
            tool_res = await self.tool_generar_memorandum_tecnic(db, empresa_id, pregunta)
            return tool_res.get("missatge", ""), tool_name, tool_args, tool_res, enllacos

        # Comprovar si hi ha un número de sèrie o client/finca a la consulta o incidències registrades
        eines = await self.read_sovereign_category(db, empresa_id, "magatzem_eines")
        sn_trobat: Optional[str] = None
        q_low = pregunta.lower()
        for e in eines:
            sn = str(e.get("numero_serie") or "").strip()
            if sn and sn.lower() in q_low:
                sn_trobat = sn
                break

        tool_name = "get_warranty_status"
        tool_args = {"numero_serie": sn_trobat}
        tool_res = await self.tool_get_warranty_status(db, empresa_id, numero_serie=sn_trobat)

        if tool_res.get("trobat"):
            msg_g = "; ".join([g["missatge"] for g in tool_res["garanties"]])
            resposta = f"Estat de garanties: {msg_g}"
        else:
            resposta = "No hi ha alertes de garantia actives per als elements consultats al disc dur de l'empresa."

        return resposta, tool_name, tool_args, tool_res, enllacos
