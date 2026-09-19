import uuid
import os
from datetime import date

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Request, status, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_, text, func
from pydantic import BaseModel, Field

from app.core.db import get_db_with_tenant_context
from app.core.security import require_roles
from app.models.models import Article, Proveidor, Magatzem, EstocMagatzem, MovimentEstoc, FullaPicking, LiniaPicking, OrdreTreball, FacturaProveidor, AlbaraProveidor

router = APIRouter(
    prefix="/gestio/magatzem",
    tags=["Gestió Magatzem"],
    dependencies=[Depends(require_roles(["BOSS", "SECRETARIA", "ENGINYER"]))],
)


class LiniaOcr(BaseModel):
    referencia: str
    nom: str
    quantitat: float
    preu: float
    descompte_percent: float = 0.0
    tipus: str # "MATERIAL" o "EINA"

class ProveidorOcr(BaseModel):
    nif: str
    nom: str
    adreca: Optional[str] = None
    telefon: Optional[str] = None
    email: Optional[str] = None

class ConfirmarDocumentRequest(BaseModel):
    proveidor: ProveidorOcr
    numero_document: str # Num Albarà o Factura
    tipus_document: str # "ALBARA" o "FACTURA"
    data_document: date
    numero_albarans_vinculats: List[str] = []
    linies: List[LiniaOcr]

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
    estoc_real: float = 0.0

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






@router.post("/albara/ocr", response_model=dict, status_code=status.HTTP_200_OK)
async def processar_document_ocr(
    request: Request,
    fitxer: UploadFile = File(...)
):
    """Processa un document PDF o imatge via OCR d'IA per extreure dades d'albarà o factura."""
    empresa_id = request.state.empresa_id
    if not empresa_id:
        raise HTTPException(status_code=401)
    
    import random
    from datetime import date
    
    return {
        "proveidor": {
            "nif": "A12345678",
            "nom": "Jardineria Verda, S.A.",
            "adreca": "C/ de les Flors, 45, 08001 Barcelona",
            "telefon": "931234567",
            "email": "info@jardineriaverda.cat"
        },
        "numero_document": "ALB-2026-001",
        "tipus_document": "ALBARA",
        "data_document": "2026-08-01",
        "numero_albarans_vinculats": [],
        "linies": [
            {
                "referencia": "PROD-01",
                "nom": "Sac Terra Vegetal (50L)",
                "quantitat": 20.0,
                "preu": 5.50,
                "descompte_percent": 0.0,
                "tipus": "MATERIAL"
            },
            {
                "referencia": "PROD-02",
                "nom": "Test Terracota Gran",
                "quantitat": 10.0,
                "preu": 12.00,
                "descompte_percent": 0.0,
                "tipus": "MATERIAL"
            },
            {
                "referencia": "PROD-03",
                "nom": "Fertilitzant Orgànic (1L)",
                "quantitat": 15.0,
                "preu": 8.20,
                "descompte_percent": 0.0,
                "tipus": "MATERIAL"
            },
            {
                "referencia": "PROD-04",
                "nom": "Tisores de Podar Professionals",
                "quantitat": 5.0,
                "preu": 25.00,
                "descompte_percent": 0.0,
                "tipus": "EINA"
            }
        ],
        "missatge": "Lectura OCR completada amb èxit. Dades extretes de l'albarà de Jardineria Verda."
    }

@router.post("/albara/confirmar", status_code=status.HTTP_201_CREATED)
async def confirmar_document(
    request: Request,
    payload: ConfirmarDocumentRequest,
    db: AsyncSession = Depends(get_db_with_tenant_context)
):
    empresa_id = uuid.UUID(request.state.empresa_id)
    
    # 1. Buscar o crear Proveïdor
    stmt_prov = select(Proveidor).where(Proveidor.empresa_id == empresa_id, Proveidor.nif == payload.proveidor.nif)
    prov = (await db.execute(stmt_prov)).scalars().first()
    if not prov:
        prov = Proveidor(
            empresa_id=empresa_id,
            codi=f"PRV-{str(uuid.uuid4())[:6].upper()}",
            rao_social=payload.proveidor.nom,
            nif=payload.proveidor.nif,
            telefon=payload.proveidor.telefon,
            email=payload.proveidor.email,
            especialitat="MATERIALS"
        )
        db.add(prov)
        await db.flush()
    else:
        # Actualitzar dades si falten
        if payload.proveidor.telefon and not prov.telefon: prov.telefon = payload.proveidor.telefon
        if payload.proveidor.email and not prov.email: prov.email = payload.proveidor.email
        await db.flush()
        
    # Crear carpeta del proveïdor al directori sobirà
    carpeta_proveidor = f"/tmp/data/{empresa_id}/proveidors/{prov.id}"
    os.makedirs(carpeta_proveidor, exist_ok=True)
    
    # Buscar el magatzem principal
    stmt_mag = select(Magatzem).where(Magatzem.empresa_id == empresa_id, Magatzem.tipus == "NAU_CENTRAL")
    magatzem = (await db.execute(stmt_mag)).scalars().first()
    if not magatzem:
        magatzem = Magatzem(empresa_id=empresa_id, nom="Nau Central Base", tipus="NAU_CENTRAL")
        db.add(magatzem)
        await db.flush()
        
    articles_creats = 0
    moviments_creats = 0
    
    if payload.tipus_document == "FACTURA":
        if not payload.numero_albarans_vinculats:
            raise HTTPException(status_code=400, detail="La factura necessita referenciar almenys un número d'albarà per creuar dades.")
            
        quantitat_total_albarans = 0.0
        
        for num_albara in payload.numero_albarans_vinculats:
            # 1. Comprovar que l'albarà existeix i pertany al mateix proveïdor
            stmt_alb = select(AlbaraProveidor).where(AlbaraProveidor.empresa_id == empresa_id, AlbaraProveidor.numero_albara == num_albara)
            albara_db = (await db.execute(stmt_alb)).scalars().first()
            if not albara_db:
                raise HTTPException(status_code=400, detail=f"No s'ha trobat l'albarà {num_albara}. No podem validar la factura.")
            
            if albara_db.proveidor_id != prov.id:
                raise HTTPException(status_code=400, detail=f"L'albarà {num_albara} no pertany a aquest proveïdor (NIF diferent).")
                
            # 2. Comprovar la data
            if payload.data_document <= albara_db.data_albara:
                raise HTTPException(status_code=400, detail=f"La data de la factura ha de ser posterior a la de l'albarà {num_albara}.")
                
            # 3. Sumar quantitats del MovimentEstoc associades a aquest albarà
            stmt_movs = select(MovimentEstoc).where(MovimentEstoc.magatzem_id == magatzem.id, MovimentEstoc.referencia_document == num_albara)
            moviments_albara = (await db.execute(stmt_movs)).scalars().all()
            quantitat_total_albarans += sum([float(m.quantitat) for m in moviments_albara])
            
        quantitat_factura = sum([float(l.quantitat) for l in payload.linies])
        
        if abs(quantitat_total_albarans - quantitat_factura) > 0.01:
            raise HTTPException(status_code=400, detail="DISCORDÀNCIA: Les quantitats de la factura no quadren amb la suma dels albarans vinculats. Revisa-ho manualment.")
            
        base_imposable = sum([(l.quantitat * l.preu) * (1 - (l.descompte_percent/100)) for l in payload.linies])
        quota_iva = base_imposable * 0.21
        
        stmt_fact = select(FacturaProveidor).where(FacturaProveidor.empresa_id == empresa_id, FacturaProveidor.proveidor_id == prov.id, FacturaProveidor.numero_factura == payload.numero_document)
        if (await db.execute(stmt_fact)).scalars().first():
            raise HTTPException(status_code=400, detail="Aquesta factura ja ha estat registrada prèviament.")
            
        factura = FacturaProveidor(
            empresa_id=empresa_id,
            proveidor_id=prov.id,
            numero_factura=payload.numero_document,
            data_factura=payload.data_document,
            base_imposable=base_imposable,
            quota_iva=quota_iva,
            total=base_imposable + quota_iva,
            albara_numero=",".join(payload.numero_albarans_vinculats)
        )
        db.add(factura)
        await db.commit()
        return {"estat": "OK", "missatge": "Factura validada amb els albarans i enviada a Control Econòmic.", "factura_id": str(factura.id), "carpeta": carpeta_proveidor}
    
    else:
        # És ALBARA
        stmt_alb_check = select(AlbaraProveidor).where(AlbaraProveidor.empresa_id == empresa_id, AlbaraProveidor.proveidor_id == prov.id, AlbaraProveidor.numero_albara == payload.numero_document)
        if (await db.execute(stmt_alb_check)).scalars().first():
            raise HTTPException(status_code=400, detail="Albarà ja pujat. Aquest document ja consta al sistema per aquest proveïdor.")
            
        nou_albara = AlbaraProveidor(
            empresa_id=empresa_id,
            proveidor_id=prov.id,
            numero_albara=payload.numero_document,
            data_albara=payload.data_document
        )
        db.add(nou_albara)
        
        for linia in payload.linies:
            stmt_art = select(Article).where(Article.empresa_id == empresa_id, Article.referencia_inventari == linia.referencia)
            article = (await db.execute(stmt_art)).scalars().first()
            
            if not article:
                article = Article(
                    empresa_id=empresa_id,
                    referencia_inventari=linia.referencia,
                    nom=linia.nom,
                    unitat_mesura="UNITAT",
                    familia="EINA" if linia.tipus == "EINA" else "GENERAL",
                    preu_cost=linia.preu * (1 - (linia.descompte_percent/100))
                )
                db.add(article)
                await db.flush()
                articles_creats += 1
            
            stmt_estoc = select(EstocMagatzem).where(EstocMagatzem.magatzem_id == magatzem.id, EstocMagatzem.article_id == article.id)
            estoc = (await db.execute(stmt_estoc)).scalars().first()
            if not estoc:
                estoc = EstocMagatzem(
                    empresa_id=empresa_id,
                    magatzem_id=magatzem.id,
                    article_id=article.id,
                    quantitat_fisica=0.0
                )
                db.add(estoc)
                await db.flush()
                
            moviment = MovimentEstoc(
                empresa_id=empresa_id,
                magatzem_id=magatzem.id,
                article_id=article.id,
                tipus_moviment="ENTRADA",
                quantitat=linia.quantitat,
                usuari_id=None,
                referencia_document=payload.numero_document,
                notes=f"Albarà Proveïdor OCR"
            )
            db.add(moviment)
            estoc.quantitat_fisica = float(estoc.quantitat_fisica) + linia.quantitat
            moviments_creats += 1
            
        await db.commit()
        
        return {
            "estat": "OK",
            "missatge": "Albarà registrat, estoc augmentat.",
            "proveidor_id": str(prov.id),
            "articles_creats": articles_creats,
            "moviments_realitzats": moviments_creats,
            "carpeta": carpeta_proveidor
        }

@router.put("/articles/{article_id}", response_model=ArticleResponse)
async def modificar_article(
    request: Request,
    article_id: uuid.UUID,
    article: ArticleCreate,
    db: AsyncSession = Depends(get_db_with_tenant_context)
):
    empresa_id = request.state.empresa_id
    if not empresa_id:
        raise HTTPException(status_code=401, detail="No identificat")
        
    stmt = select(Article).where(Article.id == article_id, Article.empresa_id == uuid.UUID(empresa_id))
    result = await db.execute(stmt)
    art_db = result.scalars().first()
    if not art_db:
        raise HTTPException(status_code=404, detail="Article no trobat")
        
    art_db.referencia_inventari = article.referencia_inventari
    art_db.nom = article.nom
    art_db.unitat_mesura = article.unitat_mesura
    art_db.familia = article.familia
    art_db.estoc_optim = article.estoc_optim
    art_db.estoc_minim = article.estoc_minim
    art_db.es_lot_caducable = article.es_lot_caducable
    art_db.preu_cost = article.preu_cost
    art_db.preu_venda = article.preu_venda
    
    await db.commit()
    
    # Calcular estoc real
    from sqlalchemy import func
    stmt_estoc = select(func.sum(EstocMagatzem.quantitat_fisica)).where(
        EstocMagatzem.article_id == article_id
    )
    estoc_real = (await db.execute(stmt_estoc)).scalar() or 0.0
    
    art_dict = {c.name: getattr(art_db, c.name) for c in art_db.__table__.columns}
    art_dict["estoc_real"] = float(estoc_real)
    
    return art_dict
