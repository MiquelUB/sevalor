"""T012: Afegir planol_id a ordres_treball i ordre_treball_id a eines_custodia

Revision ID: a012_ot_planol_i_eina_custodia
Revises: a011_expand_nom_articles_i_eines
Create Date: 2026-11-02
"""
from typing import Sequence, Union

from alembic import op

revision: str = "a012_ot_planol_i_eina_custodia"
down_revision: Union[str, Sequence[str], None] = "a011_expand_nom_articles_i_eines"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE ordres_treball ADD COLUMN IF NOT EXISTS planol_id UUID "
        "REFERENCES planols_base(id) ON DELETE SET NULL;"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_ordres_treball_planol_id ON ordres_treball(planol_id);"
    )
    op.execute(
        "ALTER TABLE eines_custodia ADD COLUMN IF NOT EXISTS ordre_treball_id UUID "
        "REFERENCES ordres_treball(id) ON DELETE SET NULL;"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_eines_custodia_ordre_treball_id ON eines_custodia(ordre_treball_id);"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_eines_custodia_ordre_treball_id;")
    op.execute("ALTER TABLE eines_custodia DROP COLUMN IF EXISTS ordre_treball_id;")
    op.execute("DROP INDEX IF EXISTS idx_ordres_treball_planol_id;")
    op.execute("ALTER TABLE ordres_treball DROP COLUMN IF EXISTS planol_id;")
