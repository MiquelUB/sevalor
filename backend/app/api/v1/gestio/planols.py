import os
import re
import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile, status
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db_with_tenant_context
from app.core.security import require_roles
from app.models.models import CapaAnotacio, CapaVectorial, CarpetaPlanol, PlanolBase
from app.workers.tasks import generar_informe_planol_pdf

router = APIRouter(
    prefix="/gestio/planols",
    tags=["Gestió Plànols"],
    dependencies=[Depends(require_roles(["BOSS", "SECRETARIA", "ENGINYER"]))],
)


class PlanolCreate(BaseModel):
    titol: str = Field(..., max_length=150)
    codi_referencia: str = Field(..., max_length=50)
    carpeta_id: uuid.UUID
    tipus_fitxer: str = Field(..., max_length=20)
    fitxer_path: str = Field("/docs/planols/default.dxf", max_length=500)
    mida_bytes: int = Field(0)
    es_georeferenciat: bool = Field(False)


class PlanolResponse(PlanolCreate):
    id: uuid.UUID
    carpeta_nom: Optional[str] = None
    municipi: Optional[str] = None


class CarpetaCreate(BaseModel):
    nom: str = Field(..., max_length=100)
    categoria: str = Field("CLIENTS", max_length=30)
    client_id: Optional[uuid.UUID] = None
    municipi: Optional[str] = Field(None, max_length=100)
    descripcio: Optional[str] = None
    parent_id: Optional[uuid.UUID] = None


class CarpetaResponse(BaseModel):
    id: uuid.UUID
    nom: str
    categoria: str
    client_id: Optional[uuid.UUID]
    municipi: Optional[str]


class CapaVectorialCreate(BaseModel):
    planol_base_id: uuid.UUID
    nom: str = Field(..., max_length=100)
    disciplina: str = Field("OBRA_CIVIL", max_length=30)
    ordre_treball_id: Optional[uuid.UUID] = None
    color_hex: str = Field("#2563eb", max_length=10)
    gruix_linia: int = 2
    opacitat_percent: int = 100
    geometries_geojson: dict = Field(default_factory=dict)


class CapaVectorialResponse(BaseModel):
    id: uuid.UUID
    nom: str
    disciplina: str
    es_immutable: bool
    version_id: int
    color_hex: str


class ImportarDirectoriRequest(BaseModel):
    carpeta_id: uuid.UUID
    ruta_origen: Optional[str] = None


@router.get("", response_model=List[PlanolResponse])
async def llistar_planols(
    request: Request,
    carpeta_id: Optional[uuid.UUID] = None,
    q: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    db: AsyncSession = Depends(get_db_with_tenant_context),
):
    empresa_id = request.state.empresa_id
    if not empresa_id or empresa_id == "undefined":
        raise HTTPException(status_code=401, detail="No identificat")

    stmt = (
        select(PlanolBase, CarpetaPlanol.nom, CarpetaPlanol.municipi)
        .outerjoin(CarpetaPlanol, PlanolBase.carpeta_id == CarpetaPlanol.id)
        .where(PlanolBase.empresa_id == uuid.UUID(empresa_id))
    )

    if carpeta_id:
        stmt = stmt.where(PlanolBase.carpeta_id == carpeta_id)

    if q:
        search_term = f"%{q}%"
        stmt = stmt.where(
            or_(PlanolBase.codi_referencia.ilike(search_term), PlanolBase.titol.ilike(search_term))
        )

    stmt = stmt.limit(limit).offset(offset).order_by(PlanolBase.created_at.desc())

    result = await db.execute(stmt)
    rows = result.all()

    planols = []
    for p_obj, c_nom, c_mun in rows:
        planols.append(
            PlanolResponse(
                id=p_obj.id,
                titol=p_obj.titol,
                codi_referencia=p_obj.codi_referencia,
                carpeta_id=p_obj.carpeta_id,
                tipus_fitxer=p_obj.tipus_fitxer,
                fitxer_path=p_obj.fitxer_path,
                mida_bytes=p_obj.mida_bytes,
                es_georeferenciat=p_obj.es_georeferenciat,
                carpeta_nom=c_nom,
                municipi=c_mun,
            )
        )

    return planols


@router.post("", response_model=PlanolResponse, status_code=status.HTTP_201_CREATED)
async def alta_planol(
    request: Request, planol: PlanolCreate, db: AsyncSession = Depends(get_db_with_tenant_context)
):
    empresa_id = request.state.empresa_id
    if not empresa_id or empresa_id == "undefined":
        raise HTTPException(status_code=401, detail="No identificat")

    # Comprovem que la carpeta existeix i pertany a l'empresa
    stmt_carp = select(CarpetaPlanol).where(
        CarpetaPlanol.id == planol.carpeta_id, CarpetaPlanol.empresa_id == uuid.UUID(empresa_id)
    )
    res_carp = await db.execute(stmt_carp)
    carpeta = res_carp.scalars().first()
    if not carpeta:
        raise HTTPException(status_code=400, detail="Carpeta no vàlida o no pertany a l'empresa")

    stmt_codi = select(PlanolBase).where(
        PlanolBase.empresa_id == uuid.UUID(empresa_id),
        PlanolBase.codi_referencia == planol.codi_referencia,
    )
    result_codi = await db.execute(stmt_codi)
    if result_codi.scalars().first():
        raise HTTPException(status_code=400, detail="El codi de plànol ja es troba registrat")

    nou_planol = PlanolBase(
        empresa_id=uuid.UUID(empresa_id),
        titol=planol.titol,
        codi_referencia=planol.codi_referencia,
        carpeta_id=planol.carpeta_id,
        tipus_fitxer=planol.tipus_fitxer,
        fitxer_path=planol.fitxer_path,
        mida_bytes=planol.mida_bytes,
        es_georeferenciat=planol.es_georeferenciat,
    )

    db.add(nou_planol)
    await db.commit()

    return PlanolResponse(
        id=nou_planol.id,
        titol=nou_planol.titol,
        codi_referencia=nou_planol.codi_referencia,
        carpeta_id=nou_planol.carpeta_id,
        tipus_fitxer=nou_planol.tipus_fitxer,
        fitxer_path=nou_planol.fitxer_path,
        mida_bytes=nou_planol.mida_bytes,
        es_georeferenciat=nou_planol.es_georeferenciat,
        carpeta_nom=carpeta.nom,
        municipi=carpeta.municipi,
    )


@router.post("/upload", response_model=PlanolResponse, status_code=status.HTTP_201_CREATED)
async def pujar_planol_fitxer(
    request: Request,
    carpeta_id: uuid.UUID = Form(...),
    fitxer: UploadFile = File(...),
    titol: Optional[str] = Form(None),
    codi_referencia: Optional[str] = Form(None),
    tipus_fitxer: Optional[str] = Form(None),
    projeccio: Optional[str] = Form("ETRS89 / UTM 31N"),
    es_georeferenciat: bool = Form(True),
    db: AsyncSession = Depends(get_db_with_tenant_context),
):
    """Puja un fitxer de plànol (PDF, DXF, DWG, GeoJSON, etc.) i el vincula a la carpeta."""
    empresa_id = request.state.empresa_id
    if not empresa_id or empresa_id == "undefined":
        raise HTTPException(status_code=401, detail="No identificat")

    stmt_carp = select(CarpetaPlanol).where(
        CarpetaPlanol.id == carpeta_id, CarpetaPlanol.empresa_id == uuid.UUID(empresa_id)
    )
    res_carp = await db.execute(stmt_carp)
    carpeta = res_carp.scalars().first()
    if not carpeta:
        raise HTTPException(status_code=400, detail="Carpeta no vàlida o no pertany a l'empresa")

    content = await fitxer.read()
    mida_bytes = len(content)
    if mida_bytes == 0:
        raise HTTPException(status_code=400, detail="El fitxer és buit")

    filename = fitxer.filename or "planol.pdf"
    base_name, file_ext = os.path.splitext(filename)
    file_ext = file_ext.lower().lstrip(".")

    detected_type = tipus_fitxer
    if not detected_type:
        ext_map = {
            "pdf": "PDF",
            "dxf": "DXF",
            "dwg": "DWG",
            "geojson": "GEOJSON",
            "json": "GEOJSON",
            "kml": "KML",
            "png": "PNG",
            "jpg": "JPG",
            "jpeg": "JPG",
            "tif": "TIFF",
            "tiff": "TIFF",
        }
        detected_type = ext_map.get(file_ext, "DXF")

    safe_id = str(uuid.uuid4())[:8]
    clean_filename = re.sub(r"[^\w\-.]", "_", filename)
    saved_filename = f"{safe_id}_{clean_filename}"

    dest_dir = None
    for base in [os.environ.get("HETZNER_DOCS_PATH", "/docs"), os.path.join(os.getcwd(), "docs")]:
        try:
            cand = os.path.join(base, str(empresa_id), "planols")
            os.makedirs(cand, exist_ok=True)
            dest_dir = cand
            break
        except (PermissionError, OSError):
            continue

    if not dest_dir:
        dest_dir = os.path.join("/tmp", f"sevalor_docs_{empresa_id}_planols")
        os.makedirs(dest_dir, exist_ok=True)

    dest_file = os.path.join(dest_dir, saved_filename)
    with open(dest_file, "wb") as f:
        f.write(content)

    final_titol = (titol or base_name.replace("_", " ")).strip()
    if not codi_referencia or not codi_referencia.strip():
        clean_code = re.sub(r"[^\w]", "-", base_name.upper())[:12]
        final_codi = f"PLN-{clean_code}-{safe_id}"
    else:
        final_codi = codi_referencia.strip()

    stmt_codi = select(PlanolBase).where(
        PlanolBase.empresa_id == uuid.UUID(empresa_id),
        PlanolBase.codi_referencia == final_codi,
    )
    if (await db.execute(stmt_codi)).scalars().first():
        final_codi = f"{final_codi}-{safe_id}"

    nou_planol = PlanolBase(
        empresa_id=uuid.UUID(empresa_id),
        titol=final_titol,
        codi_referencia=final_codi,
        carpeta_id=carpeta_id,
        tipus_fitxer=detected_type,
        fitxer_path=dest_file,
        mida_bytes=mida_bytes,
        es_georeferenciat=es_georeferenciat,
        projeccio_origen=projeccio or "ETRS89 / UTM 31N",
    )

    db.add(nou_planol)
    await db.commit()

    return PlanolResponse(
        id=nou_planol.id,
        titol=nou_planol.titol,
        codi_referencia=nou_planol.codi_referencia,
        carpeta_id=nou_planol.carpeta_id,
        tipus_fitxer=nou_planol.tipus_fitxer,
        fitxer_path=nou_planol.fitxer_path,
        mida_bytes=nou_planol.mida_bytes,
        es_georeferenciat=nou_planol.es_georeferenciat,
        carpeta_nom=carpeta.nom,
        municipi=carpeta.municipi,
    )


@router.post("/importar-directori", response_model=List[PlanolResponse])
async def importar_planols_directori(
    request: Request,
    payload: ImportarDirectoriRequest,
    db: AsyncSession = Depends(get_db_with_tenant_context),
):
    """Escaneja la carpeta d'origen al disc i registra automàticament els plànols trobats."""
    empresa_id = request.state.empresa_id
    if not empresa_id or empresa_id == "undefined":
        raise HTTPException(status_code=401, detail="No identificat")

    stmt_carp = select(CarpetaPlanol).where(
        CarpetaPlanol.id == payload.carpeta_id, CarpetaPlanol.empresa_id == uuid.UUID(empresa_id)
    )
    carpeta = (await db.execute(stmt_carp)).scalars().first()
    if not carpeta:
        raise HTTPException(status_code=400, detail="Carpeta no vàlida")

    candidats = []
    if payload.ruta_origen and os.path.isdir(payload.ruta_origen):
        candidats.append(payload.ruta_origen)

    candidats.extend(
        [
            "/media/akaun/Project_1/Sevalormante_docs/planols",
            "/media/akaun/Project_1/Sevalormante_docs",
            os.path.join(
                os.getcwd(),
                "demo_docs",
                "Banc_Documents_Sevalor_Complet",
                "demo_docs",
                "05_enginyeria_obres",
            ),
            os.path.join(os.getcwd(), "demo_docs"),
            f"/docs/{empresa_id}/planols",
        ]
    )

    importats = []
    allowed_exts = {".pdf", ".dxf", ".dwg", ".geojson", ".kml", ".png", ".jpg"}

    for dir_path in candidats:
        if not os.path.exists(dir_path) or not os.path.isdir(dir_path):
            continue

        for root, _, files in os.walk(dir_path):
            for file in files:
                base_name, ext = os.path.splitext(file)
                if ext.lower() not in allowed_exts:
                    continue

                full_path = os.path.join(root, file)
                mida = os.path.getsize(full_path)
                ext_type = ext.lower().lstrip(".").upper()
                if ext_type == "JSON":
                    ext_type = "GEOJSON"

                clean_code = re.sub(r"[^\w]", "-", base_name.upper())[:15]
                codi_ref = f"PLN-{clean_code}"

                stmt_exist = select(PlanolBase).where(
                    PlanolBase.empresa_id == uuid.UUID(empresa_id),
                    PlanolBase.codi_referencia == codi_ref,
                )
                if (await db.execute(stmt_exist)).scalars().first():
                    continue

                nou = PlanolBase(
                    empresa_id=uuid.UUID(empresa_id),
                    titol=base_name.replace("_", " ").title(),
                    codi_referencia=codi_ref,
                    carpeta_id=payload.carpeta_id,
                    tipus_fitxer=ext_type,
                    fitxer_path=full_path,
                    mida_bytes=mida,
                    es_georeferenciat=True,
                    projeccio_origen="ETRS89 / UTM 31N",
                )
                db.add(nou)
                await db.flush()

                importats.append(
                    PlanolResponse(
                        id=nou.id,
                        titol=nou.titol,
                        codi_referencia=nou.codi_referencia,
                        carpeta_id=nou.carpeta_id,
                        tipus_fitxer=nou.tipus_fitxer,
                        fitxer_path=nou.fitxer_path,
                        mida_bytes=nou.mida_bytes,
                        es_georeferenciat=nou.es_georeferenciat,
                        carpeta_nom=carpeta.nom,
                        municipi=carpeta.municipi,
                    )
                )

    await db.commit()
    return importats


@router.get("/{planol_id}/fitxer")
async def descarregar_fitxer_planol(
    planol_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_db_with_tenant_context),
):
    """Serveix el fitxer del plànol per a visualització o descàrrega."""
    empresa_id = request.state.empresa_id
    if not empresa_id or empresa_id == "undefined":
        raise HTTPException(status_code=401, detail="No identificat")

    stmt = select(PlanolBase).where(
        PlanolBase.id == planol_id, PlanolBase.empresa_id == uuid.UUID(empresa_id)
    )
    planol = (await db.execute(stmt)).scalars().first()
    if not planol or not planol.fitxer_path:
        raise HTTPException(status_code=404, detail="Fitxer de plànol no trobat")

    fpath = planol.fitxer_path
    if not os.path.isabs(fpath):
        fpath = os.path.abspath(fpath)
    if not os.path.exists(fpath):
        raise HTTPException(status_code=404, detail="Fitxer de plànol no trobat al disc")

    filename = os.path.basename(fpath)
    ext = os.path.splitext(filename)[1].lower()
    media_types = {
        ".pdf": "application/pdf",
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".svg": "image/svg+xml",
        ".dxf": "application/dxf",
        ".dwg": "application/acad",
        ".geojson": "application/geo+json",
        ".json": "application/json",
        ".kml": "application/vnd.google-earth.kml+xml",
    }
    media_type = media_types.get(ext, "application/octet-stream")
    content_disposition_type = "inline" if ext in [".pdf", ".png", ".jpg", ".jpeg", ".svg"] else "attachment"
    return FileResponse(
        path=fpath,
        filename=filename,
        media_type=media_type,
        content_disposition_type=content_disposition_type,
    )


# ---------------------------------------------------------------------------
# Carpetes de plànols (Spec 010)
# ---------------------------------------------------------------------------


@router.get("/carpetes", response_model=List[CarpetaResponse])
async def llistar_carpetes(
    request: Request, db: AsyncSession = Depends(get_db_with_tenant_context)
):
    """Llista les carpetes de plànols de l'empresa (Spec 010)."""
    empresa_id = request.state.empresa_id
    if not empresa_id or empresa_id == "undefined":
        raise HTTPException(status_code=401, detail="No identificat")

    result = await db.execute(
        select(CarpetaPlanol)
        .where(CarpetaPlanol.empresa_id == uuid.UUID(empresa_id))
        .order_by(CarpetaPlanol.nom)
    )
    return result.scalars().all()


@router.post("/carpetes", response_model=CarpetaResponse, status_code=status.HTTP_201_CREATED)
async def crear_carpeta(
    request: Request, payload: CarpetaCreate, db: AsyncSession = Depends(get_db_with_tenant_context)
):
    """Crea una carpeta de plànols (Spec 010)."""
    empresa_id = request.state.empresa_id
    if not empresa_id or empresa_id == "undefined":
        raise HTTPException(status_code=401, detail="No identificat")

    nova = CarpetaPlanol(
        empresa_id=uuid.UUID(empresa_id),
        nom=payload.nom,
        categoria=payload.categoria,
        client_id=payload.client_id,
        municipi=payload.municipi,
        descripcio=payload.descripcio,
        parent_id=payload.parent_id,
    )
    db.add(nova)
    await db.commit()
    return nova


# ---------------------------------------------------------------------------
# Capes vectorials (Spec 010 — gestió de capes per plànol)
# ---------------------------------------------------------------------------


@router.get("/planols/{planol_id}/capes", response_model=List[CapaVectorialResponse])
async def llistar_capes_planol(
    request: Request, planol_id: uuid.UUID, db: AsyncSession = Depends(get_db_with_tenant_context)
):
    """Llista les capes vectorials d'un plànol (Spec 010)."""
    empresa_id = request.state.empresa_id
    if not empresa_id or empresa_id == "undefined":
        raise HTTPException(status_code=401, detail="No identificat")

    result = await db.execute(
        select(CapaVectorial).where(
            CapaVectorial.planol_base_id == planol_id,
            CapaVectorial.empresa_id == uuid.UUID(empresa_id),
        )
    )
    return result.scalars().all()


@router.post(
    "/planols/{planol_id}/capes",
    response_model=CapaVectorialResponse,
    status_code=status.HTTP_201_CREATED,
)
async def crear_capa_planol(
    request: Request,
    planol_id: uuid.UUID,
    payload: CapaVectorialCreate,
    db: AsyncSession = Depends(get_db_with_tenant_context),
):
    """Crea una capa vectorial sobre un plànol (Spec 010)."""
    empresa_id = request.state.empresa_id
    if not empresa_id or empresa_id == "undefined":
        raise HTTPException(status_code=401, detail="No identificat")

    # Verificar que el plànol pertany a l'empresa
    planol_res = await db.execute(
        select(PlanolBase).where(
            PlanolBase.id == planol_id,
            PlanolBase.empresa_id == uuid.UUID(empresa_id),
        )
    )
    if not planol_res.scalars().first():
        raise HTTPException(status_code=404, detail="Plànol no trobat")

    nova_capa = CapaVectorial(
        empresa_id=uuid.UUID(empresa_id),
        planol_base_id=planol_id,
        nom=payload.nom,
        disciplina=payload.disciplina,
        ordre_treball_id=payload.ordre_treball_id,
        color_hex=payload.color_hex,
        gruix_linia=payload.gruix_linia,
        opacitat_percent=payload.opacitat_percent,
        geometries_geojson=payload.geometries_geojson,
        version_id=1,
    )
    db.add(nova_capa)
    await db.commit()
    return nova_capa


class CapaVectorialUpdate(BaseModel):
    nom: Optional[str] = Field(None, max_length=100)
    color_hex: Optional[str] = Field(None, max_length=10)
    gruix_linia: Optional[int] = None
    opacitat_percent: Optional[int] = None
    visible: Optional[bool] = None
    geometries_geojson: Optional[dict] = None


@router.put("/planols/{planol_id}/capes/{capa_id}", response_model=CapaVectorialResponse)
async def editar_capa_planol(
    request: Request,
    planol_id: uuid.UUID,
    capa_id: uuid.UUID,
    payload: CapaVectorialUpdate,
    db: AsyncSession = Depends(get_db_with_tenant_context),
):
    """Edita una capa vectorial d'un plànol (Spec 010). Les capes immutables no es poden editar."""
    empresa_id = request.state.empresa_id
    if not empresa_id or empresa_id == "undefined":
        raise HTTPException(status_code=401, detail="No identificat")

    capa_res = await db.execute(
        select(CapaVectorial).where(
            CapaVectorial.id == capa_id,
            CapaVectorial.planol_base_id == planol_id,
            CapaVectorial.empresa_id == uuid.UUID(empresa_id),
        )
    )
    capa = capa_res.scalars().first()
    if not capa:
        raise HTTPException(status_code=404, detail="Capa no trobada")

    if capa.es_immutable:
        raise HTTPException(status_code=403, detail="La capa és immutable i no es pot modificar")

    if payload.nom is not None:
        capa.nom = payload.nom
    if payload.color_hex is not None:
        capa.color_hex = payload.color_hex
    if payload.gruix_linia is not None:
        capa.gruix_linia = payload.gruix_linia
    if payload.opacitat_percent is not None:
        capa.opacitat_percent = payload.opacitat_percent
    if payload.visible is not None:
        capa.visible = payload.visible
    if payload.geometries_geojson is not None:
        capa.geometries_geojson = payload.geometries_geojson

    capa.version_id += 1
    await db.commit()
    return capa


@router.delete("/planols/{planol_id}/capes/{capa_id}", status_code=status.HTTP_204_NO_CONTENT)
async def eliminar_capa_planol(
    request: Request,
    planol_id: uuid.UUID,
    capa_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_with_tenant_context),
):
    """Elimina una capa vectorial (Spec 010). Les immutables no es poden eliminar."""
    empresa_id = request.state.empresa_id
    if not empresa_id or empresa_id == "undefined":
        raise HTTPException(status_code=401, detail="No identificat")

    capa_res = await db.execute(
        select(CapaVectorial).where(
            CapaVectorial.id == capa_id,
            CapaVectorial.planol_base_id == planol_id,
            CapaVectorial.empresa_id == uuid.UUID(empresa_id),
        )
    )
    capa = capa_res.scalars().first()
    if not capa:
        raise HTTPException(status_code=404, detail="Capa no trobada")

    if capa.es_immutable:
        raise HTTPException(status_code=403, detail="La capa és immutable i no es pot eliminar")

    await db.delete(capa)
    await db.commit()
    return None


@router.post("/{planol_id}/exportar-pdf", status_code=status.HTTP_202_ACCEPTED)
async def exportar_planol_pdf(
    planol_id: uuid.UUID, request: Request, db: AsyncSession = Depends(get_db_with_tenant_context)
):
    empresa_id = request.state.empresa_id
    stmt = select(PlanolBase).where(
        PlanolBase.id == planol_id, PlanolBase.empresa_id == uuid.UUID(empresa_id)
    )
    planol = (await db.execute(stmt)).scalars().first()
    if not planol:
        raise HTTPException(status_code=404)

    # Llençar a Celery
    generar_informe_planol_pdf.delay(str(planol_id), str(empresa_id))

    return {"estat": "EN_PROCES", "missatge": "El PDF s'està generant a Celery"}


class CapaAnotacioCreate(BaseModel):
    ordre_treball_id: uuid.UUID
    nom_capa: str = Field(..., max_length=100)
    fitxer_vectorial_path: str = Field(..., max_length=500)
    operari_id: Optional[uuid.UUID] = None
    estat_capa: str = Field("ACTIVA", max_length=30)


class CapaAnotacioResponse(BaseModel):
    id: uuid.UUID
    ordre_treball_id: uuid.UUID
    nom_capa: str
    fitxer_vectorial_path: str
    operari_id: Optional[uuid.UUID]
    estat_capa: str


@router.get("/anotacions", response_model=List[CapaAnotacioResponse])
async def llistar_anotacions(
    request: Request,
    ordre_treball_id: Optional[uuid.UUID] = None,
    db: AsyncSession = Depends(get_db_with_tenant_context),
):
    """Llista les capes d'anotacions."""
    empresa_id = request.state.empresa_id
    if not empresa_id or empresa_id == "undefined":
        raise HTTPException(status_code=401, detail="No identificat")

    stmt = select(CapaAnotacio).where(CapaAnotacio.empresa_id == uuid.UUID(empresa_id))
    if ordre_treball_id:
        stmt = stmt.where(CapaAnotacio.ordre_treball_id == ordre_treball_id)

    result = await db.execute(stmt)
    return result.scalars().all()


@router.post(
    "/anotacions", response_model=CapaAnotacioResponse, status_code=status.HTTP_201_CREATED
)
async def crear_anotacio(
    request: Request,
    payload: CapaAnotacioCreate,
    db: AsyncSession = Depends(get_db_with_tenant_context),
):
    """Crea una nova capa d'anotació."""
    empresa_id = request.state.empresa_id
    if not empresa_id or empresa_id == "undefined":
        raise HTTPException(status_code=401, detail="No identificat")

    from app.models.models import OrdreTreball

    stmt_ot = select(OrdreTreball.id).where(
        OrdreTreball.id == payload.ordre_treball_id,
        OrdreTreball.empresa_id == uuid.UUID(empresa_id),
    )
    if (await db.execute(stmt_ot)).scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail="Ordre de treball no trobada")

    nova_anotacio = CapaAnotacio(
        empresa_id=uuid.UUID(empresa_id),
        ordre_treball_id=payload.ordre_treball_id,
        nom_capa=payload.nom_capa,
        fitxer_vectorial_path=payload.fitxer_vectorial_path,
        operari_id=payload.operari_id,
        estat_capa=payload.estat_capa,
    )
    db.add(nova_anotacio)
    await db.commit()
    return nova_anotacio
