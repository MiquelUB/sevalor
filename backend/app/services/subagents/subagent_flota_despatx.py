"""Subagent de Flota, Desplaçaments i Rutes."""

import re
import uuid
from datetime import date, timedelta
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import DocumentFlota, OrdreTreball, Usuari, Vehicle
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
    descripcio = "Especialista en geolocalització de vehicles, càlcul Haversine de proximitat, manteniment i control d'ITV/assegurances."
    allowed_roles = ["SECRETARIA", "ENGINYER", "BOSS", "OPERARI", "CAP_DE_COLLA", "ADMIN"]
    tools_schema = SCHEMAS_FLOTA_DESPATX
    system_prompt = (
        "Ets l'assistent expert en Flota i Despatx de SEVALOR. "
        "Optimitza el desplaçament de vehicles, audita venciments d'ITV i assegurances, consulta consums de combustible, "
        "historials de reparacions i localitza el vehicle més proper a una urgència. "
        "Respon sempre en català de forma concisa i precisa basant-te exclusivament en les dades reals de la flota."
    )

    def can_handle(self, query: str, rol: str) -> bool:
        q = query.lower()
        paraules_clau = [
            "vehicle",
            "vehicles",
            "furgoneta",
            "furgonetes",
            "cotxe",
            "cotxes",
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
            "en ruta",
            "en servei",
            "assignat",
            "assignats",
            "combustible",
            "gasolina",
            "gasoil",
            "consum",
            "adblue",
            "reparació",
            "reparacions",
            "taller",
            "odometre",
            "odòmetre",
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
        if tool_name == "get_closest_vehicle":
            lat = float(args.get("lat", 0.0))
            lng = float(args.get("lng", 0.0))
            return await self.tool_get_closest_vehicle(db, empresa_id, lat, lng)
        elif tool_name == "get_vehicle_info":
            return await self.tool_get_vehicle_info(db, empresa_id, args.get("matricula", ""))
        elif tool_name == "audit_itv_insurance_fleet":
            dies = int(args.get("dies_marge", 30))
            return await self.tool_audit_itv_insurance_fleet(db, empresa_id, dies)
        elif tool_name == "get_fleet_status":
            return await self.tool_get_fleet_status(db, empresa_id, args.get("filtres_estat"))
        elif tool_name == "get_vehicle_maintenance":
            return await self.tool_get_vehicle_maintenance(
                db,
                empresa_id,
                matricula=args.get("matricula"),
                limit=int(args.get("limit", 5)),
                caller_role=caller_role,
            )
        elif tool_name == "get_fuel_consumption":
            return await self.tool_get_fuel_consumption(
                db,
                empresa_id,
                matricula=args.get("matricula"),
            )
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
            "consum_l_100km": float(v.consum_l_100km) if v.consum_l_100km is not None else None,
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

    async def tool_get_fleet_status(
        self, db: AsyncSession, empresa_id: uuid.UUID, filtres_estat: Optional[str] = None
    ) -> dict:
        stmt = (
            select(Vehicle, Usuari.nom, Usuari.cognoms)
            .outerjoin(Usuari, Vehicle.conductor_habitual_id == Usuari.id)
            .where(Vehicle.empresa_id == empresa_id)
            .order_by(Vehicle.matricula.asc())
        )
        res = await db.execute(stmt)
        rows = res.all()
        vehicles = []
        for veh, u_nom, u_cognoms in rows:
            c_nom = f"{u_nom or ''} {u_cognoms or ''}".strip() or "Sense conductor assignat"
            vehicles.append(
                {
                    "matricula": veh.matricula,
                    "marca": veh.marca,
                    "model": veh.model,
                    "estat": veh.estat,
                    "conductor": c_nom,
                    "odometre_km": veh.odometre_acumulat,
                    "estat_itv": veh.estat_itv,
                }
            )

        total = len(vehicles)
        if total == 0:
            return {
                "trobat": False,
                "total_vehicles": 0,
                "vehicles": [],
                "missatge": "Actualment no hi ha cap vehicle registrat a la flota de l'empresa.",
            }

        en_ruta = [
            v
            for v in vehicles
            if v["estat"] in ("ASSIGNAT", "EN_RUTA")
            or (v["estat"] == "OPERATIU" and v["conductor"] != "Sense conductor assignat")
        ]
        disponibles = [
            v
            for v in vehicles
            if v["estat"] in ("DISPONIBLE", "OPERATIU")
            and v["conductor"] == "Sense conductor assignat"
        ]

        txt_parts = [f"Flota de l'empresa ({total} vehicles totals):"]
        if en_ruta:
            llista_ruta = ", ".join(
                [
                    f"{v['matricula']} ({v['marca']} {v['model']} - Conductor: {v['conductor']})"
                    for v in en_ruta
                ]
            )
            txt_parts.append(f"• Vehicles en ruta o en servei ({len(en_ruta)}): {llista_ruta}.")
        else:
            txt_parts.append("• No hi ha cap vehicle en ruta o assignat a un conductor ara mateix.")

        if disponibles:
            llista_disp = ", ".join(
                [f"{v['matricula']} ({v['marca']} {v['model']})" for v in disponibles]
            )
            txt_parts.append(f"• Vehicles lliures/disponibles ({len(disponibles)}): {llista_disp}.")

        missatge = "\n".join(txt_parts)

        return {
            "trobat": True,
            "total_vehicles": total,
            "en_ruta": en_ruta,
            "disponibles": disponibles,
            "vehicles": vehicles,
            "missatge": missatge,
        }

    async def tool_get_vehicle_maintenance(
        self,
        db: AsyncSession,
        empresa_id: uuid.UUID,
        matricula: Optional[str] = None,
        limit: int = 5,
        caller_role: Optional[str] = None,
    ) -> dict:
        stmt = select(Vehicle).where(Vehicle.empresa_id == empresa_id)
        if matricula and matricula.strip():
            stmt = stmt.where(Vehicle.matricula.ilike(f"%{matricula.strip()}%"))
        stmt = stmt.order_by(Vehicle.matricula.asc()).limit(limit)
        res = await db.execute(stmt)
        vehicles = res.scalars().all()

        llista = []
        for v in vehicles:
            item = {
                "id": str(v.id),
                "matricula": v.matricula,
                "marca": v.marca,
                "model": v.model,
                "estat": v.estat,
                "odometre_km": v.odometre_acumulat,
                "proxima_itv": v.data_proxima_itv.isoformat() if v.data_proxima_itv else None,
                "estat_itv": v.estat_itv,
                "caducitat_asseguranca": v.data_caducitat_asseguranca.isoformat() if v.data_caducitat_asseguranca else None,
                "historial_reparacions": v.historial_reparacions or "Sense reparacions recents registrades",
            }
            if caller_role in ("BOSS", "ADMIN"):
                item["regim_adquisicio"] = v.regim_adquisicio
                item["renting_limit_km"] = v.renting_limit_km
            llista.append(item)

        return {
            "trobat": len(llista) > 0,
            "total": len(llista),
            "manteniments": llista,
            "missatge": (
                f"S'ha obtingut l'estat de manteniment de {len(llista)} vehicles."
                if llista
                else "No s'han trobat vehicles per a la consulta de manteniment."
            ),
        }

    async def tool_get_fuel_consumption(
        self,
        db: AsyncSession,
        empresa_id: uuid.UUID,
        matricula: Optional[str] = None,
    ) -> dict:
        stmt = select(Vehicle).where(Vehicle.empresa_id == empresa_id)
        if matricula and matricula.strip():
            stmt = stmt.where(Vehicle.matricula.ilike(f"%{matricula.strip()}%"))
        res = await db.execute(stmt)
        vehicles = res.scalars().all()

        llista = []
        for v in vehicles:
            llista.append(
                {
                    "matricula": v.matricula,
                    "marca": v.marca,
                    "model": v.model,
                    "consum_l_100km": float(v.consum_l_100km) if v.consum_l_100km is not None else None,
                    "consum_mitjana_historica": float(v.consum_mitjana_historica) if v.consum_mitjana_historica is not None else None,
                    "consum_adblue_litres": float(v.consum_adblue_litres) if v.consum_adblue_litres is not None else None,
                    "odometre_km": v.odometre_acumulat,
                }
            )

        return {
            "trobat": len(llista) > 0,
            "total": len(llista),
            "consums": llista,
            "missatge": (
                f"S'han consultat les mètriques de consum de {len(llista)} vehicles."
                if llista
                else "No s'han trobat dades de consum per als vehicles sol·licitats."
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

        # 2. Consum de combustible / AdBlue
        if any(
            k in pregunta_lower
            for k in ["consum", "gasolina", "gasoil", "combustible", "adblue", "litres"]
        ):
            tool_name = "get_fuel_consumption"
            tool_args = {"matricula": None}
            tool_res = await self.tool_get_fuel_consumption(db, empresa_id)
            if tool_res.get("trobat"):
                detalls = ", ".join(
                    [
                        f"{c['matricula']} ({c['consum_l_100km'] or 'N/D'} L/100km)"
                        for c in tool_res["consums"][:4]
                    ]
                )
                resposta = f"Dades de consum de combustible de la flota: {detalls}."
            else:
                resposta = "No s'han trobat mètriques de consum registrades a la flota."
            return resposta, tool_name, tool_args, tool_res, enllacos

        # 3. Manteniment / Reparacions / Historial de taller
        if any(
            k in pregunta_lower
            for k in ["manteniment", "reparacio", "reparacions", "taller", "avaria", "avaries"]
        ):
            tool_name = "get_vehicle_maintenance"
            tool_args = {"matricula": None, "limit": 5}
            tool_res = await self.tool_get_vehicle_maintenance(db, empresa_id, limit=5, caller_role=caller_role)
            return tool_res.get("missatge", "Consulta de manteniment completada."), tool_name, tool_args, tool_res, enllacos

        # 4. Vehicle específic per matrícula
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
                    f"Consum: {tool_res.get('consum_l_100km') or 'N/A'} L/100km. "
                    f"Odòmetre: {tool_res['odometre_acumulat']} km."
                )
            else:
                resposta = tool_res.get(
                    "missatge", f"No s'ha trobat informació per la matrícula {target_mat}."
                )
            return resposta, tool_name, tool_args, tool_res, enllacos

        # 5. ITV o assegurances de la flota (NOMÉS si es pregunta expressament per aquests conceptes)
        if any(
            k in pregunta_lower
            for k in [
                "itv",
                "asseguran",
                "caducat",
                "caduca",
                "caducitat",
                "polissa",
                "pòlissa",
                "inspecci",
            ]
        ):
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

        # 6. Estat general de la flota / vehicles en ruta / vehicles disponibles
        tool_name = "get_fleet_status"
        tool_args = {"filtres_estat": None}
        tool_res = await self.tool_get_fleet_status(db, empresa_id)
        return (
            tool_res.get("missatge", "Consulta de flota completada."),
            tool_name,
            tool_args,
            tool_res,
            enllacos,
        )
