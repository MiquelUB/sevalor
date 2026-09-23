import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db_with_tenant_context
from app.core.security import require_roles
from app.models.models import FullaPicking, LiniaPicking, OrdreTreball

router = APIRouter(
    prefix="/operari/picking",
    tags=["Operari Picking"],
    dependencies=[Depends(require_roles(["OPERARI", "CAPATAZ", "CAP_DE_COLLA", "BOSS"]))],
)

class FullaPickingCreate(BaseModel):
    ordre_treball_id: uuid.UUID
    vehicle_id: Optional[uuid.UUID] = None

class FullaPickingResponse(BaseModel):
    id: uuid.UUID
    ordre_treball_id: uuid.UUID
    vehicle_id: Optional[uuid.UUID] = None
    estat_picking: str

class LiniaPickingCreate(BaseModel):
    article_id: uuid.UUID
    quantitat_prevista: float = Field(..., gt=0)

class LiniaPickingResponse(BaseModel):
    id: uuid.UUID
    article_id: uuid.UUID
    quantitat_prevista: float
    quantitat_carregada_pick_in: float
    quantitat_retornada_pick_out: float
    quantitat_mermada: float

@router.post("", response_model=FullaPickingResponse, status_code=status.HTTP_201_CREATED)
async def crear_fulla_picking_operari(
    request: Request,
    payload: FullaPickingCreate,
    db: AsyncSession = Depends(get_db_with_tenant_context)
):
    empresa_id = request.state.empresa_id
    if not empresa_id:
        raise HTTPException(status_code=401, detail="Context d'empresa no trobat")

    ot_res = await db.execute(select(OrdreTreball).where(
        OrdreTreball.id == payload.ordre_treball_id,
        OrdreTreball.empresa_id == uuid.UUID(empresa_id)
    ))
    if not ot_res.scalars().first():
        raise HTTPException(status_code=404, detail="Ordre de treball no trobada")

    fulla = FullaPicking(
        empresa_id=uuid.UUID(empresa_id),
        ordre_treball_id=payload.ordre_treball_id,
        vehicle_id=payload.vehicle_id,
        estat_picking="PENDENT"
    )
    db.add(fulla)
    await db.commit()
    await db.refresh(fulla)

    return FullaPickingResponse(
        id=fulla.id,
        ordre_treball_id=fulla.ordre_treball_id,
        vehicle_id=fulla.vehicle_id,
        estat_picking=fulla.estat_picking
    )

@router.post("/{picking_id}/linies", response_model=LiniaPickingResponse, status_code=status.HTTP_201_CREATED)
async def afegir_linia_picking_operari(
    request: Request,
    picking_id: uuid.UUID,
    payload: LiniaPickingCreate,
    db: AsyncSession = Depends(get_db_with_tenant_context)
):
    empresa_id = request.state.empresa_id
    if not empresa_id:
        raise HTTPException(status_code=401, detail="Context d'empresa no trobat")

    fulla_res = await db.execute(select(FullaPicking).where(
        FullaPicking.id == picking_id,
        FullaPicking.empresa_id == uuid.UUID(empresa_id)
    ))
    fulla = fulla_res.scalars().first()
    if not fulla:
        raise HTTPException(status_code=404, detail="Fulla de picking no trobada")

    linia = LiniaPicking(
        empresa_id=uuid.UUID(empresa_id),
        picking_id=picking_id,
        article_id=payload.article_id,
        quantitat_prevista=payload.quantitat_prevista,
        quantitat_carregada_pick_in=0.0,
        quantitat_retornada_pick_out=0.0,
        quantitat_mermada=0.0
    )
    db.add(linia)
    await db.commit()
    await db.refresh(linia)

    return LiniaPickingResponse(
        id=linia.id,
        article_id=linia.article_id,
        quantitat_prevista=float(linia.quantitat_prevista),
        quantitat_carregada_pick_in=float(linia.quantitat_carregada_pick_in),
        quantitat_retornada_pick_out=float(linia.quantitat_retornada_pick_out),
        quantitat_mermada=float(linia.quantitat_mermada)
    )

class UpdateLiniaPickingRequest(BaseModel):
    quantitat_carregada_pick_in: Optional[float] = None
    quantitat_retornada_pick_out: Optional[float] = None
    quantitat_mermada: Optional[float] = None

class BalancLiniaResponse(BaseModel):
    id: uuid.UUID
    article_id: uuid.UUID
    quantitat_prevista: float
    quantitat_carregada_pick_in: float
    quantitat_retornada_pick_out: float
    quantitat_mermada: float
    consum_real: float  # Spec 013 RF-18: Consum Real = Pick In - Pick Out

@router.put("/linies/{linia_id}", response_model=BalancLiniaResponse)
async def actualitzar_linia_picking_operari(
    request: Request,
    linia_id: uuid.UUID,
    payload: UpdateLiniaPickingRequest,
    db: AsyncSession = Depends(get_db_with_tenant_context)
):
    empresa_id = request.state.empresa_id
    if not empresa_id:
        raise HTTPException(status_code=401, detail="Context d'empresa no trobat")

    linia_res = await db.execute(select(LiniaPicking).where(
        LiniaPicking.id == linia_id,
        LiniaPicking.empresa_id == uuid.UUID(empresa_id)
    ))
    linia = linia_res.scalars().first()
    if not linia:
        raise HTTPException(status_code=404, detail="Línia de picking no trobada")

    if payload.quantitat_carregada_pick_in is not None:
        linia.quantitat_carregada_pick_in = payload.quantitat_carregada_pick_in
    if payload.quantitat_retornada_pick_out is not None:
        linia.quantitat_retornada_pick_out = payload.quantitat_retornada_pick_out
    if payload.quantitat_mermada is not None:
        linia.quantitat_mermada = payload.quantitat_mermada

    await db.commit()
    await db.refresh(linia)

    pick_in = float(linia.quantitat_carregada_pick_in or 0.0)
    pick_out = float(linia.quantitat_retornada_pick_out or 0.0)
    consum_real = max(0.0, pick_in - pick_out)

    return BalancLiniaResponse(
        id=linia.id,
        article_id=linia.article_id,
        quantitat_prevista=float(linia.quantitat_prevista),
        quantitat_carregada_pick_in=pick_in,
        quantitat_retornada_pick_out=pick_out,
        quantitat_mermada=float(linia.quantitat_mermada or 0.0),
        consum_real=consum_real
    )
