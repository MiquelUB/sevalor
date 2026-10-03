import asyncio
from httpx import AsyncClient, ASGITransport
import sys
sys.path.insert(0, "./backend")
from app.main import app

async def test_login():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        payload = {"email": "admin@sevalor.com", "password": "Password123!"}
        res = await ac.post("/api/v1/auth/login", json=payload)
        print("Status:", res.status_code)
        print("Body:", res.text)

asyncio.run(test_login())
