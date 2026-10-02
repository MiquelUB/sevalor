import uuid
from datetime import datetime, timedelta, timezone

import jwt
import pytest
from httpx import ASGITransport, AsyncClient

from app.core.config import settings
from app.main import app

def make_token(totp=True, ip_list=None):
    if ip_list is None:
        ip_list = ["testclient", "*"]
    payload = {
        "sub": "00000000-0000-0000-0000-000000000000",
        "rol": "SUPERADMIN",
        "empresa_id": None,
        "exp": datetime.now(timezone.utc) + timedelta(minutes=15),
        "totp_activat": totp,
        "ip_allowlist": ip_list
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)

@pytest.mark.asyncio
async def test_superadmin_missing_totp():
    token = make_token(totp=False)
    headers = {"Authorization": f"Bearer {token}"}
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get("/api/v1/superadmin/tenants", headers=headers)
        assert response.status_code == 403
        assert "TOTP" in response.text

@pytest.mark.asyncio
async def test_superadmin_ip_blocking():
    # Only allow 1.1.1.1
    token = make_token(totp=True, ip_list=["1.1.1.1"])
    headers = {"Authorization": f"Bearer {token}"}
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get("/api/v1/superadmin/tenants", headers=headers)
        assert response.status_code == 403
        assert "IP" in response.text

@pytest.mark.asyncio
async def test_impersonation_jwt_generation(db_session):
    # Require an existing tenant
    token = make_token(totp=True, ip_list=["*"])
    headers = {"Authorization": f"Bearer {token}"}
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # First create a tenant
        payload = {
            "rao_social": "Imp Test",
            "nif": "B12345674",
            "subdomini": "imptest-" + str(uuid.uuid4())[:8],
            "vertical": "SEVALOR",
            "pla_subscripcio": "STARTER",
            "quota_disc_gb": 20,
            "boss_nif": "43211234A",
            "boss_nom": "Jordi",
            "boss_cognoms": "Puig",
            "boss_email": "imptest@test.cat",
            "boss_telefon": "+34600100200",
            "feature_flags": {}
        }
        res_create = await ac.post("/api/v1/superadmin/tenants/onboarding", json=payload, headers=headers)
        assert res_create.status_code == 201
        empresa_id = res_create.json()["tenant"]["id"]

        res_imp = await ac.post(f"/api/v1/superadmin/tenants/{empresa_id}/impersonate", headers=headers)
        assert res_imp.status_code == 200
        data = res_imp.json()
        assert data["is_impersonation"] is True
        
        # Verify the new token has is_impersonation=True
        imp_token = data["access_token"]
        decoded = jwt.decode(imp_token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM], options={"verify_aud": False})
        assert decoded["is_impersonation"] is True
        assert decoded["empresa_id"] == empresa_id
        assert decoded["rol"] == "SUPERADMIN"
        
        # Test financial endpoint block (example: we can't test unless we know a financial endpoint, but we can just test if the token is decoded correctly)
