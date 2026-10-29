"""Router CRM Prospecció, Leads, Pipeline Kanban de 7 dies i Demo autònoma."""

import asyncio
import json
import logging
import re
import uuid
from datetime import date, datetime, timedelta, timezone
from typing import Any, AsyncGenerator, Dict, List, Optional

import bcrypt
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.db import AsyncSessionLocal, get_db_with_tenant_context, set_tenant_context
from app.core.security import require_roles
from app.models.models import (
    Article,
    Client,
    Empresa,
    EstocMagatzem,
    FaqCorporativaRag,
    Magatzem,
    OrdreTreball,
    SaasActivitatLead,
    SaasCorreuMissatge,
    SaasCriteriFeedback,
    SaasExclusioRgpd,
    SaasLead,
    SaasOportunitat,
    SaasProspeccioCandidat,
    SaasProspeccioTasca,
    Usuari,
    Vehicle,
)
from app.services.firecrawl_service import (
    es_nom_persona_real,
    extreure_mapa_fonts_urls,
    firecrawl_service,
    formatar_fonts_verificables,
    normalitzar_adreca,
    normalitzar_cif,
    normalitzar_domini,
    obtenir_municipi_de_codi_postal,
    verificar_duplicitat_multivector,
)
from app.services.mx_shield_service import validar_email_mx
from app.services.openrouter_prospecting_service import (
    EmailStepSchema,
    qualificar_candidat_amb_openrouter,
)
from app.services.prospeccio_validacio import (
    ContextValidat,
    Gatekeeper,
    adreca_valida_per_cp,
    aplicar_regles_dures,
    bloc_gatekeeper,
    construir_context,
    telefons_es,
)
from app.services.stalwart_mail_service import (
    aprovar_i_enviar_correu_calendari,
    processar_resposta_inbound,
    programar_campanya_3_emails,
    sincronitzar_bustia_imap_stalwart,
)

logger = logging.getLogger("superadmin.crm_prospeccio")

router = APIRouter(
    prefix="/superadmin/crm/prospeccio",
    tags=["Superadmin CRM Prospecció & Pipeline"],
    dependencies=[Depends(require_roles(["SUPERADMIN"]))],
)


# ==========================================
# ESQUEMES PYDANTIC
# ==========================================

class LeadCreate(BaseModel):
    nom_empresa: str = Field(..., min_length=2, max_length=150)
    nom_contacte: str = Field(..., min_length=2, max_length=100)
    email: str = Field(..., min_length=5, max_length=150)
    telefon: Optional[str] = Field(None, max_length=30)
    vertical: str = Field("CampoPro", max_length=150)
    origen: str = Field("WEB", max_length=50)
    operaris_estimats: int = Field(5, ge=1, le=500)
    notes: Optional[str] = None
    cif: Optional[str] = Field(None, max_length=20)
    web_url: Optional[str] = Field(None, max_length=255)
    domini_normalitzat: Optional[str] = Field(None, max_length=150)
    adreca_fisica: Optional[str] = Field(None, max_length=255)
    adreca_normalitzada: Optional[str] = Field(None, max_length=255)
    codi_postal: Optional[str] = Field(None, max_length=10)
    carrec_contacte: Optional[str] = Field(None, max_length=100)
    fonts_investigades: Optional[str] = None
    fita_recent: Optional[str] = None
    punt_dolor_detectat: Optional[str] = None
    angle_atac: Optional[str] = Field(None, max_length=50)
    score_qualificacio: int = Field(0, ge=0, le=100)
    justificacio_ia: Optional[str] = None
    mx_validat: bool = False
    esborrany_email_assumpte: Optional[str] = Field(None, max_length=255)
    esborrany_email_cos: Optional[str] = None
    rao_tancament_exit: Optional[str] = None
    es_tancament_replicable: bool = False
    crear_oportunitat_inicial: bool = True
    valor_mensual_estimat: float = Field(0.0, ge=0.0)


class LeadUpdate(BaseModel):
    nom_empresa: Optional[str] = Field(None, max_length=150)
    nom_contacte: Optional[str] = Field(None, max_length=100)
    email: Optional[str] = Field(None, max_length=150)
    telefon: Optional[str] = Field(None, max_length=30)
    vertical: Optional[str] = Field(None, max_length=150)
    origen: Optional[str] = Field(None, max_length=50)
    estat_qualificacio: Optional[str] = Field(None, max_length=50)
    operaris_estimats: Optional[int] = Field(None, ge=1, le=500)
    notes: Optional[str] = None
    cif: Optional[str] = Field(None, max_length=20)
    web_url: Optional[str] = Field(None, max_length=255)
    domini_normalitzat: Optional[str] = Field(None, max_length=150)
    adreca_fisica: Optional[str] = Field(None, max_length=255)
    adreca_normalitzada: Optional[str] = Field(None, max_length=255)
    codi_postal: Optional[str] = Field(None, max_length=10)
    carrec_contacte: Optional[str] = Field(None, max_length=100)
    fonts_investigades: Optional[str] = None
    fita_recent: Optional[str] = None
    punt_dolor_detectat: Optional[str] = None
    angle_atac: Optional[str] = Field(None, max_length=50)
    score_qualificacio: Optional[int] = Field(None, ge=0, le=100)
    justificacio_ia: Optional[str] = None
    mx_validat: Optional[bool] = None
    esborrany_email_assumpte: Optional[str] = Field(None, max_length=255)
    esborrany_email_cos: Optional[str] = None
    rao_tancament_exit: Optional[str] = None
    es_tancament_replicable: Optional[bool] = None


class OportunitatCreate(BaseModel):
    lead_id: str
    titol: str = Field(..., min_length=3, max_length=200)
    etapa: str = Field("PROSPECCIO", max_length=50)
    valor_mensual_estimat: float = Field(0.0, ge=0.0)
    valor_ia_setup: float = Field(0.0, ge=0.0)
    probabilitat_percent: int = Field(20, ge=0, le=100)
    data_tancament_prevista: Optional[date] = None
    rao_tancament_exit: Optional[str] = None
    requisits_replicables: Optional[str] = None
    es_replicable: bool = False


class OportunitatUpdate(BaseModel):
    titol: Optional[str] = Field(None, max_length=200)
    etapa: Optional[str] = Field(None, max_length=50)
    valor_mensual_estimat: Optional[float] = Field(None, ge=0.0)
    valor_ia_setup: Optional[float] = Field(None, ge=0.0)
    probabilitat_percent: Optional[int] = Field(None, ge=0, le=100)
    data_tancament_prevista: Optional[date] = None
    motiu_perdua: Optional[str] = Field(None, max_length=255)
    rao_tancament_exit: Optional[str] = None
    requisits_replicables: Optional[str] = None
    es_replicable: Optional[bool] = None


class ActivitatCreate(BaseModel):
    tipus: str = Field("NOTA", max_length=30)
    titol: str = Field(..., min_length=2, max_length=200)
    descripcio: Optional[str] = None
    autor_nom: Optional[str] = "Superadmin"


class ActivarDemoRequest(BaseModel):
    vertical: Optional[str] = None  # Si és None, agafa la del lead
    durada_dies: int = Field(7, ge=1, le=30)
    recrear: bool = False


class TascaCpCreate(BaseModel):
    codi_postal: str = Field(..., min_length=4, max_length=10)
    vertical: str = Field(..., min_length=2, max_length=150)
    operaris_minims: int = Field(5, ge=1, le=500)
    candidats_descoberts: Optional[List[Dict[str, Any]]] = None
    limit: Optional[int] = Field(5, ge=1, le=20)
    executar_en_segon_pla: Optional[bool] = None


_background_tasks: set[asyncio.Task] = set()


class CorregirCriteriRequest(BaseModel):
    nova_decisio: str = Field(..., pattern="^(SELECCIONAT|SELECCIONAT_SENSE_GATEKEEPER|DESCARTAT)$")
    motiu_correccio_humana: str = Field(..., min_length=10)


class RegistrarExitRequest(BaseModel):
    rao_tancament_exit: str = Field(..., min_length=5)
    requisits_replicables: Optional[str] = None
    es_replicable: bool = True


class CalendariEsdevenimentCreate(BaseModel):
    lead_id: str
    tipus: str = Field("SEGUIMENT_CALENDARI", pattern="^(SEGUIMENT_CALENDARI|REUNIO_DEMO|NOTA)$")
    data_programada: datetime
    titol: str = Field(..., min_length=3, max_length=200)
    descripcio: Optional[str] = None


class EditarEsborranyRequest(BaseModel):
    assumpte: Optional[str] = Field(None, max_length=255)
    cos_text: Optional[str] = None
    data_programada: Optional[datetime] = None


class ExclusioRgpdCreate(BaseModel):
    email: Optional[str] = None
    domini: str = Field(..., min_length=3, max_length=150)
    cif: Optional[str] = None
    motiu: str = Field("MANUAL_SUPERADMIN", max_length=50)


class SincronitzarInboundRequest(BaseModel):
    remitent: Optional[str] = None
    assumpte: Optional[str] = None
    cos_text: Optional[str] = None
    in_reply_to: Optional[str] = None


# ==========================================
# UTILITATS INTERNES (Zero Mock & Hash)
# ==========================================

def _hash_pwd(pwd: str) -> str:
    return bcrypt.hashpw(pwd.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def _hash_pin(pin: str) -> str:
    return bcrypt.hashpw(pin.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def _sanititzar_slug(text_raw: str) -> str:
    clean = re.sub(r"[^a-z0-9]", "", text_raw.lower().strip())
    return clean[:15] or "demo"


# ==========================================
# ENDPOINTS LEADS
# ==========================================

@router.get("/leads", response_model=List[Dict[str, Any]])
async def llistar_leads(
    q: Optional[str] = None,
    estat: Optional[str] = None,
    vertical: Optional[str] = None,
    limit: int = Query(100, ge=1, le=500),
    db: AsyncSession = Depends(get_db_with_tenant_context),
) -> List[Dict[str, Any]]:
    """Llista tots els prospectes (leads) amb dades de qualificació i estat de la demo."""
    stmt = select(SaasLead).order_by(desc(SaasLead.created_at)).limit(limit)

    if estat:
        stmt = stmt.where(SaasLead.estat_qualificacio == estat)
    if vertical:
        stmt = stmt.where(SaasLead.vertical == vertical)
    if q:
        filtre = f"%{q.strip().lower()}%"
        stmt = stmt.where(
            func.lower(SaasLead.nom_empresa).like(filtre)
            | func.lower(SaasLead.nom_contacte).like(filtre)
            | func.lower(SaasLead.email).like(filtre)
        )

    res = await db.execute(stmt)
    leads = res.scalars().all()

    resultat: List[Dict[str, Any]] = []
    ara = datetime.now(timezone.utc)

    for lead_item in leads:
        dies_restants_demo = None
        demo_activa = False
        if lead_item.data_fi_demo:
            delta = (lead_item.data_fi_demo - ara).total_seconds()
            dies_restants_demo = max(0, int(delta // 86400) + 1)
            demo_activa = delta > 0

        resultat.append({
            "id": str(lead_item.id),
            "nom_empresa": lead_item.nom_empresa,
            "nom_contacte": lead_item.nom_contacte,
            "email": lead_item.email,
            "telefon": lead_item.telefon,
            "vertical": lead_item.vertical,
            "origen": lead_item.origen,
            "estat_qualificacio": lead_item.estat_qualificacio,
            "operaris_estimats": lead_item.operaris_estimats,
            "notes": lead_item.notes,
            "cif": lead_item.cif,
            "web_url": lead_item.web_url,
            "domini_normalitzat": lead_item.domini_normalitzat,
            "adreca_fisica": lead_item.adreca_fisica,
            "adreca_normalitzada": lead_item.adreca_normalitzada,
            "codi_postal": lead_item.codi_postal,
            "carrec_contacte": lead_item.carrec_contacte,
            "fonts_investigades": lead_item.fonts_investigades,
            "fita_recent": lead_item.fita_recent,
            "punt_dolor_detectat": lead_item.punt_dolor_detectat,
            "angle_atac": lead_item.angle_atac,
            "score_qualificacio": lead_item.score_qualificacio,
            "justificacio_ia": lead_item.justificacio_ia,
            "mx_validat": lead_item.mx_validat,
            "esborrany_email_assumpte": lead_item.esborrany_email_assumpte,
            "esborrany_email_cos": lead_item.esborrany_email_cos,
            "rao_tancament_exit": lead_item.rao_tancament_exit,
            "es_tancament_replicable": lead_item.es_tancament_replicable,
            "tasca_prospeccio_id": str(lead_item.tasca_prospeccio_id) if lead_item.tasca_prospeccio_id else None,
            "empresa_demo_id": str(lead_item.empresa_demo_id) if lead_item.empresa_demo_id else None,
            "data_inici_demo": lead_item.data_inici_demo.isoformat() if lead_item.data_inici_demo else None,
            "data_fi_demo": lead_item.data_fi_demo.isoformat() if lead_item.data_fi_demo else None,
            "dies_demo_durada": lead_item.dies_demo_durada,
            "dies_restants_demo": dies_restants_demo,
            "demo_activa": demo_activa,
            "created_at": lead_item.created_at.isoformat(),
            "updated_at": lead_item.updated_at.isoformat(),
        })

    return resultat


@router.post("/leads", response_model=Dict[str, Any], status_code=status.HTTP_201_CREATED)
async def crear_lead(
    payload: LeadCreate,
    db: AsyncSession = Depends(get_db_with_tenant_context),
) -> Dict[str, Any]:
    """Crea un nou prospecte comercial i opcionalment genera la seva oportunitat al Pipeline."""
    lead_id = uuid.uuid4()
    ara = datetime.now(timezone.utc)

    nou_lead = SaasLead(
        id=lead_id,
        nom_empresa=payload.nom_empresa.strip(),
        nom_contacte=payload.nom_contacte.strip(),
        email=payload.email.strip().lower(),
        telefon=payload.telefon.strip() if payload.telefon else None,
        vertical=payload.vertical.strip() or "CampoPro",
        origen=payload.origen.strip().upper() or "WEB",
        estat_qualificacio="NOU",
        operaris_estimats=payload.operaris_estimats,
        notes=payload.notes,
        cif=payload.cif.strip().upper() if payload.cif else None,
        web_url=payload.web_url.strip() if payload.web_url else None,
        domini_normalitzat=payload.domini_normalitzat.strip().lower() if payload.domini_normalitzat else None,
        adreca_fisica=payload.adreca_fisica.strip() if payload.adreca_fisica else None,
        adreca_normalitzada=payload.adreca_normalitzada.strip().lower() if payload.adreca_normalitzada else None,
        codi_postal=payload.codi_postal.strip() if payload.codi_postal else None,
        carrec_contacte=payload.carrec_contacte.strip() if payload.carrec_contacte else None,
        fonts_investigades=payload.fonts_investigades,
        fita_recent=payload.fita_recent,
        punt_dolor_detectat=payload.punt_dolor_detectat,
        angle_atac=payload.angle_atac,
        score_qualificacio=payload.score_qualificacio,
        justificacio_ia=payload.justificacio_ia,
        mx_validat=payload.mx_validat,
        esborrany_email_assumpte=payload.esborrany_email_assumpte,
        esborrany_email_cos=payload.esborrany_email_cos,
        rao_tancament_exit=payload.rao_tancament_exit,
        es_tancament_replicable=payload.es_tancament_replicable,
        created_at=ara,
        updated_at=ara,
    )
    db.add(nou_lead)
    await db.flush()

    # Creació de l'oportunitat inicial al Pipeline de Twenty CRM
    oportunitat_id = None
    if payload.crear_oportunitat_inicial:
        oportunitat_id = uuid.uuid4()
        mrr = payload.valor_mensual_estimat or float(payload.operaris_estimats * 15.0)
        nova_op = SaasOportunitat(
            id=oportunitat_id,
            lead_id=lead_id,
            titol=f"Llicència {payload.vertical} - {payload.nom_empresa}",
            etapa="PROSPECCIO",
            valor_mensual_estimat=mrr,
            valor_ia_setup=150.0,
            probabilitat_percent=20,
            created_at=ara,
            updated_at=ara,
        )
        db.add(nova_op)

    # Activitat inicial al timeline
    act = SaasActivitatLead(
        id=uuid.uuid4(),
        lead_id=lead_id,
        tipus="NOTA",
        titol="Prospecte registrat",
        descripcio=f"Lead creat des de l'origen '{payload.origen}' per a la vertical '{payload.vertical}'.",
        autor_nom="Superadmin",
        created_at=ara,
    )
    db.add(act)

    await db.commit()

    return {
        "status": "OK",
        "lead_id": str(lead_id),
        "oportunitat_id": str(oportunitat_id) if oportunitat_id else None,
        "missatge": f"Lead '{payload.nom_empresa}' creat correctament.",
    }


@router.get("/leads/{lead_id}", response_model=Dict[str, Any])
async def obtenir_detall_lead(
    lead_id: str,
    db: AsyncSession = Depends(get_db_with_tenant_context),
) -> Dict[str, Any]:
    """Retorna la fitxa completa d'un lead amb les seves oportunitats, timeline d'activitats i demo."""
    try:
        lid = uuid.UUID(lead_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="ID de lead invàlid.")

    res_l = await db.execute(select(SaasLead).where(SaasLead.id == lid))
    lead = res_l.scalars().first()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead no trobat.")

    # Oportunitats associades
    res_ops = await db.execute(select(SaasOportunitat).where(SaasOportunitat.lead_id == lid))
    oportunitats = res_ops.scalars().all()

    # Timeline d'activitats ordenat descendent
    res_acts = await db.execute(
        select(SaasActivitatLead).where(SaasActivitatLead.lead_id == lid).order_by(desc(SaasActivitatLead.created_at))
    )
    activitats = res_acts.scalars().all()

    # Estat de la demo
    demo_info = None
    ara = datetime.now(timezone.utc)
    if lead.empresa_demo_id:
        res_emp = await db.execute(select(Empresa).where(Empresa.id == lead.empresa_demo_id))
        emp = res_emp.scalars().first()
        if emp:
            delta = (lead.data_fi_demo - ara).total_seconds() if lead.data_fi_demo else 0
            dies_restants = max(0, int(delta // 86400) + 1)
            demo_info = {
                "empresa_id": str(emp.id),
                "nom": emp.nom,
                "subdomini": emp.subdomini,
                "estat_pagament": emp.estat_pagament,
                "vertical": emp.vertical,
                "dies_restants": dies_restants,
                "demo_activa": delta > 0 and emp.estat_pagament == "TRIAL",
                "data_inici": lead.data_inici_demo.isoformat() if lead.data_inici_demo else None,
                "data_fi": lead.data_fi_demo.isoformat() if lead.data_fi_demo else None,
            }

    return {
        "id": str(lead.id),
        "nom_empresa": lead.nom_empresa,
        "nom_contacte": lead.nom_contacte,
        "email": lead.email,
        "telefon": lead.telefon,
        "vertical": lead.vertical,
        "origen": lead.origen,
        "estat_qualificacio": lead.estat_qualificacio,
        "operaris_estimats": lead.operaris_estimats,
        "notes": lead.notes,
        "cif": lead.cif,
        "web_url": lead.web_url,
        "domini_normalitzat": lead.domini_normalitzat,
        "adreca_fisica": lead.adreca_fisica,
        "adreca_normalitzada": lead.adreca_normalitzada,
        "codi_postal": lead.codi_postal,
        "carrec_contacte": lead.carrec_contacte,
        "fonts_investigades": lead.fonts_investigades,
        "fonts_urls": extreure_mapa_fonts_urls(lead.fonts_investigades, web_url=lead.web_url),
        "fita_recent": lead.fita_recent,
        "punt_dolor_detectat": lead.punt_dolor_detectat,
        "angle_atac": lead.angle_atac,
        "score_qualificacio": lead.score_qualificacio,
        "justificacio_ia": lead.justificacio_ia,
        "mx_validat": lead.mx_validat,
        "esborrany_email_assumpte": lead.esborrany_email_assumpte,
        "esborrany_email_cos": lead.esborrany_email_cos,
        "rao_tancament_exit": lead.rao_tancament_exit,
        "es_tancament_replicable": lead.es_tancament_replicable,
        "tasca_prospeccio_id": str(lead.tasca_prospeccio_id) if lead.tasca_prospeccio_id else None,
        "empresa_demo_id": str(lead.empresa_demo_id) if lead.empresa_demo_id else None,
        "data_inici_demo": lead.data_inici_demo.isoformat() if lead.data_inici_demo else None,
        "data_fi_demo": lead.data_fi_demo.isoformat() if lead.data_fi_demo else None,
        "demo": demo_info,
        "oportunitats": [
            {
                "id": str(op.id),
                "titol": op.titol,
                "etapa": op.etapa,
                "valor_mensual_estimat": float(op.valor_mensual_estimat),
                "valor_ia_setup": float(op.valor_ia_setup),
                "probabilitat_percent": op.probabilitat_percent,
                "data_tancament_prevista": op.data_tancament_prevista.isoformat() if op.data_tancament_prevista else None,
                "motiu_perdua": op.motiu_perdua,
                "rao_tancament_exit": op.rao_tancament_exit,
                "requisits_replicables": op.requisits_replicables,
                "es_replicable": op.es_replicable,
            }
            for op in oportunitats
        ],
        "activitats": [
            {
                "id": str(a.id),
                "tipus": a.tipus,
                "titol": a.titol,
                "descripcio": a.descripcio,
                "autor_nom": a.autor_nom,
                "created_at": a.created_at.isoformat(),
            }
            for a in activitats
        ],
        "created_at": lead.created_at.isoformat(),
        "updated_at": lead.updated_at.isoformat(),
    }


@router.put("/leads/{lead_id}", response_model=Dict[str, Any])
@router.patch("/leads/{lead_id}", response_model=Dict[str, Any])
async def actualitzar_lead(
    lead_id: str,
    payload: LeadUpdate,
    db: AsyncSession = Depends(get_db_with_tenant_context),
) -> Dict[str, Any]:
    """Actualitza les dades d'un lead (inclosa la vertical que es manté oberta per triar en qualsevol moment)."""
    try:
        lid = uuid.UUID(lead_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="ID invàlid.")

    res_l = await db.execute(select(SaasLead).where(SaasLead.id == lid))
    lead = res_l.scalars().first()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead no trobat.")

    if payload.nom_empresa is not None:
        lead.nom_empresa = payload.nom_empresa.strip()
    if payload.nom_contacte is not None:
        lead.nom_contacte = payload.nom_contacte.strip()
    if payload.email is not None:
        lead.email = payload.email.strip().lower()
    if payload.telefon is not None:
        lead.telefon = payload.telefon.strip() or None
    if payload.vertical is not None:
        lead.vertical = payload.vertical.strip()  # Vertical configurable/oberta
    if payload.origen is not None:
        lead.origen = payload.origen.strip().upper()
    if payload.estat_qualificacio is not None:
        lead.estat_qualificacio = payload.estat_qualificacio.strip().upper()
    if payload.operaris_estimats is not None:
        lead.operaris_estimats = payload.operaris_estimats
    if payload.notes is not None:
        lead.notes = payload.notes
    if payload.cif is not None:
        cif_clean = payload.cif.strip()
        lead.cif = normalitzar_cif(cif_clean) if cif_clean else None
    if payload.web_url is not None:
        web_clean = payload.web_url.strip()
        lead.web_url = web_clean or None
        if payload.domini_normalitzat is None:
            lead.domini_normalitzat = normalitzar_domini(web_clean) if web_clean else None
    if payload.domini_normalitzat is not None:
        lead.domini_normalitzat = payload.domini_normalitzat.strip().lower() or None
    if payload.adreca_fisica is not None:
        adr_clean = payload.adreca_fisica.strip()
        lead.adreca_fisica = adr_clean or None
        if payload.adreca_normalitzada is None:
            lead.adreca_normalitzada = normalitzar_adreca(adr_clean) if adr_clean else None
    if payload.adreca_normalitzada is not None:
        lead.adreca_normalitzada = payload.adreca_normalitzada.strip().lower() or None
    if payload.codi_postal is not None:
        lead.codi_postal = payload.codi_postal.strip() or None
    if payload.carrec_contacte is not None:
        lead.carrec_contacte = payload.carrec_contacte.strip() or None
    if payload.fonts_investigades is not None:
        lead.fonts_investigades = payload.fonts_investigades
    if payload.fita_recent is not None:
        lead.fita_recent = payload.fita_recent
    if payload.punt_dolor_detectat is not None:
        lead.punt_dolor_detectat = payload.punt_dolor_detectat
    if payload.angle_atac is not None:
        lead.angle_atac = payload.angle_atac
    if payload.score_qualificacio is not None:
        lead.score_qualificacio = payload.score_qualificacio
    if payload.justificacio_ia is not None:
        lead.justificacio_ia = payload.justificacio_ia
    if payload.mx_validat is not None:
        lead.mx_validat = payload.mx_validat
    if payload.esborrany_email_assumpte is not None:
        lead.esborrany_email_assumpte = payload.esborrany_email_assumpte
    if payload.esborrany_email_cos is not None:
        lead.esborrany_email_cos = payload.esborrany_email_cos
    if payload.rao_tancament_exit is not None:
        lead.rao_tancament_exit = payload.rao_tancament_exit
    if payload.es_tancament_replicable is not None:
        lead.es_tancament_replicable = payload.es_tancament_replicable

    lead.updated_at = datetime.now(timezone.utc)
    await db.commit()

    return {"status": "OK", "missatge": "Lead actualitzat correctament.", "lead_id": str(lead.id)}


@router.delete("/leads/{lead_id}", response_model=Dict[str, Any])
async def eliminar_lead(
    lead_id: str,
    db: AsyncSession = Depends(get_db_with_tenant_context),
) -> Dict[str, Any]:
    """Elimina un lead i desvincula/neteja les seves oportunitats, activitats, correus i candidats."""
    try:
        lid = uuid.UUID(lead_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="ID invàlid.")

    res_l = await db.execute(select(SaasLead).where(SaasLead.id == lid))
    lead = res_l.scalars().first()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead no trobat.")

    nom_emp = lead.nom_empresa

    # Desvincular qualsevol candidat de prospecció que apuntés a aquest lead
    res_cands = await db.execute(select(SaasProspeccioCandidat).where(SaasProspeccioCandidat.lead_id == lid))
    for cand in res_cands.scalars().all():
        cand.lead_id = None

    # Eliminar correus, activitats i oportunitats associades
    res_msgs = await db.execute(select(SaasCorreuMissatge).where(SaasCorreuMissatge.lead_id == lid))
    for msg in res_msgs.scalars().all():
        await db.delete(msg)

    res_acts = await db.execute(select(SaasActivitatLead).where(SaasActivitatLead.lead_id == lid))
    for act in res_acts.scalars().all():
        await db.delete(act)

    res_ops = await db.execute(select(SaasOportunitat).where(SaasOportunitat.lead_id == lid))
    for op in res_ops.scalars().all():
        await db.delete(op)

    await db.delete(lead)
    await db.commit()
    return {"status": "OK", "missatge": f"Lead '{nom_emp}' eliminat correctament."}


@router.post("/leads/{lead_id}/activitats", response_model=Dict[str, Any], status_code=status.HTTP_201_CREATED)
async def afegir_activitat_lead(
    lead_id: str,
    payload: ActivitatCreate,
    db: AsyncSession = Depends(get_db_with_tenant_context),
) -> Dict[str, Any]:
    """Afegeix una nota, trucada o reunió al Timeline d'un lead (estil Twenty CRM)."""
    try:
        lid = uuid.UUID(lead_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="ID invàlid.")

    res_l = await db.execute(select(SaasLead).where(SaasLead.id == lid))
    lead = res_l.scalars().first()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead no trobat.")

    ara = datetime.now(timezone.utc)
    act = SaasActivitatLead(
        id=uuid.uuid4(),
        lead_id=lid,
        tipus=payload.tipus.upper(),
        titol=payload.titol.strip(),
        descripcio=payload.descripcio,
        autor_nom=payload.autor_nom or "Superadmin",
        created_at=ara,
    )
    db.add(act)
    lead.updated_at = ara
    await db.commit()

    return {"status": "OK", "activitat_id": str(act.id)}


# ==========================================
# PIPELINE KANBAN (TWENTY CRM STYLE)
# ==========================================

ETAPES_PIPELINE = [
    "PROSPECCIO",
    "QUALIFICACIO",
    "DEMO_7_DIES",
    "PROPOSTA",
    "NEGOCIACIO",
    "GUANYAT",
    "PERDUT",
]


@router.get("/pipeline", response_model=Dict[str, Any])
async def obtenir_pipeline_kanban(
    db: AsyncSession = Depends(get_db_with_tenant_context),
) -> Dict[str, Any]:
    """Retorna les columnes del Kanban d'oportunitats per etapes amb totals de negoci."""
    stmt = (
        select(SaasOportunitat, SaasLead)
        .join(SaasLead, SaasOportunitat.lead_id == SaasLead.id)
        .order_by(desc(SaasOportunitat.updated_at))
    )
    res = await db.execute(stmt)
    rows = res.all()

    columnes: Dict[str, List[Dict[str, Any]]] = {etapa: [] for etapa in ETAPES_PIPELINE}
    totals_mrr: Dict[str, float] = {etapa: 0.0 for etapa in ETAPES_PIPELINE}
    ara = datetime.now(timezone.utc)

    for op, lead_item in rows:
        etapa_norm = op.etapa if op.etapa in columnes else "PROSPECCIO"
        mrr = float(op.valor_mensual_estimat or 0.0)
        totals_mrr[etapa_norm] += mrr

        dies_restants_demo = None
        if lead_item.data_fi_demo:
            delta = (lead_item.data_fi_demo - ara).total_seconds()
            dies_restants_demo = max(0, int(delta // 86400) + 1)

        columnes[etapa_norm].append({
            "id": str(op.id),
            "lead_id": str(lead_item.id),
            "nom_empresa": lead_item.nom_empresa,
            "nom_contacte": lead_item.nom_contacte,
            "email": lead_item.email,
            "telefon": lead_item.telefon,
            "vertical": lead_item.vertical,
            "titol": op.titol,
            "etapa": etapa_norm,
            "valor_mensual_estimat": mrr,
            "valor_ia_setup": float(op.valor_ia_setup or 0.0),
            "probabilitat_percent": op.probabilitat_percent,
            "data_tancament_prevista": op.data_tancament_prevista.isoformat() if op.data_tancament_prevista else None,
            "dies_restants_demo": dies_restants_demo,
            "demo_activa": bool(lead_item.data_fi_demo and (lead_item.data_fi_demo - ara).total_seconds() > 0),
            "rao_tancament_exit": op.rao_tancament_exit,
            "requisits_replicables": op.requisits_replicables,
            "es_replicable": op.es_replicable,
            "created_at": op.created_at.isoformat(),
        })

    return {
        "etapes": ETAPES_PIPELINE,
        "totals_mrr": totals_mrr,
        "columnes": columnes,
    }


@router.post("/oportunitats", response_model=Dict[str, Any], status_code=status.HTTP_201_CREATED)
async def crear_oportunitat(
    payload: OportunitatCreate,
    db: AsyncSession = Depends(get_db_with_tenant_context),
) -> Dict[str, Any]:
    """Crea una nova oportunitat comercial (Deal) vinculada a un lead existent."""
    try:
        lid = uuid.UUID(payload.lead_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="ID de lead invàlid.")

    res_l = await db.execute(select(SaasLead).where(SaasLead.id == lid))
    lead = res_l.scalars().first()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead no trobat.")

    ara = datetime.now(timezone.utc)
    etapa_clean = payload.etapa.strip().upper()
    if etapa_clean not in ETAPES_PIPELINE:
        etapa_clean = "PROSPECCIO"

    op_id = uuid.uuid4()
    nova_op = SaasOportunitat(
        id=op_id,
        lead_id=lid,
        titol=payload.titol.strip(),
        etapa=etapa_clean,
        valor_mensual_estimat=payload.valor_mensual_estimat,
        valor_ia_setup=payload.valor_ia_setup,
        probabilitat_percent=payload.probabilitat_percent,
        data_tancament_prevista=payload.data_tancament_prevista,
        rao_tancament_exit=payload.rao_tancament_exit,
        requisits_replicables=payload.requisits_replicables,
        es_replicable=payload.es_replicable,
        created_at=ara,
        updated_at=ara,
    )
    db.add(nova_op)

    act = SaasActivitatLead(
        id=uuid.uuid4(),
        lead_id=lid,
        tipus="NOTA",
        titol=f"Nou Deal creat: {nova_op.titol}",
        descripcio=f"Oportunitat creada a l'etapa {etapa_clean} ({payload.valor_mensual_estimat} €/mes).",
        autor_nom="Superadmin",
        created_at=ara,
    )
    db.add(act)
    await db.commit()

    return {
        "status": "OK",
        "oportunitat_id": str(op_id),
        "missatge": f"Oportunitat '{nova_op.titol}' creada correctament.",
    }


@router.put("/oportunitats/{oportunitat_id}", response_model=Dict[str, Any])
@router.patch("/oportunitats/{oportunitat_id}", response_model=Dict[str, Any])
@router.patch("/oportunitats/{oportunitat_id}/etapa", response_model=Dict[str, Any])
async def actualitzar_o_canviar_etapa_oportunitat(
    oportunitat_id: str,
    payload: OportunitatUpdate,
    db: AsyncSession = Depends(get_db_with_tenant_context),
) -> Dict[str, Any]:
    """Edita els camps d'una oportunitat (Deal) o la mou d'etapa al Kanban i registra traça al timeline."""
    try:
        op_id = uuid.UUID(oportunitat_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="ID d'oportunitat invàlid.")

    res_op = await db.execute(select(SaasOportunitat).where(SaasOportunitat.id == op_id))
    op = res_op.scalars().first()
    if not op:
        raise HTTPException(status_code=404, detail="Oportunitat no trobada.")

    etapa_anterior = op.etapa
    if payload.titol is not None and payload.titol.strip():
        op.titol = payload.titol.strip()
    if payload.etapa:
        nova_etapa = payload.etapa.strip().upper()
        if nova_etapa in ETAPES_PIPELINE:
            op.etapa = nova_etapa

    if payload.valor_mensual_estimat is not None:
        op.valor_mensual_estimat = payload.valor_mensual_estimat
    if payload.valor_ia_setup is not None:
        op.valor_ia_setup = payload.valor_ia_setup
    if payload.probabilitat_percent is not None:
        op.probabilitat_percent = payload.probabilitat_percent
    if payload.data_tancament_prevista is not None:
        op.data_tancament_prevista = payload.data_tancament_prevista
    if payload.motiu_perdua is not None:
        op.motiu_perdua = payload.motiu_perdua
    if payload.rao_tancament_exit is not None:
        op.rao_tancament_exit = payload.rao_tancament_exit
    if payload.requisits_replicables is not None:
        op.requisits_replicables = payload.requisits_replicables
    if payload.es_replicable is not None:
        op.es_replicable = payload.es_replicable

    ara = datetime.now(timezone.utc)
    op.updated_at = ara

    # Registre al timeline del lead
    if payload.etapa and op.etapa != etapa_anterior:
        act = SaasActivitatLead(
            id=uuid.uuid4(),
            lead_id=op.lead_id,
            tipus="ESTAT_CANVIAT",
            titol=f"Oportunitat moguda a {op.etapa}",
            descripcio=f"Canvi d'etapa al Kanban: {etapa_anterior} -> {op.etapa}.",
            autor_nom="Superadmin",
            created_at=ara,
        )
        db.add(act)
    else:
        act_edit = SaasActivitatLead(
            id=uuid.uuid4(),
            lead_id=op.lead_id,
            tipus="NOTA",
            titol=f"Deal actualitzat: {op.titol}",
            descripcio=(
                f"Valors actualitzats: {float(op.valor_mensual_estimat):.0f} €/mes · "
                f"Setup IA {float(op.valor_ia_setup):.0f} € · Probabilitat {op.probabilitat_percent}%."
            ),
            autor_nom="Superadmin",
            created_at=ara,
        )
        db.add(act_edit)

    await db.commit()
    return {
        "status": "OK",
        "oportunitat_id": str(op.id),
        "titol": op.titol,
        "nova_etapa": op.etapa,
        "valor_mensual_estimat": float(op.valor_mensual_estimat),
        "valor_ia_setup": float(op.valor_ia_setup),
        "probabilitat_percent": op.probabilitat_percent,
        "missatge": "Oportunitat actualitzada correctament.",
    }


@router.delete("/oportunitats/{oportunitat_id}", response_model=Dict[str, Any])
async def eliminar_oportunitat(
    oportunitat_id: str,
    db: AsyncSession = Depends(get_db_with_tenant_context),
) -> Dict[str, Any]:
    """Elimina una oportunitat (Deal) del Pipeline i deixa constància al timeline del lead."""
    try:
        op_id = uuid.UUID(oportunitat_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="ID d'oportunitat invàlid.")

    res_op = await db.execute(select(SaasOportunitat).where(SaasOportunitat.id == op_id))
    op = res_op.scalars().first()
    if not op:
        raise HTTPException(status_code=404, detail="Oportunitat no trobada.")

    titol_op = op.titol
    lead_id_op = op.lead_id
    ara = datetime.now(timezone.utc)

    await db.delete(op)

    res_l = await db.execute(select(SaasLead).where(SaasLead.id == lead_id_op))
    if res_l.scalars().first():
        act = SaasActivitatLead(
            id=uuid.uuid4(),
            lead_id=lead_id_op,
            tipus="NOTA",
            titol=f"Deal eliminat: {titol_op}",
            descripcio=f"L'oportunitat '{titol_op}' ha estat eliminada del Pipeline.",
            autor_nom="Superadmin",
            created_at=ara,
        )
        db.add(act)

    await db.commit()
    return {"status": "OK", "missatge": f"Oportunitat '{titol_op}' eliminada correctament."}


# ==========================================
# MOTOR D'ACTIVACIÓ DE DEMO REAL DE 7 DIES
# ==========================================

@router.post("/leads/{lead_id}/activar-demo", response_model=Dict[str, Any])
async def activar_demo_lead(
    lead_id: str,
    payload: ActivarDemoRequest,
    db: AsyncSession = Depends(get_db_with_tenant_context),
) -> Dict[str, Any]:
    """Activa una Demo real de 7 dies aïllada a PostgreSQL per al prospecte amb la vertical escollida.

    Aquesta acció:
    1. Instancia un nou Tenant TRIAL aïllat a RLS (subdomini: demo-{slug}-{id}).
    2. Enllaça la IA central de demos a 'node_ia_url' (sense creuar dades gràcies al motor RLS).
    3. Inicialitza dades completes de la vertical seleccionada (articles, operaris, flota, feina de prova).
    4. Mou l'oportunitat a l'etapa 'DEMO_7_DIES' al Pipeline.
    5. Retorna les credencials d'accés llestes per enviar al prospecte.
    """
    try:
        lid = uuid.UUID(lead_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="ID de lead invàlid.")

    res_l = await db.execute(select(SaasLead).where(SaasLead.id == lid))
    lead = res_l.scalars().first()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead no trobat.")

    # La vertical pot ser la que portava el lead o una escollida expressament a la petició (Open Vertical)
    vertical_escollida = (payload.vertical or lead.vertical or "CampoPro").strip()
    durada_dies = payload.durada_dies or 7
    ara = datetime.now(timezone.utc)

    # Si ja tenia una demo creada i no demana recrear, refrescar data límit
    if lead.empresa_demo_id and not payload.recrear:
        res_emp = await db.execute(select(Empresa).where(Empresa.id == lead.empresa_demo_id))
        emp_existent = res_emp.scalars().first()
        if emp_existent:
            lead.data_fi_demo = ara + timedelta(days=durada_dies)
            lead.dies_demo_durada = durada_dies
            lead.estat_qualificacio = "DEMO_ACTIVA"
            emp_existent.estat_pagament = "TRIAL"
            emp_existent.vertical = vertical_escollida
            await db.commit()

            return {
                "status": "OK",
                "missatge": f"Demo de {durada_dies} dies prorrogada correctament.",
                "empresa_id": str(emp_existent.id),
                "subdomini": emp_existent.subdomini,
                "vertical": emp_existent.vertical,
                "data_caducitat": lead.data_fi_demo.isoformat(),
                "dies_restants": durada_dies,
                "url_oficina": f"https://{settings.PLATFORM_ADMIN_HOST}/gestio/login",
                "url_pwa": f"https://{settings.PLATFORM_ADMIN_HOST}/operari/login",
                "usuari_oficina": lead.email,
                "pin_oficina": "0000",
                "pin_operaris": ["1111", "2222"],
            }

    # 1. Crear nova Empresa Tenant de Demo aïllada
    slug_base = _sanititzar_slug(lead.nom_empresa)
    subdomini_provisional = f"demo-{slug_base}"
    check_sub = await db.execute(select(Empresa).where(Empresa.subdomini == subdomini_provisional))
    if check_sub.scalars().first():
        subdomini_provisional = f"demo-{slug_base}-{uuid.uuid4().hex[:4]}"

    nou_tenant_id = uuid.uuid4()
    nif_provisional = f"DEMO-{uuid.uuid4().hex[:8].upper()}"

    # Adreça de la IA central de demos (compartida de forma stateless)
    central_node_ia = settings.LM_STUDIO_URL or f"http://{settings.PLATFORM_EDGE_IP}:1234/v1"

    paleta_vertical = {
        "CampoPro": ("142 71% 25%", "38 92% 50%", "160 84% 39%"),  # Verd reg
        "ElectricPro": ("210 100% 20%", "45 100% 50%", "200 95% 45%"),  # Blau/Or REBT
        "HydroPro": ("199 89% 28%", "180 80% 45%", "215 90% 55%"),  # Blau aigua
    }.get(vertical_escollida, ("210 100% 15%", "38 92% 50%", "190 90% 50%"))

    nova_empresa = Empresa(
        id=nou_tenant_id,
        nom=f"{lead.nom_empresa} (Demo {durada_dies}D)",
        nif=nif_provisional,
        subdomini=subdomini_provisional,
        estat_domini="NO_CONFIGURAT",
        pla_subscripcio="PRO",
        estat_pagament="TRIAL",
        quota_operaris=max(5, lead.operaris_estimats),
        vertical=vertical_escollida,
        node_ia_url=central_node_ia,
        node_ia_actiu=True,
        feature_copilot_ia=True,
        feature_flota=True,
        feature_planols=True,
        feature_telegram=True,
        quota_disc_bytes_autoritzada=10 * 1024 * 1024 * 1024,  # 10 GB per a proves
        primari_hsl=paleta_vertical[0],
        secundari_hsl=paleta_vertical[1],
        accent_hsl=paleta_vertical[2],
        data_onboarding=ara,
    )
    db.add(nova_empresa)
    await db.flush()

    # 2. Usuari BOSS (Gerent Demo)
    boss_email = lead.email.strip().lower()
    boss_id = uuid.uuid4()
    u_boss = Usuari(
        id=boss_id,
        empresa_id=nou_tenant_id,
        nif=f"B{uuid.uuid4().hex[:8].upper()}",
        email=boss_email,
        nom=lead.nom_contacte,
        password_hash=_hash_pwd("Password123!"),
        pin_hash=_hash_pin("0000"),
        rol="BOSS",
        estat="ACTIU",
        created_at=ara,
    )
    db.add(u_boss)

    # 3. Dos Operaris de camp per a la PWA mòbil
    op1_id = uuid.uuid4()
    u_op1 = Usuari(
        id=op1_id,
        empresa_id=nou_tenant_id,
        nif=f"OP{uuid.uuid4().hex[:7].upper()}",
        email=f"operari1@{subdomini_provisional}.cat",
        nom="Marc Tècnic (Camp)",
        telefon="600000001",
        password_hash=_hash_pwd("Password123!"),
        pin_hash=_hash_pin("1111"),
        rol="OPERARI",
        estat="ACTIU",
        cost_hora_eur=22.0,
        created_at=ara,
    )
    db.add(u_op1)

    op2_id = uuid.uuid4()
    u_op2 = Usuari(
        id=op2_id,
        empresa_id=nou_tenant_id,
        nif=f"OP{uuid.uuid4().hex[:7].upper()}",
        email=f"operari2@{subdomini_provisional}.cat",
        nom="Jordi Ajudant (Camp)",
        telefon="600000002",
        password_hash=_hash_pwd("Password123!"),
        pin_hash=_hash_pin("2222"),
        rol="OPERARI",
        estat="ACTIU",
        cost_hora_eur=18.5,
        created_at=ara,
    )
    db.add(u_op2)

    # 4. Magatzem central i articles segons la vertical
    mag_id = uuid.uuid4()
    mag = Magatzem(
        id=mag_id,
        empresa_id=nou_tenant_id,
        nom="Magatzem Central de Proves",
        adreca="Seu Central Demo",
        actiu=True,
    )
    db.add(mag)
    await db.flush()

    articles_per_vertical = {
        "CampoPro": [
            ("Electrovàlvula 2'' 24VAC", "VALV-001", "Reg Localitzat", 45.0, 15),
            ("Tub Polietilè 50mm PN6 (100m)", "TUB-PE50", "Canonades", 85.0, 8),
            ("Filtre d'Anelles 2'' Manual", "FILT-02", "Filtratge", 32.5, 12),
        ],
        "ElectricPro": [
            ("Interruptor Magnetotèrmic 1P+N 16A", "MAG-16A", "Aparellatge REBT", 8.5, 30),
            ("Diferencial 2P 40A 30mA Tipus AC", "DIF-40A", "Proteccions", 24.0, 15),
            ("Cable Unipolar H07V-K 2.5mm Blau (100m)", "CAB-2.5-BL", "Conductors", 28.0, 10),
        ],
        "HydroPro": [
            ("Bomba de Pressió Superfície 1CV", "BOMB-1CV", "Bombament", 120.0, 4),
            ("Clau de Pas Esfera Llautó 1''", "VALV-LL-1", "Valvuleria", 12.0, 25),
            ("Tub Multicapa 20mm (50m)", "TUB-MULTI-20", "Canonades Aigua", 42.0, 6),
        ],
    }.get(vertical_escollida, [
        ("Material Polivalent A", "MAT-01", "General", 15.0, 20),
        ("Material Polivalent B", "MAT-02", "General", 35.0, 10),
    ])

    for nom_art, codi_art, fam_art, preu_art, estoc_art in articles_per_vertical:
        art_id = uuid.uuid4()
        art = Article(
            id=art_id,
            empresa_id=nou_tenant_id,
            nom=nom_art,
            referencia_inventari=f"{codi_art}-{nou_tenant_id.hex[:4].upper()}",
            familia=fam_art,
            preu_cost=preu_art * 0.7,
            preu_venda=preu_art,
        )
        db.add(art)
        await db.flush()
        est = EstocMagatzem(
            id=uuid.uuid4(),
            empresa_id=nou_tenant_id,
            magatzem_id=mag_id,
            article_id=art_id,
            quantitat_fisica=estoc_art,
        )
        db.add(est)
    await db.flush()

    # 5. Vehicle de flota de prova
    veh_id = uuid.uuid4()
    veh = Vehicle(
        id=veh_id,
        empresa_id=nou_tenant_id,
        matricula=f"9{uuid.uuid4().hex[:3].upper()}KLM",
        marca="Renault",
        model="Kangoo Maxi Tècnic",
        conductor_habitual_id=op1_id,
        estat_itv="FAVORABLE",
        estat="OPERATIU",
    )
    db.add(veh)
    await db.flush()

    # 6. Client de prova i ordre de treball inicial per provar la PWA
    cli_id = uuid.uuid4()
    cli = Client(
        id=cli_id,
        empresa_id=nou_tenant_id,
        codi=f"CLI-{nou_tenant_id.hex[:4].upper()}",
        rao_social="Finca / Client de Prova SL",
        nif=f"B{uuid.uuid4().hex[:8].upper()}",
        telefon="611223344",
        email="contacte@clientprova.cat",
        adreca_fiscal="Polígon Industrial Nord, Nau 4",
    )
    db.add(cli)
    await db.flush()

    ot_id = uuid.uuid4()
    ot = OrdreTreball(
        id=ot_id,
        empresa_id=nou_tenant_id,
        codi=f"OT-{nou_tenant_id.hex[:4].upper()}",
        client_id=cli_id,
        cap_de_colla_id=op1_id,
        vehicle_id=veh_id,
        titol=f"Revisió inicial d'instal·lació ({vertical_escollida})",
        adreca="Polígon Industrial Nord, Nau 4",
        descripcio="Feina de prova generada automàticament per testejar el fitxatge i signatura de l'operari a la PWA mòbil.",
        estat="PENDENT",
    )
    db.add(ot)
    await db.flush()

    # 7. FAQ per al Copilot RAG
    faq = FaqCorporativaRag(
        id=uuid.uuid4(),
        empresa_id=nou_tenant_id,
        pregunta="Quin protocol cal seguir davant una incidència urgent?",
        resposta="Notificar immediatament el cap d'operacions des del botó d'incidències de la PWA i registrar el material utilitzat.",
        categoria="Operativa",
    )
    db.add(faq)
    await db.flush()

    # 8. Vincular al Lead i actualitzar Pipeline
    data_fi = ara + timedelta(days=durada_dies)
    lead.empresa_demo_id = nou_tenant_id
    lead.data_inici_demo = ara
    lead.data_fi_demo = data_fi
    lead.dies_demo_durada = durada_dies
    lead.estat_qualificacio = "DEMO_ACTIVA"
    lead.vertical = vertical_escollida
    lead.updated_at = ara

    # Moure oportunitat a DEMO_7_DIES si existeix
    res_op = await db.execute(select(SaasOportunitat).where(SaasOportunitat.lead_id == lid))
    oportunitats = res_op.scalars().all()
    for op in oportunitats:
        op.etapa = "DEMO_7_DIES"
        op.probabilitat_percent = 50
        op.updated_at = ara

    # Registrar al timeline
    act = SaasActivitatLead(
        id=uuid.uuid4(),
        lead_id=lid,
        tipus="DEMO_LLANCADA",
        titol=f"🚀 Demo de {durada_dies} dies activada amb èxit",
        descripcio=(
            f"Tenant aïllat generat amb subdomini '{subdomini_provisional}'. "
            f"Vertical: {vertical_escollida}. Usuari Gerent: {boss_email} (Password123! / PIN 0000). "
            f"Operaris PWA mòbil: PIN 1111 (Marc) i PIN 2222 (Jordi). Caduca el {data_fi.strftime('%d/%m/%Y')}."
        ),
        autor_nom="Superadmin",
        created_at=ara,
    )
    db.add(act)

    # Registrar esdeveniment de venciment de la Demo de 7 dies al Calendari Comercial
    venciment_demo_cal = SaasCorreuMissatge(
        id=uuid.uuid4(),
        lead_id=lid,
        tipus_item_calendari="VENCIMENT_DEMO",
        pas_sequencia=None,
        tempo_dies_offset=durada_dies,
        data_programada=data_fi,
        direccio="INTERN_CALENDARI",
        estat_enviament="ESBORRANY_PROGRAMAT",
        remitent=settings.SUPERADMIN_OUTREACH_EMAIL or "tecnic@sevalor.net",
        destinatari=lead.email,
        assumpte=f"Venciment Demo {durada_dies} Dies - {lead.nom_empresa}",
        cos_text=f"La Demo aïllada ('{subdomini_provisional}') caduca el {data_fi.strftime('%d/%m/%Y')}. Contactar per tancament.",
        message_id=f"<{uuid.uuid4().hex}@sevalor.net>",
        created_at=ara,
    )
    db.add(venciment_demo_cal)

    await db.commit()

    logger.info(f"[CRM Demo] Tenant Demo '{subdomini_provisional}' activat per al lead '{lead.nom_empresa}'.")

    return {
        "status": "OK",
        "missatge": f"Demo de {durada_dies} dies generada amb èxit per a '{lead.nom_empresa}'.",
        "empresa_id": str(nou_tenant_id),
        "subdomini": subdomini_provisional,
        "vertical": vertical_escollida,
        "data_caducitat": data_fi.isoformat(),
        "dies_restants": durada_dies,
        "url_oficina": f"https://{settings.PLATFORM_ADMIN_HOST}/gestio/login",
        "url_pwa": f"https://{settings.PLATFORM_ADMIN_HOST}/operari/login",
        "usuari_oficina": boss_email,
        "password_oficina": "Password123!",
        "pin_boss": "0000",
        "pins_operaris": [
            {"nom": "Marc Tècnic", "pin": "1111"},
            {"nom": "Jordi Ajudant", "pin": "2222"},
        ],
    }


# ==========================================
# ENDPOINTS TASQUES ATÒMIQUES PER CP (T011)
# ==========================================

async def executar_proces_lot_cp(
    db: AsyncSession,
    tasca_id: uuid.UUID,
    codi_postal: str,
    vertical: str,
    operaris_minims: int,
    limit_batch: int = 5,
    candidats_descoberts: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """Processa el lot atòmic per a un Codi Postal determinat (descoberta, enriquiment, scoring i leads)."""
    ara = datetime.now(timezone.utc)
    res_t = await db.execute(select(SaasProspeccioTasca).where(SaasProspeccioTasca.id == tasca_id))
    tasca = res_t.scalars().first()
    if not tasca:
        raise ValueError(f"Tasca {tasca_id} no trobada a la base de dades.")

    # 1. Descoberta d'empreses per CP i vertical (Zero Mock Data: cap fallback sintètic)
    if candidats_descoberts is not None:
        candidats_raw = candidats_descoberts
        embut = {"trobats": len(candidats_raw), "validats": len(candidats_raw)}
    else:
        candidats_raw, embut = await firecrawl_service.descobrir_empreses_codi_postal(
            codi_postal=codi_postal,
            vertical=vertical,
            limit=limit_batch,
        )
    tasca.embut_descoberta = embut

    tasca.total_trobats = len(candidats_raw)
    tot_sel = 0
    tot_desc = 0
    tot_dup = 0

    geo_muni = await obtenir_municipi_de_codi_postal(codi_postal.strip())
    municipi_esperat = geo_muni.get("municipi") if geo_muni else None

    cp_clean = codi_postal.strip()[:10]
    vertical_clean = vertical.strip()[:150]

    for item in candidats_raw:
        cand_id = uuid.uuid4()
        nom = (item.get("nom_empresa") or "Empresa Sense Nom").strip()[:150]
        web = (item.get("web_url") or "").strip()[:255]
        dom = normalitzar_domini(web)[:150]
        adr = (item.get("adreca_fisica") or "").strip()[:255] or None
        adr_norm = normalitzar_adreca(adr)[:255] if adr else None
        cif_raw = item.get("cif")
        cif_norm = normalitzar_cif(cif_raw)[:20] if cif_raw else None
        email_det = (item.get("email") or "").strip()[:150] or None
        telefon_det = (item.get("telefon") or "").strip()[:30] or None

        try:
            async with db.begin_nested():
                # 2. Multi-Validació de 3 vectors contra saas_leads, empreses i saas_exclusio_rgpd
                es_dup, vector_dup, motiu_dup = await verificar_duplicitat_multivector(
                    db=db,
                    domini=dom,
                    adreca=adr_norm,
                    cif=cif_norm,
                )

                if es_dup:
                    tot_dup += 1
                    fonts_dup = formatar_fonts_verificables({}, web_url=web)
                    candidat_dup = SaasProspeccioCandidat(
                        id=cand_id,
                        tasca_id=tasca_id,
                        nom_empresa=nom,
                        cif=cif_norm,
                        web_url=web or f"https://{dom or 'duplicat.invalid'}"[:255],
                        domini_normalitzat=dom or "duplicat.invalid",
                        adreca_fisica=adr,
                        adreca_normalitzada=adr_norm,
                        codi_postal=cp_clean,
                        vertical=vertical_clean,
                        fonts_investigades=",".join(fonts_dup),
                        email_detectat=email_det,
                        telefon_detectat=telefon_det,
                        mx_validat=False,
                        operaris_estimats=0,
                        score=0,
                        estat_decisio="DUPLICAT",
                        vector_duplicitat=(vector_dup or "DOMINI_WEB")[:50],
                        motiu_detallat_ia=motiu_dup or "Candidat duplicat segons filtre multi-vector.",
                        created_at=ara,
                        updated_at=ara,
                    )
                    db.add(candidat_dup)
                    await db.flush()
                    continue

                # 3. Investigació complementària
                investigacio = await firecrawl_service.investigar_empresa_completa(
                    nom_empresa=nom,
                    web_url=web,
                    codi_postal=cp_clean,
                    vertical=vertical_clean,
                    dades_inicials=item,
                )

                fonts = list(investigacio.get("fonts_investigades", []))
                gk = item.get("gatekeeper")
                if not gk:
                    nom_cand = item.get("decisor_nom") or investigacio.get("gatekeeper_hints", {}).get("nom")
                    if nom_cand and es_nom_persona_real(nom_cand):
                        carrec_cand = (
                            item.get("decisor_carrec")
                            or investigacio.get("gatekeeper_hints", {}).get("carrec")
                            or "Direcció Tècnica"
                        )
                        gk = Gatekeeper(
                            nom=nom_cand.strip(),
                            carrec=carrec_cand.strip() if carrec_cand else "Direcció Tècnica",
                            font_url=item.get("linkedin_url") or web or "web",
                            cita=f"Gatekeeper verificat a les fonts: {nom_cand.strip()}",
                            confianca="alta",
                        )
                if gk:
                    fonts.append(f"web|{gk.font_url}")

                if not adr and investigacio.get("adreca_detectada"):
                    adr = str(investigacio["adreca_detectada"]).strip()[:255] or None
                    adr_norm = normalitzar_adreca(adr)[:255] if adr else None
                if not cif_norm and investigacio.get("cif_detectat"):
                    cif_norm = normalitzar_cif(str(investigacio["cif_detectat"]))[:20] or None
                if not email_det and investigacio.get("email_detectat"):
                    email_det = str(investigacio["email_detectat"]).strip()[:150] or None

                email_empresa_det = (
                    item.get("email_empresa") or investigacio.get("email_empresa_detectat") or email_det
                )
                email_gk_det = item.get("email_gatekeeper") or investigacio.get("email_gatekeeper_detectat")
                if email_gk_det:
                    email_det = str(email_gk_det).strip()[:150]
                if not telefon_det and investigacio.get("telefon_detectat"):
                    telefon_det = str(investigacio["telefon_detectat"]).strip()[:30] or None

                # 4. Validació MX Shield
                mx_valid, _ = await validar_email_mx(email_det, db=db)
                te_contacte_operatiu = bool((email_det and mx_valid) or telefon_det)

                # 5. Avaluació i Lead Scoring amb OpenRouter
                if item.get("pagines"):
                    web_ctx = construir_context(item["pagines"], max_chars=6000)
                else:
                    web_ctx = item.get("web_markdown") or investigacio.get("web_markdown") or ""

                avaluacio = await qualificar_candidat_amb_openrouter(
                    nom_empresa=nom,
                    web_url=web,
                    codi_postal=cp_clean,
                    vertical=vertical_clean,
                    operaris_minims=operaris_minims,
                    web_markdown=web_ctx,
                    fonts_investigades=fonts,
                    fita_recent=investigacio.get("fita_recent"),
                    gatekeeper_hints=investigacio.get("gatekeeper_hints"),
                    gatekeeper_bloc=bloc_gatekeeper(gk),
                    adreca_fisica=adr or "",
                    municipi=municipi_esperat,
                    te_contacte_operatiu=te_contacte_operatiu,
                    db=db,
                )

                # 6. Regles dures post-IA: el codi sempre té l'última paraula
                if item.get("cp_verificat") is not None:
                    cp_ok = bool(item["cp_verificat"])
                elif adr:
                    cp_ok = bool(adreca_valida_per_cp(adr, cp_clean))
                else:
                    cp_ok = False

                tel_valid = bool(
                    item.get("telefon_valid")
                    if item.get("telefon_valid") is not None
                    else (telefon_det and bool(telefons_es(telefon_det)))
                )

                aplicar_regles_dures(
                    avaluacio,
                    ContextValidat(
                        ubicacio_ok=cp_ok,
                        vertical_ok=True,
                        gatekeeper=gk,
                        fonts_entrada=set(fonts),
                        fita_recent=investigacio.get("fita_recent"),
                        telefon_valid=tel_valid,
                    ),
                )

                lead_creat_id: Optional[uuid.UUID] = None
                decisor_nom_clean = avaluacio.decisor_nom.strip()[:100] if avaluacio.decisor_nom else None
                decisor_carrec_clean = avaluacio.decisor_carrec.strip()[:100] if avaluacio.decisor_carrec else None

                fonts_str = (
                    ",".join(str(f) for f in avaluacio.fonts_investigades if f)
                    if avaluacio.fonts_investigades
                    else ""
                )

                es_seleccionat = avaluacio.estat_decisio in ("SELECCIONAT", "SELECCIONAT_SENSE_GATEKEEPER")
                if es_seleccionat:
                    tot_sel += 1
                    lead_creat_id = uuid.uuid4()
                    nom_contacte_final = (decisor_nom_clean or f"Direcció Tècnica ({nom[:75]})")[:100]
                    email_final = (email_det or f"contacte@{dom or 'empresa.cat'}")[:150]
                    nota_emails = ""
                    if email_empresa_det and email_gk_det and email_empresa_det != email_gk_det:
                        nota_emails = f" [Email empresa: {email_empresa_det} | Email Gatekeeper: {email_gk_det}]"

                    motiu_lead = avaluacio.motiu_detallat_ia or "Avaluació completada."
                    nou_lead = SaasLead(
                        id=lead_creat_id,
                        nom_empresa=nom,
                        nom_contacte=nom_contacte_final,
                        email=email_final,
                        telefon=telefon_det,
                        vertical=vertical_clean,
                        origen=f"SCRAPING_CP_{cp_clean}"[:50],
                        estat_qualificacio="QUALIFICAT",
                        operaris_estimats=avaluacio.operaris_estimats,
                        notes=f"Generat des del lot CP {cp_clean}.{nota_emails} {motiu_lead}"[:2000],
                        cif=cif_norm,
                        web_url=web,
                        domini_normalitzat=dom,
                        adreca_fisica=adr,
                        adreca_normalitzada=adr_norm,
                        codi_postal=cp_clean,
                        carrec_contacte=decisor_carrec_clean,
                        fonts_investigades=fonts_str,
                        fita_recent=avaluacio.fita_recent,
                        punt_dolor_detectat=avaluacio.punt_dolor,
                        angle_atac=(avaluacio.angle_atac or "ANGLE_A_VISIBILITAT_TELEGRAM")[:50],
                        score_qualificacio=avaluacio.score,
                        justificacio_ia=motiu_lead,
                        mx_validat=mx_valid,
                        cp_geocode_retornat=item.get("cp_geocode_retornat"),
                        cp_geocode_coincideix=item.get("cp_geocode_coincideix"),
                        gatekeeper_font_url=gk.font_url if gk else None,
                        gatekeeper_cita=gk.cita if gk else None,
                        gatekeeper_confianca=gk.confianca if gk else None,
                        tasca_prospeccio_id=tasca_id,
                        created_at=ara,
                        updated_at=ara,
                    )
                    db.add(nou_lead)
                    await db.flush()

                    nova_op = SaasOportunitat(
                        id=uuid.uuid4(),
                        lead_id=lead_creat_id,
                        titol=f"Llicència {vertical_clean[:50]} - {nom[:120]}"[:200],
                        etapa="PROSPECCIO",
                        valor_mensual_estimat=float(avaluacio.operaris_estimats * 18.0),
                        valor_ia_setup=150.0,
                        probabilitat_percent=30,
                        created_at=ara,
                        updated_at=ara,
                    )
                    db.add(nova_op)

                    if avaluacio.campanya_3_emails:
                        await programar_campanya_3_emails(
                            lead_id=lead_creat_id,
                            campanya=avaluacio.campanya_3_emails,
                            db=db,
                            data_base=ara,
                        )
                else:
                    tot_desc += 1

                motiu_cand = avaluacio.motiu_detallat_ia or "Avaluació completada."
                candidat_registre = SaasProspeccioCandidat(
                    id=cand_id,
                    tasca_id=tasca_id,
                    nom_empresa=nom,
                    cif=cif_norm,
                    web_url=web or f"https://{dom or 'descartat.invalid'}"[:255],
                    domini_normalitzat=dom or "descartat.invalid",
                    adreca_fisica=adr,
                    adreca_normalitzada=adr_norm,
                    codi_postal=cp_clean,
                    vertical=vertical_clean,
                    fonts_investigades=fonts_str,
                    email_detectat=email_det,
                    telefon_detectat=telefon_det,
                    mx_validat=mx_valid,
                    operaris_estimats=avaluacio.operaris_estimats,
                    decisor_nom=decisor_nom_clean,
                    decisor_carrec=decisor_carrec_clean,
                    fita_recent=avaluacio.fita_recent,
                    punt_dolor=avaluacio.punt_dolor,
                    angle_atac=(avaluacio.angle_atac or "ANGLE_A_VISIBILITAT_TELEGRAM")[:50],
                    score=avaluacio.score,
                    estat_decisio=avaluacio.estat_decisio[:50],
                    cp_geocode_retornat=item.get("cp_geocode_retornat"),
                    cp_geocode_coincideix=item.get("cp_geocode_coincideix"),
                    gatekeeper_font_url=gk.font_url if gk else None,
                    gatekeeper_cita=gk.cita if gk else None,
                    gatekeeper_confianca=gk.confianca if gk else None,
                    vector_duplicitat=None,
                    motiu_detallat_ia=motiu_cand,
                    lead_id=lead_creat_id,
                    created_at=ara,
                    updated_at=ara,
                )
                db.add(candidat_registre)
                await db.flush()

        except Exception as exc:
            logger.error("Error aïllat processant candidat '%s' (%s): %s", nom, web, exc, exc_info=True)
            tot_desc += 1
            try:
                async with db.begin_nested():
                    candidat_error = SaasProspeccioCandidat(
                        id=cand_id,
                        tasca_id=tasca_id,
                        nom_empresa=nom[:150],
                        cif=cif_norm,
                        web_url=web or "https://error-extraccio.invalid",
                        domini_normalitzat=dom or "error-extraccio.invalid",
                        adreca_fisica=adr[:255] if adr else None,
                        adreca_normalitzada=adr_norm[:255] if adr_norm else None,
                        codi_postal=cp_clean,
                        vertical=vertical_clean,
                        fonts_investigades="",
                        email_detectat=email_det[:150] if email_det else None,
                        telefon_detectat=telefon_det[:30] if telefon_det else None,
                        mx_validat=False,
                        operaris_estimats=0,
                        score=0,
                        estat_decisio="ERROR_EXTRACCIO",
                        vector_duplicitat=None,
                        motiu_detallat_ia=f"Error d'extracció aïllat durant el processament del candidat: {str(exc)[:400]}",
                        lead_id=None,
                        created_at=ara,
                        updated_at=ara,
                    )
                    db.add(candidat_error)
                    await db.flush()
            except Exception as nested_exc:
                logger.error("Error enregistrant candidat_error per '%s': %s", nom, nested_exc)

        # Actualització periòdica dels totals per alimentar l'SSE stream
        tasca.total_seleccionats = tot_sel
        tasca.total_descartats = tot_desc
        tasca.total_duplicats = tot_dup
        await db.commit()

    tasca.total_seleccionats = tot_sel
    tasca.total_descartats = tot_desc
    tasca.total_duplicats = tot_dup
    tasca.estat = "COMPLETAT"
    tasca.completed_at = datetime.now(timezone.utc)
    tasca.resum_execucio = (
        f"Lot atòmic finalitzat per al CP {codi_postal} ({vertical}). "
        f"Trobats: {tasca.total_trobats}, Seleccionats: {tot_sel}, Descartats: {tot_desc}, Duplicats: {tot_dup}."
    )
    try:
        await db.commit()
    except Exception as commit_exc:
        logger.exception("Error fent commit del lot CP %s: %s", codi_postal, commit_exc)
        await db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Error finalitzant la transacció del lot de prospecció: {str(commit_exc)[:250]}",
        )

    return {
        "status": "OK",
        "tasca_id": str(tasca_id),
        "codi_postal": codi_postal.strip(),
        "vertical": vertical.strip(),
        "total_trobats": tasca.total_trobats,
        "total_seleccionats": tot_sel,
        "total_descartats": tot_desc,
        "total_duplicats": tot_dup,
        "missatge": tasca.resum_execucio,
    }


async def executar_tasca_cp_background(
    tasca_id: uuid.UUID,
    codi_postal: str,
    vertical: str,
    operaris_minims: int,
    limit_batch: int = 5,
    candidats_descoberts: Optional[List[Dict[str, Any]]] = None,
) -> None:
    """Executa el lot atòmic de prospecció en una sessió aïllada en segon pla (Opció B)."""
    try:
        async with AsyncSessionLocal() as session:
            await set_tenant_context(session, None, is_superadmin=True, role="SUPERADMIN")
            await executar_proces_lot_cp(
                db=session,
                tasca_id=tasca_id,
                codi_postal=codi_postal,
                vertical=vertical,
                operaris_minims=operaris_minims,
                limit_batch=limit_batch,
                candidats_descoberts=candidats_descoberts,
            )
    except Exception as exc:
        logger.exception("Error aïllat en segon pla per a la tasca CP %s (%s): %s", tasca_id, codi_postal, exc)
        try:
            async with AsyncSessionLocal() as session_err:
                await set_tenant_context(session_err, None, is_superadmin=True, role="SUPERADMIN")
                res = await session_err.execute(select(SaasProspeccioTasca).where(SaasProspeccioTasca.id == tasca_id))
                t = res.scalars().first()
                if t:
                    t.estat = "ERROR"
                    t.resum_execucio = f"Error d'execució en segon pla: {str(exc)[:300]}"
                    t.completed_at = datetime.now(timezone.utc)
                    await session_err.commit()
        except Exception as e_save:
            logger.error("No s'ha pogut desar l'estat d'error per a la tasca %s: %s", tasca_id, e_save)


@router.post("/tasques-cp", response_model=Dict[str, Any], status_code=status.HTTP_201_CREATED)
async def crear_executar_tasca_cp(
    payload: TascaCpCreate,
    db: AsyncSession = Depends(get_db_with_tenant_context),
) -> Dict[str, Any]:
    """Inicia i executa un lot atòmic per Codi Postal i Vertical escrita lliurement per l'humà.

    FR-001, FR-002, FR-003, FR-004, FR-006:
    - No encadena mai el CP següent automàticament (FR-003).
    - Executa deduplicació multi-validació per 3 vectors (Domini, Adreça, CIF).
    - Registra transparentment TOTS els candidats (Seleccionats, Descartats, Duplicats).
    - Genera la campanya de 3 correus amb tempo per als seleccionats.
    - Suporta execució asíncrona en segon pla desacoblada (Opció B) per evitar talls de proxy/timeout.
    """
    ara = datetime.now(timezone.utc)
    tasca_id = uuid.uuid4()

    tasca = SaasProspeccioTasca(
        id=tasca_id,
        codi_postal=payload.codi_postal.strip()[:10],
        vertical=payload.vertical.strip()[:150],
        operaris_minims=payload.operaris_minims,
        estat="EXECUTANT",
        total_trobats=0,
        total_seleccionats=0,
        total_descartats=0,
        total_duplicats=0,
        created_at=ara,
    )
    db.add(tasca)
    await db.commit()

    # Si s'ha demanat expressament en segon pla o si no s'aporten candidats mock (cerca real web/RASIC):
    en_segon_pla = (
        payload.executar_en_segon_pla
        if payload.executar_en_segon_pla is not None
        else (payload.candidats_descoberts is None)
    )

    limit_batch = payload.limit or 5

    if en_segon_pla:
        t = asyncio.create_task(
            executar_tasca_cp_background(
                tasca_id=tasca_id,
                codi_postal=payload.codi_postal,
                vertical=payload.vertical,
                operaris_minims=payload.operaris_minims,
                limit_batch=limit_batch,
                candidats_descoberts=payload.candidats_descoberts,
            )
        )
        _background_tasks.add(t)
        t.add_done_callback(_background_tasks.discard)

        return {
            "status": "EXECUTANT",
            "tasca_id": str(tasca_id),
            "codi_postal": payload.codi_postal.strip(),
            "vertical": payload.vertical.strip(),
            "total_trobats": 0,
            "total_seleccionats": 0,
            "total_descartats": 0,
            "total_duplicats": 0,
            "missatge": (
                f"Lot atòmic iniciat en segon pla per al CP {payload.codi_postal} ({payload.vertical}). "
                "Connectant amb l'SSE stream en temps real..."
            ),
        }
    else:
        # Execució síncrona directa (apta per a tests)
        res_sync = await executar_proces_lot_cp(
            db=db,
            tasca_id=tasca_id,
            codi_postal=payload.codi_postal,
            vertical=payload.vertical,
            operaris_minims=payload.operaris_minims,
            limit_batch=limit_batch,
            candidats_descoberts=payload.candidats_descoberts,
        )
        return res_sync


@router.get("/tasques-cp", response_model=List[Dict[str, Any]])
async def llistar_tasques_cp(
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db_with_tenant_context),
) -> List[Dict[str, Any]]:
    """Llista tots els lots atòmics per Codi Postal executats."""
    stmt = select(SaasProspeccioTasca).order_by(desc(SaasProspeccioTasca.created_at)).limit(limit)
    res = await db.execute(stmt)
    tasques = res.scalars().all()

    return [
        {
            "id": str(t.id),
            "codi_postal": t.codi_postal,
            "vertical": t.vertical,
            "operaris_minims": t.operaris_minims,
            "estat": t.estat,
            "total_trobats": t.total_trobats,
            "total_seleccionats": t.total_seleccionats,
            "total_descartats": t.total_descartats,
            "total_duplicats": t.total_duplicats,
            "resum_execucio": t.resum_execucio,
            "created_at": t.created_at.isoformat(),
            "completed_at": t.completed_at.isoformat() if t.completed_at else None,
        }
        for t in tasques
    ]


@router.get("/tasques-cp/{tasca_id}", response_model=Dict[str, Any])
async def obtenir_detall_tasca_cp(
    tasca_id: str,
    db: AsyncSession = Depends(get_db_with_tenant_context),
) -> Dict[str, Any]:
    """Retorna el detall d'un lot de Codi Postal amb TOTS els candidats auditats."""
    try:
        tid = uuid.UUID(tasca_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="ID de tasca invàlid.")

    res_t = await db.execute(select(SaasProspeccioTasca).where(SaasProspeccioTasca.id == tid))
    tasca = res_t.scalars().first()
    if not tasca:
        raise HTTPException(status_code=404, detail="Tasca de Codi Postal no trobada.")

    res_c = await db.execute(
        select(SaasProspeccioCandidat)
        .where(SaasProspeccioCandidat.tasca_id == tid)
        .order_by(desc(SaasProspeccioCandidat.score))
    )
    candidats = res_c.scalars().all()

    return {
        "id": str(tasca.id),
        "codi_postal": tasca.codi_postal,
        "vertical": tasca.vertical,
        "operaris_minims": tasca.operaris_minims,
        "estat": tasca.estat,
        "total_trobats": tasca.total_trobats,
        "total_seleccionats": tasca.total_seleccionats,
        "total_descartats": tasca.total_descartats,
        "total_duplicats": tasca.total_duplicats,
        "resum_execucio": tasca.resum_execucio,
        "embut_descoberta": tasca.embut_descoberta,
        "created_at": tasca.created_at.isoformat(),
        "completed_at": tasca.completed_at.isoformat() if tasca.completed_at else None,
        "candidats": [
            {
                "id": str(c.id),
                "nom_empresa": c.nom_empresa,
                "cif": c.cif,
                "web_url": c.web_url,
                "domini_normalitzat": c.domini_normalitzat,
                "adreca_fisica": c.adreca_fisica,
                "codi_postal": c.codi_postal,
                "vertical": c.vertical,
                "fonts_investigades": c.fonts_investigades,
                "fonts_urls": extreure_mapa_fonts_urls(c.fonts_investigades, web_url=c.web_url),
                "email_detectat": c.email_detectat,
                "telefon_detectat": c.telefon_detectat,
                "mx_validat": c.mx_validat,
                "operaris_estimats": c.operaris_estimats,
                "decisor_nom": c.decisor_nom,
                "decisor_carrec": c.decisor_carrec,
                "fita_recent": c.fita_recent,
                "punt_dolor": c.punt_dolor,
                "angle_atac": c.angle_atac,
                "score": c.score,
                "estat_decisio": c.estat_decisio,
                "cp_geocode_retornat": c.cp_geocode_retornat,
                "cp_geocode_coincideix": c.cp_geocode_coincideix,
                "gatekeeper_font_url": c.gatekeeper_font_url,
                "gatekeeper_cita": c.gatekeeper_cita,
                "gatekeeper_confianca": c.gatekeeper_confianca,
                "vector_duplicitat": c.vector_duplicitat,
                "motiu_detallat_ia": c.motiu_detallat_ia,
                "corregit_huma": c.corregit_huma,
                "decisio_humana": c.decisio_humana,
                "motiu_correccio_humana": c.motiu_correccio_humana,
                "lead_id": str(c.lead_id) if c.lead_id else None,
                "created_at": c.created_at.isoformat(),
            }
            for c in candidats
        ],
    }


@router.get("/tasques-cp/{tasca_id}/stream")
async def stream_progres_tasca_cp(
    tasca_id: str,
    db: AsyncSession = Depends(get_db_with_tenant_context),
) -> StreamingResponse:
    """Stream Server-Sent Events (SSE) en temps real amb el progrés d'un lot de CP."""
    try:
        tid = uuid.UUID(tasca_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="ID invàlid.")

    async def _sse_generator() -> AsyncGenerator[str, None]:
        res_t = await db.execute(select(SaasProspeccioTasca).where(SaasProspeccioTasca.id == tid))
        tasca = res_t.scalars().first()
        if not tasca:
            yield f"event: error\ndata: {json.dumps({'error': 'Tasca no trobada'})}\n\n"
            return

        yield f"event: status\ndata: {json.dumps({'pas': 'INICI', 'tasca_id': str(tasca.id), 'estat': tasca.estat, 'codi_postal': tasca.codi_postal})}\n\n"

        if tasca.estat in ("COMPLETAT", "ERROR"):
            yield f"event: progres\ndata: {json.dumps({'pas': 'COMPLETAT', 'total_trobats': tasca.total_trobats, 'total_seleccionats': tasca.total_seleccionats, 'total_descartats': tasca.total_descartats, 'total_duplicats': tasca.total_duplicats, 'resum': tasca.resum_execucio})}\n\n"
            yield f"event: close\ndata: {json.dumps({'missatge': 'Stream finalitzat'})}\n\n"
            return

        intents = 0
        max_intents = 300  # Màxim 5 minuts (300 segons)
        ultim_trobats = tasca.total_trobats
        ultim_seleccionats = tasca.total_seleccionats
        ultim_descartats = tasca.total_descartats

        while intents < max_intents:
            await asyncio.sleep(1.0)
            intents += 1

            async with AsyncSessionLocal() as session_stream:
                await set_tenant_context(session_stream, None, is_superadmin=True, role="SUPERADMIN")
                res_upd = await session_stream.execute(
                    select(SaasProspeccioTasca).where(SaasProspeccioTasca.id == tid)
                )
                tasca_upd = res_upd.scalars().first()
                if not tasca_upd:
                    break

                if tasca_upd.estat == "COMPLETAT":
                    yield f"event: progres\ndata: {json.dumps({'pas': 'COMPLETAT', 'total_trobats': tasca_upd.total_trobats, 'total_seleccionats': tasca_upd.total_seleccionats, 'total_descartats': tasca_upd.total_descartats, 'total_duplicats': tasca_upd.total_duplicats, 'resum': tasca_upd.resum_execucio})}\n\n"
                    break
                elif tasca_upd.estat == "ERROR":
                    yield f"event: progres\ndata: {json.dumps({'pas': 'ERROR', 'error': tasca_upd.resum_execucio or 'Error executant tasca'})}\n\n"
                    break

                ha_canviat = (
                    tasca_upd.total_trobats != ultim_trobats
                    or tasca_upd.total_seleccionats != ultim_seleccionats
                    or tasca_upd.total_descartats != ultim_descartats
                )
                if ha_canviat or intents % 5 == 0:
                    ultim_trobats = tasca_upd.total_trobats
                    ultim_seleccionats = tasca_upd.total_seleccionats
                    ultim_descartats = tasca_upd.total_descartats
                    yield f"event: progres\ndata: {json.dumps({'pas': 'PROGRES', 'total_trobats': tasca_upd.total_trobats, 'total_seleccionats': tasca_upd.total_seleccionats, 'total_descartats': tasca_upd.total_descartats, 'total_duplicats': tasca_upd.total_duplicats})}\n\n"

        yield f"event: close\ndata: {json.dumps({'missatge': 'Stream finalitzat'})}\n\n"

    return StreamingResponse(_sse_generator(), media_type="text/event-stream")


# ==========================================
# ENDPOINTS DOBLE BUCLE D'APRENENTATGE (T012)
# ==========================================

@router.post("/candidats/{candidat_id}/corregir-criteri", response_model=Dict[str, Any])
async def corregir_criteri_candidat(
    candidat_id: str,
    payload: CorregirCriteriRequest,
    db: AsyncSession = Depends(get_db_with_tenant_context),
) -> Dict[str, Any]:
    """Inverteix la decisió de la IA exigint OBLIGATÒRIAMENT la justificació humana (FR-011)."""
    try:
        cid = uuid.UUID(candidat_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="ID de candidat invàlid.")

    if not payload.motiu_correccio_humana or len(payload.motiu_correccio_humana.strip()) < 10:
        raise HTTPException(
            status_code=400,
            detail="La justificació humana ('motiu_correccio_humana') és obligatòria i ha de tenir com a mínim 10 caràcters.",
        )

    res_c = await db.execute(select(SaasProspeccioCandidat).where(SaasProspeccioCandidat.id == cid))
    candidat = res_c.scalars().first()
    if not candidat:
        raise HTTPException(status_code=404, detail="Candidat no trobat.")

    ara = datetime.now(timezone.utc)
    decisio_anterior = candidat.decisio_humana or candidat.estat_decisio
    nova = payload.nova_decisio.strip().upper()

    candidat.corregit_huma = True
    candidat.decisio_humana = nova
    candidat.estat_decisio = nova
    candidat.motiu_correccio_humana = payload.motiu_correccio_humana.strip()
    candidat.updated_at = ara

    # Actualitzar comptadors de la tasca mare si la decisió ha canviat
    if decisio_anterior != nova:
        res_t = await db.execute(select(SaasProspeccioTasca).where(SaasProspeccioTasca.id == candidat.tasca_id))
        tasca_mare = res_t.scalars().first()
        if tasca_mare:
            if nova in ("SELECCIONAT", "SELECCIONAT_SENSE_GATEKEEPER"):
                tasca_mare.total_seleccionats += 1
                if decisio_anterior in ("DESCARTAT", "ERROR_EXTRACCIO"):
                    tasca_mare.total_descartats = max(0, tasca_mare.total_descartats - 1)
                elif decisio_anterior == "DUPLICAT":
                    tasca_mare.total_duplicats = max(0, tasca_mare.total_duplicats - 1)
            elif nova == "DESCARTAT":
                if decisio_anterior in ("SELECCIONAT", "SELECCIONAT_SENSE_GATEKEEPER"):
                    tasca_mare.total_descartats += 1
                    tasca_mare.total_seleccionats = max(0, tasca_mare.total_seleccionats - 1)
                elif decisio_anterior == "DUPLICAT":
                    tasca_mare.total_descartats += 1
                    tasca_mare.total_duplicats = max(0, tasca_mare.total_duplicats - 1)

    # Si canvia a SELECCIONAT i no tenia lead, es crea amb la seva oportunitat i campanya de 3 correus
    if nova in ("SELECCIONAT", "SELECCIONAT_SENSE_GATEKEEPER") and not candidat.lead_id:
        nou_lead_id = uuid.uuid4()
        lead = SaasLead(
            id=nou_lead_id,
            nom_empresa=candidat.nom_empresa,
            nom_contacte=candidat.decisor_nom or "Responsable",
            email=candidat.email_detectat or f"info@{candidat.domini_normalitzat}",
            telefon=candidat.telefon_detectat,
            vertical=candidat.vertical,
            origen=f"CORRECCIO_HUMANA_CP_{candidat.codi_postal}",
            estat_qualificacio="QUALIFICAT",
            operaris_estimats=max(candidat.operaris_estimats, 5),
            notes=f"Recuperat per l'humà: {candidat.motiu_correccio_humana}",
            cif=candidat.cif,
            web_url=candidat.web_url,
            domini_normalitzat=candidat.domini_normalitzat,
            adreca_fisica=candidat.adreca_fisica,
            adreca_normalitzada=candidat.adreca_normalitzada,
            codi_postal=candidat.codi_postal,
            carrec_contacte=candidat.decisor_carrec,
            score_qualificacio=85,
            justificacio_ia=f"Recuperat per correcció humana: {candidat.motiu_correccio_humana}",
            mx_validat=candidat.mx_validat,
            tasca_prospeccio_id=candidat.tasca_id,
            created_at=ara,
            updated_at=ara,
        )
        db.add(lead)
        candidat.lead_id = nou_lead_id
        await db.flush()

        # Crear oportunitat inicial al Kanban
        nova_op = SaasOportunitat(
            id=uuid.uuid4(),
            lead_id=nou_lead_id,
            titol=f"Llicència {candidat.vertical} - {candidat.nom_empresa}",
            etapa="PROSPECCIO",
            valor_mensual_estimat=float(max(candidat.operaris_estimats, 5) * 18.0),
            valor_ia_setup=150.0,
            probabilitat_percent=30,
            created_at=ara,
            updated_at=ara,
        )
        db.add(nova_op)

        # Generar campanya de 3 correus
        campanya_default = [
            EmailStepSchema(
                pas=1,
                tempo_offset_dies=0,
                assumpte=f"Proposta de col·laboració tècnica per a {candidat.nom_empresa}",
                cos_text=f"Hola {candidat.decisor_nom or 'Responsable'},\nus contactem per presentar Sevalor Suite (PWA + Bot de Telegram).",
            ),
            EmailStepSchema(
                pas=2,
                tempo_offset_dies=4,
                assumpte=f"Cas d'èxit en empreses de {candidat.vertical}",
                cos_text="Hola, com vam comentar fa uns dies us enviem un cas d'èxit del vostre sector amb la PWA de Sevalor.",
            ),
            EmailStepSchema(
                pas=3,
                tempo_offset_dies=8,
                assumpte=f"Demo autònoma de 7 dies per a {candidat.nom_empresa}",
                cos_text="Hola, us proposem activar un entorn demo de 7 dies totalment gratuït.",
            ),
        ]
        await programar_campanya_3_emails(lead_id=nou_lead_id, campanya=campanya_default, db=db, data_base=ara)

    elif nova == "DESCARTAT" and candidat.lead_id:
        res_l = await db.execute(select(SaasLead).where(SaasLead.id == candidat.lead_id))
        lead_existent = res_l.scalars().first()
        if lead_existent:
            lead_existent.estat_qualificacio = "DESCARTAT"
            lead_existent.updated_at = ara

        # Cancel·lar els esborranys de correu pendents al Calendari Comercial
        res_cal = await db.execute(
            select(SaasCorreuMissatge).where(
                SaasCorreuMissatge.lead_id == candidat.lead_id,
                SaasCorreuMissatge.estat_enviament.in_(("ESBORRANY_PROGRAMAT", "PENDENT_APROVACIO_AVUI")),
            )
        )
        for msg_cal in res_cal.scalars().all():
            msg_cal.estat_enviament = "CANCEL_LAT"

        # Tancar l'oportunitat associada com a PERDUT
        res_op = await db.execute(select(SaasOportunitat).where(SaasOportunitat.lead_id == candidat.lead_id))
        for op_item in res_op.scalars().all():
            op_item.etapa = "PERDUT"
            op_item.motiu_perdua = f"Descartat per correcció humana: {candidat.motiu_correccio_humana}"
            op_item.updated_at = ara

    # Enregistrar a saas_criteris_feedback per al Doble Bucle d'Aprenentatge
    tipus_apr = "CORRECCIO_DESCART" if nova == "DESCARTAT" else "CORRECCIO_SELECCIO"
    feedback = SaasCriteriFeedback(
        id=uuid.uuid4(),
        tipus_aprenentatge=tipus_apr,
        candidat_id=cid,
        lead_id=candidat.lead_id,
        vertical=candidat.vertical,
        nom_empresa=candidat.nom_empresa,
        web_url=candidat.web_url,
        resum_evidencies_o_requisits=f"Fonts: {candidat.fonts_investigades}. Operaris: {candidat.operaris_estimats}.",
        decisio_ia_original=decisio_anterior,
        decisio_humana_correcta=nova,
        explicacio_humana_o_rao_exit=payload.motiu_correccio_humana.strip(),
        es_replicable=False,
        actiu=True,
        created_at=ara,
    )
    db.add(feedback)
    await db.commit()

    return {
        "status": "OK",
        "candidat_id": str(cid),
        "nova_decisio": nova,
        "motiu_correccio_humana": candidat.motiu_correccio_humana,
        "missatge": f"Decisió corregida a '{nova}' i regla d'aprenentatge registrada.",
    }


@router.delete("/candidats/{candidat_id}", response_model=Dict[str, Any])
async def eliminar_candidat_cp(
    candidat_id: str,
    db: AsyncSession = Depends(get_db_with_tenant_context),
) -> Dict[str, Any]:
    """Elimina un candidat de prospecció del lot de Codi Postal i actualitza els comptadors de la tasca."""
    try:
        cid = uuid.UUID(candidat_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="ID de candidat invàlid.")

    res_c = await db.execute(select(SaasProspeccioCandidat).where(SaasProspeccioCandidat.id == cid))
    candidat = res_c.scalars().first()
    if not candidat:
        raise HTTPException(status_code=404, detail="Candidat no trobat.")

    nom_cand = candidat.nom_empresa
    decisio = candidat.decisio_humana or candidat.estat_decisio
    tasca_id = candidat.tasca_id

    # Desvincular feedback si en tenia
    res_fb = await db.execute(select(SaasCriteriFeedback).where(SaasCriteriFeedback.candidat_id == cid))
    for fb in res_fb.scalars().all():
        fb.candidat_id = None

    await db.delete(candidat)

    # Actualitzar comptadors de la tasca mare
    res_t = await db.execute(select(SaasProspeccioTasca).where(SaasProspeccioTasca.id == tasca_id))
    tasca = res_t.scalars().first()
    if tasca:
        tasca.total_trobats = max(0, tasca.total_trobats - 1)
        if decisio in ("SELECCIONAT", "SELECCIONAT_SENSE_GATEKEEPER"):
            tasca.total_seleccionats = max(0, tasca.total_seleccionats - 1)
        elif decisio in ("DESCARTAT", "ERROR_EXTRACCIO"):
            tasca.total_descartats = max(0, tasca.total_descartats - 1)
        elif decisio == "DUPLICAT":
            tasca.total_duplicats = max(0, tasca.total_duplicats - 1)

    await db.commit()
    return {"status": "OK", "missatge": f"Candidat '{nom_cand}' eliminat correctament."}


@router.post("/oportunitats/{oportunitat_id}/registrar-exit", response_model=Dict[str, Any])
async def registrar_exit_replicable(
    oportunitat_id: str,
    payload: RegistrarExitRequest,
    db: AsyncSession = Depends(get_db_with_tenant_context),
) -> Dict[str, Any]:
    """Registra un tancament GUANYAT amb la raó d'èxit per aprendre i buscar lookalikes (FR-012)."""
    try:
        op_id = uuid.UUID(oportunitat_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="ID d'oportunitat invàlid.")

    res_op = await db.execute(select(SaasOportunitat).where(SaasOportunitat.id == op_id))
    op = res_op.scalars().first()
    if not op:
        raise HTTPException(status_code=404, detail="Oportunitat no trobada.")

    ara = datetime.now(timezone.utc)
    op.etapa = "GUANYAT"
    op.probabilitat_percent = 100
    op.rao_tancament_exit = payload.rao_tancament_exit.strip()
    op.requisits_replicables = payload.requisits_replicables.strip() if payload.requisits_replicables else None
    op.es_replicable = payload.es_replicable
    op.updated_at = ara

    # Actualitzar lead associat
    res_l = await db.execute(select(SaasLead).where(SaasLead.id == op.lead_id))
    lead = res_l.scalars().first()
    if lead:
        lead.rao_tancament_exit = payload.rao_tancament_exit.strip()
        lead.es_tancament_replicable = payload.es_replicable
        lead.updated_at = ara

        # Desar al Doble Bucle d'Aprenentatge
        feedback = SaasCriteriFeedback(
            id=uuid.uuid4(),
            tipus_aprenentatge="TANCAMENT_EXIT_REPLICABLE",
            candidat_id=None,
            lead_id=lead.id,
            vertical=lead.vertical,
            nom_empresa=lead.nom_empresa,
            web_url=lead.web_url,
            resum_evidencies_o_requisits=payload.requisits_replicables
            or f"Empresa de {lead.vertical} amb {lead.operaris_estimats} operaris.",
            decisio_ia_original=None,
            decisio_humana_correcta="GUANYAT_REPLICABLE",
            explicacio_humana_o_rao_exit=payload.rao_tancament_exit.strip(),
            es_replicable=payload.es_replicable,
            actiu=True,
            created_at=ara,
        )
        db.add(feedback)

        act_win = SaasActivitatLead(
            id=uuid.uuid4(),
            lead_id=lead.id,
            tipus="ESTAT_CANVIAT",
            titol="🏆 Oportunitat tancada com a GUANYAT (Cas Replicable)",
            descripcio=f"Raó d'èxit: {payload.rao_tancament_exit.strip()}",
            autor_nom="Superadmin",
            created_at=ara,
        )
        db.add(act_win)

    await db.commit()
    return {
        "status": "OK",
        "oportunitat_id": str(op_id),
        "etapa": "GUANYAT",
        "rao_tancament_exit": op.rao_tancament_exit,
        "es_replicable": op.es_replicable,
        "missatge": "Tancament d'èxit registrat al Doble Bucle d'Aprenentatge per a Lookalikes.",
    }


@router.get("/criteris-feedback", response_model=List[Dict[str, Any]])
async def llistar_criteris_feedback(
    vertical: Optional[str] = None,
    tipus: Optional[str] = None,
    db: AsyncSession = Depends(get_db_with_tenant_context),
) -> List[Dict[str, Any]]:
    """Llista totes les regles d'aprenentatge (descarts justificats i tancaments replicables)."""
    stmt = (
        select(SaasCriteriFeedback)
        .where(SaasCriteriFeedback.actiu.is_(True))
        .order_by(desc(SaasCriteriFeedback.created_at))
    )
    if vertical:
        stmt = stmt.where(SaasCriteriFeedback.vertical == vertical)
    if tipus:
        stmt = stmt.where(SaasCriteriFeedback.tipus_aprenentatge == tipus)

    res = await db.execute(stmt)
    feedbacks = res.scalars().all()

    return [
        {
            "id": str(f.id),
            "tipus_aprenentatge": f.tipus_aprenentatge,
            "vertical": f.vertical,
            "nom_empresa": f.nom_empresa,
            "web_url": f.web_url,
            "resum_evidencies_o_requisits": f.resum_evidencies_o_requisits,
            "decisio_ia_original": f.decisio_ia_original,
            "decisio_humana_correcta": f.decisio_humana_correcta,
            "explicacio_humana_o_rao_exit": f.explicacio_humana_o_rao_exit,
            "es_replicable": f.es_replicable,
            "created_at": f.created_at.isoformat(),
        }
        for f in feedbacks
    ]


# ==============================================================================
# ENDPOINTS CALENDARI COMERCIAL INTEGRAT, CAMPANYES I CORREU BIDIRECCIONAL (T013)
# ==============================================================================

@router.get("/calendari", response_model=Dict[str, Any])
async def obtenir_esdeveniments_calendari(
    inici: Optional[date] = None,
    fi: Optional[date] = None,
    estat: Optional[str] = None,
    db: AsyncSession = Depends(get_db_with_tenant_context),
) -> Dict[str, Any]:
    """Retorna tots els esdeveniments del Calendari Comercial del CRM (FR-013, FR-014)."""
    stmt = (
        select(SaasCorreuMissatge, SaasLead)
        .join(SaasLead, SaasCorreuMissatge.lead_id == SaasLead.id)
        .order_by(SaasCorreuMissatge.data_programada.asc())
    )
    if inici:
        stmt = stmt.where(SaasCorreuMissatge.data_programada >= datetime.combine(inici, datetime.min.time(), tzinfo=timezone.utc))
    if fi:
        stmt = stmt.where(SaasCorreuMissatge.data_programada <= datetime.combine(fi, datetime.max.time(), tzinfo=timezone.utc))
    if estat:
        stmt = stmt.where(SaasCorreuMissatge.estat_enviament == estat)

    res = await db.execute(stmt)
    rows = res.all()
    ara = datetime.now(timezone.utc)

    items: List[Dict[str, Any]] = []
    pendents_avui = 0

    for msg, lead_item in rows:
        delta = (msg.data_programada - ara).total_seconds()
        es_avui = abs(delta) < 86400 and msg.data_programada.date() == ara.date()
        es_pendent = msg.estat_enviament == "ESBORRANY_PROGRAMAT" and msg.data_programada <= ara + timedelta(hours=12)

        if es_pendent:
            pendents_avui += 1

        items.append({
            "id": str(msg.id),
            "lead_id": str(lead_item.id),
            "nom_empresa": lead_item.nom_empresa,
            "vertical": lead_item.vertical,
            "nom_contacte": lead_item.nom_contacte,
            "destinatari": msg.destinatari,
            "telefon": lead_item.telefon,
            "tipus_item_calendari": msg.tipus_item_calendari,
            "pas_sequencia": msg.pas_sequencia,
            "tempo_dies_offset": msg.tempo_dies_offset,
            "data_programada": msg.data_programada.isoformat(),
            "direccio": msg.direccio,
            "estat_enviament": msg.estat_enviament,
            "estat_calendari": "PENDENT_APROVACIO_AVUI" if es_pendent else msg.estat_enviament,
            "assumpte": msg.assumpte,
            "cos_text": msg.cos_text,
            "message_id": msg.message_id,
            "in_reply_to": msg.in_reply_to,
            "intencio_ia": msg.intencio_ia,
            "es_avui": es_avui,
            "pendent_aprovacio": es_pendent,
            "sent_at": msg.sent_at.isoformat() if msg.sent_at else None,
        })

    # Incloure també els venciments de Demos de 7 dies (FR-014, T013, T015) si no tenen item explícit
    if not estat:
        leads_amb_venciment_explicit = {
            str(msg.lead_id) for msg, _ in rows if msg.tipus_item_calendari == "VENCIMENT_DEMO"
        }
        stmt_demos = select(SaasLead).where(SaasLead.data_fi_demo.is_not(None))
        if inici:
            stmt_demos = stmt_demos.where(SaasLead.data_fi_demo >= datetime.combine(inici, datetime.min.time(), tzinfo=timezone.utc))
        if fi:
            stmt_demos = stmt_demos.where(SaasLead.data_fi_demo <= datetime.combine(fi, datetime.max.time(), tzinfo=timezone.utc))
        res_demos = await db.execute(stmt_demos)
        for ld in res_demos.scalars().all():
            if not ld.data_fi_demo or str(ld.id) in leads_amb_venciment_explicit:
                continue
            es_avui_demo = ld.data_fi_demo.date() == ara.date()
            items.append({
                "id": f"demo-exp-{ld.id}",
                "lead_id": str(ld.id),
                "nom_empresa": ld.nom_empresa,
                "vertical": ld.vertical,
                "nom_contacte": ld.nom_contacte,
                "destinatari": ld.email,
                "telefon": ld.telefon,
                "tipus_item_calendari": "VENCIMENT_DEMO",
                "pas_sequencia": None,
                "tempo_dies_offset": ld.dies_demo_durada or 7,
                "data_programada": ld.data_fi_demo.isoformat(),
                "direccio": "INTERN_CALENDARI",
                "estat_enviament": "PROGRAMAT" if ld.data_fi_demo > ara else "EXPIRAT",
                "estat_calendari": "VENCIMENT_AVUI" if es_avui_demo else ("PROGRAMAT" if ld.data_fi_demo > ara else "EXPIRAT"),
                "assumpte": f"Venciment Demo {ld.dies_demo_durada or 7} Dies — {ld.nom_empresa}",
                "cos_text": f"L'entorn de prova de {ld.nom_empresa} ({ld.vertical}) finalitza el període de {ld.dies_demo_durada or 7} dies.",
                "message_id": None,
                "in_reply_to": None,
                "intencio_ia": None,
                "es_avui": es_avui_demo,
                "pendent_aprovacio": False,
                "sent_at": None,
            })

    items.sort(key=lambda x: x["data_programada"])

    return {
        "total_esdeveniments": len(items),
        "pendents_aprovacio_avui": pendents_avui,
        "items": items,
    }


@router.post("/calendari/esdeveniments", response_model=Dict[str, Any], status_code=status.HTTP_201_CREATED)
async def crear_esdeveniment_calendari(
    payload: CalendariEsdevenimentCreate,
    db: AsyncSession = Depends(get_db_with_tenant_context),
) -> Dict[str, Any]:
    """Crea manualment un esdeveniment o seguiment al Calendari Comercial vinculat a un lead."""
    try:
        lid = uuid.UUID(payload.lead_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="ID de lead invàlid.")

    res_l = await db.execute(select(SaasLead).where(SaasLead.id == lid))
    lead = res_l.scalars().first()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead no trobat.")

    ara = datetime.now(timezone.utc)
    ev_id = uuid.uuid4()
    msg = SaasCorreuMissatge(
        id=ev_id,
        lead_id=lid,
        tipus_item_calendari=payload.tipus,
        pas_sequencia=None,
        tempo_dies_offset=0,
        data_programada=payload.data_programada,
        direccio="INTERN_CALENDARI",
        estat_enviament="ESBORRANY_PROGRAMAT",
        remitent=settings.SUPERADMIN_OUTREACH_EMAIL or "tecnic@sevalor.net",
        destinatari=lead.email,
        assumpte=payload.titol.strip(),
        cos_text=payload.descripcio or "",
        message_id=f"<{uuid.uuid4().hex}@sevalor.net>",
        created_at=ara,
    )
    db.add(msg)
    await db.commit()

    return {"status": "OK", "esdeveniment_id": str(ev_id), "missatge": "Esdeveniment afegit al Calendari Comercial."}


@router.put("/correus/{correu_id}/esborrany", response_model=Dict[str, Any])
async def editar_esborrany_correu(
    correu_id: str,
    payload: EditarEsborranyRequest,
    db: AsyncSession = Depends(get_db_with_tenant_context),
) -> Dict[str, Any]:
    """Edita l'assumpte, el cos o la data d'un correu programat al Calendari."""
    try:
        mid = uuid.UUID(correu_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="ID invàlid.")

    res_m = await db.execute(select(SaasCorreuMissatge).where(SaasCorreuMissatge.id == mid))
    msg = res_m.scalars().first()
    if not msg:
        raise HTTPException(status_code=404, detail="Missatge no trobat.")

    if payload.assumpte is not None:
        msg.assumpte = payload.assumpte.strip()
    if payload.cos_text is not None:
        msg.cos_text = payload.cos_text.strip()
    if payload.data_programada is not None:
        msg.data_programada = payload.data_programada

    await db.commit()
    return {"status": "OK", "correu_id": str(mid), "missatge": "Esborrany actualitzat correctament."}


@router.post("/correus/{correu_id}/enviar", response_model=Dict[str, Any])
async def aprovar_enviar_correu_hitl(
    correu_id: str,
    db: AsyncSession = Depends(get_db_with_tenant_context),
) -> Dict[str, Any]:
    """Acció HITL: Valida i envia el correu programat des de tecnic@sevalor.net (FR-015, FR-017)."""
    try:
        mid = uuid.UUID(correu_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="ID invàlid.")

    try:
        correu = await aprovar_i_enviar_correu_calendari(correu_id=mid, db=db)
    except ValueError as val_err:
        raise HTTPException(status_code=400, detail=str(val_err))
    except PermissionError as perm_err:
        raise HTTPException(status_code=403, detail=str(perm_err))

    return {
        "status": "OK",
        "correu_id": str(correu.id),
        "estat_enviament": correu.estat_enviament,
        "sent_at": correu.sent_at.isoformat() if correu.sent_at else None,
        "missatge": f"Correu enviat correctament a '{correu.destinatari}'.",
    }


@router.get("/leads/{lead_id}/correus", response_model=List[Dict[str, Any]])
async def obtenir_correus_lead(
    lead_id: str,
    db: AsyncSession = Depends(get_db_with_tenant_context),
) -> List[Dict[str, Any]]:
    """Retorna la campanya i tot el fil de correus (OUTBOUND i INBOUND) d'un lead."""
    try:
        lid = uuid.UUID(lead_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="ID invàlid.")

    stmt = select(SaasCorreuMissatge).where(SaasCorreuMissatge.lead_id == lid).order_by(SaasCorreuMissatge.created_at.asc())
    res = await db.execute(stmt)
    missatges = res.scalars().all()

    return [
        {
            "id": str(m.id),
            "tipus_item_calendari": m.tipus_item_calendari,
            "pas_sequencia": m.pas_sequencia,
            "tempo_dies_offset": m.tempo_dies_offset,
            "data_programada": m.data_programada.isoformat(),
            "direccio": m.direccio,
            "estat_enviament": m.estat_enviament,
            "remitent": m.remitent,
            "destinatari": m.destinatari,
            "assumpte": m.assumpte,
            "cos_text": m.cos_text,
            "message_id": m.message_id,
            "in_reply_to": m.in_reply_to,
            "intencio_ia": m.intencio_ia,
            "sent_at": m.sent_at.isoformat() if m.sent_at else None,
            "created_at": m.created_at.isoformat(),
        }
        for m in missatges
    ]


@router.post("/leads/{lead_id}/validar-mx", response_model=Dict[str, Any])
async def validar_mx_lead(
    lead_id: str,
    db: AsyncSession = Depends(get_db_with_tenant_context),
) -> Dict[str, Any]:
    """Revalida els registres DNS MX per al correu d'un lead en viu."""
    try:
        lid = uuid.UUID(lead_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="ID invàlid.")

    res_l = await db.execute(select(SaasLead).where(SaasLead.id == lid))
    lead = res_l.scalars().first()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead no trobat.")

    es_valid, motiu = await validar_email_mx(lead.email, db=db)
    lead.mx_validat = es_valid
    lead.updated_at = datetime.now(timezone.utc)
    await db.commit()

    return {
        "status": "OK",
        "email": lead.email,
        "mx_validat": es_valid,
        "estat_dns": motiu,
    }


@router.post("/correu/sincronitzar-inbound", response_model=Dict[str, Any])
async def sincronitzar_correu_inbound(
    payload: Optional[SincronitzarInboundRequest] = None,
    db: AsyncSession = Depends(get_db_with_tenant_context),
) -> Dict[str, Any]:
    """Processa un missatge entrant o executa la sincronització IMAP de Stalwart."""
    if payload and payload.remitent and payload.cos_text:
        msg = await processar_resposta_inbound(
            remitent=payload.remitent,
            assumpte=payload.assumpte or "Re: Contacte",
            cos_text=payload.cos_text,
            in_reply_to=payload.in_reply_to,
            db=db,
        )
        return {
            "status": "OK",
            "mode": "WEBHOOK_DIRECTE",
            "message_id": msg.message_id,
            "intencio_ia": msg.intencio_ia,
            "lead_id": str(msg.lead_id),
        }

    # Sincronització IMAP
    processats = await sincronitzar_bustia_imap_stalwart(db=db)
    return {
        "status": "OK",
        "mode": "SINCRONITZACIO_IMAP",
        "total_processats": len(processats),
        "missatges": processats,
    }


@router.get("/exclusio-rgpd", response_model=List[Dict[str, Any]])
async def llistar_exclusio_rgpd(
    db: AsyncSession = Depends(get_db_with_tenant_context),
) -> List[Dict[str, Any]]:
    """Retorna la llista d'exclusió RGPD/LSSI."""
    stmt = select(SaasExclusioRgpd).order_by(desc(SaasExclusioRgpd.created_at)).limit(200)
    res = await db.execute(stmt)
    items = res.scalars().all()
    return [
        {
            "id": str(item.id),
            "email": item.email,
            "domini": item.domini,
            "cif": item.cif,
            "motiu": item.motiu,
            "created_at": item.created_at.isoformat(),
        }
        for item in items
    ]


@router.post("/exclusio-rgpd", response_model=Dict[str, Any], status_code=status.HTTP_201_CREATED)
async def afegir_exclusio_rgpd(
    payload: ExclusioRgpdCreate,
    db: AsyncSession = Depends(get_db_with_tenant_context),
) -> Dict[str, Any]:
    """Afegeix manualment un domini o correu a la llista d'exclusió RGPD/LSSI."""
    dom = normalitzar_domini(payload.domini)
    ara = datetime.now(timezone.utc)

    # Comprovar si ja existeix
    stmt = select(SaasExclusioRgpd).where(SaasExclusioRgpd.domini == dom)
    if payload.email:
        stmt = stmt.where(SaasExclusioRgpd.email == payload.email.strip().lower())
    res = await db.execute(stmt)
    if res.scalars().first():
        return {"status": "OK", "missatge": "El registre ja existia a la llista d'exclusió."}

    item = SaasExclusioRgpd(
        id=uuid.uuid4(),
        email=payload.email.strip().lower() if payload.email else None,
        domini=dom,
        cif=payload.cif.strip().upper() if payload.cif else None,
        motiu=payload.motiu.strip(),
        created_at=ara,
    )
    db.add(item)
    await db.commit()

    return {"status": "OK", "id": str(item.id), "missatge": f"Domini '{dom}' afegit a la llista d'exclusió."}

