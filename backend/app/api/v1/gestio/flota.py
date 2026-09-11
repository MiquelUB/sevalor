import uuid
from typing import List, Optional
from datetime import date
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_
from pydantic import BaseModel, Field

from app.core.db import get_db_with_tenant_context
from app.core.security import require_roles
from app.models.models import Vehicle

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

class VehicleResponse(VehicleCreate):
    id: uuid.UUID
    horometre_acumulat: float
    odometre_acumulat: int

@router.get("", response_model=List[VehicleResponse])
async def llistar_flota(
    request: Request,
    q: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    db: AsyncSession = Depends(get_db_with_tenant_context)
):
    empresa_id = request.state.empresa_id
    if not empresa_id:
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
    if not empresa_id:
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
        data_proxima_itv=vehicle.data_proxima_itv
    )
    
    db.add(nou_vehicle)
    await db.commit()

    return nou_vehicle
