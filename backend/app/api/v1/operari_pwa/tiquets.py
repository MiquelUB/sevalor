import uuid
from typing import List, Optional
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel, Field
import jwt

from app.core.config import settings
from app.core.db import get_db_with_tenant_context
from app.core.security import require_roles
from app.models.models import TiquetCarburant, Vehicle

router = APIRouter(
    prefix="/operari",
    tags=["Operari Tiquets i Despeses"],
    dependencies=[Depends(require_roles(["OPERARI", "CAPATAZ", "CAP_DE_COLLA", "BOSS", "SUPERADMIN"]))],
)

class TiquetCarburantCreate(BaseModel):
    vehicle_id: Optional[uuid.UUID] = None
    tiquet_foto_path: str = Field("/docs/tiquets/default_ticket.webp", max_length=500)
    odometre_foto_path: str = Field("/docs/tiquets/default_odometre.webp", max_length=500)
    litres: float = Field(..., gt=0)
    import_euros: float = Field(..., gt=0)
    odometre_valor: int = Field(..., ge=0)

class TiquetCarburantResponse(BaseModel):
    id: uuid.UUID
    vehicle_id: Optional[uuid.UUID]
    operari_id: uuid.UUID
    tiquet_foto_path: str
    odometre_foto_path: str
    litres: float
    import_euros: float
    odometre_valor: int
    estat_ocr: str
    created_at: Optional[datetime] = None

@router.get("/tiquets", response_model=List[TiquetCarburantResponse])
async def llistar_tiquets_operari(
    request: Request,
    db: AsyncSession = Depends(get_db_with_tenant_context)
):
    empresa_id = request.state.empresa_id
    if not empresa_id:
        raise HTTPException(status_code=401, detail="Tenant context missing")

    auth_header = request.headers.get("Authorization")
    if not auth_header:
        raise HTTPException(status_code=401, detail="Authorization missing")
    token = auth_header.split(" ")[1]
    decoded = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM], options={"verify_aud": False})
    usuari_id = decoded.get("sub")

    stmt = select(TiquetCarburant).where(
        TiquetCarburant.empresa_id == uuid.UUID(empresa_id),
        TiquetCarburant.operari_id == uuid.UUID(usuari_id)
    ).order_by(TiquetCarburant.created_at.desc())

    result = await db.execute(stmt)
    items = result.scalars().all()

    return [
        TiquetCarburantResponse(
            id=t.id,
            vehicle_id=t.vehicle_id,
            operari_id=t.operari_id,
            tiquet_foto_path=t.tiquet_foto_path,
            odometre_foto_path=t.odometre_foto_path,
            litres=float(t.litres),
            import_euros=float(t.import_),
            odometre_valor=t.odometre_valor,
            estat_ocr=t.estat_ocr,
            created_at=t.created_at,
        )
        for t in items
    ]

@router.post("/tiquets", response_model=TiquetCarburantResponse, status_code=status.HTTP_201_CREATED)
async def registrar_tiquet_carburant(
    request: Request,
    payload: TiquetCarburantCreate,
    db: AsyncSession = Depends(get_db_with_tenant_context)
):
    empresa_id = request.state.empresa_id
    if not empresa_id:
        raise HTTPException(status_code=401, detail="Tenant context missing")

    auth_header = request.headers.get("Authorization")
    if not auth_header:
        raise HTTPException(status_code=401, detail="Authorization missing")
    token = auth_header.split(" ")[1]
    decoded = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM], options={"verify_aud": False})
    usuari_id = decoded.get("sub")

    # Si no es passa vehicle_id, buscar o assignar el primer vehicle del tenant
    v_id = payload.vehicle_id
    if not v_id:
        v_res = await db.execute(select(Vehicle).where(Vehicle.empresa_id == uuid.UUID(empresa_id)))
        v = v_res.scalars().first()
        if v:
            v_id = v.id
        else:
            # Crear vehicle dummy per defecte del tenant si no n'hi ha cap
            nou_v = Vehicle(
                empresa_id=uuid.UUID(empresa_id),
                matricula="SENSE-VEHICLE",
                marca="Flota",
                model="Defecte",
                estat="OPERATIU"
            )
            db.add(nou_v)
            await db.flush()
            v_id = nou_v.id

    nou_tiquet = TiquetCarburant(
        empresa_id=uuid.UUID(empresa_id),
        operari_id=uuid.UUID(usuari_id),
        vehicle_id=v_id,
        tiquet_foto_path=payload.tiquet_foto_path,
        odometre_foto_path=payload.odometre_foto_path,
        litres=payload.litres,
        import_=payload.import_euros,
        odometre_valor=payload.odometre_valor,
        estat_ocr="PENDENT_AUDITORIA",
    )

    db.add(nou_tiquet)
    await db.commit()
    await db.refresh(nou_tiquet)

    return TiquetCarburantResponse(
        id=nou_tiquet.id,
        vehicle_id=nou_tiquet.vehicle_id,
        operari_id=nou_tiquet.operari_id,
        tiquet_foto_path=nou_tiquet.tiquet_foto_path,
        odometre_foto_path=nou_tiquet.odometre_foto_path,
        litres=float(nou_tiquet.litres),
        import_euros=float(nou_tiquet.import_),
        odometre_valor=nou_tiquet.odometre_valor,
        estat_ocr=nou_tiquet.estat_ocr,
        created_at=nou_tiquet.created_at,
    )
