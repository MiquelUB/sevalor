import uuid
from typing import Optional
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel, Field

from app.core.db import get_db_with_tenant_context
from app.core.security import require_roles
from app.models.models import RegistreJornadaLaboral

router = APIRouter(
    prefix="/operari",
    tags=["Operari Jornada"],
    dependencies=[Depends(require_roles(["OPERARI", "CAPATAZ"]))],
)

class JornadaInici(BaseModel):
    geolocalitzacio: Optional[str] = None

class JornadaResponse(BaseModel):
    id: uuid.UUID
    estat: str
    geolocalitzacio_inici: Optional[str]

@router.post("/inici", response_model=JornadaResponse, status_code=status.HTTP_201_CREATED)
async def iniciar_jornada(
    request: Request,
    payload: JornadaInici,
    db: AsyncSession = Depends(get_db_with_tenant_context)
):
    empresa_id = request.state.empresa_id
    if not empresa_id:
        raise HTTPException(status_code=401, detail="No identificat")
        
    # L'usuari ha de ser extret del token JWT (el Subject)
    import jwt
    from app.core.config import settings
    auth_header = request.headers.get("Authorization")
    token = auth_header.split(" ")[1]
    decoded = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM], options={"verify_aud": False})
    usuari_id = decoded.get("sub")


    # Validar si ja té una jornada en curs
    stmt = select(RegistreJornadaLaboral).where(
        RegistreJornadaLaboral.empresa_id == uuid.UUID(empresa_id),
        RegistreJornadaLaboral.usuari_id == uuid.UUID(usuari_id),
        RegistreJornadaLaboral.estat == "EN_CURS"
    )
    result = await db.execute(stmt)
    if result.scalars().first():
        raise HTTPException(status_code=400, detail="Ja hi ha una jornada en curs")

    jornada = RegistreJornadaLaboral(
        empresa_id=uuid.UUID(empresa_id),
        usuari_id=uuid.UUID(usuari_id),
        geolocalitzacio_inici=payload.geolocalitzacio,
        estat="EN_CURS"
    )
    
    db.add(jornada)
    await db.commit()

    return jornada

@router.get("/activa", response_model=JornadaResponse)
async def get_jornada_activa(
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


    stmt = select(RegistreJornadaLaboral).where(
        RegistreJornadaLaboral.empresa_id == uuid.UUID(empresa_id),
        RegistreJornadaLaboral.usuari_id == uuid.UUID(usuari_id),
        RegistreJornadaLaboral.estat == "EN_CURS"
    )
    result = await db.execute(stmt)
    jornada = result.scalars().first()
    
    if not jornada:
        raise HTTPException(status_code=404, detail="No hi ha jornada activa")
        
    return jornada

@router.post("/{jornada_id}/fi", response_model=JornadaResponse)
async def finalitzar_jornada(
    jornada_id: uuid.UUID,
    request: Request,
    payload: JornadaInici,
    db: AsyncSession = Depends(get_db_with_tenant_context)
):
    empresa_id = request.state.empresa_id
    if not empresa_id:
        raise HTTPException(status_code=401)
        

    stmt = select(RegistreJornadaLaboral).where(
        RegistreJornadaLaboral.id == jornada_id,
        RegistreJornadaLaboral.empresa_id == uuid.UUID(empresa_id)
    )
    result = await db.execute(stmt)
    jornada = result.scalars().first()
    
    if not jornada:
        raise HTTPException(status_code=404, detail="Jornada no trobada")
        
    if jornada.estat == "COMPLERT":
        raise HTTPException(status_code=400, detail="La jornada ja està tancada")
        
    jornada.hora_fi = datetime.now(timezone.utc)
    jornada.geolocalitzacio_fi = payload.geolocalitzacio
    jornada.estat = "COMPLERT"
    
    await db.commit()

    return jornada
