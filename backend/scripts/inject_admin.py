import asyncio
import os
import sys
import uuid

# Inject backend path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.db import AsyncSessionLocal, engine
from sqlalchemy import text
from app.api.v1.gestio.operaris import hash_pin

async def inject():
    async with AsyncSessionLocal() as session:
        print("⏳ Buscant empresa...")
        result = await session.execute(text("SELECT id, nom FROM empreses LIMIT 1;"))
        empresa = result.fetchone()
        
        if not empresa:
            print("⏳ No hi ha cap empresa, la creem...")
            empresa_id = str(uuid.uuid4())
            await session.execute(text(f"""
                INSERT INTO empreses (id, nom, nif, subdomini) 
                VALUES ('{empresa_id}', 'Sevalor Admin', 'A12345678', 'admin')
            """))
            await session.commit()
            print(f"🏢 Empresa creada: {empresa_id}")
        else:
            empresa_id = empresa[0]
            print(f"🏢 Empresa trobada: {empresa[1]} (ID: {empresa_id})")

        print("⏳ Injectant usuari SUPERADMIN...")
        nou_hash = hash_pin("1234")
        
        # Check if user exists
        res = await session.execute(text("SELECT id FROM usuaris WHERE upper(nif) = 'ADMIN';"))
        user = res.fetchone()
        
        if user:
            print("⏳ L'usuari ADMIN ja existeix. Actualitzant PIN a 1234 i rol a SUPERADMIN...")
            await session.execute(text(f"""
                UPDATE usuaris 
                SET pin_hash = '{nou_hash}', rol = 'SUPERADMIN', estat = 'ACTIU', empresa_id = '{empresa_id}'
                WHERE upper(nif) = 'ADMIN';
            """))
        else:
            print("⏳ Creant usuari ADMIN nou...")
            user_id = str(uuid.uuid4())
            await session.execute(text(f"""
                INSERT INTO usuaris (id, empresa_id, nif, nom, pin_hash, rol, estat)
                VALUES ('{user_id}', '{empresa_id}', 'ADMIN', 'Admin Principal', '{nou_hash}', 'SUPERADMIN', 'ACTIU')
            """))
            
        await session.commit()
        print("✅ ============================================")
        print("✅ ÈXIT: Usuari ADMIN injectat/actualitzat!")
        print(f"🏢 EL TEU TENANT ID ÉS: {empresa_id}")
        print("👤 Usuari NIF: ADMIN")
        print("🔑 PIN: 1234")
        print("✅ ============================================")

if __name__ == "__main__":
    asyncio.run(inject())