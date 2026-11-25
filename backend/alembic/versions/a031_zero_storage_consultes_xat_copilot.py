"""a031: Blinda Zero-Storage Hetzner a consultes_xat_copilot (pregunta/resposta nul·les + mode_resposta).

Revision ID: a031_zero_storage_consultes_xat_copilot
Revises: a030_drop_copilot_configs_table
Create Date: 2026-11-25
"""

from typing import Sequence, Union

from alembic import op

revision: str = "a031_zero_storage_xat_copilot"
down_revision: Union[str, Sequence[str], None] = "a030_drop_copilot_configs_table"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE public.consultes_xat_copilot ALTER COLUMN pregunta DROP NOT NULL"
    )
    op.execute(
        "ALTER TABLE public.consultes_xat_copilot ALTER COLUMN resposta DROP NOT NULL"
    )
    op.execute(
        "ALTER TABLE public.consultes_xat_copilot ADD COLUMN IF NOT EXISTS mode_resposta VARCHAR(40)"
    )
    op.execute(
        """
        UPDATE public.consultes_xat_copilot
        SET pregunta = NULL,
            resposta = NULL,
            tool_args = NULL,
            tool_result = NULL,
            enllacos_relacionats = '[]'::jsonb
        WHERE pregunta IS NOT NULL
           OR resposta IS NOT NULL
           OR tool_args IS NOT NULL
           OR tool_result IS NOT NULL
        """
    )


def downgrade() -> None:
    op.execute(
        """
        UPDATE public.consultes_xat_copilot
        SET pregunta = COALESCE(pregunta, ''),
            resposta = COALESCE(resposta, '')
        WHERE pregunta IS NULL OR resposta IS NULL
        """
    )
    op.execute(
        "ALTER TABLE public.consultes_xat_copilot DROP COLUMN IF EXISTS mode_resposta"
    )
    op.execute(
        "ALTER TABLE public.consultes_xat_copilot ALTER COLUMN resposta SET NOT NULL"
    )
    op.execute(
        "ALTER TABLE public.consultes_xat_copilot ALTER COLUMN pregunta SET NOT NULL"
    )
