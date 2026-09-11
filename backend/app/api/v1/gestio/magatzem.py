import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_, text
from pydantic import BaseModel, Field

from app.core.db import get_db_with_tenant_context
from app.core.security import require_roles
from app.models.models import Article, Magatzem, EstocMagatzem, FullaPicking, LiniaPicking, OrdreTreball

router = APIRouter(
    prefix="/gestio/magatzem",
    tags=["Gestió Magatzem"],
    dependencies=[Depends(require_roles(["BOSS", "SECRETARIA", "ENGINYER"]))],
)

class ArticleCreate(BaseModel):
    referencia_inventari: str = Field(..., max_length=50)
    nom: str = Field(..., max_length=150)
    unitat_mesura: str = Field("UNITAT", max_length=30)
    familia: str = Field("GENERAL", max_length=50)
    estoc_optim: float = Field(0.0)
    estoc_minim: float = Field(0.0)
    es_lot_caducable: bool = Field(False)
    preu_cost: float = Field(0.0)
    preu_venda: float = Field(0.0)

class ArticleResponse(ArticleCreate):
    id: uuid.UUID
    actiu: bool

# ---------------------------------------------------------------------------
# Estoc de magatzem (Spec 004 — gestió multimagatzem amb bloqueig pessimista)
# ---------------------------------------------------------------------------

class MovimentEstocRequest(BaseModel):
    article_id: uuid.UUID
    quantitat: float = Field(..., gt=0, description="Quantitat positiva (entrada o sortida segons 'tipus')")
    tipus: str = Field("ENTRADA", pattern="^(ENTRADA|SORTIDA|RESERVA)$")
    ubicacio_passadis: Optional[str] = Field(None, max_length=50)

class EstocResponse(BaseModel):
    article_id: uuid.UUID
    referencia_article: Optional[str] = None
    quantitat_fisica: float
    quantitat_virtual_reservada: float
    quantitat_disponible: float
    ubicacio_passadis: Optional[str]

@router.get("/articles", response_model=List[ArticleResponse])
async def llistar_articles(
    request: Request,
    q: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    db: AsyncSession = Depends(get_db_with_tenant_context)
):
    empresa_id = request.state.empresa_id
    if not empresa_id:
        raise HTTPException(status_code=401, detail="No identificat")
        
    stmt = select(Article).where(Article.empresa_id == uuid.UUID(empresa_id))
    
    if q:
        search_term = f"%{q}%"
        stmt = stmt.where(
            or_(
                Article.referencia_inventari.ilike(search_term),
                Article.nom.ilike(search_term)
            )
        )
        
    stmt = stmt.limit(limit).offset(offset).order_by(Article.created_at.desc())
    
    result = await db.execute(stmt)
    articles = result.scalars().all()
    
    return articles

@router.post("/articles", response_model=ArticleResponse, status_code=status.HTTP_201_CREATED)
async def alta_article(
    request: Request,
    article: ArticleCreate,
    db: AsyncSession = Depends(get_db_with_tenant_context)
):
    empresa_id = request.state.empresa_id
    if not empresa_id:
        raise HTTPException(status_code=401, detail="No identificat")
        
    stmt_ref = select(Article).where(Article.empresa_id == uuid.UUID(empresa_id), Article.referencia_inventari == article.referencia_inventari)
    result_ref = await db.execute(stmt_ref)
    if result_ref.scalars().first():
        raise HTTPException(status_code=400, detail="La referència ja es troba registrada")

    nou_article = Article(
        empresa_id=uuid.UUID(empresa_id),
        referencia_inventari=article.referencia_inventari,
        nom=article.nom,
        unitat_mesura=article.unitat_mesura,
        familia=article.familia,
        estoc_optim=article.estoc_optim,
        estoc_minim=article.estoc_minim,
        es_lot_caducable=article.es_lot_caducable,
        preu_cost=article.preu_cost,
        preu_venda=article.preu_venda
    )
    
    db.add(nou_article)
    await db.commit()

    return nou_article


@router.get("/magatzems/{magatzem_id}/estoc", response_model=List[EstocResponse])
async def llistar_estoc_magatzem(
    request: Request,
    magatzem_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_with_tenant_context)
):
    """Llista l'estoc d'un magatzem (Spec 004)."""
    empresa_id = request.state.empresa_id
    if not empresa_id:
        raise HTTPException(status_code=401, detail="No identificat")

    mag_res = await db.execute(select(Magatzem).where(
        Magatzem.id == magatzem_id, Magatzem.empresa_id == uuid.UUID(empresa_id)
    ))
    if not mag_res.scalars().first():
        raise HTTPException(status_code=404, detail="Magatzem no trobat")

    q = select(EstocMagatzem, Article).join(
        Article, Article.id == EstocMagatzem.article_id
    ).where(
        EstocMagatzem.magatzem_id == magatzem_id,
        EstocMagatzem.empresa_id == uuid.UUID(empresa_id),
    )
    res = await db.execute(q)
    resultats = []
    for estoc, article in res.all():
        resultats.append({
            "article_id": estoc.article_id,
            "referencia_article": article.referencia_inventari,
            "quantitat_fisica": float(estoc.quantitat_fisica),
            "quantitat_virtual_reservada": float(estoc.quantitat_virtual_reservada),
            "quantitat_disponible": float(estoc.quantitat_fisica) - float(estoc.quantitat_virtual_reservada),
            "ubicacio_passadis": estoc.ubicacio_passadis,
        })
    return resultats


@router.post("/magatzems/{magatzem_id}/moviment", response_model=EstocResponse, status_code=status.HTTP_200_OK)
async def registrar_moviment_estoc(
    request: Request,
    magatzem_id: uuid.UUID,
    payload: MovimentEstocRequest,
    db: AsyncSession = Depends(get_db_with_tenant_context)
):
    """Registra un moviment d'estoc (entrada/sortida/reserva) amb bloqueig pessimista (SELECT FOR UPDATE).

    Spec 004: prevenció de condicions de carrera. Un SELECT FOR UPDATE sobre
    la fila d'estoc garanteix que dos enginyers no puguin reservar el mateix
    stock concurrentment.
    """
    empresa_id = request.state.empresa_id
    if not empresa_id:
        raise HTTPException(status_code=401, detail="No identificat")

    # Verificar article pertany a l'empresa
    art_res = await db.execute(select(Article).where(
        Article.id == payload.article_id, Article.empresa_id == uuid.UUID(empresa_id)
    ))
    if not art_res.scalars().first():
        raise HTTPException(status_code=404, detail="Article no trobat")

    # Verificar magatzem de l'empresa
    mag_res = await db.execute(select(Magatzem).where(
        Magatzem.id == magatzem_id, Magatzem.empresa_id == uuid.UUID(empresa_id)
    ))
    if not mag_res.scalars().first():
        raise HTTPException(status_code=404, detail="Magatzem no trobat")

    # Cercar estoc existent (amb FOR UPDATE per blocar la fila)
    estoc_res = await db.execute(
        select(EstocMagatzem).where(
            EstocMagatzem.empresa_id == uuid.UUID(empresa_id),
            EstocMagatzem.article_id == payload.article_id,
            EstocMagatzem.magatzem_id == magatzem_id,
        ).with_for_update()
    )
    estoc = estoc_res.scalars().first()

    if estoc is None:
        estoc = EstocMagatzem(
            empresa_id=uuid.UUID(empresa_id),
            article_id=payload.article_id,
            magatzem_id=magatzem_id,
            quantitat_fisica=0.0,
            quantitat_virtual_reservada=0.0,
            ubicacio_passadis=payload.ubicacio_passadis,
        )
        db.add(estoc)

    quantitat = payload.quantitat

    if payload.tipus == "ENTRADA":
        estoc.quantitat_fisica = float(estoc.quantitat_fisica) + quantitat
    elif payload.tipus == "SORTIDA":
        disponible = float(estoc.quantitat_fisica) - float(estoc.quantitat_virtual_reservada)
        if quantitat > disponible:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Stock insuficient: disponible {disponible}, sol·licitat {quantitat}",
            )
        estoc.quantitat_fisica = float(estoc.quantitat_fisica) - quantitat
    elif payload.tipus == "RESERVA":
        disponible = float(estoc.quantitat_fisica) - float(estoc.quantitat_virtual_reservada)
        if quantitat > disponible:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Stock virtual insuficient per reservar: disponible {disponible}",
            )
        estoc.quantitat_virtual_reservada = float(estoc.quantitat_virtual_reservada) + quantitat

    await db.commit()

    return {
        "article_id": estoc.article_id,
        "quantitat_fisica": float(estoc.quantitat_fisica),
        "quantitat_virtual_reservada": float(estoc.quantitat_virtual_reservada),
        "quantitat_disponible": float(estoc.quantitat_fisica) - float(estoc.quantitat_virtual_reservada),
        "ubicacio_passadis": estoc.ubicacio_passadis,
    }


# ---------------------------------------------------------------------------
# Picking matinal (Spec 004 RF-17 a RF-24)
# ---------------------------------------------------------------------------

class FullaPickingCreate(BaseModel):
    ordre_treball_id: uuid.UUID
    vehicle_id: Optional[uuid.UUID] = None


class FullaPickingResponse(BaseModel):
    id: uuid.UUID
    ordre_treball_id: uuid.UUID
    vehicle_id: Optional[uuid.UUID]
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


@router.post("/picking", response_model=FullaPickingResponse, status_code=status.HTTP_201_CREATED)
async def crear_fulla_picking(
    request: Request,
    payload: FullaPickingCreate,
    db: AsyncSession = Depends(get_db_with_tenant_context)
):
    """Crea una fulla de picking per a una ordre de treball (RF-20: 1 tasca = 1 fulla)."""
    empresa_id = request.state.empresa_id
    if not empresa_id:
        raise HTTPException(status_code=401)

    # Verificar que l'ordre de treball pertany a l'empresa
    ot_res = await db.execute(select(OrdreTreball).where(
        OrdreTreball.id == payload.ordre_treball_id,
        OrdreTreball.empresa_id == uuid.UUID(empresa_id),
    ))
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

    return {
        "id": fulla.id,
        "ordre_treball_id": fulla.ordre_treball_id,
        "vehicle_id": fulla.vehicle_id,
        "estat_picking": fulla.estat_picking,
    }


@router.post("/picking/{picking_id}/linies", response_model=LiniaPickingResponse, status_code=status.HTTP_201_CREATED)
async def afegir_linia_picking(
    request: Request,
    picking_id: uuid.UUID,
    payload: LiniaPickingCreate,
    db: AsyncSession = Depends(get_db_with_tenant_context)
):
    """Afegeix una línia de picking a una fulla (RF-17: reserva amb SELECT FOR UPDATE)."""
    empresa_id = request.state.empresa_id
    if not empresa_id:
        raise HTTPException(status_code=401)

    # Verificar fulla
    fulla_res = await db.execute(select(FullaPicking).where(
        FullaPicking.id == picking_id,
        FullaPicking.empresa_id == uuid.UUID(empresa_id),
    ))
    fulla = fulla_res.scalars().first()
    if not fulla:
        raise HTTPException(status_code=404, detail="Fulla de picking no trobada")

    # Bloqueig pessimista sobre l'estoc per evitar condicions de carrera
    estoc_res = await db.execute(
        select(EstocMagatzem).where(
            EstocMagatzem.empresa_id == uuid.UUID(empresa_id),
            EstocMagatzem.article_id == payload.article_id,
        ).with_for_update()
    )
    estoc = estoc_res.scalars().first()
    if estoc:
        disponible = float(estoc.quantitat_fisica) - float(estoc.quantitat_virtual_reservada)
        if payload.quantitat_prevista > disponible:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Stock insuficient per a l'article. Necessitat: {payload.quantitat_prevista}, Disponible: {disponible}",
            )
        estoc.quantitat_virtual_reservada = float(estoc.quantitat_virtual_reservada) + payload.quantitat_prevista
    else:
        raise HTTPException(status_code=422, detail="Article sense estoc al magatzem")

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

    return {
        "id": linia.id,
        "article_id": linia.article_id,
        "quantitat_prevista": float(linia.quantitat_prevista),
        "quantitat_carregada_pick_in": float(linia.quantitat_carregada_pick_in),
        "quantitat_retornada_pick_out": float(linia.quantitat_retornada_pick_out),
        "quantitat_mermada": float(linia.quantitat_mermada),
    }


@router.put("/picking/linies/{linia_id}/pick-in", response_model=LiniaPickingResponse)
async def confirmar_pick_in(
    request: Request,
    linia_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_with_tenant_context)
):
    """Confirma la recollida de material (pick-in) des de la PWA (RF-23)."""
    empresa_id = request.state.empresa_id
    if not empresa_id:
        raise HTTPException(status_code=401)

    linia_res = await db.execute(select(LiniaPicking).where(
        LiniaPicking.id == linia_id,
        LiniaPicking.empresa_id == uuid.UUID(empresa_id),
    ))
    linia = linia_res.scalars().first()
    if not linia:
        raise HTTPException(status_code=404, detail="Línia de picking no trobada")

    if linia.quantitat_carregada_pick_in > 0:
        raise HTTPException(status_code=400, detail="Pick-in ja confirmat anteriorment")

    linia.quantitat_carregada_pick_in = float(linia.quantitat_prevista)
    await db.commit()

    return linia


@router.put("/picking/linies/{linia_id}/pick-out", response_model=LiniaPickingResponse)
async def confirmar_devolucio(
    request: Request,
    linia_id: uuid.UUID,
    quantitat_retornada: float = 0.0,
    quantitat_mermada: float = 0.0,
    db: AsyncSession = Depends(get_db_with_tenant_context)
):
    """Registra la devolució de sobrants i mermes (RF-22: pick-out post-obra)."""
    empresa_id = request.state.empresa_id
    if not empresa_id:
        raise HTTPException(status_code=401)

    linia_res = await db.execute(select(LiniaPicking).where(
        LiniaPicking.id == linia_id,
        LiniaPicking.empresa_id == uuid.UUID(empresa_id),
    ))
    linia = linia_res.scalars().first()
    if not linia:
        raise HTTPException(status_code=404, detail="Línia de picking no trobada")

    linia.quantitat_retornada_pick_out = quantitat_retornada
    linia.quantitat_mermada = quantitat_mermada

    # Reintegrar els sobrants a l'estoc físic (restar la reserva virtual)
    estoc_res = await db.execute(
        select(EstocMagatzem).where(
            EstocMagatzem.empresa_id == uuid.UUID(empresa_id),
            EstocMagatzem.article_id == linia.article_id,
        ).with_for_update()
    )
    estoc = estoc_res.scalars().first()
    if estoc:
        estoc.quantitat_virtual_reservada = float(estoc.quantitat_virtual_reservada) - float(linia.quantitat_prevista)
        estoc.quantitat_fisica = float(estoc.quantitat_fisica) - quantitat_mermada

    await db.commit()
    return linia
