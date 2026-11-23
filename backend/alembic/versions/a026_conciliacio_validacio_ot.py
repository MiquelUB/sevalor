"""a026: Afegeix camps de signatura, receptor, conciliació i validació a ordres_treball i origen/consum aplicat a linies_picking.

Revision ID: a026_conciliacio_validacio_ot
Revises: a025_add_copilot_configs_rls
Create Date: 2026-11-23
"""

from typing import Sequence, Union

from alembic import op

revision: str = "a026_conciliacio_validacio_ot"
down_revision: Union[str, Sequence[str], None] = "a025_add_copilot_configs_rls"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE public.ordres_treball
            ADD COLUMN IF NOT EXISTS signatura_client_path VARCHAR(500),
            ADD COLUMN IF NOT EXISTS nom_receptor VARCHAR(150),
            ADD COLUMN IF NOT EXISTS dni_receptor VARCHAR(30),
            ADD COLUMN IF NOT EXISTS observacions_tancament TEXT,
            ADD COLUMN IF NOT EXISTS data_signatura TIMESTAMPTZ,
            ADD COLUMN IF NOT EXISTS validada_per_id UUID REFERENCES public.usuaris(id) ON DELETE SET NULL,
            ADD COLUMN IF NOT EXISTS data_validacio TIMESTAMPTZ,
            ADD COLUMN IF NOT EXISTS notes_validacio_tecnica TEXT,
            ADD COLUMN IF NOT EXISTS checklist_conciliacio JSONB NOT NULL DEFAULT '{}'::jsonb;
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_ordres_treball_validada_per_id
            ON public.ordres_treball (validada_per_id)
            WHERE validada_per_id IS NOT NULL;
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_ordres_treball_empresa_estat_pend_fact
            ON public.ordres_treball (empresa_id, estat)
            WHERE factura_id IS NULL;
        """
    )

    op.execute(
        """
        ALTER TABLE public.linies_picking
            ADD COLUMN IF NOT EXISTS origen_estoc VARCHAR(20) NOT NULL DEFAULT 'NAU',
            ADD COLUMN IF NOT EXISTS consum_aplicat_magatzem NUMERIC(12, 3) NOT NULL DEFAULT 0.000;
        """
    )
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1
                FROM pg_constraint
                WHERE conname = 'ck_linies_picking_origen_estoc'
            ) THEN
                ALTER TABLE public.linies_picking
                    ADD CONSTRAINT ck_linies_picking_origen_estoc
                    CHECK (origen_estoc IN ('NAU', 'FURGONETA'));
            END IF;
        END
        $$;
        """
    )

    # Funcions SECURITY DEFINER estrictament acotades a OT/Client perquè l'ENGINYER pugui consultar
    # pressupostos, pre-factures i factures comercials de les tasques d'un client (reclamacions)
    # SENSE relaxar les polítiques RLS `economics_boss_only` sobre consultes globals a factures_capcalera.
    op.execute(
        """
        CREATE OR REPLACE FUNCTION public.obtenir_factura_comercial_ot(
            p_empresa_id UUID,
            p_ordre_treball_id UUID
        )
        RETURNS JSONB
        LANGUAGE plpgsql
        SECURITY DEFINER
        SET search_path = public
        AS $$
        DECLARE
            v_ctx_emp TEXT := NULLIF(current_setting('app.current_empresa_id', true), '');
            v_ctx_rol TEXT := UPPER(COALESCE(NULLIF(current_setting('app.current_user_role', true), ''), ''));
            v_factura_id UUID;
            v_cap JSONB;
            v_linies JSONB;
        BEGIN
            IF v_ctx_emp IS NULL OR v_ctx_emp::uuid <> p_empresa_id THEN
                RETURN NULL;
            END IF;
            IF v_ctx_rol NOT IN ('BOSS', 'SUPERADMIN', 'SECRETARIA', 'COMPTABILITAT', 'ENGINYER') THEN
                RETURN NULL;
            END IF;

            SELECT ot.factura_id INTO v_factura_id
            FROM public.ordres_treball ot
            WHERE ot.id = p_ordre_treball_id
              AND ot.empresa_id = p_empresa_id;

            IF v_factura_id IS NULL THEN
                SELECT fl.factura_id INTO v_factura_id
                FROM public.factures_linies fl
                WHERE fl.obra_id = p_ordre_treball_id
                  AND fl.empresa_id = p_empresa_id
                ORDER BY fl.created_at DESC
                LIMIT 1;
            END IF;

            IF v_factura_id IS NULL THEN
                RETURN NULL;
            END IF;

            SELECT jsonb_build_object(
                'id', fc.id::text,
                'serie', fc.serie,
                'numero_factura', fc.numero_factura,
                'estat_document', fc.estat_document,
                'estat_cobrament', fc.estat_cobrament,
                'data_emissio', fc.data_emissio,
                'data_venciment', fc.data_venciment,
                'base_imposable', ROUND(COALESCE(fc.base_imposable, 0)::numeric, 2),
                'quota_iva', ROUND(COALESCE(fc.quota_iva, 0)::numeric, 2),
                'liquid_exigible', ROUND(COALESCE(fc.liquid_exigible, 0)::numeric, 2)
            )
            INTO v_cap
            FROM public.factures_capcalera fc
            WHERE fc.id = v_factura_id
              AND fc.empresa_id = p_empresa_id;

            IF v_cap IS NULL THEN
                RETURN NULL;
            END IF;

            SELECT COALESCE(
                jsonb_agg(
                    jsonb_build_object(
                        'id', fl.id::text,
                        'concepte', fl.concepte,
                        'quantitat', ROUND(COALESCE(fl.quantitat, 0)::numeric, 3),
                        'preu_venda_unitari', ROUND(COALESCE(fl.preu_venda_unitari, 0)::numeric, 2),
                        'tipus_iva', ROUND(COALESCE(fl.tipus_iva, 0)::numeric, 2),
                        'subtotal', ROUND(COALESCE(fl.subtotal, 0)::numeric, 2)
                    )
                    ORDER BY fl.created_at ASC
                ),
                '[]'::jsonb
            )
            INTO v_linies
            FROM public.factures_linies fl
            WHERE fl.factura_id = v_factura_id
              AND fl.empresa_id = p_empresa_id;

            RETURN v_cap || jsonb_build_object('linies', v_linies);
        END;
        $$;
        """
    )

    op.execute(
        """
        CREATE OR REPLACE FUNCTION public.obtenir_factures_comercials_client(
            p_empresa_id UUID,
            p_client_id UUID
        )
        RETURNS JSONB
        LANGUAGE plpgsql
        SECURITY DEFINER
        SET search_path = public
        AS $$
        DECLARE
            v_ctx_emp TEXT := NULLIF(current_setting('app.current_empresa_id', true), '');
            v_ctx_rol TEXT := UPPER(COALESCE(NULLIF(current_setting('app.current_user_role', true), ''), ''));
            v_res JSONB;
        BEGIN
            IF v_ctx_emp IS NULL OR v_ctx_emp::uuid <> p_empresa_id THEN
                RETURN '[]'::jsonb;
            END IF;
            IF v_ctx_rol NOT IN ('BOSS', 'SUPERADMIN', 'SECRETARIA', 'COMPTABILITAT', 'ENGINYER') THEN
                RETURN '[]'::jsonb;
            END IF;

            SELECT COALESCE(
                jsonb_agg(
                    jsonb_build_object(
                        'id', fc.id::text,
                        'serie', fc.serie,
                        'numero_factura', fc.numero_factura,
                        'estat_document', fc.estat_document,
                        'estat_cobrament', fc.estat_cobrament,
                        'data_emissio', fc.data_emissio,
                        'data_venciment', fc.data_venciment,
                        'base_imposable', ROUND(COALESCE(fc.base_imposable, 0)::numeric, 2),
                        'quota_iva', ROUND(COALESCE(fc.quota_iva, 0)::numeric, 2),
                        'liquid_exigible', ROUND(COALESCE(fc.liquid_exigible, 0)::numeric, 2),
                        'ordres_treball_codis', COALESCE(
                            (
                                SELECT jsonb_agg(DISTINCT ot.codi ORDER BY ot.codi)
                                FROM public.ordres_treball ot
                                WHERE ot.empresa_id = p_empresa_id
                                  AND ot.client_id = p_client_id
                                  AND (
                                      ot.factura_id = fc.id
                                      OR EXISTS (
                                          SELECT 1
                                          FROM public.factures_linies fl2
                                          WHERE fl2.empresa_id = p_empresa_id
                                            AND fl2.factura_id = fc.id
                                            AND fl2.obra_id = ot.id
                                      )
                                  )
                            ),
                            '[]'::jsonb
                        )
                    )
                    ORDER BY fc.data_emissio DESC, fc.numero_factura DESC
                ),
                '[]'::jsonb
            )
            INTO v_res
            FROM public.factures_capcalera fc
            WHERE fc.empresa_id = p_empresa_id
              AND fc.client_id = p_client_id
              AND (
                  EXISTS (
                      SELECT 1
                      FROM public.ordres_treball ot
                      WHERE ot.empresa_id = p_empresa_id
                        AND ot.client_id = p_client_id
                        AND ot.factura_id = fc.id
                  )
                  OR EXISTS (
                      SELECT 1
                      FROM public.factures_linies fl
                      INNER JOIN public.ordres_treball ot2
                          ON ot2.id = fl.obra_id AND ot2.empresa_id = p_empresa_id
                      WHERE fl.empresa_id = p_empresa_id
                        AND fl.factura_id = fc.id
                        AND ot2.client_id = p_client_id
                  )
              );

            RETURN v_res;
        END;
        $$;
        """
    )

    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'sevalor_app') THEN
                GRANT EXECUTE ON FUNCTION public.obtenir_factura_comercial_ot(UUID, UUID) TO sevalor_app;
                GRANT EXECUTE ON FUNCTION public.obtenir_factures_comercials_client(UUID, UUID) TO sevalor_app;
            END IF;
        END
        $$;
        """
    )


def downgrade() -> None:
    op.execute("DROP FUNCTION IF EXISTS public.obtenir_factures_comercials_client(UUID, UUID);")
    op.execute("DROP FUNCTION IF EXISTS public.obtenir_factura_comercial_ot(UUID, UUID);")
    op.execute(
        """
        ALTER TABLE public.linies_picking
            DROP CONSTRAINT IF EXISTS ck_linies_picking_origen_estoc;
        """
    )
    op.execute(
        """
        ALTER TABLE public.linies_picking
            DROP COLUMN IF EXISTS consum_aplicat_magatzem,
            DROP COLUMN IF EXISTS origen_estoc;
        """
    )
    op.execute("DROP INDEX IF EXISTS public.ix_ordres_treball_empresa_estat_pend_fact;")
    op.execute("DROP INDEX IF EXISTS public.ix_ordres_treball_validada_per_id;")
    op.execute(
        """
        ALTER TABLE public.ordres_treball
            DROP COLUMN IF EXISTS checklist_conciliacio,
            DROP COLUMN IF EXISTS notes_validacio_tecnica,
            DROP COLUMN IF EXISTS data_validacio,
            DROP COLUMN IF EXISTS validada_per_id,
            DROP COLUMN IF EXISTS data_signatura,
            DROP COLUMN IF EXISTS observacions_tancament,
            DROP COLUMN IF EXISTS dni_receptor,
            DROP COLUMN IF EXISTS nom_receptor,
            DROP COLUMN IF EXISTS signatura_client_path;
        """
    )
