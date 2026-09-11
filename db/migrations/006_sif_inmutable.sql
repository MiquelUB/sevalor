-- 006_sif_inmutable.sql
-- Registre d'Esdeveniments SIF Inmutable (Veri*factu — RD 1007/2023) (Spec 007 & Spec 024)

CREATE TABLE IF NOT EXISTS registre_esdeveniments_sif (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    empresa_id UUID NOT NULL REFERENCES empreses(id) ON DELETE RESTRICT,
    codi_esdeveniment VARCHAR(10) NOT NULL CHECK (codi_esdeveniment IN ('EV-01', 'EV-02', 'EV-03', 'EV-04', 'EV-05', 'EV-06', 'EV-07')),
    usuari_id UUID REFERENCES usuaris(id) ON DELETE SET NULL,
    descripcio TEXT NOT NULL,
    hash_anterior VARCHAR(64), -- Encadenament SHA-256 inalterable amb l'esdeveniment anterior
    hash_sello VARCHAR(64) NOT NULL, -- Segell hash SHA-256 de l'esdeveniment actual
    dades_event JSONB NOT NULL DEFAULT '{}'::jsonb,
    data_creacio TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_sif_empresa ON registre_esdeveniments_sif(empresa_id);
CREATE INDEX IF NOT EXISTS idx_sif_esdeveniment ON registre_esdeveniments_sif(codi_esdeveniment);
CREATE INDEX IF NOT EXISTS idx_sif_data ON registre_esdeveniments_sif(data_creacio);

-- Trigger de Bloqueig Atòmic contra qualsevol UPDATE o DELETE
CREATE OR REPLACE FUNCTION trg_sif_block_modifications()
RETURNS TRIGGER AS $$
BEGIN
    RAISE EXCEPTION 'VIOLACIÓ DE SEGURETAT SIF (RD 1007/2023): El registre d''esdeveniments SIF és strictly inmutable i no permet modificacions (UPDATE) ni eliminacions (DELETE) en entorn de producció (intent d''operació %).', TG_OP
    USING ERRCODE = '55000';
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trigger_sif_prevent_update ON registre_esdeveniments_sif;
CREATE TRIGGER trigger_sif_prevent_update
    BEFORE UPDATE ON registre_esdeveniments_sif
    FOR EACH ROW EXECUTE FUNCTION trg_sif_block_modifications();

DROP TRIGGER IF EXISTS trigger_sif_prevent_delete ON registre_esdeveniments_sif;
CREATE TRIGGER trigger_sif_prevent_delete
    BEFORE DELETE ON registre_esdeveniments_sif
    FOR EACH ROW EXECUTE FUNCTION trg_sif_block_modifications();

-- RLS Mandatori i Forçat
ALTER TABLE registre_esdeveniments_sif ENABLE ROW LEVEL SECURITY;
ALTER TABLE registre_esdeveniments_sif FORCE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS rls_sif_tenant_isolation ON registre_esdeveniments_sif;
CREATE POLICY rls_sif_tenant_isolation ON registre_esdeveniments_sif
FOR ALL
USING (
    empresa_id::text = current_setting('app.current_empresa_id', true)
    OR current_setting('app.is_superadmin', true) = 'true'
);
