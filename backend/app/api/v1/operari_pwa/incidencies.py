import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel, Field

from app.core.db import get_db_with_tenant_context
from app.core.security import require_roles
from app.models.models import Incidencia

router = APIRouter(
    prefix="/operari",
    tags=["Operari Incidències"],
    dependencies=[Depends(require_roles(["OPERARI", "CAPATAZ", "CAP_DE_COLLA"]))],
)

class IncidenciaCreate(BaseModel):
    ordre_treball_id: Optional[uuid.UUID] = None
    vehicle_id: Optional[uuid.UUID] = None
    ambit: str = Field("TASCA", max_length=30)
    estat: str = Field("VERMELL", max_length=20)
    audio_path: Optional[str] = None
    foto_path: Optional[str] = None
    text_observacions: Optional[str] = None

class IncidenciaResponse(IncidenciaCreate):
    id: uuid.UUID
    operari_id: Optional[uuid.UUID]

@router.get("/incidencies", response_model=List[IncidenciaResponse])
async def llistar_incidencies_operari(
    request: Request,
    db: AsyncSession = Depends(get_db_with_tenant_context)
):
    empresa_id = request.state.empresa_id
    if not empresa_id:
        raise HTTPException(status_code=401)
        
    auth_header = request.headers.get("Authorization")
    token = auth_header.split(" ")[1]
    import jwt
    from app.core.config import settings
    decoded = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM], options={"verify_aud": False})
    usuari_id = decoded.get("sub")


    stmt = select(Incidencia).where(
        Incidencia.empresa_id == uuid.UUID(empresa_id),
        Incidencia.operari_id == uuid.UUID(usuari_id)
    ).order_by(Incidencia.created_at.desc())
    
    result = await db.execute(stmt)
    return result.scalars().all()

@router.post("/incidencies", response_model=IncidenciaResponse, status_code=status.HTTP_201_CREATED)
async def reportar_incidencia(
    request: Request,
    payload: IncidenciaCreate,
    db: AsyncSession = Depends(get_db_with_tenant_context)
):
    empresa_id = request.state.empresa_id
    if not empresa_id:
        raise HTTPException(status_code=401)
        
    auth_header = request.headers.get("Authorization")
    token = auth_header.split(" ")[1]
    import jwt
    from app.core.config import settings
    decoded = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM], options={"verify_aud": False})
    usuari_id = decoded.get("sub")


    nova_inci = Incidencia(
        empresa_id=uuid.UUID(empresa_id),
        ordre_treball_id=payload.ordre_treball_id,
        vehicle_id=payload.vehicle_id,
        operari_id=uuid.UUID(usuari_id),
        ambit=payload.ambit,
        estat=payload.estat,
        audio_path=payload.audio_path,
        foto_path=payload.foto_path,
        text_observacions=payload.text_observacions
    )
    
    db.add(nova_inci)
    await db.commit()

    return nova_inci
