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

