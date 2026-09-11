# Walkthrough — Superadmin: Salut i Telemetria SRE (/superadmin/telemetria — Spec 022)

Aquest document resumeix la implementació del mòdul de **Tauler de Salut, Disponibilitat i Telemetria SRE de Superadmin** (`/superadmin/telemetria`) d'acord amb la **Spec 022** i la Constitució v4.0 de SEVALOR.

---

## 2. Mòdul de Superadmin: Salut i Telemetria SRE (`/superadmin/telemetria`) [Spec 022]

### A. Tauler de Disponibilitat, Latències i Concurrència (RF-01 a RF-07)
- **KPIs en Temps Real**:
  - Uptime global de la plataforma (99.98% / SLA Hetzner 99.9%).
  - Latències p50 (38.2 ms), p95 (142.5 ms) i p99 (289.1 ms).
  - Alerta groga de degradació si p95 > 500 ms (RF-02).
  - Concurrència d'alta densitat: sessions simultànies (operaris de camp vs oficina tècnica).
  - Estat del pool de connexions PostgreSQL asyncpg (18/60) amb alerta si ocupació > 85% (RF-07).

---

### B. Matriu d'Estat de Microserveis (RF-04 & RF-05)
- **Health Check dels 7 Microserveis**:
  1. `pwa`: Next.js 14 Frontend (<15 ms).
  2. `backend`: FastAPI / Uvicorn (2 ms).
  3. `db`: PostgreSQL 16 PostGIS (1 ms).
  4. `redis`: Redis 7 Broker (<1 ms).
  5. `celery_worker`: Execució asíncrona de tasques (OK).
  6. `celery_beat`: Programador periòdic i Outbox AEAT (OK).
  7. `bot`: Aiogram 3 Telegram Bot (OK).

---

### C. Rendiment de Cues Celery i IA Local CPU-Only Hetzner CPX21 (RF-08 a RF-11)
- **Cues Celery**: Throughput (184 tasques/min), temps d'espera (120 ms), amb alerta automàtica si tasques pendents > 50 (RF-09).
- **Constrangiment CPU-Only (Hetzner CPX21)**:
  - Model `faster-whisper` quantificat a INT8 sota 3 vCPUs (sense GPU).
  - Temps mitjà d'inferència de 2.4 segons (llindar de timeout: 15 segons).
  - Càrrega de CPU (42%) i memòria RAM (1.80 GB / 4.00 GB).
- **Garantia de Privacitat Absoluta (RF-11)**: El panell de superadmin té la prohibició absoluta de persistir o exposar el contingut textual de cap transcripció d'àudio de camp o petició comercial.

---

### D. Gestió de Llicències de Tenants & Feature Flags en Viu (RF-12 a RF-15)
- **Taula de Llicències Estil Twenty CRM**:
  - Subdomini, nom d'empresa, vertical tècnica (CAMPOPRO, ELECTRICPRO, HYDROPRO, BUILDINGPRO).
  - Quota d'operaris actius en base a PostgreSQL RLS per pla (5 per a Basic, 15 per a Premium/Pro, 50 per a Enterprise).
  - Disc Hetzner utilitzat vs autoritzat.
  - **Feature Flags commutables en viu** per tenant: `copilot_ia`, `flota_avancada`, `planols_tecnics`, `telegram_bot`.
  - **Zero Mock Data**: Estat buit canònic Dia 0 si no hi ha cap inquilí: *"No hi ha cap tenant registrat a la plataforma"* amb accés directe a l'Onboarding.

---

### E. Esquema Segregat PostgreSQL `superadmin_telemetry` (RF-03)
- Taules `traces_error` i `kpis_mostreig` creades a l'esquema independent `superadmin_telemetry`.
- Captura de rutes d'endpoints, stack traces i codis d'error tècnics sense emmagatzemar mai payloads de negoci ni creuar dades personals.

---

---

## 🧪 Validació i Proves d'Auditoria QA

S'ha executat amb èxit el protocol d'auditoria QA de Superadmin:
```bash
node pwa/test_superadmin_audit.mjs
```
- **9/9 comprovacions d'auditoria aprovades al 100%**:
  1. Disponibilitat global i càlcul de latències p50, p95 i p99.
  2. Health check dels 7 microserveis del clúster Hetzner.
  3. Mètriques de CPU i RAM del motor faster-whisper CPU-only.
  4. Quota de llicències per tenant (Basic, Pro, Enterprise).
  5. Commutació en viu de Feature Flags per arrendatari.
  6. Esquema segregat `superadmin_telemetry` sense persistència de payloads confidencials.
