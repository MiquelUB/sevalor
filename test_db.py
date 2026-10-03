import asyncio
import os
from sqlalchemy.ext.asyncio import create_async_engine

TEST_DB_URL = os.getenv(
    "TEST_DATABASE_URL",
    "postgresql+asyncpg://postgres:postgres@localhost:5433/sevalor"
)
print("TEST_DB_URL:", TEST_DB_URL)

async def test():
    engine = create_async_engine(TEST_DB_URL, echo=False)
    async with engine.connect() as conn:
        print("CONNECTED!")

asyncio.run(test())
