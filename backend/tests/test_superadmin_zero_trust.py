import uuid
from datetime import datetime, timedelta, timezone

import jwt
import pytest
from httpx import ASGITransport, AsyncClient

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
    headers_with_origin = {
        **superadmin_token_headers,
        "Origin": "https://sevalor-sevalor-pwa.80opze.easypanel.host",
    }
    async with AsyncClient(transport=transport, base_url="http://test", headers=headers_with_origin) as client:
        # Try to access an operational route
        # /api/v1/feines (requires authentication and usually BOSS/OPERARI etc)
        response = await client.get("/api/v1/feines")
        assert response.status_code == 403
        assert "SUPERADMIN no pot accedir a rutes operatives" in response.json()["detail"]
        # Mandatory CORS check: Ensure 403 response includes CORS header so browser does not block
        assert response.headers.get("access-control-allow-origin") == "https://sevalor-sevalor-pwa.80opze.easypanel.host"

        response = await client.get("/api/v1/clients")
        assert response.status_code == 403
        assert response.headers.get("access-control-allow-origin") == "https://sevalor-sevalor-pwa.80opze.easypanel.host"

        # Spotlight items check
        response_spotlight = await client.get("/api/v1/spotlight/items")
        assert response_spotlight.status_code == 403
        assert response_spotlight.headers.get("access-control-allow-origin") == "https://sevalor-sevalor-pwa.80opze.easypanel.host"

        # But they should be able to access /api/v1/superadmin/...
        response = await client.get("/api/v1/superadmin/telemetria/kpis")
        assert response.status_code != 403


async def test_cors_options_preflight():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.options(
            "/api/v1/spotlight/items",
            headers={
                "Origin": "https://sevalor-sevalor-pwa.80opze.easypanel.host",
                "Access-Control-Request-Method": "GET",
                "Access-Control-Request-Headers": "authorization,x-empresa-id",
            },
        )
        assert response.status_code == 200
        assert response.headers.get("access-control-allow-origin") == "https://sevalor-sevalor-pwa.80opze.easypanel.host"
        assert "GET" in response.headers.get("access-control-allow-methods", "")


async def test_impersonation_not_blocked_by_superadmin_segregation():
    empresa_id = str(uuid.uuid4())
    payload = {
        "sub": str(uuid.uuid4()),
        "rol": "SUPERADMIN",
        "empresa_id": empresa_id,
        "is_impersonation": True,
        "totp_activat": True,
        "ip_allowlist": ["*"],
        "exp": datetime.now(timezone.utc) + timedelta(minutes=15),
    }
    token = jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    headers = {
        "Authorization": f"Bearer {token}",
        "Origin": "https://sevalor-sevalor-pwa.80opze.easypanel.host",
    }
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test", headers=headers) as client:
        # Should not be blocked with 403 by Zero-Trust segregation
        response = await client.get("/api/v1/spotlight/items")
        assert response.status_code != 403
        assert response.headers.get("access-control-allow-origin") == "https://sevalor-sevalor-pwa.80opze.easypanel.host"

