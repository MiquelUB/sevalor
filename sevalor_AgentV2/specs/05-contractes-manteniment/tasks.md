# Tasks: Contractes de Manteniment Recurrent (Spec 05)

**Feature Path**: `specs/05-contractes-manteniment`  
**Prerequisites**: `spec.md`, `plan.md`, `constitution.md`  
**Norma Suprema**: Zero Mock Data, Automatització Preventiva, Càlcul Real de MRR, aprovació 100% neta de tests.

---

## Phase 1: Setup & Modelat de Base de Dades (SQLAlchemy & RLS)

- [ ] T001 Crear models SQLAlchemy `ContracteManteniment`, `ContractesMantenimentFinques` i `RevisionsContracte` a `backend/app/models/contractes.py`.
- [ ] T002 Aplicar migració d'Alembic amb polítiques RLS (`SET LOCAL app.current_empresa_id`) per a les noves taules de contractes.
- [ ] T003 Tests de persistència i aïllament multi-tenant RLS per a contractes a `backend/tests/test_contractes_rls.py`.

---

## Phase 2: User Story 1 & 2 - Alta de Contractes i Generació d'OTs Preventives (Priority: P1)

- [ ] T004 [US1] Endpoints de creació, llistat i detall de contractes de manteniment a `backend/app/api/v1/gestio/contractes.py`.
- [ ] T005 [US2] Servei de generació automàtica d'Ordres de Treball preventives segons la periodicitat (mensual, trimestral, anual) a `backend/app/services/contractes_service.py`.
- [ ] T006 [US2] Tasca programada a Celery Beat (`backend/app/workers/tasks.py`) per revisar i disparar revisions imminents al calendari d'obres.
- [ ] T007 [US1/US2] Tests de creació de contracte i generació d'OTs preventives a `backend/tests/api/test_005_contractes_manteniment.py`.

---

## Phase 3: User Story 3 & 4 - Alertes de Venciment i Renovació/Baixa (Priority: P2)

- [ ] T008 [US3] Motor d'alertes de revisions preventives imminents (15d, 5d, 1d) i vençudes al dashboard tècnic.
- [ ] T009 [US4] Endpoint de renovació tàcita (amb actualització de tarifes) i registre de baixa amb motiu auditat.
- [ ] T010 [US3/US4] Tests del cicle d'alertes i renovacions a `backend/tests/api/test_contractes_cicle.py`.

---

## Phase 4: User Story 5 - Mètriques MRR i Facturació Recurrent (Priority: P2)

- [ ] T011 [US5] Algoritme de càlcul de MRR (Monthly Recurring Revenue) integrat al panell financer del Boss (`backend/app/services/economics_service.py`).
- [ ] T012 [US5] Generació d'esborranys de pre-factura periòdica (HITL) lligats al contracte de manteniment abans de la factura Veri*factu.
- [ ] T013 [US5] Tests del càlcul de MRR i facturació periòdica a `backend/tests/api/test_contractes_economics.py`.

---

## Phase 5: Verificació Integral Neta

- [ ] T014 Execució de tota la suite de proves de contractes de manteniment: `pytest backend/tests/ -k "contractes" -v`.
- [ ] T015 Verificació de tipus i linter: `mypy app/api/v1/gestio/contractes.py --strict` i `ruff check backend/app/api/v1/gestio/contractes.py`.
