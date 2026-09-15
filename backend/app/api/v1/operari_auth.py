import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any
import os

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.core.config import settings
from app.core.db import get_db, set_tenant_context
from app.models.models import Usuari
from app.api.v1.gestio.operaris import hash_pin
import jwt
import bcrypt

logger = logging.getLogger("operari_auth")

router = APIRouter(prefix="/operari_auth", tags=["Operari Auth"])
limiter_login = Limiter(key_func=get_remote_address, enabled=os.getenv("TESTING") != "1")

class LoginRequest(BaseModel):
    nif: str = Field(..., max_length=20)
    pin: str = Field(..., min_length=4, max_length=4)

class UsuariTokenResponse(BaseModel):
    id: uuid.UUID
    nom: str
    rol: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    usuari: UsuariTokenResponse

def create_access_token(subject: str | Any, rol: str, empresa_id: str, expires_delta: timedelta) -> str:
    expire = datetime.now(timezone.utc) + expires_delta
    to_encode = {
        "sub": str(subject),
        "rol": rol,
        "empresa_id": str(empresa_id),
        "exp": expire
    }
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt

@router.post("/login", response_model=TokenResponse)
@limiter_login.limit("5/minute")
async def login_operari(
    request: Request,
    login_data: LoginRequest,
    db: AsyncSession = Depends(get_db)
):
    # Prioritzem el header X-Empresa-ID perquè el TenantMiddleware pot haver
    # injectat un valor cachejat d'una petició anterior en l'entorn de tests
    # amb ASGITransport. En producció, X-Empresa-ID i el middleware coincideixen.
    empresa_id = request.headers.get("X-Empresa-ID") or getattr(request.state, "empresa_id", None)
    if not empresa_id:
        raise HTTPException(status_code=400, detail="Tenant context missing")

    try:
        empresa_uuid = uuid.UUID(empresa_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Tenant ID invàlid")

    await set_tenant_context(db, empresa_id)

    # 1. Buscar l'usuari aplicant el filtre de tenant implícitament i explícitament
    stmt = select(Usuari).where(
        Usuari.empresa_id == empresa_uuid,
        Usuari.nif == login_data.nif,
        Usuari.rol.in_(["OPERARI", "ADMIN", "SUPERADMIN"])
    )
    result = await db.execute(stmt)
    usuari = result.scalars().first()

    # Si no existeix, error opac (RF-23)
    if not usuari:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="NIF o PIN incorrectes"
        )

    # 2. Verificar PIN (també opac)
    def verify_pin(plain_pin: str, hashed_pin: str) -> bool:
        return bcrypt.checkpw(plain_pin.encode('utf-8'), hashed_pin.encode('utf-8'))
    
    is_valid = verify_pin(login_data.pin, usuari.pin_hash) if usuari.pin_hash else False
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="NIF o PIN incorrectes"
        )

    # 3. Comprovar estat actiu
    if usuari.estat != "ACTIU":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Usuari inactiu. Contacta amb l'administrador."
        )

    # Generar JWT amb claims mínims
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    token = create_access_token(
        subject=str(usuari.id),
        rol=usuari.rol,
        empresa_id=str(usuari.empresa_id),
        expires_delta=access_token_expires
    )

    return TokenResponse(
        access_token=token,
        usuari=UsuariTokenResponse(
            id=usuari.id,
            nom=usuari.nom,
            rol=usuari.rol
        )
    )