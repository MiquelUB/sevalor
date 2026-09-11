-- 003_clients_finques.sql
-- Directori Mestre de Clients i Finques Rústiques amb PostGIS (Spec 002)

-- 1. Taula de Clients
CREATE TABLE IF NOT EXISTS clients (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    empresa_id UUID NOT NULL REFERENCES empreses(id) ON DELETE CASCADE,
    codi VARCHAR(20) NOT NULL, -- CLI-XXXX
    rao_social VARCHAR(200) NOT NULL,
    nif VARCHAR(20) NOT NULL,
    telefon VARCHAR(30),
    email VARCHAR(200),
    adreca_fiscal TEXT,
    estat_canal_telegram VARCHAR(20) NOT NULL DEFAULT 'DESVINCULAT' CHECK (estat_canal_telegram IN ('VINCULAT', 'DESVINCULAT')),
    telegram_chat_id BIGINT,
    iban_xifrat_simetric TEXT, -- AES-256-GCM
    mandat_sepa_path VARCHAR(500),
    actiu BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_clients_empresa_codi UNIQUE (empresa_id, codi)
);

CREATE INDEX IF NOT EXISTS idx_clients_empresa ON clients(empresa_id);
CREATE INDEX IF NOT EXISTS idx_clients_nif ON clients(nif);

CREATE TRIGGER trigger_update_clients_updated_at
    BEFORE UPDATE ON clients
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- 2. Taula de Finques (amb suport geoespacial PostGIS Point WGS84)
CREATE TABLE IF NOT EXISTS finques (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    empresa_id UUID NOT NULL REFERENCES empreses(id) ON DELETE CASCADE,
    client_id UUID NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    nom VARCHAR(150) NOT NULL,
    adreca TEXT,
    coords_gps GEOMETRY(Point, 4326) NOT NULL, -- Format estrictament geomètric WGS84
    codi_candat_en_memoria VARCHAR(50), -- Protegit i deslligat de galeries públiques
    dades_sigpac JSONB DEFAULT '{}'::jsonb,
    superficie_ha NUMERIC(10, 4),
    actiu BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_finques_empresa ON finques(empresa_id);
CREATE INDEX IF NOT EXISTS idx_finques_client ON finques(client_id);
CREATE INDEX IF NOT EXISTS idx_finques_coords_gps ON finques USING GIST (coords_gps);

CREATE TRIGGER trigger_update_finques_updated_at
    BEFORE UPDATE ON finques
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- RLS Mandatori i Forçat
ALTER TABLE clients ENABLE ROW LEVEL SECURITY;
ALTER TABLE clients FORCE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS rls_clients_tenant_isolation ON clients;
CREATE POLICY rls_clients_tenant_isolation ON clients
FOR ALL
USING (
    empresa_id::text = current_setting('app.current_empresa_id', true)
    OR current_setting('app.is_superadmin', true) = 'true'
);

ALTER TABLE finques ENABLE ROW LEVEL SECURITY;
ALTER TABLE finques FORCE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS rls_finques_tenant_isolation ON finques;
CREATE POLICY rls_finques_tenant_isolation ON finques
FOR ALL
USING (
    empresa_id::text = current_setting('app.current_empresa_id', true)
    OR current_setting('app.is_superadmin', true) = 'true'
);
