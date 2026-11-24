"""a029: Afegeix camps web, persona_contacte i dades_contacte a public.clients.

Revision ID: a029_clients_web_i_contacte
Revises: a028_verifactu_hac1177_complet
Create Date: 2026-11-24
"""

from typing import Sequence, Union

from alembic import op

revision: str = "a029_clients_web_i_contacte"
down_revision: Union[str, Sequence[str], None] = "a028_verifactu_hac1177_complet"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE public.clients
            ADD COLUMN IF NOT EXISTS web VARCHAR(255),
            ADD COLUMN IF NOT EXISTS persona_contacte VARCHAR(150),
            ADD COLUMN IF NOT EXISTS dades_contacte TEXT;
        """
    )


def downgrade() -> None:
    op.execute(
        """
        ALTER TABLE public.clients
            DROP COLUMN IF EXISTS dades_contacte,
            DROP COLUMN IF EXISTS persona_contacte,
            DROP COLUMN IF EXISTS web;
        """
    )
