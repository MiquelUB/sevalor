"""a022: Taula de trams de temps multi-interval (obrir/tancar/reprendre) amb GPS per ordre de treball

Revision ID: a022_ordres_treball_trams_temps
Revises: a021_ordres_treball_gps_temps
Create Date: 2026-11-16
"""
from typing import Sequence, Union

from alembic import op

revision: str = "a022_ordres_treball_trams_temps"
down_revision: Union[str, Sequence[str], None] = "a021_ordres_treball_gps_temps"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS ordres_treball_trams_temps (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            empresa_id UUID NOT NULL REFERENCES empreses(id) ON DELETE CASCADE,
            ordre_treball_id UUID NOT NULL REFERENCES ordres_treball(id) ON DELETE CASCADE,
            operari_id UUID REFERENCES usuaris(id) ON DELETE SET NULL,
            hora_inici TIMESTAMPTZ NOT NULL DEFAULT now(),
            hora_fi TIMESTAMPTZ,
            gps_inici_lat NUMERIC(9, 6),
            gps_inici_lng NUMERIC(9, 6),
            gps_fi_lat NUMERIC(9, 6),
            gps_fi_lng NUMERIC(9, 6),
            durada_segons INTEGER NOT NULL DEFAULT 0,
            desviacio_geovalla BOOLEAN NOT NULL DEFAULT FALSE,
            justificacio_gps TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );
        """
    )

    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_ordres_treball_trams_temps_empresa_id ON ordres_treball_trams_temps(empresa_id);"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_ordres_treball_trams_temps_ordre_id ON ordres_treball_trams_temps(ordre_treball_id);"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_ordres_treball_trams_temps_operari_id ON ordres_treball_trams_temps(operari_id);"
    )

    op.execute("ALTER TABLE ordres_treball_trams_temps ENABLE ROW LEVEL SECURITY;")
    op.execute("ALTER TABLE ordres_treball_trams_temps FORCE ROW LEVEL SECURITY;")
    op.execute(
        "DROP POLICY IF EXISTS tenant_isolation_ordres_treball_trams_temps ON ordres_treball_trams_temps;"
    )
    op.execute(
        """
        CREATE POLICY tenant_isolation_ordres_treball_trams_temps ON ordres_treball_trams_temps
            USING (empresa_id = NULLIF(current_setting('app.current_empresa_id', true), '')::uuid)
            WITH CHECK (empresa_id = NULLIF(current_setting('app.current_empresa_id', true), '')::uuid);
        """
    )

    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'sevalor_app') THEN
                GRANT SELECT, INSERT, UPDATE, DELETE ON ordres_treball_trams_temps TO sevalor_app;
            END IF;
        END
        $$;
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS ordres_treball_trams_temps CASCADE;")
