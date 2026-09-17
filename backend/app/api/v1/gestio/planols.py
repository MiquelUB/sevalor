import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_
from pydantic import BaseModel, Field

from app.core.db import get_db_with_tenant_context
from app.core.security import require_roles
from app.models.models import PlanolBase, CarpetaPlanol, CapaVectorial

router = APIRouter(
    prefix="/gestio/planols",
    tags=["Gestió Plànols"],
    dependencies=[Depends(require_roles(["BOSS", "SECRETARIA", "ENGINYER"]))],
)

class PlanolCreate(BaseModel):
    titol: str = Field(..., max_length=150)
    codi_referencia: str = Field(..., max_length=50)
    carpeta_id: uuid.UUID
    tipus_fitxer: str = Field(..., max_length=20)
    fitxer_path: str = Field("/docs/planols/default.dxf", max_length=500)
    mida_bytes: int = Field(0)
    es_georeferenciat: bool = Field(False)

class PlanolResponse(PlanolCreate):
    id: uuid.UUID

class CarpetaCreate(BaseModel):
    nom: str = Field(..., max_length=100)
    categoria: str = Field("CLIENTS", max_length=30)
    client_id: Optional[uuid.UUID] = None
    municipi: Optional[str] = Field(None, max_length=100)
    descripcio: Optional[str] = None
    parent_id: Optional[uuid.UUID] = None

class CarpetaResponse(BaseModel):
    id: uuid.UUID
    nom: str
    categoria: str
    client_id: Optional[uuid.UUID]
    municipi: Optional[str]

class CapaVectorialCreate(BaseModel):
    planol_base_id: uuid.UUID
    nom: str = Field(..., max_length=100)
    disciplina: str = Field("OBRA_CIVIL", max_length=30)
    ordre_treball_id: Optional[uuid.UUID] = None
    color_hex: str = Field("#2563eb", max_length=10)
    gruix_linia: int = 2
    opacitat_percent: int = 100
    geometries_geojson: dict = Field(default_factory=dict)

class CapaVectorialResponse(BaseModel):
    id: uuid.UUID
    nom: str
    disciplina: str
    es_immutable: bool
    version_id: int
    color_hex: str

@router.get("", response_model=List[PlanolResponse])
async def llistar_planols(
    request: Request,
    carpeta_id: Optional[uuid.UUID] = None,
    q: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    db: AsyncSession = Depends(get_db_with_tenant_context)
):
    empresa_id = request.state.empresa_id
    if not empresa_id:
        raise HTTPException(status_code=401, detail="No identificat")
        
    stmt = select(PlanolBase).where(PlanolBase.empresa_id == uuid.UUID(empresa_id))
    
    if carpeta_id:
        stmt = stmt.where(PlanolBase.carpeta_id == carpeta_id)
        
    if q:
        search_term = f"%{q}%"
        stmt = stmt.where(
            or_(
                PlanolBase.codi_referencia.ilike(search_term),
                PlanolBase.titol.ilike(search_term)
            )
        )
        
    stmt = stmt.limit(limit).offset(offset).order_by(PlanolBase.created_at.desc())
    
    result = await db.execute(stmt)
    planols = result.scalars().all()
    
    return planols

@router.post("", response_model=PlanolResponse, status_code=status.HTTP_201_CREATED)
async def alta_planol(
    request: Request,
    planol: PlanolCreate,
    db: AsyncSession = Depends(get_db_with_tenant_context)
):
    empresa_id = request.state.empresa_id
    if not empresa_id:
        raise HTTPException(status_code=401, detail="No identificat")
        
    # Comprovem que la carpeta existeix i pertany a l'empresa
    stmt_carp = select(CarpetaPlanol).where(
        CarpetaPlanol.id == planol.carpeta_id,
        CarpetaPlanol.empresa_id == uuid.UUID(empresa_id)
    )
    res_carp = await db.execute(stmt_carp)
    if not res_carp.scalars().first():
        raise HTTPException(status_code=400, detail="Carpeta no vàlida o no pertany a l'empresa")

    stmt_codi = select(PlanolBase).where(
        PlanolBase.empresa_id == uuid.UUID(empresa_id),
        PlanolBase.codi_referencia == planol.codi_referencia
    )
    result_codi = await db.execute(stmt_codi)
    if result_codi.scalars().first():
        raise HTTPException(status_code=400, detail="El codi de plànol ja es troba registrat")

    nou_planol = PlanolBase(
        empresa_id=uuid.UUID(empresa_id),
        titol=planol.titol,
        codi_referencia=planol.codi_referencia,
        carpeta_id=planol.carpeta_id,
        tipus_fitxer=planol.tipus_fitxer,
        fitxer_path=planol.fitxer_path,
        mida_bytes=planol.mida_bytes,
        es_georeferenciat=planol.es_georeferenciat
    )
    
    db.add(nou_planol)
    await db.commit()

    return nou_planol


# ---------------------------------------------------------------------------
# Carpetes de plànols (Spec 010)
# ---------------------------------------------------------------------------

@router.get("/carpetes", response_model=List[CarpetaResponse])
async def llistar_carpetes(
    request: Request,
    db: AsyncSession = Depends(get_db_with_tenant_context)
):
    """Llista les carpetes de plànols de l'empresa (Spec 010)."""
    empresa_id = request.state.empresa_id
    if not empresa_id:
        raise HTTPException(status_code=401, detail="No identificat")

    result = await db.execute(
        select(CarpetaPlanol).where(CarpetaPlanol.empresa_id == uuid.UUID(empresa_id)).order_by(CarpetaPlanol.nom)
    )
    return result.scalars().all()


@router.post("/carpetes", response_model=CarpetaResponse, status_code=status.HTTP_201_CREATED)
async def crear_carpeta(
    request: Request,
    payload: CarpetaCreate,
    db: AsyncSession = Depends(get_db_with_tenant_context)
):
    """Crea una carpeta de plànols (Spec 010)."""
    empresa_id = request.state.empresa_id
    if not empresa_id:
        raise HTTPException(status_code=401, detail="No identificat")

    nova = CarpetaPlanol(
        empresa_id=uuid.UUID(empresa_id),
        nom=payload.nom,
        categoria=payload.categoria,
        client_id=payload.client_id,
        municipi=payload.municipi,
        descripcio=payload.descripcio,
        parent_id=payload.parent_id,
    )
    db.add(nova)
    await db.commit()
    return nova


# ---------------------------------------------------------------------------
# Capes vectorials (Spec 010 — gestió de capes per plànol)
# ---------------------------------------------------------------------------

@router.get("/planols/{planol_id}/capes", response_model=List[CapaVectorialResponse])
async def llistar_capes_planol(
    request: Request,
    planol_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_with_tenant_context)
):
    """Llista les capes vectorials d'un plànol (Spec 010)."""
    empresa_id = request.state.empresa_id
    if not empresa_id:
        raise HTTPException(status_code=401, detail="No identificat")

    result = await db.execute(
        select(CapaVectorial).where(
            CapaVectorial.planol_base_id == planol_id,
            CapaVectorial.empresa_id == uuid.UUID(empresa_id),
        )
    )
    return result.scalars().all()


@router.post("/planols/{planol_id}/capes", response_model=CapaVectorialResponse, status_code=status.HTTP_201_CREATED)
async def crear_capa_planol(
    request: Request,
    planol_id: uuid.UUID,
    payload: CapaVectorialCreate,
    db: AsyncSession = Depends(get_db_with_tenant_context)
):
    """Crea una capa vectorial sobre un plànol (Spec 010)."""
    empresa_id = request.state.empresa_id
    if not empresa_id:
        raise HTTPException(status_code=401, detail="No identificat")

    # Verificar que el plànol pertany a l'empresa
    planol_res = await db.execute(select(PlanolBase).where(
        PlanolBase.id == planol_id,
        PlanolBase.empresa_id == uuid.UUID(empresa_id),
    ))
    if not planol_res.scalars().first():
        raise HTTPException(status_code=404, detail="Plànol no trobat")

    nova_capa = CapaVectorial(
        empresa_id=uuid.UUID(empresa_id),
        planol_base_id=planol_id,
        nom=payload.nom,
        disciplina=payload.disciplina,
        ordre_treball_id=payload.ordre_treball_id,
        color_hex=payload.color_hex,
        gruix_linia=payload.gruix_linia,
        opacitat_percent=payload.opacitat_percent,
        geometries_geojson=payload.geometries_geojson,
        version_id=1,
    )
    db.add(nova_capa)
    await db.commit()
    return nova_capa


class CapaVectorialUpdate(BaseModel):
    nom: Optional[str] = Field(None, max_length=100)
    color_hex: Optional[str] = Field(None, max_length=10)
    gruix_linia: Optional[int] = None
    opacitat_percent: Optional[int] = None
    visible: Optional[bool] = None
    geometries_geojson: Optional[dict] = None


@router.put("/planols/{planol_id}/capes/{capa_id}", response_model=CapaVectorialResponse)
async def editar_capa_planol(
    request: Request,
    planol_id: uuid.UUID,
    capa_id: uuid.UUID,
    payload: CapaVectorialUpdate,
    db: AsyncSession = Depends(get_db_with_tenant_context)
):
    """Edita una capa vectorial d'un plànol (Spec 010). Les capes immutables no es poden editar."""
    empresa_id = request.state.empresa_id
    if not empresa_id:
        raise HTTPException(status_code=401, detail="No identificat")

    capa_res = await db.execute(select(CapaVectorial).where(
        CapaVectorial.id == capa_id,
        CapaVectorial.planol_base_id == planol_id,
        CapaVectorial.empresa_id == uuid.UUID(empresa_id),
    ))
    capa = capa_res.scalars().first()
    if not capa:
        raise HTTPException(status_code=404, detail="Capa no trobada")

    if capa.es_immutable:
        raise HTTPException(status_code=403, detail="La capa és immutable i no es pot modificar")

    if payload.nom is not None:
        capa.nom = payload.nom
    if payload.color_hex is not None:
        capa.color_hex = payload.color_hex
    if payload.gruix_linia is not None:
        capa.gruix_linia = payload.gruix_linia
    if payload.opacitat_percent is not None:
        capa.opacitat_percent = payload.opacitat_percent
    if payload.visible is not None:
        capa.visible = payload.visible
    if payload.geometries_geojson is not None:
        capa.geometries_geojson = payload.geometries_geojson

    capa.version_id += 1
    await db.commit()
    return capa


@router.delete("/planols/{planol_id}/capes/{capa_id}", status_code=status.HTTP_204_NO_CONTENT)
async def eliminar_capa_planol(
    request: Request,
    planol_id: uuid.UUID,
    capa_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_with_tenant_context)
):
    """Elimina una capa vectorial (Spec 010). Les immutables no es poden eliminar."""
    empresa_id = request.state.empresa_id
    if not empresa_id:
        raise HTTPException(status_code=401, detail="No identificat")

    capa_res = await db.execute(select(CapaVectorial).where(
        CapaVectorial.id == capa_id,
        CapaVectorial.planol_base_id == planol_id,
        CapaVectorial.empresa_id == uuid.UUID(empresa_id),
    ))
    capa = capa_res.scalars().first()
    if not capa:
        raise HTTPException(status_code=404, detail="Capa no trobada")

    if capa.es_immutable:
        raise HTTPException(status_code=403, detail="La capa és immutable i no es pot eliminar")

    await db.delete(capa)
    await db.commit()
    return None
