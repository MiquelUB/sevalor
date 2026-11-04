"""Endpoints per al Copilot de Camp de l'Operari (/operari/copilot — PWA)."""

import uuid
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db_with_tenant_context
from app.core.security import get_current_user_claims, require_roles
from app.models.models import Empresa
from app.services.subagents.dispatcher import copilot_dispatcher

router = APIRouter(
    prefix="/operari/copilot",
    tags=["Operari Copilot de Camp"],
    dependencies=[
        Depends(require_roles(["OPERARI", "CAPATAZ", "CAP_DE_COLLA", "BOSS", "ENGINYER"]))
    ],
)


class OperariConsultaXatIn(BaseModel):
    pregunta: str
    imatge_b64: Optional[str] = None
    historial: Optional[List[Dict[str, Any]]] = None
    context_id: Optional[str] = None


@router.post("/xat")
async def consultar_copilot_operari(
    dades: OperariConsultaXatIn,
    db: AsyncSession = Depends(get_db_with_tenant_context),
    claims: Dict[str, Any] = Depends(get_current_user_claims),
) -> Dict[str, Any]:
    """Assistent IA tècnic de camp per a operaris i caps de colla."""
    empresa_id_str = claims.get("empresa_id")
    if not empresa_id_str:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Tenant no vàlid")
    empresa_id = uuid.UUID(empresa_id_str)

    usuari_id_str = claims.get("sub")
    usuari_id = uuid.UUID(usuari_id_str) if usuari_id_str else uuid.uuid4()
    rol_usuari = claims.get("rol", "OPERARI").upper()

    q_emp = select(Empresa).where(Empresa.id == empresa_id)
    res_emp = await db.execute(q_emp)
    empresa = res_emp.scalar_one_or_none()
    vertical = empresa.vertical if empresa else "SEVALOR"

    usuari_nom = claims.get("nom") or claims.get("email")

    return await copilot_dispatcher.dispatch(
        pregunta=dades.pregunta,
        db=db,
        empresa_id=empresa_id,
        usuari_id=usuari_id,
        rol_usuari=rol_usuari,
        usuari_nom=usuari_nom,
        context_id=dades.context_id,
        vertical=vertical,
        historial=dades.historial,
        agent_prompt_system=empresa.agent_prompt_system if empresa else None,
        allow_operari=True,
    )

