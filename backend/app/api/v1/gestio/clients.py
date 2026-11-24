import logging
import uuid
from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Sequence

import filetype  # type: ignore[import-untyped]
from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field, ValidationError, field_validator
from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db_with_tenant_context
from app.core.security import require_roles
from app.models.models import Client, Finca
from app.services.codis_service import generar_seguent_codi
from app.services.csv_service import CsvImportResult, generate_csv_content
from app.services.sovereign_storage import SovereignStorageGateway
from app.services.subagents.dispatcher import copilot_dispatcher

logger = logging.getLogger("sevalor.clients")

router = APIRouter(
    prefix="/gestio/clients",
    tags=["Gestió Clients"],
    dependencies=[Depends(require_roles(["BOSS", "SECRETARIA", "ENGINYER"]))],
)


def _resolve_emp_uuid(request: Request, claims: Optional[dict[str, Any]] = None) -> uuid.UUID:
    raw = (
        getattr(request.state, "empresa_id", None)
        or (claims.get("empresa_id") if claims else None)
        or request.headers.get("X-Empresa-ID")
    )
    if not raw or str(raw) in ("undefined", "null", "None"):
        raise HTTPException(status_code=401, detail="No identificat")
    try:
        return uuid.UUID(str(raw))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Identificador d'empresa invàlid") from exc


def _serialitzar_client(c: Client, rol: str) -> dict[str, Any]:
    """Serialitza Client aplicant Principi VI (oculta IBAN complet a ENGINYER)."""
    is_enginyer = rol.upper() == "ENGINYER"
    return {
        "id": c.id,
        "codi": c.codi,
        "rao_social": c.rao_social,
        "nif": c.nif,
        "telefon": c.telefon,
        "email": c.email,
        "adreca_fiscal": c.adreca_fiscal,
        "codi_postal": c.codi_postal,
        "poblacio": c.poblacio,
        "provincia": c.provincia,
        "web": c.web,
        "persona_contacte": c.persona_contacte,
        "dades_contacte": c.dades_contacte,
        "iban": None if is_enginyer else c.iban_xifrat_simetric,
        "estat_canal_telegram": c.estat_canal_telegram or "INACTIU",
        "actiu": bool(c.actiu) if c.actiu is not None else True,
    }


class ClientCreate(BaseModel):
    codi: Optional[str] = Field(None, max_length=20)
    rao_social: str = Field(..., max_length=200)
    nif: str = Field(..., max_length=20)
    telefon: Optional[str] = Field(None, max_length=30)
    email: Optional[str] = Field(None, max_length=200)
    adreca_fiscal: Optional[str] = Field(None)
    codi_postal: Optional[str] = Field(None, max_length=15)
    poblacio: Optional[str] = Field(None, max_length=100)
    provincia: Optional[str] = Field(None, max_length=100)
    web: Optional[str] = Field(None, max_length=255)
    persona_contacte: Optional[str] = Field(None, max_length=150)
    dades_contacte: Optional[str] = Field(None)
    iban: Optional[str] = Field(None, max_length=34)

    @field_validator("nif")
    @classmethod
    def validate_nif(cls, v: str) -> str:
        import re

        v = v.upper().replace("-", "").replace(" ", "").replace(".", "")
        if len(v) == 11 and v.startswith("ES"):
            v = v[2:]
        if not re.match(r"^[A-Z0-9]{9}$", v):
            raise ValueError("El NIF/CIF ha de tenir 9 caràcters alfanumèrics")
        return v

    @field_validator("iban")
    @classmethod
    def validate_iban(cls, v: Optional[str]) -> Optional[str]:
        if not v:
            return v
        v = v.upper().replace(" ", "")
        if len(v) < 15 or len(v) > 34:
            raise ValueError("Longitud d'IBAN invàlida")
        if not v.isalnum():
            raise ValueError("L'IBAN només pot contenir lletres i números")
        # Modulo 97 check
        # Move first 4 chars to the end
        rearranged = v[4:] + v[:4]
        # Convert letters to numbers
        numeric_iban = ""
        for char in rearranged:
            if char.isalpha():
                numeric_iban += str(ord(char) - 55)
            else:
                numeric_iban += char
        if int(numeric_iban) % 97 != 1:
            raise ValueError("L'IBAN no és vàlid")
        return v


class ClientResponse(BaseModel):
    id: uuid.UUID
    codi: str
    rao_social: str
    nif: str = ""
    telefon: Optional[str] = None
    email: Optional[str] = None
    adreca_fiscal: Optional[str] = None
    codi_postal: Optional[str] = None
    poblacio: Optional[str] = None
    provincia: Optional[str] = None
    web: Optional[str] = None
    persona_contacte: Optional[str] = None
    dades_contacte: Optional[str] = None
    iban: Optional[str] = None
    estat_canal_telegram: str
    actiu: bool
    model_config = {"from_attributes": True}


class ClientCsvImportRow(BaseModel):
    """Esquema tolerant per a importació CSV: cap camp buit o null atura l'extracció."""

    codi: Optional[str] = None
    rao_social: Optional[str] = None
    nif: Optional[str] = None
    telefon: Optional[str] = None
    email: Optional[str] = None
    adreca_fiscal: Optional[str] = None
    web: Optional[str] = None
    persona_contacte: Optional[str] = None
    dades_contacte: Optional[str] = None
    iban: Optional[str] = None


class ClientAmbIBANResponse(BaseModel):
    id: uuid.UUID
    rao_social: str
    iban_xifrat_simetric: Optional[str]


class CanviIBANRequest(BaseModel):
    nou_iban: str = Field(..., min_length=15, max_length=34)


@router.get("", response_model=List[ClientResponse])
async def llistar_clients(
    request: Request,
    q: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    claims: Dict[str, Any] = Depends(require_roles(["BOSS", "SECRETARIA", "ENGINYER"])),
    db: AsyncSession = Depends(get_db_with_tenant_context),
) -> List[Dict[str, Any]]:
    emp_uuid = _resolve_emp_uuid(request, claims)
    rol = str(claims.get("rol", "")).upper()

    stmt = select(Client).where(Client.empresa_id == emp_uuid)

    if q:
        search_term = f"%{q}%"
        stmt = stmt.where(
            or_(
                Client.codi.ilike(search_term),
                Client.rao_social.ilike(search_term),
                Client.nif.ilike(search_term),
            )
        )

    stmt = stmt.limit(limit).offset(offset).order_by(Client.created_at.desc())

    result = await db.execute(stmt)
    clients = result.scalars().all()

    return [_serialitzar_client(c, rol) for c in clients]


@router.post("", response_model=ClientResponse, status_code=status.HTTP_201_CREATED)
async def alta_client(
    request: Request,
    client: ClientCreate,
    claims: Dict[str, Any] = Depends(require_roles(["BOSS", "SECRETARIA", "ENGINYER"])),
    db: AsyncSession = Depends(get_db_with_tenant_context),
) -> Dict[str, Any]:
    emp_uuid = _resolve_emp_uuid(request, claims)
    rol = str(claims.get("rol", "")).upper()

    stmt_nif = select(Client).where(
        Client.empresa_id == emp_uuid, Client.nif == client.nif
    )
    result_nif = await db.execute(stmt_nif)
    if result_nif.scalars().first():
        raise HTTPException(
            status_code=400, detail="El NIF/CIF ja es troba registrat en el sistema"
        )

    codi_auto = await generar_seguent_codi(db, Client, emp_uuid, "CLI")

    nou_client = Client(
        empresa_id=emp_uuid,
        codi=codi_auto,
        rao_social=client.rao_social,
        nif=client.nif,
        telefon=client.telefon,
        email=client.email,
        adreca_fiscal=client.adreca_fiscal,
        codi_postal=client.codi_postal,
        poblacio=client.poblacio,
        provincia=client.provincia,
        web=client.web,
        persona_contacte=client.persona_contacte,
        dades_contacte=client.dades_contacte,
        iban_xifrat_simetric=None if rol == "ENGINYER" else client.iban,
    )

    db.add(nou_client)
    await db.commit()

    try:
        ruta = await SovereignStorageGateway.desar_entitat_json(
            db=db,
            empresa_id=emp_uuid,
            categoria="clients",
            item_id=str(nou_client.id),
            dades={
                "id": str(nou_client.id),
                "codi": nou_client.codi,
                "rao_social": nou_client.rao_social,
                "nif": nou_client.nif,
                "telefon": nou_client.telefon,
                "email": nou_client.email,
                "adreca_fiscal": nou_client.adreca_fiscal,
                "web": nou_client.web,
                "persona_contacte": nou_client.persona_contacte,
                "dades_contacte": nou_client.dades_contacte,
            },
        )
        if not str(ruta).startswith("transit://"):
            await SovereignStorageGateway.drenar_cua_transit_empresa(db, emp_uuid)
    except Exception as exc:
        logger.warning("No s'ha pogut sincronitzar client %s al disc sobirà: %s", nou_client.id, exc)

    return _serialitzar_client(nou_client, rol)


@router.put("/{client_id}", response_model=ClientResponse)
async def modificar_client(
    request: Request,
    client_id: uuid.UUID,
    payload: ClientCreate,
    claims: Dict[str, Any] = Depends(require_roles(["BOSS", "SECRETARIA", "ENGINYER"])),
    db: AsyncSession = Depends(get_db_with_tenant_context),
) -> Dict[str, Any]:
    """Actualitza la fitxa d'un client preservant l'IBAN i l'aïllament per rol (ENGINYER)."""
    emp_uuid = _resolve_emp_uuid(request, claims)
    rol = str(claims.get("rol", "")).upper()

    client_db = (
        await db.execute(
            select(Client).where(Client.id == client_id, Client.empresa_id == emp_uuid)
        )
    ).scalars().first()
    if not client_db:
        raise HTTPException(status_code=404, detail="Client no trobat")

    if client_db.nif != payload.nif:
        dup_nif = (
            await db.execute(
                select(Client.id).where(
                    Client.empresa_id == emp_uuid,
                    Client.nif == payload.nif,
                    Client.id != client_id,
                )
            )
        ).first()
        if dup_nif:
            raise HTTPException(status_code=400, detail="Ja existeix un altre client amb aquest NIF")

    # El codi del client s'assigna automàticament i no s'altera manualment
    client_db.rao_social = payload.rao_social
    client_db.nif = payload.nif
    client_db.telefon = payload.telefon
    client_db.email = payload.email
    client_db.adreca_fiscal = payload.adreca_fiscal
    if payload.codi_postal is not None:
        client_db.codi_postal = payload.codi_postal
    if payload.poblacio is not None:
        client_db.poblacio = payload.poblacio
    if payload.provincia is not None:
        client_db.provincia = payload.provincia
    client_db.web = payload.web
    client_db.persona_contacte = payload.persona_contacte
    client_db.dades_contacte = payload.dades_contacte
    if rol != "ENGINYER" and payload.iban is not None:
        client_db.iban_xifrat_simetric = payload.iban or None

    await db.commit()

    try:
        ruta = await SovereignStorageGateway.desar_entitat_json(
            db=db,
            empresa_id=emp_uuid,
            categoria="clients",
            item_id=str(client_db.id),
            dades={
                "id": str(client_db.id),
                "codi": client_db.codi,
                "rao_social": client_db.rao_social,
                "nif": client_db.nif,
                "telefon": client_db.telefon,
                "email": client_db.email,
                "adreca_fiscal": client_db.adreca_fiscal,
                "web": client_db.web,
                "persona_contacte": client_db.persona_contacte,
                "dades_contacte": client_db.dades_contacte,
            },
        )
        if not str(ruta).startswith("transit://"):
            await SovereignStorageGateway.drenar_cua_transit_empresa(db, emp_uuid)
    except Exception as exc:
        logger.warning("No s'ha pogut sincronitzar client %s al disc sobirà: %s", client_db.id, exc)

    return _serialitzar_client(client_db, rol)


# ---------------------------------------------------------------------------
# IBAN xifrat — Veto d'Enginyer (Spec 002). BOSS/SECRETARIA poden accedir-hi.
# ---------------------------------------------------------------------------


@router.get(
    "/{client_id}/iban",
    response_model=ClientAmbIBANResponse,
    dependencies=[Depends(require_roles(["BOSS", "SECRETARIA"]))],
)
async def obtenir_iban_client(
    request: Request, client_id: uuid.UUID, db: AsyncSession = Depends(get_db_with_tenant_context)
) -> Dict[str, Any]:
    """Retorna l'IBAN complet del client. Enginyer rep 403."""
    empresa_id = getattr(request.state, "empresa_id", None) or request.headers.get("X-Empresa-ID")
    if not empresa_id or empresa_id == "undefined":
        raise HTTPException(status_code=401, detail="No identificat")
    res = await db.execute(
        select(Client).where(Client.id == client_id, Client.empresa_id == uuid.UUID(empresa_id))
    )
    client = res.scalars().first()
    if not client:
        raise HTTPException(status_code=404, detail="Client no trobat")
    return {
        "id": client.id,
        "rao_social": client.rao_social,
        "iban_xifrat_simetric": client.iban_xifrat_simetric,
    }


@router.put(
    "/{client_id}/iban",
    response_model=ClientAmbIBANResponse,
    dependencies=[Depends(require_roles(["BOSS", "SECRETARIA"]))],
)
async def canviar_iban_client(
    request: Request,
    client_id: uuid.UUID,
    payload: CanviIBANRequest,
    db: AsyncSession = Depends(get_db_with_tenant_context),
) -> Dict[str, Any]:
    """Canvia l'IBAN d'un client (Spec 002). Enginyer rep 403."""
    empresa_id = getattr(request.state, "empresa_id", None) or request.headers.get("X-Empresa-ID")
    if not empresa_id or empresa_id == "undefined":
        raise HTTPException(status_code=401, detail="No identificat")
    res = await db.execute(
        select(Client).where(Client.id == client_id, Client.empresa_id == uuid.UUID(empresa_id))
    )
    client = res.scalars().first()
    if not client:
        raise HTTPException(status_code=404, detail="Client no trobat")
    client.iban_xifrat_simetric = payload.nou_iban
    await db.commit()
    return {
        "id": client.id,
        "rao_social": client.rao_social,
        "iban_xifrat_simetric": client.iban_xifrat_simetric,
    }


# ---------------------------------------------------------------------------
# Fitxa 360° del Client (Spec 012 RF-04 & Spec 002)
# ---------------------------------------------------------------------------


class FincaFitxa360(BaseModel):
    id: uuid.UUID
    nom: str
    adreca: Optional[str] = None
    superficie_ha: Optional[float] = None
    dades_sigpac: Optional[Dict[str, Any]] = None


class PecaInstaladaFitxa360(BaseModel):
    article_id: uuid.UUID
    codi_article: str
    nom_article: str
    quantitat_instalada: float
    unitat_mesura: str
    data_instalacio: datetime
    ordre_treball_id: uuid.UUID
    ordre_treball_codi: str


class IncidenciaFitxa360(BaseModel):
    id: uuid.UUID
    ordre_treball_id: Optional[uuid.UUID] = None
    ordre_treball_codi: Optional[str] = None
    ambit: str
    estat: str
    text_observacions: Optional[str] = None
    foto_path: Optional[str] = None
    audio_path: Optional[str] = None
    created_at: datetime


class IntervencioFitxa360(BaseModel):
    id: uuid.UUID
    codi: str
    titol: str
    adreca: str
    estat: str
    data_planificacio: Optional[date] = None
    hora_inici_prevista: Optional[datetime] = None
    hora_fi_prevista: Optional[datetime] = None
    created_at: datetime
    cost_material: Optional[float] = 0.0
    ingres_facturat: Optional[float] = 0.0
    marge_brut: Optional[float] = 0.0


class PressupostFitxa360(BaseModel):
    id: uuid.UUID
    numero: str
    estat: str
    total: Optional[float] = None
    created_at: datetime


class FacturaClientFitxa360(BaseModel):
    id: uuid.UUID
    serie: str
    numero_factura: int
    estat_document: str
    estat_cobrament: str = "PENDENT"
    data_emissio: Optional[str] = None
    data_venciment: Optional[str] = None
    base_imposable: float = 0.0
    quota_iva: float = 0.0
    liquid_exigible: float = 0.0
    ordres_treball_codis: List[str] = []


class Fitxa360Resum(BaseModel):
    total_intervencions: int
    total_incidencies: int
    total_peces_instalades: int
    dies_analitzats: int = 365


class Fitxa360Response(BaseModel):
    client: ClientResponse
    finques: List[FincaFitxa360]
    intervencions: List[IntervencioFitxa360]
    peces_instalades: List[PecaInstaladaFitxa360]
    incidencies: List[IncidenciaFitxa360]
    alertes_garantia: List[Dict[str, Any]]
    pressupostos: List[PressupostFitxa360] = []
    factures: List[FacturaClientFitxa360] = []
    resum: Fitxa360Resum


@router.get("/{client_id}/fitxa-360", response_model=Fitxa360Response)
@router.get("/{client_id}/fitxa360", response_model=Fitxa360Response)
async def obtenir_fitxa_360_client(
    request: Request,
    client_id: uuid.UUID,
    claims: Dict[str, Any] = Depends(require_roles(["BOSS", "SECRETARIA", "ENGINYER"])),
    db: AsyncSession = Depends(get_db_with_tenant_context),
) -> Fitxa360Response:
    """
    Recopila cronològicament totes les intervencions tècniques, peces instal·lades
    i incidències registrades per al client durant els últims 365 dies (Spec 012 RF-04).
    Aplica Principi VI: oculta IBAN i imports financers a ENGINYER.
    """
    empresa_uuid = _resolve_emp_uuid(request, claims)
    rol = str(claims.get("rol", "")).upper()
    is_enginyer = rol == "ENGINYER"

    # 1. Verificar client
    res_client = await db.execute(
        select(Client).where(Client.id == client_id, Client.empresa_id == empresa_uuid)
    )
    client = res_client.scalars().first()
    if not client:
        raise HTTPException(status_code=404, detail="Client no trobat")

    fa_un_any = datetime.now(timezone.utc) - timedelta(days=365)

    # 2. Obtenir Finques
    from sqlalchemy import func

    from app.models.models import (
        AlertaGarantiaRecompra,
        Article,
        FacturaLinia,
        Finca,
        FullaPicking,
        Incidencia,
        LiniaPicking,
        OrdreTreball,
        Pressupost,
    )

    res_finques = await db.execute(
        select(Finca).where(Finca.client_id == client_id, Finca.empresa_id == empresa_uuid)
    )
    finques_db = res_finques.scalars().all()
    finques = [
        FincaFitxa360(
            id=f.id,
            nom=f.nom,
            adreca=f.adreca,
            superficie_ha=float(f.superficie_ha) if f.superficie_ha is not None else None,
            dades_sigpac=f.dades_sigpac or {},
        )
        for f in finques_db
    ]

    # 3. Obtenir Ordres de Treball (últims 365 dies)
    res_ots = await db.execute(
        select(OrdreTreball)
        .where(
            OrdreTreball.client_id == client_id,
            OrdreTreball.empresa_id == empresa_uuid,
            OrdreTreball.created_at >= fa_un_any,
        )
        .order_by(OrdreTreball.created_at.desc())
    )
    ots = res_ots.scalars().all()
    ot_map = {ot.id: ot for ot in ots}
    ot_ids = list(ot_map.keys())

    # NEW BLOCK: Calculate Financials for OTs (ocult per ENGINYER)
    costos_materials: dict[uuid.UUID, float] = {}
    ingressos: dict[uuid.UUID, float] = {}
    if ot_ids and not is_enginyer:
        stmt_costos = (
            select(
                FullaPicking.ordre_treball_id,
                func.sum(LiniaPicking.quantitat_carregada_pick_in * Article.preu_cost),
            )
            .join(FullaPicking, LiniaPicking.picking_id == FullaPicking.id)
            .join(Article, LiniaPicking.article_id == Article.id)
            .where(
                FullaPicking.ordre_treball_id.in_(ot_ids),
                LiniaPicking.empresa_id == empresa_uuid,
            )
            .group_by(FullaPicking.ordre_treball_id)
        )
        res_costos = await db.execute(stmt_costos)
        for ot_id, cost in res_costos.all():
            costos_materials[ot_id] = float(cost or 0.0)

        stmt_ing = (
            select(
                FacturaLinia.obra_id,
                func.sum(FacturaLinia.preu_venda_unitari * FacturaLinia.quantitat),
            )
            .where(
                FacturaLinia.obra_id.in_(ot_ids),
                FacturaLinia.empresa_id == empresa_uuid,
            )
            .group_by(FacturaLinia.obra_id)
        )
        res_ing = await db.execute(stmt_ing)
        for ot_id, ing in res_ing.all():
            ingressos[ot_id] = float(ing or 0.0)

    intervencions = [
        IntervencioFitxa360(
            id=ot.id,
            codi=ot.codi,
            titol=ot.titol,
            adreca=ot.adreca,
            estat=ot.estat,
            data_planificacio=ot.data_planificacio,
            hora_inici_prevista=ot.hora_inici_prevista,
            hora_fi_prevista=ot.hora_fi_prevista,
            created_at=ot.created_at,
            cost_material=None if is_enginyer else costos_materials.get(ot.id, 0.0),
            ingres_facturat=None if is_enginyer else ingressos.get(ot.id, 0.0),
            marge_brut=None if is_enginyer else (ingressos.get(ot.id, 0.0) - costos_materials.get(ot.id, 0.0)),
        )
        for ot in ots
    ]

    # 4. Obtenir Peces instal·lades a les OTs dels últims 365 dies
    peces_instalades: List[PecaInstaladaFitxa360] = []
    if ot_ids:
        stmt_peces = (
            select(LiniaPicking, Article, FullaPicking)
            .join(FullaPicking, LiniaPicking.picking_id == FullaPicking.id)
            .join(Article, LiniaPicking.article_id == Article.id)
            .where(
                FullaPicking.ordre_treball_id.in_(ot_ids), LiniaPicking.empresa_id == empresa_uuid
            )
            .order_by(LiniaPicking.created_at.desc())
        )
        res_peces = await db.execute(stmt_peces)
        for lp, art, fp in res_peces.all():
            ot = ot_map.get(fp.ordre_treball_id)
            # Consum real = carregat - retornat
            quantitat = float(lp.quantitat_carregada_pick_in or 0.0) - float(
                lp.quantitat_retornada_pick_out or 0.0
            )
            if quantitat <= 0:
                quantitat = float(lp.quantitat_carregada_pick_in or 0.0)
            peces_instalades.append(
                PecaInstaladaFitxa360(
                    article_id=art.id,
                    codi_article=art.referencia_inventari,
                    nom_article=art.nom,
                    quantitat_instalada=quantitat,
                    unitat_mesura=art.unitat_mesura,
                    data_instalacio=lp.created_at,
                    ordre_treball_id=fp.ordre_treball_id,
                    ordre_treball_codi=ot.codi if ot else "S/C",
                )
            )

    # 5. Obtenir Incidències associades
    incidencies: List[IncidenciaFitxa360] = []
    if ot_ids:
        stmt_inc = (
            select(Incidencia)
            .where(
                Incidencia.ordre_treball_id.in_(ot_ids),
                Incidencia.empresa_id == empresa_uuid,
                Incidencia.created_at >= fa_un_any,
            )
            .order_by(Incidencia.created_at.desc())
        )
        res_inc = await db.execute(stmt_inc)
        for inc in res_inc.scalars().all():
            ot = ot_map.get(inc.ordre_treball_id) if inc.ordre_treball_id else None
            incidencies.append(
                IncidenciaFitxa360(
                    id=inc.id,
                    ordre_treball_id=inc.ordre_treball_id,
                    ordre_treball_codi=ot.codi if ot else None,
                    ambit=inc.ambit,
                    estat=inc.estat,
                    text_observacions=inc.text_observacions,
                    foto_path=inc.foto_path,
                    audio_path=inc.audio_path,
                    created_at=inc.created_at,
                )
            )

    # 6. Obtenir Alertes de Garantia
    alertes: List[Dict[str, Any]] = []
    if ot_ids:
        stmt_alertes = select(AlertaGarantiaRecompra).where(
            AlertaGarantiaRecompra.ordre_treball_id.in_(ot_ids),
            AlertaGarantiaRecompra.empresa_id == empresa_uuid,
        )
        res_alertes = await db.execute(stmt_alertes)
        for al in res_alertes.scalars().all():
            alertes.append(
                {
                    "id": str(al.id),
                    "ordre_treball_id": str(al.ordre_treball_id) if al.ordre_treball_id else None,
                    "tipus_alerta": al.tipus_alerta,
                    "missatge": al.missatge,
                    "data_fi_garantia": str(al.data_fi_garantia) if al.data_fi_garantia else None,
                    "estat": al.estat,
                }
            )

    # 7. Obtenir Pressupostos del client (imports comercials visibles per a tots 3 rols)
    stmt_pres = (
        select(Pressupost)
        .where(
            Pressupost.client_id == client_id,
            Pressupost.empresa_id == empresa_uuid,
        )
        .order_by(Pressupost.created_at.desc())
    )
    pres_rows = (await db.execute(stmt_pres)).scalars().all()
    pressupostos_fitxa = [
        PressupostFitxa360(
            id=p.id,
            numero=p.numero,
            estat=p.estat,
            total=float(p.total or 0.0),
            created_at=p.created_at,
        )
        for p in pres_rows
    ]

    # 8. Obtenir Pre-factures i Factures relacionades amb les tasques d'aquest client
    # (via funció SECURITY DEFINER acotada al client/OT per preservar economics_boss_only sobre comptabilitat global)
    from sqlalchemy import text as sa_text

    res_facs = await db.execute(
        sa_text(
            "SELECT public.obtenir_factures_comercials_client(CAST(:emp_id AS uuid), CAST(:cli_id AS uuid))"
        ),
        {"emp_id": str(empresa_uuid), "cli_id": str(client_id)},
    )
    raw_facs = res_facs.scalar_one_or_none()
    factures_fitxa: List[FacturaClientFitxa360] = []
    if isinstance(raw_facs, list):
        for f_item in raw_facs:
            if not isinstance(f_item, dict):
                continue
            factures_fitxa.append(
                FacturaClientFitxa360(
                    id=uuid.UUID(str(f_item["id"])),
                    serie=str(f_item.get("serie") or ""),
                    numero_factura=int(f_item.get("numero_factura") or 0),
                    estat_document=str(f_item.get("estat_document") or ""),
                    estat_cobrament=str(f_item.get("estat_cobrament") or "PENDENT"),
                    data_emissio=str(f_item["data_emissio"]) if f_item.get("data_emissio") else None,
                    data_venciment=(
                        str(f_item["data_venciment"]) if f_item.get("data_venciment") else None
                    ),
                    base_imposable=float(f_item.get("base_imposable") or 0.0),
                    quota_iva=float(f_item.get("quota_iva") or 0.0),
                    liquid_exigible=float(f_item.get("liquid_exigible") or 0.0),
                    ordres_treball_codis=[
                        str(c) for c in (f_item.get("ordres_treball_codis") or [])
                    ],
                )
            )

    resum = Fitxa360Resum(
        total_intervencions=len(intervencions),
        total_incidencies=len(incidencies),
        total_peces_instalades=len(peces_instalades),
        dies_analitzats=365,
    )

    client_resp = ClientResponse(
        id=client.id,
        codi=client.codi,
        rao_social=client.rao_social,
        nif=client.nif,
        telefon=client.telefon,
        email=client.email,
        adreca_fiscal=client.adreca_fiscal,
        web=client.web,
        persona_contacte=client.persona_contacte,
        dades_contacte=client.dades_contacte,
        iban=None if is_enginyer else client.iban_xifrat_simetric,
        estat_canal_telegram=client.estat_canal_telegram,
        actiu=client.actiu,
    )

    return Fitxa360Response(
        client=client_resp,
        finques=finques,
        intervencions=intervencions,
        peces_instalades=peces_instalades,
        incidencies=incidencies,
        alertes_garantia=alertes,
        pressupostos=pressupostos_fitxa,
        factures=factures_fitxa,
        resum=resum,
    )


@router.post("/import", response_model=CsvImportResult)
async def importar_clients_csv(
    request: Request,
    file: UploadFile = File(...),
    claims: Dict[str, Any] = Depends(require_roles(["BOSS", "SECRETARIA", "ENGINYER"])),
    db: AsyncSession = Depends(get_db_with_tenant_context),
) -> CsvImportResult:
    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="El fitxer ha de ser un CSV")

    content = await file.read()
    if not content or not content.strip():
        raise HTTPException(status_code=400, detail="El fitxer CSV està buit")

    kind = filetype.guess(content)
    if kind is not None and not kind.mime.startswith("text/"):
        raise HTTPException(
            status_code=400,
            detail=f"Format de fitxer invàlid ({kind.mime}). Puja un fitxer CSV de text pla.",
        )

    emp_uuid = _resolve_emp_uuid(request, claims)
    rol = str(claims.get("rol", "")).upper()

    # Delegar l'extracció i mapeig semàntic al Copilot (estructura agent/subagents)
    extraction = await copilot_dispatcher.extraure_clients_csv(
        db=db,
        empresa_id=emp_uuid,
        csv_bytes=content,
    )
    copilot_usat = bool(extraction.get("copilot_usat", False))
    mapping_aplicat: Dict[str, List[str]] = extraction.get("mapping_aplicat") or {}
    errors: List[Dict[str, Any]] = list(extraction.get("errors") or [])
    extracted_rows: List[tuple[int, Dict[str, Optional[str]]]] = extraction.get("rows") or []

    valid_rows: List[tuple[int, ClientCsvImportRow]] = []
    for row_num, raw_record in extracted_rows:
        # Ometre només files totalment buides (si almenys un camp té dades, no aturem l'extracció)
        if not any((v or "").strip() for v in raw_record.values()):
            continue
        try:
            row_obj = ClientCsvImportRow(**raw_record)
        except ValidationError as exc:
            for err in exc.errors():
                col_name = str(err["loc"][0]) if err.get("loc") else "desconeguda"
                motiu = err.get("msg", "Error de validació")
                valor_original = raw_record.get(col_name, "")
                errors.append(
                    {
                        "fila": row_num,
                        "columna": col_name,
                        "valor": str(valor_original) if valor_original is not None else "",
                        "motiu": motiu,
                    }
                )
            continue

        # Normalització tolerant sense descartar la fila si algun camp és buit/null
        nif_clean = (row_obj.nif or "").strip().upper().replace("-", "").replace(" ", "").replace(".", "")
        if len(nif_clean) == 11 and nif_clean.startswith("ES"):
            nif_clean = nif_clean[2:]
        row_obj.nif = nif_clean[:20]

        rao_clean = (row_obj.rao_social or "").strip()
        if not rao_clean:
            rao_clean = (
                (row_obj.persona_contacte or "").strip()
                or (row_obj.email or "").strip()
                or (row_obj.web or "").strip()
                or nif_clean
                or f"Client fila {row_num}"
            )
        row_obj.rao_social = rao_clean[:200]

        tel_clean = (row_obj.telefon or "").strip() or None
        dades_clean = (row_obj.dades_contacte or "").strip() or None
        if tel_clean and len(tel_clean) > 30:
            dades_clean = f"{dades_clean} · Tel: {tel_clean}" if dades_clean else f"Tel: {tel_clean}"
            tel_clean = tel_clean[:30]
        row_obj.telefon = tel_clean
        row_obj.dades_contacte = dades_clean
        row_obj.email = ((row_obj.email or "").strip()[:200]) or None
        row_obj.adreca_fiscal = (row_obj.adreca_fiscal or "").strip() or None
        row_obj.web = ((row_obj.web or "").strip()[:255]) or None
        row_obj.persona_contacte = ((row_obj.persona_contacte or "").strip()[:150]) or None
        row_obj.iban = ((row_obj.iban or "").strip().upper().replace(" ", "")[:34]) or None

        valid_rows.append((row_num, row_obj))

    inserits = 0
    total_processats = len(valid_rows) + len({e["fila"] for e in errors})

    # Processar els vàlids un a un amb enumeració automàtica CLI-XXXX i SAVEPOINT per fila
    for row_num, record in valid_rows:
        nif_val = record.nif or ""
        if nif_val:
            dup_nif = (
                await db.execute(
                    select(Client.id).where(
                        Client.empresa_id == emp_uuid,
                        Client.nif == nif_val,
                    )
                )
            ).first()
            if dup_nif:
                errors.append(
                    {
                        "fila": row_num,
                        "columna": "nif",
                        "valor": nif_val,
                        "motiu": "Ja existeix un client amb aquest NIF",
                    }
                )
                continue

        codi_auto = await generar_seguent_codi(db, Client, emp_uuid, "CLI")
        client_db = Client(
            empresa_id=emp_uuid,
            codi=codi_auto,
            rao_social=record.rao_social or f"Client fila {row_num}",
            nif=nif_val,
            telefon=record.telefon,
            email=record.email,
            adreca_fiscal=record.adreca_fiscal,
            web=record.web,
            persona_contacte=record.persona_contacte,
            dades_contacte=record.dades_contacte,
            iban_xifrat_simetric=None if rol == "ENGINYER" else record.iban,
        )
        try:
            async with db.begin_nested():
                db.add(client_db)
                await db.flush()
            inserits += 1
        except IntegrityError:
            errors.append(
                {
                    "fila": row_num,
                    "columna": "nif/codi",
                    "valor": nif_val,
                    "motiu": "Ja existeix un client amb aquest NIF o Codi",
                }
            )

    await db.commit()

    return CsvImportResult(
        total_processats=total_processats,
        inserits=inserits,
        errors_detectats=errors,
        copilot_usat=copilot_usat,
        mapping_aplicat=mapping_aplicat,
    )


@router.get("/export")
async def exportar_clients_csv(
    request: Request, db: AsyncSession = Depends(get_db_with_tenant_context)
) -> StreamingResponse:
    emp_uuid = _resolve_emp_uuid(request)
    result = await db.execute(select(Client).where(Client.empresa_id == emp_uuid))
    clients = result.scalars().all()

    fieldnames = [
        "codi",
        "rao_social",
        "nif",
        "telefon",
        "email",
        "adreca_fiscal",
        "web",
        "persona_contacte",
        "dades_contacte",
        "actiu",
    ]
    records = []
    for c in clients:
        records.append(
            {
                "codi": c.codi,
                "rao_social": c.rao_social,
                "nif": c.nif,
                "telefon": c.telefon or "",
                "email": c.email or "",
                "adreca_fiscal": c.adreca_fiscal or "",
                "web": c.web or "",
                "persona_contacte": c.persona_contacte or "",
                "dades_contacte": c.dades_contacte or "",
                "actiu": str(c.actiu),
            }
        )

    csv_io = generate_csv_content(records, fieldnames)
    csv_io.seek(0)

    return StreamingResponse(
        iter([csv_io.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=clients_export.csv"},
    )


class FincaCreate(BaseModel):
    nom: str = Field(..., max_length=150)
    adreca: Optional[str] = None
    latitud: float
    longitud: float
    ref_cadastral: Optional[str] = Field(None, max_length=50)
    poligon_sigpac: Optional[str] = Field(None, max_length=50)
    parcel_sigpac: Optional[str] = Field(None, max_length=50)
    codi_candat_en_memoria: Optional[str] = Field(None, max_length=50)
    superficie_ha: Optional[float] = None


class FincaResponse(FincaCreate):
    id: uuid.UUID
    actiu: bool
    model_config = {"from_attributes": True}


@router.get("/{client_id}/finques", response_model=List[FincaResponse])
async def llistar_finques_client(
    request: Request, client_id: uuid.UUID, db: AsyncSession = Depends(get_db_with_tenant_context)
) -> Sequence[Finca]:
    empresa_id = getattr(request.state, "empresa_id", None) or request.headers.get("X-Empresa-ID")
    if not empresa_id or empresa_id == "undefined":
        raise HTTPException(status_code=401, detail="No identificat")

    stmt = (
        select(Finca)
        .where(Finca.client_id == client_id, Finca.empresa_id == uuid.UUID(empresa_id))
        .order_by(Finca.created_at.desc())
    )

    result = await db.execute(stmt)
    finques = result.scalars().all()
    return finques


@router.post(
    "/{client_id}/finques", response_model=FincaResponse, status_code=status.HTTP_201_CREATED
)
async def crear_finca_client(
    request: Request,
    client_id: uuid.UUID,
    finca: FincaCreate,
    db: AsyncSession = Depends(get_db_with_tenant_context),
) -> Finca:
    empresa_id = getattr(request.state, "empresa_id", None) or request.headers.get("X-Empresa-ID")
    if not empresa_id or empresa_id == "undefined":
        raise HTTPException(status_code=401, detail="No identificat")

    empresa_uuid = uuid.UUID(empresa_id)

    res = await db.execute(
        select(Client).where(Client.id == client_id, Client.empresa_id == empresa_uuid)
    )
    client_obj = res.scalars().first()
    if not client_obj:
        raise HTTPException(status_code=404, detail="Client no trobat")
    client_nom = client_obj.rao_social

    nova_finca = Finca(
        empresa_id=empresa_uuid,
        client_id=client_id,
        nom=finca.nom,
        adreca=finca.adreca,
        latitud=finca.latitud,
        longitud=finca.longitud,
        ref_cadastral=finca.ref_cadastral,
        poligon_sigpac=finca.poligon_sigpac,
        parcel_sigpac=finca.parcel_sigpac,
        codi_candat_en_memoria=finca.codi_candat_en_memoria,
        superficie_ha=finca.superficie_ha,
    )

    db.add(nova_finca)
    await db.flush()
    from app.services.sovereign_sync_service import serialize_finca

    finca_id_str = str(nova_finca.id)
    finca_payload = serialize_finca(nova_finca, client_nom=client_nom)
    await db.commit()

    try:
        await SovereignStorageGateway.desar_entitat_json(
            db=db,
            empresa_id=empresa_uuid,
            categoria="finques",
            item_id=finca_id_str,
            dades=finca_payload,
        )
    except Exception:
        pass

    return nova_finca
