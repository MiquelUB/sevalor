"""a019: Pla 2 - Pont Magatzem -> Comptabilitat (PMP, Mermes, Costos OT i Tiquets OCR)

Revision ID: a019_pla2_magatzem_comptabilitat
Revises: a018_pla1_operari_telegram
Create Date: 2026-11-13
"""
from typing import Sequence, Union

from alembic import op

revision: str = "a019_pla2_magatzem_comptabilitat"
down_revision: Union[str, Sequence[str], None] = "a018_pla1_operari_telegram"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    statements = [
        """
        ALTER TABLE articles
            ADD COLUMN IF NOT EXISTS pmp_actual NUMERIC(12, 4) NOT NULL DEFAULT 0.0000,
            ADD COLUMN IF NOT EXISTS ultim_preu_compra NUMERIC(12, 4) NOT NULL DEFAULT 0.0000,
            ADD COLUMN IF NOT EXISTS estoc_total_actual NUMERIC(12, 3) NOT NULL DEFAULT 0.000,
            ADD COLUMN IF NOT EXISTS estoc_slot_residus NUMERIC(12, 3) NOT NULL DEFAULT 0.000,
            ADD COLUMN IF NOT EXISTS es_custodia_rma_client BOOLEAN NOT NULL DEFAULT false
        """,
        """
        UPDATE articles
        SET pmp_actual = COALESCE(NULLIF(preu_cost_mitja, 0), preu_cost, 0),
            ultim_preu_compra = COALESCE(NULLIF(preu_cost_ultim, 0), preu_cost, 0)
        WHERE pmp_actual = 0
        """,
        """
        ALTER TABLE vehicles
            ADD COLUMN IF NOT EXISTS targeta_combustible_bloquejada BOOLEAN NOT NULL DEFAULT false
        """,
        """
        ALTER TABLE ordres_treball
            ADD COLUMN IF NOT EXISTS cost_materials_picking_pmp NUMERIC(12, 2) NOT NULL DEFAULT 0.00,
            ADD COLUMN IF NOT EXISTS cost_ma_obra_real NUMERIC(12, 2) NOT NULL DEFAULT 0.00,
            ADD COLUMN IF NOT EXISTS cost_flota_real NUMERIC(12, 2) NOT NULL DEFAULT 0.00,
            ADD COLUMN IF NOT EXISTS import_pressupostat_net NUMERIC(12, 2) NOT NULL DEFAULT 0.00
        """,
        """
        ALTER TABLE tiquets_despesa
            ALTER COLUMN estat_aprovacio TYPE VARCHAR(50),
            ALTER COLUMN subcompte_pgc TYPE VARCHAR(40)
        """,
        """
        CREATE TABLE IF NOT EXISTS mermes_inventari (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            empresa_id UUID NOT NULL REFERENCES empreses(id) ON DELETE CASCADE,
            article_id UUID NOT NULL REFERENCES articles(id) ON DELETE CASCADE,
            magatzem_id UUID NOT NULL REFERENCES magatzems(id) ON DELETE CASCADE,
            ordre_treball_id UUID REFERENCES ordres_treball(id) ON DELETE SET NULL,
            usuari_id UUID REFERENCES usuaris(id) ON DELETE SET NULL,
            quantitat NUMERIC(12, 3) NOT NULL,
            pmp_aplicat NUMERIC(12, 4) NOT NULL,
            cost_total NUMERIC(12, 2) NOT NULL,
            motiu VARCHAR(50) NOT NULL,
            subcompte_comptable VARCHAR(40) NOT NULL,
            transferit_slot_residus BOOLEAN NOT NULL DEFAULT true,
            notes TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS despeses_comptables (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            empresa_id UUID NOT NULL REFERENCES empreses(id) ON DELETE CASCADE,
            ordre_treball_id UUID REFERENCES ordres_treball(id) ON DELETE SET NULL,
            tiquet_id UUID REFERENCES tiquets_despesa(id) ON DELETE SET NULL,
            merma_id UUID REFERENCES mermes_inventari(id) ON DELETE SET NULL,
            concepte VARCHAR(500) NOT NULL,
            subcompte VARCHAR(40) NOT NULL,
            base_imposable NUMERIC(12, 2) NOT NULL DEFAULT 0.00,
            quota_iva NUMERIC(12, 2) NOT NULL DEFAULT 0.00,
            import_total NUMERIC(12, 2) NOT NULL DEFAULT 0.00,
            estat VARCHAR(40) NOT NULL DEFAULT 'PENDENT_VALIDACIO',
            origen VARCHAR(40) NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """,
        "CREATE INDEX IF NOT EXISTS idx_mermes_empresa_ot ON mermes_inventari(empresa_id, ordre_treball_id)",
        "CREATE INDEX IF NOT EXISTS idx_mermes_empresa_art ON mermes_inventari(empresa_id, article_id, created_at)",
        "CREATE INDEX IF NOT EXISTS idx_despeses_comp_empresa_ot ON despeses_comptables(empresa_id, ordre_treball_id)",
        "CREATE INDEX IF NOT EXISTS idx_despeses_comp_empresa_origen ON despeses_comptables(empresa_id, origen, created_at)",
    ]

    for table_name in ("mermes_inventari", "despeses_comptables"):
        statements.extend(
            [
                f"ALTER TABLE {table_name} ENABLE ROW LEVEL SECURITY",
                f"ALTER TABLE {table_name} FORCE ROW LEVEL SECURITY",
                f"DROP POLICY IF EXISTS rls_tenant_isolation ON {table_name}",
                f"""
                CREATE POLICY rls_tenant_isolation ON {table_name}
                    USING (empresa_id = NULLIF(current_setting('app.current_empresa_id', true), '')::uuid)
                    WITH CHECK (empresa_id = NULLIF(current_setting('app.current_empresa_id', true), '')::uuid)
                """,
            ]
        )

    for stmt in statements:
        op.execute(stmt)


def downgrade() -> None:
    statements = [
        "DROP TABLE IF EXISTS despeses_comptables CASCADE",
        "DROP TABLE IF EXISTS mermes_inventari CASCADE",
        """
        ALTER TABLE ordres_treball
            DROP COLUMN IF EXISTS import_pressupostat_net,
            DROP COLUMN IF EXISTS cost_flota_real,
            DROP COLUMN IF EXISTS cost_ma_obra_real,
            DROP COLUMN IF EXISTS cost_materials_picking_pmp
        """,
        """
        ALTER TABLE vehicles
            DROP COLUMN IF EXISTS targeta_combustible_bloquejada
        """,
        """
        ALTER TABLE articles
            DROP COLUMN IF EXISTS es_custodia_rma_client,
            DROP COLUMN IF EXISTS estoc_slot_residus,
            DROP COLUMN IF EXISTS estoc_total_actual,
            DROP COLUMN IF EXISTS ultim_preu_compra,
            DROP COLUMN IF EXISTS pmp_actual
        """,
    ]
    for stmt in statements:
        op.execute(stmt)
