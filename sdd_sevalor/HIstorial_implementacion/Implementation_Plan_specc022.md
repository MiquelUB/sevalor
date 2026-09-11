# Pla d'Implementació — Superadmin: Tauler de Salut i Telemetria SRE (/superadmin/telemetria — Spec 022)

Aquest pla defineix la implementació del mòdul de **Superadmin Telemetria i Salut de la Plataforma** (`/superadmin/telemetria`) d'acord amb la **Spec 022**, la Constitució v4.0 de SEVALOR, la política de **Zero Mock Data**, i la privacitat innegociable de dades Hetzner.

---

## 🎯 Objectius del Mòdul
1. **Telemetria en Temps Real**: Monitorització d'uptime (SLA 99.9%), latències p50, p95 i p99 de peticions HTTP i concurrència activa.
2. **Matriu de Salut dels 7 Microserveis**: Probes d'estat de Next.js, FastAPI, PostgreSQL PostGIS, Redis Broker, Celery Worker, Celery Beat i Telegram Bot.
3. **Control d'Inferència Local Hetzner CPX21**: Mètriques de CPU/RAM del servei faster-whisper CPU-only, cues Celery i temps d'espera.
4. **Governança de Tenants i Llicències**: Quotes d'operaris per pla, espai de disc Hetzner consumit i commutador en viu de Feature Flags.
5. **Esquema Segregat PostgreSQL**: Disseny de l'esquema `superadmin_telemetry` amb taules `traces_error` i `kpis_mostreig` desvinculades de dades de negoci dels arrendataris.

---

## 🛠️ Canvis Tècnics Proposats
### 1. Base de Dades PostgreSQL (`superadmin_telemetry`)
- Creació de taules d'auditoria tècnica sense registre de dades personals.
### 2. Backend FastAPI (`backend/app/api/v1/superadmin/telemetria.py`)
- Endpoints de resum de telemetria, llicències i estat dels contenidors Docker.
### 3. Frontend Next.js (`pwa/src/app/superadmin/telemetria/page.tsx`)
- Tauler d'alta densitat d'enginyeria SRE amb actualització periòdica reactiva.
### 4. Protocol de Proves QA (`pwa/test_superadmin_audit.mjs`)
- Validació de totes les regles de negoci i mètriques.

---

## 🧪 Pla de Verificació
- Execució de l'auditoria automatitzada: `node pwa/test_superadmin_audit.mjs`.
- Verificació del contracte d'aïllament i no exposició de payloads de negoci.
