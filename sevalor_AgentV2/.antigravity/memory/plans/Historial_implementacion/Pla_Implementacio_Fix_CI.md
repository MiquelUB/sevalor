# Resolució dels Errors de CI/CD i Refactoring de Tests (Fase Fixes Integració)

Aquesta documentació detalla els canvis fets per corregir els problemes d'integració contínua on els tests fallaven amb errors d'integritat SQL i conflictes de tipus en el front-end.

## Problemes Diagnosticats

1.  **Errors `IntegrityError` en massa a PostgreSQL (36 errors/failed):**
    S'ha detectat que 14 fitxers de tests utilitzaven instruccions `INSERT INTO empreses ...` (SQL cru) ignorant fins a 15 columnes `NOT NULL`. Aquestes columnes tenien el paràmetre `default=` definit a SQLAlchemy (Pydantic / ORM a Python) però **no disposaven d'un `server_default=` en el DDL de PostgreSQL**. Quan el codi SQL cru s'executava, la base de dades rebia `NULL` en aquests camps requerits. En fallar la inserció de la primera empresa de test, la transacció de la base de dades es marcava com a "enverinada" / "aborted", provocant una cascada d'errors en tots els tests de la mateixa suite de tests asíncrons.
2.  **Desincronització Frontend ↔ Backend (Motiu 422 Unprocessable Entity):**
    El Backend esperava la vertical `SEVALOR` però el panell d'Onboarding de l'Admin en Next.js (Frontend) seguia codificat fixat (hardcoded) enviant `"CAMPOPRO"`.
3.  **Bypass del mecanisme d'aïllament de Tests:**
    El test RLS `test_rls.py` obviava completament els _fixtures_ de test `conftest.py` i les `SAVEPOINTs`, obrint connexions brutes a la BD que no aplicaven el `rollback`, embrutant la base de dades de tests. Addicionalment, el `test_phase4_superadmin.py` s'havia quedat obsolet respecte als darrers requeriments de creació de carpetes sobiranes.

## Pla de Resolució Aplicat

### 1. Reforç dels Models (Base de Dades)
S'ha recorregut completament el fitxer `models.py` i afegit `server_default=text(...)` (o string pla) a **Totes** les columnes obligatòries (`nullable=False`) que contenien algun valor per defecte (`default=`). 
Ara, PostgreSQL sap construir les files fins i tot quan scripts manuals, ETLs o queries en SQL cru intenten fer `INSERT` sense esmentar totes les columnes obligatòries.

### 2. Refactoring a ORM de les Suites de Test
S'han analitzat 15 fitxers de tests `tests/test_*.py` que creaven Entitats Base a través d'SQL cru i substituït completament per l'ORM de SQLAlchemy.

*Canvi Representatiu:*
```python
# Abans
await admin_session.execute(text("INSERT INTO empreses (id, nom...) VALUES (...)"))

# Després
admin_session.add(Empresa(id=uuid.UUID(empresa_id), nom="..."))
await admin_session.flush()
```
L'ús del `flush()` manté la inserció dins el _savepoint_ de la transacció aïllada pel test en curs, garantint-ne el rollback automàtic un cop finalitza la prova.

### 3. Ajustament Strict del Row Level Security Test
S'ha refet el `test_rls.py` sencer. S'han canviat les signatures per dependre del framework de Pytest amb `pytest.mark.asyncio`, implementant `set_tenant_context` sobre la pròpia sessió `admin_session` proveïda pels _fixtures_, per validar que la BD respecta la capa Multi-Tenant en una mateixa connexió. 

### 4. Correcció de Formularis Frontend (CAMPOPRO -> SEVALOR)
Actualitzats els paràmetres TSX d'estat a `useState("SEVALOR")` i els arrays d'opcions en:
- `pwa/src/app/superadmin/tenants/onboarding/page.tsx`
- `pwa/src/app/gestio/copilot/page.tsx`
- `pwa/src/app/superadmin/telemetria/page.tsx`

---
*Aquesta documentació i implementació tanca la petició d'auditoria de la fase de Fixes per al CI/CD.*
