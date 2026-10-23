"""Afegir estat_domini a Empresa

Revision ID: a005_estat_domini
Revises: a004_superadmin_crm_verifactu
Create Date: 2026-10-23
"""
from typing import Sequence, Union

from alembic import op

revision: str = "a005_estat_domini"
down_revision: Union[str, Sequence[str], None] = "a004_superadmin_crm_verifactu"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE empreses ADD COLUMN IF NOT EXISTS estat_domini VARCHAR(30) NOT NULL DEFAULT 'NO_CONFIGURAT'"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE empreses DROP COLUMN IF EXISTS estat_domini")
