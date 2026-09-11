-- 004_magatzem.sql
-- Magatzem Central, Inventari de Format Continu i Eines de Custòdia (Spec 004 & Spec 014)

-- 1. Taula d'Articles i Materials
CREATE TABLE IF NOT EXISTS articles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    empresa_id UUID NOT NULL REFERENCES empreses(id) ON DELETE CASCADE,
    referencia_inventari VARCHAR(50) NOT NULL,
    nom VARCHAR(150) NOT NULL,
    unitat_mesura VARCHAR(30) NOT NULL DEFAULT 'UNITAT' CHECK (unitat_mesura IN ('METRES_LINEALS', 'UNITAT', 'KG', 'LITRES', 'M2', 'M3')),
    familia VARCHAR(50) NOT NULL DEFAULT 'GENERAL',
    estoc_optim NUMERIC(12, 3) NOT NULL DEFAULT 0,
    estoc_minim NUMERIC(12, 3) NOT NULL DEFAULT 0,
    es_lot_caducable BOOLEAN NOT NULL DEFAULT false,
    parent_material_id UUID REFERENCES articles(id) ON DELETE SET NULL, -- Traçabilitat de retalls de tubs i cables
    preu_cost NUMERIC(10, 2) NOT NULL DEFAULT 0.00,
    preu_venda NUMERIC(10, 2) NOT NULL DEFAULT 0.00,
    actiu BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_articles_empresa_ref UNIQUE (empresa_id, referencia_inventari)
);

CREATE INDEX IF NOT EXISTS idx_articles_empresa ON articles(empresa_id);
CREATE INDEX IF NOT EXISTS idx_articles_parent ON articles(parent_material_id);

CREATE TRIGGER trigger_update_articles_updated_at
    BEFORE UPDATE ON articles
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- 2. Taula de Magatzems (Nius Centrals, Furgonetes Taller o Dipòsits en Obra)
CREATE TABLE IF NOT EXISTS magatzems (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    empresa_id UUID NOT NULL REFERENCES empreses(id) ON DELETE CASCADE,
    nom VARCHAR(100) NOT NULL,
    tipus VARCHAR(30) NOT NULL DEFAULT 'NAU_CENTRAL' CHECK (tipus IN ('NAU_CENTRAL', 'FURGONETA_TALLER', 'OBRA_TEMPORAL')),
    vehicle_id UUID, -- Vinculació a vehicle si és furgoneta taller
    adreca TEXT,
    actiu BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_magatzems_empresa ON magatzems(empresa_id);

CREATE TRIGGER trigger_update_magatzems_updated_at
    BEFORE UPDATE ON magatzems
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- 3. Taula d'Estocs per Magatzem
CREATE TABLE IF NOT EXISTS estocs_magatzem (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    empresa_id UUID NOT NULL REFERENCES empreses(id) ON DELETE CASCADE,
    article_id UUID NOT NULL REFERENCES articles(id) ON DELETE CASCADE,
    magatzem_id UUID NOT NULL REFERENCES magatzems(id) ON DELETE CASCADE,
    quantitat_fisica NUMERIC(12, 3) NOT NULL DEFAULT 0,
    quantitat_virtual_reservada NUMERIC(12, 3) NOT NULL DEFAULT 0,
    ubicacio_passadis VARCHAR(50),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_estocs_article_magatzem UNIQUE (empresa_id, article_id, magatzem_id)
);

CREATE INDEX IF NOT EXISTS idx_estocs_empresa ON estocs_magatzem(empresa_id);
CREATE INDEX IF NOT EXISTS idx_estocs_article ON estocs_magatzem(article_id);
CREATE INDEX IF NOT EXISTS idx_estocs_magatzem ON estocs_magatzem(magatzem_id);

CREATE TRIGGER trigger_update_estocs_updated_at
    BEFORE UPDATE ON estocs_magatzem
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- 4. Taula d'Eines de Custòdia Nominal
CREATE TABLE IF NOT EXISTS eines_custodia (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    empresa_id UUID NOT NULL REFERENCES empreses(id) ON DELETE CASCADE,
    referencia_fabricant VARCHAR(100),
    nom VARCHAR(150) NOT NULL,
    model VARCHAR(100),
    numero_serie VARCHAR(100) NOT NULL,
    estat VARCHAR(30) NOT NULL DEFAULT 'DISPONIBLE' CHECK (estat IN ('DISPONIBLE', 'EN_TALLER', 'PERDUDA', 'ROBADA', 'DE_BAIXA')),
    custodiat_per_operari_id UUID REFERENCES usuaris(id) ON DELETE SET NULL,
    magatzem_id UUID REFERENCES magatzems(id) ON DELETE SET NULL,
    data_ultima_calibracio DATE,
    data_propera_calibracio DATE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_eines_empresa ON eines_custodia(empresa_id);
CREATE INDEX IF NOT EXISTS idx_eines_operari ON eines_custodia(custodiat_per_operari_id);

CREATE TRIGGER trigger_update_eines_updated_at
    BEFORE UPDATE ON eines_custodia
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- RLS Mandatori i Forçat
ALTER TABLE articles ENABLE ROW LEVEL SECURITY;
ALTER TABLE articles FORCE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS rls_articles_tenant_isolation ON articles;
CREATE POLICY rls_articles_tenant_isolation ON articles
FOR ALL
USING (
    empresa_id::text = current_setting('app.current_empresa_id', true)
    OR current_setting('app.is_superadmin', true) = 'true'
);

ALTER TABLE magatzems ENABLE ROW LEVEL SECURITY;
ALTER TABLE magatzems FORCE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS rls_magatzems_tenant_isolation ON magatzems;
CREATE POLICY rls_magatzems_tenant_isolation ON magatzems
FOR ALL
USING (
    empresa_id::text = current_setting('app.current_empresa_id', true)
    OR current_setting('app.is_superadmin', true) = 'true'
);

ALTER TABLE estocs_magatzem ENABLE ROW LEVEL SECURITY;
ALTER TABLE estocs_magatzem FORCE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS rls_estocs_tenant_isolation ON estocs_magatzem;
CREATE POLICY rls_estocs_tenant_isolation ON estocs_magatzem
FOR ALL
USING (
    empresa_id::text = current_setting('app.current_empresa_id', true)
    OR current_setting('app.is_superadmin', true) = 'true'
);

ALTER TABLE eines_custodia ENABLE ROW LEVEL SECURITY;
ALTER TABLE eines_custodia FORCE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS rls_eines_tenant_isolation ON eines_custodia;
CREATE POLICY rls_eines_tenant_isolation ON eines_custodia
FOR ALL
USING (
    empresa_id::text = current_setting('app.current_empresa_id', true)
    OR current_setting('app.is_superadmin', true) = 'true'
);
