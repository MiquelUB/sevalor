import uuid
from typing import List, Optional
from datetime import date
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_
from pydantic import BaseModel, Field

from app.core.db import get_db_with_tenant_context
from app.core.security import require_roles
from app.models.models import OrdreTreball

router = APIRouter(
    prefix="/gestio/feines",
    tags=["Gestió Feines i Mapa"],
    dependencies=[Depends(require_roles(["BOSS", "SECRETARIA", "ENGINYER"]))],
)

class FeinaCreate(BaseModel):
    codi: str = Field(..., max_length=20)
    client_id: uuid.UUID
    finca_id: Optional[uuid.UUID] = None
    titol: str = Field(..., max_length=200)
    adreca: str = Field(..., max_length=255)
    descripcio: Optional[str] = None
    estat: str = Field("PENDENT", max_length=30)
    data_planificacio: date
    cap_de_colla_id: uuid.UUID
    vehicle_id: Optional[uuid.UUID] = None

class FeinaResponse(FeinaCreate):
    id: uuid.UUID

@router.get("", response_model=List[FeinaResponse])
async def llistar_feines(
    request: Request,
    q: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    db: AsyncSession = Depends(get_db_with_tenant_context)
):
    empresa_id = request.state.empresa_id
    if not empresa_id:
        raise HTTPException(status_code=401, detail="No identificat")
        
    stmt = select(OrdreTreball).where(OrdreTreball.empresa_id == uuid.UUID(empresa_id))
    
    if q:
        search_term = f"%{q}%"
        stmt = stmt.where(
            or_(
                OrdreTreball.codi.ilike(search_term),
                OrdreTreball.titol.ilike(search_term)
            )
        )
        
    stmt = stmt.limit(limit).offset(offset).order_by(OrdreTreball.created_at.desc())
    
    result = await db.execute(stmt)
    feines = result.scalars().all()
    
    return feines

@router.post("", response_model=FeinaResponse, status_code=status.HTTP_201_CREATED)
async def alta_feina(
    request: Request,
    feina: FeinaCreate,
    db: AsyncSession = Depends(get_db_with_tenant_context)
):
    empresa_id = request.state.empresa_id
    if not empresa_id:
        raise HTTPException(status_code=401, detail="No identificat")
        
    stmt_codi = select(OrdreTreball).where(
        OrdreTreball.empresa_id == uuid.UUID(empresa_id),
        OrdreTreball.codi == feina.codi
    )
    result_codi = await db.execute(stmt_codi)
    if result_codi.scalars().first():
        raise HTTPException(status_code=400, detail="El codi de feina ja es troba registrat")

    nova_feina = OrdreTreball(
        empresa_id=uuid.UUID(empresa_id),
        codi=feina.codi,
        client_id=feina.client_id,
        finca_id=feina.finca_id,
        titol=feina.titol,
        adreca=feina.adreca,
        descripcio=feina.descripcio,
        estat=feina.estat,
        data_planificacio=feina.data_planificacio,
        cap_de_colla_id=feina.cap_de_colla_id,
        vehicle_id=feina.vehicle_id
    )
    
    db.add(nova_feina)
    await db.commit()

    return nova_feina
