"""T013: Afegir camps de financament, regims i odometre de contracte a vehicles

Revision ID: a013_flota_regims_i_odometre
Revises: a012_ot_planol_i_eina_custodia
Create Date: 2026-11-10
"""
from typing import Sequence, Union

from alembic import op


revision: str = "a013_flota_regims_i_odometre"
down_revision: Union[str, Sequence[str], None] = "a012_ot_planol_i_eina_custodia"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Odometre inicial del contracte i dates de contracte
    op.execute(
        "ALTER TABLE vehicles ADD COLUMN IF NOT EXISTS odometre_inici_contracte INTEGER DEFAULT 0 NOT NULL;"
    )
    op.execute(
        "ALTER TABLE vehicles ADD COLUMN IF NOT EXISTS data_inici_contracte DATE;"
    )
    op.execute(
        "ALTER TABLE vehicles ADD COLUMN IF NOT EXISTS data_fi_contracte DATE;"
    )

    # 2. Camps economics i financers (Renting, Leasing, Lloguer, Amortitzacio)
    op.execute(
        "ALTER TABLE vehicles ADD COLUMN IF NOT EXISTS quota_mensual_eur NUMERIC(10, 2) DEFAULT 0.00 NOT NULL;"
    )
    op.execute(
        "ALTER TABLE vehicles ADD COLUMN IF NOT EXISTS tarifa_diaria_eur NUMERIC(10, 2) DEFAULT 0.00 NOT NULL;"
    )
    op.execute(
        "ALTER TABLE vehicles ADD COLUMN IF NOT EXISTS preu_km_exces_eur NUMERIC(6, 4) DEFAULT 0.0000 NOT NULL;"
    )
    op.execute(
        "ALTER TABLE vehicles ADD COLUMN IF NOT EXISTS valor_residual_eur NUMERIC(10, 2);"
    )
    op.execute(
        "ALTER TABLE vehicles ADD COLUMN IF NOT EXISTS fianca_eur NUMERIC(10, 2);"
    )

    # 3. Manteniment, garantia, anomalies i alertes legals (FR-011 / US4 / Spec 006)
    op.execute(
        "ALTER TABLE vehicles ADD COLUMN IF NOT EXISTS data_fi_garantia_oficial DATE;"
    )
    op.execute(
        "ALTER TABLE vehicles ADD COLUMN IF NOT EXISTS interval_canvi_oli_km INTEGER DEFAULT 15000;"
    )
    op.execute(
        "ALTER TABLE vehicles ADD COLUMN IF NOT EXISTS ultim_canvi_oli_km INTEGER DEFAULT 0;"
    )
    op.execute(
        "ALTER TABLE vehicles ADD COLUMN IF NOT EXISTS anomalia_consum_descartada BOOLEAN DEFAULT FALSE NOT NULL;"
    )
    op.execute(
        "ALTER TABLE vehicles ADD COLUMN IF NOT EXISTS data_itv_negativa DATE;"
    )
    op.execute(
        "ALTER TABLE vehicles ADD COLUMN IF NOT EXISTS data_ultima_descarrega_tacograf DATE;"
    )

    # 4. Normalitzacio d'estat ASSIGNAT -> OPERATIU i reconciliacio 1:1 bidireccional
    op.execute(
        "UPDATE vehicles SET estat = 'OPERATIU' WHERE estat = 'ASSIGNAT';"
    )
    op.execute(
        """
        UPDATE usuaris u
        SET vehicle_assignat_id = v.id
        FROM vehicles v
        WHERE v.conductor_habitual_id = u.id
          AND v.empresa_id = u.empresa_id
          AND u.vehicle_assignat_id IS NULL;
        """
    )
    op.execute(
        """
        UPDATE vehicles v
        SET conductor_habitual_id = u.id
        FROM usuaris u
        WHERE u.vehicle_assignat_id = v.id
          AND u.empresa_id = v.empresa_id
          AND v.conductor_habitual_id IS NULL;
        """
    )


def downgrade() -> None:
    op.execute("ALTER TABLE vehicles DROP COLUMN IF EXISTS data_ultima_descarrega_tacograf;")
    op.execute("ALTER TABLE vehicles DROP COLUMN IF EXISTS data_itv_negativa;")
    op.execute("ALTER TABLE vehicles DROP COLUMN IF EXISTS anomalia_consum_descartada;")
    op.execute("ALTER TABLE vehicles DROP COLUMN IF EXISTS ultim_canvi_oli_km;")
    op.execute("ALTER TABLE vehicles DROP COLUMN IF EXISTS interval_canvi_oli_km;")
    op.execute("ALTER TABLE vehicles DROP COLUMN IF EXISTS data_fi_garantia_oficial;")
    op.execute("ALTER TABLE vehicles DROP COLUMN IF EXISTS fianca_eur;")
    op.execute("ALTER TABLE vehicles DROP COLUMN IF EXISTS valor_residual_eur;")
    op.execute("ALTER TABLE vehicles DROP COLUMN IF EXISTS preu_km_exces_eur;")
    op.execute("ALTER TABLE vehicles DROP COLUMN IF EXISTS tarifa_diaria_eur;")
    op.execute("ALTER TABLE vehicles DROP COLUMN IF EXISTS quota_mensual_eur;")
    op.execute("ALTER TABLE vehicles DROP COLUMN IF EXISTS data_fi_contracte;")
    op.execute("ALTER TABLE vehicles DROP COLUMN IF EXISTS data_inici_contracte;")
    op.execute("ALTER TABLE vehicles DROP COLUMN IF EXISTS odometre_inici_contracte;")
