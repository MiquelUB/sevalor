import uuid
from datetime import datetime, timezone
from typing import List, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db_with_tenant_context
from app.core.security import get_current_user_claims, require_roles
from app.models.models import (
    Article,
    EinaCustodia,
    FullaPicking,
    Incidencia,
    LiniaPicking,
    Magatzem,
    OrdreTreball,
    OrdreTreballOperari,
)
from app.services.picking_stock_service import (
    actualitzar_linia_picking_amb_estoc,
    obtenir_estoc_furgoneta_operari,
    registrar_consum_material_furgoneta,
    resoldre_magatzem_furgoneta,
)
from app.services.sovereign_storage import SovereignStorageGateway

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


class EinaPickingItemResponse(BaseModel):
    id: uuid.UUID
    nom: str
    model: Optional[str] = None
    numero_serie: str
    referencia_fabricant: Optional[str] = None
    estat: str
    ordre_treball_id: Optional[uuid.UUID] = None
    ordre_codi: Optional[str] = None
    custodiat_per_operari_id: Optional[uuid.UUID] = None
    magatzem_id: Optional[uuid.UUID] = None
    magatzem_nom: Optional[str] = None
    observacions: Optional[str] = None
    incidencies: Optional[str] = None


class EinesPickingLlistaResponse(BaseModel):
    eines_assignades: List[EinaPickingItemResponse] = []
    eines_disponibles: List[EinaPickingItemResponse] = []


class EinaPickInRequest(BaseModel):
    ordre_treball_id: Optional[uuid.UUID] = None
    desti: Literal["CUSTODIADA", "EN_VEHICLE"] = "CUSTODIADA"
    observacions: Optional[str] = Field(default=None, max_length=500)


class EinaPickOutRequest(BaseModel):
    ordre_treball_id: Optional[uuid.UUID] = None
    estat_retorn: Literal["DISPONIBLE", "AVARIADA"] = "DISPONIBLE"
    incidencia: Optional[str] = Field(default=None, max_length=500)


def _extract_usuari_uuid(request: Request, claims: dict) -> Optional[uuid.UUID]:
    raw = getattr(request.state, "user_id", None) or (claims.get("sub") if claims else None)
    if not raw:
        return None
    try:
        return uuid.UUID(str(raw))
    except (ValueError, TypeError):
        return None


def _build_eina_picking_item(
    eina: EinaCustodia,
    ordre_codi: Optional[str] = None,
    magatzem_nom: Optional[str] = None,
) -> EinaPickingItemResponse:
    return EinaPickingItemResponse(
        id=eina.id,
        nom=eina.nom,
        model=eina.model,
        numero_serie=eina.numero_serie,
        referencia_fabricant=eina.referencia_fabricant,
        estat=eina.estat,
        ordre_treball_id=eina.ordre_treball_id,
        ordre_codi=ordre_codi,
        custodiat_per_operari_id=eina.custodiat_per_operari_id,
        magatzem_id=eina.magatzem_id,
        magatzem_nom=magatzem_nom,
        observacions=eina.observacions,
        incidencies=eina.incidencies,
    )


@router.get("/eines", response_model=EinesPickingLlistaResponse)
async def llistar_eines_picking_operari(
    request: Request,
    ordre_treball_id: Optional[uuid.UUID] = None,
    incloure_disponibles: bool = True,
    db: AsyncSession = Depends(get_db_with_tenant_context),
    claims: dict = Depends(get_current_user_claims),
):
    """Llista les eines vinculades a l'OT / operari per Pick-In i Pick-Out, i les disponibles a nau."""
    empresa_id = request.state.empresa_id
    if not empresa_id or empresa_id == "undefined":
        raise HTTPException(status_code=401, detail="Context d'empresa no trobat")
    emp_uuid = uuid.UUID(str(empresa_id))
    user_uuid = _extract_usuari_uuid(request, claims)

    conds = []
    if ordre_treball_id is not None:
        conds.append(EinaCustodia.ordre_treball_id == ordre_treball_id)
    if user_uuid is not None:
        if ordre_treball_id is not None:
            conds.append(
                and_(
                    EinaCustodia.custodiat_per_operari_id == user_uuid,
                    EinaCustodia.ordre_treball_id.is_(None),
                )
            )
        else:
            conds.append(EinaCustodia.custodiat_per_operari_id == user_uuid)

    stmt_assig = (
        select(EinaCustodia, OrdreTreball.codi, Magatzem.nom)
        .outerjoin(OrdreTreball, EinaCustodia.ordre_treball_id == OrdreTreball.id)
        .outerjoin(Magatzem, EinaCustodia.magatzem_id == Magatzem.id)
        .where(EinaCustodia.empresa_id == emp_uuid)
    )
    if conds:
        stmt_assig = stmt_assig.where(or_(*conds))
    else:
        stmt_assig = stmt_assig.where(EinaCustodia.estat.in_(["CUSTODIADA", "EN_VEHICLE"]))
    stmt_assig = stmt_assig.order_by(EinaCustodia.nom.asc())

    rows_assig = (await db.execute(stmt_assig)).all()
    assigned_ids = {e.id for e, _ot_codi, _mag_nom in rows_assig}
    eines_assignades = [
        _build_eina_picking_item(e, ordre_codi=ot_codi, magatzem_nom=mag_nom)
        for e, ot_codi, mag_nom in rows_assig
    ]

    eines_disponibles: List[EinaPickingItemResponse] = []
    if incloure_disponibles:
        stmt_disp = (
            select(EinaCustodia, Magatzem.nom)
            .outerjoin(Magatzem, EinaCustodia.magatzem_id == Magatzem.id)
            .where(
                EinaCustodia.empresa_id == emp_uuid,
                EinaCustodia.estat == "DISPONIBLE",
            )
            .order_by(EinaCustodia.nom.asc())
        )
        rows_disp = (await db.execute(stmt_disp)).all()
        for e, mag_nom in rows_disp:
            if e.id not in assigned_ids:
                eines_disponibles.append(_build_eina_picking_item(e, magatzem_nom=mag_nom))

    return EinesPickingLlistaResponse(
        eines_assignades=eines_assignades,
        eines_disponibles=eines_disponibles,
    )


@router.post("/eines/{eina_id}/pick-in", response_model=EinaPickingItemResponse)
async def pick_in_eina_operari(
    eina_id: uuid.UUID,
    payload: EinaPickInRequest,
    request: Request,
    db: AsyncSession = Depends(get_db_with_tenant_context),
    claims: dict = Depends(get_current_user_claims),
):
    """Confirma el Pick-In (càrrega / custòdia) d'una eina per a l'operari i/o furgoneta vinculada a l'OT."""
    empresa_id = request.state.empresa_id
    if not empresa_id or empresa_id == "undefined":
        raise HTTPException(status_code=401, detail="Context d'empresa no trobat")
    emp_uuid = uuid.UUID(str(empresa_id))
    user_uuid = _extract_usuari_uuid(request, claims)

    eina = (
        await db.execute(
            select(EinaCustodia).where(
                EinaCustodia.id == eina_id,
                EinaCustodia.empresa_id == emp_uuid,
            )
        )
    ).scalars().first()
    if not eina:
        raise HTTPException(status_code=404, detail="Eina no trobada")

    if eina.estat in ("AVARIADA", "BAIXA"):
        raise HTTPException(
            status_code=400,
            detail=f"L'eina no està operativa (estat actual: {eina.estat}).",
        )

    # Validar que no la tingui custodiada un altre operari en una altra OT diferent
    if (
        eina.estat in ("CUSTODIADA", "EN_VEHICLE")
        and eina.ordre_treball_id is not None
        and payload.ordre_treball_id is not None
        and eina.ordre_treball_id != payload.ordre_treball_id
    ):
        raise HTTPException(
            status_code=409,
            detail="Aquesta eina ja està assignada a una altra ordre de treball activa.",
        )

    ordre_codi: Optional[str] = None
    target_ot_id = payload.ordre_treball_id or eina.ordre_treball_id
    if target_ot_id is not None:
        ot = (
            await db.execute(
                select(OrdreTreball).where(
                    OrdreTreball.id == target_ot_id,
                    OrdreTreball.empresa_id == emp_uuid,
                )
            )
        ).scalars().first()
        if not ot:
            raise HTTPException(status_code=404, detail="Ordre de treball no trobada")
        ordre_codi = ot.codi
        eina.ordre_treball_id = ot.id

    magatzem_nom: Optional[str] = None
    if payload.desti == "EN_VEHICLE":
        mag, _veh = await resoldre_magatzem_furgoneta(
            db,
            emp_uuid,
            ordre_treball_id=target_ot_id,
            usuari_id=user_uuid,
        )
        eina.magatzem_id = mag.id if mag else None
        magatzem_nom = mag.nom if mag else None
    else:
        eina.magatzem_id = None

    eina.estat = payload.desti
    if user_uuid is not None:
        eina.custodiat_per_operari_id = user_uuid
    if payload.observacions and payload.observacions.strip():
        stamp = datetime.now(timezone.utc).strftime("%d/%m %H:%M")
        nota = f"[Pick-In {stamp}] {payload.observacions.strip()}"
        eina.observacions = f"{eina.observacions}\n{nota}".strip() if eina.observacions else nota

    resp_item = _build_eina_picking_item(eina, ordre_codi=ordre_codi, magatzem_nom=magatzem_nom)
    await db.commit()

    await SovereignStorageGateway.desar_entitat_json(
        db=db,
        empresa_id=emp_uuid,
        categoria="magatzem_eines",
        item_id=str(resp_item.id),
        dades={
            "id": str(resp_item.id),
            "nom": resp_item.nom,
            "model": resp_item.model,
            "numero_serie": resp_item.numero_serie,
            "estat": resp_item.estat,
            "ordre_treball_id": str(resp_item.ordre_treball_id) if resp_item.ordre_treball_id else None,
            "custodiat_per_operari_id": (
                str(resp_item.custodiat_per_operari_id) if resp_item.custodiat_per_operari_id else None
            ),
            "magatzem_id": str(resp_item.magatzem_id) if resp_item.magatzem_id else None,
            "observacions": resp_item.observacions,
            "incidencies": resp_item.incidencies,
        },
    )

    return resp_item


@router.post("/eines/{eina_id}/pick-out", response_model=EinaPickingItemResponse)
async def pick_out_eina_operari(
    eina_id: uuid.UUID,
    payload: EinaPickOutRequest,
    request: Request,
    db: AsyncSession = Depends(get_db_with_tenant_context),
    claims: dict = Depends(get_current_user_claims),
):
    """Executa el Pick-Out (retorn a magatzem / nau) d'una eina en custòdia, amb opció d'avaria."""
    empresa_id = request.state.empresa_id
    if not empresa_id or empresa_id == "undefined":
        raise HTTPException(status_code=401, detail="Context d'empresa no trobat")
    emp_uuid = uuid.UUID(str(empresa_id))
    user_uuid = _extract_usuari_uuid(request, claims)

    eina = (
        await db.execute(
            select(EinaCustodia).where(
                EinaCustodia.id == eina_id,
                EinaCustodia.empresa_id == emp_uuid,
            )
        )
    ).scalars().first()
    if not eina:
        raise HTTPException(status_code=404, detail="Eina no trobada")

    if eina.estat not in ("CUSTODIADA", "EN_VEHICLE"):
        raise HTTPException(
            status_code=400,
            detail="L'eina no està en custòdia ni carregada a furgoneta per fer Pick-Out.",
        )

    ot_ref_id = payload.ordre_treball_id or eina.ordre_treball_id
    incidencia_clean = payload.incidencia.strip() if payload.incidencia else None
    eina.estat = payload.estat_retorn
    eina.custodiat_per_operari_id = None
    eina.ordre_treball_id = None
    eina.magatzem_id = None

    if incidencia_clean or payload.estat_retorn == "AVARIADA":
        stamp = datetime.now(timezone.utc).strftime("%d/%m %H:%M")
        detall_inc = incidencia_clean or "Retornada amb avaria o incidència des de camp (Pick-Out)"
        nota_inc = f"[Pick-Out {stamp}] {detall_inc}"
        eina.incidencies = f"{eina.incidencies}\n{nota_inc}".strip() if eina.incidencies else nota_inc

        nova_inc = Incidencia(
            empresa_id=emp_uuid,
            ordre_treball_id=ot_ref_id,
            operari_id=user_uuid,
            ambit="MAGATZEM",
            estat="VERMELL",
            text_observacions=f"Eina {eina.nom} (SN: {eina.numero_serie}): {detall_inc}",
        )
        db.add(nova_inc)

    resp_item = _build_eina_picking_item(eina)
    await db.commit()

    await SovereignStorageGateway.desar_entitat_json(
        db=db,
        empresa_id=emp_uuid,
        categoria="magatzem_eines",
        item_id=str(resp_item.id),
        dades={
            "id": str(resp_item.id),
            "nom": resp_item.nom,
            "model": resp_item.model,
            "numero_serie": resp_item.numero_serie,
            "estat": resp_item.estat,
            "ordre_treball_id": None,
            "custodiat_per_operari_id": None,
            "magatzem_id": None,
            "observacions": resp_item.observacions,
            "incidencies": resp_item.incidencies,
        },
    )

    return resp_item


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

