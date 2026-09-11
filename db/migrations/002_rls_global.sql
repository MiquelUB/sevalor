-- 002_rls_global.sql
-- Activació de Row Level Security (RLS) Mandatatori i Polítiques d'Aïllament

-- 1. RLS sobre taula empreses
ALTER TABLE empreses ENABLE ROW LEVEL SECURITY;
ALTER TABLE empreses FORCE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS rls_empreses_tenant_isolation ON empreses;
CREATE POLICY rls_empreses_tenant_isolation ON empreses
FOR ALL
USING (
    id::text = current_setting('app.current_empresa_id', true)
    OR current_setting('app.is_superadmin', true) = 'true'
);

-- 2. RLS sobre taula slots_jornada
ALTER TABLE slots_jornada ENABLE ROW LEVEL SECURITY;
ALTER TABLE slots_jornada FORCE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS rls_slots_jornada_tenant_isolation ON slots_jornada;
CREATE POLICY rls_slots_jornada_tenant_isolation ON slots_jornada
FOR ALL
USING (
    empresa_id::text = current_setting('app.current_empresa_id', true)
    OR current_setting('app.is_superadmin', true) = 'true'
);

-- 3. RLS sobre taula usuaris
ALTER TABLE usuaris ENABLE ROW LEVEL SECURITY;
ALTER TABLE usuaris FORCE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS rls_usuaris_tenant_isolation ON usuaris;
CREATE POLICY rls_usuaris_tenant_isolation ON usuaris
FOR ALL
USING (
    empresa_id::text = current_setting('app.current_empresa_id', true)
    OR (empresa_id IS NULL AND current_setting('app.is_superadmin', true) = 'true')
);
