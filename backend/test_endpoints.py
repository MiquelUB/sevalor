import asyncio
from httpx import AsyncClient, ASGITransport
from app.main import app
async def main():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
        r = await client.get("/api/v1/gestio/economia/dashboard")
        print(r.status_code)
asyncio.run(main())
