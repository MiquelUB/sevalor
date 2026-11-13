"""a018: Pla 1 - Telegram OTP Enrolament, Seguretat PIN i Tiquets Zero-Tecleig

Revision ID: a018_pla1_operari_telegram
Revises: a017_spec007_economic_suite
Create Date: 2026-11-13
"""
from typing import Sequence, Union

from alembic import op

revision: str = "a018_pla1_operari_telegram"
down_revision: Union[str, Sequence[str], None] = "a017_spec007_economic_suite"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    statements = [
        """
        ALTER TABLE usuaris
            ADD COLUMN IF NOT EXISTS telegram_chat_id BIGINT,
            ADD COLUMN IF NOT EXISTS dispositiu_referencia VARCHAR(255),
            ADD COLUMN IF NOT EXISTS requereix_rexifrat_idb BOOLEAN NOT NULL DEFAULT false
        """,
        """
        ALTER TABLE incidencies
            ADD COLUMN IF NOT EXISTS tipus VARCHAR(60),
            ADD COLUMN IF NOT EXISTS gravetat VARCHAR(20)
        """,
        """
        ALTER TABLE tiquets_despesa
            ALTER COLUMN base_imposable DROP NOT NULL,
            ALTER COLUMN import_total DROP NOT NULL,
            ALTER COLUMN data_tiquet SET DEFAULT CURRENT_DATE
        """,
        """
        ALTER TABLE tiquets_despesa
            ADD COLUMN IF NOT EXISTS nom_fitxer_visible VARCHAR(255),
            ADD COLUMN IF NOT EXISTS foto_odometre_path VARCHAR(500),
            ADD COLUMN IF NOT EXISTS nif_comprador VARCHAR(20)
        """,
    ]
    for stmt in statements:
        op.execute(stmt)


def downgrade() -> None:
    statements = [
        """
        ALTER TABLE tiquets_despesa
            DROP COLUMN IF EXISTS nif_comprador,
            DROP COLUMN IF EXISTS foto_odometre_path,
            DROP COLUMN IF EXISTS nom_fitxer_visible
        """,
        """
        ALTER TABLE incidencies
            DROP COLUMN IF EXISTS gravetat,
            DROP COLUMN IF EXISTS tipus
        """,
        """
        ALTER TABLE usuaris
            DROP COLUMN IF EXISTS requereix_rexifrat_idb,
            DROP COLUMN IF EXISTS dispositiu_referencia,
            DROP COLUMN IF EXISTS telegram_chat_id
        """,
    ]
    for stmt in statements:
        op.execute(stmt)
