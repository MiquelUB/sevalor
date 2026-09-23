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
        "exp": datetime.now(timezone.utc) + timedelta(minutes=15)
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
