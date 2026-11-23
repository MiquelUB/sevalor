"""a028: Veri*factu complet segons RD 1007/2023 i Ordre HAC/1177/2024 (Esquema, Cadena Global, Triggers Immutables i RLS).

Revision ID: a028_verifactu_hac1177_complet
Revises: a027_prefactura_ot_comercial
Create Date: 2026-11-23
"""

from typing import Sequence, Union

from alembic import op

revision: str = "a028_verifactu_hac1177_complet"
down_revision: Union[str, Sequence[str], None] = "a027_prefactura_ot_comercial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Nous camps fiscals, bancaris i de certificat AEAT a empreses
    op.execute(
        """
        ALTER TABLE public.empreses
            ADD COLUMN IF NOT EXISTS rao_social_fiscal VARCHAR(200),
            ADD COLUMN IF NOT EXISTS eslogan_activitat VARCHAR(255),
            ADD COLUMN IF NOT EXISTS codi_postal VARCHAR(15),
            ADD COLUMN IF NOT EXISTS poblacio VARCHAR(100),
            ADD COLUMN IF NOT EXISTS provincia VARCHAR(100),
            ADD COLUMN IF NOT EXISTS telefon_facturacio VARCHAR(40),
            ADD COLUMN IF NOT EXISTS email_facturacio VARCHAR(200),
            ADD COLUMN IF NOT EXISTS titular_compte_bancari VARCHAR(200),
            ADD COLUMN IF NOT EXISTS iban_cobrament_xifrat TEXT,
            ADD COLUMN IF NOT EXISTS dades_registre_mercantil TEXT,
            ADD COLUMN IF NOT EXISTS verifactu_entorn VARCHAR(20) NOT NULL DEFAULT 'PREPRODUCCIO',
            ADD COLUMN IF NOT EXISTS verifactu_cert_path VARCHAR(500),
            ADD COLUMN IF NOT EXISTS verifactu_cert_pass_xifrat TEXT,
            ADD COLUMN IF NOT EXISTS verifactu_cert_subject VARCHAR(300),
            ADD COLUMN IF NOT EXISTS verifactu_cert_caducitat TIMESTAMPTZ
        """
    )

    # 2. Nous camps d'adreça desglossada a clients
    op.execute(
        """
        ALTER TABLE public.clients
            ADD COLUMN IF NOT EXISTS codi_postal VARCHAR(15),
            ADD COLUMN IF NOT EXISTS poblacio VARCHAR(100),
            ADD COLUMN IF NOT EXISTS provincia VARCHAR(100)
        """
    )

    # 3. Nous camps Ordre HAC/1177/2024 i Plantilla Factura a factures_capcalera
    op.execute(
        """
        ALTER TABLE public.factures_capcalera
            ADD COLUMN IF NOT EXISTS exercici INTEGER,
            ADD COLUMN IF NOT EXISTS num_serie_verifactu VARCHAR(60),
            ADD COLUMN IF NOT EXISTS tipus_factura VARCHAR(5) NOT NULL DEFAULT 'F1',
            ADD COLUMN IF NOT EXISTS tipus_rectificacio VARCHAR(1),
            ADD COLUMN IF NOT EXISTS data_operacio DATE,
            ADD COLUMN IF NOT EXISTS referencia_client VARCHAR(100),
            ADD COLUMN IF NOT EXISTS quota_recarrec_equivalencia NUMERIC(12, 2) NOT NULL DEFAULT 0.00,
            ADD COLUMN IF NOT EXISTS import_total_verifactu NUMERIC(12, 2) NOT NULL DEFAULT 0.00,
            ADD COLUMN IF NOT EXISTS causa_exempcio VARCHAR(10),
            ADD COLUMN IF NOT EXISTS mencio_legal TEXT,
            ADD COLUMN IF NOT EXISTS notes_factura TEXT,
            ADD COLUMN IF NOT EXISTS fecha_hora_huso_gen_registro VARCHAR(35),
            ADD COLUMN IF NOT EXISTS estat_anulacio VARCHAR(25) NOT NULL DEFAULT 'ACTIVA',
            ADD COLUMN IF NOT EXISTS data_anulacio TIMESTAMPTZ,
            ADD COLUMN IF NOT EXISTS motiu_anulacio TEXT,
            ADD COLUMN IF NOT EXISTS hash_anulacio_sha256 VARCHAR(64),
            ADD COLUMN IF NOT EXISTS csv_aeat VARCHAR(64),
            ADD COLUMN IF NOT EXISTS darrer_error_aeat TEXT
        """
    )
    op.execute("ALTER TABLE public.factures_capcalera ALTER COLUMN estat_enviament TYPE VARCHAR(30)")
    op.execute(
        """
        UPDATE public.factures_capcalera
        SET exercici = COALESCE(EXTRACT(YEAR FROM data_emissio)::INT, EXTRACT(YEAR FROM CURRENT_DATE)::INT)
        WHERE exercici IS NULL
        """
    )
    op.execute(
        """
        ALTER TABLE public.factures_capcalera
            ALTER COLUMN exercici SET NOT NULL,
            ALTER COLUMN exercici SET DEFAULT EXTRACT(YEAR FROM CURRENT_DATE)::INT
        """
    )
    op.execute(
        """
        UPDATE public.factures_capcalera
        SET num_serie_verifactu = serie || '-' || exercici::text || '-' || LPAD(numero_factura::text, 4, '0')
        WHERE num_serie_verifactu IS NULL
        """
    )
    op.execute(
        """
        UPDATE public.factures_capcalera
        SET import_total_verifactu = ROUND((COALESCE(base_imposable, 0) + COALESCE(quota_iva, 0) + COALESCE(quota_recarrec_equivalencia, 0))::numeric, 2)
        WHERE COALESCE(import_total_verifactu, 0) = 0 AND (COALESCE(base_imposable, 0) <> 0 OR COALESCE(quota_iva, 0) <> 0)
        """
    )

    # Substituir constraint d'unicitat sense exercici pel nou amb exercici
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM pg_constraint WHERE conname = 'uq_factures_empresa_serie_num'
            ) THEN
                ALTER TABLE public.factures_capcalera DROP CONSTRAINT uq_factures_empresa_serie_num;
            END IF;
            IF NOT EXISTS (
                SELECT 1 FROM pg_constraint WHERE conname = 'uq_factures_empresa_exercici_serie_num'
            ) THEN
                ALTER TABLE public.factures_capcalera
                    ADD CONSTRAINT uq_factures_empresa_exercici_serie_num
                    UNIQUE (empresa_id, exercici, serie, numero_factura);
            END IF;
        END
        $$
        """
    )

    # 4. Nous camps a factures_linies
    op.execute(
        """
        ALTER TABLE public.factures_linies
            ADD COLUMN IF NOT EXISTS descripcio_detall TEXT,
            ADD COLUMN IF NOT EXISTS tipus_recarrec_equivalencia NUMERIC(4, 2) NOT NULL DEFAULT 0.00,
            ADD COLUMN IF NOT EXISTS quota_recarrec_linia NUMERIC(12, 2) NOT NULL DEFAULT 0.00
        """
    )

    # 5. Nous camps a outbox_enviaments_aeat + índex parcial
    op.execute(
        """
        ALTER TABLE public.outbox_enviaments_aeat
            ADD COLUMN IF NOT EXISTS tipus_registre VARCHAR(15) NOT NULL DEFAULT 'ALTA',
            ADD COLUMN IF NOT EXISTS proper_reintent_at TIMESTAMPTZ,
            ADD COLUMN IF NOT EXISTS codi_resposta_aeat VARCHAR(30),
            ADD COLUMN IF NOT EXISTS csv_aeat VARCHAR(64),
            ADD COLUMN IF NOT EXISTS temps_espera_segons INTEGER NOT NULL DEFAULT 60
        """
    )
    op.execute("ALTER TABLE public.outbox_enviaments_aeat ALTER COLUMN estat_enviament TYPE VARCHAR(30)")
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_outbox_aeat_pendents
            ON public.outbox_enviaments_aeat (estat_enviament, proper_reintent_at)
            WHERE estat_enviament IN ('PENDENT', 'ERROR_TEMPORAL', 'PENDENT_CERTIFICAT')
        """
    )

    # 6. Taula verifactu_cadena_tenant + RLS
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS public.verifactu_cadena_tenant (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            empresa_id UUID NOT NULL REFERENCES public.empreses(id) ON DELETE CASCADE,
            ultim_hash_sha256 VARCHAR(64),
            ultim_num_serie VARCHAR(60),
            ultima_data_expedicio VARCHAR(15),
            ultim_tipus_registre VARCHAR(15),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            CONSTRAINT uq_verifactu_cadena_empresa UNIQUE (empresa_id)
        )
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_verifactu_cadena_tenant_empresa_id
            ON public.verifactu_cadena_tenant (empresa_id)
        """
    )
    op.execute("ALTER TABLE public.verifactu_cadena_tenant ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE public.verifactu_cadena_tenant FORCE ROW LEVEL SECURITY")
    op.execute("DROP POLICY IF EXISTS tenant_isolation_verifactu_cadena_tenant ON public.verifactu_cadena_tenant")
    op.execute(
        """
        CREATE POLICY tenant_isolation_verifactu_cadena_tenant ON public.verifactu_cadena_tenant
            FOR ALL
            USING (empresa_id = NULLIF(current_setting('app.current_empresa_id', true), '')::uuid)
            WITH CHECK (empresa_id = NULLIF(current_setting('app.current_empresa_id', true), '')::uuid)
        """
    )
    op.execute("DROP POLICY IF EXISTS economics_boss_only_verifactu_cadena_tenant ON public.verifactu_cadena_tenant")
    op.execute(
        """
        CREATE POLICY economics_boss_only_verifactu_cadena_tenant ON public.verifactu_cadena_tenant
            AS RESTRICTIVE
            FOR ALL
            USING (
                NULLIF(current_setting('app.current_user_role', true), '')
                IN ('BOSS', 'SUPERADMIN', 'SECRETARIA', 'COMPTABILITAT')
            )
            WITH CHECK (
                NULLIF(current_setting('app.current_user_role', true), '')
                IN ('BOSS', 'SUPERADMIN', 'SECRETARIA', 'COMPTABILITAT')
            )
        """
    )

    # 7. Nous camps a saas_factures_b2b
    op.execute(
        """
        ALTER TABLE public.saas_factures_b2b
            ADD COLUMN IF NOT EXISTS exercici INTEGER NOT NULL DEFAULT EXTRACT(YEAR FROM CURRENT_DATE)::INT,
            ADD COLUMN IF NOT EXISTS num_serie_verifactu VARCHAR(60),
            ADD COLUMN IF NOT EXISTS tipus_factura VARCHAR(5) NOT NULL DEFAULT 'F1',
            ADD COLUMN IF NOT EXISTS tipus_rectificacio VARCHAR(1),
            ADD COLUMN IF NOT EXISTS import_total_verifactu NUMERIC(12, 2) NOT NULL DEFAULT 0.00,
            ADD COLUMN IF NOT EXISTS fecha_hora_huso_gen_registro VARCHAR(35),
            ADD COLUMN IF NOT EXISTS xml_path VARCHAR(500),
            ADD COLUMN IF NOT EXISTS data_operacio DATE,
            ADD COLUMN IF NOT EXISTS notes_factura TEXT,
            ADD COLUMN IF NOT EXISTS estat_enviament_aeat VARCHAR(30) NOT NULL DEFAULT 'PENDENT',
            ADD COLUMN IF NOT EXISTS csv_aeat VARCHAR(64),
            ADD COLUMN IF NOT EXISTS darrer_error_aeat TEXT,
            ADD COLUMN IF NOT EXISTS estat_anulacio VARCHAR(25) NOT NULL DEFAULT 'ACTIVA',
            ADD COLUMN IF NOT EXISTS data_anulacio TIMESTAMPTZ,
            ADD COLUMN IF NOT EXISTS motiu_anulacio TEXT,
            ADD COLUMN IF NOT EXISTS hash_anulacio_sha256 VARCHAR(64)
        """
    )

    # 8. Triggers PostgreSQL d'immutabilitat Veri*factu
    op.execute(
        """
        CREATE OR REPLACE FUNCTION public.fn_prevent_verifactu_invoice_mutation()
        RETURNS TRIGGER AS $$
        BEGIN
            IF TG_OP = 'DELETE' THEN
                IF OLD.estat_document = 'EMESA' AND COALESCE(OLD.serie, '') <> 'PRE' THEN
                    RAISE EXCEPTION 'VERIFACTU_IMMUTABLE_VIOLATION: Una factura emesa a Veri*factu és immutable i no es pot eliminar; cal emetre una factura rectificativa o un registre d anul·lació.';
                END IF;
                RETURN OLD;
            ELSIF TG_OP = 'UPDATE' THEN
                IF OLD.estat_document = 'EMESA' AND COALESCE(OLD.serie, '') <> 'PRE' THEN
                    IF NEW.empresa_id IS DISTINCT FROM OLD.empresa_id
                       OR NEW.client_id IS DISTINCT FROM OLD.client_id
                       OR NEW.serie IS DISTINCT FROM OLD.serie
                       OR NEW.exercici IS DISTINCT FROM OLD.exercici
                       OR NEW.numero_factura IS DISTINCT FROM OLD.numero_factura
                       OR (OLD.num_serie_verifactu IS NOT NULL AND NEW.num_serie_verifactu IS DISTINCT FROM OLD.num_serie_verifactu)
                       OR NEW.data_emissio IS DISTINCT FROM OLD.data_emissio
                       OR NEW.base_imposable IS DISTINCT FROM OLD.base_imposable
                       OR NEW.quota_iva IS DISTINCT FROM OLD.quota_iva
                       OR COALESCE(NEW.quota_recarrec_equivalencia, 0) IS DISTINCT FROM COALESCE(OLD.quota_recarrec_equivalencia, 0)
                       OR (COALESCE(OLD.import_total_verifactu, 0) <> 0 AND NEW.import_total_verifactu IS DISTINCT FROM OLD.import_total_verifactu)
                       OR NEW.import_suplits IS DISTINCT FROM OLD.import_suplits
                       OR NEW.import_retencio IS DISTINCT FROM OLD.import_retencio
                       OR NEW.import_retencio_garantia_4308 IS DISTINCT FROM OLD.import_retencio_garantia_4308
                       OR NEW.liquid_exigible IS DISTINCT FROM OLD.liquid_exigible
                       OR NEW.hash_sha256 IS DISTINCT FROM OLD.hash_sha256
                       OR NEW.hash_anterior IS DISTINCT FROM OLD.hash_anterior
                       OR (OLD.fecha_hora_huso_gen_registro IS NOT NULL AND NEW.fecha_hora_huso_gen_registro IS DISTINCT FROM OLD.fecha_hora_huso_gen_registro)
                       OR (OLD.qr_verifactu_payload IS NOT NULL AND NEW.qr_verifactu_payload IS DISTINCT FROM OLD.qr_verifactu_payload)
                       OR NEW.estat_document IS DISTINCT FROM OLD.estat_document
                    THEN
                        RAISE EXCEPTION 'VERIFACTU_IMMUTABLE_VIOLATION: Els camps fiscals i criptogràfics d una factura emesa a Veri*factu són immutables.';
                    END IF;
                    IF OLD.estat_anulacio = 'ANULADA_VERIFACTU'
                       AND (NEW.estat_anulacio IS DISTINCT FROM OLD.estat_anulacio
                            OR NEW.hash_anulacio_sha256 IS DISTINCT FROM OLD.hash_anulacio_sha256)
                    THEN
                        RAISE EXCEPTION 'VERIFACTU_IMMUTABLE_VIOLATION: Un registre d anul·lació Veri*factu no es pot revertir ni alterar.';
                    END IF;
                END IF;
                RETURN NEW;
            END IF;
            RETURN NULL;
        END;
        $$ LANGUAGE plpgsql
        """
    )
    op.execute("DROP TRIGGER IF EXISTS trg_factures_verifactu_immutable ON public.factures_capcalera")
    op.execute(
        """
        CREATE TRIGGER trg_factures_verifactu_immutable
        BEFORE UPDATE OR DELETE ON public.factures_capcalera
        FOR EACH ROW EXECUTE FUNCTION public.fn_prevent_verifactu_invoice_mutation()
        """
    )

    op.execute(
        """
        CREATE OR REPLACE FUNCTION public.fn_prevent_saas_invoice_mutation()
        RETURNS TRIGGER AS $$
        BEGIN
            IF TG_OP = 'DELETE' THEN
                IF OLD.estat IN ('EMESA_VERIFACTU', 'COBRADA', 'IMPAGADA') THEN
                    RAISE EXCEPTION 'VERIFACTU_IMMUTABLE_VIOLATION: Una factura SaaS B2B emesa a Veri*factu és immutable i no es pot eliminar.';
                END IF;
                RETURN OLD;
            ELSIF TG_OP = 'UPDATE' THEN
                IF OLD.estat IN ('EMESA_VERIFACTU', 'COBRADA', 'IMPAGADA') THEN
                    IF NEW.serie IS DISTINCT FROM OLD.serie
                       OR NEW.exercici IS DISTINCT FROM OLD.exercici
                       OR NEW.numero_factura IS DISTINCT FROM OLD.numero_factura
                       OR (OLD.num_serie_verifactu IS NOT NULL AND NEW.num_serie_verifactu IS DISTINCT FROM OLD.num_serie_verifactu)
                       OR NEW.base_imposable IS DISTINCT FROM OLD.base_imposable
                       OR NEW.quota_iva IS DISTINCT FROM OLD.quota_iva
                       OR NEW.import_total IS DISTINCT FROM OLD.import_total
                       OR NEW.hash_sha256 IS DISTINCT FROM OLD.hash_sha256
                       OR NEW.hash_anterior IS DISTINCT FROM OLD.hash_anterior
                       OR (OLD.fecha_hora_huso_gen_registro IS NOT NULL AND NEW.fecha_hora_huso_gen_registro IS DISTINCT FROM OLD.fecha_hora_huso_gen_registro)
                       OR (OLD.qr_verifactu IS NOT NULL AND NEW.qr_verifactu IS DISTINCT FROM OLD.qr_verifactu)
                       OR NEW.estat = 'ESBORRANY_PREFACTURA'
                    THEN
                        RAISE EXCEPTION 'VERIFACTU_IMMUTABLE_VIOLATION: Els camps fiscals i criptogràfics d una factura SaaS B2B emesa a Veri*factu són immutables.';
                    END IF;
                    IF OLD.estat_anulacio = 'ANULADA_VERIFACTU'
                       AND (NEW.estat_anulacio IS DISTINCT FROM OLD.estat_anulacio
                            OR NEW.hash_anulacio_sha256 IS DISTINCT FROM OLD.hash_anulacio_sha256)
                    THEN
                        RAISE EXCEPTION 'VERIFACTU_IMMUTABLE_VIOLATION: Un registre d anul·lació SaaS B2B Veri*factu no es pot revertir.';
                    END IF;
                END IF;
                RETURN NEW;
            END IF;
            RETURN NULL;
        END;
        $$ LANGUAGE plpgsql
        """
    )
    op.execute("DROP TRIGGER IF EXISTS trg_saas_factures_immutable ON public.saas_factures_b2b")
    op.execute(
        """
        CREATE TRIGGER trg_saas_factures_immutable
        BEFORE UPDATE OR DELETE ON public.saas_factures_b2b
        FOR EACH ROW EXECUTE FUNCTION public.fn_prevent_saas_invoice_mutation()
        """
    )

    # 9. Actualitzar obtenir_detall_factura_comercial i permisos
    op.execute(
        """
        CREATE OR REPLACE FUNCTION public.obtenir_detall_factura_comercial(
            p_empresa_id UUID,
            p_factura_id UUID
        )
        RETURNS JSONB
        LANGUAGE plpgsql
        SECURITY DEFINER
        SET search_path = public
        AS $$
        DECLARE
            v_ctx_emp TEXT := NULLIF(current_setting('app.current_empresa_id', true), '');
            v_ctx_rol TEXT := UPPER(COALESCE(NULLIF(current_setting('app.current_user_role', true), ''), ''));
            v_vinculada_ot BOOLEAN := FALSE;
            v_cap JSONB;
            v_linies JSONB;
            v_ot_codis JSONB;
        BEGIN
            IF v_ctx_emp IS NULL OR v_ctx_emp::uuid <> p_empresa_id THEN
                RETURN NULL;
            END IF;
            IF v_ctx_rol NOT IN ('BOSS', 'SUPERADMIN', 'SECRETARIA', 'COMPTABILITAT', 'ENGINYER') THEN
                RETURN NULL;
            END IF;

            IF v_ctx_rol = 'ENGINYER' THEN
                SELECT EXISTS (
                    SELECT 1
                    FROM public.ordres_treball ot
                    WHERE ot.empresa_id = p_empresa_id
                      AND ot.factura_id = p_factura_id
                ) OR EXISTS (
                    SELECT 1
                    FROM public.factures_linies fl
                    INNER JOIN public.ordres_treball ot2
                        ON ot2.id = fl.obra_id AND ot2.empresa_id = p_empresa_id
                    WHERE fl.empresa_id = p_empresa_id
                      AND fl.factura_id = p_factura_id
                ) INTO v_vinculada_ot;

                IF NOT v_vinculada_ot THEN
                    RETURN NULL;
                END IF;
            END IF;

            SELECT COALESCE(
                jsonb_agg(DISTINCT ot.codi ORDER BY ot.codi),
                '[]'::jsonb
            )
            INTO v_ot_codis
            FROM public.ordres_treball ot
            WHERE ot.empresa_id = p_empresa_id
              AND (
                  ot.factura_id = p_factura_id
                  OR EXISTS (
                      SELECT 1
                      FROM public.factures_linies fl2
                      WHERE fl2.empresa_id = p_empresa_id
                        AND fl2.factura_id = p_factura_id
                        AND fl2.obra_id = ot.id
                  )
              );

            SELECT jsonb_build_object(
                'id', fc.id::text,
                'client_id', fc.client_id::text,
                'client_nom', c.rao_social,
                'client_nif', c.nif,
                'client_adreca', c.adreca_fiscal,
                'client_cp', c.codi_postal,
                'client_poblacio', c.poblacio,
                'client_provincia', c.provincia,
                'client_email', c.email,
                'exercici', fc.exercici,
                'serie', fc.serie,
                'numero_factura', fc.numero_factura,
                'num_serie_verifactu', COALESCE(fc.num_serie_verifactu, fc.serie || '-' || fc.exercici::text || '-' || LPAD(fc.numero_factura::text, 4, '0')),
                'tipus_factura', COALESCE(fc.tipus_factura, 'F1'),
                'tipus_rectificacio', fc.tipus_rectificacio,
                'estat_document', fc.estat_document,
                'estat_cobrament', fc.estat_cobrament,
                'estat_anulacio', COALESCE(fc.estat_anulacio, 'ACTIVA'),
                'data_emissio', fc.data_emissio,
                'data_operacio', fc.data_operacio,
                'data_venciment', fc.data_venciment,
                'metode_pagament', COALESCE(fc.metode_pagament, 'TRANSFERENCIA'),
                'referencia_client', fc.referencia_client,
                'base_imposable', ROUND(COALESCE(fc.base_imposable, 0)::numeric, 2),
                'quota_iva', ROUND(COALESCE(fc.quota_iva, 0)::numeric, 2),
                'quota_recarrec_equivalencia', ROUND(COALESCE(fc.quota_recarrec_equivalencia, 0)::numeric, 2),
                'import_total_verifactu', ROUND(COALESCE(fc.import_total_verifactu, COALESCE(fc.base_imposable, 0) + COALESCE(fc.quota_iva, 0))::numeric, 2),
                'import_suplits', ROUND(COALESCE(fc.import_suplits, 0)::numeric, 2),
                'import_retencio', ROUND(COALESCE(fc.import_retencio, 0)::numeric, 2),
                'import_retencio_garantia_4308', ROUND(COALESCE(fc.import_retencio_garantia_4308, 0)::numeric, 2),
                'liquid_exigible', ROUND(COALESCE(fc.liquid_exigible, 0)::numeric, 2),
                'es_inversio_subjecte_passiu', COALESCE(fc.es_inversio_subjecte_passiu, FALSE),
                'causa_exempcio', fc.causa_exempcio,
                'mencio_legal', fc.mencio_legal,
                'notes_factura', fc.notes_factura,
                'motiu_rectificacio', fc.motiu_rectificacio,
                'hash_sha256', fc.hash_sha256,
                'hash_anterior', fc.hash_anterior,
                'qr_verifactu_payload', fc.qr_verifactu_payload,
                'pdf_path', fc.pdf_path,
                'ordres_treball_codis', v_ot_codis
            )
            INTO v_cap
            FROM public.factures_capcalera fc
            LEFT JOIN public.clients c
                ON c.id = fc.client_id AND c.empresa_id = p_empresa_id
            WHERE fc.id = p_factura_id
              AND fc.empresa_id = p_empresa_id;

            IF v_cap IS NULL THEN
                RETURN NULL;
            END IF;

            SELECT COALESCE(
                jsonb_agg(
                    jsonb_build_object(
                        'id', fl.id::text,
                        'concepte', fl.concepte,
                        'descripcio_detall', fl.descripcio_detall,
                        'quantitat', ROUND(COALESCE(fl.quantitat, 0)::numeric, 3),
                        'preu_venda_unitari', ROUND(COALESCE(fl.preu_venda_unitari, 0)::numeric, 2),
                        'tipus_iva', ROUND(COALESCE(fl.tipus_iva, 0)::numeric, 2),
                        'tipus_recarrec_equivalencia', ROUND(COALESCE(fl.tipus_recarrec_equivalencia, 0)::numeric, 2),
                        'quota_recarrec_linia', ROUND(COALESCE(fl.quota_recarrec_linia, 0)::numeric, 2),
                        'subtotal', ROUND(COALESCE(fl.subtotal, 0)::numeric, 2),
                        'descompte_aplicat_pct', ROUND(COALESCE(fl.descompte_aplicat_pct, 0)::numeric, 2),
                        'obra_id', CASE WHEN fl.obra_id IS NOT NULL THEN fl.obra_id::text ELSE NULL END
                    )
                    ORDER BY fl.created_at ASC
                ),
                '[]'::jsonb
            )
            INTO v_linies
            FROM public.factures_linies fl
            WHERE fl.factura_id = p_factura_id
              AND fl.empresa_id = p_empresa_id;

            RETURN v_cap || jsonb_build_object('linies', v_linies);
        END;
        $$
        """
    )
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'sevalor_app') THEN
                GRANT SELECT, INSERT, UPDATE, DELETE ON public.verifactu_cadena_tenant TO sevalor_app;
                GRANT EXECUTE ON FUNCTION public.obtenir_detall_factura_comercial(UUID, UUID) TO sevalor_app;
            END IF;
        END
        $$
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_factures_verifactu_immutable ON public.factures_capcalera")
    op.execute("DROP FUNCTION IF EXISTS public.fn_prevent_verifactu_invoice_mutation()")
    op.execute("DROP TRIGGER IF EXISTS trg_saas_factures_immutable ON public.saas_factures_b2b")
    op.execute("DROP FUNCTION IF EXISTS public.fn_prevent_saas_invoice_mutation()")
    op.execute("DROP TABLE IF EXISTS public.verifactu_cadena_tenant")
    op.execute("DROP INDEX IF EXISTS public.idx_outbox_aeat_pendents")
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM pg_constraint WHERE conname = 'uq_factures_empresa_exercici_serie_num'
            ) THEN
                ALTER TABLE public.factures_capcalera DROP CONSTRAINT uq_factures_empresa_exercici_serie_num;
            END IF;
        END
        $$
        """
    )
