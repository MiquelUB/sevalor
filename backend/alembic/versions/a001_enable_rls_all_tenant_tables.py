"""T001: Enable RLS and tenant isolation policies on all tables with empresa_id.

Revision ID: a001_rls_all
Revises: 33d35fa1f8e2
Create Date: 2026-10-01

Per AGENTS.md §3.1: RLS activat obligatòriament en el 100% de les taules
que posseixin empresa_id.
"""
from alembic import op

# revision identifiers, used by Alembic.
revision = "a001_rls_all"
down_revision = "33d35fa1f8e2"
branch_labels = None
depends_on = None

# Tables that already have RLS enabled and policies created.
ALREADY_ENABLED = frozenset({
    "articles",
    "clients",
    "ordres_treball",
    "vehicles",
})

# All tables with empresa_id that need RLS activation.
TABLES_WITH_EMPRESA_ID = [
    "albarans_proveidor",
    "alertes_garantia_recompra",
    "articles",
    "auditoria_registres_jornada",
    "auditories_post_obra",
    "capes_anotacions",
    "capes_vectorials",
    "carpetes_planols",
    "clients",
    "consultes_xat_copilot",
    "converses_notificacio",
    "documents_cae_rc",
    "documents_flota",
    "eines_custodia",
    "estocs_magatzem",
    "exportacions_pdf_planol",
    "factures_capcalera",
    "factures_linies",
    "factures_proveidor",
    "factures_proveidor_linies",
    "faqs_corporatives_rag",
    "finques",
    "fulles_picking",
    "historial_assignacions_vehicles",
    "incidencies",
    "linies_picking",
    "magatzems",
    "memorandums_tecnics_copilot",
    "missatges_notificacio",
    "moviments_estoc",
    "ordres_treball",
    "outbox_enviaments_aeat",
    "pins_incidencia_planol",
    "planols_base",
    "pressupostos",
    "proveidors",
    "registre_esdeveniments_sif",
    "registres_jornada_laboral",
    "slots_jornada",
    "tiquets_carburant",
    "tiquets_combustible",
    "tokens_invitacio_telegram",
    "usuaris",
    "vehicles",
]


def upgrade() -> None:
    """Enable RLS, create tenant isolation policy, and grant DML to sevalor_app."""
    for table in TABLES_WITH_EMPRESA_ID:
        if table in ALREADY_ENABLED:
            # Already has RLS enabled and policy — only ensure FORCE and grants.
            op.execute(
                f"ALTER TABLE public.{table} FORCE ROW LEVEL SECURITY;"
            )
            op.execute(
                f"GRANT SELECT, INSERT, UPDATE, DELETE "
                f"ON public.{table} TO sevalor_app;"
            )
            continue

        # 1. Enable RLS on the table
        op.execute(
            f"ALTER TABLE public.{table} ENABLE ROW LEVEL SECURITY;"
        )

        # 2. Force RLS even for the table owner (defense in depth)
        op.execute(
            f"ALTER TABLE public.{table} FORCE ROW LEVEL SECURITY;"
        )

        # 3. Create the tenant isolation policy (ALL = SELECT/INSERT/UPDATE/DELETE)
        op.execute(
            f"CREATE POLICY tenant_isolation_{table} ON public.{table} "
            f"FOR ALL "
            f"USING (empresa_id = NULLIF(current_setting('app.current_empresa_id', true), '')::uuid) "
            f"WITH CHECK (empresa_id = NULLIF(current_setting('app.current_empresa_id', true), '')::uuid);"
        )

        # 4. Grant DML permissions to the application role
        op.execute(
            f"GRANT SELECT, INSERT, UPDATE, DELETE "
            f"ON public.{table} TO sevalor_app;"
        )


def downgrade() -> None:
    """Remove RLS policies and disable RLS on tables that were enabled by this migration."""
    for table in TABLES_WITH_EMPRESA_ID:
        if table in ALREADY_ENABLED:
            # Don't touch the original 4 — they predate this migration.
            op.execute(
                f"ALTER TABLE public.{table} NO FORCE ROW LEVEL SECURITY;"
            )
            continue

        # Drop policy first (must exist before disabling RLS)
        op.execute(
            f"DROP POLICY IF EXISTS tenant_isolation_{table} ON public.{table};"
        )
        op.execute(
            f"ALTER TABLE public.{table} NO FORCE ROW LEVEL SECURITY;"
        )
        op.execute(
            f"ALTER TABLE public.{table} DISABLE ROW LEVEL SECURITY;"
        )
