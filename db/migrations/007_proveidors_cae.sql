-- 007_proveidors_cae.sql
-- Mòdul de Proveïdors, CAE (Coordinació d'Activitats Empresarials) i Prevenció Anti-Frau BEC (Spec 003)

CREATE TABLE IF NOT EXISTS proveidors (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    empresa_id UUID NOT NULL REFERENCES empreses(id) ON DELETE CASCADE,
    codi VARCHAR(20) NOT NULL, -- PRV-XXXX
    rao_social VARCHAR(200) NOT NULL,
    nif VARCHAR(20) NOT NULL,
    telefon VARCHAR(30),
    email VARCHAR(200),
    especialitat VARCHAR(50) NOT NULL DEFAULT 'MATERIALS' CHECK (especialitat IN ('MATERIALS', 'MAQUINARIA', 'SUBCONTRACTA')),
    es_recc BOOLEAN NOT NULL DEFAULT false, -- Règim Especial del Criteri de Caixa
    aplica_isp_defecte BOOLEAN NOT NULL DEFAULT false, -- Inversió del Subjecte Passiu
    iban_xifrat_simetric TEXT, -- Xifratge simètric per protecció anti-frau BEC
    actiu BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_proveidors_empresa_codi UNIQUE (empresa_id, codi)
);

CREATE INDEX IF NOT EXISTS idx_proveidors_empresa ON proveidors(empresa_id);
CREATE INDEX IF NOT EXISTS idx_proveidors_nif ON proveidors(nif);

CREATE TRIGGER trigger_update_proveidors_updated_at
    BEFORE UPDATE ON proveidors
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Documents CAE i Pòlisses de Responsabilitat Civil (RD 171/2004)
CREATE TABLE IF NOT EXISTS documents_cae_rc (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    empresa_id UUID NOT NULL REFERENCES empreses(id) ON DELETE CASCADE,
    proveidor_id UUID NOT NULL REFERENCES proveidors(id) ON DELETE CASCADE,
    tipus_document VARCHAR(30) NOT NULL CHECK (tipus_document IN ('POLISSA_RC', 'CERTIFICAT_PRL', 'TC2')),
    data_caducitat DATE NOT NULL,
    fitxer_path VARCHAR(500) NOT NULL,
    estat VARCHAR(20) NOT NULL DEFAULT 'VALIDAT' CHECK (estat IN ('VALIDAT', 'CADUCAT', 'REBUTJAT')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_cae_empresa ON documents_cae_rc(empresa_id);
CREATE INDEX IF NOT EXISTS idx_cae_proveidor ON documents_cae_rc(proveidor_id);
CREATE INDEX IF NOT EXISTS idx_cae_caducitat ON documents_cae_rc(data_caducitat);

CREATE TRIGGER trigger_update_documents_cae_updated_at
    BEFORE UPDATE ON documents_cae_rc
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Comandes i Factures de Proveïdors per a Triple Conciliació (Three-Way Matching)
CREATE TABLE IF NOT EXISTS factures_proveidor (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    empresa_id UUID NOT NULL REFERENCES empreses(id) ON DELETE CASCADE,
    proveidor_id UUID NOT NULL REFERENCES proveidors(id) ON DELETE CASCADE,
    numero_factura VARCHAR(100) NOT NULL,
    data_factura DATE NOT NULL,
    base_imposable NUMERIC(12, 2) NOT NULL DEFAULT 0.00,
    quota_iva NUMERIC(12, 2) NOT NULL DEFAULT 0.00,
    total NUMERIC(12, 2) NOT NULL DEFAULT 0.00,
    albara_numero VARCHAR(100),
    comanda_numero VARCHAR(100),
    estat_conciliacio VARCHAR(30) NOT NULL DEFAULT 'PENDENT' CHECK (estat_conciliacio IN ('PENDENT', 'CONCILIADA', 'DESVIACIO_DETECTADA', 'REBUTJADA')),
    desviacio_percent NUMERIC(5, 2) NOT NULL DEFAULT 0.00,
    fitxer_pdf_path VARCHAR(500),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_factures_prov_empresa_num UNIQUE (empresa_id, proveidor_id, numero_factura)
);

CREATE INDEX IF NOT EXISTS idx_fact_prov_empresa ON factures_proveidor(empresa_id);

CREATE TRIGGER trigger_update_factures_proveidor_updated_at
    BEFORE UPDATE ON factures_proveidor
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- RLS Mandatori i Forçat
ALTER TABLE proveidors ENABLE ROW LEVEL SECURITY;
ALTER TABLE proveidors FORCE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS rls_proveidors_tenant_isolation ON proveidors;
CREATE POLICY rls_proveidors_tenant_isolation ON proveidors
FOR ALL
USING (
    empresa_id::text = current_setting('app.current_empresa_id', true)
    OR current_setting('app.is_superadmin', true) = 'true'
);

ALTER TABLE documents_cae_rc ENABLE ROW LEVEL SECURITY;
ALTER TABLE documents_cae_rc FORCE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS rls_cae_tenant_isolation ON documents_cae_rc;
CREATE POLICY rls_cae_tenant_isolation ON documents_cae_rc
FOR ALL
USING (
    empresa_id::text = current_setting('app.current_empresa_id', true)
    OR current_setting('app.is_superadmin', true) = 'true'
);

ALTER TABLE factures_proveidor ENABLE ROW LEVEL SECURITY;
ALTER TABLE factures_proveidor FORCE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS rls_fact_prov_tenant_isolation ON factures_proveidor;
CREATE POLICY rls_fact_prov_tenant_isolation ON factures_proveidor
FOR ALL
USING (
    empresa_id::text = current_setting('app.current_empresa_id', true)
    OR current_setting('app.is_superadmin', true) = 'true'
);
