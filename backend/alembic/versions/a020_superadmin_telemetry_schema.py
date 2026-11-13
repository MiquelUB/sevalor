"""Move telemetry tables to isolated PostgreSQL schema superadmin_telemetry (Spec 022 RF-03, RF-06).

Revision ID: a020_superadmin_telemetry_schema
Revises: a019_pla2_magatzem_comptabilitat
Create Date: 2026-11-13 19:35:00.000000
"""

from alembic import op

revision = "a020_superadmin_telemetry_schema"
down_revision = "a019_pla2_magatzem_comptabilitat"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE SCHEMA IF NOT EXISTS superadmin_telemetry;")

    for table_name in ("telemetria_sistema", "alertes_seguretat", "registre_baixes_certificats"):
        op.execute(
            f"""
            DO $$
            BEGIN
                IF EXISTS (
                    SELECT 1 FROM information_schema.tables
                    WHERE table_schema = 'public' AND table_name = '{table_name}'
                ) THEN
                    ALTER TABLE public.{table_name} SET SCHEMA superadmin_telemetry;
                END IF;
            END $$;
            """
        )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS superadmin_telemetry.telemetria_sistema (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            cluster VARCHAR(100) NOT NULL DEFAULT 'hetzner-cpx21',
            node VARCHAR(255),
            cpu_utilization_percent NUMERIC(6, 2) NOT NULL DEFAULT 0.00,
            ram_utilization_mb NUMERIC(12, 2) NOT NULL DEFAULT 0.00,
            ram_total_mb NUMERIC(12, 2) NOT NULL DEFAULT 0.00,
            db_pool_occupancy_percent NUMERIC(6, 2),
            p95_latency_ms NUMERIC(10, 2),
            queue_depths JSONB NOT NULL DEFAULT '{}'::jsonb,
            captured_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );
        """
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS superadmin_telemetry.alertes_seguretat (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tipus VARCHAR(100) NOT NULL,
            gravetat VARCHAR(20) NOT NULL DEFAULT 'GROGA',
            origen VARCHAR(80) NOT NULL DEFAULT 'whisper_service',
            detall TEXT NOT NULL,
            resolta BOOLEAN NOT NULL DEFAULT false,
            empresa_id UUID,
            creat_a TIMESTAMPTZ NOT NULL DEFAULT now(),
            resolta_a TIMESTAMPTZ
        );
        """
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS superadmin_telemetry.registre_baixes_certificats (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id UUID NOT NULL,
            nif_hash VARCHAR(64) NOT NULL,
            certificat_path VARCHAR(500) NOT NULL,
            estat VARCHAR(40) NOT NULL DEFAULT 'ELIMINAT',
            custodia_anys INTEGER NOT NULL DEFAULT 5,
            periode_gracia_dies INTEGER NOT NULL DEFAULT 30,
            creat_a TIMESTAMPTZ NOT NULL DEFAULT now()
        );
        """
    )

    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_superadmin_telemetria_captured_at ON superadmin_telemetry.telemetria_sistema (captured_at DESC);"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_superadmin_alertes_creat_a ON superadmin_telemetry.alertes_seguretat (creat_a DESC);"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_superadmin_baixes_tenant_id ON superadmin_telemetry.registre_baixes_certificats (tenant_id);"
    )
    op.execute("GRANT USAGE ON SCHEMA superadmin_telemetry TO PUBLIC;")
    op.execute(
        "GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA superadmin_telemetry TO PUBLIC;"
    )


def downgrade() -> None:
    for table_name in ("telemetria_sistema", "alertes_seguretat", "registre_baixes_certificats"):
        op.execute(f"ALTER TABLE IF EXISTS superadmin_telemetry.{table_name} SET SCHEMA public;")
