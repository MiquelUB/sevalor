-- 009_factures_outbox_aeat.sql
-- Motor de Facturació Veri*factu (RD 1007/2023), Línies d'Albarà i Outbox Asíncron SOAP (Spec 007 & Spec 024)

-- 1. Capçalera de Factures amb Hash SHA-256 Encadenat
CREATE TABLE IF NOT EXISTS factures_capcalera (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    empresa_id UUID NOT NULL REFERENCES empreses(id) ON DELETE CASCADE,
    numero_factura INT NOT NULL,
    serie VARCHAR(20) NOT NULL DEFAULT '2026',
    client_id UUID NOT NULL REFERENCES clients(id) ON DELETE RESTRICT,
    data_emissio TIMESTAMPTZ NOT NULL DEFAULT now(),
    base_imposable NUMERIC(12, 2) NOT NULL DEFAULT 0.00,
    quota_iva NUMERIC(12, 2) NOT NULL DEFAULT 0.00,
    import_retencio NUMERIC(12, 2) NOT NULL DEFAULT 0.00,
    import_suplits NUMERIC(12, 2) NOT NULL DEFAULT 0.00,
    liquid_exigible NUMERIC(12, 2) NOT NULL DEFAULT 0.00,
    estat_cobrament VARCHAR(20) NOT NULL DEFAULT 'PENDENT' CHECK (estat_cobrament IN ('PENDENT', 'COBRAT', 'PARCIAL')),
    estat_enviament VARCHAR(20) NOT NULL DEFAULT 'PENDENT' CHECK (estat_enviament IN ('PENDENT', 'ENVIAT', 'ERROR')),
    hash_anterior VARCHAR(64), -- Encadenament SHA-256 amb la factura anterior de la sèrie
    hash_sha256 VARCHAR(64) NOT NULL, -- Empremta inalterable de la factura
    qr_code_path VARCHAR(500),
    pdf_path VARCHAR(500),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_factures_empresa_serie_num UNIQUE (empresa_id, serie, numero_factura)
);

CREATE INDEX IF NOT EXISTS idx_factures_empresa ON factures_capcalera(empresa_id);
CREATE INDEX IF NOT EXISTS idx_factures_client ON factures_capcalera(client_id);
CREATE INDEX IF NOT EXISTS idx_factures_serie_num ON factures_capcalera(serie, numero_factura);

CREATE TRIGGER trigger_update_factures_updated_at
    BEFORE UPDATE ON factures_capcalera
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- 2. Línies de Factura
CREATE TABLE IF NOT EXISTS factures_linies (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    empresa_id UUID NOT NULL REFERENCES empreses(id) ON DELETE CASCADE,
    factura_id UUID NOT NULL REFERENCES factures_capcalera(id) ON DELETE CASCADE,
    centre_de_cost_id VARCHAR(50),
    obra_id UUID REFERENCES ordres_treball(id) ON DELETE SET NULL,
    article_id UUID REFERENCES articles(id) ON DELETE SET NULL,
    concepte VARCHAR(200) NOT NULL,
    quantitat NUMERIC(12, 3) NOT NULL DEFAULT 1.0,
    preu_venda_unitari NUMERIC(10, 2) NOT NULL DEFAULT 0.00,
    tipus_iva NUMERIC(4, 2) NOT NULL DEFAULT 21.00,
    subtotal NUMERIC(12, 2) NOT NULL DEFAULT 0.00,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_factures_linies_empresa ON factures_linies(empresa_id);
CREATE INDEX IF NOT EXISTS idx_factures_linies_factura ON factures_linies(factura_id);

-- 3. Outbox Pattern per a Enviaments SOAP a la AEAT (Spec 024)
CREATE TABLE IF NOT EXISTS outbox_enviaments_aeat (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    empresa_id UUID NOT NULL REFERENCES empreses(id) ON DELETE CASCADE,
    factura_id UUID NOT NULL REFERENCES factures_capcalera(id) ON DELETE CASCADE,
    payload_xml_path VARCHAR(500) NOT NULL,
    hash_sha256 VARCHAR(64) NOT NULL,
    intents_enviament INT NOT NULL DEFAULT 0,
    estat_enviament VARCHAR(20) NOT NULL DEFAULT 'PENDENT' CHECK (estat_enviament IN ('PENDENT', 'ENVIAT', 'REBUTJAT')),
    darrera_resposta_soap TEXT,
    data_creacio TIMESTAMPTZ NOT NULL DEFAULT now(),
    data_actualitzacio TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_outbox_empresa ON outbox_enviaments_aeat(empresa_id);
CREATE INDEX IF NOT EXISTS idx_outbox_estat ON outbox_enviaments_aeat(estat_enviament);

CREATE TRIGGER trigger_update_outbox_updated_at
    BEFORE UPDATE ON outbox_enviaments_aeat
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- RLS Mandatori i Forçat
ALTER TABLE factures_capcalera ENABLE ROW LEVEL SECURITY;
ALTER TABLE factures_capcalera FORCE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS rls_factures_tenant_isolation ON factures_capcalera;
CREATE POLICY rls_factures_tenant_isolation ON factures_capcalera
FOR ALL
USING (
    empresa_id::text = current_setting('app.current_empresa_id', true)
    OR current_setting('app.is_superadmin', true) = 'true'
);

ALTER TABLE factures_linies ENABLE ROW LEVEL SECURITY;
ALTER TABLE factures_linies FORCE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS rls_factures_linies_tenant_isolation ON factures_linies;
CREATE POLICY rls_factures_linies_tenant_isolation ON factures_linies
FOR ALL
USING (
    empresa_id::text = current_setting('app.current_empresa_id', true)
    OR current_setting('app.is_superadmin', true) = 'true'
);

ALTER TABLE outbox_enviaments_aeat ENABLE ROW LEVEL SECURITY;
ALTER TABLE outbox_enviaments_aeat FORCE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS rls_outbox_tenant_isolation ON outbox_enviaments_aeat;
CREATE POLICY rls_outbox_tenant_isolation ON outbox_enviaments_aeat
FOR ALL
USING (
    empresa_id::text = current_setting('app.current_empresa_id', true)
    OR current_setting('app.is_superadmin', true) = 'true'
);
