import asyncio
import os
import sys

# Inject backend path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text

from app.core.db import engine


async def force():
    async with engine.begin() as conn:
        print("⏳ Cercant usuaris a la base de dades...")
        result = await conn.execute(text("SELECT nif, rol, empresa_id FROM usuaris;"))
        rows = result.fetchall()
        for r in rows:
            print(f"👉 Trobat: NIF='{r[0]}', ROL='{r[1]}', EMPRESA='{r[2]}'")

        print("⏳ Forçant NIF a majúscules per si de cas...")
        await conn.execute(text("UPDATE usuaris SET nif = 'ADMIN' WHERE nif = 'admin';"))

        # També forcem el hash del PIN 1234 directament, per assegurar-nos que no va fallar l'encriptació
        from app.api.v1.gestio.operaris import hash_pin
        nou_hash = hash_pin("1234")
        await conn.execute(text(f"UPDATE usuaris SET pin_hash = '{nou_hash}' WHERE nif = 'ADMIN';"))

    print("✅ Administrador actualitzat i forçat a ADMIN amb pin 1234.")

if __name__ == "__main__":
    asyncio.run(force())
