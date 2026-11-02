"""T010: Afegir disc_dur_url a Empresa

Revision ID: a010_disc_dur_url
Revises: a009_empreses_rls_grants
Create Date: 2026-11-02
"""
from typing import Sequence, Union

from alembic import op

revision: str = "a010_disc_dur_url"
down_revision: Union[str, Sequence[str], None] = "a009_empreses_rls_grants"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TABLE empreses ADD COLUMN IF NOT EXISTS disc_dur_url VARCHAR(255)")


def downgrade() -> None:
    op.execute("ALTER TABLE empreses DROP COLUMN IF EXISTS disc_dur_url")
