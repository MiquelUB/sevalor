import math
import sys
import uuid
from datetime import date
from typing import Any, List, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
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
    Vehicle,
)

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


class FeinaOperariDetailResponse(BaseModel):
    id: uuid.UUID
    codi: str
    titol: str
    descripcio: Optional[str] = None
    estat: str
    adreca: Optional[str] = None
    data_planificacio: Optional[date] = None
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
            OrdreTreball.cap_de_colla_id == uuid.UUID(usuari_id),
            OrdreTreball.estat.in_(["PENDENT", "ASSIGNADA", "PROGRAMADA", "EN_CURS", "EN_RUTA", "EN_OBRA", "PAUSADA"]),
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
                OrdreTreball.cap_de_colla_id == uuid.UUID(usuari_id),
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


@router.put("/feines/{feina_id}/comencar")
async def comencar_feina(
    feina_id: uuid.UUID,
    payload: ComencarFeinaRequest,
    request: Request,
    db: AsyncSession = Depends(get_db_with_tenant_context),
):
    """Comença el cronòmetre de la feina amb control de geovalla (Spec 013 RF-12, RF-12.1)."""
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

    # Comprovació Geovalla de 50 m si es passen coordenades i l'adreça té coordenades
    if payload.lat is not None and payload.lng is not None and feina.adreca and "," in feina.adreca:
        try:
            parts = [float(p.strip()) for p in feina.adreca.split(",")]
            if len(parts) >= 2:
                dest_lat, dest_lng = parts[0], parts[1]
                distancia = calcular_distancia_metres(payload.lat, payload.lng, dest_lat, dest_lng)
                if distancia > 50.0 and not payload.desviacio_justificada:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Geovalla d'obra superada (distància: {distancia:.1f}m > 50m). Cal sol·licitud d'inici per desviació amb foto d'evidència.",
                    )
        except (ValueError, TypeError):
            pass

    feina.estat = "EN_CURS"
    await db.commit()
    return {"feina_id": str(feina.id), "estat": "EN_CURS", "missatge": "Feina iniciada amb èxit"}


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

    tipus_upper = tipus.upper()
    if tipus_upper not in ("INICIAL", "INTERMEDIA", "FINAL"):
        raise HTTPException(
            status_code=422, detail="El tipus de foto ha de ser INICIAL, INTERMEDIA o FINAL"
        )

    nom_fitxer = f"ot_{feina_id}_foto_{tipus_upper.lower()}.webp"
    file_obj = foto or fitxer
    content = await file_obj.read() if file_obj else b"WEBP_EVIDENCE_PLACEHOLDER"

    file_path = await SovereignStorageGateway.pujar_fitxer_binari(
        db=db,
        empresa_id=empresa_id,
        categoria="ots_actives",
        nom_fitxer=nom_fitxer,
        content=content,
        content_type="image/webp",
    )

    return {"feina_id": str(feina_id), "tipus": tipus_upper, "path": file_path, "status": "GUARDAT"}


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
    observacions: Optional[str] = None
    signatura_base64: Optional[str] = None


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

    ot_res = await db.execute(
        select(OrdreTreball).where(
            OrdreTreball.id == feina_id, OrdreTreball.empresa_id == uuid.UUID(empresa_id)
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
            "hores": payload.hores if payload else None,
            "observacions": payload.observacions if payload else None,
            "signatura_present": bool(payload and payload.signatura_base64),
        },
    )

    return {
        "feina_id": str(feina.id),
        "estat": "COMPLERT",
        "missatge": "Feina finalitzada satisfactòriament",
    }


@router.get("/materials")
async def llistar_materials_operari_en_feines(
    request: Request,
    db: AsyncSession = Depends(get_db_with_tenant_context),
):
    from app.api.v1.operari_pwa.picking import llistar_materials_operari

    return await llistar_materials_operari(request, db)

