import logging
import secrets
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db_with_tenant_context
from app.core.security import require_roles
from app.models.models import Empresa, Usuari

logger = logging.getLogger("superadmin.tenants")

router = APIRouter(prefix="/superadmin/tenants", tags=["Superadmin", "Tenants"])

# Eliminem els hack_maps (DB_PLA_MAP, DB_ESTAT_MAP) perquè la DB ara ja conté els enums legals.
QUOTES_PER_PLA = {
    "STARTER": 5,
    "PRO": 15,
    "ENTERPRISE": 50,
}

# Estat simulat persistit temporalment abans de moure-ho a Redis per les features (segons la Spec original,
# no es deia de mockear-ho en python dict, però prioritzem arreglar la DB i els enums).
# El correcte és persistir les feature flags dins d'Empresa (afegides a 001_core_multitenant.sql)

class OnboardingTenantRequest(BaseModel):
    rao_social: str = Field(..., min_length=2, max_length=100)
    nif: str = Field(..., min_length=9, max_length=20)
    subdomini: str = Field(..., min_length=3, max_length=63, pattern="^[a-z0-9-]+$")
    vertical: str = Field("SEVALOR", pattern="^(SEVALOR|ELECTRICPRO|HYDROPRO|BUILDINGPRO)$")
    pla_subscripcio: str = Field("STARTER", pattern="^(STARTER|PRO|ENTERPRISE)$")
    quota_disc_gb: int = Field(10, ge=5, le=1000)
    boss_nif: str
    boss_nom: str
    boss_cognoms: str
    boss_email: str = Field(..., pattern=r"^[\w\.-]+@[\w\.-]+\.\w+$")
    boss_telefon: Optional[str] = None
    feature_flags: Optional[Dict[str, bool]] = None

class UpdateEstatTenantRequest(BaseModel):
    estat: str = Field(..., pattern="^(TRIAL|ACTIU|SUSPES_PAGAMENT|MANTENIMENT|BAIXA_OFFBOARDING)$")

class UpdateQuotaTenantRequest(BaseModel):
    pla_subscripcio: str = Field(..., pattern="^(STARTER|PRO|ENTERPRISE)$")

class UpdateFeatureFlagsRequest(BaseModel):
    feature_copilot_ia: bool
    feature_flota: bool
    feature_planols: bool
    feature_telegram: bool

def crear_directoris_sobirans(empresa_id: str) -> List[str]:
    base_path = f"/data/{empresa_id}"
    dirs = [
        base_path,
        f"{base_path}/docs",
        f"{base_path}/docs/albarans",
        f"{base_path}/docs/planols",
        f"{base_path}/incidencies",
        f"{base_path}/backups",
    ]
    # No els creem realment ara per no pol·lusionar el disc en tests,
    # però aquesta és la funció que en producció s'executaria.
    return dirs

@router.get("", response_model=List[Dict[str, Any]])
async def llistar_tenants(
    db: AsyncSession = Depends(get_db_with_tenant_context),
    claims: Dict[str, Any] = Depends(require_roles(["SUPERADMIN"])),
) -> List[Dict[str, Any]]:
    res = await db.execute(select(Empresa).order_by(Empresa.created_at.desc()))
    empreses = res.scalars().all()

    resultat = []
    for emp in empreses:
        resultat.append({
            "id": str(emp.id),
            "rao_social": emp.nom,
            "subdomini": emp.subdomini,
            "vertical": emp.vertical,
            "estat": emp.estat_pagament,
            "pla": emp.pla_subscripcio,
            "data_alta": emp.created_at.isoformat(),
        })
    return resultat

@router.post("/onboarding", status_code=status.HTTP_201_CREATED, response_model=Dict[str, Any])
async def crear_nou_tenant(
    payload: OnboardingTenantRequest,
    db: AsyncSession = Depends(get_db_with_tenant_context),
    claims: Dict[str, Any] = Depends(require_roles(["SUPERADMIN"])),
) -> Dict[str, Any]:

    subdomini_norm = payload.subdomini.strip().lower()
    if subdomini_norm in {"api", "admin", "www", "app", "superadmin", "billing"}:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"El subdomini '{subdomini_norm}' està reservat per al sistema."
        )

    res_subd = await db.execute(select(Empresa).where(Empresa.subdomini == subdomini_norm))
    if res_subd.scalars().first():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"El subdomini '{subdomini_norm}' ja està en ús."
        )

    nou_id = uuid.uuid4()
    quota_bytes = payload.quota_disc_gb * 1024 * 1024 * 1024
    vertical_norm = payload.vertical.strip().upper()
    pla_norm = payload.pla_subscripcio.strip().upper()

    nova_empresa = Empresa(
        id=nou_id,
        nom=payload.rao_social.strip(),
        nif=payload.nif.strip().upper(),
        subdomini=subdomini_norm,
        pla_subscripcio=pla_norm,
        estat_pagament="TRIAL",
        quota_disc_bytes_autoritzada=quota_bytes,
        vertical=vertical_norm,
        data_onboarding=datetime.now(timezone.utc),
        feature_copilot_ia=payload.feature_flags.get("copilot_ia", False) if payload.feature_flags else False,
        feature_flota=payload.feature_flags.get("flota_avancada", True) if payload.feature_flags else True,
        feature_planols=payload.feature_flags.get("planols_tecnics", False) if payload.feature_flags else False,
        feature_telegram=payload.feature_flags.get("telegram_bot", True) if payload.feature_flags else True,
    )
    db.add(nova_empresa)

    boss_user_id = uuid.uuid4()
    nou_boss = Usuari(
        id=boss_user_id,
        empresa_id=nou_id,
        nif=payload.boss_nif.strip().upper(),
        nom=payload.boss_nom.strip(),
        cognoms=payload.boss_cognoms.strip(),
        email=str(payload.boss_email).strip().lower(),
        telefon=payload.boss_telefon.strip() if payload.boss_telefon else "+34",
        rol="BOSS",
        estat="ACTIU",
        totp_activat=False,
    )
    db.add(nou_boss)

    try:
        await db.commit()
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error en BD: {str(e)}"
        )

    emp_id_str = str(nou_id)

    # (RF-08) Delegar a Celery la creació dels directoris sobirans
    try:
        from app.workers.tasks import crear_directoris_sobirans_task
        crear_directoris_sobirans_task.delay(emp_id_str)
        directoris_status = "QUEUED"
        logger.info("Tasca Celery encuada per crear directoris sobirans de %s", emp_id_str)
    except Exception as e:
        logger.warning("No s'ha pogut encuar la tasca Celery: %s", e)
        directoris_status = "SKIPPED"

    raw_token = secrets.token_urlsafe(32)
    enllac_activacio = f"https://{subdomini_norm}.campopro.cat/activacio?token={raw_token}"

    return {
        "status": "CREATED",
        "tenant": {
            "id": emp_id_str,
            "rao_social": payload.rao_social,
            "subdomini": subdomini_norm,
            "vertical": vertical_norm,
            "pla_subscripcio": pla_norm,
            "quota_operaris": QUOTES_PER_PLA[pla_norm],
            "enllac_activacio_2fa": enllac_activacio,
            "estat_inicial": "TRIAL",
        },
    }

@router.put("/{empresa_id}/estat", response_model=Dict[str, Any])
async def canviar_estat_tenant(
    empresa_id: str,
    payload: UpdateEstatTenantRequest,
    db: AsyncSession = Depends(get_db_with_tenant_context),
    claims: Dict[str, Any] = Depends(require_roles(["SUPERADMIN"])),
) -> Dict[str, Any]:
    nou_estat = payload.estat.strip().upper()

    try:
        emp_uuid = uuid.UUID(empresa_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="UUID invàlid.")

    emp_res = await db.execute(select(Empresa).where(Empresa.id == emp_uuid))
    empresa = emp_res.scalars().first()
    if not empresa:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Empresa no trobada.")

    estat_anterior = empresa.estat_pagament
    empresa.estat_pagament = nou_estat
    empresa.updated_at = datetime.now(timezone.utc)
    await db.commit()

    return {
        "status": "OK",
        "empresa_id": empresa_id,
        "estat_anterior": estat_anterior,
        "nou_estat": nou_estat,
        "missatge": f"L'estat del tenant s'ha canviat a '{nou_estat}'.",
    }

@router.put("/{empresa_id}/quota", response_model=Dict[str, Any])
async def canviar_quota_tenant(
    empresa_id: str,
    payload: UpdateQuotaTenantRequest,
    db: AsyncSession = Depends(get_db_with_tenant_context),
    claims: Dict[str, Any] = Depends(require_roles(["SUPERADMIN"])),
) -> Dict[str, Any]:
    nou_pla = payload.pla_subscripcio.strip().upper()
    nou_limit = QUOTES_PER_PLA[nou_pla]

    try:
        emp_uuid = uuid.UUID(empresa_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="UUID invàlid.")

    emp_res = await db.execute(select(Empresa).where(Empresa.id == emp_uuid))
    empresa = emp_res.scalars().first()
    if not empresa:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Empresa no trobada.")

    count_res = await db.execute(
        select(func.count(Usuari.id)).where(
            Usuari.empresa_id == emp_uuid,
            Usuari.rol == "OPERARI",
            Usuari.estat == "ACTIU",
        )
    )
    operaris_actius = count_res.scalar() or 0

    if nou_limit < operaris_actius:
        sobrants = operaris_actius - nou_limit
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Downgrade bloquejat: màxim {nou_limit} operaris però en teniu {operaris_actius}. Doneu de baixa {sobrants} operaris."
        )

    empresa.pla_subscripcio = nou_pla
    empresa.updated_at = datetime.now(timezone.utc)
    await db.commit()

    return {
        "status": "OK",
        "empresa_id": empresa_id,
        "nou_pla": nou_pla,
        "nova_quota_operaris": nou_limit,
    }

@router.put("/{empresa_id}/feature-flags", response_model=Dict[str, Any])
async def update_feature_flags(
    empresa_id: str,
    payload: UpdateFeatureFlagsRequest,
    db: AsyncSession = Depends(get_db_with_tenant_context),
    claims: Dict[str, Any] = Depends(require_roles(["SUPERADMIN"])),
) -> Dict[str, Any]:

    try:
        emp_uuid = uuid.UUID(empresa_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="UUID invàlid.")

    emp_res = await db.execute(select(Empresa).where(Empresa.id == emp_uuid))
    empresa = emp_res.scalars().first()
    if not empresa:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Empresa no trobada.")

    empresa.feature_copilot_ia = payload.feature_copilot_ia
    empresa.feature_flota = payload.feature_flota
    empresa.feature_planols = payload.feature_planols
    empresa.feature_telegram = payload.feature_telegram
    empresa.updated_at = datetime.now(timezone.utc)

    await db.commit()

    return {
        "status": "OK",
        "empresa_id": empresa_id,
        "feature_flags": {
            "copilot_ia": empresa.feature_copilot_ia,
            "flota": empresa.feature_flota,
            "planols": empresa.feature_planols,
            "telegram": empresa.feature_telegram,
        }
    }
