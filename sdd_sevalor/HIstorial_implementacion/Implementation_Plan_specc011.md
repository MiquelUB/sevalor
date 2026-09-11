# Implementació de Configuració de l'Empresa, Jornada Laboral, Marca Camaleònica i Rols (/gestio/configuracio — Spec 011)

Aquest pla detalla la implementació integral del mòdul **Spec 011** (`/gestio/configuracio`), el panell d'ajustos estratègics, identitat corporativa, governança laboral i motor camaleònic de CampoPro / SEVALOR Suite v4.0.

## User Review Required

> [!IMPORTANT]
> **Segregació de Funcions i Veto Estricte d'Enginyer (HTTP 403)**:
> - El rol **Enginyer** té accés de **Només Lectura** a la consulta dels paràmetres corporatius i al seu propi slot de jornada assignat.
> - Té **VETO TOTAL (HTTP 403 Forbidden)** sobre l'edició d'usuaris d'oficina, modificació de colors HSL de marca, càrrega de logotips, reinici de 2FA i paràmetres del bot de Telegram.
> - La tresoreria i dades financeres (IBAN, Bizum, targetes) estan reubicades de forma exclusiva a `/gestio/comptabilitat` (Spec 007).

> [!WARNING]
> **Protecció de l'Últim Boss (EDGE-05)**:
> - Es bloqueja a nivell d'API i base de dades (HTTP 400 Bad Request) qualsevol intent de donar de baixa o eliminar l'últim compte amb rol `BOSS` de l'empresa per evitar l'orfandat de l'administració.

> [!NOTE]
> **Política de Codis QR Constitucional (v4.0)**:
> - **Prohibició absoluta** de codis QR per a la traçabilitat d'eines de camp (les eines s'identifiquen per marca, model i número de sèrie segons Spec 004/008).
> - **S'autoritza exclusivament**:
>   1. El codi QR legal Veri*factu a les factures i albarans oficials (Spec 007).
>   2. El codi QR estàndard de configuració 2FA TOTP (Google Authenticator) per a l'enrolament o reinici d'accés de personal d'oficina (RF-06).

---

## Proposta de Canvis

### 1. Base de Dades & Migracions PostgreSQL (PostGIS + RLS)

#### [NEW] `db/migrations/013_configuracio_marca_telegram.sql`
- Ampliació de la taula `empreses`:
  - `telegram_bot_token VARCHAR(255)`
  - `telegram_webhook_secret VARCHAR(255)`
  - `telegram_bot_actiu BOOLEAN NOT NULL DEFAULT false`
  - `telegram_estat_connexio VARCHAR(30) NOT NULL DEFAULT 'NO_CONFIGURAT'`
  - `adn_marca_path VARCHAR(500)`
  - `adn_paleta_proposta JSONB`
  - `codis_recuperacio_2fa TEXT[]`
  - `monograma VARCHAR(10)`
- Ampliació de la taula `slots_jornada`:
  - `es_intensiva_estiu BOOLEAN NOT NULL DEFAULT false`
  - `data_inici_estiu DATE`
  - `data_fi_estiu DATE`
  - `hora_entrada_estiu TIME`
  - `hora_sortida_estiu TIME`
- Ampliació de la taula `usuaris`:
  - `data_ultim_acces TIMESTAMPTZ`
- Polítiques RLS obligatòries (`FORCE ROW LEVEL SECURITY`) sota `app.current_empresa_id`.

---

### 2. Models ORM SQLAlchemy 2.0 (`backend/app/models/models.py`)

#### [MODIFY] [`backend/app/models/models.py`](file:///media/akaun/Project_1/SEVALOR/backend/app/models/models.py)
- Afegir els nous camps a les classes `Empresa`, `SlotJornada` i `Usuari`.

---

### 3. Backend API REST (`/api/v1/gestio/configuracio`)

#### [NEW] `backend/app/api/v1/gestio/configuracio.py`
Endpoints clau:
- `GET /api/v1/gestio/configuracio/empresa`: Dades corporatives, monograma, quota de disc i estat del bot (lectura per a Boss, Secretaria i Enginyer).
- `PUT /api/v1/gestio/configuracio/empresa`: Actualització de dades fiscals/contacte (Boss i Secretaria; Enginyer 403).
- `PUT /api/v1/gestio/configuracio/marca`: Modificació de `primari_hsl`, `secundari_hsl`, `accent_hsl`. Validació algorítmica de contrast WCAG 2.1 AA (mínim 4.5:1, EDGE-02).
- `POST /api/v1/gestio/configuracio/marca/adn`: Càrrega de guia d'estil amb anàlisi IA de paleta i mandat HITL per al Boss (RF-12, RF-13).
- `POST /api/v1/gestio/configuracio/logotip`: Pujada de logotip (PNG/JPG <= 10MB) amb comprovació de Magic Bytes (EDGE-03) i emmagatzematge sobirà a Hetzner Falkenstein (`/docs/<empresa_id>/configuracio/`).
- `GET /api/v1/gestio/configuracio/usuaris`: Llistat d'usuaris administratius d'oficina (Zero Mock Data).
- `POST /api/v1/gestio/configuracio/usuaris`: Alta de personal administratiu amb contrasenya forta de 12 caràcters (Boss i Secretaria; Enginyer 403).
- `PUT /api/v1/gestio/configuracio/usuaris/{id}`: Modificació d'usuari i rol.
- `DELETE /api/v1/gestio/configuracio/usuaris/{id}`: Baixa d'usuari amb protecció de l'últim Boss (HTTP 400 si és l'últim Boss, EDGE-05).
- `POST /api/v1/gestio/configuracio/usuaris/{id}/reset-2fa`: Reinici de secret TOTP facultat exclusivament al Boss (RF-06).
- `GET /api/v1/gestio/configuracio/slots`: Llistat d'slots de jornada laboral.
- `POST /api/v1/gestio/configuracio/slots` & `PUT /api/v1/gestio/configuracio/slots/{id}`: Creació/edició d'slot amb validació de rangs coherents (EDGE-08) i suport d'Intensiva d'Estiu (RF-10).
- `PUT /api/v1/gestio/configuracio/telegram`: Credencials del Bot de Telegram (Token i Webhook Secret).
- `POST /api/v1/gestio/configuracio/telegram/provar`: Prova asíncrona de connexió amb Telegram `getMe` gestionant timeouts de 5s (RF-20, EDGE-09).

#### [MODIFY] [`backend/app/main.py`](file:///media/akaun/Project_1/SEVALOR/backend/app/main.py)
- Muntar el router `configuracio_router` sota `settings.API_V1_STR`.

---

### 4. Bateria de Proves Backend Docker (`backend/tests/test_configuracio.py`)

#### [NEW] `backend/tests/test_configuracio.py`
- Prova 1: Lectura de paràmetres corporatius i aïllament RLS multi-inquilí.
- Prova 2: Veto d'Enginyer (HTTP 403) a edició de marca, usuaris, logotip i bot de Telegram.
- Prova 3: Validació de contrast WCAG 2.1 AA (<4.5:1 rebutjat amb HTTP 422/400).
- Prova 4: Pujada de logotip amb validació de Magic Bytes (rebuig d'executables camuflats).
- Prova 5: Protecció de l'últim Boss (HTTP 400 davant d'intent de baixa).
- Prova 6: Reinici de 2FA TOTP reservat exclusivament al Boss.
- Prova 7: Slots de jornada amb validació cronològica coherent i intensiva d'estiu.
- Prova 8: Prova asíncrona de Telegram getMe amb gestió de timeout.

---

### 5. Frontend PWA Next.js 14 (`pwa/src/app/gestio/configuracio/page.tsx`)

#### [NEW] `pwa/src/app/gestio/configuracio/page.tsx`
Pàgina d'alta densitat organitzada en 4 pestanyes principals:
1. **Identitat & Marca Camaleònica**:
   - Color picker visual per a primari, secundari i accent en HSL.
   - Indicador de contrast WCAG 2.1 AA en viu (mínim 4.5:1).
   - Finestra de Live Preview (botons, targetes i elements interactius).
   - Càrrega d'ADN de marca amb anàlisi IA de paleta i botó d'aprovació Boss (HITL).
   - Slot de pujada de logotip oficial (PNG/JPG <= 10MB) o fallback a monograma tipogràfic net (Zero Mock Data).
2. **Personal Administratiu & Seguretat 2FA**:
   - Taula d'usuaris d'oficina (Boss, Secretaria, Enginyer, Comptabilitat).
   - Generació automàtica de contrasenya de 12 caràcters per a noves altes.
   - Indicador d'estat 2FA TOTP per usuari.
   - Botó "Reiniciar 2FA" reservat per a Boss amb modal de codi QR per a Google Authenticator.
   - Bloqueig visual de baixa sobre l'últim Boss.
3. **Slots de Jornada Laboral**:
   - Llistat de torns configurats (Continuada, Partida, Torn Especial).
   - Editor de rangs horaris amb validació d'inici/fi de dinar.
   - Commutador de Jornada Intensiva d'Estiu amb selector de dates de vigència.
4. **Integració Telegram Bot**:
   - Camps per a Bot Token i Webhook Secret.
   - Botó "Provar Connexió Bot" amb diagnòstic en temps real (OPERATIU, ERROR_CONNEXIO).
   - Enllaç d'ajuda oficial amb BotFather.

#### [MODIFY] [`pwa/src/app/gestio/layout.tsx`](file:///media/akaun/Project_1/SEVALOR/pwa/src/app/gestio/layout.tsx)
- Afegir `Configuració & Marca` (`/gestio/configuracio`, icona `Settings`, badge `CFG`) a la navegació lateral i al cercador Spotlight (`Ctrl + K`).

---

### 6. Protocol d'Auditoria QA Frontend (`pwa/test_configuracio_audit.mjs`)

#### [NEW] `pwa/test_configuracio_audit.mjs`
10 tests exhaustius cobrint els 22 RFs i els 10 Casos Límit (EDGE-01 a EDGE-10):
1. **RF-01 a RF-04, RF-21, Zero Mock Data**: Llistat tabular d'usuaris administratius, aïllament RLS i empty state canònic de Dia 0.
2. **RF-03, EDGE-10**: Veto total d'Enginyer (HTTP 403) a modificació d'usuaris, marca i paràmetres.
3. **EDGE-05**: Protecció d'orfandat de l'inquilí (rebuig d'esborrat de l'últim Boss amb HTTP 400).
4. **RF-05, RF-06, EDGE-01**: 2FA TOTP mandatori, reinici facultat al Boss, i codis de recuperació estàtics d'onboarding.
5. **RF-07**: Inactivació de compte amb expulsió immediata i revocació de JWT.
6. **RF-08 a RF-11, EDGE-04, EDGE-06, EDGE-08**: Slots de jornada individualitzats, validació cronològica, intensiva d'estiu i càlcul DST en UTC.
7. **RF-12 a RF-15, EDGE-02**: Motor Camaleònic HSL, mandat HITL d'aprovació d'ADN de marca i validació de contrast WCAG 2.1 AA (mínim 4.5:1).
8. **RF-16 a RF-18, EDGE-03**: Càrrega de logotip <=10MB, validació de Magic Bytes (rebuig d'executables camuflats) i fallback a monograma net.
9. **RF-19, RF-20, EDGE-09**: Credencials del Bot de Telegram, prova de connexió getMe amb gestió asíncrona de timeouts.
10. **RNF Sobirania Hetzner & Disseny Camaleònic**: Emmagatzematge a Hetzner Alemanya (`/docs/<empresa_id>/configuracio/`), zero dependències d'AWS S3 i suport complet de Mode Fosc (`dark:`).

---

## Pla de Verificació

### Proves Automatitzades
- **Backend Docker**: `docker run ... python run_tests.py` (Objectiu: 60+ proves en verd).
- **Frontend QA Audit**: `node test_configuracio_audit.mjs` (Objectiu: 10/10 proves en verd).
- **Bateria Global de QA**: `for f in test_*_audit.mjs; do node "$f"; done` (Objectiu: 96/96 proves en verd).
- **Compilació Next.js 14**: `npm run build` (Objectiu: 25/25 pàgines estàtiques generades amb èxit).
