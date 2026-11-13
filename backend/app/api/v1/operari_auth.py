import logging
import os
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

import bcrypt
import jwt
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, Field
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.db import get_db, set_tenant_context
from app.core.redis import get_redis
from app.models.models import Empresa, Incidencia, Usuari
from app.services.telegram_service import send_telegram_direct_message

logger = logging.getLogger("operari_auth")

router = APIRouter(prefix="/operari_auth", tags=["Operari Auth"])
enrolament_router = APIRouter(prefix="/operari", tags=["Operari Auth PWA"])
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
    requereix_rexifrat_idb: bool = False
    dispositiu_referencia: Optional[str] = None


class EnrolamentRequest(BaseModel):
    telefon_o_nif: str = Field(..., min_length=4, max_length=20)
    empresa_id: Optional[uuid.UUID] = None


class EnrolamentVerifyOTPRequest(BaseModel):
    telefon_o_nif: str = Field(..., min_length=4, max_length=20)
    empresa_id: Optional[uuid.UUID] = None
    otp_code: str = Field(..., min_length=6, max_length=6, pattern=r"^\d{6}$")
    device_fingerprint: str = Field(..., min_length=4, max_length=128)


class RecuperarPinByNifRequest(BaseModel):
    telefon_o_nif: str = Field(..., min_length=4, max_length=20)
    empresa_id: Optional[uuid.UUID] = None


class PinAttemptReport(BaseModel):
    operari_id: Optional[uuid.UUID] = None
    telefon_o_nif: Optional[str] = None
    empresa_id: Optional[uuid.UUID] = None
    intents_fallits: int = Field(..., ge=3)
    device_token: str = Field(..., min_length=1, max_length=255)


def _hash_pin_bcrypt(pin: str) -> str:
    return bcrypt.hashpw(pin.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


async def _resolve_empresa_uuid(
    request: Request,
    explicit_empresa_id: Optional[uuid.UUID],
    db: AsyncSession,
    identificador: Optional[str] = None,
) -> Optional[uuid.UUID]:
    if explicit_empresa_id:
        return explicit_empresa_id
    state_emp = getattr(request.state, "empresa_id", None)
    if state_emp:
        try:
            return uuid.UUID(str(state_emp))
        except ValueError:
            pass
    header_emp = request.headers.get("X-Tenant-ID") or request.headers.get("X-Empresa-ID")
    if header_emp:
        try:
            return uuid.UUID(header_emp)
        except ValueError:
            res_sub = await db.execute(select(Empresa.id).where(Empresa.subdomini == header_emp))
            found = res_sub.scalar()
            if found:
                return found
    if identificador and os.getenv("TESTING") == "1":
        res_u = await db.execute(
            select(Usuari.empresa_id).where(
                or_(
                    func.upper(Usuari.nif) == identificador.strip().upper(),
                    Usuari.telefon == identificador.strip(),
                )
            )
        )
        found = res_u.scalar()
        if found:
            return found
    return None


def create_access_token(
    subject: str | Any, rol: str, empresa_id: str, expires_delta: timedelta
) -> str:
    expire = datetime.now(timezone.utc) + expires_delta
    to_encode = {"sub": str(subject), "rol": rol, "empresa_id": str(empresa_id), "exp": expire}
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt


@router.post("/login", response_model=TokenResponse)
@limiter_login.limit("5/minute")
async def login_operari(
    request: Request, login_data: LoginRequest, db: AsyncSession = Depends(get_db)
):
    empresa_id = (
        getattr(request.state, "empresa_id", None)
        or request.headers.get("X-Tenant-ID")
        or request.headers.get("X-Empresa-ID")
    )
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
        # 1. Intentar resoldre pel host del subdomini de l'empresa
        raw_host = request.headers.get("x-forwarded-host") or request.headers.get("host") or ""
        clean_host = (
            raw_host.strip()
            .lower()
            .replace("https://", "")
            .replace("http://", "")
            .split("/")[0]
            .split(":")[0]
        )
        if clean_host and clean_host not in ("localhost", "127.0.0.1", "testserver", "test"):
            parts = clean_host.split(".")
            subdomini_cand = parts[0] if len(parts) >= 3 else None
            conds = [func.lower(Empresa.domini_custom) == clean_host]
            if subdomini_cand and subdomini_cand not in ("www", "api", "app", "localhost", "sevalor", "superadmin"):
                conds.append(func.lower(Empresa.subdomini) == subdomini_cand)
            res_h = await db.execute(select(Empresa.id).where(or_(*conds)))
            emp_id_found = res_h.scalar()
            if emp_id_found:
                empresa_uuid = emp_id_found

    if not empresa_uuid and os.getenv("TESTING") == "1":
        # Fallback exclusiu per a l'entorn de testing quan no s'envia X-Empresa-ID
        stmt_nif = select(Usuari.empresa_id).where(
            func.upper(Usuari.nif) == login_data.nif.upper(),
            Usuari.rol.in_(["OPERARI", "CAPATAZ", "CAP_DE_COLLA", "ADMIN", "SUPERADMIN"]),
        )
        res_nif = await db.execute(stmt_nif)
        empresa_uuid = res_nif.scalar()

    if not empresa_uuid:
        raise HTTPException(
            status_code=400,
            detail="Tenant context missing. Cal accedir des del subdomini registrat de l'empresa.",
        )

    await set_tenant_context(db, str(empresa_uuid))

    # 1. Buscar l'usuari aplicant el filtre de tenant implícitament i explícitament
    stmt = select(Usuari).where(
        Usuari.empresa_id == empresa_uuid,
        func.upper(Usuari.nif) == login_data.nif.upper(),
        Usuari.rol.in_(["OPERARI", "CAPATAZ", "CAP_DE_COLLA", "ADMIN", "SUPERADMIN"]),
    )

    result = await db.execute(stmt)
    usuari = result.scalars().first()

    # Si no existeix, error opac (RF-23)
    if not usuari:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Credencials invàlides"
        )

    # 2. Comprovar si el compte ja està bloquejat per intents fallits
    if usuari.pin_bloquejat or (
        usuari.intents_pin_fallits is not None and usuari.intents_pin_fallits >= 4
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="El compte ha estat bloquejat per massa intents fallits. Contacteu amb el supervisor.",
        )

    # 3. Comprovar estat actiu de l'usuari i estat d'hibernació/suspensió de l'empresa
    if usuari.estat != "ACTIU":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Usuari inactiu. Contacta amb l'administrador.",
        )

    emp_check_res = await db.execute(select(Empresa).where(Empresa.id == empresa_uuid))
    emp_check = emp_check_res.scalars().first()
    if emp_check and emp_check.estat_pagament in {
        "HIBERNANT",
        "SUSPES_PAGAMENT",
        "SUSPES",
        "BAIXA_OFFBOARDING",
        "ELIMINAT",
    }:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                f"Servei temporalment pausat ({emp_check.estat_pagament}). "
                "Contacta amb l'oficina de la teva empresa."
            ),
        )

    # 4. Verificar PIN (amb bcrypt)
    def verify_pin(plain_pin: str, hashed_pin: str) -> bool:
        if not hashed_pin:
            return False
        try:
            return bcrypt.checkpw(plain_pin.encode("utf-8"), hashed_pin.encode("utf-8"))
        except Exception:
            return False

    is_valid = verify_pin(login_data.pin, usuari.pin_hash) if usuari.pin_hash else False

    if not is_valid:
        usuari.intents_pin_fallits = (usuari.intents_pin_fallits or 0) + 1
        if usuari.intents_pin_fallits == 3:
            db.add(
                Incidencia(
                    id=uuid.uuid4(),
                    empresa_id=usuari.empresa_id,
                    operari_id=usuari.id,
                    ambit="SEGURETAT",
                    tipus="FORCA_BRUTA_PIN",
                    gravetat="CRITICA",
                    estat="OBERTA",
                    text_observacions=(
                        f"Alerta de Seguretat per Intents Fallits de PIN (3 intents consecutius) "
                        f"per a l'operari {usuari.nif}."
                    ),
                )
            )
        if usuari.intents_pin_fallits >= 4:
            usuari.pin_bloquejat = True
            await db.commit()
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="El compte ha estat bloquejat per massa intents fallits. Contacteu amb el supervisor.",
            )
        await db.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Credencials invàlides"
        )

    # 5. Login correcte: reiniciar comptador d'intents, bloqueig i capturar flag de re-xifrat
    rexifrat_pendent = bool(getattr(usuari, "requereix_rexifrat_idb", False))
    dispositiu_ref = getattr(usuari, "dispositiu_referencia", None)
    usuari.intents_pin_fallits = 0
    usuari.pin_bloquejat = False
    usuari.requereix_rexifrat_idb = False
    usuari.data_ultim_acces = datetime.now(timezone.utc)
    await db.commit()

    # Generar JWT amb claims mínims
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    token = create_access_token(
        subject=str(usuari.id),
        rol=usuari.rol,
        empresa_id=str(usuari.empresa_id),
        expires_delta=access_token_expires,
    )

    return TokenResponse(
        access_token=token,
        usuari=UsuariTokenResponse(id=usuari.id, nom=usuari.nom, rol=usuari.rol),
        requereix_rexifrat_idb=rexifrat_pendent,
        dispositiu_referencia=dispositiu_ref,
    )


async def _find_active_operari(
    db: AsyncSession, empresa_uuid: uuid.UUID, telefon_o_nif: str
) -> Optional[Usuari]:
    ident = telefon_o_nif.strip()
    stmt = select(Usuari).where(
        Usuari.empresa_id == empresa_uuid,
        Usuari.estat == "ACTIU",
        or_(Usuari.telefon == ident, func.upper(Usuari.nif) == ident.upper()),
    )
    return (await db.execute(stmt)).scalar_one_or_none()


async def _executar_reset_pin_telegram(
    db: AsyncSession,
    operari: Usuari,
) -> Incidencia:
    nou_pin = f"{secrets.randbelow(9000) + 1000}"
    operari.pin_hash = _hash_pin_bcrypt(nou_pin)
    operari.requereix_rexifrat_idb = True
    operari.pin_bloquejat = False
    operari.intents_pin_fallits = 0

    incidencia_seg = Incidencia(
        id=uuid.uuid4(),
        empresa_id=operari.empresa_id,
        operari_id=operari.id,
        ambit="SEGURETAT",
        tipus="SEGURETAT_RESTABLIMENT_PIN",
        gravetat="ALTA",
        estat="OBERTA",
        text_observacions=(
            f"Incidència de Seguretat per Restabliment de PIN enviada via Telegram "
            f"({datetime.now(timezone.utc).isoformat()})"
        ),
    )
    db.add(incidencia_seg)
    await db.commit()

    if operari.telegram_chat_id and operari.empresa_id:
        await send_telegram_direct_message(
            empresa_id=operari.empresa_id,
            chat_id=int(operari.telegram_chat_id),
            text=(
                f"🛡️ *Restabliment de PIN de Seguretat*\n\n"
                f"Secretaria ha generat un nou PIN temporal de 4 dígits per a la teva PWA:\n"
                f"🔢 *{nou_pin}*\n\n"
                f"En el teu proper accés amb cobertura, la memòria local del mòbil es re-xifrarà automàticament."
            ),
        )
    return incidencia_seg


@enrolament_router.post("/enrolar/solicitar-otp", status_code=status.HTTP_200_OK)
@limiter_login.limit("5/minute")
async def solicitar_otp_telegram_enrolament(
    request: Request,
    payload: EnrolamentRequest,
    db: AsyncSession = Depends(get_db),
    redis=Depends(get_redis),
):
    """Spec 019 (RF-03 / RF-11 Telegram): Envia OTP de 6 dígits al Telegram vinculat."""
    empresa_uuid = await _resolve_empresa_uuid(
        request, payload.empresa_id, db, payload.telefon_o_nif
    )
    if not empresa_uuid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No s'ha pogut identificar l'empresa per a l'enrolament.",
        )

    await set_tenant_context(db, str(empresa_uuid))
    operari = await _find_active_operari(db, empresa_uuid, payload.telefon_o_nif)
    if not operari or not operari.telegram_chat_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "No s'ha pogut iniciar l'enrolament. Verifica amb Secretaria que tens el teu "
                "Telegram vinculat a la Fitxa 360."
            ),
        )

    otp_code = f"{secrets.randbelow(900000) + 100000}"
    redis_key = f"pwa_enrol_otp:{empresa_uuid}:{operari.id}"
    await redis.set(redis_key, otp_code, ex=300)

    missatge = (
        f"🔐 *Enrolament de Dispositiu PWA*\n\n"
        f"Hola {operari.nom}, el teu codi OTP d'un sol ús per vincular aquest terminal mòbil és:\n\n"
        f"👉 *{otp_code}*\n\n"
        f"_(Vàlid durant 5 minuts. No el comparteixis amb ningú)_"
    )
    await send_telegram_direct_message(
        empresa_id=empresa_uuid,
        chat_id=int(operari.telegram_chat_id),
        text=missatge,
    )
    return {"status": "OTP_SENT_TELEGRAM", "operari_id": str(operari.id)}


@enrolament_router.post("/enrolar/verificar-otp", status_code=status.HTTP_200_OK)
@limiter_login.limit("10/minute")
async def verificar_otp_telegram_enrolament(
    request: Request,
    payload: EnrolamentVerifyOTPRequest,
    db: AsyncSession = Depends(get_db),
    redis=Depends(get_redis),
):
    """Verifica el codi OTP enviat per Telegram i emet el device_token per a IndexedDB."""
    empresa_uuid = await _resolve_empresa_uuid(
        request, payload.empresa_id, db, payload.telefon_o_nif
    )
    if not empresa_uuid:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Credencials d'enrolament invàlides",
        )

    await set_tenant_context(db, str(empresa_uuid))
    operari = await _find_active_operari(db, empresa_uuid, payload.telefon_o_nif)
    if not operari:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Credencials d'enrolament invàlides",
        )

    redis_key = f"pwa_enrol_otp:{empresa_uuid}:{operari.id}"
    stored_raw = await redis.get(redis_key)
    stored_otp = (
        stored_raw.decode("utf-8") if isinstance(stored_raw, bytes) else (stored_raw or "")
    )
    if not stored_otp or not secrets.compare_digest(stored_otp, payload.otp_code):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Codi OTP de Telegram caducat o incorrecte",
        )

    await redis.delete(redis_key)
    device_token = f"dev_{empresa_uuid.hex[:8]}_{uuid.uuid4().hex}"
    operari.dispositiu_referencia = f"{device_token}:{payload.device_fingerprint[:32]}"
    await db.commit()

    return {
        "status": "ENROLLED",
        "device_token": device_token,
        "operari_id": str(operari.id),
        "operari_nom": f"{operari.nom} {operari.cognoms or ''}".strip(),
        "nif": operari.nif,
        "empresa_id": str(empresa_uuid),
    }


@enrolament_router.post("/recuperar-pin/{operari_id}", status_code=status.HTTP_200_OK)
@limiter_login.limit("5/minute")
async def restablir_pin_via_telegram(
    request: Request,
    operari_id: uuid.UUID,
    empresa_id: Optional[uuid.UUID] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """Spec 019 RF-15/RF-16: Genera PIN temporal de 4 dígits per Telegram i crea incidència."""
    empresa_uuid = await _resolve_empresa_uuid(request, empresa_id, db)
    if not empresa_uuid:
        raise HTTPException(status_code=400, detail="Cal indicar l'empresa_id del tenant")

    await set_tenant_context(db, str(empresa_uuid))
    stmt = select(Usuari).where(Usuari.id == operari_id, Usuari.empresa_id == empresa_uuid)
    operari = (await db.execute(stmt)).scalar_one_or_none()
    if not operari or not operari.telegram_chat_id:
        raise HTTPException(
            status_code=400,
            detail="L'operari no té Telegram vinculat per rebre el PIN temporal",
        )

    incidencia_seg = await _executar_reset_pin_telegram(db, operari)
    return {
        "status": "PIN_RESET_TELEGRAM_SENT",
        "incidencia_id": str(incidencia_seg.id),
    }


@enrolament_router.post("/recuperar-pin", status_code=status.HTTP_200_OK)
@limiter_login.limit("5/minute")
async def recuperar_pin_per_nif_telegram(
    request: Request,
    payload: RecuperarPinByNifRequest,
    db: AsyncSession = Depends(get_db),
):
    """Flux 'Has oblidat el teu PIN?' des de la pantalla de login PWA."""
    empresa_uuid = await _resolve_empresa_uuid(
        request, payload.empresa_id, db, payload.telefon_o_nif
    )
    if not empresa_uuid:
        raise HTTPException(status_code=400, detail="No s'ha pogut identificar l'empresa")

    await set_tenant_context(db, str(empresa_uuid))
    operari = await _find_active_operari(db, empresa_uuid, payload.telefon_o_nif)
    if not operari or not operari.telegram_chat_id:
        raise HTTPException(
            status_code=400,
            detail="Verifica amb Secretaria que tens el Telegram vinculat per recuperar el PIN.",
        )

    incidencia_seg = await _executar_reset_pin_telegram(db, operari)
    return {
        "status": "PIN_RESET_TELEGRAM_SENT",
        "incidencia_id": str(incidencia_seg.id),
    }


@enrolament_router.post("/alerta-forca-bruta", status_code=status.HTTP_201_CREATED)
async def registrar_alerta_forca_bruta_pin(
    request: Request,
    payload: PinAttemptReport,
    db: AsyncSession = Depends(get_db),
):
    """Spec 019 RF-09 / RF-10 / EDGE-03: Registra 3 intents fallits consecutius de PIN."""
    empresa_uuid = await _resolve_empresa_uuid(
        request, payload.empresa_id, db, payload.telefon_o_nif
    )
    if not empresa_uuid:
        raise HTTPException(status_code=400, detail="Tenant context missing")

    await set_tenant_context(db, str(empresa_uuid))
    operari_id = payload.operari_id
    if not operari_id and payload.telefon_o_nif:
        op = await _find_active_operari(db, empresa_uuid, payload.telefon_o_nif)
        if op:
            operari_id = op.id

    incidencia = Incidencia(
        id=uuid.uuid4(),
        empresa_id=empresa_uuid,
        operari_id=operari_id,
        ambit="SEGURETAT",
        tipus="FORCA_BRUTA_PIN",
        gravetat="CRITICA",
        estat="OBERTA",
        text_observacions=(
            f"Alerta de Seguretat per Intents Fallits de PIN ({payload.intents_fallits} intents consecutius) "
            f"al terminal {payload.device_token}. Numpad bloquejat 30 segons."
        ),
    )
    db.add(incidencia)
    await db.commit()
    return {"status": "ALERT_RECORDED", "incidencia_id": str(incidencia.id)}
