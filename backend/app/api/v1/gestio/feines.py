import collections
import json
import logging
import uuid
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional

import filetype  # type: ignore[import-untyped]
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import Response
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import delete, func, or_, select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db_with_tenant_context, set_tenant_context
from app.core.security import get_current_user_claims, require_roles
from app.models.models import (
    Article,
    Client,
    EinaCustodia,
    EstocMagatzem,
    Finca,
    FullaPicking,
    LiniaPicking,
    OrdreTreball,
    OrdreTreballOperari,
    OrdreTreballTramTemps,
    PlanolBase,
    TiquetDespesa,
    Usuari,
    Vehicle,
)
from app.services.barema_service import (
    calcular_cost_ma_obra_real,
    obtenir_barema_empresa,
    resoldre_preu_hora_control_panel,
)
from app.services.flota_service import validar_permis_conduir
from app.services.geocoding_service import geocodificar_adreca
from app.services.picking_stock_service import actualitzar_linia_picking_amb_estoc
from app.services.reconciliacio_ot_service import (
    ESTATS_OT_CONCLOSES,
    ReconciliacioOTService,
    calcular_estat_disclaimer_ot,
    desar_signatura_client_ot,
)
from app.services.sovereign_storage import SovereignStorageGateway

logger = logging.getLogger("sevalor.feines")

router = APIRouter(
    prefix="/gestio/feines",
    tags=["Gestió Feines i Mapa"],
    dependencies=[Depends(require_roles(["BOSS", "SECRETARIA", "ENGINYER"]))],
)


class LiniaPickingItem(BaseModel):
    id: Optional[uuid.UUID] = None
    article_id: uuid.UUID
    article_nom: Optional[str] = None
    referencia_inventari: Optional[str] = None
    quantitat_prevista: float = Field(..., gt=0)
    quantitat_carregada_pick_in: float = 0.0
    quantitat_retornada_pick_out: float = 0.0
    quantitat_mermada: float = 0.0
    consum_real: float = 0.0
    origen_estoc: str = "NAU"
    unitat_mesura: Optional[str] = "UNITAT"
    estoc_disponible: Optional[float] = 0.0
    magatzem_id: Optional[uuid.UUID] = None
    model_config = ConfigDict(from_attributes=True)


class EinaItem(BaseModel):
    id: uuid.UUID
    nom: str
    model: Optional[str] = None
    numero_serie: str
    estat: str
    model_config = ConfigDict(from_attributes=True)


class OperariAssignatItem(BaseModel):
    id: uuid.UUID
    nom: str
    cognoms: Optional[str] = None
    rol: Optional[str] = None
    es_cap_de_colla: bool = False
    telefon: Optional[str] = None
    model_config = ConfigDict(from_attributes=True)


class FeinaCreate(BaseModel):
    codi: str = Field(..., max_length=20)
    client_id: uuid.UUID
    versio: int = 1
    finca_id: Optional[uuid.UUID] = None
    planol_id: Optional[uuid.UUID] = None
    titol: str = Field(..., max_length=200)
    adreca: str = Field(..., max_length=255)
    descripcio: Optional[str] = None
    estat: str = Field("PENDENT", max_length=30)
    data_planificacio: date
    hora_inici_prevista: Optional[datetime] = None
    hora_fi_prevista: Optional[datetime] = None
    cap_de_colla_id: Optional[uuid.UUID] = None
    operaris_ids: Optional[List[uuid.UUID]] = None
    vehicle_id: Optional[uuid.UUID] = None
    latitud: Optional[float] = None
    longitud: Optional[float] = None
    eina_ids: Optional[List[uuid.UUID]] = None
    magatzem_id: Optional[uuid.UUID] = None
    linies_picking: Optional[List[LiniaPickingItem]] = None
    model_config = ConfigDict(from_attributes=True)

    @field_validator("adreca")
    @classmethod
    def validar_adreca_no_buida(cls, v: str) -> str:
        v_clean = v.strip()
        if not v_clean:
            raise ValueError("L'adreça de l'obra és obligatòria i no pot estar buida")
        return v_clean


class TramTempsGestioItem(BaseModel):
    id: uuid.UUID
    hora_inici: datetime
    hora_fi: Optional[datetime] = None
    durada_segons: int = 0
    gps_inici_lat: Optional[float] = None
    gps_inici_lng: Optional[float] = None
    gps_fi_lat: Optional[float] = None
    gps_fi_lng: Optional[float] = None
    desviacio_geovalla: bool = False
    justificacio_gps: Optional[str] = None
    model_config = ConfigDict(from_attributes=True)


class FeinaResponse(FeinaCreate):
    id: uuid.UUID
    versio: int = 1
    latitud: Optional[float] = None
    longitud: Optional[float] = None
    client_nom: Optional[str] = None
    cap_de_colla_nom: Optional[str] = None
    planol_titol: Optional[str] = None
    planol_codi: Optional[str] = None
    hora_inici_real: Optional[datetime] = None
    hora_fi_real: Optional[datetime] = None
    hores_previstes: float = 0.0
    hores_imputades_facturables: Optional[float] = 0.0
    preu_venda_hora_aplicat: Optional[float] = None
    factura_id: Optional[uuid.UUID] = None
    factura_serie: Optional[str] = None
    factura_numero: Optional[int] = None
    factura_estat_document: Optional[str] = None
    validada_per_id: Optional[uuid.UUID] = None
    validada_per_nom: Optional[str] = None
    data_validacio: Optional[datetime] = None
    notes_validacio_tecnica: Optional[str] = None
    signatura_present: bool = False
    nom_receptor: Optional[str] = None
    dni_receptor: Optional[str] = None
    desviacio_geovalla: bool = False
    justificacio_geovalla: Optional[str] = None
    disclaimer: Optional[Dict[str, Any]] = None
    te_tram_obert: bool = False
    temps_acumulat_segons: int = 0
    trams_temps: List[TramTempsGestioItem] = []
    linies_picking: List[LiniaPickingItem] = []
    eines: List[EinaItem] = []
    operaris_assignats: List[OperariAssignatItem] = []
    operaris_ids: List[uuid.UUID] = []
    model_config = ConfigDict(from_attributes=True)


class FeinaUpdate(BaseModel):
    titol: Optional[str] = Field(None, max_length=200)
    descripcio: Optional[str] = None
    client_id: Optional[uuid.UUID] = None
    finca_id: Optional[uuid.UUID] = None
    planol_id: Optional[uuid.UUID] = None
    adreca: Optional[str] = Field(None, max_length=255)
    estat: Optional[str] = Field(None, max_length=30)
    data_planificacio: Optional[date] = None
    hora_inici_prevista: Optional[datetime] = None
    hora_fi_prevista: Optional[datetime] = None
    cap_de_colla_id: Optional[uuid.UUID] = None
    operaris_ids: Optional[List[uuid.UUID]] = None
    vehicle_id: Optional[uuid.UUID] = None
    latitud: Optional[float] = None
    longitud: Optional[float] = None
    versio: Optional[int] = None
    eina_ids: Optional[List[uuid.UUID]] = None
    linies_picking: Optional[List[LiniaPickingItem]] = None
    model_config = ConfigDict(from_attributes=True)

    @field_validator("adreca")
    @classmethod
    def validar_adreca_no_buida(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        v_clean = v.strip()
        if not v_clean:
            raise ValueError("L'adreça de l'obra no pot estar buida")
        return v_clean


def _calcular_hores_previstes(ordre: OrdreTreball) -> float:
    """Calcula les hores previstes a partir de hora_inici_prevista i hora_fi_prevista."""
    if (
        ordre.hora_inici_prevista
        and ordre.hora_fi_prevista
        and ordre.hora_fi_prevista > ordre.hora_inici_prevista
    ):
        diff_sec = (ordre.hora_fi_prevista - ordre.hora_inici_prevista).total_seconds()
        return round(diff_sec / 3600.0, 2)
    return 0.0


def _aplicar_veto_rol_feina(f_resp: FeinaResponse, claims: Optional[Dict[str, Any]]) -> FeinaResponse:
    """Preserva dades comercials de venda al client (preu_venda_hora_aplicat) per a ENGINYER/SECRETARIA/BOSS.

    Els costos interns (PMP, cost mà d'obra real, marges empresarials) mai no s'exposen a FeinaResponse.
    """
    _ = claims
    return f_resp


async def _carregar_resum_factures_ots(
    db: AsyncSession,
    emp_uuid: uuid.UUID,
    ot_ids: List[uuid.UUID],
) -> Dict[uuid.UUID, tuple[str, int, str]]:
    """Consulta el resum comercial de factures vinculades a un lot d'OTs via funció SECURITY DEFINER (a027)."""
    if not ot_ids:
        return {}
    res = await db.execute(
        text(
            "SELECT public.obtenir_resum_factures_ots(CAST(:emp_id AS uuid), CAST(:ot_ids AS uuid[]))"
        ),
        {
            "emp_id": str(emp_uuid),
            "ot_ids": [str(x) for x in ot_ids],
        },
    )
    raw_map = res.scalar_one_or_none()
    if not isinstance(raw_map, dict):
        return {}
    out: Dict[uuid.UUID, tuple[str, int, str]] = {}
    for ot_id_str, info in raw_map.items():
        if not isinstance(info, dict):
            continue
        try:
            out[uuid.UUID(ot_id_str)] = (
                str(info.get("serie") or ""),
                int(info.get("numero_factura") or 0),
                str(info.get("estat_document") or ""),
            )
        except (ValueError, TypeError):
            continue
    return out


async def _validar_client_i_permisos(
    db: AsyncSession,
    emp_uuid: uuid.UUID,
    client_id: uuid.UUID,
    cap_de_colla_id: Optional[uuid.UUID],
    vehicle_id: Optional[uuid.UUID],
) -> Client:
    """Valida pertinença i bloqueig de risc operatiu (423), i permís de conduir FR-012 (422)."""
    client_obj = (
        await db.execute(select(Client).where(Client.id == client_id, Client.empresa_id == emp_uuid))
    ).scalars().first()
    if not client_obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Client no trobat")

    if (client_obj.estat_risc_operatiu or "").upper() == "BLOQUEJAT_RISC":
        raise HTTPException(
            status_code=status.HTTP_423_LOCKED,
            detail="Client bloquejat per risc operatiu (BLOQUEJAT_RISC). No es pot donar d'alta l'Ordre de Treball.",
        )

    if cap_de_colla_id and vehicle_id:
        op_db = (
            await db.execute(
                select(Usuari).where(Usuari.id == cap_de_colla_id, Usuari.empresa_id == emp_uuid)
            )
        ).scalars().first()
        veh_db = (
            await db.execute(
                select(Vehicle).where(Vehicle.id == vehicle_id, Vehicle.empresa_id == emp_uuid)
            )
        ).scalars().first()
        if op_db and veh_db:
            validar_permis_conduir(veh_db, op_db)

    return client_obj


async def _preparar_picking_atomic(
    db: AsyncSession,
    emp_uuid: uuid.UUID,
    linies_picking: List[LiniaPickingItem],
    default_magatzem_id: Optional[uuid.UUID],
) -> List[tuple[LiniaPickingItem, float, List[tuple[EstocMagatzem, float]]]]:
    """Adquireix bloquejos SELECT ... WITH FOR UPDATE i valida estoc abans d'inserir cap OT."""
    allocations: List[tuple[LiniaPickingItem, float, List[tuple[EstocMagatzem, float]]]] = []
    pending_by_estoc: Dict[uuid.UUID, float] = {}

    for lp in linies_picking:
        q_req = float(lp.quantitat_prevista)
        target_mag_id = lp.magatzem_id or default_magatzem_id
        stmt_estoc = select(EstocMagatzem).where(
            EstocMagatzem.article_id == lp.article_id,
            EstocMagatzem.empresa_id == emp_uuid,
        )
        if target_mag_id is not None:
            stmt_estoc = stmt_estoc.where(EstocMagatzem.magatzem_id == target_mag_id)
        stmt_estoc = stmt_estoc.order_by(EstocMagatzem.quantitat_fisica.desc()).with_for_update()

        estocs = list((await db.execute(stmt_estoc)).scalars().all())
        if not estocs:
            raise HTTPException(
                status_code=422,
                detail=(
                    f"Stock insuficient: l'article {lp.article_id} no té estoc registrat"
                    + (f" al magatzem {target_mag_id}" if target_mag_id else "")
                ),
            )

        disp_total = sum(
            max(
                0.0,
                float(e.quantitat_fisica)
                - float(e.quantitat_virtual_reservada)
                - pending_by_estoc.get(e.id, 0.0),
            )
            for e in estocs
        )
        if q_req > disp_total:
            raise HTTPException(
                status_code=422,
                detail=(
                    f"Stock insuficient per reservar l'article {lp.article_id}. "
                    f"Disponible: {disp_total}, sol·licitat: {q_req}"
                ),
            )

        remaining = q_req
        line_takes: List[tuple[EstocMagatzem, float]] = []
        for estoc in estocs:
            if remaining <= 0:
                break
            disp = max(
                0.0,
                float(estoc.quantitat_fisica)
                - float(estoc.quantitat_virtual_reservada)
                - pending_by_estoc.get(estoc.id, 0.0),
            )
            if disp <= 0:
                continue
            take = min(disp, remaining)
            pending_by_estoc[estoc.id] = pending_by_estoc.get(estoc.id, 0.0) + take
            line_takes.append((estoc, take))
            remaining -= take
        allocations.append((lp, q_req, line_takes))

    return allocations


async def _aplicar_picking_atomic(
    db: AsyncSession,
    emp_uuid: uuid.UUID,
    ordre: OrdreTreball,
    allocations: List[tuple[LiniaPickingItem, float, List[tuple[EstocMagatzem, float]]]],
) -> FullaPicking:
    """Crea la Fulla de Picking i les seves línies un cop validat i bloquejat l'estoc."""
    fulla = FullaPicking(
        empresa_id=emp_uuid,
        ordre_treball_id=ordre.id,
        vehicle_id=ordre.vehicle_id,
        estat_picking="PENDENT",
    )
    db.add(fulla)
    await db.flush()

    for lp, q_req, line_takes in allocations:
        for estoc, take in line_takes:
            estoc.quantitat_virtual_reservada = float(estoc.quantitat_virtual_reservada) + take
        resolved_mag_id = line_takes[0][0].magatzem_id if line_takes else lp.magatzem_id
        db.add(
            LiniaPicking(
                empresa_id=emp_uuid,
                picking_id=fulla.id,
                article_id=lp.article_id,
                magatzem_id=resolved_mag_id,
                quantitat_prevista=q_req,
                quantitat_carregada_pick_in=0.0,
                quantitat_retornada_pick_out=0.0,
                quantitat_mermada=0.0,
            )
        )

    return fulla


async def _sincronitzar_feina_disc(
    db: AsyncSession,
    emp_uuid: uuid.UUID,
    f_resp: FeinaResponse,
    raw_estat: Optional[str] = None,
) -> None:
    """Sincronitza la OT i el seu picking al disc sobirà de l'empresa sense deixar fitxers a Hetzner."""
    estat_up = str(raw_estat or f_resp.estat or "").upper()
    es_tancada = estat_up in {
        "COMPLERT",
        "TANCADA",
        "COMPLETADA",
        "FINALITZADA",
        "PREFACTURADA",
        "FACTURADA",
        "CANCEL·LADA",
        "CANCELLADA",
    }
    categoria = "ots_historic" if es_tancada else "ots_actives"
    payload = {
        **f_resp.model_dump(mode="json"),
        "synced_at": datetime.now(timezone.utc).isoformat(),
    }
    try:
        ruta = await SovereignStorageGateway.desar_entitat_json(
            db=db,
            empresa_id=emp_uuid,
            categoria=categoria,
            item_id=str(f_resp.id),
            dades=payload,
        )
        if f_resp.linies_picking:
            await SovereignStorageGateway.desar_entitat_json(
                db=db,
                empresa_id=emp_uuid,
                categoria="picking",
                item_id=f"picking_{f_resp.id}",
                dades={
                    "ordre_treball_id": str(f_resp.id),
                    "codi": f_resp.codi,
                    "estat_ot": f_resp.estat,
                    "linies_picking": payload.get("linies_picking", []),
                    "synced_at": payload["synced_at"],
                },
            )
        if not str(ruta).startswith("transit://"):
            await SovereignStorageGateway.drenar_cua_transit_empresa(db, emp_uuid)
    except Exception as exc:
        logger.warning("No s'ha pogut sincronitzar la feina %s al disc sobirà: %s", f_resp.id, exc)


@router.get("", response_model=List[FeinaResponse])
async def llistar_feines(
    request: Request,
    q: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    db: AsyncSession = Depends(get_db_with_tenant_context),
    claims: Dict[str, Any] = Depends(get_current_user_claims),
):
    empresa_id = request.state.empresa_id
    if not empresa_id or empresa_id == "undefined":
        raise HTTPException(status_code=401, detail="No identificat")

    stmt = (
        select(OrdreTreball, Client, Usuari, PlanolBase)
        .outerjoin(Client, OrdreTreball.client_id == Client.id)
        .outerjoin(Usuari, OrdreTreball.cap_de_colla_id == Usuari.id)
        .outerjoin(PlanolBase, OrdreTreball.planol_id == PlanolBase.id)
        .where(OrdreTreball.empresa_id == uuid.UUID(empresa_id))
    )

    if q:
        search_term = f"%{q}%"
        stmt = stmt.where(
            or_(OrdreTreball.codi.ilike(search_term), OrdreTreball.titol.ilike(search_term))
        )

    stmt = stmt.limit(limit).offset(offset).order_by(OrdreTreball.created_at.desc())

    result = await db.execute(stmt)
    rows = result.all()

    # Precarregar Fulles de picking, Eines i Operaris de Colla en batch per a totes les OTs retornades
    ot_ids = [ordre.id for ordre, _, _, _ in rows]
    picking_by_ot: Dict[uuid.UUID, List[LiniaPickingItem]] = collections.defaultdict(list)
    eines_by_ot: Dict[uuid.UUID, List[EinaItem]] = collections.defaultdict(list)
    operaris_by_ot: Dict[uuid.UUID, List[OperariAssignatItem]] = collections.defaultdict(list)
    trams_by_ot: Dict[uuid.UUID, List[TramTempsGestioItem]] = collections.defaultdict(list)

    if ot_ids:
        # 1. Carregar Fulles de picking i línies d'articles en batch
        pk_stmt = (
            select(FullaPicking.ordre_treball_id, LiniaPicking, Article)
            .join(LiniaPicking, LiniaPicking.picking_id == FullaPicking.id)
            .join(Article, LiniaPicking.article_id == Article.id)
            .where(
                FullaPicking.ordre_treball_id.in_(ot_ids),
                FullaPicking.empresa_id == uuid.UUID(empresa_id),
            )
        )
        pk_res = (await db.execute(pk_stmt)).all()
        for ot_id, lp, art in pk_res:
            q_in = float(lp.quantitat_carregada_pick_in or 0.0)
            q_out = float(lp.quantitat_retornada_pick_out or 0.0)
            q_merma = float(lp.quantitat_mermada or 0.0)
            picking_by_ot[ot_id].append(
                LiniaPickingItem(
                    id=lp.id,
                    article_id=art.id,
                    article_nom=art.nom,
                    referencia_inventari=art.referencia_inventari,
                    quantitat_prevista=float(lp.quantitat_prevista or 0.0),
                    quantitat_carregada_pick_in=q_in,
                    quantitat_retornada_pick_out=q_out,
                    quantitat_mermada=q_merma,
                    consum_real=max(0.0, round(q_in - q_out, 3)),
                    origen_estoc=str(getattr(lp, "origen_estoc", "NAU") or "NAU"),
                    unitat_mesura=art.unitat_mesura or "UNITAT",
                    estoc_disponible=0.0,
                    magatzem_id=getattr(lp, "magatzem_id", None),
                )
            )

        # 2. Carregar Eines en custòdia vinculades a les OTs en batch
        eines_stmt = (
            select(EinaCustodia)
            .where(
                EinaCustodia.ordre_treball_id.in_(ot_ids),
                EinaCustodia.empresa_id == uuid.UUID(empresa_id),
            )
        )
        eines_res = (await db.execute(eines_stmt)).scalars().all()
        for e in eines_res:
            if e.ordre_treball_id:
                eines_by_ot[e.ordre_treball_id].append(
                    EinaItem(
                        id=e.id,
                        nom=e.nom,
                        model=getattr(e, "model", None),
                        numero_serie=e.numero_serie,
                        estat=e.estat,
                    )
                )

        # 3. Carregar Operaris de la Colla vinculats a les OTs en batch
        ops_stmt = (
            select(OrdreTreballOperari, Usuari)
            .join(Usuari, OrdreTreballOperari.operari_id == Usuari.id)
            .where(
                OrdreTreballOperari.ordre_treball_id.in_(ot_ids),
                OrdreTreballOperari.empresa_id == uuid.UUID(empresa_id),
            )
            .order_by(OrdreTreballOperari.es_cap_de_colla.desc(), Usuari.nom.asc())
        )
        ops_res = (await db.execute(ops_stmt)).all()
        for oto, u in ops_res:
            operaris_by_ot[oto.ordre_treball_id].append(
                OperariAssignatItem(
                    id=u.id,
                    nom=u.nom,
                    cognoms=u.cognoms,
                    rol=u.rol,
                    es_cap_de_colla=oto.es_cap_de_colla,
                    telefon=u.telefon,
                )
            )

        # 4. Carregar Trams de Temps multi-interval en batch
        trams_stmt = (
            select(OrdreTreballTramTemps)
            .where(
                OrdreTreballTramTemps.ordre_treball_id.in_(ot_ids),
                OrdreTreballTramTemps.empresa_id == uuid.UUID(empresa_id),
            )
            .order_by(OrdreTreballTramTemps.hora_inici.asc())
        )
        trams_res = (await db.execute(trams_stmt)).scalars().all()
        for t in trams_res:
            trams_by_ot[t.ordre_treball_id].append(TramTempsGestioItem.model_validate(t))

    emp_uuid = uuid.UUID(empresa_id)
    factures_by_ot = await _carregar_resum_factures_ots(db, emp_uuid, ot_ids)

    val_ids = list({ordre.validada_per_id for ordre, _, _, _ in rows if ordre.validada_per_id is not None})
    validadors_map: Dict[uuid.UUID, str] = {}
    if val_ids:
        v_rows = (
            await db.execute(
                select(Usuari.id, Usuari.nom, Usuari.cognoms).where(
                    Usuari.empresa_id == emp_uuid,
                    Usuari.id.in_(val_ids),
                )
            )
        ).all()
        validadors_map = {vid: f"{vnom} {vcog or ''}".strip() for vid, vnom, vcog in v_rows}

    barema_empresa = await obtenir_barema_empresa(db, emp_uuid)
    feines = []
    for ordre, client, operari, planol in rows:
        f_resp = FeinaResponse.model_validate(ordre)
        if ordre.id in factures_by_ot:
            f_ser, f_num, f_edoc = factures_by_ot[ordre.id]
            f_resp.factura_serie = f_ser
            f_resp.factura_numero = f_num
            f_resp.factura_estat_document = f_edoc
        if ordre.validada_per_id and ordre.validada_per_id in validadors_map:
            f_resp.validada_per_nom = validadors_map[ordre.validada_per_id]
        f_resp.signatura_present = bool(ordre.signatura_client_path)
        f_resp.desviacio_geovalla = bool(ordre.desviacio_geovalla)
        f_resp.hores_previstes = _calcular_hores_previstes(ordre)
        f_resp.preu_venda_hora_aplicat = await resoldre_preu_hora_control_panel(
            db,
            emp_uuid,
            ordre,
            barema_cache=barema_empresa,
            barema_fetched=True,
        )
        # Resolució automàtica de coordenades si no estaven persistides
        if (f_resp.latitud is None or f_resp.longitud is None) and ordre.adreca:
            c_lat, c_lng = geocodificar_adreca(ordre.adreca)
            if c_lat is not None and c_lng is not None:
                f_resp.latitud = c_lat
                f_resp.longitud = c_lng
        if client:
            f_resp.client_nom = client.rao_social
        if operari:
            f_resp.cap_de_colla_nom = f"{operari.nom} {operari.cognoms or ''}".strip()
        if planol:
            f_resp.planol_titol = planol.titol
            f_resp.planol_codi = planol.codi_referencia

        # Assignar materials de picking i eines en custòdia reals
        f_resp.linies_picking = picking_by_ot.get(ordre.id, [])
        f_resp.eines = eines_by_ot.get(ordre.id, [])
        f_resp.eina_ids = [e.id for e in f_resp.eines]

        # Assignar trams de temps treballats
        ot_trams = trams_by_ot.get(ordre.id, [])
        f_resp.trams_temps = ot_trams
        f_resp.te_tram_obert = any(t.hora_fi is None for t in ot_trams) or (
            ordre.estat == "EN_CURS" and ordre.hora_inici_real is not None and ordre.hora_fi_real is None
        )
        f_resp.temps_acumulat_segons = sum(t.durada_segons for t in ot_trams if t.hora_fi is not None)
        if not ot_trams and ordre.hores_imputades_facturables:
            f_resp.temps_acumulat_segons = int(round(float(ordre.hores_imputades_facturables) * 3600.0))

        f_resp.disclaimer = calcular_estat_disclaimer_ot(
            ordre.estat,
            te_tram_obert=f_resp.te_tram_obert,
            validada_per_id=ordre.validada_per_id,
            factura_id=ordre.factura_id,
            factura_estat_document=f_resp.factura_estat_document,
        )

        # Assignar membres de colla
        assigned_ops = operaris_by_ot.get(ordre.id, [])
        if not assigned_ops and operari:
            # Fallback legacy si la feina té cap_de_colla_id però no tenia fila a ordres_treball_operaris
            assigned_ops = [
                OperariAssignatItem(
                    id=operari.id,
                    nom=operari.nom,
                    cognoms=operari.cognoms,
                    rol=operari.rol,
                    es_cap_de_colla=True,
                    telefon=operari.telefon,
                )
            ]
        f_resp.operaris_assignats = assigned_ops
        f_resp.operaris_ids = [op.id for op in assigned_ops]

        feines.append(_aplicar_veto_rol_feina(f_resp, claims))

    return feines


@router.post("", response_model=FeinaResponse, status_code=status.HTTP_201_CREATED)
async def alta_feina(
    request: Request,
    feina: FeinaCreate,
    db: AsyncSession = Depends(get_db_with_tenant_context),
    claims: Dict[str, Any] = Depends(get_current_user_claims),
):
    empresa_id = request.state.empresa_id
    if not empresa_id or empresa_id == "undefined":
        raise HTTPException(status_code=401, detail="No identificat")
    emp_uuid = uuid.UUID(empresa_id)

    stmt_codi = select(OrdreTreball).where(
        OrdreTreball.empresa_id == emp_uuid, OrdreTreball.codi == feina.codi
    )
    result_codi = await db.execute(stmt_codi)
    if result_codi.scalars().first():
        raise HTTPException(status_code=400, detail="El codi de feina ja es troba registrat")

    # Validar Client (404 / 423 BLOQUEJAT_RISC) i permís de conduir (FR-012) abans de crear la OT
    await _validar_client_i_permisos(
        db=db,
        emp_uuid=emp_uuid,
        client_id=feina.client_id,
        cap_de_colla_id=feina.cap_de_colla_id,
        vehicle_id=feina.vehicle_id,
    )

    # Adquirir bloquejos SELECT ... FOR UPDATE i validar disponibilitat d'estoc ABANS de crear l'OT
    picking_allocations: List[tuple[LiniaPickingItem, float, List[tuple[EstocMagatzem, float]]]] = []
    if feina.linies_picking:
        picking_allocations = await _preparar_picking_atomic(
            db=db,
            emp_uuid=emp_uuid,
            linies_picking=feina.linies_picking,
            default_magatzem_id=feina.magatzem_id,
        )

    # Coordenades: geocodificar adreça de text o respectar coordenades directes
    lat, lng = geocodificar_adreca(feina.adreca, feina.latitud, feina.longitud)

    if (lat is None or lng is None) and feina.finca_id:
        stmt_finca = select(Finca).where(
            Finca.id == feina.finca_id,
            Finca.empresa_id == emp_uuid,
        )
        finca_db = (await db.execute(stmt_finca)).scalars().first()
        if finca_db and finca_db.latitud is not None and finca_db.longitud is not None:
            lat = float(finca_db.latitud)
            lng = float(finca_db.longitud)

    barema_empresa = await obtenir_barema_empresa(db, emp_uuid)
    preu_hora_inicial = (
        float(barema_empresa["preu_hora_standard_eur"])
        if barema_empresa is not None and barema_empresa.get("preu_hora_standard_eur") is not None
        else 0.0
    )

    nova_feina = OrdreTreball(
        empresa_id=emp_uuid,
        codi=feina.codi,
        client_id=feina.client_id,
        finca_id=feina.finca_id,
        planol_id=feina.planol_id,
        titol=feina.titol,
        adreca=feina.adreca,
        descripcio=feina.descripcio,
        estat="ASSIGNADA"
        if (feina.cap_de_colla_id or feina.operaris_ids) and feina.estat == "PENDENT"
        else feina.estat,
        data_planificacio=feina.data_planificacio,
        hora_inici_prevista=feina.hora_inici_prevista,
        hora_fi_prevista=feina.hora_fi_prevista,
        cap_de_colla_id=feina.cap_de_colla_id,
        vehicle_id=feina.vehicle_id,
        latitud=lat,
        longitud=lng,
        preu_venda_hora_aplicat=preu_hora_inicial,
    )

    try:
        db.add(nova_feina)
        await db.flush()

        # Sincronitzar estat del vehicle a ASSIGNAT si la feina és activa
        if nova_feina.vehicle_id and nova_feina.estat in ("PENDENT", "ASSIGNADA", "PROGRAMADA", "EN_CURS", "EN_RUTA", "EN_OBRA"):
            stmt_v = select(Vehicle).where(
                Vehicle.id == nova_feina.vehicle_id,
                Vehicle.empresa_id == emp_uuid,
            )
            veh_obj = (await db.execute(stmt_v)).scalars().first()
            if veh_obj and veh_obj.estat == "OPERATIU":
                veh_obj.estat = "ASSIGNAT"

        # Custòdia d'eines seleccionades per a la feina
        if feina.eina_ids:
            for eina_id in feina.eina_ids:
                stmt_eina = select(EinaCustodia).where(
                    EinaCustodia.id == eina_id,
                    EinaCustodia.empresa_id == emp_uuid,
                )
                eina_obj = (await db.execute(stmt_eina)).scalars().first()
                if eina_obj:
                    eina_obj.estat = "CUSTODIADA"
                    eina_obj.ordre_treball_id = nova_feina.id
                    if feina.cap_de_colla_id:
                        eina_obj.custodiat_per_operari_id = feina.cap_de_colla_id

        # Assignació de Quadrilla / Colla (Cap de Colla Responsable + Operaris de suport sense duplicats)
        operaris_a_assignar: Dict[uuid.UUID, bool] = {}
        if feina.cap_de_colla_id:
            operaris_a_assignar[feina.cap_de_colla_id] = True
        if feina.operaris_ids:
            for op_id in feina.operaris_ids:
                if op_id not in operaris_a_assignar:
                    operaris_a_assignar[op_id] = False

        for op_id, es_cap in operaris_a_assignar.items():
            db.add(
                OrdreTreballOperari(
                    empresa_id=emp_uuid,
                    ordre_treball_id=nova_feina.id,
                    operari_id=op_id,
                    es_cap_de_colla=es_cap,
                )
            )

        if picking_allocations:
            await _aplicar_picking_atomic(
                db=db,
                emp_uuid=emp_uuid,
                ordre=nova_feina,
                allocations=picking_allocations,
            )

        await db.commit()
    except Exception:
        await db.rollback()
        raise

    f_resp = await build_feina_response(nova_feina, db, emp_uuid)
    await _sincronitzar_feina_disc(db, emp_uuid, f_resp, nova_feina.estat)
    return _aplicar_veto_rol_feina(f_resp, claims)


@router.get("/mapa")
async def llistar_feines_mapa(
    request: Request, db: AsyncSession = Depends(get_db_with_tenant_context)
):
    empresa_id = getattr(request.state, "empresa_id", None) or request.headers.get("X-Empresa-ID")
    if not empresa_id or empresa_id == "undefined":
        raise HTTPException(status_code=401, detail="No identificat")

    stmt = (
        select(OrdreTreball, Client, Finca)
        .outerjoin(Client, OrdreTreball.client_id == Client.id)
        .outerjoin(Finca, OrdreTreball.finca_id == Finca.id)
        .where(
            OrdreTreball.empresa_id == uuid.UUID(empresa_id),
            OrdreTreball.estat.in_(["PENDENT", "EN_CURS", "BLOQUEJADA", "EN_OBRA", "EN_RUTA", "ASSIGNADA", "PROGRAMADA"]),
        )
        .order_by(OrdreTreball.created_at.desc())
    )
    result = await db.execute(stmt)
    rows = result.all()

    features = []
    for ordre, client, finca in rows:
        lat = ordre.latitud
        lng = ordre.longitud

        if lat is None or lng is None:
            if finca and finca.latitud is not None and finca.longitud is not None:
                lat = float(finca.latitud)
                lng = float(finca.longitud)

        if lat is None or lng is None:
            c_lat, c_lng = geocodificar_adreca(ordre.adreca)
            if c_lat is not None and c_lng is not None:
                lat, lng = c_lat, c_lng

        if lat is None or lng is None:
            continue

        features.append(
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [float(lng), float(lat)]},
                "properties": {
                    "id": str(ordre.id),
                    "codi": ordre.codi,
                    "titol": ordre.titol,
                    "estat": ordre.estat,
                    "adreca": ordre.adreca,
                    "cap_de_colla_id": str(ordre.cap_de_colla_id) if ordre.cap_de_colla_id else None,
                    "client_rao_social": client.rao_social if client else None,
                    "is_incidencia": False,
                },
            }
        )

    return {"type": "FeatureCollection", "features": features}


async def build_feina_response(
    ordre: OrdreTreball, db: AsyncSession, empresa_id: uuid.UUID
) -> FeinaResponse:
    """Construeix la resposta completa d'una Ordre de Treball amb plànol, picking i eines."""
    f_resp = FeinaResponse.model_validate(ordre)
    if ordre.factura_id:
        fact_map = await _carregar_resum_factures_ots(db, empresa_id, [ordre.id])
        if ordre.id in fact_map:
            f_resp.factura_serie, f_resp.factura_numero, f_resp.factura_estat_document = fact_map[
                ordre.id
            ]
    if ordre.validada_per_id:
        val_obj = (
            await db.execute(
                select(Usuari.nom, Usuari.cognoms).where(
                    Usuari.id == ordre.validada_per_id,
                    Usuari.empresa_id == empresa_id,
                )
            )
        ).first()
        if val_obj:
            f_resp.validada_per_nom = f"{val_obj[0]} {val_obj[1] or ''}".strip()
    f_resp.signatura_present = bool(ordre.signatura_client_path)
    f_resp.desviacio_geovalla = bool(ordre.desviacio_geovalla)
    f_resp.hores_previstes = _calcular_hores_previstes(ordre)
    f_resp.preu_venda_hora_aplicat = await resoldre_preu_hora_control_panel(
        db, empresa_id, ordre
    )

    # Trams de temps treballats
    trams_stmt = (
        select(OrdreTreballTramTemps)
        .where(
            OrdreTreballTramTemps.ordre_treball_id == ordre.id,
            OrdreTreballTramTemps.empresa_id == empresa_id,
        )
        .order_by(OrdreTreballTramTemps.hora_inici.asc())
    )
    ot_trams = [
        TramTempsGestioItem.model_validate(t)
        for t in (await db.execute(trams_stmt)).scalars().all()
    ]
    f_resp.trams_temps = ot_trams
    f_resp.te_tram_obert = any(t.hora_fi is None for t in ot_trams) or (
        ordre.estat == "EN_CURS" and ordre.hora_inici_real is not None and ordre.hora_fi_real is None
    )
    f_resp.temps_acumulat_segons = sum(t.durada_segons for t in ot_trams if t.hora_fi is not None)
    if not ot_trams and ordre.hores_imputades_facturables:
        f_resp.temps_acumulat_segons = int(round(float(ordre.hores_imputades_facturables) * 3600.0))

    # Coordenades
    if (f_resp.latitud is None or f_resp.longitud is None) and ordre.adreca:
        c_lat, c_lng = geocodificar_adreca(ordre.adreca)
        if c_lat is not None and c_lng is not None:
            f_resp.latitud = c_lat
            f_resp.longitud = c_lng

    # Client
    if ordre.client_id:
        c_stmt = select(Client.rao_social).where(Client.id == ordre.client_id)
        f_resp.client_nom = (await db.execute(c_stmt)).scalars().first()

    # Cap de colla
    if ordre.cap_de_colla_id:
        u_stmt = select(Usuari).where(Usuari.id == ordre.cap_de_colla_id)
        u_obj = (await db.execute(u_stmt)).scalars().first()
        if u_obj:
            f_resp.cap_de_colla_nom = f"{u_obj.nom} {u_obj.cognoms or ''}".strip()

    # Plànol
    if ordre.planol_id:
        p_stmt = select(PlanolBase).where(
            PlanolBase.id == ordre.planol_id,
            PlanolBase.empresa_id == empresa_id,
        )
        p_obj = (await db.execute(p_stmt)).scalars().first()
        if p_obj:
            f_resp.planol_titol = p_obj.titol
            f_resp.planol_codi = p_obj.codi_referencia

    # Fulla de picking i línies
    pk_stmt = select(FullaPicking).where(
        FullaPicking.ordre_treball_id == ordre.id,
        FullaPicking.empresa_id == empresa_id,
    )
    fulla = (await db.execute(pk_stmt)).scalars().first()
    linies_items: List[LiniaPickingItem] = []
    if fulla:
        lin_stmt = (
            select(LiniaPicking, Article)
            .join(Article, LiniaPicking.article_id == Article.id)
            .where(LiniaPicking.picking_id == fulla.id)
        )
        lin_rows = (await db.execute(lin_stmt)).all()
        for lp, art in lin_rows:
            lp_mag_id = getattr(lp, "magatzem_id", None)
            estoc_stmt = select(
                func.coalesce(
                    func.sum(EstocMagatzem.quantitat_fisica - EstocMagatzem.quantitat_virtual_reservada),
                    0.0,
                )
            ).where(
                EstocMagatzem.article_id == art.id,
                EstocMagatzem.empresa_id == empresa_id,
            )
            if lp_mag_id is not None:
                estoc_stmt = estoc_stmt.where(EstocMagatzem.magatzem_id == lp_mag_id)
            disp = float((await db.execute(estoc_stmt)).scalar() or 0.0)
            q_in = float(lp.quantitat_carregada_pick_in or 0.0)
            q_out = float(lp.quantitat_retornada_pick_out or 0.0)
            q_merma = float(lp.quantitat_mermada or 0.0)
            linies_items.append(
                LiniaPickingItem(
                    id=lp.id,
                    article_id=art.id,
                    article_nom=art.nom,
                    referencia_inventari=art.referencia_inventari,
                    quantitat_prevista=float(lp.quantitat_prevista or 0.0),
                    quantitat_carregada_pick_in=q_in,
                    quantitat_retornada_pick_out=q_out,
                    quantitat_mermada=q_merma,
                    consum_real=max(0.0, round(q_in - q_out, 3)),
                    origen_estoc=str(getattr(lp, "origen_estoc", "NAU") or "NAU"),
                    unitat_mesura=art.unitat_mesura or "UNITAT",
                    estoc_disponible=max(0.0, disp),
                    magatzem_id=lp_mag_id,
                )
            )
    f_resp.linies_picking = linies_items

    # Eines en custòdia vinculades a la feina
    eines_stmt = select(EinaCustodia).where(
        EinaCustodia.ordre_treball_id == ordre.id,
        EinaCustodia.empresa_id == empresa_id,
    )
    eines_db = (await db.execute(eines_stmt)).scalars().all()
    f_resp.eines = [
        EinaItem(
            id=e.id,
            nom=e.nom,
            model=getattr(e, "model", None),
            numero_serie=e.numero_serie,
            estat=e.estat,
        )
        for e in eines_db
    ]
    f_resp.eina_ids = [e.id for e in eines_db]

    # Operaris assignats a la Colla
    op_stmt = (
        select(OrdreTreballOperari, Usuari)
        .join(Usuari, OrdreTreballOperari.operari_id == Usuari.id)
        .where(
            OrdreTreballOperari.ordre_treball_id == ordre.id,
            OrdreTreballOperari.empresa_id == empresa_id,
        )
        .order_by(OrdreTreballOperari.es_cap_de_colla.desc(), Usuari.nom.asc())
    )
    op_rows = (await db.execute(op_stmt)).all()
    assigned_ops: List[OperariAssignatItem] = []
    for oto, u in op_rows:
        assigned_ops.append(
            OperariAssignatItem(
                id=u.id,
                nom=u.nom,
                cognoms=u.cognoms,
                rol=u.rol,
                es_cap_de_colla=oto.es_cap_de_colla,
                telefon=u.telefon,
            )
        )
    if not assigned_ops and ordre.cap_de_colla_id and u_obj:
        assigned_ops.append(
            OperariAssignatItem(
                id=u_obj.id,
                nom=u_obj.nom,
                cognoms=u_obj.cognoms,
                rol=u_obj.rol,
                es_cap_de_colla=True,
                telefon=u_obj.telefon,
            )
        )
    f_resp.operaris_assignats = assigned_ops
    f_resp.operaris_ids = [op.id for op in assigned_ops]
    f_resp.disclaimer = calcular_estat_disclaimer_ot(
        ordre.estat,
        te_tram_obert=f_resp.te_tram_obert,
        validada_per_id=ordre.validada_per_id,
        factura_id=ordre.factura_id,
        factura_estat_document=f_resp.factura_estat_document,
    )

    return f_resp


@router.get("/{feina_id}", response_model=FeinaResponse)
async def obtenir_feina(
    feina_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_db_with_tenant_context),
    claims: Dict[str, Any] = Depends(get_current_user_claims),
):
    """Obté el detall complet d'una Ordre de Treball per ID amb aïllament RLS."""
    empresa_id = getattr(request.state, "empresa_id", None) or request.headers.get("X-Empresa-ID")
    if not empresa_id or empresa_id in ("undefined", "null", "None"):
        raise HTTPException(status_code=401, detail="No identificat")
    emp_uuid = uuid.UUID(empresa_id)

    stmt = select(OrdreTreball).where(
        OrdreTreball.id == feina_id,
        OrdreTreball.empresa_id == emp_uuid,
    )
    result = await db.execute(stmt)
    ordre = result.scalars().first()
    if not ordre:
        raise HTTPException(status_code=404, detail="Ordre de treball no trobada")

    f_resp = await build_feina_response(ordre, db, emp_uuid)
    return _aplicar_veto_rol_feina(f_resp, claims)


@router.put("/{feina_id}", response_model=FeinaResponse)
async def modificar_feina(
    feina_id: uuid.UUID,
    payload: FeinaUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db_with_tenant_context),
    claims: Dict[str, Any] = Depends(get_current_user_claims),
):
    """Actualitza i edita una Ordre de Treball existent amb concurrència optimista."""
    empresa_id = getattr(request.state, "empresa_id", None) or request.headers.get("X-Empresa-ID")
    if not empresa_id or empresa_id in ("undefined", "null", "None"):
        raise HTTPException(status_code=401, detail="No identificat")
    emp_uuid = uuid.UUID(empresa_id)

    stmt = select(OrdreTreball).where(
        OrdreTreball.id == feina_id,
        OrdreTreball.empresa_id == emp_uuid,
    )
    result = await db.execute(stmt)
    ordre = result.scalars().first()
    if not ordre:
        raise HTTPException(status_code=404, detail="Ordre de treball no trobada")

    if payload.versio is not None and ordre.versio != payload.versio:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Conflicte de concurrència: la feina ha estat modificada per un altre usuari (versió actual: {ordre.versio}, versió enviada: {payload.versio})",
        )

    update_data = payload.model_dump(exclude_unset=True)
    antic_vehicle_id = ordre.vehicle_id

    if "client_id" in update_data and update_data["client_id"]:
        await _validar_client_i_permisos(
            db=db,
            emp_uuid=emp_uuid,
            client_id=update_data["client_id"],
            cap_de_colla_id=None,
            vehicle_id=None,
        )

    if "titol" in update_data and update_data["titol"]:
        ordre.titol = update_data["titol"].strip()
    if "descripcio" in update_data:
        ordre.descripcio = update_data["descripcio"].strip() if update_data["descripcio"] else None
    if "client_id" in update_data and update_data["client_id"]:
        ordre.client_id = update_data["client_id"]
    if "finca_id" in update_data:
        ordre.finca_id = update_data["finca_id"]
    if "planol_id" in update_data:
        ordre.planol_id = update_data["planol_id"]
    if "data_planificacio" in update_data and update_data["data_planificacio"]:
        ordre.data_planificacio = update_data["data_planificacio"]
    if "hora_inici_prevista" in update_data:
        ordre.hora_inici_prevista = update_data["hora_inici_prevista"]
    if "hora_fi_prevista" in update_data:
        ordre.hora_fi_prevista = update_data["hora_fi_prevista"]
    if "estat" in update_data and update_data["estat"]:
        ordre.estat = update_data["estat"]
    if "vehicle_id" in update_data:
        ordre.vehicle_id = update_data["vehicle_id"]

    # Assignació operativa (cap de colla)
    if "cap_de_colla_id" in update_data:
        nou_cap = update_data["cap_de_colla_id"]
        ordre.cap_de_colla_id = nou_cap
        if nou_cap and ordre.estat == "PENDENT":
            ordre.estat = "ASSIGNADA"
        elif not nou_cap and ordre.estat == "ASSIGNADA":
            ordre.estat = "PENDENT"

    # Validar FR-012 si canvia cap de colla o vehicle assignat
    if ("cap_de_colla_id" in update_data or "vehicle_id" in update_data) and ordre.cap_de_colla_id and ordre.vehicle_id:
        op_db = (
            await db.execute(
                select(Usuari).where(Usuari.id == ordre.cap_de_colla_id, Usuari.empresa_id == emp_uuid)
            )
        ).scalars().first()
        veh_db = (
            await db.execute(
                select(Vehicle).where(Vehicle.id == ordre.vehicle_id, Vehicle.empresa_id == emp_uuid)
            )
        ).scalars().first()
        if op_db and veh_db:
            validar_permis_conduir(veh_db, op_db)

    # Sincronització de Colla / Operaris de suport (sense duplicats)
    if "operaris_ids" in update_data or "cap_de_colla_id" in update_data:
        cap_id = ordre.cap_de_colla_id
        target_operaris_ids = update_data.get("operaris_ids")
        if target_operaris_ids is None:
            stmt_curr_ops = select(OrdreTreballOperari.operari_id).where(
                OrdreTreballOperari.ordre_treball_id == ordre.id,
                OrdreTreballOperari.empresa_id == uuid.UUID(empresa_id),
            )
            target_operaris_ids = list((await db.execute(stmt_curr_ops)).scalars().all())

        operaris_map = {}
        if cap_id:
            operaris_map[cap_id] = True
        for op_id in target_operaris_ids:
            if op_id not in operaris_map:
                operaris_map[op_id] = False

        stmt_del_ops = delete(OrdreTreballOperari).where(
            OrdreTreballOperari.ordre_treball_id == ordre.id,
            OrdreTreballOperari.empresa_id == uuid.UUID(empresa_id),
        )
        await db.execute(stmt_del_ops)

        for op_id, es_cap in operaris_map.items():
            db.add(
                OrdreTreballOperari(
                    empresa_id=uuid.UUID(empresa_id),
                    ordre_treball_id=ordre.id,
                    operari_id=op_id,
                    es_cap_de_colla=es_cap,
                )
            )

    # Adreça i coordenades
    if "adreca" in update_data and update_data["adreca"]:
        ordre.adreca = update_data["adreca"].strip()
        c_lat, c_lng = geocodificar_adreca(
            ordre.adreca, update_data.get("latitud"), update_data.get("longitud")
        )
        if c_lat is not None and c_lng is not None:
            ordre.latitud = c_lat
            ordre.longitud = c_lng
    elif "latitud" in update_data and "longitud" in update_data:
        ordre.latitud = update_data["latitud"]
        ordre.longitud = update_data["longitud"]

    # Eines en custòdia
    if "eina_ids" in update_data and update_data["eina_ids"] is not None:
        target_eina_ids = set(update_data["eina_ids"])
        stmt_linked = select(EinaCustodia).where(
            EinaCustodia.ordre_treball_id == ordre.id,
            EinaCustodia.empresa_id == uuid.UUID(empresa_id),
        )
        current_linked_eines = (await db.execute(stmt_linked)).scalars().all()
        for e in current_linked_eines:
            if e.id not in target_eina_ids:
                e.ordre_treball_id = None
                e.estat = "DISPONIBLE"
                e.custodiat_per_operari_id = None

        for eina_id in target_eina_ids:
            stmt_eina = select(EinaCustodia).where(
                EinaCustodia.id == eina_id,
                EinaCustodia.empresa_id == uuid.UUID(empresa_id),
            )
            eina_obj = (await db.execute(stmt_eina)).scalars().first()
            if eina_obj:
                eina_obj.estat = "CUSTODIADA"
                eina_obj.ordre_treball_id = ordre.id
                if ordre.cap_de_colla_id:
                    eina_obj.custodiat_per_operari_id = ordre.cap_de_colla_id
    elif "cap_de_colla_id" in update_data:
        stmt_linked = select(EinaCustodia).where(
            EinaCustodia.ordre_treball_id == ordre.id,
            EinaCustodia.empresa_id == uuid.UUID(empresa_id),
        )
        linked_eines = (await db.execute(stmt_linked)).scalars().all()
        for e in linked_eines:
            e.custodiat_per_operari_id = ordre.cap_de_colla_id

    # Sincronització de Fulla de Picking (Pickup de Materials) i reserves d'estoc
    if "linies_picking" in update_data and update_data["linies_picking"] is not None:
        stmt_fulla = select(FullaPicking).where(
            FullaPicking.ordre_treball_id == ordre.id,
            FullaPicking.empresa_id == uuid.UUID(empresa_id),
        )
        fulla = (await db.execute(stmt_fulla)).scalars().first()
        if not fulla:
            fulla = FullaPicking(
                empresa_id=uuid.UUID(empresa_id),
                ordre_treball_id=ordre.id,
                vehicle_id=ordre.vehicle_id,
                estat_picking="PENDENT",
            )
            db.add(fulla)
            await db.flush()
        else:
            if ordre.vehicle_id:
                fulla.vehicle_id = ordre.vehicle_id

        stmt_existing_linies = select(LiniaPicking).where(LiniaPicking.picking_id == fulla.id)
        existing_linies = (await db.execute(stmt_existing_linies)).scalars().all()
        existing_map = {lin.article_id: lin for lin in existing_linies}
        new_linies_list = update_data["linies_picking"]
        new_article_ids = {
            lp["article_id"] if isinstance(lp, dict) else lp.article_id for lp in new_linies_list
        }

        # 1. Eliminar línies descartades i alliberar reserva d'estoc
        for art_id, old_line in existing_map.items():
            if art_id not in new_article_ids:
                stmt_estoc = select(EstocMagatzem).where(
                    EstocMagatzem.article_id == art_id,
                    EstocMagatzem.empresa_id == uuid.UUID(empresa_id),
                )
                if getattr(old_line, "magatzem_id", None) is not None:
                    stmt_estoc = stmt_estoc.where(EstocMagatzem.magatzem_id == old_line.magatzem_id)
                stmt_estoc = stmt_estoc.with_for_update()
                estoc = (await db.execute(stmt_estoc)).scalars().first()
                if estoc:
                    estoc.quantitat_virtual_reservada = max(
                        0.0,
                        float(estoc.quantitat_virtual_reservada)
                        - float(old_line.quantitat_prevista or 0.0),
                    )
                await db.delete(old_line)

        # 2. Afegir o actualitzar línies sol·licitades
        for lp in new_linies_list:
            art_id = lp["article_id"] if isinstance(lp, dict) else lp.article_id
            lp_mag = lp.get("magatzem_id") if isinstance(lp, dict) else getattr(lp, "magatzem_id", None)
            q_prevista = float(
                lp["quantitat_prevista"] if isinstance(lp, dict) else lp.quantitat_prevista
            )
            if art_id in existing_map:
                line = existing_map[art_id]
                diff = q_prevista - float(line.quantitat_prevista or 0.0)
                if diff != 0:
                    target_mag = lp_mag or getattr(line, "magatzem_id", None)
                    stmt_estoc = select(EstocMagatzem).where(
                        EstocMagatzem.article_id == art_id,
                        EstocMagatzem.empresa_id == uuid.UUID(empresa_id),
                    )
                    if target_mag is not None:
                        stmt_estoc = stmt_estoc.where(EstocMagatzem.magatzem_id == target_mag)
                    stmt_estoc = stmt_estoc.with_for_update()
                    estoc = (await db.execute(stmt_estoc)).scalars().first()
                    if estoc:
                        if diff > 0:
                            disp = float(estoc.quantitat_fisica) - float(
                                estoc.quantitat_virtual_reservada
                            )
                            if diff > disp:
                                raise HTTPException(
                                    status_code=422,
                                    detail=f"Stock insuficient per ampliar reserva de l'article {art_id}. Disponible: {disp}, sol·licitat extra: {diff}",
                                )
                        estoc.quantitat_virtual_reservada = max(
                            0.0, float(estoc.quantitat_virtual_reservada) + diff
                        )
                    line.quantitat_prevista = q_prevista
                    if lp_mag is not None:
                        line.magatzem_id = lp_mag
            else:
                stmt_estoc = select(EstocMagatzem).where(
                    EstocMagatzem.article_id == art_id,
                    EstocMagatzem.empresa_id == uuid.UUID(empresa_id),
                )
                if lp_mag is not None:
                    stmt_estoc = stmt_estoc.where(EstocMagatzem.magatzem_id == lp_mag)
                stmt_estoc = stmt_estoc.order_by(EstocMagatzem.quantitat_fisica.desc()).with_for_update()
                estoc = (await db.execute(stmt_estoc)).scalars().first()
                if estoc:
                    disp = float(estoc.quantitat_fisica) - float(estoc.quantitat_virtual_reservada)
                    if q_prevista > disp:
                        raise HTTPException(
                            status_code=422,
                            detail=f"Stock insuficient per reservar l'article {art_id}. Disponible: {disp}, sol·licitat: {q_prevista}",
                        )
                    estoc.quantitat_virtual_reservada = (
                        float(estoc.quantitat_virtual_reservada) + q_prevista
                    )
                nova_linia = LiniaPicking(
                    empresa_id=uuid.UUID(empresa_id),
                    picking_id=fulla.id,
                    article_id=art_id,
                    magatzem_id=lp_mag or (estoc.magatzem_id if estoc else None),
                    quantitat_prevista=q_prevista,
                    quantitat_carregada_pick_in=0.0,
                    quantitat_retornada_pick_out=0.0,
                    quantitat_mermada=0.0,
                )
                db.add(nova_linia)

    if (
        str(ordre.estat or "").upper()
        in (
            "TANCADA",
            "COMPLETADA",
            "FINALITZADA",
            "COMPLERT",
            "EXECUTADA_PENDENT_VALIDACIO",
            "ALBARA_SIGNAT",
        )
        and ordre.data_finalitzacio_camp is None
    ):
        ordre.data_finalitzacio_camp = date.today()

    # Sincronització de l'estat del vehicle
    nou_vehicle_id = ordre.vehicle_id
    if antic_vehicle_id != nou_vehicle_id or "estat" in update_data:
        if antic_vehicle_id and antic_vehicle_id != nou_vehicle_id:
            stmt_altres = select(OrdreTreball).where(
                OrdreTreball.vehicle_id == antic_vehicle_id,
                OrdreTreball.id != ordre.id,
                OrdreTreball.empresa_id == uuid.UUID(empresa_id),
                OrdreTreball.estat.in_(["PENDENT", "ASSIGNADA", "PROGRAMADA", "EN_CURS", "EN_RUTA", "EN_OBRA"]),
            )
            altres = (await db.execute(stmt_altres)).scalars().first()
            if not altres:
                stmt_v_antic = select(Vehicle).where(
                    Vehicle.id == antic_vehicle_id,
                    Vehicle.empresa_id == uuid.UUID(empresa_id),
                )
                v_antic = (await db.execute(stmt_v_antic)).scalars().first()
                if v_antic and v_antic.estat == "ASSIGNAT":
                    v_antic.estat = "OPERATIU"

        if nou_vehicle_id:
            stmt_v_nou = select(Vehicle).where(
                Vehicle.id == nou_vehicle_id,
                Vehicle.empresa_id == uuid.UUID(empresa_id),
            )
            v_nou = (await db.execute(stmt_v_nou)).scalars().first()
            if v_nou:
                if ordre.estat in ("PENDENT", "ASSIGNADA", "PROGRAMADA", "EN_CURS", "EN_RUTA", "EN_OBRA"):
                    if v_nou.estat == "OPERATIU":
                        v_nou.estat = "ASSIGNAT"
                elif ordre.estat in (
                    "TANCADA",
                    "COMPLETADA",
                    "FINALITZADA",
                    "COMPLERT",
                    "EXECUTADA_PENDENT_VALIDACIO",
                    "ALBARA_SIGNAT",
                    "CANCEL·LADA",
                ):
                    if ordre.estat != "CANCEL·LADA" and ordre.data_finalitzacio_camp is None:
                        ordre.data_finalitzacio_camp = date.today()
                    stmt_altres = select(OrdreTreball).where(
                        OrdreTreball.vehicle_id == nou_vehicle_id,
                        OrdreTreball.id != ordre.id,
                        OrdreTreball.empresa_id == uuid.UUID(empresa_id),
                        OrdreTreball.estat.in_(["PENDENT", "ASSIGNADA", "PROGRAMADA", "EN_CURS", "EN_RUTA", "EN_OBRA"]),
                    )
                    altres = (await db.execute(stmt_altres)).scalars().first()
                    if not altres and v_nou.estat == "ASSIGNAT":
                        v_nou.estat = "OPERATIU"

    ordre.versio = (ordre.versio or 1) + 1
    await db.commit()

    f_resp = await build_feina_response(ordre, db, emp_uuid)
    await _sincronitzar_feina_disc(db, emp_uuid, f_resp, ordre.estat)
    return _aplicar_veto_rol_feina(f_resp, claims)


class AgendarFeinaRequest(BaseModel):
    hora_inici_prevista: datetime
    hora_fi_prevista: datetime
    version_id: int


class AgendarFeinaResponse(BaseModel):
    id: uuid.UUID
    versio: int = 1
    hora_inici_prevista: datetime
    hora_fi_prevista: datetime
    version_id: int
    estat: str


@router.put("/{feina_id}/agendar", response_model=AgendarFeinaResponse)
async def agendar_feina(
    feina_id: uuid.UUID,
    payload: AgendarFeinaRequest,
    request: Request,
    db: AsyncSession = Depends(get_db_with_tenant_context),
):
    """
    Planifica/reagenda una Ordre de Treball usant Optimistic Locking (version_id).
    Si un altre usuari ha modificat l'OT, es retorna HTTP 409 Conflict.
    """
    empresa_id = getattr(request.state, "empresa_id", None) or request.headers.get("X-Empresa-ID")
    if not empresa_id or empresa_id == "undefined":
        raise HTTPException(status_code=401, detail="No identificat")

    stmt = select(OrdreTreball).where(
        OrdreTreball.id == feina_id, OrdreTreball.empresa_id == uuid.UUID(empresa_id)
    )
    result = await db.execute(stmt)
    ordre = result.scalars().first()
    if not ordre:
        raise HTTPException(status_code=404, detail="Ordre de treball no trobada")

    if ordre.versio != payload.version_id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Conflicte de concurrència: la feina ha estat modificada per un altre usuari (versió actual: {ordre.versio}, versió enviada: {payload.version_id})",
        )

    ordre.hora_inici_prevista = payload.hora_inici_prevista
    ordre.hora_fi_prevista = payload.hora_fi_prevista
    ordre.versio = ordre.versio + 1

    await db.commit()

    return AgendarFeinaResponse(
        id=ordre.id,
        hora_inici_prevista=ordre.hora_inici_prevista,
        hora_fi_prevista=ordre.hora_fi_prevista,
        version_id=ordre.versio,
        estat=ordre.estat,
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
    request: Request, db: AsyncSession = Depends(get_db_with_tenant_context)
):
    empresa_id = getattr(request.state, "empresa_id", None) or request.headers.get("X-Empresa-ID")
    if not empresa_id or empresa_id == "undefined":
        raise HTTPException(status_code=401, detail="No identificat")
    emp_uuid = uuid.UUID(empresa_id)

    stmt = (
        select(OrdreTreball, Client, Usuari, Finca)
        .outerjoin(Client, OrdreTreball.client_id == Client.id)
        .outerjoin(Usuari, OrdreTreball.cap_de_colla_id == Usuari.id)
        .outerjoin(Finca, OrdreTreball.finca_id == Finca.id)
        .where(
            OrdreTreball.empresa_id == emp_uuid,
            OrdreTreball.estat.in_(["PENDENT", "EN_CURS", "BLOQUEJADA", "EN_OBRA", "EN_RUTA"]),
        )
        .order_by(OrdreTreball.created_at.desc())
    )

    rows = (await db.execute(stmt)).all()

    items = []
    for o, client, cap, finca in rows:
        lat = float(o.latitud) if o.latitud is not None else None
        lng = float(o.longitud) if o.longitud is not None else None
        if (lat is None or lng is None) and finca and finca.latitud is not None and finca.longitud is not None:
            lat = float(finca.latitud)
            lng = float(finca.longitud)
        if (lat is None or lng is None) and o.adreca:
            c_lat, c_lng = geocodificar_adreca(o.adreca)
            if c_lat is not None and c_lng is not None:
                lat, lng = c_lat, c_lng

        items.append(
            {
                "id": str(o.id),
                "codi": o.codi,
                "client": client.rao_social if client else None,
                "titol": o.titol,
                "cap_colla": f"{cap.nom} {cap.cognoms or ''}".strip() if cap else None,
                "estat": o.estat
                if o.estat in ["EN_OBRA", "EN_RUTA", "PENDENT", "INCIDENCIA"]
                else "PENDENT",
                "coords": [lat, lng] if (lat is not None and lng is not None) else None,
                "sector": finca.nom if finca else None,
                "pressio_bar": None,
                "codi_candat": finca.codi_candat_en_memoria if finca else None,
            }
        )

    return items


class DropAndGoRequest(BaseModel):
    versio: int
    cap_de_colla_id: Optional[uuid.UUID] = None
    data_programada: Optional[date] = None


@router.patch("/{id}/drop-and-go")
async def drop_and_go(
    id: uuid.UUID,
    payload: DropAndGoRequest,
    request: Request,
    db: AsyncSession = Depends(get_db_with_tenant_context),
):
    empresa_id = getattr(request.state, "empresa_id", None) or request.headers.get("X-Empresa-ID")
    if not empresa_id or empresa_id == "undefined":
        raise HTTPException(status_code=401, detail="No identificat")
    emp_uuid = uuid.UUID(empresa_id)

    stmt = select(OrdreTreball).where(
        OrdreTreball.id == id, OrdreTreball.empresa_id == emp_uuid
    )
    result = await db.execute(stmt)
    ordre = result.scalars().first()
    if not ordre:
        raise HTTPException(status_code=404, detail="Ordre de treball no trobada")

    if ordre.versio != payload.versio:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Conflicte de concurrència: la feina ha estat modificada per un altre usuari (versió actual: {ordre.versio}, versió enviada: {payload.versio})",
        )

    if payload.cap_de_colla_id is not None:
        if ordre.vehicle_id:
            op_db = (
                await db.execute(
                    select(Usuari).where(Usuari.id == payload.cap_de_colla_id, Usuari.empresa_id == emp_uuid)
                )
            ).scalars().first()
            veh_db = (
                await db.execute(
                    select(Vehicle).where(Vehicle.id == ordre.vehicle_id, Vehicle.empresa_id == emp_uuid)
                )
            ).scalars().first()
            if op_db and veh_db:
                validar_permis_conduir(veh_db, op_db)

        ordre.cap_de_colla_id = payload.cap_de_colla_id
        if ordre.estat == "PENDENT":
            ordre.estat = "ASSIGNADA"

        # Demote former cap in colla
        stmt_demote = (
            update(OrdreTreballOperari)
            .where(
                OrdreTreballOperari.ordre_treball_id == ordre.id,
                OrdreTreballOperari.empresa_id == emp_uuid,
            )
            .values(es_cap_de_colla=False)
        )
        await db.execute(stmt_demote)

        # Ensure new cap is present and marked as cap
        stmt_del_new = delete(OrdreTreballOperari).where(
            OrdreTreballOperari.ordre_treball_id == ordre.id,
            OrdreTreballOperari.empresa_id == emp_uuid,
            OrdreTreballOperari.operari_id == payload.cap_de_colla_id,
        )
        await db.execute(stmt_del_new)
        db.add(
            OrdreTreballOperari(
                empresa_id=emp_uuid,
                ordre_treball_id=ordre.id,
                operari_id=payload.cap_de_colla_id,
                es_cap_de_colla=True,
            )
        )
    if payload.data_programada is not None:
        ordre.data_planificacio = payload.data_programada

    ordre.versio = ordre.versio + 1

    await db.commit()

    f_resp = await build_feina_response(ordre, db, emp_uuid)
    await _sincronitzar_feina_disc(db, emp_uuid, f_resp, ordre.estat)

    return {
        "status": "ok",
        "versio": ordre.versio,
        "cap_de_colla_id": ordre.cap_de_colla_id,
        "data_planificacio": ordre.data_planificacio,
        "estat": ordre.estat,
    }


# ── T024: Signatura Digital de Conformitat de Tancament d'Obra ─────────────
class TancarObraRequest(BaseModel):
    signatura_base64: str = Field(..., description="Signatura digital del client en base64")
    conformitat_client: bool = Field(..., description="Conformitat expressa del client")
    observacions: Optional[str] = None
    nom_receptor: Optional[str] = Field(None, max_length=150)
    dni_receptor: Optional[str] = Field(None, max_length=30)


@router.put("/{id}/tancar-obra")
async def tancar_obra(
    id: uuid.UUID,
    payload: TancarObraRequest,
    request: Request,
    db: AsyncSession = Depends(get_db_with_tenant_context),
):
    """T024: Tanca una ordre de treball amb signatura digital del client (Spec 03 Bloc 5).

    Desa la imatge de signatura al disc sobirà i persisteix ruta, receptor i observacions a BD.
    Requereix conformitat_client=True per procedir.
    """
    empresa_id = getattr(request.state, "empresa_id", None) or request.headers.get("X-Empresa-ID")
    if not empresa_id or empresa_id == "undefined":
        raise HTTPException(status_code=401, detail="No identificat")
    emp_uuid = uuid.UUID(empresa_id)
    if not payload.conformitat_client:
        raise HTTPException(
            status_code=422,
            detail="La conformitat del client és obligatòria per tancar l'obra",
        )
    stmt = select(OrdreTreball).where(
        OrdreTreball.id == id, OrdreTreball.empresa_id == emp_uuid
    )
    result = await db.execute(stmt)
    ordre = result.scalars().first()
    if not ordre:
        raise HTTPException(status_code=404, detail="Ordre de treball no trobada")
    if ordre.estat == "TANCADA":
        raise HTTPException(status_code=409, detail="L'obra ja estava tancada")

    sig_path = await desar_signatura_client_ot(
        db=db,
        empresa_id=emp_uuid,
        ordre_treball_id=ordre.id,
        signatura_base64=payload.signatura_base64,
        exigir_magic_bytes=False,
    )

    now_utc = datetime.now(timezone.utc)
    ordre.estat = "TANCADA"
    if ordre.data_finalitzacio_camp is None:
        ordre.data_finalitzacio_camp = now_utc.date()
    ordre.signatura_client_path = sig_path
    ordre.data_signatura = now_utc
    if payload.nom_receptor is not None:
        ordre.nom_receptor = payload.nom_receptor.strip() or None
    if payload.dni_receptor is not None:
        ordre.dni_receptor = payload.dni_receptor.strip().upper() or None
    if payload.observacions is not None:
        ordre.observacions_tancament = payload.observacions.strip() or None

    # Alliberar el vehicle si no té altres ordres actives
    if ordre.vehicle_id:
        stmt_altres = select(OrdreTreball).where(
            OrdreTreball.vehicle_id == ordre.vehicle_id,
            OrdreTreball.id != ordre.id,
            OrdreTreball.empresa_id == emp_uuid,
            OrdreTreball.estat.in_(["PENDENT", "ASSIGNADA", "PROGRAMADA", "EN_CURS", "EN_RUTA", "EN_OBRA"]),
        )
        altres = (await db.execute(stmt_altres)).scalars().first()
        if not altres:
            stmt_v = select(Vehicle).where(
                Vehicle.id == ordre.vehicle_id,
                Vehicle.empresa_id == emp_uuid,
            )
            v_obj = (await db.execute(stmt_v)).scalars().first()
            if v_obj and v_obj.estat == "ASSIGNAT":
                v_obj.estat = "OPERATIU"

    ordre.versio = (ordre.versio or 1) + 1

    await db.commit()

    f_resp = await build_feina_response(ordre, db, emp_uuid)
    await _sincronitzar_feina_disc(db, emp_uuid, f_resp, ordre.estat)

    return {
        "status": "TANCADA",
        "ordre_id": str(ordre.id),
        "versio": ordre.versio,
        "signatura_registrada": True,
        "signatura_client_path": sig_path,
        "nom_receptor": ordre.nom_receptor,
        "dni_receptor": ordre.dni_receptor,
        "observacions_tancament": ordre.observacions_tancament,
    }


# ── T027-T028: Reconciliació Post-Obra Real (Zero Mock Data + Barrera Econòmica) ──
@router.post("/{id}/reconciliacio-post-obra")
async def reconciliacio_post_obra(
    id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_db_with_tenant_context),
    claims: Dict[str, Any] = Depends(get_current_user_claims),
):
    """T027-T028: Reconciliació post-obra real dels 4 pilars (materials, hores, km i tiquets).

    Llegeix 100% dades reals de PostgreSQL i Disc Sobirà via ReconciliacioOTService.
    Respecta la Barrera Econòmica: ENGINYER rep dades tècniques i comercials del client,
    però mai costos interns (PMP, cost mà d'obra real) ni marges empresarials.
    """
    empresa_id = getattr(request.state, "empresa_id", None) or request.headers.get("X-Empresa-ID")
    if not empresa_id or empresa_id == "undefined":
        raise HTTPException(status_code=401, detail="No identificat")
    emp_uuid = uuid.UUID(empresa_id)
    rol = str((claims or {}).get("rol") or "").upper()

    conc = await ReconciliacioOTService.obtenir_conciliacio_completa(
        db=db,
        empresa_id=emp_uuid,
        ordre_treball_id=id,
        rol_usuari=rol,
    )
    resum_com = conc["resum_comercial"]
    resum_int = conc["resum_intern"]
    bloqueig = resum_int["bloqueig_marge_critic"]

    return {
        "ordre_id": conc["ordre_treball_id"],
        "previst": {
            "import_pressupostat": resum_com["import_pressupostat"],
            "cost_materials": resum_int["cost_materials_previst_pmp"],
            "hores": resum_com["hores_previstes"],
        },
        "real": {
            "cost_materials": resum_int["cost_materials_pmp"],
            "cost_ma_obra": resum_int["cost_ma_obra_real"],
            "hores": resum_com["hores_reals"],
            "km": resum_com["km_imputats"],
            "tiquets_despesa": resum_com["total_tiquets_camp"],
            "cost_total": resum_int["cost_total_real"],
            "valor_materials_pvp": resum_com["valor_materials_pvp"],
            "valor_ma_obra_pvp": resum_com["valor_ma_obra_pvp"],
            "total_valorat_pvp": resum_com["total_valorat_pvp"],
        },
        "marge_real": resum_int["marge_real_eur"],
        "marge_percentatge": resum_int["marge_real_percentatge"],
        "bloqueig_facturacio_directa": bloqueig,
        "alerta": "MERMA_OPERATIVA_REVISAR_AMB_BOSS" if bloqueig else None,
        "conciliacio": conc,
    }


# ── FASE 5: Fulla 360° Conciliada, Evidències, Validació Tècnica i Pre-facturació (3 Rols) ──


class AjustPickingValidacioItem(BaseModel):
    linia_id: uuid.UUID
    quantitat_carregada_pick_in: Optional[float] = Field(None, ge=0)
    quantitat_retornada_pick_out: Optional[float] = Field(None, ge=0)
    quantitat_mermada: Optional[float] = Field(None, ge=0)


class ValidarConciliacioRequest(BaseModel):
    hores_imputades_facturables: Optional[float] = Field(None, ge=0)
    ajustos_picking: Optional[List[AjustPickingValidacioItem]] = None
    checklist_conciliacio: Dict[str, bool] = Field(default_factory=dict)
    notes_validacio_tecnica: Optional[str] = Field(None, max_length=3000)


class PassarAPrefacturacioRequest(BaseModel):
    data_emissio: Optional[date] = None
    data_venciment: Optional[date] = None
    incloure_tiquets_camp: bool = True


@router.get("/{feina_id}/conciliacio")
async def obtenir_conciliacio_fulla_360(
    feina_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_db_with_tenant_context),
    claims: Dict[str, Any] = Depends(get_current_user_claims),
) -> Dict[str, Any]:
    """Dossier complet de conciliació PWA per a la Fulla 360° (tots 3 rols, costos interns ocults a ENGINYER)."""
    empresa_id = getattr(request.state, "empresa_id", None) or request.headers.get("X-Empresa-ID")
    if not empresa_id or empresa_id == "undefined":
        raise HTTPException(status_code=401, detail="No identificat")
    emp_uuid = uuid.UUID(str(empresa_id))
    rol = str((claims or {}).get("rol") or "").upper()

    return await ReconciliacioOTService.obtenir_conciliacio_completa(
        db=db,
        empresa_id=emp_uuid,
        ordre_treball_id=feina_id,
        rol_usuari=rol,
    )


@router.get("/{feina_id}/evidencies/{tipus}")
async def obtenir_evidencia_fulla_360(
    feina_id: uuid.UUID,
    tipus: str,
    request: Request,
    db: AsyncSession = Depends(get_db_with_tenant_context),
) -> Response:
    """Serveix les evidències fotogràfiques i la signatura digital de l'OT des del disc sobirà amb RLS."""
    empresa_id = getattr(request.state, "empresa_id", None) or request.headers.get("X-Empresa-ID")
    if not empresa_id or empresa_id == "undefined":
        raise HTTPException(status_code=401, detail="No identificat")
    emp_uuid = uuid.UUID(str(empresa_id))

    ordre = (
        await db.execute(
            select(OrdreTreball).where(
                OrdreTreball.id == feina_id,
                OrdreTreball.empresa_id == emp_uuid,
            )
        )
    ).scalar_one_or_none()
    if not ordre:
        raise HTTPException(status_code=404, detail="Ordre de treball no trobada")

    tipus_norm = tipus.strip().lower()
    raw_bytes: Optional[bytes] = None
    default_mime = "image/webp"

    if tipus_norm in ("foto_inicial", "foto_intermedia", "foto_final"):
        clau_foto = tipus_norm.replace("foto_", "")
        fitxer_rel = f"06_ordres_treball/actives_buffer/ot_{feina_id}_foto_{clau_foto}.webp"
        try:
            raw_bytes, _ = await SovereignStorageGateway.obtenir_bytes_fitxer(
                db=db,
                empresa_id=emp_uuid,
                fitxer_path=fitxer_rel,
            )
        except HTTPException:
            raw_bytes = None
    elif tipus_norm == "signatura":
        default_mime = "image/png"
        if ordre.signatura_client_path:
            try:
                raw_bytes, _ = await SovereignStorageGateway.obtenir_bytes_fitxer(
                    db=db,
                    empresa_id=emp_uuid,
                    fitxer_path=ordre.signatura_client_path,
                )
            except HTTPException:
                raw_bytes = None
        if raw_bytes is None:
            for ext in ("png", "webp", "jpg"):
                try:
                    raw_bytes, _ = await SovereignStorageGateway.obtenir_bytes_fitxer(
                        db=db,
                        empresa_id=emp_uuid,
                        fitxer_path=f"06_ordres_treball/historic_tancades/ot_{feina_id}_signatura_client.{ext}",
                    )
                    if raw_bytes:
                        break
                except HTTPException:
                    continue
    elif tipus_norm == "foto_geovalla":
        if ordre.foto_evidencia_desviacio:
            try:
                raw_bytes, _ = await SovereignStorageGateway.obtenir_bytes_fitxer(
                    db=db,
                    empresa_id=emp_uuid,
                    fitxer_path=ordre.foto_evidencia_desviacio,
                )
            except HTTPException:
                raw_bytes = None
    else:
        raise HTTPException(
            status_code=400,
            detail="Tipus d'evidència no vàlid. Valors: foto_inicial, foto_intermedia, foto_final, signatura, foto_geovalla.",
        )

    if not raw_bytes:
        raise HTTPException(status_code=404, detail=f"Evidència '{tipus_norm}' no trobada al disc sobirà.")

    kind = filetype.guess(raw_bytes)
    media_type = str(kind.mime) if kind and kind.mime else default_mime
    return Response(
        content=raw_bytes,
        media_type=media_type,
        headers={"Cache-Control": "private, max-age=60"},
    )


@router.put("/{feina_id}/validar-conciliacio")
async def validar_conciliacio_ot(
    feina_id: uuid.UUID,
    payload: ValidarConciliacioRequest,
    request: Request,
    db: AsyncSession = Depends(get_db_with_tenant_context),
    claims: Dict[str, Any] = Depends(get_current_user_claims),
) -> Dict[str, Any]:
    """Concilia i valida tècnicament una OT conclosa (ajustos hores/picking + checklist) -> VALIDADA_PER_FACTURAR."""
    empresa_id = getattr(request.state, "empresa_id", None) or request.headers.get("X-Empresa-ID")
    if not empresa_id or empresa_id == "undefined":
        raise HTTPException(status_code=401, detail="No identificat")
    emp_uuid = uuid.UUID(str(empresa_id))
    rol = str((claims or {}).get("rol") or "").upper()
    usuari_sub = (claims or {}).get("sub")
    usuari_uuid = uuid.UUID(str(usuari_sub)) if usuari_sub else None

    ordre = (
        await db.execute(
            select(OrdreTreball).where(
                OrdreTreball.id == feina_id,
                OrdreTreball.empresa_id == emp_uuid,
            )
        )
    ).scalar_one_or_none()
    if not ordre:
        raise HTTPException(status_code=404, detail="Ordre de treball no trobada")

    estat_up = str(ordre.estat or "").upper()
    if ordre.factura_id is not None or estat_up in ("PREFACTURADA", "FACTURADA"):
        raise HTTPException(
            status_code=400,
            detail="L'ordre de treball ja està pre-facturada o facturada i no es pot revalidar.",
        )

    if estat_up not in ESTATS_OT_CONCLOSES:
        raise HTTPException(
            status_code=400,
            detail="La feina no ha finalitzat. Cal que l'operari conclogui la tasca abans de validar la conciliació.",
        )

    tram_obert = (
        await db.execute(
            select(OrdreTreballTramTemps.id).where(
                OrdreTreballTramTemps.empresa_id == emp_uuid,
                OrdreTreballTramTemps.ordre_treball_id == ordre.id,
                OrdreTreballTramTemps.hora_fi.is_(None),
            )
        )
    ).scalar_one_or_none()
    if tram_obert is not None:
        raise HTTPException(
            status_code=400,
            detail="Hi ha un tram de temps obert al cronòmetre de camp. Tanca'l abans de validar la conciliació.",
        )

    # 1. Aplicar ajustos tècnics de picking/merma amb regularització atòmica de magatzem (mateixa transacció)
    if payload.ajustos_picking:
        for ajust in payload.ajustos_picking:
            await actualitzar_linia_picking_amb_estoc(
                db=db,
                empresa_id=emp_uuid,
                linia_id=ajust.linia_id,
                quantitat_carregada_pick_in=ajust.quantitat_carregada_pick_in,
                quantitat_retornada_pick_out=ajust.quantitat_retornada_pick_out,
                quantitat_mermada=ajust.quantitat_mermada,
                usuari_id=usuari_uuid,
                auto_commit=False,
            )

    # 2. Aplicar ajust d'hores facturables si s'ha especificat
    if payload.hores_imputades_facturables is not None:
        hores_noves = round(float(payload.hores_imputades_facturables), 2)
        ordre.hores_imputades_facturables = hores_noves
        trams_finals = list(
            (
                await db.execute(
                    select(OrdreTreballTramTemps).where(
                        OrdreTreballTramTemps.empresa_id == emp_uuid,
                        OrdreTreballTramTemps.ordre_treball_id == ordre.id,
                    )
                )
            )
            .scalars()
            .all()
        )
        ordre.cost_ma_obra_real = await calcular_cost_ma_obra_real(
            db, emp_uuid, ordre, trams_finals, hores_noves
        )

    # 3. Persistir checklist, notes i segell de validació tècnica
    now_utc = datetime.now(timezone.utc)
    ordre.checklist_conciliacio = dict(payload.checklist_conciliacio or {})
    if payload.notes_validacio_tecnica is not None:
        ordre.notes_validacio_tecnica = payload.notes_validacio_tecnica.strip() or None
    ordre.validada_per_id = usuari_uuid
    ordre.data_validacio = now_utc
    ordre.estat = "VALIDADA_PER_FACTURAR"
    ordre.versio = (ordre.versio or 1) + 1

    await db.commit()
    await set_tenant_context(
        db,
        str(emp_uuid),
        bool(getattr(request.state, "is_superadmin", False)),
        role=rol,
    )

    return await ReconciliacioOTService.obtenir_conciliacio_completa(
        db=db,
        empresa_id=emp_uuid,
        ordre_treball_id=feina_id,
        rol_usuari=rol,
    )


@router.post("/{feina_id}/passar-a-prefacturacio", status_code=status.HTTP_201_CREATED)
async def passar_ot_a_prefacturacio(
    feina_id: uuid.UUID,
    request: Request,
    payload: Optional[PassarAPrefacturacioRequest] = None,
    db: AsyncSession = Depends(get_db_with_tenant_context),
    claims: Dict[str, Any] = Depends(get_current_user_claims),
) -> Dict[str, Any]:
    """Passa una OT conclosa i validada (VALIDADA_PER_FACTURAR) a Pre-factura Sèrie PRE des de la Fulla 360°.

    Accessible als 3 rols: ENGINYER, SECRETARIA i BOSS.
    Utilitza la funció SQL SECURITY DEFINER `crear_prefactura_ot_autoritzada` per preservar intacta
    la barrera RLS `economics_boss_only` sobre consultes globals de comptabilitat.
    """
    empresa_id = getattr(request.state, "empresa_id", None) or request.headers.get("X-Empresa-ID")
    if not empresa_id or empresa_id == "undefined":
        raise HTTPException(status_code=401, detail="No identificat")
    emp_uuid = uuid.UUID(str(empresa_id))
    usuari_sub = (claims or {}).get("sub")
    usuari_uuid = uuid.UUID(str(usuari_sub)) if usuari_sub else None

    ordre = (
        await db.execute(
            select(OrdreTreball).where(
                OrdreTreball.id == feina_id,
                OrdreTreball.empresa_id == emp_uuid,
            )
        )
    ).scalar_one_or_none()
    if not ordre:
        raise HTTPException(status_code=404, detail="Ordre de treball no trobada")

    if ordre.factura_id is not None or str(ordre.estat or "").upper() in ("PREFACTURADA", "FACTURADA"):
        raise HTTPException(
            status_code=400, detail="L'ordre de treball ja es troba pre-facturada o facturada."
        )

    estat_up = str(ordre.estat or "").upper()
    if estat_up not in ESTATS_OT_CONCLOSES:
        raise HTTPException(
            status_code=400,
            detail="La feina no ha finalitzat. No es pot passar a pre-facturació fins que estigui conclosa i validada.",
        )

    if estat_up != "VALIDADA_PER_FACTURAR" or ordre.validada_per_id is None:
        raise HTTPException(
            status_code=400,
            detail="Cal conciliar i validar la Fulla 360° abans de passar l'ordre de treball a pre-facturació.",
        )

    tram_obert = (
        await db.execute(
            select(OrdreTreballTramTemps.id).where(
                OrdreTreballTramTemps.empresa_id == emp_uuid,
                OrdreTreballTramTemps.ordre_treball_id == ordre.id,
                OrdreTreballTramTemps.hora_fi.is_(None),
            )
        )
    ).scalar_one_or_none()
    if tram_obert is not None:
        raise HTTPException(
            status_code=400,
            detail="Hi ha un tram de temps obert al cronòmetre de camp. Tanca'l abans de pre-facturar.",
        )

    if not ordre.client_id:
        raise HTTPException(status_code=400, detail="L'OT no té cap client associat.")

    # Construir les línies comercials reals de la pre-factura a partir de les dades conciliades
    linies_json: List[Dict[str, Any]] = []

    hores = Decimal(str(ordre.hores_imputades_facturables or 0))
    preu_hora_real = Decimal(str(await resoldre_preu_hora_control_panel(db, emp_uuid, ordre)))
    if hores > 0:
        linies_json.append(
            {
                "concepte": f"Mà d'obra tècnica OT {ordre.codi} ({ordre.titol})"[:200],
                "quantitat": float(hores),
                "preu_venda_unitari": float(preu_hora_real),
                "tipus_iva": 21.0,
                "article_id": None,
            }
        )

    # Materials reals consumits (Nau + Furgoneta) des de linies_picking
    pk_rows = (
        await db.execute(
            select(LiniaPicking, Article)
            .join(FullaPicking, LiniaPicking.picking_id == FullaPicking.id)
            .join(Article, LiniaPicking.article_id == Article.id)
            .where(
                FullaPicking.ordre_treball_id == ordre.id,
                FullaPicking.empresa_id == emp_uuid,
                LiniaPicking.empresa_id == emp_uuid,
            )
            .order_by(LiniaPicking.created_at.asc())
        )
    ).all()

    afegit_material_picking = False
    for lp, art in pk_rows:
        consum = max(
            0.0,
            round(
                float(lp.quantitat_carregada_pick_in or 0.0)
                - float(lp.quantitat_retornada_pick_out or 0.0),
                3,
            ),
        )
        if consum <= 0:
            continue
        afegit_material_picking = True
        origen_lbl = (
            " [Furgoneta]"
            if str(getattr(lp, "origen_estoc", "NAU") or "NAU").upper() == "FURGONETA"
            else ""
        )
        linies_json.append(
            {
                "concepte": f"Material {art.nom}{origen_lbl} (OT {ordre.codi})"[:200],
                "quantitat": consum,
                "preu_venda_unitari": float(art.preu_venda or 0.0),
                "tipus_iva": 21.0,
                "article_id": str(art.id),
            }
        )

    pvp_mat_ot = Decimal(str(ordre.pvp_materials_aplicat or 0))
    if not afegit_material_picking and pvp_mat_ot > 0:
        linies_json.append(
            {
                "concepte": f"Subministrament i materials OT {ordre.codi}"[:200],
                "quantitat": 1.0,
                "preu_venda_unitari": float(pvp_mat_ot),
                "tipus_iva": 21.0,
                "article_id": None,
            }
        )

    # Tiquets de despesa vinculats a l'OT (excloent rebutjats)
    incloure_tiq = True if payload is None else bool(payload.incloure_tiquets_camp)
    if incloure_tiq:
        tiq_rows = (
            await db.execute(
                select(TiquetDespesa).where(
                    TiquetDespesa.empresa_id == emp_uuid,
                    TiquetDespesa.ordre_treball_id == ordre.id,
                    TiquetDespesa.estat_aprovacio != "REBUTJAT",
                )
            )
        ).scalars().all()
        for tiq in tiq_rows:
            imp_tiq = float(tiq.base_imposable or tiq.import_total or 0.0)
            if imp_tiq > 0:
                linies_json.append(
                    {
                        "concepte": f"Despesa camp ({tiq.categoria}) OT {ordre.codi}"[:200],
                        "quantitat": 1.0,
                        "preu_venda_unitari": round(imp_tiq, 2),
                        "tipus_iva": 21.0,
                        "article_id": None,
                    }
                )

    if not linies_json:
        pressup = float(ordre.import_pressupostat_net or ordre.import_pressupostat or 0.0)
        linies_json.append(
            {
                "concepte": f"Treballs tècnics executats OT {ordre.codi} ({ordre.titol})"[:200],
                "quantitat": 1.0,
                "preu_venda_unitari": round(pressup, 2),
                "tipus_iva": 21.0,
                "article_id": None,
            }
        )

    data_em = payload.data_emissio if payload and payload.data_emissio else date.today()
    data_venc = payload.data_venciment if payload and payload.data_venciment else data_em

    res_fn = await db.execute(
        text(
            """
            SELECT public.crear_prefactura_ot_autoritzada(
                CAST(:emp_id AS uuid),
                CAST(:usuari_id AS uuid),
                CAST(:ot_id AS uuid),
                CAST(:data_em AS date),
                CAST(:data_venc AS date),
                CAST(:linies AS jsonb)
            )
            """
        ),
        {
            "emp_id": str(emp_uuid),
            "usuari_id": str(usuari_uuid) if usuari_uuid else None,
            "ot_id": str(ordre.id),
            "data_em": data_em,
            "data_venc": data_venc,
            "linies": json.dumps(linies_json),
        },
    )
    pref_json = res_fn.scalar_one_or_none()
    if not isinstance(pref_json, dict):
        raise HTTPException(
            status_code=500, detail="No s'ha pogut generar la pre-factura des de la Fulla 360°."
        )

    await db.commit()
    return pref_json
