# Auditoria i Normativa de Tests Backend (Fase 0)

Aquest document resumeix els errors crítics detectats i solucionats durant la Fase 0 d'auditoria (Zero Mock - Backend), establint l'estàndard OBLIGATORI per a la realització de tests d'integració asíncrons amb FastAPI i SQLAlchemy.

## 1. Historial d'Errors Crítics i Solucions

### 1.1 Error de Polítiques RLS Ocult: `Could not refresh instance`
**Problema:** Els endpoints d'alta (clients, operaris, magatzem, etc.) feien `await db.refresh(objecte)` després de `await db.commit()`. Això fallava estrepitosament amb Error 500 en producció a causa del Row Level Security (RLS) de Postgres, que denega la lectura de la fila si el context del tenant no es manté o s'ha netejat en fer commit.
**Com s'amagava?** En els tests de Pytest, s'emprava una transacció que feia un *SAVEPOINT*. L'ordre `db.commit()` no tancava la transacció, per la qual cosa les variables locals (`SET LOCAL app.current_empresa_id`) es mantenien actives, fent que el `refresh()` funcionés només en testing.
**Solució:** Eliminació total de `await db.refresh(...)` de TOTS els endpoints. S'han de retornar directament els objectes ORM instanciats; FastAPI (Pydantic) utilitza els valors per defecte definits pel model si cal.

### 1.2 Col·lapse del Loop d'Esdeveniments Asíncrons (Pytest)
**Problema:** `RuntimeError: Task attached to a different loop`. Això passava perquè `pytest-asyncio` creava un event loop per test, però el motor de la base de dades (`engine`) i el seu *Connection Pool* eren instanciats a nivell de mòdul (globalment). El pool quedava lligat al loop del primer test, fent petar els tests posteriors.
**Solució:**
1. A `pytest.ini` s'ha configurat explícitament `asyncio_mode = strict`.
2. A `conftest.py`, s'ha establert un aïllament transaccional pur amb `join_transaction_mode="create_savepoint"`, recreant l'`engine` (amb `NullPool`) *dins* del fixture asíncron de la base de dades.
3. Ús exclusiu de `@pytest_asyncio.fixture` per als fixtures asíncrons.

### 1.3 Falses "Bones Pràctiques" de Mocking i Dades Compartides
**Problema:** Alguns tests fallaven per `IntegrityError` (claus duplicades, subdominis repetits) perquè assumien una base de dades neta o hardcodejaven strings idèntics per diferents suites (ex: `incpwa` o `pickpwa`).
**Solució:** Ús obligatori de generadors pseudoaleatoris coherents (ex: `"incpwa-" + str(uuid.uuid4())[:8]`) als fixtures del Pytest per garantir la unicitat de les proves.

---

## 2. Normativa Estricta de Testing (Llegir sempre al tancar una Fase)

**Com a Agent, TENS L'OBLIGACIÓ de complir les següents regles abans de donar qualsevol test per vàlid:**

1. **PROHIBICIÓ TOTAL DE MOCKS AL BACKEND:** Les crides a base de dades s'han de fer contra PostgreSQL. Prohibit fer un mock de la funció `db_session` o de l'accés a dades. S'ha d'usar `TestClient` o `httpx.AsyncClient` real passant per l'`app` de FastAPI, respectant el override de `get_db`.
2. **VERIFICACIÓ DE L'AÏLLAMENT DEL TENANT (RLS):** Cada suite de tests *ha de provar expressament* que un usuari d'un Tenant A no pot llegir, escriure, ni esborrar dades del Tenant B.
3. **RESPECTAR `create_savepoint`:** Els tests han d'executar-se envoltant el test en un SAVEPOINT, fent `rollback()` en finalitzar, deixant la base de dades impecable per al següent test. Això evita dependre de l'estat anterior i errors d'integritat.
4. **NO OCULTAR ERRORS DE FLUSH/COMMIT:** Cal recordar l'error del `db.refresh()`. Mai fer refresh de models si no estem segurs de la seguretat a nivell de fila (RLS). Si un test funciona, però l'arquitectura utilitza `refresh()`, assumir que està trencat.
5. **ZERO WARNINGS DE LOOPS ASÍNCRONS:** Qualsevol advertència de *Future exception was never retrieved* o *attached to a different loop* anul·la la validesa del test automàticament.
6. **CORRESPONDÈNCIA EXACTA AMB ELS SPECS (Check Constraints):** Verificar que els formularis del Frontend (les proves E2E de Playwright) enviïn les cadenes de text *exactes* exigides pels Enums i CHECK CONSTRAINTS del Backend (`METRES_LINEALS`, `JORNADA_CONTINUADA`, etc.).

**Quan finalitzis la implementació del codi d'una fase, HAURÀS DE LLEGIR aquest document novament abans d'executar `pytest` per confirmar mentalment que els tests compleixen aquesta normativa.**
