import uuid
from typing import Any, Dict, List

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db_with_tenant_context
from app.core.security import require_roles
from app.models.models import CapaAnotacio, CapaVectorial, Empresa, PlanolBase

router = APIRouter(
    prefix="/operari/planols",
    tags=["Operari PWA Planols"],
    dependencies=[
        Depends(require_roles(["OPERARI", "CAPATAZ", "CAP_DE_COLLA", "BOSS", "SUPERADMIN"]))
    ],
)


class CapaVectorialCreate(BaseModel):
    nom: str
    es_tancada: bool = False
    visible: bool = True
    dades_geojson: Dict[str, Any]


class CapaVectorialResponse(BaseModel):
    id: uuid.UUID
    nom: str
    es_tancada: bool
    dades_geojson: Dict[str, Any]


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

    planol_res = await db.execute(
        select(PlanolBase).where(
            PlanolBase.id == planol_id, PlanolBase.empresa_id == uuid.UUID(empresa_id)
        )
    )
    if not planol_res.scalars().first():
        raise HTTPException(status_code=404, detail="Plànol no trobat")

    nova_capa = CapaVectorial(
        empresa_id=uuid.UUID(empresa_id),
        planol_id=planol_id,
        nom=payload.nom,
        es_tancada=payload.es_tancada,
        dades_geojson=payload.dades_geojson,
    )
    db.add(nova_capa)
    await db.commit()

    return CapaVectorialResponse(
        id=nova_capa.id,
        nom=nova_capa.nom,
        es_tancada=nova_capa.es_tancada,  # type: ignore
        dades_geojson=nova_capa.dades_geojson,  # type: ignore
    )


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


@router.get("/arxiu-extern", response_model=Dict[str, Any])
async def consultar_planol_arxiu_extern_empresa(
    request: Request,
    referencia: str | None = None,
    cerca: str | None = None,
    db: AsyncSession = Depends(get_db_with_tenant_context),
) -> Any:
    """Consulta un plànol o document tècnic extra (ex: caldera no inclosa a l'OT d'avui) al disc local de l'empresa.

    El servidor de Sevalor només emmagatzema les feines actives del dia. Si l'ordinador central de
    l'empresa (node_ia_url) està apagat o desconnectat, retorna HTTP 503 amb codi NODE_EMPRESA_OFFLINE.
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

    if not emp or not emp.node_ia_actiu or not emp.node_ia_url:
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

    base_url = emp.node_ia_url.rstrip("/")
    if not base_url.startswith("http"):
        base_url = f"http://{base_url}"

    try:
        async with httpx.AsyncClient(timeout=2.0) as client:
            resp = await client.get(f"{base_url}/docs/planols/{ref_query}")
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

