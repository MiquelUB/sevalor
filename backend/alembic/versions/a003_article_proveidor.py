"""Add proveidor_id to articles.

Revision ID: a003_article_proveidor
Revises: a002_rls_economics_boss_only
Create Date: 2026-10-12
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "a003_article_proveidor"
down_revision: Union[str, Sequence[str], None] = "a002_rls_economics_boss_only"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "articles",
        sa.Column(
            "proveidor_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("proveidors.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("articles", "proveidor_id")
