# Walkthrough d'Auditoria i Verificació — Superadmin: Gestió de Tenants i Onboarding Transaccional (/superadmin/tenants — Spec 021)

Aquest document certifica el desplegament, la verificació i les auditories de qualitat superades amb èxit pel mòdul **Superadmin: Gestió de Tenants i Onboarding Transaccional** (`/superadmin/tenants`) d'acord amb la **Spec 021**.

---

## 🎯 Proves i Regles de Negoci Verificades

### 1. Governança Global de Tenants (`RF-01`)
- S'ha verificat la consulta de tots els arrendataris actius mitjançant `GET /api/v1/superadmin/tenants`.
- Les dades mostren correctament la raó social, NIF, pla de subscripció (`BASIC`, `PREMIUM`, `ENTERPRISE`), estat financer (`AL_DIA`, `DEUTOR`, `SUSPES`) i el recompte d'operaris actius enfront de la quota autoritzada.
- Respecte estricte de la política **Zero Mock Data** (dades directes de PostgreSQL).

### 2. Onboarding Transaccional Multi-Tenant (`RF-02` a `RF-12`)
- Execució transaccional (ACID) comprovada mitjançant `test_onboarding_tenant_exit`:
  1. Alta d'empresa a `empreses`.
  2. Subdomini unificat generat i validat (p. ex. `vins-penedes`).
  3. Rebuig categòric de dominis reservats del sistema (`api`, `admin`, `superadmin`, `app`, `auth`) amb codi HTTP 400 Bad Request (`test_onboarding_subdomini_reservat`).
  4. Alta de l'usuari fundador "Boss" a `usuaris` amb rol `ADMINISTRACIO`.
  5. Configuració corporativa inicial a `configuracio_empresa`.
  6. Creació dels directoris sobirans a Hetzner Falkenstein (`/docs/<empresa_id>/`, `/data/<empresa_id>/`).

### 3. Cicle de Vida, Suspensió i Revocació de Sessions (`RF-13` a `RF-16`)
- Verificat mitjançant `test_canviar_estat_tenant_i_revocacio`:
  - Canvi d'estat a `SUSPES` / `DEUTOR`.
  - Neteja immediata de tokens JWT actius i sessions a Redis per a tots els usuaris de l'empresa.
  - Bloqueig transparent d'accés a l'API per a l'arrendatari suspès.

### 4. Blindatge de Downgrade de Llicències (`RF-17`, `RF-18`)
- Verificat mitjançant `test_canviar_quota_downgrade_protection`:
  - Un intent de reduir la quota de llicències a un nombre inferior al total d'operaris actius actuals és interceptat i rebutjat amb codi HTTP 422 Unprocessable Entity, especificant clarament la quantitat d'operaris que cal donar de baixa prèviament.

### 5. Commutació en Viu de Feature Flags (`RF-19`, `RF-20`)
- Endpoint `PUT /api/v1/superadmin/tenants/{id}/feature-flags` operatiu per a activar o desactivar dinàmicament `copilot_ia`, `planols_gis`, `verifactu` i `bot_telegram_clients`.

---

## 📊 Resultats de la Suite de Proves QA
- **Suite Backend Unit & Integration Tests**:
  - Fitxer: `backend/tests/test_superadmin_tenants.py`
  - 5/5 proves superades (100% OK).
- **Suite Auditoria Automatitzada PWA/API**:
  - Fitxer: `pwa/test_tenants_audit.mjs`
  - 10/10 proves superades (100% OK).
