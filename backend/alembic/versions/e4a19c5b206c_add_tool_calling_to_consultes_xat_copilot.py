"""Add tool calling fields to consultes_xat_copilot

Revision ID: e4a19c5b206c
Revises: 3a5a206b1bed
Create Date: 2026-09-23 15:45:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'e4a19c5b206c'
down_revision: Union[str, Sequence[str], None] = '3a5a206b1bed'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('consultes_xat_copilot', sa.Column('tool_name', sa.String(length=100), nullable=True))
    op.add_column('consultes_xat_copilot', sa.Column('tool_args', postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    op.add_column('consultes_xat_copilot', sa.Column('tool_result', postgresql.JSONB(astext_type=sa.Text()), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('consultes_xat_copilot', 'tool_result')
    op.drop_column('consultes_xat_copilot', 'tool_args')
    op.drop_column('consultes_xat_copilot', 'tool_name')
