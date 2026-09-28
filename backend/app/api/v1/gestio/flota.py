import math
import re
import uuid
from datetime import date
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db_with_tenant_context
from app.core.security import require_roles
from app.models.models import OrdreTreball, Vehicle

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
    data_proxima_itv: Optional[date] = None
    estat_itv: str = Field("FAVORABLE", max_length=50)
    data_caducitat_asseguranca: Optional[date] = None
    companyia_asseguradora: Optional[str] = Field(None, max_length=100)
    carnet_necessari: str = Field("B", max_length=10)
    historial_reparacions: Optional[str] = None
    regim_adquisicio: str = Field("PROPIETAT", max_length=30)
    renting_limit_km: Optional[int] = None
    tacograf_necessari: bool = False
    data_propera_descarrega_tacograf: Optional[date] = None
    capacitat_bateria_kwh: Optional[float] = None
    soh_bateria: Optional[float] = None
    places: int = 5
    pes_maxim_autoritzat: int = 3500

class VehicleResponse(VehicleCreate):
    id: uuid.UUID
    horometre_acumulat: float
    odometre_acumulat: int
    consum_l_100km: Optional[float] = None
    consum_mitjana_historica: Optional[float] = None
    consum_adblue_litres: float = 0.0

@router.get("", response_model=List[VehicleResponse])
async def llistar_flota(
    request: Request,
    q: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    db: AsyncSession = Depends(get_db_with_tenant_context)
):
    empresa_id = request.state.empresa_id
    if not empresa_id or empresa_id == 'undefined':
        raise HTTPException(status_code=401, detail="No identificat")

    stmt = select(Vehicle).where(Vehicle.empresa_id == uuid.UUID(empresa_id))

    if q:
        search_term = f"%{q}%"
        stmt = stmt.where(
            or_(
                Vehicle.matricula.ilike(search_term),
                Vehicle.marca.ilike(search_term),
                Vehicle.model.ilike(search_term)
            )
        )

    stmt = stmt.limit(limit).offset(offset).order_by(Vehicle.created_at.desc())

    result = await db.execute(stmt)
    vehicles = result.scalars().all()

    return vehicles

@router.post("", response_model=VehicleResponse, status_code=status.HTTP_201_CREATED)
async def alta_vehicle(
    request: Request,
    vehicle: VehicleCreate,
    db: AsyncSession = Depends(get_db_with_tenant_context)
):
    empresa_id = request.state.empresa_id
    if not empresa_id or empresa_id == 'undefined':
        raise HTTPException(status_code=401, detail="No identificat")

    stmt_mat = select(Vehicle).where(Vehicle.empresa_id == uuid.UUID(empresa_id), Vehicle.matricula == vehicle.matricula)
    result_mat = await db.execute(stmt_mat)
    if result_mat.scalars().first():
        raise HTTPException(status_code=400, detail="La matrícula ja es troba registrada")

    nou_vehicle = Vehicle(
        empresa_id=uuid.UUID(empresa_id),
        matricula=vehicle.matricula,
        marca=vehicle.marca,
        model=vehicle.model,
        tipus=vehicle.tipus,
        distintiu_ambiental=vehicle.distintiu_ambiental,
        estat=vehicle.estat,
        data_proxima_itv=vehicle.data_proxima_itv,
        estat_itv=vehicle.estat_itv,
        data_caducitat_asseguranca=vehicle.data_caducitat_asseguranca,
        companyia_asseguradora=vehicle.companyia_asseguradora,
        carnet_necessari=vehicle.carnet_necessari,
        historial_reparacions=vehicle.historial_reparacions,
        regim_adquisicio=vehicle.regim_adquisicio,
        renting_limit_km=vehicle.renting_limit_km,
        tacograf_necessari=vehicle.tacograf_necessari,
        data_propera_descarrega_tacograf=vehicle.data_propera_descarrega_tacograf,
        capacitat_bateria_kwh=vehicle.capacitat_bateria_kwh,
        soh_bateria=vehicle.soh_bateria,
        places=vehicle.places,
        pes_maxim_autoritzat=vehicle.pes_maxim_autoritzat
    )

    db.add(nou_vehicle)
    await db.commit()

    return nou_vehicle

@router.put("/{vehicle_id}", response_model=VehicleResponse)
async def editar_vehicle(
    request: Request,
    vehicle_id: uuid.UUID,
    vehicle: VehicleCreate,
    db: AsyncSession = Depends(get_db_with_tenant_context)
):
    empresa_id = request.state.empresa_id
    if not empresa_id or empresa_id == 'undefined':
        raise HTTPException(status_code=401, detail="No identificat")

    stmt = select(Vehicle).where(Vehicle.id == vehicle_id, Vehicle.empresa_id == uuid.UUID(empresa_id))
    result = await db.execute(stmt)
    v_db = result.scalars().first()
    if not v_db:
        raise HTTPException(status_code=404, detail="Vehicle no trobat")
        
    v_db.matricula = vehicle.matricula
    v_db.marca = vehicle.marca
    v_db.model = vehicle.model
    v_db.tipus = vehicle.tipus
    v_db.distintiu_ambiental = vehicle.distintiu_ambiental
    v_db.estat = vehicle.estat
    v_db.data_proxima_itv = vehicle.data_proxima_itv
    v_db.estat_itv = vehicle.estat_itv
    v_db.data_caducitat_asseguranca = vehicle.data_caducitat_asseguranca
    v_db.companyia_asseguradora = vehicle.companyia_asseguradora
    v_db.carnet_necessari = vehicle.carnet_necessari
    v_db.historial_reparacions = vehicle.historial_reparacions
    v_db.regim_adquisicio = vehicle.regim_adquisicio
    v_db.renting_limit_km = vehicle.renting_limit_km
    v_db.tacograf_necessari = vehicle.tacograf_necessari
    v_db.data_propera_descarrega_tacograf = vehicle.data_propera_descarrega_tacograf
    v_db.capacitat_bateria_kwh = vehicle.capacitat_bateria_kwh
    v_db.soh_bateria = vehicle.soh_bateria
    v_db.places = vehicle.places
    v_db.pes_maxim_autoritzat = vehicle.pes_maxim_autoritzat

    await db.commit()
    await db.refresh(v_db)
    
    return v_db



# ---------------------------------------------------------------------------
# Càlcul de Vehicles Propers per Haversine (Spec 006 / Spec 012 / Phase 3)
# ---------------------------------------------------------------------------

def calcular_distancia_haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calcula la distància en quilòmetres entre dues coordenades usant la fórmula de Haversine."""
    R = 6371.0  # Radi de la Terra en km
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat / 2) ** 2 +
         math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2)
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
    db: AsyncSession = Depends(get_db_with_tenant_context)
):
    """
    Retorna els vehicles de l'empresa ordenats per proximitat geogràfica a les coordenades donades (Haversine).
    Determina la posició del vehicle segons l'OT activa en curs o ubicació registrada.
    """
    empresa_id = getattr(request.state, "empresa_id", None) or request.headers.get("X-Empresa-ID")
    if not empresa_id or empresa_id == 'undefined':
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
        OrdreTreball.estat.in_(["EN_OBRA", "EN_RUTA", "EN_CURS", "PENDENT"])
    )
    res_ot = await db.execute(stmt_ot)
    ots = res_ot.scalars().all()
    vehicle_ot_map = {ot.vehicle_id: ot for ot in ots}

    resultats: List[VehicleProperItem] = []

    for v in vehicles:
        # Coordenades per defecte si no té OT activa
        v_lat, v_lng = 41.3851, 2.1734
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

        dist = calcular_distancia_haversine(lat, lng, v_lat, v_lng)

        resultats.append(VehicleProperItem(
            vehicle_id=v.id,
            matricula=v.matricula,
            marca=v.marca,
            model=v.model,
            estat=v.estat,
            distancia_km=dist,
            lat=v_lat,
            lng=v_lng,
            ordre_treball_id=ot_associada.id if ot_associada else None,
            ordre_treball_codi=ot_associada.codi if ot_associada else None,
            ordre_treball_titol=ot_associada.titol if ot_associada else None
        ))

    # Ordenar pel vehicle més proper
    resultats.sort(key=lambda x: x.distancia_km)

    return resultats[:limit]

