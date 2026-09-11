import uuid
import bcrypt
from datetime import datetime, timedelta, timezone
import jwt
from fastapi import APIRouter, Depends, HTTPException, Request, status
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel, Field

from app.core.db import get_db, set_tenant_context
from app.core.config import settings
from app.models.models import Usuari
from app.api.v1.gestio.operaris import hash_pin

router = APIRouter(prefix="/operari_auth", tags=["Auth Operari PWA"])
limiter_login = Limiter(key_func=get_remote_address)

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

def verify_pin(plain_pin: str, hashed_pin: str) -> bool:
    try:
        return bcrypt.checkpw(plain_pin.encode('utf-8'), hashed_pin.encode('utf-8'))
    except Exception:
        return False

def create_access_token(subject: str, rol: str, empresa_id: str) -> str:
    expires_delta = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    expire = datetime.now(timezone.utc) + expires_delta
    to_encode = {
        "sub": subject,
        "rol": rol,
        "empresa_id": empresa_id,
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

    await set_tenant_context(db, empresa_id)

    # 1. Buscar l'usuari aplicant el filtre de tenant implícitament i explícitament
    stmt = select(Usuari).where(
        Usuari.empresa_id == uuid.UUID(empresa_id),
        Usuari.nif == login_data.nif,
        Usuari.rol == "OPERARI"
    )
    result = await db.execute(stmt)
    usuari = result.scalars().first()

    # Si no existeix, error opac (RF-23)
    if not usuari:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credencials invàlides"
        )

    # Si ja està bloquejat, ni tan sols comprovem el PIN (estalviem CPU)
    if usuari.pin_bloquejat:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="El compte ha estat bloquejat per seguretat. Contacta amb Secretaria."
        )

    # Verifiquem el PIN
    is_valid = verify_pin(login_data.pin, usuari.pin_hash) if usuari.pin_hash else False

    if not is_valid:
        # Incrementem comptador
        usuari.intents_pin_fallits += 1
        if usuari.intents_pin_fallits >= 4:
            usuari.pin_bloquejat = True
            await db.commit()
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="S'ha excedit el límit d'intents. El compte ha estat bloquejat per seguretat."
            )
        await db.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credencials invàlides"
        )

    # PIN correcte
    usuari.intents_pin_fallits = 0
    await db.commit()

    token = create_access_token(
        subject=str(usuari.id),
        rol=usuari.rol,
        empresa_id=str(usuari.empresa_id)
    )

    return TokenResponse(
        access_token=token,
        usuari=UsuariTokenResponse(
            id=usuari.id,
            nom=usuari.nom,
            rol=usuari.rol
        )
    )
