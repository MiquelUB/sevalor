"""dummy baseline

Revision ID: db371c77b254
Revises: 
Create Date: 2026-09-11 16:31:22.833836

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = 'db371c77b254'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    pass

def downgrade() -> None:
    pass
