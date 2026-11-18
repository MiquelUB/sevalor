"""a024: Alinea les polítiques RLS de taules comptables amb Constitució §1.2 (BOSS, SUPERADMIN, SECRETARIA, COMPTABILITAT)

Revision ID: a024_rls_accounting_roles
Revises: a023_picking_linia_magatzem
Create Date: 2026-11-18
"""

from typing import Sequence, Union

from alembic import op

revision: str = "a024_rls_accounting_roles"
down_revision: Union[str, Sequence[str], None] = "a023_picking_linia_magatzem"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

ACCOUNTING_TABLES = [
    "factures_capcalera",
    "factures_linies",
    "factures_proveidor",
    "factures_proveidor_linies",
    "outbox_enviaments_aeat",
    "registre_esdeveniments_sif",
]


def upgrade() -> None:
    for table in ACCOUNTING_TABLES:
        op.execute(
            f"""
            DO $$
            BEGIN
                DROP POLICY IF EXISTS economics_boss_only_{table} ON public.{table};
                CREATE POLICY economics_boss_only_{table} ON public.{table}
                    AS RESTRICTIVE
                    FOR ALL
                    USING (
                        NULLIF(current_setting('app.current_user_role', true), '')
                        IN ('BOSS', 'SUPERADMIN', 'SECRETARIA', 'COMPTABILITAT')
                    )
                    WITH CHECK (
                        NULLIF(current_setting('app.current_user_role', true), '')
                        IN ('BOSS', 'SUPERADMIN', 'SECRETARIA', 'COMPTABILITAT')
                    );
            END
            $$;
            """
        )


def downgrade() -> None:
    for table in ACCOUNTING_TABLES:
        op.execute(
            f"""
            DO $$
            BEGIN
                DROP POLICY IF EXISTS economics_boss_only_{table} ON public.{table};
                CREATE POLICY economics_boss_only_{table} ON public.{table}
                    AS RESTRICTIVE
                    FOR ALL
                    USING (
                        NULLIF(current_setting('app.current_user_role', true), '')
                        IN ('BOSS', 'SUPERADMIN')
                    )
                    WITH CHECK (
                        NULLIF(current_setting('app.current_user_role', true), '')
                        IN ('BOSS', 'SUPERADMIN')
                    );
            END
            $$;
            """
        )
