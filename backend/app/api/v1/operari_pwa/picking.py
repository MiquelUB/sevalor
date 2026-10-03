import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db_with_tenant_context
from app.core.security import require_roles
from app.models.models import Article, FullaPicking, LiniaPicking, OrdreTreball

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


@router.put("/linies/{linia_id}", response_model=BalancLiniaResponse)
async def actualitzar_linia_picking_operari(
    request: Request,
    linia_id: uuid.UUID,
    payload: UpdateLiniaPickingRequest,
    db: AsyncSession = Depends(get_db_with_tenant_context),
):
    empresa_id = request.state.empresa_id
    if not empresa_id or empresa_id == "undefined":
        raise HTTPException(status_code=401, detail="Context d'empresa no trobat")

    linia_res = await db.execute(
        select(LiniaPicking).where(
            LiniaPicking.id == linia_id, LiniaPicking.empresa_id == uuid.UUID(empresa_id)
        )
    )
    linia = linia_res.scalars().first()
    if not linia:
        raise HTTPException(status_code=404, detail="Línia de picking no trobada")

    if payload.quantitat_carregada_pick_in is not None:
        linia.quantitat_carregada_pick_in = payload.quantitat_carregada_pick_in
    if payload.quantitat_retornada_pick_out is not None:
        linia.quantitat_retornada_pick_out = payload.quantitat_retornada_pick_out
    if payload.quantitat_mermada is not None:
        linia.quantitat_mermada = payload.quantitat_mermada

    await db.commit()

    pick_in = float(linia.quantitat_carregada_pick_in or 0.0)
    pick_out = float(linia.quantitat_retornada_pick_out or 0.0)
    consum_real = max(0.0, pick_in - pick_out)

    return BalancLiniaResponse(
        id=linia.id,
        article_id=linia.article_id,
        quantitat_prevista=float(linia.quantitat_prevista),
        quantitat_carregada_pick_in=pick_in,
        quantitat_retornada_pick_out=pick_out,
        quantitat_mermada=float(linia.quantitat_mermada or 0.0),
        consum_real=consum_real,
    )


class MaterialOperariItemResponse(BaseModel):
    id: uuid.UUID
    nom: str
    referencia: str
    quantitat_programada: float
    unitat: str
    es_eina: bool = False
    format_continu: bool = False
    carregat_pick_in: bool = False
    retornat_pick_out: float = 0.0


@router.get("/materials", response_model=List[MaterialOperariItemResponse])
async def llistar_materials_operari(
    request: Request,
    db: AsyncSession = Depends(get_db_with_tenant_context),
):
    """Llista els materials i línies de picking programades per a la jornada de l'operari."""
    empresa_id = request.state.empresa_id
    if not empresa_id or empresa_id == "undefined":
        raise HTTPException(status_code=401, detail="Context d'empresa no trobat")

    stmt = (
        select(LiniaPicking, Article)
        .join(Article, LiniaPicking.article_id == Article.id)
        .where(LiniaPicking.empresa_id == uuid.UUID(empresa_id))
    )
    result = await db.execute(stmt)
    items = []
    for lin, art in result.all():
        q_prev = float(lin.quantitat_prevista or 0.0)
        q_carr = float(lin.quantitat_carregada_pick_in or 0.0)
        q_ret = float(lin.quantitat_retornada_pick_out or 0.0)
        items.append(
            MaterialOperariItemResponse(
                id=lin.id,
                nom=art.nom,
                referencia=art.referencia_inventari,
                quantitat_programada=q_prev,
                unitat=art.unitat_mesura or "UNITAT",
                es_eina=(getattr(art, "familia", "") == "EINES"),
                format_continu=bool(getattr(art, "es_material_continu", False)),
                carregat_pick_in=(q_carr >= q_prev and q_prev > 0),
                retornat_pick_out=q_ret,
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
    db: AsyncSession = Depends(get_db_with_tenant_context),
):
    """Endpoint directe /api/v1/materials/operari per a compatibilitat total PWA."""
    return await llistar_materials_operari(request, db)

