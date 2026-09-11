-- 008_feines_picking_incidencies.sql
-- Ordres de Treball (OT), Picking Matinal/Tarda, Incidències Multimodal/SOS i Capes As-Built (Specs 001, 005, 013, 014, 016, 017)

-- 1. Taula d'Ordres de Treball
CREATE TABLE IF NOT EXISTS ordres_treball (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    empresa_id UUID NOT NULL REFERENCES empreses(id) ON DELETE CASCADE,
    codi VARCHAR(20) NOT NULL, -- OT-XXXX
    client_id UUID NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    finca_id UUID REFERENCES finques(id) ON DELETE SET NULL,
    titol VARCHAR(200) NOT NULL,
    descripcio TEXT,
    estat VARCHAR(30) NOT NULL DEFAULT 'PENDENT' CHECK (estat IN ('PENDENT', 'EN_CAMI', 'EN_OBRA', 'PAUSA', 'COMPLETADA', 'CANCEL_LADA')),
    data_planificacio DATE NOT NULL DEFAULT CURRENT_DATE,
    cap_de_colla_id UUID REFERENCES usuaris(id) ON DELETE SET NULL,
    vehicle_id UUID REFERENCES vehicles(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_ordres_empresa_codi UNIQUE (empresa_id, codi)
);

CREATE INDEX IF NOT EXISTS idx_ordres_empresa ON ordres_treball(empresa_id);
CREATE INDEX IF NOT EXISTS idx_ordres_client ON ordres_treball(client_id);
CREATE INDEX IF NOT EXISTS idx_ordres_estat ON ordres_treball(estat);
CREATE INDEX IF NOT EXISTS idx_ordres_data ON ordres_treball(data_planificacio);

CREATE TRIGGER trigger_update_ordres_updated_at
    BEFORE UPDATE ON ordres_treball
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- 2. Taula de Fulles de Picking
CREATE TABLE IF NOT EXISTS fulles_picking (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    empresa_id UUID NOT NULL REFERENCES empreses(id) ON DELETE CASCADE,
    ordre_treball_id UUID NOT NULL REFERENCES ordres_treball(id) ON DELETE CASCADE,
    vehicle_id UUID REFERENCES vehicles(id) ON DELETE SET NULL,
    estat_picking VARCHAR(30) NOT NULL DEFAULT 'PENDENT' CHECK (estat_picking IN ('PENDENT', 'CARREGAT_PICK_IN', 'DEVOLUT_PICK_OUT')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_picking_empresa ON fulles_picking(empresa_id);
CREATE INDEX IF NOT EXISTS idx_picking_ordre ON fulles_picking(ordre_treball_id);

CREATE TRIGGER trigger_update_picking_updated_at
    BEFORE UPDATE ON fulles_picking
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- 3. Línies de Material de Picking
CREATE TABLE IF NOT EXISTS linies_picking (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    empresa_id UUID NOT NULL REFERENCES empreses(id) ON DELETE CASCADE,
    picking_id UUID NOT NULL REFERENCES fulles_picking(id) ON DELETE CASCADE,
    article_id UUID NOT NULL REFERENCES articles(id) ON DELETE CASCADE,
    quantitat_prevista NUMERIC(12, 3) NOT NULL DEFAULT 0,
    quantitat_carregada_pick_in NUMERIC(12, 3) NOT NULL DEFAULT 0,
    quantitat_retornada_pick_out NUMERIC(12, 3) NOT NULL DEFAULT 0,
    quantitat_mermada NUMERIC(12, 3) NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_linies_picking_empresa ON linies_picking(empresa_id);
CREATE INDEX IF NOT EXISTS idx_linies_picking_parent ON linies_picking(picking_id);

CREATE TRIGGER trigger_update_linies_picking_updated_at
    BEFORE UPDATE ON linies_picking
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- 4. Bústia d'Incidències Multimodal i SOS (Spec 016)
CREATE TABLE IF NOT EXISTS incidencies (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    empresa_id UUID NOT NULL REFERENCES empreses(id) ON DELETE CASCADE,
    ordre_treball_id UUID REFERENCES ordres_treball(id) ON DELETE SET NULL,
    vehicle_id UUID REFERENCES vehicles(id) ON DELETE SET NULL,
    operari_id UUID REFERENCES usuaris(id) ON DELETE SET NULL,
    ambit VARCHAR(30) NOT NULL DEFAULT 'TASCA' CHECK (ambit IN ('TASCA', 'VEHICLE', 'GENERAL', 'SOS')),
    estat VARCHAR(20) NOT NULL DEFAULT 'VERMELL' CHECK (estat IN ('VERMELL', 'VERD')),
    audio_path VARCHAR(500),
    foto_path VARCHAR(500),
    text_observacions TEXT,
    coords_gps GEOMETRY(Point, 4326),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_incidencies_empresa ON incidencies(empresa_id);
CREATE INDEX IF NOT EXISTS idx_incidencies_ordre ON incidencies(ordre_treball_id);
CREATE INDEX IF NOT EXISTS idx_incidencies_estat ON incidencies(estat);
CREATE INDEX IF NOT EXISTS idx_incidencies_coords ON incidencies USING GIST (coords_gps);

CREATE TRIGGER trigger_update_incidencies_updated_at
    BEFORE UPDATE ON incidencies
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- 5. Capes d'Anotacions As-Built (Spec 010 & Spec 017)
CREATE TABLE IF NOT EXISTS capes_anotacions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    empresa_id UUID NOT NULL REFERENCES empreses(id) ON DELETE CASCADE,
    ordre_treball_id UUID NOT NULL REFERENCES ordres_treball(id) ON DELETE CASCADE,
    nom_capa VARCHAR(100) NOT NULL,
    fitxer_vectorial_path VARCHAR(500) NOT NULL,
    operari_id UUID REFERENCES usuaris(id) ON DELETE SET NULL,
    estat_capa VARCHAR(30) NOT NULL DEFAULT 'ACTIVA' CHECK (estat_capa IN ('ACTIVA', 'HISTORICA', 'NOMES_LECTURA')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_capes_empresa ON capes_anotacions(empresa_id);
CREATE INDEX IF NOT EXISTS idx_capes_ordre ON capes_anotacions(ordre_treball_id);

CREATE TRIGGER trigger_update_capes_updated_at
    BEFORE UPDATE ON capes_anotacions
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- RLS Mandatori i Forçat
ALTER TABLE ordres_treball ENABLE ROW LEVEL SECURITY;
ALTER TABLE ordres_treball FORCE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS rls_ordres_tenant_isolation ON ordres_treball;
CREATE POLICY rls_ordres_tenant_isolation ON ordres_treball
FOR ALL
USING (
    empresa_id::text = current_setting('app.current_empresa_id', true)
    OR current_setting('app.is_superadmin', true) = 'true'
);

ALTER TABLE fulles_picking ENABLE ROW LEVEL SECURITY;
ALTER TABLE fulles_picking FORCE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS rls_picking_tenant_isolation ON fulles_picking;
CREATE POLICY rls_picking_tenant_isolation ON fulles_picking
FOR ALL
USING (
    empresa_id::text = current_setting('app.current_empresa_id', true)
    OR current_setting('app.is_superadmin', true) = 'true'
);

ALTER TABLE linies_picking ENABLE ROW LEVEL SECURITY;
ALTER TABLE linies_picking FORCE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS rls_linies_picking_tenant_isolation ON linies_picking;
CREATE POLICY rls_linies_picking_tenant_isolation ON linies_picking
FOR ALL
USING (
    empresa_id::text = current_setting('app.current_empresa_id', true)
    OR current_setting('app.is_superadmin', true) = 'true'
);

ALTER TABLE incidencies ENABLE ROW LEVEL SECURITY;
ALTER TABLE incidencies FORCE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS rls_incidencies_tenant_isolation ON incidencies;
CREATE POLICY rls_incidencies_tenant_isolation ON incidencies
FOR ALL
USING (
    empresa_id::text = current_setting('app.current_empresa_id', true)
    OR current_setting('app.is_superadmin', true) = 'true'
);

ALTER TABLE capes_anotacions ENABLE ROW LEVEL SECURITY;
ALTER TABLE capes_anotacions FORCE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS rls_capes_tenant_isolation ON capes_anotacions;
CREATE POLICY rls_capes_tenant_isolation ON capes_anotacions
FOR ALL
USING (
    empresa_id::text = current_setting('app.current_empresa_id', true)
    OR current_setting('app.is_superadmin', true) = 'true'
);
