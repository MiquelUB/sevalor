"""Add economics_boss_only restrictive RLS policies (Constitució §2.VI and plan.md §3.3.2).

Revision ID: a002_rls_economics_boss_only
Revises: 5278392ca81d
Create Date: 2026-10-09

Constitució §2.VI:
Les dades econòmiques (marges, EBITDA, nòmines, barema de preus) estan restringides
exclusivament al rol Boss mitjançant:
- Capa 1 (Soft): Classificador IA que filtra preguntes econòmiques per rol.
- Capa 2 (Hard): RLS PostgreSQL amb policy economics_boss_only que retorna 0 rows
  si el rol no és Boss. Infranquejable.
"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a002_rls_economics_boss_only"
down_revision: Union[str, Sequence[str], None] = "5278392ca81d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

ECONOMIC_TABLES = [
    "auditories_post_obra",
    "factures_capcalera",
    "factures_linies",
    "factures_proveidor",
    "factures_proveidor_linies",
    "outbox_enviaments_aeat",
    "registre_esdeveniments_sif",
]


def upgrade() -> None:
    """Create economics_boss_only restrictive RLS policy on economic tables."""
    for table in ECONOMIC_TABLES:
        # Force RLS for defense in depth
        op.execute(f"ALTER TABLE public.{table} ENABLE ROW LEVEL SECURITY;")
        op.execute(f"ALTER TABLE public.{table} FORCE ROW LEVEL SECURITY;")

        # Policy RESTRICTIVE: must be satisfied in AND conjunction with tenant_isolation
        op.execute(
            f"""
            DO $$
            BEGIN
                DROP POLICY IF EXISTS economics_boss_only_{table} ON public.{table};
                CREATE POLICY economics_boss_only_{table} ON public.{table}
                    AS RESTRICTIVE
                    FOR ALL
                    USING (
                        NULLIF(current_setting('app.current_user_role', true), '') IN ('BOSS', 'SUPERADMIN')
                    )
                    WITH CHECK (
                        NULLIF(current_setting('app.current_user_role', true), '') IN ('BOSS', 'SUPERADMIN')
                    );
            END
            $$;
            """
        )

    # Standardize tenant_isolation_policy on contractes tables with NULLIF
    op.execute(
        """
        DO $$
        DECLARE
            taula TEXT;
        BEGIN
            FOR taula IN SELECT unnest(ARRAY['contractes_manteniment', 'contractes_manteniment_finques', 'revisions_contracte']) LOOP
                EXECUTE format('DROP POLICY IF EXISTS tenant_isolation_policy ON public.%I;', taula);
                EXECUTE format('DROP POLICY IF EXISTS tenant_isolation_%I ON public.%I;', taula, taula);
                EXECUTE format('CREATE POLICY tenant_isolation_%I ON public.%I FOR ALL USING (empresa_id = NULLIF(current_setting(''app.current_empresa_id'', true), '''')::uuid) WITH CHECK (empresa_id = NULLIF(current_setting(''app.current_empresa_id'', true), '''')::uuid);', taula, taula);
                EXECUTE format('ALTER TABLE public.%I FORCE ROW LEVEL SECURITY;', taula);
                EXECUTE format('GRANT SELECT, INSERT, UPDATE, DELETE ON public.%I TO sevalor_app;', taula);
            END LOOP;
        END
        $$;
        """
    )


def downgrade() -> None:
    """Drop economics_boss_only restrictive RLS policy."""
    for table in ECONOMIC_TABLES:
        op.execute(f"DROP POLICY IF EXISTS economics_boss_only_{table} ON public.{table};")
