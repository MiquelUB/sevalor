import asyncio
import uuid
import bcrypt
import os
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

DATABASE_URL = os.getenv("TEST_DATABASE_URL", "postgresql+asyncpg://postgres:postgres@db:5432/sevalor")

async def seed():
    engine = create_async_engine(DATABASE_URL)
    async with engine.begin() as conn:
        await conn.execute(text("DELETE FROM usuaris WHERE nif = '99999999E'"))
        
        res = await conn.execute(text("SELECT id FROM empreses WHERE nif = 'NIF-E2E'"))
        empresa_id = res.scalar()
        if not empresa_id:
            empresa_id = str(uuid.uuid4())
            await conn.execute(
                text("INSERT INTO empreses (id, nom, nif, subdomini, pla_subscripcio, estat_pagament) VALUES (:id, 'Test E2E Empresa', 'NIF-E2E', 'e2e', 'STARTER', 'ACTIU')"),
                {"id": empresa_id}
            )
            
        operari_id = str(uuid.uuid4())
        hashed_pin = bcrypt.hashpw('1234'.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        await conn.execute(
            text("""INSERT INTO usuaris (id, empresa_id, nif, nom, rol, pin_hash, pin_bloquejat, intents_pin_fallits) 
                    VALUES (:id, :emp, '99999999E', 'Operari E2E', 'OPERARI', :pin, false, 0)"""),
            {"id": operari_id, "emp": empresa_id, "pin": hashed_pin}
        )
    print(f"Database seeded for E2E tests: EmpresaID={empresa_id}")
    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(seed())
