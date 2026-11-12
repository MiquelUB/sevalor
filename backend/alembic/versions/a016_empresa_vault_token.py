"""a016: Columna dedicada vault_token a empreses (desacoblat de Telegram)

Revision ID: a016_empresa_vault_token
Revises: a015_colla_ordres_treball
Create Date: 2026-11-12
"""
from typing import Sequence, Union

from alembic import op

revision: str = "a016_empresa_vault_token"
down_revision: Union[str, Sequence[str], None] = "a015_colla_ordres_treball"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TABLE empreses ADD COLUMN IF NOT EXISTS vault_token VARCHAR(255)")
    op.execute(
        """
        UPDATE empreses
        SET vault_token = telegram_webhook_secret,
            telegram_webhook_secret = NULL
        WHERE vault_token IS NULL
          AND telegram_webhook_secret LIKE 'svlt\\_%' ESCAPE '\\'
        """
    )


def downgrade() -> None:
    op.execute(
        """
        UPDATE empreses
        SET telegram_webhook_secret = vault_token
        WHERE telegram_webhook_secret IS NULL
          AND vault_token IS NOT NULL
        """
    )
    op.execute("ALTER TABLE empreses DROP COLUMN IF EXISTS vault_token")
