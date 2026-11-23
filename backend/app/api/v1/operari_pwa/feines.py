import math
import sys
import uuid
from datetime import date, datetime, timezone
from typing import Any, List, Optional

import filetype  # type: ignore[import-untyped]
from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db_with_tenant_context
from app.core.security import get_current_user_id, require_roles
from app.models.models import (
    Article,
    Client,
    EinaCustodia,
    FullaPicking,
    LiniaPicking,
    OrdreTreball,
    OrdreTreballOperari,
    OrdreTreballTramTemps,
    Vehicle,
)
from app.services.barema_service import (
    calcular_cost_ma_obra_real,
    resoldre_preu_hora_control_panel,
)
from app.services.reconciliacio_ot_service import desar_signatura_client_ot

MAX_FOTO_QA_BYTES = 10 * 1024 * 1024  # 10 MB (AGENTS.md §3.4)
ALLOWED_FOTO_QA_MIMES = {
    "image/webp": "webp",
    "image/jpeg": "jpg",
    "image/png": "png",
}

router = APIRouter(
    prefix="/operari",
    tags=["Operari Feines"],
    dependencies=[Depends(require_roles(["OPERARI", "CAPATAZ", "CAP_DE_COLLA"]))],
)


class ClientResponse(BaseModel):
    id: uuid.UUID
    rao_social: str
    model_config = ConfigDict(from_attributes=True)


class VehicleResponse(BaseModel):
    id: uuid.UUID
    matricula: str
    model: str
    model_config = ConfigDict(from_attributes=True)


class EinaCustodiaResponse(BaseModel):
    id: uuid.UUID
    nom: str
    model: Optional[str] = None
    numero_serie: str
    estat: str
    model_config = ConfigDict(from_attributes=True)


class LiniaPickingDetailResponse(BaseModel):
    id: uuid.UUID
    article_id: uuid.UUID
    article_nom: str
    quantitat_prevista: float
    quantitat_carregada_pick_in: float
    model_config = ConfigDict(from_attributes=True)


class TramTempsResponse(BaseModel):
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


class FeinaOperariDetailResponse(BaseModel):
    id: uuid.UUID
    codi: str
    titol: str
    descripcio: Optional[str] = None
    estat: str
    adreca: Optional[str] = None
    data_planificacio: Optional[date] = None
    hora_inici_real: Optional[datetime] = None
    hora_fi_real: Optional[datetime] = None
    gps_inici_lat: Optional[float] = None
    gps_inici_lng: Optional[float] = None
    gps_fi_lat: Optional[float] = None
    gps_fi_lng: Optional[float] = None
    hores_imputades_facturables: Optional[float] = None
    preu_venda_hora_aplicat: Optional[float] = None
    desviacio_geovalla: Optional[bool] = False
    justificacio_geovalla: Optional[str] = None
    foto_evidencia_desviacio: Optional[str] = None
    te_tram_obert: bool = False
    tram_actiu_inici: Optional[datetime] = None
    temps_acumulat_segons: int = 0
    trams_temps: List[TramTempsResponse] = []
    client: Optional[ClientResponse] = None
    vehicle: Optional[VehicleResponse] = None
    picking_id: Optional[uuid.UUID] = None
    planol_id: Optional[uuid.UUID] = None
    planol_titol: Optional[str] = None
    planol_codi: Optional[str] = None
    planol_tipus_fitxer: Optional[str] = None
    linies_picking: List[LiniaPickingDetailResponse] = []
    eines_assignades: List[EinaCustodiaResponse] = []
    model_config = ConfigDict(from_attributes=True)


class FeinaOperariResponse(BaseModel):
    id: uuid.UUID
    codi: str
    titol: str
    estat: str
    estat_local: Optional[str] = None
    adreca: Optional[str] = None
    data_planificacio: Optional[date] = None
    data_programada: Optional[str] = None
    client_nom: Optional[str] = None
    desviacio_geovalla: Optional[bool] = False
    client: Optional[ClientResponse] = None
    model_config = ConfigDict(from_attributes=True)


def _get_usuari_id(request: Request) -> str:
    return get_current_user_id(request)


@router.get("/feines", response_model=List[FeinaOperariResponse])
async def llistar_les_meves_feines(
    request: Request, db: AsyncSession = Depends(get_db_with_tenant_context)
):
    empresa_id = request.state.empresa_id
    if not empresa_id or empresa_id == "undefined":
        raise HTTPException(status_code=401)
    usuari_id = _get_usuari_id(request)

    stmt = (
        select(OrdreTreball, Client)
        .outerjoin(Client, OrdreTreball.client_id == Client.id)
        .where(
            OrdreTreball.empresa_id == uuid.UUID(empresa_id),
            or_(
                OrdreTreball.cap_de_colla_id == uuid.UUID(usuari_id),
                OrdreTreball.id.in_(
                    select(OrdreTreballOperari.ordre_treball_id).where(
                        OrdreTreballOperari.operari_id == uuid.UUID(usuari_id),
                        OrdreTreballOperari.empresa_id == uuid.UUID(empresa_id),
                    )
                ),
            ),
            OrdreTreball.estat.in_(["PENDENT", "ASSIGNADA", "PROGRAMADA", "EN_CURS", "EN_RUTA", "EN_OBRA", "PAUSADA", "FINALITZADA"]),
        )
        .order_by(OrdreTreball.data_planificacio.asc())
    )

    result = await db.execute(stmt)
    feines = []
    for feina, client in result.all():
        feina_resp = FeinaOperariResponse.model_validate(feina)
        feina_resp.estat_local = feina.estat
        feina_resp.data_programada = str(feina.data_planificacio) if feina.data_planificacio else None
        if client:
            feina_resp.client = ClientResponse.model_validate(client)
            feina_resp.client_nom = client.rao_social
        feines.append(feina_resp)

    return feines


@router.get("/feines/{feina_id}")
async def obtenir_detall_feina(
    feina_id: uuid.UUID, request: Request, db: AsyncSession = Depends(get_db_with_tenant_context)
):
    try:
        empresa_id = getattr(request.state, "empresa_id", None)
        if not empresa_id or empresa_id == "undefined":
            raise HTTPException(status_code=401, detail="No empresa_id in state")

        usuari_id = _get_usuari_id(request)

        stmt = (
            select(OrdreTreball, Client, Vehicle, FullaPicking)
            .outerjoin(Client, OrdreTreball.client_id == Client.id)
            .outerjoin(Vehicle, OrdreTreball.vehicle_id == Vehicle.id)
            .outerjoin(FullaPicking, OrdreTreball.id == FullaPicking.ordre_treball_id)
            .where(
                OrdreTreball.id == feina_id,
                OrdreTreball.empresa_id == uuid.UUID(empresa_id),
                or_(
                    OrdreTreball.cap_de_colla_id == uuid.UUID(usuari_id),
                    OrdreTreball.id.in_(
                        select(OrdreTreballOperari.ordre_treball_id).where(
                            OrdreTreballOperari.operari_id == uuid.UUID(usuari_id),
                            OrdreTreballOperari.empresa_id == uuid.UUID(empresa_id),
                        )
                    ),
                ),
            )
        )
        result = await db.execute(stmt)
        row = result.first()

        if not row:
            raise HTTPException(status_code=404, detail="Feina no trobada o no assignada")

        feina, client, vehicle, picking = row

        resp = FeinaOperariDetailResponse.model_validate(feina)
        if client:
            resp.client = ClientResponse.model_validate(client)
        if vehicle:
            resp.vehicle = VehicleResponse.model_validate(vehicle)

        if picking:
            resp.picking_id = picking.id
            stmt_linies = (
                select(LiniaPicking, Article)
                .join(Article, LiniaPicking.article_id == Article.id)
                .where(LiniaPicking.picking_id == picking.id)
            )
            result_linies = await db.execute(stmt_linies)

            linies = []
            for lin, a in result_linies.all():
                linies.append(
                    LiniaPickingDetailResponse(
                        id=lin.id,
                        article_id=lin.article_id,
                        article_nom=a.nom,
                        quantitat_prevista=lin.quantitat_prevista,
                        quantitat_carregada_pick_in=lin.quantitat_carregada_pick_in,
                    )
                )
            resp.linies_picking = linies

        # Eines en custòdia assignades a l'operari
        stmt_eines = select(EinaCustodia).where(
            EinaCustodia.empresa_id == uuid.UUID(empresa_id),
            EinaCustodia.custodiat_per_operari_id == uuid.UUID(usuari_id),
        )
        result_eines = await db.execute(stmt_eines)
        resp.eines_assignades = [
            EinaCustodiaResponse.model_validate(e) for e in result_eines.scalars().all()
        ]

        # Plànol tècnic assignat a la feina
        if feina.planol_id:
            from app.models.models import PlanolBase
            p_stmt = select(PlanolBase).where(
                PlanolBase.id == feina.planol_id,
                PlanolBase.empresa_id == uuid.UUID(empresa_id),
            )
            p_obj = (await db.execute(p_stmt)).scalars().first()
            if p_obj:
                resp.planol_id = p_obj.id
                resp.planol_titol = p_obj.titol
                resp.planol_codi = p_obj.codi_referencia
                resp.planol_tipus_fitxer = p_obj.tipus_fitxer

        # Trams de temps treballat multi-interval
        trams_resp, _, tram_actiu_inici, temps_acumulat_segons, te_tram_obert = (
            await _carregar_estat_trams(db, uuid.UUID(empresa_id), feina)
        )
        resp.trams_temps = trams_resp
        resp.te_tram_obert = te_tram_obert
        resp.tram_actiu_inici = tram_actiu_inici
        resp.temps_acumulat_segons = temps_acumulat_segons
        resp.preu_venda_hora_aplicat = None

        return resp
    except HTTPException:
        raise
    except Exception as e:
        sys.stderr.write(f"ERROR: {str(e)}\n")
        raise HTTPException(status_code=500, detail=str(e))


def calcular_distancia_metres(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6371000.0  # radi de la Terra en metres
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)
    a = (
        math.sin(delta_phi / 2.0) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2.0) ** 2
    )
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return R * c


class IniciarTrajecteResponse(BaseModel):
    feina_id: uuid.UUID
    estat_vehicle: str
    eta_minuts: int
    missatge: str


@router.put("/feines/{feina_id}/iniciar-trajecte", response_model=IniciarTrajecteResponse)
async def iniciar_trajecte(
    feina_id: uuid.UUID, request: Request, db: AsyncSession = Depends(get_db_with_tenant_context)
):
    """Commuta el vehicle a Blau (En trànsit) i activa buffer de 25 min (Spec 013 RF-11)."""
    empresa_id = request.state.empresa_id
    if not empresa_id or empresa_id == "undefined":
        raise HTTPException(status_code=401)

    ot_res = await db.execute(
        select(OrdreTreball).where(
            OrdreTreball.id == feina_id, OrdreTreball.empresa_id == uuid.UUID(empresa_id)
        )
    )
    feina = ot_res.scalars().first()
    if not feina:
        raise HTTPException(status_code=404, detail="Feina no trobada")

    if feina.vehicle_id:
        veh_res = await db.execute(select(Vehicle).where(Vehicle.id == feina.vehicle_id))
        veh = veh_res.scalars().first()
        if veh:
            veh.estat = "EN_TRANSIT"
            await db.commit()

    return IniciarTrajecteResponse(
        feina_id=feina.id,
        estat_vehicle="EN_TRANSIT",
        eta_minuts=25,
        missatge="Vehicle en trànsit, ETA de 25 minuts activat",
    )


class ComencarFeinaRequest(BaseModel):
    lat: Optional[float] = None
    lng: Optional[float] = None
    lon: Optional[float] = None
    desviacio_justificada: bool = False
    justificacio_gps: Optional[str] = None
    foto_evidencia_desviacio: Optional[str] = None

    def model_post_init(self, __context: Any) -> None:
        if self.lng is None and self.lon is not None:
            self.lng = self.lon
        if self.justificacio_gps and not self.desviacio_justificada:
            self.desviacio_justificada = True


def _validar_geovalla_feina(feina: OrdreTreball, payload: ComencarFeinaRequest) -> Optional[float]:
    """Valida que el punt GPS es trobi dins del radi de 50m de l'obra (o justificat)."""
    if payload.lat is None or payload.lng is None:
        return None

    dest_lat: Optional[float] = None
    dest_lng: Optional[float] = None

    if feina.latitud is not None and feina.longitud is not None:
        dest_lat = float(feina.latitud)
        dest_lng = float(feina.longitud)
    elif feina.adreca and "," in feina.adreca:
        try:
            parts = [float(p.strip()) for p in feina.adreca.split(",")]
            if len(parts) >= 2:
                dest_lat, dest_lng = parts[0], parts[1]
        except (ValueError, TypeError):
            return None

    if dest_lat is None or dest_lng is None:
        return None

    distancia = calcular_distancia_metres(payload.lat, payload.lng, dest_lat, dest_lng)
    if distancia > 50.0 and not payload.desviacio_justificada:
        raise HTTPException(
            status_code=400,
            detail=f"Geovalla d'obra superada (distància: {distancia:.1f}m > 50m). Cal justificació de desviació.",
        )
    return distancia


async def _carregar_estat_trams(
    db: AsyncSession, empresa_uuid: uuid.UUID, feina: OrdreTreball
) -> tuple[List[TramTempsResponse], Optional[OrdreTreballTramTemps], Optional[datetime], int, bool]:
    """Carrega els trams de temps d'una ordre i retorna el resum multi-interval."""
    stmt = (
        select(OrdreTreballTramTemps)
        .where(
            OrdreTreballTramTemps.empresa_id == empresa_uuid,
            OrdreTreballTramTemps.ordre_treball_id == feina.id,
        )
        .order_by(OrdreTreballTramTemps.hora_inici.asc())
    )
    trams = list((await db.execute(stmt)).scalars().all())
    trams_resp = [TramTempsResponse.model_validate(t) for t in trams]
    tram_obert = next((t for t in reversed(trams) if t.hora_fi is None), None)
    temps_acumulat_segons = sum(int(t.durada_segons or 0) for t in trams if t.hora_fi is not None)

    if tram_obert is not None:
        return trams_resp, tram_obert, tram_obert.hora_inici, temps_acumulat_segons, True

    # Compatibilitat amb ordres anteriors a la taula de trams
    if not trams:
        if feina.estat == "EN_CURS" and feina.hora_inici_real is not None and feina.hora_fi_real is None:
            return trams_resp, None, feina.hora_inici_real, 0, True
        if feina.hora_inici_real is not None and feina.hora_fi_real is not None:
            legacy_sec = max(0, int((feina.hora_fi_real - feina.hora_inici_real).total_seconds()))
            if legacy_sec == 0 and feina.hores_imputades_facturables:
                legacy_sec = int(round(float(feina.hores_imputades_facturables) * 3600.0))
            return trams_resp, None, None, legacy_sec, False
        if feina.hores_imputades_facturables and float(feina.hores_imputades_facturables) > 0:
            return trams_resp, None, None, int(round(float(feina.hores_imputades_facturables) * 3600.0)), False

    return trams_resp, None, None, temps_acumulat_segons, False


async def _tancar_tram_actiu_i_acumular(
    db: AsyncSession,
    empresa_uuid: uuid.UUID,
    feina: OrdreTreball,
    now: datetime,
    lat: Optional[float] = None,
    lng: Optional[float] = None,
    desviacio_justificada: bool = False,
    justificacio_gps: Optional[str] = None,
) -> tuple[List[TramTempsResponse], int, float]:
    """Tanca el tram actiu (si existeix) i recalcula les hores acumulades facturables."""
    stmt = (
        select(OrdreTreballTramTemps)
        .where(
            OrdreTreballTramTemps.empresa_id == empresa_uuid,
            OrdreTreballTramTemps.ordre_treball_id == feina.id,
        )
        .order_by(OrdreTreballTramTemps.hora_inici.asc())
    )
    trams = list((await db.execute(stmt)).scalars().all())
    tram_obert = next((t for t in reversed(trams) if t.hora_fi is None), None)

    if tram_obert is not None:
        tram_obert.hora_fi = now
        if lat is not None and lng is not None:
            tram_obert.gps_fi_lat = lat
            tram_obert.gps_fi_lng = lng
        sec = max(0, int((now - tram_obert.hora_inici).total_seconds()))
        tram_obert.durada_segons = max(1, sec) if now >= tram_obert.hora_inici else 0
        if desviacio_justificada or justificacio_gps:
            tram_obert.desviacio_geovalla = True
            if justificacio_gps:
                just_txt = justificacio_gps.strip()
                tram_obert.justificacio_gps = (
                    f"{tram_obert.justificacio_gps} | Final: {just_txt}"
                    if tram_obert.justificacio_gps
                    else just_txt
                )
    elif not trams and feina.hora_inici_real is not None and feina.hora_fi_real is None:
        if feina.hores_imputades_facturables and float(feina.hores_imputades_facturables) > 0:
            prev_sec = int(round(float(feina.hores_imputades_facturables) * 3600.0))
            tram_previ = OrdreTreballTramTemps(
                empresa_id=empresa_uuid,
                ordre_treball_id=feina.id,
                operari_id=feina.cap_de_colla_id,
                hora_inici=feina.hora_inici_real,
                hora_fi=feina.hora_inici_real,
                gps_inici_lat=feina.gps_inici_lat,
                gps_inici_lng=feina.gps_inici_lng,
                durada_segons=prev_sec,
                desviacio_geovalla=bool(feina.desviacio_geovalla),
                justificacio_gps=feina.justificacio_geovalla,
            )
            db.add(tram_previ)
            trams.append(tram_previ)

        sec = max(0, int((now - feina.hora_inici_real).total_seconds()))
        tram_legacy = OrdreTreballTramTemps(
            empresa_id=empresa_uuid,
            ordre_treball_id=feina.id,
            operari_id=feina.cap_de_colla_id,
            hora_inici=feina.hora_inici_real,
            hora_fi=now,
            gps_inici_lat=feina.gps_inici_lat,
            gps_inici_lng=feina.gps_inici_lng,
            gps_fi_lat=lat,
            gps_fi_lng=lng,
            durada_segons=max(1, sec) if now >= feina.hora_inici_real else 0,
            desviacio_geovalla=bool(desviacio_justificada or feina.desviacio_geovalla),
            justificacio_gps=justificacio_gps.strip() if justificacio_gps else feina.justificacio_geovalla,
        )
        db.add(tram_legacy)
        trams.append(tram_legacy)

    await db.flush()
    total_segons = sum(int(t.durada_segons or 0) for t in trams if t.hora_fi is not None)
    if total_segons > 0:
        total_hores = round(max(0.01, total_segons / 3600.0), 2)
        feina.hores_imputades_facturables = total_hores
        feina.cost_ma_obra_real = await calcular_cost_ma_obra_real(
            db, empresa_uuid, feina, trams, total_hores
        )
    else:
        total_hores = float(feina.hores_imputades_facturables or 0.0)
        total_segons = int(round(total_hores * 3600.0))

    trams_resp = [TramTempsResponse.model_validate(t) for t in trams]
    return trams_resp, total_segons, total_hores


@router.put("/feines/{feina_id}/comencar")
async def comencar_feina(
    feina_id: uuid.UUID,
    payload: ComencarFeinaRequest,
    request: Request,
    db: AsyncSession = Depends(get_db_with_tenant_context),
):
    """Obre un tram de temps de feina (inici o represa després de pausa) amb GPS i geovalla."""
    empresa_id = request.state.empresa_id
    if not empresa_id or empresa_id == "undefined":
        raise HTTPException(status_code=401)
    emp_uuid = uuid.UUID(empresa_id)
    usuari_id = uuid.UUID(_get_usuari_id(request))

    ot_res = await db.execute(
        select(OrdreTreball).where(
            OrdreTreball.id == feina_id, OrdreTreball.empresa_id == emp_uuid
        )
    )
    feina = ot_res.scalars().first()
    if not feina:
        raise HTTPException(status_code=404, detail="Feina no trobada")

    _validar_geovalla_feina(feina, payload)

    now = datetime.now(timezone.utc)
    stmt_trams = (
        select(OrdreTreballTramTemps)
        .where(
            OrdreTreballTramTemps.empresa_id == emp_uuid,
            OrdreTreballTramTemps.ordre_treball_id == feina.id,
        )
        .order_by(OrdreTreballTramTemps.hora_inici.asc())
    )
    existing_trams = list((await db.execute(stmt_trams)).scalars().all())

    # Preservar un tram previ tancat o hores anteriors si l'ordre tenia dades antigues però cap fila de tram
    if not existing_trams:
        prev_hores_sec = (
            int(round(float(feina.hores_imputades_facturables) * 3600.0))
            if feina.hores_imputades_facturables and float(feina.hores_imputades_facturables) > 0
            else 0
        )
        if feina.hora_inici_real is not None and feina.hora_fi_real is not None:
            sec_diff = max(1, int((feina.hora_fi_real - feina.hora_inici_real).total_seconds()))
            tram_previ = OrdreTreballTramTemps(
                empresa_id=emp_uuid,
                ordre_treball_id=feina.id,
                operari_id=usuari_id,
                hora_inici=feina.hora_inici_real,
                hora_fi=feina.hora_fi_real,
                gps_inici_lat=feina.gps_inici_lat,
                gps_inici_lng=feina.gps_inici_lng,
                gps_fi_lat=feina.gps_fi_lat,
                gps_fi_lng=feina.gps_fi_lng,
                durada_segons=max(sec_diff, prev_hores_sec),
                desviacio_geovalla=bool(feina.desviacio_geovalla),
                justificacio_gps=feina.justificacio_geovalla,
            )
            db.add(tram_previ)
            existing_trams.append(tram_previ)
        elif prev_hores_sec > 0:
            ref_inici = feina.hora_inici_real or now
            tram_previ = OrdreTreballTramTemps(
                empresa_id=emp_uuid,
                ordre_treball_id=feina.id,
                operari_id=usuari_id,
                hora_inici=ref_inici,
                hora_fi=ref_inici,
                gps_inici_lat=feina.gps_inici_lat,
                gps_inici_lng=feina.gps_inici_lng,
                durada_segons=prev_hores_sec,
                desviacio_geovalla=bool(feina.desviacio_geovalla),
                justificacio_gps=feina.justificacio_geovalla,
            )
            db.add(tram_previ)
            existing_trams.append(tram_previ)

    tram_obert = next((t for t in reversed(existing_trams) if t.hora_fi is None), None)
    if tram_obert is None:
        nou_tram = OrdreTreballTramTemps(
            empresa_id=emp_uuid,
            ordre_treball_id=feina.id,
            operari_id=usuari_id,
            hora_inici=now,
            gps_inici_lat=payload.lat,
            gps_inici_lng=payload.lng,
            durada_segons=0,
            desviacio_geovalla=bool(payload.desviacio_justificada or payload.justificacio_gps),
            justificacio_gps=payload.justificacio_gps.strip() if payload.justificacio_gps else None,
        )
        db.add(nou_tram)
        existing_trams.append(nou_tram)
        tram_obert = nou_tram

    if feina.hora_inici_real is None:
        feina.hora_inici_real = now
    feina.hora_fi_real = None

    if payload.lat is not None and payload.lng is not None and feina.gps_inici_lat is None:
        feina.gps_inici_lat = payload.lat
        feina.gps_inici_lng = payload.lng

    if payload.desviacio_justificada or payload.justificacio_gps:
        feina.desviacio_geovalla = True
        if payload.justificacio_gps:
            just_txt = payload.justificacio_gps.strip()
            feina.justificacio_geovalla = (
                f"{feina.justificacio_geovalla} | Inici tram: {just_txt}"
                if feina.justificacio_geovalla
                else just_txt
            )
        if payload.foto_evidencia_desviacio:
            feina.foto_evidencia_desviacio = payload.foto_evidencia_desviacio

    feina.estat = "EN_CURS"
    try:
        await db.commit()
    except Exception as e:
        await db.rollback()
        sys.stderr.write(f"ERROR db.commit a comencar_feina: {str(e)}\n")
        raise HTTPException(
            status_code=500,
            detail=f"Error en persistir inici de feina i geovalla a la base de dades: {str(e)}",
        )

    temps_acumulat_segons = sum(
        int(t.durada_segons or 0) for t in existing_trams if t.hora_fi is not None
    )
    trams_resp = [TramTempsResponse.model_validate(t).model_dump(mode="json") for t in existing_trams]

    return {
        "feina_id": str(feina.id),
        "estat": "EN_CURS",
        "hora_inici_real": feina.hora_inici_real.isoformat(),
        "hora_fi_real": None,
        "te_tram_obert": True,
        "tram_actiu_inici": tram_obert.hora_inici.isoformat(),
        "temps_acumulat_segons": temps_acumulat_segons,
        "hores_imputades_facturables": float(feina.hores_imputades_facturables or 0),
        "trams_temps": trams_resp,
        "gps_inici_lat": float(feina.gps_inici_lat) if feina.gps_inici_lat is not None else None,
        "gps_inici_lng": float(feina.gps_inici_lng) if feina.gps_inici_lng is not None else None,
        "desviacio_geovalla": feina.desviacio_geovalla,
        "justificacio_geovalla": feina.justificacio_geovalla,
        "missatge": "Temps de feina obert amb èxit",
    }


@router.put("/feines/{feina_id}/finalitzar-temps")
async def finalitzar_temps_feina(
    feina_id: uuid.UUID,
    payload: ComencarFeinaRequest,
    request: Request,
    db: AsyncSession = Depends(get_db_with_tenant_context),
):
    """Tanca el tram de temps actiu amb GPS, acumula el temps treballat i computa hores facturables."""
    empresa_id = request.state.empresa_id
    if not empresa_id or empresa_id == "undefined":
        raise HTTPException(status_code=401)
    emp_uuid = uuid.UUID(empresa_id)

    ot_res = await db.execute(
        select(OrdreTreball).where(
            OrdreTreball.id == feina_id, OrdreTreball.empresa_id == emp_uuid
        )
    )
    feina = ot_res.scalars().first()
    if not feina:
        raise HTTPException(status_code=404, detail="Feina no trobada")

    _validar_geovalla_feina(feina, payload)

    trams_existents = list(
        (
            await db.execute(
                select(OrdreTreballTramTemps).where(
                    OrdreTreballTramTemps.empresa_id == emp_uuid,
                    OrdreTreballTramTemps.ordre_treball_id == feina.id,
                )
            )
        )
        .scalars()
        .all()
    )
    te_tram_actiu = any(t.hora_fi is None for t in trams_existents) or (
        not trams_existents
        and feina.hora_inici_real is not None
        and feina.hora_fi_real is None
    )
    if not te_tram_actiu:
        raise HTTPException(
            status_code=400,
            detail="No hi ha cap temps de feina iniciat o obert per finalitzar.",
        )

    now = datetime.now(timezone.utc)
    if feina.hora_inici_real is None:
        feina.hora_inici_real = now

    trams_resp, total_segons, total_hores = await _tancar_tram_actiu_i_acumular(
        db=db,
        empresa_uuid=emp_uuid,
        feina=feina,
        now=now,
        lat=payload.lat,
        lng=payload.lng,
        desviacio_justificada=payload.desviacio_justificada,
        justificacio_gps=payload.justificacio_gps,
    )

    feina.hora_fi_real = now
    if payload.lat is not None and payload.lng is not None:
        feina.gps_fi_lat = payload.lat
        feina.gps_fi_lng = payload.lng

    feina.estat = "PAUSADA"
    feina.data_finalitzacio_camp = now.date()

    if payload.desviacio_justificada or payload.justificacio_gps:
        feina.desviacio_geovalla = True
        if payload.justificacio_gps:
            just_text = payload.justificacio_gps.strip()
            feina.justificacio_geovalla = (
                f"{feina.justificacio_geovalla} | Final: {just_text}"
                if feina.justificacio_geovalla
                else just_text
            )
        if payload.foto_evidencia_desviacio:
            feina.foto_evidencia_desviacio = payload.foto_evidencia_desviacio

    try:
        await db.commit()
    except Exception as e:
        await db.rollback()
        sys.stderr.write(f"ERROR db.commit a finalitzar_temps_feina: {str(e)}\n")
        raise HTTPException(
            status_code=500,
            detail=f"Error en persistir final de feina i geovalla a la base de dades: {str(e)}",
        )

    preu_hora = await resoldre_preu_hora_control_panel(db, emp_uuid, feina)
    total_facturable = round(total_hores * preu_hora, 2)

    return {
        "feina_id": str(feina.id),
        "estat": "PAUSADA",
        "hora_inici_real": feina.hora_inici_real.isoformat() if feina.hora_inici_real else None,
        "hora_fi_real": feina.hora_fi_real.isoformat(),
        "te_tram_obert": False,
        "tram_actiu_inici": None,
        "temps_acumulat_segons": total_segons,
        "trams_temps": [t.model_dump(mode="json") for t in trams_resp],
        "gps_fi_lat": float(feina.gps_fi_lat) if feina.gps_fi_lat is not None else None,
        "gps_fi_lng": float(feina.gps_fi_lng) if feina.gps_fi_lng is not None else None,
        "hores_imputades_facturables": total_hores,
        "total_facturable_estimat": total_facturable,
        "desviacio_geovalla": feina.desviacio_geovalla,
        "justificacio_geovalla": feina.justificacio_geovalla,
        "missatge": f"Temps de feina finalitzat amb GPS. Total acumulat: {total_hores}h.",
    }


def _detectar_mime_imatge_qa(raw_bytes: bytes) -> Optional[str]:
    """Valida Magic Bytes d'imatge real (WebP, JPEG o PNG) sense confiar en l'extensió."""
    kind = filetype.guess(raw_bytes)
    if kind is not None and kind.mime in ALLOWED_FOTO_QA_MIMES:
        return str(kind.mime)
    if raw_bytes.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if raw_bytes.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if len(raw_bytes) >= 12 and raw_bytes[:4] == b"RIFF" and raw_bytes[8:12] == b"WEBP":
        return "image/webp"
    return None


@router.post("/feines/{feina_id}/fotos")
async def pujar_foto_qualitat(
    feina_id: uuid.UUID,
    request: Request,
    tipus: str = Form(..., description="INICIAL, INTERMEDIA o FINAL"),
    foto: Optional[UploadFile] = File(None),
    fitxer: Optional[UploadFile] = File(None),
    db: AsyncSession = Depends(get_db_with_tenant_context),
):
    """Protocol obligatori de 3 fotos de control de qualitat al disc dur del client (Spec 013 RF-13)."""
    from app.services.sovereign_storage import SovereignStorageGateway

    empresa_id = request.state.empresa_id
    if not empresa_id or empresa_id == "undefined":
        raise HTTPException(status_code=401)
    emp_uuid = uuid.UUID(str(empresa_id))

    tipus_upper = tipus.upper()
    if tipus_upper not in ("INICIAL", "INTERMEDIA", "FINAL"):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="El tipus de foto ha de ser INICIAL, INTERMEDIA o FINAL",
        )

    ot_res = await db.execute(
        select(OrdreTreball.id).where(
            OrdreTreball.id == feina_id,
            OrdreTreball.empresa_id == emp_uuid,
        )
    )
    if not ot_res.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Feina no trobada")

    file_obj = foto or fitxer
    if file_obj is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="És obligatori adjuntar el fitxer d'imatge de control de qualitat.",
        )

    content = await file_obj.read()
    if not content:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="El fitxer de fotografia està buit.",
        )
    if len(content) > MAX_FOTO_QA_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail="La fotografia supera el límit màxim de 10 MB.",
        )

    detected_mime = _detectar_mime_imatge_qa(content)
    if not detected_mime:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Format d'imatge no vàlid (Magic Bytes). Només s'admeten WebP, JPEG o PNG.",
        )

    nom_fitxer = f"ot_{feina_id}_foto_{tipus_upper.lower()}.webp"
    file_path = await SovereignStorageGateway.pujar_fitxer_binari(
        db=db,
        empresa_id=empresa_id,
        categoria="ots_actives",
        nom_fitxer=nom_fitxer,
        content=content,
        content_type=detected_mime,
    )

    return {
        "feina_id": str(feina_id),
        "tipus": tipus_upper,
        "path": file_path,
        "content_type": detected_mime,
        "mida_bytes": len(content),
        "status": "GUARDAT",
    }


@router.get("/feines/{feina_id}/fotos")
async def consultar_fotos_qualitat(
    feina_id: uuid.UUID, request: Request, db: AsyncSession = Depends(get_db_with_tenant_context)
):
    """Consulta l'estat del protocol de 3 fotos al disc dur del client (Spec 013 RF-13, RF-14)."""
    from app.services.sovereign_storage import SovereignStorageGateway

    empresa_id = request.state.empresa_id
    if not empresa_id or empresa_id == "undefined":
        raise HTTPException(status_code=401)

    fotos_pujades = {}
    for t in ["inicial", "intermedia", "final"]:
        nom_fitxer = f"ot_{feina_id}_foto_{t}.webp"
        fotos_pujades[t] = await SovereignStorageGateway.existeix_fitxer_categoria(
            db=db,
            empresa_id=empresa_id,
            categoria="ots_actives",
            nom_fitxer=nom_fitxer,
        )

    complet = all(fotos_pujades.values())
    return {"feina_id": str(feina_id), "fotos": fotos_pujades, "protocol_complet": complet}


class FinalitzarFeinaRequest(BaseModel):
    hores: Optional[float] = None
    observacions: Optional[str] = Field(None, max_length=2000)
    signatura_base64: Optional[str] = None
    nom_receptor: Optional[str] = Field(None, max_length=150)
    dni_receptor: Optional[str] = Field(None, max_length=30)


@router.put("/feines/{feina_id}/finalitzar")
async def finalitzar_feina(
    feina_id: uuid.UUID,
    request: Request,
    payload: Optional[FinalitzarFeinaRequest] = None,
    db: AsyncSession = Depends(get_db_with_tenant_context),
):
    """Finalitza la feina. Bloquejat si no s'han capturat les 3 fotos (Spec 013 RF-14, RF-17)."""
    from app.services.sovereign_storage import SovereignStorageGateway

    empresa_id = request.state.empresa_id
    if not empresa_id or empresa_id == "undefined":
        raise HTTPException(status_code=401)
    emp_uuid = uuid.UUID(str(empresa_id))

    ot_res = await db.execute(
        select(OrdreTreball).where(
            OrdreTreball.id == feina_id, OrdreTreball.empresa_id == emp_uuid
        )
    )
    feina = ot_res.scalars().first()
    if not feina:
        raise HTTPException(status_code=404, detail="Feina no trobada")

    faltants = []
    for t in ["inicial", "intermedia", "final"]:
        nom_fitxer = f"ot_{feina_id}_foto_{t}.webp"
        exists = await SovereignStorageGateway.existeix_fitxer_categoria(
            db=db,
            empresa_id=empresa_id,
            categoria="ots_actives",
            nom_fitxer=nom_fitxer,
        )
        if not exists:
            faltants.append(t.capitalize())

    if faltants:
        raise HTTPException(
            status_code=400,
            detail=f"Falten fotografies requerides de control de qualitat: {', '.join(faltants)} (Spec 013 RF-14)",
        )

    now = datetime.now(timezone.utc)
    if payload and payload.signatura_base64:
        sig_path = await desar_signatura_client_ot(
            db=db,
            empresa_id=emp_uuid,
            ordre_treball_id=feina.id,
            signatura_base64=payload.signatura_base64,
            exigir_magic_bytes=True,
        )
        feina.signatura_client_path = sig_path
        feina.data_signatura = now

    if payload:
        if payload.nom_receptor is not None:
            feina.nom_receptor = payload.nom_receptor.strip() or None
        if payload.dni_receptor is not None:
            feina.dni_receptor = payload.dni_receptor.strip().upper() or None
        if payload.observacions is not None:
            feina.observacions_tancament = payload.observacions.strip() or None

    await _tancar_tram_actiu_i_acumular(
        db=db,
        empresa_uuid=emp_uuid,
        feina=feina,
        now=now,
    )
    if feina.hora_inici_real is not None and feina.hora_fi_real is None:
        feina.hora_fi_real = now

    if (
        (not feina.hores_imputades_facturables or float(feina.hores_imputades_facturables) <= 0)
        and payload
        and payload.hores is not None
        and payload.hores > 0
    ):
        feina.hores_imputades_facturables = round(payload.hores, 2)

    if feina.hores_imputades_facturables:
        trams_finals = list(
            (
                await db.execute(
                    select(OrdreTreballTramTemps).where(
                        OrdreTreballTramTemps.empresa_id == emp_uuid,
                        OrdreTreballTramTemps.ordre_treball_id == feina.id,
                    )
                )
            )
            .scalars()
            .all()
        )
        feina.cost_ma_obra_real = await calcular_cost_ma_obra_real(
            db,
            emp_uuid,
            feina,
            trams_finals,
            float(feina.hores_imputades_facturables),
        )

    feina.data_finalitzacio_camp = now.date()
    feina.estat = "COMPLERT"
    await db.commit()

    # Desar l'OT tancada a la carpeta d'històric del disc dur del client
    await SovereignStorageGateway.desar_entitat_json(
        db=db,
        empresa_id=empresa_id,
        categoria="ots_historic",
        item_id=str(feina.id),
        dades={
            "id": str(feina.id),
            "codi": feina.codi,
            "titol": feina.titol,
            "estat": feina.estat,
            "adreca": feina.adreca,
            "client_id": str(feina.client_id) if feina.client_id else None,
            "cap_de_colla_id": str(feina.cap_de_colla_id) if feina.cap_de_colla_id else None,
            "fotos_qa": [
                f"ot_{feina_id}_foto_inicial.webp",
                f"ot_{feina_id}_foto_intermedia.webp",
                f"ot_{feina_id}_foto_final.webp",
            ],
            "hores": float(
                feina.hores_imputades_facturables
                or (payload.hores if payload and payload.hores is not None else 0.0)
            ),
            "observacions": feina.observacions_tancament,
            "nom_receptor": feina.nom_receptor,
            "dni_receptor": feina.dni_receptor,
            "signatura_client_path": feina.signatura_client_path,
            "data_signatura": feina.data_signatura.isoformat() if feina.data_signatura else None,
            "signatura_present": bool(feina.signatura_client_path),
        },
    )

    return {
        "feina_id": str(feina.id),
        "estat": "COMPLERT",
        "signatura_client_path": feina.signatura_client_path,
        "nom_receptor": feina.nom_receptor,
        "dni_receptor": feina.dni_receptor,
        "observacions_tancament": feina.observacions_tancament,
        "data_signatura": feina.data_signatura.isoformat() if feina.data_signatura else None,
        "missatge": "Feina finalitzada satisfactòriament",
    }


@router.get("/materials")
async def llistar_materials_operari_en_feines(
    request: Request,
    ordre_treball_id: Optional[uuid.UUID] = None,
    db: AsyncSession = Depends(get_db_with_tenant_context),
):
    from app.api.v1.operari_pwa.picking import llistar_materials_operari

    return await llistar_materials_operari(request, db, ordre_treball_id=ordre_treball_id)

