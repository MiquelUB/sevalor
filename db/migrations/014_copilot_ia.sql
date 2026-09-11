-- 014_copilot_ia.sql
-- Mòdul d'IA Copilot de Camp i Gestió: Memòria Tècnica, Peritatge Multimodal, Garanties, Reconciliació Post-Obra i Xat RAG (/gestio/copilot — Spec 012)

-- 1. Ampliació de la taula empreses amb paràmetres de vertical d'ofici i node d'IA local
ALTER TABLE empreses
    ADD COLUMN IF NOT EXISTS vertical VARCHAR(50) NOT NULL DEFAULT 'CAMPOPRO',
    ADD COLUMN IF NOT EXISTS node_ia_url VARCHAR(255) NOT NULL DEFAULT 'http://localhost:11434',
    ADD COLUMN IF NOT EXISTS node_ia_actiu BOOLEAN NOT NULL DEFAULT true;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'empreses_vertical_check'
    ) THEN
        ALTER TABLE empreses ADD CONSTRAINT empreses_vertical_check
            CHECK (vertical IN ('CAMPOPRO', 'ELECTRICPRO', 'HYDROPRO', 'BUILDINGPRO'));
    END IF;
END $$;

-- 2. Taula de Memoràndums Tècnics de Camp (Peritatge Multimodal Veu + Foto)
CREATE TABLE IF NOT EXISTS memorandums_tecnics_copilot (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    empresa_id UUID NOT NULL REFERENCES empreses(id) ON DELETE CASCADE,
    ordre_treball_id UUID REFERENCES ordres_treball(id) ON DELETE SET NULL,
    incidencia_id UUID REFERENCES incidencies(id) ON DELETE SET NULL,
    transcripcio_audio TEXT,
    confianca_acustica NUMERIC(4, 2) NOT NULL DEFAULT 1.00,
    avis_soroll_sever BOOLEAN NOT NULL DEFAULT false, -- True si confianca < 0.40 (EDGE-03)
    analisi_visual TEXT,
    dictamen_pericial VARCHAR(30) NOT NULL DEFAULT 'EXTRA_FACTURABLE' CHECK (dictamen_pericial IN ('EXTRA_FACTURABLE', 'COST_NO_IMPUTABLE')),
    motiu_dictamen TEXT NOT NULL,
    estimacio_temps_extra_minuts INT NOT NULL DEFAULT 0,
    estimacio_materials_extra JSONB NOT NULL DEFAULT '[]'::jsonb,
    cost_estimat_total NUMERIC(10, 2) NOT NULL DEFAULT 0.00,
    validat_per_enginyer BOOLEAN NOT NULL DEFAULT false,
    enginyer_validador_id UUID REFERENCES usuaris(id) ON DELETE SET NULL,
    data_validacio TIMESTAMPTZ,
    observacions_enginyer TEXT,
    estat VARCHAR(20) NOT NULL DEFAULT 'PROPOSTA' CHECK (estat IN ('PROPOSTA', 'APROVAT', 'REBUTJAT', 'EDITAT')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_memo_empresa ON memorandums_tecnics_copilot(empresa_id);
CREATE INDEX IF NOT EXISTS idx_memo_ot ON memorandums_tecnics_copilot(ordre_treball_id);
CREATE INDEX IF NOT EXISTS idx_memo_incidencia ON memorandums_tecnics_copilot(incidencia_id);
CREATE INDEX IF NOT EXISTS idx_memo_estat ON memorandums_tecnics_copilot(estat);

CREATE TRIGGER trigger_update_memorandums_updated_at
    BEFORE UPDATE ON memorandums_tecnics_copilot
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- 3. Taula d'Auditories de Pre-Facturació Post-Obra i Control de Desviacions
CREATE TABLE IF NOT EXISTS auditories_post_obra (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    empresa_id UUID NOT NULL REFERENCES empreses(id) ON DELETE CASCADE,
    ordre_treball_id UUID NOT NULL REFERENCES ordres_treball(id) ON DELETE CASCADE,
    desviacio_hores NUMERIC(6, 2) NOT NULL DEFAULT 0.00,
    desviacio_materials JSONB NOT NULL DEFAULT '[]'::jsonb,
    desviacio_km NUMERIC(8, 2) NOT NULL DEFAULT 0.00,
    despeses_camp NUMERIC(10, 2) NOT NULL DEFAULT 0.00,
    marge_previst_percentatge NUMERIC(5, 2) NOT NULL DEFAULT 30.00,
    marge_real_liquidat_percentatge NUMERIC(5, 2) NOT NULL DEFAULT 30.00,
    alerta_merma_operativa BOOLEAN NOT NULL DEFAULT false,
    detall_merma TEXT,
    bloqueig_consum_excessiu BOOLEAN NOT NULL DEFAULT false, -- EDGE-08 (>250% continu sense incidència)
    bloqueig_sync_pendent BOOLEAN NOT NULL DEFAULT false,    -- EDGE-04 (offline sync pendent)
    pressupost_corregit_proposta JSONB NOT NULL DEFAULT '{}'::jsonb,
    estat VARCHAR(30) NOT NULL DEFAULT 'PENDENT_CONFIRMACIO' CHECK (estat IN ('PENDENT_CONFIRMACIO', 'APROVAT_ENGINYER', 'ENVIAT_FACTURACIO', 'REBUTJAT')),
    enginyer_id UUID REFERENCES usuaris(id) ON DELETE SET NULL,
    data_aprovacio TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_auditories_ordre UNIQUE (ordre_treball_id)
);

CREATE INDEX IF NOT EXISTS idx_auditories_empresa ON auditories_post_obra(empresa_id);
CREATE INDEX IF NOT EXISTS idx_auditories_ordre ON auditories_post_obra(ordre_treball_id);
CREATE INDEX IF NOT EXISTS idx_auditories_estat ON auditories_post_obra(estat);

CREATE TRIGGER trigger_update_auditories_updated_at
    BEFORE UPDATE ON auditories_post_obra
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- 4. Taula d'Alertes de Garantia i Recompra de Stock
CREATE TABLE IF NOT EXISTS alertes_garantia_recompra (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    empresa_id UUID NOT NULL REFERENCES empreses(id) ON DELETE CASCADE,
    ordre_treball_id UUID REFERENCES ordres_treball(id) ON DELETE SET NULL,
    tipus_alerta VARCHAR(30) NOT NULL CHECK (tipus_alerta IN ('GARANTIA_FABRICANT', 'GARANTIA_INTERNA_SERVEI', 'CORTESIA_EXPIRADA', 'RECOMPRA_STOCK')),
    article_id UUID REFERENCES articles(id) ON DELETE SET NULL,
    numero_serie VARCHAR(100),
    proveidor_id UUID REFERENCES proveidors(id) ON DELETE SET NULL,
    missatge TEXT NOT NULL,
    data_fi_garantia DATE,
    estat VARCHAR(20) NOT NULL DEFAULT 'ACTIVA' CHECK (estat IN ('ACTIVA', 'RESOLTA', 'DESCARTADA')),
    dades_comanda_proposta JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_alertes_copilot_empresa ON alertes_garantia_recompra(empresa_id);
CREATE INDEX IF NOT EXISTS idx_alertes_copilot_tipus ON alertes_garantia_recompra(tipus_alerta);
CREATE INDEX IF NOT EXISTS idx_alertes_copilot_estat ON alertes_garantia_recompra(estat);

CREATE TRIGGER trigger_update_alertes_copilot_updated_at
    BEFORE UPDATE ON alertes_garantia_recompra
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- 5. Taula de Consultes del Xat Tècnic Copilot
CREATE TABLE IF NOT EXISTS consultes_xat_copilot (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    empresa_id UUID NOT NULL REFERENCES empreses(id) ON DELETE CASCADE,
    usuari_id UUID NOT NULL REFERENCES usuaris(id) ON DELETE CASCADE,
    pregunta TEXT NOT NULL,
    resposta TEXT NOT NULL,
    vertical VARCHAR(50) NOT NULL DEFAULT 'CAMPOPRO',
    temps_inferencia_ms INT NOT NULL DEFAULT 0,
    enllacos_relacionats JSONB NOT NULL DEFAULT '[]'::jsonb,
    es_error_timeout BOOLEAN NOT NULL DEFAULT false,
    denegat_per_rol BOOLEAN NOT NULL DEFAULT false,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_xat_copilot_empresa ON consultes_xat_copilot(empresa_id);
CREATE INDEX IF NOT EXISTS idx_xat_copilot_usuari ON consultes_xat_copilot(usuari_id);
CREATE INDEX IF NOT EXISTS idx_xat_copilot_created ON consultes_xat_copilot(created_at);

-- 6. RLS Mandatori i Forçat
ALTER TABLE memorandums_tecnics_copilot ENABLE ROW LEVEL SECURITY;
ALTER TABLE memorandums_tecnics_copilot FORCE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS rls_memorandums_copilot_isolation ON memorandums_tecnics_copilot;
CREATE POLICY rls_memorandums_copilot_isolation ON memorandums_tecnics_copilot
FOR ALL
USING (
    empresa_id::text = current_setting('app.current_empresa_id', true)
    OR current_setting('app.is_superadmin', true) = 'true'
);

ALTER TABLE auditories_post_obra ENABLE ROW LEVEL SECURITY;
ALTER TABLE auditories_post_obra FORCE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS rls_auditories_copilot_isolation ON auditories_post_obra;
CREATE POLICY rls_auditories_copilot_isolation ON auditories_post_obra
FOR ALL
USING (
    empresa_id::text = current_setting('app.current_empresa_id', true)
    OR current_setting('app.is_superadmin', true) = 'true'
);

ALTER TABLE alertes_garantia_recompra ENABLE ROW LEVEL SECURITY;
ALTER TABLE alertes_garantia_recompra FORCE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS rls_alertes_copilot_isolation ON alertes_garantia_recompra;
CREATE POLICY rls_alertes_copilot_isolation ON alertes_garantia_recompra
FOR ALL
USING (
    empresa_id::text = current_setting('app.current_empresa_id', true)
    OR current_setting('app.is_superadmin', true) = 'true'
);

ALTER TABLE consultes_xat_copilot ENABLE ROW LEVEL SECURITY;
ALTER TABLE consultes_xat_copilot FORCE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS rls_consultes_copilot_isolation ON consultes_xat_copilot;
CREATE POLICY rls_consultes_copilot_isolation ON consultes_xat_copilot
FOR ALL
USING (
    empresa_id::text = current_setting('app.current_empresa_id', true)
    OR current_setting('app.is_superadmin', true) = 'true'
);

-- 7. Concessió de permisos al rol de l'aplicació
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO sevalor_app;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO sevalor_app;
