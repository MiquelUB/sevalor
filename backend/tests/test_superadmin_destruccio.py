import uuid
from datetime import datetime, timedelta, timezone
import jwt
import pytest
from httpx import AsyncClient, ASGITransport
import os

from app.core.config import settings
from app.main import app
from app.models.models import Empresa
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

async def test_tenant_destruccio(superadmin_token_headers, db_session: AsyncSession):
    empresa = Empresa(nom="Empresa To Delete", subdomini="delete-me", nif="99999999D")
    db_session.add(empresa)
    await db_session.commit()
    await db_session.refresh(empresa)

    empresa_id = str(empresa.id)

    # Mock the celery task apply_async so it doesn't run during test
    from unittest.mock import patch
    with patch("app.workers.tasks.purgar_dades_tenant_destruit.apply_async") as mock_apply:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test", headers=superadmin_token_headers) as client:
            response = await client.post(f"/api/v1/superadmin/tenants/{empresa_id}/destruccio")
            
            assert response.status_code == 200
            data = response.json()
            assert data["estat"] == "ELIMINAT"
            assert "certificat_url" in data
            assert os.path.exists(data["certificat_url"])
            
            mock_apply.assert_called_once()

    # Verify DB state
    await db_session.refresh(empresa)
    assert empresa.estat_pagament == "ELIMINAT"
