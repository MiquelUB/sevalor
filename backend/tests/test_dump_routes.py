import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app

@pytest.mark.asyncio
async def test_dump_routes():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.get("/api/v1/gestio/contractes/alertes/venciments")
        print(f"STATUS {resp.status_code}")
        print(f"TEXT {resp.text}")
