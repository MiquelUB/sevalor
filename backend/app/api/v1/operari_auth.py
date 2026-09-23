import logging
import os
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

import bcrypt
import jwt
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.db import get_db, set_tenant_context
from app.models.models import Empresa, Usuari

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
    empresa_id = request.headers.get("X-Empresa-ID") or getattr(request.state, "empresa_id", None)
    empresa_uuid = None

    if empresa_id:
        try:
            empresa_uuid = uuid.UUID(empresa_id)
        except ValueError:
            res_sub = await db.execute(select(Empresa).where(Empresa.subdomini == empresa_id))
            emp = res_sub.scalars().first()
            if emp:
                empresa_uuid = emp.id

    if not empresa_uuid:
        # Fallback de conveniència per a la PWA quan s'accedeix sense subdomini/header
        stmt_nif = select(Usuari).where(
            func.upper(Usuari.nif) == login_data.nif.upper(),
            Usuari.rol.in_(["OPERARI", "CAP_DE_COLLA", "ADMIN", "SUPERADMIN"])
        )
        res_nif = await db.execute(stmt_nif)
        usuari_pre = res_nif.scalars().first()
        if usuari_pre:
            empresa_uuid = usuari_pre.empresa_id

    if not empresa_uuid:
        raise HTTPException(status_code=400, detail="Tenant context missing")

    await set_tenant_context(db, str(empresa_uuid))


    # 1. Buscar l'usuari aplicant el filtre de tenant implícitament i explícitament
    stmt = select(Usuari).where(
        Usuari.empresa_id == empresa_uuid,
        func.upper(Usuari.nif) == login_data.nif.upper(),
        Usuari.rol.in_(["OPERARI", "CAP_DE_COLLA", "ADMIN", "SUPERADMIN"])
    )

    result = await db.execute(stmt)
    usuari = result.scalars().first()

    # Si no existeix, error opac (RF-23)
    if not usuari:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credencials invàlides"
        )

    # 2. Comprovar si el compte ja està bloquejat per intents fallits
    if usuari.pin_bloquejat or (usuari.intents_pin_fallits is not None and usuari.intents_pin_fallits >= 4):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="El compte ha estat bloquejat per massa intents fallits. Contacteu amb el supervisor."
        )

    # 3. Comprovar estat actiu
    if usuari.estat != "ACTIU":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Usuari inactiu. Contacta amb l'administrador."
        )

    # 4. Verificar PIN (amb bcrypt)
    def verify_pin(plain_pin: str, hashed_pin: str) -> bool:
        if not hashed_pin:
            return False
        try:
            return bcrypt.checkpw(plain_pin.encode('utf-8'), hashed_pin.encode('utf-8'))
        except Exception:
            return False

    is_valid = verify_pin(login_data.pin, usuari.pin_hash) if usuari.pin_hash else False

    if not is_valid:
        usuari.intents_pin_fallits = (usuari.intents_pin_fallits or 0) + 1
        if usuari.intents_pin_fallits >= 4:
            usuari.pin_bloquejat = True
            await db.commit()
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="El compte ha estat bloquejat per massa intents fallits. Contacteu amb el supervisor."
            )
        await db.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credencials invàlides"
        )

    # 5. Login correcte: reiniciar comptador d'intents i bloqueig
    usuari.intents_pin_fallits = 0
    usuari.pin_bloquejat = False
    await db.commit()

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
