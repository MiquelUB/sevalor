import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from app.models.models import Base

async def drop():
    engine = create_async_engine("postgresql+asyncpg://postgres:postgres@localhost:5433/sevalor")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

asyncio.run(drop())
