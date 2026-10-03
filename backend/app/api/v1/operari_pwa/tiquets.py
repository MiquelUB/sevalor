import os
import secrets
import uuid
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db_with_tenant_context
from app.core.security import get_current_user_claims, require_roles
from app.models.models import TiquetCarburant, Vehicle

router = APIRouter(
    prefix="/operari",
    tags=["Operari Tiquets i Despeses"],
    dependencies=[Depends(require_roles(["OPERARI", "CAPATAZ", "CAP_DE_COLLA", "BOSS", "SUPERADMIN"]))],
)

class TiquetCarburantCreate(BaseModel):
    vehicle_id: Optional[uuid.UUID] = None
    tiquet_foto_path: str = Field(..., max_length=500)
    odometre_foto_path: Optional[str] = Field(None, max_length=500)
    litres: Optional[float] = None
    import_euros: Optional[float] = None
    odometre_valor: Optional[int] = None

class TiquetCarburantResponse(BaseModel):
    id: uuid.UUID
    vehicle_id: Optional[uuid.UUID]
    operari_id: uuid.UUID
    tiquet_foto_path: str
    odometre_foto_path: Optional[str]
    litres: Optional[float]
    import_euros: Optional[float]
    odometre_valor: Optional[int]
    estat_ocr: str
    created_at: Optional[datetime] = None

@router.get("/tiquets", response_model=List[TiquetCarburantResponse])
async def llistar_tiquets_operari(
    request: Request,
    db: AsyncSession = Depends(get_db_with_tenant_context)
):
    empresa_id = request.state.empresa_id
    if not empresa_id or empresa_id == 'undefined':
        raise HTTPException(status_code=401, detail="Tenant context missing")

    claims = get_current_user_claims(request)
    usuari_id = claims.get("sub")

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
            litres=float(t.litres) if t.litres is not None else None,
            import_euros=float(t.import_) if t.import_ is not None else None,
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
    if not empresa_id or empresa_id == 'undefined':
        raise HTTPException(status_code=401, detail="Tenant context missing")

    claims = get_current_user_claims(request)
    usuari_id = claims.get("sub")

    # Si no es passa vehicle_id, buscar o assignar el primer vehicle del tenant
    v_id = payload.vehicle_id
    if not v_id:
        v_res = await db.execute(select(Vehicle).where(Vehicle.empresa_id == uuid.UUID(empresa_id)))
        v = v_res.scalars().first()
        if v:
            v_id = v.id
        else:
            raise HTTPException(status_code=400, detail="No hi ha cap vehicle registrat al tenant. Doneu-ne d'alta un primer.")

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

    return TiquetCarburantResponse(
        id=nou_tiquet.id,
        vehicle_id=nou_tiquet.vehicle_id,
        operari_id=nou_tiquet.operari_id,
        tiquet_foto_path=nou_tiquet.tiquet_foto_path,
        odometre_foto_path=nou_tiquet.odometre_foto_path,
        litres=float(nou_tiquet.litres) if nou_tiquet.litres is not None else None,
        import_euros=float(nou_tiquet.import_) if nou_tiquet.import_ is not None else None,
        odometre_valor=nou_tiquet.odometre_valor,
        estat_ocr=nou_tiquet.estat_ocr,
        created_at=nou_tiquet.created_at,
    )



@router.post("/tiquets/ocr", response_model=dict, status_code=status.HTTP_200_OK)
async def pujar_tiquet_ocr(
    request: Request,
    file: UploadFile = File(...),
    vehicle_id: Optional[str] = Form(None),
    db: AsyncSession = Depends(get_db_with_tenant_context)
):
    """(Spec 018) Rep una imatge de tiquet, simula extracció OCR i ho desa a DB."""
    empresa_id = request.state.empresa_id
    if not empresa_id or empresa_id == 'undefined':
        raise HTTPException(status_code=401, detail="Tenant context missing")

    claims = get_current_user_claims(request)
    usuari_id = claims.get("sub")

    v_id = None
    if vehicle_id:
        try:
            v_id = uuid.UUID(vehicle_id)
        except ValueError:
            pass

    if not v_id:
        v_res = await db.execute(select(Vehicle).where(Vehicle.empresa_id == uuid.UUID(empresa_id)))
        v = v_res.scalars().first()
        if v:
            v_id = v.id
        else:
            raise HTTPException(status_code=400, detail="No hi ha cap vehicle registrat al tenant. Doneu-ne d'alta un primer.")

    # Desa el fitxer (Simulació guardat sobiran)
    base_dir = os.getenv("SOVEREIGN_DATA_PATH", "/tmp/data")
    save_dir = f"{base_dir}/{empresa_id}/docs/tiquets"
    os.makedirs(save_dir, exist_ok=True)

    file_ext = file.filename.split(".")[-1] if file.filename else "jpg"
    safe_name = f"ocr_{secrets.token_hex(8)}.{file_ext}"
    file_path = f"{save_dir}/{safe_name}"

    file_bytes = await file.read()
    with open(file_path, "wb") as f:
        f.write(file_bytes)

    from app.services.ocr_service import processar_tiquet_ocr
    ocr_result = await processar_tiquet_ocr(file_bytes)

    nou_tiquet = TiquetCarburant(
        empresa_id=uuid.UUID(empresa_id),
        operari_id=uuid.UUID(usuari_id),
        vehicle_id=v_id,
        tiquet_foto_path=file_path,
        odometre_foto_path=None,
        litres=ocr_result.get("litres"),
        import_=ocr_result.get("import_euros"),
        odometre_valor=None,
        estat_ocr=ocr_result.get("status", "PENDENT_AUDITORIA"),
    )

    db.add(nou_tiquet)
    await db.commit()

    return {
        "status": "OK",
        "id": str(nou_tiquet.id),
        "litres_extrets": nou_tiquet.litres,
        "import_extret": nou_tiquet.import_,
        "odometre_valor": nou_tiquet.odometre_valor,
        "estat_ocr": nou_tiquet.estat_ocr,
        "missatge": "Tiquet pujat amb processament OCR automàtic."
    }
