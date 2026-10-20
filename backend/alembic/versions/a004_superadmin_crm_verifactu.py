"""Superadmin CRM, Facturació B2B Veri*factu HITL, Tiquets i Quota Dinàmica.

Revision ID: a004_superadmin_crm_verifactu
Revises: a003_article_proveidor
Create Date: 2026-10-20
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "a004_superadmin_crm_verifactu"
down_revision: Union[str, Sequence[str], None] = "a003_article_proveidor"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TABLE empreses ALTER COLUMN estat_pagament TYPE VARCHAR(30)")
    op.execute("ALTER TABLE empreses ADD COLUMN IF NOT EXISTS quota_operaris INTEGER NOT NULL DEFAULT 5")
    op.execute("ALTER TABLE empreses ADD COLUMN IF NOT EXISTS quota_buffer_mb INTEGER NOT NULL DEFAULT 500")
    op.execute("ALTER TABLE empreses ADD COLUMN IF NOT EXISTS tarifa_llicencia_base NUMERIC(10, 2) NOT NULL DEFAULT 0.00")
    op.execute("ALTER TABLE empreses ADD COLUMN IF NOT EXISTS tarifa_per_operari NUMERIC(10, 2) NOT NULL DEFAULT 0.00")
    op.execute("ALTER TABLE empreses ADD COLUMN IF NOT EXISTS tarifa_config_ia NUMERIC(10, 2) NOT NULL DEFAULT 0.00")
    op.execute("ALTER TABLE empreses ADD COLUMN IF NOT EXISTS equips_ia_venuts JSONB DEFAULT '[]'::jsonb")
    op.execute("ALTER TABLE empreses ADD COLUMN IF NOT EXISTS notes_crm TEXT")

    op.create_table(
        "saas_factures_b2b",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("empresa_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("empreses.id", ondelete="SET NULL"), nullable=True),
        sa.Column("client_nom_snapshot", sa.String(150), nullable=False),
        sa.Column("client_nif_snapshot", sa.String(20), nullable=False),
        sa.Column("serie", sa.String(20), server_default="SAAS", nullable=False),
        sa.Column("numero_factura", sa.Integer(), nullable=True),
        sa.Column("estat", sa.String(30), server_default="ESBORRANY_PREFACTURA", nullable=False),
        sa.Column("periode", sa.String(30), nullable=False),
        sa.Column("concepte_onboarding_desc", sa.String(255), nullable=True),
        sa.Column("import_onboarding", sa.Numeric(10, 2), server_default=sa.text("0.00"), nullable=False),
        sa.Column("concepte_config_ia_desc", sa.String(255), nullable=True),
        sa.Column("import_config_ia", sa.Numeric(10, 2), server_default=sa.text("0.00"), nullable=False),
        sa.Column("equips_ia_detall", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'[]'::jsonb"), nullable=True),
        sa.Column("import_equips_ia", sa.Numeric(10, 2), server_default=sa.text("0.00"), nullable=False),
        sa.Column("num_operaris_facturats", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("preu_unitari_operari", sa.Numeric(10, 2), server_default=sa.text("0.00"), nullable=False),
        sa.Column("import_operaris", sa.Numeric(10, 2), server_default=sa.text("0.00"), nullable=False),
        sa.Column("base_imposable", sa.Numeric(12, 2), server_default=sa.text("0.00"), nullable=False),
        sa.Column("tipus_iva_percent", sa.Numeric(5, 2), server_default=sa.text("21.00"), nullable=False),
        sa.Column("quota_iva", sa.Numeric(12, 2), server_default=sa.text("0.00"), nullable=False),
        sa.Column("import_total", sa.Numeric(12, 2), server_default=sa.text("0.00"), nullable=False),
        sa.Column("verificada_per_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("data_verificacio_humana", sa.DateTime(timezone=True), nullable=True),
        sa.Column("hash_sha256", sa.String(64), nullable=True),
        sa.Column("hash_anterior", sa.String(64), nullable=True),
        sa.Column("qr_verifactu", sa.Text(), nullable=True),
        sa.Column("pdf_path", sa.String(500), nullable=True),
        sa.Column("data_emissio", sa.Date(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "saas_tiquets_suport",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("empresa_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("empreses.id", ondelete="SET NULL"), nullable=True),
        sa.Column("empresa_nom_snapshot", sa.String(150), nullable=False),
        sa.Column("assumpte", sa.String(200), nullable=False),
        sa.Column("descripcio", sa.Text(), nullable=False),
        sa.Column("severitat", sa.String(20), server_default="NORMAL", nullable=False),
        sa.Column("estat", sa.String(30), server_default="OBERT", nullable=False),
        sa.Column("pc_empresa_online_al_crear", sa.Boolean(), nullable=True),
        sa.Column("diagnostic_automatic", sa.Text(), nullable=True),
        sa.Column("resolucio_notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "saas_historial_llicencia",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("empresa_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("empreses.id", ondelete="SET NULL"), nullable=True),
        sa.Column("quota_operaris_anterior", sa.Integer(), nullable=False),
        sa.Column("quota_operaris_nova", sa.Integer(), nullable=False),
        sa.Column("estat_anterior", sa.String(30), nullable=True),
        sa.Column("estat_nou", sa.String(30), nullable=True),
        sa.Column("motiu", sa.String(255), nullable=True),
        sa.Column("autor_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("saas_historial_llicencia")
    op.drop_table("saas_tiquets_suport")
    op.drop_table("saas_factures_b2b")
