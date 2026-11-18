"""Endpoints per a la gestió completa de Pressupostos, PDF i enviament multi-canal (Email / Telegram / Enllaç públic)."""

import logging
import re
import uuid
from datetime import date, datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import Response
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db_with_tenant_context
from app.core.security import get_current_user_claims, require_roles
from app.models.models import Client, Empresa, OrdreTreball, Pressupost
from app.services.pressupost_service import (
    DEFAULT_VALIDESA_DIES,
    calcular_totals_linies_pressupost,
    carregar_detalls_pressupostos_map,
    construir_acceptacio_url,
    construir_mailto_url,
    desar_detalls_pressupost_disc,
    enviar_pressupost_email_smtp,
    generar_pdf_pressupost_bytes,
    generar_token_acceptacio_pressupost,
)
from app.services.sovereign_storage import SovereignStorageGateway
from app.services.telegram_service import telegram_service

logger = logging.getLogger("sevalor.pressupostos")

router = APIRouter(
    prefix="/gestio/pressupostos",
    tags=["Gestió Pressupostos i Telegram"],
    dependencies=[Depends(require_roles(["BOSS", "SECRETARIA", "ENGINYER"]))],
)


# ---------------------------------------------------------------------------
# DTOs / Esquemes Pydantic
# ---------------------------------------------------------------------------


class PressupostLiniaIn(BaseModel):
    article_id: Optional[uuid.UUID] = None
    concepte: str = Field(..., min_length=1, max_length=200)
    quantitat: float = Field(default=1.0, gt=0)
    preu_unitari: float = Field(default=0.0, ge=0.0)
    descompte_pct: float = Field(default=0.0, ge=0.0, le=100.0)
    tipus_iva: float = Field(default=21.0, ge=0.0, le=100.0)


class PressupostLiniaOut(BaseModel):
    article_id: Optional[str] = None
    concepte: str
    quantitat: float = 1.0
    preu_unitari: float = 0.0
    descompte_pct: float = 0.0
    tipus_iva: float = 21.0
    subtotal: float = 0.0


class PressupostCreate(BaseModel):
    client_id: uuid.UUID
    numero: str = Field(..., max_length=30)
    total: float = Field(default=0.00, ge=0.0)
    titol: Optional[str] = Field(None, max_length=200)
    descripcio: Optional[str] = None
    validesa_dies: int = Field(default=DEFAULT_VALIDESA_DIES, ge=1, le=365)
    linies: Optional[List[PressupostLiniaIn]] = None


class PressupostUpdate(BaseModel):
    client_id: Optional[uuid.UUID] = None
    titol: Optional[str] = Field(None, max_length=200)
    descripcio: Optional[str] = None
    validesa_dies: Optional[int] = Field(None, ge=1, le=365)
    total: Optional[float] = Field(None, ge=0.0)
    linies: Optional[List[PressupostLiniaIn]] = None


class PressupostEnviarEmailRequest(BaseModel):
    email_destinatari: Optional[str] = Field(None, max_length=200)
    assumpte: Optional[str] = Field(None, max_length=255)
    missatge: Optional[str] = None


class PressupostRegistrarEnviamentRequest(BaseModel):
    canal: str = Field(..., max_length=30)  # WHATSAPP, ENLLAC, EMAIL_MANUAL
    destinatari: Optional[str] = Field(None, max_length=200)


class PressupostConvertirOTRequest(BaseModel):
    titol: Optional[str] = Field(None, max_length=200)
    adreca: Optional[str] = Field(None, max_length=255)
    data_planificacio: Optional[date] = None
    forcar_si_pendent: bool = False


class PressupostResponse(BaseModel):
    id: uuid.UUID
    empresa_id: uuid.UUID
    client_id: uuid.UUID
    client_nom: Optional[str] = None
    client_email: Optional[str] = None
    client_telefon: Optional[str] = None
    client_te_telegram: bool = False
    numero: str
    titol: Optional[str] = None
    descripcio: Optional[str] = None
    base_imposable: float = 0.0
    quota_iva: float = 0.0
    total: float
    validesa_dies: int = DEFAULT_VALIDESA_DIES
    estat: str
    token_signatura: Optional[str] = None
    canal_enviament: Optional[str] = None
    email_destinatari: Optional[str] = None
    data_enviament: Optional[str] = None
    acceptacio_url: Optional[str] = None
    ordre_treball_id: Optional[str] = None
    motiu_canvis_client: Optional[str] = None
    linies: List[PressupostLiniaOut] = []
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------
# Helpers de serialització
# ---------------------------------------------------------------------------


def _resolve_origin(request: Optional[Request]) -> Optional[str]:
    if not request:
        return None
    origin = request.headers.get("origin")
    if origin:
        return origin
    xf_host = request.headers.get("x-forwarded-host") or request.headers.get("host")
    xf_proto = request.headers.get("x-forwarded-proto") or "https"
    if xf_host and not xf_host.startswith("test"):
        return f"{xf_proto}://{xf_host}"
    return None


def _serialitzar_pressupost(
    pressupost: Pressupost,
    client: Optional[Client],
    detalls: Dict[str, Any],
    origin: Optional[str],
    amagar_imports: bool = False,
) -> PressupostResponse:
    token = generar_token_acceptacio_pressupost(pressupost.empresa_id, pressupost.id)
    acceptacio_url = construir_acceptacio_url(origin, token)
    raw_linies = detalls.get("linies") or []
    linies_out = [
        PressupostLiniaOut(
            article_id=lin.get("article_id"),
            concepte=str(lin.get("concepte") or ""),
            quantitat=float(lin.get("quantitat") or 1.0),
            preu_unitari=0.0 if amagar_imports else float(lin.get("preu_unitari") or 0.0),
            descompte_pct=float(lin.get("descompte_pct") or 0.0),
            tipus_iva=float(lin.get("tipus_iva") if lin.get("tipus_iva") is not None else 21.0),
            subtotal=0.0 if amagar_imports else float(lin.get("subtotal") or 0.0),
        )
        for lin in raw_linies
    ]
    total_raw = float(pressupost.total) if pressupost.total is not None else 0.0
    total_val = 0.0 if amagar_imports else total_raw
    raw_base = detalls.get("base_imposable")
    base_val = 0.0 if amagar_imports else (float(raw_base) if raw_base is not None else total_raw)
    iva_val = 0.0 if amagar_imports else float(detalls.get("quota_iva") or 0.0)

    return PressupostResponse(
        id=pressupost.id,
        empresa_id=pressupost.empresa_id,
        client_id=pressupost.client_id,
        client_nom=client.rao_social if client else None,
        client_email=client.email if client else None,
        client_telefon=client.telefon if client else None,
        client_te_telegram=bool(
            client and client.telegram_chat_id and client.estat_canal_telegram == "ACTIU"
        ),
        numero=pressupost.numero,
        titol=detalls.get("titol"),
        descripcio=detalls.get("descripcio"),
        base_imposable=base_val,
        quota_iva=iva_val,
        total=total_val,
        validesa_dies=int(detalls.get("validesa_dies") or DEFAULT_VALIDESA_DIES),
        estat=pressupost.estat,
        token_signatura=pressupost.token_signatura,
        canal_enviament=detalls.get("canal_enviament"),
        email_destinatari=detalls.get("email_destinatari"),
        data_enviament=detalls.get("data_enviament"),
        acceptacio_url=acceptacio_url,
        ordre_treball_id=detalls.get("ordre_treball_id"),
        motiu_canvis_client=detalls.get("motiu_canvis_client"),
        linies=linies_out,
        created_at=pressupost.created_at,
        updated_at=pressupost.updated_at,
    )


async def _carregar_pressupost_i_client(
    db: AsyncSession, empresa_id: uuid.UUID, pressupost_id: uuid.UUID
) -> tuple[Pressupost, Optional[Client]]:
    stmt = select(Pressupost).where(
        Pressupost.id == pressupost_id, Pressupost.empresa_id == empresa_id
    )
    pressupost = (await db.execute(stmt)).scalars().first()
    if not pressupost:
        raise HTTPException(status_code=404, detail="Pressupost no trobat.")
    cli = (
        await db.execute(
            select(Client).where(Client.id == pressupost.client_id, Client.empresa_id == empresa_id)
        )
    ).scalars().first()
    return pressupost, cli


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("", response_model=List[PressupostResponse])
async def llistar_pressupostos(
    request: Request,
    client_id: Optional[uuid.UUID] = Query(None),
    estat: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db_with_tenant_context),
    claims: Dict[str, Any] = Depends(get_current_user_claims),
):
    """Llista els pressupostos de l'empresa amb detall complet i estat d'enviament."""
    empresa_id_str = claims.get("empresa_id")
    if not empresa_id_str:
        raise HTTPException(status_code=400, detail="Falta el tenant al token.")
    empresa_id = uuid.UUID(empresa_id_str)
    rol = str(claims.get("rol") or "").upper()
    amagar_imports = rol == "ENGINYER"

    stmt = select(Pressupost).where(Pressupost.empresa_id == empresa_id)
    if client_id:
        stmt = stmt.where(Pressupost.client_id == client_id)
    if estat:
        stmt = stmt.where(Pressupost.estat == estat.upper())
    stmt = stmt.order_by(Pressupost.created_at.desc())

    rows = list((await db.execute(stmt)).scalars().all())
    cli_ids = list({p.client_id for p in rows})
    cli_map: Dict[uuid.UUID, Client] = {}
    if cli_ids:
        cli_rows = (
            await db.execute(
                select(Client).where(Client.empresa_id == empresa_id, Client.id.in_(cli_ids))
            )
        ).scalars().all()
        cli_map = {c.id: c for c in cli_rows}

    detalls_map = await carregar_detalls_pressupostos_map(db, empresa_id)
    origin = _resolve_origin(request)
    return [
        _serialitzar_pressupost(
            p,
            cli_map.get(p.client_id),
            detalls_map.get(str(p.id), {}),
            origin,
            amagar_imports=amagar_imports,
        )
        for p in rows
    ]


@router.post("", response_model=PressupostResponse, status_code=status.HTTP_201_CREATED)
async def crear_pressupost(
    request: Request,
    dades: PressupostCreate,
    db: AsyncSession = Depends(get_db_with_tenant_context),
    claims: Dict[str, Any] = Depends(get_current_user_claims),
):
    """Crea un nou pressupost en estat PENDENT (amb partides i IVA opcionals) i el sincronitza al disc."""
    empresa_id_str = claims.get("empresa_id")
    if not empresa_id_str:
        raise HTTPException(status_code=400, detail="Falta el tenant al token.")
    empresa_id = uuid.UUID(empresa_id_str)

    stmt_c = select(Client).where(Client.id == dades.client_id, Client.empresa_id == empresa_id)
    client = (await db.execute(stmt_c)).scalars().first()
    if not client:
        raise HTTPException(
            status_code=404,
            detail="El client especificat no existeix o no pertany a la teva empresa.",
        )

    linies_norm: List[Dict[str, Any]] = []
    base_imp = float(dades.total)
    quota_iva = 0.0
    total_final = float(dades.total)

    if dades.linies:
        linies_norm, base_imp, quota_iva, total_final = calcular_totals_linies_pressupost(
            [lin.model_dump() for lin in dades.linies]
        )

    nou_pressupost = Pressupost(
        id=uuid.uuid4(),
        empresa_id=empresa_id,
        client_id=dades.client_id,
        numero=dades.numero,
        total=total_final,
        estat="PENDENT",
    )
    db.add(nou_pressupost)
    await db.commit()

    detalls = {
        "titol": dades.titol.strip() if dades.titol else f"Pressupost {dades.numero}",
        "descripcio": dades.descripcio.strip() if dades.descripcio else None,
        "validesa_dies": dades.validesa_dies,
        "linies": linies_norm,
        "base_imposable": base_imp,
        "quota_iva": quota_iva,
    }
    await desar_detalls_pressupost_disc(db, empresa_id, nou_pressupost, detalls)
    return _serialitzar_pressupost(nou_pressupost, client, detalls, _resolve_origin(request))


@router.get("/{pressupost_id}", response_model=PressupostResponse)
async def obtenir_pressupost(
    request: Request,
    pressupost_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_with_tenant_context),
    claims: Dict[str, Any] = Depends(get_current_user_claims),
):
    """Obté el detall complet d'un pressupost per ID."""
    empresa_id_str = claims.get("empresa_id")
    if not empresa_id_str:
        raise HTTPException(status_code=400, detail="Falta el tenant al token.")
    empresa_id = uuid.UUID(empresa_id_str)
    rol = str(claims.get("rol") or "").upper()

    pressupost, client = await _carregar_pressupost_i_client(db, empresa_id, pressupost_id)
    detalls_map = await carregar_detalls_pressupostos_map(db, empresa_id)
    return _serialitzar_pressupost(
        pressupost,
        client,
        detalls_map.get(str(pressupost.id), {}),
        _resolve_origin(request),
        amagar_imports=(rol == "ENGINYER"),
    )


@router.put("/{pressupost_id}", response_model=PressupostResponse)
async def editar_pressupost(
    request: Request,
    pressupost_id: uuid.UUID,
    dades: PressupostUpdate,
    db: AsyncSession = Depends(get_db_with_tenant_context),
    claims: Dict[str, Any] = Depends(get_current_user_claims),
):
    """Edita títol, descripció, validesa i partides d'un pressupost pendent abans d'enviar-lo."""
    empresa_id_str = claims.get("empresa_id")
    if not empresa_id_str:
        raise HTTPException(status_code=400, detail="Falta el tenant al token.")
    empresa_id = uuid.UUID(empresa_id_str)

    pressupost, client = await _carregar_pressupost_i_client(db, empresa_id, pressupost_id)
    if pressupost.estat != "PENDENT":
        raise HTTPException(
            status_code=400,
            detail="Només es poden editar pressupostos en estat PENDENT.",
        )

    if dades.client_id and dades.client_id != pressupost.client_id:
        cli_nou = (
            await db.execute(
                select(Client).where(Client.id == dades.client_id, Client.empresa_id == empresa_id)
            )
        ).scalars().first()
        if not cli_nou:
            raise HTTPException(status_code=404, detail="Client destí no trobat.")
        pressupost.client_id = dades.client_id
        client = cli_nou

    detalls_map = await carregar_detalls_pressupostos_map(db, empresa_id)
    detalls = dict(detalls_map.get(str(pressupost.id), {}))

    if dades.titol is not None:
        detalls["titol"] = dades.titol.strip()
    if dades.descripcio is not None:
        detalls["descripcio"] = dades.descripcio.strip() or None
    if dades.validesa_dies is not None:
        detalls["validesa_dies"] = dades.validesa_dies

    if dades.linies is not None:
        linies_norm, base_imp, quota_iva, total_final = calcular_totals_linies_pressupost(
            [lin.model_dump() for lin in dades.linies]
        )
        detalls["linies"] = linies_norm
        detalls["base_imposable"] = base_imp
        detalls["quota_iva"] = quota_iva
        pressupost.total = total_final
    elif dades.total is not None:
        pressupost.total = float(dades.total)
        detalls["base_imposable"] = float(dades.total)
        detalls["quota_iva"] = 0.0

    pressupost.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await desar_detalls_pressupost_disc(db, empresa_id, pressupost, detalls)
    return _serialitzar_pressupost(pressupost, client, detalls, _resolve_origin(request))


@router.delete("/{pressupost_id}", status_code=status.HTTP_200_OK)
async def eliminar_pressupost(
    pressupost_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_with_tenant_context),
    claims: Dict[str, Any] = Depends(get_current_user_claims),
):
    """Elimina un pressupost en estat PENDENT o REBUTJAT."""
    empresa_id_str = claims.get("empresa_id")
    if not empresa_id_str:
        raise HTTPException(status_code=400, detail="Falta el tenant al token.")
    empresa_id = uuid.UUID(empresa_id_str)

    pressupost, _ = await _carregar_pressupost_i_client(db, empresa_id, pressupost_id)
    if pressupost.estat == "APROVAT":
        raise HTTPException(
            status_code=400, detail="No es pot eliminar un pressupost ja aprovat pel client."
        )
    await db.delete(pressupost)
    await db.commit()
    return {"status": "eliminat", "id": str(pressupost_id)}


@router.get("/{pressupost_id}/pdf")
async def descarregar_pressupost_pdf(
    request: Request,
    pressupost_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_with_tenant_context),
    claims: Dict[str, Any] = Depends(get_current_user_claims),
) -> Response:
    """Genera i retorna el PDF oficial amb línies i codi QR d'acceptació online."""
    empresa_id_str = claims.get("empresa_id")
    if not empresa_id_str:
        raise HTTPException(status_code=400, detail="Falta el tenant al token.")
    empresa_id = uuid.UUID(empresa_id_str)

    pressupost, client = await _carregar_pressupost_i_client(db, empresa_id, pressupost_id)
    empresa = (await db.execute(select(Empresa).where(Empresa.id == empresa_id))).scalar_one_or_none()
    detalls_map = await carregar_detalls_pressupostos_map(db, empresa_id)
    detalls = detalls_map.get(str(pressupost.id), {})

    token = generar_token_acceptacio_pressupost(empresa_id, pressupost.id)
    acceptacio_url = construir_acceptacio_url(_resolve_origin(request), token)
    pdf_bytes = generar_pdf_pressupost_bytes(
        empresa=empresa,
        client=client,
        pressupost=pressupost,
        detalls=detalls,
        acceptacio_url=acceptacio_url,
    )
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'inline; filename="PRESSUPOST_{pressupost.numero}.pdf"'
        },
    )


@router.post("/{pressupost_id}/enviar-telegram")
async def enviar_pressupost_via_telegram(
    request: Request,
    pressupost_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_with_tenant_context),
    claims: Dict[str, Any] = Depends(get_current_user_claims),
):
    """Envia el pressupost amb Inline Keyboard al client via Telegram (Spec 009 RF-09)."""
    empresa_id_str = claims.get("empresa_id")
    if not empresa_id_str:
        raise HTTPException(status_code=400, detail="Falta el tenant al token.")
    empresa_id = uuid.UUID(empresa_id_str)

    pressupost, _ = await _carregar_pressupost_i_client(db, empresa_id, pressupost_id)
    detalls_map = await carregar_detalls_pressupostos_map(db, empresa_id)
    detalls = dict(detalls_map.get(str(pressupost.id), {}))
    token = generar_token_acceptacio_pressupost(empresa_id, pressupost.id)
    acceptacio_url = construir_acceptacio_url(_resolve_origin(request), token)

    resultat = await telegram_service.enviar_pressupost_telegram(
        db,
        pressupost.id,
        titol=detalls.get("titol"),
        acceptacio_url=acceptacio_url,
    )
    if not resultat.get("ok"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=resultat.get("detail", "No s'ha pogut enviar el missatge per Telegram."),
        )

    detalls["canal_enviament"] = "TELEGRAM"
    detalls["data_enviament"] = datetime.now(timezone.utc).isoformat()
    await desar_detalls_pressupost_disc(db, empresa_id, pressupost, detalls)

    return {
        "status": "enviat",
        "pressupost_id": str(pressupost.id),
        "numero": pressupost.numero,
        "chat_id": resultat.get("chat_id"),
        "acceptacio_url": acceptacio_url,
    }


@router.post("/{pressupost_id}/enviar-email")
async def enviar_pressupost_via_email(
    request: Request,
    pressupost_id: uuid.UUID,
    payload: Optional[PressupostEnviarEmailRequest] = None,
    db: AsyncSession = Depends(get_db_with_tenant_context),
    claims: Dict[str, Any] = Depends(get_current_user_claims),
):
    """Envia el pressupost en PDF amb enllaç d'acceptació al correu electrònic del client."""
    empresa_id_str = claims.get("empresa_id")
    if not empresa_id_str:
        raise HTTPException(status_code=400, detail="Falta el tenant al token.")
    empresa_id = uuid.UUID(empresa_id_str)

    pressupost, client = await _carregar_pressupost_i_client(db, empresa_id, pressupost_id)
    dest_email = (
        payload.email_destinatari.strip()
        if payload and payload.email_destinatari
        else (client.email or "").strip() if client else ""
    )
    if not dest_email or "@" not in dest_email:
        raise HTTPException(
            status_code=400,
            detail="El client no té un correu electrònic vàlid configurat. Introdueix-lo manualment.",
        )

    empresa = (await db.execute(select(Empresa).where(Empresa.id == empresa_id))).scalar_one_or_none()
    detalls_map = await carregar_detalls_pressupostos_map(db, empresa_id)
    detalls = dict(detalls_map.get(str(pressupost.id), {}))

    token = generar_token_acceptacio_pressupost(empresa_id, pressupost.id)
    acceptacio_url = construir_acceptacio_url(_resolve_origin(request), token)
    pdf_bytes = generar_pdf_pressupost_bytes(
        empresa=empresa,
        client=client,
        pressupost=pressupost,
        detalls=detalls,
        acceptacio_url=acceptacio_url,
    )

    empresa_nom = empresa.nom if empresa else "Sevalor Suite"
    titol = detalls.get("titol") or f"Pressupost {pressupost.numero}"
    assumpte = (
        payload.assumpte.strip()
        if payload and payload.assumpte
        else f"Pressupost {pressupost.numero} — {titol} ({empresa_nom})"
    )
    cos_defecte = (
        f"Bon dia{' ' + client.rao_social if client else ''},\n\n"
        f"Us fem arribar el pressupost {pressupost.numero} ({titol}) per un import total de "
        f"{float(pressupost.total or 0.0):.2f} €.\n\n"
        f"Podeu consultar-lo i acceptar-lo directament en línia amb 1 clic aquí:\n{acceptacio_url}\n\n"
        f"Atentament,\n{empresa_nom}"
    )
    cos = payload.missatge.strip() if payload and payload.missatge else cos_defecte

    smtp_ok, smtp_err = enviar_pressupost_email_smtp(
        empresa_nom=empresa_nom,
        destinatari_email=dest_email,
        assumpte=assumpte,
        cos_missatge=cos,
        numero_pressupost=pressupost.numero,
        pdf_bytes=pdf_bytes,
    )

    mailto_url = construir_mailto_url(dest_email, assumpte, cos)
    if smtp_ok:
        detalls["canal_enviament"] = "EMAIL"
        detalls["email_destinatari"] = dest_email
        detalls["data_enviament"] = datetime.now(timezone.utc).isoformat()
        await desar_detalls_pressupost_disc(db, empresa_id, pressupost, detalls)
        return {
            "status": "enviat",
            "smtp_enviat": True,
            "email_destinatari": dest_email,
            "acceptacio_url": acceptacio_url,
            "mailto_url": mailto_url,
            "missatge": f"Pressupost enviat per correu SMTP a {dest_email}.",
        }

    return {
        "status": "pendent_client_correu",
        "smtp_enviat": False,
        "email_destinatari": dest_email,
        "acceptacio_url": acceptacio_url,
        "mailto_url": mailto_url,
        "missatge": smtp_err
        or "El servidor SMTP no està actiu; utilitza l'opció d'obrir al client de correu o copia l'enllaç.",
    }


@router.post("/{pressupost_id}/registrar-enviament", response_model=PressupostResponse)
async def registrar_enviament_manual(
    request: Request,
    pressupost_id: uuid.UUID,
    payload: PressupostRegistrarEnviamentRequest,
    db: AsyncSession = Depends(get_db_with_tenant_context),
    claims: Dict[str, Any] = Depends(get_current_user_claims),
):
    """Registra l'enviament del pressupost per un canal extern (WhatsApp, Enllaç, Correu manual)."""
    empresa_id_str = claims.get("empresa_id")
    if not empresa_id_str:
        raise HTTPException(status_code=400, detail="Falta el tenant al token.")
    empresa_id = uuid.UUID(empresa_id_str)

    pressupost, client = await _carregar_pressupost_i_client(db, empresa_id, pressupost_id)
    detalls_map = await carregar_detalls_pressupostos_map(db, empresa_id)
    detalls = dict(detalls_map.get(str(pressupost.id), {}))
    detalls["canal_enviament"] = payload.canal.strip().upper()[:30]
    if payload.destinatari:
        detalls["email_destinatari"] = payload.destinatari.strip()[:200]
    detalls["data_enviament"] = datetime.now(timezone.utc).isoformat()
    await desar_detalls_pressupost_disc(db, empresa_id, pressupost, detalls)
    return _serialitzar_pressupost(pressupost, client, detalls, _resolve_origin(request))


@router.post("/{pressupost_id}/aprovar", response_model=PressupostResponse)
async def aprovar_pressupost(
    request: Request,
    pressupost_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_with_tenant_context),
    claims: Dict[str, Any] = Depends(get_current_user_claims),
):
    """Aprova un pressupost, canviant el seu estat a APROVAT."""
    empresa_id_str = claims.get("empresa_id")
    if not empresa_id_str:
        raise HTTPException(status_code=400, detail="Falta el tenant al token.")
    empresa_id = uuid.UUID(empresa_id_str)

    pressupost, client = await _carregar_pressupost_i_client(db, empresa_id, pressupost_id)
    if pressupost.estat != "PENDENT":
        raise HTTPException(
            status_code=400, detail="Només es poden aprovar pressupostos en estat PENDENT."
        )

    pressupost.estat = "APROVAT"
    if not pressupost.token_signatura:
        pressupost.token_signatura = f"GESTIO-APROV-{pressupost.id}"
    await db.commit()

    detalls_map = await carregar_detalls_pressupostos_map(db, empresa_id)
    detalls = detalls_map.get(str(pressupost.id), {})
    await desar_detalls_pressupost_disc(db, empresa_id, pressupost, detalls)
    return _serialitzar_pressupost(pressupost, client, detalls, _resolve_origin(request))


@router.post("/{pressupost_id}/rebutjar", response_model=PressupostResponse)
async def rebutjar_pressupost(
    request: Request,
    pressupost_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_with_tenant_context),
    claims: Dict[str, Any] = Depends(get_current_user_claims),
):
    """Rebutja un pressupost, canviant el seu estat a REBUTJAT."""
    empresa_id_str = claims.get("empresa_id")
    if not empresa_id_str:
        raise HTTPException(status_code=400, detail="Falta el tenant al token.")
    empresa_id = uuid.UUID(empresa_id_str)

    pressupost, client = await _carregar_pressupost_i_client(db, empresa_id, pressupost_id)
    if pressupost.estat != "PENDENT":
        raise HTTPException(
            status_code=400, detail="Només es poden rebutjar pressupostos en estat PENDENT."
        )

    pressupost.estat = "REBUTJAT"
    await db.commit()

    detalls_map = await carregar_detalls_pressupostos_map(db, empresa_id)
    detalls = detalls_map.get(str(pressupost.id), {})
    await desar_detalls_pressupost_disc(db, empresa_id, pressupost, detalls)
    return _serialitzar_pressupost(pressupost, client, detalls, _resolve_origin(request))


@router.post("/{pressupost_id}/convertir-ot", status_code=status.HTTP_201_CREATED)
async def convertir_pressupost_a_ordre_treball(
    pressupost_id: uuid.UUID,
    payload: Optional[PressupostConvertirOTRequest] = None,
    db: AsyncSession = Depends(get_db_with_tenant_context),
    claims: Dict[str, Any] = Depends(get_current_user_claims),
):
    """Converteix un pressupost aprovat en una Ordre de Treball amb import pressupostat vinculat."""
    empresa_id_str = claims.get("empresa_id")
    if not empresa_id_str:
        raise HTTPException(status_code=400, detail="Falta el tenant al token.")
    empresa_id = uuid.UUID(empresa_id_str)

    pressupost, client = await _carregar_pressupost_i_client(db, empresa_id, pressupost_id)
    forcar = bool(payload and payload.forcar_si_pendent)
    if pressupost.estat != "APROVAT" and not (forcar and pressupost.estat == "PENDENT"):
        raise HTTPException(
            status_code=400,
            detail="El pressupost ha d'estar en estat APROVAT abans de convertir-lo a Ordre de Treball.",
        )

    detalls_map = await carregar_detalls_pressupostos_map(db, empresa_id)
    detalls = dict(detalls_map.get(str(pressupost.id), {}))
    if detalls.get("ordre_treball_id"):
        raise HTTPException(
            status_code=400,
            detail="Aquest pressupost ja té una Ordre de Treball associada.",
        )

    if pressupost.estat == "PENDENT" and forcar:
        pressupost.estat = "APROVAT"
        pressupost.token_signatura = f"GESTIO-APROV-{pressupost.id}"

    codi_ot = f"OT-{str(uuid.uuid4())[:6].upper()}"
    titol_ot = (
        payload.titol.strip()
        if payload and payload.titol
        else str(detalls.get("titol") or f"Execució {pressupost.numero}")[:200]
    )
    adreca_ot = (
        payload.adreca.strip()
        if payload and payload.adreca
        else (client.adreca_fiscal if client and client.adreca_fiscal else "Adreça pendent de confirmar")
    )
    total_brut = float(pressupost.total) if pressupost.total is not None else 0.0
    raw_base = detalls.get("base_imposable")
    base_net = float(raw_base) if raw_base is not None else total_brut

    nova_ot = OrdreTreball(
        id=uuid.uuid4(),
        empresa_id=empresa_id,
        codi=codi_ot,
        client_id=pressupost.client_id,
        titol=titol_ot,
        adreca=adreca_ot[:255],
        descripcio=detalls.get("descripcio"),
        estat="PENDENT",
        data_planificacio=(payload.data_planificacio if payload and payload.data_planificacio else date.today()),
        import_pressupostat=float(pressupost.total or 0.0),
        import_pressupostat_net=base_net,
    )
    db.add(nova_ot)
    await db.commit()

    detalls["ordre_treball_id"] = str(nova_ot.id)
    await desar_detalls_pressupost_disc(db, empresa_id, pressupost, detalls)

    return {
        "status": "convertit",
        "pressupost_id": str(pressupost.id),
        "ordre_treball_id": str(nova_ot.id),
        "codi_ot": nova_ot.codi,
    }


@router.post("/generar-ia")
async def generar_pressupost_ia(
    prompt: str = Query(..., description="Descripció del pressupost per a la IA"),
    client_id: Optional[uuid.UUID] = Query(None, description="Client opcional"),
    db: AsyncSession = Depends(get_db_with_tenant_context),
    claims: Dict[str, Any] = Depends(get_current_user_claims),
):
    """Genera un esborrany de pressupost via Node IA Local + Catàleg al Disc de l'Empresa (Zero Fallback / Zero Mock)."""
    empresa_id_str = claims.get("empresa_id")
    if not empresa_id_str:
        raise HTTPException(status_code=400, detail="Falta el tenant al token.")
    empresa_id = uuid.UUID(empresa_id_str)
    rol = str(claims.get("rol") or "").upper()

    res_emp = await db.execute(select(Empresa).where(Empresa.id == empresa_id))
    empresa = res_emp.scalar_one_or_none()
    node_url = (empresa.node_ia_url or "").strip() if empresa and empresa.node_ia_url else ""
    disc_url = (
        getattr(empresa, "disc_dur_url", None) or ""
    ).strip() if empresa else ""

    if (
        not empresa
        or not getattr(empresa, "feature_copilot_ia", False)
        or not getattr(empresa, "node_ia_actiu", False)
        or not (node_url or disc_url)
    ):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "code": "COPILOT_DESACTIVAT",
                "message": "El Copilot IA local està desactivat per a aquesta empresa. Zero fallback a Hetzner.",
            },
        )

    articles_disc = await SovereignStorageGateway.llegir_entitats_json(
        db, empresa_id, "magatzem_articles"
    )
    ots_hist = await SovereignStorageGateway.llegir_entitats_json(
        db, empresa_id, "ots_historic"
    )

    tokens = [t for t in re.split(r"[\s,;:.!?]+", prompt.lower()) if len(t) >= 3]
    linies: List[Dict[str, Any]] = []
    total_calculat = 0.0
    te_preus_reals = True
    pot_veure_preus = rol in ("BOSS", "ADMIN", "SECRETARIA")

    for art in articles_disc:
        nom_art = str(art.get("nom") or "")
        ref_art = str(art.get("referencia_inventari") or "")
        blob = f"{nom_art} {ref_art}".lower()
        if any(tok in blob for tok in tokens):
            pvp_raw = art.get("preu_venda")
            pvp = float(pvp_raw) if (pot_veure_preus and pvp_raw is not None and float(pvp_raw) > 0) else None
            if pvp is None:
                te_preus_reals = False
            else:
                total_calculat += pvp
            linies.append(
                {
                    "concepte": nom_art or ref_art,
                    "quantitat": 1,
                    "preu_unitari": pvp,
                    "total": pvp,
                }
            )
            if len(linies) >= 5:
                break

    hist_match = [
        o
        for o in ots_hist
        if any(tok in f"{o.get('titol', '')} {o.get('descripcio', '')}".lower() for tok in tokens)
    ]

    llm_summary: Optional[str] = None
    if node_url.startswith(("http://", "https://")):
        from app.api.v1.gestio.copilot import cridar_lm_studio

        context_str = (
            f"Articles coincidents al catàleg del disc: {len(linies)}. "
            f"Feines històriques similars: {len(hist_match)}."
        )
        llm_summary = await cridar_lm_studio(
            pregunta=f"Redacta una breu justificació tècnica de pressupost per a: {prompt}",
            vertical=empresa.vertical or "SEVALOR",
            context_addicional=context_str,
            empresa=empresa,
        )
        if llm_summary is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail={
                    "code": "NODE_IA_OFFLINE",
                    "message": "El túnel Copilot / Node IA local no respon. Zero fallback a Hetzner.",
                },
            )
    elif disc_url.startswith(("http://", "https://")) and not node_url:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "code": "NODE_IA_OFFLINE",
                "message": "Falta configurar node_ia_url per al node IA local de l'empresa.",
            },
        )

    if not linies:
        te_preus_reals = False
        linies.append(
            {
                "concepte": prompt.strip()[:120],
                "quantitat": 1,
                "preu_unitari": None,
                "total": None,
            }
        )

    draft_id = str(uuid.uuid4())
    total_estimat = round(total_calculat, 2) if (pot_veure_preus and te_preus_reals and total_calculat > 0) else None
    draft_payload: Dict[str, Any] = {
        "titol": f"Esborrany Pressupost Copilot — {prompt.strip()[:60]}",
        "resum_tecnic": llm_summary,
        "feines_historiques_similars": len(hist_match),
        "linies": linies,
        "total_estimat": total_estimat,
    }

    await SovereignStorageGateway.desar_entitat_json(
        db=db,
        empresa_id=empresa_id,
        categoria="pressupostos",
        item_id=f"draft_{draft_id}",
        dades={
            "id": draft_id,
            "client_id": str(client_id) if client_id else None,
            "estat": "PENDENT_AUDITORIA",
            "origen": "COPILOT_IA",
            "draft": draft_payload,
        },
    )

    return {
        "id": draft_id,
        "estat": "PENDENT_AUDITORIA",
        "draft": draft_payload,
        "missatge": "Esborrany generat en mode PENDENT_AUDITORIA amb dades del disc sobirà.",
    }
