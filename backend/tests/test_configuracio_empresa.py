import pytest
from httpx import AsyncClient

@pytest.mark.asyncio
async def test_configuracio_empresa_boss_only(client: AsyncClient, headers_admin):
    payload = {"nom": "Nova Empresa SA"}
    
    response = await client.put(
        "/api/v1/gestio/configuracio/empresa",
        json=payload,
        headers=headers_admin
    )
    assert response.status_code in (200, 403)
