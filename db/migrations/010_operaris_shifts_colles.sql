-- Migració 010: Gestió d'Operaris, Fitxa 360°, Control Horari RDL 8/2019 i Colles (Spec 008)

-- 1. Ampliació de la taula usuaris per a suport 360° d'operaris
ALTER TABLE usuaris
    ADD COLUMN IF NOT EXISTS especialitat VARCHAR(50) DEFAULT 'SISTEMES_REG',
    ADD COLUMN IF NOT EXISTS estat_operatiu VARCHAR(30) DEFAULT 'DISPONIBLE',
    ADD COLUMN IF NOT EXISTS cap_de_grup_id UUID REFERENCES usuaris(id) ON DELETE SET NULL,
    ADD COLUMN IF NOT EXISTS cost_hora_eur NUMERIC(8, 2) DEFAULT 22.50,
    ADD COLUMN IF NOT EXISTS carnet_conduir VARCHAR(20) DEFAULT 'B',
    ADD COLUMN IF NOT EXISTS carnet_caducitat DATE,
    ADD COLUMN IF NOT EXISTS prl_certificat_vigencia DATE,
    ADD COLUMN IF NOT EXISTS intents_pin_fallits INTEGER DEFAULT 0,
    ADD COLUMN IF NOT EXISTS pin_bloquejat BOOLEAN DEFAULT false;

-- Índexs de recerca ràpida (<200ms)
CREATE INDEX IF NOT EXISTS idx_usuaris_especialitat ON usuaris(especialitat);
CREATE INDEX IF NOT EXISTS idx_usuaris_estat_operatiu ON usuaris(estat_operatiu);
CREATE INDEX IF NOT EXISTS idx_usuaris_cap_de_grup ON usuaris(cap_de_grup_id);

-- 2. Registres de Jornada Laboral (RDL 8/2019)
CREATE TABLE IF NOT EXISTS registres_jornada_laboral (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    empresa_id UUID NOT NULL REFERENCES empreses(id) ON DELETE CASCADE,
    usuari_id UUID NOT NULL REFERENCES usuaris(id) ON DELETE CASCADE,
    data_jornada DATE NOT NULL DEFAULT CURRENT_DATE,
    hora_inici TIMESTAMPTZ NOT NULL DEFAULT now(),
    hora_fi TIMESTAMPTZ,
    geolocalitzacio_inici VARCHAR(100),
    geolocalitzacio_fi VARCHAR(100),
    estat VARCHAR(20) NOT NULL DEFAULT 'EN_CURS' CHECK (estat IN ('EN_CURS', 'COMPLERT', 'INCIDENCIA')),
    tancament_automatic BOOLEAN NOT NULL DEFAULT false,
    motiu_incidencia TEXT,
    hores_ordinaries NUMERIC(5,2) DEFAULT 0.00,
    hores_extraordinaries NUMERIC(5,2) DEFAULT 0.00,
    auditat_per_usuari_id UUID REFERENCES usuaris(id) ON DELETE SET NULL,
    auditoria_data TIMESTAMPTZ,
    auditoria_motiu TEXT,
    version_id INTEGER NOT NULL DEFAULT 1,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_jornada_empresa ON registres_jornada_laboral(empresa_id);
CREATE INDEX IF NOT EXISTS idx_jornada_usuari ON registres_jornada_laboral(usuari_id);
CREATE INDEX IF NOT EXISTS idx_jornada_data ON registres_jornada_laboral(data_jornada);
CREATE INDEX IF NOT EXISTS idx_jornada_estat ON registres_jornada_laboral(estat);

-- 3. Traça Immutable d'Auditoria de Rectificacions Horàries (Inspecció de Treball)
CREATE TABLE IF NOT EXISTS auditoria_registres_jornada (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    empresa_id UUID NOT NULL REFERENCES empreses(id) ON DELETE CASCADE,
    shift_id UUID NOT NULL REFERENCES registres_jornada_laboral(id) ON DELETE CASCADE,
    modificat_per_id UUID NOT NULL REFERENCES usuaris(id) ON DELETE CASCADE,
    valors_anteriors JSONB NOT NULL,
    nous_valors JSONB NOT NULL,
    motiu_justificatiu TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_audit_jornada_empresa ON auditoria_registres_jornada(empresa_id);
CREATE INDEX IF NOT EXISTS idx_audit_jornada_shift ON auditoria_registres_jornada(shift_id);

-- 4. RLS Mandatori i Forçat
ALTER TABLE registres_jornada_laboral ENABLE ROW LEVEL SECURITY;
ALTER TABLE registres_jornada_laboral FORCE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS rls_jornada_tenant_isolation ON registres_jornada_laboral;
CREATE POLICY rls_jornada_tenant_isolation ON registres_jornada_laboral
FOR ALL
USING (
    empresa_id::text = current_setting('app.current_empresa_id', true)
    OR current_setting('app.is_superadmin', true) = 'true'
);

ALTER TABLE auditoria_registres_jornada ENABLE ROW LEVEL SECURITY;
ALTER TABLE auditoria_registres_jornada FORCE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS rls_audit_jornada_tenant_isolation ON auditoria_registres_jornada;
CREATE POLICY rls_audit_jornada_tenant_isolation ON auditoria_registres_jornada
FOR ALL
USING (
    empresa_id::text = current_setting('app.current_empresa_id', true)
    OR current_setting('app.is_superadmin', true) = 'true'
);
