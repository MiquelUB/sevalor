-- Migració 012: Notificacions, Xat Multicanal, Bot Telegram i Alertes Centralitzades (Spec 009)

-- 1. Taula de Tokens d'Invitació Unívocs a Telegram (Deep Linking 48h)
CREATE TABLE IF NOT EXISTS tokens_invitacio_telegram (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    empresa_id UUID NOT NULL REFERENCES empreses(id) ON DELETE CASCADE,
    client_id UUID NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    token_hash VARCHAR(100) NOT NULL UNIQUE,
    expira_a TIMESTAMPTZ NOT NULL,
    utilitzat BOOLEAN NOT NULL DEFAULT false,
    utilitzat_a TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_tokens_invitacio_empresa ON tokens_invitacio_telegram(empresa_id);
CREATE INDEX IF NOT EXISTS idx_tokens_invitacio_client ON tokens_invitacio_telegram(client_id);
CREATE INDEX IF NOT EXISTS idx_tokens_invitacio_token ON tokens_invitacio_telegram(token_hash);

-- 2. Taula de Converses / Fils de Notificació
CREATE TABLE IF NOT EXISTS converses_notificacio (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    empresa_id UUID NOT NULL REFERENCES empreses(id) ON DELETE CASCADE,
    client_id UUID NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    ordre_treball_id UUID REFERENCES ordres_treball(id) ON DELETE SET NULL,
    estat VARCHAR(30) NOT NULL DEFAULT 'BLAU_OBERT' CHECK (estat IN ('VERMELL_PRIORITARI', 'BLAU_OBERT', 'VERD_SOLUCIONAT')),
    titol VARCHAR(150) NOT NULL,
    ultim_missatge_text TEXT,
    ultim_missatge_data TIMESTAMPTZ NOT NULL DEFAULT now(),
    num_missatges_sense_llegir INTEGER NOT NULL DEFAULT 0,
    es_arxivada BOOLEAN NOT NULL DEFAULT false,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_converses_empresa ON converses_notificacio(empresa_id);
CREATE INDEX IF NOT EXISTS idx_converses_client ON converses_notificacio(client_id);
CREATE INDEX IF NOT EXISTS idx_converses_estat ON converses_notificacio(estat);
CREATE INDEX IF NOT EXISTS idx_converses_ordre ON converses_notificacio(ordre_treball_id);

-- 3. Taula de Missatges de Notificació i Xat Multicanal
CREATE TABLE IF NOT EXISTS missatges_notificacio (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    empresa_id UUID NOT NULL REFERENCES empreses(id) ON DELETE CASCADE,
    conversa_id UUID NOT NULL REFERENCES converses_notificacio(id) ON DELETE CASCADE,
    remitent_tipus VARCHAR(30) NOT NULL CHECK (remitent_tipus IN ('OFICINA', 'CLIENT', 'BOT_IA', 'SISTEMA_CAMP')),
    remitent_usuari_id UUID REFERENCES usuaris(id) ON DELETE SET NULL,
    canal VARCHAR(20) NOT NULL DEFAULT 'TELEGRAM' CHECK (canal IN ('TELEGRAM', 'EMAIL', 'SMS', 'WEB_PWA')),
    contingut_text TEXT NOT NULL,
    tipus_esdeveniment VARCHAR(50) DEFAULT 'MISSATGE_TEXT',
    adjunt_url VARCHAR(500),
    adjunt_tipus VARCHAR(50),
    adjunt_mida_bytes BIGINT,
    token_aprobacio VARCHAR(100),
    estat_aprobacio VARCHAR(30) DEFAULT 'PENDENT' CHECK (estat_aprobacio IN ('PENDENT', 'ACCEPTAT', 'MODIFICACIONS_SOLICITADES')),
    token_descarrega_factura VARCHAR(100),
    token_descarrega_expira_a TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_missatges_empresa ON missatges_notificacio(empresa_id);
CREATE INDEX IF NOT EXISTS idx_missatges_conversa ON missatges_notificacio(conversa_id);
CREATE INDEX IF NOT EXISTS idx_missatges_token_aprobacio ON missatges_notificacio(token_aprobacio);
CREATE INDEX IF NOT EXISTS idx_missatges_token_factura ON missatges_notificacio(token_descarrega_factura);

-- 4. Taula de Base de Coneixement Local (RAG FAQs Hetzner)
CREATE TABLE IF NOT EXISTS faqs_corporatives_rag (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    empresa_id UUID NOT NULL REFERENCES empreses(id) ON DELETE CASCADE,
    pregunta VARCHAR(255) NOT NULL,
    resposta TEXT NOT NULL,
    categoria VARCHAR(50) DEFAULT 'GENERAL',
    paraules_clau VARCHAR(255),
    actiu BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_faqs_empresa ON faqs_corporatives_rag(empresa_id);

-- 5. Polítiques RLS Mandatòries i Forçades
ALTER TABLE tokens_invitacio_telegram ENABLE ROW LEVEL SECURITY;
ALTER TABLE tokens_invitacio_telegram FORCE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS rls_tokens_invitacio_tenant_isolation ON tokens_invitacio_telegram;
CREATE POLICY rls_tokens_invitacio_tenant_isolation ON tokens_invitacio_telegram
FOR ALL
USING (
    empresa_id::text = current_setting('app.current_empresa_id', true)
    OR current_setting('app.is_superadmin', true) = 'true'
);

ALTER TABLE converses_notificacio ENABLE ROW LEVEL SECURITY;
ALTER TABLE converses_notificacio FORCE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS rls_converses_tenant_isolation ON converses_notificacio;
CREATE POLICY rls_converses_tenant_isolation ON converses_notificacio
FOR ALL
USING (
    empresa_id::text = current_setting('app.current_empresa_id', true)
    OR current_setting('app.is_superadmin', true) = 'true'
);

ALTER TABLE missatges_notificacio ENABLE ROW LEVEL SECURITY;
ALTER TABLE missatges_notificacio FORCE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS rls_missatges_tenant_isolation ON missatges_notificacio;
CREATE POLICY rls_missatges_tenant_isolation ON missatges_notificacio
FOR ALL
USING (
    empresa_id::text = current_setting('app.current_empresa_id', true)
    OR current_setting('app.is_superadmin', true) = 'true'
);

ALTER TABLE faqs_corporatives_rag ENABLE ROW LEVEL SECURITY;
ALTER TABLE faqs_corporatives_rag FORCE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS rls_faqs_tenant_isolation ON faqs_corporatives_rag;
CREATE POLICY rls_faqs_tenant_isolation ON faqs_corporatives_rag
FOR ALL
USING (
    empresa_id::text = current_setting('app.current_empresa_id', true)
    OR current_setting('app.is_superadmin', true) = 'true'
);
