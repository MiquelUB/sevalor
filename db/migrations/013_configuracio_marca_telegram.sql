-- 013_configuracio_marca_telegram.sql
-- Mòdul de Configuració de l'Empresa, Jornada Laboral, Marca Camaleònica i Rols (Spec 011)

-- 1. Ampliació de la taula empreses amb paràmetres de Telegram, ADN de marca i 2FA
ALTER TABLE empreses
    ADD COLUMN IF NOT EXISTS telegram_bot_token VARCHAR(255),
    ADD COLUMN IF NOT EXISTS telegram_webhook_secret VARCHAR(255),
    ADD COLUMN IF NOT EXISTS telegram_bot_actiu BOOLEAN NOT NULL DEFAULT false,
    ADD COLUMN IF NOT EXISTS telegram_estat_connexio VARCHAR(30) NOT NULL DEFAULT 'NO_CONFIGURAT',
    ADD COLUMN IF NOT EXISTS adn_marca_path VARCHAR(500),
    ADD COLUMN IF NOT EXISTS adn_paleta_proposta JSONB,
    ADD COLUMN IF NOT EXISTS codis_recuperacio_2fa TEXT[],
    ADD COLUMN IF NOT EXISTS monograma VARCHAR(10);

-- Comprovació de valors permesos d'estat de connexió del bot
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'empreses_telegram_estat_connexio_check'
    ) THEN
        ALTER TABLE empreses ADD CONSTRAINT empreses_telegram_estat_connexio_check
            CHECK (telegram_estat_connexio IN ('OPERATIU', 'ERROR_CONNEXIO', 'NO_CONFIGURAT'));
    END IF;
END $$;

-- 2. Ampliació de la taula slots_jornada amb Jornada Intensiva d'Estiu
ALTER TABLE slots_jornada
    ADD COLUMN IF NOT EXISTS es_intensiva_estiu BOOLEAN NOT NULL DEFAULT false,
    ADD COLUMN IF NOT EXISTS data_inici_estiu DATE,
    ADD COLUMN IF NOT EXISTS data_fi_estiu DATE,
    ADD COLUMN IF NOT EXISTS hora_entrada_estiu TIME,
    ADD COLUMN IF NOT EXISTS hora_sortida_estiu TIME;

-- 3. Ampliació de la taula usuaris amb data d'últim accés per auditoria
ALTER TABLE usuaris
    ADD COLUMN IF NOT EXISTS data_ultim_acces TIMESTAMPTZ;

-- 4. Permisos per al rol d'aplicació
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO sevalor_app;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO sevalor_app;
