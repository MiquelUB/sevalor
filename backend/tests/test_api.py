import httpx
import pytest

from app.main import app


@pytest.mark.asyncio
async def test_root_endpoint():
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert data["service"] == "Sevalor Suite API"
        assert data["status"] == "operational"

@pytest.mark.asyncio
async def test_health_check_endpoint():
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/health")
        # Health check failed with 503 before because db_session wasn't overriding healthcheck DB dependency?
        # Let's print the response if it fails
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert data["status"] == "healthy"
        assert data["database"] == "connected"
