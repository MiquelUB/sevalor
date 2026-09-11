-- 001_core_multitenant.sql
-- Nucli Multi-Tenant de Sevalor Suite: empreses, slots_jornada i usuaris
-- REESCRIPTURA DES DE ZERO (Compliment Estricte Spec 021)

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS postgis;

-- Creació del rol d'aplicació sense privilegis de superusuari per a compliment estricte de RLS
DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'sevalor_app') THEN
        CREATE ROLE sevalor_app WITH LOGIN PASSWORD 'sevalor_app_secret' NOSUPERUSER NOBYPASSRLS;
    END IF;
END $$;

GRANT USAGE ON SCHEMA public TO sevalor_app;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO sevalor_app;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO sevalor_app;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO sevalor_app;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO sevalor_app;

-- Funció genèrica per actualitzar automàticament el camp updated_at
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- 1. Taula Mestre d'Empreses (Tenants)
CREATE TABLE IF NOT EXISTS empreses (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    nom VARCHAR(100) NOT NULL,
    nif VARCHAR(20) NOT NULL UNIQUE,
    adreca TEXT,
    subdomini VARCHAR(63) UNIQUE,
    primari_hsl VARCHAR(30) NOT NULL DEFAULT '210 100% 15%',
    secundari_hsl VARCHAR(30) NOT NULL DEFAULT '38 92% 50%',
    accent_hsl VARCHAR(30) NOT NULL DEFAULT '190 90% 50%',
    logotip_path VARCHAR(500),
    favicon_path VARCHAR(500),
    vertical VARCHAR(50) NOT NULL DEFAULT 'CAMPOPRO' CHECK (vertical IN ('CAMPOPRO', 'ELECTRICPRO', 'HYDROPRO', 'BUILDINGPRO')),
    pla_subscripcio VARCHAR(20) NOT NULL DEFAULT 'STARTER' CHECK (pla_subscripcio IN ('STARTER', 'PRO', 'ENTERPRISE')),
    estat_pagament VARCHAR(30) NOT NULL DEFAULT 'TRIAL' CHECK (estat_pagament IN ('TRIAL', 'ACTIU', 'SUSPES_PAGAMENT', 'MANTENIMENT', 'BAIXA_OFFBOARDING')),
    quota_disc_bytes_autoritzada BIGINT NOT NULL DEFAULT 10737418240, -- 10 GB per defecte
    quota_disc_bytes_utilitzada BIGINT NOT NULL DEFAULT 0,
    node_ia_actiu BOOLEAN NOT NULL DEFAULT false,
    node_ia_url VARCHAR(255),
    feature_copilot_ia BOOLEAN NOT NULL DEFAULT false,
    feature_flota BOOLEAN NOT NULL DEFAULT true,
    feature_planols BOOLEAN NOT NULL DEFAULT false,
    feature_telegram BOOLEAN NOT NULL DEFAULT true,
    data_onboarding TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TRIGGER trigger_update_empreses_updated_at
    BEFORE UPDATE ON empreses
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- 2. Taula d'Horaris i Torns Laborals (Slots de Jornada)
CREATE TABLE IF NOT EXISTS slots_jornada (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    empresa_id UUID NOT NULL REFERENCES empreses(id) ON DELETE CASCADE,
    nom VARCHAR(100) NOT NULL,
    modalitat VARCHAR(30) NOT NULL DEFAULT 'JORNADA_CONTINUADA' CHECK (modalitat IN ('JORNADA_CONTINUADA', 'JORNADA_PARTIDA', 'TORN_ESPECIAL')),
    hora_entrada_teorica TIME NOT NULL DEFAULT '08:00:00',
    hora_sortida_teorica TIME NOT NULL DEFAULT '17:00:00',
    hora_inici_dinar TIME DEFAULT '13:00:00',
    hora_fi_dinar TIME DEFAULT '14:00:00',
    hores_convenio_setmanals NUMERIC(4, 2) NOT NULL DEFAULT 40.00,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_slots_empresa ON slots_jornada(empresa_id);

CREATE TRIGGER trigger_update_slots_jornada_updated_at
    BEFORE UPDATE ON slots_jornada
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- 3. Taula d'Usuaris
CREATE TABLE IF NOT EXISTS usuaris (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    empresa_id UUID REFERENCES empreses(id) ON DELETE CASCADE, -- NULL per a SUPERADMIN
    nif VARCHAR(20) NOT NULL,
    nom VARCHAR(100) NOT NULL,
    cognoms VARCHAR(100) NOT NULL DEFAULT '',
    email VARCHAR(200),
    telefon VARCHAR(20),
    password_hash VARCHAR(255),
    pin_hash VARCHAR(255),
    rol VARCHAR(30) NOT NULL DEFAULT 'OPERARI' CHECK (rol IN ('SUPERADMIN', 'BOSS', 'SECRETARIA', 'ENGINYER', 'COMPTABILITAT', 'CAP_DE_COLLA', 'OPERARI')),
    estat VARCHAR(20) NOT NULL DEFAULT 'ACTIU' CHECK (estat IN ('ACTIU', 'INACTIU')),
    secret_2fa VARCHAR(64),
    totp_activat BOOLEAN NOT NULL DEFAULT false,
    slot_jornada_id UUID REFERENCES slots_jornada(id) ON DELETE SET NULL,
    ip_allowlist TEXT[],
    vehicle_assignat_id UUID,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_usuaris_empresa_nif UNIQUE (empresa_id, nif)
);

CREATE INDEX IF NOT EXISTS idx_usuaris_email ON usuaris(email) WHERE email IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_usuaris_telefon ON usuaris(telefon) WHERE telefon IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_usuaris_empresa ON usuaris(empresa_id);
CREATE INDEX IF NOT EXISTS idx_usuaris_rol ON usuaris(rol);

CREATE TRIGGER trigger_update_usuaris_updated_at
    BEFORE UPDATE ON usuaris
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
