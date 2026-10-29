"""Ampliació Spec 007: Geocodificació, Gatekeeper auditat i Embut de Descoberta.

Revision ID: a008_spec007_gatekeeper_i_cp_geocode
Revises: a007_prospeccio_leads_calendari
Create Date: 2026-10-28
"""
from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "a008_spec007_gk_cp"
down_revision: Union[str, Sequence[str], None] = "a007_prospeccio_leads_calendari"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    tables = insp.get_table_names()

    # 1. Ampliació saas_leads
    if "saas_leads" in tables:
        cols_lead = [c["name"] for c in insp.get_columns("saas_leads")]
        if "cp_geocode_retornat" not in cols_lead:
            op.add_column("saas_leads", sa.Column("cp_geocode_retornat", sa.String(10), nullable=True))
        if "cp_geocode_coincideix" not in cols_lead:
            op.add_column("saas_leads", sa.Column("cp_geocode_coincideix", sa.Boolean(), nullable=True))
        if "gatekeeper_font_url" not in cols_lead:
            op.add_column("saas_leads", sa.Column("gatekeeper_font_url", sa.Text(), nullable=True))
        if "gatekeeper_cita" not in cols_lead:
            op.add_column("saas_leads", sa.Column("gatekeeper_cita", sa.Text(), nullable=True))
        if "gatekeeper_confianca" not in cols_lead:
            op.add_column("saas_leads", sa.Column("gatekeeper_confianca", sa.String(20), nullable=True))

    # 2. Ampliació saas_prospeccio_candidats
    if "saas_prospeccio_candidats" in tables:
        cols_cand = [c["name"] for c in insp.get_columns("saas_prospeccio_candidats")]
        if "cp_geocode_retornat" not in cols_cand:
            op.add_column("saas_prospeccio_candidats", sa.Column("cp_geocode_retornat", sa.String(10), nullable=True))
        if "cp_geocode_coincideix" not in cols_cand:
            op.add_column("saas_prospeccio_candidats", sa.Column("cp_geocode_coincideix", sa.Boolean(), nullable=True))
        if "gatekeeper_font_url" not in cols_cand:
            op.add_column("saas_prospeccio_candidats", sa.Column("gatekeeper_font_url", sa.Text(), nullable=True))
        if "gatekeeper_cita" not in cols_cand:
            op.add_column("saas_prospeccio_candidats", sa.Column("gatekeeper_cita", sa.Text(), nullable=True))
        if "gatekeeper_confianca" not in cols_cand:
            op.add_column("saas_prospeccio_candidats", sa.Column("gatekeeper_confianca", sa.String(20), nullable=True))

        # Assegurar que estat_decisio admet fins a 50 caràcters per a SELECCIONAT_SENSE_GATEKEEPER
        op.alter_column(
            "saas_prospeccio_candidats",
            "estat_decisio",
            existing_type=sa.String(30),
            type_=sa.String(50),
            existing_nullable=False,
        )

    # 3. Ampliació saas_prospeccio_tasques (embut)
    if "saas_prospeccio_tasques" in tables:
        cols_tasca = [c["name"] for c in insp.get_columns("saas_prospeccio_tasques")]
        if "embut_descoberta" not in cols_tasca:
            op.add_column("saas_prospeccio_tasques", sa.Column("embut_descoberta", postgresql.JSONB(astext_type=sa.Text()), nullable=True))


def downgrade() -> None:
    for col in ("gatekeeper_confianca", "gatekeeper_cita", "gatekeeper_font_url",
                "cp_geocode_coincideix", "cp_geocode_retornat"):
        op.drop_column("saas_leads", col)
        op.drop_column("saas_prospeccio_candidats", col)
    op.drop_column("saas_prospeccio_tasques", "embut_descoberta")
