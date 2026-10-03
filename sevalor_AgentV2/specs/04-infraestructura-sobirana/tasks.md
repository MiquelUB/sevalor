# Tasks: Infraestructura Sobirana & Governança Superadmin (Spec 04)

**Feature Path**: `specs/04-infraestructura-sobirana`  
**Prerequisites**: `spec.md`, `plan.md`, `constitution.md`  
**Norma Suprema**: Zero Mock Data, Segregació Zero-Trust, Sobirania Europea Hetzner, aprovació 100% neta de tests.

---

## Phase 1: Setup & Seguretat Superadmin (Zero-Trust & IP Allowlist)

- [x] T001 Implementar verificació d'IP Allowlist a la base de dades i 2FA TOTP obligatori per a usuaris Superadmin a `backend/app/core/security.py`.
- [x] T002 Implementar sessions d'impersonació estrictes (màxim 2 hores, auditades, mode només lectura sobre dades bancàries).
- [x] T003 Tests de seguretat d'accés a la consola Superadmin a `backend/tests/test_superadmin_auth.py`.

---

## Phase 2: User Story 1 - Assistent d'Onboarding amb Marca Camaleònica (Priority: P1)

- [x] T004 [US1] Endpoints d'onboarding de noves empreses amb validació de NIF algorítmica i disponibilitat de subdomini a `backend/app/api/v1/superadmin/tenants.py`.
- [x] T005 [US1] Injecció de paleta cromàtica camaleònica (Primary, Secondary, Accent) en tokens CSS HSL per a PWA, Dashboard i PDFs.
- [x] T006 [US1] Emissió d'enllaç segur d'activació (24h) per al compte arrel de gerència.
- [x] T007 [US1] Tests d'onboarding i marca camaleònica a `backend/tests/test_superadmin_tenants.py`.

---

## Phase 3: User Story 2 - Segregació Zero-Trust (Priority: P1)

- [x] T008 [US2] Bloqueig estructural a l'API i models per impedir que Superadmin pugui visualitzar dades operatives privades (feines, factures, fotos o xats).
- [x] T009 [US2] Tests d'intent d'accés no autoritzat de Superadmin a dades de negoci comprovant rebuig 403 / 0 rows a `backend/tests/test_superadmin_zero_trust.py`.

---

## Phase 4: User Story 3 & 4 - Torre de Control de Salut & Quota Guard (Priority: P2)

- [x] T010 [US3] Telemetria en temps real: disponibilitat global, latències percentils (p95), volum de sessions i salut dels serveis.
- [x] T011 [US4] Governança de llicències (Trial 14d, Actiu, Suspès) i protecció Quota Guard que bloqueja downgrades amb excés d'operaris actius.
- [x] T012 [US3/US4] Tests de mètriques i transicions d'estat de quota a `backend/tests/test_superadmin_kpis.py`.

---

## Phase 5: User Story 5 - Baixa Certificada i Certificat de Destrucció (Priority: P2)

- [x] T013 [US5] Flux de baixa: període de custòdia de 30 dies, descàrrega d'actius i purga irreversible de dades.
- [x] T014 [US5] Emissió del Certificat de Destrucció de Dades amb segell criptogràfic custodiat durant 5 anys.
- [x] T015 [US5] Tests del cicle de baixa i destrucció a `backend/tests/test_superadmin_destruccio.py`.

---

## Phase 6: Verificació Integral Neta

- [x] T016 Execució de tota la suite de proves de Superadmin i Infraestructura: `pytest backend/tests/ -k "superadmin" -v`.
- [x] T017 Verificació de tipus i linter: `mypy app/api/v1/superadmin/ --strict` i `ruff check backend/app/api/v1/superadmin/`.
