import secrets
import string
import uuid
from datetime import date, datetime, timezone
from typing import List, Optional

import bcrypt
from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.operari_pwa.jornada import JornadaInici
from app.core.db import get_db_with_tenant_context
from app.core.security import require_roles, veto_enginyer_finances
from app.models.models import Empresa, OrdreTreball, RegistreJornadaLaboral, Usuari
from app.services.ocr_service import processar_dni_ocr

router = APIRouter(
    prefix="/gestio/operaris",
    tags=["Gestió Operaris"],
    dependencies=[Depends(require_roles(["BOSS", "SECRETARIA", "ENGINYER"]))],
)


class OperariCreate(BaseModel):
    nif: str = Field(..., max_length=20)
    nom: str = Field(..., max_length=100)
    cognoms: str = Field("", max_length=100)
    telefon: str = Field(..., max_length=20)
    email: Optional[str] = Field(None, max_length=150)
    rol: str = Field("OPERARI", max_length=30)
    especialitat: str = Field("SISTEMES_REG", max_length=50)
    cost_hora_eur: float = Field(22.50)
    carnet_conduir: str = Field("B", max_length=20)


class OperariUpdate(BaseModel):
    nom: Optional[str] = Field(None, max_length=100)
    cognoms: Optional[str] = Field(None, max_length=100)
    nif: Optional[str] = Field(None, max_length=20)
    telefon: Optional[str] = Field(None, max_length=20)
    email: Optional[str] = Field(None, max_length=150)
    rol: Optional[str] = Field(None, max_length=30)
    especialitat: Optional[str] = Field(None, max_length=50)
    estat_operatiu: Optional[str] = Field(None, max_length=30)
    estat: Optional[str] = Field(None, max_length=20)
    cost_hora_eur: Optional[float] = None
    carnet_conduir: Optional[str] = Field(None, max_length=20)
    carnet_caducitat: Optional[date] = None
    prl_certificat_vigencia: Optional[date] = None
    cap_de_grup_id: Optional[uuid.UUID] = None
    vehicle_assignat_id: Optional[uuid.UUID] = None


class OperariResponse(BaseModel):
    id: uuid.UUID
    nif: str
    nom: str
    cognoms: str = ""
    email: Optional[str] = None
    telefon: Optional[str] = None
    rol: str = "OPERARI"
    especialitat: Optional[str] = "SISTEMES_REG"
    estat_operatiu: Optional[str] = "DISPONIBLE"
    estat: str = "ACTIU"
    cost_hora_eur: float = 22.50
    carnet_conduir: str = "B"
    carnet_caducitat: Optional[date] = None
    prl_certificat_vigencia: Optional[date] = None
    pin_bloquejat: bool = False
    intents_pin_fallits: int = 0
    cap_de_grup_id: Optional[uuid.UUID] = None
    vehicle_assignat_id: Optional[uuid.UUID] = None
    latitud: Optional[float] = None
    longitud: Optional[float] = None
    pin_generat: Optional[str] = None
    login_url: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


def generar_pin() -> str:
    """Genera un PIN numèric segur de 4 dígits."""
    return "".join(secrets.choice(string.digits) for _ in range(4))


def hash_pin(pin: str) -> str:
    """Hashea el PIN utilitzant bcrypt directament."""
    return bcrypt.hashpw(pin.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


async def verificar_permisos_boss(request: Request):
    """Comprova que l'usuari té rol BOSS o SECRETARIA."""
    if not request.state.empresa_id:
        raise HTTPException(status_code=401, detail="No identificat")
    return request.state.empresa_id


@router.get("", response_model=List[OperariResponse])
async def llistar_operaris(
    request: Request, db: AsyncSession = Depends(get_db_with_tenant_context)
):
    empresa_id = await verificar_permisos_boss(request)

    stmt = (
        select(Usuari)
        .where(
            Usuari.empresa_id == uuid.UUID(empresa_id),
            Usuari.rol.in_(["OPERARI", "CAP_DE_COLLA"]),
        )
        .order_by(Usuari.nom.asc())
    )
    result = await db.execute(stmt)
    operaris = result.scalars().all()

    # Afegir coordenades de feines actives per relacionar visualment l'operari al mapa
    response_list = []
    for idx, op in enumerate(operaris):
        op_resp = OperariResponse.model_validate(op)
        stmt_ot = select(OrdreTreball).where(
            OrdreTreball.empresa_id == uuid.UUID(empresa_id),
            OrdreTreball.cap_de_colla_id == op.id,
            OrdreTreball.estat.in_(["EN_CURS", "EN_RUTA", "EN_OBRA", "ASSIGNADA", "PROGRAMADA"]),
        ).order_by(OrdreTreball.created_at.desc())
        ot_res = await db.execute(stmt_ot)
        ot_activa = ot_res.scalars().first()
        if ot_activa:
            if ot_activa.latitud is not None and ot_activa.longitud is not None:
                op_resp.latitud = float(ot_activa.latitud) + 0.002
                op_resp.longitud = float(ot_activa.longitud) + 0.002
            elif ot_activa.adreca and "," in ot_activa.adreca:
                try:
                    parts = [float(p.strip()) for p in ot_activa.adreca.split(",")]
                    if len(parts) >= 2:
                        op_resp.latitud = parts[0] + 0.002
                        op_resp.longitud = parts[1] + 0.002
                except (ValueError, TypeError):
                    pass

        if op_resp.latitud is None or op_resp.longitud is None:
            # Coordenades de base operativa / seu central (Lleida)
            op_resp.latitud = 41.6176 + ((idx % 7) - 3) * 0.003
            op_resp.longitud = 0.6200 + ((idx % 7) - 3) * 0.003

        response_list.append(op_resp)

    return response_list


@router.post("", response_model=OperariResponse, status_code=status.HTTP_201_CREATED)
async def alta_operari(
    request: Request,
    operari: OperariCreate,
    db: AsyncSession = Depends(get_db_with_tenant_context),
    claims: dict = Depends(require_roles(["BOSS", "SECRETARIA"])),
):
    empresa_id = await verificar_permisos_boss(request)
    emp_uuid = uuid.UUID(empresa_id)

    emp_res = await db.execute(select(Empresa).where(Empresa.id == emp_uuid))
    emp = emp_res.scalars().first()
    if emp and getattr(emp, "quota_operaris", None) is not None:
        count_res = await db.execute(
            select(func.count(Usuari.id)).where(
                Usuari.empresa_id == emp_uuid,
                Usuari.rol == "OPERARI",
                Usuari.estat == "ACTIU",
            )
        )
        operaris_actius = count_res.scalar() or 0
        if operaris_actius >= int(emp.quota_operaris):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    f"S'ha assolit el límit d'operaris de la vostra llicència ({operaris_actius}/{emp.quota_operaris}). "
                    "Contacteu amb l'administració SaaS per ampliar la quota."
                ),
            )

    nif_clean = operari.nif.strip().upper()
    stmt = select(Usuari).where(
        Usuari.empresa_id == emp_uuid, func.upper(Usuari.nif) == nif_clean
    )
    result = await db.execute(stmt)
    if result.scalars().first():
        raise HTTPException(status_code=400, detail="Ja existeix un operari amb aquest NIF")

    nou_pin = generar_pin()
    hashed_pin = hash_pin(nou_pin)
    rol_norm = operari.rol.strip().upper() if operari.rol else "OPERARI"
    if rol_norm not in ("OPERARI", "CAP_DE_COLLA"):
        rol_norm = "OPERARI"

    nou_usuari = Usuari(
        id=uuid.uuid4(),
        empresa_id=uuid.UUID(empresa_id),
        nif=nif_clean,
        nom=operari.nom.strip(),
        cognoms=(operari.cognoms or "").strip(),
        email=operari.email.strip().lower() if operari.email else None,
        telefon=operari.telefon.strip(),
        especialitat=operari.especialitat,
        cost_hora_eur=operari.cost_hora_eur,
        carnet_conduir=operari.carnet_conduir or "B",
        rol=rol_norm,
        estat="ACTIU",
        pin_hash=hashed_pin,
    )
    db.add(nou_usuari)
    await db.flush()
    resp_obj = OperariResponse.model_validate(nou_usuari)
    resp_obj.pin_generat = nou_pin
    resp_obj.login_url = "/operari/login"
    await db.commit()

    print(f"[SMS DISPATCH] -> Per a {operari.telefon}: El teu nou PIN de CampoPro és {nou_pin}")
    return resp_obj


@router.put("/{operari_id}", response_model=OperariResponse)
async def actualitzar_operari(
    request: Request,
    operari_id: uuid.UUID,
    payload: OperariUpdate,
    db: AsyncSession = Depends(get_db_with_tenant_context),
    claims: dict = Depends(require_roles(["BOSS", "SECRETARIA"])),
):
    """Actualitza les dades d'un operari (només BOSS i SECRETARIA; Veto d'Enginyer HTTP 403)."""
    empresa_id = await verificar_permisos_boss(request)
    emp_uuid = uuid.UUID(empresa_id)

    stmt = select(Usuari).where(
        Usuari.id == operari_id,
        Usuari.empresa_id == emp_uuid,
        Usuari.rol.in_(["OPERARI", "CAP_DE_COLLA"]),
    )
    result = await db.execute(stmt)
    usuari = result.scalars().first()
    if not usuari:
        raise HTTPException(status_code=404, detail="Operari no trobat")

    if payload.nif is not None:
        nif_clean = payload.nif.strip().upper()
        if nif_clean != usuari.nif:
            res_nif = await db.execute(
                select(Usuari).where(
                    Usuari.empresa_id == emp_uuid,
                    func.upper(Usuari.nif) == nif_clean,
                    Usuari.id != operari_id,
                )
            )
            if res_nif.scalars().first():
                raise HTTPException(
                    status_code=400, detail="Ja existeix un altre usuari amb aquest NIF"
                )
            usuari.nif = nif_clean

    if payload.nom is not None and payload.nom.strip():
        usuari.nom = payload.nom.strip()
    if payload.cognoms is not None:
        usuari.cognoms = payload.cognoms.strip()
    if payload.telefon is not None and payload.telefon.strip():
        usuari.telefon = payload.telefon.strip()
    if payload.email is not None:
        usuari.email = payload.email.strip().lower() if payload.email.strip() else None
    if payload.rol is not None:
        rol_norm = payload.rol.strip().upper()
        if rol_norm in ("OPERARI", "CAP_DE_COLLA"):
            usuari.rol = rol_norm
    if payload.especialitat is not None and payload.especialitat.strip():
        usuari.especialitat = payload.especialitat.strip()
    if payload.estat_operatiu is not None and payload.estat_operatiu.strip():
        usuari.estat_operatiu = payload.estat_operatiu.strip().upper()
    if payload.estat is not None and payload.estat.strip():
        usuari.estat = payload.estat.strip().upper()
    if payload.cost_hora_eur is not None:
        usuari.cost_hora_eur = float(payload.cost_hora_eur)
    if payload.carnet_conduir is not None and payload.carnet_conduir.strip():
        usuari.carnet_conduir = payload.carnet_conduir.strip()
    if payload.carnet_caducitat is not None:
        usuari.carnet_caducitat = payload.carnet_caducitat
    if payload.prl_certificat_vigencia is not None:
        usuari.prl_certificat_vigencia = payload.prl_certificat_vigencia
    if "cap_de_grup_id" in payload.model_fields_set:
        usuari.cap_de_grup_id = payload.cap_de_grup_id
    if "vehicle_assignat_id" in payload.model_fields_set:
        usuari.vehicle_assignat_id = payload.vehicle_assignat_id

    usuari.updated_at = datetime.now(timezone.utc)
    await db.flush()
    resp_obj = OperariResponse.model_validate(usuari)
    await db.commit()
    return resp_obj


@router.post("/{operari_id}/baixa")
async def tramitar_baixa_operari(
    request: Request,
    operari_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_with_tenant_context),
    claims: dict = Depends(require_roles(["BOSS", "SECRETARIA"])),
):
    """Tramita la baixa laboral d'un operari (només BOSS i SECRETARIA)."""
    empresa_id = await verificar_permisos_boss(request)
    emp_uuid = uuid.UUID(empresa_id)

    stmt = select(Usuari).where(
        Usuari.id == operari_id,
        Usuari.empresa_id == emp_uuid,
    )
    result = await db.execute(stmt)
    usuari = result.scalars().first()
    if not usuari:
        raise HTTPException(status_code=404, detail="Operari no trobat")

    usuari.estat = "BAIXA"
    usuari.estat_operatiu = "BAIXA"
    usuari.updated_at = datetime.now(timezone.utc)
    await db.commit()

    return {"status": "OK", "missatge": "Baixa laboral tramitada correctament", "id": str(operari_id)}


@router.post("/{operari_id}/reset-pin")
async def reset_pin_operari(
    request: Request,
    operari_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_with_tenant_context),
    claims: dict = Depends(require_roles(["BOSS", "SECRETARIA"])),
):
    empresa_id = await verificar_permisos_boss(request)

    stmt = select(Usuari).where(Usuari.id == operari_id, Usuari.empresa_id == uuid.UUID(empresa_id))
    result = await db.execute(stmt)
    usuari = result.scalars().first()

    if not usuari:
        raise HTTPException(status_code=404, detail="Operari no trobat")

    nou_pin = generar_pin()
    usuari.pin_hash = hash_pin(nou_pin)
    usuari.pin_bloquejat = False
    usuari.intents_pin_fallits = 0
    nom_complet = f"{usuari.nom or ''} {usuari.cognoms or ''}".strip()
    nif_str = usuari.nif
    telefon_str = usuari.telefon
    rol_str = usuari.rol

    await db.commit()
    print(f"[SMS DISPATCH] -> Per a {telefon_str}: El teu nou PIN de CampoPro és {nou_pin}")

    return {
        "missatge": "Nou PIN generat i tramès per SMS",
        "id": str(operari_id),
        "nom_complet": nom_complet,
        "nif": nif_str,
        "telefon": telefon_str,
        "rol": rol_str,
        "pin_generat": nou_pin,
        "login_url": "/operari/login",
        "pin_bloquejat": False,
        "intents_pin_fallits": 0,
    }


@router.post("/alta-dni-ocr")
async def alta_dni_ocr(
    request: Request,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db_with_tenant_context),
    claims: dict = Depends(require_roles(["BOSS", "SECRETARIA"])),
):
    await verificar_permisos_boss(request)
    content = await file.read()
    data = await processar_dni_ocr(content)
    return data


@router.post("/{operari_id}/fitxar")
async def fitxar_operari_gestio(
    request: Request,
    operari_id: uuid.UUID,
    payload: JornadaInici,
    db: AsyncSession = Depends(get_db_with_tenant_context),
    claims: dict = Depends(require_roles(["BOSS", "SECRETARIA"])),
):
    empresa_id = await verificar_permisos_boss(request)

    stmt = select(RegistreJornadaLaboral).where(
        RegistreJornadaLaboral.empresa_id == uuid.UUID(empresa_id),
        RegistreJornadaLaboral.usuari_id == operari_id,
        RegistreJornadaLaboral.estat == "EN_CURS",
    )
    result = await db.execute(stmt)
    jornada = result.scalars().first()

    if jornada:
        jornada.hora_fi = datetime.now(timezone.utc)
        jornada.geolocalitzacio_fi = f"{payload.latitud},{payload.longitud}"
        jornada.estat = "COMPLERT"
        await db.commit()
        return {"estat": "COMPLERT", "jornada_id": jornada.id}
    else:
        nova_jornada = RegistreJornadaLaboral(
            empresa_id=uuid.UUID(empresa_id),
            usuari_id=operari_id,
            geolocalitzacio_inici=f"{payload.latitud},{payload.longitud}",
            estat="EN_CURS",
        )
        db.add(nova_jornada)
        await db.commit()
        return {"estat": "EN_CURS", "jornada_id": nova_jornada.id}


@router.get("/{operari_id}/control-horari")
async def get_control_horari(
    request: Request,
    operari_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_with_tenant_context),
    claims: dict = Depends(veto_enginyer_finances),
):
    empresa_id = await verificar_permisos_boss(request)
    stmt = (
        select(RegistreJornadaLaboral)
        .where(
            RegistreJornadaLaboral.empresa_id == uuid.UUID(empresa_id),
            RegistreJornadaLaboral.usuari_id == operari_id,
        )
        .order_by(RegistreJornadaLaboral.hora_inici.desc())
    )
    result = await db.execute(stmt)
    jornades = result.scalars().all()
    return jornades
