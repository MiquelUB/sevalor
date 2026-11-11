"""a014: Ampliacio flota pesants, renting estes i documents flota OCR

Revision ID: a014_flota_pesants_i_renting_ext
Revises: a013_flota_regims_i_odometre
Create Date: 2026-11-11
"""
from typing import Sequence, Union

from alembic import op

revision: str = "a014_flota_pesants_i_renting_ext"
down_revision: Union[str, Sequence[str], None] = "a013_flota_regims_i_odometre"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Ampliacio de taula vehicles (NIFs, Categoria UE, Pesos, CAP, Equipament, Renting i Dades Pesants)
    op.execute(
        "ALTER TABLE vehicles ADD COLUMN IF NOT EXISTS titular_nif VARCHAR(20);"
    )
    op.execute(
        "ALTER TABLE vehicles ADD COLUMN IF NOT EXISTS arrendatari_nif VARCHAR(20);"
    )
    op.execute(
        "ALTER TABLE vehicles ADD COLUMN IF NOT EXISTS codi_servei_dgt VARCHAR(10);"
    )
    op.execute(
        "ALTER TABLE vehicles ADD COLUMN IF NOT EXISTS categoria_ue VARCHAR(10);"
    )
    op.execute(
        "ALTER TABLE vehicles ADD COLUMN IF NOT EXISTS mma_kg INTEGER;"
    )
    op.execute(
        "ALTER TABLE vehicles ADD COLUMN IF NOT EXISTS tara_kg INTEGER;"
    )
    op.execute(
        "ALTER TABLE vehicles ADD COLUMN IF NOT EXISTS carrega_util_kg INTEGER;"
    )
    op.execute(
        "ALTER TABLE vehicles ADD COLUMN IF NOT EXISTS mmr_amb_fre_kg INTEGER;"
    )
    op.execute(
        "ALTER TABLE vehicles ADD COLUMN IF NOT EXISTS requereix_cap BOOLEAN DEFAULT FALSE NOT NULL;"
    )
    op.execute(
        "ALTER TABLE vehicles ADD COLUMN IF NOT EXISTS equipament_homologat JSONB DEFAULT '[]'::jsonb NOT NULL;"
    )
    op.execute(
        "ALTER TABLE vehicles ADD COLUMN IF NOT EXISTS certificats_prl_requerits JSONB DEFAULT '[]'::jsonb NOT NULL;"
    )
    op.execute(
        "ALTER TABLE vehicles ADD COLUMN IF NOT EXISTS empresa_renting VARCHAR(120);"
    )
    op.execute(
        "ALTER TABLE vehicles ADD COLUMN IF NOT EXISTS num_contracte_renting VARCHAR(80);"
    )
    op.execute(
        "ALTER TABLE vehicles ADD COLUMN IF NOT EXISTS data_venciment_renting DATE;"
    )
    op.execute(
        "ALTER TABLE vehicles ADD COLUMN IF NOT EXISTS dades_pesants JSONB;"
    )
    op.execute(
        "ALTER TABLE vehicles ADD COLUMN IF NOT EXISTS regulacio_pesants JSONB DEFAULT '{}'::jsonb;"
    )
    op.execute(
        "ALTER TABLE vehicles ADD COLUMN IF NOT EXISTS apte_assignacio_pwa BOOLEAN DEFAULT TRUE NOT NULL;"
    )
    op.execute(
        "ALTER TABLE vehicles ADD COLUMN IF NOT EXISTS estat_semafor VARCHAR(40) DEFAULT 'OPERATIU_OK' NOT NULL;"
    )

    # 2. Ampliacio de taula documents_flota (auditoria OCR i desglossament de tipus de document)
    op.execute(
        "ALTER TABLE documents_flota ADD COLUMN IF NOT EXISTS bastidor_detectat VARCHAR(30);"
    )
    op.execute(
        "ALTER TABLE documents_flota ADD COLUMN IF NOT EXISTS nif_detectat VARCHAR(20);"
    )
    op.execute(
        "ALTER TABLE documents_flota ADD COLUMN IF NOT EXISTS metadata_ocr JSONB;"
    )

    # 3. Check constraint idempotent per tipus_document
    op.execute("ALTER TABLE documents_flota DROP CONSTRAINT IF EXISTS chk_documents_flota_tipus;")
    op.execute(
        """
        ALTER TABLE documents_flota ADD CONSTRAINT chk_documents_flota_tipus
        CHECK (tipus_document IN (
            'ITV', 'FITXA_TECNICA', 'INFORME_ITV', 'ASSEGURANCA', 'REPARACIO',
            'CONTRACTE', 'CONTRACTE_RENTING', 'TARGETA_TRANSPORT', 'GENERAL', 'MANTENIMENT'
        ));
        """
    )


def downgrade() -> None:
    # 1. documents_flota
    op.execute("ALTER TABLE documents_flota DROP CONSTRAINT IF EXISTS chk_documents_flota_tipus;")
    op.execute("ALTER TABLE documents_flota DROP COLUMN IF EXISTS metadata_ocr;")
    op.execute("ALTER TABLE documents_flota DROP COLUMN IF EXISTS nif_detectat;")
    op.execute("ALTER TABLE documents_flota DROP COLUMN IF EXISTS bastidor_detectat;")

    # 2. vehicles
    op.execute("ALTER TABLE vehicles DROP COLUMN IF EXISTS estat_semafor;")
    op.execute("ALTER TABLE vehicles DROP COLUMN IF EXISTS apte_assignacio_pwa;")
    op.execute("ALTER TABLE vehicles DROP COLUMN IF EXISTS regulacio_pesants;")
    op.execute("ALTER TABLE vehicles DROP COLUMN IF EXISTS dades_pesants;")
    op.execute("ALTER TABLE vehicles DROP COLUMN IF EXISTS data_venciment_renting;")
    op.execute("ALTER TABLE vehicles DROP COLUMN IF EXISTS num_contracte_renting;")
    op.execute("ALTER TABLE vehicles DROP COLUMN IF EXISTS empresa_renting;")
    op.execute("ALTER TABLE vehicles DROP COLUMN IF EXISTS certificats_prl_requerits;")
    op.execute("ALTER TABLE vehicles DROP COLUMN IF EXISTS equipament_homologat;")
    op.execute("ALTER TABLE vehicles DROP COLUMN IF EXISTS requereix_cap;")
    op.execute("ALTER TABLE vehicles DROP COLUMN IF EXISTS mmr_amb_fre_kg;")
    op.execute("ALTER TABLE vehicles DROP COLUMN IF EXISTS carrega_util_kg;")
    op.execute("ALTER TABLE vehicles DROP COLUMN IF EXISTS tara_kg;")
    op.execute("ALTER TABLE vehicles DROP COLUMN IF EXISTS mma_kg;")
    op.execute("ALTER TABLE vehicles DROP COLUMN IF EXISTS categoria_ue;")
    op.execute("ALTER TABLE vehicles DROP COLUMN IF EXISTS codi_servei_dgt;")
    op.execute("ALTER TABLE vehicles DROP COLUMN IF EXISTS arrendatari_nif;")
    op.execute("ALTER TABLE vehicles DROP COLUMN IF EXISTS titular_nif;")
