import pytest
from httpx import AsyncClient
import uuid
import jwt
from datetime import datetime, timezone, timedelta
from app.core.config import settings

@pytest.fixture(scope="function")
def headers_enginyer():
    empresa_id = str(uuid.uuid4())
    payload = {
        "sub": str(uuid.uuid4()),
        "rol": "ENGINYER",
        "empresa_id": empresa_id,
        "exp": datetime.now(timezone.utc) + timedelta(minutes=15),
    }
    token = jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return {
        "Authorization": f"Bearer {token}",
        "X-Empresa-ID": empresa_id,
    }

@pytest.mark.asyncio
async def test_configuracio_empresa_boss_only(async_client: AsyncClient, headers_enginyer):
    payload = {"nom": "Nova Empresa SA"}
    
    response = await async_client.put(
        "/gestio/configuracio/empresa",
        json=payload,
        headers=headers_enginyer
    )
    assert response.status_code == 403
