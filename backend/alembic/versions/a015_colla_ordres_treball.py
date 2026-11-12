"""a015: Assignacio de colla a ordres de treball (cap de colla + operaris)

Revision ID: a015_colla_ordres_treball
Revises: a014_flota_pesants_i_renting_ext
Create Date: 2026-11-12
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "a015_colla_ordres_treball"
down_revision: Union[str, Sequence[str], None] = "a014_flota_pesants_i_renting_ext"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Crear taula ordres_treball_operaris
    op.execute("""
    CREATE TABLE IF NOT EXISTS ordres_treball_operaris (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        empresa_id UUID NOT NULL REFERENCES empreses(id) ON DELETE CASCADE,
        ordre_treball_id UUID NOT NULL REFERENCES ordres_treball(id) ON DELETE CASCADE,
        operari_id UUID NOT NULL REFERENCES usuaris(id) ON DELETE CASCADE,
        es_cap_de_colla BOOLEAN NOT NULL DEFAULT FALSE,
        created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        CONSTRAINT uq_ordres_treball_operaris UNIQUE (empresa_id, ordre_treball_id, operari_id)
    )
    """)

    # 2. Indexos
    op.execute("CREATE INDEX IF NOT EXISTS ix_ordres_treball_operaris_empresa_id ON ordres_treball_operaris(empresa_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_ordres_treball_operaris_ordre_treball_id ON ordres_treball_operaris(ordre_treball_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_ordres_treball_operaris_operari_id ON ordres_treball_operaris(operari_id)")

    # 3. RLS i Politica d'Aïllament per Tenant
    op.execute("ALTER TABLE ordres_treball_operaris ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE ordres_treball_operaris FORCE ROW LEVEL SECURITY")
    op.execute("DROP POLICY IF EXISTS tenant_isolation_ordres_treball_operaris ON ordres_treball_operaris")
    op.execute("""
    CREATE POLICY tenant_isolation_ordres_treball_operaris ON ordres_treball_operaris
        USING (empresa_id = NULLIF(current_setting('app.current_empresa_id', true), '')::uuid)
        WITH CHECK (empresa_id = NULLIF(current_setting('app.current_empresa_id', true), '')::uuid)
    """)

    # 4. Concedir permisos al rol sevalor_app si existeix
    op.execute("""
    DO $$
    BEGIN
        IF EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'sevalor_app') THEN
            GRANT SELECT, INSERT, UPDATE, DELETE ON ordres_treball_operaris TO sevalor_app;
        END IF;
    END
    $$;
    """)

    # 5. Backfill d'ordres existents (crear registre per al cap_de_colla_id existent com a es_cap_de_colla=TRUE)
    op.execute("""
    INSERT INTO ordres_treball_operaris (id, empresa_id, ordre_treball_id, operari_id, es_cap_de_colla, created_at)
    SELECT gen_random_uuid(), ot.empresa_id, ot.id, ot.cap_de_colla_id, TRUE, now()
    FROM ordres_treball ot
    WHERE ot.cap_de_colla_id IS NOT NULL
    ON CONFLICT (empresa_id, ordre_treball_id, operari_id) DO NOTHING
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS ordres_treball_operaris CASCADE")
