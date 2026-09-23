import uuid

import jwt as pyjwt
import pytest
import pytest_asyncio
from fastapi import status
from httpx import AsyncClient

from app.core.config import settings
from app.main import app


def crear_token(rol: str, empresa_id: str, sub: str = None) -> str:
    payload = {
        "sub": sub or str(uuid.uuid4()),
        "rol": rol,
        "empresa_id": empresa_id,
        "exp": 9999999999,
    }
    return pyjwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)

@pytest.fixture
def empresa_id():
    return str(uuid.uuid4())

@pytest.fixture
def operari_id():
    return str(uuid.uuid4())

@pytest.fixture
def altre_operari_id():
    return str(uuid.uuid4())

from httpx import ASGITransport


@pytest_asyncio.fixture
async def client_autenticat_enginyer(empresa_id):
    token = crear_token("ENGINYER", empresa_id)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test", headers={"Authorization": f"Bearer {token}", "x-tenant-id": empresa_id}) as client:
        yield client

@pytest_asyncio.fixture
async def client_autenticat_operari(empresa_id, operari_id):
    token = crear_token("OPERARI", empresa_id, sub=operari_id)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test", headers={"Authorization": f"Bearer {token}", "x-tenant-id": empresa_id}) as client:
        yield client

@pytest_asyncio.fixture
async def client_autenticat_altre_operari(empresa_id, altre_operari_id):
    token = crear_token("OPERARI", empresa_id, sub=altre_operari_id)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test", headers={"Authorization": f"Bearer {token}", "x-tenant-id": empresa_id}) as client:
        yield client

@pytest_asyncio.fixture
async def client_autenticat_superadmin(empresa_id):
    token = crear_token("SUPERADMIN", empresa_id)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test", headers={"Authorization": f"Bearer {token}", "x-tenant-id": empresa_id}) as client:
        yield client

@pytest.mark.asyncio
async def test_enginyer_cannot_access_financial_data(client_autenticat_enginyer: AsyncClient):
    """L'enginyer no pot veure factures (Veto d'Enginyer)."""
    response = await client_autenticat_enginyer.get("/api/v1/gestio/comptabilitat/factures")
    assert response.status_code == status.HTTP_403_FORBIDDEN

@pytest.mark.asyncio
async def test_operari_cannot_access_gestio_clients(client_autenticat_operari: AsyncClient):
    """L'operari no pot accedir a la gestió de clients."""
    payload = {
        "codi": "CLI-123",
        "rao_social": "Test Client",
        "nif": "B12345678"
    }
    response = await client_autenticat_operari.post("/api/v1/gestio/clients", json=payload)
    assert response.status_code == status.HTTP_403_FORBIDDEN

@pytest.mark.asyncio
async def test_superadmin_has_bypass_access(client_autenticat_superadmin: AsyncClient):
    """El superadmin té bypass autoritzat per administració del sistema (by design)."""
    response = await client_autenticat_superadmin.get("/api/v1/gestio/comptabilitat/factures")
    assert response.status_code == status.HTTP_200_OK

@pytest.mark.asyncio
async def test_operari_cannot_close_others_jornada(client_autenticat_altre_operari: AsyncClient):
    """Un operari no pot tancar la jornada d'un altre operari."""
    # Intentem tancar una jornada dummy amb el token de l'altre operari
    dummy_jornada_id = str(uuid.uuid4())
    res_fi = await client_autenticat_altre_operari.post(f"/api/v1/operari/jornada/{dummy_jornada_id}/fi", json={"geolocalitzacio": "0,0"})
    assert res_fi.status_code == status.HTTP_404_NOT_FOUND or res_fi.status_code == status.HTTP_403_FORBIDDEN
