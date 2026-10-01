import pytest
from httpx import AsyncClient
from fastapi import status
from sqlalchemy.ext.asyncio import AsyncSession

@pytest.mark.asyncio
async def test_economia_rendibilitat(async_client: AsyncClient, headers: dict):
    response = await async_client.get("/gestio/economia/rendibilitat")
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert isinstance(data, list)
    if len(data) > 0:
        assert "marge_brut" in data[0]
        assert "import_facturat" in data[0]
        assert "cost_materials" in data[0]

@pytest.mark.asyncio
async def test_economia_dashboard(async_client: AsyncClient, headers: dict):
    response = await async_client.get("/gestio/economia/dashboard")
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert "ingressos_mensuals" in data
    assert "marge_brut" in data
    assert "factures_pendents" in data
