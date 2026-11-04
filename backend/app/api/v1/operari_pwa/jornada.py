import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
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
    await db.commit()

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

    await db.commit()

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

    return jornada


class AssignarVehicleRequest(BaseModel):
    vehicle_id: uuid.UUID
    km_actuals: int = 0
    km_inicials: Optional[int] = None
    fotos_check_in: Optional[list[str]] = None

    def model_post_init(self, __context: Any) -> None:
        if self.km_actuals == 0 and self.km_inicials is not None:
            self.km_actuals = self.km_inicials


@router.post("/{jornada_id}/vehicle")
@router.post("/jornada/{jornada_id}/vehicle")
async def assignar_vehicle_a_jornada(
    jornada_id: uuid.UUID,
    payload: AssignarVehicleRequest,
    request: Request,
    db: AsyncSession = Depends(get_db_with_tenant_context),
):
    """Assigna un vehicle a l'operari per a la jornada actual i comprova odòmetre."""
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

    if vehicle.odometre_acumulat and payload.km_actuals < vehicle.odometre_acumulat:
        raise HTTPException(
            status_code=422, detail="Els km reportats són inferiors als últims registrats"
        )

    # Actualitzar Vehicle i Usuari
    vehicle.odometre_acumulat = payload.km_actuals
    u_res = await db.execute(select(Usuari).where(Usuari.id == uuid.UUID(usuari_id)))
    usuari = u_res.scalars().first()
    usuari.vehicle_assignat_id = vehicle.id  # type: ignore

    await db.commit()

    from app.services.sovereign_storage import SovereignStorageGateway

    await SovereignStorageGateway.desar_entitat_json(
        db=db,
        empresa_id=empresa_id,
        categoria="vehicles",
        item_id=str(vehicle.id),
        dades={
            "id": str(vehicle.id),
            "matricula": vehicle.matricula,
            "model": vehicle.model,
            "odometre_acumulat": vehicle.odometre_acumulat,
            "ultim_operari_id": str(usuari_id),
            "jornada_id": str(jornada_id),
        },
    )

    return {
        "status": "OK",
        "vehicle_assignat_id": str(vehicle.id),
        "km_actuals": payload.km_actuals,
    }
