import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text
from app.models.models import Base

async def drop():
    engine = create_async_engine("postgresql+asyncpg://postgres:postgres@localhost:5433/sevalor")
    async with engine.begin() as conn:
        await conn.execute(text("DROP SCHEMA public CASCADE"))
        await conn.execute(text("CREATE SCHEMA public"))
        await conn.execute(text("GRANT ALL ON SCHEMA public TO postgres"))
        await conn.execute(text("GRANT ALL ON SCHEMA public TO public"))

asyncio.run(drop())
