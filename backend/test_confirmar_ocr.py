import asyncio

from httpx import ASGITransport, AsyncClient

from app.main import app


async def run():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test/api/v1") as ac:
        # We need a valid token for a user. We can use the login test fixture approach, or just create a quick test user in DB.
        pass

if __name__ == "__main__":
    asyncio.run(run())
