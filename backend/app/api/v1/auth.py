import logging
import uuid
import bcrypt
import jwt
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, EmailStr
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from slowapi import Limiter
from slowapi.util import get_remote_address
import os

from app.core.config import settings
from app.core.db import get_db, set_tenant_context
from app.models.models import Usuari

logger = logging.getLogger(__name__)

router = APIRouter()
limiter_login = Limiter(key_func=get_remote_address, enabled=os.getenv("TESTING") != "1")

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    rol: str
    nom: str

def verify_password(plain_password: str, hashed_password: str) -> bool:
    if not hashed_password:
        return False
    try:
        return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password.encode('utf-8'))
    except Exception:
        return False

@router.post("/login", response_model=TokenResponse)
@limiter_login.limit("5/minute")
async def login_oficina(
    request: Request,
    login_data: LoginRequest,
    db: AsyncSession = Depends(get_db)
):
    try:
        # We don't have tenant context yet, we search by email
        stmt = select(Usuari).where(
            func.lower(Usuari.email) == login_data.email.lower()
        )
        result = await db.execute(stmt)
        usuari = result.scalars().first()

        if not usuari:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Credencials invàlides",
            )

        if not verify_password(login_data.password, usuari.password_hash):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Credencials invàlides",
            )
            
        if usuari.rol.upper() == "OPERARI":
             raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Els operaris han d'accedir per la PWA amb PIN",
            )

        # Generar JWT
        expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        payload = {
            "sub": str(usuari.id),
            "empresa_id": str(usuari.empresa_id) if usuari.empresa_id else "",
            "rol": usuari.rol.upper(),
            "exp": expire,
            "iat": datetime.now(timezone.utc),
        }
        token = jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)

        return TokenResponse(
            access_token=token,
            rol=usuari.rol.upper(),
            nom=usuari.nom
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error intern durant login d'oficina: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error intern del servidor"
        )
