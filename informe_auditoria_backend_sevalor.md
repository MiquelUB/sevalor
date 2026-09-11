# Informe d'Auditoria del Backend SEVALOR — FastAPI vs. Especificacions i Constitució

**Data:** 8 de setembre de 2026  
**Projecte:** SEVALOR / CampoPro Suite — Backend FastAPI  
**Repositori:** `/media/akaun/Project_1/SEVALOR/backend`  
**Especificacions revisades:** `sdd_sevalor/specs` (001, 002, 003, 004, 007, 008, 011, 012, 013, 014, 015, 016, 017, 018, 019, 021, 022, 024), `sdd_sevalor/constitution.md`, `sdd_sevalor/Auditoria_i_Normativa_Tests_Backend.md`, `sdd_sevalor/AGENTS.md`.

---

## 1. Resum executiu

El backend actual implementa un esquelet funcional de CRUD multi-tenant sobre **FastAPI + SQLAlchemy 2.0 + asyncpg** amb **Row Level Security (RLS)** a PostgreSQL, però presenta **fallades crítiques d'arquitectura i de seguretat** que el fan inviable per a producció tal com està. Els problemes més greus són:

- **Absència quasi total de control de rols (RBAC)** als endpoints de `/gestio`: qualsevol usuari amb un JWT vàlid (inclòs un operari de camp) pot crear clients, ordres de treball, articles, vehicles i **factures**.
- **Duplicació de columnes i errors del model ORM** que impedeixen l'arrencada correcta de l'aplicació.
- **Imports inexistents al mòdul Celery** per a Veri*factu, backup i OCR, deixant les funcionalitats requerides per la Constitució i l'especifiació sense implementar.
- **Routers PWA incomplets i insegurs**: picking, jornada i incidències manquen de validacions d'ownership, dupliquen la lògica JWT i permeten manipulació de dades alienes.
- **Onboarding de tenants incomplet**: no hi ha Celery, 2FA obligatori, inicialització de contrasenya del Boss ni validació d'IP.

La suite de tests passa en un **96% (25/26)**, però l'única prova fallida demostra un endpoint totalment absent, i alguns tests clau (especialment de seguretat de middleware i rols) són meres placeholders.

---

## 2. Objectiu i abast

L'auditoria compara l'implementació actual del backend amb els requisits de la Constitució v3.1, les especificacions funcionals (especialment 007, 008, 012, 021, 022, 024) i la normativa interna de tests de Fase 0. No s'ha modificat codi de producció; només s'han executat eines d'anàlisi i tests amb una nova còpia del venv de desenvolupament.

---

## 3. Metodologia

- Lectura del codi font del backend a `backend/app/`.
- Lectura de les migracions SQL a `db/migrations/`.
- Comparativa manual amb els `specs/` i `constitution.md`.
- Execució de:
  - `pytest tests/ -v` — resultat: 25 passades, 1 fallida.
  - `mypy app/` — resultat: 11 errors.
  - `ruff check app/ tests/` — resultat: 269 problemes (imports, espais en blanc).

---

## 4. Avaluació global

| Àmbit | Estat | Comentari |
|---|---|---|
| Arquitectura FastAPI / SQLAlchemy 2.0 | 🟡 Parcial | Estructura de routers correcta, però manca cohesió. |
| Multi-tenancy RLS (PostgreSQL) | 🟢 Majoritàriament correcte | `app.current_empresa_id` configurat; RLS `FORCE` present a les migracions. |
| RBAC / Zero-Trust | 🔴 Crític | Cap endpoint de `/gestio` restringeix per rol. |
| Veri*factu / Facturació | 🔴 Crític | Només hash SHA-256 bàsic; falta PDF, QR, AEAT, workers. |
| PWA Operari | 🔴 Crític | Routers incomplets, sense ownership ni separació de responsabilitats. |
| Onboarding / Superadmin | 🟠 Alt | Esquelet de tenants sense 2FA, Celery, ni emails. |
| Workers Celery | 🟠 Alt | `tasks.py` importa serveis inexistents. |
| Model ORM | 🔴 Crític | Columnes duplicades i errors de mapatge. |
| Tests / QA | 🟡 Parcial | Alta taxa de passades però cobertura de seguretat insuficient. |

---

## 5. Hallazgos per severitat

### 5.1 CRÍTICS

#### CR-01 — Control de rols absent a `/gestio`
- **Ubicació:** `backend/app/api/v1/gestio/*.py` (clients, proveidors, magatzem, feines, flota, planols, notificacions, operaris, comptabilitat).
- **Descripció:** Els endpoints només comproven `request.state.empresa_id`. No utilitzen `require_roles`, `require_financial_access` ni cap altre guardiola de rol. Un usuari amb rol `OPERARI` pot invocar `POST /gestio/comptabilitat/factures` o `POST /gestio/clients`.
- **Impacte:** Violació directa de la Constitució (principi Zero-Trust), Spec 003 (Enginyer no pot veure dades bancàries / IBAN / mètriques comptables) i Spec 007 (facturació reservada a Boss/Secretaria). Risc d'emissió de factures il·legals i manipulació de dades sensibles.
- **Recomanació:** Aplicar dependències de rol centralitzades a cada router: `require_roles(["BOSS", "SECRETARIA", "ENGINYER"])` segons la funció; utilitzar `require_financial_access` per a `/gestio/comptabilitat`.

#### CR-02 — `/gestio/comptabilitat` permet crear factures sense privilegis financers
- **Ubicació:** `backend/app/api/v1/gestio/comptabilitat.py`.
- **Descripció:** L'endpoint `POST /gestio/comptabilitat/factures` no restringeix per rol. A més, el hash SHA-256 no inclou el `client_id`, `tipus_iva` ni cap element inalterable exigit pel RD 1007/2023; s'ordena per `created_at` per obtenir el registre anterior en lloc d'usar sèrie + número estrictament consecutiu.
- **Impacte:** No es compleix Veri*factu; possible encadenament corrupte o duplicat; qualsevol rol pot emetre factures legals.
- **Recomanació:** Protegir amb `require_financial_access`; calcular el hash sobre tots els camps immutables (incloent-hi sèrie, número, NIFs, base, IVA, data, hash anterior); assegurar sèrie/número consecutiu amb restricció única i bloqueig en transacció.

#### CR-03 — Duplicació de columnes al model ORM
- **Ubicació:** `backend/app/models/models.py`, classe `Empresa` (línies 51–52 i 58–59) i classe `ConsultaXatCopilot` (línies 754–760).
- **Descripció:** `Empresa` defineix dues vegades `node_ia_url` i `node_ia_actiu`. `ConsultaXatCopilot` copia atributs del tenant (`feature_copilot_ia`, `feature_flota`, etc.) que no pertanyen a una consulta de xat.
- **Impacte:** SQLAlchemy pot fallar en temps d'elaboració del mapa o generarduesiguacions; `mypy` reporta `[no-redef]`. Afegeix inconsistència entre model i migracions.
- **Recomanació:** Eliminar els atributs duplicats de `Empresa`; retornar `ConsultaXatCopilot` a la semàntica real (pregunta, resposta, temps d'inferència, enllaços, vertical).

#### CR-04 — Workers Celery importen serveis inexistents
- **Ubicació:** `backend/app/workers/tasks.py`, línies 12–15.
- **Descripció:** Importa `app.services.verifactu`, `app.services.backup`, `app.services.outbox_aeat` i `app.services.whisper_service`, però cap d'aquests paquets existeix al repositori.
- **Impacte:** Tota la facturació Veri*factu, backups setmanals, transcripció d'àudio i enviaments AEAT estan sense implementar; les cues fallaran immediatament. Incompliment de la Constitució i Spec 024.
- **Recomanació:** Crear els mòduls `app/services/verifactu.py`, `backup.py`, `outbox_aeat.py`, `whisper_service.py` o eliminar els imports fins que existeixin i cobrir-ho amb tests d'integració.

#### CR-05 — Router PWA de picking incomplet; prova de test en vermell
- **Ubicació:** `backend/app/api/v1/operari_pwa/picking.py`.
- **Descripció:** Només existeix el `PUT /operari/picking/linies/{linia_id}`. Falten els endpoints per crear una fulla de picking (`POST /operari/picking`), afegir línies (`POST /operari/picking/{id}/linies`) i reportar devolucions/mermes. Tampoc valida que la línia pertanyi a l'operari o a la seva empresa.
- **Impacte:** El `test_crear_picking` falla (`404 != 201`). La PWA no pot realitzar picking ni conciliació de material.
- **Recomanació:** Implementar els endpoints de picking complets amb verificació d'ownership i actualització d'estoc (`EstocMagatzem` / `FullaPicking` / `LiniaPicking`).

---

### 5.2 ALTS

#### ALT-01 — Duplicació de la lògica JWT als routers PWA
- **Ubicació:** `backend/app/api/v1/operari_pwa/jornada.py`, `incidencies.py`, `feines.py`; `backend/app/api/v1/operari_auth.py`.
- **Descripció:** Cada router decodifica el Bearer token inline en lloc d'utilitzar la dependència centralitzada `get_current_user_claims` de `app.core.security`. L'`operari_auth.py` duplica la generació JWT.
- **Impacte:** Codi difícil de mantenir, inconsistències en gestió de `exp`, errors silenciats i omissions de claims.
- **Recomanació:** Crear una dependència `get_current_operari` reutilitzable que extregui `sub`, `rol` i `empresa_id` i rebutgi tokens absents o malformats amb `401`.

#### ALT-02 — `/operari/jornada/{id}/fi` permet tancar qualsevol jornada
- **Ubicació:** `backend/app/api/v1/operari_pwa/jornada.py`, línies 95–126.
- **Descripció:** L'endpoint `POST /{jornada_id}/fi` rep el `jornada_id` per paràmetre i només filtra per `empresa_id`. No comprova que la jornada pertanyi a l'usuari autenticat. Rep un body de tipus `JornadaInici` per a la geolocalització de fi, que és confús.
- **Impacte:** Un operari pot tancar la jornada d'un altre. També s'omet el càlcul d'hores, el tancament automàtic de 8 hores i el registre d'auditoria.
- **Recomanació:** Afegir `usuari_id == token_sub` a la consulta; utilitzar un esquema diferent per a la fi (`JornadaFi`); implementar càlcul d'hores i auto-tancament.

#### ALT-03 — Onboarding de tenants sense flux real de Bootstrapping
- **Ubicació:** `backend/app/api/v1/superadmin/tenants.py`.
- **Descripció:** L'endpoint `POST /superadmin/tenants/onboarding` crea l'empresa i un usuari BOSS, però no assigna contrasenya, no genera ni persisteix token d'activació, no força 2FA TOTP, no crea els directoris sobirans, no configura Nginx/Certbot i no envia res a Celery.
- **Impacte:** Incompliment de Spec 021. El Boss no pot activar el tenant de forma segura.
- **Recomanació:** Desenvolupar el flux complet: token d'activació d'un sol ús a `tokens_invitacio`, endpoint d'activació, setup de 2FA, creació de directoris via Celery, enviament d'email xifrat.

#### ALT-04 — Superadmin sense autenticació addicional (IP allowlist / 2FA)
- **Ubicació:** `backend/app/middleware/tenant.py`, `backend/app/core/security.py`.
- **Descripció:** La middleware actual desa `is_superadmin` del JWT i permet passar `X-Empresa-ID`, però no verifica cap cua de sessió a Redis, cap IP allowlist de la base de dades ni cap 2FA.
- **Impacte:** Un token SUPERADMIN robat permet accedir a dades de qualsevol tenant.
- **Recomanació:** Implementar middleware d'IP allowlist, 2FA TOTP obligatori per a SUPERADMIN, i llista negra de tokens a Redis.

#### ALT-05 — Tests de seguretat incomplets
- **Ubicació:** `backend/tests/test_rls_middleware.py`.
- **Descripció:** El test de middleware acaba amb `pass` i no conté cap assert. No es comprova que un token d'un tenant A no pugui accedir a dades del tenant B a través de capçaleres falsificades, ni que un rol d'Enginyer rebi `403` a comptabilitat.
- **Impacte:** Falsos positius de seguretat. La cobertura de tests no detecta les vulnerabilitats CR-01 ni CR-02.
- **Recomanació:** Completar `test_rls_middleware.py` amb crides reals a endpoints protegits i afegir tests de rols per a cada mòdul.

---

### 5.3 MITJANS

#### MED-01 — `run_tests.py` i configuració de pytest conflictiva
- **Ubicació:** `backend/run_tests.py`, `backend/pytest.ini`, `backend/pyproject.toml`.
- **Descripció:** `run_tests.py` utilitza `unittest` per descobrir tests de pytest, cosa que no és fiable. `pytest.ini` activa `asyncio_mode = strict` però no defineix `testpaths`, i ignora la secció `pyproject.toml` amb `asyncio_mode = auto` i `testpaths = ["tests"]`.
- **Impacte:** Execució confusa; `test_rls.py` de l'arrel es recull accidentalment i falla per manca de plugin.
- **Recomanació:** Eliminar `run_tests.py` o convertir-lo en un wrapper de `pytest`; unificar la configuració a `pyproject.toml` i afegir `testpaths = ["tests"]`.

#### MED-02 — Qualitat de codi: imports i espais en blanc
- **Ubicació:** Tot el backend i tests.
- **Descripció:** `ruff` reporta 269 problemes (importacions desordenades, línies en blanc amb espais, imports no utilitzats).
- **Impacte:** Deute tècnic i dificultat de lectura.
- **Recomanació:** Executar `ruff check . --fix` i `ruff format .`.

#### MED-03 — Models avançats sense endpoints corresponents
- **Ubicació:** Models `Finca`, `EinaCustodia`, `SlotJornada`, `Magatzem`, `EstocMagatzem`, `TiquetCarburant`, `DocumentCAERC`, `FacturaProveidor`, etc.
- **Descripció:** Les migracions defineixen taules complexes (magatzem multi-nivell, estoc virtual, picking, fulles, eines de custòdia, factures de proveïdor, RMA...), però els routers només exposen CRUD bàsics d'articles, clients, vehicles i ordres de treball.
- **Impacte:** Grans funcionalitats de Spec 004 (magatzem), Spec 006 (flota), Spec 003 (proveïdors / RMA / CAE) i Spec 008 (operaris 360°) resten sense implementar.
- **Recomanació:** Desenvolupar els endpoints restants de forma esglaonada, lligada a casa Spec.

#### MED-04 — Configuració però sense features
- **Ubicació:** `backend/app/core/config.py`.
- **Descripció:** Existeixen variables per a Redis, CORS, tokens, Whisper, però no hi ha:
  - llista negra de JWT a Redis,
  - rate limiting `slowapi`,
  - validació d'arxius per magic bytes.
- **Impacte:** Menor robustesa contra atacs de força bruta i pujades de fitxers maliciosos.
- **Recomanació:** Afegir `Limiter` de slowapi, middleware de validació d'IP allowlist i validadors de fitxers.

---

### 5.4 BAIXOS

#### LOW-01 — Health check exposa versió
- **Ubicació:** `backend/app/api/v1/health.py`.
- **Descripció:** L'endpoint públic retorna `version`. No és greu però augmenta la superfície d'informació.
- **Recomanació:** Limitar la versió a usuaris autentitzats o superadmin.

#### LOW-02 — CORS massa permisiu per defecte
- **Ubicació:** `backend/app/core/config.py`.
- **Descripció:** `BACKEND_CORS_ORIGINS` inclou diversos orígens localhost i `*` a nivell d'`allow_methods`. La Constitució requereix restringir als dominis configurats per cada empresa.
- **Recomanació:** Fer que els orígens es carreguin dinàmicament des de `empreses.domini_custom` i restringir mètodes.

---

## 6. Conformitat amb especificacions principals

| Spec | Nivell de conformitat | Observacions clau |
|---|---|---|
| **001/005 — Dashboard / Torre de Control** | 🟡 Crud bàsic de clients, feines, flota | Falten mapes, geovalla, KPIs, conciliació offline. |
| **002/003 — Clients / Proveïdors** | 🟡 Alta i llistat simple | Sense IBAN xifrat, finques, polices RC, RMA, OCR. |
| **004 — Magatzem** | 🔴 Molt baixa | Només articles; falta estoc, picking, FEFO, retalls, traspàs offline. |
| **007 — Comptabilitat / Veri*factu** | 🔴 Crítica | Hash bàsic; sense PDF, QR, AEAT, workers, rol financer. |
| **008 — Operaris** | 🟠 Parcial | Alta d'operari, PIN i bloqueig; falta fitxa 360°, hores, auditoria, baixa segura. |
| **012 — Copilot IA** | 🔴 No implementat | Taules RAG existeixen però cap endpoint d'inferència. |
| **013-019 — PWA** | 🟠 Parcial | Login, jornada i incidències bàsics; picking incomplet; feines sense transicions d'estat. |
| **021 — Onboarding tenant** | 🔴 Crítica | Falta Celery, 2FA, enllaç d'activació, directoris, Nginx/Certbot. |
| **022 — KPIs / Superadmin** | 🔴 No implementat | No hi ha endpoints de KPIs ni esquema `superadmin_telemetry`. |
| **024 — Workers asíncrons** | 🔴 Crítica | `tasks.py` no funciona perquè importa serveis inexistents. |

---

## 7. Tests, linter i type checker

S'ha recreat el venv de desenvolupament i s'han instal·lat les dependències per poder avaluar el codi sense dependre d'un entorn preconfigurat.

- **Pytest:** `25 passed, 1 failed`. Falla `tests/test_014_operari_picking.py::test_crear_picking` perquè l'endpoint `POST /operari/picking` no existeix.
- **Mypy:** `11 errors` en `app/models/models.py`, `app/workers/tasks.py` i routers PWA.
- **Ruff:** `269 errors` (imports desordenats, espais en blanc, imports no utilitzats).

La taxa de passades és alta però enganyosa: cobreix principalment camins feliços de CRUD sense tests negatius ni de seguretat.

---

## 8. Recomanacions prioritzades

1. **Arreglar immediatament el model ORM** (CR-03) perquè l'aplicació pugui arrencar sense errors.
2. **Implementar RBAC centralitzat** a tots els routers de `/gestio`, començant per `/gestio/comptabilitat` (CR-01, CR-02).
3. **Crear la capa de serveis** (`app/services/verifactu.py`, `backup.py`, `outbox_aeat.py`, `whisper_service.py`) i vincular-la amb Celery (CR-04).
4. **Completar els routers PWA** de picking, jornada i incidències amb validació d'ownership i dependència JWT reutilitzable (CR-05, ALT-01, ALT-02).
5. **Desenvolupar el flux d'onboarding** complert (2FA, activació, Celery) segons Spec 021 (ALT-03).
6. **Ampliar la suite de tests** amb:
   - Tests negatius de rols (Enginyer rebent `403`, Operari no pot crear factura).
   - Test d'aïllament de middleware amb asserts reals (ALT-05).
   - Tests d'integritat Veri*factu.
7. **Unificar la configuració pytest** i eliminar `run_tests.py` com a mecanisme oficial (MED-01).
8. **Corregir el deute d'estil** amb `ruff --fix` i resoldre els errors de `mypy`.

---

## 9. Conclusió

El backend de SEVALOR és **un prototip estructuralment coherent però funcionalment incomplet**. Les bases de multi-tenancy RLS i CRUD sí que estan posades, però l'absència de RBAC, la duplicació de codi JWT, els errors del model ORM i els serveis inexistents de Veri*factu/Celery impedeixen que el sistema compleixi els estàndards de producció definits a la Constitució i les especificacions. L'auditoria recomana **aturar qualsevol desplegament** fins que els punts crítics (CR-01 a CR-05) i els alts (ALT-01 a ALT-05) estiguin resolts i coberts per tests d'integració.

---

*Elaborat seguint el protocol d'auditoria de `sdd_sevalor/Auditoria_i_Normativa_Tests_Backend.md` i `sdd_sevalor/AGENTS.md`.*
