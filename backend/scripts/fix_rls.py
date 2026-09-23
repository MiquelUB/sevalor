import asyncio
import os
import sys

# Inject backend path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text

from app.core.db import engine


async def fix_rls():
    async with engine.begin() as conn:
        print("⏳ Creant rol sevalor_app per a RLS...")
        await conn.execute(text("""
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'sevalor_app') THEN
                CREATE ROLE sevalor_app;
            END IF;
        END
        $$;
        """))

        # Concedir permisos bàsics al rol sobre totes les taules de l'esquema public
        await conn.execute(text("GRANT USAGE ON SCHEMA public TO sevalor_app;"))
        await conn.execute(text("GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO sevalor_app;"))
        await conn.execute(text("ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO sevalor_app;"))
        await conn.execute(text("GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO sevalor_app;"))
        await conn.execute(text("ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT USAGE, SELECT ON SEQUENCES TO sevalor_app;"))

    print("✅ Rol 'sevalor_app' creat i configurat correctament!")

if __name__ == "__main__":
    asyncio.run(fix_rls())
