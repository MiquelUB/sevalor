import logging
import os
import uuid
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, EmailStr, Field
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy import func, or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.db import get_db
from app.core.security import get_current_user_claims
from app.models.models import Empresa, Usuari

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
        return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))
    except Exception:
        return False


@router.post("/login", response_model=TokenResponse)
@limiter_login.limit("5/minute")
async def login_oficina(
    request: Request, login_data: LoginRequest, db: AsyncSession = Depends(get_db)
):
    try:
        # Guardem el rol actual per no trencar les transaccions de test
        res_role = await db.execute(text("SELECT current_user;"))
        current_role = res_role.scalar()

        await db.execute(text("RESET ROLE;"))
        try:
            stmt = select(Usuari).where(func.lower(Usuari.email) == login_data.email.lower())
            result = await db.execute(stmt)
            usuaris = result.scalars().all()
        finally:
            if current_role:
                await db.execute(text(f'SET ROLE "{current_role}";'))

        if len(usuaris) > 1:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Error de consistència: L'email està duplicat a diferents empreses. L'accés ha estat bloquejat per seguretat.",
            )

        usuari = usuaris[0] if usuaris else None

        if not usuari:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Credencials invàlides",
            )

        if not verify_password(login_data.password, usuari.password_hash):  # type: ignore
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Credencials invàlides",
            )

        if usuari.rol.upper() == "OPERARI":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Els operaris han d'accedir per la PWA amb PIN",
            )

        # Blindatge de domini per rol (Zero-Trust Domain Gate)
        raw_host = request.headers.get("x-forwarded-host") or request.headers.get("host") or ""
        clean_host = (
            raw_host.strip()
            .lower()
            .replace("https://", "")
            .replace("http://", "")
            .split("/")[0]
            .split(":")[0]
        )
        is_local = clean_host in ("localhost", "127.0.0.1", "testserver", "test", "")

        if usuari.rol.upper() == "SUPERADMIN":
            admin_host = (settings.PLATFORM_ADMIN_HOST or "").strip().lower()
            if not is_local and admin_host and clean_host != admin_host:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="L'accés com a SUPERADMIN només està permès des del domini oficial d'administració.",
                )
        elif usuari.empresa_id and not is_local:
            # Validar que l'usuari d'oficina inicia sessió al domini de la seva pròpia empresa
            parts = clean_host.split(".")
            subdomini_cand = parts[0] if len(parts) >= 3 else None
            conds = [func.lower(Empresa.domini_custom) == clean_host]
            if subdomini_cand and subdomini_cand not in ("www", "api", "app", "localhost", "sevalor", "superadmin"):
                conds.append(func.lower(Empresa.subdomini) == subdomini_cand)

            res_h = await db.execute(select(Empresa.id).where(or_(*conds)))
            emp_id_found = res_h.scalar()
            if emp_id_found and str(emp_id_found) != str(usuari.empresa_id):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Aquest usuari no pertany a l'empresa associada a aquest subdomini.",
                )

        if usuari.rol.upper() != "SUPERADMIN" and usuari.empresa_id:
            await db.execute(text("RESET ROLE;"))
            try:
                emp_res = await db.execute(select(Empresa).where(Empresa.id == usuari.empresa_id))
                emp = emp_res.scalars().first()
            finally:
                if current_role:
                    await db.execute(text(f'SET ROLE "{current_role}";'))

            if emp and emp.estat_pagament in {
                "HIBERNANT",
                "SUSPES_PAGAMENT",
                "SUSPES",
                "BAIXA_OFFBOARDING",
                "ELIMINAT",
            }:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=(
                        f"El compte de l'empresa es troba en estat '{emp.estat_pagament}'. "
                        "Contacteu amb l'administració de Sevalor per regularitzar el servei."
                    ),
                )

        # Generar JWT
        expire = datetime.now(timezone.utc) + timedelta(
            minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
        )
        payload = {
            "sub": str(usuari.id),
            "empresa_id": str(usuari.empresa_id) if usuari.empresa_id else "",
            "rol": usuari.rol.upper(),
            "exp": expire,
            "iat": datetime.now(timezone.utc),
        }

        if usuari.rol.upper() == "SUPERADMIN":
            payload["totp_activat"] = usuari.totp_activat
            payload["ip_allowlist"] = usuari.ip_allowlist or []

        token = jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)

        return TokenResponse(access_token=token, rol=usuari.rol.upper(), nom=usuari.nom)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error intern durant login d'oficina: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error intern del servidor"
        )


class UserMeResponse(BaseModel):
    id: str
    empresa_id: str | None = None
    rol: str
    nom: str | None = None
    email: str | None = None
    is_impersonation: bool = False
    feature_copilot_ia: bool = True


@router.get("/me", response_model=UserMeResponse)
async def get_me(
    claims: dict = Depends(get_current_user_claims), db: AsyncSession = Depends(get_db)
):
    usuari_id = claims.get("sub")
    try:
        user_uuid = uuid.UUID(usuari_id)
    except Exception:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token invàlid")

    is_impersonation = bool(claims.get("is_impersonation", False))

    stmt = select(Usuari).where(Usuari.id == user_uuid)
    result = await db.execute(stmt)
    usuari = result.scalars().first()

    emp_id = claims.get("empresa_id") or (str(usuari.empresa_id) if usuari and usuari.empresa_id else None)
    has_copilot = True
    if emp_id:
        try:
            emp_uuid = uuid.UUID(emp_id)
            emp_res = await db.execute(select(Empresa.feature_copilot_ia).where(Empresa.id == emp_uuid))
            f_val = emp_res.scalar()
            if f_val is not None:
                has_copilot = bool(f_val)
        except Exception:
            pass

    if not usuari:
        return UserMeResponse(
            id=str(user_uuid),
            empresa_id=claims.get("empresa_id"),
            rol=claims.get("rol", "OPERARI").upper(),
            nom=claims.get("nom", "Usuari"),
            email=claims.get("email"),
            is_impersonation=is_impersonation,
            feature_copilot_ia=has_copilot,
        )

    return UserMeResponse(
        id=str(usuari.id),
        empresa_id=emp_id,
        rol=usuari.rol.upper(),
        nom=usuari.nom,
        email=usuari.email,
        is_impersonation=is_impersonation,
        feature_copilot_ia=has_copilot,
    )


class VerificarActivacioResponse(BaseModel):
    valid: bool
    usuari_id: str
    nom: str
    cognoms: str
    email: str
    empresa_id: str
    empresa_nom: str
    subdomini: str
    primari_hsl: str | None = None
    logotip_path: str | None = None


class CompletarActivacioRequest(BaseModel):
    token: str
    password: str
    password_confirm: str


@router.get("/activacio/verificar", response_model=VerificarActivacioResponse)
async def verificar_token_activacio(
    token: str,
    db: AsyncSession = Depends(get_db),
) -> VerificarActivacioResponse:
    """Verifica si el token d'activació de 24h per al gerent és vàlid."""
    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM],
            options={"verify_exp": True},
        )
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail="L'enllaç d'activació ha caducat (validesa màxima de 24 hores). Sol·liciteu un nou enllaç a l'administració de la plataforma.",
        )
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Token d'activació invàlid o malmès.",
        )

    if payload.get("action") != "activate":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Aquest token no correspon a una acció d'activació de compte.",
        )

    user_id_str = payload.get("sub")
    if not user_id_str:
        raise HTTPException(status_code=400, detail="Token sense identificador d'usuari.")

    try:
        user_uuid = uuid.UUID(str(user_id_str))
    except ValueError:
        raise HTTPException(status_code=400, detail="UUID d'usuari invàlid.")

    res_role = await db.execute(text("SELECT current_user;"))
    current_role = res_role.scalar()

    await db.execute(text("RESET ROLE;"))
    try:
        usuari_res = await db.execute(select(Usuari).where(Usuari.id == user_uuid))
        usuari = usuari_res.scalars().first()
        if not usuari:
            raise HTTPException(status_code=404, detail="Usuari no trobat.")

        emp_res = await db.execute(select(Empresa).where(Empresa.id == usuari.empresa_id))
        empresa = emp_res.scalars().first()
        if not empresa:
            raise HTTPException(status_code=404, detail="Empresa no trobada.")
    finally:
        if current_role:
            await db.execute(text(f'SET ROLE "{current_role}";'))

    return VerificarActivacioResponse(
        valid=True,
        usuari_id=str(usuari.id),
        nom=usuari.nom,
        cognoms=usuari.cognoms,
        email=usuari.email or "",
        empresa_id=str(empresa.id),
        empresa_nom=empresa.nom,
        subdomini=empresa.subdomini or "",
        primari_hsl=empresa.primari_hsl,
        logotip_path=empresa.logotip_path,
    )


@router.post("/activacio", response_model=dict[str, str])
async def completar_activacio(
    payload_in: CompletarActivacioRequest,
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    """Estableix la contrasenya del gerent i activa el seu compte des de l'enllaç d'onboarding (Spec 04 FR-004/005)."""
    if len(payload_in.password) < 8:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="La contrasenya ha de tenir com a mínim 8 caràcters.",
        )

    if payload_in.password != payload_in.password_confirm:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Les contrasenyes introduïdes no coincideixen.",
        )

    try:
        token_data = jwt.decode(
            payload_in.token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM],
            options={"verify_exp": True},
        )
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail="L'enllaç d'activació ha caducat (validesa màxima de 24 hores).",
        )
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Token d'activació invàlid.",
        )

    if token_data.get("action") != "activate":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Acció no autoritzada amb aquest token.",
        )

    try:
        user_uuid = uuid.UUID(str(token_data.get("sub")))
    except Exception:
        raise HTTPException(status_code=400, detail="UUID d'usuari invàlid.")

    res_role = await db.execute(text("SELECT current_user;"))
    current_role = res_role.scalar()

    await db.execute(text("RESET ROLE;"))
    try:
        usuari_res = await db.execute(select(Usuari).where(Usuari.id == user_uuid))
        usuari = usuari_res.scalars().first()
        if not usuari:
            raise HTTPException(status_code=404, detail="Usuari no trobat.")

        salt = bcrypt.gensalt(rounds=12)
        hashed = bcrypt.hashpw(payload_in.password.encode("utf-8"), salt).decode("utf-8")

        usuari.password_hash = hashed
        usuari.estat = "ACTIU"
        usuari.updated_at = datetime.now(timezone.utc)
        await db.commit()
    finally:
        if current_role:
            await db.execute(text(f'SET ROLE "{current_role}";'))

    return {
        "status": "ACTIVATED",
        "message": "El vostre compte de gerència ha estat activat satisfactòriament. Ja podeu iniciar sessió.",
        "redirect": "/gestio/login",
    }


class IntercanviImpersonacioRequest(BaseModel):
    code: str = Field(..., min_length=20, max_length=128, pattern=r"^[A-Za-z0-9_-]+$")


class IntercanviImpersonacioResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    rol: str = "SUPERADMIN"
    empresa_id: str
    empresa_nom: str = ""
    is_impersonation: bool = True
    return_url: str = ""


@router.post("/impersonacio/intercanvi", response_model=IntercanviImpersonacioResponse)
@limiter_login.limit("10/minute")
async def intercanviar_codi_impersonacio(
    request: Request, payload_in: IntercanviImpersonacioRequest
) -> IntercanviImpersonacioResponse:
    """Consumeix un codi d'un sol ús generat pel Superadmin i retorna el JWT d'impersonació.

    - El codi és opac (256 bits), viu 60 s a Redis i es consumeix atòmicament (GETDEL).
    - Només es pot bescanviar des del host de l'empresa impersonada.
    """
    import json

    from app.api.v1.superadmin.tenants import IMPERSONATION_HANDOFF_PREFIX
    from app.core.redis import get_redis_client
    from app.middleware.tenant import resoldre_empresa_id_per_host

    no_valid = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Codi d'impersonació invàlid o caducat.",
    )

    client = await get_redis_client()
    if not client:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Servei de sessions no disponible temporalment.",
        )

    raw = await client.getdel(f"{IMPERSONATION_HANDOFF_PREFIX}{payload_in.code}")
    if not raw:
        raise no_valid

    try:
        dades = json.loads(raw)
        token = str(dades["token"])
        empresa_id = str(dades["empresa_id"])
    except (ValueError, KeyError, TypeError):
        raise no_valid

    # El token ha de ser un JWT d'impersonació vàlid i coherent amb el codi
    try:
        claims = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    except jwt.PyJWTError:
        raise no_valid
    if not claims.get("is_impersonation") or str(claims.get("empresa_id")) != empresa_id:
        raise no_valid

    # Vinculació al host: el codi només es pot bescanviar al domini de l'empresa impersonada
    host = str(getattr(request.state, "tenant_host", "") or "")
    if host not in ("localhost", "127.0.0.1", "testserver", "test", ""):
        host_empresa_id = await resoldre_empresa_id_per_host(host)
        if str(host_empresa_id or "") != empresa_id:
            logger.warning("Intent de bescanvi d'impersonació des d'un host no coincident: %s", host)
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Aquest codi d'impersonació no és vàlid per a aquest domini.",
            )

    return IntercanviImpersonacioResponse(
        access_token=token,
        empresa_id=empresa_id,
        empresa_nom=str(dades.get("empresa_nom") or ""),
        return_url=str(dades.get("return_url") or ""),
    )
