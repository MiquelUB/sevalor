import uuid
from typing import List, Optional

from app.core.database import get_db_with_tenant_context
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import CapaAnotacio, OrdreTreball

router = APIRouter(tags=["Gestió - Anotacions"])


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

    # Check if ordre_treball exists for this empresa
    stmt_ot = select(OrdreTreball).where(
        OrdreTreball.id == payload.ordre_treball_id,
        OrdreTreball.empresa_id == uuid.UUID(empresa_id),
    )
    result_ot = await db.execute(stmt_ot)
    ot = result_ot.scalar_one_or_none()
    if not ot:
        raise HTTPException(
            status_code=404, detail="Ordre de treball no trobada o no pertany a l'empresa"
        )

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

    # Zero Mock & No Refresh (RLS)
    # Instead of db.refresh, we just return the object because Postgres generates the ID
    # But wait, SQLAlchemy doesn't populate generated IDs automatically unless autoflush is true,
    # actually await db.commit() expires the instance.
    # The normative says: "Return object without db.refresh per RLS".
    # We should query it again if we need to, but wait, returning `nova_anotacio` might raise DetachedInstanceError.

    stmt = (
        select(CapaAnotacio)
        .where(
            CapaAnotacio.ordre_treball_id == payload.ordre_treball_id,
            CapaAnotacio.nom_capa == payload.nom_capa,
        )
        .order_by(CapaAnotacio.creat_el.desc())  # type: ignore
        .limit(1)
    )

    res = await db.execute(stmt)
    return res.scalar_one()
