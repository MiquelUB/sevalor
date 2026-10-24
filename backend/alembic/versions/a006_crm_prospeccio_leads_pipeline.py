"""CRM Prospecció, Leads, Pipeline Kanban de 7 dies i Activitats comercials.

Revision ID: a006_crm_prospeccio
Revises: a005_estat_domini
Create Date: 2026-10-24
"""
from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from alembic import op

revision: str = "a006_crm_prospeccio"
down_revision: Union[str, Sequence[str], None] = "a005_estat_domini"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    tables = insp.get_table_names()

    if "saas_leads" not in tables:
        op.create_table(
            "saas_leads",
            sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
            sa.Column("nom_empresa", sa.String(150), nullable=False),
            sa.Column("nom_contacte", sa.String(100), nullable=False),
            sa.Column("email", sa.String(150), nullable=False),
            sa.Column("telefon", sa.String(30), nullable=True),
            sa.Column("vertical", sa.String(100), server_default="CampoPro", nullable=False),
            sa.Column("origen", sa.String(50), server_default="WEB", nullable=False),
            sa.Column("estat_qualificacio", sa.String(50), server_default="NOU", nullable=False),
            sa.Column("operaris_estimats", sa.Integer(), server_default=sa.text("5"), nullable=False),
            sa.Column("notes", sa.Text(), nullable=True),
            sa.Column("empresa_demo_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("empreses.id", ondelete="SET NULL"), nullable=True),
            sa.Column("data_inici_demo", sa.DateTime(timezone=True), nullable=True),
            sa.Column("data_fi_demo", sa.DateTime(timezone=True), nullable=True),
            sa.Column("dies_demo_durada", sa.Integer(), server_default=sa.text("7"), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_saas_leads_email", "saas_leads", ["email"])
        op.create_index("ix_saas_leads_estat", "saas_leads", ["estat_qualificacio"])

    if "saas_oportunitats" not in tables:
        op.create_table(
            "saas_oportunitats",
            sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
            sa.Column("lead_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("saas_leads.id", ondelete="CASCADE"), nullable=False),
            sa.Column("titol", sa.String(200), nullable=False),
            sa.Column("etapa", sa.String(50), server_default="PROSPECCIO", nullable=False),
            sa.Column("valor_mensual_estimat", sa.Numeric(10, 2), server_default=sa.text("0.00"), nullable=False),
            sa.Column("valor_ia_setup", sa.Numeric(10, 2), server_default=sa.text("0.00"), nullable=False),
            sa.Column("probabilitat_percent", sa.Integer(), server_default=sa.text("20"), nullable=False),
            sa.Column("data_tancament_prevista", sa.Date(), nullable=True),
            sa.Column("motiu_perdua", sa.String(255), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_saas_oportunitats_etapa", "saas_oportunitats", ["etapa"])

    if "saas_activitats_lead" not in tables:
        op.create_table(
            "saas_activitats_lead",
            sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
            sa.Column("lead_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("saas_leads.id", ondelete="CASCADE"), nullable=False),
            sa.Column("tipus", sa.String(30), server_default="NOTA", nullable=False),
            sa.Column("titol", sa.String(200), nullable=False),
            sa.Column("descripcio", sa.Text(), nullable=True),
            sa.Column("autor_nom", sa.String(100), server_default="Superadmin", nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_saas_activitats_lead_id", "saas_activitats_lead", ["lead_id"])


def downgrade() -> None:
    op.drop_table("saas_activitats_lead")
    op.drop_table("saas_oportunitats")
    op.drop_table("saas_leads")
