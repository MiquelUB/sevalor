import asyncio
import os
import sys

# Inject backend path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select

from app.core.db import AsyncSessionLocal
from app.models.models import Usuari


async def fix():
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Usuari).where(Usuari.nif == "admin"))
        admin = result.scalar_one_or_none()
        if admin:
            admin.nif = "ADMIN"
            await session.commit()
            print("✅ NIF d'admin canviat a majúscules (ADMIN)")
        else:
            print("❌ No s'ha trobat l'usuari admin")

if __name__ == "__main__":
    asyncio.run(fix())
