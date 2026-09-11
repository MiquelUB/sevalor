import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel, Field

from app.core.db import get_db_with_tenant_context
from app.core.security import require_roles
from app.models.models import FullaPicking, LiniaPicking, OrdreTreball, Article

router = APIRouter(
    prefix="/operari",
    tags=["Operari Picking"],
    dependencies=[Depends(require_roles(["OPERARI", "CAPATAZ"]))],
)

class LiniaPickingUpdate(BaseModel):
    quantitat_carregada_pick_in: float

class LiniaPickingResponse(BaseModel):
    id: uuid.UUID
    quantitat_carregada_pick_in: float

@router.put("/picking/linies/{linia_id}", response_model=LiniaPickingResponse)
async def actualitzar_linia_picking(
    linia_id: uuid.UUID,
    request: Request,
    payload: LiniaPickingUpdate,
    db: AsyncSession = Depends(get_db_with_tenant_context)
):
    empresa_id = request.state.empresa_id
    if not empresa_id:
        raise HTTPException(status_code=401)
        

    stmt = select(LiniaPicking).where(LiniaPicking.id == linia_id, LiniaPicking.empresa_id == uuid.UUID(empresa_id))
    result = await db.execute(stmt)
    linia = result.scalars().first()
    
    if not linia:
        raise HTTPException(status_code=404, detail="Línia no trobada")

    linia.quantitat_carregada_pick_in = payload.quantitat_carregada_pick_in
    await db.commit()

    return LiniaPickingResponse(
        id=linia.id,
        quantitat_carregada_pick_in=linia.quantitat_carregada_pick_in
    )
