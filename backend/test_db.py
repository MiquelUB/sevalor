import asyncio

from sqlalchemy import select

from app.core.db import AsyncSessionLocal
from app.models.models import Proveidor


async def main():
    async with AsyncSessionLocal() as db:
        res = await db.execute(select(Proveidor))
        provs = res.scalars().all()
        print(f"Proveidors found: {len(provs)}")
        for p in provs:
            print(f" - {p.rao_social} (NIF: {p.nif})")

if __name__ == "__main__":
    asyncio.run(main())
