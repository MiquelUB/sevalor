import uuid
from datetime import datetime, timedelta, timezone
import jwt
import pytest
from httpx import AsyncClient, ASGITransport

from app.core.config import settings
from app.main import app

pytestmark = pytest.mark.asyncio

@pytest.fixture
def superadmin_token_headers():
    empresa_id = str(uuid.uuid4())
    payload = {
        "sub": str(uuid.uuid4()),
        "rol": "SUPERADMIN",
        "empresa_id": empresa_id,
        "totp_activat": True,
        "ip_allowlist": ["*"],
        "exp": datetime.now(timezone.utc) + timedelta(minutes=15),
    }
    token = jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return {
        "Authorization": f"Bearer {token}",
        "X-Empresa-ID": empresa_id,
    }

async def test_superadmin_blocked_from_operational_routes(superadmin_token_headers):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test", headers=superadmin_token_headers) as client:
        # Try to access an operational route
        # Since DB session is mocked by conftest we might get a 403 before it even hits the DB
        # /api/v1/feines (requires authentication and usually BOSS/OPERARI etc)
        response = await client.get("/api/v1/feines")
        assert response.status_code == 403
        assert "SUPERADMIN no pot accedir a rutes operatives" in response.json()["detail"]

        response = await client.get("/api/v1/clients")
        assert response.status_code == 403

        # But they should be able to access /api/v1/superadmin/...
        # Let's test a non-existent or existing superadmin route
        response = await client.get("/api/v1/superadmin/telemetria/kpis")
        # Could be 200, 500 or something if not fully populated, but shouldn't be 403 from the middleware
        assert response.status_code != 403
