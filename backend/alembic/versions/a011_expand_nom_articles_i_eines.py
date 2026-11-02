"""T011: Ampliar longitud de nom a articles i eines_custodia

Revision ID: a011_expand_nom_articles_i_eines
Revises: a010_disc_dur_url
Create Date: 2026-11-02
"""
from typing import Sequence, Union

from alembic import op

revision: str = "a011_expand_nom_articles_i_eines"
down_revision: Union[str, Sequence[str], None] = "a010_disc_dur_url"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TABLE articles ALTER COLUMN nom TYPE VARCHAR(500);")
    op.execute("ALTER TABLE eines_custodia ALTER COLUMN nom TYPE VARCHAR(500);")


def downgrade() -> None:
    op.execute("ALTER TABLE articles ALTER COLUMN nom TYPE VARCHAR(150);")
    op.execute("ALTER TABLE eines_custodia ALTER COLUMN nom TYPE VARCHAR(150);")
