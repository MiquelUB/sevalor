import asyncio
from sqlalchemy import text
from app.core.db import engine

async def main():
    async with engine.connect() as conn:
        res = await conn.execute(text("SELECT pg_get_constraintdef(c.oid) FROM pg_constraint c JOIN pg_namespace n ON n.oid = c.connamespace WHERE conname = 'registres_jornada_laboral_estat_check'"))
        print(res.scalar())

asyncio.run(main())
