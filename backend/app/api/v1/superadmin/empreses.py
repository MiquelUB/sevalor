import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db_with_tenant_context
from app.core.security import require_roles
from app.models.models import Empresa

logger = logging.getLogger("superadmin.empreses")

router = APIRouter(prefix="/superadmin/empreses", tags=["Superadmin", "Empreses Configuració Camaleó"])

class UpdateCamaleoConfigRequest(BaseModel):
    primari_hsl: Optional[str] = Field(None, max_length=30)
    secundari_hsl: Optional[str] = Field(None, max_length=30)
    accent_hsl: Optional[str] = Field(None, max_length=30)
    logotip_path: Optional[str] = Field(None, max_length=500)
    favicon_path: Optional[str] = Field(None, max_length=500)
    domini_custom: Optional[str] = Field(None, max_length=100)

@router.put("/{empresa_id}/camaleo", response_model=Dict[str, Any])
async def update_camaleo_config(
    empresa_id: str,
    payload: UpdateCamaleoConfigRequest,
    db: AsyncSession = Depends(get_db_with_tenant_context),
    claims: Dict[str, Any] = Depends(require_roles(["SUPERADMIN", "BOSS"])),
) -> Dict[str, Any]:
    try:
        emp_uuid = uuid.UUID(empresa_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="UUID invàlid.")

    # BOSS role validation: make sure BOSS is modifying their own company
    rol = claims.get("rol", "")
    token_emp_id = claims.get("empresa_id")
    if rol == "BOSS":
        if str(token_emp_id) != str(empresa_id):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Un BOSS només pot modificar la configuració de la seva pròpia empresa.")

    emp_res = await db.execute(select(Empresa).where(Empresa.id == emp_uuid))
    empresa = emp_res.scalars().first()
    if not empresa:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Empresa no trobada.")

    if payload.primari_hsl is not None:
        empresa.primari_hsl = payload.primari_hsl
    if payload.secundari_hsl is not None:
        empresa.secundari_hsl = payload.secundari_hsl
    if payload.accent_hsl is not None:
        empresa.accent_hsl = payload.accent_hsl
    if payload.logotip_path is not None:
        empresa.logotip_path = payload.logotip_path
    if payload.favicon_path is not None:
        empresa.favicon_path = payload.favicon_path
    if payload.domini_custom is not None:
        empresa.domini_custom = payload.domini_custom

    empresa.updated_at = datetime.now(timezone.utc)
    await db.commit()

    return {
        "status": "OK",
        "empresa_id": empresa_id,
        "configuracio_actualitzada": {
            "primari_hsl": empresa.primari_hsl,
            "secundari_hsl": empresa.secundari_hsl,
            "accent_hsl": empresa.accent_hsl,
            "logotip_path": empresa.logotip_path,
            "favicon_path": empresa.favicon_path,
            "domini_custom": getattr(empresa, 'domini_custom', None),
        }
    }
