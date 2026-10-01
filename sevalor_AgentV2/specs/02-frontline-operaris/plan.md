# Technical Implementation Plan: Frontline Operaris

**Feature Directory**: `sevalor_AgentV2/specs/02-frontline-operaris`  
**Date**: 2026-09-29  
**Specification**: [Feature Specification: Frontline Operaris](./spec.md)

---

## 1. Technical Context

- **Frontend Platform**: Next.js 14+ (App Router), TypeScript, Tailwind CSS, Lucide Icons.
- **PWA Technologies**: Service Worker (`sw.js`), Workbox Background Sync, Dexie.js (IndexedDB wrapper), HTML5 Media Capture & Video APIs, Web Crypto API.
- **Backend API**: Python 3.11+, FastAPI (asynchronous ASGI), Pydantic v2.
- **Database & Storage**: PostgreSQL 15+ with mandatory `FORCE ROW LEVEL SECURITY` (RLS), SQLAlchemy 2.0 (AsyncSession), Alembic migrations, Sovereign Local Storage (Hetzner, Falkenstein EU - AES-256-GCM at rest, no public cloud S3).
- **Caching & Async Queues**: Redis 7+, Celery Workers (`queue_default`, `queue_media`).
- **AI & Processing Models**: Whisper v3 (local audio transcription), OCR Pipeline (Tesseract/PaddleOCR for receipt and odometer text extraction), Douglas-Peucker geometry simplification algorithm (for dense GIS GeoJSON).
- **Testing**: pytest (FastAPI integration & unit), Playwright (E2E & PWA offline flows), Web Crypto test suites.

---

## 2. Architecture & Offline-First Data Flow

### 2.1 High-Level Component Topology

```
+-----------------------------------------------------------------------------------+
| Next.js PWA Client (Mobile Browser / Installed PWA)                               |
|                                                                                   |
|  [Tactile UI / Numpad]  [Camera / Torch]  [Map / 4-Color Canvas]  [Voice Recorder]|
|           |                     |                 |                      |        |
|  +--------v---------------------v-----------------v----------------------v-----+  |
|  | Web Crypto API (PBKDF2 100k + AES-GCM 256) / Memory Vault                   |  |
|  +---------------------------------+-------------------------------------------+  |
|                                    |                                              |
|  +---------------------------------v-------------------------------------------+  |
|  | Dexie.js IndexedDB: ordres, tiquets, incidencies, fichajes, sync_queue      |  |
|  +---------------------------------+-------------------------------------------+  |
|                                    |                                              |
|  +---------------------------------v-------------------------------------------+  |
|  | Service Worker (Cache-First Assets + Workbox Background Sync)               |  |
|  +---------------------------------+-------------------------------------------+  |
+------------------------------------|----------------------------------------------+
                                     | Network Online / Sync Event
                                     v
+-----------------------------------------------------------------------------------+
| FastAPI Backend Gateway (Python 3.11 ASGI)                                        |
|                                                                                   |
|  - Middleware: Next.js Auth Cookie / Bearer JWT Verification                      |
|  - Rate Limiter: SlowAPI (5 req/min on /operari_auth/login)                       |
|  - Multi-Tenant RLS: set_tenant_context() -> SET LOCAL app.current_empresa_id     |
|                                                                                   |
|  [POST /api/v1/operari_pwa/sync/push]   <-- Batch Atomic Sync Endpoint            |
|  [Routers: auth, feines, jornada, picking, vehicles, incidencies, planols, tiquets|
+-------------------+---------------------------------------+-----------------------+
                    |                                       |
                    v                                       v
+-----------------------------------+   +-------------------------------------------+
| PostgreSQL 15 (Sovereign Storage) |   | Celery Workers + Redis Cluster            |
|  - FORCE ROW LEVEL SECURITY (RLS) |   |  - Whisper v3 (Catalan/Spanish Audio)     |
|  - AES-256-GCM encrypted volumes  |   |  - OCR Pipeline (Receipts & Odometers)    |
|  - Strict tenant table schemas    |   |  - Douglas-Peucker Vector Simplification  |
+-----------------------------------+   +-------------------------------------------+
```

### 2.2 Offline Cryptography & Sentinel Validation Flow
1. **Device Enrollment**: The technician enters their corporate phone number and receives an SMS OTP. Upon verification, the device generates a local salt and stores tenant metadata in IndexedDB.
2. **Key Derivation (Zero-Trust Offline)**:
   $$\text{MasterKey} = \text{PBKDF2}(\text{PIN}, \text{Salt}, \text{iterations}=100000, \text{hash}=\text{SHA-256}, \text{length}=256)$$
3. **Sentinel Decryption**: The master key attempts to decrypt a static sentinel block (`"CAMPOPRO_SENTINEL"`) encrypted with AES-GCM 256 bits in IndexedDB. If the decrypted payload matches, the PIN is validated locally, opening the session.
4. **RAM Volatility**: Master keys exist only in volatile JavaScript memory. On logout or after 5 minutes in the background, keys are scrubbed from RAM.

---

## 3. Database Schema & Tables

All PostgreSQL tables enforce `FORCE ROW LEVEL SECURITY` using `app.current_empresa_id`.

### 3.1 Server Database Tables

#### `usuaris` (Field Worker Authentication & Profile)
```sql
CREATE TABLE usuaris (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    empresa_id UUID NOT NULL REFERENCES empreses(id) ON DELETE CASCADE,
    nif VARCHAR(20) NOT NULL,
    nom VARCHAR(100) NOT NULL,
    telefon VARCHAR(20),
    rol VARCHAR(30) NOT NULL DEFAULT 'OPERARI', -- OPERARI, CAP_DE_COLLA, CAPATAZ
    pin_hash VARCHAR(255),
    intents_pin_fallits INT DEFAULT 0,
    pin_bloquejat BOOLEAN DEFAULT FALSE,
    vehicle_assignat_id UUID REFERENCES vehicles(id) ON DELETE SET NULL,
    estat VARCHAR(20) DEFAULT 'ACTIU',
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);
ALTER TABLE usuaris ENABLE ROW LEVEL SECURITY;
ALTER TABLE usuaris FORCE ROW LEVEL SECURITY;
CREATE POLICY usuaris_empresa_isolation ON usuaris
    FOR ALL USING (empresa_id = NULLIF(current_setting('app.current_empresa_id', true), '')::uuid);
```

#### `registres_jornada_laboral` (Shift Clock-in & Clock-out)
```sql
CREATE TABLE registres_jornada_laboral (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    empresa_id UUID NOT NULL REFERENCES empreses(id) ON DELETE CASCADE,
    usuari_id UUID NOT NULL REFERENCES usuaris(id) ON DELETE CASCADE,
    hora_inici TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    hora_fi TIMESTAMPTZ,
    geolocalitzacio_inici VARCHAR(100),
    geolocalitzacio_fi VARCHAR(100),
    odometre_inici INT,
    odometre_fi INT,
    estat VARCHAR(20) DEFAULT 'EN_CURS', -- EN_CURS, COMPLERT
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);
ALTER TABLE registres_jornada_laboral ENABLE ROW LEVEL SECURITY;
ALTER TABLE registres_jornada_laboral FORCE ROW LEVEL SECURITY;
CREATE POLICY jornada_empresa_isolation ON registres_jornada_laboral
    FOR ALL USING (empresa_id = NULLIF(current_setting('app.current_empresa_id', true), '')::uuid);
```

#### `ordres_treball` (Work Orders & 3-Phase Photos)
```sql
CREATE TABLE ordres_treball (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    empresa_id UUID NOT NULL REFERENCES empreses(id) ON DELETE CASCADE,
    codi VARCHAR(50) NOT NULL,
    titol VARCHAR(255) NOT NULL,
    descripcio TEXT,
    client_id UUID REFERENCES clients(id),
    vehicle_id UUID REFERENCES vehicles(id),
    cap_de_colla_id UUID REFERENCES usuaris(id),
    adreca VARCHAR(255),
    coords_gps VARCHAR(100), -- Lat, Lng
    data_planificacio DATE,
    estat VARCHAR(30) DEFAULT 'PENDENT', -- PENDENT, EN_TRANSIT, EN_CURS, PAUSADA, COMPLERT
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);
ALTER TABLE ordres_treball ENABLE ROW LEVEL SECURITY;
ALTER TABLE ordres_treball FORCE ROW LEVEL SECURITY;
CREATE POLICY ot_empresa_isolation ON ordres_treball
    FOR ALL USING (empresa_id = NULLIF(current_setting('app.current_empresa_id', true), '')::uuid);
```

#### `fulles_picking` and `linies_picking` (Materials & Mathematical Balance)
```sql
CREATE TABLE fulles_picking (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    empresa_id UUID NOT NULL REFERENCES empreses(id) ON DELETE CASCADE,
    ordre_treball_id UUID NOT NULL REFERENCES ordres_treball(id) ON DELETE CASCADE,
    vehicle_id UUID REFERENCES vehicles(id),
    estat_picking VARCHAR(30) DEFAULT 'PENDENT', -- PENDENT, PICK_IN_CONFIRMAT, TANCAT
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE linies_picking (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    empresa_id UUID NOT NULL REFERENCES empreses(id) ON DELETE CASCADE,
    picking_id UUID NOT NULL REFERENCES fulles_picking(id) ON DELETE CASCADE,
    article_id UUID NOT NULL REFERENCES articles(id),
    quantitat_prevista NUMERIC(10, 2) NOT NULL,
    quantitat_carregada_pick_in NUMERIC(10, 2) DEFAULT 0.00,
    quantitat_retornada_pick_out NUMERIC(10, 2) DEFAULT 0.00,
    quantitat_mermada NUMERIC(10, 2) DEFAULT 0.00,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);
ALTER TABLE fulles_picking ENABLE ROW LEVEL SECURITY;
ALTER TABLE fulles_picking FORCE ROW LEVEL SECURITY;
ALTER TABLE linies_picking ENABLE ROW LEVEL SECURITY;
ALTER TABLE linies_picking FORCE ROW LEVEL SECURITY;
CREATE POLICY fulles_empresa_isolation ON fulles_picking
    FOR ALL USING (empresa_id = NULLIF(current_setting('app.current_empresa_id', true), '')::uuid);
CREATE POLICY linies_empresa_isolation ON linies_picking
    FOR ALL USING (empresa_id = NULLIF(current_setting('app.current_empresa_id', true), '')::uuid);
```

#### `vehicles` & `tiquets_carburant` (Fleet & Fuel Audit)
```sql
CREATE TABLE vehicles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    empresa_id UUID NOT NULL REFERENCES empreses(id) ON DELETE CASCADE,
    matricula VARCHAR(20) NOT NULL,
    marca VARCHAR(50) NOT NULL,
    model VARCHAR(50) NOT NULL,
    tipus VARCHAR(30) DEFAULT 'FURGONETA', -- FURGONETA, CAMIO, 4X4, REMOLC, MAQUINARIA
    estat VARCHAR(20) DEFAULT 'OPERATIU', -- OPERATIU, EN_TRANSIT, AVERIAT, BAIXA_TEMPORAL
    odometre_acumulat INT DEFAULT 0,
    hores_motor_acumulades INT DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE tiquets_carburant (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    empresa_id UUID NOT NULL REFERENCES empreses(id) ON DELETE CASCADE,
    vehicle_id UUID NOT NULL REFERENCES vehicles(id),
    operari_id UUID NOT NULL REFERENCES usuaris(id),
    tiquet_foto_path VARCHAR(500) NOT NULL,
    odometre_foto_path VARCHAR(500) NOT NULL,
    litres NUMERIC(8, 2) NOT NULL,
    import_ NUMERIC(10, 2) NOT NULL,
    odometre_valor INT NOT NULL,
    estat_ocr VARCHAR(30) DEFAULT 'PENDENT_AUDITORIA', -- EXTRET_AUTOMATIC, PENDENT_AUDITORIA, REVISAT
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);
ALTER TABLE vehicles ENABLE ROW LEVEL SECURITY;
ALTER TABLE vehicles FORCE ROW LEVEL SECURITY;
ALTER TABLE tiquets_carburant ENABLE ROW LEVEL SECURITY;
ALTER TABLE tiquets_carburant FORCE ROW LEVEL SECURITY;
CREATE POLICY vehicles_empresa_isolation ON vehicles
    FOR ALL USING (empresa_id = NULLIF(current_setting('app.current_empresa_id', true), '')::uuid);
CREATE POLICY tiquets_carburant_empresa_isolation ON tiquets_carburant
    FOR ALL USING (empresa_id = NULLIF(current_setting('app.current_empresa_id', true), '')::uuid);
```

#### `incidencies` (Multimodal Field Contingencies)
```sql
CREATE TABLE incidencies (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    empresa_id UUID NOT NULL REFERENCES empreses(id) ON DELETE CASCADE,
    ordre_treball_id UUID REFERENCES ordres_treball(id),
    vehicle_id UUID REFERENCES vehicles(id),
    operari_id UUID REFERENCES usuaris(id),
    ambit VARCHAR(30) NOT NULL DEFAULT 'TASCA', -- TASCA, VEHICLE, GENERAL, SOS
    estat VARCHAR(20) NOT NULL DEFAULT 'VERMELL', -- VERMELL (Obert), VERD (Tancat)
    audio_path VARCHAR(500),
    transcripcio_audio TEXT,
    foto_path VARCHAR(500),
    planol_capa_id UUID,
    text_observacions TEXT,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);
ALTER TABLE incidencies ENABLE ROW LEVEL SECURITY;
ALTER TABLE incidencies FORCE ROW LEVEL SECURITY;
CREATE POLICY incidencies_empresa_isolation ON incidencies
    FOR ALL USING (empresa_id = NULLIF(current_setting('app.current_empresa_id', true), '')::uuid);
```

#### `planols_base` & `capes_vectorials` (Technical Plans & As-Built)
```sql
CREATE TABLE planols_base (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    empresa_id UUID NOT NULL REFERENCES empreses(id) ON DELETE CASCADE,
    ordre_treball_id UUID REFERENCES ordres_treball(id),
    nom VARCHAR(255) NOT NULL,
    fitxer_path VARCHAR(500) NOT NULL,
    tipus_format VARCHAR(20) NOT NULL, -- PDF, DXF, GEOJSON, RASTER
    es_georeferenciat BOOLEAN DEFAULT FALSE,
    bounds_json JSONB,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE capes_vectorials (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    empresa_id UUID NOT NULL REFERENCES empreses(id) ON DELETE CASCADE,
    planol_id UUID NOT NULL REFERENCES planols_base(id) ON DELETE CASCADE,
    nom VARCHAR(255) NOT NULL,
    es_tancada BOOLEAN DEFAULT FALSE,
    visible BOOLEAN DEFAULT TRUE,
    dades_geojson JSONB NOT NULL,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);
ALTER TABLE planols_base ENABLE ROW LEVEL SECURITY;
ALTER TABLE planols_base FORCE ROW LEVEL SECURITY;
ALTER TABLE capes_vectorials ENABLE ROW LEVEL SECURITY;
ALTER TABLE capes_vectorials FORCE ROW LEVEL SECURITY;
CREATE POLICY planols_empresa_isolation ON planols_base
    FOR ALL USING (empresa_id = NULLIF(current_setting('app.current_empresa_id', true), '')::uuid);
CREATE POLICY capes_empresa_isolation ON capes_vectorials
    FOR ALL USING (empresa_id = NULLIF(current_setting('app.current_empresa_id', true), '')::uuid);
```

---

### 3.2 Client-Side Dexie.js Schema (`pwa/src/lib/db.ts`)

```typescript
export class SevalorLocalDatabase extends Dexie {
  ordres!: Table<LocalOrdreTreball, string>;
  tiquets!: Table<LocalTiquetDespesa, string>;
  incidencies!: Table<LocalIncidencia, string>;
  fichajes!: Table<LocalFichaje, string>;
  sync_queue!: Table<SyncQueueItem, string>;

  constructor() {
    super("SevalorFieldDB");
    this.version(1).stores({
      ordres: "id, empresa_id, estat, data_planificacio",
      tiquets: "id, empresa_id, categoria, estat_sync",
      incidencies: "id, empresa_id, tipus, estat_sync",
      fichajes: "id, usuari_id, estat, timestamp",
      sync_queue: "id, bloc_uuid, timestamp, intents",
    });
  }
}
```

---

## 4. API Endpoints & Contract Matrix

| Method | Endpoint | Description | Auth / Role |
|---|---|---|---|
| `POST` | `/api/v1/operari_auth/login` | Validates NIF + 4-digit PIN, checks rate limit (5/min), returns JWT token. | Public (Rate limited) |
| `POST` | `/api/v1/operari/jornada/inici` | Starts shift clock-in with optional geolocation and vehicle odometer check. | `OPERARI`, `CAPATAZ` |
| `GET` | `/api/v1/operari/jornada/activa` | Returns the currently active shift for the authenticated worker. | `OPERARI`, `CAPATAZ` |
| `POST` | `/api/v1/operari/jornada/{id}/fi` | Concludes shift clock-out with geolocation and final odometer. | `OPERARI`, `CAPATAZ` |
| `POST` | `/api/v1/operari/jornada/{id}/vehicle`| Binds a vehicle to the operator's shift and validates cumulative odometer. | `OPERARI`, `CAPATAZ` |
| `GET` | `/api/v1/operari/feines` | Lists assigned work orders for the current day. | `OPERARI`, `CAPATAZ` |
| `GET` | `/api/v1/operari/feines/{id}` | Detailed work order modal data: customer, GPS, locks, picking items. | `OPERARI`, `CAPATAZ` |
| `PUT` | `/api/v1/operari/feines/{id}/iniciar-trajecte` | Commutes vehicle status to Blue (In Transit) and sets 25-minute ETA buffer. | `OPERARI`, `CAPATAZ` |
| `PUT` | `/api/v1/operari/feines/{id}/comencar` | Begins work timer. Enforces 50m geofence unless deviation flag is true. | `OPERARI`, `CAPATAZ` |
| `POST` | `/api/v1/operari/feines/{id}/fotos` | Uploads QA photo (`INICIAL`, `INTERMEDIA`, `FINAL`) with WebP formatting. | `OPERARI`, `CAPATAZ` |
| `GET` | `/api/v1/operari/feines/{id}/fotos` | Checks completeness status of the 3-phase photo quality assurance protocol. | `OPERARI`, `CAPATAZ` |
| `PUT` | `/api/v1/operari/feines/{id}/finalitzar` | Finalizes work order. Strict 400 error if any of the 3 photos are missing. | `OPERARI`, `CAPATAZ` |
| `POST` | `/api/v1/operari/picking` | Creates a picking sheet associated with a work order. | `OPERARI`, `CAPATAZ` |
| `POST` | `/api/v1/operari/picking/{id}/linies`| Adds scheduled material line to a picking sheet. | `OPERARI`, `CAPATAZ` |
| `PUT` | `/api/v1/operari/picking/linies/{id}`| Updates Pick In, Pick Out, Merma quantities; computes `Consum Real`. | `OPERARI`, `CAPATAZ` |
| `GET` | `/api/v1/operari/vehicles` | Returns fleet vehicles assigned to the operator's tenant. | `OPERARI`, `CAPATAZ` |
| `POST` | `/api/v1/operari/vehicles/{id}/checkin` | Records morning check-in: odometer, fuel level selector, equipment hours. | `OPERARI`, `CAPATAZ` |
| `POST` | `/api/v1/operari/vehicles/{id}/repostatge` | Logs refuel with dual photo paths (receipt + live odometer). | `OPERARI`, `CAPATAZ` |
| `POST` | `/api/v1/operari/vehicles/{id}/checkout` | Records evening check-out and computes daily net kilometers. | `OPERARI`, `CAPATAZ` |
| `POST` | `/api/v1/operari/vehicles/{id}/danys` | Reports vehicle bodywork or mechanical defect incident. | `OPERARI`, `CAPATAZ` |
| `GET` | `/api/v1/operari/incidencies` | Lists incidents created by the operator/squad. | `OPERARI`, `CAPATAZ` |
| `POST` | `/api/v1/operari/incidencies` | Creates multimodal incident (audio, photo, pin, text). Dispatches Celery Whisper. | `OPERARI`, `CAPATAZ` |
| `POST` | `/api/v1/operari/planols/{id}/capes` | Creates non-destructive As-Built annotation layer on a blueprint. | `OPERARI`, `CAPATAZ` |
| `GET` | `/api/v1/operari/tiquets` | Lists expense receipts for the day. | `OPERARI`, `CAPATAZ` |
| `POST` | `/api/v1/operari/tiquets` | Saves fuel or general expense ticket record. | `OPERARI`, `CAPATAZ` |
| `POST` | `/api/v1/operari/tiquets/ocr` | Uploads ticket image, processes OCR extraction, and stores receipt file. | `OPERARI`, `CAPATAZ` |
| `POST` | `/api/v1/operari_pwa/sync/push` | Bulk synchronization of offline queued actions (`FITXAR_JORNADA`, `CREAR_TIQUET`, `REPORTAR_INCIDENCIA`, `INICIAR_TRAJECTE`, `FINALITZAR_ORDRE`). | `OPERARI`, `CAPATAZ` |

---

## 5. Middleware, Auth & Security

### 5.1 Next.js Edge Middleware (`pwa/src/middleware.ts`)
- **Route Protection**: Matches `/operari/:path*`, `/gestio/:path*`, `/superadmin/:path*`.
- **Absolute Redirection Rule**: Redirects **MUST ALWAYS** use absolute pathnames evaluated against `request.url`:
  ```typescript
  const createRedirectWithClearedCookie = (targetUrl: string) => {
    return NextResponse.redirect(new URL(targetUrl, request.url));
  };
  // Example: createRedirectWithClearedCookie('/operari/login');
  ```
- **Role Enforcement**: Ensures tokens with `OPERARI` or `CAPATAZ` roles only access `/operari` routes, redirecting unauthorized attempts to `/operari/login?error=unauthorized`.

### 5.2 FastAPI Database Tenant Isolation Middleware
- Every incoming request passes through `get_db_with_tenant_context`:
  ```python
  async def get_db_with_tenant_context(request: Request) -> AsyncGenerator[AsyncSession, None]:
      empresa_id = getattr(request.state, "empresa_id", None) or request.headers.get("X-Empresa-ID")
      async with async_session_factory() as session:
          if empresa_id:
              await session.execute(text(f"SET LOCAL app.current_empresa_id = '{empresa_id}'"))
          yield session
  ```
- Guaranteed defense-in-depth: Even if raw SQL is executed, PostgreSQL's `FORCE ROW LEVEL SECURITY` rejects rows from other tenants.

---

## 6. Celery Asynchronous Workers & Tasks

All background workers run in dedicated Docker containers connected to Redis:

1. **`app.workers.tasks.transcriure_audio_task`** (`queue_media`):
   - **Trigger**: New audio voice note submitted on `/operari/incidencies`.
   - **Logic**: Loads local Whisper v3 model, transcribes Catalan & Spanish technical audio into text, saves transcription into `incidencies.transcripcio_audio`, and notifies the engineering dashboard via WebSocket.
2. **`app.workers.tasks.processar_ocr_tiquet_task`** (`queue_media`):
   - **Trigger**: New expense receipt uploaded.
   - **Logic**: Executes OCR on receipt image, detects total amount (€), date, provider tax ID (NIF/CIF), flags mixed diesel+AdBlue purchases, and saves to `tiquets_carburant`.
3. **`app.workers.tasks.processar_odometre_ocr_task`** (`queue_media`):
   - **Trigger**: Odometer picture uploaded during check-in or refuel.
   - **Logic**: Segments dashboard digits, extracts integer mileage, cross-checks against `vehicles.odometre_acumulat`, and triggers alert if mileage decreased.
4. **`app.workers.tasks.simplificar_geojson_task`** (`queue_default`):
   - **Trigger**: Blueprint vector layers with >10,000 vertices assigned to mobile.
   - **Logic**: Applies Douglas-Peucker algorithm with 0.5-meter tolerance, generating a lightened representation cached for mobile Dexie download.

---

## 7. Workbox Service Worker Synchronization Pipeline

1. **Service Worker Registration**: `sw.js` registers on PWA start with `skipWaiting: true` and `clientsClaim: true`.
2. **Workbox Background Sync**:
   - Intercepts failed `POST`, `PUT`, `PATCH` requests when offline (`navigator.onLine === false`).
   - Stores request payload in Dexie `sync_queue`.
   - Listens for `sync` events from the browser or the `online` window event.
3. **Sequential Push Batching**:
   - Replays queued actions against `POST /api/v1/operari_pwa/sync/push`.
   - Processes actions sequentially in FIFO order.
   - Handles network errors using exponential backoff (tenacity) to avoid duplicating records.
   - Drops committed items upon `200 OK` response.
