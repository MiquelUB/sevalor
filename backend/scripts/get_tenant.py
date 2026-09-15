import asyncio
import os
import sys

# Inject backend path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.db import AsyncSessionLocal
from app.models.models import Empresa
from sqlalchemy import select

async def get_tenant():
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Empresa).where(Empresa.nom == "Sevalor Admin"))
        emp = result.scalar_one_or_none()
        if emp:
            print("\n" + "="*50)
            print("🏢 EL TEU TENANT ID ÉS:")
            print(emp.id)
            print("="*50 + "\n")
        else:
            print("❌ No s'ha trobat cap empresa. Has executat seed.py?")

if __name__ == "__main__":
    asyncio.run(get_tenant())