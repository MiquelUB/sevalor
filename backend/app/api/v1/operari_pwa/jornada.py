import uuid
from datetime import datetime, timezone
from typing import Any, Optional

import filetype
from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db_with_tenant_context
from app.core.security import get_current_user_id, require_roles
from app.models.models import RegistreJornadaLaboral

router = APIRouter(
    prefix="/operari",
    tags=["Operari Jornada"],
    dependencies=[Depends(require_roles(["OPERARI", "CAPATAZ", "CAP_DE_COLLA"]))],
)


class JornadaInici(BaseModel):
    latitud: Optional[float] = None
    longitud: Optional[float] = None
    lat: Optional[float] = None
    lon: Optional[float] = None

    def model_post_init(self, __context: Any) -> None:
        if self.latitud is None and self.lat is not None:
            self.latitud = self.lat
        if self.longitud is None and self.lon is not None:
            self.longitud = self.lon
        if self.latitud is None:
            self.latitud = 0.0
        if self.longitud is None:
            self.longitud = 0.0


class JornadaResponse(BaseModel):
    id: uuid.UUID
    estat: str
    geolocalitzacio_inici: Optional[str]


@router.post("/inici", response_model=JornadaResponse, status_code=status.HTTP_201_CREATED)
@router.post("/jornada/inici", response_model=JornadaResponse, status_code=status.HTTP_201_CREATED)
async def iniciar_jornada(
    request: Request, payload: JornadaInici, db: AsyncSession = Depends(get_db_with_tenant_context)
):
    empresa_id = request.state.empresa_id
    if not empresa_id or empresa_id == "undefined":
        raise HTTPException(status_code=401, detail="No identificat")

    usuari_id = get_current_user_id(request)

    # Validar si ja té una jornada en curs
    stmt = select(RegistreJornadaLaboral).where(
        RegistreJornadaLaboral.empresa_id == uuid.UUID(empresa_id),
        RegistreJornadaLaboral.usuari_id == uuid.UUID(usuari_id),
        RegistreJornadaLaboral.estat == "EN_CURS",
    )
    result = await db.execute(stmt)
    if result.scalars().first():
        raise HTTPException(status_code=400, detail="Ja hi ha una jornada en curs")

    jornada = RegistreJornadaLaboral(
        empresa_id=uuid.UUID(empresa_id),
        usuari_id=uuid.UUID(usuari_id),
        geolocalitzacio_inici=f"{payload.latitud},{payload.longitud}",
        estat="EN_CURS",
    )

    db.add(jornada)
    await db.flush()

    from app.services.sovereign_storage import SovereignStorageGateway

    await SovereignStorageGateway.desar_entitat_json(
        db=db,
        empresa_id=empresa_id,
        categoria="jornades",
        item_id=str(jornada.id),
        dades={
            "id": str(jornada.id),
            "usuari_id": str(jornada.usuari_id),
            "estat": jornada.estat,
            "hora_inici": jornada.hora_inici.isoformat() if jornada.hora_inici else None,
            "geolocalitzacio_inici": jornada.geolocalitzacio_inici,
        },
    )
    await db.commit()

    return jornada


@router.get("/activa", response_model=JornadaResponse)
@router.get("/jornada/activa", response_model=JornadaResponse)
async def get_jornada_activa(
    request: Request, db: AsyncSession = Depends(get_db_with_tenant_context)
):
    empresa_id = request.state.empresa_id
    if not empresa_id or empresa_id == "undefined":
        raise HTTPException(status_code=401)

    usuari_id = get_current_user_id(request)

    stmt = select(RegistreJornadaLaboral).where(
        RegistreJornadaLaboral.empresa_id == uuid.UUID(empresa_id),
        RegistreJornadaLaboral.usuari_id == uuid.UUID(usuari_id),
        RegistreJornadaLaboral.estat == "EN_CURS",
    )
    result = await db.execute(stmt)
    jornada = result.scalars().first()

    if not jornada:
        raise HTTPException(status_code=404, detail="No hi ha jornada activa")

    return jornada


@router.post("/{jornada_id}/fi", response_model=JornadaResponse)
@router.post("/jornada/{jornada_id}/fi", response_model=JornadaResponse)
async def finalitzar_jornada(
    jornada_id: uuid.UUID,
    request: Request,
    payload: JornadaInici,
    db: AsyncSession = Depends(get_db_with_tenant_context),
):
    empresa_id = request.state.empresa_id
    if not empresa_id or empresa_id == "undefined":
        raise HTTPException(status_code=401)

    stmt = select(RegistreJornadaLaboral).where(
        RegistreJornadaLaboral.id == jornada_id,
        RegistreJornadaLaboral.empresa_id == uuid.UUID(empresa_id),
    )
    result = await db.execute(stmt)
    jornada = result.scalars().first()

    if not jornada:
        raise HTTPException(status_code=404, detail="Jornada no trobada")

    if jornada.estat == "COMPLERT":
        raise HTTPException(status_code=400, detail="La jornada ja està tancada")

    jornada.hora_fi = datetime.now(timezone.utc)
    jornada.geolocalitzacio_fi = f"{payload.latitud},{payload.longitud}"
    jornada.estat = "COMPLERT"
    await db.flush()

    from app.services.sovereign_storage import SovereignStorageGateway

    await SovereignStorageGateway.desar_entitat_json(
        db=db,
        empresa_id=empresa_id,
        categoria="jornades",
        item_id=str(jornada.id),
        dades={
            "id": str(jornada.id),
            "usuari_id": str(jornada.usuari_id),
            "estat": jornada.estat,
            "hora_inici": jornada.hora_inici.isoformat() if jornada.hora_inici else None,
            "hora_fi": jornada.hora_fi.isoformat() if jornada.hora_fi else None,
            "geolocalitzacio_inici": jornada.geolocalitzacio_inici,
            "geolocalitzacio_fi": jornada.geolocalitzacio_fi,
        },
    )
    await db.commit()

    return jornada


class AssignarVehicleRequest(BaseModel):
    vehicle_id: uuid.UUID
    km_actuals: Optional[int] = None
    km_inicials: Optional[int] = None
    fotos_check_in: Optional[list[str]] = None
    odometre_foto_path: Optional[str] = None

    def model_post_init(self, __context: Any) -> None:
        if self.km_actuals is None and self.km_inicials is not None:
            self.km_actuals = self.km_inicials


@router.post("/{jornada_id}/vehicle")
@router.post("/jornada/{jornada_id}/vehicle")
async def assignar_vehicle_a_jornada(
    jornada_id: uuid.UUID,
    payload: AssignarVehicleRequest,
    request: Request,
    db: AsyncSession = Depends(get_db_with_tenant_context),
):
    """Assigna un vehicle a l'operari per a la jornada actual i comprova odòmetre o foto."""
    empresa_id = request.state.empresa_id
    if not empresa_id or empresa_id == "undefined":
        raise HTTPException(status_code=401)

    usuari_id = get_current_user_id(request)

    # Obtenir vehicle
    from app.models.models import Usuari, Vehicle

    v_res = await db.execute(
        select(Vehicle).where(
            Vehicle.id == payload.vehicle_id, Vehicle.empresa_id == uuid.UUID(empresa_id)
        )
    )
    vehicle = v_res.scalars().first()
    if not vehicle:
        raise HTTPException(status_code=404, detail="Vehicle no trobat")

    u_res = await db.execute(select(Usuari).where(Usuari.id == uuid.UUID(usuari_id)))
    usuari = u_res.scalars().first()
    if not usuari:
        raise HTTPException(status_code=404, detail="Operari no trobat")

    # Guarda de carnet, CAP i aptitud del vehicle a la PWA (Fase 4 / FR-012)
    from app.services.flota_service import validar_permis_conduir

    validar_permis_conduir(vehicle, usuari)

    km_reportat = payload.km_actuals
    if km_reportat is not None:
        if vehicle.odometre_acumulat and km_reportat < vehicle.odometre_acumulat:
            raise HTTPException(
                status_code=422, detail="Els km reportats són inferiors als últims registrats"
            )
        vehicle.odometre_acumulat = km_reportat
    elif not payload.odometre_foto_path and not payload.fotos_check_in:
        raise HTTPException(
            status_code=422,
            detail="Cal capturar la fotografia de l'odòmetre o indicar el quilometratge.",
        )

    usuari.vehicle_assignat_id = vehicle.id
    if not vehicle.conductor_habitual_id:
        vehicle.conductor_habitual_id = usuari.id

    await db.flush()

    from app.services.sovereign_storage import SovereignStorageGateway

    await SovereignStorageGateway.desar_entitat_json(
        db=db,
        empresa_id=empresa_id,
        categoria="vehicles",
        item_id=str(vehicle.id),
        dades={
            "id": str(vehicle.id),
            "matricula": vehicle.matricula,
            "marca": vehicle.marca,
            "model": vehicle.model,
            "odometre_acumulat": vehicle.odometre_acumulat,
            "odometre_foto_path": payload.odometre_foto_path,
            "conductor_habitual_id": (
                str(vehicle.conductor_habitual_id) if vehicle.conductor_habitual_id else None
            ),
            "ultim_operari_id": str(usuari_id),
            "jornada_id": str(jornada_id),
        },
    )
    await db.commit()

    return {
        "status": "OK",
        "vehicle_assignat_id": str(vehicle.id),
        "km_actuals": vehicle.odometre_acumulat,
        "odometre_foto_path": payload.odometre_foto_path,
    }


@router.post("/{jornada_id}/odometre-foto", status_code=status.HTTP_201_CREATED)
@router.post("/jornada/{jornada_id}/odometre-foto", status_code=status.HTTP_201_CREATED)
async def pujar_foto_odometre_jornada(
    jornada_id: uuid.UUID,
    request: Request,
    foto_odometre: UploadFile = File(...),
    vehicle_id: Optional[str] = Form(None),
    moment: str = Form("INICI"),
    db: AsyncSession = Depends(get_db_with_tenant_context),
):
    """(Spec 015/020) Captura fotogràfica obligatòria d'odòmetre en inici o tancament de jornada."""
    empresa_id = request.state.empresa_id
    if not empresa_id or empresa_id == "undefined":
        raise HTTPException(status_code=401, detail="Tenant context missing")

    emp_uuid = uuid.UUID(str(empresa_id))
    usuari_id = get_current_user_id(request)
    raw = await foto_odometre.read()
    if not raw:
        raise HTTPException(status_code=422, detail="La foto de l'odòmetre és obligatòria.")
    if len(raw) > 10 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="La foto supera el límit de 10 MB.")

    kind = filetype.guess(raw)
    mimes_map = {"image/webp": "webp", "image/jpeg": "jpg", "image/png": "png"}
    if kind is None or kind.mime not in mimes_map:
        raise HTTPException(
            status_code=422, detail="Format d'imatge no vàlid. Admesos: WebP, JPEG, PNG."
        )

    from app.services.sovereign_storage import SovereignStorageGateway

    ext = mimes_map[kind.mime]
    path = await SovereignStorageGateway.pujar_fitxer_binari(
        db=db,
        empresa_id=str(emp_uuid),
        categoria="odometres",
        nom_fitxer=f"{uuid.uuid4().hex}.{ext}",
        content=raw,
        content_type=kind.mime,
    )

    moment_norm = moment.strip().upper() or "INICI"
    await SovereignStorageGateway.desar_entitat_json(
        db=db,
        empresa_id=str(emp_uuid),
        categoria="odometres",
        item_id=f"odo_{jornada_id}_{moment_norm.lower()}_{uuid.uuid4().hex[:8]}",
        dades={
            "jornada_id": str(jornada_id),
            "operari_id": str(usuari_id),
            "vehicle_id": vehicle_id,
            "moment": moment_norm,
            "foto_path": path,
            "created_at": datetime.now(timezone.utc).isoformat(),
        },
    )
    await db.commit()
    return {
        "status": "OK",
        "jornada_id": str(jornada_id),
        "moment": moment_norm,
        "foto_odometre_path": path,
    }
