# Tasks: Backoffice Gestió (Spec 01) — Microtasques < 30 minuts

**Feature Path**: `specs/01-backoffice-gestio`  
**Prerequisites**: `spec.md`, `plan.md`, `constitution.md`, `AGENTS.md`  
**Norma Suprema**: Zero Mock Data, RLS obligatori, comprovació neta al 100% (`pytest -v`), cadena de test per tasca.  
**Criteri de Granularitat**: Totes les tasques estan estrictament acotades a una durada estimada **< 30 minuts**, ordenades per dependència lògica descendent, amb **Skill mandatoria** i **Eina MCP** associades.

---

## 🔒 Bloc 1: Fonaments de Seguretat, RLS i Context Multi-Inquilí

- [ ] **T001 [Backend/DB] Polítiques RLS de PostgreSQL per a les taules de Backoffice** (~25 min)  
  *Dependència*: Cap  
  *Requisits Funcionals*: `FR-001`, `FR-003`  
  *Skill Mandatòria*: `supabase-postgres-best-practices` ([`.agents/skills/supabase-postgres-best-practices/SKILL.md`](file:///.agents/skills/supabase-postgres-best-practices/SKILL.md))  
  *Eina MCP*: `postgres` (verificació en viu d'esquema i estat RLS)  
  *Descripció*: Configurar i verificar que totes les taules de gestió (`usuaris`, `clients`, `ordres_treball`, `magatzem`, `vehicles`, `factures`) tenen `ENABLE ROW LEVEL SECURITY` i política per `empresa_id = NULLIF(current_setting('app.current_empresa_id', true), '')::uuid`.  
  **Hecho cuando:** La consulta `SELECT relrowsecurity FROM pg_class WHERE relname IN ('clients', 'ordres_treball', 'factures_capcalera')` retorna `true` per a totes les taules.  
  *Cadena de Test*:  
  `backend/.venv/bin/pytest backend/tests/test_rls.py backend/tests/test_021_rls_isolation.py -v`

- [ ] **T002 [Backend/Middleware] Injecció de Sessió RLS a `TenantContextMiddleware`** (~20 min)  
  *Dependència*: `T001`  
  *Requisits Funcionals*: `FR-001`  
  *Skill Mandatòria*: `security-and-hardening` ([`.agents/skills/security-and-hardening/SKILL.md`](file:///.agents/skills/security-and-hardening/SKILL.md))  
  *Eina MCP*: `postgres` (auditoria de variable de sessió per connexió)  
  *Descripció*: Garantir que el middleware FastAPI extreu `empresa_id` del token JWT i executa `SET LOCAL app.current_empresa_id = :empresa_id` al principi de cada transacció de base de dades.  
  **Hecho cuando:** Una petició HTTP amb JWT vàlid executa `SHOW app.current_empresa_id` i retorna el UUID corresponent al payload.  
  *Cadena de Test*:  
  `backend/.venv/bin/pytest backend/tests/test_rls_middleware.py backend/tests/test_021_rls_tenant_injection.py -v`

- [ ] **T003 [Backend/RBAC] Guardes Zero-Trust de Segregació de Rols a `deps.py`** (~20 min)  
  *Dependència*: `T002`  
  *Requisits Funcionals*: `FR-003`  
  *Skill Mandatòria*: `security-review` ([`.agents/skills/security-review/SKILL.md`](file:///.agents/skills/security-review/SKILL.md))  
  *Eina MCP*: `postgres` (comprovació de rols a taula `usuaris`)  
  *Descripció*: Implementar i blindar les dependències `require_boss`, `require_enginyer_or_boss` i `veto_enginyer_finances`, denegant amb `HTTP 403 Forbidden` accessos no autoritzats.  
  **Hecho cuando:** Un usuari amb rol `ENGINYER` que sol·licita un recurs financer rep directament HTTP 403 amb `{ "detail": "Accés denegat per rol" }`.  
  *Cadena de Test*:  
  `backend/.venv/bin/pytest backend/tests/test_security_rbac.py -k "test_enginyer_cannot_access_financial_data" -v`

---

## 👥 Bloc 2: Clients, Finques Georeferenciades i Domiciliació SEPA

- [ ] **T004 [Backend/Schemas] Esquemes Pydantic de Clients i Validació de NIF/CIF i SEPA** (~20 min)  
  *Dependència*: `T002`  
  *Requisits Funcionals*: `FR-006`  
  *Skill Mandatòria*: `security-and-hardening` ([`.agents/skills/security-and-hardening/SKILL.md`](file:///.agents/skills/security-and-hardening/SKILL.md))  
  *Eina MCP*: `postgres` (verificació de dades fiscals reals)  
  *Descripció*: Crear esquemes de validació per a clients: comprovació del dígit de control de NIF/CIF espanyol i validació de format IBAN amb checksum mòdul 97 (sense fer-lo obligatori en alta inicial).  
  **Hecho cuando:** El validador accepta un NIF/CIF vàlid o IBAN vàlid i rebutja un IBAN sintètic amb `ValueError: IBAN invàlid`.  
  *Cadena de Test*:  
  `backend/.venv/bin/pytest backend/tests/test_phase2_gestio.py -k "test_clients_crud_dia0_i_alta" -v`

- [ ] **T005 [Backend/API] Endpoints CRUD de Clients (`GET` i `POST /api/v1/gestio/clients`)** (~25 min)  
  *Dependència*: `T004`  
  *Requisits Funcionals*: `FR-006`  
  *Skill Mandatòria*: `supabase-postgres-best-practices` ([`.agents/skills/supabase-postgres-best-practices/SKILL.md`](file:///.agents/skills/supabase-postgres-best-practices/SKILL.md))  
  *Eina MCP*: `postgres` (consulta a taula `clients`)  
  *Descripció*: Implementar llistat paginat amb filtres per nom/nif i creació de nous clients persistint a la taula `clients` sota RLS.  
  **Hecho cuando:** `POST /api/v1/gestio/clients` retorna HTTP 201 amb el nou registre i `GET /api/v1/gestio/clients` el llista de forma aïllada per empresa.  
  *Cadena de Test*:  
  `backend/.venv/bin/pytest backend/tests/test_002_gestio_clients.py -k "test_crear_client" -v`

- [ ] **T006 [Backend/Model] Model de Finques amb Coordenades GPS i Dades SIGPAC** (~20 min)  
  *Dependència*: `T005`  
  *Requisits Funcionals*: `FR-005`  
  *Skill Mandatòria*: `supabase-postgres-best-practices` ([`.agents/skills/supabase-postgres-best-practices/SKILL.md`](file:///.agents/skills/supabase-postgres-best-practices/SKILL.md))  
  *Eina MCP*: `postgres` (verificació de taula `finques` i relació FK)  
  *Descripció*: Modelar la taula `finques` vinculada a `clients.id` amb latitud, longitud, referència cadastral, polígon/parcel·la SIGPAC i codi d'accés a candat.  
  **Hecho cuando:** La relació ORM `Client.finques` carrega les finques associades i valida rangs de latitud (-90 a 90) i longitud (-180 a 180).  
  *Cadena de Test*:  
  `backend/.venv/bin/pytest backend/tests/test_002_gestio_clients.py -k "test_crear_finca" -v`

- [ ] **T007 [Backend/API] Endpoints de Finques (`GET` i `POST /api/v1/gestio/clients/{id}/finques`)** (~25 min)  
  *Dependència*: `T006`  
  *Requisits Funcionals*: `FR-005`  
  *Skill Mandatòria*: `supabase-postgres-best-practices` ([`.agents/skills/supabase-postgres-best-practices/SKILL.md`](file:///.agents/skills/supabase-postgres-best-practices/SKILL.md))  
  *Eina MCP*: `postgres` (validació de geolocalització a PostgreSQL)  
  *Descripció*: Crear rutes per afegir escomeses o parcel·les georeferenciades a un client existent, garantint que la localització sigui obligatòria.  
  **Hecho cuando:** `POST /api/v1/gestio/clients/{id}/finques` sense coordenades retorna HTTP 422, i amb coordenades vàlides persisteix la finca retornant HTTP 201.  
  *Cadena de Test*:  
  `backend/.venv/bin/pytest backend/tests/test_002_gestio_clients.py -k "test_finca_coordenades" -v`

- [ ] **T008 [Backend/API] Endpoint de Fitxa 360° del Client (`GET /api/v1/gestio/clients/{id}/fitxa-360`)** (~25 min)  
  *Dependència*: `T005`, `T007`  
  *Requisits Funcionals*: `FR-006`, `US9`  
  *Skill Mandatòria*: `supabase-postgres-best-practices` ([`.agents/skills/supabase-postgres-best-practices/SKILL.md`](file:///.agents/skills/supabase-postgres-best-practices/SKILL.md))  
  *Eina MCP*: `postgres` (consulta consolidada multi-taula)  
  *Descripció*: Construir endpoint consolidat que unifica en una sola càrrega l'historial complet del client: finques, ordres de treball actives/passades, pressupostos, factures i incidències.  
  **Hecho cuando:** La crida a `/api/v1/gestio/clients/{id}/fitxa-360` respon en <250ms retornant l'objecte consolidat amb totes les relacions del tenant.  
  *Cadena de Test*:  
  `backend/.venv/bin/pytest backend/tests/test_phase2_torre_control_eval.py -k "test_f2_04_fitxa_360_client" -v`

---

## 🗺️ Bloc 3: Torre de Control, Feines i Mapa Operatiu GIS

- [ ] **T009 [Backend/Model] Model `ordres_treball` amb Bloqueig Optimista i Georeferenciació** (~25 min)  
  *Dependència*: `T006`  
  *Requisits Funcionals*: `FR-005`, `US1`  
  *Skill Mandatòria*: `supabase-postgres-best-practices` ([`.agents/skills/supabase-postgres-best-practices/SKILL.md`](file:///.agents/skills/supabase-postgres-best-practices/SKILL.md))  
  *Eina MCP*: `postgres` (verificació de columna `versio` i índexs espacials)  
  *Descripció*: Definir la taula `ordres_treball` amb columna `versio` (per a concurrència optimista), estat (`PENDENT`, `PROGRAMADA`, `EN_CURS`, `FINALITZADA`, etc.) i coordenades `latitud`/`longitud`.  
  **Hecho cuando:** Un intent d'actualització amb una versió desfasada llança un error HTTP 409 Conflict de concurrència.  
  *Cadena de Test*:  
  `backend/.venv/bin/pytest backend/tests/test_phase2_torre_control_eval.py -k "test_f2_02_bloqueig_optimista_agenda" -v`

- [ ] **T010 [Backend/API] Endpoints de Creació i Gestió d'OTs (`/api/v1/gestio/feines`)** (~25 min)  
  *Dependència*: `T009`  
  *Requisits Funcionals*: `FR-005`, `US1`  
  *Skill Mandatòria*: `supabase-postgres-best-practices` ([`.agents/skills/supabase-postgres-best-practices/SKILL.md`](file:///.agents/skills/supabase-postgres-best-practices/SKILL.md))  
  *Eina MCP*: `postgres` (inserció a `ordres_treball`)  
  *Descripció*: Endpoints `GET` paginat i `POST` per a la creació d'ordres de treball amb operaris, vehicle assignat i materials de picking requerits.  
  **Hecho cuando:** `POST /api/v1/gestio/feines` crea la feina a la base de dades i retorna HTTP 201 amb l'estat inicial `PENDENT` o `PROGRAMADA`.  
  *Cadena de Test*:  
  `backend/.venv/bin/pytest backend/tests/test_005_gestio_feines.py -k "test_crear_feina" -v`

- [ ] **T011 [Backend/Service] Reassignació Ràpida "Drop & Go" (`PATCH /api/v1/gestio/feines/{id}/drop-and-go`)** (~25 min)  
  *Dependència*: `T010`  
  *Requisits Funcionals*: `US1`  
  *Skill Mandatòria*: `systematic-debugging` ([`.agents/skills/systematic-debugging/SKILL.md`](file:///.agents/skills/systematic-debugging/SKILL.md))  
  *Eina MCP*: `postgres` (comprovació de canvi de `capataz_id` / `data_programada`)  
  *Descripció*: Implementar la reassignació dinàmica d'operari o data/franja horària arrossegant la feina, verificant disponibilitat de l'operari i actualitzant l'estat.  
  **Hecho cuando:** `PATCH /api/v1/gestio/feines/{id}/drop-and-go` amb `operari_id` nou actualitza l'assignació i retorna la feina modificada amb versió incrementada.  
  *Cadena de Test*:  
  `backend/.venv/bin/pytest backend/tests/test_005_gestio_feines.py -k "test_drop_and_go" -v`

- [ ] **T012 [Backend/GIS] Capa Cartogràfica GeoJSON (`GET /api/v1/gestio/feines/mapa`)** (~25 min)  
  *Dependència*: `T010`  
  *Requisits Funcionals*: `FR-005`, `FR-018`  
  *Skill Mandatòria*: `supabase-postgres-best-practices` ([`.agents/skills/supabase-postgres-best-practices/SKILL.md`](file:///.agents/skills/supabase-postgres-best-practices/SKILL.md))  
  *Eina MCP*: `postgres` (validació de GeoJSON generat per la BD)  
  *Descripció*: Retornar una FeatureCollection GeoJSON amb les feines del dia, coordenades reals de les finques i posicions de les colles actives del tenant.  
  **Hecho cuando:** L'endpoint retorna JSON amb `type: "FeatureCollection"`, propietats d'estat de cada feina i cap coordenada inventada.  
  *Cadena de Test*:  
  `backend/.venv/bin/pytest backend/tests/test_phase2_torre_control_eval.py -k "test_f2_01_mapa_serveix_dades_reals" -v`

- [ ] **T013 [Backend/API] Endpoint HUD de la Torre de Control (`GET /api/v1/gestio/dashboard/hud`)** (~20 min)  
  *Dependència*: `T010`  
  *Requisits Funcionals*: `FR-018`  
  *Skill Mandatòria*: `frontend-design` ([`.agents/skills/frontend-design/SKILL.md`](file:///.agents/skills/frontend-design/SKILL.md))  
  *Eina MCP*: `postgres` (consultes de recompte d'OTs i incidències)  
  *Descripció*: Calcular i retornar els 6 KPIs operatius en viu (feines actives, completades, incidències obertes, colles en camp, estoc crític, vehicles amb alerta). Sense dades econòmiques.  
  **Hecho cuando:** L'endpoint respon en <100ms amb els comptadors calculats contra taules reals sense cap camp `marge_brut` o `euros`.  
  *Cadena de Test*:  
  `backend/.venv/bin/pytest backend/tests/test_005_gestio_feines.py -k "test_dashboard_hud" -v`

- [ ] **T014 [Backend/WebSocket] Canal de Telemetria i Esdeveniments (`/api/v1/gestio/ws`)** (~25 min)  
  *Dependència*: `T013`  
  *Requisits Funcionals*: `US1`  
  *Skill Mandatòria*: `systematic-debugging` ([`.agents/skills/systematic-debugging/SKILL.md`](file:///.agents/skills/systematic-debugging/SKILL.md))  
  *Eina MCP*: `chrome-devtools` (connexió WS i recepció d'esdeveniments)  
  *Descripció*: Connector WebSocket amb subscripció per `empresa_id` que emet broadcasts de canvis d'estat d'OTs, noves incidències i posició GPS dels vehicles.  
  **Hecho cuando:** Una connexió client WebSocket rep el missatge JSON d'esdeveniment `OT_ESTAT_CANVIAT` quan s'actualitza una feina.  
  *Cadena de Test*:  
  `backend/.venv/bin/pytest backend/tests/test_phase2_gestio.py -k "test_ws_telemetria" -v`

---

## 🪪 Bloc 4: Operaris, Fitxa 360, Control Horari GPS & DNI OCR

- [ ] **T015 [Backend/OCR] Servei d'Extracció OCR per a DNI d'Operaris (`ocr_service.py`)** (~25 min)  
  *Dependència*: `T003`  
  *Requisits Funcionals*: `SC-001`, `US2`  
  *Skill Mandatòria*: `systematic-debugging` ([`.agents/skills/systematic-debugging/SKILL.md`](file:///.agents/skills/systematic-debugging/SKILL.md))  
  *Eina MCP*: `postgres` (comprovació de no-duplicació de NIF)  
  *Descripció*: Processar imatge/PDF de DNI real per extreure NIF, Nom, Cognoms, Data de Naixement i Data de Caducitat estructurats (Zero Data Entry).  
  **Hecho cuando:** La funció `processar_dni_ocr(bytes)` extreu el NIF i nom amb un nivell de confiança documentat sense dades falses.  
  *Cadena de Test*:  
  `backend/.venv/bin/pytest backend/tests/test_008_gestio_operaris.py -k "test_dni_ocr_service" -v`

- [ ] **T016 [Backend/API] Endpoint d'Alta Màgica via DNI (`POST /api/v1/gestio/operaris/alta-dni-ocr`)** (~20 min)  
  *Dependència*: `T015`  
  *Requisits Funcionals*: `SC-001`, `US2`  
  *Skill Mandatòria*: `security-and-hardening` ([`.agents/skills/security-and-hardening/SKILL.md`](file:///.agents/skills/security-and-hardening/SKILL.md))  
  *Eina MCP*: `chrome-devtools` (pujada de fitxer DNI des de la UI)  
  *Descripció*: Recepció multipart/form-data del fitxer de DNI, crida al servei OCR i retorn d'un esborrany estructurat llest per validar per RRHH/Secretaria.  
  **Hecho cuando:** La pujada d'un DNI vàlid retorna HTTP 200 amb l'objecte draft `{ "nif": "...", "nom": "...", "cognoms": "...", "caducitat": "..." }`.  
  *Cadena de Test*:  
  `backend/.venv/bin/pytest backend/tests/test_008_gestio_operaris.py -k "test_alta_dni_ocr_endpoint" -v`

- [ ] **T017 [Backend/API] Endpoints de la Fitxa 360 de l'Operari (`/api/v1/gestio/operaris`)** (~25 min)  
  *Dependència*: `T016`  
  *Requisits Funcionals*: `FR-012`, `US2`  
  *Skill Mandatòria*: `security-and-hardening` ([`.agents/skills/security-and-hardening/SKILL.md`](file:///.agents/skills/security-and-hardening/SKILL.md))  
  *Eina MCP*: `postgres` (verificació de hashing de PIN i camps PRL)  
  *Descripció*: CRUD d'operaris amb camps de carnet de conduir (permís, caducitat), certificats PRL, telèfon i generació de PIN PWA inicial xifrat amb bcrypt.  
  **Hecho cuando:** `POST /api/v1/gestio/operaris` persisteix l'operari a `usuaris` i el PIN no es guarda mai en text pla.  
  *Cadena de Test*:  
  `backend/.venv/bin/pytest backend/tests/test_008_gestio_operaris.py -k "test_crear_operari_amb_carnet" -v`

- [ ] **T018 [Backend/Model] Model de Control Horari `registres_jornada_laboral` amb GPS** (~20 min)  
  *Dependència*: `T017`  
  *Requisits Funcionals*: `FR-004`  
  *Skill Mandatòria*: `supabase-postgres-best-practices` ([`.agents/skills/supabase-postgres-best-practices/SKILL.md`](file:///.agents/skills/supabase-postgres-best-practices/SKILL.md))  
  *Eina MCP*: `postgres` (constrenyiments de dades GPS a PostgreSQL)  
  *Descripció*: Taula de registre de jornada laboral amb columnes `inici`, `fi`, `latitud_inici`, `longitud_inici`, `latitud_fi`, `longitud_fi` i taula d'auditoria de canvis inalterable.  
  **Hecho cuando:** La inserció d'un fitxatge de camp sense coordenades GPS és rebutjada per constrenyiment de base de dades o validació Pydantic.  
  *Cadena de Test*:  
  `backend/.venv/bin/pytest backend/tests/test_008_gestio_operaris.py -k "test_fitxatge_gps_obligatori" -v`

- [ ] **T019 [Backend/API] Endpoints de Fitxatge i Consulta (`POST /fitxar` i `GET /control-horari`)** (~25 min)  
  *Dependència*: `T018`  
  *Requisits Funcionals*: `FR-004`  
  *Skill Mandatòria*: `security-review` ([`.agents/skills/security-review/SKILL.md`](file:///.agents/skills/security-review/SKILL.md))  
  *Eina MCP*: `postgres` (verificació de veto a l'endpoint)  
  *Descripció*: Endpoint de fitxar entrada/sortida per a qualsevol treballador, i endpoint de consulta d'auditoria reservat a Boss i Secretaria (veto per a Enginyer).  
  **Hecho cuando:** Un usuari amb rol `ENGINYER` que consulta `/api/v1/gestio/operaris/{id}/control-horari` rep HTTP 403 Forbidden.  
  *Cadena de Test*:  
  `backend/.venv/bin/pytest backend/tests/test_008_gestio_operaris.py -k "test_veto_enginyer_control_horari" -v`

- [ ] **T020 [Backend/Worker] Suport de Jornades > 8 hores i Celery Beat de Revisió** (~25 min)  
  *Dependència*: `T019`  
  *Requisits Funcionals*: `FR-004`  
  *Skill Mandatòria*: `systematic-debugging` ([`.agents/skills/systematic-debugging/SKILL.md`](file:///.agents/skills/systematic-debugging/SKILL.md))  
  *Eina MCP*: `postgres` (consulta a registres d'anomalia)  
  *Descripció*: Assegurar que el backend no tanca bruscament jornades a les 8h, sinó que permet hores extres i programa una tasca Celery Beat que detecta jornades obertes >12h marcant-les `ANOMALIA_REVISIO`.  
  **Hecho cuando:** Una jornada de 9h 30m queda registrada amb totes les seves hores i la tasca Celery la marca com a anomalia sense perdre cap minut.  
  *Cadena de Test*:  
  `backend/.venv/bin/pytest backend/tests/test_013_operari_jornada.py -k "test_jornada_mes_de_8h_permesa" -v`

---

## 📦 Bloc 5: Magatzem, Mermes, Codis de Barres & Albarans OCR

- [ ] **T021 [Backend/Model] Catàleg d'Articles amb Codis de Barres EAN-13/Code128 (Sense QR)** (~20 min)  
  *Dependència*: `T002`  
  *Requisits Funcionals*: `FR-007`  
  *Skill Mandatòria*: `supabase-postgres-best-practices` ([`.agents/skills/supabase-postgres-best-practices/SKILL.md`](file:///.agents/skills/supabase-postgres-best-practices/SKILL.md))  
  *Eina MCP*: `postgres` (verificació d'índexs a `articles`)  
  *Descripció*: Modelar `articles` amb validació de format de referència o codi de barres EAN-13/Code128, descartant i rebutjant de forma expressa codis QR per a gestió interna.  
  **Hecho cuando:** Un intent de donar d'alta un article amb format QR llança un error de validació i amb codi EAN-13 és acceptat.  
  *Cadena de Test*:  
  `backend/.venv/bin/pytest backend/tests/test_004_gestio_magatzem.py -k "test_article_codi_barres_sense_qr" -v`

- [ ] **T022 [Backend/Service] Gestió de Materials Continus i Percentatge de Merma** (~20 min)  
  *Dependència*: `T021`  
  *Requisits Funcionals*: `FR-008`  
  *Skill Mandatòria*: `systematic-debugging` ([`.agents/skills/systematic-debugging/SKILL.md`](file:///.agents/skills/systematic-debugging/SKILL.md))  
  *Eina MCP*: `postgres` (càlcul exacte de `quantitat_disponible`)  
  *Descripció*: Lògica de càlcul d'estoc per a materials continus (bobines de cable, canonades de reg) que descompta la longitud utilitzada més el % de merma configurat.  
  **Hecho cuando:** Un consum de 100m de cable amb 5% de merma redueix l'estoc en exactament 105 metres i registra el retall residual.  
  *Cadena de Test*:  
  `backend/.venv/bin/pytest backend/tests/test_004_gestio_magatzem.py -k "test_consum_material_continu_amb_merma" -v`

- [ ] **T023 [Backend/OCR] Extracció OCR d'Albarans de Proveïdor (`POST /ocr-albara`)** (~25 min)  
  *Dependència*: `T021`  
  *Requisits Funcionals*: `FR-009`, `SC-001`  
  *Skill Mandatòria*: `systematic-debugging` ([`.agents/skills/systematic-debugging/SKILL.md`](file:///.agents/skills/systematic-debugging/SKILL.md))  
  *Eina MCP*: `postgres` + `chrome-devtools` (pujada de PDF i comprovació d'esborrany)  
  *Descripció*: Ingesta de fotografies/PDFs d'albarans de proveïdor, extracció de capçalera (NIF, data, núm.) i graella d'articles en estat `PENDENT_AUDITORIA`.  
  **Hecho cuando:** L'endpoint retorna l'albarà amb la taula d'articles extrets i la base de dades el desa sense incrementar l'estoc fins a revisió humana.  
  *Cadena de Test*:  
  `backend/.venv/bin/pytest backend/tests/test_004_gestio_magatzem_ocr.py -k "test_ocr_albara_pendent_auditoria" -v`

- [ ] **T024 [Backend/API] Consolidació Humana d'Albarà i Actualització d'Estoc** (~25 min)  
  *Dependència*: `T023`  
  *Requisits Funcionals*: `FR-009`  
  *Skill Mandatòria*: `supabase-postgres-best-practices` ([`.agents/skills/supabase-postgres-best-practices/SKILL.md`](file:///.agents/skills/supabase-postgres-best-practices/SKILL.md))  
  *Eina MCP*: `postgres` (verificació d'increment atòmic a `estocs_magatzem`)  
  *Descripció*: Endpoint de validació manual per l'encarregat de compres que commuta l'estat a `CONSOLIDAT` i aplica l'increment físic d'estoc al magatzem corresponent.  
  **Hecho cuando:** L'estoc de l'article s'incrementa en la quantitat de l'albarà exclusivament després d'executar `POST /api/v1/gestio/magatzem/albarans/{id}/consolidar`.  
  *Cadena de Test*:  
  `backend/.venv/bin/pytest backend/tests/test_004_gestio_magatzem.py -k "test_consolidacio_albara_humana" -v`

- [ ] **T025 [Backend/Service] Detecció de Trencament d'Estoc i Esborrany d'Email (HITL)** (~25 min)  
  *Dependència*: `T024`  
  *Requisits Funcionals*: `FR-010`, `SC-003`  
  *Skill Mandatòria*: `security-review` ([`.agents/skills/security-review/SKILL.md`](file:///.agents/skills/security-review/SKILL.md))  
  *Eina MCP*: `postgres` (comprovació de cua de missatges pendents)  
  *Descripció*: Servei que avalua si `quantitat_disponible < estoc_minim` i genera un esborrany d'email al proveïdor amb la comanda necessària (sense auto-enviament).  
  **Hecho cuando:** Quan un consum baixa l'estoc d'un article per sota del mínim, es crea un draft d'email a la taula d'esborranys i cap correu s'envia a SMTP.  
  *Cadena de Test*:  
  `backend/.venv/bin/pytest backend/tests/test_033_backorder_ai.py -k "test_draft_email_sense_auto_enviament" -v`

- [ ] **T026 [Backend/API] Traspàs d'Estoc entre Magatzem Central i Furgonetes** (~25 min)  
  *Dependència*: `T024`  
  *Requisits Funcionals*: `US3`  
  *Skill Mandatòria*: `supabase-postgres-best-practices` ([`.agents/skills/supabase-postgres-best-practices/SKILL.md`](file:///.agents/skills/supabase-postgres-best-practices/SKILL.md))  
  *Eina MCP*: `postgres` (bloqueig transaccional `SELECT FOR UPDATE`)  
  *Descripció*: Endpoint `POST /api/v1/gestio/magatzem/traspas-furgoneta` amb bloqueig transaccional `SELECT FOR UPDATE` per moure material a furgonetes sense condicions de cursa.  
  **Hecho cuando:** Una transferència de 10 unitats resta exactament 10 del magatzem central i en suma 10 al magatzem de la furgoneta.  
  *Cadena de Test*:  
  `backend/.venv/bin/pytest backend/tests/test_031_picking_concurrency.py -k "test_traspas_furgoneta_segur" -v`

---

## 🚛 Bloc 6: Flota, Permisos de Carnet, Taller & Odòmetre OCR

- [ ] **T027 [Backend/Model] Model de Vehicles amb Taxonomia de Carnet Requerit** (~20 min)  
  *Dependència*: `T002`  
  *Requisits Funcionals*: `FR-011`, `FR-012`  
  *Skill Mandatòria*: `supabase-postgres-best-practices` ([`.agents/skills/supabase-postgres-best-practices/SKILL.md`](file:///.agents/skills/supabase-postgres-best-practices/SKILL.md))  
  *Eina MCP*: `postgres` (verificació de taula `vehicles`)  
  *Descripció*: Definir `vehicles` amb `matricula`, `marca_model`, `carnet_requerit` (B, B+E, C, C1), `odometre_km`, estat i dates de venciment d'ITV i assegurança.  
  **Hecho cuando:** La base de dades emmagatzema correctament un vehicle amb el tipus de permís de conduir assignat segons la seva MMA.  
  *Cadena de Test*:  
  `backend/.venv/bin/pytest backend/tests/test_006_gestio_flota.py -k "test_model_vehicle_carnet" -v`

- [ ] **T028 [Backend/Guard] Veto d'Assignació d'Operari sense Carnet Adequat** (~25 min)  
  *Dependència*: `T027`, `T017`  
  *Requisits Funcionals*: `FR-012`  
  *Skill Mandatòria*: `security-review` ([`.agents/skills/security-review/SKILL.md`](file:///.agents/skills/security-review/SKILL.md))  
  *Eina MCP*: `postgres` (validació de carnet d'operari a la BD)  
  *Descripció*: Lògica de comprovació a l'assignació de feina o vehicle que bloqueja l'operació si l'operari no disposa del carnet exigit pel vehicle o si està caducat.  
  **Hecho cuando:** L'intent d'assignar un camió (carnet C) a un operari amb permís B retorna HTTP 400 amb detall `L'operari no disposa del carnet C requerit`.  
  *Cadena de Test*:  
  `backend/.venv/bin/pytest backend/tests/test_006_gestio_flota.py -k "test_bloqueig_operari_sense_carnet" -v`

- [ ] **T029 [Backend/OCR] Extracció OCR de Quilòmetres per Foto d'Odòmetre** (~25 min)  
  *Dependència*: `T027`  
  *Requisits Funcionals*: `US4`  
  *Skill Mandatòria*: `systematic-debugging` ([`.agents/skills/systematic-debugging/SKILL.md`](file:///.agents/skills/systematic-debugging/SKILL.md))  
  *Eina MCP*: `postgres` + `chrome-devtools` (validació de foto d'odòmetre)  
  *Descripció*: Endpoint `POST /api/v1/gestio/flota/ocr-odometre` que analitza la fotografia del quadre de comandament i extreu la lectura numèrica de quilòmetres reals.  
  **Hecho cuando:** La pujada d'una foto d'odòmetre retorna el valor numèric extret i verifica que sigui estrictament superior a l'anterior quilometratge registrat.  
  *Cadena de Test*:  
  `backend/.venv/bin/pytest backend/tests/test_006_gestio_flota.py -k "test_ocr_odometre_lectura" -v`

- [ ] **T030 [Backend/API] Historial de Manteniment, Taller i Gestió de Grua** (~25 min)  
  *Dependència*: `T027`  
  *Requisits Funcionals*: `FR-011`  
  *Skill Mandatòria*: `supabase-postgres-best-practices` ([`.agents/skills/supabase-postgres-best-practices/SKILL.md`](file:///.agents/skills/supabase-postgres-best-practices/SKILL.md))  
  *Eina MCP*: `postgres` (registre de manteniments)  
  *Descripció*: Endpoints per registrar canvis d'oli pautats, reparacions efectuades, taller de referència, estat de garantia oficial i commutació d'estat a `IMMOBILITZAT_TALLER`.  
  **Hecho cuando:** L'endpoint `POST /api/v1/gestio/flota/{id}/manteniments` desa la intervenció de taller i actualitza l'estat operatiu del vehicle.  
  *Cadena de Test*:  
  `backend/.venv/bin/pytest backend/tests/test_006_gestio_flota.py -k "test_manteniment_taller" -v`

- [ ] **T031 [Backend/Worker] Semàfor Preventiu de Caducitats d'ITV i Assegurances** (~20 min)  
  *Dependència*: `T027`  
  *Requisits Funcionals*: `FR-011`  
  *Skill Mandatòria*: `systematic-debugging` ([`.agents/skills/systematic-debugging/SKILL.md`](file:///.agents/skills/systematic-debugging/SKILL.md))  
  *Eina MCP*: `postgres` (comprovació d'estat d'alertes preventives)  
  *Descripció*: Tasca Celery Beat executada cada dia a les 06:00 que avalua venciments a 30, 15, 5 i 1 dia, generant alertes al tauler de gestió de flota.  
  **Hecho cuando:** La tasca detecta un vehicle amb ITV que venç en 10 dies i genera una alerta d'estat groc al llistat de la flota.  
  *Cadena de Test*:  
  `backend/.venv/bin/pytest backend/tests/test_006_gestio_flota.py -k "test_alertes_itv_flota" -v`

---

## 🧾 Bloc 7: Facturació Veri*factu & Segregació Fiscal

- [ ] **T032 [Backend/Model] Model de Pre-Factura (Albarà Valorat HITL)** (~25 min)  
  *Dependència*: `T010`  
  *Requisits Funcionals*: `FR-013`  
  *Skill Mandatòria*: `security-review` ([`.agents/skills/security-review/SKILL.md`](file:///.agents/skills/security-review/SKILL.md))  
  *Eina MCP*: `postgres` (verificació d'estat `PROFORMA` / Pre-albarà)  
  *Descripció*: Crear l'estat transitori `PROFORMA` / Pre-albarà que unifica el full de la tasca completada, materials reals consumits i pressupost abans de la factura final.  
  **Hecho cuando:** El sistema impedeix generar una factura definitiva sense que existeixi prèviament la pre-factura validada per un humà.  
  *Cadena de Test*:  
  `backend/.venv/bin/pytest backend/tests/test_007_gestio_comptabilitat.py -k "test_prefactura_requerida_abans_emissio" -v`

- [ ] **T033 [Backend/Crypto] Emissió de Factura Veri*factu amb Hash SHA-256 Encadenat** (~25 min)  
  *Dependència*: `T032`  
  *Requisits Funcionals*: `FR-013`, `US5`  
  *Skill Mandatòria*: `security-and-hardening` ([`.agents/skills/security-and-hardening/SKILL.md`](file:///.agents/skills/security-and-hardening/SKILL.md))  
  *Eina MCP*: `postgres` (bloqueig `SELECT FOR UPDATE` i hash a la BD)  
  *Descripció*: Generació de factura oficial amb bloqueig `SELECT FOR UPDATE` de l'última factura emesa per calcular el hash encadenat SHA-256 inalterable.  
  **Hecho cuando:** La factura creada conté `hash_cadena_sha256` calculat a partir de les dades fiscals i del `hash_anterior_sha256`.  
  *Cadena de Test*:  
  `backend/.venv/bin/pytest backend/tests/test_051_factura_hash.py -v`

- [ ] **T034 [Backend/XML] Generador de Payload XML Veri*factu i Codi QR Tributari** (~25 min)  
  *Dependència*: `T033`  
  *Requisits Funcionals*: `FR-013`  
  *Skill Mandatòria*: `security-and-hardening` ([`.agents/skills/security-and-hardening/SKILL.md`](file:///.agents/skills/security-and-hardening/SKILL.md))  
  *Eina MCP*: `postgres` (emmagatzematge de payload XML)  
  *Descripció*: Generació del fitxer XML segons l'esquema reglamentari AEAT Veri*factu i càlcul de la URL signada per al codi QR de la factura.  
  **Hecho cuando:** `GET /api/v1/gestio/comptabilitat/factures/{id}/xml` retorna un XML vàlid amb capçalera i elements conformes a la normativa de l'Agència Tributària.  
  *Cadena de Test*:  
  `backend/.venv/bin/pytest backend/tests/test_052_xml_aeat.py -v`

- [ ] **T035 [Backend/Worker] Cua `queue_critical` per al Despatx AEAT (`processar_outbox_aeat`)** (~25 min)  
  *Dependència*: `T034`  
  *Requisits Funcionals*: `FR-013`  
  *Skill Mandatòria*: `systematic-debugging` ([`.agents/skills/systematic-debugging/SKILL.md`](file:///.agents/skills/systematic-debugging/SKILL.md))  
  *Eina MCP*: `postgres` (estat de la taula `outbox_enviaments_aeat`)  
  *Descripció*: Enviar la factura a la taula `outbox_enviaments_aeat` i despatxar-la asíncronament via Celery amb gestió de reintents exponencials.  
  **Hecho cuando:** La tasca Celery processa el registre outbox i marca l'estat com a `ENVIAT` registrant el timestamp d'acceptació.  
  *Cadena de Test*:  
  `backend/.venv/bin/pytest backend/tests/test_024_workers_aeat_backups.py -k "test_processar_outbox_aeat" -v`

- [ ] **T036 [Backend/API] Gestió de Factures Rectificatives Inalterables** (~20 min)  
  *Dependència*: `T033`  
  *Requisits Funcionals*: `FR-013`  
  *Skill Mandatòria*: `security-and-hardening` ([`.agents/skills/security-and-hardening/SKILL.md`](file:///.agents/skills/security-and-hardening/SKILL.md))  
  *Eina MCP*: `postgres` (relació de rectificativa a PostgreSQL)  
  *Descripció*: Endpoint per emetre factures rectificatives referenciant la factura rectificada, amb sèrie específica i motiu de rectificació tributari.  
  **Hecho cuando:** La factura rectificativa conté el camp `factura_rectificada_id` i s'encadena correctament a la cadena criptogràfica SHA-256.  
  *Cadena de Test*:  
  `backend/.venv/bin/pytest backend/tests/test_007_gestio_comptabilitat.py -k "test_factura_rectificativa" -v`

---

## 📈 Bloc 8: Panell Economics & Tresoreria (NOMÉS Boss)

- [ ] **T037 [Backend/RLS] Política RLS `economics_boss_only` a PostgreSQL** (~20 min)  
  *Dependència*: `T003`, `T033`  
  *Requisits Funcionals*: `FR-003`  
  *Skill Mandatòria*: `security-review` ([`.agents/skills/security-review/SKILL.md`](file:///.agents/skills/security-review/SKILL.md))  
  *Eina MCP*: `postgres` (test d'aïllament amb diferents usuaris i rols)  
  *Descripció*: Aplicar política RLS que garanteix a nivell de PostgreSQL que cap consulta de dades de rendibilitat empresarial o tresoreria pugui retornar files si el rol de l'usuari no és `BOSS`.  
  **Hecho cuando:** Una consulta `SELECT * FROM factures_capcalera` executada amb rol `ENGINYER` o `SECRETARIA` retorna exactament 0 files en els camps de marge brut.  
  *Cadena de Test*:  
  `backend/.venv/bin/pytest backend/tests/test_security_rbac.py -k "test_enginyer_cannot_access_financial_data" -v`

- [ ] **T038 [Backend/API] Panell de Tresoreria i Factures Impagades (`GET /tresoreria`)** (~25 min)  
  *Dependència*: `T037`  
  *Requisits Funcionals*: `FR-014`, `US10`  
  *Skill Mandatòria*: `security-review` ([`.agents/skills/security-review/SKILL.md`](file:///.agents/skills/security-review/SKILL.md))  
  *Eina MCP*: `postgres` (consultes de factures amb data de venciment passada)  
  *Descripció*: Endpoint de seguiment de tresoreria que calcula flux de caixa i destaca factures vençudes (>30 dies i >90 dies) per a reclamació de Secretaria/Direcció.  
  **Hecho cuando:** L'endpoint retorna el desglossament de factures vençudes correctament categoritzades per antiguitat (>30d, >90d).  
  *Cadena de Test*:  
  `backend/.venv/bin/pytest backend/tests/test_007_gestio_comptabilitat.py -k "test_tresoreria_impagades" -v`

- [ ] **T039 [Backend/API] KPIs Executius Boss: EBITDA, Marges, MRR i Previsió 90d** (~25 min)  
  *Dependència*: `T038`  
  *Requisits Funcionals*: `FR-003`, `US10`  
  *Skill Mandatòria*: `security-review` ([`.agents/skills/security-review/SKILL.md`](file:///.agents/skills/security-review/SKILL.md))  
  *Eina MCP*: `postgres` + `chrome-devtools` (auditoria de seguretat de dades en trànsit)  
  *Descripció*: Endpoint `GET /api/v1/gestio/economics/kpis` que consolida EBITDA, marge brut per feina, cost/hora d'operari, cost/km de flota, MRR de contractes i previsió de liquiditat a 30, 60 i 90 dies.  
  **Hecho cuando:** La petició feta per un `BOSS` retorna el paquet complet de mètriques financeres calculades i qualsevol altre rol rep HTTP 403.  
  *Cadena de Test*:  
  `backend/.venv/bin/pytest backend/tests/test_phase2_gestio.py -k "test_comptabilitat_dia0_i_veto_enginyer" -v`

---

## 📐 Bloc 9: Edició de Plànols GIS per Capes No Destructives

- [ ] **T040 [Backend/Model] Model de Biblioteca de Plànols (`carpetes`, `planols_base`, `capes`)** (~20 min)  
  *Dependència*: `T002`  
  *Requisits Funcionals*: `FR-015`  
  *Skill Mandatòria*: `supabase-postgres-best-practices` ([`.agents/skills/supabase-postgres-best-practices/SKILL.md`](file:///.agents/skills/supabase-postgres-best-practices/SKILL.md))  
  *Eina MCP*: `postgres` (verificació de taules de plànols i FKs)  
  *Descripció*: Estructurar la base documental de plànols per carpetes (per client/obra), plànol font original immutable i capes vectorials d'anotació abstractes.  
  **Hecho cuando:** La base de dades permet associar múltiples `capes_vectorials` a un mateix `planol_base` sense modificar el registre pare.  
  *Cadena de Test*:  
  `backend/.venv/bin/pytest backend/tests/test_010_gestio_planols.py -k "test_model_planols_capes" -v`

- [ ] **T041 [Backend/API] Càrrega Immutabilitzada de Plànols (`POST /planols/pujar`)** (~25 min)  
  *Dependència*: `T040`  
  *Requisits Funcionals*: `FR-015`, `SC-002`  
  *Skill Mandatòria*: `security-and-hardening` ([`.agents/skills/security-and-hardening/SKILL.md`](file:///.agents/skills/security-and-hardening/SKILL.md))  
  *Eina MCP*: `postgres` (comprovació de hash SHA-256 i volum local immutable)  
  *Descripció*: Endpoint de càrrega de fitxers de plànol (PDF, GeoJSON, DXF) que valida Magic Bytes, xifra el fitxer a `/docs/{empresa_id}/planols/` i el marca de només lectura.  
  **Hecho cuando:** El fitxer original queda desat amb permisos de lectura estricta i el seu hash sha256 és registrat a la base de dades.  
  *Cadena de Test*:  
  `backend/.venv/bin/pytest backend/tests/test_010_gestio_planols.py -k "test_pujar_planol_immutable" -v`

- [ ] **T042 [Backend/API] Gestió de Capes Vectorials d'Anotació No Destructiva** (~25 min)  
  *Dependència*: `T041`  
  *Requisits Funcionals*: `FR-015`, `US6`  
  *Skill Mandatòria*: `supabase-postgres-best-practices` ([`.agents/skills/supabase-postgres-best-practices/SKILL.md`](file:///.agents/skills/supabase-postgres-best-practices/SKILL.md))  
  *Eina MCP*: `postgres` (consulta de capes GeoJSON)  
  *Descripció*: Endpoints per desar noves capes de línies, canonades o cables (GeoJSON) vinculades a una feina, deixant el PDF original 100% incorrupte.  
  **Hecho cuando:** Crear una capa de traçat de canonada nova no modifica la data ni el contingut del plànol base original.  
  *Cadena de Test*:  
  `backend/.venv/bin/pytest backend/tests/test_010_gestio_planols.py -k "test_edicio_no_destructiva_capes" -v`

---

## 📑 Bloc 10: Pressupostos, Botó Triple & Conversió a OT

- [ ] **T043 [Backend/Model] Model de Pressupostos i Barema de Preus de l'Empresa** (~20 min)  
  *Dependència*: `T010`  
  *Requisits Funcionals*: `FR-017`, `US8`  
  *Skill Mandatòria*: `supabase-postgres-best-practices` ([`.agents/skills/supabase-postgres-best-practices/SKILL.md`](file:///.agents/skills/supabase-postgres-best-practices/SKILL.md))  
  *Eina MCP*: `postgres` (verificació de taula `pressupostos`)  
  *Descripció*: Model de pressupostos amb capçalera i línies desglossades calculades a partir del catàleg de preus oficial de l'empresa (mà d'obra, desplaçament, materials).  
  **Hecho cuando:** Un pressupost calcula la base imposable i l'IVA correctament basant-se en les tarifes de l'empresa.  
  *Cadena de Test*:  
  `backend/.venv/bin/pytest backend/tests/test_phase4_telegram_portal_eval.py -k "test_f4_04_enviar_pressupost_via_telegram_endpoint" -v`

- [ ] **T044 [Backend/AI] Servei de "Pressupost Intel·ligent" basat en Històric** (~25 min)  
  *Dependència*: `T043`  
  *Requisits Funcionals*: `US8`  
  *Skill Mandatòria*: `systematic-debugging` ([`.agents/skills/systematic-debugging/SKILL.md`](file:///.agents/skills/systematic-debugging/SKILL.md))  
  *Eina MCP*: `postgres` (consulta a històric d'ordres completades)  
  *Descripció*: Endpoint que proposa línies i preus estimats per a una feina consultant feines anteriors similars tancades de l'empresa.  
  **Hecho cuando:** La crida retorna l'esborrany de pressupost amb materials i hores suggerides basat en l'històric real de l'empresa.  
  *Cadena de Test*:  
  `backend/.venv/bin/pytest backend/tests/test_phase3_copilot_eval.py -k "test_f3_01_tool_calling_stock_real" -v`

- [ ] **T045 [Backend/Workflow] Acceptació de Pressupost i Conversió Automàtica a OT amb Picking** (~25 min)  
  *Dependència*: `T044`  
  *Requisits Funcionals*: `US8`  
  *Skill Mandatòria*: `supabase-postgres-best-practices` ([`.agents/skills/supabase-postgres-best-practices/SKILL.md`](file:///.agents/skills/supabase-postgres-best-practices/SKILL.md))  
  *Eina MCP*: `postgres` (transició d'estat a `APROVAT` i generació d'OT)  
  *Descripció*: En acceptar un pressupost (per signatura o token digital `TG-APROV-...`), commutar l'estat a `APROVAT` i crear l'Ordre de Treball amb la fulla de picking de materials pre-assignada.  
  **Hecho cuando:** El pressupost canvia a `APROVAT` i es crea automàticament l'OT amb els materials reservats a la taula `estocs_magatzem`.  
  *Cadena de Test*:  
  `backend/.venv/bin/pytest backend/tests/test_phase4_telegram_portal_eval.py -k "test_f4_01_aprovacio_pressupost_telegram" -v`

---

## 🤖 Bloc 11: Copilot IA, Notificacions Telegram & Incidències

- [ ] **T046 [Backend/API] Drawer d'Incidències Reactives de Camp (`/incidencies-drawer`)** (~20 min)  
  *Dependència*: `T010`  
  *Requisits Funcionals*: `US1`, `US7`  
  *Skill Mandatòria*: `frontend-design` ([`.agents/skills/frontend-design/SKILL.md`](file:///.agents/skills/frontend-design/SKILL.md))  
  *Eina MCP*: `postgres` + `chrome-devtools` (verificació de dades d'incidència al calaix)  
  *Descripció*: Endpoint que retorna les incidències obertes amb àudios, fotografies i pressupostos suggerits per al calaix lateral de la Torre de Control.  
  **Hecho cuando:** L'endpoint retorna les incidències amb la seva URL d'àudio i grau de severitat (`LLEU`, `MODERADA`, `URGENT_BLOQUEJANT`).  
  *Cadena de Test*:  
  `backend/.venv/bin/pytest backend/tests/test_016_operari_incidencies.py -k "test_llistar_incidencies_drawer" -v`

- [ ] **T047 [Backend/Telegram] Notificació d'Incidències cap al Telegram del Client (HITL)** (~25 min)  
  *Dependència*: `T046`  
  *Requisits Funcionals*: `FR-016`, `US7`  
  *Skill Mandatòria*: `security-and-hardening` ([`.agents/skills/security-and-hardening/SKILL.md`](file:///.agents/skills/security-and-hardening/SKILL.md))  
  *Eina MCP*: `postgres` (registre d'enviament a auditoria)  
  *Descripció*: Acció d'un sol clic des del dashboard que envia un avís amb el resum de l'avaria al client final pel seu canal de Telegram (prèvia confirmació humana).  
  **Hecho cuando:** El missatge s'encua i el bot de Telegram el transmet al `chat_id` del client vinculat.  
  *Cadena de Test*:  
  `backend/.venv/bin/pytest backend/tests/test_bot_telegram.py -k "test_enviament_alerta_incidencia" -v`

- [ ] **T048 [Backend/API] Validació HITL d'Imprevistos i Pressupostos Suggerits per IA** (~25 min)  
  *Dependència*: `T047`  
  *Requisits Funcionals*: `FR-016`, `US7`  
  *Skill Mandatòria*: `security-review` ([`.agents/skills/security-review/SKILL.md`](file:///.agents/skills/security-review/SKILL.md))  
  *Eina MCP*: `postgres` (actualització de costos d'OT)  
  *Descripció*: Endpoint `PATCH /api/v1/gestio/dashboard/incidencies/{id}/aprova-hitl` per autoritzar la despesa extraordinària abans d'incorporar-la a la feina.  
  **Hecho cuando:** El camp `aprovacio_hitl_supervisor` passa a `true` i s'actualitza la fulla de costos de l'ordre de treball.  
  *Cadena de Test*:  
  `backend/.venv/bin/pytest backend/tests/test_phase3_copilot_eval.py -k "test_f3_03_veto_financer" -v`

---

## ⚙️ Bloc 12: Configuració Empresa, Marca Camaleònica & Slots Laborals

- [ ] **T049 [Backend/API] Paràmetres Locals, Torns d'Estiu i Barema de Preus** (~20 min)  
  *Dependència*: `T002`  
  *Requisits Funcionals*: `FR-002`, `FR-017`  
  *Skill Mandatòria*: `supabase-postgres-best-practices` ([`.agents/skills/supabase-postgres-best-practices/SKILL.md`](file:///.agents/skills/supabase-postgres-best-practices/SKILL.md))  
  *Eina MCP*: `postgres` (mutació a taula `empreses`)  
  *Descripció*: Endpoints `GET` i `PUT /api/v1/gestio/configuracio/empresa` per a horaris de jornada habituals, configuració de torn intensiu d'estiu i catàleg de preus unitaris.  
  **Hecho cuando:** `PUT /api/v1/gestio/configuracio/empresa` actualitza el catàleg de preus i la nova tarifa s'aplica als nous pressupostos.  
  *Cadena de Test*:  
  `backend/.venv/bin/pytest backend/tests/test_011_configuracio_slots.py -v`

- [ ] **T050 [Backend/API] Actualització de Marca Camaleònica (NOMÉS Boss)** (~20 min)  
  *Dependència*: `T049`  
  *Requisits Funcionals*: `FR-002`  
  *Skill Mandatòria*: `frontend-design` ([`.agents/skills/frontend-design/SKILL.md`](file:///.agents/skills/frontend-design/SKILL.md))  
  *Eina MCP*: `postgres` + `chrome-devtools` (verificació de valors HSL i renderitzat visual)  
  *Descripció*: Endpoint `PUT /api/v1/gestio/configuracio/marca` reservat a Boss per modificar els colors primari/secundari en format HSL i carregar el logotip oficial.  
  **Hecho cuando:** Els nous valors HSL es guarden a la taula `empreses` i un enginyer rep HTTP 403 si intenta modificar-los.  
  *Cadena de Test*:  
  `backend/.venv/bin/pytest backend/tests/test_phase3_operari.py -k "test_intervencions_actives_gis_i_marca" -v`

---

## 🖥️ Bloc 13: Frontend Dashboard Next.js 14 & Chameleon UI

- [ ] **T051 [Frontend/CSS] Injecció de Variables HSL Dinàmiques al Shell Corporatiu** (~25 min)  
  *Dependència*: `T050`  
  *Requisits Funcionals*: `FR-002`  
  *Skill Mandatòria*: `frontend-design` ([`.agents/skills/frontend-design/SKILL.md`](file:///.agents/skills/frontend-design/SKILL.md))  
  *Eina MCP*: `chrome-devtools` (inspecció de variables `:root` CSS al DOM)  
  *Descripció*: Configurar `pwa/src/app/gestio/layout.tsx` perquè rebi els colors del tenant des de l'API i els injecti al `:root` (`--color-primary`, `--color-secondary`), sense colors hardcodejats a Tailwind.  
  **Hecho cuando:** El DOM conté les propietats d'estil CSS HSL corresponents al tenant actiu verificant-ho per inspecció de consola.  
  *Cadena de Test*:  
  `npm --prefix pwa run lint && npm --prefix pwa run build`

- [ ] **T052 [Frontend/UI] Panell HUD amb 6 KPIs i Drawer d'Incidències (Zero Mock Data)** (~25 min)  
  *Dependència*: `T013`, `T046`, `T051`  
  *Requisits Funcionals*: `FR-018`, `US1`  
  *Skill Mandatòria*: `frontend-design` ([`.agents/skills/frontend-design/SKILL.md`](file:///.agents/skills/frontend-design/SKILL.md))  
  *Eina MCP*: `chrome-devtools` (comprovació visual d'Empty States i dades reals)  
  *Descripció*: Maquetar `pwa/src/app/gestio/page.tsx` mostrant els 6 KPIs de camp reals i el calaix desplegable d'incidències, amb Empty State natiu si no hi ha dades.  
  **Hecho cuando:** La pàgina renderitza els 6 blocs KPI consumint dades reals de `/api/v1/gestio/dashboard/hud` sense elements ficticis.  
  *Cadena de Test*:  
  `npm --prefix pwa run build`

- [ ] **T053 [Frontend/GIS] Mapa Cartogràfic Interactiu amb Drop & Go** (~25 min)  
  *Dependència*: `T011`, `T012`, `T052`  
  *Requisits Funcionals*: `FR-005`, `US1`  
  *Skill Mandatòria*: `frontend-design` ([`.agents/skills/frontend-design/SKILL.md`](file:///.agents/skills/frontend-design/SKILL.md))  
  *Eina MCP*: `chrome-devtools` (interacció d'arrossegament drag & drop de marcadors)  
  *Descripció*: Component `pwa/src/components/gestio/Map.tsx` que renderitza el mapa Leaflet/MapLibre amb les feines del dia, permetent moure una feina a una altra colla (Drop & Go).  
  **Hecho cuando:** L'arrossegament d'un marcador de feina dispara la crida `PATCH /drop-and-go` i actualitza visualment la posició al mapa.  
  *Cadena de Test*:  
  `npm --prefix pwa run build`

- [ ] **T054 [Frontend/UI] Modal de Creació d'OT amb Botó Triple** (~25 min)  
  *Dependència*: `T045`, `T053`  
  *Requisits Funcionals*: `US8`  
  *Skill Mandatòria*: `frontend-design` ([`.agents/skills/frontend-design/SKILL.md`](file:///.agents/skills/frontend-design/SKILL.md))  
  *Eina MCP*: `chrome-devtools` (interacció amb modal i formulari)  
  *Descripció*: Crear `pwa/src/components/gestio/CrearOTModal.tsx` amb els 3 botons: `[Generar Tasca]`, `[Generar Pressupost]` i `[✨ Pressupost Intel·ligent]`.  
  **Hecho cuando:** Cada botó executa la seva acció corresponent (creació directa, formulari econòmic manual o proposta per IA).  
  *Cadena de Test*:  
  `npm --prefix pwa run build`

- [ ] **T055 [Frontend/UI] Pantalla Exclusiva de Tauler Economics (Boss Only)** (~25 min)  
  *Dependència*: `T039`, `T051`  
  *Requisits Funcionals*: `FR-003`, `US10`  
  *Skill Mandatòria*: `security-review` ([`.agents/skills/security-review/SKILL.md`](file:///.agents/skills/security-review/SKILL.md)) + `frontend-design` ([`.agents/skills/frontend-design/SKILL.md`](file:///.agents/skills/frontend-design/SKILL.md))  
  *Eina MCP*: `chrome-devtools` (verificació de bloqueig visual per rol)  
  *Descripció*: Maquetar la vista `/gestio/comptabilitat` (o `/gestio/economics`) mostrant gràfiques d'EBITDA, tresoreria 90d i factures vençudes, amb rebuig visual a altres rols.  
  **Hecho cuando:** Un usuari amb rol `BOSS` visualitza els KPIs financers i un usuari amb rol `ENGINYER` veu l'avís d'accés denegat sense que cap dada viatgi pel wire.  
  *Cadena de Test*:  
  `npm --prefix pwa run build`

---

## 🏆 Bloc 14: Cadena d'Auditoria Zero Mock & Verificació Final

- [ ] **T056 [QA/Pytest] Execució de la Suite Completa de Tests de Backoffice Gestió** (~25 min)  
  *Dependència*: `T001` fins a `T050`  
  *Requisits Funcionals*: `FR-001`  
  *Skill Mandatòria*: `systematic-debugging` ([`.agents/skills/systematic-debugging/SKILL.md`](file:///.agents/skills/systematic-debugging/SKILL.md))  
  *Eina MCP*: `postgres` (aïllament RLS certificat)  
  *Descripció*: Llançar tots els tests automatitzats de gestió amb aïllament RLS, comprovant 100% netedat, absència de warnings d'event loop i zero dades sintètiques.  
  **Hecho cuando:** La suite completa de gestió passa amb èxit (`100% passed`) sense cap omissió ni fals positiu.  
  *Cadena de Test*:  
  `backend/.venv/bin/pytest backend/tests/test_phase2_gestio.py backend/tests/test_phase2_torre_control_eval.py backend/tests/test_002_gestio_clients.py backend/tests/test_004_gestio_magatzem.py backend/tests/test_005_gestio_feines.py backend/tests/test_006_gestio_flota.py backend/tests/test_007_gestio_comptabilitat.py backend/tests/test_008_gestio_operaris.py -v`

- [ ] **T057 [QA/MCP] Verificació en Viu amb Chrome DevTools MCP (Login, OTs i Albarans)** (~25 min)  
  *Dependència*: `T051` fins a `T055`, `T056`  
  *Requisits Funcionals*: `FR-001`  
  *Skill Mandatòria*: `security-review` ([`.agents/skills/security-review/SKILL.md`](file:///.agents/skills/security-review/SKILL.md))  
  *Eina MCP*: `chrome-devtools` (navegació real, trànsit de xarxa i screenshots)  
  *Descripció*: Executar una auditoria en viu amb l'eina MCP `chrome-devtools`: login de gestió real, creació d'una OT sobre el mapa, pujada d'albarà real des de `/demo_docs` i presa de captura d'evidència (`take_screenshot`).  
  **Hecho cuando:** `chrome-devtools` inspecciona el trànsit de xarxa en viu confirmant que tots els endpoints retornen HTTP 200/201 contra FastAPI sense errors a la consola (`list_console_messages`).  
  *Cadena de Test*:  
  `mcp_chrome-devtools_navigate_page` + `mcp_chrome-devtools_list_console_messages`

- [ ] **T058 [QA/MCP] Auditoria de Persistència Física a PostgreSQL viu amb MCP `postgres`** (~20 min)  
  *Dependència*: `T056`, `T057`  
  *Requisits Funcionals*: `FR-001`  
  *Skill Mandatòria*: `supabase-postgres-best-practices` ([`.agents/skills/supabase-postgres-best-practices/SKILL.md`](file:///.agents/skills/supabase-postgres-best-practices/SKILL.md))  
  *Eina MCP*: `postgres` (consultes SQL d'auditoria Zero Mock)  
  *Descripció*: Utilitzar `postgres.query` per certificar la inserció física de les entitats creades en viu i validar la política RLS executant consultes amb `SET LOCAL app.current_empresa_id = :id`.  
  **Hecho cuando:** La consulta SQL retorna els registres creats durant la prova i confirma l'aïllament creuat davant un segon tenant buit.  
  *Cadena de Test*:  
  `mcp_postgres_query` amb `SELECT count(*) FROM ordres_treball WHERE empresa_id = '...'`
