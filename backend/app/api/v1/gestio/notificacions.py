import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db_with_tenant_context
from app.core.security import require_roles
from app.models.models import Client, ConversaNotificacio, MissatgeNotificacio

router = APIRouter(
    prefix="/gestio/notificacions",
    tags=["Gestió Notificacions"],
    dependencies=[Depends(require_roles(["BOSS", "SECRETARIA", "ENGINYER"]))],
)

class ConversaCreate(BaseModel):
    client_id: uuid.UUID
    ordre_treball_id: Optional[uuid.UUID] = None
    titol: str = Field(..., max_length=150)

class ConversaResponse(ConversaCreate):
    id: uuid.UUID
    estat: str
    es_arxivada: bool

@router.get("/converses", response_model=List[ConversaResponse])
async def llistar_converses(
    request: Request,
    db: AsyncSession = Depends(get_db_with_tenant_context)
):
    empresa_id = request.state.empresa_id
    if not empresa_id:
        raise HTTPException(status_code=401)
    stmt = select(ConversaNotificacio).where(ConversaNotificacio.empresa_id == uuid.UUID(empresa_id)).order_by(ConversaNotificacio.updated_at.desc())
    result = await db.execute(stmt)
    return result.scalars().all()

@router.post("/converses", response_model=ConversaResponse, status_code=status.HTTP_201_CREATED)
async def crear_conversa(
    request: Request,
    payload: ConversaCreate,
    db: AsyncSession = Depends(get_db_with_tenant_context)
):
    empresa_id = request.state.empresa_id
    if not empresa_id:
        raise HTTPException(status_code=401)
    stmt_c = select(Client).where(Client.id == payload.client_id, Client.empresa_id == uuid.UUID(empresa_id))
    if not (await db.execute(stmt_c)).scalars().first():
        raise HTTPException(status_code=404, detail="Client no trobat")
    nova_conversa = ConversaNotificacio(
        empresa_id=uuid.UUID(empresa_id), client_id=payload.client_id,
        ordre_treball_id=payload.ordre_treball_id, titol=payload.titol, estat="BLAU_OBERT"
    )
    db.add(nova_conversa)
    await db.commit()
    return nova_conversa

class MissatgeCreate(BaseModel):
    contingut_text: str = Field(..., max_length=2000)
    tipus_esdeveniment: str = Field("MISSATGE_MANUAL", max_length=50)

class MissatgeResponse(BaseModel):
    id: uuid.UUID
    contingut_text: str
    remitent_tipus: str
    tipus_esdeveniment: str
    created_at: datetime

class EstatUpdate(BaseModel):
    estat: str = Field(..., pattern="^(VERMELL_PRIORITARI|BLAU_OBERT|VERD_SOLUCIONAT)$")

@router.get("/converses/{conversa_id}/missatges", response_model=List[MissatgeResponse])
async def llistar_missatges(
    request: Request, conversa_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_with_tenant_context)
):
    empresa_id = request.state.empresa_id
    if not empresa_id:
        raise HTTPException(status_code=401)
    stmt = select(MissatgeNotificacio).where(
        MissatgeNotificacio.conversa_id == conversa_id,
        MissatgeNotificacio.empresa_id == uuid.UUID(empresa_id),
    ).order_by(MissatgeNotificacio.created_at.asc())
    result = await db.execute(stmt)
    return result.scalars().all()

@router.post("/converses/{conversa_id}/missatges", response_model=MissatgeResponse, status_code=status.HTTP_201_CREATED)
async def crear_missatge(
    request: Request, conversa_id: uuid.UUID, payload: MissatgeCreate,
    db: AsyncSession = Depends(get_db_with_tenant_context)
):
    empresa_id = request.state.empresa_id
    if not empresa_id:
        raise HTTPException(status_code=401)
    conv_res = await db.execute(select(ConversaNotificacio).where(
        ConversaNotificacio.id == conversa_id, ConversaNotificacio.empresa_id == uuid.UUID(empresa_id),
    ))
    conversa = conv_res.scalars().first()
    if not conversa:
        raise HTTPException(status_code=404, detail="Conversa no trobada")
    nou_missatge = MissatgeNotificacio(
        empresa_id=uuid.UUID(empresa_id), conversa_id=conversa_id,
        remitent_tipus="OFICINA", contingut_text=payload.contingut_text,
        tipus_esdeveniment=payload.tipus_esdeveniment,
    )
    db.add(nou_missatge)
    if payload.tipus_esdeveniment != "TANCAMENT":
        conversa.estat = "BLAU_OBERT"
    await db.commit()
    return nou_missatge

@router.put("/converses/{conversa_id}/estat", response_model=ConversaResponse)
async def canviar_estat_conversa(
    request: Request, conversa_id: uuid.UUID, payload: EstatUpdate,
    db: AsyncSession = Depends(get_db_with_tenant_context)
):
    empresa_id = request.state.empresa_id
    if not empresa_id:
        raise HTTPException(status_code=401)
    conv_res = await db.execute(select(ConversaNotificacio).where(
        ConversaNotificacio.id == conversa_id, ConversaNotificacio.empresa_id == uuid.UUID(empresa_id),
    ))
    conversa = conv_res.scalars().first()
    if not conversa:
        raise HTTPException(status_code=404, detail="Conversa no trobada")
    conversa.estat = payload.estat
    if payload.estat == "VERD_SOLUCIONAT":
        conversa.es_arxivada = True
    await db.commit()
    return conversa

TOKENS_FACTURA: dict = {}

@router.get("/converses/{conversa_id}/enllac-factura")
async def generar_enllac_factura(
    request: Request, conversa_id: uuid.UUID, factura_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_with_tenant_context)
):
    empresa_id = request.state.empresa_id
    if not empresa_id:
        raise HTTPException(status_code=401)
    conv_res = await db.execute(select(ConversaNotificacio).where(
        ConversaNotificacio.id == conversa_id, ConversaNotificacio.empresa_id == uuid.UUID(empresa_id),
    ))
    if not conv_res.scalars().first():
        raise HTTPException(status_code=404, detail="Conversa no trobada")
    token = secrets.token_urlsafe(32)
    TOKENS_FACTURA[token] = {
        "factura_id": str(factura_id), "empresa_id": empresa_id,
        "expira": datetime.now(timezone.utc) + timedelta(hours=72),
    }
    return {"token": token, "expira": (datetime.now(timezone.utc) + timedelta(hours=72)).isoformat(), "enllac": f"/descarregar-factura?token={token}"}


# ---------------------------------------------------------------------------
# Invitació Bot de Telegram (Spec 023 RF-05: deep-linking, token 48h, un sol ús)
# ---------------------------------------------------------------------------

class InvitacioTelegramResponse(BaseModel):
    token: str
    enllac_profund: str
    expira: str

@router.post("/converses/{conversa_id}/invitar-telegram", response_model=InvitacioTelegramResponse)
async def generar_invitacio_telegram(
    request: Request, conversa_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_with_tenant_context)
):
    """Genera un token d'invitació per al Bot de Telegram (Spec 023 RF-05: expira 48h, un sol ús)."""
    empresa_id = request.headers.get("X-Empresa-ID") or getattr(request.state, "empresa_id", None)
    if not empresa_id:
        raise HTTPException(status_code=401, detail="No identificat")
    conv_res = await db.execute(select(ConversaNotificacio).where(
        ConversaNotificacio.id == conversa_id, ConversaNotificacio.empresa_id == uuid.UUID(empresa_id),
    ))
    conversa = conv_res.scalars().first()
    if not conversa:
        raise HTTPException(status_code=404, detail="Conversa no trobada")

    token = secrets.token_urlsafe(32)
    expira = datetime.now(timezone.utc) + timedelta(hours=48)
    await db.execute(
        text("""INSERT INTO tokens_invitacio_telegram
                (id, empresa_id, client_id, token_hash, expira_a, utilitzat)
                VALUES (:id, :eid, :cid, :th, :exp, FALSE)"""),
        {"id": str(uuid.uuid4()), "eid": empresa_id, "cid": str(conversa.client_id),
         "th": token, "exp": expira},
    )
    await db.commit()

    return {
        "token": token,
        "enllac_profund": f"https://t.me/campopro_bot?start={token}",
        "expira": expira.isoformat(),
    }
