"""a032: Afegeix columnes de posició GPS real (ultima_latitud, ultima_longitud, ultima_posicio_at) a public.usuaris.

Revision ID: a032_usuari_posicio_gps
Revises: a031_zero_storage_xat_copilot
Create Date: 2026-11-27
"""

from typing import Sequence, Union

from alembic import op

revision: str = "a032_usuari_posicio_gps"
down_revision: Union[str, Sequence[str], None] = "a031_zero_storage_xat_copilot"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE public.usuaris
            ADD COLUMN IF NOT EXISTS ultima_latitud NUMERIC(9, 6),
            ADD COLUMN IF NOT EXISTS ultima_longitud NUMERIC(9, 6),
            ADD COLUMN IF NOT EXISTS ultima_posicio_at TIMESTAMPTZ;
        """
    )


def downgrade() -> None:
    op.execute(
        """
        ALTER TABLE public.usuaris
            DROP COLUMN IF EXISTS ultima_posicio_at,
            DROP COLUMN IF EXISTS ultima_longitud,
            DROP COLUMN IF EXISTS ultima_latitud;
        """
    )
