import os
import uuid
from typing import Any, Dict, List

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db_with_tenant_context
from app.core.network_utils import resolve_effective_node_url
from app.core.security import require_roles
from app.models.models import CapaAnotacio, CapaVectorial, Empresa, PlanolBase
from app.services.sovereign_storage import SovereignStorageGateway

router = APIRouter(
    prefix="/operari/planols",
    tags=["Operari PWA Planols"],
    dependencies=[
        Depends(require_roles(["OPERARI", "CAPATAZ", "CAP_DE_COLLA", "BOSS", "SUPERADMIN"]))
    ],
)


class CapaVectorialCreate(BaseModel):
    nom: str
    disciplina: str = "OBRA_CIVIL"
    color_hex: str = "#0284c7"
    gruix_linia: int = 3
    es_tancada: bool = False
    visible: bool = True
    dades_geojson: Dict[str, Any] | None = None
    geometries_geojson: Dict[str, Any] | None = None


class CapaVectorialResponse(BaseModel):
    id: uuid.UUID
    nom: str
    disciplina: str
    color_hex: str
    gruix_linia: int
    es_tancada: bool
    visible: bool
    dades_geojson: Dict[str, Any]


@router.get("/disponibles")
async def llistar_planols_disponibles_operari(
    request: Request,
    db: AsyncSession = Depends(get_db_with_tenant_context),
):
    """Llista els plànols base disponibles per a l'operari."""
    empresa_id = request.state.empresa_id
    if not empresa_id or empresa_id == "undefined":
        raise HTTPException(status_code=401, detail="Context d'empresa no trobat")

    result = await db.execute(
        select(PlanolBase).where(PlanolBase.empresa_id == uuid.UUID(empresa_id))
    )
    planols = result.scalars().all()
    return [
        {
            "id": str(p.id),
            "titol": p.titol,
            "codi_referencia": p.codi_referencia,
            "tipus_fitxer": p.tipus_fitxer,
            "es_georeferenciat": p.es_georeferenciat,
            "projeccio": p.projeccio,
        }
        for p in planols
    ]


@router.post(
    "/{planol_id}/capes", response_model=CapaVectorialResponse, status_code=status.HTTP_201_CREATED
)
async def crear_capa_operari(
    planol_id: uuid.UUID,
    payload: CapaVectorialCreate,
    request: Request,
    db: AsyncSession = Depends(get_db_with_tenant_context),
) -> CapaVectorialResponse:
    """Operari crea una capa sobre un plànol (Spec 017 RF-13.1)."""
    empresa_id = request.state.empresa_id
    if not empresa_id or empresa_id == "undefined":
        raise HTTPException(status_code=401, detail="Context d'empresa no trobat")

    planol_res = await db.execute(
        select(PlanolBase).where(
            PlanolBase.id == planol_id, PlanolBase.empresa_id == uuid.UUID(empresa_id)
        )
    )
    if not planol_res.scalars().first():
        raise HTTPException(status_code=404, detail="Plànol no trobat")

    geojson = (
        payload.geometries_geojson
        or payload.dades_geojson
        or {"type": "FeatureCollection", "features": []}
    )

    nova_capa = CapaVectorial(
        empresa_id=uuid.UUID(empresa_id),
        planol_base_id=planol_id,
        nom=payload.nom,
        disciplina=payload.disciplina or "OBRA_CIVIL",
        es_immutable=payload.es_tancada,
        color_hex=payload.color_hex or "#0284c7",
        gruix_linia=payload.gruix_linia or 3,
        opacitat_percent=100,
        visible=payload.visible,
        geometries_geojson=geojson,
        version_id=1,
    )
    db.add(nova_capa)
    await db.commit()

    return CapaVectorialResponse(
        id=nova_capa.id,
        nom=nova_capa.nom,
        disciplina=nova_capa.disciplina,
        color_hex=nova_capa.color_hex,
        gruix_linia=nova_capa.gruix_linia,
        es_tancada=nova_capa.es_immutable,
        visible=nova_capa.visible,
        dades_geojson=nova_capa.geometries_geojson,
    )


@router.get("/{planol_id}/capes")
async def llistar_capes_operari_per_planol(
    planol_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_db_with_tenant_context),
):
    """Llista les capes vectorials d'un plànol per a la PWA operari."""
    empresa_id = request.state.empresa_id
    if not empresa_id or empresa_id == "undefined":
        raise HTTPException(status_code=401, detail="Context d'empresa no trobat")

    result = await db.execute(
        select(CapaVectorial).where(
            CapaVectorial.planol_base_id == planol_id,
            CapaVectorial.empresa_id == uuid.UUID(empresa_id),
        )
    )
    return result.scalars().all()


@router.put("/{planol_id}/capes/{capa_id}")
async def editar_capa_operari_per_planol(
    planol_id: uuid.UUID,
    capa_id: uuid.UUID,
    request: Request,
    payload: Dict[str, Any],
    db: AsyncSession = Depends(get_db_with_tenant_context),
):
    """Edita una capa vectorial d'un plànol des de la PWA operari."""
    empresa_id = request.state.empresa_id
    if not empresa_id or empresa_id == "undefined":
        raise HTTPException(status_code=401, detail="Context d'empresa no trobat")

    stmt = select(CapaVectorial).where(
        CapaVectorial.id == capa_id,
        CapaVectorial.planol_base_id == planol_id,
        CapaVectorial.empresa_id == uuid.UUID(empresa_id),
    )
    capa = (await db.execute(stmt)).scalars().first()
    if not capa:
        raise HTTPException(status_code=404, detail="Capa no trobada")
    if capa.es_immutable:
        raise HTTPException(status_code=403, detail="La capa és immutable")

    if "nom" in payload:
        capa.nom = str(payload["nom"])
    if "geometries_geojson" in payload:
        capa.geometries_geojson = payload["geometries_geojson"]
    elif "dades_geojson" in payload:
        capa.geometries_geojson = payload["dades_geojson"]
    if "visible" in payload:
        capa.visible = bool(payload["visible"])

    capa.version_id += 1
    await db.commit()
    return capa


class CapaAnotacioOperariResponse(BaseModel):
    id: uuid.UUID
    nom: str
    es_tancada: bool = False
    visible: bool = True
    pins: List[Dict[str, Any]] = []


@router.get("", response_model=List[CapaAnotacioOperariResponse])
async def llistar_capes_operari(
    request: Request,
    db: AsyncSession = Depends(get_db_with_tenant_context),
) -> List[CapaAnotacioOperariResponse]:
    """Llista les capes d'anotació vectorials de l'empresa per a la PWA operari."""
    empresa_id = request.state.empresa_id
    if not empresa_id or empresa_id == "undefined":
        raise HTTPException(status_code=401, detail="Context d'empresa no trobat")

    stmt = select(CapaAnotacio).where(CapaAnotacio.empresa_id == uuid.UUID(empresa_id))
    res = await db.execute(stmt)
    capes = res.scalars().all()

    return [
        CapaAnotacioOperariResponse(
            id=c.id,
            nom=c.nom_capa,
            es_tancada=(c.estat_capa == "TANCADA"),
            visible=True,
            pins=[],
        )
        for c in capes
    ]


@router.get("/{planol_id}/fitxer")
async def descarregar_fitxer_planol_operari(
    planol_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_db_with_tenant_context),
):
    """Serveix el fitxer del plànol des del disc dur del client per a la PWA d'operari."""
    empresa_id = request.state.empresa_id
    if not empresa_id or empresa_id == "undefined":
        raise HTTPException(status_code=401, detail="Context d'empresa no trobat")

    stmt = select(PlanolBase).where(
        PlanolBase.id == planol_id, PlanolBase.empresa_id == uuid.UUID(empresa_id)
    )
    planol = (await db.execute(stmt)).scalars().first()
    if not planol or not planol.fitxer_path:
        raise HTTPException(status_code=404, detail="Fitxer de plànol no trobat")

    filename = os.path.basename(planol.fitxer_path)
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
    content_disposition_type = (
        "inline" if ext in [".pdf", ".png", ".jpg", ".jpeg", ".svg"] else "attachment"
    )
    return await SovereignStorageGateway.servir_fitxer(
        db=db,
        empresa_id=empresa_id,
        fitxer_path=planol.fitxer_path,
        media_type=media_type,
        disposition=content_disposition_type,
    )


@router.get("/arxiu-extern", response_model=Dict[str, Any])
async def consultar_planol_arxiu_extern_empresa(
    request: Request,
    referencia: str | None = None,
    cerca: str | None = None,
    db: AsyncSession = Depends(get_db_with_tenant_context),
) -> Any:
    """Consulta un plànol o document tècnic extra al disc dur o ordinador local de l'empresa.

    El servidor central de Sevalor només emmagatzema les feines actives del dia. Si l'ordinador central
    de l'empresa (node_ia_url o disc_dur_url) està apagat o desconnectat, retorna HTTP 503 amb codi NODE_EMPRESA_OFFLINE.
    """
    ref_query = (referencia or cerca or "general").strip()
    empresa_id = request.state.empresa_id
    if not empresa_id or empresa_id == "undefined":
        raise HTTPException(status_code=401, detail="Context d'empresa no trobat")

    emp_res = await db.execute(select(Empresa).where(Empresa.id == uuid.UUID(empresa_id)))
    emp = emp_res.scalars().first()

    msg_offline = (
        "L'ordinador central de la teva empresa està apagat o desconnectat. "
        "Tens cobertura mòbil correcta, però aquest plànol extra viu al disc dur de l'oficina. "
        "Avisa a administració perquè encenguin l'equip central."
    )

    if not emp or not emp.node_ia_actiu or not (emp.node_ia_url or emp.disc_dur_url):
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "code": "NODE_EMPRESA_OFFLINE",
                "detail": {
                    "code": "NODE_EMPRESA_OFFLINE",
                    "message": msg_offline,
                },
            },
        )

    remote_url = emp.node_ia_url or emp.disc_dur_url
    if remote_url and (remote_url.startswith("http://") or remote_url.startswith("https://")):
        raw_url = remote_url.rstrip("/")
        effective_url = resolve_effective_node_url(raw_url) or raw_url
        base_url = effective_url.rstrip("/")
        try:
            async with httpx.AsyncClient(timeout=2.0) as client:
                for cand in [
                    f"{base_url}/docs/planols/{ref_query}",
                    f"{base_url}/fitxers/05_planols_i_enginyeria/{ref_query}",
                ]:
                    resp = await client.get(cand)
                    if resp.status_code == 200:
                        return resp.json()
        except Exception:
            pass

        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "code": "NODE_EMPRESA_OFFLINE",
                "detail": {
                    "code": "NODE_EMPRESA_OFFLINE",
                    "message": msg_offline,
                },
            },
        )

    # Si té disc local físic muntat (/media/..., /mnt/...)
    disc_local = emp.disc_dur_url
    if disc_local and (
        disc_local.startswith("/") or (len(disc_local) > 2 and disc_local[1] == ":")
    ):
        import glob

        candidats = glob.glob(f"{disc_local}/**/{ref_query}*", recursive=True)
        if candidats:
            f = candidats[0]
            return {
                "status": "ok",
                "fitxer": os.path.basename(f),
                "ruta": f,
                "mode": "LOCAL_FS",
            }
        return {
            "status": "ok",
            "items": os.listdir(disc_local)[:10] if os.path.exists(disc_local) else [],
            "mode": "LOCAL_FS",
        }

    return JSONResponse(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        content={
            "code": "NODE_EMPRESA_OFFLINE",
            "detail": {
                "code": "NODE_EMPRESA_OFFLINE",
                "message": msg_offline,
            },
        },
    )


planols_operari_router = APIRouter(
    prefix="/planols",
    tags=["Planols Operari Direct"],
    dependencies=[
        Depends(require_roles(["OPERARI", "CAPATAZ", "CAP_DE_COLLA", "BOSS", "SUPERADMIN"]))
    ],
)


@planols_operari_router.get("/operari", response_model=List[CapaAnotacioOperariResponse])
async def llistar_planols_operari_direct(
    request: Request,
    db: AsyncSession = Depends(get_db_with_tenant_context),
) -> List[CapaAnotacioOperariResponse]:
    """Endpoint directe /api/v1/planols/operari per a compatibilitat PWA."""
    return await llistar_capes_operari(request, db)
