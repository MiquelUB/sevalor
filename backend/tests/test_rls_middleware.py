import pytest
import jwt
from httpx import AsyncClient, ASGITransport
from datetime import datetime, timedelta, timezone
from app.main import app
from app.core.config import settings

@pytest.fixture
def fake_secret():
    # Assegurem que el settings.SECRET_KEY té un valor durant els tests per poder signar
    if not settings.SECRET_KEY:
        settings.SECRET_KEY = "test-secret-key-32-chars-long-xxx"
    return settings.SECRET_KEY

def create_token(rol: str, empresa_id: str, secret: str):
    payload = {
        "sub": "00000000-0000-0000-0000-000000000000",
        "rol": rol,
        "empresa_id": empresa_id,
        "exp": datetime.now(timezone.utc) + timedelta(minutes=15)
    }
    return jwt.encode(payload, secret, algorithm=settings.ALGORITHM)

@pytest.mark.asyncio
async def test_middleware_blocks_tenant_spoofing(fake_secret):
    real_tenant = "11111111-1111-1111-1111-111111111111"
    forged_tenant = "99999999-9999-9999-9999-999999999999"
    
    token = create_token("OPERARI", real_tenant, fake_secret)
    headers = {
        "Authorization": f"Bearer {token}",
        "X-Empresa-ID": forged_tenant
    }
    
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        res = await ac.get("/api/v1/auth/me", headers=headers)
        assert res.status_code == 200
        data = res.json()
        # El middleware ha d'ignorar la capçalera X-Empresa-ID spoofejada i utilitzar el JWT signat
        assert data["empresa_id"] == real_tenant
        assert data["empresa_id"] != forged_tenant

@pytest.mark.asyncio
async def test_superadmin_can_impersonate_tenant(fake_secret):
    superadmin_token = create_token("SUPERADMIN", "00000000-0000-0000-0000-000000000000", fake_secret)
    target_tenant = "33333333-3333-3333-3333-333333333333"
    headers = {
        "Authorization": f"Bearer {superadmin_token}",
        "X-Empresa-ID": target_tenant
    }
    
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        res = await ac.get("/api/v1/auth/me", headers=headers)
        assert res.status_code == 200
        data = res.json()
        assert data["rol"] == "SUPERADMIN"

