"""a023: Afegeix magatzem_id a linies_picking per traçar el magatzem origen/destí exacte del picking

Revision ID: a023_picking_linia_magatzem
Revises: a022_ordres_treball_trams_temps
Create Date: 2026-11-17
"""
from typing import Sequence, Union

from alembic import op

revision: str = "a023_picking_linia_magatzem"
down_revision: Union[str, Sequence[str], None] = "a022_ordres_treball_trams_temps"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE linies_picking
            ADD COLUMN IF NOT EXISTS magatzem_id UUID REFERENCES magatzems(id) ON DELETE SET NULL;
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_linies_picking_magatzem_id ON linies_picking(magatzem_id);"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_linies_picking_magatzem_id;")
    op.execute("ALTER TABLE linies_picking DROP COLUMN IF EXISTS magatzem_id;")
