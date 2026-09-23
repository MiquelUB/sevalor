import uuid

import jwt
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.main import app
from app.models.models import Empresa, Usuari
from app.workers.tasks import crear_directoris_sobirans


@pytest.fixture
def superadmin_headers():
    token_payload = {
        "sub": str(uuid.uuid4()),
        "rol": "SUPERADMIN",
        "empresa_id": str(uuid.uuid4()),
    }
    token = jwt.encode(token_payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_superadmin_onboarding_nou_tenant(superadmin_headers, admin_session: AsyncSession):
    """Verifica el provisionament real d'un tenant via POST /superadmin/tenants/onboarding."""
    subdomini_test = f"tenant-{uuid.uuid4().hex[:8]}"
    nif_test = f"B{uuid.uuid4().hex[:8].upper()}"
    boss_email = f"boss.{subdomini_test}@sevalor-test.cat"

    payload = {
        "rao_social": "Serveis Agrícoles del Segrià S.L.",
        "nif": nif_test,
        "subdomini": subdomini_test,
        "vertical": "SEVALOR",
        "pla_subscripcio": "PRO",
        "quota_disc_gb": 50,
        "boss_nif": "47123456Z",
        "boss_nom": "Jordi",
        "boss_cognoms": "Puig",
        "boss_email": boss_email,
        "boss_telefon": "+34611223344",
        "feature_flags": {
            "copilot_ia": True,
            "flota_avancada": True,
            "planols_tecnics": True,
            "telegram_bot": True,
        }
    }

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test/api/v1") as client:
        res = await client.post("/superadmin/tenants/onboarding", json=payload, headers=superadmin_headers)
        assert res.status_code == 201
        data = res.json()
        assert data["status"] == "CREATED"
        tenant_info = data["tenant"]
        assert tenant_info["subdomini"] == subdomini_test
        assert tenant_info["pla_subscripcio"] == "PRO"
        assert "enllac_activacio_2fa" in tenant_info

        # Verificar persistència real a PostgreSQL
        emp_res = await admin_session.execute(select(Empresa).where(Empresa.subdomini == subdomini_test))
        empresa = emp_res.scalars().first()
        assert empresa is not None
        assert empresa.nom == "Serveis Agrícoles del Segrià S.L."
        assert empresa.estat_pagament == "TRIAL"
        assert empresa.vertical == "SEVALOR"

        # Verificar creació de l'usuari Boss
        boss_res = await admin_session.execute(select(Usuari).where(Usuari.email == boss_email))
        boss = boss_res.scalars().first()
        assert boss is not None
        assert boss.rol == "BOSS"
        assert boss.estat == "ACTIU"
        assert boss.empresa_id == empresa.id


@pytest.mark.asyncio
async def test_superadmin_llistar_tenants(superadmin_headers):
    """Verifica el llistat real de tenants a GET /superadmin/tenants."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test/api/v1") as client:
        res = await client.get("/superadmin/tenants", headers=superadmin_headers)
        assert res.status_code == 200
        tenants = res.json()
        assert isinstance(tenants, list)
        assert len(tenants) >= 1
        primari = tenants[0]
        assert "id" in primari
        assert "rao_social" in primari
        assert "subdomini" in primari
        assert "estat" in primari


@pytest.mark.asyncio
async def test_superadmin_telemetria_kpis(superadmin_headers):
    """Verifica l'endpoint de telemetria i salut del sistema a /superadmin/telemetria/kpis."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test/api/v1") as client:
        res = await client.get("/superadmin/telemetria/kpis", headers=superadmin_headers)
        assert res.status_code == 200
        kpis = res.json()
        assert "uptime_percent" in kpis
        assert "microservices" in kpis
        assert "concurrency" in kpis
        assert "celery_queues" in kpis
        assert "cpu_ia_telemetry" in kpis
        assert "tenants" in kpis


def test_workers_sobirans_directory_structure():
    """Verifica que la funció de directoris sobirans genera l'arbre UE estricte (RF-08)."""
    empresa_id = str(uuid.uuid4())
    dirs = crear_directoris_sobirans(empresa_id)
    assert len(dirs) == 6
    assert any(d.endswith(empresa_id) for d in dirs)
    assert any(d.endswith("/docs") for d in dirs)
    assert any(d.endswith("/albarans") for d in dirs)
    assert any(d.endswith("/planols") for d in dirs)
    assert any(d.endswith("/incidencies") for d in dirs)
    assert any(d.endswith("/backups") for d in dirs)
