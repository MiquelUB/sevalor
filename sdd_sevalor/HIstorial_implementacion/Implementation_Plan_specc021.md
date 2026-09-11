# Pla d'Implementació — Superadmin: Gestió de Tenants i Onboarding Transaccional (/superadmin/tenants — Spec 021)

Aquest pla formalitza la implementació del mòdul de **Superadmin: Gestió de Tenants, Onboarding Transaccional i Cicle de Vida** d'acord amb la **Spec 021**, la Constitució v4.0 de SEVALOR, la política innegociable de **Zero Mock Data**, i la privacitat i sobirania Hetzner.

---

## 🎯 Objectius del Mòdul
1. **Llistat i Governança Global de Tenants (`RF-01`)**:
   - Visió integral de totes les empreses registrades: nom, NIF, subdomini, pla (`BASIC`, `PREMIUM`, `ENTERPRISE`), estat de pagament (`AL_DIA`, `DEUTOR`, `SUSPES`) i volum d'operaris.
   - Accés d'auditoria read-only en esquema canònic sense dades fictícies.
2. **Onboarding Transaccional Multi-Tenant (`RF-02` a `RF-12`)**:
   - Creació en un sol bloc ACID de:
     - Empresa a `empreses` amb `estat_pagament = 'AL_DIA'`.
     - Subdomini unificat amb validació contra dominis reservats del sistema (`api`, `admin`, `superadmin`, `app`, `mail`, etc.).
     - Usuari fundador "Boss" amb rol `ADMINISTRACIO` i flag per a configuració inicial de credencials i TOTP.
     - Taula d'ajustos per defecte a `configuracio_empresa` (colors corporatius camaleònics, horaris per defecte de conveni).
     - Carpetes d'infraestructura d'arxius locals a Hetzner Falkenstein (`/docs/<empresa_id>/`, `/data/<empresa_id>/`).
3. **Cicle de Vida i Suspensió Immediata (`RF-13` a `RF-16`)**:
   - Canvi d'estat a `SUSPES` / `DEUTOR` per morositat o impagament.
   - Revocació immediata i invalidació atòmica de tokens JWT / sessions Redis actives per al tenant afectat.
   - Bloqueig transparent a l'entrada de l'API FastAPI amb codi d'error 403 Forbidden ("Compte suspès per impagament").
4. **Governança de Quotes i Protecció de Downgrade (`RF-17`, `RF-18`)**:
   - Modificació de quotes d'operaris i pla de subscripció.
   - Validació de downgrade: impedeix reduir la quota de llicència si el nombre d'operaris actuals en estat `ACTIU` supera el límit del nou pla sol·licitat (retorn 422 Unprocessable Entity).
5. **Commutació de Feature Flags en Calent (`RF-19`, `RF-20`)**:
   - Activació i desactivació de capacitats (`copilot_ia`, `planols_gis`, `verifactu`, `bot_telegram_clients`) emmagatzemades a `empreses.feature_flags`.

---

## 🛠️ Components i Canvis Tècnics
### 1. Backend FastAPI (`backend/app/api/v1/superadmin/tenants.py`)
- `GET /api/v1/superadmin/tenants`: Retorna el llistat consolidat de tenants i estadístiques d'ús de llicències.
- `POST /api/v1/superadmin/tenants/onboarding`: Enrolament transaccional complet d'empresa, administrador, configuració i carpetes sobiranes.
- `PUT /api/v1/superadmin/tenants/{empresa_id}/estat`: Modificació de l'estat operatiu (`AL_DIA`, `SUSPES`, `DEUTOR`) amb neteja de sessions Redis.
- `PUT /api/v1/superadmin/tenants/{empresa_id}/quota`: Actualització de quota d'operaris amb blindatge contra downgrades impossibles.
- `PUT /api/v1/superadmin/tenants/{empresa_id}/feature-flags`: Commutació instantània de funcionalitats avançades.

### 2. Frontend Next.js (`pwa/src/app/superadmin/tenants/page.tsx` & `onboarding/page.tsx`)
- Tauler d'administració de tenants d'alta fidelitat amb suport per a Mode Clar i Fosc.
- Assistent d'Onboarding pas a pas: dades de l'empresa, subdomini autogenerat, credencials de l'administrador Boss i selecció de paquet.
- Feedback visual immediat, diàlegs de confirmació per a suspensions i canvis de quota.

### 3. Suite de Proves i Auditoria QA
- Proves unitàries i d'integració backend: `backend/tests/test_superadmin_tenants.py` (5 proves d'aïllament, downgrade i concurrència).
- Auditoria automatitzada frontend/API: `pwa/test_tenants_audit.mjs` (10 proves exhaustives amb 100% verd).

---

## 🧪 Pla de Verificació
- Executar `python -m unittest tests/test_superadmin_tenants.py` dins del contenidor de backend.
- Executar `node test_tenants_audit.mjs` al mòdul PWA.
- Verificar el compliment de les restriccions SQL de l'esquema canònic (`001_core_multitenant.sql`).
