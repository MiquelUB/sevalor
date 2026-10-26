"""Motor de Prospecció Atòmica per Codi Postal, Lead Scoring Evolutiu, Calendari i Correu.

Revision ID: a007_prospeccio_leads_calendari
Revises: a006_crm_prospeccio
Create Date: 2026-10-26
"""
from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "a007_prospeccio_leads_calendari"
down_revision: Union[str, Sequence[str], None] = "a006_crm_prospeccio"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    tables = insp.get_table_names()

    # 1. Crear taula saas_prospeccio_tasques
    if "saas_prospeccio_tasques" not in tables:
        op.create_table(
            "saas_prospeccio_tasques",
            sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
            sa.Column("codi_postal", sa.String(10), nullable=False),
            sa.Column("vertical", sa.String(150), nullable=False),
            sa.Column("operaris_minims", sa.Integer(), server_default=sa.text("5"), nullable=False),
            sa.Column("estat", sa.String(30), server_default="PENDENT", nullable=False),
            sa.Column("total_trobats", sa.Integer(), server_default=sa.text("0"), nullable=False),
            sa.Column("total_seleccionats", sa.Integer(), server_default=sa.text("0"), nullable=False),
            sa.Column("total_descartats", sa.Integer(), server_default=sa.text("0"), nullable=False),
            sa.Column("total_duplicats", sa.Integer(), server_default=sa.text("0"), nullable=False),
            sa.Column("resum_execucio", sa.Text(), nullable=True),
            sa.Column("autor_id", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_saas_prospeccio_tasques_cp", "saas_prospeccio_tasques", ["codi_postal"])
        op.create_index("ix_saas_prospeccio_tasques_estat", "saas_prospeccio_tasques", ["estat"])

    # 2. Ampliar taula saas_leads amb columnes de multi-validació, fites i outreach
    if "saas_leads" in tables:
        lead_cols = [c["name"] for c in insp.get_columns("saas_leads")]

        new_lead_columns = [
            ("cif", sa.String(20), True),
            ("web_url", sa.String(255), True),
            ("domini_normalitzat", sa.String(150), True),
            ("adreca_fisica", sa.String(255), True),
            ("adreca_normalitzada", sa.String(255), True),
            ("codi_postal", sa.String(10), True),
            ("carrec_contacte", sa.String(100), True),
            ("fonts_investigades", sa.Text(), True),
            ("fita_recent", sa.Text(), True),
            ("punt_dolor_detectat", sa.Text(), True),
            ("angle_atac", sa.String(50), True),
            ("score_qualificacio", sa.Integer(), False, sa.text("0")),
            ("justificacio_ia", sa.Text(), True),
            ("mx_validat", sa.Boolean(), False, sa.text("false")),
            ("esborrany_email_assumpte", sa.String(255), True),
            ("esborrany_email_cos", sa.Text(), True),
            ("rao_tancament_exit", sa.Text(), True),
            ("es_tancament_replicable", sa.Boolean(), False, sa.text("false")),
            ("tasca_prospeccio_id", postgresql.UUID(as_uuid=True), True),
        ]

        for col_name, col_type, col_nullable, *default_val in new_lead_columns:
            if col_name not in lead_cols:
                kw = {}
                if default_val:
                    kw["server_default"] = default_val[0]
                op.add_column("saas_leads", sa.Column(col_name, col_type, nullable=col_nullable, **kw))

        # Canviar longitud de vertical a 150 si cal
        op.alter_column("saas_leads", "vertical", type_=sa.String(150), existing_type=sa.String(100), existing_nullable=False)

        # Crear índexs
        existing_indices = [idx["name"] for idx in insp.get_indexes("saas_leads")]
        if "ix_saas_leads_cif" not in existing_indices:
            op.create_index("ix_saas_leads_cif", "saas_leads", ["cif"])
        if "ix_saas_leads_domini_normalitzat" not in existing_indices:
            op.create_index("ix_saas_leads_domini_normalitzat", "saas_leads", ["domini_normalitzat"])
        if "ix_saas_leads_adreca_normalitzada" not in existing_indices:
            op.create_index("ix_saas_leads_adreca_normalitzada", "saas_leads", ["adreca_normalitzada"])
        if "ix_saas_leads_codi_postal" not in existing_indices:
            op.create_index("ix_saas_leads_codi_postal", "saas_leads", ["codi_postal"])

        # Foreign Key cap a tasques de prospecció si existeix
        fk_names = [fk["name"] for fk in insp.get_foreign_keys("saas_leads")]
        if "fk_saas_leads_tasca_id" not in fk_names:
            op.create_foreign_key(
                "fk_saas_leads_tasca_id",
                "saas_leads",
                "saas_prospeccio_tasques",
                ["tasca_prospeccio_id"],
                ["id"],
                ondelete="SET NULL",
            )

    # 3. Ampliar saas_oportunitats amb aprenentatge de tancament d'èxit replicable
    if "saas_oportunitats" in tables:
        opp_cols = [c["name"] for c in insp.get_columns("saas_oportunitats")]
        if "rao_tancament_exit" not in opp_cols:
            op.add_column("saas_oportunitats", sa.Column("rao_tancament_exit", sa.Text(), nullable=True))
        if "requisits_replicables" not in opp_cols:
            op.add_column("saas_oportunitats", sa.Column("requisits_replicables", sa.Text(), nullable=True))
        if "es_replicable" not in opp_cols:
            op.add_column("saas_oportunitats", sa.Column("es_replicable", sa.Boolean(), server_default=sa.text("false"), nullable=False))

    # 4. Crear taula saas_prospeccio_candidats (auditoria transparent)
    if "saas_prospeccio_candidats" not in tables:
        op.create_table(
            "saas_prospeccio_candidats",
            sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
            sa.Column("tasca_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("saas_prospeccio_tasques.id", ondelete="CASCADE"), nullable=False),
            sa.Column("nom_empresa", sa.String(150), nullable=False),
            sa.Column("cif", sa.String(20), nullable=True),
            sa.Column("web_url", sa.String(255), nullable=False),
            sa.Column("domini_normalitzat", sa.String(150), nullable=False),
            sa.Column("adreca_fisica", sa.String(255), nullable=True),
            sa.Column("adreca_normalitzada", sa.String(255), nullable=True),
            sa.Column("codi_postal", sa.String(10), nullable=False),
            sa.Column("vertical", sa.String(150), nullable=False),
            sa.Column("fonts_investigades", sa.Text(), nullable=True),
            sa.Column("email_detectat", sa.String(150), nullable=True),
            sa.Column("telefon_detectat", sa.String(30), nullable=True),
            sa.Column("mx_validat", sa.Boolean(), server_default=sa.text("false"), nullable=False),
            sa.Column("operaris_estimats", sa.Integer(), server_default=sa.text("0"), nullable=False),
            sa.Column("decisor_nom", sa.String(100), nullable=True),
            sa.Column("decisor_carrec", sa.String(100), nullable=True),
            sa.Column("fita_recent", sa.Text(), nullable=True),
            sa.Column("punt_dolor", sa.Text(), nullable=True),
            sa.Column("angle_atac", sa.String(50), nullable=True),
            sa.Column("score", sa.Integer(), server_default=sa.text("0"), nullable=False),
            sa.Column("estat_decisio", sa.String(30), nullable=False),
            sa.Column("vector_duplicitat", sa.String(50), nullable=True),
            sa.Column("motiu_detallat_ia", sa.Text(), nullable=False),
            sa.Column("corregit_huma", sa.Boolean(), server_default=sa.text("false"), nullable=False),
            sa.Column("decisio_humana", sa.String(30), nullable=True),
            sa.Column("motiu_correccio_humana", sa.Text(), nullable=True),
            sa.Column("lead_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("saas_leads.id", ondelete="SET NULL"), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_saas_prospeccio_candidats_tasca_id", "saas_prospeccio_candidats", ["tasca_id"])
        op.create_index("ix_saas_prospeccio_candidats_estat_decisio", "saas_prospeccio_candidats", ["estat_decisio"])
        op.create_index("ix_saas_prospeccio_candidats_cif", "saas_prospeccio_candidats", ["cif"])
        op.create_index("ix_saas_prospeccio_candidats_domini", "saas_prospeccio_candidats", ["domini_normalitzat"])
        op.create_index("ix_saas_prospeccio_candidats_adreca", "saas_prospeccio_candidats", ["adreca_normalitzada"])
        op.create_index("ix_saas_prospeccio_candidats_cp", "saas_prospeccio_candidats", ["codi_postal"])

    # 5. Crear taula saas_criteris_feedback (doble bucle d'aprenentatge)
    if "saas_criteris_feedback" not in tables:
        op.create_table(
            "saas_criteris_feedback",
            sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
            sa.Column("tipus_aprenentatge", sa.String(40), nullable=False),
            sa.Column("candidat_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("saas_prospeccio_candidats.id", ondelete="SET NULL"), nullable=True),
            sa.Column("lead_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("saas_leads.id", ondelete="SET NULL"), nullable=True),
            sa.Column("vertical", sa.String(150), nullable=False),
            sa.Column("nom_empresa", sa.String(150), nullable=False),
            sa.Column("web_url", sa.String(255), nullable=True),
            sa.Column("resum_evidencies_o_requisits", sa.Text(), nullable=False),
            sa.Column("decisio_ia_original", sa.String(30), nullable=True),
            sa.Column("decisio_humana_correcta", sa.String(30), nullable=False),
            sa.Column("explicacio_humana_o_rao_exit", sa.Text(), nullable=False),
            sa.Column("es_replicable", sa.Boolean(), server_default=sa.text("false"), nullable=False),
            sa.Column("actiu", sa.Boolean(), server_default=sa.text("true"), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_saas_criteris_feedback_vertical", "saas_criteris_feedback", ["vertical"])
        op.create_index("ix_saas_criteris_feedback_tipus", "saas_criteris_feedback", ["tipus_aprenentatge"])

    # 6. Crear taula saas_correu_missatges (campanya 3 emails, calendari comercial, fils)
    if "saas_correu_missatges" not in tables:
        op.create_table(
            "saas_correu_missatges",
            sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
            sa.Column("lead_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("saas_leads.id", ondelete="CASCADE"), nullable=False),
            sa.Column("tipus_item_calendari", sa.String(30), server_default="EMAIL_CAMPANYA", nullable=False),
            sa.Column("pas_sequencia", sa.Integer(), nullable=True),
            sa.Column("tempo_dies_offset", sa.Integer(), server_default=sa.text("0"), nullable=False),
            sa.Column("data_programada", sa.DateTime(timezone=True), nullable=False),
            sa.Column("direccio", sa.String(20), server_default="OUTBOUND", nullable=False),
            sa.Column("estat_enviament", sa.String(30), server_default="ESBORRANY_PROGRAMAT", nullable=False),
            sa.Column("remitent", sa.String(150), nullable=False),
            sa.Column("destinatari", sa.String(150), nullable=False),
            sa.Column("assumpte", sa.String(255), nullable=False),
            sa.Column("cos_text", sa.Text(), nullable=False),
            sa.Column("message_id", sa.String(255), nullable=False),
            sa.Column("in_reply_to", sa.String(255), nullable=True),
            sa.Column("references_header", sa.Text(), nullable=True),
            sa.Column("intencio_ia", sa.String(50), nullable=True),
            sa.Column("resum_ia", sa.Text(), nullable=True),
            sa.Column("aprovat_per_id", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("message_id", name="uq_saas_correu_missatges_msgid"),
        )
        op.create_index("ix_saas_correu_missatges_lead_id", "saas_correu_missatges", ["lead_id"])
        op.create_index("ix_saas_correu_missatges_data_prog", "saas_correu_missatges", ["data_programada"])
        op.create_index("ix_saas_correu_missatges_estat", "saas_correu_missatges", ["estat_enviament"])
        op.create_index("ix_saas_correu_missatges_in_reply_to", "saas_correu_missatges", ["in_reply_to"])

    # 7. Crear taula saas_exclusio_rgpd
    if "saas_exclusio_rgpd" not in tables:
        op.create_table(
            "saas_exclusio_rgpd",
            sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
            sa.Column("email", sa.String(150), nullable=True),
            sa.Column("domini", sa.String(150), nullable=False),
            sa.Column("cif", sa.String(20), nullable=True),
            sa.Column("motiu", sa.String(50), server_default="OPTOUT_EXPLICIT", nullable=False),
            sa.Column("origen_message_id", sa.String(255), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("email", "domini", name="uq_exclusio_email_domini"),
        )
        op.create_index("ix_saas_exclusio_rgpd_domini", "saas_exclusio_rgpd", ["domini"])
        op.create_index("ix_saas_exclusio_rgpd_email", "saas_exclusio_rgpd", ["email"])
        op.create_index("ix_saas_exclusio_rgpd_cif", "saas_exclusio_rgpd", ["cif"])

    # 8. Garantir permisos al rol d'aplicació sevalor_app si existeix
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'sevalor_app') THEN
                GRANT SELECT, INSERT, UPDATE, DELETE ON
                    public.saas_prospeccio_tasques,
                    public.saas_prospeccio_candidats,
                    public.saas_criteris_feedback,
                    public.saas_correu_missatges,
                    public.saas_exclusio_rgpd
                TO sevalor_app;
            END IF;
        END
        $$;
        """
    )


def downgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    tables = insp.get_table_names()

    if "saas_leads" in tables:
        fk_names = [fk["name"] for fk in insp.get_foreign_keys("saas_leads")]
        if "fk_saas_leads_tasca_id" in fk_names:
            op.drop_constraint("fk_saas_leads_tasca_id", "saas_leads", type_="foreignkey")

        existing_indices = [idx["name"] for idx in insp.get_indexes("saas_leads")]
        for idx_name in [
            "ix_saas_leads_cif",
            "ix_saas_leads_domini_normalitzat",
            "ix_saas_leads_adreca_normalitzada",
            "ix_saas_leads_codi_postal",
        ]:
            if idx_name in existing_indices:
                op.drop_index(idx_name, table_name="saas_leads")

        lead_cols = [c["name"] for c in insp.get_columns("saas_leads")]
        for col_name in [
            "tasca_prospeccio_id",
            "es_tancament_replicable",
            "rao_tancament_exit",
            "esborrany_email_cos",
            "esborrany_email_assumpte",
            "mx_validat",
            "justificacio_ia",
            "score_qualificacio",
            "angle_atac",
            "punt_dolor_detectat",
            "fita_recent",
            "fonts_investigades",
            "carrec_contacte",
            "codi_postal",
            "adreca_normalitzada",
            "adreca_fisica",
            "domini_normalitzat",
            "web_url",
            "cif",
        ]:
            if col_name in lead_cols:
                op.drop_column("saas_leads", col_name)

    if "saas_oportunitats" in tables:
        opp_cols = [c["name"] for c in insp.get_columns("saas_oportunitats")]
        for col_name in ["es_replicable", "requisits_replicables", "rao_tancament_exit"]:
            if col_name in opp_cols:
                op.drop_column("saas_oportunitats", col_name)

    for tbl in [
        "saas_exclusio_rgpd",
        "saas_correu_missatges",
        "saas_criteris_feedback",
        "saas_prospeccio_candidats",
        "saas_prospeccio_tasques",
    ]:
        if tbl in tables:
            op.drop_table(tbl)
