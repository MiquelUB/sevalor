import asyncio
import os
import sys
import uuid

# Inject backend path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.db import AsyncSessionLocal
from app.models.models import Empresa, Usuari
from app.api.v1.gestio.operaris import hash_pin

async def seed():
    async with AsyncSessionLocal() as session:
        # Create Empresa
        empresa_id = uuid.uuid4()
        empresa = Empresa(
            id=empresa_id,
            nom="Sevalor Admin",
            nif="A12345678",
            subdomini="admin"
        )
        session.add(empresa)
        
        # Create Superadmin
        admin = Usuari(
            id=uuid.uuid4(),
            empresa_id=empresa_id,
            nif="admin",
            nom="Admin",
            cognoms="Principal",
            email="admin@sevalor.com",
            pin_hash=hash_pin("1234"),
            rol="SUPERADMIN",
            estat="ACTIU"
        )
        session.add(admin)
        
        await session.commit()
        print("✅ Superadmin creat!")
        print(f"🏢 Empresa ID: {empresa_id}")
        print("👤 Usuari: admin")
        print("🔑 PIN: 1234")

if __name__ == "__main__":
    asyncio.run(seed())