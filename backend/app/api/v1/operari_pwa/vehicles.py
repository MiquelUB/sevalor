import uuid
from typing import List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel, Field

from app.core.db import get_db_with_tenant_context
from app.core.security import require_roles
from app.models.models import Vehicle, Incidencia

router = APIRouter(
    prefix="/operari/vehicles",
    tags=["Operari PWA Vehicles"],
    dependencies=[Depends(require_roles(["OPERARI", "CAPATAZ", "CAP_DE_COLLA", "BOSS", "SUPERADMIN"]))],
)

class VehicleResponse(BaseModel):
    id: uuid.UUID
    matricula: str
    marca: str
    model: str
    estat: str
    odometre_acumulat: int | None

@router.get("", response_model=List[VehicleResponse])
async def llistar_vehicles_pwa(
    request: Request,
    db: AsyncSession = Depends(get_db_with_tenant_context)
):
    empresa_id = request.state.empresa_id
    res = await db.execute(select(Vehicle).where(Vehicle.empresa_id == uuid.UUID(empresa_id)))
    vehicles = res.scalars().all()
    return [
        VehicleResponse(
            id=v.id,
            matricula=v.matricula,
            marca=v.marca,
            model=v.model,
            estat=v.estat,
            odometre_acumulat=v.odometre_acumulat
        ) for v in vehicles
    ]

class ReportDanyRequest(BaseModel):
    descripcio: str
    gravetat: str

@router.post("/{vehicle_id}/danys")
async def reportar_dany_vehicle(
    vehicle_id: uuid.UUID,
    payload: ReportDanyRequest,
    request: Request,
    db: AsyncSession = Depends(get_db_with_tenant_context)
):
    empresa_id = request.state.empresa_id
    
    nova_incidencia = Incidencia(
        empresa_id=uuid.UUID(empresa_id),
        vehicle_id=vehicle_id,
        text_observacions=payload.descripcio,
        estat='VERMELL',
        ambit="VEHICLE"
    )
    db.add(nova_incidencia)
    await db.commit()
    
    return {"status": "OK", "incidencia_id": str(nova_incidencia.id)}


class CheckinVehicleRequest(BaseModel):
    odometre_inicial: int
    foto_odometre_id: str | None = None
    nivell_combustible: str | None = None

@router.post("/{vehicle_id}/checkin", status_code=status.HTTP_201_CREATED)
async def vehicle_checkin(
    vehicle_id: uuid.UUID,
    payload: CheckinVehicleRequest,
    request: Request,
    db: AsyncSession = Depends(get_db_with_tenant_context)
):
    empresa_id = request.state.empresa_id
    vehicle = (await db.execute(select(Vehicle).where(Vehicle.id == vehicle_id, Vehicle.empresa_id == uuid.UUID(empresa_id)))).scalars().first()
    if not vehicle:
        raise HTTPException(status_code=404)
        
    # En un sistema real, guardaríem l'estat del Checkin (potser en una taula JornadaVehicle)
    # Per ara, l'assignem al vehicle l'odòmetre per a validació de Check-out
    vehicle.odometre_acumulat = payload.odometre_inicial
    await db.commit()
    
    # Store checkin kms in cache or state to calculate diff at checkout
    # We'll just rely on vehicle.odometre_acumulat being updated
    
    return {"estat": "CHECKIN_OK", "odometre": vehicle.odometre_acumulat}


class RepostatgeRequest(BaseModel):
    litres: float
    euros: float
    odometre: int

@router.post("/{vehicle_id}/repostatge", status_code=status.HTTP_201_CREATED)
async def vehicle_repostatge(
    vehicle_id: uuid.UUID,
    payload: RepostatgeRequest,
    request: Request,
    db: AsyncSession = Depends(get_db_with_tenant_context)
):
    empresa_id = request.state.empresa_id
    vehicle = (await db.execute(select(Vehicle).where(Vehicle.id == vehicle_id, Vehicle.empresa_id == uuid.UUID(empresa_id)))).scalars().first()
    if not vehicle:
        raise HTTPException(status_code=404)
        
    return {"estat": "REPOSTATGE_OK", "consum_litres": payload.litres}


class CheckoutVehicleRequest(BaseModel):
    odometre_final: int
    foto_odometre_id: str | None = None
    nivell_combustible: str | None = None

@router.post("/{vehicle_id}/checkout", status_code=status.HTTP_200_OK)
async def vehicle_checkout(
    vehicle_id: uuid.UUID,
    payload: CheckoutVehicleRequest,
    request: Request,
    db: AsyncSession = Depends(get_db_with_tenant_context)
):
    empresa_id = request.state.empresa_id
    vehicle = (await db.execute(select(Vehicle).where(Vehicle.id == vehicle_id, Vehicle.empresa_id == uuid.UUID(empresa_id)))).scalars().first()
    if not vehicle:
        raise HTTPException(status_code=404)
        
    km_recorreguts = payload.odometre_final - (vehicle.odometre_acumulat or 0)
    
    vehicle.odometre_acumulat = payload.odometre_final
    await db.commit()
    
    return {"estat": "CHECKOUT_OK", "km_recorreguts": km_recorreguts}
