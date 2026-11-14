"""a021: Afegir camps de temps real i GPS inici/final a ordres_treball

Revision ID: a021_ordres_treball_gps_temps
Revises: a020_superadmin_telemetry_schema
Create Date: 2026-11-14
"""
from typing import Sequence, Union

from alembic import op

revision: str = "a021_ordres_treball_gps_temps"
down_revision: Union[str, Sequence[str], None] = "a020_superadmin_telemetry_schema"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE ordres_treball
            ADD COLUMN IF NOT EXISTS hora_inici_real TIMESTAMPTZ,
            ADD COLUMN IF NOT EXISTS hora_fi_real TIMESTAMPTZ,
            ADD COLUMN IF NOT EXISTS gps_inici_lat NUMERIC(9, 6),
            ADD COLUMN IF NOT EXISTS gps_inici_lng NUMERIC(9, 6),
            ADD COLUMN IF NOT EXISTS gps_fi_lat NUMERIC(9, 6),
            ADD COLUMN IF NOT EXISTS gps_fi_lng NUMERIC(9, 6)
        """
    )


def downgrade() -> None:
    op.execute(
        """
        ALTER TABLE ordres_treball
            DROP COLUMN IF EXISTS gps_fi_lng,
            DROP COLUMN IF EXISTS gps_fi_lat,
            DROP COLUMN IF EXISTS gps_inici_lng,
            DROP COLUMN IF EXISTS gps_inici_lat,
            DROP COLUMN IF EXISTS hora_fi_real,
            DROP COLUMN IF EXISTS hora_inici_real
        """
    )
