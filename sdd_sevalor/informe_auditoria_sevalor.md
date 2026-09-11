# Informe d'Auditoria — SEVALOR (Projecte en desenvolupament)

**Data:** setembre 2025  
**Objectiu:** Analitzar si el projecte SEVALOR compleix les especificacions vigents, si els tests de comprovació són correctes i proposar millores **sense canviar les specs**, tot justificant-les.

---

## 1. Resum executiu

| Àrea | Estat general | Risc |
|---|---|---|
| Backend FastAPI (workspace actual) | **Parcialment implementat**, inconsistències importants | **Alt** |
| PWA Next.js (`/pwa`) | **Esquelet molt inicial**, falten funcionalitats crítiques | **Crític** |
| Tests backend | **No són correctes/corren establement**: imports trencats, errors de loop, 54 fallades sobre 93 proves | **Crític** |
| Seguretat (RBAC, rate-limit, 2FA, JWT) | **No implementada** segons Constitució/AGENTS.md | **Crític** |
| RLS multi-tenant | **Parcial**: existeix `set_tenant_context` però **no s'injecta automàticament** en obrir sessió | **Alt** |
| Infra / Docker / workers | Imatge de backend amb codi **desfasat respecte al workspace**; workers Celery amb rutes a tasques inexistents | **Alt** |
| Qualitat de codi (`ruff`, `mypy`) | **339 errors ruff**, **118 errors mypy --strict** | **Alt** |

**Opinió global:** El projecte **no segueix encara les specs** d'una manera fiable per a producció. El backend té l'esquelet de CRUD i alguns fluxos funcionals, però li falten mecanismes de seguretat Zero-Trust, RBAC, rate-limiting, 2FA TOTP i un RLS realment automàtic. La PWA és pràcticament només un `layout.tsx` i un redirect a `/operari/login` sense implementació de les pantalles de camp. Els tests tenen imports trencats i, quan corren, fallen la majoria, pel que no es poden considerar "correctes". Tot i això **és possible millorar sense tocar les specs**: completant la implementació dels requisits ja definits.

---

## 2. Observacions innegociables detectades

### 2.1 Backend — Model de dades i ORM

1. **Columna duplicada a `Empresa`** (`backend/app/models/models.py`:51‑59)
   - `node_ia_url` i `node_ia_actiu` estan declarats dues vegades.
   - Impacte: SQLAlchemy fallarà en crear la taula / `mypy` ja ho detecta (`no-redef`).
   - Millora: eliminar el bloc duplicat (línies 58‑59).

2. **Falten `CHECK` constraints i `Enum` de PostgreSQL.**
   - Estat/camps com `estat`, `modalitat`, `vertical`, etc. tenen valors lliures.
   - Les specs citen valors canònics (`JORNADA_CONTINUADA`, `PENDENT`, `EN_CURS`, etc.).
   - Millora: afegir `CheckConstraint`/`Enum` de PostgreSQL als models (no canvia funcionalitats, només blinda integritat).

3. **Model `OrdreTreball` no inclou coordenades GPS ni geovalla.**
   - La Spec 001 RF‑12 exigeix georreferenciació obligatòria prèvia.
   - Millora: afegir `latitud`/`longitud` i validar-les en crear una ordre.

4. **`RegistreJornadaLaboral` no calcula hores.**
   - Té `hores_ordinaries` i `hores_extraordinaries` però no hi ha lògica de càlcle en cap endpoint.
   - Spec 008 exigeix tancament automàtic a 8h i còmput d'hores.
   - Millora: implementar càlcul en finalitzar jornada segons `SlotJornada` assignat.

### 2.2 Backend — Seguretat i RBAC

5. **No s'aplica RBAC real als endpoints.**
   - `require_roles` i `require_financial_access` existeixen (`backend/app/core/security.py`) però cap endpoint de `/gestio/*` els utilitza.
   - Impacte: un token amb rol `OPERARI` pot teòricament crear clients, operaris, factures, etc.
   - Millora: decorar cada router amb el rol mínim requerit segons les matrius de permisos de cada Spec (007, 008, 011, etc.).

6. **Mòdul `/gestio/comptabilitat` no veto l'enginyer.**
   - Spec 001 RF‑03 / Spec 007 RF‑05 exigeixen `403 Forbidden` per a rols no autoritzats.
   - L'endpoint actual no filtra per rol.
   - Millora: afegir `require_financial_access` al router i crear el DTO tècnic `FacturaConsultaTecnicaDTO` per al rol `ENGINYER`.

7. **Sense rate-limiting global.**
   - `slowapi` és dependency però no està instanciada a `main.py` ni aplicada.
   - Spec 019 exigeix 5 intents/min per login.
   - Millora: afegir `SlowAPI`/`Limiter` a `main.py` i decorar `/operari_auth/login`, endpoints d'onboarding, etc.

8. **Sense 2FA TOTP obligatori per a usuaris d'oficina.**
   - Spec 011 exigeix 2FA TOTP per a Boss/Secretaria/Enginyer.
   - Els models tenen `secret_2fa` i `totp_activat` però no hi ha endpoints de setup/verificació.
   - Millora: implementar flux d'enrolament TOTP i verificació en login.

9. **Sense refresh tokens ni cookies HttpOnly.**
   - Constitució §3 / AGENTS.md §3.2 ho exigeix explícitament.
   - Millora: afegir endpoint `/auth/refresh` amb cookie `HttpOnly; Secure; SameSite=Strict` i llista negra a Redis.

10. **Manlleu de codi JWT repetit a múltiples endpoints (`operari_pwa/jornada.py`, `feines.py`).**
    - `_get_usuari_id` duplica la lògica de `security.py` i no comprova `Bearer` abans de fer `split()`.
    - Millora: reutilitzar `get_current_user_claims` com a dependència FastAPI.

### 2.3 Backend — Multi-tenant i RLS

11. **`TenantMiddleware` no injecta RLS a la sessió de BD.**
    - Només posa `request.state.empresa_id`; no fa `SET LOCAL app.current_empresa_id`.
    - Per tant, els endpoints depenen de `set_tenant_context` cridat manualment, cosa que és fràgil.
    - Millora: afegir un `BaseHTTPMiddleware` o dependència global que, en obrir-se una `AsyncSession`, executi les sentències RLS amb el `empresa_id` extret del JWT o `X-Empresa-ID`.

12. **`set_tenant_context` fa `SET ROLE sevalor_app;` però no comprova que el rol existeixi.**
    - En tests aïllats sense el rol creat, fallarà.
    - Millora: garantir que el rol `sevalor_app` es creï en la inicialització de BD i que els tests el creïn.

13. **Tests RLS incomplets / no executables.**
    - `backend/tests/test_rls_middleware.py` és un test buit (`pass`).
    - `backend/tests/test_rls.py` funciona només si la BD real té el rol i polítiques creades; però no està integrat amb la suite d'integració amb `httpx`.
    - Millora: completar `test_rls_middleware.py` cridant un endpoint real i verificant que `X-Empresa-ID` no pot falsejar el tenant.

### 2.4 Backend — Veri*factu i workers

14. **Hash Veri*factu simplificat no és legalment conforme.**
    - A `comptabilitat.py` es calcula un SHA‑256 bàsic d'un string concatenat.
    - La Spec 007/024 exigeix camp `hash_anterior`, SELECT FOR UPDATE, codi QR estructurat, signatura, Outbox AEAT.
    - Millora: implementar el motor a `app/services/verifactu.py` amb ReportLab, QR oficial i encadenament determinista; no alterar la spec.

15. **Tasques Celery fan referències a funcions inexistents.**
    - `celery_app.py` enruta `processar_tiquet_ocr_task`, `sincronitzar_bloc_offline_task`, `enviar_notificacio_telegram_task`, que no existeixen a `app/workers/tasks.py`.
    - Millora: crear les tasques o eliminar les rutes fins que estiguin implementades.

16. **Workers no injecten `empresa_id` per a RLS.**
    - La tasca `transcriure_audio_task` usa `asyncio.run()` sense obrir sessió PostgreSQL amb RLS.
    - Spec 024 RF‑02 ho exigeix.
    - Millora: passar la sessió async de BD amb `set_tenant_context` des de cada worker, o delegar a una primitiva reutilitzable.

### 2.5 Frontend / PWA (`/pwa`)

17. **PWA no té pantalles de camp implementades.**
    - Només existeixen `layout.tsx`, `page.tsx` (redirect) i un parell de pàgines `/superadmin`.
    - Falten `/operari/login`, `/operari/feines`, `/operari/incidencies`, etc.
    - Millora: crear les rutes Next.js segons Spec 013‑020 ja aprovades.

18. **Service Worker / Workbox absent.**
    - Spec 019 i Constitució §2 exigeixen offline‑first amb Workbox.
    - `package.json` no inclou `workbox-*`.
    - Millora: afegir `next-pwa` o workbox-webpack-plugin amb estratègia `NetworkFirst`/`BackgroundSync`.

19. **No existeix criptografia real de tokens a la PWA.**
    - `test_crypto.mjs` valida la primitiva, però `pwa/src/lib/db.ts` no xifra res.
    - IndexedDB guardaria tokens en text pla.
    - Millora: implementar `crypto.service.ts` que derivi la clau del PIN i xifri/desxifri token + sentinel.

20. **No hi ha captura de càmera, geovalla, cronòmetre ni biblioteca d'imatges.**
    - `media.ts` només defineix una funció de compressió WebP; no hi ha component de càmera.
    - `geo.ts` només calcula distància; no s'integra amb el flux d'inici de feina.
    - Millora: implementar components/visor de càmera amb `capture="environment"`, control de geovalla i cronòmetre.

21. **Tema camaleònic (Chameleon UI Engine) no implementat.**
    - `globals.css` i `tailwind.config.js` no defineixen variables CSS HSL dinàmiques.
    - `layout.tsx` té `themeColor` hardcodejat a `#15803d`.
    - Millora: carregar valors `primari_hsl`/`secundari_hsl` de l'empresa i injectar-los a `:root`.

### 2.6 Tests i qualitat de codi

22. **Imports trencats en tests.**
    - `tests/test_operari_auth.py` importa `hash_pin` d'`app.api.v1.operari_auth`, però aquesta funció està a `app.api.v1.gestio.operaris`.
    - `tests/test_bot_telegram.py` importa `bot.security`, però `bot/` no és un paquet amb `__init__.py` ni està al PYTHONPATH.
    - Millora: corregir els imports dels tests o moure les funcions al lloc esperat.

23. **Ruff i Mypy amb molts errors.**
    - `ruff check /app` → **339 errors** (imports desordenats, espais en blanc, imports no usats, escape sequences).
    - `mypy /app/app --strict` → **118 errors** (tipatges faltants, redefinicions, retorns no tipats).
    - Segons AGENTS.md, els tests no poden donar-se per vàlids si aquests informes no estan nets.
    - Millora: executar `ruff check --fix` i completar tipatges; afegir anotacions de retorn als endpoints.

24. **`pytest` no corre establement en el contenidor desplegat.**
    - Amb `TEST_DATABASE_URL` correcte, la suite obtinguda: **54 fallades, 39 passades, 2 warnings**.
    - Molts tests més complexos (copilot, notificacions, planols, configuració) importen codi del backend del contenidor que **no existeix al workspace actual** (`cerca.py`, `copilot.py`, `configuracio.py`, `telemetria.py`).
    - Això evidencia **desfasament entre el codi del workspace i la imatge Docker**.
    - Millora: sincronitzar workspace → imatge; no deixar codi "fantasma" només al contenidor.

### 2.7 Bot de Telegram

25. **El bot (`bot/main.py`) no està connectat amb el backend.**
    - Gestiona vinculació a Redis però no consulta la taula `tokens_invitacio_telegram` ni persisteix res a PostgreSQL.
    - Millora: integrar el bot amb els models del backend i executar-lo com a microservei independent amb accés a BD.

26. **`RateLimiterTelegram` del test no existeix.**
    - El test importa `RateLimiterTelegram` però el fitxer defineix `RedisRateLimiter`.
    - Millora: alinear noms o refactoritzar el test.

---

## 3. Justificació de les millores proposades (sense canviar especificacions)

| Millora | Justificació (especs/constitució) |
|---|---|
| Implementar RBAC als endpoints | Spec 007 RF‑05, Spec 008 matriu de permisos, Constitució Zero‑Trust §3 |
| Activar rate-limiting real | AGENTS.md §3.3, Spec 019 RF sobre intents de PIN |
| Completar 2FA TOTP | Spec 011 matriu, AGENTS.md §3.2 |
| Fer automàtic el RLS a `get_db`/`TenantMiddleware` | Spec 011 RF‑21, Constitució §6, Auditoria_i_Normativa_Tests_Backend.md §2 |
| Corregir el backend Veri*factu amb QR + Outbox | Spec 007 RF‑12/RF‑25, Spec 024 RF‑05/RF‑07 |
| Desenvolupar la PWA de camp (login, feines, incidències, càmera) | Spec 013‑020, Constitució §2 (offline‑first) |
| Afegir Service Worker i xifrat AES‑GCM a IndexedDB | Constitució §2, Spec 019 RF‑04/RF‑05 |
| Sincronitzar workspace amb Docker i eliminar codi fantasma | AGENTS.md §1.1, Definition of Done |
| Netejar ruff/mypy | AGENTS.md §5 i Definition of Done |
| Completar tests reals (RLS, RBAC, Veri*factu, PWA) | Auditoria_i_Normativa_Tests_Backend.md, Definition of Done |

---

## 4. Valoració dels tests de comprovació

**Conclusió: els tests NO són correctes actualment.**
- Dos mòduls de test fallen ja en la fase de col·lecció (`test_bot_telegram.py`, `test_operari_auth.py`) per imports invàlids.
- Quan s'ignoren aquests dos, la majoria de tests més ambiciosos fallen perque el backend del workspace no implementa els serveis que els tests supposen (`copilot`, `configuracio`, `notificacions avançades`, etc.), o bé per errors de loop asíncron i connexió a BD.
- Només 39 de 93 tests passen (després d'ignorar imports trencats), i aquests són principalment els CRUDs senzills.
- **Millora immediata:** corregir imports trencats, afegir `TEST_DATABASE_URL`, crear el rol `sevalor_app` i les polítiques RLS a la BD de tests, i reduir la duplicació de la lògica Pydantic/JWT per evitar loops.

---

## 5. Recomanacions d'ordre d'execució

1. **Correccions crítiques de seguretat i integritat (1‑2 dies)**
   - Arreglar columnes duplicades a `models.py`.
   - Fer que `get_db`/`TenantMiddleware` injectin RLS automàticament.
   - Afegir RBAC als endpoints amb `require_roles` / `require_financial_access`.
   - Afegir rate-limiting a login i endpoints sensibles.

2. **Correcció del backend Veri*factu i workers (2‑3 dies)**
   - Implementar `verifactu.py`, `outbox_aeat.py`, QR i encadenament.
   - Corregir rutes Celery i assegurar RLS als workers.

3. **Sanejament de qualitat de codi (1 dia)**
   - `ruff check --fix`.
   - Resoldre errors mypy (tipatges, `Optional` checks, imports).

4. **Desenvolupament de la PWA (1‑2 setmanes)**
   - Login amb numpad, xifrat de token.
   - Service Worker + sync en segon pla.
   - Pantalles de feines, incidències, vehicles, tiquets, càmera, plànols.
   - Tema camaleònic amb variables CSS HSL.

5. **Sincronització workspace ↔ Docker i tests (2‑3 dies)**
   - Eliminar codi fantasma del contenidor o portar-lo al workspace.
   - Completar tests d'RLS, RBAC i Veri*factu.

---

## 6. Conclusió

El projecte SEVALOR té una base d'arquitectura correcta (FastAPI + asyncpg + SQLAlchemy 2.0, models multi‑tenant, esquelet de tenants i bot Telegram), però **no està llest per a producció i encara no compleix de manera demostra­ble les specs**, especialment en seguretat, offline‑first de la PWA i facturació legal Veri*factu. La bona notícia és que **totes les millores necessàries caben dins les especificacions aprovades**: no cal canviar cap `spec.md`, sinó acabar de implementar allò que ja s'ha exigit. La primera prioritat hauria de ser la seguretat Zero‑Trust (RLS automàtic + RBAC + rate‑limiting + 2FA), seguida de la sanejada de tests i la PWA operativa de camp.

---

## Annex A — Resum de l’auditoria PWA (subagent e2d5f73e)

Fitxer font: `AUDIT_SEVALOR_PWA.md`.

**Resultats executats:**
- `npm test` (crypto) ✅ — però només valida primitives aïllades.
- `node test_pwa_logic.mjs` ✅ — valida geovalla i atributs de càmera.
- `npm run build` ✅ — però genera output SSR `.next/`, **no export estàtic PWA**.
- `npm run lint` ❌ — falta configuració ESLint.

**Hallazgos crítics:**
1. **C-01**: No existeix `public/manifest.json`, Service Worker, Workbox ni `next.config.js`; no és PWA real (incompliment Constitució §2 i Spec 019).
2. **C-02**: Login operari amb PIN fallback `1234` i NIF hardcoded `12345678Z`.
3. **C-03**: `crypto.ts` i `db.ts` implementen primitives correctes però **no s’integren** al login; no es persisteix token xifrat.

**Hallazgos alts:**
- Dades mock/hardcoded generalitzades a `feines`, `material`, `planols`, `vehicles`, `gestio/mapa`, `gestio/copilot`, `superadmin/telemetria`, etc. (incompliment Zero Mock Data).
- Backend URL hardcoded `http://127.0.0.1:8001/api/v1/...` sense headers de tenant ni variables d’entorn.
- Chameleon UI hardcoded: `themeColor`, tokens HSL i marca fixes a la sidebar.
- Mapa amb imatges Unsplash i vectors hardcoded com a dades GIS.

**Recomanacions immediates:**
1. Crear `next.config.js` amb `withPWA`, `output: 'export'`, `distDir: 'dist'` i `public/manifest.json`.
2. Integrar `crypto.ts` al flux de login amb sentinel + JWT xifrat a IndexedDB; eliminar PIN fallback.
3. Eliminar funcions `*Demo` i substituir-les per fetchers reals/backend o IndexedDB.
4. Centralitzar API URL i tenant headers a `src/lib/api.ts` amb variables d’entorn.
5. Implementar Workbox amb background sync per a `sync_queue` i cue offline-first.
6. Aplicar Chameleon UI real via endpoint `/config/brand` i variables CSS HSL dinàmiques.
7. Configurar ESLint perquè `npm run lint` passi.

---

## Annex B — Resum de l’auditoria Infra/DevOps (subagent b7c336d4)

**Contenidor backend inspeccionat:** `sevalor_backend` (UP, `127.0.0.1:8001`).

**Mètriques clau:**
- `ruff check .` = **339 errors**.
- `mypy app/ --strict` = **118 errors**.
- Tests: 0/93 executables correctament (imports trencats + `ConnectionRefusedError`).
- Servicios desplegats SEVALOR: **3/7** (db, redis, backend). Falten `pwa`, `celery_worker`, `celery_beat`, `bot`, `nginx`.
- Workers Celery operativos: **0/2** — estan en bucle de reinici per apuntar a `app.core.celery_app` (inexistent) en lloc de `app.workers.celery_app`.
- Bot Telegram: **no desplegat com a servei Docker**.
- Secrets per defecte: **3+** (`SECRET_KEY`, Postgres, `sevalor_app`).

**Hallazgos crítics:**
1. **C1**: Workers Celery en bucle de reinici. S’han de corregir command i afegir `celery_worker`/`celery_beat` al `docker-compose.yml` de SEVALOR.
2. **C2**: `SECRET_KEY`, `POSTGRES_PASSWORD` i contrasenya del rol `sevalor_app` amb valors per defecte; compromet JWT i RLS.
3. **C3**: Falten 4 dels 7 microserveis declarats a AGENTS.md: PWA, workers, bot, nginx.
4. **C4**: `TenantMiddleware` no reutilitza `get_current_user_claims` i captura excepcions JWT amb `pass`, deixant `empresa_id = None`; pot saltar-se RLS.
5. **C5**: CORS permet origens locals amb `allow_methods=["*"]` i `allow_headers=["*"]`, sense consultar `empreses.domini_custom`.

**Hallazgos importants:**
- Redis sense contrasenya.
- Rate-limiting `slowapi` declarat però no implementat.
- JWT sense `aud`/`iss`; refresh token no en cookie HttpOnly/Secure.
- `superadmin/tenants` sense IP Allowlist ni 2FA TOTP.
- Bot Telegram sense validació de firma HMAC ni vinculació amb PostgreSQL.
- Sense pipeline CI/CD; sense `.github/workflows/` ni `Jenkinsfile`.
- Sense scripts/programació real de backup (`backup.py` existeix però Celery Beat no el programa).
- Mapa d’entorns corrupte: els contenidors `infra-*` en execució pertanyen al projecte **CAMPOPRO**, no a **SEVALOR**.

**Recomanacions immediates:**
1. Reconciliar imatge Docker vs workspace (el contenidor té `app/services/*`, `cerca.py`, etc., que no són al workspace).
2. Corregir arrancada de Celery (`-A app.workers.celery_app`) i afegir-lo a `docker-compose.yml`.
3. Rotar tots els secrets per defecte i usar Docker Secrets/EasyPanel.
4. Completar arquitectura: PWA, bot, nginx amb SSL/CSP, healthchecks i límits de recursos.
5. Implementar rate-limiting/CORS restrictiu, IP Allowlist i 2FA TOTP per a `/superadmin`.
6. Corregir errors de tipat/sintaxi (`backup.py`, `outbox_aeat.py`, columnes duplicades) abans de testejar.
7. Reparar suite de tests: imports, apuntar a `db:5432` dins del contenidor i validar RLS/Zero Mock.
8. Crear pipeline CI/CD amb `ruff`, `mypy --strict`, `pytest --cov` i escaneig de secrets.
9. Crear volums per a `/data` i `/docs` amb propietari `1000:1000` i programar backups setmanals via Celery Beat.
10. Alinear models amb migracions: eliminar columnes duplicades, parametritzar genèrics i coherir SQLAlchemy/PostgreSQL.

---

*Informe general consolidat amb aportacions dels subagents d’auditoria Backend, PWA i Infra/DevOps. Tots els documents es troben a:*
- `sdd_sevalor/informe_auditoria_sevalor.md` (aquest document)
- `AUDIT_SEVALOR_PWA.md`
- `informe_auditoria_backend_sevalor.md`

---

## Annex C — Resum de l’auditoria Backend vs specs (subagent 33c101bb)

Fitxer font: `informe_auditoria_backend_sevalor.md`.

**Mètriques d’anàlisi:**
- `pytest tests/ -v` → **25 passades, 1 fallida** (`test_crear_picking`, `404 != 201`, per endpoint inexistent).
- `mypy app/` → **11 errors** (duplicació columnes Empresa/ConsultaXatCopilot, imports inexistents a workers, JWT inline als routers PWA).
- `ruff check app/ tests/` → **269 errors** (imports, espais en blanc, imports no utilitzats).

**Hallazgos crítics:**
1. **CR-01 — Absència de RBAC als endpoints `/gestio`:** qualsevol JWT vàlid (inclòs `OPERARI`) pot crear clients, vehicles i **factures**.
2. **CR-02 — `/gestio/comptabilitat` permet emetre factures sense privilegis financers**; hash Veri*factu incomplet (falta camps immutables, `hash_anterior`, sèrie/número consecutiu, QR, AEAT).
3. **CR-03 — Model ORM amb columnes duplicades:** `Empresa` (`node_ia_url`, `node_ia_actiu`) i `ConsultaXatCopilot` (atributs del tenant).
4. **CR-04 — Workers Celery importen serveis inexistents:** `app.services.verifactu`, `backup`, `outbox_aeat`, `whisper_service`.
5. **CR-05 — Router PWA de picking incomplet:** falten `POST /operari/picking` i `POST /operari/picking/{id}/linies`, i no valida ownership.

**Hallazgos alts:**
- **ALT-01**: routers PWA dupliquen la lògica JWT inline en lloc d’usar `get_current_user_claims`.
- **ALT-02**: `/operari/jornada/{id}/fi` permet tancar jornades alienes i no calcula hores.
- **ALT-03**: onboarding de tenants incomplet (sense 2FA TOTP, token d’activació, directoris sobirans, Celery).
- **ALT-04**: superadmin sense IP Allowlist ni 2FA.
- **ALT-05**: `test_rls_middleware.py` és un `pass` sense assertions.

**Conformitat per especificacions principals:**
- **004 Magatzem**: falten picking, estoc, FEFO, retalls, traspàs offline.
- **007 Comptabilitat/Veri*factu**: hash bàsic; falta PDF, QR, AEAT, workers, rol financer.
- **012 Copilot IA**: taules RAG existents però cap endpoint d’inferència.
- **021 Onboarding tenant**: falta Celery, 2FA, enllaç d’activació, directoris, Nginx/Certbot.
- **022 KPIs/Superadmin**: no implementat; falta esquema `superadmin_telemetry`.
- **024 Workers asíncrons**: `tasks.py` falla per imports inexistents.

**Recomanacions prioritzades:**
1. Arreglar model ORM (columnes duplicades).
2. Implementar RBAC centralitzat a `/gestio`, començant per `comptabilitat`.
3. Crear capa de serveis (`verifactu`, `backup`, `outbox_aeat`, `whisper_service`) i vincular Celery.
4. Completar routers PWA (picking, jornada, incidències) amb ownership i JWT reutilitzable.
5. Desenvolupar onboarding complert segons Spec 021.
6. Ampliar tests amb negatius de rol, test RLS real i tests Veri*factu.
7. Unificar configuració pytest i eliminar `run_tests.py`.
8. Corregir deute d’estil amb `ruff --fix` i errors mypy.

---

## Annex D — Índex de fitxers auditors lliurats

| Fitxer | Contingut |
|---|---|
| `sdd_sevalor/informe_auditoria_sevalor.md` | Informe general consolidat (aquest document) |
| `AUDIT_SEVALOR_PWA.md` | Auditoria PWA Next.js |
| `informe_auditoria_backend_sevalor.md` | Auditoria backend FastAPI vs specs i constitució |


