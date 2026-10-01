# Pla Tècnic d'Implementació: Infraestructura Sobirana & Governança Superadmin

**Macro-Feature**: `04-infraestructura-sobirana`  
**Estat**: Implementat & Consolidat (Sprint V2)  
**Especificació**: `sevalor_AgentV2/specs/04-infraestructura-sobirana/spec.md`  

---

## 1. Arquitectura del Sistema i Context Tècnic

El mòdul d'Infraestructura Sobirana i Superadmin assegura l'execució multi-inquilí d'alt rendiment, el compliment normatiu del RGPD/LOPDGDD i la sobirania tecnològica mitjançant infraestructura radicada a la Unió Europea (Hetzner Falkenstein / Nuremberg).

```text
                               +----------------------------------------+
                               |        Client / Browser / PWA          |
                               +----------------------------------------+
                                                   |
                                                   v
                               +----------------------------------------+
                               |     Nginx Reverse Proxy & SSL TLS      |
                               | (Let's Encrypt / Certbot / IP White)   |
                               +----------------------------------------+
                                                   |
                                                   v
                               +----------------------------------------+
                               |           Next.js 14 Frontend          |
                               |  (/superadmin, /gestio, /operari)      |
                               +----------------------------------------+
                                                   |
                                                   v
                         +----------------------------------------------------+
                         |             FastAPI Backend (Python 3.12)          |
                         |  - TenantMiddleware (JWT + X-Empresa-ID Context)   |
                         |  - Security Dependencies (Role SUPERADMIN check)   |
                         |  - Session Context: SET ROLE sevalor_app & RLS     |
                         +----------------------------------------------------+
                                    |                               |
             +----------------------+                               +---------------------+
             v                                                                            v
+-------------------------------+                                           +-------------------------------+
|    PostgreSQL 16 Engine       |                                           |     Redis 7 & Celery 5.3      |
|  - Schema public (RLS Active) |                                           |  - Broker & Token Blacklist   |
|  - Schema superadmin_telemetry|                                           |  - Asynchronous Queues        |
|  - Connection Pool (asyncpg)  |                                           |    (docs, periodic, media)    |
+-------------------------------+                                           +-------------------------------+
             |                                                                            |
             v                                                                            v
+-------------------------------+                                           +-------------------------------+
|   Local Sovereign Storage     |                                           |    Local AI Node (CPU-Only)   |
|   /data/<empresa_id>/...      |                                           |    Faster-Whisper INT8        |
|   /docs/<empresa_id>/...      |                                           |    Ollama / LM Studio         |
+-------------------------------+                                           +-------------------------------+
```

### Pila Tecnològica i Dependències Principals
- **Llenguatge & Versió**: Python 3.12 (Backend), TypeScript 5.4 / Node.js 20+ (Frontend).
- **Framework Web Backend**: FastAPI 0.110+, Starlette, Pydantic v2.
- **Accés a Base de Dades**: SQLAlchemy 2.0 (Async ORM), asyncpg 0.29+.
- **Base de Dades**: PostgreSQL 16 amb Row Level Security (RLS) mandatori sota `FORCE ROW LEVEL SECURITY`.
- **Missatgeria & Cues**: Redis 7.2 (Broker, Caching i Llista Negra de Tokens) + Celery 5.3 + Celery Beat.
- **Frontend**: Next.js 14 (App Router), Tailwind CSS, Lucide React, Disseny d'alta densitat tipus Twenty CRM.
- **Inferència d'IA Sobirana**: Node Hetzner CPX21 CPU-only (3 vCPUs, 4GB RAM), Faster-Whisper INT8, sense dependència de GPU ni sortida de dades cap a núvols forans.
- **Emmagatzematge Local**: Discs NVMe locals a `/data` i `/docs`, rebutjant taxativament AWS S3 o núvols públics.

---

## 2. Model de Dades & Esquemes de Base de Dades

L'aïllament multi-tenant i la privacitat estricta s'articulen mitjançant la coexistència de dos esquemes a PostgreSQL:

### 2.1 Esquema `public` (Dades de Negoci sota RLS)

#### Taula `empreses`
Entitat matriu de governança per a cada inquilí (Tenant):
```sql
CREATE TABLE public.empreses (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    nom VARCHAR(100) NOT NULL,
    nif VARCHAR(20) NOT NULL UNIQUE,
    adreca TEXT,
    subdomini VARCHAR(63) UNIQUE,
    primari_hsl VARCHAR(30) DEFAULT '210 100% 15%',
    secundari_hsl VARCHAR(30) DEFAULT '38 92% 50%',
    accent_hsl VARCHAR(30) DEFAULT '190 90% 50%',
    logotip_path VARCHAR(500),
    favicon_path VARCHAR(500),
    pla_subscripcio VARCHAR(20) DEFAULT 'STARTER' NOT NULL, -- STARTER (5), PRO (15), ENTERPRISE (50)
    estat_pagament VARCHAR(20) DEFAULT 'ACTIU' NOT NULL,   -- TRIAL, ACTIU, SUSPES_PAGAMENT, MANTENIMENT, BAIXA_OFFBOARDING
    quota_disc_bytes_autoritzada BIGINT DEFAULT 10737418240 NOT NULL, -- 10 GB per defecte
    quota_disc_bytes_utilitzada BIGINT DEFAULT 0 NOT NULL,
    telegram_bot_token VARCHAR(255),
    telegram_webhook_secret VARCHAR(255),
    telegram_bot_actiu BOOLEAN DEFAULT FALSE,
    telegram_estat_connexio VARCHAR(30) DEFAULT 'NO_CONFIGURAT',
    vertical VARCHAR(100) DEFAULT 'SEVALOR' NOT NULL,     -- SEVALOR, ELECTRICPRO, HYDROPRO, BUILDINGPRO o Custom
    magatzem_families_default TEXT,
    agent_prompt_system TEXT,
    feature_copilot_ia BOOLEAN DEFAULT FALSE,
    feature_flota BOOLEAN DEFAULT TRUE,
    feature_planols BOOLEAN DEFAULT FALSE,
    feature_telegram BOOLEAN DEFAULT TRUE,
    data_onboarding TIMESTAMPTZ DEFAULT now() NOT NULL,
    created_at TIMESTAMPTZ DEFAULT now() NOT NULL,
    updated_at TIMESTAMPTZ DEFAULT now() NOT NULL
);
```

#### Taula `usuaris`
Credencials, identitats i rols d'usuaris (inclòs el compte Boss inicial):
```sql
CREATE TABLE public.usuaris (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    empresa_id UUID REFERENCES public.empreses(id) ON DELETE CASCADE,
    nif VARCHAR(20) NOT NULL,
    nom VARCHAR(100) NOT NULL,
    cognoms VARCHAR(100) DEFAULT '',
    email VARCHAR(200),
    telefon VARCHAR(20),
    password_hash VARCHAR(255),
    rol VARCHAR(20) NOT NULL, -- SUPERADMIN, BOSS, GESTOR, OPERARI
    estat VARCHAR(20) DEFAULT 'ACTIU' NOT NULL,
    totp_activat BOOLEAN DEFAULT FALSE,
    secret_totp VARCHAR(64),
    created_at TIMESTAMPTZ DEFAULT now() NOT NULL,
    updated_at TIMESTAMPTZ DEFAULT now() NOT NULL,
    CONSTRAINT uq_usuaris_empresa_nif UNIQUE (empresa_id, nif)
);
```

#### Polítiques de Row Level Security (RLS)
Totes les taules operatives de l'esquema `public` (`clients`, `ordres_treball`, `articles`, `vehicles`, etc.) tenen RLS forçat:
```sql
-- Habilitació i forçat de RLS
ALTER TABLE public.clients ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.clients FORCE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS tenant_isolation_clients ON public.clients;
CREATE POLICY tenant_isolation_clients ON public.clients
    USING (empresa_id = current_setting('app.current_empresa_id')::uuid);
```
> [!IMPORTANT]
> **Norma Tècnica RLS**: El backend de FastAPI es connecta mitjançant el rol de base de dades `sevalor_app` (`SET ROLE sevalor_app;`), assegurant que cap consulta de l'API pugui ometre el filtratge RLS de PostgreSQL.

---

### 2.2 Esquema `superadmin_telemetry` (Segregació Tècnica Zero-Trust)

Per complir el mandat de no intromissió en dades privades de clients (Spec 022), totes les dades de rendiment i traces de diagnòstic es guarden en un esquema aïllat:

```sql
CREATE SCHEMA IF NOT EXISTS superadmin_telemetry;

CREATE TABLE superadmin_telemetry.traces_error (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    endpoint TEXT NOT NULL,
    metode VARCHAR(10) DEFAULT 'GET' NOT NULL,
    status_code INTEGER DEFAULT 500 NOT NULL,
    stack_trace TEXT NOT NULL,
    detall TEXT,
    creat_a TIMESTAMPTZ DEFAULT now() NOT NULL
);
```

---

## 3. Middlewares & Injecció de Context

### 3.1 `TenantMiddleware` (`backend/app/middleware/tenant.py`)
Intercepta cada petició HTTP a la plataforma per establir el context d'execució:
1. **Extracció del Token JWT**: Descodifica la capçalera `Authorization: Bearer <token>`.
2. **Identificació del Rol**: Si `rol == "SUPERADMIN"`, marca `is_superadmin = True`.
3. **Determinació del Tenant**:
   - Per a usuaris regulars: pren l'`empresa_id` del payload del JWT.
   - Per a Superadmin: permet l'ús de la capçalera `X-Empresa-ID` si cal emular el context d'un tenant.
   - Per a peticions anònimes: analitza la capçalera `Host` per deduir el subdomini tècnic (`request.state.subdomain`).
4. **Context Asíncron (`ContextVars`)**:
   - `tenant_context.set(empresa_id)`
   - `superadmin_context.set(is_superadmin)`
   - Neteja segura mitjançant blocs `try / finally` al tancament de la connexió.

### 3.2 Injecció de Sessió i Context RLS (`backend/app/core/db.py`)
La dependència `get_db()` gestiona el cicle de vida de la sessió PostgreSQL injectant les variables de sessió pertinents:
```python
async def set_tenant_context(session: AsyncSession, empresa_id: str | None, is_superadmin: bool = False) -> None:
    if is_superadmin:
        await session.execute(text("RESET ROLE;"))
        await session.execute(text("SELECT set_config('app.is_superadmin', 'true', true);"))
    else:
        # Imposa el rol d'aplicació per garantir el compliment de RLS
        await session.execute(text("SET ROLE sevalor_app;"))
        await session.execute(text("SELECT set_config('app.is_superadmin', 'false', true);"))

    if empresa_id:
        await session.execute(
            text("SELECT set_config('app.current_empresa_id', :val, true);"),
            {"val": str(empresa_id)},
        )
    else:
        await session.execute(text("SELECT set_config('app.current_empresa_id', '', true);"))
```
> [!CAUTION]
> **Prohibició de Clàusules Manuals**: Queda terminantment prohibit afegir manualment condicions `WHERE empresa_id = ...` a les consultes SQLAlchemy quan RLS està actiu. Tot l'aïllament és responsabilitat del motor PostgreSQL.

### 3.3 Seguretat de Xarxa & IP Allowlist
Les rutes `/superadmin/*` estan protegides a nivell de Nginx i middleware mitjançant validació estricta d'adreces IP corporatives autoritzades (IP Allowlist). Qualsevol petició procedent d'una IP no reconeguda rep un codi d'estat `403 Forbidden` opac abans de carregar cap recurs de la interfície.

---

## 4. Tasques Asíncrones de Fons (Celery & Workers)

Totes les operacions pesades o amb potencial d'introduir latència s'executen de forma asíncrona a través de Celery (`backend/app/workers/tasks.py`):

| Nom de la Tasca | Cua Celery | Descripció Tècnica |
| :--- | :--- | :--- |
| `crear_directoris_sobirans_task` | `queue_periodic` / `queue_documents` | Inicialitza l'arbre de carpetes físic a Hetzner (`/data/<id>/...` i `/docs/<id>/...`) en completar l'onboarding. |
| `generar_backup_pgdump` | `queue_critical` | Executa un bolcat setmanal de PostgreSQL xifrat amb gzip per tenant. |
| `generar_exportacio_aeat` | `queue_critical` | Construeix el paquet d'exportació d'albarans i factures per a compliment fiscal trimestral. |
| `processar_ocr_document_task` | `queue_media` | Anàlisi d'imatges/PDFs d'albarans o factures mitjançant OCR per implementar l'Alta Màgica. |
| `transcriure_audio_task` | `queue_media` | Transcripció local d'àudio (Whisper INT8 sota CPU Hetzner CPX21) amb temps límit de 15 segons. |
| `ping` | `queue_critical` | Monitoratge de latència de la cua Celery i connexió amb Redis. |

### Estructura de Directoris Sobirans per Tenant (Disc Local Hetzner)
```text
/data/<empresa_id>/
├── incidencies/         # Imatges de camp i incidències d'obra
├── vehicles/            # Registres d'odòmetre i tiquets de combustible
├── comptabilitat/       # Justificants de despeses menors
└── backups/             # Còpies de seguretat setmanals xifrades

/docs/<empresa_id>/
├── albarans/            # Documents i signatures digitals d'albarà
├── planols/             # Plànols en format PDF o vectorial
└── factures/            # Facturació oficial amb QR Veri*factu
```

---

## 5. Rutes API de Governança & Contractes de Serveis

### 5.1 Aprovisionament de Tenants (`/api/v1/superadmin/tenants`)

#### `GET /api/v1/superadmin/tenants`
Retorna el llistat de totes les empreses registrades amb les seves mètriques d'ús i llicència.
- **Seguretat**: Requereix rol `SUPERADMIN`.
- **Resposta (200 OK)**:
```json
[
  {
    "id": "c3b9b4f2-9588-4235-866d-1bf8db3e9e30",
    "rao_social": "Instal·lacions Segrià S.L.",
    "subdomini": "segria",
    "vertical": "ELECTRICPRO",
    "estat": "ACTIU",
    "pla": "PRO",
    "data_alta": "2026-09-24T10:00:00Z"
  }
]
```

#### `POST /api/v1/superadmin/tenants/onboarding`
Crea de manera atòmica una nova empresa, el compte gerent (Boss) i encua la creació de l'arbre sobirà.
- **Payload (`OnboardingTenantRequest`)**:
```json
{
  "rao_social": "Climatització del Pirineu S.L.",
  "nif": "B25896314",
  "subdomini": "clipirineu",
  "vertical": "SEVALOR",
  "pla_subscripcio": "PRO",
  "quota_disc_gb": 20,
  "boss_nif": "47123987X",
  "boss_nom": "Marc",
  "boss_cognoms": "Vila",
  "boss_email": "gerencia@clipirineu.cat",
  "boss_telefon": "+34612345678",
  "feature_flags": {
    "copilot_ia": true,
    "flota_avancada": true,
    "planols_tecnics": false,
    "telegram_bot": true
  }
}
```
- **Resposta (201 Created)**:
```json
{
  "status": "CREATED",
  "tenant": {
    "id": "f2a1b945-8123-4d2c-98ef-51a89c90b341",
    "rao_social": "Climatització del Pirineu S.L.",
    "subdomini": "clipirineu",
    "vertical": "SEVALOR",
    "pla_subscripcio": "PRO",
    "quota_operaris": 15,
    "enllac_activacio_2fa": "https://clipirineu.campopro.cat/activacio?token=abc123token",
    "estat_inicial": "TRIAL"
  }
}
```

#### `PUT /api/v1/superadmin/tenants/{empresa_id}/estat`
Modifica l'estat del cicle de vida (`TRIAL`, `ACTIU`, `SUSPES_PAGAMENT`, `MANTENIMENT`, `BAIXA_OFFBOARDING`). Si l'estat passa a `SUSPES_PAGAMENT`, afegeix els tokens a la llista negra de Redis.

#### `PUT /api/v1/superadmin/tenants/{empresa_id}/quota`
Actualitza el pla (`STARTER` -> 5, `PRO` -> 15, `ENTERPRISE` -> 50).
- **Validació de Downgrade**: Si el nombre d'operaris en estat `ACTIU` a la base de dades és superior al límit del nou pla, l'endpoint retorna `422 Unprocessable Entity` amb el detall de quants operaris cal donar de baixa prèviament.

#### `PUT /api/v1/superadmin/tenants/{empresa_id}/feature-flags`
Commuta de manera immediata els interruptors opcionals per tenant (`copilot_ia`, `flota`, `planols`, `telegram`).

---

### 5.2 Torre de Control de Salut & Telemetria (`/api/v1/superadmin/telemetria`)

#### `GET /api/v1/superadmin/telemetria/kpis`
Retorna els indicadors de rendiment tècnic, latències, concurrència, cues i estat dels contenidors sense exposar dades de negoci.
- **Resposta (200 OK)**:
```json
{
  "cluster": "hetzner-prod-fsn1 (Nuremberg DC14)",
  "node": "CPX21 (3 vCPU / 4GB RAM / 80GB NVMe)",
  "uptime_percent": 99.98,
  "latencies_ms": {
    "p50": 38.2,
    "p95": 142.5,
    "p99": 289.1,
    "alerta_p95_degradat": false
  },
  "http_ratio": {
    "2xx_3xx_percent": 99.4,
    "4xx_percent": 0.5,
    "5xx_percent": 0.1
  },
  "microservices": {
    "pwa": {"status": "HEALTHY", "version": "14.2.5", "type": "Next.js 14"},
    "backend": {"status": "HEALTHY", "version": "0.110.0", "type": "FastAPI"},
    "db": {"status": "HEALTHY", "version": "16.2", "type": "PostgreSQL 16"},
    "redis": {"status": "HEALTHY", "version": "7.2.4", "type": "Broker & Cache"},
    "celery_worker": {"status": "HEALTHY", "version": "5.3.6", "type": "Async Tasks"},
    "celery_beat": {"status": "HEALTHY", "version": "5.3.6", "type": "Scheduler"},
    "bot": {"status": "HEALTHY", "version": "3.4.1", "type": "Aiogram 3"}
  },
  "concurrency": {
    "active_sessions": 24,
    "operaris_camp": 18,
    "oficina_tecnica": 6,
    "db_pool_occupancy_percent": 30.0,
    "alerta_pool_saturacio": false
  },
  "celery_queues": {
    "tasks_per_minute": 184,
    "queue_wait_ms": 120,
    "failed_tasks_count": 0
  },
  "cpu_ia_telemetry": {
    "constraint": "Hetzner CPX21 CPU-Only (No GPU)",
    "whisper_avg_inference_sec": 2.4,
    "whisper_quantization": "INT8 (faster-whisper)",
    "cpu_utilization_percent": 42.0,
    "ram_utilization_mb": 1840,
    "alerta_cpu_saturacio": false,
    "privacy_guarantee": "Zero text retention - Transcripcions estrictament excloses de telemetria"
  },
  "tenants": []
}
```

#### `POST /api/v1/superadmin/telemetria/traces-error`
Ingesta traces d'error des del frontend o serveis auxiliars directament cap a la taula `superadmin_telemetry.traces_error`. Garanteix l'absència de càrregues útils (payloads) amb dades confidencials de clients.

#### `GET /api/v1/superadmin/telemetria/traces-error`
Consulta les últimes traces tècniques registrades a l'esquema segregat amb finalitats de depuració.

---

## 6. Estructura de Fitxers & Implementació

```text
sevalor_AgentV2/specs/04-infraestructura-sobirana/
├── spec.md                  # Especificació de negoci i històries d'usuari
├── plan.md                  # Pla tècnic, esquemes BD, API i middlewares (aquest fitxer)
└── research.md              # Regles d'or, solucions a errors històrics i lliçons apreses

backend/
├── app/
│   ├── api/v1/
│   │   ├── superadmin/
│   │   │   └── tenants.py   # Rutes d'onboarding, estats, quotes i flags
│   │   └── telemetria.py    # KPIs de salut, concurrència, cues i traces
│   ├── core/
│   │   ├── context.py       # ContextVars per a tenant_id i is_superadmin
│   │   ├── db.py            # AsyncSessionLocal, get_db i set_tenant_context
│   │   └── security.py      # Validació de rols (SUPERADMIN) i tokens JWT
│   ├── middleware/
│   │   └── tenant.py        # Intercepció de capçaleres, JWT i subdomini
│   ├── models/
│   │   └── models.py        # Models ORM Empresa, Usuari i relacions RLS
│   └── workers/
│       ├── celery_app.py    # Configuració de cues Celery i broker Redis
│       └── tasks.py         # Tasques asíncrones de disc sobirà, backups i IA
└── tests/
    ├── test_021_rls_tenant_injection.py  # Verificació de variables de sessió RLS
    ├── test_superadmin_tenants.py        # Tests d'onboarding, rols i transicions
    └── test_phase4_superadmin.py         # Tests de KPIs de telemetria i directoris

pwa/src/app/superadmin/
├── layout.tsx               # Shell d'alta densitat d'estil Twenty CRM
├── login/page.tsx           # Accés restringit amb 2FA TOTP mandatori
├── telemetria/page.tsx      # Torre de control tècnica, microserveis i cues
└── tenants/
    ├── page.tsx             # Llistat d'empreses, estats i accions
    └── onboarding/page.tsx  # Assistent per passos d'alta d'empreses
```
