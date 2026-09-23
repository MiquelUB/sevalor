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

        print("⏳ Aplicant polítiques RLS a totes les taules...")
        result = await conn.execute(text("""
            SELECT table_name 
            FROM information_schema.columns 
            WHERE table_schema = 'public' AND column_name = 'empresa_id'
        """))
        tables_with_empresa = [row[0] for row in result.fetchall()]

        for table in tables_with_empresa:
            await conn.execute(text(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY;"))
            await conn.execute(text(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY;"))
            await conn.execute(text(f"DROP POLICY IF EXISTS rls_{table}_tenant_isolation ON {table};"))
            # For usuaris, superadmin can be NULL empresa_id. But simple policy works for all (superadmin sees all)
            if table == 'usuaris':
                await conn.execute(text(f"""
                CREATE POLICY rls_{table}_tenant_isolation ON {table}
                FOR ALL
                USING (
                    empresa_id::text = current_setting('app.current_empresa_id', true)
                    OR (empresa_id IS NULL AND current_setting('app.is_superadmin', true) = 'true')
                    OR current_setting('app.is_superadmin', true) = 'true'
                );
                """))
            else:
                await conn.execute(text(f"""
                CREATE POLICY rls_{table}_tenant_isolation ON {table}
                FOR ALL
                USING (
                    empresa_id::text = current_setting('app.current_empresa_id', true)
                    OR current_setting('app.is_superadmin', true) = 'true'
                );
                """))

        # For empreses table itself
        await conn.execute(text("ALTER TABLE empreses ENABLE ROW LEVEL SECURITY;"))
        await conn.execute(text("ALTER TABLE empreses FORCE ROW LEVEL SECURITY;"))
        await conn.execute(text("DROP POLICY IF EXISTS rls_empreses_tenant_isolation ON empreses;"))
        await conn.execute(text("""
        CREATE POLICY rls_empreses_tenant_isolation ON empreses
        FOR ALL
        USING (
            id::text = current_setting('app.current_empresa_id', true)
            OR current_setting('app.is_superadmin', true) = 'true'
        );
        """))

    print("✅ Rol 'sevalor_app' i polítiques RLS creats correctament!")

if __name__ == "__main__":
    asyncio.run(fix_rls())
