import math
import os
import re
import uuid
from datetime import date, datetime, timezone
from typing import Any, Dict, List, Optional

import filetype
from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    Request,
    UploadFile,
    status,
)
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db_with_tenant_context
from app.core.security import require_roles
from app.models.models import (
    DocumentFlota,
    HistorialAssignacioVehicle,
    Magatzem,
    MantenimentVehicle,
    OrdreTreball,
    Usuari,
    Vehicle,
)
from app.services.ocr_service import processar_ocr_document_vehicle

router = APIRouter(
    prefix="/gestio/flota",
    tags=["Gestió Flota"],
    dependencies=[Depends(require_roles(["BOSS", "SECRETARIA", "ENGINYER"]))],
)


class VehicleCreate(BaseModel):
    matricula: str = Field(..., max_length=20)
    marca: str = Field(..., max_length=50)
    model: str = Field(..., max_length=50)
    tipus: str = Field("THERMIC", max_length=30)
    distintiu_ambiental: Optional[str] = Field(None, max_length=10)
    estat: str = Field("OPERATIU", max_length=30)
    conductor_habitual_id: Optional[uuid.UUID] = None
    odometre_acumulat: Optional[int] = 0
    data_proxima_itv: Optional[date] = None
    estat_itv: str = Field("FAVORABLE", max_length=50)
    data_caducitat_asseguranca: Optional[date] = None
    companyia_asseguradora: Optional[str] = Field(None, max_length=100)
    polissa_asseguranca: Optional[str] = Field(None, max_length=100)
    carnet_necessari: str = Field("B", max_length=10)
    historial_reparacions: Optional[str] = None
    regim_adquisicio: str = Field("PROPIETAT", max_length=30)
    renting_limit_km: Optional[int] = None
    tacograf_necessari: bool = False
    data_propera_descarrega_tacograf: Optional[date] = None
    capacitat_bateria_kwh: Optional[float] = None
    soh_bateria: Optional[float] = None
    places: int = 5
    pes_maxim_autoritzat: int = 3500


class VehicleResponse(VehicleCreate):
    id: uuid.UUID
    horometre_acumulat: float
    odometre_acumulat: int
    conductor_nom: Optional[str] = None
    consum_l_100km: Optional[float] = None
    consum_mitjana_historica: Optional[float] = None
    consum_adblue_litres: float = 0.0

    model_config = ConfigDict(from_attributes=True)


@router.get("", response_model=List[VehicleResponse])
@router.get("/vehicles", response_model=List[VehicleResponse])
async def llistar_flota(
    request: Request,
    q: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    db: AsyncSession = Depends(get_db_with_tenant_context),
):
    empresa_id = request.state.empresa_id
    if not empresa_id or empresa_id == "undefined":
        raise HTTPException(status_code=401, detail="No identificat")

    stmt = (
        select(Vehicle, Usuari.nom, Usuari.cognoms)
        .outerjoin(Usuari, Vehicle.conductor_habitual_id == Usuari.id)
        .where(Vehicle.empresa_id == uuid.UUID(empresa_id))
    )

    if q:
        search_term = f"%{q}%"
        stmt = stmt.where(
            or_(
                Vehicle.matricula.ilike(search_term),
                Vehicle.marca.ilike(search_term),
                Vehicle.model.ilike(search_term),
            )
        )

    stmt = stmt.limit(limit).offset(offset).order_by(Vehicle.created_at.desc())

    result = await db.execute(stmt)
    rows = result.all()
    vehicles = []
    for veh, u_nom, u_cognoms in rows:
        c_nom = f"{u_nom or ''} {u_cognoms or ''}".strip() or None
        v_dict = {c.name: getattr(veh, c.name) for c in veh.__table__.columns}
        v_dict["conductor_nom"] = c_nom
        vehicles.append(VehicleResponse.model_validate(v_dict))

    return vehicles


@router.post("", response_model=VehicleResponse, status_code=status.HTTP_201_CREATED)
async def alta_vehicle(
    request: Request, vehicle: VehicleCreate, db: AsyncSession = Depends(get_db_with_tenant_context)
):
    empresa_id = request.state.empresa_id
    if not empresa_id or empresa_id == "undefined":
        raise HTTPException(status_code=401, detail="No identificat")

    stmt_mat = select(Vehicle).where(
        Vehicle.empresa_id == uuid.UUID(empresa_id), Vehicle.matricula == vehicle.matricula
    )
    result_mat = await db.execute(stmt_mat)
    if result_mat.scalars().first():
        raise HTTPException(status_code=400, detail="La matrícula ja es troba registrada")

    nou_vehicle = Vehicle(
        empresa_id=uuid.UUID(empresa_id),
        matricula=vehicle.matricula,
        marca=vehicle.marca,
        model=vehicle.model,
        tipus=vehicle.tipus,
        distintiu_ambiental=vehicle.distintiu_ambiental,
        estat=vehicle.estat,
        odometre_acumulat=vehicle.odometre_acumulat or 0,
        data_proxima_itv=vehicle.data_proxima_itv,
        estat_itv=vehicle.estat_itv,
        data_caducitat_asseguranca=vehicle.data_caducitat_asseguranca,
        companyia_asseguradora=vehicle.companyia_asseguradora,
        polissa_asseguranca=vehicle.polissa_asseguranca,
        carnet_necessari=vehicle.carnet_necessari,
        historial_reparacions=vehicle.historial_reparacions,
        regim_adquisicio=vehicle.regim_adquisicio,
        renting_limit_km=vehicle.renting_limit_km if vehicle.regim_adquisicio in ("RENTING", "LLOGUER") else None,
        tacograf_necessari=vehicle.tacograf_necessari,
        data_propera_descarrega_tacograf=vehicle.data_propera_descarrega_tacograf,
        capacitat_bateria_kwh=vehicle.capacitat_bateria_kwh,
        soh_bateria=vehicle.soh_bateria,
        places=vehicle.places,
        pes_maxim_autoritzat=vehicle.pes_maxim_autoritzat,
    )

    db.add(nou_vehicle)
    await db.flush()

    # Creació automàtica del Magatzem Mòbil per al Vehicle (Spec 004 / Spec 01 / Spec 015)
    magatzem_furgoneta = Magatzem(
        empresa_id=uuid.UUID(empresa_id),
        nom=f"Vehicle {nou_vehicle.matricula} ({nou_vehicle.marca} {nou_vehicle.model})",
        tipus="FURGONETA",
        vehicle_id=nou_vehicle.id,
        actiu=True,
    )
    db.add(magatzem_furgoneta)
    await db.commit()

    return nou_vehicle


@router.put("/{vehicle_id}", response_model=VehicleResponse)
async def editar_vehicle(
    request: Request,
    vehicle_id: uuid.UUID,
    vehicle: VehicleCreate,
    db: AsyncSession = Depends(get_db_with_tenant_context),
):
    empresa_id = request.state.empresa_id
    if not empresa_id or empresa_id == "undefined":
        raise HTTPException(status_code=401, detail="No identificat")

    stmt = select(Vehicle).where(
        Vehicle.id == vehicle_id, Vehicle.empresa_id == uuid.UUID(empresa_id)
    )
    result = await db.execute(stmt)
    v_db = result.scalars().first()
    if not v_db:
        raise HTTPException(status_code=404, detail="Vehicle no trobat")

    v_db.matricula = vehicle.matricula
    v_db.marca = vehicle.marca
    v_db.model = vehicle.model
    v_db.tipus = vehicle.tipus
    v_db.distintiu_ambiental = vehicle.distintiu_ambiental
    v_db.estat = vehicle.estat
    if vehicle.odometre_acumulat is not None:
        v_db.odometre_acumulat = vehicle.odometre_acumulat
    v_db.data_proxima_itv = vehicle.data_proxima_itv
    v_db.estat_itv = vehicle.estat_itv
    v_db.data_caducitat_asseguranca = vehicle.data_caducitat_asseguranca
    v_db.companyia_asseguradora = vehicle.companyia_asseguradora
    v_db.polissa_asseguranca = vehicle.polissa_asseguranca
    v_db.carnet_necessari = vehicle.carnet_necessari
    v_db.historial_reparacions = vehicle.historial_reparacions
    v_db.regim_adquisicio = vehicle.regim_adquisicio
    v_db.renting_limit_km = vehicle.renting_limit_km if vehicle.regim_adquisicio in ("RENTING", "LLOGUER") else None
    v_db.tacograf_necessari = vehicle.tacograf_necessari
    v_db.data_propera_descarrega_tacograf = vehicle.data_propera_descarrega_tacograf
    v_db.capacitat_bateria_kwh = vehicle.capacitat_bateria_kwh
    v_db.soh_bateria = vehicle.soh_bateria
    v_db.places = vehicle.places
    v_db.pes_maxim_autoritzat = vehicle.pes_maxim_autoritzat

    await db.commit()

    return v_db


# ---------------------------------------------------------------------------
# Càlcul de Vehicles Propers per Haversine (Spec 006 / Spec 012 / Phase 3)
# ---------------------------------------------------------------------------


def calcular_distancia_haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calcula la distància en quilòmetres entre dues coordenades usant la fórmula de Haversine."""
    R = 6371.0  # Radi de la Terra en km
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return round(R * c, 2)


class VehicleProperItem(BaseModel):
    vehicle_id: uuid.UUID
    matricula: str
    marca: str
    model: str
    estat: str
    distancia_km: float
    lat: float
    lng: float
    ordre_treball_id: Optional[uuid.UUID] = None
    ordre_treball_codi: Optional[str] = None
    ordre_treball_titol: Optional[str] = None


@router.get("/propers", response_model=List[VehicleProperItem])
async def llistar_vehicles_propers(
    request: Request,
    lat: float = Query(..., description="Latitud de l'objectiu"),
    lng: float = Query(..., description="Longitud de l'objectiu"),
    limit: int = Query(10, ge=1, le=50),
    db: AsyncSession = Depends(get_db_with_tenant_context),
):
    """
    Retorna els vehicles de l'empresa ordenats per proximitat geogràfica a les coordenades donades (Haversine).
    Determina la posició del vehicle segons l'OT activa en curs o ubicació registrada.
    """
    empresa_id = getattr(request.state, "empresa_id", None) or request.headers.get("X-Empresa-ID")
    if not empresa_id or empresa_id == "undefined":
        raise HTTPException(status_code=401, detail="No identificat")

    empresa_uuid = uuid.UUID(empresa_id)

    # Obtenir vehicles de l'empresa
    stmt_v = select(Vehicle).where(Vehicle.empresa_id == empresa_uuid)
    res_v = await db.execute(stmt_v)
    vehicles = res_v.scalars().all()

    if not vehicles:
        return []

    # Obtenir feines actives per associar posició de camp
    stmt_ot = select(OrdreTreball).where(
        OrdreTreball.empresa_id == empresa_uuid,
        OrdreTreball.vehicle_id.isnot(None),
        OrdreTreball.estat.in_(["EN_OBRA", "EN_RUTA", "EN_CURS", "PENDENT"]),
    )
    res_ot = await db.execute(stmt_ot)
    ots = res_ot.scalars().all()
    vehicle_ot_map = {ot.vehicle_id: ot for ot in ots}

    resultats: List[VehicleProperItem] = []

    for v in vehicles:
        # Coordenades per defecte si no té OT activa
        v_lat, v_lng = None, None
        ot_associada = vehicle_ot_map.get(v.id)

        if ot_associada and ot_associada.adreca:
            m = re.findall(r"[-+]?\d+\.\d+", ot_associada.adreca)
            if len(m) >= 2:
                v_lat, v_lng = float(m[0]), float(m[1])
            elif "," in ot_associada.adreca:
                try:
                    parts = [float(p.strip()) for p in ot_associada.adreca.split(",")]
                    if len(parts) >= 2:
                        v_lat, v_lng = parts[0], parts[1]
                except (ValueError, TypeError):
                    pass

        dist = (
            calcular_distancia_haversine(lat, lng, v_lat, v_lng)
            if v_lat is not None and v_lng is not None
            else None
        )

        resultats.append(
            VehicleProperItem(
                vehicle_id=v.id,
                matricula=v.matricula,
                marca=v.marca,
                model=v.model,
                estat=v.estat,
                distancia_km=dist,  # type: ignore
                lat=v_lat,  # type: ignore
                lng=v_lng,  # type: ignore
                ordre_treball_id=ot_associada.id if ot_associada else None,
                ordre_treball_codi=ot_associada.codi if ot_associada else None,
                ordre_treball_titol=ot_associada.titol if ot_associada else None,
            )
        )

    # Ordenar pel vehicle més proper
    resultats.sort(key=lambda x: x.distancia_km if x.distancia_km is not None else float("inf"))

    return resultats[:limit]


@router.post("/{vehicle_id}/documents", status_code=201)
async def pujar_document_flota(
    request: Request,
    vehicle_id: uuid.UUID,
    tipus_document: str = Form(...),
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db_with_tenant_context),
):
    empresa_id = request.state.empresa_id
    if not empresa_id:
        raise HTTPException(status_code=401)
    empresa_id = uuid.UUID(empresa_id)

    # Comprovar vehicle
    stmt = select(Vehicle).where(Vehicle.id == vehicle_id, Vehicle.empresa_id == empresa_id)
    res = await db.execute(stmt)
    v_db = res.scalars().first()
    if not v_db:
        raise HTTPException(status_code=404, detail="Vehicle no trobat")

    # Guardar disc local
    file_bytes = await file.read()
    kind = filetype.guess(file_bytes)
    is_pdf = file_bytes.startswith(b"%PDF") or (bool(file.filename) and file.filename.lower().endswith(".pdf"))
    filename_lower = (file.filename or "").lower()
    is_text = False
    if filename_lower.endswith((".md", ".txt", ".markdown", ".csv")):
        is_text = True
    else:
        try:
            file_bytes.decode("utf-8")
            is_text = True
        except Exception:
            is_text = False

    if not kind and not is_pdf and not is_text:
        raise HTTPException(
            status_code=400,
            detail="Tipus de fitxer invàlid. Cal una imatge, document PDF o fitxer de text/markdown (.md).",
        )

    if kind:
        file_ext = kind.extension
    elif is_pdf:
        file_ext = "pdf"
    elif filename_lower.endswith(".md"):
        file_ext = "md"
    elif filename_lower.endswith(".markdown"):
        file_ext = "markdown"
    else:
        file_ext = "txt"

    docs_dir = f"/docs/{empresa_id}/flota/{vehicle_id}"
    try:
        os.makedirs(docs_dir, exist_ok=True)
    except PermissionError:
        docs_dir = f"/tmp/docs/{empresa_id}/flota/{vehicle_id}"
        os.makedirs(docs_dir, exist_ok=True)
    safe_name = f"{uuid.uuid4()}.{file_ext}"
    file_path = os.path.join(docs_dir, safe_name)

    with open(file_path, "wb") as buffer:
        buffer.write(file_bytes)

    doc = DocumentFlota(
        empresa_id=empresa_id,
        vehicle_id=vehicle_id,
        tipus_document=tipus_document,
        nom_arxiu=safe_name,
        ruta_arxiu=file_path,
        creat_per_id=None,
    )
    db.add(doc)
    await db.commit()

    # Executar OCR asíncron
    try:
        from app.workers.tasks import processar_ocr_document_task

        processar_ocr_document_task.delay(file_path, str(empresa_id))
    except Exception:
        pass

    return {"missatge": "Document pujat i en procés d'OCR", "id": str(doc.id)}


@router.get("/{vehicle_id}/documents")
async def llistar_documents_flota(
    request: Request, vehicle_id: uuid.UUID, db: AsyncSession = Depends(get_db_with_tenant_context)
):
    empresa_id = request.state.empresa_id
    if not empresa_id:
        raise HTTPException(status_code=401)
    empresa_id = uuid.UUID(empresa_id)
    stmt = select(DocumentFlota).where(
        DocumentFlota.vehicle_id == vehicle_id, DocumentFlota.empresa_id == empresa_id
    )
    res = await db.execute(stmt)
    docs = res.scalars().all()

    return [
        {
            "id": str(d.id),
            "tipus": d.tipus_document,
            "nom_arxiu": d.nom_arxiu,
            "data": d.data_document.isoformat() if d.data_document else None,
        }
        for d in docs
    ]


@router.post("/ocr-draft")
async def ocr_vehicle_draft(
    request: Request,
    files: Optional[List[UploadFile]] = File(None),
    file: Optional[UploadFile] = File(None),
):
    empresa_id = request.state.empresa_id
    if not empresa_id or empresa_id == "undefined":
        raise HTTPException(status_code=401, detail="No identificat")

    all_files: List[UploadFile] = []
    if files:
        all_files.extend([f for f in files if f and f.filename])
    if file and file.filename and file not in all_files:
        all_files.append(file)

    if not all_files:
        raise HTTPException(
            status_code=400,
            detail="Cal adjuntar com a mínim un document de vehicle (Targeta ITV, Permís de Circulació o Pòlissa d'Assegurança)",
        )

    merged_data: Dict[str, Any] = {
        "status": "EXTRET_AUTOMATIC",
        "confidence": 0.0,
        "matricula": None,
        "bastidor": None,
        "marca": None,
        "model": None,
        "tipus": None,
        "distintiu_ambiental": None,
        "estat_itv": None,
        "data_proxima_itv": None,
        "data_inspeccio_itv": None,
        "data_matriculacio": None,
        "odometre_acumulat": None,
        "companyia_asseguradora": None,
        "polissa_asseguranca": None,
        "data_caducitat_asseguranca": None,
        "regim_adquisicio": None,
        "renting_limit_km": None,
        "carnet_necessari": None,
        "documents_processats": [],
    }

    confidences: List[float] = []

    for upload in all_files:
        file_bytes = await upload.read()
        if not file_bytes:
            continue

        res = await processar_ocr_document_vehicle(file_bytes)
        confidences.append(res.get("confidence", 0.0))

        # Fusionar camps no nuls procedents de qualsevol document pujat
        for k in [
            "matricula",
            "bastidor",
            "marca",
            "model",
            "tipus",
            "distintiu_ambiental",
            "estat_itv",
            "data_proxima_itv",
            "data_inspeccio_itv",
            "data_matriculacio",
            "odometre_acumulat",
            "companyia_asseguradora",
            "polissa_asseguranca",
            "data_caducitat_asseguranca",
            "regim_adquisicio",
            "renting_limit_km",
            "carnet_necessari",
        ]:
            if res.get(k) is not None and not merged_data.get(k):
                merged_data[k] = res[k]

        merged_data["documents_processats"].append(
            {
                "nom": upload.filename,
                "tipus_detectat": res.get("tipus_document", "GENERAL"),
                "matricula_detectada": res.get("matricula"),
            }
        )

    # Valors per defecte si no s'han especificat en cap document
    if not merged_data["tipus"]:
        merged_data["tipus"] = "DIESEL"
    if not merged_data["distintiu_ambiental"]:
        if merged_data["tipus"] == "EV":
            merged_data["distintiu_ambiental"] = "ZERO"
        elif merged_data["tipus"] == "PHEV":
            merged_data["distintiu_ambiental"] = "ECO"
        else:
            merged_data["distintiu_ambiental"] = "C"
    if not merged_data["regim_adquisicio"]:
        merged_data["regim_adquisicio"] = "PROPIETAT"
    if merged_data["regim_adquisicio"] not in ("RENTING", "LLOGUER"):
        merged_data["renting_limit_km"] = None
    if not merged_data["carnet_necessari"]:
        merged_data["carnet_necessari"] = "B"
    if not merged_data["estat_itv"]:
        merged_data["estat_itv"] = "FAVORABLE"

    merged_data["confidence"] = max(confidences) if confidences else 0.0
    trobat = bool(merged_data.get("matricula") or merged_data.get("bastidor"))
    merged_data["status"] = "EXTRET_AUTOMATIC" if trobat else "PENDENT_REVISIO_MANUAL"

    return merged_data


class AssignarVehicleRequest(BaseModel):
    usuari_id: uuid.UUID
    odometre: Optional[int] = None
    motiu: Optional[str] = None


@router.post("/{id}/assignar")
async def assignar_vehicle(
    request: Request,
    id: uuid.UUID,
    data: AssignarVehicleRequest,
    db: AsyncSession = Depends(get_db_with_tenant_context),
):
    empresa_id = uuid.UUID(request.state.empresa_id)

    # Check vehicle
    v = await db.scalar(select(Vehicle).where(Vehicle.id == id, Vehicle.empresa_id == empresa_id))
    if not v:
        raise HTTPException(status_code=404, detail="Vehicle no trobat")

    # Check usuari
    u = await db.scalar(
        select(Usuari).where(Usuari.id == data.usuari_id, Usuari.empresa_id == empresa_id)
    )
    if not u:
        raise HTTPException(status_code=404, detail="Usuari no trobat")

    v.estat = "ASSIGNAT"
    u.vehicle_assignat_id = v.id

    historial = HistorialAssignacioVehicle(
        empresa_id=empresa_id,
        vehicle_id=v.id,
        conductor_id=u.id,
        data_inici=datetime.now(timezone.utc),
        odometre_inici=data.odometre,
        motiu=data.motiu,
    )
    db.add(historial)
    await db.commit()
    return {"status": "ok", "missatge": "Vehicle assignat correctament"}


class RevocarVehicleRequest(BaseModel):
    odometre: Optional[int] = None
    motiu: Optional[str] = None


@router.post("/{id}/revocar")
async def revocar_vehicle(
    request: Request,
    id: uuid.UUID,
    data: RevocarVehicleRequest,
    db: AsyncSession = Depends(get_db_with_tenant_context),
):
    empresa_id = uuid.UUID(request.state.empresa_id)

    v = await db.scalar(select(Vehicle).where(Vehicle.id == id, Vehicle.empresa_id == empresa_id))
    if not v:
        raise HTTPException(status_code=404, detail="Vehicle no trobat")

    # Update usuari
    usuaris = await db.execute(
        select(Usuari).where(Usuari.vehicle_assignat_id == v.id, Usuari.empresa_id == empresa_id)
    )
    for u in usuaris.scalars().all():
        u.vehicle_assignat_id = None

    v.estat = "DISPONIBLE"

    # Close historial
    hist = await db.scalar(
        select(HistorialAssignacioVehicle)
        .where(
            HistorialAssignacioVehicle.vehicle_id == v.id,
            HistorialAssignacioVehicle.data_fi.is_(None),
        )
        .order_by(HistorialAssignacioVehicle.data_inici.desc())
    )
    if hist:
        hist.data_fi = datetime.now(timezone.utc)
        hist.odometre_fi = data.odometre

    await db.commit()
    return {"status": "ok", "missatge": "Assignació revocada"}


class MantenimentCreate(BaseModel):
    data_manteniment: date
    tipus: str = Field(..., max_length=50)
    descripcio: str
    taller: Optional[str] = None
    cost_euros: Optional[float] = None


@router.post("/{vehicle_id}/manteniments", status_code=201)
async def crear_manteniment(
    request: Request,
    vehicle_id: uuid.UUID,
    manteniment: MantenimentCreate,
    db: AsyncSession = Depends(get_db_with_tenant_context),
):
    empresa_id = uuid.UUID(request.state.empresa_id)

    v = await db.scalar(
        select(Vehicle).where(Vehicle.id == vehicle_id, Vehicle.empresa_id == empresa_id)
    )
    if not v:
        raise HTTPException(status_code=404, detail="Vehicle no trobat")

    mant = MantenimentVehicle(
        empresa_id=empresa_id,
        vehicle_id=vehicle_id,
        data_manteniment=datetime.combine(
            manteniment.data_manteniment, datetime.min.time(), tzinfo=timezone.utc
        ),
        tipus=manteniment.tipus,
        descripcio=manteniment.descripcio,
        taller=manteniment.taller,
        cost_euros=manteniment.cost_euros,
    )
    db.add(mant)
    await db.commit()
    return {"id": str(mant.id), "missatge": "Manteniment registrat"}


@router.get("/{vehicle_id}/manteniments")
async def llistar_manteniments(
    request: Request, vehicle_id: uuid.UUID, db: AsyncSession = Depends(get_db_with_tenant_context)
):
    empresa_id = uuid.UUID(request.state.empresa_id)
    mants = await db.execute(
        select(MantenimentVehicle)
        .where(
            MantenimentVehicle.vehicle_id == vehicle_id, MantenimentVehicle.empresa_id == empresa_id
        )
        .order_by(MantenimentVehicle.data_manteniment.desc())
    )
    return mants.scalars().all()


@router.post("/ocr-document")
async def ocr_document_vehicle(request: Request, file: UploadFile = File(...)):
    empresa_id = request.state.empresa_id
    if not empresa_id or empresa_id == "undefined":
        raise HTTPException(status_code=401, detail="No identificat")

    file_bytes = await file.read()
    if not file_bytes:
        raise HTTPException(status_code=400, detail="Fitxer buit")

    kind = filetype.guess(file_bytes)
    is_pdf = file_bytes.startswith(b"%PDF") or (bool(file.filename) and file.filename.lower().endswith(".pdf"))
    filename_lower = (file.filename or "").lower()
    is_text = False
    if filename_lower.endswith((".md", ".txt", ".markdown", ".csv")):
        is_text = True
    else:
        try:
            file_bytes.decode("utf-8")
            is_text = True
        except Exception:
            is_text = False

    if not kind and not is_pdf and not is_text:
        raise HTTPException(
            status_code=400,
            detail="Tipus de fitxer invàlid. Cal una imatge, document PDF o fitxer de text/markdown (.md).",
        )

    resultat = await processar_ocr_document_vehicle(file_bytes)
    return resultat
