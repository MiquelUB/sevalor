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
from app.services.codis_service import generar_seguent_codi  # noqa: E402
from app.services.magatzem_comptabilitat_service import (  # noqa: E402
    processar_entrada_albara_i_recalcular_pmp,
    registrar_merma_i_imputar_a_comptabilitat,
)
from app.services.pressupost_service import construir_mailto_url  # noqa: E402
from app.services.recompra_service import (  # noqa: E402
    agrupar_alertes_recompra_per_proveidor,
    avaluar_i_sincronitzar_alertes_recompra,
    construir_text_esborrany_email_recompra,
    enviar_email_recompra_smtp,
    validar_email_destinatari,
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
    nomes_trencament: bool = False,
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

    if nomes_trencament:
        estoc_stmt = select(
            EstocMagatzem.article_id.label("art_id"),
            func.coalesce(
                func.sum(EstocMagatzem.quantitat_fisica - EstocMagatzem.quantitat_virtual_reservada),
                0.0,
            ).label("disp"),
        ).where(EstocMagatzem.empresa_id == empresa_uuid)
        if magatzem_id:
            estoc_stmt = estoc_stmt.where(EstocMagatzem.magatzem_id == magatzem_id)
        estoc_subq = estoc_stmt.group_by(EstocMagatzem.article_id).subquery()

        stmt = stmt.outerjoin(estoc_subq, Article.id == estoc_subq.c.art_id).where(
            Article.actiu.is_(True),
            Article.estoc_minim > 0,
            func.coalesce(estoc_subq.c.disp, 0.0) <= Article.estoc_minim,
        )
        effective_limit = max(limit, 200)
    else:
        effective_limit = limit

    stmt = stmt.limit(effective_limit).offset(offset).order_by(Article.created_at.desc())
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

    await avaluar_i_sincronitzar_alertes_recompra(db, emp_uuid, [nou_article.id])
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

    await avaluar_i_sincronitzar_alertes_recompra(db, emp_uuid, [payload.article_id])
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
    await avaluar_i_sincronitzar_alertes_recompra(db, emp_uuid, [payload.article_id])
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

    await avaluar_i_sincronitzar_alertes_recompra(db, emp_uuid, [linia.article_id])
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


async def _resoldre_o_crear_proveidor_albara(
    db: AsyncSession,
    empresa_id: uuid.UUID,
    prov_ocr: ProveidorOcr,
) -> Proveidor:
    """Cerca o dona d'alta automàticament el proveïdor d'un albarà OCR amb codi seqüencial."""
    stmt_prov = select(Proveidor).where(
        Proveidor.empresa_id == empresa_id,
        or_(
            Proveidor.nif == prov_ocr.nif,
            func.lower(Proveidor.rao_social) == prov_ocr.nom.strip().lower(),
        ),
    )
    prov = (await db.execute(stmt_prov)).scalars().first()
    if not prov:
        codi_prov_auto = await generar_seguent_codi(db, Proveidor, empresa_id, "PRV")
        prov = Proveidor(
            empresa_id=empresa_id,
            codi=codi_prov_auto,
            rao_social=prov_ocr.nom,
            nif=prov_ocr.nif,
            telefon=prov_ocr.telefon,
            email=prov_ocr.email,
            especialitat="MATERIALS",
        )
        db.add(prov)
        await db.flush()
    else:
        if prov_ocr.telefon and not prov.telefon:
            prov.telefon = prov_ocr.telefon
        if prov_ocr.email and not prov.email:
            prov.email = prov_ocr.email
        await db.flush()
    return prov


async def _obtenir_nau_central(db: AsyncSession, empresa_id: uuid.UUID) -> Magatzem:
    """Obté o inicialitza el magatzem principal NAU_CENTRAL del tenant."""
    stmt_mag = select(Magatzem).where(
        Magatzem.empresa_id == empresa_id,
        Magatzem.tipus == "NAU_CENTRAL",
    )
    magatzem = (await db.execute(stmt_mag)).scalars().first()
    if not magatzem:
        magatzem = Magatzem(empresa_id=empresa_id, nom="Nau Central Base", tipus="NAU_CENTRAL")
        db.add(magatzem)
        await db.flush()
    return magatzem


async def _aplicar_linies_albara_a_estoc(
    db: AsyncSession,
    empresa_id: uuid.UUID,
    prov: Proveidor,
    magatzem: Magatzem,
    numero_document: str,
    linies: List[LiniaOcr],
) -> tuple[int, int, List[Article]]:
    """Aplica les línies validades d'un albarà al magatzem, PMP i alertes d'estoc."""
    articles_creats = 0
    moviments_creats = 0
    articles_afectats: List[Article] = []

    for linia in linies:
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
            referencia_document=numero_document,
            notes="Albarà Proveïdor OCR",
        )
        db.add(moviment)
        estoc.quantitat_fisica = float(estoc.quantitat_fisica) + linia.quantitat
        moviments_creats += 1

    if articles_afectats:
        await avaluar_i_sincronitzar_alertes_recompra(
            db, empresa_id, [a.id for a in articles_afectats]
        )
    return articles_creats, moviments_creats, articles_afectats


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
    prov = await _resoldre_o_crear_proveidor_albara(db, empresa_id, payload.proveidor)

    ruta_sobirana_proveidor = f"vault://{empresa_id}/02_proveidors/fitxes/{prov.id}.json"

    # Buscar el magatzem principal del tenant
    magatzem = await _obtenir_nau_central(db, empresa_id)

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
            estat="CONSOLIDAT",
        )
        db.add(nou_albara)
        articles_creats, moviments_creats, articles_afectats = await _aplicar_linies_albara_a_estoc(
            db=db,
            empresa_id=empresa_id,
            prov=prov,
            magatzem=magatzem,
            numero_document=payload.numero_document,
            linies=payload.linies,
        )

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
                    "estat": "CONSOLIDAT",
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
            "albara_id": str(nou_albara.id),
            "proveidor_id": str(prov.id),
            "articles_creats": articles_creats,
            "moviments_realitzats": moviments_creats,
            "carpeta": ruta_sobirana_proveidor,
        }


@router.post("/albarans/desar-pendent", status_code=status.HTTP_201_CREATED)
async def desar_albara_pendent_auditoria(
    request: Request,
    payload: ConfirmarDocumentRequest,
    db: AsyncSession = Depends(get_db_with_tenant_context),
):
    """Desa un albarà OCR en estat PENDENT_AUDITORIA sense incrementar l'estoc fins consolidació humana (FR-009 / T023)."""
    raw_emp = getattr(request.state, "empresa_id", None)
    if not raw_emp or raw_emp in ("undefined", "null", "None"):
        raise HTTPException(status_code=401, detail="No identificat")
    empresa_id = valida_uuid(str(raw_emp))

    prov = await _resoldre_o_crear_proveidor_albara(db, empresa_id, payload.proveidor)

    dup = (
        await db.execute(
            select(AlbaraProveidor).where(
                AlbaraProveidor.empresa_id == empresa_id,
                AlbaraProveidor.proveidor_id == prov.id,
                AlbaraProveidor.numero_albara == payload.numero_document,
            )
        )
    ).scalars().first()
    if dup:
        raise HTTPException(
            status_code=400,
            detail="Albarà ja pujat. Aquest document ja consta al sistema per aquest proveïdor.",
        )

    nou_albara = AlbaraProveidor(
        empresa_id=empresa_id,
        proveidor_id=prov.id,
        numero_albara=payload.numero_document,
        data_albara=payload.data_document,
        estat="PENDENT_AUDITORIA",
    )
    db.add(nou_albara)
    await db.flush()

    ruta_alb = ""
    try:
        ruta_alb = await SovereignStorageGateway.desar_entitat_json(
            db=db,
            empresa_id=empresa_id,
            categoria="albarans",
            item_id=str(nou_albara.id),
            dades={
                "id": str(nou_albara.id),
                "proveidor_id": str(prov.id),
                "proveidor": payload.proveidor.model_dump(),
                "numero_albara": nou_albara.numero_albara,
                "data_albara": nou_albara.data_albara.isoformat(),
                "estat": "PENDENT_AUDITORIA",
                "linies": [lin.model_dump() for lin in payload.linies],
            },
        )
        nou_albara.fitxer_path = ruta_alb
    except Exception as exc:
        logger.warning("No s'ha pogut desar esborrany JSON albarà pendent %s: %s", nou_albara.id, exc)

    await db.commit()
    return {
        "id": str(nou_albara.id),
        "estat": nou_albara.estat,
        "numero_albara": nou_albara.numero_albara,
        "proveidor_id": str(prov.id),
        "proveidor_nom": prov.rao_social,
        "linies": [lin.model_dump() for lin in payload.linies],
        "fitxer_path": ruta_alb,
    }


@router.get("/albarans")
async def llistar_albarans_proveidor(
    request: Request,
    estat: Optional[str] = None,
    claims: dict = Depends(get_current_user_claims),
    db: AsyncSession = Depends(get_db_with_tenant_context),
):
    """Llista albarans de proveïdors (inclosos els PENDENT_AUDITORIA per revisió humana T023/T024)."""
    raw_emp = getattr(request.state, "empresa_id", None) or claims.get("empresa_id")
    if not raw_emp or str(raw_emp) in ("undefined", "null", "None"):
        raise HTTPException(status_code=401, detail="No identificat")
    emp_uuid = valida_uuid(str(raw_emp))
    rol = str(claims.get("rol", "")).upper()
    is_enginyer = rol == "ENGINYER"

    stmt = (
        select(AlbaraProveidor, Proveidor.rao_social, Proveidor.nif, Proveidor.email)
        .outerjoin(Proveidor, AlbaraProveidor.proveidor_id == Proveidor.id)
        .where(AlbaraProveidor.empresa_id == emp_uuid)
        .order_by(AlbaraProveidor.created_at.desc())
    )
    if estat and estat.upper() != "TOTS":
        stmt = stmt.where(AlbaraProveidor.estat == estat.upper())

    rows = (await db.execute(stmt)).all()
    json_albarans = await SovereignStorageGateway.llegir_entitats_json(db, emp_uuid, "albarans")
    drafts_map: Dict[str, Dict[str, Any]] = {}
    for item in json_albarans:
        if not isinstance(item, dict):
            continue
        alb_key = str(item.get("id") or "")
        if alb_key:
            drafts_map[alb_key] = item

    resultat: List[Dict[str, Any]] = []
    for alb, prov_nom, prov_nif, prov_email in rows:
        esborrany = drafts_map.get(str(alb.id), {})
        linies_raw = esborrany.get("linies") or []
        linies_out = []
        for lin in linies_raw:
            if not isinstance(lin, dict):
                continue
            linies_out.append(
                {
                    **lin,
                    "preu": None if is_enginyer else lin.get("preu", 0.0),
                }
            )
        resultat.append(
            {
                "id": str(alb.id),
                "proveidor_id": str(alb.proveidor_id),
                "proveidor_nom": prov_nom or (esborrany.get("proveidor") or {}).get("nom"),
                "proveidor_nif": prov_nif or (esborrany.get("proveidor") or {}).get("nif"),
                "proveidor_email": prov_email,
                "numero_albara": alb.numero_albara,
                "data_albara": alb.data_albara.isoformat() if alb.data_albara else None,
                "estat": alb.estat,
                "linies": linies_out,
                "created_at": alb.created_at.isoformat() if alb.created_at else None,
            }
        )
    return resultat


@router.post("/albarans/{albara_id}/consolidar")
async def consolidar_albara_pendent(
    request: Request,
    albara_id: uuid.UUID,
    payload: Optional[ConfirmarDocumentRequest] = None,
    db: AsyncSession = Depends(get_db_with_tenant_context),
):
    """Consolida manualment un albarà PENDENT_AUDITORIA i aplica l'increment físic d'estoc (T024)."""
    raw_emp = getattr(request.state, "empresa_id", None)
    if not raw_emp or raw_emp in ("undefined", "null", "None"):
        raise HTTPException(status_code=401, detail="No identificat")
    emp_uuid = valida_uuid(str(raw_emp))

    albara = (
        await db.execute(
            select(AlbaraProveidor).where(
                AlbaraProveidor.id == albara_id,
                AlbaraProveidor.empresa_id == emp_uuid,
            )
        )
    ).scalars().first()
    if not albara:
        raise HTTPException(status_code=404, detail="Albarà no trobat")
    if albara.estat == "CONSOLIDAT":
        raise HTTPException(status_code=400, detail="Aquest albarà ja es troba consolidat.")

    linies_aplicar: List[LiniaOcr] = []
    if payload and payload.linies:
        prov = await _resoldre_o_crear_proveidor_albara(db, emp_uuid, payload.proveidor)
        albara.proveidor_id = prov.id
        albara.numero_albara = payload.numero_document
        albara.data_albara = payload.data_document
        linies_aplicar = payload.linies
    else:
        prov_trobat = (
            await db.execute(
                select(Proveidor).where(
                    Proveidor.id == albara.proveidor_id,
                    Proveidor.empresa_id == emp_uuid,
                )
            )
        ).scalars().first()
        if not prov_trobat:
            raise HTTPException(status_code=404, detail="Proveïdor de l'albarà no trobat")
        prov = prov_trobat
        json_albarans = await SovereignStorageGateway.llegir_entitats_json(db, emp_uuid, "albarans")
        esborrany = next(
            (x for x in json_albarans if isinstance(x, dict) and str(x.get("id") or "") == str(albara.id)),
            None,
        )
        if esborrany and isinstance(esborrany.get("linies"), list):
            linies_aplicar = [LiniaOcr(**lin) for lin in esborrany["linies"]]

    if not linies_aplicar:
        raise HTTPException(
            status_code=422,
            detail="L'albarà pendent no conté cap línia d'article per consolidar.",
        )

    magatzem = await _obtenir_nau_central(db, emp_uuid)
    articles_creats, moviments_creats, articles_afectats = await _aplicar_linies_albara_a_estoc(
        db=db,
        empresa_id=emp_uuid,
        prov=prov,
        magatzem=magatzem,
        numero_document=albara.numero_albara,
        linies=linies_aplicar,
    )
    albara.estat = "CONSOLIDAT"
    await db.commit()

    try:
        from app.core.db import set_tenant_context

        await set_tenant_context(db, str(emp_uuid))
        await SovereignStorageGateway.desar_entitat_json(
            db=db,
            empresa_id=emp_uuid,
            categoria="albarans",
            item_id=str(albara.id),
            dades={
                "id": str(albara.id),
                "proveidor_id": str(prov.id),
                "numero_albara": albara.numero_albara,
                "data_albara": albara.data_albara.isoformat(),
                "estat": "CONSOLIDAT",
                "linies": [lin.model_dump() for lin in linies_aplicar],
            },
        )
        for art_afectat in articles_afectats:
            await _sync_article_disc(db, emp_uuid, art_afectat)
    except Exception as exc:
        logger.warning("No s'ha pogut sincronitzar consolidació d'albarà %s: %s", albara.id, exc)

    return {
        "estat": "CONSOLIDAT",
        "missatge": "Albarà consolidat manualment i estoc incrementat.",
        "albara_id": str(albara.id),
        "articles_creats": articles_creats,
        "moviments_realitzats": moviments_creats,
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

    await avaluar_i_sincronitzar_alertes_recompra(db, emp_uuid, [art_db.id])
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


@router.get("/articles/{article_id}/suggeriment-merma")
async def suggeriment_merma_article(
    request: Request,
    article_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_with_tenant_context),
):
    """Calcula el % històric de merma recomanat per a materials continus (FR-008)."""
    raw_emp = getattr(request.state, "empresa_id", None) or request.headers.get("X-Empresa-ID")
    if not raw_emp or raw_emp in ("undefined", "null", "None"):
        raise HTTPException(status_code=401, detail="No identificat")
    emp_uuid = valida_uuid(str(raw_emp))

    art = (
        await db.execute(
            select(Article).where(Article.id == article_id, Article.empresa_id == emp_uuid)
        )
    ).scalars().first()
    if not art:
        raise HTTPException(status_code=404, detail="Article no trobat")

    merma_stats = (
        await db.execute(
            select(
                func.count(MermaInventari.id),
                func.coalesce(func.sum(MermaInventari.quantitat), 0.0),
            ).where(
                MermaInventari.empresa_id == emp_uuid,
                MermaInventari.article_id == article_id,
            )
        )
    ).one()
    total_registres = int(merma_stats[0] or 0)
    total_mermat = float(merma_stats[1] or 0.0)

    total_sortides = float(
        (
            await db.execute(
                select(func.coalesce(func.sum(MovimentEstoc.quantitat), 0.0)).where(
                    MovimentEstoc.empresa_id == emp_uuid,
                    MovimentEstoc.article_id == article_id,
                    MovimentEstoc.tipus_moviment.in_(["SORTIDA", "MERMA"]),
                )
            )
        ).scalar()
        or 0.0
    )

    pct_suggerit = 0.0
    if total_sortides > 0 and total_mermat > 0:
        pct_suggerit = round(min(25.0, (total_mermat / total_sortides) * 100.0), 2)
    elif bool(getattr(art, "es_material_continu", False)):
        pct_suggerit = 5.0 if total_registres == 0 else 0.0

    return {
        "article_id": str(art.id),
        "es_material_continu": bool(getattr(art, "es_material_continu", False)),
        "merma_suggerida_pct": pct_suggerit,
        "total_mermes_registrades": total_registres,
        "quantitat_total_mermada": total_mermat,
        "recomanacio": (
            f"Basat en {total_registres} registres històrics de merma: tolerància recomanada del {pct_suggerit}%."
            if total_registres > 0
            else (
                "Material continu sense històric previ: s'aplica tolerància estàndard de tall del 5%."
                if getattr(art, "es_material_continu", False)
                else "Sense històric de mermes previ per a aquest article."
            )
        ),
    }


# ---------------------------------------------------------------------------
# Safata HITL de Recompra d'Estoc Mínim (Spec 01-backoffice FR-010)
# ---------------------------------------------------------------------------


class RecompraAccioRequest(BaseModel):
    accio: str = Field(..., pattern="^(APROVAR|DESCARTAR)$")
    quantitat_aprovada: Optional[float] = Field(default=None, gt=0)
    notes: Optional[str] = Field(default=None, max_length=500)
    proveidor_id: Optional[uuid.UUID] = None
    proveidor_email: Optional[str] = Field(default=None, max_length=200)
    assumpte: Optional[str] = Field(default=None, max_length=250)
    cos_email: Optional[str] = Field(default=None, max_length=5000)
    enviar_email: bool = False


class RecompraEnviarEmailRequest(BaseModel):
    alerta_ids: List[uuid.UUID] = Field(..., min_length=1)
    proveidor_id: Optional[uuid.UUID] = None
    destinatari_email: str = Field(..., min_length=5, max_length=200)
    assumpte: str = Field(..., min_length=3, max_length=250)
    cos_missatge: str = Field(..., min_length=5, max_length=8000)
    quantitats: Optional[Dict[str, float]] = None
    canal: str = Field("SMTP", pattern="^(SMTP|MAILTO)$")


def _serialitzar_alerta_recompra(
    alerta: AlertaGarantiaRecompra,
    art_nom: Optional[str],
    art_ref: Optional[str],
    art_cb: Optional[str],
    prov_nom: Optional[str],
    rol: str,
    prov_email: Optional[str] = None,
) -> Dict[str, Any]:
    proposta = dict(alerta.dades_comanda_proposta or {})
    if rol.upper() == "ENGINYER":
        proposta["preu_unitari_estimat"] = None
        proposta["import_estimat"] = None

    email_eff = prov_email or proposta.get("proveidor_email")
    assumpte = proposta.get("esborrany_email_assumpte")
    cos = proposta.get("esborrany_email_cos")
    if not assumpte or not cos:
        assumpte, cos = construir_text_esborrany_email_recompra(
            empresa_nom="la nostra empresa",
            proveidor_nom=prov_nom or proposta.get("proveidor_nom"),
            items=[
                {
                    "referencia": art_ref or proposta.get("referencia"),
                    "codi_barres": art_cb or proposta.get("codi_barres"),
                    "nom": art_nom or proposta.get("nom"),
                    "unitat_mesura": proposta.get("unitat_mesura") or "UNITAT",
                    "quantitat_proposada": proposta.get("quantitat_proposada") or 1,
                    "quantitat_aprovada": proposta.get("quantitat_aprovada"),
                }
            ],
        )
    mailto_eff = proposta.get("mailto_url")
    if not mailto_eff and email_eff and "@" in str(email_eff):
        try:
            mailto_eff = construir_mailto_url(str(email_eff), str(assumpte), str(cos))
        except Exception:
            mailto_eff = None

    return {
        "id": str(alerta.id),
        "tipus_alerta": alerta.tipus_alerta,
        "article_id": str(alerta.article_id) if alerta.article_id else None,
        "article_nom": art_nom or proposta.get("nom"),
        "article_ref": art_ref or proposta.get("referencia"),
        "article_codi_barres": art_cb or proposta.get("codi_barres"),
        "proveidor_id": str(alerta.proveidor_id) if alerta.proveidor_id else None,
        "proveidor_nom": prov_nom or proposta.get("proveidor_nom"),
        "proveidor_email": email_eff,
        "esborrany_email_assumpte": assumpte,
        "esborrany_email_cos": cos,
        "mailto_url": mailto_eff,
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
    """Llista la safata HITL de propostes de recompra sincronitzant automàticament trencaments d'estoc (FR-010)."""
    empresa_raw = getattr(request.state, "empresa_id", None) or claims.get("empresa_id")
    if not empresa_raw or str(empresa_raw) == "undefined":
        raise HTTPException(status_code=401, detail="No identificat")
    emp_uuid = valida_uuid(str(empresa_raw))
    rol = str(claims.get("rol", "")).upper()

    await avaluar_i_sincronitzar_alertes_recompra(db, emp_uuid)

    stmt = (
        select(
            AlertaGarantiaRecompra,
            Article.nom,
            Article.referencia_inventari,
            Article.codi_barres,
            Proveidor.rao_social,
            Proveidor.email,
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
    resultat = [
        _serialitzar_alerta_recompra(alerta, art_nom, art_ref, art_cb, prov_nom, rol, prov_email)
        for alerta, art_nom, art_ref, art_cb, prov_nom, prov_email in rows
    ]
    await db.commit()
    return resultat


@router.get("/recompra/agrupades-proveidor")
async def llistar_esborranys_recompra_agrupats(
    request: Request,
    claims: dict = Depends(get_current_user_claims),
    db: AsyncSession = Depends(get_db_with_tenant_context),
):
    """Agrupa les alertes ACTIVA per proveïdor i genera esborranys d'email conjunts HITL (FR-010)."""
    empresa_raw = getattr(request.state, "empresa_id", None) or claims.get("empresa_id")
    if not empresa_raw or str(empresa_raw) == "undefined":
        raise HTTPException(status_code=401, detail="No identificat")
    emp_uuid = valida_uuid(str(empresa_raw))
    rol = str(claims.get("rol", "")).upper()

    await avaluar_i_sincronitzar_alertes_recompra(db, emp_uuid)

    empresa_nom = (
        await db.execute(select(Empresa.nom).where(Empresa.id == emp_uuid))
    ).scalar() or "Sevalor"

    stmt = (
        select(
            AlertaGarantiaRecompra,
            Article.nom,
            Article.referencia_inventari,
            Article.codi_barres,
            Proveidor.rao_social,
            Proveidor.email,
        )
        .outerjoin(Article, AlertaGarantiaRecompra.article_id == Article.id)
        .outerjoin(Proveidor, AlertaGarantiaRecompra.proveidor_id == Proveidor.id)
        .where(
            AlertaGarantiaRecompra.empresa_id == emp_uuid,
            AlertaGarantiaRecompra.tipus_alerta == "RECOMPRA_STOCK",
            AlertaGarantiaRecompra.estat == "ACTIVA",
        )
        .order_by(AlertaGarantiaRecompra.created_at.desc())
    )
    rows = (await db.execute(stmt)).all()
    rows_tuples = [(r[0], r[1], r[2], r[3], r[4], r[5]) for r in rows]
    grups = agrupar_alertes_recompra_per_proveidor(rows_tuples, empresa_nom=empresa_nom, rol=rol)
    await db.commit()
    return grups


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

    noves = await avaluar_i_sincronitzar_alertes_recompra(db, emp_uuid)
    noves_ids = [a.id for a in noves]
    alertes_out: List[Dict[str, Any]] = []
    if noves_ids:
        rows = (
            await db.execute(
                select(
                    AlertaGarantiaRecompra,
                    Article.nom,
                    Article.referencia_inventari,
                    Article.codi_barres,
                    Proveidor.rao_social,
                    Proveidor.email,
                )
                .outerjoin(Article, AlertaGarantiaRecompra.article_id == Article.id)
                .outerjoin(Proveidor, AlertaGarantiaRecompra.proveidor_id == Proveidor.id)
                .where(AlertaGarantiaRecompra.id.in_(noves_ids))
            )
        ).all()
        alertes_out = [
            _serialitzar_alerta_recompra(alerta, art_nom, art_ref, art_cb, prov_nom, rol, prov_email)
            for alerta, art_nom, art_ref, art_cb, prov_nom, prov_email in rows
        ]

    await db.commit()
    return {
        "esborranys_generats": len(alertes_out),
        "alertes": alertes_out,
    }


@router.post("/recompra/enviar-email")
async def enviar_email_recompra_proveidor(
    request: Request,
    payload: RecompraEnviarEmailRequest,
    claims: dict = Depends(get_current_user_claims),
    db: AsyncSession = Depends(get_db_with_tenant_context),
):
    """Envia (només sota confirmació humana BOSS/SECRETARIA) l'esborrany d'email de reposició al proveïdor."""
    empresa_raw = getattr(request.state, "empresa_id", None) or claims.get("empresa_id")
    if not empresa_raw or str(empresa_raw) in ("undefined", "null", "None"):
        raise HTTPException(status_code=401, detail="No identificat")
    emp_uuid = valida_uuid(str(empresa_raw))
    rol = str(claims.get("rol", "")).upper()

    if rol not in ("BOSS", "SECRETARIA"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Només direcció o administració (BOSS/SECRETARIA) poden aprovar i enviar comandes a proveïdors.",
        )

    try:
        dest_email = validar_email_destinatari(payload.destinatari_email)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    empresa_nom = (
        await db.execute(select(Empresa.nom).where(Empresa.id == emp_uuid))
    ).scalar() or "Sevalor"

    if payload.proveidor_id is not None:
        prov_check = (
            await db.execute(
                select(Proveidor.id).where(
                    Proveidor.id == payload.proveidor_id,
                    Proveidor.empresa_id == emp_uuid,
                )
            )
        ).scalars().first()
        if not prov_check:
            raise HTTPException(status_code=404, detail="Proveïdor no trobat")

    alertes_db = (
        await db.execute(
            select(AlertaGarantiaRecompra).where(
                AlertaGarantiaRecompra.id.in_(payload.alerta_ids),
                AlertaGarantiaRecompra.empresa_id == emp_uuid,
                AlertaGarantiaRecompra.tipus_alerta == "RECOMPRA_STOCK",
            )
        )
    ).scalars().all()
    if not alertes_db:
        raise HTTPException(status_code=404, detail="No s'han trobat alertes de recompra vàlides")

    ara = datetime.now(timezone.utc)
    mailto_url = construir_mailto_url(dest_email, payload.assumpte, payload.cos_missatge)
    email_enviat = False
    email_error: Optional[str] = None

    if payload.canal.upper() == "SMTP":
        email_enviat, email_error = enviar_email_recompra_smtp(
            empresa_nom=empresa_nom,
            destinatari_email=dest_email,
            assumpte=payload.assumpte,
            cos_missatge=payload.cos_missatge,
        )

    qty_overrides = payload.quantitats or {}
    for al in alertes_db:
        prop = dict(al.dades_comanda_proposta or {})
        override_val = qty_overrides.get(str(al.id))
        if override_val is not None and float(override_val) > 0:
            prop["quantitat_aprovada"] = float(override_val)
            preu_u = float(prop.get("preu_unitari_estimat") or 0.0)
            prop["import_estimat"] = round(float(override_val) * preu_u, 2)
        else:
            prop["quantitat_aprovada"] = float(prop.get("quantitat_aprovada") or prop.get("quantitat_proposada") or 0.0)

        if payload.proveidor_id is not None:
            al.proveidor_id = payload.proveidor_id
            prop["proveidor_id"] = str(payload.proveidor_id)

        prop["proveidor_email"] = dest_email
        prop["esborrany_email_assumpte"] = payload.assumpte
        prop["esborrany_email_cos"] = payload.cos_missatge
        prop["mailto_url"] = mailto_url
        prop["estat_hitl"] = "ENVIADA_SMTP_HITL" if email_enviat else "APROVADA_PER_EMISSIO_MANUAL"
        prop["enviat_automaticament"] = False
        prop["confirmacio_humana"] = True
        prop["canal_enviament"] = "SMTP" if email_enviat else "MAILTO"
        prop["resolt_per_usuari_id"] = str(claims.get("sub")) if claims.get("sub") else None
        prop["resolt_en"] = ara.isoformat()

        al.estat = "APROVADA"
        al.dades_comanda_proposta = prop
        al.updated_at = ara

    await db.commit()

    try:
        from app.core.db import set_tenant_context

        await set_tenant_context(db, str(emp_uuid), role=rol)
        await SovereignStorageGateway.desar_entitat_json(
            db=db,
            empresa_id=emp_uuid,
            categoria="albarans",
            item_id=f"recompra_email_{alertes_db[0].id}",
            dades={
                "alerta_ids": [str(a.id) for a in alertes_db],
                "destinatari_email": dest_email,
                "assumpte": payload.assumpte,
                "cos_missatge": payload.cos_missatge,
                "email_enviat_smtp": email_enviat,
                "canal": "SMTP" if email_enviat else "MAILTO",
                "resolt_en": ara.isoformat(),
            },
        )
    except Exception as exc:
        logger.warning("No s'ha pogut desar traça d'email de recompra al disc sobirà: %s", exc)

    return {
        "estat": "OK",
        "alertes_aprovades": [str(a.id) for a in alertes_db],
        "destinatari_email": dest_email,
        "email_enviat": email_enviat,
        "email_error": email_error,
        "mailto_url": mailto_url,
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
            Proveidor.email,
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

    alerta, art_nom, art_ref, art_cb, prov_nom, prov_email = row
    proposta = dict(alerta.dades_comanda_proposta or {})
    ara = datetime.now(timezone.utc)
    email_enviat = False
    email_error: Optional[str] = None

    if payload.proveidor_id is not None:
        prov_row = (
            await db.execute(
                select(Proveidor).where(
                    Proveidor.id == payload.proveidor_id,
                    Proveidor.empresa_id == emp_uuid,
                )
            )
        ).scalars().first()
        if not prov_row:
            raise HTTPException(status_code=404, detail="Proveïdor no trobat")
        alerta.proveidor_id = prov_row.id
        prov_nom = prov_row.rao_social
        prov_email = prov_row.email
        proposta["proveidor_id"] = str(prov_row.id)
        proposta["proveidor_nom"] = prov_row.rao_social

    email_dest = (payload.proveidor_email or prov_email or proposta.get("proveidor_email") or "").strip() or None
    if email_dest:
        proposta["proveidor_email"] = email_dest

    if payload.accio == "APROVAR":
        alerta.estat = "APROVADA"
        if payload.quantitat_aprovada is not None:
            proposta["quantitat_aprovada"] = float(payload.quantitat_aprovada)
            preu_u = float(proposta.get("preu_unitari_estimat") or 0.0)
            proposta["import_estimat"] = round(float(payload.quantitat_aprovada) * preu_u, 2)
        else:
            proposta["quantitat_aprovada"] = float(proposta.get("quantitat_proposada") or 0.0)

        empresa_nom = (
            await db.execute(select(Empresa.nom).where(Empresa.id == emp_uuid))
        ).scalar() or "Sevalor"
        assumpte_def, cos_def = construir_text_esborrany_email_recompra(
            empresa_nom=empresa_nom,
            proveidor_nom=prov_nom,
            items=[
                {
                    "referencia": art_ref or proposta.get("referencia"),
                    "codi_barres": art_cb or proposta.get("codi_barres"),
                    "nom": art_nom or proposta.get("nom"),
                    "unitat_mesura": proposta.get("unitat_mesura") or "UNITAT",
                    "quantitat_proposada": proposta.get("quantitat_proposada"),
                    "quantitat_aprovada": proposta.get("quantitat_aprovada"),
                }
            ],
            notes_extra=payload.notes,
        )
        assumpte_final = (payload.assumpte or proposta.get("esborrany_email_assumpte") or assumpte_def).strip()
        cos_final = (payload.cos_email or proposta.get("esborrany_email_cos") or cos_def).strip()
        proposta["esborrany_email_assumpte"] = assumpte_final
        proposta["esborrany_email_cos"] = cos_final
        if email_dest:
            try:
                proposta["mailto_url"] = construir_mailto_url(email_dest, assumpte_final, cos_final)
            except Exception:
                pass

        if payload.enviar_email:
            if not email_dest:
                raise HTTPException(
                    status_code=422,
                    detail="Cal indicar l'adreça de correu del proveïdor per enviar la comanda.",
                )
            try:
                validar_email_destinatari(email_dest)
            except ValueError as exc:
                raise HTTPException(status_code=422, detail=str(exc)) from exc

            email_enviat, email_error = enviar_email_recompra_smtp(
                empresa_nom=empresa_nom,
                destinatari_email=email_dest,
                assumpte=assumpte_final,
                cos_missatge=cos_final,
            )
            proposta["estat_hitl"] = "ENVIADA_SMTP_HITL" if email_enviat else "APROVADA_PER_EMISSIO_MANUAL"
        else:
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
            from app.core.db import set_tenant_context

            await set_tenant_context(db, str(emp_uuid), role=rol)
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

    res_serialitzat = _serialitzar_alerta_recompra(
        alerta, art_nom, art_ref, art_cb, prov_nom, rol, email_dest
    )
    res_serialitzat["email_enviat"] = email_enviat
    res_serialitzat["email_error"] = email_error
    return res_serialitzat
