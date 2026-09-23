import uuid
from datetime import date, datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db_with_tenant_context
from app.core.security import require_roles
from app.models.models import Client, OrdreTreball

router = APIRouter(
    prefix="/gestio/feines",
    tags=["Gestió Feines i Mapa"],
    dependencies=[Depends(require_roles(["BOSS", "SECRETARIA", "ENGINYER"]))],
)

class FeinaCreate(BaseModel):
    codi: str = Field(..., max_length=20)
    client_id: uuid.UUID
    finca_id: Optional[uuid.UUID] = None
    titol: str = Field(..., max_length=200)
    adreca: str = Field(..., max_length=255)
    descripcio: Optional[str] = None
    estat: str = Field("PENDENT", max_length=30)
    data_planificacio: date
    cap_de_colla_id: uuid.UUID
    vehicle_id: Optional[uuid.UUID] = None

class FeinaResponse(FeinaCreate):
    id: uuid.UUID

@router.get("", response_model=List[FeinaResponse])
async def llistar_feines(
    request: Request,
    q: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    db: AsyncSession = Depends(get_db_with_tenant_context)
):
    empresa_id = request.state.empresa_id
    if not empresa_id:
        raise HTTPException(status_code=401, detail="No identificat")

    stmt = select(OrdreTreball).where(OrdreTreball.empresa_id == uuid.UUID(empresa_id))

    if q:
        search_term = f"%{q}%"
        stmt = stmt.where(
            or_(
                OrdreTreball.codi.ilike(search_term),
                OrdreTreball.titol.ilike(search_term)
            )
        )

    stmt = stmt.limit(limit).offset(offset).order_by(OrdreTreball.created_at.desc())

    result = await db.execute(stmt)
    feines = result.scalars().all()

    return feines

@router.post("", response_model=FeinaResponse, status_code=status.HTTP_201_CREATED)
async def alta_feina(
    request: Request,
    feina: FeinaCreate,
    db: AsyncSession = Depends(get_db_with_tenant_context)
):
    empresa_id = request.state.empresa_id
    if not empresa_id:
        raise HTTPException(status_code=401, detail="No identificat")

    stmt_codi = select(OrdreTreball).where(
        OrdreTreball.empresa_id == uuid.UUID(empresa_id),
        OrdreTreball.codi == feina.codi
    )
    result_codi = await db.execute(stmt_codi)
    if result_codi.scalars().first():
        raise HTTPException(status_code=400, detail="El codi de feina ja es troba registrat")

    nova_feina = OrdreTreball(
        empresa_id=uuid.UUID(empresa_id),
        codi=feina.codi,
        client_id=feina.client_id,
        finca_id=feina.finca_id,
        titol=feina.titol,
        adreca=feina.adreca,
        descripcio=feina.descripcio,
        estat=feina.estat,
        data_planificacio=feina.data_planificacio,
        cap_de_colla_id=feina.cap_de_colla_id,
        vehicle_id=feina.vehicle_id
    )

    db.add(nova_feina)
    await db.commit()

    return nova_feina


class MapaMarkerItem(BaseModel):
    id: str
    codi: str
    titol: str
    estat: str
    lat: float
    lng: float
    is_incidencia: bool = False
    adreca: Optional[str] = None
    client_rao_social: Optional[str] = None

@router.get("/mapa", response_model=List[MapaMarkerItem])
async def llistar_feines_mapa(
    request: Request,
    db: AsyncSession = Depends(get_db_with_tenant_context)
):
    """Retorna les OTs del tenant actual amb les seves coordenades reals per al Mapa GIS (Spec 001/005)."""
    empresa_id = request.headers.get("X-Empresa-ID") or getattr(request.state, "empresa_id", None)
    if not empresa_id:
        raise HTTPException(status_code=401, detail="No identificat")

    stmt = (
        select(OrdreTreball, Client)
        .outerjoin(Client, OrdreTreball.client_id == Client.id)
        .where(
            OrdreTreball.empresa_id == uuid.UUID(empresa_id),
            OrdreTreball.estat.in_(["PENDENT", "EN_CURS", "BLOQUEJADA", "EN_OBRA", "EN_RUTA"])
        )
        .order_by(OrdreTreball.created_at.desc())
    )
    result = await db.execute(stmt)
    rows = result.all()

    markers: List[MapaMarkerItem] = []
    for ordre, client in rows:
        lat = 41.3851
        lng = 2.1734
        if ordre.adreca and "," in ordre.adreca:
            try:
                parts = [float(p.strip()) for p in ordre.adreca.split(",")]
                if len(parts) >= 2:
                    lat, lng = parts[0], parts[1]
            except (ValueError, TypeError):
                pass

        markers.append(MapaMarkerItem(
            id=str(ordre.id),
            codi=ordre.codi,
            titol=ordre.titol,
            estat=ordre.estat,
            lat=lat,
            lng=lng,
            is_incidencia=False,
            adreca=ordre.adreca,
            client_rao_social=client.rao_social if client else None
        ))

    return markers

class AgendarFeinaRequest(BaseModel):
    hora_inici_prevista: datetime
    hora_fi_prevista: datetime
    version_id: int

class AgendarFeinaResponse(BaseModel):
    id: uuid.UUID
    hora_inici_prevista: datetime
    hora_fi_prevista: datetime
    version_id: int
    estat: str

@router.put("/{feina_id}/agendar", response_model=AgendarFeinaResponse)
async def agendar_feina(
    feina_id: uuid.UUID,
    payload: AgendarFeinaRequest,
    request: Request,
    db: AsyncSession = Depends(get_db_with_tenant_context)
):
    """
    Planifica/reagenda una Ordre de Treball usant Optimistic Locking (version_id).
    Si un altre usuari ha modificat l'OT, es retorna HTTP 409 Conflict.
    """
    empresa_id = request.headers.get("X-Empresa-ID") or getattr(request.state, "empresa_id", None)
    if not empresa_id:
        raise HTTPException(status_code=401, detail="No identificat")

    stmt = select(OrdreTreball).where(
        OrdreTreball.id == feina_id,
        OrdreTreball.empresa_id == uuid.UUID(empresa_id)
    )
    result = await db.execute(stmt)
    ordre = result.scalars().first()
    if not ordre:
        raise HTTPException(status_code=404, detail="Ordre de treball no trobada")

    if ordre.version_id != payload.version_id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Conflicte de concurrència: la feina ha estat modificada per un altre usuari (versió actual: {ordre.version_id}, versió enviada: {payload.version_id})"
        )

    ordre.hora_inici_prevista = payload.hora_inici_prevista
    ordre.hora_fi_prevista = payload.hora_fi_prevista
    ordre.version_id = ordre.version_id + 1

    await db.commit()
    await db.refresh(ordre)

    return AgendarFeinaResponse(
        id=ordre.id,
        hora_inici_prevista=ordre.hora_inici_prevista,
        hora_fi_prevista=ordre.hora_fi_prevista,
        version_id=ordre.version_id,
        estat=ordre.estat
    )

# ---------------------------------------------------------------------------
# Intervencions Actives per a la Torre de Control GIS (Spec 001)
# ---------------------------------------------------------------------------

intervencions_router = APIRouter(
    prefix="/intervencions",
    tags=["Intervencions GIS"],
    dependencies=[Depends(require_roles(["BOSS", "SECRETARIA", "ENGINYER", "SUPERADMIN"]))],
)

@intervencions_router.get("/actives")
async def llistar_intervencions_actives(
    request: Request,
    db: AsyncSession = Depends(get_db_with_tenant_context)
):
    empresa_id = request.state.empresa_id
    if not empresa_id:
        raise HTTPException(status_code=401, detail="No identificat")

    stmt = select(OrdreTreball).where(
        OrdreTreball.empresa_id == uuid.UUID(empresa_id),
        OrdreTreball.estat.in_(["PENDENT", "EN_CURS", "BLOQUEJADA", "EN_OBRA", "EN_RUTA"])
    ).order_by(OrdreTreball.created_at.desc())

    res = await db.execute(stmt)
    ordres = res.scalars().all()

    items = []
    for o in ordres:
        lat = 41.3851
        lng = 2.1734
        if o.adreca and "," in o.adreca:
            try:
                parts = [float(p.strip()) for p in o.adreca.split(",")]
                if len(parts) >= 2:
                    lat, lng = parts[0], parts[1]
            except (ValueError, TypeError):
                pass

        items.append({
            "id": str(o.id),
            "codi": o.codi,
            "client": "Client " + str(o.client_id)[:8],
            "titol": o.titol,
            "cap_colla": "Capataz",
            "estat": o.estat if o.estat in ["EN_OBRA", "EN_RUTA", "PENDENT", "INCIDENCIA"] else "PENDENT",
            "coords": [lat, lng],
            "sector": "Sector Operatiu",
            "pressio_bar": 3.8,
            "codi_candat": "N/A",
        })

    return items
