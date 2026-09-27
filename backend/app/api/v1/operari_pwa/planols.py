import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db_with_tenant_context
from app.core.security import require_roles
from app.models.models import PlanolBase, CapaVectorial

router = APIRouter(
    prefix="/operari/planols",
    tags=["Operari PWA Planols"],
    dependencies=[Depends(require_roles(["OPERARI", "CAPATAZ", "CAP_DE_COLLA", "BOSS", "SUPERADMIN"]))],
)

class CapaVectorialCreate(BaseModel):
    nom: str
    es_tancada: bool = False
    visible: bool = True
    dades_geojson: dict

class CapaVectorialResponse(BaseModel):
    id: uuid.UUID
    nom: str
    es_tancada: bool
    dades_geojson: dict

@router.post("/{planol_id}/capes", response_model=CapaVectorialResponse, status_code=status.HTTP_201_CREATED)
async def crear_capa_operari(
    planol_id: uuid.UUID,
    payload: CapaVectorialCreate,
    request: Request,
    db: AsyncSession = Depends(get_db_with_tenant_context)
):
    """Operari crea una capa sobre un plànol (Spec 017 RF-13.1)."""
    empresa_id = request.state.empresa_id
    
    planol_res = await db.execute(select(PlanolBase).where(
        PlanolBase.id == planol_id,
        PlanolBase.empresa_id == uuid.UUID(empresa_id)
    ))
    if not planol_res.scalars().first():
        raise HTTPException(status_code=404, detail="Plànol no trobat")
    
    nova_capa = CapaVectorial(
        empresa_id=uuid.UUID(empresa_id),
        planol_id=planol_id,
        nom=payload.nom,
        es_tancada=payload.es_tancada,
        dades_geojson=payload.dades_geojson
    )
    db.add(nova_capa)
    await db.commit()
    await db.refresh(nova_capa)
    
    return CapaVectorialResponse(
        id=nova_capa.id,
        nom=nova_capa.nom,
        es_tancada=nova_capa.es_tancada,
        dades_geojson=nova_capa.dades_geojson
    )
