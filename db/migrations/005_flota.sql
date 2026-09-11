-- 005_flota.sql
-- Parc Mòbil, ITV en Quatre Veredictes i Tiquets de Carburant amb Doble Evidència (Spec 006, Spec 015, Spec 018)

-- 1. Taula de Vehicles
CREATE TABLE IF NOT EXISTS vehicles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    empresa_id UUID NOT NULL REFERENCES empreses(id) ON DELETE CASCADE,
    matricula VARCHAR(20) NOT NULL,
    marca VARCHAR(50) NOT NULL,
    model VARCHAR(50) NOT NULL,
    tipus VARCHAR(30) NOT NULL DEFAULT 'THERMIC' CHECK (tipus IN ('THERMIC', 'EV', 'PHEV', 'MAQUINARIA', 'REMOLC')),
    horometre_acumulat NUMERIC(10, 2) NOT NULL DEFAULT 0,
    odometre_acumulat INT NOT NULL DEFAULT 0,
    distintiu_ambiental VARCHAR(10) CHECK (distintiu_ambiental IN ('0', 'ECO', 'C', 'B', 'SENSE')),
    estat VARCHAR(30) NOT NULL DEFAULT 'OPERATIU' CHECK (estat IN ('OPERATIU', 'LEVE', 'DESFAVORABLE', 'INACTIVAT')),
    conductor_habitual_id UUID REFERENCES usuaris(id) ON DELETE SET NULL,
    magatzem_id UUID REFERENCES magatzems(id) ON DELETE SET NULL,
    data_proxima_itv DATE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_vehicles_empresa_matricula UNIQUE (empresa_id, matricula)
);

CREATE INDEX IF NOT EXISTS idx_vehicles_empresa ON vehicles(empresa_id);

CREATE TRIGGER trigger_update_vehicles_updated_at
    BEFORE UPDATE ON vehicles
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- 2. Taula d'Estades de Substitució de Flota
CREATE TABLE IF NOT EXISTS estancies_substitucio (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    empresa_id UUID NOT NULL REFERENCES empreses(id) ON DELETE CASCADE,
    vehicle_principal_id UUID NOT NULL REFERENCES vehicles(id) ON DELETE CASCADE,
    vehicle_substitucio_id UUID NOT NULL REFERENCES vehicles(id) ON DELETE CASCADE,
    data_inici TIMESTAMPTZ NOT NULL DEFAULT now(),
    data_fi TIMESTAMPTZ,
    motiu TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_substitucions_empresa ON estancies_substitucio(empresa_id);

-- 3. Taula de Tiquets de Carburant (Doble Foto Obligatòria: Tiquet + Odòmetre en viu)
CREATE TABLE IF NOT EXISTS tiquets_carburant (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    empresa_id UUID NOT NULL REFERENCES empreses(id) ON DELETE CASCADE,
    vehicle_id UUID NOT NULL REFERENCES vehicles(id) ON DELETE CASCADE,
    operari_id UUID NOT NULL REFERENCES usuaris(id) ON DELETE CASCADE,
    tiquet_foto_path VARCHAR(500) NOT NULL,
    odometre_foto_path VARCHAR(500) NOT NULL, -- Obligatòria per mandat de doble foto antifrau
    litres NUMERIC(8, 2) NOT NULL,
    import NUMERIC(10, 2) NOT NULL,
    data_repostatge TIMESTAMPTZ NOT NULL DEFAULT now(),
    odometre_valor INT NOT NULL,
    estat_ocr VARCHAR(30) NOT NULL DEFAULT 'PENDENT_AUDITORIA' CHECK (estat_ocr IN ('PENDENT_AUDITORIA', 'VALIDAT', 'PENDENT_DESGLOSE', 'REBUTJAT')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_tiquets_empresa ON tiquets_carburant(empresa_id);
CREATE INDEX IF NOT EXISTS idx_tiquets_vehicle ON tiquets_carburant(vehicle_id);

CREATE TRIGGER trigger_update_tiquets_updated_at
    BEFORE UPDATE ON tiquets_carburant
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- RLS Mandatori i Forçat
ALTER TABLE vehicles ENABLE ROW LEVEL SECURITY;
ALTER TABLE vehicles FORCE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS rls_vehicles_tenant_isolation ON vehicles;
CREATE POLICY rls_vehicles_tenant_isolation ON vehicles
FOR ALL
USING (
    empresa_id::text = current_setting('app.current_empresa_id', true)
    OR current_setting('app.is_superadmin', true) = 'true'
);

ALTER TABLE estancies_substitucio ENABLE ROW LEVEL SECURITY;
ALTER TABLE estancies_substitucio FORCE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS rls_estancies_tenant_isolation ON estancies_substitucio;
CREATE POLICY rls_estancies_tenant_isolation ON estancies_substitucio
FOR ALL
USING (
    empresa_id::text = current_setting('app.current_empresa_id', true)
    OR current_setting('app.is_superadmin', true) = 'true'
);

ALTER TABLE tiquets_carburant ENABLE ROW LEVEL SECURITY;
ALTER TABLE tiquets_carburant FORCE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS rls_tiquets_tenant_isolation ON tiquets_carburant;
CREATE POLICY rls_tiquets_tenant_isolation ON tiquets_carburant
FOR ALL
USING (
    empresa_id::text = current_setting('app.current_empresa_id', true)
    OR current_setting('app.is_superadmin', true) = 'true'
);
