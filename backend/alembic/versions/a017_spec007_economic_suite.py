"""a017: Spec 007 v5.0 Suite Econòmica, Retencions, Tiquets, MRR, Norma 43 i Trigger SIF

Revision ID: a017_spec007_economic_suite
Revises: a016_empresa_vault_token
Create Date: 2026-11-13
"""
from typing import Sequence, Union

from alembic import op

revision: str = "a017_spec007_economic_suite"
down_revision: Union[str, Sequence[str], None] = "a016_empresa_vault_token"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    statements = [
        # 1. Ampliació de taules existents (una sentència per op.execute per asyncpg)
        """
        ALTER TABLE usuaris
            ADD COLUMN IF NOT EXISTS es_alta_direccio BOOLEAN NOT NULL DEFAULT false,
            ADD COLUMN IF NOT EXISTS cost_hora_referencia NUMERIC(8, 2) NOT NULL DEFAULT 22.50,
            ADD COLUMN IF NOT EXISTS salari_mensual_brut NUMERIC(10, 2) NOT NULL DEFAULT 0.00,
            ADD COLUMN IF NOT EXISTS cost_ss_mensual NUMERIC(10, 2) NOT NULL DEFAULT 0.00
        """,
        """
        ALTER TABLE registres_jornada_laboral
            ADD COLUMN IF NOT EXISTS hores_imputades_ot NUMERIC(6, 2) NOT NULL DEFAULT 0.00
        """,
        """
        ALTER TABLE clients
            ADD COLUMN IF NOT EXISTS limit_risc_credit NUMERIC(12, 2) NOT NULL DEFAULT 15000.00,
            ADD COLUMN IF NOT EXISTS estat_risc_operatiu VARCHAR(30) NOT NULL DEFAULT 'APTE',
            ADD COLUMN IF NOT EXISTS motiu_override_risc TEXT,
            ADD COLUMN IF NOT EXISTS override_boss_usuari_id UUID,
            ADD COLUMN IF NOT EXISTS data_override_risc TIMESTAMPTZ
        """,
        """
        ALTER TABLE articles
            ADD COLUMN IF NOT EXISTS preu_cost_ultim NUMERIC(12, 4) NOT NULL DEFAULT 0.0000,
            ADD COLUMN IF NOT EXISTS preu_cost_mitja NUMERIC(12, 4) NOT NULL DEFAULT 0.0000,
            ADD COLUMN IF NOT EXISTS llindar_marge_minim_pct NUMERIC(5, 2) NOT NULL DEFAULT 25.00,
            ADD COLUMN IF NOT EXISTS es_diposit_proveidor BOOLEAN NOT NULL DEFAULT false,
            ADD COLUMN IF NOT EXISTS darrer_moviment_sortida DATE
        """,
        """
        ALTER TABLE vehicles
            ADD COLUMN IF NOT EXISTS km_inicials_mes INTEGER NOT NULL DEFAULT 0,
            ADD COLUMN IF NOT EXISTS despeses_taller_mes NUMERIC(10, 2) NOT NULL DEFAULT 0.00
        """,
        """
        ALTER TABLE factures_proveidor
            ADD COLUMN IF NOT EXISTS data_venciment DATE,
            ADD COLUMN IF NOT EXISTS data_pagament_real DATE,
            ADD COLUMN IF NOT EXISTS import_retencio_garantia_4008 NUMERIC(12, 2) NOT NULL DEFAULT 0.00,
            ADD COLUMN IF NOT EXISTS import_pagat NUMERIC(12, 2) NOT NULL DEFAULT 0.00,
            ADD COLUMN IF NOT EXISTS es_recc_passiu_4729 BOOLEAN NOT NULL DEFAULT false,
            ADD COLUMN IF NOT EXISTS pagada BOOLEAN NOT NULL DEFAULT false,
            ADD COLUMN IF NOT EXISTS estat_pagament VARCHAR(40) NOT NULL DEFAULT 'PENDENT'
        """,
        """
        ALTER TABLE ordres_treball
            ADD COLUMN IF NOT EXISTS contracte_mrr_id UUID,
            ADD COLUMN IF NOT EXISTS vertical VARCHAR(50) NOT NULL DEFAULT 'INSTAL_LACIONS',
            ADD COLUMN IF NOT EXISTS data_finalitzacio_camp DATE,
            ADD COLUMN IF NOT EXISTS factura_id UUID,
            ADD COLUMN IF NOT EXISTS import_pressupostat NUMERIC(12, 2) NOT NULL DEFAULT 0.00,
            ADD COLUMN IF NOT EXISTS hores_imputades_facturables NUMERIC(8, 2) NOT NULL DEFAULT 0.00,
            ADD COLUMN IF NOT EXISTS preu_venda_hora_aplicat NUMERIC(8, 2) NOT NULL DEFAULT 45.00,
            ADD COLUMN IF NOT EXISTS cost_materials_pmp NUMERIC(12, 2) NOT NULL DEFAULT 0.00,
            ADD COLUMN IF NOT EXISTS pvp_materials_aplicat NUMERIC(12, 2) NOT NULL DEFAULT 0.00,
            ADD COLUMN IF NOT EXISTS km_imputats INTEGER NOT NULL DEFAULT 0
        """,
        """
        ALTER TABLE factures_capcalera
            ADD COLUMN IF NOT EXISTS estat_document VARCHAR(30) NOT NULL DEFAULT 'EMESA',
            ADD COLUMN IF NOT EXISTS data_venciment DATE,
            ADD COLUMN IF NOT EXISTS data_cobrament_real DATE,
            ADD COLUMN IF NOT EXISTS metode_pagament VARCHAR(30) NOT NULL DEFAULT 'TRANSFERENCIA',
            ADD COLUMN IF NOT EXISTS es_inversio_subjecte_passiu BOOLEAN NOT NULL DEFAULT false,
            ADD COLUMN IF NOT EXISTS justificant_suplerts_pdf_path VARCHAR(500),
            ADD COLUMN IF NOT EXISTS import_retencio_garantia_4308 NUMERIC(12, 2) NOT NULL DEFAULT 0.00,
            ADD COLUMN IF NOT EXISTS import_cobrat NUMERIC(12, 2) NOT NULL DEFAULT 0.00,
            ADD COLUMN IF NOT EXISTS factura_rectificada_id UUID REFERENCES factures_capcalera(id) ON DELETE RESTRICT,
            ADD COLUMN IF NOT EXISTS motiu_rectificacio TEXT,
            ADD COLUMN IF NOT EXISTS estat_art80 VARCHAR(40) NOT NULL DEFAULT 'NO_APLICA',
            ADD COLUMN IF NOT EXISTS justificant_reclamacio_art80_path VARCHAR(500),
            ADD COLUMN IF NOT EXISTS qr_verifactu_payload TEXT
        """,
        """
        ALTER TABLE factures_linies
            ADD COLUMN IF NOT EXISTS compte_pgc VARCHAR(10) NOT NULL DEFAULT '700000',
            ADD COLUMN IF NOT EXISTS quantitat_merma NUMERIC(10, 2) NOT NULL DEFAULT 0.00,
            ADD COLUMN IF NOT EXISTS descompte_aplicat_pct NUMERIC(5, 2) NOT NULL DEFAULT 0.00,
            ADD COLUMN IF NOT EXISTS cost_unitari_historic NUMERIC(12, 4) NOT NULL DEFAULT 0.0000
        """,
        # 2. Noves taules
        """
        CREATE TABLE IF NOT EXISTS contractes_manteniment_mrr (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            empresa_id UUID NOT NULL REFERENCES empreses(id) ON DELETE CASCADE,
            client_id UUID NOT NULL REFERENCES clients(id) ON DELETE RESTRICT,
            codi_contracte VARCHAR(50) NOT NULL,
            quota_mensual_mrr NUMERIC(12, 2) NOT NULL,
            data_inici DATE NOT NULL,
            data_fi DATE,
            actiu BOOLEAN NOT NULL DEFAULT true,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS series_fiscals_verifactu (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            empresa_id UUID NOT NULL REFERENCES empreses(id) ON DELETE CASCADE,
            codi_serie VARCHAR(20) NOT NULL,
            exercici INTEGER NOT NULL,
            ultim_numero INTEGER NOT NULL DEFAULT 0,
            ultim_hash_sha256 VARCHAR(64) NOT NULL DEFAULT repeat('0', 64),
            CONSTRAINT uq_serie_empresa_exercici UNIQUE (empresa_id, codi_serie, exercici)
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS retencions_garantia (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            empresa_id UUID NOT NULL REFERENCES empreses(id) ON DELETE CASCADE,
            tipus VARCHAR(30) NOT NULL,
            factura_client_id UUID REFERENCES factures_capcalera(id) ON DELETE SET NULL,
            factura_proveidor_id UUID REFERENCES factures_proveidor(id) ON DELETE SET NULL,
            client_id UUID REFERENCES clients(id) ON DELETE SET NULL,
            obra_id UUID REFERENCES ordres_treball(id) ON DELETE SET NULL,
            import_retingut NUMERIC(12, 2) NOT NULL,
            percentatge_aplicat NUMERIC(5, 2) NOT NULL DEFAULT 5.00,
            data_retencio DATE NOT NULL,
            data_venciment_garantia DATE NOT NULL,
            estat VARCHAR(30) NOT NULL DEFAULT 'RETINGUDA',
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS tiquets_despesa (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            empresa_id UUID NOT NULL REFERENCES empreses(id) ON DELETE CASCADE,
            categoria VARCHAR(30) NOT NULL,
            usuari_id UUID NOT NULL REFERENCES usuaris(id) ON DELETE RESTRICT,
            vehicle_id UUID REFERENCES vehicles(id) ON DELETE SET NULL,
            ordre_treball_id UUID REFERENCES ordres_treball(id) ON DELETE SET NULL,
            data_tiquet DATE NOT NULL,
            nif_emissor VARCHAR(20),
            rao_social VARCHAR(255),
            base_imposable NUMERIC(10, 2) NOT NULL,
            iva_pct NUMERIC(5, 2) NOT NULL DEFAULT 21.00,
            quota_iva NUMERIC(10, 2) NOT NULL DEFAULT 0.00,
            import_total NUMERIC(10, 2) NOT NULL,
            subcompte_pgc VARCHAR(10) NOT NULL DEFAULT '629000',
            estat_aprovacio VARCHAR(30) NOT NULL DEFAULT 'PENDENT_AUDITORIA',
            estat_fiscal VARCHAR(30) NOT NULL DEFAULT 'DEDUIBLE',
            requereix_aprovacio_boss BOOLEAN NOT NULL DEFAULT false,
            custodia_paper_confirmada BOOLEAN NOT NULL DEFAULT false,
            foto_tiquet_path VARCHAR(500),
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS despeses_fixes_recurrents (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            empresa_id UUID NOT NULL REFERENCES empreses(id) ON DELETE CASCADE,
            concepte VARCHAR(255) NOT NULL,
            categoria VARCHAR(50) NOT NULL,
            import_base NUMERIC(12, 2) NOT NULL,
            quota_iva NUMERIC(12, 2) NOT NULL DEFAULT 0.00,
            periodicitat VARCHAR(20) NOT NULL DEFAULT 'MENSUAL',
            dia_carrec INTEGER NOT NULL DEFAULT 5,
            actiu BOOLEAN NOT NULL DEFAULT true,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS apunts_bancaris_norma43 (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            empresa_id UUID NOT NULL REFERENCES empreses(id) ON DELETE CASCADE,
            data_operacio DATE NOT NULL,
            concepte VARCHAR(500) NOT NULL,
            import_moviment NUMERIC(12, 2) NOT NULL,
            divisa VARCHAR(3) NOT NULL DEFAULT 'EUR',
            saldo_resultant NUMERIC(14, 2) NOT NULL,
            huella_sha256 VARCHAR(64) NOT NULL,
            conciliat BOOLEAN NOT NULL DEFAULT false,
            factura_conciliada_id UUID REFERENCES factures_capcalera(id) ON DELETE SET NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            CONSTRAINT uq_norma43_huella UNIQUE (empresa_id, huella_sha256)
        )
        """,
        # 3. Índexs
        "CREATE INDEX IF NOT EXISTS idx_mrr_empresa_actiu ON contractes_manteniment_mrr(empresa_id, actiu)",
        "CREATE INDEX IF NOT EXISTS idx_retencions_empresa_estat ON retencions_garantia(empresa_id, estat, data_venciment_garantia)",
        "CREATE INDEX IF NOT EXISTS idx_tiquets_despesa_empresa_estat ON tiquets_despesa(empresa_id, estat_aprovacio, data_tiquet)",
        "CREATE INDEX IF NOT EXISTS idx_despeses_fixes_empresa_actiu ON despeses_fixes_recurrents(empresa_id, actiu)",
        "CREATE INDEX IF NOT EXISTS idx_factures_cap_empresa_venc ON factures_capcalera(empresa_id, estat_cobrament, data_venciment)",
        "CREATE INDEX IF NOT EXISTS idx_ot_empresa_wip ON ordres_treball(empresa_id, estat) WHERE factura_id IS NULL",
        # 4. Trigger SIF Append-Only
        """
        CREATE OR REPLACE FUNCTION fn_prevent_sif_mutation()
        RETURNS TRIGGER AS $$
        BEGIN
            RAISE EXCEPTION 'SIF_IMMUTABLE_VIOLATION: El Registre d Esdeveniments SIF és Append-Only i no permet UPDATE ni DELETE.';
        END;
        $$ LANGUAGE plpgsql
        """,
        "DROP TRIGGER IF EXISTS trg_sif_immutable ON registre_esdeveniments_sif",
        """
        CREATE TRIGGER trg_sif_immutable
        BEFORE UPDATE OR DELETE ON registre_esdeveniments_sif
        FOR EACH ROW EXECUTE FUNCTION fn_prevent_sif_mutation()
        """,
    ]

    for table_name in (
        "contractes_manteniment_mrr",
        "series_fiscals_verifactu",
        "retencions_garantia",
        "tiquets_despesa",
        "despeses_fixes_recurrents",
        "apunts_bancaris_norma43",
    ):
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
    op.execute("DROP TRIGGER IF EXISTS trg_sif_immutable ON registre_esdeveniments_sif")
    op.execute("DROP FUNCTION IF EXISTS fn_prevent_sif_mutation()")

    for table_name in (
        "apunts_bancaris_norma43",
        "despeses_fixes_recurrents",
        "tiquets_despesa",
        "retencions_garantia",
        "series_fiscals_verifactu",
        "contractes_manteniment_mrr",
    ):
        op.execute(f"DROP TABLE IF EXISTS {table_name} CASCADE")
