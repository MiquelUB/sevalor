# Tasks: Frontline Operaris (Spec 02) — Microtasques < 30 minuts

**Feature Path**: `specs/02-frontline-operaris`  
**Prerequisites**: `spec.md`, `plan.md`, `constitution.md`, `AGENTS.md`  
**Norma Suprema**: Zero Mock Data, Offline-First criptogràfic (AES-GCM Web Crypto API), aprovació 100% neta de tests.  
**Criteri de Granularitat**: Totes les tasques estan estrictament acotades a una durada estimada **< 30 minuts**, ordenades per dependència lògica descendent, amb **Skill mandatoria** i **Eina MCP** associades.

---

## 🔐 Bloc 1: Criptografia Offline, Magatzem Local i Model de Dades

- [x] **T001 [Backend/DB] Taules d'Operaris i Polítiques RLS a PostgreSQL** (~25 min)  
  *Dependència*: Cap  
  *Requisits Funcionals*: `FR-001`, `FR-003`  
  *Skill Mandatòria*: `supabase-postgres-best-practices` ([`.agents/skills/supabase-postgres-best-practices/SKILL.md`](file:///.agents/skills/supabase-postgres-best-practices/SKILL.md))  
  *Eina MCP*: `postgres` (verificació en viu d'esquema)  
  *Descripció*: Modelar i aplicar `FORCE ROW LEVEL SECURITY` per a `usuaris` (amb camps `pin_hash`, `intents_pin_fallits`, `pin_bloquejat`), `registres_jornada_laboral`, `ordres_treball`, `fulles_picking`, `linies_picking` i `incidencies`.  
  **Hecho cuando:** La consulta `SELECT relrowsecurity, relforcerowsecurity FROM pg_class WHERE relname = 'usuaris'` retorna `(true, true)` a la base de dades activa.  
  *Cadena de Test*:  
  `backend/.venv/bin/pytest backend/tests/test_rls.py backend/tests/test_019_operari_login.py -k "test_login_tenant_isolation" -v`

- [x] **T002 [Frontend/Crypto] Mòdul Criptogràfic Web Crypto API (PBKDF2 + AES-GCM 256)** (~25 min)  
  *Dependència*: `T001`  
  *Requisits Funcionals*: `FR-002`, `FR-003`  
  *Skill Mandatòria*: `security-and-hardening` ([`.agents/skills/security-and-hardening/SKILL.md`](file:///.agents/skills/security-and-hardening/SKILL.md))  
  *Eina MCP*: `chrome-devtools` (inspecció de context de seguretat criptogràfica)  
  *Descripció*: Implementar `pwa/src/lib/offline/crypto.ts` derivant la clau mestra mitjançant `PBKDF2` (100.000 iteracions, SHA-256) del PIN de 4 dígits de l'operari i xifrant el payload en `AES-GCM` de 256 bits amb salt únic per dispositiu.  
  **Hecho cuando:** La funció `deriveMasterKeyFromPin("1234", salt)` genera una clau `CryptoKey` no exportable i xifra un buffer de text retornant ciphertext i IV diferents a cada execució.  
  *Cadena de Test*:  
  `npm --prefix pwa run lint && npm --prefix pwa test -- tests/crypto.test.ts 2>/dev/null || npm --prefix pwa run build`

- [x] **T003 [Frontend/Crypto] Sentinel de Validació de PIN Offline a IndexedDB** (~20 min)  
  *Dependència*: `T002`  
  *Requisits Funcionals*: `FR-002`, `FR-003`  
  *Skill Mandatòria*: `security-and-hardening` ([`.agents/skills/security-and-hardening/SKILL.md`](file:///.agents/skills/security-and-hardening/SKILL.md))  
  *Eina MCP*: `chrome-devtools` (verificació d'IndexedDB)  
  *Descripció*: Crear el mecanisme de validació offline mitjançant un bloc xifrat de referència (`"SEVALOR_SENTINEL"`). Si el PIN introduït desxifra correctament aquest bloc amb `AES-GCM`, el PIN es dóna per vàlid sense contactar amb la xarxa.  
  **Hecho cuando:** `verifyPinOffline("1234")` retorna `true` quan el PIN és correcte i llança excepció criptogràfica (retornant `false`) si el PIN és incorrecte, sense filtrar cap clau a disc.  
  *Cadena de Test*:  
  `npm --prefix pwa run build`

- [x] **T004 [Frontend/DB] Esquema Dexie.js amb Taules Xifrades a IndexedDB** (~20 min)  
  *Dependència*: `T003`  
  *Requisits Funcionals*: `FR-001`, `FR-002`  
  *Skill Mandatòria*: `security-review` ([`.agents/skills/security-review/SKILL.md`](file:///.agents/skills/security-review/SKILL.md))  
  *Eina MCP*: `chrome-devtools` (inspecció d'Application Storage)  
  *Descripció*: Definir `SevalorLocalDatabase` a `pwa/src/lib/offline/db.ts` amb les taules `ordres`, `tiquets`, `incidencies`, `fichajes` i `sync_queue`. Prohibició expressa d'emmagatzemar tokens JWT o credencials en text pla a `localStorage`.  
  **Hecho cuando:** La inspecció de `localStorage` al navegador no conté cap token JWT o PIN, i les taules d'IndexedDB s'obren exclusivament en sessió desxifrada.  
  *Cadena de Test*:  
  `npm --prefix pwa run build`

---

## 🌅 Bloc 2: User Story 1 - Autenticació DNI + PIN i Morning Briefing Seqüencial

- [x] **T005 [Backend/Auth] Endpoint d'Enrolament Inicial de Dispositiu (DNI + Codi)** (~25 min)  
  *Dependència*: `T001`  
  *Requisits Funcionals*: `FR-003`, `SC-001`  
  *Skill Mandatòria*: `security-and-hardening` ([`.agents/skills/security-and-hardening/SKILL.md`](file:///.agents/skills/security-and-hardening/SKILL.md))  
  *Eina MCP*: `postgres` (verificació de codi d'activació i operari)  
  *Descripció*: Endpoint `POST /api/v1/operari_auth/enrolar` que valida DNI + codi d'activació facilitat per l'empresa (sense SMS), genera el salt local i retorna les metadades de l'operari per a inicialització offline.  
  **Hecho cuando:** La crida amb DNI i codi d'activació vàlids retorna HTTP 200 amb el `dispositiu_salt` i estableix el PIN inicial de 4 dígits de l'operari.  
  *Cadena de Test*:  
  `backend/.venv/bin/pytest backend/tests/test_019_operari_login.py -k "test_login_operari_valid" -v`

- [x] **T006 [Backend/Auth] Endpoint de Login per PIN amb Rate Limiting (`SlowAPI`)** (~20 min)  
  *Dependència*: `T005`  
  *Requisits Funcionals*: `FR-003`, `SC-001`  
  *Skill Mandatòria*: `security-and-hardening` ([`.agents/skills/security-and-hardening/SKILL.md`](file:///.agents/skills/security-and-hardening/SKILL.md))  
  *Eina MCP*: `chrome-devtools` (comprovació de capçaleres i cookies)  
  *Descripció*: Endpoint `POST /api/v1/operari_auth/login` que rep DNI i PIN de 4 dígits, aplica rate limiting estricte (màx. 5 intents/minut) i bloqueja el compte (`pin_bloquejat = true`) al cinquè intent fallit consecutiu.  
  **Hecho cuando:** Cinc intents erronis consecutius de PIN retornen HTTP 429 / 403 i deixen l'usuari amb `pin_bloquejat = true` a la base de dades.  
  *Cadena de Test*:  
  `backend/.venv/bin/pytest backend/tests/test_019_operari_login.py -k "test_login_operari_pin_incorrecte_i_bloqueig" -v`

- [x] **T007 [Frontend/UI] Numpad Tàctil i Pantalla de Login Offline a la PWA** (~25 min)  
  *Dependència*: `T003`, `T006`  
  *Requisits Funcionals*: `FR-001`, `FR-003`, `SC-001`  
  *Skill Mandatòria*: `frontend-design` ([`.agents/skills/frontend-design/SKILL.md`](file:///.agents/skills/frontend-design/SKILL.md))  
  *Eina MCP*: `chrome-devtools` (interacció de clic al numpad i screenshot)  
  *Descripció*: Dissenyar `pwa/src/app/operari/login/page.tsx` amb un teclat numèric tàctil gran (Numpad) optimitzat per a guants de treball, pantalla d'introducció de PIN de 4 dígits i verificació híbrida (offline sentinel si no hi ha xarxa, o backend si online).  
  **Hecho cuando:** La pulsació dels 4 dígits al teclat desbloqueja la PWA en <1 segon i redirigeix automàticament a `/operari` sense necessitat de prémer botó 'Entrar'.  
  *Cadena de Test*:  
  `npm --prefix pwa run build`

- [x] **T008 [Backend/API] Endpoint de Fitxatge d'Inici de Torn amb GPS Obligatori** (~25 min)  
  *Dependència*: `T001`, `T006`  
  *Requisits Funcionals*: `FR-004`, `FR-007`  
  *Skill Mandatòria*: `supabase-postgres-best-practices` ([`.agents/skills/supabase-postgres-best-practices/SKILL.md`](file:///.agents/skills/supabase-postgres-best-practices/SKILL.md))  
  *Eina MCP*: `postgres` (consulta a `registres_jornada_laboral`)  
  *Descripció*: Endpoint `POST /api/v1/operari/jornada/inici` que exigeix `latitud`, `longitud` i timestamp UTC, creant un registre amb estat `EN_CURS`.  
  **Hecho cuando:** Una crida sense coordenades GPS retorna HTTP 422 Unprocessable Entity, i amb coordenades persisteix el registre retornant HTTP 201.  
  *Cadena de Test*:  
  `backend/.venv/bin/pytest backend/tests/test_phase1_operari_pwa_eval.py -k "test_f1_02_fitxatge_gps_i_timestamp" -v`

- [x] **T009 [Backend/API] Odòmetre Inicial i Checklist Visual del Vehicle** (~25 min)  
  *Dependència*: `T008`  
  *Requisits Funcionals*: `FR-007`, `US1`  
  *Skill Mandatòria*: `supabase-postgres-best-practices` ([`.agents/skills/supabase-postgres-best-practices/SKILL.md`](file:///.agents/skills/supabase-postgres-best-practices/SKILL.md))  
  *Eina MCP*: `postgres` (verificació de quilometratge del vehicle)  
  *Descripció*: Endpoint `POST /api/v1/operari/jornada/{id}/vehicle` que vincula el vehicle assignat, registra l'odòmetre d'inici i valida que el quilometratge sigui estrictament igual o superior a l'acumulat anterior.  
  **Hecho cuando:** El registre vincula el `vehicle_id` i rebutja un valor d'odòmetre inferior a l'últim conegut amb HTTP 400 Bad Request.  
  *Cadena de Test*:  
  `backend/.venv/bin/pytest backend/tests/test_015_operari_vehicles_rutines.py -k "test_checkin_odometre" -v`

- [x] **T010 [Frontend/UI] Pas 1 & 2 Morning Briefing: Fitxatge GPS i Checklist Vehicle** (~25 min)  
  *Dependència*: `T007`, `T008`, `T009`  
  *Requisits Funcionals*: `FR-004`, `US1`  
  *Skill Mandatòria*: `frontend-design` ([`.agents/skills/frontend-design/SKILL.md`](file:///.agents/skills/frontend-design/SKILL.md))  
  *Eina MCP*: `chrome-devtools` (captura de flux visual i geolocalització)  
  *Descripció*: Crear el flux seqüencial de passos a la PWA (`pwa/src/components/operari/MorningBriefing.tsx`) que demana fitxar amb geolocalització del dispositiu i posteriorment fotografia de l'odòmetre i semàfor visual d'estat del vehicle.  
  **Hecho cuando:** L'operari completa el fitxatge i el checklist del vehicle avançant automàticament al Pas 3 (Resum de tasques).  
  *Cadena de Test*:  
  `npm --prefix pwa run build`

- [x] **T011 [Backend/API] Resum de Feines Assignades i Empty State Dia-0** (~20 min)  
  *Dependència*: `T001`  
  *Requisits Funcionals*: `FR-001`, `US1`  
  *Skill Mandatòria*: `supabase-postgres-best-practices` ([`.agents/skills/supabase-postgres-best-practices/SKILL.md`](file:///.agents/skills/supabase-postgres-best-practices/SKILL.md))  
  *Eina MCP*: `postgres` (auditoria de resposta en taula buida)  
  *Descripció*: Endpoint `GET /api/v1/operari/feines` que retorna les tasques planificades per al dia de l'operari autenticat. Si no en té cap, retorna `[]` netament (sense dades de prova ni sintètiques).  
  **Hecho cuando:** Un operari sense feines rep `HTTP 200 []` i la UI renderitza l'Empty State honest ("Cap tasca assignada avui") sense dades hardcodejades.  
  *Cadena de Test*:  
  `backend/.venv/bin/pytest backend/tests/test_phase1_operari_pwa_eval.py -k "test_f1_03_empty_state_dia0" -v`

- [x] **T012 [Backend/API] Fulla de Picking d'Entrada (Pick In) cap a Furgoneta** (~25 min)  
  *Dependència*: `T011`  
  *Requisits Funcionals*: `US1`  
  *Skill Mandatòria*: `supabase-postgres-best-practices` ([`.agents/skills/supabase-postgres-best-practices/SKILL.md`](file:///.agents/skills/supabase-postgres-best-practices/SKILL.md))  
  *Eina MCP*: `postgres` (consulta a `linies_picking`)  
  *Descripció*: Endpoints `POST /api/v1/operari/picking` i `PUT /api/v1/operari/picking/linies/{id}` per confirmar la càrrega de materials (Pick In) a la furgoneta abans de sortir cap a l'obra.  
  **Hecho cuando:** L'estat del picking passa a `PICK_IN_CONFIRMAT` registrant la quantitat carregada per cada línia de material.  
  *Cadena de Test*:  
  `backend/.venv/bin/pytest backend/tests/test_014_operari_picking.py -k "test_picking_pick_in_confirmacio" -v`

- [x] **T013 [Frontend/UI] Pas 3 & 4 Morning Briefing: Resum de Tasca i Pick In Guiat** (~25 min)  
  *Dependència*: `T010`, `T011`, `T012`  
  *Requisits Funcionals*: `FR-001`, `US1`  
  *Skill Mandatòria*: `frontend-design` ([`.agents/skills/frontend-design/SKILL.md`](file:///.agents/skills/frontend-design/SKILL.md))  
  *Eina MCP*: `chrome-devtools` (interacció amb llista de picking i Empty State)  
  *Descripció*: Implementar a la PWA el resum visual de la primera ordre de treball (client, adreça, botó de navegació GPS) i la llista de verificació de materials amb botó 'Confirmar Càrrega a Furgoneta'.  
  **Hecho cuando:** La confirmació del Pick In tanca satisfactòriament el cicle de Morning Briefing situant l'operari al panell principal d'obra.  
  *Cadena de Test*:  
  `npm --prefix pwa run build`

---

## 📷 Bloc 3: User Story 2 - Execució de Feines & Protocol de Qualitat 3-Fases

- [ ] **T014 [Frontend/Media] Càmera Tècnica HTML5 (`CameraCapture.tsx`) amb Bloqueig de Galeria** (~25 min)  
  *Dependència*: `T004`  
  *Requisits Funcionals*: `FR-006`  
  *Skill Mandatòria*: `security-and-hardening` ([`.agents/skills/security-and-hardening/SKILL.md`](file:///.agents/skills/security-and-hardening/SKILL.md))  
  *Eina MCP*: `chrome-devtools` (inspecció de MediaDevices)  
  *Descripció*: Component `pwa/src/components/operari/CameraCapture.tsx` que accedeix exclusivament a `navigator.mediaDevices.getUserMedia({ video: { facingMode: "environment" } })` sobre un `<video>` i `<canvas>`, prohibint explícitament `<input type="file">` per evitar pujades de fotos des de la galeria.  
  **Hecho cuando:** El component no conté cap input de tipus file i obté el fotograma directament del flux del sensor de la càmera en viu.  
  *Cadena de Test*:  
  `npm --prefix pwa run build`

- [x] **T015 [Frontend/Service] Compressió d'Imatge WebP al Client (< 1 MB) i Metadades GPS** (~20 min)  
  *Dependència*: `T014`  
  *Requisits Funcionals*: `FR-007`, `FR-012`  
  *Skill Mandatòria*: `frontend-design` ([`.agents/skills/frontend-design/SKILL.md`](file:///.agents/skills/frontend-design/SKILL.md))  
  *Eina MCP*: `chrome-devtools` (anàlisi de pes de fitxer a memòria)  
  *Descripció*: Funció de processament que redueix el fotograma a format WebP garantint mida inferior a 1 MB, preservant la resolució necessària per llegir números de sèrie i incrustant les coordenades GPS de captura.  
  **Hecho cuando:** El blob resultant té mida `< 1.000.000 bytes` i conté la latitud/longitud obtinguda de `navigator.geolocation`.  
  *Cadena de Test*:  
  `npm --prefix pwa run build`

- [x] **T016 [Backend/Workflow] Iniciar Trajecte i Estat Blau (`PUT /iniciar-trajecte`)** (~20 min)  
  *Dependència*: `T001`  
  *Requisits Funcionals*: `US2`  
  *Skill Mandatòria*: `supabase-postgres-best-practices` ([`.agents/skills/supabase-postgres-best-practices/SKILL.md`](file:///.agents/skills/supabase-postgres-best-practices/SKILL.md))  
  *Eina MCP*: `postgres` (verificació d'estat a `ordres_treball`)  
  *Descripció*: Endpoint `PUT /api/v1/operari/feines/{id}/iniciar-trajecte` que commuta l'estat de la feina a `EN_TRANSIT` (estat Blau al mapa de la Torre de Control) i assigna temps estimat d'arribada (ETA).  
  **Hecho cuando:** La crida commuta l'estat de la feina a `EN_TRANSIT` i emet l'esdeveniment corresponent.  
  *Cadena de Test*:  
  `backend/.venv/bin/pytest backend/tests/test_phase1_operari_pwa_eval.py -k "test_f1_06_iniciar_trajecte_i_geovalla" -v`

- [x] **T017 [Backend/Workflow] Començar Feina amb Geovalla de 50 metres (`PUT /comencar`)** (~25 min)  
  *Dependència*: `T016`  
  *Requisits Funcionals*: `FR-004`, `US2`  
  *Skill Mandatòria*: `supabase-postgres-best-practices` ([`.agents/skills/supabase-postgres-best-practices/SKILL.md`](file:///.agents/skills/supabase-postgres-best-practices/SKILL.md))  
  *Eina MCP*: `postgres` (càlcul de distància geodèsica)  
  *Descripció*: Endpoint `PUT /api/v1/operari/feines/{id}/comencar` que compara les coordenades de l'operari amb les de la finca aplicant fórmula Haversine: si supera 50 metres de distància, exigeix el flag `desviacio_ubicacio = true` amb motiu justificatiu.  
  **Hecho cuando:** Un intent d'inici a 500m sense justificació retorna HTTP 409 Geovalla, i dins del radi de 50m inicia el comptador de la feina (`EN_CURS`).  
  *Cadena de Test*:  
  `backend/.venv/bin/pytest backend/tests/test_phase1_operari_pwa_eval.py -k "test_f1_06_iniciar_trajecte_i_geovalla" -v`

- [x] **T018 [Backend/API] Càrrega Segura de Fotos QA (`POST /feines/{id}/fotos`)** (~25 min)  
  *Dependència*: `T017`  
  *Requisits Funcionals*: `FR-005`, `FR-007`  
  *Skill Mandatòria*: `security-and-hardening` ([`.agents/skills/security-and-hardening/SKILL.md`](file:///.agents/skills/security-and-hardening/SKILL.md))  
  *Eina MCP*: `postgres` (registre de camí de foto a PostgreSQL)  
  *Descripció*: Endpoint multipart/form-data que valida Magic Bytes (`filetype`), xifra la foto a `/data/{empresa_id}/feines/{id}/` amb UUID v4 i registra la fase (`INICIAL`, `INTERMEDIA`, `FINAL`) i les coordenades GPS.  
  **Hecho cuando:** La pujada d'una foto WebP/JPEG vàlida es desa amb nom UUID i s'associa a la fase corresponent de la feina.  
  *Cadena de Test*:  
  `backend/.venv/bin/pytest backend/tests/test_phase1_operari_pwa_eval.py -k "test_f1_04_protocol_3_fotos_i_bloqueig" -v`

- [x] **T019 [Backend/Workflow] Bloqueig Estricte de Tancament d'OT sense les 3 Fotos Obligatòries** (~20 min)  
  *Dependència*: `T018`  
  *Requisits Funcionals*: `FR-005`, `SC-003`  
  *Skill Mandatòria*: `supabase-postgres-best-practices` ([`.agents/skills/supabase-postgres-best-practices/SKILL.md`](file:///.agents/skills/supabase-postgres-best-practices/SKILL.md))  
  *Eina MCP*: `postgres` (comprovació de bloqueig de finalització)  
  *Descripció*: A `PUT /api/v1/operari/feines/{id}/finalitzar`, verificar que la feina disposa de com a mínim 1 foto `INICIAL`, 1 `INTERMEDIA` i 1 `FINAL`. Si en manca alguna, denegar el tancament amb HTTP 400 Bad Request.  
  **Hecho cuando:** L'intent de finalitzar una feina amb 2 fotos retorna `HTTP 400 { "detail": "Manca foto obligatòria: FINAL" }`, i amb les 3 fotos commuta a `FINALITZADA`.  
  *Cadena de Test*:  
  `backend/.venv/bin/pytest backend/tests/test_phase1_operari_pwa_eval.py -k "test_f1_04_protocol_3_fotos_i_bloqueig" -v`

- [x] **T020 [Frontend/UI] Pantalla d'Obra en Curs i Semàfor de les 3 Fotos QA** (~25 min)  
  *Dependència*: `T014`, `T015`, `T019`  
  *Requisits Funcionals*: `FR-005`, `US2`  
  *Skill Mandatòria*: `frontend-design` ([`.agents/skills/frontend-design/SKILL.md`](file:///.agents/skills/frontend-design/SKILL.md))  
  *Eina MCP*: `chrome-devtools` (renderitzat del semàfor visual de fotos)  
  *Descripció*: Pantalla `/operari/feines/[id]` amb cronòmetre en viu, targeta d'ubicació i 3 caselles d'estat de fotos (Abans [Verd/Vermell], Durant [Verd/Vermell], Després [Verd/Vermell]), amb el botó 'Finalitzar Feina' desactivat fins a completar les 3.  
  **Hecho cuando:** El botó de finalització roman inhabilitat visualment i funcionalment fins que les 3 caselles de fotos estan validades en verd.  
  *Cadena de Test*:  
  `npm --prefix pwa run build`

---

## 🌆 Bloc 4: User Story 3 - Evening Checkout Guiat

- [x] **T021 [Backend/API] Pick Out de Retorn i Balanç Matemàtic de Materials** (~25 min)  
  *Dependència*: `T012`  
  *Requisits Funcionals*: `US3`, `SC-005`  
  *Skill Mandatòria*: `supabase-postgres-best-practices` ([`.agents/skills/supabase-postgres-best-practices/SKILL.md`](file:///.agents/skills/supabase-postgres-best-practices/SKILL.md))  
  *Eina MCP*: `postgres` (comprovació de la igualtat aritmètica a la BD)  
  *Descripció*: Endpoint de registre de Pick Out que computa el balanç de materials: `Quantitat Carregada (Pick In) = Consum Real a Obra + Quantitat Retornada (Pick Out) + Merma`. Si hi ha desviació sense justificar, aixeca alerta de reconciliació.  
  **Hecho cuando:** La crida valida la coherència aritmètica del balanç de materials i incrementa l'estoc del magatzem central amb el material retornat.  
  *Cadena de Test*:  
  `backend/.venv/bin/pytest backend/tests/test_phase1_operari_pwa_eval.py -k "test_f1_05_balanc_materials_picking" -v`

- [x] **T022 [Backend/API] Odòmetre Final i Quilometratge Net del Dia** (~20 min)  
  *Dependència*: `T009`  
  *Requisits Funcionals*: `FR-007`, `US3`  
  *Skill Mandatòria*: `supabase-postgres-best-practices` ([`.agents/skills/supabase-postgres-best-practices/SKILL.md`](file:///.agents/skills/supabase-postgres-best-practices/SKILL.md))  
  *Eina MCP*: `postgres` (actualització de quilòmetres acumulats)  
  *Descripció*: Endpoint `POST /api/v1/operari/vehicles/{id}/checkout` que rep la fotografia de l'odòmetre del final del dia, valida que sigui superior a l'odòmetre d'inici i registra els km nets recorreguts durant la jornada.  
  **Hecho cuando:** El vehicle actualitza el seu `odometre_acumulat` i queda desat el total de km fets durant la jornada de l'operari.  
  *Cadena de Test*:  
  `backend/.venv/bin/pytest backend/tests/test_015_operari_vehicles_rutines.py -k "test_checkout_odometre_final" -v`

- [x] **T023 [Backend/API] Resum de Tiquets del Dia i Confirmació de Custòdia de Paper** (~20 min)  
  *Dependència*: `T001`  
  *Requisits Funcionals*: `FR-009`, `US3`  
  *Skill Mandatòria*: `supabase-postgres-best-practices` ([`.agents/skills/supabase-postgres-best-practices/SKILL.md`](file:///.agents/skills/supabase-postgres-best-practices/SKILL.md))  
  *Eina MCP*: `postgres` (actualització d'estat de custòdia de tiquets)  
  *Descripció*: Endpoint de consolidació d'Evening Checkout que presenta els tiquets capturats durant el dia i exigeix la confirmació booleana `custodia_paper_confirmada = true` per part de l'operari abans de finalitzar la jornada.  
  **Hecho cuando:** El camp `custodia_paper_confirmada` de tots els tiquets de la jornada queda marcat a `true`.  
  *Cadena de Test*:  
  `backend/.venv/bin/pytest backend/tests/test_018_operari_tiquets_ocr.py -k "test_confirmar_custodia_paper" -v`

- [x] **T024 [Backend/API] Fitxatge de Sortida amb GPS i Marcatge de Torn Complert** (~20 min)  
  *Dependència*: `T008`, `T021`, `T022`, `T023`  
  *Requisits Funcionals*: `FR-004`, `US3`, `SC-005`  
  *Skill Mandatòria*: `supabase-postgres-best-practices` ([`.agents/skills/supabase-postgres-best-practices/SKILL.md`](file:///.agents/skills/supabase-postgres-best-practices/SKILL.md))  
  *Eina MCP*: `postgres` (verificació de jornada tancada amb `COMPLERT`)  
  *Descripció*: Endpoint `POST /api/v1/operari/jornada/{id}/fi` que captura `latitud_fi`, `longitud_fi`, calcula les hores totals treballades i commuta l'estat a `COMPLERT`.  
  **Hecho cuando:** El registre de jornada té `hora_fi` no nul·la, coordenades GPS finals registrades i estat `COMPLERT`.  
  *Cadena de Test*:  
  `backend/.venv/bin/pytest backend/tests/test_phase1_operari_pwa_eval.py -k "test_f1_02_fitxatge_gps_i_timestamp" -v`

- [x] **T025 [Frontend/UI] Assistent Seqüencial Evening Checkout a la PWA** (~25 min)  
  *Dependència*: `T021`, `T022`, `T023`, `T024`  
  *Requisits Funcionals*: `FR-004`, `US3`, `SC-005`  
  *Skill Mandatòria*: `frontend-design` ([`.agents/skills/frontend-design/SKILL.md`](file:///.agents/skills/frontend-design/SKILL.md))  
  *Eina MCP*: `chrome-devtools` (verificació del flux complet d'Evening Checkout)  
  *Descripció*: Interfície guiada `EveningCheckoutModal.tsx` amb 4 pantalles successives: 1) Balanç de Pick Out, 2) Foto odòmetre final, 3) Check de custòdia de tiquets, 4) Botó de fitxatge de sortida amb GPS.  
  **Hecho cuando:** L'operari completa els 4 passos i la PWA el retorna a la pantalla de comiat de torn amb el resum d'hores treballades.  
  *Cadena de Test*:  
  `npm --prefix pwa run build`

---

## 🚨 Bloc 5: User Story 4 - Resolució d'Incidències "Cicle Vermell-Verd"

- [x] **T026 [Frontend/Media] Gravadora d'Àudio Real (`MediaRecorder`) per a Notes de Veu** (~25 min)  
  *Dependència*: `T004`  
  *Requisits Funcionals*: `FR-013`, `US4`  
  *Skill Mandatòria*: `frontend-design` ([`.agents/skills/frontend-design/SKILL.md`](file:///.agents/skills/frontend-design/SKILL.md))  
  *Eina MCP*: `chrome-devtools` (inspecció de gravació de so)  
  *Descripció*: Mòdul de gravació de veu a `pwa/src/components/operari/VoiceRecorder.tsx` utilitzant l'API estàndard `MediaRecorder` (WebM/Opus, màxim 30 segons) amb micròfon real, sense simulacions de temps ni àudios dummy.  
  **Hecho cuando:** La gravació produeix un `Blob` d'àudio autèntic amb MIME type `audio/webm;codecs=opus` i pes superior a 0 bytes.  
  *Cadena de Test*:  
  `npm --prefix pwa run build`

- [x] **T027 [Backend/API] Endpoint d'Incidències Multimodal en Estat Inicial Vermell** (~25 min)  
  *Dependència*: `T001`  
  *Requisits Funcionals*: `FR-007`, `FR-008`, `US4`  
  *Skill Mandatòria*: `security-and-hardening` ([`.agents/skills/security-and-hardening/SKILL.md`](file:///.agents/skills/security-and-hardening/SKILL.md))  
  *Eina MCP*: `postgres` (inserció a taula `incidencies`)  
  *Descripció*: Endpoint `POST /api/v1/operari/incidencies` multipart/form-data que rep foto, àudio, coordenades GPS i descripció, assignant per defecte l'estat bloquejant `VERMELL`.  
  **Hecho cuando:** La incidència es crea amb `estat = 'VERMELL'` i queda encuada la tasca de transcripció de l'àudio.  
  *Cadena de Test*:  
  `backend/.venv/bin/pytest backend/tests/test_phase1_operari_pwa_eval.py -k "test_f1_01_incidencia_multipart_i_buit" -v`

- [x] **T028 [Backend/Worker] Tasca Celery de Transcripció Whisper v3 (`transcriure_audio_task`)** (~25 min)  
  *Dependència*: `T027`  
  *Requisits Funcionals*: `FR-013`  
  *Skill Mandatòria*: `systematic-debugging` ([`.agents/skills/systematic-debugging/SKILL.md`](file:///.agents/skills/systematic-debugging/SKILL.md))  
  *Eina MCP*: `postgres` (verificació del camp `transcripcio_audio`)  
  *Descripció*: Tasca asíncrona a `app.workers.tasks` que carrega el model local Whisper (quantitzat INT8), transcriu l'àudio català/castellà i actualitza el camp `incidencies.transcripcio_audio`.  
  **Hecho cuando:** La tasca s'executa a Celery i el registre d'incidència passa a contenir el text transcrit de la nota de veu.  
  *Cadena de Test*:  
  `backend/.venv/bin/pytest backend/tests/test_016_operari_incidencies.py -k "test_transcripcio_audio_incidencia" -v`

- [x] **T029 [Backend/Workflow] Resolució d'Incidència i Commutació a Estat Verd** (~20 min)  
  *Dependència*: `T027`  
  *Requisits Funcionals*: `FR-008`, `US4`  
  *Skill Mandatòria*: `supabase-postgres-best-practices` ([`.agents/skills/supabase-postgres-best-practices/SKILL.md`](file:///.agents/skills/supabase-postgres-best-practices/SKILL.md))  
  *Eina MCP*: `postgres` (verificació de canvi d'estat a `VERD`)  
  *Descripció*: Endpoint `PATCH /api/v1/operari/incidencies/{id}/resoldre` que permet a l'operari o al supervisor tancar el bloqueig aportant observacions finals i commutant l'estat a `VERD`.  
  **Hecho cuando:** L'estat de la incidència passa a `VERD` alliberant el bloqueig de la feina al mapa de gestió.  
  *Cadena de Test*:  
  `backend/.venv/bin/pytest backend/tests/test_016_operari_incidencies.py -k "test_resoldre_incidencia_verd" -v`

---

## ⛽ Bloc 6: User Story 5 - Tiquets de Despesa & Control de Límit

- [x] **T030 [Backend/API] Càrrega de Tiquets de Despesa i Flag de Límit (>100 €)** (~25 min)  
  *Dependència*: `T001`  
  *Requisits Funcionals*: `FR-009`, `US5`  
  *Skill Mandatòria*: `supabase-postgres-best-practices` ([`.agents/skills/supabase-postgres-best-practices/SKILL.md`](file:///.agents/skills/supabase-postgres-best-practices/SKILL.md))  
  *Eina MCP*: `postgres` (consulta a `tiquets_carburant`)  
  *Descripció*: Endpoint `POST /api/v1/operari/tiquets` que rep la fotografia del tiquet i la categoria (BENZINA, PEATGE, MATERIAL_URGENT). Si l'import supera 100 €, activa el flag `requereix_aprovacio = true`.  
  **Hecho cuando:** Un tiquet de 120 € es desa amb `requereix_aprovacio = true`, i un de 40 € amb `requereix_aprovacio = false`.  
  *Cadena de Test*:  
  `backend/.venv/bin/pytest backend/tests/test_018_operari_tiquets_ocr.py -k "test_tiquet_limit_flag" -v`

- [x] **T031 [Backend/Worker] Worker Celery OCR de Tiquets (`processar_ocr_tiquet_task`)** (~25 min)  
  *Dependència*: `T030`  
  *Requisits Funcionals*: `FR-009`  
  *Skill Mandatòria*: `systematic-debugging` ([`.agents/skills/systematic-debugging/SKILL.md`](file:///.agents/skills/systematic-debugging/SKILL.md))  
  *Eina MCP*: `postgres` (verificació d'import i litres extrets)  
  *Descripció*: Tasca asíncrona a la cua `queue_media` que extreu per OCR el total (€), litres, data i NIF de la benzinera, detectant compres mixtes de Gasoli + AdBlue.  
  **Hecho cuando:** La tasca omple automàticament els camps `import_`, `litres` i `estat_ocr = 'EXTRET_AUTOMATIC'` sense necessitat que l'operari teclegi res.  
  *Cadena de Test*:  
  `backend/.venv/bin/pytest backend/tests/test_018_operari_tiquets_ocr.py -k "test_ocr_extracccio_tiquet" -v`

- [x] **T032 [Frontend/UI] Captura Ràpida de Tiquets Sense Text a la PWA** (~25 min)  
  *Dependència*: `T014`, `T030`  
  *Requisits Funcionals*: `FR-009`, `US5`  
  *Skill Mandatòria*: `frontend-design` ([`.agents/skills/frontend-design/SKILL.md`](file:///.agents/skills/frontend-design/SKILL.md))  
  *Eina MCP*: `chrome-devtools` (captura de foto de tiquet sense tecleig)  
  *Descripció*: Pantalla `pwa/src/app/operari/tiquets/page.tsx` amb accés instantani a càmera i 3 botons grans de categoria (Benzina / Peatge / Parking), desant el tiquet en 1 sol toc.  
  **Hecho cuando:** L'operari desa un tiquet en menys de 3 segons prement únicament la foto i la icona de categoria.  
  *Cadena de Test*:  
  `npm --prefix pwa run build`

---

## 🗺️ Bloc 7: User Story 6 - Plànols GIS As-Built & Llanterna Integrada

- [x] **T033 [Frontend/Media] Control de Llanterna Contínua (`torch` MediaStream)** (~20 min)  
  *Dependència*: `T014`  
  *Requisits Funcionals*: `FR-011`  
  *Skill Mandatòria*: `frontend-design` ([`.agents/skills/frontend-design/SKILL.md`](file:///.agents/skills/frontend-design/SKILL.md))  
  *Eina MCP*: `chrome-devtools` (inspecció de MediaStreamTrack constraints)  
  *Descripció*: Botó flotant de llanterna a la càmera i al visor de plànols que aplica `{ advanced: [{ torch: true }] }` sobre el `MediaStreamTrack` per il·luminar rases i quadres foscos.  
  **Hecho cuando:** La pulsació del botó commuta l'estat de la llanterna sense tallar el flux de vídeo ni perdre la posició a la pantalla.  
  *Cadena de Test*:  
  `npm --prefix pwa run build`

- [x] **T034 [Frontend/GIS] Visor de Plànols As-Built amb Posició GPS de l'Operari** (~25 min)  
  *Dependència*: `T004`  
  *Requisits Funcionals*: `FR-007`, `FR-010`, `US6`  
  *Skill Mandatòria*: `frontend-design` ([`.agents/skills/frontend-design/SKILL.md`](file:///.agents/skills/frontend-design/SKILL.md))  
  *Eina MCP*: `chrome-devtools` (renderitzat del mapa cartogràfic i marcador GPS)  
  *Descripció*: Visor a `pwa/src/app/operari/planols/page.tsx` que carrega el plànol vectorial/raster de l'OT activa i dibuixa un marcador blau amb la posició GPS en temps real de l'operari.  
  **Hecho cuando:** El visor renderitza el plànol i ubica el punt de l'operari centrant el mapa sobre les seves coordenades.  
  *Cadena de Test*:  
  `npm --prefix pwa run build`

- [x] **T035 [Backend/API] Creació de Capes Vectorials As-Built Sense Modificar Plànol Base** (~25 min)  
  *Dependència*: `T001`  
  *Requisits Funcionals*: `FR-010`, `US6`  
  *Skill Mandatòria*: `supabase-postgres-best-practices` ([`.agents/skills/supabase-postgres-best-practices/SKILL.md`](file:///.agents/skills/supabase-postgres-best-practices/SKILL.md))  
  *Eina MCP*: `postgres` (consulta a `capes_vectorials`)  
  *Descripció*: Endpoint `POST /api/v1/operari/planols/{id}/capes` que desa el GeoJSON de canonades o cables dibuixats per l'operari com a capa independent lligada a la feina.  
  **Hecho cuando:** La creació de la capa vectorial no modifica el hash ni el contingut del registre `planols_base`.  
  *Cadena de Test*:  
  `backend/.venv/bin/pytest backend/tests/test_phase3_operari.py -k "test_intervencions_actives_gis_i_marca" -v`

- [x] **T036 [Frontend/Export] Exportació de Vista de Plànol Anotat a Incidència** (~25 min)  
  *Dependència*: `T027`, `T034`, `T035`  
  *Requisits Funcionals*: `FR-014`, `US6`  
  *Skill Mandatòria*: `frontend-design` ([`.agents/skills/frontend-design/SKILL.md`](file:///.agents/skills/frontend-design/SKILL.md))  
  *Eina MCP*: `chrome-devtools` (captura d'imatge del canvas de plànol)  
  *Descripció*: Acció que captura el canvas del plànol amb les capes dibuixades com a imatge PNG i l'adjunta directament a una incidència nova o existent.  
  **Hecho cuando:** La imatge renderitzada del plànol apareix com a `foto_path` de la incidència generada.  
  *Cadena de Test*:  
  `npm --prefix pwa run build`

---

## 🔄 Bloc 8: Pipeline de Sincronització Offline & Service Worker

- [x] **T037 [Frontend/SW] Service Worker amb Cua FIFO a Dexie (`sync_queue`)** (~25 min)  
  *Dependència*: `T004`  
  *Requisits Funcionals*: `FR-002`, `SC-002`  
  *Skill Mandatòria*: `security-and-hardening` ([`.agents/skills/security-and-hardening/SKILL.md`](file:///.agents/skills/security-and-hardening/SKILL.md))  
  *Eina MCP*: `chrome-devtools` (simulació de mode fora de línia a Network tab)  
  *Descripció*: Configurar `sw.js` i Workbox perquè interceptin fallades de xarxa i desin les mutacions (`FITXAR_JORNADA`, `PUJAR_FOTO`, `CREAR_INCIDENCIA`, `CREAR_TIQUET`) a `sync_queue` de forma ordenada.  
  **Hecho cuando:** En desconnectar la xarxa, les accions de l'operari no donen error i queden emmagatzemades a `sync_queue`.  
  *Cadena de Test*:  
  `npm --prefix pwa run build`

- [x] **T038 [Backend/Sync] Endpoint de Sincronització Atòmica Massiva (`POST /sync/push`)** (~25 min)  
  *Dependència*: `T001`  
  *Requisits Funcionals*: `FR-002`, `SC-002`  
  *Skill Mandatòria*: `supabase-postgres-best-practices` ([`.agents/skills/supabase-postgres-best-practices/SKILL.md`](file:///.agents/skills/supabase-postgres-best-practices/SKILL.md))  
  *Eina MCP*: `postgres` (comprovació de persistència de la cua sincronitzada)  
  *Descripció*: Endpoint `POST /api/v1/operari_pwa/sync/push` que rep un lot d'accions pendents, les executa en ordre seqüencial estricte dins d'una transacció i retorna els identificadors confirmats.  
  **Hecho cuando:** El lot de 5 accions offline s'aplica atòmicament a PostgreSQL retornant HTTP 200 amb `{ "processats": 5, "errors": 0 }`.  
  *Cadena de Test*:  
  `backend/.venv/bin/pytest backend/tests/test_043_bulk_sync.py -v`

---

## 🏆 Bloc 9: Suite d'Auditoria Zero Mock & Verificació en Viu

- [x] **T039 [QA/Pytest] Execució de Tota la Suite de Tests d'Operaris** (~25 min)  
  *Dependència*: `T001` fins a `T038`  
  *Requisits Funcionals*: `FR-001`, `SC-001` a `SC-005`  
  *Skill Mandatòria*: `systematic-debugging` ([`.agents/skills/systematic-debugging/SKILL.md`](file:///.agents/skills/systematic-debugging/SKILL.md))  
  *Eina MCP*: `postgres` (aïllament RLS certificat)  
  *Descripció*: Llançar tots els tests del mòdul operari i verificar netedat al 100%, absència de warnings d'event loop i conformitat Zero Mock Data.  
  **Hecho cuando:** Tots els tests d'operari passen en verd (`100% passed`) sense cap mock de base de dades.  
  *Cadena de Test*:  
  `backend/.venv/bin/pytest backend/tests/test_phase1_operari_pwa_eval.py backend/tests/test_019_operari_login.py backend/tests/test_013_operari_jornada.py backend/tests/test_014_operari_picking.py backend/tests/test_015_operari_vehicles_rutines.py backend/tests/test_016_operari_incidencies.py backend/tests/test_018_operari_tiquets_ocr.py -v`

- [x] **T040 [QA/MCP] Prova en Viu amb Chrome DevTools MCP (Login Offline i 3 Fotos)** (~25 min)  
  *Dependència*: `T039`  
  *Requisits Funcionals*: `FR-001`, `FR-005`, `FR-006`  
  *Skill Mandatòria*: `security-review` ([`.agents/skills/security-review/SKILL.md`](file:///.agents/skills/security-review/SKILL.md))  
  *Eina MCP*: `chrome-devtools` (navegació real, inspecció de peticions i screenshots)  
  *Descripció*: Connectar a la PWA `/operari`, fer login introduint PIN amb clics al Numpad, verificar Morning Briefing i comprovar que el tancament de feina està bloquejat fins a aportar les 3 fotos.  
  **Hecho cuando:** `chrome-devtools` pren captura de pantalla de la feina amb les 3 fotos validades i confirma trànsit HTTP net a `list_network_requests`.  
  *Cadena de Test*:  
  `mcp_chrome-devtools_navigate_page` (`http://localhost:3000/operari/login`) + `mcp_chrome-devtools_take_screenshot`

- [x] **T041 [QA/MCP] Auditoria de Persistència a PostgreSQL viu amb MCP `postgres`** (~20 min)  
  *Dependència*: `T040`  
  *Requisits Funcionals*: `FR-001`  
  *Skill Mandatòria*: `supabase-postgres-best-practices` ([`.agents/skills/supabase-postgres-best-practices/SKILL.md`](file:///.agents/skills/supabase-postgres-best-practices/SKILL.md))  
  *Eina MCP*: `postgres` (consultes SQL d'auditoria Zero Mock)  
  *Descripció*: Executar consultes directes contra PostgreSQL per certificar que el fitxatge GPS, la càrrega de fotos WebP i el balanç de materials de picking s'han persistit amb èxit sota el tenant real.  
  **Hecho cuando:** La consulta SQL certifica que la feina té estat `FINALITZADA`, les 3 fotos associades i el fitxatge té coordenades vàlides.  
  *Cadena de Test*:  
  `mcp_postgres_query` amb `SELECT id, estat, coords_gps FROM ordres_treball WHERE empresa_id = '...'`
