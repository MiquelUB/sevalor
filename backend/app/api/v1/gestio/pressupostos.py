"""Endpoints per a la gestió completa de Pressupostos, plantilla HTML/PDF WeasyPrint, edició prèvia i enviament multi-canal."""

import logging
import re
import uuid
from datetime import date, datetime, timezone
from decimal import ROUND_HALF_UP, Decimal
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import HTMLResponse, Response
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db_with_tenant_context
from app.core.security import get_current_user_claims, require_roles
from app.models.models import (
    Client,
    EinaCustodia,
    Empresa,
    OrdreTreball,
    Pressupost,
    Usuari,
    Vehicle,
)
from app.services.pressupost_service import (
    DEFAULT_VALIDESA_DIES,
    calcular_totals_pressupost_complet,
    carregar_detalls_pressupostos_map,
    construir_acceptacio_url,
    construir_mailto_url,
    desar_detalls_pressupost_disc,
    enviar_pressupost_email_smtp,
    generar_pdf_pressupost_bytes,
    generar_token_acceptacio_pressupost,
    renderitzar_html_pressupost,
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
    vehicle_id: Optional[uuid.UUID] = None
    eina_id: Optional[uuid.UUID] = None
    seccio: Optional[str] = Field(None, max_length=120)
    tipus_linia: str = Field(default="ALTRE", max_length=30)
    concepte: str = Field(..., min_length=1, max_length=200)
    detall: Optional[str] = Field(None, max_length=600)
    quantitat: float = Field(default=1.0, gt=0)
    preu_unitari: float = Field(default=0.0, ge=0.0)
    descompte_pct: float = Field(default=0.0, ge=0.0, le=100.0)
    tipus_iva: float = Field(default=21.0, ge=0.0, le=100.0)


class PressupostLiniaOut(BaseModel):
    article_id: Optional[str] = None
    vehicle_id: Optional[str] = None
    eina_id: Optional[str] = None
    seccio: Optional[str] = None
    tipus_linia: str = "ALTRE"
    concepte: str
    detall: Optional[str] = None
    quantitat: float = 1.0
    preu_unitari: float = 0.0
    descompte_pct: float = 0.0
    tipus_iva: float = 21.0
    subtotal: float = 0.0


class EinaResumOut(BaseModel):
    id: str
    nom: str
    model: Optional[str] = None
    numero_serie: Optional[str] = None


class PressupostCreate(BaseModel):
    client_id: uuid.UUID
    numero: str = Field(..., max_length=30)
    total: float = Field(default=0.00, ge=0.0)
    titol: Optional[str] = Field(None, max_length=200)
    descripcio: Optional[str] = None
    data_pressupost: Optional[date] = None
    validesa_dies: int = Field(default=DEFAULT_VALIDESA_DIES, ge=1, le=365)
    referencia_client: Optional[str] = Field(None, max_length=120)
    elaborat_per: Optional[str] = Field(None, max_length=150)

    # Dades de client autocompletables i editables per a aquest pressupost
    client_rao_social: Optional[str] = Field(None, max_length=200)
    client_nif: Optional[str] = Field(None, max_length=30)
    client_adreca: Optional[str] = Field(None, max_length=300)
    client_codi_postal: Optional[str] = Field(None, max_length=15)
    client_poblacio: Optional[str] = Field(None, max_length=100)
    client_provincia: Optional[str] = Field(None, max_length=100)
    client_persona_contacte: Optional[str] = Field(None, max_length=150)
    client_email: Optional[str] = Field(None, max_length=200)
    client_telefon: Optional[str] = Field(None, max_length=40)

    # Ubicació i recursos operatius
    finca_id: Optional[uuid.UUID] = None
    adreca_obra: Optional[str] = Field(None, max_length=300)
    vehicle_id: Optional[uuid.UUID] = None
    vehicle_nom: Optional[str] = Field(None, max_length=200)
    eines_ids: List[uuid.UUID] = Field(default_factory=list)
    desplacament_km: Optional[float] = Field(None, ge=0.0)
    desplacament_preu_km: Optional[float] = Field(None, ge=0.0)
    desplacament_import_fix: Optional[float] = Field(None, ge=0.0)

    # Econòmics, condicions i notes (plantilla oficial)
    descompte_global_pct: float = Field(default=0.0, ge=0.0, le=100.0)
    forma_pagament: Optional[str] = Field(None, max_length=200)
    percentatge_acompte: float = Field(default=0.0, ge=0.0, le=100.0)
    termini_execucio: Optional[str] = Field(None, max_length=200)
    notes_exclusions: Optional[str] = None
    mencio_legal: Optional[str] = None
    nom_signant_client: Optional[str] = Field(None, max_length=150)

    linies: Optional[List[PressupostLiniaIn]] = None


class PressupostUpdate(BaseModel):
    client_id: Optional[uuid.UUID] = None
    numero: Optional[str] = Field(None, max_length=30)
    titol: Optional[str] = Field(None, max_length=200)
    descripcio: Optional[str] = None
    data_pressupost: Optional[date] = None
    validesa_dies: Optional[int] = Field(None, ge=1, le=365)
    referencia_client: Optional[str] = Field(None, max_length=120)
    elaborat_per: Optional[str] = Field(None, max_length=150)

    client_rao_social: Optional[str] = Field(None, max_length=200)
    client_nif: Optional[str] = Field(None, max_length=30)
    client_adreca: Optional[str] = Field(None, max_length=300)
    client_codi_postal: Optional[str] = Field(None, max_length=15)
    client_poblacio: Optional[str] = Field(None, max_length=100)
    client_provincia: Optional[str] = Field(None, max_length=100)
    client_persona_contacte: Optional[str] = Field(None, max_length=150)
    client_email: Optional[str] = Field(None, max_length=200)
    client_telefon: Optional[str] = Field(None, max_length=40)

    finca_id: Optional[uuid.UUID] = None
    adreca_obra: Optional[str] = Field(None, max_length=300)
    vehicle_id: Optional[uuid.UUID] = None
    vehicle_nom: Optional[str] = Field(None, max_length=200)
    eines_ids: Optional[List[uuid.UUID]] = None
    desplacament_km: Optional[float] = Field(None, ge=0.0)
    desplacament_preu_km: Optional[float] = Field(None, ge=0.0)
    desplacament_import_fix: Optional[float] = Field(None, ge=0.0)

    descompte_global_pct: Optional[float] = Field(None, ge=0.0, le=100.0)
    forma_pagament: Optional[str] = Field(None, max_length=200)
    percentatge_acompte: Optional[float] = Field(None, ge=0.0, le=100.0)
    termini_execucio: Optional[str] = Field(None, max_length=200)
    notes_exclusions: Optional[str] = None
    mencio_legal: Optional[str] = None
    nom_signant_client: Optional[str] = Field(None, max_length=150)

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
    client_rao_social: Optional[str] = None
    client_nif: Optional[str] = None
    client_adreca: Optional[str] = None
    client_codi_postal: Optional[str] = None
    client_poblacio: Optional[str] = None
    client_provincia: Optional[str] = None
    client_persona_contacte: Optional[str] = None
    client_email: Optional[str] = None
    client_telefon: Optional[str] = None
    client_te_telegram: bool = False

    numero: str
    titol: Optional[str] = None
    descripcio: Optional[str] = None
    data_pressupost: Optional[str] = None
    validesa_dies: int = DEFAULT_VALIDESA_DIES
    referencia_client: Optional[str] = None
    elaborat_per: Optional[str] = None

    finca_id: Optional[str] = None
    adreca_obra: Optional[str] = None
    vehicle_id: Optional[str] = None
    vehicle_nom: Optional[str] = None
    eines_ids: List[str] = Field(default_factory=list)
    eines_resum: List[EinaResumOut] = Field(default_factory=list)
    desplacament_km: Optional[float] = None
    desplacament_preu_km: Optional[float] = None
    desplacament_import_fix: Optional[float] = None

    subtotal_brut: float = 0.0
    descompte_global_pct: float = 0.0
    descompte_global_import: float = 0.0
    base_imposable: float = 0.0
    quota_iva: float = 0.0
    total: float

    forma_pagament: Optional[str] = None
    percentatge_acompte: float = 0.0
    import_acompte: float = 0.0
    termini_execucio: Optional[str] = None
    notes_exclusions: Optional[str] = None
    mencio_legal: Optional[str] = None
    nom_signant_client: Optional[str] = None

    estat: str
    token_signatura: Optional[str] = None
    canal_enviament: Optional[str] = None
    email_destinatari: Optional[str] = None
    data_enviament: Optional[str] = None
    acceptacio_url: Optional[str] = None
    ordre_treball_id: Optional[str] = None
    motiu_canvis_client: Optional[str] = None
    linies: List[PressupostLiniaOut] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------
# Helpers de serialització i resolució de recursos
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


async def _resoldre_nom_elaborador(
    db: AsyncSession, empresa_id: uuid.UUID, claims: Dict[str, Any]
) -> Optional[str]:
    sub = claims.get("sub")
    if not sub:
        return None
    try:
        u_id = uuid.UUID(str(sub))
    except ValueError:
        return None
    u = (
        await db.execute(select(Usuari).where(Usuari.id == u_id, Usuari.empresa_id == empresa_id))
    ).scalar_one_or_none()
    if not u:
        return None
    nom_complet = f"{u.nom or ''} {u.cognoms or ''}".strip()
    return nom_complet or u.email or None


async def _resoldre_vehicle_nom(
    db: AsyncSession, empresa_id: uuid.UUID, vehicle_id: Optional[uuid.UUID], fallback_nom: Optional[str]
) -> Optional[str]:
    if not vehicle_id:
        return (fallback_nom or "").strip() or None
    veh = (
        await db.execute(
            select(Vehicle).where(Vehicle.id == vehicle_id, Vehicle.empresa_id == empresa_id)
        )
    ).scalar_one_or_none()
    if not veh:
        return (fallback_nom or "").strip() or None
    parts = [p for p in [veh.matricula, veh.marca, veh.model] if p and str(p).strip()]
    return " · ".join(parts) if parts else (fallback_nom or "").strip() or None


async def _resoldre_eines_resum(
    db: AsyncSession, empresa_id: uuid.UUID, eines_ids: List[uuid.UUID]
) -> List[Dict[str, Any]]:
    if not eines_ids:
        return []
    rows = (
        await db.execute(
            select(EinaCustodia).where(
                EinaCustodia.empresa_id == empresa_id,
                EinaCustodia.id.in_(eines_ids),
            )
        )
    ).scalars().all()
    by_id = {e.id: e for e in rows}
    out: List[Dict[str, Any]] = []
    for eid in eines_ids:
        eina = by_id.get(eid)
        if eina:
            out.append(
                {
                    "id": str(eina.id),
                    "nom": eina.nom,
                    "model": eina.model,
                    "numero_serie": eina.numero_serie,
                }
            )
    return out


async def _carregar_logotip_empresa_safe(
    db: AsyncSession, empresa: Optional[Empresa]
) -> tuple[Optional[bytes], str]:
    if not empresa or not empresa.logotip_path:
        return None, "image/png"
    try:
        content, filename = await SovereignStorageGateway.obtenir_bytes_fitxer(
            db=db, empresa_id=empresa.id, fitxer_path=empresa.logotip_path
        )
        if content:
            lower = (filename or "").lower()
            mime = "image/png"
            if lower.endswith((".jpg", ".jpeg")):
                mime = "image/jpeg"
            elif lower.endswith(".webp"):
                mime = "image/webp"
            elif lower.endswith(".svg"):
                mime = "image/svg+xml"
            return bytes(content), mime
    except Exception:
        pass
    return None, "image/png"


def _construir_snapshot_client(
    client: Optional[Client], dades: PressupostCreate | PressupostUpdate, existing: Optional[Dict[str, Any]] = None
) -> Dict[str, Optional[str]]:
    ext = existing or {}

    def pick(field: str, client_attr: str) -> Optional[str]:
        val = getattr(dades, field, None)
        if val is not None:
            return str(val).strip() or None
        if field in ext and ext.get(field) is not None:
            return str(ext[field]).strip() or None
        if client is not None:
            c_val = getattr(client, client_attr, None)
            if c_val is not None:
                return str(c_val).strip() or None
        return None

    return {
        "client_rao_social": pick("client_rao_social", "rao_social"),
        "client_nif": pick("client_nif", "nif"),
        "client_adreca": pick("client_adreca", "adreca_fiscal"),
        "client_codi_postal": pick("client_codi_postal", "codi_postal"),
        "client_poblacio": pick("client_poblacio", "poblacio"),
        "client_provincia": pick("client_provincia", "provincia"),
        "client_persona_contacte": pick("client_persona_contacte", "persona_contacte"),
        "client_email": pick("client_email", "email"),
        "client_telefon": pick("client_telefon", "telefon"),
    }


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
            vehicle_id=lin.get("vehicle_id"),
            eina_id=lin.get("eina_id"),
            seccio=lin.get("seccio"),
            tipus_linia=str(lin.get("tipus_linia") or "ALTRE"),
            concepte=str(lin.get("concepte") or ""),
            detall=lin.get("detall"),
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
    subtotal_brut_raw = detalls.get("subtotal_brut")
    subtotal_brut_val = (
        0.0
        if amagar_imports
        else (float(subtotal_brut_raw) if subtotal_brut_raw is not None else base_val)
    )
    dto_global_pct = float(detalls.get("descompte_global_pct") or 0.0)
    dto_global_imp = 0.0 if amagar_imports else float(detalls.get("descompte_global_import") or 0.0)
    pct_acompte = float(detalls.get("percentatge_acompte") or 0.0)
    imp_acompte = (
        0.0
        if amagar_imports
        else float(
            (Decimal(str(total_val)) * Decimal(str(pct_acompte)) / Decimal("100")).quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP
            )
        )
    )

    eines_resum_out = [
        EinaResumOut(
            id=str(e.get("id") or ""),
            nom=str(e.get("nom") or ""),
            model=e.get("model"),
            numero_serie=e.get("numero_serie"),
        )
        for e in (detalls.get("eines_resum") or [])
        if isinstance(e, dict) and e.get("nom")
    ]

    cli_rao = detalls.get("client_rao_social") or (client.rao_social if client else None)
    cli_email = detalls.get("client_email") or (client.email if client else None)
    cli_tel = detalls.get("client_telefon") or (client.telefon if client else None)

    return PressupostResponse(
        id=pressupost.id,
        empresa_id=pressupost.empresa_id,
        client_id=pressupost.client_id,
        client_nom=cli_rao,
        client_rao_social=cli_rao,
        client_nif=detalls.get("client_nif") or (client.nif if client else None),
        client_adreca=detalls.get("client_adreca") or (client.adreca_fiscal if client else None),
        client_codi_postal=detalls.get("client_codi_postal")
        or (getattr(client, "codi_postal", None) if client else None),
        client_poblacio=detalls.get("client_poblacio")
        or (getattr(client, "poblacio", None) if client else None),
        client_provincia=detalls.get("client_provincia")
        or (getattr(client, "provincia", None) if client else None),
        client_persona_contacte=detalls.get("client_persona_contacte")
        or (getattr(client, "persona_contacte", None) if client else None),
        client_email=cli_email,
        client_telefon=cli_tel,
        client_te_telegram=bool(
            client and client.telegram_chat_id and client.estat_canal_telegram == "ACTIU"
        ),
        numero=pressupost.numero,
        titol=detalls.get("titol"),
        descripcio=detalls.get("descripcio"),
        data_pressupost=detalls.get("data_pressupost")
        or (pressupost.created_at.date().isoformat() if pressupost.created_at else None),
        validesa_dies=int(detalls.get("validesa_dies") or DEFAULT_VALIDESA_DIES),
        referencia_client=detalls.get("referencia_client"),
        elaborat_per=detalls.get("elaborat_per"),
        finca_id=detalls.get("finca_id"),
        adreca_obra=detalls.get("adreca_obra"),
        vehicle_id=detalls.get("vehicle_id"),
        vehicle_nom=detalls.get("vehicle_nom"),
        eines_ids=[str(x) for x in (detalls.get("eines_ids") or [])],
        eines_resum=eines_resum_out,
        desplacament_km=detalls.get("desplacament_km"),
        desplacament_preu_km=detalls.get("desplacament_preu_km"),
        desplacament_import_fix=detalls.get("desplacament_import_fix"),
        subtotal_brut=subtotal_brut_val,
        descompte_global_pct=dto_global_pct,
        descompte_global_import=dto_global_imp,
        base_imposable=base_val,
        quota_iva=iva_val,
        total=total_val,
        forma_pagament=detalls.get("forma_pagament"),
        percentatge_acompte=pct_acompte,
        import_acompte=imp_acompte,
        termini_execucio=detalls.get("termini_execucio"),
        notes_exclusions=detalls.get("notes_exclusions"),
        mencio_legal=detalls.get("mencio_legal"),
        nom_signant_client=detalls.get("nom_signant_client"),
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


@router.get("/seguent-numero")
async def obtenir_seguent_numero_pressupost(
    db: AsyncSession = Depends(get_db_with_tenant_context),
    claims: Dict[str, Any] = Depends(get_current_user_claims),
) -> Dict[str, Any]:
    """Proposa el següent número correlatiu de pressupost de l'exercici actual (ex: P-2026/001)."""
    empresa_id_str = claims.get("empresa_id")
    if not empresa_id_str:
        raise HTTPException(status_code=400, detail="Falta el tenant al token.")
    empresa_id = uuid.UUID(empresa_id_str)
    any_actual = date.today().year
    prefix = f"P-{any_actual}/"

    rows = (
        await db.execute(
            select(Pressupost.numero).where(
                Pressupost.empresa_id == empresa_id,
                Pressupost.numero.like(f"{prefix}%"),
            )
        )
    ).scalars().all()

    max_seq = 0
    for num in rows:
        m = re.search(r"/(\d+)$", str(num or ""))
        if m:
            max_seq = max(max_seq, int(m.group(1)))

    seguent = f"{prefix}{max_seq + 1:03d}"
    elaborat_per = await _resoldre_nom_elaborador(db, empresa_id, claims)
    return {
        "numero": seguent,
        "any": any_actual,
        "sequencia": max_seq + 1,
        "elaborat_per": elaborat_per,
    }


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
    amagar_imports = False

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
    """Crea un nou pressupost en estat PENDENT amb tots els camps de la plantilla i recursos, sincronitzat al disc."""
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

    dup_num = (
        await db.execute(
            select(Pressupost.id).where(
                Pressupost.empresa_id == empresa_id,
                Pressupost.numero == dades.numero.strip(),
            )
        )
    ).first()
    if dup_num:
        raise HTTPException(
            status_code=400,
            detail=f"Ja existeix un pressupost amb el número '{dades.numero.strip()}'.",
        )

    linies_norm: List[Dict[str, Any]] = []
    subtotal_brut = float(dades.total)
    dto_global_pct = float(dades.descompte_global_pct or 0.0)
    dto_global_imp = 0.0
    base_imp = float(dades.total)
    quota_iva = 0.0
    total_final = float(dades.total)

    if dades.linies:
        calc = calcular_totals_pressupost_complet(
            [lin.model_dump() for lin in dades.linies],
            descompte_global_pct=dto_global_pct,
        )
        linies_norm = calc["linies"]
        subtotal_brut = calc["subtotal_brut"]
        dto_global_pct = calc["descompte_global_pct"]
        dto_global_imp = calc["descompte_global_import"]
        base_imp = calc["base_imposable"]
        quota_iva = calc["quota_iva"]
        total_final = calc["total"]

    elaborat_per = (dades.elaborat_per or "").strip() or await _resoldre_nom_elaborador(
        db, empresa_id, claims
    )
    vehicle_nom = await _resoldre_vehicle_nom(db, empresa_id, dades.vehicle_id, dades.vehicle_nom)
    eines_resum = await _resoldre_eines_resum(db, empresa_id, dades.eines_ids)

    nou_pressupost = Pressupost(
        id=uuid.uuid4(),
        empresa_id=empresa_id,
        client_id=dades.client_id,
        numero=dades.numero.strip(),
        total=total_final,
        estat="PENDENT",
    )
    db.add(nou_pressupost)
    await db.commit()

    client_snap = _construir_snapshot_client(client, dades)
    detalls: Dict[str, Any] = {
        **client_snap,
        "titol": dades.titol.strip() if dades.titol else f"Pressupost {dades.numero.strip()}",
        "descripcio": dades.descripcio.strip() if dades.descripcio else None,
        "data_pressupost": (dades.data_pressupost or date.today()).isoformat(),
        "validesa_dies": dades.validesa_dies,
        "referencia_client": dades.referencia_client.strip() if dades.referencia_client else None,
        "elaborat_per": elaborat_per,
        "finca_id": str(dades.finca_id) if dades.finca_id else None,
        "adreca_obra": dades.adreca_obra.strip() if dades.adreca_obra else None,
        "vehicle_id": str(dades.vehicle_id) if dades.vehicle_id else None,
        "vehicle_nom": vehicle_nom,
        "eines_ids": [str(eid) for eid in dades.eines_ids],
        "eines_resum": eines_resum,
        "desplacament_km": dades.desplacament_km,
        "desplacament_preu_km": dades.desplacament_preu_km,
        "desplacament_import_fix": dades.desplacament_import_fix,
        "linies": linies_norm,
        "subtotal_brut": subtotal_brut,
        "descompte_global_pct": dto_global_pct,
        "descompte_global_import": dto_global_imp,
        "base_imposable": base_imp,
        "quota_iva": quota_iva,
        "forma_pagament": dades.forma_pagament.strip() if dades.forma_pagament else None,
        "percentatge_acompte": float(dades.percentatge_acompte or 0.0),
        "termini_execucio": dades.termini_execucio.strip() if dades.termini_execucio else None,
        "notes_exclusions": dades.notes_exclusions.strip() if dades.notes_exclusions else None,
        "mencio_legal": dades.mencio_legal.strip() if dades.mencio_legal else None,
        "nom_signant_client": dades.nom_signant_client.strip() if dades.nom_signant_client else None,
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

    pressupost, client = await _carregar_pressupost_i_client(db, empresa_id, pressupost_id)
    detalls_map = await carregar_detalls_pressupostos_map(db, empresa_id)
    return _serialitzar_pressupost(
        pressupost,
        client,
        detalls_map.get(str(pressupost.id), {}),
        _resolve_origin(request),
        amagar_imports=False,
    )


@router.put("/{pressupost_id}", response_model=PressupostResponse)
async def editar_pressupost(
    request: Request,
    pressupost_id: uuid.UUID,
    dades: PressupostUpdate,
    db: AsyncSession = Depends(get_db_with_tenant_context),
    claims: Dict[str, Any] = Depends(get_current_user_claims),
):
    """Edita qualsevol camp d'un pressupost abans que estigui APROVAT (reobre a PENDENT si havia estat REBUTJAT)."""
    empresa_id_str = claims.get("empresa_id")
    if not empresa_id_str:
        raise HTTPException(status_code=400, detail="Falta el tenant al token.")
    empresa_id = uuid.UUID(empresa_id_str)

    pressupost, client = await _carregar_pressupost_i_client(db, empresa_id, pressupost_id)
    if pressupost.estat == "APROVAT":
        raise HTTPException(
            status_code=400,
            detail="No es pot editar un pressupost ja APROVAT pel client.",
        )

    detalls_map = await carregar_detalls_pressupostos_map(db, empresa_id)
    detalls = dict(detalls_map.get(str(pressupost.id), {}))
    fields_set = dades.model_fields_set

    if "numero" in fields_set and dades.numero and dades.numero.strip() != pressupost.numero:
        if detalls.get("canal_enviament"):
            raise HTTPException(
                status_code=400,
                detail="No es pot canviar el número d'un pressupost que ja s'ha enviat al client.",
            )
        nou_num = dades.numero.strip()
        dup = (
            await db.execute(
                select(Pressupost.id).where(
                    Pressupost.empresa_id == empresa_id,
                    Pressupost.numero == nou_num,
                    Pressupost.id != pressupost.id,
                )
            )
        ).first()
        if dup:
            raise HTTPException(status_code=400, detail=f"El número '{nou_num}' ja existeix.")
        pressupost.numero = nou_num

    client_canviat = False
    if "client_id" in fields_set and dades.client_id and dades.client_id != pressupost.client_id:
        cli_nou = (
            await db.execute(
                select(Client).where(Client.id == dades.client_id, Client.empresa_id == empresa_id)
            )
        ).scalars().first()
        if not cli_nou:
            raise HTTPException(status_code=404, detail="Client destí no trobat.")
        pressupost.client_id = dades.client_id
        client = cli_nou
        client_canviat = True

    # Snapshot de client: si canvia client i no s'envien overrides, refresquem des del nou client
    client_snap = _construir_snapshot_client(
        client, dades, existing=None if client_canviat else detalls
    )
    detalls.update(client_snap)

    for str_field in (
        "titol",
        "descripcio",
        "referencia_client",
        "elaborat_per",
        "adreca_obra",
        "forma_pagament",
        "termini_execucio",
        "notes_exclusions",
        "mencio_legal",
        "nom_signant_client",
    ):
        if str_field in fields_set:
            val = getattr(dades, str_field)
            detalls[str_field] = val.strip() if isinstance(val, str) and val.strip() else None

    if "data_pressupost" in fields_set and dades.data_pressupost is not None:
        detalls["data_pressupost"] = dades.data_pressupost.isoformat()
    if "validesa_dies" in fields_set and dades.validesa_dies is not None:
        detalls["validesa_dies"] = dades.validesa_dies
    if "finca_id" in fields_set:
        detalls["finca_id"] = str(dades.finca_id) if dades.finca_id else None
    if "vehicle_id" in fields_set or "vehicle_nom" in fields_set:
        v_id = dades.vehicle_id if "vehicle_id" in fields_set else (
            uuid.UUID(detalls["vehicle_id"]) if detalls.get("vehicle_id") else None
        )
        v_nom_in = dades.vehicle_nom if "vehicle_nom" in fields_set else None
        detalls["vehicle_id"] = str(v_id) if v_id else None
        detalls["vehicle_nom"] = await _resoldre_vehicle_nom(db, empresa_id, v_id, v_nom_in)
    if "eines_ids" in fields_set:
        e_ids = dades.eines_ids or []
        detalls["eines_ids"] = [str(eid) for eid in e_ids]
        detalls["eines_resum"] = await _resoldre_eines_resum(db, empresa_id, e_ids)

    for num_field in (
        "desplacament_km",
        "desplacament_preu_km",
        "desplacament_import_fix",
        "percentatge_acompte",
    ):
        if num_field in fields_set:
            detalls[num_field] = getattr(dades, num_field)

    dto_global_pct = (
        float(dades.descompte_global_pct or 0.0)
        if "descompte_global_pct" in fields_set
        else float(detalls.get("descompte_global_pct") or 0.0)
    )

    if dades.linies is not None:
        calc = calcular_totals_pressupost_complet(
            [lin.model_dump() for lin in dades.linies],
            descompte_global_pct=dto_global_pct,
        )
        detalls["linies"] = calc["linies"]
        detalls["subtotal_brut"] = calc["subtotal_brut"]
        detalls["descompte_global_pct"] = calc["descompte_global_pct"]
        detalls["descompte_global_import"] = calc["descompte_global_import"]
        detalls["base_imposable"] = calc["base_imposable"]
        detalls["quota_iva"] = calc["quota_iva"]
        pressupost.total = calc["total"]
    elif "descompte_global_pct" in fields_set and detalls.get("linies"):
        calc = calcular_totals_pressupost_complet(
            detalls["linies"],
            descompte_global_pct=dto_global_pct,
        )
        detalls["linies"] = calc["linies"]
        detalls["subtotal_brut"] = calc["subtotal_brut"]
        detalls["descompte_global_pct"] = calc["descompte_global_pct"]
        detalls["descompte_global_import"] = calc["descompte_global_import"]
        detalls["base_imposable"] = calc["base_imposable"]
        detalls["quota_iva"] = calc["quota_iva"]
        pressupost.total = calc["total"]
    elif dades.total is not None:
        pressupost.total = float(dades.total)
        detalls["subtotal_brut"] = float(dades.total)
        detalls["base_imposable"] = float(dades.total)
        detalls["quota_iva"] = 0.0

    # Si el client havia demanat canvis (REBUTJAT), en editar-lo el reobrim a PENDENT per poder re-enviar
    if pressupost.estat == "REBUTJAT":
        pressupost.estat = "PENDENT"

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


@router.get("/{pressupost_id}/html", response_class=HTMLResponse)
async def previsualitzar_pressupost_html(
    pressupost_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_with_tenant_context),
    claims: Dict[str, Any] = Depends(get_current_user_claims),
) -> HTMLResponse:
    """Retorna l'HTML renderitzat amb la plantilla oficial per revisar el pressupost abans d'enviar-lo."""
    empresa_id_str = claims.get("empresa_id")
    if not empresa_id_str:
        raise HTTPException(status_code=400, detail="Falta el tenant al token.")
    empresa_id = uuid.UUID(empresa_id_str)

    pressupost, client = await _carregar_pressupost_i_client(db, empresa_id, pressupost_id)
    empresa = (await db.execute(select(Empresa).where(Empresa.id == empresa_id))).scalar_one_or_none()
    detalls_map = await carregar_detalls_pressupostos_map(db, empresa_id)
    detalls = detalls_map.get(str(pressupost.id), {})
    logo_bytes, logo_mime = await _carregar_logotip_empresa_safe(db, empresa)

    html_str = renderitzar_html_pressupost(
        empresa=empresa,
        client=client,
        pressupost=pressupost,
        detalls=detalls,
        logotip_bytes=logo_bytes,
        logotip_mime=logo_mime,
    )
    return HTMLResponse(content=html_str)


@router.get("/{pressupost_id}/pdf")
async def descarregar_pressupost_pdf(
    request: Request,
    pressupost_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_with_tenant_context),
    claims: Dict[str, Any] = Depends(get_current_user_claims),
) -> Response:
    """Genera i retorna el PDF oficial del pressupost renderitzat des de la plantilla HTML amb WeasyPrint."""
    empresa_id_str = claims.get("empresa_id")
    if not empresa_id_str:
        raise HTTPException(status_code=400, detail="Falta el tenant al token.")
    empresa_id = uuid.UUID(empresa_id_str)

    pressupost, client = await _carregar_pressupost_i_client(db, empresa_id, pressupost_id)
    empresa = (await db.execute(select(Empresa).where(Empresa.id == empresa_id))).scalar_one_or_none()
    detalls_map = await carregar_detalls_pressupostos_map(db, empresa_id)
    detalls = detalls_map.get(str(pressupost.id), {})
    logo_bytes, logo_mime = await _carregar_logotip_empresa_safe(db, empresa)

    token = generar_token_acceptacio_pressupost(empresa_id, pressupost.id)
    acceptacio_url = construir_acceptacio_url(_resolve_origin(request), token)
    pdf_bytes = generar_pdf_pressupost_bytes(
        empresa=empresa,
        client=client,
        pressupost=pressupost,
        detalls=detalls,
        acceptacio_url=acceptacio_url,
        logotip_bytes=logo_bytes,
        logotip_mime=logo_mime,
    )
    safe_num = re.sub(r"[^A-Za-z0-9._-]+", "_", pressupost.numero)
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'inline; filename="PRESSUPOST_{safe_num}.pdf"'
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
    detalls_map = await carregar_detalls_pressupostos_map(db, empresa_id)
    detalls = dict(detalls_map.get(str(pressupost.id), {}))

    dest_email = (
        payload.email_destinatari.strip()
        if payload and payload.email_destinatari
        else (detalls.get("client_email") or (client.email if client else "") or "").strip()
    )
    if not dest_email or "@" not in dest_email:
        raise HTTPException(
            status_code=400,
            detail="El client no té un correu electrònic vàlid configurat. Introdueix-lo manualment.",
        )

    empresa = (await db.execute(select(Empresa).where(Empresa.id == empresa_id))).scalar_one_or_none()
    logo_bytes, logo_mime = await _carregar_logotip_empresa_safe(db, empresa)

    token = generar_token_acceptacio_pressupost(empresa_id, pressupost.id)
    acceptacio_url = construir_acceptacio_url(_resolve_origin(request), token)
    pdf_bytes = generar_pdf_pressupost_bytes(
        empresa=empresa,
        client=client,
        pressupost=pressupost,
        detalls=detalls,
        acceptacio_url=acceptacio_url,
        logotip_bytes=logo_bytes,
        logotip_mime=logo_mime,
    )

    empresa_nom = empresa.nom if empresa else "Sevalor Suite"
    titol = detalls.get("titol") or f"Pressupost {pressupost.numero}"
    assumpte = (
        payload.assumpte.strip()
        if payload and payload.assumpte
        else f"Pressupost {pressupost.numero} — {titol} ({empresa_nom})"
    )
    cli_nom = detalls.get("client_rao_social") or (client.rao_social if client else "")
    cos_defecte = (
        f"Bon dia{' ' + cli_nom if cli_nom else ''},\n\n"
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
    detalls = dict(detalls_map.get(str(pressupost.id), {}))
    detalls["data_resposta_client"] = datetime.now(timezone.utc).isoformat()
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
    """Converteix un pressupost aprovat en una Ordre de Treball traspassant adreça, vehicle, finca i descripció."""
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
        else (
            detalls.get("adreca_obra")
            or detalls.get("client_adreca")
            or (client.adreca_fiscal if client and client.adreca_fiscal else "Adreça pendent de confirmar")
        )
    )

    finca_uuid: Optional[uuid.UUID] = None
    if detalls.get("finca_id"):
        try:
            finca_uuid = uuid.UUID(str(detalls["finca_id"]))
        except ValueError:
            finca_uuid = None

    vehicle_uuid: Optional[uuid.UUID] = None
    if detalls.get("vehicle_id"):
        try:
            vehicle_uuid = uuid.UUID(str(detalls["vehicle_id"]))
        except ValueError:
            vehicle_uuid = None

    desc_parts = [p for p in [detalls.get("descripcio")] if p and str(p).strip()]
    eines_resum = detalls.get("eines_resum") or []
    if eines_resum:
        eines_str = ", ".join(str(e.get("nom") or "") for e in eines_resum if isinstance(e, dict) and e.get("nom"))
        if eines_str:
            desc_parts.append(f"Eines previstes ({pressupost.numero}): {eines_str}")
    descripcio_ot = "\n\n".join(desc_parts) if desc_parts else None

    total_brut = float(pressupost.total) if pressupost.total is not None else 0.0
    raw_base = detalls.get("base_imposable")
    base_net = float(raw_base) if raw_base is not None else total_brut

    nova_ot = OrdreTreball(
        id=uuid.uuid4(),
        empresa_id=empresa_id,
        codi=codi_ot,
        client_id=pressupost.client_id,
        finca_id=finca_uuid,
        vehicle_id=vehicle_uuid,
        titol=titol_ot,
        adreca=str(adreca_ot)[:255],
        descripcio=descripcio_ot,
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
    if (
        not empresa
        or not getattr(empresa, "feature_copilot_ia", False)
        or not getattr(empresa, "node_ia_actiu", False)
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
                    "seccio": "Materials",
                    "tipus_linia": "MATERIAL",
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
    from app.api.v1.gestio.copilot import cridar_lm_studio
    from app.services.vault_tunnel import empresa_target_key, vault_tunnel_broker

    if await vault_tunnel_broker.is_online(empresa_target_key(empresa_id)):
        context_str = (
            f"Articles coincidents al catàleg del disc: {len(linies)}. "
            f"Feines històriques similars: {len(hist_match)}."
        )
        llm_summary = await cridar_lm_studio(
            pregunta=f"Redacta una breu justificació tècnica de pressupost per a: {prompt}",
            vertical=empresa.vertical or "SEVALOR",
            context_addicional=context_str,
            empresa=empresa,
            db=db,
        )
        if llm_summary is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail={
                    "code": "NODE_IA_OFFLINE",
                    "message": "El PC de l'empresa està connectat, però LM Studio/Ollama local no respon a 127.0.0.1:1234. Zero fallback a Hetzner.",
                },
            )
    else:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "code": "NODE_IA_OFFLINE",
                "message": "L'ordinador dedicat de l'empresa no està connectat al túnel WSS de Sevalor. Zero fallback a Hetzner.",
            },
        )

    if not linies:
        te_preus_reals = False
        linies.append(
            {
                "seccio": "Treballs tècnics",
                "tipus_linia": "MA_OBRA",
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
            "prompt": prompt,
            "draft": draft_payload,
            "created_at": datetime.now(timezone.utc).isoformat(),
        },
    )

    return {
        "id": draft_id,
        "status": "PENDENT_AUDITORIA",
        "estat": "PENDENT_AUDITORIA",
        "draft": draft_payload,
        "missatge": "Proposta PENDENT_AUDITORIA desada al disc de l'empresa per a validació humana (HITL).",
    }
