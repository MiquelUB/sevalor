"""Subagent de Flota, Desplaçaments i Rutes (Lectura Exclusiva al Disc Sobirà de l'Empresa)."""

import re
import uuid
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.subagents.base import BaseSubagent
from app.services.subagents.schemas import SCHEMAS_FLOTA_DESPATX


def calcular_distancia_haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Fórmula Haversine per calcular la distància en km entre dos punts GPS."""
    import math

    r = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return round(r * c, 2)


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


def _extract_coords(
    vehicle: Dict[str, Any], ot_rel: Optional[Dict[str, Any]]
) -> Optional[Tuple[float, float]]:
    if ot_rel:
        if ot_rel.get("latitud") is not None and ot_rel.get("longitud") is not None:
            try:
                return float(ot_rel["latitud"]), float(ot_rel["longitud"])
            except (ValueError, TypeError):
                pass
        adr = str(ot_rel.get("adreca") or "")
        if adr:
            m = re.findall(r"[-+]?\d+\.\d+", adr)
            if len(m) >= 2:
                return float(m[0]), float(m[1])
            if "," in adr:
                try:
                    parts = [float(p.strip()) for p in adr.split(",")]
                    if len(parts) >= 2:
                        return parts[0], parts[1]
                except (ValueError, TypeError):
                    pass

    for lat_k, lng_k in (("latitud", "longitud"), ("lat", "lng")):
        if vehicle.get(lat_k) is not None and vehicle.get(lng_k) is not None:
            try:
                return float(vehicle[lat_k]), float(vehicle[lng_k])
            except (ValueError, TypeError):
                pass
    return None


class SubagentFlotaDespatx(BaseSubagent):
    id = "subagent_flota_despatx"
    nom = "Subagent de Flota i Desplaçaments"
    descripcio = (
        "Especialista en geolocalització de vehicles, càlcul Haversine de proximitat, manteniment i control d'ITV/assegurances."
    )
    allowed_roles = ["SECRETARIA", "ENGINYER", "BOSS", "OPERARI", "CAP_DE_COLLA", "ADMIN"]
    tools_schema = SCHEMAS_FLOTA_DESPATX
    system_prompt = (
        "Ets l'assistent expert en Flota i Despatx de SEVALOR. "
        "Consultes l'estat actual dels vehicles de la flota (en ruta, assignats a operaris o disponibles), "
        "audites venciments d'ITV i assegurances, optimitzes desplaçaments, revises consums de carburant "
        "i localitzes el vehicle més proper a una urgència. "
        "Respon sempre en català de forma concisa i precisa basant-te exclusivament en les dades reals del disc dur de l'empresa."
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
            "grua",
            "grua autocargant",
            "pesant",
            "pesants",
            "carrega util",
            "càrrega útil",
            "mma",
            "cap",
            "tacograf",
            "tacògraf",
            "visat",
            "targeta transport",
            "renting km",
            "exces km",
            "excés km",
            "venciment",
            "venciments",
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
        if tool_name == "get_vehicle_info":
            return await self.tool_get_vehicle_info(db, empresa_id, args.get("matricula", ""))
        if tool_name == "audit_itv_insurance_fleet":
            dies = int(args.get("dies_marge", 30))
            return await self.tool_audit_itv_insurance_fleet(db, empresa_id, dies)
        if tool_name == "get_heavy_vehicles_for_ot":
            c_min = int(args["carrega_minima_kg"]) if args.get("carrega_minima_kg") is not None else None
            return await self.tool_get_heavy_vehicles_for_ot(
                db,
                empresa_id,
                carrega_minima_kg=c_min,
                equipament=args.get("equipament"),
                categoria_ue=args.get("categoria_ue"),
            )
        if tool_name == "get_fleet_status":
            return await self.tool_get_fleet_status(db, empresa_id, args.get("filtres_estat"))
        if tool_name == "get_vehicle_maintenance":
            return await self.tool_get_vehicle_maintenance(
                db,
                empresa_id,
                matricula=args.get("matricula"),
                limit=int(args.get("limit", 5)),
                caller_role=caller_role,
            )
        if tool_name == "get_fuel_consumption":
            return await self.tool_get_fuel_consumption(
                db,
                empresa_id,
                matricula=args.get("matricula"),
            )
        return {"error": f"Eina no suportada pel subagent de flota: {tool_name}"}

    async def tool_get_closest_vehicle(
        self, db: AsyncSession, empresa_id: uuid.UUID, lat: float, lng: float
    ) -> dict:
        vehicles = await self.read_sovereign_category(db, empresa_id, "vehicles")
        if not vehicles:
            return {"trobat": False, "missatge": "No hi ha cap vehicle registrat a la flota."}

        ots = await self.read_sovereign_category(db, empresa_id, "ots_actives")
        vehicle_ot_map: Dict[str, Dict[str, Any]] = {}
        for ot in ots:
            vid = str(ot.get("vehicle_id") or "")
            estat_ot = str(ot.get("estat") or "").upper()
            if vid and estat_ot in ("EN_OBRA", "EN_RUTA", "EN_CURS", "PENDENT") and vid not in vehicle_ot_map:
                vehicle_ot_map[vid] = ot

        llista: List[Dict[str, Any]] = []
        for v in vehicles:
            vid = str(v.get("id") or "")
            ot_rel = vehicle_ot_map.get(vid)
            coords = _extract_coords(v, ot_rel)
            if coords is None:
                # Zero Mock Data: sense coordenades reals no s'inventen coordenades per defecte
                continue

            v_lat, v_lng = coords
            dist = calcular_distancia_haversine(lat, lng, v_lat, v_lng)
            llista.append(
                {
                    "vehicle_id": vid,
                    "matricula": v.get("matricula"),
                    "marca": v.get("marca"),
                    "model": v.get("model"),
                    "estat": v.get("estat"),
                    "distancia_km": dist,
                    "lat": v_lat,
                    "lng": v_lng,
                    "ordre_treball_actual": ot_rel.get("codi") if ot_rel else None,
                }
            )

        if not llista:
            return {
                "trobat": False,
                "coordenades_cercades": {"lat": lat, "lng": lng},
                "missatge": "Cap vehicle té posició GPS o adreça amb coordenades registrada al disc dur de l'empresa.",
            }

        llista.sort(key=lambda x: float(x["distancia_km"]))
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
        vehicles = await self.read_sovereign_category(db, empresa_id, "vehicles")
        mat_q = (matricula or "").strip().lower()
        v = next((veh for veh in vehicles if mat_q and mat_q in str(veh.get("matricula") or "").lower()), None)
        if not v:
            return {
                "trobat": False,
                "matricula_cercada": matricula,
                "missatge": f"No s'ha trobat cap vehicle amb la matrícula '{matricula}'.",
            }

        alertes_docs = await self.read_sovereign_category(db, empresa_id, "alertes_flota")
        vid = str(v.get("id") or "")
        docs_list: List[Dict[str, Any]] = []
        raw_embedded_docs = v.get("documents")
        if isinstance(raw_embedded_docs, list):
            for d in raw_embedded_docs:
                if isinstance(d, dict):
                    docs_list.append(
                        {
                            "tipus": d.get("tipus_document") or d.get("tipus"),
                            "nom_arxiu": d.get("nom_arxiu"),
                            "data": d.get("data_document") or d.get("data"),
                        }
                    )
        for ad in alertes_docs:
            if str(ad.get("vehicle_id") or "") == vid and ad.get("nom_arxiu"):
                docs_list.append(
                    {
                        "tipus": ad.get("tipus_document") or ad.get("tipus"),
                        "nom_arxiu": ad.get("nom_arxiu"),
                        "data": ad.get("data_document") or ad.get("data"),
                    }
                )

        d_itv = _parse_date(v.get("data_proxima_itv"))
        d_asseg = _parse_date(v.get("data_caducitat_asseguranca"))

        return {
            "trobat": True,
            "vehicle_id": vid,
            "documents": docs_list,
            "matricula": v.get("matricula"),
            "marca": v.get("marca"),
            "model": v.get("model"),
            "tipus": v.get("tipus"),
            "estat": v.get("estat"),
            "data_proxima_itv": d_itv.isoformat() if d_itv else None,
            "odometre_acumulat": v.get("odometre_acumulat"),
            "estat_itv": v.get("estat_itv"),
            "data_caducitat_asseguranca": d_asseg.isoformat() if d_asseg else None,
            "companyia_asseguradora": v.get("companyia_asseguradora"),
            "carnet_necessari": v.get("carnet_necessari"),
            "historial_reparacions": v.get("historial_reparacions"),
            "regim_adquisicio": v.get("regim_adquisicio"),
            "renting_limit_km": v.get("renting_limit_km"),
            "consum_l_100km": (
                float(v["consum_l_100km"]) if v.get("consum_l_100km") is not None else None
            ),
        }

    async def tool_audit_itv_insurance_fleet(
        self, db: AsyncSession, empresa_id: uuid.UUID, dies_marge: int = 30
    ) -> dict:
        avui = date.today()
        limit = avui + timedelta(days=dies_marge)
        vehs = await self.read_sovereign_category(db, empresa_id, "vehicles")

        alertes: List[Dict[str, Any]] = []
        alertes_renting_km: List[Dict[str, Any]] = []

        for v in vehs:
            d_itv = _parse_date(v.get("data_proxima_itv"))
            if d_itv and d_itv <= limit:
                d_rest = (d_itv - avui).days
                alertes.append(
                    {
                        "matricula": v.get("matricula"),
                        "tipus": "ITV",
                        "data_limit": d_itv.isoformat(),
                        "dies_restants": d_rest,
                        "caducada": d_rest <= 0,
                        "severitat": "CRITICAL" if d_rest <= 0 else ("WARNING" if d_rest <= 15 else "INFO"),
                    }
                )

            d_asseg = _parse_date(v.get("data_caducitat_asseguranca"))
            if d_asseg and d_asseg <= limit:
                d_rest = (d_asseg - avui).days
                alertes.append(
                    {
                        "matricula": v.get("matricula"),
                        "tipus": "ASSEGURANÇA",
                        "data_limit": d_asseg.isoformat(),
                        "dies_restants": d_rest,
                        "caducada": d_rest <= 0,
                        "severitat": "CRITICAL" if d_rest <= 0 else ("WARNING" if d_rest <= 15 else "INFO"),
                    }
                )

            d_rent = _parse_date(v.get("data_venciment_renting"))
            if d_rent and d_rent <= limit:
                d_rest = (d_rent - avui).days
                alertes.append(
                    {
                        "matricula": v.get("matricula"),
                        "tipus": "RÈNTING",
                        "data_limit": d_rent.isoformat(),
                        "dies_restants": d_rest,
                        "caducada": d_rest <= 0,
                        "severitat": "CRITICAL" if d_rest <= 0 else ("WARNING" if d_rest <= 15 else "INFO"),
                    }
                )

            dades_pesants = v.get("dades_pesants")
            if isinstance(dades_pesants, dict):
                d_vis = _parse_date(dades_pesants.get("data_visat_transport"))
                if d_vis and d_vis <= limit:
                    d_rest = (d_vis - avui).days
                    alertes.append(
                        {
                            "matricula": v.get("matricula"),
                            "tipus": "VISAT_TRANSPORT",
                            "data_limit": d_vis.isoformat(),
                            "dies_restants": d_rest,
                            "caducada": d_rest <= 0,
                            "severitat": "CRITICAL" if d_rest <= 0 else "WARNING",
                        }
                    )
                d_taco = _parse_date(dades_pesants.get("data_calibratge_tacograf"))
                if d_taco and d_taco <= limit:
                    d_rest = (d_taco - avui).days
                    alertes.append(
                        {
                            "matricula": v.get("matricula"),
                            "tipus": "CALIBRATGE_TACOGRAF",
                            "data_limit": d_taco.isoformat(),
                            "dies_restants": d_rest,
                            "caducada": d_rest <= 0,
                            "severitat": "CRITICAL" if d_rest <= 0 else "WARNING",
                        }
                    )

            regim = v.get("regim_adquisicio")
            limit_km = v.get("renting_limit_km") or 0
            if regim in ("RENTING", "LEASING", "LLOGUER") and limit_km > 0:
                odo_act = v.get("odometre_acumulat") or 0
                odo_ini = v.get("odometre_inici_contracte") or 0
                km_fets = max(0, int(odo_act) - int(odo_ini))
                if km_fets > int(limit_km):
                    exces = km_fets - int(limit_km)
                    penalitzacio = round(exces * float(v.get("preu_km_exces_eur") or 0.0), 2)
                    alertes_renting_km.append(
                        {
                            "matricula": v.get("matricula"),
                            "km_recorreguts": km_fets,
                            "limit_km": int(limit_km),
                            "exces_km": exces,
                            "penalitzacio_eur": penalitzacio,
                            "severitat": "CRITICAL",
                        }
                    )

        total_alertes = len(alertes) + len(alertes_renting_km)
        parts = []
        if alertes:
            parts.append(f"{len(alertes)} venciments legals pendents")
        if alertes_renting_km:
            parts.append(f"{len(alertes_renting_km)} vehicles amb excés de quilometratge de rènting")

        missatge = (
            f"S'han detectat alertes a la flota: {', '.join(parts)}."
            if total_alertes > 0
            else "Tots els vehicles tenen les inspeccions, assegurances i contractes de rènting al dia."
        )

        return {
            "trobat": total_alertes > 0,
            "total_alertes": total_alertes,
            "alertes": alertes,
            "alertes_renting_km": alertes_renting_km,
            "missatge": missatge,
        }

    async def tool_get_heavy_vehicles_for_ot(
        self,
        db: AsyncSession,
        empresa_id: uuid.UUID,
        carrega_minima_kg: Optional[int] = None,
        equipament: Optional[str] = None,
        categoria_ue: Optional[str] = None,
    ) -> dict:
        vehs = await self.read_sovereign_category(db, empresa_id, "vehicles")
        operaris = await self.read_sovereign_category(db, empresa_id, "operaris")
        op_map = {
            str(u.get("id")): f"{u.get('nom') or ''} {u.get('cognoms') or ''}".strip()
            for u in operaris
            if u.get("id")
        }

        vehs_sorted = sorted(
            vehs,
            key=lambda x: (x.get("carrega_util_kg") is None, -(float(x.get("carrega_util_kg") or 0))),
        )
        trobats: List[Dict[str, Any]] = []
        for veh in vehs_sorted:
            if carrega_minima_kg is not None:
                carrega_actual = veh.get("carrega_util_kg")
                if carrega_actual is None or int(carrega_actual) < carrega_minima_kg:
                    continue

            if equipament:
                eq_requerit = equipament.upper().strip()
                homologats = [str(e).upper().strip() for e in (veh.get("equipament_homologat") or [])]
                if not any(eq_requerit in h or h in eq_requerit for h in homologats):
                    continue

            if categoria_ue:
                cat_req = categoria_ue.upper().strip()
                cat_veh = str(veh.get("categoria_ue") or "").upper().strip()
                if cat_veh != cat_req:
                    continue

            c_nom = (
                op_map.get(str(veh.get("conductor_habitual_id")))
                or str(veh.get("conductor") or "").strip()
                or "Sense conductor"
            )
            trobats.append(
                {
                    "matricula": veh.get("matricula"),
                    "marca": veh.get("marca"),
                    "model": veh.get("model"),
                    "categoria_ue": veh.get("categoria_ue"),
                    "mma_kg": veh.get("mma_kg"),
                    "carrega_util_kg": veh.get("carrega_util_kg"),
                    "equipament_homologat": veh.get("equipament_homologat") or [],
                    "carnet_necessari": veh.get("carnet_necessari"),
                    "requereix_cap": veh.get("requereix_cap"),
                    "apte_assignacio_pwa": veh.get("apte_assignacio_pwa", True),
                    "estat": veh.get("estat"),
                    "conductor": c_nom,
                }
            )

        if not trobats:
            criteris = []
            if carrega_minima_kg:
                criteris.append(f"càrrega útil >= {carrega_minima_kg} kg")
            if equipament:
                criteris.append(f"equipament '{equipament}'")
            if categoria_ue:
                criteris.append(f"categoria {categoria_ue}")
            desc_criteris = " amb " + " i ".join(criteris) if criteris else ""
            return {
                "trobat": False,
                "total_vehicles": 0,
                "vehicles": [],
                "missatge": f"No s'ha trobat cap vehicle a la flota{desc_criteris}.",
            }

        detalls = [
            f"{v['matricula']} ({v['marca']} {v['model']} - Càrrega útil: {v['carrega_util_kg'] or 'N/D'} kg, Equipament: {', '.join(v['equipament_homologat']) or 'Estàndard'})"
            for v in trobats
        ]
        return {
            "trobat": True,
            "total_vehicles": len(trobats),
            "vehicles": trobats,
            "missatge": f"S'han trobat {len(trobats)} vehicles aptes per a l'ordre de treball: {'; '.join(detalls)}.",
        }

    async def tool_get_fleet_status(
        self, db: AsyncSession, empresa_id: uuid.UUID, filtres_estat: Optional[str] = None
    ) -> dict:
        vehs = await self.read_sovereign_category(db, empresa_id, "vehicles")
        operaris = await self.read_sovereign_category(db, empresa_id, "operaris")
        op_map = {
            str(u.get("id")): f"{u.get('nom') or ''} {u.get('cognoms') or ''}".strip()
            for u in operaris
            if u.get("id")
        }

        vehicles: List[Dict[str, Any]] = []
        for veh in sorted(vehs, key=lambda x: str(x.get("matricula") or "")):
            if filtres_estat and filtres_estat.strip().lower() not in str(veh.get("estat") or "").lower():
                continue
            c_nom = (
                op_map.get(str(veh.get("conductor_habitual_id")))
                or str(veh.get("conductor") or "").strip()
                or "Sense conductor assignat"
            )
            vehicles.append(
                {
                    "matricula": veh.get("matricula"),
                    "marca": veh.get("marca"),
                    "model": veh.get("model"),
                    "estat": veh.get("estat"),
                    "conductor": c_nom,
                    "odometre_km": veh.get("odometre_acumulat"),
                    "estat_itv": veh.get("estat_itv"),
                }
            )

        total = len(vehicles)
        if total == 0:
            return {
                "trobat": False,
                "total_vehicles": 0,
                "vehicles": [],
                "missatge": "Actualment no hi ha cap vehicle registrat a la flota al disc dur de l'empresa.",
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
            llista_disp = ", ".join([f"{v['matricula']} ({v['marca']} {v['model']})" for v in disponibles])
            txt_parts.append(f"• Vehicles lliures/disponibles ({len(disponibles)}): {llista_disp}.")

        return {
            "trobat": True,
            "total_vehicles": total,
            "en_ruta": en_ruta,
            "disponibles": disponibles,
            "vehicles": vehicles,
            "missatge": "\n".join(txt_parts),
        }

    async def tool_get_vehicle_maintenance(
        self,
        db: AsyncSession,
        empresa_id: uuid.UUID,
        matricula: Optional[str] = None,
        limit: int = 5,
        caller_role: Optional[str] = None,
    ) -> dict:
        vehs = await self.read_sovereign_category(db, empresa_id, "vehicles")
        mat_q = (matricula or "").strip().lower()
        filtrats = [
            v
            for v in sorted(vehs, key=lambda x: str(x.get("matricula") or ""))
            if not mat_q or mat_q in str(v.get("matricula") or "").lower()
        ][:limit]

        llista: List[Dict[str, Any]] = []
        for v in filtrats:
            d_itv = _parse_date(v.get("data_proxima_itv"))
            d_asseg = _parse_date(v.get("data_caducitat_asseguranca"))
            item: Dict[str, Any] = {
                "id": str(v.get("id")),
                "matricula": v.get("matricula"),
                "marca": v.get("marca"),
                "model": v.get("model"),
                "estat": v.get("estat"),
                "odometre_km": v.get("odometre_acumulat"),
                "proxima_itv": d_itv.isoformat() if d_itv else None,
                "estat_itv": v.get("estat_itv"),
                "caducitat_asseguranca": d_asseg.isoformat() if d_asseg else None,
                "historial_reparacions": v.get("historial_reparacions") or "Sense reparacions recents registrades",
            }
            if caller_role in ("BOSS", "ADMIN"):
                item["regim_adquisicio"] = v.get("regim_adquisicio")
                item["renting_limit_km"] = v.get("renting_limit_km")
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
        vehs = await self.read_sovereign_category(db, empresa_id, "vehicles")
        tiquets = await self.read_sovereign_category(db, empresa_id, "tiquets_despesa")
        mat_q = (matricula or "").strip().lower()
        filtrats = [v for v in vehs if not mat_q or mat_q in str(v.get("matricula") or "").lower()]

        tiquets_per_veh: Dict[str, float] = {}
        for t in tiquets:
            if str(t.get("categoria") or "").upper() in ("COMBUSTIBLE", "GASOIL", "BENZINA", "ADBLUE", ""):
                vid = str(t.get("vehicle_id") or "")
                if vid and t.get("litres") is not None:
                    tiquets_per_veh[vid] = tiquets_per_veh.get(vid, 0.0) + float(t.get("litres") or 0.0)

        llista: List[Dict[str, Any]] = []
        for v in filtrats:
            vid = str(v.get("id") or "")
            llista.append(
                {
                    "matricula": v.get("matricula"),
                    "marca": v.get("marca"),
                    "model": v.get("model"),
                    "consum_l_100km": (
                        float(v["consum_l_100km"]) if v.get("consum_l_100km") is not None else None
                    ),
                    "consum_mitjana_historica": (
                        float(v["consum_mitjana_historica"])
                        if v.get("consum_mitjana_historica") is not None
                        else None
                    ),
                    "consum_adblue_litres": (
                        float(v["consum_adblue_litres"])
                        if v.get("consum_adblue_litres") is not None
                        else None
                    ),
                    "odometre_km": v.get("odometre_acumulat"),
                    "litres_repostats_tiquets": tiquets_per_veh.get(vid, 0.0),
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
            if len(coords) < 2:
                coords = re.findall(r"[-+]?\d+(?:\.\d+)?", pregunta)
            if len(coords) < 2:
                return (
                    "Cal indicar les coordenades reals (latitud, longitud) per calcular el vehicle més proper.",
                    "get_closest_vehicle",
                    {},
                    {"trobat": False, "missatge": "Falten coordenades GPS a la consulta."},
                    enllacos,
                )

            lat, lng = float(coords[0]), float(coords[1])
            tool_name = "get_closest_vehicle"
            tool_args: dict[str, Any] = {"lat": lat, "lng": lng}
            tool_res_dict = await self.tool_get_closest_vehicle(db, empresa_id, lat, lng)

            if tool_res_dict.get("trobat") and tool_res_dict.get("vehicle_mes_proper"):
                v = tool_res_dict["vehicle_mes_proper"]
                resposta = (
                    f"El vehicle més proper a les coordenades [{lat}, {lng}] és el {v['matricula']} "
                    f"({v['marca']} {v['model']}), que es troba a {v['distancia_km']} km (estat: {v['estat']})."
                )
            else:
                resposta = tool_res_dict.get(
                    "missatge", "No hi ha cap vehicle geolocalitzat al disc dur per calcular la proximitat."
                )
            return resposta, tool_name, tool_args, tool_res_dict, enllacos

        if any(k in pregunta_lower for k in ["consum", "gasolina", "gasoil", "combustible", "adblue", "litres"]):
            tool_name = "get_fuel_consumption"
            tool_args = {"matricula": None}
            tool_res = await self.tool_get_fuel_consumption(db, empresa_id)
            if tool_res.get("trobat"):
                detalls = ", ".join(
                    [f"{c['matricula']} ({c['consum_l_100km'] or 'N/D'} L/100km)" for c in tool_res["consums"][:4]]
                )
                resposta = f"Dades de consum de combustible de la flota: {detalls}."
            else:
                resposta = "No s'han trobat mètriques de consum registrades a la flota."
            return resposta, tool_name, tool_args, tool_res, enllacos

        if any(k in pregunta_lower for k in ["manteniment", "reparacio", "reparacions", "taller", "avaria", "avaries"]):
            tool_name = "get_vehicle_maintenance"
            tool_args = {"matricula": None, "limit": 5}
            tool_res = await self.tool_get_vehicle_maintenance(
                db, empresa_id, limit=5, caller_role=caller_role
            )
            return (
                tool_res.get("missatge", "Consulta de manteniment completada."),
                tool_name,
                tool_args,
                tool_res,
                enllacos,
            )

        if any(
            k in pregunta_lower
            for k in [
                "grua",
                "grua autocargant",
                "pesant",
                "pesants",
                "carrega util",
                "càrrega útil",
                "càrrega",
                "carrega",
                "pes autoritzat",
            ]
        ):
            c_min = None
            kg_match = re.search(r"(\d+)\s*(?:kg|quilos|kgs)", pregunta_lower)
            if kg_match:
                c_min = int(kg_match.group(1))
            eq = "GRUA_AUTOCARGANT" if "grua" in pregunta_lower else None
            cat = "N2" if "n2" in pregunta_lower else ("N3" if "n3" in pregunta_lower else ("N1" if "n1" in pregunta_lower else None))

            tool_name = "get_heavy_vehicles_for_ot"
            tool_args = {"carrega_minima_kg": c_min, "equipament": eq, "categoria_ue": cat}
            tool_res = await self.tool_get_heavy_vehicles_for_ot(
                db, empresa_id, carrega_minima_kg=c_min, equipament=eq, categoria_ue=cat
            )
            return tool_res.get("missatge", "Cerca de vehicles per a OT completada."), tool_name, tool_args, tool_res, enllacos

        vehs = await self.read_sovereign_category(db, empresa_id, "vehicles")
        target_mat = ""
        for v in vehs:
            mat = str(v.get("matricula") or "")
            if mat and mat.lower() in pregunta_lower:
                target_mat = mat
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
                resposta = tool_res.get("missatge", f"No s'ha trobat informació per la matrícula {target_mat}.")
            return resposta, tool_name, tool_args, tool_res, enllacos

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
                "venciment",
                "venciments",
                "rènting",
                "renting",
                "exces km",
                "excés km",
                "tacògraf",
                "tacograf",
                "visat",
            ]
        ):
            tool_name = "audit_itv_insurance_fleet"
            tool_args = {"dies_marge": 30}
            tool_res = await self.tool_audit_itv_insurance_fleet(db, empresa_id, 30)
            return tool_res.get("missatge", "Revisió de flota completada."), tool_name, tool_args, tool_res, enllacos

        tool_name = "get_fleet_status"
        tool_args = {"filtres_estat": None}
        tool_res = await self.tool_get_fleet_status(db, empresa_id)
        return tool_res.get("missatge", "Consulta de flota completada."), tool_name, tool_args, tool_res, enllacos
