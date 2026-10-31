"""T009: Grant DML to sevalor_app on empreses and ensure RLS policies.

Revision ID: a009_empreses_rls_grants
Revises: a008_spec007_gk_cp
Create Date: 2026-10-31

Garanteix que el rol d'aplicació sevalor_app tingui permisos de SELECT i UPDATE
a la taula empreses sota RLS, evitant errors 'permission denied for table empreses'.
"""
from typing import Sequence, Union
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a009_empreses_rls_grants"
down_revision: Union[str, Sequence[str], None] = "a008_spec007_gk_cp"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Assegurar que el rol sevalor_app existeix
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'sevalor_app') THEN
                CREATE ROLE sevalor_app NOLOGIN;
            END IF;
        END
        $$;
        """
    )

    # 2. Assegurar permisos USAGE a schema public
    op.execute("GRANT USAGE ON SCHEMA public TO sevalor_app;")

    # 3. Permisos a la taula empreses
    op.execute("GRANT SELECT, UPDATE ON public.empreses TO sevalor_app;")

    # 4. Permisos generals per a totes les taules i seqüències actuals i futures
    op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO sevalor_app;")
    op.execute("GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO sevalor_app;")
    op.execute("ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO sevalor_app;")
    op.execute("ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT USAGE, SELECT ON SEQUENCES TO sevalor_app;")

    # 5. RLS a la taula empreses
    op.execute("ALTER TABLE public.empreses ENABLE ROW LEVEL SECURITY;")
    op.execute("ALTER TABLE public.empreses FORCE ROW LEVEL SECURITY;")

    # Netejar polítiques prèvies si existien
    op.execute("DROP POLICY IF EXISTS rls_empreses_select ON public.empreses;")
    op.execute("DROP POLICY IF EXISTS rls_empreses_mutation ON public.empreses;")
    op.execute("DROP POLICY IF EXISTS tenant_isolation_empreses ON public.empreses;")

    # Política de lectura per a tothom (resolució pública de tenants, marca, auth/me, etc.)
    op.execute(
        """
        CREATE POLICY rls_empreses_select ON public.empreses
        FOR SELECT
        USING (true);
        """
    )

    # Política de mutació (només el propi tenant o superadmin)
    op.execute(
        """
        CREATE POLICY rls_empreses_mutation ON public.empreses
        FOR ALL
        USING (
            id = NULLIF(current_setting('app.current_empresa_id', true), '')::uuid
            OR current_setting('app.is_superadmin', true) = 'true'
        )
        WITH CHECK (
            id = NULLIF(current_setting('app.current_empresa_id', true), '')::uuid
            OR current_setting('app.is_superadmin', true) = 'true'
        );
        """
    )


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS rls_empreses_select ON public.empreses;")
    op.execute("DROP POLICY IF EXISTS rls_empreses_mutation ON public.empreses;")
    op.execute("ALTER TABLE public.empreses NO FORCE ROW LEVEL SECURITY;")
