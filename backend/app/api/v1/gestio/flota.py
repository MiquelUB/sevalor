import math
import re
import uuid
from datetime import date, datetime, timezone
from typing import Any, Dict, List, Optional

import filetype  # type: ignore[import-untyped]
from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    Request,
    UploadFile,
    status,
)
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db_with_tenant_context
from app.core.security import require_roles
from app.models.models import (
    DocumentFlota,
    Magatzem,
    MantenimentVehicle,
    OrdreTreball,
    TiquetCarburant,
    TiquetCombustible,
    Usuari,
    Vehicle,
)
from app.services.flota_service import (
    sincronitzar_assignacio_vehicle_operari,
    sincronitzar_vehicle_al_disc_empresa,
)
from app.services.ocr_service import processar_ocr_document_vehicle
from app.services.sovereign_storage import SovereignStorageGateway

router = APIRouter(
    prefix="/gestio/flota",
    tags=["Gestió Flota"],
    dependencies=[Depends(require_roles(["BOSS", "SECRETARIA", "ENGINYER"]))],
)


class VehicleCreate(BaseModel):
    matricula: str = Field(..., max_length=20)
    marca: str = Field(..., max_length=50)
    model: str = Field(..., max_length=50)
    tipus: str = Field("THERMIC", max_length=30)
    distintiu_ambiental: Optional[str] = Field(None, max_length=10)
    estat: str = Field("OPERATIU", max_length=30)
    conductor_habitual_id: Optional[uuid.UUID] = None
    odometre_acumulat: Optional[int] = 0
    data_proxima_itv: Optional[date] = None
    estat_itv: str = Field("FAVORABLE", max_length=50)
    data_caducitat_asseguranca: Optional[date] = None
    companyia_asseguradora: Optional[str] = Field(None, max_length=100)
    polissa_asseguranca: Optional[str] = Field(None, max_length=100)
    carnet_necessari: str = Field("B", max_length=10)
    historial_reparacions: Optional[str] = None
    regim_adquisicio: str = Field("PROPIETAT", max_length=30)
    renting_limit_km: Optional[int] = None
    odometre_inici_contracte: Optional[int] = 0
    data_inici_contracte: Optional[date] = None
    data_fi_contracte: Optional[date] = None
    quota_mensual_eur: Optional[float] = 0.0
    tarifa_diaria_eur: Optional[float] = 0.0
    preu_km_exces_eur: Optional[float] = 0.0
    valor_residual_eur: Optional[float] = None
    fianca_eur: Optional[float] = None
    data_fi_garantia_oficial: Optional[date] = None
    interval_canvi_oli_km: Optional[int] = 15000
    ultim_canvi_oli_km: Optional[int] = 0
    data_itv_negativa: Optional[date] = None
    data_ultima_descarrega_tacograf: Optional[date] = None
    tacograf_necessari: bool = False
    data_propera_descarrega_tacograf: Optional[date] = None
    capacitat_bateria_kwh: Optional[float] = None
    soh_bateria: Optional[float] = None
    places: int = 5
    pes_maxim_autoritzat: int = 3500
    consum_l_100km: Optional[float] = None
    consum_mitjana_historica: Optional[float] = None
    consum_adblue_litres: Optional[float] = 0.0


class VehicleResponse(VehicleCreate):
    id: uuid.UUID
    horometre_acumulat: float
    odometre_acumulat: int
    conductor_nom: Optional[str] = None
    consum_format: str = "Sense dades"
    anomalia_consum: bool = False
    anomalia_descartada: bool = False
    renting_ocupacio_percent: Optional[float] = None
    renting_alerta: bool = False
    renting_nivell_alerta: Optional[str] = None
    alerta_renting_km: Optional[str] = None
    dies_propera_itv: Optional[int] = None
    km_recorreguts_contracte: int = 0
    dies_restants_contracte: Optional[int] = None
    ocupacio_temps_percent: Optional[float] = None
    desviacio_ritme_percent: Optional[float] = None
    cost_fix_meritat_eur: float = 0.0
    cost_penalitzacio_km_eur: float = 0.0
    despesa_combustible_acumulada_eur: float = 0.0
    despesa_manteniment_acumulada_eur: float = 0.0
    manteniment_computable_tco_eur: float = 0.0
    cost_total_acumulat_eur: float = 0.0
    cost_per_km_eur: float = 0.0
    alerta_contracte_venciment: bool = False

    model_config = ConfigDict(from_attributes=True)


async def _obtenir_despeses_vehicles(
    db: AsyncSession, empresa_id: uuid.UUID, vehicle_ids: List[uuid.UUID]
) -> tuple[Dict[uuid.UUID, float], Dict[uuid.UUID, float]]:
    """Retorna (despesa_combustible_per_vehicle, despesa_manteniment_per_vehicle) per als vehicles indicats."""
    if not vehicle_ids:
        return {}, {}

    comb_map: Dict[uuid.UUID, float] = {}
    mant_map: Dict[uuid.UUID, float] = {}

    # 1. Manteniments (MantenimentVehicle.cost_euros)
    stmt_m = (
        select(MantenimentVehicle.vehicle_id, func.coalesce(func.sum(MantenimentVehicle.cost_euros), 0.0))
        .where(
            MantenimentVehicle.empresa_id == empresa_id,
            MantenimentVehicle.vehicle_id.in_(vehicle_ids),
        )
        .group_by(MantenimentVehicle.vehicle_id)
    )
    res_m = await db.execute(stmt_m)
    for v_id, total_m in res_m.all():
        mant_map[v_id] = float(total_m or 0.0)

    # 2. Tiquets Combustible Backoffice (TiquetCombustible.import_euros)
    stmt_tc = (
        select(TiquetCombustible.vehicle_id, func.coalesce(func.sum(TiquetCombustible.import_euros), 0.0))
        .where(
            TiquetCombustible.empresa_id == empresa_id,
            TiquetCombustible.vehicle_id.in_(vehicle_ids),
        )
        .group_by(TiquetCombustible.vehicle_id)
    )
    res_tc = await db.execute(stmt_tc)
    for v_id, total_tc in res_tc.all():
        comb_map[v_id] = comb_map.get(v_id, 0.0) + float(total_tc or 0.0)

    # 3. Tiquets Carburant Operari PWA (TiquetCarburant.import_)
    stmt_tcarb = (
        select(TiquetCarburant.vehicle_id, func.coalesce(func.sum(TiquetCarburant.import_), 0.0))
        .where(
            TiquetCarburant.empresa_id == empresa_id,
            TiquetCarburant.vehicle_id.in_(vehicle_ids),
        )
        .group_by(TiquetCarburant.vehicle_id)
    )
    res_tcarb = await db.execute(stmt_tcarb)
    for v_id, total_tcarb in res_tcarb.all():
        comb_map[v_id] = comb_map.get(v_id, 0.0) + float(total_tcarb or 0.0)

    return comb_map, mant_map


def _build_vehicle_response(
    veh: Vehicle,
    conductor_nom: Optional[str] = None,
    despesa_combustible_acumulada: float = 0.0,
    despesa_manteniment_acumulada: float = 0.0,
    conductor_id_fallback: Optional[uuid.UUID] = None,
) -> VehicleResponse:
    v_dict = {c.name: getattr(veh, c.name) for c in veh.__table__.columns}
    v_dict["conductor_nom"] = conductor_nom
    if v_dict.get("conductor_habitual_id") is None and conductor_id_fallback is not None:
        v_dict["conductor_habitual_id"] = conductor_id_fallback
    if v_dict.get("estat") == "ASSIGNAT":
        v_dict["estat"] = "OPERATIU"

    if v_dict.get("estat_itv") is None:
        v_dict["estat_itv"] = "FAVORABLE"
    if v_dict.get("carnet_necessari") is None:
        v_dict["carnet_necessari"] = "B"
    if v_dict.get("tacograf_necessari") is None:
        v_dict["tacograf_necessari"] = False
    if v_dict.get("places") is None:
        v_dict["places"] = 5
    if v_dict.get("pes_maxim_autoritzat") is None:
        v_dict["pes_maxim_autoritzat"] = 3500
    if v_dict.get("horometre_acumulat") is None:
        v_dict["horometre_acumulat"] = 0.0
    if v_dict.get("odometre_acumulat") is None:
        v_dict["odometre_acumulat"] = 0
    if v_dict.get("odometre_inici_contracte") is None:
        v_dict["odometre_inici_contracte"] = 0
    if v_dict.get("consum_adblue_litres") is None:
        v_dict["consum_adblue_litres"] = 0.0
    if v_dict.get("quota_mensual_eur") is None:
        v_dict["quota_mensual_eur"] = 0.0
    if v_dict.get("tarifa_diaria_eur") is None:
        v_dict["tarifa_diaria_eur"] = 0.0
    if v_dict.get("preu_km_exces_eur") is None:
        v_dict["preu_km_exces_eur"] = 0.0
    if v_dict.get("interval_canvi_oli_km") is None:
        v_dict["interval_canvi_oli_km"] = 15000
    if v_dict.get("ultim_canvi_oli_km") is None:
        v_dict["ultim_canvi_oli_km"] = 0

    consum = float(veh.consum_l_100km) if veh.consum_l_100km is not None else None
    mitjana = float(veh.consum_mitjana_historica) if veh.consum_mitjana_historica is not None else None
    tipus_upper = (veh.tipus or "").upper()

    if tipus_upper == "REMOLC":
        v_dict["consum_format"] = "Exempt"
    elif tipus_upper == "MAQUINARIA":
        v_dict["consum_format"] = f"{consum:.1f} L/h" if consum is not None else "Sense dades"
    elif tipus_upper in ("EV", "ELECTRIC"):
        v_dict["consum_format"] = f"{consum:.1f} kWh/100km" if consum is not None else "Sense dades"
    else:
        v_dict["consum_format"] = f"{consum:.1f} L/100km" if consum is not None else "Sense dades"

    anomalia = False
    if consum is not None and mitjana is not None and mitjana > 0:
        if consum > mitjana * 1.10:
            anomalia = True
    v_dict["anomalia_consum"] = anomalia
    v_dict["anomalia_descartada"] = bool(getattr(veh, "anomalia_consum_descartada", False))
    if v_dict["anomalia_descartada"]:
        v_dict["anomalia_consum"] = False

    avui = date.today()
    odo_actual = int(veh.odometre_acumulat or 0)
    odo_inici = int(getattr(veh, "odometre_inici_contracte", 0) or 0)
    km_contracte = max(0, odo_actual - odo_inici)
    v_dict["km_recorreguts_contracte"] = km_contracte

    # Càlcul de percentatge d'ocupació de km (RENTING, LEASING, LLOGUER)
    renting_percent = None
    alerta_renting = False
    nivell_alerta = None
    alerta_renting_km = None
    if veh.regim_adquisicio in ("RENTING", "LEASING", "LLOGUER") and veh.renting_limit_km and veh.renting_limit_km > 0:
        renting_percent = round((km_contracte / veh.renting_limit_km) * 100, 1)
        if renting_percent >= 100:
            alerta_renting = True
            nivell_alerta = "100%"
            alerta_renting_km = "SUPERAT_100"
        elif renting_percent >= 95:
            alerta_renting = True
            nivell_alerta = "95%"
            alerta_renting_km = "CRITIC_95"
        elif renting_percent >= 90:
            alerta_renting = True
            nivell_alerta = "90%"
            alerta_renting_km = "AVIS_90"

    # Projecció temporal del contracte
    dies_restants_contracte = None
    ocupacio_temps_pct = None
    desviacio_ritme_pct = None
    alerta_contracte_venciment = False
    llindar_venciment = 3 if veh.regim_adquisicio == "LLOGUER" else 15

    if veh.data_inici_contracte and veh.data_fi_contracte and veh.data_fi_contracte > veh.data_inici_contracte:
        dies_totals = (veh.data_fi_contracte - veh.data_inici_contracte).days
        dies_passats = max(0, (avui - veh.data_inici_contracte).days)
        dies_restants_contracte = (veh.data_fi_contracte - avui).days
        ocupacio_temps_pct = round(min(100.0, (dies_passats / dies_totals) * 100.0), 1)
        if renting_percent is not None:
            desviacio_ritme_pct = round(renting_percent - ocupacio_temps_pct, 1)
            if desviacio_ritme_pct > 10.0 and not alerta_renting:
                alerta_renting = True
                nivell_alerta = "RITME_EXCES_KM"
                alerta_renting_km = "RITME_EXCES_KM"
        if dies_restants_contracte is not None and dies_restants_contracte <= llindar_venciment:
            alerta_contracte_venciment = True
    elif veh.data_fi_contracte:
        dies_restants_contracte = (veh.data_fi_contracte - avui).days
        if dies_restants_contracte <= llindar_venciment:
            alerta_contracte_venciment = True

    # Càlcul de costos meritats (Fix + Penalització Km Excés + Combustible + Manteniment segons règim)
    cost_fix_meritat = 0.0
    if veh.data_inici_contracte and avui >= veh.data_inici_contracte:
        dies_actiu = max(1, (min(avui, veh.data_fi_contracte or avui) - veh.data_inici_contracte).days)
        if veh.regim_adquisicio == "LLOGUER" and float(veh.tarifa_diaria_eur or 0) > 0:
            cost_fix_meritat = round(dies_actiu * float(veh.tarifa_diaria_eur), 2)
        elif float(veh.quota_mensual_eur or 0) > 0:
            mesos_actiu = max(1.0, round(dies_actiu / 30.4375, 2))
            cost_fix_meritat = round(mesos_actiu * float(veh.quota_mensual_eur), 2)

    km_exces = max(0, km_contracte - (veh.renting_limit_km or 0)) if veh.renting_limit_km else 0
    cost_penalitzacio_km = round(km_exces * float(veh.preu_km_exces_eur or 0.0), 2)

    despesa_comb = round(float(despesa_combustible_acumulada or 0.0), 2)
    despesa_mant = round(float(despesa_manteniment_acumulada or 0.0), 2)
    # En RENTING, LLOGUER i SUBSTITUCIO el manteniment ordinari està inclòs en la quota/tarifa;
    # en PROPIETAT i LEASING corre a càrrec de l'empresa i s'imputa al TCO
    manteniment_computable = (
        0.0 if veh.regim_adquisicio in ("RENTING", "LLOGUER", "SUBSTITUCIO") else despesa_mant
    )

    cost_total = round(cost_fix_meritat + cost_penalitzacio_km + despesa_comb + manteniment_computable, 2)
    cost_per_km = round(cost_total / km_contracte, 4) if km_contracte > 0 else 0.0

    v_dict["renting_ocupacio_percent"] = renting_percent
    v_dict["renting_alerta"] = alerta_renting
    v_dict["renting_nivell_alerta"] = nivell_alerta
    v_dict["alerta_renting_km"] = alerta_renting_km
    v_dict["dies_restants_contracte"] = dies_restants_contracte
    v_dict["ocupacio_temps_percent"] = ocupacio_temps_pct
    v_dict["desviacio_ritme_percent"] = desviacio_ritme_pct
    v_dict["cost_fix_meritat_eur"] = cost_fix_meritat
    v_dict["cost_penalitzacio_km_eur"] = cost_penalitzacio_km
    v_dict["despesa_combustible_acumulada_eur"] = despesa_comb
    v_dict["despesa_manteniment_acumulada_eur"] = despesa_mant
    v_dict["manteniment_computable_tco_eur"] = manteniment_computable
    v_dict["cost_total_acumulat_eur"] = cost_total
    v_dict["cost_per_km_eur"] = cost_per_km
    v_dict["alerta_contracte_venciment"] = alerta_contracte_venciment

    dies_itv = None
    if veh.data_proxima_itv:
        dies_itv = (veh.data_proxima_itv - avui).days
    v_dict["dies_propera_itv"] = dies_itv

    return VehicleResponse.model_validate(v_dict)


@router.get("", response_model=List[VehicleResponse])
@router.get("/vehicles", response_model=List[VehicleResponse])
async def llistar_flota(
    request: Request,
    q: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    db: AsyncSession = Depends(get_db_with_tenant_context),
):
    empresa_id = request.state.empresa_id
    if not empresa_id or empresa_id == "undefined":
        raise HTTPException(status_code=401, detail="No identificat")

    emp_uuid = uuid.UUID(empresa_id)
    stmt = (
        select(Vehicle, Usuari.id, Usuari.nom, Usuari.cognoms)
        .outerjoin(
            Usuari,
            and_(
                Usuari.empresa_id == emp_uuid,
                or_(
                    Vehicle.conductor_habitual_id == Usuari.id,
                    Usuari.vehicle_assignat_id == Vehicle.id,
                ),
            ),
        )
        .where(Vehicle.empresa_id == emp_uuid)
    )

    if q:
        search_term = f"%{q.strip()}%"
        stmt = stmt.where(
            or_(
                Vehicle.matricula.ilike(search_term),
                Vehicle.marca.ilike(search_term),
                Vehicle.model.ilike(search_term),
                Vehicle.companyia_asseguradora.ilike(search_term),
                Vehicle.polissa_asseguranca.ilike(search_term),
                Usuari.nom.ilike(search_term),
                Usuari.cognoms.ilike(search_term),
            )
        )

    stmt = stmt.limit(limit).offset(offset).order_by(Vehicle.created_at.desc())

    result = await db.execute(stmt)
    rows = result.all()
    veh_ids = [veh.id for veh, _, _, _ in rows]
    comb_map, mant_map = await _obtenir_despeses_vehicles(db, emp_uuid, veh_ids)

    vehicles = []
    seen_veh_ids = set()
    for veh, u_id, u_nom, u_cognoms in rows:
        if veh.id in seen_veh_ids:
            continue
        seen_veh_ids.add(veh.id)
        c_nom = f"{u_nom or ''} {u_cognoms or ''}".strip() or None
        vehicles.append(
            _build_vehicle_response(
                veh,
                c_nom,
                despesa_combustible_acumulada=comb_map.get(veh.id, 0.0),
                despesa_manteniment_acumulada=mant_map.get(veh.id, 0.0),
                conductor_id_fallback=u_id,
            )
        )

    return vehicles


@router.post("", response_model=VehicleResponse, status_code=status.HTTP_201_CREATED)
async def alta_vehicle(
    request: Request, vehicle: VehicleCreate, db: AsyncSession = Depends(get_db_with_tenant_context)
):
    empresa_id = request.state.empresa_id
    if not empresa_id or empresa_id == "undefined":
        raise HTTPException(status_code=401, detail="No identificat")

    stmt_mat = select(Vehicle).where(
        Vehicle.empresa_id == uuid.UUID(empresa_id), Vehicle.matricula == vehicle.matricula.strip().upper()
    )
    result_mat = await db.execute(stmt_mat)
    if result_mat.scalars().first():
        raise HTTPException(status_code=400, detail="La matrícula ja es troba registrada")

    estat_norm = "OPERATIU" if vehicle.estat == "ASSIGNAT" else vehicle.estat
    nou_vehicle = Vehicle(
        empresa_id=uuid.UUID(empresa_id),
        matricula=vehicle.matricula.strip().upper(),
        marca=vehicle.marca.strip(),
        model=vehicle.model.strip(),
        tipus=vehicle.tipus,
        distintiu_ambiental=vehicle.distintiu_ambiental,
        estat=estat_norm,
        conductor_habitual_id=None,
        odometre_acumulat=vehicle.odometre_acumulat or 0,
        data_proxima_itv=vehicle.data_proxima_itv,
        estat_itv=vehicle.estat_itv,
        data_caducitat_asseguranca=vehicle.data_caducitat_asseguranca,
        companyia_asseguradora=vehicle.companyia_asseguradora,
        polissa_asseguranca=vehicle.polissa_asseguranca,
        carnet_necessari=vehicle.carnet_necessari,
        historial_reparacions=vehicle.historial_reparacions,
        regim_adquisicio=vehicle.regim_adquisicio,
        renting_limit_km=vehicle.renting_limit_km if vehicle.regim_adquisicio in ("RENTING", "LEASING", "LLOGUER") else None,
        odometre_inici_contracte=vehicle.odometre_inici_contracte or 0,
        data_inici_contracte=vehicle.data_inici_contracte,
        data_fi_contracte=vehicle.data_fi_contracte,
        quota_mensual_eur=vehicle.quota_mensual_eur or 0.0,
        tarifa_diaria_eur=vehicle.tarifa_diaria_eur or 0.0,
        preu_km_exces_eur=vehicle.preu_km_exces_eur or 0.0,
        valor_residual_eur=vehicle.valor_residual_eur,
        fianca_eur=vehicle.fianca_eur,
        data_fi_garantia_oficial=vehicle.data_fi_garantia_oficial,
        interval_canvi_oli_km=vehicle.interval_canvi_oli_km or 15000,
        ultim_canvi_oli_km=vehicle.ultim_canvi_oli_km or 0,
        data_itv_negativa=vehicle.data_itv_negativa,
        data_ultima_descarrega_tacograf=vehicle.data_ultima_descarrega_tacograf,
        tacograf_necessari=vehicle.tacograf_necessari,
        data_propera_descarrega_tacograf=vehicle.data_propera_descarrega_tacograf,
        capacitat_bateria_kwh=vehicle.capacitat_bateria_kwh,
        soh_bateria=vehicle.soh_bateria,
        places=vehicle.places,
        pes_maxim_autoritzat=vehicle.pes_maxim_autoritzat,
        consum_l_100km=vehicle.consum_l_100km,
        consum_mitjana_historica=vehicle.consum_mitjana_historica,
        consum_adblue_litres=vehicle.consum_adblue_litres or 0.0,
    )

    db.add(nou_vehicle)
    await db.flush()

    # Creació automàtica del Magatzem Mòbil per al Vehicle (Spec 004 / Spec 01 / Spec 015)
    magatzem_furgoneta = Magatzem(
        empresa_id=uuid.UUID(empresa_id),
        nom=f"Vehicle {nou_vehicle.matricula} ({nou_vehicle.marca} {nou_vehicle.model})",
        tipus="FURGONETA",
        vehicle_id=nou_vehicle.id,
        actiu=True,
    )
    db.add(magatzem_furgoneta)
    await db.flush()

    if vehicle.conductor_habitual_id:
        await sincronitzar_assignacio_vehicle_operari(
            db=db,
            empresa_id=uuid.UUID(empresa_id),
            vehicle=nou_vehicle,
            nou_conductor_id=vehicle.conductor_habitual_id,
            motiu="Alta de vehicle",
            odometre=nou_vehicle.odometre_acumulat,
        )
        await db.flush()

    c_nom = None
    if nou_vehicle.conductor_habitual_id:
        res_u = await db.execute(select(Usuari).where(Usuari.id == nou_vehicle.conductor_habitual_id))
        u = res_u.scalars().first()
        if u:
            c_nom = f"{u.nom or ''} {u.cognoms or ''}".strip() or None

    response = _build_vehicle_response(nou_vehicle, c_nom)
    await sincronitzar_vehicle_al_disc_empresa(
        db, nou_vehicle.empresa_id, nou_vehicle, response.model_dump(mode="json")
    )
    await db.commit()
    return response


@router.put("/{vehicle_id}", response_model=VehicleResponse)
async def editar_vehicle(
    request: Request,
    vehicle_id: uuid.UUID,
    vehicle: VehicleCreate,
    db: AsyncSession = Depends(get_db_with_tenant_context),
):
    empresa_id = request.state.empresa_id
    if not empresa_id or empresa_id == "undefined":
        raise HTTPException(status_code=401, detail="No identificat")

    emp_uuid = uuid.UUID(empresa_id)
    stmt = select(Vehicle).where(
        Vehicle.id == vehicle_id, Vehicle.empresa_id == emp_uuid
    )
    result = await db.execute(stmt)
    v_db = result.scalars().first()
    if not v_db:
        raise HTTPException(status_code=404, detail="Vehicle no trobat")

    v_db.matricula = vehicle.matricula.strip().upper()
    v_db.marca = vehicle.marca.strip()
    v_db.model = vehicle.model.strip()
    v_db.tipus = vehicle.tipus
    v_db.distintiu_ambiental = vehicle.distintiu_ambiental
    v_db.estat = "OPERATIU" if vehicle.estat == "ASSIGNAT" else vehicle.estat
    if vehicle.odometre_acumulat is not None:
        v_db.odometre_acumulat = vehicle.odometre_acumulat
    v_db.data_proxima_itv = vehicle.data_proxima_itv
    v_db.estat_itv = vehicle.estat_itv
    v_db.data_caducitat_asseguranca = vehicle.data_caducitat_asseguranca
    v_db.companyia_asseguradora = vehicle.companyia_asseguradora
    v_db.polissa_asseguranca = vehicle.polissa_asseguranca
    v_db.carnet_necessari = vehicle.carnet_necessari
    v_db.historial_reparacions = vehicle.historial_reparacions
    v_db.regim_adquisicio = vehicle.regim_adquisicio
    v_db.renting_limit_km = vehicle.renting_limit_km if vehicle.regim_adquisicio in ("RENTING", "LEASING", "LLOGUER") else None
    if vehicle.odometre_inici_contracte is not None:
        v_db.odometre_inici_contracte = vehicle.odometre_inici_contracte
    v_db.data_inici_contracte = vehicle.data_inici_contracte
    v_db.data_fi_contracte = vehicle.data_fi_contracte
    if vehicle.quota_mensual_eur is not None:
        v_db.quota_mensual_eur = vehicle.quota_mensual_eur
    if vehicle.tarifa_diaria_eur is not None:
        v_db.tarifa_diaria_eur = vehicle.tarifa_diaria_eur
    if vehicle.preu_km_exces_eur is not None:
        v_db.preu_km_exces_eur = vehicle.preu_km_exces_eur
    v_db.valor_residual_eur = vehicle.valor_residual_eur
    v_db.fianca_eur = vehicle.fianca_eur
    v_db.data_fi_garantia_oficial = vehicle.data_fi_garantia_oficial
    if vehicle.interval_canvi_oli_km is not None:
        v_db.interval_canvi_oli_km = vehicle.interval_canvi_oli_km
    if vehicle.ultim_canvi_oli_km is not None:
        v_db.ultim_canvi_oli_km = vehicle.ultim_canvi_oli_km
    v_db.data_itv_negativa = vehicle.data_itv_negativa
    v_db.data_ultima_descarrega_tacograf = vehicle.data_ultima_descarrega_tacograf
    v_db.tacograf_necessari = vehicle.tacograf_necessari
    v_db.data_propera_descarrega_tacograf = vehicle.data_propera_descarrega_tacograf
    v_db.capacitat_bateria_kwh = vehicle.capacitat_bateria_kwh
    v_db.soh_bateria = vehicle.soh_bateria
    v_db.places = vehicle.places
    v_db.pes_maxim_autoritzat = vehicle.pes_maxim_autoritzat
    v_db.consum_l_100km = vehicle.consum_l_100km
    v_db.consum_mitjana_historica = vehicle.consum_mitjana_historica
    if vehicle.consum_adblue_litres is not None:
        v_db.consum_adblue_litres = vehicle.consum_adblue_litres

    if vehicle.conductor_habitual_id != v_db.conductor_habitual_id or vehicle.conductor_habitual_id is not None:
        await sincronitzar_assignacio_vehicle_operari(
            db=db,
            empresa_id=emp_uuid,
            vehicle=v_db,
            nou_conductor_id=vehicle.conductor_habitual_id,
            motiu="Modificació fitxa vehicle",
            odometre=v_db.odometre_acumulat,
        )

    await db.flush()

    c_nom = None
    if v_db.conductor_habitual_id:
        res_u = await db.execute(select(Usuari).where(Usuari.id == v_db.conductor_habitual_id))
        u = res_u.scalars().first()
        if u:
            c_nom = f"{u.nom or ''} {u.cognoms or ''}".strip() or None

    comb_map, mant_map = await _obtenir_despeses_vehicles(db, emp_uuid, [v_db.id])
    response = _build_vehicle_response(
        v_db,
        c_nom,
        despesa_combustible_acumulada=comb_map.get(v_db.id, 0.0),
        despesa_manteniment_acumulada=mant_map.get(v_db.id, 0.0),
    )
    await sincronitzar_vehicle_al_disc_empresa(
        db, emp_uuid, v_db, response.model_dump(mode="json")
    )
    await db.commit()
    return response


class RegistrarItvRequest(BaseModel):
    vehicle_id: uuid.UUID
    veredicte: str = Field(..., description="FAVORABLE, LEVE, DESFAVORABLE, NEGATIVA")
    data_proxima_itv: date
    defectes_detectats: Optional[str] = None


@router.post("/registrar-itv")
async def registrar_itv(
    request: Request,
    payload: RegistrarItvRequest,
    db: AsyncSession = Depends(get_db_with_tenant_context),
):
    empresa_id = request.state.empresa_id
    if not empresa_id or empresa_id == "undefined":
        raise HTTPException(status_code=401, detail="No identificat")

    emp_uuid = uuid.UUID(empresa_id)
    stmt = select(Vehicle).where(
        Vehicle.id == payload.vehicle_id, Vehicle.empresa_id == emp_uuid
    )
    result = await db.execute(stmt)
    v_db = result.scalars().first()
    if not v_db:
        raise HTTPException(status_code=404, detail="Vehicle no trobat")

    v_db.estat_itv = payload.veredicte
    v_db.data_proxima_itv = payload.data_proxima_itv

    # 4 veredictes d'acord amb la Spec 006 RF-18:
    # 1. FAVORABLE -> OPERATIU
    # 2. LEVE -> LEVE (operatiu per llei, defectes a manteniment)
    # 3. DESFAVORABLE -> DESFAVORABLE (immobilitzat + finestra 2 mesos + OT interna)
    # 4. NEGATIVA -> INACTIVAT (immobilitzat immediat grua obligatòria)
    if payload.veredicte == "FAVORABLE":
        v_db.estat = "OPERATIU"
    elif payload.veredicte in ("LEVE", "FAVORABLE_LEUS"):
        v_db.estat = "LEVE"
        if payload.defectes_detectats:
            prev = v_db.historial_reparacions or ""
            v_db.historial_reparacions = f"{prev}\n[ITV Favorable DL {date.today()}]: {payload.defectes_detectats}".strip()
    elif payload.veredicte == "DESFAVORABLE":
        v_db.estat = "DESFAVORABLE"
        ot_interna = OrdreTreball(
            empresa_id=emp_uuid,
            codi=f"OT-ITV-{v_db.matricula}-{str(uuid.uuid4())[:4].upper()}",
            titol=f"Subsanació ITV Desfavorable - {v_db.matricula}",
            descripcio=f"Defectes detectats en ITV: {payload.defectes_detectats or 'Revisió general urgent per ITV desfavorable'}. Termini màxim 2 mesos (RD 920/2017).",
            estat="PENDENT",
            prioritat="CRITICA",
            vehicle_id=v_db.id,
        )
        db.add(ot_interna)
    elif payload.veredicte == "NEGATIVA":
        v_db.estat = "INACTIVAT"
        ot_interna = OrdreTreball(
            empresa_id=emp_uuid,
            codi=f"OT-GRUA-{v_db.matricula}-{str(uuid.uuid4())[:4].upper()}",
            titol=f"Immobilització Total ITV Negativa - {v_db.matricula}",
            descripcio=f"Vehicle immobilitzat per ITV Negativa. Trasllat en grua obligatori a taller. Defectes: {payload.defectes_detectats or 'Defectes molt greus que inhabiliten la circulació'}.",
            estat="PENDENT",
            prioritat="CRITICA",
            vehicle_id=v_db.id,
        )
        db.add(ot_interna)

    estat_final = v_db.estat
    estat_itv_final = v_db.estat_itv
    data_prox_str = str(v_db.data_proxima_itv)
    await sincronitzar_vehicle_al_disc_empresa(db, emp_uuid, v_db)
    await db.commit()
    return {"ok": True, "estat": estat_final, "estat_itv": estat_itv_final, "data_proxima_itv": data_prox_str}


class DescartarAnomaliaRequest(BaseModel):
    vehicle_id: uuid.UUID
    motiu_tipificat: str
    observacions: Optional[str] = None


@router.post("/descartar-anomalia-consum")
async def descartar_anomalia_consum(
    request: Request,
    payload: DescartarAnomaliaRequest,
    db: AsyncSession = Depends(get_db_with_tenant_context),
):
    empresa_id = request.state.empresa_id
    if not empresa_id or empresa_id == "undefined":
        raise HTTPException(status_code=401, detail="No identificat")

    emp_uuid = uuid.UUID(empresa_id)
    stmt = select(Vehicle).where(
        Vehicle.id == payload.vehicle_id, Vehicle.empresa_id == emp_uuid
    )
    result = await db.execute(stmt)
    v_db = result.scalars().first()
    if not v_db:
        raise HTTPException(status_code=404, detail="Vehicle no trobat")

    data_avui = date.today().isoformat()
    nota = f"[Anomalia Consum Descartada {data_avui} - Motiu: {payload.motiu_tipificat}]: {payload.observacions or 'Sense observacions'}"
    prev = v_db.historial_reparacions or ""
    v_db.historial_reparacions = f"{prev}\n{nota}".strip()

    await sincronitzar_vehicle_al_disc_empresa(
        db, emp_uuid, v_db, {"historial_reparacions": v_db.historial_reparacions}
    )
    await db.commit()
    return {"ok": True, "vehicle_id": str(v_db.id), "motiu": payload.motiu_tipificat, "data_resolucio": data_avui}


# ---------------------------------------------------------------------------
# Càlcul de Vehicles Propers per Haversine (Spec 006 / Spec 012 / Phase 3)
# ---------------------------------------------------------------------------


def calcular_distancia_haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calcula la distància en quilòmetres entre dues coordenades usant la fórmula de Haversine."""
    R = 6371.0  # Radi de la Terra en km
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return round(R * c, 2)


class VehicleProperItem(BaseModel):
    vehicle_id: uuid.UUID
    matricula: str
    marca: str
    model: str
    estat: str
    distancia_km: float
    lat: float
    lng: float
    ordre_treball_id: Optional[uuid.UUID] = None
    ordre_treball_codi: Optional[str] = None
    ordre_treball_titol: Optional[str] = None


@router.get("/propers", response_model=List[VehicleProperItem])
async def llistar_vehicles_propers(
    request: Request,
    lat: float = Query(..., description="Latitud de l'objectiu"),
    lng: float = Query(..., description="Longitud de l'objectiu"),
    limit: int = Query(10, ge=1, le=50),
    db: AsyncSession = Depends(get_db_with_tenant_context),
):
    """
    Retorna els vehicles de l'empresa ordenats per proximitat geogràfica a les coordenades donades (Haversine).
    Determina la posició del vehicle segons l'OT activa en curs o ubicació registrada.
    """
    empresa_id = getattr(request.state, "empresa_id", None) or request.headers.get("X-Empresa-ID")
    if not empresa_id or empresa_id == "undefined":
        raise HTTPException(status_code=401, detail="No identificat")

    empresa_uuid = uuid.UUID(empresa_id)

    # Obtenir vehicles de l'empresa
    stmt_v = select(Vehicle).where(Vehicle.empresa_id == empresa_uuid)
    res_v = await db.execute(stmt_v)
    vehicles = res_v.scalars().all()

    if not vehicles:
        return []

    # Obtenir feines actives per associar posició de camp
    stmt_ot = select(OrdreTreball).where(
        OrdreTreball.empresa_id == empresa_uuid,
        OrdreTreball.vehicle_id.isnot(None),
        OrdreTreball.estat.in_(["EN_OBRA", "EN_RUTA", "EN_CURS", "PENDENT"]),
    )
    res_ot = await db.execute(stmt_ot)
    ots = res_ot.scalars().all()
    vehicle_ot_map = {ot.vehicle_id: ot for ot in ots}

    resultats: List[VehicleProperItem] = []

    for v in vehicles:
        # Coordenades per defecte si no té OT activa
        v_lat, v_lng = None, None
        ot_associada = vehicle_ot_map.get(v.id)

        if ot_associada and ot_associada.adreca:
            m = re.findall(r"[-+]?\d+\.\d+", ot_associada.adreca)
            if len(m) >= 2:
                v_lat, v_lng = float(m[0]), float(m[1])
            elif "," in ot_associada.adreca:
                try:
                    parts = [float(p.strip()) for p in ot_associada.adreca.split(",")]
                    if len(parts) >= 2:
                        v_lat, v_lng = parts[0], parts[1]
                except (ValueError, TypeError):
                    pass

        dist = (
            calcular_distancia_haversine(lat, lng, v_lat, v_lng)
            if v_lat is not None and v_lng is not None
            else None
        )

        resultats.append(
            VehicleProperItem(
                vehicle_id=v.id,
                matricula=v.matricula,
                marca=v.marca,
                model=v.model,
                estat=v.estat,
                distancia_km=dist,  # type: ignore
                lat=v_lat,  # type: ignore
                lng=v_lng,  # type: ignore
                ordre_treball_id=ot_associada.id if ot_associada else None,
                ordre_treball_codi=ot_associada.codi if ot_associada else None,
                ordre_treball_titol=ot_associada.titol if ot_associada else None,
            )
        )

    # Ordenar pel vehicle més proper
    resultats.sort(key=lambda x: x.distancia_km if x.distancia_km is not None else float("inf"))

    return resultats[:limit]


@router.get("/{vehicle_id}", response_model=VehicleResponse)
async def obtenir_vehicle(
    request: Request,
    vehicle_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_with_tenant_context),
):
    empresa_id = request.state.empresa_id
    if not empresa_id or empresa_id == "undefined":
        raise HTTPException(status_code=401, detail="No identificat")

    emp_uuid = uuid.UUID(empresa_id)
    stmt = (
        select(Vehicle, Usuari.id, Usuari.nom, Usuari.cognoms)
        .outerjoin(
            Usuari,
            and_(
                Usuari.empresa_id == emp_uuid,
                or_(
                    Vehicle.conductor_habitual_id == Usuari.id,
                    Usuari.vehicle_assignat_id == Vehicle.id,
                ),
            ),
        )
        .where(Vehicle.id == vehicle_id, Vehicle.empresa_id == emp_uuid)
    )
    result = await db.execute(stmt)
    row = result.first()
    if not row:
        raise HTTPException(status_code=404, detail="Vehicle no trobat")

    veh, u_id, u_nom, u_cognoms = row
    c_nom = f"{u_nom or ''} {u_cognoms or ''}".strip() or None
    comb_map, mant_map = await _obtenir_despeses_vehicles(db, emp_uuid, [veh.id])
    return _build_vehicle_response(
        veh,
        c_nom,
        despesa_combustible_acumulada=comb_map.get(veh.id, 0.0),
        despesa_manteniment_acumulada=mant_map.get(veh.id, 0.0),
        conductor_id_fallback=u_id,
    )


@router.post("/{vehicle_id}/documents", status_code=201)
async def pujar_document_flota(
    request: Request,
    vehicle_id: uuid.UUID,
    tipus_document: str = Form(...),
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db_with_tenant_context),
):
    empresa_id = request.state.empresa_id
    if not empresa_id:
        raise HTTPException(status_code=401)
    empresa_id = uuid.UUID(empresa_id)

    # Comprovar vehicle
    stmt = select(Vehicle).where(Vehicle.id == vehicle_id, Vehicle.empresa_id == empresa_id)
    res = await db.execute(stmt)
    v_db = res.scalars().first()
    if not v_db:
        raise HTTPException(status_code=404, detail="Vehicle no trobat")

    # Guardar disc local
    file_bytes = await file.read()
    kind = filetype.guess(file_bytes)
    filename_lower = (file.filename or "").lower()
    is_pdf = file_bytes.startswith(b"%PDF") or filename_lower.endswith(".pdf")
    is_text = False
    if filename_lower.endswith((".md", ".txt", ".markdown", ".csv")):
        is_text = True
    else:
        try:
            file_bytes.decode("utf-8")
            is_text = True
        except Exception:
            is_text = False

    if not kind and not is_pdf and not is_text:
        raise HTTPException(
            status_code=400,
            detail="Tipus de fitxer invàlid. Cal una imatge, document PDF o fitxer de text/markdown (.md).",
        )

    if kind:
        file_ext = kind.extension
        content_type = kind.mime
    elif is_pdf:
        file_ext = "pdf"
        content_type = "application/pdf"
    elif filename_lower.endswith(".md"):
        file_ext = "md"
        content_type = "text/markdown; charset=utf-8"
    elif filename_lower.endswith(".markdown"):
        file_ext = "markdown"
        content_type = "text/markdown; charset=utf-8"
    else:
        file_ext = "txt"
        content_type = "text/plain; charset=utf-8"

    safe_name = f"doc_{vehicle_id}_{uuid.uuid4().hex[:8]}.{file_ext}"
    file_path = await SovereignStorageGateway.pujar_fitxer_binari(
        db=db,
        empresa_id=empresa_id,
        categoria="vehicles",
        nom_fitxer=safe_name,
        content=file_bytes,
        content_type=content_type,
    )

    doc = DocumentFlota(
        empresa_id=empresa_id,
        vehicle_id=vehicle_id,
        tipus_document=tipus_document,
        nom_arxiu=safe_name,
        ruta_arxiu=file_path,
        creat_per_id=None,
    )
    db.add(doc)
    await db.flush()

    await SovereignStorageGateway.desar_entitat_json(
        db=db,
        empresa_id=empresa_id,
        categoria="vehicles",
        item_id=f"doc_{doc.id}",
        dades={
            "id": str(doc.id),
            "vehicle_id": str(vehicle_id),
            "matricula": v_db.matricula,
            "tipus_document": tipus_document,
            "nom_arxiu": safe_name,
            "ruta_arxiu": file_path,
        },
    )
    await db.commit()

    # Executar OCR asíncron
    try:
        from app.workers.tasks import processar_ocr_document_task

        processar_ocr_document_task.delay(file_path, str(empresa_id))
    except Exception:
        pass

    return {
        "missatge": "Document pujat al disc dur de l'empresa i en procés d'OCR",
        "id": str(doc.id),
        "ruta_arxiu": file_path,
    }


@router.get("/{vehicle_id}/documents")
async def llistar_documents_flota(
    request: Request, vehicle_id: uuid.UUID, db: AsyncSession = Depends(get_db_with_tenant_context)
):
    empresa_id = request.state.empresa_id
    if not empresa_id:
        raise HTTPException(status_code=401)
    empresa_id = uuid.UUID(empresa_id)
    stmt = select(DocumentFlota).where(
        DocumentFlota.vehicle_id == vehicle_id, DocumentFlota.empresa_id == empresa_id
    )
    res = await db.execute(stmt)
    docs = res.scalars().all()

    return [
        {
            "id": str(d.id),
            "tipus": d.tipus_document,
            "nom_arxiu": d.nom_arxiu,
            "ruta_arxiu": d.ruta_arxiu,
            "url_fitxer": f"/api/v1/gestio/flota/{vehicle_id}/documents/{d.id}/fitxer",
            "data": d.data_document.isoformat() if d.data_document else None,
        }
        for d in docs
    ]


@router.get("/{vehicle_id}/documents/{doc_id}/fitxer")
async def descarregar_document_flota(
    request: Request,
    vehicle_id: uuid.UUID,
    doc_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_with_tenant_context),
):
    """Serveix el document del vehicle directament des del disc dur dedicat de l'empresa."""
    empresa_id = request.state.empresa_id
    if not empresa_id:
        raise HTTPException(status_code=401, detail="No identificat")
    emp_uuid = uuid.UUID(empresa_id)

    stmt = select(DocumentFlota).where(
        DocumentFlota.id == doc_id,
        DocumentFlota.vehicle_id == vehicle_id,
        DocumentFlota.empresa_id == emp_uuid,
    )
    doc = (await db.execute(stmt)).scalars().first()
    if not doc or not doc.ruta_arxiu:
        raise HTTPException(status_code=404, detail="Document de vehicle no trobat")

    ext = (doc.nom_arxiu or "").lower().rsplit(".", 1)[-1]
    media_map = {
        "pdf": "application/pdf",
        "jpg": "image/jpeg",
        "jpeg": "image/jpeg",
        "png": "image/png",
        "webp": "image/webp",
        "md": "text/markdown; charset=utf-8",
        "txt": "text/plain; charset=utf-8",
    }
    media_type = media_map.get(ext, "application/octet-stream")
    return await SovereignStorageGateway.servir_fitxer(
        db=db,
        empresa_id=emp_uuid,
        fitxer_path=doc.ruta_arxiu,
        media_type=media_type,
        disposition="inline",
    )


@router.post("/ocr-draft")
async def ocr_vehicle_draft(
    request: Request,
    files: Optional[List[UploadFile]] = File(None),
    file: Optional[UploadFile] = File(None),
):
    empresa_id = request.state.empresa_id
    if not empresa_id or empresa_id == "undefined":
        raise HTTPException(status_code=401, detail="No identificat")

    all_files: List[UploadFile] = []
    if files:
        all_files.extend([f for f in files if f and f.filename])
    if file and file.filename and file not in all_files:
        all_files.append(file)

    if not all_files:
        raise HTTPException(
            status_code=400,
            detail="Cal adjuntar com a mínim un document de vehicle (Targeta ITV, Permís de Circulació o Pòlissa d'Assegurança)",
        )

    merged_data: Dict[str, Any] = {
        "status": "EXTRET_AUTOMATIC",
        "confidence": 0.0,
        "matricula": None,
        "bastidor": None,
        "marca": None,
        "model": None,
        "tipus": None,
        "distintiu_ambiental": None,
        "estat_itv": None,
        "data_proxima_itv": None,
        "data_inspeccio_itv": None,
        "data_matriculacio": None,
        "odometre_acumulat": None,
        "companyia_asseguradora": None,
        "polissa_asseguranca": None,
        "data_caducitat_asseguranca": None,
        "regim_adquisicio": None,
        "renting_limit_km": None,
        "carnet_necessari": None,
        "documents_processats": [],
    }

    confidences: List[float] = []

    for upload in all_files:
        file_bytes = await upload.read()
        if not file_bytes:
            continue

        res = await processar_ocr_document_vehicle(file_bytes)
        confidences.append(res.get("confidence", 0.0))

        # Fusionar camps no nuls procedents de qualsevol document pujat
        for k in [
            "matricula",
            "bastidor",
            "marca",
            "model",
            "tipus",
            "distintiu_ambiental",
            "estat_itv",
            "data_proxima_itv",
            "data_inspeccio_itv",
            "data_matriculacio",
            "odometre_acumulat",
            "companyia_asseguradora",
            "polissa_asseguranca",
            "data_caducitat_asseguranca",
            "regim_adquisicio",
            "renting_limit_km",
            "carnet_necessari",
        ]:
            if res.get(k) is not None and not merged_data.get(k):
                merged_data[k] = res[k]

        merged_data["documents_processats"].append(
            {
                "nom": upload.filename,
                "tipus_detectat": res.get("tipus_document", "GENERAL"),
                "matricula_detectada": res.get("matricula"),
            }
        )

    # Valors per defecte si no s'han especificat en cap document
    if not merged_data["tipus"]:
        merged_data["tipus"] = "DIESEL"
    if not merged_data["distintiu_ambiental"]:
        if merged_data["tipus"] == "EV":
            merged_data["distintiu_ambiental"] = "ZERO"
        elif merged_data["tipus"] == "PHEV":
            merged_data["distintiu_ambiental"] = "ECO"
        else:
            merged_data["distintiu_ambiental"] = "C"
    if not merged_data["regim_adquisicio"]:
        merged_data["regim_adquisicio"] = "PROPIETAT"
    if merged_data["regim_adquisicio"] not in ("RENTING", "LEASING", "LLOGUER"):
        merged_data["renting_limit_km"] = None
    if not merged_data["carnet_necessari"]:
        merged_data["carnet_necessari"] = "B"
    if not merged_data["estat_itv"]:
        merged_data["estat_itv"] = "FAVORABLE"

    merged_data["confidence"] = max(confidences) if confidences else 0.0
    trobat = bool(merged_data.get("matricula") or merged_data.get("bastidor"))
    merged_data["status"] = "EXTRET_AUTOMATIC" if trobat else "PENDENT_REVISIO_MANUAL"

    return merged_data


class AssignarVehicleRequest(BaseModel):
    usuari_id: uuid.UUID
    odometre: Optional[int] = None
    motiu: Optional[str] = None


@router.post("/{id}/assignar")
async def assignar_vehicle(
    request: Request,
    id: uuid.UUID,
    data: AssignarVehicleRequest,
    db: AsyncSession = Depends(get_db_with_tenant_context),
):
    empresa_id = uuid.UUID(request.state.empresa_id)

    # Check vehicle
    v = await db.scalar(select(Vehicle).where(Vehicle.id == id, Vehicle.empresa_id == empresa_id))
    if not v:
        raise HTTPException(status_code=404, detail="Vehicle no trobat")

    # Sincronitzar assignació 1:1 amb guarda de carnet
    await sincronitzar_assignacio_vehicle_operari(
        db=db,
        empresa_id=empresa_id,
        vehicle=v,
        nou_conductor_id=data.usuari_id,
        motiu=data.motiu or "Assignació de flota",
        odometre=data.odometre,
    )
    await db.commit()
    return {
        "status": "ok",
        "missatge": "Vehicle assignat correctament",
        "id": str(v.id),
        "vehicle_id": str(v.id),
        "conductor_habitual_id": str(v.conductor_habitual_id) if v.conductor_habitual_id else None,
        "estat": v.estat,
    }


class RevocarVehicleRequest(BaseModel):
    odometre: Optional[int] = None
    motiu: Optional[str] = None


@router.post("/{id}/revocar")
async def revocar_vehicle(
    request: Request,
    id: uuid.UUID,
    data: RevocarVehicleRequest,
    db: AsyncSession = Depends(get_db_with_tenant_context),
):
    empresa_id = uuid.UUID(request.state.empresa_id)

    v = await db.scalar(select(Vehicle).where(Vehicle.id == id, Vehicle.empresa_id == empresa_id))
    if not v:
        raise HTTPException(status_code=404, detail="Vehicle no trobat")

    # Sincronitzar desvinculació 1:1
    await sincronitzar_assignacio_vehicle_operari(
        db=db,
        empresa_id=empresa_id,
        vehicle=v,
        nou_conductor_id=None,
        motiu=data.motiu or "Revocació d'assignació",
        odometre=data.odometre,
    )
    await db.commit()
    return {
        "status": "ok",
        "missatge": "Assignació revocada correctament",
        "id": str(v.id),
        "vehicle_id": str(v.id),
        "conductor_habitual_id": None,
        "estat": v.estat,
    }


class MantenimentCreate(BaseModel):
    data_manteniment: date
    tipus: str = Field(..., max_length=50)
    descripcio: str
    taller: Optional[str] = None
    cost_euros: Optional[float] = None


@router.post("/{vehicle_id}/manteniments", status_code=201)
async def crear_manteniment(
    request: Request,
    vehicle_id: uuid.UUID,
    manteniment: MantenimentCreate,
    db: AsyncSession = Depends(get_db_with_tenant_context),
):
    empresa_id = uuid.UUID(request.state.empresa_id)

    v = await db.scalar(
        select(Vehicle).where(Vehicle.id == vehicle_id, Vehicle.empresa_id == empresa_id)
    )
    if not v:
        raise HTTPException(status_code=404, detail="Vehicle no trobat")

    mant = MantenimentVehicle(
        empresa_id=empresa_id,
        vehicle_id=vehicle_id,
        data_manteniment=datetime.combine(
            manteniment.data_manteniment, datetime.min.time(), tzinfo=timezone.utc
        ),
        tipus=manteniment.tipus,
        descripcio=manteniment.descripcio,
        taller=manteniment.taller,
        cost_euros=manteniment.cost_euros,
    )
    db.add(mant)
    await db.flush()
    await SovereignStorageGateway.desar_entitat_json(
        db=db,
        empresa_id=empresa_id,
        categoria="vehicles",
        item_id=f"manteniment_{mant.id}",
        dades={
            "id": str(mant.id),
            "vehicle_id": str(vehicle_id),
            "matricula": v.matricula,
            "data_manteniment": manteniment.data_manteniment.isoformat(),
            "tipus": manteniment.tipus,
            "descripcio": manteniment.descripcio,
            "taller": manteniment.taller,
            "cost_euros": manteniment.cost_euros,
        },
    )
    await sincronitzar_vehicle_al_disc_empresa(db, empresa_id, v)
    await db.commit()
    return {"id": str(mant.id), "missatge": "Manteniment registrat"}


@router.get("/{vehicle_id}/manteniments")
async def llistar_manteniments(
    request: Request, vehicle_id: uuid.UUID, db: AsyncSession = Depends(get_db_with_tenant_context)
):
    empresa_id = uuid.UUID(request.state.empresa_id)
    mants = await db.execute(
        select(MantenimentVehicle)
        .where(
            MantenimentVehicle.vehicle_id == vehicle_id, MantenimentVehicle.empresa_id == empresa_id
        )
        .order_by(MantenimentVehicle.data_manteniment.desc())
    )
    return list(mants.scalars().all())


@router.post("/ocr-document")
async def ocr_document_vehicle(request: Request, file: UploadFile = File(...)):
    empresa_id = request.state.empresa_id
    if not empresa_id or empresa_id == "undefined":
        raise HTTPException(status_code=401, detail="No identificat")

    file_bytes = await file.read()
    if not file_bytes:
        raise HTTPException(status_code=400, detail="Fitxer buit")

    kind = filetype.guess(file_bytes)
    filename_lower = (file.filename or "").lower()
    is_pdf = file_bytes.startswith(b"%PDF") or filename_lower.endswith(".pdf")
    is_text = False
    if filename_lower.endswith((".md", ".txt", ".markdown", ".csv")):
        is_text = True
    else:
        try:
            file_bytes.decode("utf-8")
            is_text = True
        except Exception:
            is_text = False

    if not kind and not is_pdf and not is_text:
        raise HTTPException(
            status_code=400,
            detail="Tipus de fitxer invàlid. Cal una imatge, document PDF o fitxer de text/markdown (.md).",
        )

    resultat = await processar_ocr_document_vehicle(file_bytes)
    return resultat
