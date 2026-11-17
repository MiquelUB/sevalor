import logging
import uuid
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile, status
from pydantic import BaseModel, ConfigDict, Field


def valida_uuid(id_str: str) -> uuid.UUID:
    try:
        return uuid.UUID(str(id_str))
    except Exception:
        raise HTTPException(status_code=400, detail="Identificador d'empresa invàlid.")


from sqlalchemy import case, func, or_, select  # noqa: E402
from sqlalchemy.ext.asyncio import AsyncSession  # noqa: E402

from app.core.db import get_db_with_tenant_context  # noqa: E402
from app.core.security import get_current_user_claims, require_roles  # noqa: E402
from app.models.models import (  # noqa: E402
    AlbaraProveidor,
    AlertaGarantiaRecompra,
    Article,
    Empresa,
    EstocMagatzem,
    FacturaProveidor,
    FullaPicking,
    LiniaPicking,
    Magatzem,
    MermaInventari,
    MovimentEstoc,
    OrdreTreball,
    Proveidor,
    Usuari,
    Vehicle,
)
from app.services.magatzem_comptabilitat_service import (  # noqa: E402
    processar_entrada_albara_i_recalcular_pmp,
    registrar_merma_i_imputar_a_comptabilitat,
)
from app.services.sovereign_storage import SovereignStorageGateway  # noqa: E402

logger = logging.getLogger("sevalor.magatzem")

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
    tipus: str  # "MATERIAL" o "EINA"


class ProveidorOcr(BaseModel):
    nif: str
    nom: str
    adreca: Optional[str] = None
    telefon: Optional[str] = None
    email: Optional[str] = None


class ConfirmarDocumentRequest(BaseModel):
    proveidor: ProveidorOcr
    numero_document: str  # Num Albarà o Factura
    tipus_document: str  # "ALBARA" o "FACTURA"
    data_document: date
    numero_albarans_vinculats: List[str] = []
    linies: List[LiniaOcr]


class ArticleCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    referencia_inventari: str = Field(..., max_length=50)
    codi_barres: Optional[str] = Field(None, max_length=100)
    nom: str = Field(..., max_length=500)
    unitat_mesura: str = Field("UNITAT", max_length=30)
    es_material_continu: bool = Field(False)
    familia: str = Field("GENERAL", max_length=50)
    estoc_optim: float = Field(0.0)
    estoc_minim: float = Field(0.0)
    es_lot_caducable: bool = Field(False)
    preu_cost: float = Field(0.0)
    descompte_proveidor: float = Field(0.0)
    marge_guanys: float = Field(0.0)
    preu_venda: float = Field(0.0)
    proveidor_id: Optional[uuid.UUID] = None
    estoc_inicial: Optional[float] = Field(default=None, ge=0)
    magatzem_id: Optional[uuid.UUID] = None


class ArticleResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    referencia_inventari: str
    codi_barres: Optional[str] = None
    nom: str
    unitat_mesura: str = "UNITAT"
    es_material_continu: bool = False
    familia: str = "GENERAL"
    estoc_optim: float = 0.0
    estoc_minim: float = 0.0
    es_lot_caducable: bool = False
    preu_cost: Optional[float] = 0.0
    descompte_proveidor: Optional[float] = 0.0
    marge_guanys: Optional[float] = 0.0
    preu_venda: float = 0.0
    proveidor_id: Optional[uuid.UUID] = None
    actiu: bool = True
    estoc_fisic: float = 0.0
    estoc_reservat: float = 0.0
    estoc_disponible: float = 0.0
    estoc_real: float = 0.0
    proveidor_nom: Optional[str] = None
    pmp_actual: Optional[float] = 0.0
    estoc_slot_residus: float = 0.0
    estoc_total_actual: float = 0.0
    es_diposit_proveidor: bool = False
    es_custodia_rma_client: bool = False


def _normalitzar_codi_barres(codi: Optional[str]) -> Optional[str]:
    """Valida format de codi de barres sense QR (FR-007) i retorna None si és buit."""
    if not codi:
        return None
    net = codi.strip()
    if not net:
        return None
    lower = net.lower()
    if lower.startswith(("qr:", "http://", "https://")) or "qrcode" in lower:
        raise HTTPException(
            status_code=422,
            detail="Format invàlid (FR-007): només s'admeten codis de barres EAN/Code128 o referències alfanumèriques (prohibit QR).",
        )
    return net


def _serialitzar_article(
    art: Article,
    estoc_fisic: float,
    estoc_reservat: float,
    prov_nom: Optional[str],
    rol: str,
) -> Dict[str, Any]:
    """Construeix resposta segura d'Article amb estoc disponible real i veto financer ENGINYER."""
    fisic = float(estoc_fisic or 0.0)
    reservat = float(estoc_reservat or 0.0)
    disponible = max(0.0, fisic - reservat)
    preu_cost_val = float(getattr(art, "preu_cost", 0.0) or 0.0)
    pmp_raw = getattr(art, "pmp_actual", None)
    pmp_val = float(pmp_raw) if pmp_raw is not None else preu_cost_val
    is_enginyer = rol.upper() == "ENGINYER"

    return {
        "id": art.id,
        "referencia_inventari": art.referencia_inventari or "N/A",
        "codi_barres": getattr(art, "codi_barres", None),
        "nom": art.nom or "N/A",
        "unitat_mesura": art.unitat_mesura or "UNITAT",
        "es_material_continu": bool(getattr(art, "es_material_continu", False)),
        "familia": art.familia or "GENERAL",
        "estoc_optim": float(art.estoc_optim or 0.0),
        "estoc_minim": float(art.estoc_minim or 0.0),
        "es_lot_caducable": bool(getattr(art, "es_lot_caducable", False)),
        "preu_cost": None if is_enginyer else preu_cost_val,
        "descompte_proveidor": None if is_enginyer else float(getattr(art, "descompte_proveidor", 0.0) or 0.0),
        "marge_guanys": None if is_enginyer else float(getattr(art, "marge_guanys", 0.0) or 0.0),
        "preu_venda": float(art.preu_venda or 0.0),
        "proveidor_id": getattr(art, "proveidor_id", None),
        "actiu": True if getattr(art, "actiu", True) is None else bool(art.actiu),
        "estoc_fisic": fisic,
        "estoc_reservat": reservat,
        "estoc_disponible": disponible,
        "estoc_real": disponible,
        "proveidor_nom": prov_nom,
        "pmp_actual": None if is_enginyer else pmp_val,
        "estoc_slot_residus": float(getattr(art, "estoc_slot_residus", 0.0) or 0.0),
        "estoc_total_actual": disponible,
        "es_diposit_proveidor": bool(getattr(art, "es_diposit_proveidor", False)),
        "es_custodia_rma_client": bool(getattr(art, "es_custodia_rma_client", False)),
    }


async def _sync_article_disc(
    db: AsyncSession,
    empresa_id: uuid.UUID,
    art: Article,
    estoc_fisic: Optional[float] = None,
    estoc_reservat: Optional[float] = None,
) -> None:
    """Sincronitza la fitxa d'article (i el seu estoc disponible real) al disc sobirà 03_magatzem."""
    try:
        if estoc_fisic is None or estoc_reservat is None:
            agg = (
                await db.execute(
                    select(
                        func.coalesce(func.sum(EstocMagatzem.quantitat_fisica), 0.0),
                        func.coalesce(func.sum(EstocMagatzem.quantitat_virtual_reservada), 0.0),
                    ).where(
                        EstocMagatzem.empresa_id == empresa_id,
                        EstocMagatzem.article_id == art.id,
                    )
                )
            ).one()
            estoc_fisic = float(agg[0] or 0.0)
            estoc_reservat = float(agg[1] or 0.0)

        disponible = max(0.0, float(estoc_fisic) - float(estoc_reservat))
        ruta = await SovereignStorageGateway.desar_entitat_json(
            db=db,
            empresa_id=empresa_id,
            categoria="magatzem_articles",
            item_id=str(art.id),
            dades={
                "id": str(art.id),
                "referencia_inventari": art.referencia_inventari,
                "codi_barres": getattr(art, "codi_barres", None),
                "nom": art.nom,
                "unitat_mesura": art.unitat_mesura,
                "familia": art.familia,
                "estoc_minim": float(art.estoc_minim or 0.0),
                "estoc_optim": float(art.estoc_optim or 0.0),
                "estoc_fisic": float(estoc_fisic),
                "estoc_reservat": float(estoc_reservat),
                "estoc_disponible": disponible,
                "preu_cost": float(art.preu_cost or 0.0),
                "preu_venda": float(art.preu_venda or 0.0),
                "synced_at": datetime.now(timezone.utc).isoformat(),
            },
        )
        if not str(ruta).startswith("transit://"):
            await SovereignStorageGateway.drenar_cua_transit_empresa(db, empresa_id)
    except Exception as exc:
        logger.warning("No s'ha pogut sincronitzar l'article %s al disc sobirà: %s", art.id, exc)


class EntradaPMPRequest(BaseModel):
    article_id: uuid.UUID
    magatzem_id: uuid.UUID
    quantitat_rebuda: Decimal = Field(..., gt=0)
    preu_compra_unitari: Decimal = Field(..., ge=0)
    preu_ferm_comanda: Optional[Decimal] = Field(None, ge=0)
    es_granel_continu: bool = False
    quantitat_demanada_comanda: Optional[Decimal] = Field(None, gt=0)
    referencia_document: Optional[str] = Field(None, max_length=100)


class MermaInventariRequest(BaseModel):
    article_id: uuid.UUID
    magatzem_id: uuid.UUID
    quantitat_mermada: Decimal = Field(..., gt=0)
    motiu: str = Field(..., max_length=50)
    ordre_treball_id: Optional[uuid.UUID] = None
    notes: Optional[str] = Field(None, max_length=500)


# ---------------------------------------------------------------------------
# Estoc de magatzem (Spec 004 — gestió multimagatzem amb bloqueig pessimista)
# ---------------------------------------------------------------------------


class MovimentEstocRequest(BaseModel):
    article_id: uuid.UUID
    quantitat: float = Field(
        ..., gt=0, description="Quantitat positiva (entrada o sortida segons 'tipus')"
    )
    tipus: str = Field("ENTRADA", pattern="^(ENTRADA|SORTIDA|RESERVA)$")
    ubicacio_passadis: Optional[str] = Field(None, max_length=50)
    notes: Optional[str] = Field(None, max_length=255)


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
    magatzem_id: Optional[uuid.UUID] = None,
    limit: int = 50,
    offset: int = 0,
    claims: dict = Depends(get_current_user_claims),
    db: AsyncSession = Depends(get_db_with_tenant_context),
):
    empresa_id = getattr(request.state, "empresa_id", None) or request.headers.get("X-Empresa-ID")
    if not empresa_id or empresa_id in ("undefined", "null", "None"):
        raise HTTPException(status_code=401, detail="No identificat")

    empresa_uuid = valida_uuid(str(empresa_id))
    rol = str(claims.get("rol") or "").upper()

    stmt = select(Article).where(Article.empresa_id == empresa_uuid)

    if q:
        search_term = f"%{q}%"
        stmt = stmt.where(
            or_(
                Article.referencia_inventari.ilike(search_term),
                Article.nom.ilike(search_term),
                Article.codi_barres.ilike(search_term),
            )
        )

    stmt = stmt.limit(limit).offset(offset).order_by(Article.created_at.desc())
    result = await db.execute(stmt)
    articles = result.scalars().all()

    articles_ids = [a.id for a in articles]
    estocs_map: Dict[uuid.UUID, tuple[float, float]] = {}
    if articles_ids:
        stmt_estocs = select(
            EstocMagatzem.article_id,
            func.coalesce(func.sum(EstocMagatzem.quantitat_fisica), 0.0),
            func.coalesce(func.sum(EstocMagatzem.quantitat_virtual_reservada), 0.0),
        ).where(
            EstocMagatzem.empresa_id == empresa_uuid,
            EstocMagatzem.article_id.in_(articles_ids),
        )
        if magatzem_id:
            stmt_estocs = stmt_estocs.where(EstocMagatzem.magatzem_id == magatzem_id)
        stmt_estocs = stmt_estocs.group_by(EstocMagatzem.article_id)
        res_estocs = await db.execute(stmt_estocs)
        for article_id, qt_fis, qt_res in res_estocs.all():
            estocs_map[article_id] = (float(qt_fis or 0.0), float(qt_res or 0.0))

    prov_ids = [a.proveidor_id for a in articles if getattr(a, "proveidor_id", None)]
    prov_map: Dict[uuid.UUID, str] = {}
    if prov_ids:
        stmt_prov = select(Proveidor.id, Proveidor.rao_social).where(
            Proveidor.empresa_id == empresa_uuid,
            Proveidor.id.in_(prov_ids),
        )
        res_prov = await db.execute(stmt_prov)
        for pid, rsocial in res_prov.all():
            prov_map[pid] = rsocial

    return [
        _serialitzar_article(
            art=art,
            estoc_fisic=estocs_map.get(art.id, (0.0, 0.0))[0],
            estoc_reservat=estocs_map.get(art.id, (0.0, 0.0))[1],
            prov_nom=prov_map.get(art.proveidor_id) if art.proveidor_id is not None else None,
            rol=rol,
        )
        for art in articles
    ]


@router.post("/articles", response_model=ArticleResponse, status_code=status.HTTP_201_CREATED)
async def alta_article(
    request: Request,
    article: ArticleCreate,
    claims: dict = Depends(get_current_user_claims),
    db: AsyncSession = Depends(get_db_with_tenant_context),
):
    empresa_id = getattr(request.state, "empresa_id", None) or request.headers.get("X-Empresa-ID")
    if not empresa_id or empresa_id in ("undefined", "null", "None"):
        raise HTTPException(status_code=401, detail="No identificat")
    emp_uuid = valida_uuid(str(empresa_id))
    rol = str(claims.get("rol") or "").upper()

    stmt_ref = select(Article).where(
        Article.empresa_id == emp_uuid,
        Article.referencia_inventari == article.referencia_inventari,
    )
    if (await db.execute(stmt_ref)).scalars().first():
        raise HTTPException(status_code=400, detail="La referència ja es troba registrada")

    codi_barres_net = _normalitzar_codi_barres(article.codi_barres)
    if codi_barres_net:
        dup_cb = (
            await db.execute(select(Article.id).where(Article.codi_barres == codi_barres_net))
        ).scalars().first()
        if dup_cb:
            raise HTTPException(
                status_code=400,
                detail="El codi de barres ja es troba assignat a un altre article.",
            )

    nou_article = Article(
        empresa_id=emp_uuid,
        referencia_inventari=article.referencia_inventari,
        codi_barres=codi_barres_net,
        nom=article.nom,
        unitat_mesura=article.unitat_mesura,
        es_material_continu=article.es_material_continu,
        familia=article.familia,
        estoc_optim=article.estoc_optim,
        estoc_minim=article.estoc_minim,
        es_lot_caducable=article.es_lot_caducable,
        preu_cost=article.preu_cost,
        descompte_proveidor=article.descompte_proveidor,
        marge_guanys=article.marge_guanys,
        preu_venda=article.preu_venda,
        proveidor_id=article.proveidor_id,
    )

    db.add(nou_article)
    await db.flush()

    estoc_inicial_val = float(article.estoc_inicial or 0.0)
    if estoc_inicial_val > 0:
        if article.magatzem_id:
            mag_target = (
                await db.execute(
                    select(Magatzem).where(
                        Magatzem.id == article.magatzem_id,
                        Magatzem.empresa_id == emp_uuid,
                    )
                )
            ).scalars().first()
            if not mag_target:
                raise HTTPException(status_code=404, detail="Magatzem inicial no trobat")
        else:
            mag_target = (
                await db.execute(
                    select(Magatzem).where(
                        Magatzem.empresa_id == emp_uuid,
                        Magatzem.tipus == "NAU_CENTRAL",
                    )
                )
            ).scalars().first()
            if not mag_target:
                mag_target = Magatzem(
                    empresa_id=emp_uuid,
                    nom="Nau Central Base",
                    tipus="NAU_CENTRAL",
                    actiu=True,
                )
                db.add(mag_target)
                await db.flush()

        db.add(
            EstocMagatzem(
                empresa_id=emp_uuid,
                magatzem_id=mag_target.id,
                article_id=nou_article.id,
                quantitat_fisica=estoc_inicial_val,
                quantitat_virtual_reservada=0.0,
            )
        )
        db.add(
            MovimentEstoc(
                empresa_id=emp_uuid,
                magatzem_id=mag_target.id,
                article_id=nou_article.id,
                tipus_moviment="ENTRADA",
                quantitat=estoc_inicial_val,
                usuari_id=uuid.UUID(str(claims["sub"])) if claims.get("sub") else None,
                notes="Estoc inicial alta article",
            )
        )

    await db.commit()

    await _sync_article_disc(
        db=db,
        empresa_id=emp_uuid,
        art=nou_article,
        estoc_fisic=estoc_inicial_val,
        estoc_reservat=0.0,
    )

    prov_nom_res: Optional[str] = None
    if nou_article.proveidor_id:
        stmt_prov_n = select(Proveidor.rao_social).where(
            Proveidor.id == nou_article.proveidor_id,
            Proveidor.empresa_id == emp_uuid,
        )
        prov_nom_res = (await db.execute(stmt_prov_n)).scalar_one_or_none()

    return _serialitzar_article(
        art=nou_article,
        estoc_fisic=estoc_inicial_val,
        estoc_reservat=0.0,
        prov_nom=prov_nom_res,
        rol=rol,
    )


from app.models.models import EinaCustodia  # noqa: E402


class EinaCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    referencia_fabricant: Optional[str] = None
    nom: str = Field(..., max_length=500)
    model: Optional[str] = None
    numero_serie: str = Field(..., max_length=100)
    data_fi_garantia: Optional[date] = None
    observacions: Optional[str] = None
    incidencies: Optional[str] = None


class EinaResponse(EinaCreate):
    id: uuid.UUID
    estat: str
    custodiat_per_operari_id: Optional[uuid.UUID] = None
    magatzem_id: Optional[uuid.UUID] = None
    custodia_nom: Optional[str] = None


@router.post("/eines", response_model=EinaResponse, status_code=status.HTTP_201_CREATED)
async def crear_eina(
    request: Request, payload: EinaCreate, db: AsyncSession = Depends(get_db_with_tenant_context)
):
    empresa_id = getattr(request.state, "empresa_id", None) or request.headers.get("X-Empresa-ID")
    if not empresa_id or empresa_id in ("undefined", "null", "None"):
        raise HTTPException(status_code=401, detail="No identificat")
    emp_uuid = valida_uuid(empresa_id)

    nova_eina = EinaCustodia(
        empresa_id=emp_uuid,
        referencia_fabricant=payload.referencia_fabricant,
        nom=payload.nom,
        model=payload.model,
        numero_serie=payload.numero_serie,
        data_fi_garantia=payload.data_fi_garantia,
        observacions=payload.observacions,
        incidencies=payload.incidencies,
        estat="DISPONIBLE",
    )
    db.add(nova_eina)
    await db.commit()
    return nova_eina


class MagatzemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    nom: str
    tipus: str
    vehicle_id: Optional[uuid.UUID] = None
    vehicle_matricula: Optional[str] = None
    actiu: bool
    created_at: Optional[datetime] = None


@router.get("/magatzems", response_model=List[MagatzemResponse])
async def llistar_magatzems(
    request: Request, db: AsyncSession = Depends(get_db_with_tenant_context)
):
    """Llista tots els magatzems de l'empresa (Nau Central i Furgonetes / Vehicles mòbils)."""
    empresa_id = getattr(request.state, "empresa_id", None) or request.headers.get("X-Empresa-ID")
    if not empresa_id or empresa_id in ("undefined", "null", "None"):
        raise HTTPException(status_code=401, detail="No identificat")
    emp_uuid = valida_uuid(empresa_id)

    # Assegurar que la Nau Central Base existeix per a aquest tenant
    stmt_central = select(Magatzem).where(
        Magatzem.empresa_id == emp_uuid, Magatzem.tipus == "NAU_CENTRAL"
    )
    central = (await db.execute(stmt_central)).scalars().first()
    if not central:
        central = Magatzem(
            empresa_id=emp_uuid,
            nom="Nau Central Base",
            tipus="NAU_CENTRAL",
            actiu=True,
        )
        db.add(central)
        await db.flush()

    # Sincronitzar vehicles de flota que encara no tinguin magatzem mòbil
    stmt_vehs = select(Vehicle).where(Vehicle.empresa_id == emp_uuid)
    vehs = (await db.execute(stmt_vehs)).scalars().all()

    stmt_mags_furg = select(Magatzem).where(
        Magatzem.empresa_id == emp_uuid, Magatzem.tipus == "FURGONETA"
    )
    mags_furg = {
        m.vehicle_id: m for m in (await db.execute(stmt_mags_furg)).scalars().all() if m.vehicle_id
    }

    hi_ha_nous = False
    for v in vehs:
        if v.id not in mags_furg:
            db.add(
                Magatzem(
                    empresa_id=emp_uuid,
                    nom=f"Vehicle {v.matricula} ({v.marca} {v.model})",
                    tipus="FURGONETA",
                    vehicle_id=v.id,
                    actiu=True,
                )
            )
            hi_ha_nous = True

    if hi_ha_nous:
        await db.commit()

    stmt_all = (
        select(Magatzem, Vehicle.matricula)
        .outerjoin(Vehicle, Magatzem.vehicle_id == Vehicle.id)
        .where(Magatzem.empresa_id == emp_uuid, Magatzem.actiu.is_(True))
        .order_by(
            case((Magatzem.tipus == "NAU_CENTRAL", 0), else_=1),
            Magatzem.nom.asc(),
        )
    )
    res = await db.execute(stmt_all)
    llista = []
    for mag, mat in res.all():
        llista.append(
            MagatzemResponse(
                id=mag.id,
                nom=mag.nom,
                tipus=mag.tipus,
                vehicle_id=mag.vehicle_id,
                vehicle_matricula=mat,
                actiu=mag.actiu,
                created_at=mag.created_at,
            )
        )
    return llista


@router.get("/magatzems/{magatzem_id}/estoc", response_model=List[EstocResponse])
async def llistar_estoc_magatzem(
    request: Request, magatzem_id: uuid.UUID, db: AsyncSession = Depends(get_db_with_tenant_context)
):
    """Llista l'estoc d'un magatzem (Spec 004)."""
    empresa_id = request.state.empresa_id
    if not empresa_id or empresa_id == "undefined":
        raise HTTPException(status_code=401, detail="No identificat")

    mag_res = await db.execute(
        select(Magatzem).where(
            Magatzem.id == magatzem_id, Magatzem.empresa_id == uuid.UUID(empresa_id)
        )
    )
    if not mag_res.scalars().first():
        raise HTTPException(status_code=404, detail="Magatzem no trobat")

    q = (
        select(EstocMagatzem, Article)
        .join(Article, Article.id == EstocMagatzem.article_id)
        .where(
            EstocMagatzem.magatzem_id == magatzem_id,
            EstocMagatzem.empresa_id == uuid.UUID(empresa_id),
        )
    )
    res = await db.execute(q)
    resultats = []
    for estoc, article in res.all():
        resultats.append(
            {
                "article_id": estoc.article_id,
                "referencia_article": article.referencia_inventari,
                "quantitat_fisica": float(estoc.quantitat_fisica),
                "quantitat_virtual_reservada": float(estoc.quantitat_virtual_reservada),
                "quantitat_disponible": float(estoc.quantitat_fisica)
                - float(estoc.quantitat_virtual_reservada),
                "ubicacio_passadis": estoc.ubicacio_passadis,
            }
        )
    return resultats


@router.post(
    "/magatzems/{magatzem_id}/moviment",
    response_model=EstocResponse,
    status_code=status.HTTP_200_OK,
)
async def registrar_moviment_estoc(
    request: Request,
    magatzem_id: uuid.UUID,
    payload: MovimentEstocRequest,
    claims: dict = Depends(get_current_user_claims),
    db: AsyncSession = Depends(get_db_with_tenant_context),
):
    """Registra un moviment d'estoc (entrada/sortida/reserva) amb bloqueig pessimista (SELECT FOR UPDATE).

    Spec 004: prevenció de condicions de carrera. Un SELECT FOR UPDATE sobre
    la fila d'estoc garanteix que dos enginyers no puguin reservar el mateix
    stock concurrentment.
    """
    empresa_id = getattr(request.state, "empresa_id", None) or request.headers.get("X-Empresa-ID")
    if not empresa_id or empresa_id == "undefined":
        raise HTTPException(status_code=401, detail="No identificat")
    emp_uuid = valida_uuid(str(empresa_id))

    # Verificar article pertany a l'empresa
    art_res = await db.execute(
        select(Article).where(
            Article.id == payload.article_id, Article.empresa_id == emp_uuid
        )
    )
    art_obj = art_res.scalars().first()
    if not art_obj:
        raise HTTPException(status_code=404, detail="Article no trobat")

    # Verificar magatzem de l'empresa
    mag_res = await db.execute(
        select(Magatzem).where(
            Magatzem.id == magatzem_id, Magatzem.empresa_id == emp_uuid
        )
    )
    if not mag_res.scalars().first():
        raise HTTPException(status_code=404, detail="Magatzem no trobat")

    # Cercar estoc existent (amb FOR UPDATE per blocar la fila)
    estoc_res = await db.execute(
        select(EstocMagatzem)
        .where(
            EstocMagatzem.empresa_id == emp_uuid,
            EstocMagatzem.article_id == payload.article_id,
            EstocMagatzem.magatzem_id == magatzem_id,
        )
        .with_for_update()
    )
    estoc = estoc_res.scalars().first()

    if estoc is None:
        estoc = EstocMagatzem(
            empresa_id=emp_uuid,
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
                status_code=422,
                detail=f"Stock insuficient: disponible {disponible}, sol·licitat {quantitat}",
            )
        estoc.quantitat_fisica = float(estoc.quantitat_fisica) - quantitat
    elif payload.tipus == "RESERVA":
        disponible = float(estoc.quantitat_fisica) - float(estoc.quantitat_virtual_reservada)
        if quantitat > disponible:
            raise HTTPException(
                status_code=422,
                detail=f"Stock virtual insuficient per reservar: disponible {disponible}",
            )
        estoc.quantitat_virtual_reservada = float(estoc.quantitat_virtual_reservada) + quantitat

    if payload.ubicacio_passadis is not None:
        estoc.ubicacio_passadis = payload.ubicacio_passadis

    if payload.tipus in ("ENTRADA", "SORTIDA"):
        db.add(
            MovimentEstoc(
                empresa_id=emp_uuid,
                magatzem_id=magatzem_id,
                article_id=payload.article_id,
                tipus_moviment=payload.tipus,
                quantitat=quantitat,
                usuari_id=uuid.UUID(str(claims["sub"])) if claims.get("sub") else None,
                notes=payload.notes or f"Ajust manual {payload.tipus}",
            )
        )

    await db.commit()
    await _sync_article_disc(db, emp_uuid, art_obj)

    return {
        "article_id": estoc.article_id,
        "quantitat_fisica": float(estoc.quantitat_fisica),
        "quantitat_virtual_reservada": float(estoc.quantitat_virtual_reservada),
        "quantitat_disponible": float(estoc.quantitat_fisica)
        - float(estoc.quantitat_virtual_reservada),
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
    magatzem_id: Optional[uuid.UUID] = None
    quantitat_prevista: float = Field(..., gt=0)


class LiniaPickingResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    article_id: uuid.UUID
    magatzem_id: Optional[uuid.UUID] = None
    quantitat_prevista: float
    quantitat_carregada_pick_in: float
    quantitat_retornada_pick_out: float
    quantitat_mermada: float


async def _sincronitzar_picking_disc(
    db: AsyncSession,
    empresa_id: uuid.UUID,
    picking_id: uuid.UUID,
) -> None:
    """Sincronitza la fulla de picking i les seves línies al disc sobirà 03_magatzem."""
    try:
        fulla = (
            await db.execute(
                select(FullaPicking).where(
                    FullaPicking.id == picking_id,
                    FullaPicking.empresa_id == empresa_id,
                )
            )
        ).scalars().first()
        if not fulla:
            return
        linies = (
            await db.execute(
                select(LiniaPicking).where(
                    LiniaPicking.picking_id == picking_id,
                    LiniaPicking.empresa_id == empresa_id,
                )
            )
        ).scalars().all()
        ruta = await SovereignStorageGateway.desar_entitat_json(
            db=db,
            empresa_id=empresa_id,
            categoria="picking",
            item_id=str(fulla.id),
            dades={
                "id": str(fulla.id),
                "ordre_treball_id": str(fulla.ordre_treball_id),
                "vehicle_id": str(fulla.vehicle_id) if fulla.vehicle_id else None,
                "estat_picking": fulla.estat_picking,
                "linies": [
                    {
                        "id": str(lin.id),
                        "article_id": str(lin.article_id),
                        "magatzem_id": str(lin.magatzem_id) if lin.magatzem_id else None,
                        "quantitat_prevista": float(lin.quantitat_prevista or 0.0),
                        "quantitat_carregada_pick_in": float(lin.quantitat_carregada_pick_in or 0.0),
                        "quantitat_retornada_pick_out": float(lin.quantitat_retornada_pick_out or 0.0),
                        "quantitat_mermada": float(lin.quantitat_mermada or 0.0),
                    }
                    for lin in linies
                ],
                "synced_at": datetime.now(timezone.utc).isoformat(),
            },
        )
        if not str(ruta).startswith("transit://"):
            await SovereignStorageGateway.drenar_cua_transit_empresa(db, empresa_id)
    except Exception as exc:
        logger.warning("No s'ha pogut sincronitzar picking %s al disc sobirà: %s", picking_id, exc)


@router.post("/picking", response_model=FullaPickingResponse, status_code=status.HTTP_201_CREATED)
async def crear_fulla_picking(
    request: Request,
    payload: FullaPickingCreate,
    db: AsyncSession = Depends(get_db_with_tenant_context),
):
    """Crea una fulla de picking per a una ordre de treball (RF-20: 1 tasca = 1 fulla)."""
    empresa_id = request.state.empresa_id
    if not empresa_id or empresa_id == "undefined":
        raise HTTPException(status_code=401)
    emp_uuid = valida_uuid(str(empresa_id))

    # Verificar que l'ordre de treball pertany a l'empresa
    ot_res = await db.execute(
        select(OrdreTreball).where(
            OrdreTreball.id == payload.ordre_treball_id,
            OrdreTreball.empresa_id == emp_uuid,
        )
    )
    if not ot_res.scalars().first():
        raise HTTPException(status_code=404, detail="Ordre de treball no trobada")

    fulla = FullaPicking(
        empresa_id=emp_uuid,
        ordre_treball_id=payload.ordre_treball_id,
        vehicle_id=payload.vehicle_id,
        estat_picking="PENDENT",
    )
    db.add(fulla)
    await db.commit()
    await _sincronitzar_picking_disc(db, emp_uuid, fulla.id)

    return {
        "id": fulla.id,
        "ordre_treball_id": fulla.ordre_treball_id,
        "vehicle_id": fulla.vehicle_id,
        "estat_picking": fulla.estat_picking,
    }


@router.post(
    "/picking/{picking_id}/linies",
    response_model=LiniaPickingResponse,
    status_code=status.HTTP_201_CREATED,
)
async def afegir_linia_picking(
    request: Request,
    picking_id: uuid.UUID,
    payload: LiniaPickingCreate,
    db: AsyncSession = Depends(get_db_with_tenant_context),
):
    """Afegeix una línia de picking a una fulla (RF-17: reserva amb SELECT FOR UPDATE per magatzem)."""
    empresa_id = request.state.empresa_id
    if not empresa_id or empresa_id == "undefined":
        raise HTTPException(status_code=401)
    emp_uuid = valida_uuid(str(empresa_id))

    # Verificar fulla
    fulla_res = await db.execute(
        select(FullaPicking).where(
            FullaPicking.id == picking_id,
            FullaPicking.empresa_id == emp_uuid,
        )
    )
    fulla = fulla_res.scalars().first()
    if not fulla:
        raise HTTPException(status_code=404, detail="Fulla de picking no trobada")

    # Verificar article dins el tenant
    art_obj = (
        await db.execute(
            select(Article).where(
                Article.id == payload.article_id,
                Article.empresa_id == emp_uuid,
            )
        )
    ).scalars().first()
    if not art_obj:
        raise HTTPException(status_code=404, detail="Article no trobat")

    # Bloqueig pessimista sobre l'estoc del magatzem especificat (o major disponible)
    stmt_estoc = select(EstocMagatzem).where(
        EstocMagatzem.empresa_id == emp_uuid,
        EstocMagatzem.article_id == payload.article_id,
    )
    if payload.magatzem_id:
        stmt_estoc = stmt_estoc.where(EstocMagatzem.magatzem_id == payload.magatzem_id)
    else:
        stmt_estoc = stmt_estoc.order_by(
            (EstocMagatzem.quantitat_fisica - EstocMagatzem.quantitat_virtual_reservada).desc()
        )
    estoc_res = await db.execute(stmt_estoc.with_for_update())
    estoc = estoc_res.scalars().first()
    if estoc:
        disponible = float(estoc.quantitat_fisica) - float(estoc.quantitat_virtual_reservada)
        if payload.quantitat_prevista > disponible:
            emp_res = await db.execute(select(Empresa).where(Empresa.id == emp_uuid))
            empresa = emp_res.scalars().first()
            avís_ia = None
            if (
                empresa
                and getattr(empresa, "feature_copilot_ia", False)
                and getattr(empresa, "node_ia_actiu", False)
                and getattr(empresa, "node_ia_url", None)
            ):
                from app.api.v1.gestio.copilot import cridar_lm_studio

                # RF-18 / RF-33: Intervenció del Copilot per avaluar Backorders o falta d'estoc
                avís_ia = await cridar_lm_studio(
                    pregunta=(
                        f"S'ha intentat extreure {payload.quantitat_prevista} unitats de l'article {estoc.article_id}, "
                        f"però només hi ha {disponible} disponibles físicament. Si no hi ha comandes en trànsit, "
                        "adverteix el cap de magatzem de forma tècnica i concisa."
                    ),
                    vertical="LOGISTICA",
                    context_addicional="El teu objectiu és bloquejar el picking i advertir del trencament d'estoc.",
                    empresa=empresa,
                    node_ia_url=empresa.node_ia_url,
                )

            detail_msg = (
                f"❌ Copilot IA: {avís_ia}"
                if avís_ia
                else f"Falta d'estoc: Només hi ha {disponible} unitats disponibles físiques per a l'article sol·licitat (es demanen {payload.quantitat_prevista})."
            )
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=detail_msg,
            )
        estoc.quantitat_virtual_reservada = (
            float(estoc.quantitat_virtual_reservada) + payload.quantitat_prevista
        )
    else:
        raise HTTPException(status_code=422, detail="Article sense estoc al magatzem")

    linia = LiniaPicking(
        empresa_id=emp_uuid,
        picking_id=picking_id,
        article_id=payload.article_id,
        magatzem_id=estoc.magatzem_id,
        quantitat_prevista=payload.quantitat_prevista,
        quantitat_carregada_pick_in=0.0,
        quantitat_retornada_pick_out=0.0,
        quantitat_mermada=0.0,
    )
    db.add(linia)
    await db.commit()

    await _sync_article_disc(db, emp_uuid, art_obj)
    await _sincronitzar_picking_disc(db, emp_uuid, picking_id)

    return {
        "id": linia.id,
        "article_id": linia.article_id,
        "magatzem_id": linia.magatzem_id,
        "quantitat_prevista": float(linia.quantitat_prevista),
        "quantitat_carregada_pick_in": float(linia.quantitat_carregada_pick_in),
        "quantitat_retornada_pick_out": float(linia.quantitat_retornada_pick_out),
        "quantitat_mermada": float(linia.quantitat_mermada),
    }


@router.put("/picking/linies/{linia_id}/pick-in", response_model=LiniaPickingResponse)
async def confirmar_pick_in(
    request: Request, linia_id: uuid.UUID, db: AsyncSession = Depends(get_db_with_tenant_context)
):
    """Confirma la recollida de material (pick-in) des de la PWA (RF-23)."""
    empresa_id = request.state.empresa_id
    if not empresa_id or empresa_id == "undefined":
        raise HTTPException(status_code=401)
    emp_uuid = valida_uuid(str(empresa_id))

    linia_res = await db.execute(
        select(LiniaPicking).where(
            LiniaPicking.id == linia_id,
            LiniaPicking.empresa_id == emp_uuid,
        )
    )
    linia = linia_res.scalars().first()
    if not linia:
        raise HTTPException(status_code=404, detail="Línia de picking no trobada")

    if float(linia.quantitat_carregada_pick_in or 0.0) > 0:
        raise HTTPException(status_code=400, detail="Pick-in ja confirmat anteriorment")

    linia.quantitat_carregada_pick_in = float(linia.quantitat_prevista)
    fulla = (
        await db.execute(
            select(FullaPicking).where(
                FullaPicking.id == linia.picking_id,
                FullaPicking.empresa_id == emp_uuid,
            )
        )
    ).scalars().first()
    if fulla and fulla.estat_picking == "PENDENT":
        fulla.estat_picking = "EN_CURS"

    resp_data = {
        "id": linia.id,
        "article_id": linia.article_id,
        "magatzem_id": linia.magatzem_id,
        "quantitat_prevista": float(linia.quantitat_prevista),
        "quantitat_carregada_pick_in": float(linia.quantitat_carregada_pick_in),
        "quantitat_retornada_pick_out": float(linia.quantitat_retornada_pick_out or 0.0),
        "quantitat_mermada": float(linia.quantitat_mermada or 0.0),
    }
    await db.commit()
    await _sincronitzar_picking_disc(db, emp_uuid, linia.picking_id)
    return resp_data


@router.put("/picking/linies/{linia_id}/pick-out", response_model=LiniaPickingResponse)
async def confirmar_devolucio(
    request: Request,
    linia_id: uuid.UUID,
    quantitat_retornada: float = 0.0,
    quantitat_mermada: float = 0.0,
    db: AsyncSession = Depends(get_db_with_tenant_context),
):
    """Registra devolució de sobrants/mermes (pick-out) i descompta consum real del magatzem."""
    empresa_id = request.state.empresa_id
    if not empresa_id or empresa_id == "undefined":
        raise HTTPException(status_code=401)
    emp_uuid = valida_uuid(str(empresa_id))

    if quantitat_retornada < 0 or quantitat_mermada < 0:
        raise HTTPException(status_code=422, detail="Les quantitats no poden ser negatives")

    linia_res = await db.execute(
        select(LiniaPicking).where(
            LiniaPicking.id == linia_id,
            LiniaPicking.empresa_id == emp_uuid,
        )
    )
    linia = linia_res.scalars().first()
    if not linia:
        raise HTTPException(status_code=404, detail="Línia de picking no trobada")

    linia.quantitat_retornada_pick_out = quantitat_retornada
    linia.quantitat_mermada = quantitat_mermada

    # Reintegrar els sobrants i descomptar consum real + mermes del magatzem exacte
    stmt_estoc = select(EstocMagatzem).where(
        EstocMagatzem.empresa_id == emp_uuid,
        EstocMagatzem.article_id == linia.article_id,
    )
    if linia.magatzem_id:
        stmt_estoc = stmt_estoc.where(EstocMagatzem.magatzem_id == linia.magatzem_id)

    estoc_res = await db.execute(stmt_estoc.with_for_update())
    estoc = estoc_res.scalars().first()
    if estoc:
        base_carregada = float(linia.quantitat_carregada_pick_in or 0.0)
        consum_real = max(0.0, base_carregada - float(quantitat_retornada) - float(quantitat_mermada))
        baixa_fisica_total = consum_real + float(quantitat_mermada)

        estoc.quantitat_virtual_reservada = max(
            0.0,
            float(estoc.quantitat_virtual_reservada) - float(linia.quantitat_prevista or 0.0),
        )
        estoc.quantitat_fisica = max(0.0, float(estoc.quantitat_fisica) - baixa_fisica_total)
        estoc.quantitat_cuarentena = float(estoc.quantitat_cuarentena) + float(quantitat_mermada)

        if baixa_fisica_total > 0:
            db.add(
                MovimentEstoc(
                    empresa_id=emp_uuid,
                    magatzem_id=estoc.magatzem_id,
                    article_id=linia.article_id,
                    tipus_moviment="SORTIDA",
                    quantitat=baixa_fisica_total,
                    usuari_id=None,
                    referencia_document=str(linia.picking_id),
                    notes=(
                        f"Picking pick-out: consum_real={consum_real}, "
                        f"retorn={quantitat_retornada}, merma={quantitat_mermada}"
                    ),
                )
            )

    resp_data = {
        "id": linia.id,
        "article_id": linia.article_id,
        "magatzem_id": linia.magatzem_id,
        "quantitat_prevista": float(linia.quantitat_prevista),
        "quantitat_carregada_pick_in": float(linia.quantitat_carregada_pick_in or 0.0),
        "quantitat_retornada_pick_out": float(linia.quantitat_retornada_pick_out or 0.0),
        "quantitat_mermada": float(linia.quantitat_mermada or 0.0),
    }

    await db.commit()

    art_obj = (
        await db.execute(
            select(Article).where(Article.id == linia.article_id, Article.empresa_id == emp_uuid)
        )
    ).scalars().first()
    if art_obj:
        await _sync_article_disc(db, emp_uuid, art_obj)
    await _sincronitzar_picking_disc(db, emp_uuid, linia.picking_id)
    return resp_data


@router.post("/albara/ocr", response_model=dict, status_code=status.HTTP_202_ACCEPTED)
async def processar_document_ocr(
    request: Request,
    fitxer: UploadFile = File(...),
    db: AsyncSession = Depends(get_db_with_tenant_context),
):
    empresa_id = request.state.empresa_id
    if not empresa_id or empresa_id == "undefined":
        raise HTTPException(status_code=401)

    uuid.UUID(empresa_id)

    file_bytes = await fitxer.read()

    from app.services.ocr_service import processar_albara_ocr

    ocr_result = await processar_albara_ocr(file_bytes)

    # Retorna l'estructura estandarditzada per a la interfície
    return {
        "task_id": "ocr-" + str(uuid.uuid4())[:8],
        "status": ocr_result.get("status", "PENDENT_REVISIO_MANUAL"),
        "ocr_data": ocr_result,
        "proveidor": {
            "nif": ocr_result.get("proveidor_nif") or "B00000000",
            "nom": ocr_result.get("proveidor_nom") or "Proveïdor per revisar",
            "adreca": "",
            "telefon": "",
            "email": "",
        },
        "numero_document": ocr_result.get("numero_albara")
        or f"ALB-{date.today().strftime('%Y%m%d')}-01",
        "tipus_document": "ALBARA",
        "data_document": ocr_result.get("data_albara") or date.today().isoformat(),
        "linies": ocr_result.get("linies") or [],
    }


@router.post("/albara/confirmar", status_code=status.HTTP_201_CREATED)
async def confirmar_document(
    request: Request,
    payload: ConfirmarDocumentRequest,
    db: AsyncSession = Depends(get_db_with_tenant_context),
):
    raw_emp = getattr(request.state, "empresa_id", None)
    if not raw_emp or raw_emp in ("undefined", "null", "None"):
        raise HTTPException(status_code=401, detail="No identificat")
    empresa_id = valida_uuid(str(raw_emp))

    # 1. Buscar o crear Proveïdor dins del tenant (per NIF o nom)
    stmt_prov = select(Proveidor).where(
        Proveidor.empresa_id == empresa_id,
        or_(
            Proveidor.nif == payload.proveidor.nif,
            func.lower(Proveidor.rao_social) == payload.proveidor.nom.strip().lower(),
        ),
    )
    prov = (await db.execute(stmt_prov)).scalars().first()

    if not prov:
        prov = Proveidor(
            empresa_id=empresa_id,
            codi=f"PRV-{str(uuid.uuid4())[:6].upper()}",
            rao_social=payload.proveidor.nom,
            nif=payload.proveidor.nif,
            telefon=payload.proveidor.telefon,
            email=payload.proveidor.email,
            especialitat="MATERIALS",
        )
        db.add(prov)
        await db.flush()
    else:
        if payload.proveidor.telefon and not prov.telefon:
            prov.telefon = payload.proveidor.telefon
        if payload.proveidor.email and not prov.email:
            prov.email = payload.proveidor.email
        await db.flush()

    ruta_sobirana_proveidor = f"vault://{empresa_id}/02_proveidors/fitxes/{prov.id}.json"

    # Buscar el magatzem principal del tenant
    stmt_mag = select(Magatzem).where(
        Magatzem.empresa_id == empresa_id,
        Magatzem.tipus == "NAU_CENTRAL",
    )
    magatzem = (await db.execute(stmt_mag)).scalars().first()
    if not magatzem:
        magatzem = Magatzem(empresa_id=empresa_id, nom="Nau Central Base", tipus="NAU_CENTRAL")
        db.add(magatzem)
        await db.flush()

    articles_creats = 0
    moviments_creats = 0

    if payload.tipus_document == "FACTURA":
        if not payload.numero_albarans_vinculats:
            raise HTTPException(
                status_code=400,
                detail="La factura necessita referenciar almenys un número d'albarà per creuar dades.",
            )

        quantitat_total_albarans = 0.0

        for num_albara in payload.numero_albarans_vinculats:
            stmt_alb = select(AlbaraProveidor).where(
                AlbaraProveidor.empresa_id == empresa_id,
                AlbaraProveidor.numero_albara == num_albara,
            )
            albara_db = (await db.execute(stmt_alb)).scalars().first()
            if not albara_db:
                raise HTTPException(
                    status_code=400,
                    detail=f"No s'ha trobat l'albarà {num_albara}. No podem validar la factura.",
                )

            if albara_db.proveidor_id != prov.id:
                raise HTTPException(
                    status_code=400,
                    detail=f"L'albarà {num_albara} no pertany a aquest proveïdor (NIF diferent).",
                )

            if payload.data_document <= albara_db.data_albara:
                raise HTTPException(
                    status_code=400,
                    detail=f"La data de la factura ha de ser posterior a la de l'albarà {num_albara}.",
                )

            stmt_movs = select(MovimentEstoc).where(
                MovimentEstoc.empresa_id == empresa_id,
                MovimentEstoc.magatzem_id == magatzem.id,
                MovimentEstoc.referencia_document == num_albara,
            )
            moviments_albara = (await db.execute(stmt_movs)).scalars().all()
            quantitat_total_albarans += sum(float(m.quantitat) for m in moviments_albara)

        quantitat_factura = sum(
            float(lin.quantitat) for lin in payload.linies if lin.tipus != "EINA"
        )

        if abs(quantitat_total_albarans - quantitat_factura) > 0.01:
            raise HTTPException(
                status_code=400,
                detail="DISCORDÀNCIA: Les quantitats de la factura no quadren amb la suma dels albarans vinculats. Revisa-ho manualment.",
            )

        base_imposable = sum(
            (lin.quantitat * lin.preu) * (1 - (lin.descompte_percent / 100))
            for lin in payload.linies
        )
        quota_iva = base_imposable * 0.21

        stmt_fact = select(FacturaProveidor).where(
            FacturaProveidor.empresa_id == empresa_id,
            FacturaProveidor.proveidor_id == prov.id,
            FacturaProveidor.numero_factura == payload.numero_document,
        )
        if (await db.execute(stmt_fact)).scalars().first():
            raise HTTPException(
                status_code=400, detail="Aquesta factura ja ha estat registrada prèviament."
            )

        factura = FacturaProveidor(
            empresa_id=empresa_id,
            proveidor_id=prov.id,
            numero_factura=payload.numero_document,
            data_factura=payload.data_document,
            base_imposable=base_imposable,
            quota_iva=quota_iva,
            total=base_imposable + quota_iva,
            albara_numero=",".join(payload.numero_albarans_vinculats),
        )
        db.add(factura)
        await db.commit()

        try:
            ruta_sobirana_proveidor = await SovereignStorageGateway.desar_entitat_json(
                db=db,
                empresa_id=empresa_id,
                categoria="proveidors",
                item_id=str(prov.id),
                dades={
                    "id": str(prov.id),
                    "codi": prov.codi,
                    "rao_social": prov.rao_social,
                    "nif": prov.nif,
                    "telefon": prov.telefon,
                    "email": prov.email,
                },
            )
            await SovereignStorageGateway.desar_entitat_json(
                db=db,
                empresa_id=empresa_id,
                categoria="factures_proveidors",
                item_id=str(factura.id),
                dades={
                    "id": str(factura.id),
                    "proveidor_id": str(prov.id),
                    "numero_factura": factura.numero_factura,
                    "data_factura": factura.data_factura.isoformat(),
                    "base_imposable": float(factura.base_imposable),
                    "quota_iva": float(factura.quota_iva),
                    "total": float(factura.total),
                    "albarans": payload.numero_albarans_vinculats,
                },
            )
            if not str(ruta_sobirana_proveidor).startswith("transit://"):
                await SovereignStorageGateway.drenar_cua_transit_empresa(db, empresa_id)
        except Exception as exc:
            logger.warning("No s'ha pogut sincronitzar factura proveïdor al disc sobirà: %s", exc)

        return {
            "estat": "OK",
            "missatge": "Factura validada amb els albarans i enviada a Control Econòmic.",
            "factura_id": str(factura.id),
            "carpeta": ruta_sobirana_proveidor,
        }

    else:
        stmt_alb_check = select(AlbaraProveidor).where(
            AlbaraProveidor.empresa_id == empresa_id,
            AlbaraProveidor.proveidor_id == prov.id,
            AlbaraProveidor.numero_albara == payload.numero_document,
        )
        if (await db.execute(stmt_alb_check)).scalars().first():
            raise HTTPException(
                status_code=400,
                detail="Albarà ja pujat. Aquest document ja consta al sistema per aquest proveïdor.",
            )

        nou_albara = AlbaraProveidor(
            empresa_id=empresa_id,
            proveidor_id=prov.id,
            numero_albara=payload.numero_document,
            data_albara=payload.data_document,
        )
        db.add(nou_albara)
        articles_afectats: List[Article] = []

        for linia in payload.linies:
            nou_preu = float(linia.preu) * (1.0 - (float(linia.descompte_percent) / 100.0))

            if linia.tipus == "EINA":
                quantitat = int(linia.quantitat) if linia.quantitat > 0 else 1
                for _ in range(quantitat):
                    eina_ocr = EinaCustodia(
                        empresa_id=empresa_id,
                        referencia_fabricant=linia.referencia[:100] if linia.referencia else None,
                        nom=linia.nom.strip()[:500] if linia.nom else "Eina sense nom",
                        model="OCR pendent revisió",
                        numero_serie=f"PENDENT_SN_{uuid.uuid4().hex[:8].upper()}",
                        estat="DISPONIBLE",
                    )
                    db.add(eina_ocr)
                await db.flush()
                continue

            ref_neta = (
                linia.referencia.strip()[:50]
                if linia.referencia
                else f"REF-{uuid.uuid4().hex[:8].upper()}"
            )
            stmt_art = select(Article).where(
                Article.empresa_id == empresa_id,
                Article.referencia_inventari == ref_neta,
            )
            article = (await db.execute(stmt_art)).scalars().first()

            if not article:
                nom_net = linia.nom.strip()[:500] if linia.nom else "Article sense nom"
                article = Article(
                    empresa_id=empresa_id,
                    referencia_inventari=ref_neta,
                    nom=nom_net,
                    unitat_mesura="UNITAT",
                    familia="GENERAL",
                    proveidor_id=prov.id,
                    descompte_proveidor=float(linia.descompte_percent),
                    preu_cost=nou_preu,
                )
                db.add(article)
                await db.flush()
                articles_creats += 1
            else:
                if not article.proveidor_id:
                    article.proveidor_id = prov.id
                article.descompte_proveidor = float(linia.descompte_percent)
                estoc_res = await db.execute(
                    select(EstocMagatzem).where(
                        EstocMagatzem.empresa_id == empresa_id,
                        EstocMagatzem.article_id == article.id,
                    )
                )
                estocs_actuals = estoc_res.scalars().all()
                estoc_total_actual = sum(float(e.quantitat_fisica) for e in estocs_actuals)

                if estoc_total_actual + float(linia.quantitat) > 0 and nou_preu > 0:
                    valor_actual = estoc_total_actual * float(article.preu_cost)
                    valor_entrada = float(linia.quantitat) * nou_preu
                    pmp = (valor_actual + valor_entrada) / (
                        estoc_total_actual + float(linia.quantitat)
                    )
                    article.preu_cost = pmp
                elif nou_preu > 0 and estoc_total_actual <= 0:
                    article.preu_cost = nou_preu

            articles_afectats.append(article)

            stmt_estoc = select(EstocMagatzem).where(
                EstocMagatzem.empresa_id == empresa_id,
                EstocMagatzem.magatzem_id == magatzem.id,
                EstocMagatzem.article_id == article.id,
            )
            estoc = (await db.execute(stmt_estoc)).scalars().first()
            if not estoc:
                estoc = EstocMagatzem(
                    empresa_id=empresa_id,
                    magatzem_id=magatzem.id,
                    article_id=article.id,
                    quantitat_fisica=0.0,
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
                notes="Albarà Proveïdor OCR",
            )
            db.add(moviment)
            estoc.quantitat_fisica = float(estoc.quantitat_fisica) + linia.quantitat
            moviments_creats += 1

        await db.commit()

        try:
            ruta_sobirana_proveidor = await SovereignStorageGateway.desar_entitat_json(
                db=db,
                empresa_id=empresa_id,
                categoria="proveidors",
                item_id=str(prov.id),
                dades={
                    "id": str(prov.id),
                    "codi": prov.codi,
                    "rao_social": prov.rao_social,
                    "nif": prov.nif,
                    "telefon": prov.telefon,
                    "email": prov.email,
                },
            )
            await SovereignStorageGateway.desar_entitat_json(
                db=db,
                empresa_id=empresa_id,
                categoria="albarans",
                item_id=str(nou_albara.id),
                dades={
                    "id": str(nou_albara.id),
                    "proveidor_id": str(prov.id),
                    "numero_albara": nou_albara.numero_albara,
                    "data_albara": nou_albara.data_albara.isoformat(),
                    "linies": [lin.model_dump() for lin in payload.linies],
                },
            )
            for art_afectat in articles_afectats:
                await _sync_article_disc(db, empresa_id, art_afectat)
            if not str(ruta_sobirana_proveidor).startswith("transit://"):
                await SovereignStorageGateway.drenar_cua_transit_empresa(db, empresa_id)
        except Exception as exc:
            logger.warning("No s'ha pogut sincronitzar l'albarà OCR al disc sobirà: %s", exc)

        return {
            "estat": "OK",
            "missatge": "Albarà registrat, estoc augmentat.",
            "proveidor_id": str(prov.id),
            "articles_creats": articles_creats,
            "moviments_realitzats": moviments_creats,
            "carpeta": ruta_sobirana_proveidor,
        }


@router.put("/articles/{article_id}", response_model=ArticleResponse)
async def modificar_article(
    request: Request,
    article_id: uuid.UUID,
    article: ArticleCreate,
    claims: dict = Depends(get_current_user_claims),
    db: AsyncSession = Depends(get_db_with_tenant_context),
):
    empresa_id = request.state.empresa_id
    if not empresa_id or empresa_id == "undefined":
        raise HTTPException(status_code=401, detail="No identificat")
    emp_uuid = valida_uuid(str(empresa_id))
    rol = str(claims.get("rol", "")).upper()

    stmt = select(Article).where(
        Article.id == article_id,
        Article.empresa_id == emp_uuid,
    )
    result = await db.execute(stmt)
    art_db = result.scalars().first()
    if not art_db:
        raise HTTPException(status_code=404, detail="Article no trobat")

    codi_barres_net = _normalitzar_codi_barres(article.codi_barres)

    dup_ref = (
        await db.execute(
            select(Article.id).where(
                Article.empresa_id == emp_uuid,
                Article.referencia_inventari == article.referencia_inventari,
                Article.id != article_id,
            )
        )
    ).first()
    if dup_ref:
        raise HTTPException(
            status_code=400, detail="Ja existeix un altre article amb aquesta referència."
        )

    if codi_barres_net:
        dup_cb = (
            await db.execute(
                select(Article.id).where(
                    Article.empresa_id == emp_uuid,
                    Article.codi_barres == codi_barres_net,
                    Article.id != article_id,
                )
            )
        ).first()
        if dup_cb:
            raise HTTPException(
                status_code=400, detail="Ja existeix un altre article amb aquest codi de barres."
            )

    art_db.referencia_inventari = article.referencia_inventari
    art_db.codi_barres = codi_barres_net
    art_db.nom = article.nom
    art_db.unitat_mesura = article.unitat_mesura
    art_db.es_material_continu = article.es_material_continu
    art_db.familia = article.familia
    art_db.estoc_optim = article.estoc_optim
    art_db.estoc_minim = article.estoc_minim
    art_db.es_lot_caducable = article.es_lot_caducable
    # Principi VI: Un ENGINYER mai pot sobreescriure ni visualitzar camps econòmics interns
    if rol != "ENGINYER":
        art_db.preu_cost = article.preu_cost
        art_db.descompte_proveidor = article.descompte_proveidor
        art_db.marge_guanys = article.marge_guanys
    art_db.preu_venda = article.preu_venda
    art_db.proveidor_id = article.proveidor_id

    await db.commit()

    stmt_estoc = select(
        func.coalesce(func.sum(EstocMagatzem.quantitat_fisica), 0.0),
        func.coalesce(func.sum(EstocMagatzem.quantitat_virtual_reservada), 0.0),
    ).where(
        EstocMagatzem.empresa_id == emp_uuid,
        EstocMagatzem.article_id == article_id,
    )
    estoc_row = (await db.execute(stmt_estoc)).one()
    estoc_fisic = float(estoc_row[0] or 0.0)
    estoc_reservat = float(estoc_row[1] or 0.0)

    await _sync_article_disc(
        db=db,
        empresa_id=emp_uuid,
        art=art_db,
        estoc_fisic=estoc_fisic,
        estoc_reservat=estoc_reservat,
    )

    prov_nom: Optional[str] = None
    if art_db.proveidor_id:
        prov_nom = (
            await db.execute(
                select(Proveidor.rao_social).where(
                    Proveidor.id == art_db.proveidor_id,
                    Proveidor.empresa_id == emp_uuid,
                )
            )
        ).scalar()

    return _serialitzar_article(
        art=art_db,
        estoc_fisic=estoc_fisic,
        estoc_reservat=estoc_reservat,
        prov_nom=prov_nom,
        rol=rol,
    )


@router.get("/eines", response_model=List[EinaResponse])
async def llistar_eines(
    request: Request,
    magatzem_id: Optional[uuid.UUID] = None,
    db: AsyncSession = Depends(get_db_with_tenant_context),
):
    empresa_id = getattr(request.state, "empresa_id", None) or request.headers.get("X-Empresa-ID")
    if not empresa_id or empresa_id in ("undefined", "null", "None"):
        raise HTTPException(status_code=401, detail="No identificat")
    emp_uuid = valida_uuid(empresa_id)

    stmt = (
        select(EinaCustodia, Usuari.nom, Usuari.cognoms, Magatzem.nom)
        .outerjoin(Usuari, EinaCustodia.custodiat_per_operari_id == Usuari.id)
        .outerjoin(Magatzem, EinaCustodia.magatzem_id == Magatzem.id)
        .where(EinaCustodia.empresa_id == emp_uuid)
    )
    if magatzem_id:
        stmt = stmt.where(EinaCustodia.magatzem_id == magatzem_id)

    res = await db.execute(stmt)
    resultats = []
    for eina, u_nom, u_cognoms, mag_nom in res.all():
        cust_nom = None
        if u_nom:
            cust_nom = f"{u_nom} {u_cognoms or ''}".strip()
        elif mag_nom:
            cust_nom = mag_nom

        resp = EinaResponse(
            id=eina.id,
            referencia_fabricant=eina.referencia_fabricant,
            nom=eina.nom,
            model=eina.model,
            numero_serie=eina.numero_serie,
            data_fi_garantia=eina.data_fi_garantia,
            observacions=eina.observacions,
            incidencies=eina.incidencies,
            estat=eina.estat,
            custodiat_per_operari_id=eina.custodiat_per_operari_id,
            magatzem_id=eina.magatzem_id,
            custodia_nom=cust_nom,
        )
        resultats.append(resp)
    return resultats


class CheckoutPayload(BaseModel):
    operari_id: Optional[uuid.UUID] = None
    magatzem_id: Optional[uuid.UUID] = None


@router.post("/eines/{eina_id}/checkout", response_model=EinaResponse)
async def checkout_eina(
    eina_id: uuid.UUID,
    payload: CheckoutPayload,
    request: Request,
    db: AsyncSession = Depends(get_db_with_tenant_context),
):
    empresa_id = getattr(request.state, "empresa_id", None) or request.headers.get("X-Empresa-ID")
    if not empresa_id or empresa_id in ("undefined", "null", "None"):
        raise HTTPException(status_code=401, detail="No identificat")
    emp_uuid = valida_uuid(empresa_id)

    stmt = select(EinaCustodia).where(
        EinaCustodia.id == eina_id, EinaCustodia.empresa_id == emp_uuid
    )
    res = await db.execute(stmt)
    eina = res.scalars().first()
    if not eina:
        raise HTTPException(status_code=404, detail="Eina no trobada")

    if eina.estat != "DISPONIBLE":
        raise HTTPException(status_code=400, detail="Eina no disponible per checkout")

    if payload.magatzem_id:
        eina.estat = "EN_VEHICLE"
        eina.magatzem_id = payload.magatzem_id
        eina.custodiat_per_operari_id = None
    elif payload.operari_id:
        eina.estat = "CUSTODIADA"
        eina.custodiat_per_operari_id = payload.operari_id
        eina.magatzem_id = None
    else:
        raise HTTPException(
            status_code=400, detail="Cal especificar un operari o un vehicle/magatzem"
        )

    await db.commit()
    return eina


@router.post("/eines/{eina_id}/checkin", response_model=EinaResponse)
async def checkin_eina(
    eina_id: uuid.UUID, request: Request, db: AsyncSession = Depends(get_db_with_tenant_context)
):
    empresa_id = getattr(request.state, "empresa_id", None) or request.headers.get("X-Empresa-ID")
    if not empresa_id or empresa_id in ("undefined", "null", "None"):
        raise HTTPException(status_code=401, detail="No identificat")
    emp_uuid = valida_uuid(empresa_id)

    stmt = select(EinaCustodia).where(
        EinaCustodia.id == eina_id, EinaCustodia.empresa_id == emp_uuid
    )
    res = await db.execute(stmt)
    eina = res.scalars().first()
    if not eina:
        raise HTTPException(status_code=404, detail="Eina no trobada")

    if eina.estat not in ("CUSTODIADA", "EN_VEHICLE"):
        raise HTTPException(
            status_code=400,
            detail="L'eina no està en custòdia ni en vehicle actualment",
        )

    eina.estat = "DISPONIBLE"
    eina.custodiat_per_operari_id = None
    eina.magatzem_id = None
    await db.commit()
    return eina


@router.put("/eines/{eina_id}", response_model=EinaResponse)
async def modificar_eina(
    eina_id: uuid.UUID,
    payload: EinaCreate,
    request: Request,
    db: AsyncSession = Depends(get_db_with_tenant_context),
):
    empresa_id = getattr(request.state, "empresa_id", None) or request.headers.get("X-Empresa-ID")
    if not empresa_id or empresa_id in ("undefined", "null", "None"):
        raise HTTPException(status_code=401, detail="No identificat")
    emp_uuid = valida_uuid(empresa_id)

    stmt = select(EinaCustodia).where(
        EinaCustodia.id == eina_id, EinaCustodia.empresa_id == emp_uuid
    )
    res = await db.execute(stmt)
    eina = res.scalars().first()
    if not eina:
        raise HTTPException(status_code=404, detail="Eina no trobada")

    eina.referencia_fabricant = payload.referencia_fabricant
    eina.nom = payload.nom
    eina.model = payload.model
    eina.numero_serie = payload.numero_serie
    eina.data_fi_garantia = payload.data_fi_garantia
    eina.observacions = payload.observacions
    eina.incidencies = payload.incidencies

    resp_eina = {
        "id": eina.id,
        "referencia_fabricant": eina.referencia_fabricant,
        "nom": eina.nom,
        "model": eina.model,
        "numero_serie": eina.numero_serie,
        "data_fi_garantia": eina.data_fi_garantia,
        "observacions": eina.observacions,
        "incidencies": eina.incidencies,
        "estat": eina.estat,
        "custodiat_per_operari_id": eina.custodiat_per_operari_id,
        "magatzem_id": eina.magatzem_id,
        "custodia_nom": None,
    }
    await db.commit()
    try:
        ruta = await SovereignStorageGateway.desar_entitat_json(
            db=db,
            empresa_id=emp_uuid,
            categoria="magatzem_eines",
            item_id=str(eina.id),
            dades={
                "id": str(eina.id),
                "referencia_fabricant": eina.referencia_fabricant,
                "nom": eina.nom,
                "model": eina.model,
                "numero_serie": eina.numero_serie,
                "data_fi_garantia": (
                    eina.data_fi_garantia.isoformat() if eina.data_fi_garantia else None
                ),
                "estat": eina.estat,
                "observacions": eina.observacions,
                "incidencies": eina.incidencies,
            },
        )
        if not str(ruta).startswith("transit://"):
            await SovereignStorageGateway.drenar_cua_transit_empresa(db, emp_uuid)
    except Exception as exc:
        logger.warning("No s'ha pogut sincronitzar eina %s al disc sobirà: %s", eina.id, exc)
    return resp_eina


@router.post("/ocr-albara")
async def ocr_albara(request: Request, fitxer: UploadFile = File(...)):
    empresa_id = request.state.empresa_id
    if not empresa_id or empresa_id == "undefined":
        raise HTTPException(status_code=401, detail="No identificat")

    from app.services.ocr_service import processar_albara_ocr

    file_bytes = await fitxer.read()
    result = await processar_albara_ocr(file_bytes)
    return result


class TraspasRequest(BaseModel):
    article_id: uuid.UUID
    origen_magatzem_id: uuid.UUID
    desti_magatzem_id: uuid.UUID
    quantitat: float


@router.post("/traspas")
@router.post("/traspas-furgoneta")
async def traspas_estoc(
    request: Request,
    payload: TraspasRequest,
    db: AsyncSession = Depends(get_db_with_tenant_context),
):
    empresa_id = request.state.empresa_id
    if not empresa_id or empresa_id == "undefined":
        raise HTTPException(status_code=401, detail="No identificat")
    emp_uuid = valida_uuid(str(empresa_id))

    if payload.quantitat <= 0:
        raise HTTPException(status_code=400, detail="La quantitat ha de ser superior a 0")

    mag_origen = (
        await db.execute(
            select(Magatzem).where(
                Magatzem.id == payload.origen_magatzem_id,
                Magatzem.empresa_id == emp_uuid,
            )
        )
    ).scalars().first()
    mag_desti = (
        await db.execute(
            select(Magatzem).where(
                Magatzem.id == payload.desti_magatzem_id,
                Magatzem.empresa_id == emp_uuid,
            )
        )
    ).scalars().first()
    if not mag_origen or not mag_desti:
        raise HTTPException(status_code=404, detail="Magatzem d'origen o destí no trobat")

    art_obj = (
        await db.execute(
            select(Article).where(
                Article.id == payload.article_id,
                Article.empresa_id == emp_uuid,
            )
        )
    ).scalars().first()
    if not art_obj:
        raise HTTPException(status_code=404, detail="Article no trobat")

    # Lock source and dest rows to prevent race conditions
    stmt_origen = (
        select(EstocMagatzem)
        .where(
            EstocMagatzem.empresa_id == emp_uuid,
            EstocMagatzem.magatzem_id == payload.origen_magatzem_id,
            EstocMagatzem.article_id == payload.article_id,
        )
        .with_for_update()
    )

    origen = (await db.execute(stmt_origen)).scalars().first()
    disponible_origen = (
        float(origen.quantitat_fisica) - float(origen.quantitat_virtual_reservada)
        if origen
        else 0.0
    )
    if not origen or disponible_origen < payload.quantitat:
        raise HTTPException(
            status_code=400,
            detail=f"No hi ha prou estoc disponible a l'origen (disponible: {disponible_origen})",
        )

    stmt_desti = (
        select(EstocMagatzem)
        .where(
            EstocMagatzem.empresa_id == emp_uuid,
            EstocMagatzem.magatzem_id == payload.desti_magatzem_id,
            EstocMagatzem.article_id == payload.article_id,
        )
        .with_for_update()
    )

    desti = (await db.execute(stmt_desti)).scalars().first()
    if not desti:
        desti = EstocMagatzem(
            empresa_id=emp_uuid,
            magatzem_id=payload.desti_magatzem_id,
            article_id=payload.article_id,
            quantitat_fisica=0.0,
        )
        db.add(desti)
        await db.flush()

    origen.quantitat_fisica = float(origen.quantitat_fisica) - payload.quantitat
    desti.quantitat_fisica = float(desti.quantitat_fisica) + payload.quantitat

    mov_sortida = MovimentEstoc(
        empresa_id=emp_uuid,
        magatzem_id=payload.origen_magatzem_id,
        article_id=payload.article_id,
        tipus_moviment="SORTIDA",
        quantitat=payload.quantitat,
        notes=f"Traspàs a {payload.desti_magatzem_id}",
    )
    mov_entrada = MovimentEstoc(
        empresa_id=emp_uuid,
        magatzem_id=payload.desti_magatzem_id,
        article_id=payload.article_id,
        tipus_moviment="ENTRADA",
        quantitat=payload.quantitat,
        notes=f"Traspàs des de {payload.origen_magatzem_id}",
    )
    db.add(mov_sortida)
    db.add(mov_entrada)

    await db.commit()
    await _sync_article_disc(db, emp_uuid, art_obj)
    return {"estat": "OK", "missatge": "Traspàs completat amb èxit."}


@router.post("/entrades-pmp", status_code=status.HTTP_200_OK)
async def registrar_entrada_pmp(
    request: Request,
    payload: EntradaPMPRequest,
    claims: dict = Depends(get_current_user_claims),
    db: AsyncSession = Depends(get_db_with_tenant_context),
):
    """Entrada d'albarà amb control de Preu Ferm, tolerància +-2% granel i recàlcul atòmic de PMP."""
    empresa_uuid = valida_uuid(str(request.state.empresa_id))
    usuari_uuid = uuid.UUID(str(claims["sub"])) if claims.get("sub") else None
    return await processar_entrada_albara_i_recalcular_pmp(
        db=db,
        empresa_id=empresa_uuid,
        article_id=payload.article_id,
        magatzem_id=payload.magatzem_id,
        quantitat_rebuda=payload.quantitat_rebuda,
        preu_compra_unitari=payload.preu_compra_unitari,
        preu_ferm_comanda=payload.preu_ferm_comanda,
        es_granel_continu=payload.es_granel_continu,
        quantitat_demanada_comanda=payload.quantitat_demanada_comanda,
        referencia_document=payload.referencia_document,
        usuari_id=usuari_uuid,
    )


@router.post("/mermes", status_code=status.HTTP_201_CREATED)
async def registrar_merma_inventari(
    request: Request,
    payload: MermaInventariRequest,
    claims: dict = Depends(get_current_user_claims),
    db: AsyncSession = Depends(get_db_with_tenant_context),
):
    """Registra una merma, mou unitats al Slot de Residus i l'imputa a Comptabilitat (600/659)."""
    empresa_uuid = valida_uuid(str(request.state.empresa_id))
    usuari_uuid = uuid.UUID(str(claims["sub"])) if claims.get("sub") else None
    return await registrar_merma_i_imputar_a_comptabilitat(
        db=db,
        empresa_id=empresa_uuid,
        article_id=payload.article_id,
        magatzem_id=payload.magatzem_id,
        quantitat_mermada=payload.quantitat_mermada,
        motiu=payload.motiu,
        ordre_treball_id=payload.ordre_treball_id,
        usuari_id=usuari_uuid,
        notes=payload.notes,
    )


@router.get("/mermes")
async def llistar_mermes_inventari(
    request: Request,
    limit: int = 50,
    db: AsyncSession = Depends(get_db_with_tenant_context),
):
    """Llista les mermes d'inventari del tenant ordenades de més recent a més antiga."""
    empresa_uuid = valida_uuid(str(request.state.empresa_id))
    stmt = (
        select(MermaInventari, Article.nom, Article.referencia_inventari, OrdreTreball.codi)
        .join(Article, MermaInventari.article_id == Article.id)
        .outerjoin(OrdreTreball, MermaInventari.ordre_treball_id == OrdreTreball.id)
        .where(MermaInventari.empresa_id == empresa_uuid)
        .order_by(MermaInventari.created_at.desc())
        .limit(limit)
    )
    rows = (await db.execute(stmt)).all()
    return [
        {
            "id": str(m.id),
            "article_id": str(m.article_id),
            "article_nom": art_nom,
            "article_ref": art_ref,
            "magatzem_id": str(m.magatzem_id),
            "ordre_treball_id": str(m.ordre_treball_id) if m.ordre_treball_id else None,
            "ordre_treball_codi": ot_codi,
            "quantitat": float(m.quantitat),
            "pmp_aplicat": float(m.pmp_aplicat),
            "cost_total": float(m.cost_total),
            "motiu": m.motiu,
            "subcompte_comptable": m.subcompte_comptable,
            "transferit_slot_residus": bool(m.transferit_slot_residus),
            "notes": m.notes,
            "created_at": m.created_at.isoformat() if m.created_at else None,
        }
        for m, art_nom, art_ref, ot_codi in rows
    ]


# ---------------------------------------------------------------------------
# Safata HITL de Recompra d'Estoc Mínim (Spec 01-backoffice FR-010)
# ---------------------------------------------------------------------------


class RecompraAccioRequest(BaseModel):
    accio: str = Field(..., pattern="^(APROVAR|DESCARTAR)$")
    quantitat_aprovada: Optional[float] = Field(default=None, gt=0)
    notes: Optional[str] = Field(default=None, max_length=500)


def _serialitzar_alerta_recompra(
    alerta: AlertaGarantiaRecompra,
    art_nom: Optional[str],
    art_ref: Optional[str],
    art_cb: Optional[str],
    prov_nom: Optional[str],
    rol: str,
) -> Dict[str, Any]:
    proposta = dict(alerta.dades_comanda_proposta or {})
    if rol.upper() == "ENGINYER":
        proposta["preu_unitari_estimat"] = None
        proposta["import_estimat"] = None

    return {
        "id": str(alerta.id),
        "tipus_alerta": alerta.tipus_alerta,
        "article_id": str(alerta.article_id) if alerta.article_id else None,
        "article_nom": art_nom or proposta.get("nom"),
        "article_ref": art_ref or proposta.get("referencia"),
        "article_codi_barres": art_cb or proposta.get("codi_barres"),
        "proveidor_id": str(alerta.proveidor_id) if alerta.proveidor_id else None,
        "proveidor_nom": prov_nom or proposta.get("proveidor_nom"),
        "missatge": alerta.missatge,
        "estat": alerta.estat,
        "dades_comanda_proposta": proposta,
        "enviat_automaticament": False,
        "created_at": alerta.created_at.isoformat() if alerta.created_at else None,
        "updated_at": alerta.updated_at.isoformat() if alerta.updated_at else None,
    }


@router.get("/recompra")
async def llistar_esborranys_recompra(
    request: Request,
    estat: Optional[str] = None,
    claims: dict = Depends(get_current_user_claims),
    db: AsyncSession = Depends(get_db_with_tenant_context),
):
    """Llista la safata HITL de propostes de recompra per trencament d'estoc (FR-010)."""
    empresa_raw = getattr(request.state, "empresa_id", None) or claims.get("empresa_id")
    if not empresa_raw or str(empresa_raw) == "undefined":
        raise HTTPException(status_code=401, detail="No identificat")
    emp_uuid = valida_uuid(str(empresa_raw))
    rol = str(claims.get("rol", "")).upper()

    stmt = (
        select(
            AlertaGarantiaRecompra,
            Article.nom,
            Article.referencia_inventari,
            Article.codi_barres,
            Proveidor.rao_social,
        )
        .outerjoin(Article, AlertaGarantiaRecompra.article_id == Article.id)
        .outerjoin(Proveidor, AlertaGarantiaRecompra.proveidor_id == Proveidor.id)
        .where(
            AlertaGarantiaRecompra.empresa_id == emp_uuid,
            AlertaGarantiaRecompra.tipus_alerta == "RECOMPRA_STOCK",
        )
        .order_by(AlertaGarantiaRecompra.created_at.desc())
    )
    if estat and estat.upper() != "TOTES":
        stmt = stmt.where(AlertaGarantiaRecompra.estat == estat.upper())

    rows = (await db.execute(stmt)).all()
    return [
        _serialitzar_alerta_recompra(alerta, art_nom, art_ref, art_cb, prov_nom, rol)
        for alerta, art_nom, art_ref, art_cb, prov_nom in rows
    ]


@router.post("/recompra/escanejar", status_code=status.HTTP_201_CREATED)
async def escanejar_trencaments_recompra(
    request: Request,
    claims: dict = Depends(get_current_user_claims),
    db: AsyncSession = Depends(get_db_with_tenant_context),
):
    """Escaneja articles sota estoc mínim i genera esborranys HITL (mai envia correus automàtics)."""
    empresa_raw = getattr(request.state, "empresa_id", None) or claims.get("empresa_id")
    if not empresa_raw or str(empresa_raw) == "undefined":
        raise HTTPException(status_code=401, detail="No identificat")
    emp_uuid = valida_uuid(str(empresa_raw))
    rol = str(claims.get("rol", "")).upper()

    stmt_arts = (
        select(Article, Proveidor.rao_social, Proveidor.email)
        .outerjoin(Proveidor, Article.proveidor_id == Proveidor.id)
        .where(
            Article.empresa_id == emp_uuid,
            Article.actiu.is_(True),
            Article.estoc_minim > 0,
        )
    )
    articles_rows = (await db.execute(stmt_arts)).all()
    if not articles_rows:
        return {"esborranys_generats": 0, "alertes": []}

    stmt_estocs = (
        select(
            EstocMagatzem.article_id,
            func.coalesce(func.sum(EstocMagatzem.quantitat_fisica), 0.0),
            func.coalesce(func.sum(EstocMagatzem.quantitat_virtual_reservada), 0.0),
        )
        .where(EstocMagatzem.empresa_id == emp_uuid)
        .group_by(EstocMagatzem.article_id)
    )
    estoc_map = {
        row[0]: max(0.0, float(row[1] or 0.0) - float(row[2] or 0.0))
        for row in (await db.execute(stmt_estocs)).all()
    }

    existing_actives = set(
        (
            await db.execute(
                select(AlertaGarantiaRecompra.article_id).where(
                    AlertaGarantiaRecompra.empresa_id == emp_uuid,
                    AlertaGarantiaRecompra.tipus_alerta == "RECOMPRA_STOCK",
                    AlertaGarantiaRecompra.estat == "ACTIVA",
                    AlertaGarantiaRecompra.article_id.is_not(None),
                )
            )
        )
        .scalars()
        .all()
    )

    noves_alertes: List[tuple[AlertaGarantiaRecompra, Article, Optional[str]]] = []
    for art, prov_nom, prov_email in articles_rows:
        disponible = estoc_map.get(art.id, 0.0)
        estoc_min = float(art.estoc_minim or 0.0)
        if disponible > estoc_min or art.id in existing_actives:
            continue

        estoc_opt = float(art.estoc_optim or 0.0)
        qty_sug = max(estoc_opt - disponible, estoc_min * 2.0 - disponible, 1.0)
        qty_sug = round(qty_sug, 2)
        preu_unit = float(getattr(art, "pmp_actual", None) or art.preu_cost or 0.0)

        proposta = {
            "article_id": str(art.id),
            "referencia": art.referencia_inventari,
            "codi_barres": getattr(art, "codi_barres", None),
            "nom": art.nom,
            "unitat_mesura": art.unitat_mesura,
            "estoc_disponible": disponible,
            "estoc_minim": estoc_min,
            "estoc_optim": estoc_opt,
            "quantitat_proposada": qty_sug,
            "proveidor_id": str(art.proveidor_id) if art.proveidor_id else None,
            "proveidor_nom": prov_nom,
            "proveidor_email": prov_email,
            "preu_unitari_estimat": preu_unit,
            "import_estimat": round(qty_sug * preu_unit, 2),
            "enviat_automaticament": False,
            "requereix_aprovacio_humana": True,
            "estat_hitl": "ESBORRANY_PENDENT_APROVACIO",
        }
        alerta = AlertaGarantiaRecompra(
            empresa_id=emp_uuid,
            tipus_alerta="RECOMPRA_STOCK",
            article_id=art.id,
            proveidor_id=art.proveidor_id,
            missatge=(
                f"Trencament d'estoc a {art.nom} ({art.referencia_inventari}): "
                f"disponible {disponible} <= mínim {estoc_min}. Esborrany per {qty_sug} {art.unitat_mesura}."
            ),
            estat="ACTIVA",
            dades_comanda_proposta=proposta,
        )
        db.add(alerta)
        noves_alertes.append((alerta, art, prov_nom))

    await db.commit()

    return {
        "esborranys_generats": len(noves_alertes),
        "alertes": [
            _serialitzar_alerta_recompra(
                alerta,
                art.nom,
                art.referencia_inventari,
                getattr(art, "codi_barres", None),
                prov_nom,
                rol,
            )
            for alerta, art, prov_nom in noves_alertes
        ],
    }


@router.patch("/recompra/{alerta_id}")
async def resoldre_esborrany_recompra(
    request: Request,
    alerta_id: uuid.UUID,
    payload: RecompraAccioRequest,
    claims: dict = Depends(get_current_user_claims),
    db: AsyncSession = Depends(get_db_with_tenant_context),
):
    """Aprova o descarta un esborrany HITL de recompra (només BOSS o SECRETARIA; mai auto-envia)."""
    empresa_raw = getattr(request.state, "empresa_id", None) or claims.get("empresa_id")
    if not empresa_raw or str(empresa_raw) == "undefined":
        raise HTTPException(status_code=401, detail="No identificat")
    emp_uuid = valida_uuid(str(empresa_raw))
    rol = str(claims.get("rol", "")).upper()

    if rol not in ("BOSS", "SECRETARIA"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Només direcció o administració (BOSS/SECRETARIA) poden aprovar compres de recompra.",
        )

    stmt = (
        select(
            AlertaGarantiaRecompra,
            Article.nom,
            Article.referencia_inventari,
            Article.codi_barres,
            Proveidor.rao_social,
        )
        .outerjoin(Article, AlertaGarantiaRecompra.article_id == Article.id)
        .outerjoin(Proveidor, AlertaGarantiaRecompra.proveidor_id == Proveidor.id)
        .where(
            AlertaGarantiaRecompra.id == alerta_id,
            AlertaGarantiaRecompra.empresa_id == emp_uuid,
            AlertaGarantiaRecompra.tipus_alerta == "RECOMPRA_STOCK",
        )
    )
    row = (await db.execute(stmt)).first()
    if not row:
        raise HTTPException(status_code=404, detail="Esborrany de recompra no trobat")

    alerta, art_nom, art_ref, art_cb, prov_nom = row
    proposta = dict(alerta.dades_comanda_proposta or {})
    ara = datetime.now(timezone.utc)

    if payload.accio == "APROVAR":
        alerta.estat = "APROVADA"
        if payload.quantitat_aprovada is not None:
            proposta["quantitat_aprovada"] = float(payload.quantitat_aprovada)
            preu_u = float(proposta.get("preu_unitari_estimat") or 0.0)
            proposta["import_estimat"] = round(float(payload.quantitat_aprovada) * preu_u, 2)
        else:
            proposta["quantitat_aprovada"] = float(proposta.get("quantitat_proposada") or 0.0)
        proposta["estat_hitl"] = "APROVADA_PER_EMISSIO_MANUAL"
    else:
        alerta.estat = "DESCARTADA"
        proposta["estat_hitl"] = "DESCARTADA"

    proposta["enviat_automaticament"] = False
    proposta["resolt_per_usuari_id"] = str(claims.get("sub")) if claims.get("sub") else None
    proposta["resolt_en"] = ara.isoformat()
    if payload.notes:
        proposta["notes_hitl"] = payload.notes

    alerta.dades_comanda_proposta = proposta
    alerta.updated_at = ara

    await db.commit()

    if alerta.estat == "APROVADA":
        try:
            ruta = await SovereignStorageGateway.desar_entitat_json(
                db=db,
                empresa_id=emp_uuid,
                categoria="albarans",
                item_id=f"recompra_{alerta.id}",
                dades={
                    "alerta_id": str(alerta.id),
                    "estat": alerta.estat,
                    "article_id": str(alerta.article_id) if alerta.article_id else None,
                    "proveidor_id": str(alerta.proveidor_id) if alerta.proveidor_id else None,
                    "proposta": proposta,
                },
            )
            if not str(ruta).startswith("transit://"):
                await SovereignStorageGateway.drenar_cua_transit_empresa(db, emp_uuid)
        except Exception as exc:
            logger.warning("No s'ha pogut sincronitzar recompra %s al disc sobirà: %s", alerta.id, exc)

    return _serialitzar_alerta_recompra(alerta, art_nom, art_ref, art_cb, prov_nom, rol)
