import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db_with_tenant_context
from app.core.security import get_current_user_claims, require_roles
from app.models.models import (
    Article,
    FullaPicking,
    LiniaPicking,
    Magatzem,
    OrdreTreball,
    OrdreTreballOperari,
)
from app.services.picking_stock_service import (
    actualitzar_linia_picking_amb_estoc,
    obtenir_estoc_furgoneta_operari,
    registrar_consum_material_furgoneta,
)

router = APIRouter(
    prefix="/operari/picking",
    tags=["Operari Picking"],
    dependencies=[Depends(require_roles(["OPERARI", "CAPATAZ", "CAP_DE_COLLA", "BOSS"]))],
)


class FullaPickingCreate(BaseModel):
    ordre_treball_id: uuid.UUID
    vehicle_id: Optional[uuid.UUID] = None


class FullaPickingResponse(BaseModel):
    id: uuid.UUID
    ordre_treball_id: uuid.UUID
    vehicle_id: Optional[uuid.UUID] = None
    estat_picking: str


class LiniaPickingCreate(BaseModel):
    article_id: uuid.UUID
    quantitat_prevista: float = Field(..., gt=0)


class LiniaPickingResponse(BaseModel):
    id: uuid.UUID
    article_id: uuid.UUID
    quantitat_prevista: float
    quantitat_carregada_pick_in: float
    quantitat_retornada_pick_out: float
    quantitat_mermada: float


@router.post("", response_model=FullaPickingResponse, status_code=status.HTTP_201_CREATED)
async def crear_fulla_picking_operari(
    request: Request,
    payload: FullaPickingCreate,
    db: AsyncSession = Depends(get_db_with_tenant_context),
):
    empresa_id = request.state.empresa_id
    if not empresa_id or empresa_id == "undefined":
        raise HTTPException(status_code=401, detail="Context d'empresa no trobat")

    ot_res = await db.execute(
        select(OrdreTreball).where(
            OrdreTreball.id == payload.ordre_treball_id,
            OrdreTreball.empresa_id == uuid.UUID(empresa_id),
        )
    )
    if not ot_res.scalars().first():
        raise HTTPException(status_code=404, detail="Ordre de treball no trobada")

    fulla = FullaPicking(
        empresa_id=uuid.UUID(empresa_id),
        ordre_treball_id=payload.ordre_treball_id,
        vehicle_id=payload.vehicle_id,
        estat_picking="PENDENT",
    )
    db.add(fulla)
    await db.commit()

    from app.services.sovereign_storage import SovereignStorageGateway

    await SovereignStorageGateway.desar_entitat_json(
        db=db,
        empresa_id=empresa_id,
        categoria="picking",
        item_id=str(fulla.id),
        dades={
            "id": str(fulla.id),
            "ordre_treball_id": str(fulla.ordre_treball_id),
            "vehicle_id": str(fulla.vehicle_id) if fulla.vehicle_id else None,
            "estat_picking": fulla.estat_picking,
        },
    )

    return FullaPickingResponse(
        id=fulla.id,
        ordre_treball_id=fulla.ordre_treball_id,
        vehicle_id=fulla.vehicle_id,
        estat_picking=fulla.estat_picking,
    )


@router.post(
    "/{picking_id}/linies", response_model=LiniaPickingResponse, status_code=status.HTTP_201_CREATED
)
async def afegir_linia_picking_operari(
    request: Request,
    picking_id: uuid.UUID,
    payload: LiniaPickingCreate,
    db: AsyncSession = Depends(get_db_with_tenant_context),
):
    empresa_id = request.state.empresa_id
    if not empresa_id or empresa_id == "undefined":
        raise HTTPException(status_code=401, detail="Context d'empresa no trobat")

    fulla_res = await db.execute(
        select(FullaPicking).where(
            FullaPicking.id == picking_id, FullaPicking.empresa_id == uuid.UUID(empresa_id)
        )
    )
    fulla = fulla_res.scalars().first()
    if not fulla:
        raise HTTPException(status_code=404, detail="Fulla de picking no trobada")

    linia = LiniaPicking(
        empresa_id=uuid.UUID(empresa_id),
        picking_id=picking_id,
        article_id=payload.article_id,
        quantitat_prevista=payload.quantitat_prevista,
        quantitat_carregada_pick_in=0.0,
        quantitat_retornada_pick_out=0.0,
        quantitat_mermada=0.0,
    )
    db.add(linia)
    await db.commit()

    return LiniaPickingResponse(
        id=linia.id,
        article_id=linia.article_id,
        quantitat_prevista=float(linia.quantitat_prevista),
        quantitat_carregada_pick_in=float(linia.quantitat_carregada_pick_in),
        quantitat_retornada_pick_out=float(linia.quantitat_retornada_pick_out),
        quantitat_mermada=float(linia.quantitat_mermada),
    )


class UpdateLiniaPickingRequest(BaseModel):
    quantitat_carregada_pick_in: Optional[float] = None
    quantitat_retornada_pick_out: Optional[float] = None
    quantitat_mermada: Optional[float] = None


class BalancLiniaResponse(BaseModel):
    id: uuid.UUID
    article_id: uuid.UUID
    quantitat_prevista: float
    quantitat_carregada_pick_in: float
    quantitat_retornada_pick_out: float
    quantitat_mermada: float
    consum_real: float  # Spec 013 RF-18: Consum Real = Pick In - Pick Out
    consum_aplicat_magatzem: float = 0.0
    origen_estoc: str = "NAU"
    estoc_actualitzat: bool = False


@router.put("/linies/{linia_id}", response_model=BalancLiniaResponse)
async def actualitzar_linia_picking_operari(
    request: Request,
    linia_id: uuid.UUID,
    payload: UpdateLiniaPickingRequest,
    db: AsyncSession = Depends(get_db_with_tenant_context),
    claims: dict = Depends(get_current_user_claims),
):
    empresa_id = request.state.empresa_id
    if not empresa_id or empresa_id == "undefined":
        raise HTTPException(status_code=401, detail="Context d'empresa no trobat")

    usuari_id: Optional[uuid.UUID] = None
    sub_raw = claims.get("sub") if claims else None
    if sub_raw:
        try:
            usuari_id = uuid.UUID(str(sub_raw))
        except ValueError:
            usuari_id = None

    res = await actualitzar_linia_picking_amb_estoc(
        db=db,
        empresa_id=uuid.UUID(empresa_id),
        linia_id=linia_id,
        usuari_id=usuari_id,
        quantitat_carregada_pick_in=payload.quantitat_carregada_pick_in,
        quantitat_retornada_pick_out=payload.quantitat_retornada_pick_out,
        quantitat_mermada=payload.quantitat_mermada,
    )
    return BalancLiniaResponse(**res)


class ConsumVehicleRequest(BaseModel):
    ordre_treball_id: uuid.UUID
    article_id: uuid.UUID
    quantitat: float = Field(..., gt=0)
    quantitat_mermada: float = Field(default=0.0, ge=0.0)
    magatzem_id: Optional[uuid.UUID] = None
    notes: Optional[str] = Field(default=None, max_length=300)


class ConsumVehicleResponse(BaseModel):
    linia_id: str
    picking_id: str
    ordre_treball_id: str
    article_id: str
    article_nom: str
    magatzem_id: str
    magatzem_nom: str
    origen_estoc: str
    quantitat_consumida: float
    quantitat_mermada: float
    estoc_restant_furgoneta: float


@router.get("/vehicle-stock")
async def llistar_estoc_furgoneta_ot(
    request: Request,
    ordre_treball_id: Optional[uuid.UUID] = None,
    db: AsyncSession = Depends(get_db_with_tenant_context),
    claims: dict = Depends(get_current_user_claims),
):
    """Retorna l'estoc real disponible al magatzem mòbil (FURGONETA) assignat a l'OT o operari."""
    empresa_id = request.state.empresa_id
    if not empresa_id or empresa_id == "undefined":
        raise HTTPException(status_code=401, detail="Context d'empresa no trobat")

    usuari_id: Optional[uuid.UUID] = None
    sub_raw = claims.get("sub") if claims else None
    if sub_raw:
        try:
            usuari_id = uuid.UUID(str(sub_raw))
        except ValueError:
            usuari_id = None

    return await obtenir_estoc_furgoneta_operari(
        db=db,
        empresa_id=uuid.UUID(empresa_id),
        ordre_treball_id=ordre_treball_id,
        usuari_id=usuari_id,
    )


@router.post(
    "/consum-vehicle",
    response_model=ConsumVehicleResponse,
    status_code=status.HTTP_201_CREATED,
)
async def consumir_material_furgoneta_ot(
    request: Request,
    payload: ConsumVehicleRequest,
    db: AsyncSession = Depends(get_db_with_tenant_context),
    claims: dict = Depends(get_current_user_claims),
):
    """Agafa material real del magatzem de la furgoneta, descompta estoc i el vincula a l'OT."""
    empresa_id = request.state.empresa_id
    if not empresa_id or empresa_id == "undefined":
        raise HTTPException(status_code=401, detail="Context d'empresa no trobat")

    usuari_id: Optional[uuid.UUID] = None
    sub_raw = claims.get("sub") if claims else None
    if sub_raw:
        try:
            usuari_id = uuid.UUID(str(sub_raw))
        except ValueError:
            usuari_id = None

    res = await registrar_consum_material_furgoneta(
        db=db,
        empresa_id=uuid.UUID(empresa_id),
        ordre_treball_id=payload.ordre_treball_id,
        article_id=payload.article_id,
        quantitat=payload.quantitat,
        quantitat_mermada=payload.quantitat_mermada,
        magatzem_id=payload.magatzem_id,
        usuari_id=usuari_id,
        notes=payload.notes,
        auto_commit=True,
    )
    # Sense camps monetaris per a l'operari (Barrera Econòmica)
    return ConsumVehicleResponse(
        linia_id=res["linia_id"],
        picking_id=res["picking_id"],
        ordre_treball_id=res["ordre_treball_id"],
        article_id=res["article_id"],
        article_nom=res["article_nom"],
        magatzem_id=res["magatzem_id"],
        magatzem_nom=res["magatzem_nom"],
        origen_estoc=res["origen_estoc"],
        quantitat_consumida=res["quantitat_consumida"],
        quantitat_mermada=res["quantitat_mermada"],
        estoc_restant_furgoneta=res["estoc_restant_furgoneta"],
    )


class MaterialOperariItemResponse(BaseModel):
    id: uuid.UUID
    ordre_treball_id: Optional[uuid.UUID] = None
    ordre_codi: Optional[str] = None
    article_id: Optional[uuid.UUID] = None
    nom: str
    referencia: str
    quantitat_programada: float
    quantitat_carregada_pick_in: float = 0.0
    unitat: str
    es_eina: bool = False
    format_continu: bool = False
    carregat_pick_in: bool = False
    retornat_pick_out: float = 0.0
    quantitat_mermada: float = 0.0
    origen_estoc: str = "NAU"
    magatzem_nom: Optional[str] = None


@router.get("/materials", response_model=List[MaterialOperariItemResponse])
async def llistar_materials_operari(
    request: Request,
    db: AsyncSession = Depends(get_db_with_tenant_context),
    ordre_treball_id: Optional[uuid.UUID] = None,
):
    """Llista els materials i línies de picking programades per a la jornada o OT concreta de l'operari."""
    empresa_id = request.state.empresa_id
    if not empresa_id or empresa_id == "undefined":
        raise HTTPException(status_code=401, detail="Context d'empresa no trobat")
    emp_uuid = uuid.UUID(empresa_id)

    stmt = (
        select(LiniaPicking, Article, FullaPicking, OrdreTreball, Magatzem)
        .join(Article, LiniaPicking.article_id == Article.id)
        .join(FullaPicking, LiniaPicking.picking_id == FullaPicking.id)
        .join(OrdreTreball, FullaPicking.ordre_treball_id == OrdreTreball.id)
        .outerjoin(Magatzem, LiniaPicking.magatzem_id == Magatzem.id)
        .where(LiniaPicking.empresa_id == emp_uuid)
    )
    if ordre_treball_id is not None:
        stmt = stmt.where(FullaPicking.ordre_treball_id == ordre_treball_id)
    else:
        user_id_raw = getattr(request.state, "user_id", None)
        if user_id_raw:
            try:
                user_uuid = uuid.UUID(str(user_id_raw))
                colla_ot_ids = (
                    select(OrdreTreballOperari.ordre_treball_id).where(
                        OrdreTreballOperari.empresa_id == emp_uuid,
                        OrdreTreballOperari.operari_id == user_uuid,
                    )
                )
                stmt = stmt.where(
                    or_(
                        OrdreTreball.cap_de_colla_id == user_uuid,
                        OrdreTreball.id.in_(colla_ot_ids),
                        OrdreTreball.cap_de_colla_id.is_(None),
                    )
                )
            except (ValueError, TypeError):
                pass

    stmt = stmt.order_by(LiniaPicking.created_at.asc())
    result = await db.execute(stmt)
    items = []
    for lin, art, _fp, ot, mag in result.all():
        q_prev = float(lin.quantitat_prevista or 0.0)
        q_carr = float(lin.quantitat_carregada_pick_in or 0.0)
        q_ret = float(lin.quantitat_retornada_pick_out or 0.0)
        q_merma = float(lin.quantitat_mermada or 0.0)
        origen = str(getattr(lin, "origen_estoc", "NAU") or "NAU").upper()
        items.append(
            MaterialOperariItemResponse(
                id=lin.id,
                ordre_treball_id=ot.id,
                ordre_codi=ot.codi,
                article_id=art.id,
                nom=art.nom,
                referencia=art.referencia_inventari,
                quantitat_programada=q_prev,
                quantitat_carregada_pick_in=q_carr,
                unitat=art.unitat_mesura or "UNITAT",
                es_eina=(getattr(art, "familia", "") == "EINES"),
                format_continu=bool(getattr(art, "es_material_continu", False)),
                carregat_pick_in=(q_carr >= q_prev and q_prev > 0) or (origen == "FURGONETA" and q_carr > 0),
                retornat_pick_out=q_ret,
                quantitat_mermada=q_merma,
                origen_estoc=origen,
                magatzem_nom=mag.nom if mag else None,
            )
        )
    return items


materials_operari_router = APIRouter(
    prefix="/materials",
    tags=["Operari Materials"],
    dependencies=[
        Depends(require_roles(["OPERARI", "CAPATAZ", "CAP_DE_COLLA", "BOSS", "SUPERADMIN"]))
    ],
)


@materials_operari_router.get("/operari", response_model=List[MaterialOperariItemResponse])
async def llistar_materials_operari_direct(
    request: Request,
    ordre_treball_id: Optional[uuid.UUID] = None,
    db: AsyncSession = Depends(get_db_with_tenant_context),
):
    """Endpoint directe /api/v1/materials/operari per a compatibilitat total PWA."""
    return await llistar_materials_operari(request, db, ordre_treball_id=ordre_treball_id)

