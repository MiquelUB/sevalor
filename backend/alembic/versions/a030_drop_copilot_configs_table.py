"""a030: Elimina la taula residual copilot_configs (Zero-Storage Hetzner -> copilot_profile.json al disc dedicat).

Revision ID: a030_drop_copilot_configs_table
Revises: a029_clients_web_i_contacte
Create Date: 2026-11-25
"""

from typing import Sequence, Union

from alembic import op

revision: str = "a030_drop_copilot_configs_table"
down_revision: Union[str, Sequence[str], None] = "a029_clients_web_i_contacte"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        "DROP POLICY IF EXISTS copilot_configs_strict_isolation ON public.copilot_configs"
    )
    op.execute("DROP TABLE IF EXISTS public.copilot_configs")


def downgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS public.copilot_configs (
            empresa_id UUID PRIMARY KEY REFERENCES public.empreses(id) ON DELETE CASCADE,
            system_prompt TEXT NOT NULL DEFAULT '',
            rag_prompt TEXT NOT NULL DEFAULT '',
            subagent_prompts JSONB NOT NULL DEFAULT '{}'::jsonb,
            llm_model VARCHAR(120) NOT NULL DEFAULT '',
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )
    op.execute("ALTER TABLE public.copilot_configs ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE public.copilot_configs FORCE ROW LEVEL SECURITY")
    op.execute(
        "DROP POLICY IF EXISTS copilot_configs_strict_isolation ON public.copilot_configs"
    )
    op.execute(
        """
        CREATE POLICY copilot_configs_strict_isolation ON public.copilot_configs
            FOR ALL
            USING (empresa_id = NULLIF(current_setting('app.current_empresa_id', true), '')::uuid)
            WITH CHECK (empresa_id = NULLIF(current_setting('app.current_empresa_id', true), '')::uuid)
        """
    )
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'sevalor_app') THEN
                GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE public.copilot_configs TO sevalor_app;
            END IF;
        END
        $$
        """
    )
