# Pla d'Arquitectura, Base de Dades, Seguretat i Execució — Spec 007 v5.0

## 1. Arquitectura General (Adaptada a SEVALOR Async)
- **Models**: `backend/app/models/models.py` (extensió d'entitats existents `Usuari`, `RegistreJornadaLaboral`, `Client`, `Article`, `Vehicle`, `FacturaProveidor`, `OrdreTreball`, `FacturaCapcalera`, `FacturaLinia` i noves entitats `ContracteMantenimentMRR`, `SerieFiscalVerifactu`, `RetencioGarantia`, `TiquetDespesa`, `DespesaFixaRecurrent`, `ApuntBancariNorma43`, més trigger append-only `trg_sif_immutable` sobre `registres_esdeveniments_sif`).
- **Migració Alembic**: `backend/alembic/versions/a017_spec007_economic_suite.py` (head `a016_empresa_vault_token` -> `a017_spec007_economic_suite`) amb `ENABLE` + `FORCE ROW LEVEL SECURITY` en totes les noves taules multi-tenant i polítiques RLS basades en `current_setting('app.current_empresa_id', true)`.
- **Esquemes Pydantic**: `backend/app/schemas/comptabilitat.py` (DTOs estrictes Zero-Mock + DTOs sanititzats C-05 per a Enginyeria/Secretaria sense xifres econòmiques globals).
- **Servei de Domini**: `backend/app/services/economic_suite_service.py` (`EconomicSuiteService` amb `AsyncSession` / `asyncpg`).
- **Routers FastAPI**:
  - `backend/app/api/v1/gestio/comptabilitat.py` (`/api/v1/gestio/comptabilitat/*`, accés protegit per `require_financial_access` / `BOSS` segons endpoint).
  - `backend/app/api/v1/gestio/operativa_financera.py` (`/api/v1/gestio/operativa-financera/*`, accés C-05 sanititzat per a `ENGINYER` i `BOSS`).
- **Workers Celery**: `backend/app/workers/comptabilitat_tasks.py` (`executar_auditoria_diaria_financera_tenant` i tasca beat diària per tots els tenants).
- **Frontend PWA**:
  - `pwa/src/components/comptabilitat/EconomicCharts.tsx` (5 gràfics interactius SVG natius amb tokens HSL Chameleon UI).
  - `pwa/src/app/gestio/comptabilitat/page.tsx` (Dashboard econòmic 6 pestanyes amb Zero-Mock Empty States).

## 2. Regles de Seguretat i Compliment
- **C-01 / RLS**: Totes les consultes s'executen dins `get_db_with_tenant_context` amb `SET LOCAL app.current_empresa_id`.
- **C-05**: Separació estricta entre dades econòmiques globals (`BOSS` / `FINANCES`) i dades operatives sanititzades (`ENGINYER`).
- **EDGE-03**: Màscara `***` per a `es_alta_direccio=True` i divisió segura per zero en `hores_productives_mes`.
- **EDGE-07**: Les retencions de garantia `4308` no bloquegen el risc creditici del client.
- **EDGE-10**: Trigger PostgreSQL `BEFORE UPDATE OR DELETE` sobre `registres_esdeveniments_sif` impedeix qualsevol alteració o esborrat.
- **EDGE-11**: Finestra Art. 80 LIVA (`180` a `270` dies des del venciment) per emissió de rectificativa sèrie `R`.
