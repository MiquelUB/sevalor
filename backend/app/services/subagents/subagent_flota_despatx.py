"""Subagent de Flota, Desplaçaments i Rutes."""

import re
import uuid
from datetime import date, timedelta
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import DocumentFlota, OrdreTreball, Vehicle
from app.services.subagents.base import BaseSubagent
from app.services.subagents.schemas import SCHEMAS_FLOTA_DESPATX


def calcular_distancia_haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Fórmula Haversine per calcular la distància en km entre dos punts GPS."""
    import math

    r = 6371.0  # Radi de la Terra en km
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return round(r * c, 2)


class SubagentFlotaDespatx(BaseSubagent):
    id = "subagent_flota_despatx"
    nom = "Subagent de Flota i Desplaçaments"
    descripcio = "Especialista en geolocalització de vehicles, càlcul Haversine de proximitat i control d'ITV/assegurances."
    allowed_roles = ["SECRETARIA", "ENGINYER", "BOSS"]
    tools_schema = SCHEMAS_FLOTA_DESPATX
    system_prompt = (
        "Ets l'assistent expert en Flota i Despatx de SEVALOR. "
        "Optimitza el desplaçament de vehicles, audita venciments d'ITV i assegurances i localitza "
        "el vehicle més proper a una urgència. Respon en català de forma concisa i precisa."
    )

    def can_handle(self, query: str, rol: str) -> bool:
        q = query.lower()
        paraules_clau = [
            "vehicle",
            "furgoneta",
            "cotxe",
            "matricula",
            "matrícula",
            "itv",
            "asseguranca",
            "assegurança",
            "més a prop",
            "mes aprop",
            "mes a prop",
            "més proper",
            "mes proper",
            "proper",
            "aprop",
            "proxim",
            "pròxim",
            "closest",
            "cercano",
            "flota",
        ]
        return any(k in q for k in paraules_clau)

    async def execute_tool(
        self, tool_name: str, args: dict, db: AsyncSession, empresa_id: uuid.UUID
    ) -> dict:
        if tool_name == "get_closest_vehicle":
            lat = float(args.get("lat", 0.0))
            lng = float(args.get("lng", 0.0))
            return await self.tool_get_closest_vehicle(db, empresa_id, lat, lng)
        elif tool_name == "get_vehicle_info":
            return await self.tool_get_vehicle_info(db, empresa_id, args.get("matricula", ""))
        elif tool_name == "audit_itv_insurance_fleet":
            dies = int(args.get("dies_marge", 30))
            return await self.tool_audit_itv_insurance_fleet(db, empresa_id, dies)
        return {"error": f"Eina no suportada pel subagent de flota: {tool_name}"}

    async def tool_get_closest_vehicle(
        self, db: AsyncSession, empresa_id: uuid.UUID, lat: float, lng: float
    ) -> dict:
        stmt_v = select(Vehicle).where(Vehicle.empresa_id == empresa_id)
        res_v = await db.execute(stmt_v)
        vehicles = res_v.scalars().all()

        if not vehicles:
            return {"trobat": False, "missatge": "No hi ha cap vehicle registrat a la flota."}

        stmt_ot = (
            select(OrdreTreball)
            .where(
                OrdreTreball.empresa_id == empresa_id,
                OrdreTreball.vehicle_id.isnot(None),
                OrdreTreball.estat.in_(["EN_OBRA", "EN_RUTA", "EN_CURS", "PENDENT"]),
            )
            .order_by(OrdreTreball.created_at.desc())
        )
        res_ot = await db.execute(stmt_ot)
        ots = res_ot.scalars().all()
        vehicle_ot_map = {}
        for ot in ots:
            if ot.vehicle_id not in vehicle_ot_map:
                vehicle_ot_map[ot.vehicle_id] = ot

        llista = []
        for v in vehicles:
            v_lat, v_lng = 41.3851, 2.1734
            ot_rel = vehicle_ot_map.get(v.id)
            if ot_rel and ot_rel.adreca:
                m = re.findall(r"[-+]?\d+\.\d+", ot_rel.adreca)
                if len(m) >= 2:
                    v_lat, v_lng = float(m[0]), float(m[1])
                elif "," in ot_rel.adreca:
                    try:
                        parts = [float(p.strip()) for p in ot_rel.adreca.split(",")]
                        if len(parts) >= 2:
                            v_lat, v_lng = parts[0], parts[1]
                    except (ValueError, TypeError):
                        pass

            dist = calcular_distancia_haversine(lat, lng, v_lat, v_lng)
            llista.append(
                {
                    "vehicle_id": str(v.id),
                    "matricula": v.matricula,
                    "marca": v.marca,
                    "model": v.model,
                    "estat": v.estat,
                    "distancia_km": dist,
                    "lat": v_lat,
                    "lng": v_lng,
                    "ordre_treball_actual": ot_rel.codi if ot_rel else None,
                }
            )

        llista.sort(key=lambda x: x["distancia_km"])  # type: ignore
        closest = llista[0]

        return {
            "trobat": True,
            "coordenades_cercades": {"lat": lat, "lng": lng},
            "vehicle_mes_proper": closest,
            "tots_els_vehicles": llista,
        }

    async def tool_get_vehicle_info(
        self, db: AsyncSession, empresa_id: uuid.UUID, matricula: str
    ) -> dict:
        stmt = select(Vehicle).where(
            Vehicle.empresa_id == empresa_id, Vehicle.matricula.ilike(f"%{matricula.strip()}%")
        )
        res = await db.execute(stmt)
        v = res.scalars().first()
        if not v:
            return {
                "trobat": False,
                "matricula_cercada": matricula,
                "missatge": f"No s'ha trobat cap vehicle amb la matrícula '{matricula}'.",
            }

        stmt_docs = select(DocumentFlota).where(
            DocumentFlota.vehicle_id == v.id, DocumentFlota.empresa_id == empresa_id
        )
        res_docs = await db.execute(stmt_docs)
        docs = res_docs.scalars().all()
        docs_list = [
            {
                "tipus": d.tipus_document,
                "nom_arxiu": d.nom_arxiu,
                "data": d.data_document.isoformat() if d.data_document else None,
            }
            for d in docs
        ]

        return {
            "trobat": True,
            "vehicle_id": str(v.id),
            "documents": docs_list,
            "matricula": v.matricula,
            "marca": v.marca,
            "model": v.model,
            "tipus": v.tipus,
            "estat": v.estat,
            "data_proxima_itv": v.data_proxima_itv.isoformat() if v.data_proxima_itv else None,
            "odometre_acumulat": v.odometre_acumulat,
            "estat_itv": v.estat_itv,
            "data_caducitat_asseguranca": v.data_caducitat_asseguranca.isoformat()
            if v.data_caducitat_asseguranca
            else None,
            "companyia_asseguradora": v.companyia_asseguradora,
            "carnet_necessari": v.carnet_necessari,
            "historial_reparacions": v.historial_reparacions,
            "regim_adquisicio": v.regim_adquisicio,
            "renting_limit_km": v.renting_limit_km,
            "consum_l_100km": v.consum_l_100km,
        }

    async def tool_audit_itv_insurance_fleet(
        self, db: AsyncSession, empresa_id: uuid.UUID, dies_marge: int = 30
    ) -> dict:
        avui = date.today()
        limit = avui + timedelta(days=dies_marge)
        stmt = select(Vehicle).where(Vehicle.empresa_id == empresa_id)
        res = await db.execute(stmt)
        vehs = res.scalars().all()

        alertes = []
        for v in vehs:
            if v.data_proxima_itv and v.data_proxima_itv <= limit:
                alertes.append(
                    {
                        "matricula": v.matricula,
                        "tipus": "ITV",
                        "data_limit": v.data_proxima_itv.isoformat(),
                        "caducada": v.data_proxima_itv < avui,
                    }
                )
            if v.data_caducitat_asseguranca and v.data_caducitat_asseguranca <= limit:
                alertes.append(
                    {
                        "matricula": v.matricula,
                        "tipus": "ASSEGURANÇA",
                        "data_limit": v.data_caducitat_asseguranca.isoformat(),
                        "caducada": v.data_caducitat_asseguranca < avui,
                    }
                )

        return {
            "trobat": len(alertes) > 0,
            "total_alertes": len(alertes),
            "alertes": alertes,
            "missatge": (
                f"S'han detectat {len(alertes)} alertes de manteniment/assegurança."
                if alertes
                else "Tots els vehicles tenen la ITV i l'assegurança al dia."
            ),
        }

    async def run_sovereign(
        self, pregunta: str, db: AsyncSession, empresa_id: uuid.UUID
    ) -> Tuple[str, Optional[str], Optional[dict], Optional[dict], List[dict]]:
        pregunta_lower = pregunta.lower()
        enllacos: List[dict] = [{"titol": "Flota de Vehicles", "url": "/gestio/flota"}]

        tool_name: Optional[str] = None
        tool_args: Optional[Dict[str, Any]] = None
        tool_res: Optional[dict] = None

        # 1. Proximitat / Vehicle més proper
        if any(
            k in pregunta_lower
            for k in [
                "més a prop",
                "mes aprop",
                "mes a prop",
                "més proper",
                "mes proper",
                "proper",
                "aprop",
                "proxim",
                "pròxim",
                "closest",
                "cercano",
                "cerca",
            ]
        ):
            coords = re.findall(r"[-+]?\d+\.\d+", pregunta)
            if len(coords) >= 2:
                lat = float(coords[0])
                lng = float(coords[1])
            else:
                nums = re.findall(r"[-+]?\d+(?:\.\d+)?", pregunta)
                if len(nums) >= 2:
                    lat = float(nums[0])
                    lng = float(nums[1])
                else:
                    lat, lng = 41.3851, 2.1734

            tool_name = "get_closest_vehicle"
            tool_args = {"lat": lat, "lng": lng}
            tool_res_dict = await self.tool_get_closest_vehicle(db, empresa_id, lat, lng)
            tool_res = tool_res_dict

            if tool_res_dict.get("trobat") and tool_res_dict.get("vehicle_mes_proper"):
                v = tool_res_dict["vehicle_mes_proper"]
                resposta = (
                    f"El vehicle més proper a les coordenades [{lat}, {lng}] és el {v['matricula']} "
                    f"({v['marca']} {v['model']}), que es troba a {v['distancia_km']} km (estat: {v['estat']})."
                )
            else:
                resposta = "No hi ha cap vehicle registrat a la flota per calcular la proximitat."

            return resposta, tool_name, tool_args, tool_res, enllacos

        # 2. Vehicle per matrícula o informació de vehicle
        stmt_v = select(Vehicle).where(Vehicle.empresa_id == empresa_id)
        vehs = (await db.execute(stmt_v)).scalars().all()
        target_mat = ""
        for v in vehs:
            if v.matricula.lower() in pregunta_lower:
                target_mat = v.matricula
                break

        if not target_mat:
            mat_match = re.search(r"\b[0-9]{4}[ -]?[A-Z]{3}\b", pregunta.upper())
            if mat_match:
                target_mat = mat_match.group(0).replace(" ", "-")

        if target_mat:
            tool_name = "get_vehicle_info"
            tool_args = {"matricula": target_mat}
            tool_res = await self.tool_get_vehicle_info(db, empresa_id, target_mat)
            if tool_res.get("trobat"):
                resposta = (
                    f"Vehicle {tool_res['matricula']} ({tool_res['marca']} {tool_res['model']}): "
                    f"Estat: {tool_res['estat']}. "
                    f"ITV: {tool_res.get('estat_itv')} (Propera: {tool_res.get('data_proxima_itv') or 'Pendent'}). "
                    f"Assegurança: {tool_res.get('companyia_asseguradora') or 'No consta'} (Caduca: {tool_res.get('data_caducitat_asseguranca') or 'No consta'}). "
                    f"Carnet Requerit: {tool_res.get('carnet_necessari')}. "
                    f"Règim: {tool_res.get('regim_adquisicio')} (Límit: {tool_res.get('renting_limit_km') or 'N/A'} km). "
                    f"Consum: {tool_res.get('consum_l_100km') or 'N/A'} L/100km. "
                    f"Odòmetre: {tool_res['odometre_acumulat']} km. "
                    f"Documents Registrats: {len(tool_res.get('documents', []))} arxius."
                )
            else:
                resposta = tool_res.get(
                    "missatge", f"No s'ha trobat informació per la matrícula {target_mat}."
                )
            return resposta, tool_name, tool_args, tool_res, enllacos

        # Si pregunta per ITV o assegurances de la flota
        tool_name = "audit_itv_insurance_fleet"
        tool_args = {"dies_marge": 30}
        tool_res = await self.tool_audit_itv_insurance_fleet(db, empresa_id, 30)
        return (
            tool_res.get("missatge", "Revisió de flota completada."),
            tool_name,
            tool_args,
            tool_res,
            enllacos,
        )
