"""a025: Crea la taula copilot_configs amb PK(empresa_id) i FORCE ROW LEVEL SECURITY

Revision ID: a025_add_copilot_configs_rls
Revises: a024_rls_accounting_roles
Create Date: 2026-11-20
"""

from typing import Sequence, Union

from alembic import op

revision: str = "a025_add_copilot_configs_rls"
down_revision: Union[str, Sequence[str], None] = "a024_rls_accounting_roles"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS public.copilot_configs (
            empresa_id UUID PRIMARY KEY REFERENCES public.empreses(id) ON DELETE CASCADE,
            system_prompt TEXT NOT NULL DEFAULT '',
            rag_prompt TEXT NOT NULL DEFAULT '',
            subagent_prompts JSONB NOT NULL DEFAULT '{}'::jsonb,
            llm_model VARCHAR(120) NOT NULL DEFAULT '',
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );

        ALTER TABLE public.copilot_configs ENABLE ROW LEVEL SECURITY;
        ALTER TABLE public.copilot_configs FORCE ROW LEVEL SECURITY;

        DROP POLICY IF EXISTS copilot_configs_strict_isolation ON public.copilot_configs;
        CREATE POLICY copilot_configs_strict_isolation ON public.copilot_configs
            FOR ALL
            USING (empresa_id = NULLIF(current_setting('app.current_empresa_id', true), '')::uuid)
            WITH CHECK (empresa_id = NULLIF(current_setting('app.current_empresa_id', true), '')::uuid);

        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'sevalor_app') THEN
                GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE public.copilot_configs TO sevalor_app;
            END IF;
        END
        $$;
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DROP POLICY IF EXISTS copilot_configs_strict_isolation ON public.copilot_configs;
        DROP TABLE IF EXISTS public.copilot_configs;
        """
    )
