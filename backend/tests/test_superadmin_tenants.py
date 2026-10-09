import uuid
from datetime import datetime, timedelta, timezone

import jwt
import pytest
from httpx import ASGITransport, AsyncClient

from app.core.config import settings
from app.main import app


@pytest.fixture
def superadmin_token():
    payload = {
        "sub": "00000000-0000-0000-0000-000000000000",
        "rol": "SUPERADMIN",
        "empresa_id": None,
        "exp": datetime.now(timezone.utc) + timedelta(minutes=15),
        "totp_activat": True,
        "ip_allowlist": ["testclient", "127.0.0.1", "localhost", "*"]
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)

@pytest.fixture
def headers(superadmin_token):
    return {"Authorization": f"Bearer {superadmin_token}"}

@pytest.mark.asyncio
async def test_onboarding_tenant_success(headers):
    payload = {
        "rao_social": "Test Empresa S.L.",
        "nif": "B" + str(uuid.uuid4())[:8].upper(),
        "subdomini": "testempresa-" + str(uuid.uuid4())[:8],
        "vertical": "SEVALOR",
        "pla_subscripcio": "STARTER",
        "quota_disc_gb": 20,
        "boss_nif": "43211234A",
        "boss_nom": "Jordi",
        "boss_cognoms": "Puig",
        "boss_email": "jordi@testempresa.cat",
        "boss_telefon": "+34600100200",
        "feature_flags": {
            "copilot_ia": False,
            "flota_avancada": True,
            "planols_tecnics": False,
            "telegram_bot": True
        }
    }
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.post("/api/v1/superadmin/tenants/onboarding", json=payload, headers=headers)
        assert response.status_code == 201, f"Expected 201 but got {response.status_code}: {response.text}"
        data = response.json()
        assert data["status"] == "CREATED"
        assert data["tenant"]["pla_subscripcio"] == "STARTER"
        assert data["tenant"]["estat_inicial"] == "TRIAL"

@pytest.mark.asyncio
async def test_onboarding_requires_superadmin():
    payload_jwt = {
        "sub": "11111111-1111-1111-1111-111111111111",
        "rol": "OPERARI",
        "empresa_id": "22222222-2222-2222-2222-222222222222",
        "exp": datetime.now(timezone.utc) + timedelta(minutes=15)
    }
    token = jwt.encode(payload_jwt, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    headers = {"Authorization": f"Bearer {token}"}

    payload = {
        "rao_social": "Test Fals",
        "nif": "B00000000",
        "subdomini": "testfals",
        "vertical": "SEVALOR",
        "pla_subscripcio": "STARTER",
        "quota_disc_gb": 10,
        "boss_nif": "12345678Z",
        "boss_nom": "Hacker",
        "boss_cognoms": "Dolent",
        "boss_email": "hacker@test.com"
    }
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.post("/api/v1/superadmin/tenants/onboarding", json=payload, headers=headers)
        assert response.status_code == 403, "L'API no ha bloquejat a l'operari! Greu fallada de seguretat."

@pytest.mark.asyncio
async def test_estat_transicions_correctes(headers):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        res_list = await ac.get("/api/v1/superadmin/tenants", headers=headers)
        assert res_list.status_code == 200
        llista = res_list.json()
        assert len(llista) > 0
        empresa_id = llista[0]["id"]

        payload = {"estat": "SUSPES_PAGAMENT"}
        res_update = await ac.put(f"/api/v1/superadmin/tenants/{empresa_id}/estat", json=payload, headers=headers)
        assert res_update.status_code == 200, f"Expected 200 but got {res_update.status_code}: {res_update.text}"
        data = res_update.json()
        assert data["nou_estat"] == "SUSPES_PAGAMENT"


@pytest.mark.asyncio
async def test_obtenir_tenant_individual(headers):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        res_list = await ac.get("/api/v1/superadmin/tenants", headers=headers)
        assert res_list.status_code == 200
        llista = res_list.json()
        assert len(llista) > 0
        empresa_id = llista[0]["id"]

        res_detail = await ac.get(f"/api/v1/superadmin/tenants/{empresa_id}", headers=headers)
        assert res_detail.status_code == 200
        data = res_detail.json()
        assert data["id"] == empresa_id
        assert "quota_operaris" in data
        assert "operaris_actius" in data
        assert "features" in data
        assert "pla_subscripcio" in data
        assert "estat_pagament" in data


@pytest.mark.asyncio
async def test_seguretat_status_endpoint(headers):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        res = await ac.get("/api/v1/superadmin/tenants/seguretat/status", headers=headers)
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "SECURE"
        assert data["ip_allowlist_enforced"] is True
        assert data["totp_enforced"] is True
        assert "rls_multi_tenant" in data


@pytest.mark.asyncio
async def test_auditoria_certificats_endpoint(headers):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        res = await ac.get("/api/v1/superadmin/tenants/auditoria/certificats", headers=headers)
        assert res.status_code == 200
        data = res.json()
        assert isinstance(data, list)


@pytest.mark.asyncio
async def test_onboarding_tenant_amb_domini_propi(headers):
    unique_suffix = str(uuid.uuid4())[:8]
    subdomini = f"soler-{unique_suffix}"
    domini_custom = f"sevalor.soler-{unique_suffix}.cat"

    payload = {
        "rao_social": f"Soler Instal·lacions {unique_suffix} S.L.",
        "nif": "B" + str(uuid.uuid4())[:8].upper(),
        "subdomini": subdomini,
        "domini_custom": domini_custom,
        "vertical": "ELECTRICPRO",
        "pla_subscripcio": "PRO",
        "quota_disc_gb": 50,
        "boss_nif": "12345678A",
        "boss_nom": "Pere",
        "boss_cognoms": "Soler",
        "boss_email": f"pere@{subdomini}.cat",
        "boss_telefon": "+34611223344",
        "feature_flags": {
            "copilot_ia": True,
            "flota_avancada": True,
            "planols_tecnics": True,
            "telegram_bot": True
        }
    }
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.post("/api/v1/superadmin/tenants/onboarding", json=payload, headers=headers)
        assert response.status_code == 201, f"Expected 201 but got {response.status_code}: {response.text}"
        data = response.json()
        assert data["status"] == "CREATED"
        tenant = data["tenant"]
        assert tenant["domini_custom"] == domini_custom
        assert tenant["domini_complet"] == domini_custom
        assert tenant["enllac_activacio_2fa"].startswith(f"https://{domini_custom}/activacio?token=")

        empresa_id = tenant["id"]

        # Comprovar que /superadmin/tenants/{id} retorna el domini_custom
        res_get = await ac.get(f"/api/v1/superadmin/tenants/{empresa_id}", headers=headers)
        assert res_get.status_code == 200
        assert res_get.json()["domini_custom"] == domini_custom

        # Comprovar actualització del domini via PUT /{id}/domini
        nou_domini = f"app.soler-{unique_suffix}.cat"
        res_put = await ac.put(
            f"/api/v1/superadmin/tenants/{empresa_id}/domini",
            json={"domini_custom": nou_domini},
            headers=headers,
        )
        assert res_put.status_code == 200
        assert res_put.json()["domini_custom"] == nou_domini

        # Comprovar rebuig de duplicats de domini
        payload_dup = {
            **payload,
            "nif": "B" + str(uuid.uuid4())[:8].upper(),
            "subdomini": f"altre-{unique_suffix}",
            "domini_custom": nou_domini,
            "boss_email": f"altre@{subdomini}.cat",
        }
        res_dup = await ac.post("/api/v1/superadmin/tenants/onboarding", json=payload_dup, headers=headers)
        assert res_dup.status_code == 409
        assert "ja està en ús" in res_dup.json()["detail"]

