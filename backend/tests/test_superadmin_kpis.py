import uuid
from datetime import datetime, timedelta, timezone
import jwt
import pytest
from httpx import AsyncClient, ASGITransport

from app.core.config import settings
from app.main import app
from app.models.models import Empresa, Usuari
from sqlalchemy.ext.asyncio import AsyncSession

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

async def test_telemetry_global_endpoint(superadmin_token_headers):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test", headers=superadmin_token_headers) as client:
        response = await client.get("/api/v1/superadmin/telemetria/global")
        assert response.status_code == 200
        data = response.json()
        assert "cluster" in data
        assert "microservices" in data
        assert "concurrency" in data
        assert "db" in data["microservices"]

async def test_quota_guard_downgrade(superadmin_token_headers, db_session: AsyncSession):
    # Prepare data: 1 Empresa, 6 Usuaris actius
    empresa = Empresa(nom="Empresa Test", subdomini="test", nif="12345678A")
    db_session.add(empresa)
    await db_session.flush()

    for i in range(6):
        u = Usuari(
            empresa_id=empresa.id,
            nom=f"Usuari {i}",
            email=f"u{i}@test.com",
            nif=f"1234567{i}X",
            password_hash="hashed",
            rol="OPERARI",
            estat="ACTIU"
        )
        db_session.add(u)
    await db_session.commit()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test", headers=superadmin_token_headers) as client:
        # Intento de downgrade a BASIC (limit 5) per una empresa amb 6 operaris actius
        response = await client.patch(
            f"/api/v1/superadmin/telemetria/tenants/{empresa.id}/quota",
            json={"pla_subscripcio": "BASIC"}
        )
        assert response.status_code == 400
        assert "Downgrade blocat" in response.json()["detail"]

        # Intento d'upgrade a PREMIUM (limit 15) hauria de funcionar
        response = await client.patch(
            f"/api/v1/superadmin/telemetria/tenants/{empresa.id}/quota",
            json={"pla_subscripcio": "PREMIUM"}
        )
        assert response.status_code == 200
        assert response.json()["quota_operaris"] == 15
