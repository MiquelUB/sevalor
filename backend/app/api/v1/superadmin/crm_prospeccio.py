"""Router CRM Prospecció, Leads, Pipeline Kanban de 7 dies i Demo autònoma."""

import logging
import re
import uuid
from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

import bcrypt
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.db import get_db_with_tenant_context
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
    SaasLead,
    SaasOportunitat,
    Usuari,
    Vehicle,
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
    vertical: str = Field("CampoPro", max_length=100)
    origen: str = Field("WEB", max_length=50)
    operaris_estimats: int = Field(5, ge=1, le=500)
    notes: Optional[str] = None
    crear_oportunitat_inicial: bool = True
    valor_mensual_estimat: float = Field(0.0, ge=0.0)


class LeadUpdate(BaseModel):
    nom_empresa: Optional[str] = Field(None, max_length=150)
    nom_contacte: Optional[str] = Field(None, max_length=100)
    email: Optional[str] = Field(None, max_length=150)
    telefon: Optional[str] = Field(None, max_length=30)
    vertical: Optional[str] = Field(None, max_length=100)
    origen: Optional[str] = Field(None, max_length=50)
    estat_qualificacio: Optional[str] = Field(None, max_length=50)
    operaris_estimats: Optional[int] = Field(None, ge=1, le=500)
    notes: Optional[str] = None


class OportunitatCreate(BaseModel):
    lead_id: str
    titol: str = Field(..., min_length=3, max_length=200)
    etapa: str = Field("PROSPECCIO", max_length=50)
    valor_mensual_estimat: float = Field(0.0, ge=0.0)
    valor_ia_setup: float = Field(0.0, ge=0.0)
    probabilitat_percent: int = Field(20, ge=0, le=100)
    data_tancament_prevista: Optional[date] = None


class OportunitatUpdate(BaseModel):
    titol: Optional[str] = Field(None, max_length=200)
    etapa: Optional[str] = Field(None, max_length=50)
    valor_mensual_estimat: Optional[float] = Field(None, ge=0.0)
    valor_ia_setup: Optional[float] = Field(None, ge=0.0)
    probabilitat_percent: Optional[int] = Field(None, ge=0, le=100)
    data_tancament_prevista: Optional[date] = None
    motiu_perdua: Optional[str] = Field(None, max_length=255)


class ActivitatCreate(BaseModel):
    tipus: str = Field("NOTA", max_length=30)
    titol: str = Field(..., min_length=2, max_length=200)
    descripcio: Optional[str] = None
    autor_nom: Optional[str] = "Superadmin"


class ActivarDemoRequest(BaseModel):
    vertical: Optional[str] = None  # Si és None, agafa la del lead
    durada_dies: int = Field(7, ge=1, le=30)
    recrear: bool = False


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

    lead.updated_at = datetime.now(timezone.utc)
    await db.commit()

    return {"status": "OK", "missatge": "Lead actualitzat correctament."}


@router.delete("/leads/{lead_id}", response_model=Dict[str, Any])
async def eliminar_lead(
    lead_id: str,
    db: AsyncSession = Depends(get_db_with_tenant_context),
) -> Dict[str, Any]:
    """Elimina un lead i les seves oportunitats i activitats en cascada."""
    try:
        lid = uuid.UUID(lead_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="ID invàlid.")

    res_l = await db.execute(select(SaasLead).where(SaasLead.id == lid))
    lead = res_l.scalars().first()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead no trobat.")

    await db.delete(lead)
    await db.commit()
    return {"status": "OK", "missatge": f"Lead '{lead.nom_empresa}' eliminat correctament."}


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
            "created_at": op.created_at.isoformat(),
        })

    return {
        "etapes": ETAPES_PIPELINE,
        "totals_mrr": totals_mrr,
        "columnes": columnes,
    }


@router.patch("/oportunitats/{oportunitat_id}/etapa", response_model=Dict[str, Any])
async def canviar_etapa_oportunitat(
    oportunitat_id: str,
    payload: OportunitatUpdate,
    db: AsyncSession = Depends(get_db_with_tenant_context),
) -> Dict[str, Any]:
    """Mou una oportunitat d'etapa al Kanban (Drag & Drop) i afegeix traça al timeline."""
    try:
        op_id = uuid.UUID(oportunitat_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="ID d'oportunitat invàlid.")

    res_op = await db.execute(select(SaasOportunitat).where(SaasOportunitat.id == op_id))
    op = res_op.scalars().first()
    if not op:
        raise HTTPException(status_code=404, detail="Oportunitat no trobada.")

    etapa_anterior = op.etapa
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
    if payload.motiu_perdua is not None:
        op.motiu_perdua = payload.motiu_perdua

    ara = datetime.now(timezone.utc)
    op.updated_at = ara

    # Registre al timeline del lead
    if payload.etapa and payload.etapa != etapa_anterior:
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

    await db.commit()
    return {"status": "OK", "nova_etapa": op.etapa}


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
