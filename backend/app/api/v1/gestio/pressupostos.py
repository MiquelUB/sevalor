"""Endpoints per a la gestió de Pressupostos i integració transaccional amb Telegram (Spec 009 / Phase 4)."""

import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db_with_tenant_context
from app.core.security import get_current_user_claims, require_roles
from app.models.models import Client, Pressupost
from app.services.telegram_service import telegram_service

router = APIRouter(
    prefix="/gestio/pressupostos",
    tags=["Gestió Pressupostos i Telegram"],
    dependencies=[Depends(require_roles(["BOSS", "SECRETARIA", "ENGINYER"]))],
)


# ---------------------------------------------------------------------------
# DTOs / Esquemes Pydantic
# ---------------------------------------------------------------------------

class PressupostCreate(BaseModel):
    client_id: uuid.UUID
    numero: str = Field(..., max_length=30)
    total: float = Field(default=0.00, ge=0.0)


class PressupostResponse(BaseModel):
    id: uuid.UUID
    empresa_id: uuid.UUID
    client_id: uuid.UUID
    numero: str
    total: float
    estat: str
    token_signatura: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("", response_model=List[PressupostResponse])
async def llistar_pressupostos(
    client_id: Optional[uuid.UUID] = Query(None),
    estat: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db_with_tenant_context),
    claims: Dict[str, Any] = Depends(get_current_user_claims),
):
    """Llista els pressupostos de l'empresa (filtrats per RLS)."""
    empresa_id_str = claims.get("empresa_id")
    if not empresa_id_str:
        raise HTTPException(status_code=400, detail="Falta el tenant al token.")
    empresa_id = uuid.UUID(empresa_id_str)

    stmt = select(Pressupost).where(Pressupost.empresa_id == empresa_id)
    if client_id:
        stmt = stmt.where(Pressupost.client_id == client_id)
    if estat:
        stmt = stmt.where(Pressupost.estat == estat.upper())

    stmt = stmt.order_by(Pressupost.created_at.desc())
    res = await db.execute(stmt)
    return res.scalars().all()


@router.post("", response_model=PressupostResponse, status_code=status.HTTP_201_CREATED)
async def crear_pressupost(
    dades: PressupostCreate,
    db: AsyncSession = Depends(get_db_with_tenant_context),
    claims: Dict[str, Any] = Depends(get_current_user_claims),
):
    """Crea un nou pressupost en estat PENDENT."""
    empresa_id_str = claims.get("empresa_id")
    if not empresa_id_str:
        raise HTTPException(status_code=400, detail="Falta el tenant al token.")
    empresa_id = uuid.UUID(empresa_id_str)

    # Verificar que el client pertany a l'empresa
    stmt_c = select(Client).where(Client.id == dades.client_id, Client.empresa_id == empresa_id)
    client = (await db.execute(stmt_c)).scalars().first()
    if not client:
        raise HTTPException(status_code=404, detail="El client especificat no existeix o no pertany a la teva empresa.")

    nou_pressupost = Pressupost(
        id=uuid.uuid4(),
        empresa_id=empresa_id,
        client_id=dades.client_id,
        numero=dades.numero,
        total=dades.total,
        estat="PENDENT",
    )
    db.add(nou_pressupost)
    await db.commit()
    await db.refresh(nou_pressupost)
    return nou_pressupost


@router.get("/{pressupost_id}", response_model=PressupostResponse)
async def obtenir_pressupost(
    pressupost_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_with_tenant_context),
    claims: Dict[str, Any] = Depends(get_current_user_claims),
):
    """Obté el detall d'un pressupost per ID (Spec 009 / TEST-F4-01)."""
    empresa_id_str = claims.get("empresa_id")
    if not empresa_id_str:
        raise HTTPException(status_code=400, detail="Falta el tenant al token.")
    empresa_id = uuid.UUID(empresa_id_str)

    stmt = select(Pressupost).where(Pressupost.id == pressupost_id, Pressupost.empresa_id == empresa_id)
    res = await db.execute(stmt)
    pressupost = res.scalars().first()
    if not pressupost:
        raise HTTPException(status_code=404, detail="Pressupost no trobat.")
    return pressupost


@router.post("/{pressupost_id}/enviar-telegram")
async def enviar_pressupost_via_telegram(
    pressupost_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_with_tenant_context),
    claims: Dict[str, Any] = Depends(get_current_user_claims),
):
    """Envia el pressupost amb Inline Keyboard al client via Telegram (Spec 009 RF-09)."""
    empresa_id_str = claims.get("empresa_id")
    if not empresa_id_str:
        raise HTTPException(status_code=400, detail="Falta el tenant al token.")
    empresa_id = uuid.UUID(empresa_id_str)

    stmt = select(Pressupost).where(Pressupost.id == pressupost_id, Pressupost.empresa_id == empresa_id)
    res = await db.execute(stmt)
    pressupost = res.scalars().first()
    if not pressupost:
        raise HTTPException(status_code=404, detail="Pressupost no trobat.")

    resultat = await telegram_service.enviar_pressupost_telegram(db, pressupost.id)
    if not resultat.get("ok"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=resultat.get("detail", "No s'ha pogut enviar el missatge per Telegram.")
        )

    return {
        "status": "enviat",
        "pressupost_id": str(pressupost.id),
        "numero": pressupost.numero,
        "chat_id": resultat.get("chat_id"),
    }
