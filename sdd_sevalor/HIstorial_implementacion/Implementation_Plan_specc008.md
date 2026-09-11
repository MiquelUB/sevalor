# Pla d'Implementació: Gestió d'Operaris i Rendiment de Camp (/gestio/operaris — Spec 008)

Aquest pla defineix la implementació integral del mòdul de **Gestió d'Operaris i Rendiment de Camp** (`/gestio/operaris`) d'acord amb la **Spec 008**, la Constitució v4.0 de SEVALOR, la política de **Zero Mock Data**, el suport complet per a **Mode Clar i Mode Fosc**, el compliment estricte del **RDL 8/2019 de Registre de Jornada Laboral**, la custòdia d'eines i vehicles, i el **Veto d'Enginyer**.

---

## User Review Required

> [!IMPORTANT]
> **Registre de Jornada Laboral i Tancament Automàtic a les 8 hores (RDL 8/2019 — RF-06, RF-07 / EDGE-03)**:
> - Si un operari manté la jornada oberta durant més de 8 hores sense marcar la sortida, el sistema aplica un tancament automàtic a les 8h segons la modalitat d'empresa (continuada o partida), canviant l'estat del shift a `INCIDENCIA` amb el motiu *"Tancament automàtic per omissió de sortida"*.
> - La regularització manual de jornades queda reservada a **Secretaria, RRHH i Boss**, i genera una traça d'auditoria immutable (`auditoria_registres_jornada`) amb els valors anteriors, els nous valors i el motiu justificatiu requerit per la Inspecció de Treball.

> [!WARNING]
> **Veto d'Enginyer a Control Horari, Salaris i Credencials (RF-09, RF-17, RF-28 / EDGE-02)**:
> - Els usuaris amb rol `ENGINYER` tenen **veto absolut (HTTP 403 Forbidden)** sobre:
>   - La pestanya de Control Horari (`shifts`) i endpoints de fitxatges.
>   - L'edició del cost/hora laboral i qualsevol dada salarial o de nòmina (restringida a Spec 007).
>   - La generació o restabliment de PINs d'accés PWA.
>   - L'assignació directa d'actius de flota i magatzem.
> - L'Enginyer **SÍ que pot visualitzar** el cost/hora teòric de referència per al càlcul de pressupostos d'obra (RF-27) i articular la composició de **Colles de Camp** per tasca (RF-13).

> [!NOTE]
> **Gestió de Custòdia d'Eines i Reversió de Baixa (RF-18 a RF-20, RF-29, RF-30 / EDGE-07)**:
> - Les eines de treball s'identifiquen i custodien estrictament pel seu **número de referència de fabricant, marca, model i número de sèrie** (amb exclusió formal de codis QR en eines d'acord amb la Constitució v4.0).
> - La baixa laboral d'un operari bloqueja si manté eines o vehicles pendents de devolució (EDGE-07), revoca de forma immediata els tokens JWT actius a Redis (RF-30) i transfereix la responsabilitat de devolució física al Cap de Colla (RF-29).

---

## Proposed Changes

### Base de Dades PostgreSQL (`db/migrations/010_operaris_shifts_colles.sql`)

#### [NEW] `db/migrations/010_operaris_shifts_colles.sql`
- Afegir camps a `usuaris`:
  - `especialitat VARCHAR(50)` (SISTEMES_REG, OBRA_CIVIL, ELECTRICITAT, CONDUCTOR_MAQUINARIA, FONTANERIA).
  - `estat_operatiu VARCHAR(30) DEFAULT 'DISPONIBLE'` (DISPONIBLE, EN_FEINA, VACANCES, BAIXA).
  - `cap_de_grup_id UUID REFERENCES usuaris(id)`.
  - `cost_hora_eur NUMERIC(8, 2) DEFAULT 22.50`.
  - `carnet_conduir VARCHAR(20) DEFAULT 'B'`.
  - `carnet_caducitat DATE`.
  - `prl_certificat_vigencia DATE`.
  - `intents_pin_fallits INTEGER DEFAULT 0`.
  - `pin_bloquejat BOOLEAN DEFAULT false`.
- Crear taula `registres_jornada_laboral` (RDL 8/2019):
  - `id UUID PRIMARY KEY`, `empresa_id UUID REFERENCES empreses(id)`, `usuari_id UUID REFERENCES usuaris(id)`.
  - `data_jornada DATE`, `hora_inici TIMESTAMPTZ`, `hora_fi TIMESTAMPTZ`.
  - `geolocalitzacio_inici VARCHAR(100)`, `geolocalitzacio_fi VARCHAR(100)`.
  - `estat VARCHAR(20)` (EN_CURS, COMPLERT, INCIDENCIA).
  - `tancament_automatic BOOLEAN DEFAULT false`, `motiu_incidencia TEXT`.
  - `hores_ordinaries NUMERIC(5,2)`, `hores_extraordinaries NUMERIC(5,2)`.
  - `version_id INTEGER DEFAULT 1` (control de concurrència optimista EDGE-09).
- Crear taula `auditoria_registres_jornada`:
  - `id UUID PRIMARY KEY`, `shift_id UUID REFERENCES registres_jornada_laboral(id)`, `modificat_per_id UUID REFERENCES usuaris(id)`.
  - `valors_anteriors JSONB`, `nous_valors JSONB`, `motiu_justificatiu TEXT NOT NULL`, `created_at TIMESTAMPTZ`.
- Configurar polítiques RLS (Row Level Security) per tenant a totes les noves taules.

---

### Backend FastAPI (`backend/app/api/v1/gestio/operaris.py`)

#### [NEW] `backend/app/api/v1/gestio/operaris.py`
- `GET /gestio/operaris`: Directori d'operaris actius amb mètriques agregades de capçalera (Total Operaris, Valoració Clients, % Compliment Horari d'avui, Km conduïts, Eines assignades).
- `POST /gestio/operaris`: Alta manual d'operari per Secretaria/Boss (HTTP 403 si Enginyer). Genera PIN aleatori de 4 dígits i simula tramesa SMS.
- `POST /gestio/operaris/{id}/reset-pin`: Restabliment de PIN i desbloqueig per 4 intents fallits (HTTP 403 si Enginyer).
- `GET /gestio/operaris/{id}/shifts`: Llistat de jornades sota RDL 8/2019 (Secretaria/Boss). Si el rol és Enginyer retorna HTTP 403 Forbidden.
- `POST /gestio/operaris/{id}/shifts/regularitzar`: Rectificació manual d'un shift amb traça immutable d'auditoria i control de versió optimista (`version_id`).
- `POST /gestio/operaris/shifts/tancament-automatic`: Executa el protocol d'auto-tancament a 8h en jornades que no han marcat sortida.
- `PUT /gestio/operaris/{id}/colla`: Modificació de composició de colla per l'Enginyer. Inhabilita treballadors de baixa o vacances (RF-15).
- `PUT /gestio/operaris/{id}/custodia`: Assignació de vehicle i eines (Secretaria/Boss només).
- `POST /gestio/operaris/{id}/baixa`: Protocol d'inactivació amb comprovació d'actius pendents (EDGE-07) i revocació de tokens.
- `PATCH /gestio/operaris/{id}/cost-hora`: Actualització de cost/hora per Secretaria/Boss (HTTP 403 si Enginyer).

#### [MODIFY] `backend/app/main.py`
- Importar i registrar `operaris_router` a l'aplicació FastAPI sota el prefix `/api/v1`.

---

### Layout Desktop (`pwa/src/app/gestio/layout.tsx`)

#### [MODIFY] `pwa/src/app/gestio/layout.tsx`
- Afegir l'enllaç de navegació a la barra lateral:
  `{ label: "Equip & Operaris", href: "/gestio/operaris", icon: HardHat, badge: "RRHH" }`
- Afegir operaris i colles a la base de cerca de Spotlight (`Ctrl + K`).

---

### Pàgina Principal de Gestió d'Operaris (`pwa/src/app/gestio/operaris/page.tsx`)

#### [NEW] `pwa/src/app/gestio/operaris/page.tsx`
- **Mètriques Consolidades de Capçalera (RF-02)**: Total plantilla, complimient horari avui (%), hores extres acumulades, eines assignades, km mensuals.
- **Directori d'Alta Densitat en Quadrícula / Llista**: Codi, Nom, NIF, Rol (Cap de Colla 👑 / Oficial), Especialitat, Estat Operatiu (Disponible, En feina, Vacances, Baixa), Cost/Hora (visió teòrica per a pressupostació), Vehicle assignat.
- **Cercador Reactiu (<200 ms)** per nom, NIF o especialitat.
- **Fitxa 360° en 8 Pestanyes Independents (RF-04)**:
  1. `info`: Dades personals, contacte, carnet de conduir i vigència PRL.
  2. `shifts`: Taula oficial RDL 8/2019. **Veto d'Enginyer: si l'usuari és Enginyer, mostra missatge d'accés denegat 403**. Botó de regularització d'anomalies per a Secretaria/Boss.
  3. `crew`: Colla operativa. Desplegable d'ajudants sota el Cap de Colla amb bloqueig visual de Baixa/Vacances.
  4. `jobs`: Historial de feines finalitzades amb visor de les 3 fotografies obligatòries d'obra.
  5. `reviews`: Ressenyes i valoracions de clients.
  6. `vehicles`: Vehicle habitual i registres d'odòmetre per OCR.
  7. `tools`: Eines sota custòdia amb referència, marca, model i estat (alerta si està en reparació o perduda).
  8. `incidents`: Historial d'incidències de camp reportades per l'operari amb notes de veu i resolució tècnica de l'Enginyer.
- **Modals Específics**:
  - Modal d'Alta d'Operari & generació de PIN via SMS.
  - Modal de Regularització de Jornada amb motiu d'auditoria obligatori.
  - Modal de Reset de PIN PWA.
  - Modal de Baixa Laboral amb comprovació de custòdia d'actius.
- **Zero Mock Data (Dia 0 Canònic)**:
  - Text buit canònic: *"No hi ha operaris registrats a la plantilla"*.
- **Suport complet per a Mode Clar i Mode Fosc (`dark:`)**.

---

### Protocol de Proves i Auditoria QA (`pwa/test_operaris_audit.mjs`)

#### [NEW] `pwa/test_operaris_audit.mjs`
- Prova 1: Renderitzat de directori i estat buit canònic Dia 0 (RF-01, RF-02 / Zero Mock Data).
- Prova 2: Tancament automàtic a 8h de jornada oberta amb incidència per omissió (RF-07 / EDGE-03).
- Prova 3: Veto d'Enginyer sobre endpoints i pestanya de Control Horari (HTTP 403) (RF-09 / EDGE-04).
- Prova 4: Traça immutable d'auditoria en regularitzacions de jornada laboral segons RDL 8/2019 (RF-10).
- Prova 5: Bloqueig d'assignació a colles d'operaris en situació de Baixa o Vacances (RF-15).
- Prova 6: Veto d'Enginyer sobre modificació de cost/hora i custòdia d'eines (RF-17, RF-28).
- Prova 7: Bloqueig de planificació d'eines marcades en estat EN_REPARACIO o PERDUDA (RF-19 / EDGE-06).
- Prova 8: Bloqueig de baixa d'operari amb eines o vehicle pendents de devolució (EDGE-07).
- Prova 9: Generació de PIN PWA, enviament per SMS i suspensió per 4 intents fallits (RF-25, RF-26).
- Prova 10: Control de concurrència optimista (`version_id`) davant modificacions simultànies (EDGE-09).

---

## Verification Plan

### Automated Tests
1. **Bateria Backend a Docker**:
   ```bash
   docker run --rm --network host -v /media/akaun/Project_1/SEVALOR/backend:/app -w /app campopro-backend:latest python run_tests.py
   ```
2. **Auditoria QA de Gestió d'Operaris**:
   ```bash
   node pwa/test_operaris_audit.mjs
   ```
3. **Bateria Global de Totes les Suites Frontend QA**:
   ```bash
   node pwa/test_pwa_audit.mjs && node pwa/test_gestio_audit.mjs && node pwa/test_flota_audit.mjs && node pwa/test_superadmin_audit.mjs && node pwa/test_proveidors_audit.mjs && node pwa/test_operaris_audit.mjs
   ```
4. **Compilació de Producció Next.js**:
   ```bash
   cd pwa && npm run build
   ```
