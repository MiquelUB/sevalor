-- Migració 011: Plànols, Xarxes Tècniques, Capes i Caixetí Industrial Oficial (Spec 010)

-- 1. Taula de Carpetes de Plànols
CREATE TABLE IF NOT EXISTS carpetes_planols (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    empresa_id UUID NOT NULL REFERENCES empreses(id) ON DELETE CASCADE,
    nom VARCHAR(100) NOT NULL,
    categoria VARCHAR(30) NOT NULL CHECK (categoria IN ('CLIENTS', 'INFRAESTRUCTURA_COMUNITARIA', 'MUNICIPAL_TERRITORIAL')),
    client_id UUID REFERENCES clients(id) ON DELETE SET NULL,
    municipi VARCHAR(100),
    descripcio TEXT,
    parent_id UUID REFERENCES carpetes_planols(id) ON DELETE CASCADE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_carpetes_empresa ON carpetes_planols(empresa_id);
CREATE INDEX IF NOT EXISTS idx_carpetes_categoria ON carpetes_planols(categoria);
CREATE INDEX IF NOT EXISTS idx_carpetes_client ON carpetes_planols(client_id);

-- 2. Taula de Plànols Base
CREATE TABLE IF NOT EXISTS planols_base (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    empresa_id UUID NOT NULL REFERENCES empreses(id) ON DELETE CASCADE,
    carpeta_id UUID REFERENCES carpetes_planols(id) ON DELETE CASCADE,
    client_id UUID REFERENCES clients(id) ON DELETE SET NULL,
    titol VARCHAR(150) NOT NULL,
    codi_referencia VARCHAR(50) NOT NULL,
    tipus_fitxer VARCHAR(20) NOT NULL CHECK (tipus_fitxer IN ('DXF', 'GEOJSON', 'KML', 'PDF', 'TIFF', 'PNG', 'JPG')),
    es_georeferenciat BOOLEAN NOT NULL DEFAULT false,
    fitxer_path VARCHAR(500) NOT NULL,
    mida_bytes BIGINT NOT NULL,
    bounds_wgs84 JSONB,
    projeccio_origen VARCHAR(30) DEFAULT 'WGS84',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_planols_codi UNIQUE (empresa_id, codi_referencia)
);

CREATE INDEX IF NOT EXISTS idx_planols_empresa ON planols_base(empresa_id);
CREATE INDEX IF NOT EXISTS idx_planols_carpeta ON planols_base(carpeta_id);
CREATE INDEX IF NOT EXISTS idx_planols_client ON planols_base(client_id);

-- 3. Taula de Capes Vectorials Superposades
CREATE TABLE IF NOT EXISTS capes_vectorials (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    empresa_id UUID NOT NULL REFERENCES empreses(id) ON DELETE CASCADE,
    planol_base_id UUID NOT NULL REFERENCES planols_base(id) ON DELETE CASCADE,
    nom VARCHAR(100) NOT NULL,
    disciplina VARCHAR(30) NOT NULL CHECK (disciplina IN ('AIGUA_REG', 'ELECTRICITAT', 'OBRA_CIVIL', 'INCIDENCIA_PERICIAL')),
    ordre_treball_id UUID REFERENCES ordres_treball(id) ON DELETE SET NULL,
    es_immutable BOOLEAN NOT NULL DEFAULT false,
    color_hex VARCHAR(10) DEFAULT '#2563eb',
    gruix_linia INTEGER DEFAULT 2,
    opacitat_percent INTEGER DEFAULT 100,
    visible BOOLEAN DEFAULT true,
    geometries_geojson JSONB NOT NULL DEFAULT '{"type": "FeatureCollection", "features": []}'::jsonb,
    version_id INTEGER NOT NULL DEFAULT 1,
    creat_per_usuari_id UUID REFERENCES usuaris(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_capes_vectorials_empresa ON capes_vectorials(empresa_id);
CREATE INDEX IF NOT EXISTS idx_capes_vectorials_planol ON capes_vectorials(planol_base_id);
CREATE INDEX IF NOT EXISTS idx_capes_vectorials_ordre ON capes_vectorials(ordre_treball_id);

-- 4. Pins d'Incidència Georeferenciats (Geofotos & Àudio WebM)
CREATE TABLE IF NOT EXISTS pins_incidencia_planol (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    empresa_id UUID NOT NULL REFERENCES empreses(id) ON DELETE CASCADE,
    capa_id UUID NOT NULL REFERENCES capes_vectorials(id) ON DELETE CASCADE,
    latitud NUMERIC(10, 7) NOT NULL,
    longitud NUMERIC(10, 7) NOT NULL,
    titol VARCHAR(150) NOT NULL,
    descripcio TEXT,
    simbol VARCHAR(50) DEFAULT 'AVARIA_REG',
    estat VARCHAR(20) DEFAULT 'PENDENT_REVISIO' CHECK (estat IN ('PENDENT_REVISIO', 'EN_REPARACIO', 'RESOLT')),
    audio_nota_path VARCHAR(500),
    foto_evidencia_path VARCHAR(500),
    operari_id UUID REFERENCES usuaris(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_pins_empresa ON pins_incidencia_planol(empresa_id);
CREATE INDEX IF NOT EXISTS idx_pins_capa ON pins_incidencia_planol(capa_id);

-- 5. Taula d'Exportacions Oficials PDF amb Caixetí
CREATE TABLE IF NOT EXISTS exportacions_pdf_planol (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    empresa_id UUID NOT NULL REFERENCES empreses(id) ON DELETE CASCADE,
    planol_base_id UUID NOT NULL REFERENCES planols_base(id) ON DELETE CASCADE,
    titol_report VARCHAR(200) NOT NULL,
    client_id UUID REFERENCES clients(id) ON DELETE SET NULL,
    capes_incloses_ids UUID[] NOT NULL,
    escala_grafica VARCHAR(30) DEFAULT '1:500',
    pdf_generat_path VARCHAR(500),
    estat VARCHAR(20) DEFAULT 'GENERAT' CHECK (estat IN ('PENDENT', 'GENERAT', 'FALLIDA')),
    caixeti_dades JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_exportacions_empresa ON exportacions_pdf_planol(empresa_id);

-- 6. Polítiques RLS Mandatòries i Forçades
ALTER TABLE carpetes_planols ENABLE ROW LEVEL SECURITY;
ALTER TABLE carpetes_planols FORCE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS rls_carpetes_tenant_isolation ON carpetes_planols;
CREATE POLICY rls_carpetes_tenant_isolation ON carpetes_planols
FOR ALL
USING (
    empresa_id::text = current_setting('app.current_empresa_id', true)
    OR current_setting('app.is_superadmin', true) = 'true'
);

ALTER TABLE planols_base ENABLE ROW LEVEL SECURITY;
ALTER TABLE planols_base FORCE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS rls_planols_base_tenant_isolation ON planols_base;
CREATE POLICY rls_planols_base_tenant_isolation ON planols_base
FOR ALL
USING (
    empresa_id::text = current_setting('app.current_empresa_id', true)
    OR current_setting('app.is_superadmin', true) = 'true'
);

ALTER TABLE capes_vectorials ENABLE ROW LEVEL SECURITY;
ALTER TABLE capes_vectorials FORCE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS rls_capes_vectorials_tenant_isolation ON capes_vectorials;
CREATE POLICY rls_capes_vectorials_tenant_isolation ON capes_vectorials
FOR ALL
USING (
    empresa_id::text = current_setting('app.current_empresa_id', true)
    OR current_setting('app.is_superadmin', true) = 'true'
);

ALTER TABLE pins_incidencia_planol ENABLE ROW LEVEL SECURITY;
ALTER TABLE pins_incidencia_planol FORCE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS rls_pins_tenant_isolation ON pins_incidencia_planol;
CREATE POLICY rls_pins_tenant_isolation ON pins_incidencia_planol
FOR ALL
USING (
    empresa_id::text = current_setting('app.current_empresa_id', true)
    OR current_setting('app.is_superadmin', true) = 'true'
);

ALTER TABLE exportacions_pdf_planol ENABLE ROW LEVEL SECURITY;
ALTER TABLE exportacions_pdf_planol FORCE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS rls_exportacions_tenant_isolation ON exportacions_pdf_planol;
CREATE POLICY rls_exportacions_tenant_isolation ON exportacions_pdf_planol
FOR ALL
USING (
    empresa_id::text = current_setting('app.current_empresa_id', true)
    OR current_setting('app.is_superadmin', true) = 'true'
);
