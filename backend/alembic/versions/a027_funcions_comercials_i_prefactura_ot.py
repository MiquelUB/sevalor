"""a027: Funcions SQL SECURITY DEFINER estrictament acotades per consulta comercial d'OT/client i pre-facturació des de Fulla 360°.

Preserva intactes totes les polítiques RLS RESTRICTIVE `economics_boss_only_*` sobre consultes globals
a `factures_capcalera`, `factures_linies` i `registre_esdeveniments_sif`.

Revision ID: a027_prefactura_ot_comercial
Revises: a026_conciliacio_validacio_ot
Create Date: 2026-11-23
"""

from typing import Sequence, Union

from alembic import op

revision: str = "a027_prefactura_ot_comercial"
down_revision: Union[str, Sequence[str], None] = "a026_conciliacio_validacio_ot"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Detall comercial d'una factura / pre-factura vinculada a una OT/client (per a Fulla 360°, Fitxa Client i PDF)
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

            -- Per a ENGINYER només és accessible si la factura/pre-factura està vinculada a alguna tasca (OT) del tenant
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
                'serie', fc.serie,
                'numero_factura', fc.numero_factura,
                'estat_document', fc.estat_document,
                'estat_cobrament', fc.estat_cobrament,
                'data_emissio', fc.data_emissio,
                'data_venciment', fc.data_venciment,
                'base_imposable', ROUND(COALESCE(fc.base_imposable, 0)::numeric, 2),
                'quota_iva', ROUND(COALESCE(fc.quota_iva, 0)::numeric, 2),
                'import_suplits', ROUND(COALESCE(fc.import_suplits, 0)::numeric, 2),
                'import_retencio', ROUND(COALESCE(fc.import_retencio, 0)::numeric, 2),
                'import_retencio_garantia_4308', ROUND(COALESCE(fc.import_retencio_garantia_4308, 0)::numeric, 2),
                'liquid_exigible', ROUND(COALESCE(fc.liquid_exigible, 0)::numeric, 2),
                'es_inversio_subjecte_passiu', COALESCE(fc.es_inversio_subjecte_passiu, FALSE),
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
                        'quantitat', ROUND(COALESCE(fl.quantitat, 0)::numeric, 3),
                        'preu_venda_unitari', ROUND(COALESCE(fl.preu_venda_unitari, 0)::numeric, 2),
                        'tipus_iva', ROUND(COALESCE(fl.tipus_iva, 0)::numeric, 2),
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
        $$;
        """
    )

    # 2. Resum en batch de factures vinculades a un conjunt d'OTs (per badges i disclaimer al llistat /gestio/feines)
    op.execute(
        """
        CREATE OR REPLACE FUNCTION public.obtenir_resum_factures_ots(
            p_empresa_id UUID,
            p_ot_ids UUID[]
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
                RETURN '{}'::jsonb;
            END IF;
            IF v_ctx_rol NOT IN ('BOSS', 'SUPERADMIN', 'SECRETARIA', 'COMPTABILITAT', 'ENGINYER') THEN
                RETURN '{}'::jsonb;
            END IF;
            IF p_ot_ids IS NULL OR array_length(p_ot_ids, 1) IS NULL THEN
                RETURN '{}'::jsonb;
            END IF;

            SELECT COALESCE(
                jsonb_object_agg(
                    ot.id::text,
                    jsonb_build_object(
                        'factura_id', fc.id::text,
                        'serie', fc.serie,
                        'numero_factura', fc.numero_factura,
                        'estat_document', fc.estat_document
                    )
                ),
                '{}'::jsonb
            )
            INTO v_res
            FROM public.ordres_treball ot
            INNER JOIN public.factures_capcalera fc
                ON fc.id = ot.factura_id AND fc.empresa_id = p_empresa_id
            WHERE ot.empresa_id = p_empresa_id
              AND ot.id = ANY(p_ot_ids)
              AND ot.factura_id IS NOT NULL;

            RETURN v_res;
        END;
        $$;
        """
    )

    # 3. Creació atòmica de Pre-factura Sèrie PRE (ESBORRANY_PREFACTURA) per a una OT VALIDADA_PER_FACTURAR
    # accessible als 3 rols operatius (ENGINYER, SECRETARIA, BOSS) sense obrir accés directe d'escriptura a factures emeses.
    op.execute(
        """
        CREATE OR REPLACE FUNCTION public.crear_prefactura_ot_autoritzada(
            p_empresa_id UUID,
            p_usuari_id UUID,
            p_ordre_treball_id UUID,
            p_data_emissio DATE,
            p_data_venciment DATE,
            p_linies JSONB
        )
        RETURNS JSONB
        LANGUAGE plpgsql
        SECURITY DEFINER
        SET search_path = public
        AS $$
        DECLARE
            v_ctx_emp TEXT := NULLIF(current_setting('app.current_empresa_id', true), '');
            v_ctx_rol TEXT := UPPER(COALESCE(NULLIF(current_setting('app.current_user_role', true), ''), ''));
            v_ot RECORD;
            v_exercici INT := EXTRACT(YEAR FROM p_data_emissio)::INT;
            v_serie_id UUID;
            v_num_pref INT;
            v_factura_id UUID := gen_random_uuid();
            v_lin JSONB;
            v_qty NUMERIC(12, 3);
            v_pvp NUMERIC(10, 2);
            v_iva_pct NUMERIC(4, 2);
            v_sub NUMERIC(12, 2);
            v_iva_lin NUMERIC(12, 2);
            v_base_total NUMERIC(12, 2) := 0;
            v_iva_total NUMERIC(12, 2) := 0;
            v_liquid_total NUMERIC(12, 2) := 0;
            v_art_id UUID;
            v_cost_hist NUMERIC(12, 4);
            v_linies_out JSONB := '[]'::jsonb;
            v_lin_id UUID;
            v_sello TEXT;
        BEGIN
            IF v_ctx_emp IS NULL OR v_ctx_emp::uuid <> p_empresa_id THEN
                RAISE EXCEPTION 'TENANT_CONTEXT_MISMATCH' USING ERRCODE = '42501';
            END IF;
            IF v_ctx_rol NOT IN ('BOSS', 'SUPERADMIN', 'SECRETARIA', 'COMPTABILITAT', 'ENGINYER') THEN
                RAISE EXCEPTION 'ROLE_NOT_AUTHORIZED' USING ERRCODE = '42501';
            END IF;

            SELECT id, codi, client_id, estat, factura_id
            INTO v_ot
            FROM public.ordres_treball
            WHERE id = p_ordre_treball_id
              AND empresa_id = p_empresa_id
            FOR UPDATE;

            IF NOT FOUND THEN
                RAISE EXCEPTION 'OT_NOT_FOUND' USING ERRCODE = 'P0002';
            END IF;
            IF v_ot.factura_id IS NOT NULL THEN
                RAISE EXCEPTION 'OT_ALREADY_INVOICED' USING ERRCODE = 'P0001';
            END IF;
            IF v_ot.client_id IS NULL THEN
                RAISE EXCEPTION 'OT_NO_CLIENT' USING ERRCODE = 'P0001';
            END IF;
            IF UPPER(COALESCE(v_ot.estat, '')) <> 'VALIDADA_PER_FACTURAR' THEN
                RAISE EXCEPTION 'OT_NOT_VALIDATED' USING ERRCODE = 'P0001';
            END IF;
            IF p_linies IS NULL OR jsonb_typeof(p_linies) <> 'array' OR jsonb_array_length(p_linies) = 0 THEN
                RAISE EXCEPTION 'PREFACTURA_EMPTY_LINES' USING ERRCODE = 'P0001';
            END IF;

            -- Bloqueig atòmic o alta de la sèrie PRE per a l'exercici
            SELECT id, ultim_numero
            INTO v_serie_id, v_num_pref
            FROM public.series_fiscals_verifactu
            WHERE empresa_id = p_empresa_id
              AND codi_serie = 'PRE'
              AND exercici = v_exercici
            FOR UPDATE;

            IF NOT FOUND THEN
                v_serie_id := gen_random_uuid();
                v_num_pref := 1;
                INSERT INTO public.series_fiscals_verifactu (
                    id, empresa_id, codi_serie, exercici, ultim_numero, ultim_hash_sha256
                )
                VALUES (
                    v_serie_id, p_empresa_id, 'PRE', v_exercici, v_num_pref, repeat('0', 64)
                );
            ELSE
                v_num_pref := v_num_pref + 1;
                UPDATE public.series_fiscals_verifactu
                SET ultim_numero = v_num_pref
                WHERE id = v_serie_id;
            END IF;

            -- Precalcular totals de capçalera
            FOR v_lin IN SELECT * FROM jsonb_array_elements(p_linies)
            LOOP
                v_qty := ROUND(COALESCE((v_lin->>'quantitat')::NUMERIC, 1), 3);
                v_pvp := ROUND(COALESCE((v_lin->>'preu_venda_unitari')::NUMERIC, 0), 2);
                v_iva_pct := ROUND(COALESCE((v_lin->>'tipus_iva')::NUMERIC, 21), 2);
                v_sub := ROUND(v_qty * v_pvp, 2);
                v_iva_lin := ROUND(v_sub * (v_iva_pct / 100.0), 2);
                v_base_total := v_base_total + v_sub;
                v_iva_total := v_iva_total + v_iva_lin;
            END LOOP;
            v_liquid_total := ROUND(v_base_total + v_iva_total, 2);

            -- Inserir capçalera exclusivament com ESBORRANY_PREFACTURA / Sèrie PRE (mai EMESA)
            INSERT INTO public.factures_capcalera (
                id,
                empresa_id,
                numero_factura,
                serie,
                client_id,
                data_emissio,
                data_venciment,
                base_imposable,
                quota_iva,
                import_retencio,
                import_suplits,
                import_retencio_garantia_4308,
                liquid_exigible,
                estat_cobrament,
                estat_enviament,
                estat_document,
                metode_pagament,
                es_inversio_subjecte_passiu,
                hash_anterior,
                hash_sha256,
                qr_verifactu_payload,
                created_at,
                updated_at
            )
            VALUES (
                v_factura_id,
                p_empresa_id,
                v_num_pref,
                'PRE',
                v_ot.client_id,
                (p_data_emissio::TIMESTAMP AT TIME ZONE 'UTC'),
                COALESCE(p_data_venciment, p_data_emissio),
                v_base_total,
                v_iva_total,
                0.00,
                0.00,
                0.00,
                v_liquid_total,
                'PENDENT',
                'ESBORRANY',
                'ESBORRANY_PREFACTURA',
                'TRANSFERENCIA',
                FALSE,
                NULL,
                'ESBORRANY_PREFACTURA',
                NULL,
                NOW(),
                NOW()
            );

            -- Inserir línies de la pre-factura
            FOR v_lin IN SELECT * FROM jsonb_array_elements(p_linies)
            LOOP
                v_lin_id := gen_random_uuid();
                v_qty := ROUND(COALESCE((v_lin->>'quantitat')::NUMERIC, 1), 3);
                v_pvp := ROUND(COALESCE((v_lin->>'preu_venda_unitari')::NUMERIC, 0), 2);
                v_iva_pct := ROUND(COALESCE((v_lin->>'tipus_iva')::NUMERIC, 21), 2);
                v_sub := ROUND(v_qty * v_pvp, 2);
                v_art_id := NULLIF(v_lin->>'article_id', '')::UUID;
                v_cost_hist := 0.0000;

                IF v_art_id IS NOT NULL THEN
                    SELECT COALESCE(a.preu_cost, 0)
                    INTO v_cost_hist
                    FROM public.articles a
                    WHERE a.id = v_art_id AND a.empresa_id = p_empresa_id;
                    IF NOT FOUND THEN
                        v_cost_hist := 0.0000;
                    END IF;
                END IF;

                INSERT INTO public.factures_linies (
                    id,
                    empresa_id,
                    factura_id,
                    obra_id,
                    article_id,
                    concepte,
                    quantitat,
                    preu_venda_unitari,
                    tipus_iva,
                    subtotal,
                    compte_pgc,
                    quantitat_merma,
                    descompte_aplicat_pct,
                    cost_unitari_historic,
                    created_at
                )
                VALUES (
                    v_lin_id,
                    p_empresa_id,
                    v_factura_id,
                    p_ordre_treball_id,
                    v_art_id,
                    LEFT(COALESCE(v_lin->>'concepte', 'Servei tècnic'), 200),
                    v_qty,
                    v_pvp,
                    v_iva_pct,
                    v_sub,
                    '700000',
                    0.00,
                    0.00,
                    v_cost_hist,
                    NOW()
                );

                v_linies_out := v_linies_out || jsonb_build_array(
                    jsonb_build_object(
                        'id', v_lin_id::text,
                        'concepte', LEFT(COALESCE(v_lin->>'concepte', 'Servei tècnic'), 200),
                        'quantitat', v_qty,
                        'preu_venda_unitari', v_pvp,
                        'tipus_iva', v_iva_pct,
                        'subtotal', v_sub
                    )
                );
            END LOOP;

            -- Actualitzar l'Ordre de Treball a PREFACTURADA vinculant la pre-factura creada
            UPDATE public.ordres_treball
            SET factura_id = v_factura_id,
                estat = 'PREFACTURADA',
                updated_at = NOW()
            WHERE id = p_ordre_treball_id
              AND empresa_id = p_empresa_id;

            -- Registrar esdeveniment SIF EV-01 (auditoria immutable)
            v_sello := encode(
                sha256(
                    convert_to(
                        p_empresa_id::text || '|' || COALESCE(p_usuari_id::text, '') || '|EV-01|PRE-' || v_exercici::text || '-' || lpad(v_num_pref::text, 4, '0') || '|' || NOW()::text,
                        'UTF8'
                    )
                ),
                'hex'
            );
            INSERT INTO public.registre_esdeveniments_sif (
                id,
                empresa_id,
                codi_esdeveniment,
                usuari_id,
                descripcio,
                hash_sello,
                dades_event,
                data_creacio
            )
            VALUES (
                gen_random_uuid(),
                p_empresa_id,
                'EV-01',
                p_usuari_id,
                'Creació Esborrany Pre-factura PRE-' || v_exercici::text || '-' || lpad(v_num_pref::text, 4, '0') || ' des de Fulla 360° (OT ' || v_ot.codi || ')',
                v_sello,
                jsonb_build_object(
                    'ordre_treball_id', p_ordre_treball_id::text,
                    'factura_id', v_factura_id::text,
                    'rol_origen', v_ctx_rol
                ),
                NOW()
            );

            RETURN jsonb_build_object(
                'id', v_factura_id::text,
                'serie', 'PRE',
                'numero_factura', v_num_pref,
                'estat_document', 'ESBORRANY_PREFACTURA',
                'data_emissio', p_data_emissio::text,
                'data_venciment', COALESCE(p_data_venciment, p_data_emissio)::text,
                'base_imposable', v_base_total,
                'quota_iva', v_iva_total,
                'liquid_exigible', v_liquid_total,
                'ordre_treball_id', p_ordre_treball_id::text,
                'linies', v_linies_out
            );
        END;
        $$;
        """
    )

    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'sevalor_app') THEN
                GRANT EXECUTE ON FUNCTION public.obtenir_detall_factura_comercial(UUID, UUID) TO sevalor_app;
                GRANT EXECUTE ON FUNCTION public.obtenir_resum_factures_ots(UUID, UUID[]) TO sevalor_app;
                GRANT EXECUTE ON FUNCTION public.crear_prefactura_ot_autoritzada(UUID, UUID, UUID, DATE, DATE, JSONB) TO sevalor_app;
            END IF;
        END
        $$;
        """
    )


def downgrade() -> None:
    op.execute(
        "DROP FUNCTION IF EXISTS public.crear_prefactura_ot_autoritzada(UUID, UUID, UUID, DATE, DATE, JSONB);"
    )
    op.execute("DROP FUNCTION IF EXISTS public.obtenir_resum_factures_ots(UUID, UUID[]);")
    op.execute("DROP FUNCTION IF EXISTS public.obtenir_detall_factura_comercial(UUID, UUID);")
