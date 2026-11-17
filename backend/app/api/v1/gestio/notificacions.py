import json
import logging
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Sequence

import httpx
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.db import get_db_with_tenant_context
from app.core.redis import get_redis_client
from app.core.security import require_roles
from app.models.models import Client, ConversaNotificacio, Empresa, MissatgeNotificacio
from app.services.telegram_service import send_telegram_direct_message

logger = logging.getLogger(__name__)
_REDIS_FACTURA_TOKEN_PREFIX = "sevalor:notificacions:factura_token:"
_FACTURA_TOKEN_TTL_SECONDS = 72 * 3600

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
    client_nom: Optional[str] = None
    client_te_telegram: bool = False


async def _resoldre_clients_map(
    db: AsyncSession, empresa_uuid: uuid.UUID, client_ids: List[uuid.UUID]
) -> Dict[uuid.UUID, Client]:
    if not client_ids:
        return {}
    res = await db.execute(
        select(Client).where(Client.empresa_id == empresa_uuid, Client.id.in_(client_ids))
    )
    return {c.id: c for c in res.scalars().all()}


def _serialitzar_conversa(conv: ConversaNotificacio, client: Optional[Client]) -> ConversaResponse:
    return ConversaResponse(
        id=conv.id,
        client_id=conv.client_id,
        ordre_treball_id=conv.ordre_treball_id,
        titol=conv.titol,
        estat=conv.estat,
        es_arxivada=bool(conv.es_arxivada),
        client_nom=client.rao_social if client else None,
        client_te_telegram=bool(client and client.telegram_chat_id),
    )


async def _enviar_telegram_en_segon_pla(
    empresa_id: uuid.UUID, chat_id: int, missatge: str
) -> None:
    try:
        await send_telegram_direct_message(empresa_id, chat_id, missatge)
    except Exception as exc:
        logger.warning("Error enviant notificació Telegram en segon pla: %s", exc)


async def _resoldre_bot_username(empresa: Optional[Empresa]) -> str:
    redis_cli = await get_redis_client()
    cache_key = f"sevalor:tg_username:{empresa.id}" if empresa else None
    if redis_cli and cache_key:
        cached = await redis_cli.get(cache_key)
        if cached:
            return str(cached)

    token = ((empresa.telegram_bot_token if empresa else None) or settings.TELEGRAM_BOT_TOKEN or "").strip()
    if token and token != "DUMMY_TOKEN":
        try:
            async with httpx.AsyncClient(timeout=2.0) as cli:
                resp = await cli.get(f"https://api.telegram.org/bot{token}/getMe")
                if resp.status_code == 200:
                    username = (resp.json().get("result") or {}).get("username")
                    if username:
                        if redis_cli and cache_key:
                            await redis_cli.setex(cache_key, 3600, str(username))
                        return str(username)
        except Exception as exc:
            logger.debug("No s'ha pogut resoldre bot username via getMe: %s", exc)

    fallback = (getattr(settings, "TELEGRAM_BOT_USERNAME", None) or "").strip()
    if fallback:
        return fallback.lstrip("@")
    if empresa and empresa.subdomini:
        clean_sub = "".join(ch for ch in empresa.subdomini if ch.isalnum() or ch == "_").lower()
        if clean_sub:
            return f"{clean_sub}_bot"
    return "sevalor_bot"


@router.get("/converses", response_model=List[ConversaResponse])
async def llistar_converses(
    request: Request, db: AsyncSession = Depends(get_db_with_tenant_context)
) -> List[ConversaResponse]:
    empresa_id = request.state.empresa_id
    if not empresa_id or empresa_id == "undefined":
        raise HTTPException(status_code=401)
    emp_uuid = uuid.UUID(empresa_id)
    stmt = (
        select(ConversaNotificacio)
        .where(ConversaNotificacio.empresa_id == emp_uuid)
        .order_by(ConversaNotificacio.updated_at.desc())
    )
    result = await db.execute(stmt)
    converses = result.scalars().all()
    clients_map = await _resoldre_clients_map(
        db, emp_uuid, list({c.client_id for c in converses if c.client_id})
    )
    return [_serialitzar_conversa(c, clients_map.get(c.client_id)) for c in converses]


@router.post("/converses", response_model=ConversaResponse, status_code=status.HTTP_201_CREATED)
async def crear_conversa(
    request: Request,
    payload: ConversaCreate,
    db: AsyncSession = Depends(get_db_with_tenant_context),
) -> ConversaResponse:
    empresa_id = request.state.empresa_id
    if not empresa_id or empresa_id == "undefined":
        raise HTTPException(status_code=401)
    emp_uuid = uuid.UUID(empresa_id)
    stmt_c = select(Client).where(
        Client.id == payload.client_id, Client.empresa_id == emp_uuid
    )
    client_db = (await db.execute(stmt_c)).scalars().first()
    if not client_db:
        raise HTTPException(status_code=404, detail="Client no trobat")
    nova_conversa = ConversaNotificacio(
        empresa_id=emp_uuid,
        client_id=payload.client_id,
        ordre_treball_id=payload.ordre_treball_id,
        titol=payload.titol,
        estat="BLAU_OBERT",
    )
    db.add(nova_conversa)
    await db.commit()
    return _serialitzar_conversa(nova_conversa, client_db)


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
    request: Request, conversa_id: uuid.UUID, db: AsyncSession = Depends(get_db_with_tenant_context)
) -> Sequence[MissatgeNotificacio]:
    empresa_id = request.state.empresa_id
    if not empresa_id or empresa_id == "undefined":
        raise HTTPException(status_code=401)
    stmt = (
        select(MissatgeNotificacio)
        .where(
            MissatgeNotificacio.conversa_id == conversa_id,
            MissatgeNotificacio.empresa_id == uuid.UUID(empresa_id),
        )
        .order_by(MissatgeNotificacio.created_at.asc())
    )
    result = await db.execute(stmt)
    return result.scalars().all()


@router.post(
    "/converses/{conversa_id}/missatges",
    response_model=MissatgeResponse,
    status_code=status.HTTP_201_CREATED,
)
async def crear_missatge(
    request: Request,
    conversa_id: uuid.UUID,
    payload: MissatgeCreate,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db_with_tenant_context),
) -> MissatgeNotificacio:
    empresa_id = request.state.empresa_id
    if not empresa_id or empresa_id == "undefined":
        raise HTTPException(status_code=401)
    emp_uuid = uuid.UUID(empresa_id)
    conv_res = await db.execute(
        select(ConversaNotificacio).where(
            ConversaNotificacio.id == conversa_id,
            ConversaNotificacio.empresa_id == emp_uuid,
        )
    )
    conversa = conv_res.scalars().first()
    if not conversa:
        raise HTTPException(status_code=404, detail="Conversa no trobada")
    nou_missatge = MissatgeNotificacio(
        empresa_id=emp_uuid,
        conversa_id=conversa_id,
        remitent_tipus="OFICINA",
        contingut_text=payload.contingut_text,
        tipus_esdeveniment=payload.tipus_esdeveniment,
    )
    db.add(nou_missatge)
    if payload.tipus_esdeveniment != "TANCAMENT":
        conversa.estat = "BLAU_OBERT"
    await db.commit()

    # Despatxar via bot Telegram al client si disposa de telegram_chat_id vinculat
    cli_res = await db.execute(
        select(Client).where(Client.id == conversa.client_id, Client.empresa_id == emp_uuid)
    )
    client_db = cli_res.scalars().first()
    if client_db and client_db.telegram_chat_id:
        background_tasks.add_task(
            _enviar_telegram_en_segon_pla,
            emp_uuid,
            int(client_db.telegram_chat_id),
            payload.contingut_text,
        )

    return nou_missatge


@router.put("/converses/{conversa_id}/estat", response_model=ConversaResponse)
async def canviar_estat_conversa(
    request: Request,
    conversa_id: uuid.UUID,
    payload: EstatUpdate,
    db: AsyncSession = Depends(get_db_with_tenant_context),
) -> ConversaResponse:
    empresa_id = request.state.empresa_id
    if not empresa_id or empresa_id == "undefined":
        raise HTTPException(status_code=401)
    emp_uuid = uuid.UUID(empresa_id)
    conv_res = await db.execute(
        select(ConversaNotificacio).where(
            ConversaNotificacio.id == conversa_id,
            ConversaNotificacio.empresa_id == emp_uuid,
        )
    )
    conversa = conv_res.scalars().first()
    if not conversa:
        raise HTTPException(status_code=404, detail="Conversa no trobada")
    conversa.estat = payload.estat
    if payload.estat == "VERD_SOLUCIONAT":
        conversa.es_arxivada = True
    await db.commit()
    cli = (
        await db.execute(
            select(Client).where(Client.id == conversa.client_id, Client.empresa_id == emp_uuid)
        )
    ).scalars().first()
    return _serialitzar_conversa(conversa, cli)


@router.get("/converses/{conversa_id}/enllac-factura")
async def generar_enllac_factura(
    request: Request,
    conversa_id: uuid.UUID,
    factura_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_with_tenant_context),
) -> Dict[str, str]:
    empresa_id = request.state.empresa_id
    if not empresa_id or empresa_id == "undefined":
        raise HTTPException(status_code=401)
    conv_res = await db.execute(
        select(ConversaNotificacio).where(
            ConversaNotificacio.id == conversa_id,
            ConversaNotificacio.empresa_id == uuid.UUID(empresa_id),
        )
    )
    if not conv_res.scalars().first():
        raise HTTPException(status_code=404, detail="Conversa no trobada")

    redis_cli = await get_redis_client()
    if not redis_cli:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Redis no disponible per emetre tokens temporals de factura",
        )

    token = secrets.token_urlsafe(32)
    expira = datetime.now(timezone.utc) + timedelta(seconds=_FACTURA_TOKEN_TTL_SECONDS)
    await redis_cli.set(
        f"{_REDIS_FACTURA_TOKEN_PREFIX}{token}",
        json.dumps(
            {
                "factura_id": str(factura_id),
                "empresa_id": str(empresa_id),
                "expira": expira.isoformat(),
            }
        ),
        ex=_FACTURA_TOKEN_TTL_SECONDS,
    )
    return {
        "token": token,
        "expira": expira.isoformat(),
        "enllac": f"/descarregar-factura?token={token}",
    }


@router.get("/descarregar-factura")
async def verificar_token_factura(
    request: Request,
    token: str = Query(..., min_length=16),
) -> Dict[str, Any]:
    """Valida i resol un token efímer d'enllaç de factura emmagatzemat a Redis (sense RAM)."""
    empresa_id = request.state.empresa_id
    if not empresa_id or empresa_id == "undefined":
        raise HTTPException(status_code=401)
    redis_cli = await get_redis_client()
    if not redis_cli:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Servei Redis no disponible",
        )
    raw = await redis_cli.get(f"{_REDIS_FACTURA_TOKEN_PREFIX}{token}")
    if not raw:
        raise HTTPException(status_code=404, detail="Token inexistent o expirat")
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise HTTPException(status_code=500, detail="Format de token invàlid")
    if str(data.get("empresa_id")) != str(empresa_id):
        raise HTTPException(status_code=403, detail="Accés denegat al recurs d'un altre tenant")
    return data


# ---------------------------------------------------------------------------
# Invitació Bot de Telegram (Spec 023 RF-05: deep-linking, token 48h, un sol ús)
# ---------------------------------------------------------------------------


class InvitacioTelegramResponse(BaseModel):
    token: str
    enllac_profund: str
    expira: str


@router.post("/converses/{conversa_id}/invitar-telegram", response_model=InvitacioTelegramResponse)
async def generar_invitacio_telegram(
    request: Request, conversa_id: uuid.UUID, db: AsyncSession = Depends(get_db_with_tenant_context)
) -> InvitacioTelegramResponse:
    """Genera un token d'invitació per al Bot de Telegram (Spec 023 RF-05: expira 48h, un sol ús)."""
    empresa_id = getattr(request.state, "empresa_id", None) or request.headers.get("X-Empresa-ID")
    if not empresa_id or empresa_id == "undefined":
        raise HTTPException(status_code=401, detail="No identificat")
    emp_uuid = uuid.UUID(empresa_id)
    conv_res = await db.execute(
        select(ConversaNotificacio).where(
            ConversaNotificacio.id == conversa_id,
            ConversaNotificacio.empresa_id == emp_uuid,
        )
    )
    conversa = conv_res.scalars().first()
    if not conversa:
        raise HTTPException(status_code=404, detail="Conversa no trobada")

    empresa = (
        await db.execute(select(Empresa).where(Empresa.id == emp_uuid))
    ).scalars().first()
    bot_username = await _resoldre_bot_username(empresa)

    token = secrets.token_urlsafe(32)
    expira = datetime.now(timezone.utc) + timedelta(hours=48)
    await db.execute(
        text("""INSERT INTO tokens_invitacio_telegram
                (id, empresa_id, client_id, token_hash, expira_a, utilitzat)
                VALUES (:id, :eid, :cid, :th, :exp, FALSE)"""),
        {
            "id": str(uuid.uuid4()),
            "eid": empresa_id,
            "cid": str(conversa.client_id),
            "th": token,
            "exp": expira,
        },
    )
    await db.commit()

    return InvitacioTelegramResponse(
        token=token,
        enllac_profund=f"https://t.me/{bot_username}?start={token}",
        expira=expira.isoformat(),
    )
