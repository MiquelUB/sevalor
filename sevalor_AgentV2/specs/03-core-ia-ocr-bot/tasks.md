# Tasks: Core IA, OCR, Bot de Telegram & Processament Asíncron (Spec 03) — Microtasques < 30 minuts

**Feature Path**: `specs/03-core-ia-ocr-bot`  
**Prerequisites**: `spec.md`, `plan.md`, `constitution.md`, `AGENTS.md`  
**Norma Suprema**: Zero Mock Data, Human-in-the-Loop, Barrera Econòmica Doble Capa, aprovació 100% neta de tests.  
**Criteri de Granularitat**: Totes les tasques estan estrictament acotades a una durada estimada **< 30 minuts**, ordenades per dependència lògica descendent, amb **Skill mandatoria** i **Eina MCP** associades.

---

## ⚙️ Bloc 1: Cues Celery, Topologia Redis i Polítiques RLS de Workers

- [ ] **T001 [Backend/Celery] Configuració de les 5 Cues Dedicades de Celery a Redis 7** (~25 min)  
  *Dependència*: Cap  
  *Requisits Funcionals*: `FR-003`, `FR-012`  
  *Skill Mandatòria*: `systematic-debugging` ([`.agents/skills/systematic-debugging/SKILL.md`](file:///.agents/skills/systematic-debugging/SKILL.md))  
  *Eina MCP*: `postgres` (connexió compartida)  
  *Descripció*: Configurar a `backend/app/workers/celery_app.py` les cinc cues prioritzades: `queue_critical` (15s soft), `queue_documents` (60s), `queue_sync` (45s), `queue_media` (120s) i `queue_periodic` (600s), amb `acks_late=True` i `reject_on_worker_lost=True`.  
  **Hecho cuando:** La inspecció del broker Celery via CLI o client Redis confirma el registre de les 5 cues sense caigudes de procés.  
  *Cadena de Test*:  
  `backend/.venv/bin/pytest backend/tests/test_024_celery_ping_async.py backend/tests/test_024_celery_ping.py -v`

- [ ] **T002 [Backend/Worker] Injecció de Sessió RLS a les Tasques Asíncrones de Celery** (~20 min)  
  *Dependència*: `T001`  
  *Requisits Funcionals*: `FR-003`  
  *Skill Mandatòria*: `supabase-postgres-best-practices` ([`.agents/skills/supabase-postgres-best-practices/SKILL.md`](file:///.agents/skills/supabase-postgres-best-practices/SKILL.md))  
  *Eina MCP*: `postgres` (comprovació de `SET LOCAL app.current_empresa_id` dins del worker)  
  *Descripció*: Assegurar que tota tasca Celery que accedeix a PostgreSQL rep el paràmetre `empresa_id` i executa `SET LOCAL app.current_empresa_id = :empresa_id` abans de consultar o mutar taules sota RLS.  
  **Hecho cuando:** Una tasca Celery executada amb el tenant A no pot llegir ni modificar registres del tenant B a PostgreSQL.  
  *Cadena de Test*:  
  `backend/.venv/bin/pytest backend/tests/test_021_rls_isolation.py -v`

- [ ] **T003 [Backend/API] Endpoint de Seguiment d'Estat de Workers (`GET /workers/status/{task_id}`)** (~20 min)  
  *Dependència*: `T001`  
  *Requisits Funcionals*: `FR-012`  
  *Skill Mandatòria*: `systematic-debugging` ([`.agents/skills/systematic-debugging/SKILL.md`](file:///.agents/skills/systematic-debugging/SKILL.md))  
  *Eina MCP*: `postgres` (estat de tasques a la BD)  
  *Descripció*: Endpoint reactiu `GET /api/v1/workers/status/{task_id}` que consulta el Result Backend de Redis i retorna l'estat (`PENDENT`, `PROCESSANT`, `COMPLETAT`, `ERROR`) i resultat de la tasca en segon pla.  
  **Hecho cuando:** L'endpoint retorna JSON amb `task_id`, `estat` i `resultat` en <50ms.  
  *Cadena de Test*:  
  `backend/.venv/bin/pytest backend/tests/test_024_workers_status.py -v`

- [ ] **T004 [Backend/Worker] Health Check i Tasca de Ping Asíncron dels Workers** (~20 min)  
  *Dependència*: `T001`  
  *Requisits Funcionals*: `FR-012`  
  *Skill Mandatòria*: `systematic-debugging` ([`.agents/skills/systematic-debugging/SKILL.md`](file:///.agents/skills/systematic-debugging/SKILL.md))  
  *Eina MCP*: `postgres` (comprovació de connectivitat)  
  *Descripció*: Implementar la tasca `app.workers.tasks.ping` a `queue_critical` per avaluar la latència i connectivitat entre FastAPI, Redis i els processos Celery.  
  **Hecho cuando:** `ping.delay()` respon `pong` en menys d'1 segon confirmant que els workers estan actius.  
  *Cadena de Test*:  
  `backend/.venv/bin/pytest backend/tests/test_024_celery_ping_async.py -v`

---

## 📄 Bloc 2: Alta Màgica OCR Transversal "Zero Data Entry"

- [ ] **T005 [Backend/OCR] Pipeline Unificat d'Extracció OCR de Documents (`ocr_service.py`)** (~25 min)  
  *Dependència*: `T001`  
  *Requisits Funcionals*: `FR-001`, `SC-001`, `US1`  
  *Skill Mandatòria*: `systematic-debugging` ([`.agents/skills/systematic-debugging/SKILL.md`](file:///.agents/skills/systematic-debugging/SKILL.md))  
  *Eina MCP*: `postgres` (inserció de draft estructurat)  
  *Descripció*: Implementar a `backend/app/services/ocr_service.py` el processament d'imatges i PDFs utilitzant el node local de visió/OCR per extreure NIF, imports, dates, referències i matrícules sense dades simulades (Zero Mock Data).  
  **Hecho cuando:** La funció d'extracció rep un fitxer real i retorna un diccionari amb els camps reconeguts i un percentatge de certesa per camp.  
  *Cadena de Test*:  
  `backend/.venv/bin/pytest backend/tests/test_004_gestio_magatzem_ocr.py -v`

- [ ] **T006 [Backend/API] Endpoint d'Alta Ràpida de Vehicles via OCR (`POST /flota/ocr-draft`)** (~25 min)  
  *Dependència*: `T005`  
  *Requisits Funcionals*: `FR-001`, `SC-001`, `US1`  
  *Skill Mandatòria*: `security-and-hardening` ([`.agents/skills/security-and-hardening/SKILL.md`](file:///.agents/skills/security-and-hardening/SKILL.md))  
  *Eina MCP*: `postgres` (comprovació de format de matrícula)  
  *Descripció*: Endpoint multipart/form-data que analitza fotografies de Fitxa Tècnica o Permís de Circulació i retorna l'esborrany JSON amb matrícula, VIN de 17 dígits, marca, model, cilindrada i MMA.  
  **Hecho cuando:** La càrrega d'una fitxa tècnica retorna HTTP 200 amb les dades estructurades del vehicle llestes per acceptar amb 1 clic.  
  *Cadena de Test*:  
  `backend/.venv/bin/pytest backend/tests/test_006_gestio_flota.py -k "test_ocr" -v`

- [ ] **T007 [Backend/API] Endpoint d'Albarans de Proveïdor OCR (`POST /magatzem/albara/ocr`)** (~25 min)  
  *Dependència*: `T005`  
  *Requisits Funcionals*: `FR-001`, `SC-001`, `US1`  
  *Skill Mandatòria*: `supabase-postgres-best-practices` ([`.agents/skills/supabase-postgres-best-practices/SKILL.md`](file:///.agents/skills/supabase-postgres-best-practices/SKILL.md))  
  *Eina MCP*: `postgres` (desa registre en estat `PENDENT_AUDITORIA`)  
  *Descripció*: Ingesta de documents d'albarà o factura de compra, extracció de capçalera i graella de línies d'articles desant el document a `albarans_proveidor` en estat transitori `PENDENT_AUDITORIA`.  
  **Hecho cuando:** L'albarà queda registrat a PostgreSQL amb la seva taula de línies extreta sense alterar l'estoc fins a revisió humana.  
  *Cadena de Test*:  
  `backend/.venv/bin/pytest backend/tests/test_004_gestio_magatzem_ocr.py -k "test_ocr_albara_pendent_auditoria" -v`

- [ ] **T008 [Backend/API] Alta de Proveïdors via OCR a 1 Clic (`POST /proveidors/ocr-draft`)** (~20 min)  
  *Dependència*: `T005`  
  *Requisits Funcionals*: `FR-001`, `SC-001`, `US1`  
  *Skill Mandatòria*: `security-and-hardening` ([`.agents/skills/security-and-hardening/SKILL.md`](file:///.agents/skills/security-and-hardening/SKILL.md))  
  *Eina MCP*: `postgres` (verificació de dades fiscals de proveïdor)  
  *Descripció*: Endpoint que extreu dades fiscals (CIF, raó social, domicili) des d'un document per generar l'alta ràpida de proveïdor sense picar dades a mà.  
  **Hecho cuando:** La pujada de la factura retorna l'objecte JSON amb CIF vàlid i raó social preomplerta.  
  *Cadena de Test*:  
  `backend/.venv/bin/pytest backend/tests/test_003_gestio_proveidors.py -v`

- [ ] **T009 [Backend/API] Extracció OCR de Tiquets de Carburant i Despeses de Camp** (~25 min)  
  *Dependència*: `T005`  
  *Requisits Funcionals*: `FR-001`, `US1`  
  *Skill Mandatòria*: `systematic-debugging` ([`.agents/skills/systematic-debugging/SKILL.md`](file:///.agents/skills/systematic-debugging/SKILL.md))  
  *Eina MCP*: `postgres` (consulta a `tiquets_carburant`)  
  *Descripció*: Endpoint `POST /api/v1/operari_pwa/tiquets/ocr` que analitza la foto del tiquet, extreu el total en euros, litres, data i NIF benzinera, detectant compres mixtes de Gasoli + AdBlue.  
  **Hecho cuando:** El tiquet queda registrat a la base de dades amb els camps `import_`, `litres` i `estat_ocr = 'EXTRET_AUTOMATIC'`.  
  *Cadena de Test*:  
  `backend/.venv/bin/pytest backend/tests/test_018_operari_tiquets_ocr.py -v`

- [ ] **T010 [Backend/Worker] Generació Asíncrona de Miniatures WebP a `queue_media`** (~20 min)  
  *Dependència*: `T009`  
  *Requisits Funcionals*: `FR-001`  
  *Skill Mandatòria*: `systematic-debugging` ([`.agents/skills/systematic-debugging/SKILL.md`](file:///.agents/skills/systematic-debugging/SKILL.md))  
  *Eina MCP*: `postgres` (actualització de `thumbnail_url`)  
  *Descripció*: Tasca Celery `generar_miniatura_webp_task` que optimitza fotografies d'albarans, tiquets i incidències generant una miniatura WebP (màxim 800px, 80% qualitat) per a càrrega ràpida a la UI.  
  **Hecho cuando:** La imatge original conserva la seva resolució a `/data/` i es genera la miniatura WebP associada de menys de 100 KB.  
  *Cadena de Test*:  
  `backend/.venv/bin/pytest backend/tests/test_018_operari_tiquets_ocr.py -k "test_thumbnail" -v`

---

## 🎙️ Bloc 3: Peritatge Multimodal d'Incidències & Memoràndum Tècnic HITL

- [ ] **T011 [Backend/AI] Servei Whisper v3 Local de Transcripció Fonètica (`whisper_service.py`)** (~25 min)  
  *Dependència*: `T001`  
  *Requisits Funcionals*: `FR-004`, `SC-002`, `SC-003`, `US2`  
  *Skill Mandatòria*: `systematic-debugging` ([`.agents/skills/systematic-debugging/SKILL.md`](file:///.agents/skills/systematic-debugging/SKILL.md))  
  *Eina MCP*: `postgres` (emmagatzematge de transcripció)  
  *Descripció*: Mòdul de connexió al node Whisper local per processar notes d'àudio de camp en català i castellà tècnic, calculant la mètrica de confiança acústica (avís si <0.40 per soroll de maquinària).  
  **Hecho cuando:** L'enviament d'un arxiu `.webm` retorna el text transcrit fidelment i el valor flotant de confiança acústica.  
  *Cadena de Test*:  
  `backend/.venv/bin/pytest backend/tests/test_residual.py -k "test_whisper_service" -v`

- [ ] **T012 [Backend/AI] Fallback Sobirà en Cas d'Indisponibilitat del Node d'IA** (~20 min)  
  *Dependència*: `T011`  
  *Requisits Funcionals*: `FR-004`, `US2`  
  *Skill Mandatòria*: `systematic-debugging` ([`.agents/skills/systematic-debugging/SKILL.md`](file:///.agents/skills/systematic-debugging/SKILL.md))  
  *Eina MCP*: `postgres` (verificació de persistència sense IA)  
  *Descripció*: Assegurar que si el servei Whisper o LLM no respon (<15s) o està apagat, el sistema no cau ni inventa dades, sinó que retorna el missatge de fallback sobirà ("Copilot provisionalment no disponible") i preserva els arxius originals per a revisió humana.  
  **Hecho cuando:** Amb el servei d'IA desconnectat, la tasca retorna el missatge sobirà sense error 500 ni bloqueig del procés.  
  *Cadena de Test*:  
  `backend/.venv/bin/pytest backend/tests/test_phase3_copilot_eval.py -k "test_f3_05_fallback_sense_ia" -v`

- [ ] **T013 [Backend/AI] Generador de Memoràndum Tècnic d'Incidència (Extra vs. Cost Intern)** (~25 min)  
  *Dependència*: `T011`  
  *Requisits Funcionals*: `FR-004`, `US2`  
  *Skill Mandatòria*: `security-review` ([`.agents/skills/security-review/SKILL.md`](file:///.agents/skills/security-review/SKILL.md))  
  *Eina MCP*: `postgres` (creació de registre `memorandum_tecnic`)  
  *Descripció*: Avaluar la nota de veu transcrita i la foto pericial per generar una proposta de dictamen: Extra Facturable (imprevist de la finca) o Cost No Imputable al Client (error d'execució), desglossant materials estimats.  
  **Hecho cuando:** Es crea el registre a `memorandum_tecnic` amb `estat_validacio = 'PENDENT_REVISIO'` i la qualificació proposada.  
  *Cadena de Test*:  
  `backend/.venv/bin/pytest backend/tests/test_phase3_copilot_eval.py -k "test_f3_01_tool_calling_stock_real" -v`

- [ ] **T014 [Backend/API] Endpoint de Peritatge d'Incidències (`POST /copilot/incidencies/peritatge`)** (~25 min)  
  *Dependència*: `T013`  
  *Requisits Funcionals*: `FR-004`, `US2`  
  *Skill Mandatòria*: `security-and-hardening` ([`.agents/skills/security-and-hardening/SKILL.md`](file:///.agents/skills/security-and-hardening/SKILL.md))  
  *Eina MCP*: `postgres` (comprovació de creació del memoràndum)  
  *Descripció*: Endpoint que rep l'àudio i la fotografia d'obra des de la PWA, dispara la tasca a Celery i retorna l'identificador del memoràndum generat.  
  **Hecho cuando:** La crida retorna HTTP 202 Accepted amb `{ "memorandum_id": "...", "estat": "PROCESSANT" }`.  
  *Cadena de Test*:  
  `backend/.venv/bin/pytest backend/tests/test_016_operari_incidencies.py -v`

- [ ] **T015 [Backend/API] Validació Humana HITL del Memoràndum Tècnic** (~20 min)  
  *Dependència*: `T014`  
  *Requisits Funcionals*: `FR-002`, `US2`  
  *Skill Mandatòria*: `security-review` ([`.agents/skills/security-review/SKILL.md`](file:///.agents/skills/security-review/SKILL.md))  
  *Eina MCP*: `postgres` (verificació de transició a `APROVAT_ENGINYER`)  
  *Descripció*: Endpoint `PUT /api/v1/gestio/copilot/memorandums/{id}/validacio` que permet a l'enginyer supervisor ratificar o rectificar el dictamen abans de generar cap pressupost al client (HITL estricte).  
  **Hecho cuando:** El camp `estat_validacio` commuta a `APROVAT_ENGINYER` registrant el dictamen final i l'usuari que ha validat.  
  *Cadena de Test*:  
  `backend/.venv/bin/pytest backend/tests/test_phase3_copilot_eval.py -k "test_f3_03_veto_financer" -v`

---

## 🤖 Bloc 4: Canal de Telegram per a Clients Finals

- [ ] **T016 [Backend/Bot] Microservei aiogram 3.x amb Webhook HTTPS Securitzat** (~25 min)  
  *Dependència*: `T001`  
  *Requisits Funcionals*: `FR-008`, `FR-009`, `US3`  
  *Skill Mandatòria*: `security-and-hardening` ([`.agents/skills/security-and-hardening/SKILL.md`](file:///.agents/skills/security-and-hardening/SKILL.md))  
  *Eina MCP*: `postgres` (verificació de credencials bot del tenant)  
  *Descripció*: Configurar el despachador de Webhooks a `/api/v1/webhooks/telegram` validant la capçalera obligatòria `X-Telegram-Bot-Api-Secret-Token` i suportant rutes multi-bot dinàmiques per empresa.  
  **Hecho cuando:** Una petició sense la capçalera secreta és rebutjada amb HTTP 401/403 i amb el token vàlid processa l'update d'aiogram.  
  *Cadena de Test*:  
  `backend/.venv/bin/pytest backend/tests/test_bot_telegram.py -k "test_webhook_auth" -v`

- [ ] **T017 [Backend/Bot] Vinculació de Client per Deep-Linking d'Un Sol Ús (`/start <token>`)** (~25 min)  
  *Dependència*: `T016`  
  *Requisits Funcionals*: `FR-008`, `US3`  
  *Skill Mandatòria*: `security-and-hardening` ([`.agents/skills/security-and-hardening/SKILL.md`](file:///.agents/skills/security-and-hardening/SKILL.md))  
  *Eina MCP*: `postgres` (actualització de `telegram_chat_id` a `clients`)  
  *Descripció*: Enviar enllaç d'invitació unívoc al client (`https://t.me/bot?start=TOKEN_48H`). En prémer [START], vincula el seu `telegram_chat_id` a la seva fitxa corporativa i crema el token d'un sol ús.  
  **Hecho cuando:** La taula `clients` emmagatzema el `telegram_chat_id` i un segon ús del mateix token és rebutjat.  
  *Cadena de Test*:  
  `backend/.venv/bin/pytest backend/tests/test_phase4_telegram_portal_eval.py -k "test_f4_01_aprovacio_pressupost_telegram" -v`

- [ ] **T018 [Backend/Bot] Bloqueig Opac d'Usuaris Desconeguts o No Convidats** (~20 min)  
  *Dependència*: `T017`  
  *Requisits Funcionals*: `FR-009`, `US3`  
  *Skill Mandatòria*: `security-review` ([`.agents/skills/security-review/SKILL.md`](file:///.agents/skills/security-review/SKILL.md))  
  *Eina MCP*: `postgres` (verificació de no-creació de registres)  
  *Descripció*: Middleware d'aiogram que comprova si el `chat_id` emissor està vinculat a un client del tenant: si és desconegut, descarta el missatge sense obre cap fil de conversa al panell de gestió.  
  **Hecho cuando:** Un usuari no registrat envia missatges i el bot respon silenciosament sense crear cap conversa a la base de dades.  
  *Cadena de Test*:  
  `backend/.venv/bin/pytest backend/tests/test_phase4_telegram_portal_eval.py -k "test_f4_03_pressupost_inexistent_telegram" -v`

- [ ] **T019 [Backend/Bot] Token Bucket Rate Limiter per a Telegram sobre Redis** (~20 min)  
  *Dependència*: `T016`  
  *Requisits Funcionals*: `FR-008`  
  *Skill Mandatòria*: `security-and-hardening` ([`.agents/skills/security-and-hardening/SKILL.md`](file:///.agents/skills/security-and-hardening/SKILL.md))  
  *Eina MCP*: `postgres` (connexió paral·lela)  
  *Descripció*: Implementar control de flux asíncron a Redis que assegura no superar els límits de l'API de Telegram (màx. 30 msg/s global, 1 msg/s per xat privat) gestionant reintents davant HTTP 429.  
  **Hecho cuando:** El llançament en ràfega de 10 missatges a un mateix client es despatxa espaiat a 1 segon sense rebre cap error 429 de Telegram.  
  *Cadena de Test*:  
  `backend/.venv/bin/pytest backend/tests/test_bot_telegram.py -k "test_rate_limiter" -v`

- [ ] **T020 [Backend/Bot] Blindatge contra Arxius Maliciosos (Magic Bytes & Doble Extensió)** (~25 min)  
  *Dependència*: `T016`  
  *Requisits Funcionals*: `FR-009`  
  *Skill Mandatòria*: `security-and-hardening` ([`.agents/skills/security-and-hardening/SKILL.md`](file:///.agents/skills/security-and-hardening/SKILL.md))  
  *Eina MCP*: `postgres` (auditoria de rebuig d'arxius)  
  *Descripció*: Filtre que intercepta qualsevol document enviat per Telegram: rebutja cadenes amb múltiples extensions (ex: `.jpg.exe`, `.png.sh`) i comprova els Magic Bytes reals amb `filetype`.  
  **Hecho cuando:** L'enviament d'un fitxer executable rebatejat com a `.jpg` és rebutjat immediatament i alertat com a fitxer maliciós.  
  *Cadena de Test*:  
  `backend/.venv/bin/pytest backend/tests/test_bot_telegram.py -k "test_arxiu_malicios" -v`

- [ ] **T021 [Backend/Bot] Despatx de Pressupostos amb Inline Keyboard Interactiu** (~25 min)  
  *Dependència*: `T017`  
  *Requisits Funcionals*: `FR-008`, `SC-004`, `US3`  
  *Skill Mandatòria*: `frontend-design` ([`.agents/skills/frontend-design/SKILL.md`](file:///.agents/skills/frontend-design/SKILL.md))  
  *Eina MCP*: `postgres` (verificació d'estat de pressupost enviat)  
  *Descripció*: Endpoint `POST /api/v1/gestio/pressupostos/{id}/enviar-telegram` que transmet el resum econòmic al client amb dos botons: `[✅ Acceptar Pressupost]` i `[❌ Demanar Canvis]`.  
  **Hecho cuando:** El client rep el missatge a Telegram amb la botonera interactiva encreuada amb el seu `chat_id`.  
  *Cadena de Test*:  
  `backend/.venv/bin/pytest backend/tests/test_phase4_telegram_portal_eval.py -k "test_f4_04_enviar_pressupost_via_telegram_endpoint" -v`

- [ ] **T022 [Backend/Bot] Resolució de Callback Query d'Acceptació amb Token Digital** (~25 min)  
  *Dependència*: `T021`  
  *Requisits Funcionals*: `FR-008`, `SC-004`, `US3`  
  *Skill Mandatòria*: `supabase-postgres-best-practices` ([`.agents/skills/supabase-postgres-best-practices/SKILL.md`](file:///.agents/skills/supabase-postgres-best-practices/SKILL.md))  
  *Eina MCP*: `postgres` (verificació de commutació a `APROVAT` i token `TG-APROV-`)  
  *Descripció*: En prémer `[✅ Acceptar]`, el bot processa la callback_query, canvia l'estat a `APROVAT`, assigna un token digital que comença per `TG-APROV-` i elimina la botonera per prevenir clics dobles.  
  **Hecho cuando:** `pressupost.estat == 'APROVAT'` i `pressupost.token_signatura.startswith('TG-APROV-')` queden persistits a PostgreSQL.  
  *Cadena de Test*:  
  `backend/.venv/bin/pytest backend/tests/test_phase4_telegram_portal_eval.py -k "test_f4_01_aprovacio_pressupost_telegram" -v`

- [ ] **T023 [Backend/Bot] Enllaç de Descàrrega Efímer de 24 Hores per a Factures** (~20 min)  
  *Dependència*: `T021`  
  *Requisits Funcionals*: `FR-003`, `US3`  
  *Skill Mandatòria*: `security-and-hardening` ([`.agents/skills/security-and-hardening/SKILL.md`](file:///.agents/skills/security-and-hardening/SKILL.md))  
  *Eina MCP*: `postgres` (comprovació de venciment del token temporal)  
  *Descripció*: Les factures mai s'adjunten directament en cru al xat de Telegram; es genera una URL temporal signada que caduca als 1.440 minuts (24 hores) allotjada al servidor Hetzner de l'empresa.  
  **Hecho cuando:** La descàrrega és permesa durant les primeres 24h i denegada amb HTTP 410 Gone un cop vençut el token.  
  *Cadena de Test*:  
  `backend/.venv/bin/pytest backend/tests/test_bot_telegram.py -k "test_enllac_efimer" -v`

- [ ] **T024 [Backend/Bot] Signatura Digital de Conformitat de Tancament d'Obra** (~25 min)  
  *Dependència*: `T022`  
  *Requisits Funcionals*: `FR-008`, `US12`  
  *Skill Mandatòria*: `security-and-hardening` ([`.agents/skills/security-and-hardening/SKILL.md`](file:///.agents/skills/security-and-hardening/SKILL.md))  
  *Eina MCP*: `postgres` (incorporació de rúbrica a la feina)  
  *Descripció*: Quan l'operari finalitza la feina, el bot envia al client un enllaç a un canvas lleuger de signatura web mòbil per rubricar la conformitat de l'actuació sense paper.  
  **Hecho cuando:** La rúbrica en format PNG signat queda xifrada a `/docs/<empresa_id>/conformitats/` i vinculada a l'ordre de treball.  
  *Cadena de Test*:  
  `backend/.venv/bin/pytest backend/tests/test_phase4_telegram_portal_eval.py -k "test_f4_05_generacio_pdf_post_obra" -v`

---

## 🔍 Bloc 5: Memòria Històrica 360°, Garanties i Reconciliació Post-Obra

- [ ] **T025 [Backend/API] Auditoria Històrica 360° d'Instal·lacions (`GET /copilot/garanties/auditoria`)** (~25 min)  
  *Dependència*: `T002`  
  *Requisits Funcionals*: `FR-005`, `SC-005`, `US4`  
  *Skill Mandatòria*: `supabase-postgres-best-practices` ([`.agents/skills/supabase-postgres-best-practices/SKILL.md`](file:///.agents/skills/supabase-postgres-best-practices/SKILL.md))  
  *Eina MCP*: `postgres` (consulta d'intervencions dels darrers 365 dies)  
  *Descripció*: Recopilar totes les ordres de treball, recanvis instal·lats i actuacions prèvies de la finca dels darrers 365 dies en una única crida analítica.  
  **Hecho cuando:** L'endpoint retorna l'arbre d'intervencions amb els números de sèrie i proveïdors dels equips instal·lats.  
  *Cadena de Test*:  
  `backend/.venv/bin/pytest backend/tests/test_phase3_copilot_eval.py -k "test_f3_01_tool_calling_stock_real" -v`

- [ ] **T026 [Backend/Service] Motor d'Alertes de Garanties de Fabricant i Servei Intern** (~25 min)  
  *Dependència*: `T025`  
  *Requisits Funcionals*: `FR-005`, `SC-005`, `US4`  
  *Skill Mandatòria*: `security-review` ([`.agents/skills/security-review/SKILL.md`](file:///.agents/skills/security-review/SKILL.md))  
  *Eina MCP*: `postgres` (inserció a `alerta_garantia_recompra`)  
  *Descripció*: Avaluar dates de compra d'equips: si està sota garantia de fabricant (<2 anys), proposa tramitar RMA; si és feina recent (<3 mesos), alerta de garantia interna per no cobrar mà d'obra.  
  **Hecho cuando:** El component genera l'alerta de garantia activa advertint de no repercutir el cost al client.  
  *Cadena de Test*:  
  `backend/.venv/bin/pytest backend/tests/test_phase3_copilot_eval.py -k "test_f3_01_tool_calling_stock_real" -v`

- [ ] **T027 [Backend/API] Reconciliació Post-Obra dels 4 Pilars (`POST /reconciliacio/post-obra`)** (~25 min)  
  *Dependència*: `T002`  
  *Requisits Funcionals*: `FR-006`, `US5`  
  *Skill Mandatòria*: `supabase-postgres-best-practices` ([`.agents/skills/supabase-postgres-best-practices/SKILL.md`](file:///.agents/skills/supabase-postgres-best-practices/SKILL.md))  
  *Eina MCP*: `postgres` (creació de registre `auditoria_post_obra`)  
  *Descripció*: Endpoint que encreua 1) Materials reals consumits (picking), 2) Hores presencials GPS de l'equip, 3) Quilòmetres reals d'odòmetre i 4) Tiquets de despesa de camp aprovats.  
  **Hecho cuando:** La resposta conté la comparativa numèrica "Previst vs. Real" i el nou marge comercial calculat.  
  *Cadena de Test*:  
  `backend/.venv/bin/pytest backend/tests/test_phase2_torre_control_eval.py -k "test_f2_04_fitxa_360_client" -v`

- [ ] **T028 [Backend/Workflow] Alerta de Merma Operativa i Bloqueig de Facturació Directa** (~20 min)  
  *Dependència*: `T027`  
  *Requisits Funcionals*: `FR-006`, `US5`  
  *Skill Mandatòria*: `security-review` ([`.agents/skills/security-review/SKILL.md`](file:///.agents/skills/security-review/SKILL.md))  
  *Eina MCP*: `postgres` (bloqueig de transició a factura)  
  *Descripció*: Si es detecta una caiguda de rendibilitat (>5%) o un consum de material continu desproporcionat (>25%), activa `alerta_merma_oberta = true` i bloqueja l'emissió de factura fins a revisió explícita.  
  **Hecho cuando:** L'intent de facturar directament una feina amb alerta de merma sense revisió és rebutjat amb HTTP 409 Conflict.  
  *Cadena de Test*:  
  `backend/.venv/bin/pytest backend/tests/test_phase2_torre_control_eval.py -k "test_f2_04_fitxa_360_client" -v`

- [ ] **T029 [Backend/API] Aprovació de Pressupost Corregit i Pas a Pre-Factura** (~20 min)  
  *Dependència*: `T028`  
  *Requisits Funcionals*: `FR-002`, `FR-006`, `US5`  
  *Skill Mandatòria*: `supabase-postgres-best-practices` ([`.agents/skills/supabase-postgres-best-practices/SKILL.md`](file:///.agents/skills/supabase-postgres-best-practices/SKILL.md))  
  *Eina MCP*: `postgres` (canvi d'estat a `CONFIRMAT_PER_FACTURAR`)  
  *Descripció*: Endpoint `PUT /api/v1/gestio/copilot/reconciliacio/{id}/aprovar-pressupost` que valida la pre-factura corregida i la transfereix a la safata de comptabilitat per a emissió oficial.  
  **Hecho cuando:** El registre d'auditoria passa a `CONFIRMAT_PER_FACTURAR` i queda llest per a Veri*factu.  
  *Cadena de Test*:  
  `backend/.venv/bin/pytest backend/tests/test_phase2_gestio.py -k "test_comptabilitat_dia0_i_veto_enginyer" -v`

---

## 📦 Bloc 6: Alerta Preventiva de Recompra & Tool Calling Autònom

- [ ] **T030 [Backend/Service] Verificació d'Estoc en Assignació d'Obra** (~20 min)  
  *Dependència*: `T002`  
  *Requisits Funcionals*: `FR-007`, `US6`  
  *Skill Mandatòria*: `supabase-postgres-best-practices` ([`.agents/skills/supabase-postgres-best-practices/SKILL.md`](file:///.agents/skills/supabase-postgres-best-practices/SKILL.md))  
  *Eina MCP*: `postgres` (càlcul de saldo virtual d'estoc)  
  *Descripció*: Endpoint `POST /api/v1/gestio/copilot/stock/verificacio-assignacio` que avalua si el consum previst d'una nova obra reduirà el saldo d'algun material per sota del seu estoc mínim.  
  **Hecho cuando:** La crida retorna la llista d'articles en risc de trencament d'estoc amb la quantitat necessària a demanar.  
  *Cadena de Test*:  
  `backend/.venv/bin/pytest backend/tests/test_033_backorder_ai.py -v`

- [ ] **T031 [Backend/Service] Generació d'Esborrany de Comanda de Recompra (HITL)** (~25 min)  
  *Dependència*: `T030`  
  *Requisits Funcionals*: `FR-002`, `FR-007`, `US6`  
  *Skill Mandatòria*: `security-review` ([`.agents/skills/security-review/SKILL.md`](file:///.agents/skills/security-review/SKILL.md))  
  *Eina MCP*: `postgres` (inserció a taula de comandes esborrany)  
  *Descripció*: Crear una comanda de compra en estat esborrany dirigida al proveïdor preferent amb el material mancant, requerint la confirmació expressa de compres abans de comunicar-la.  
  **Hecho cuando:** L'esborrany apareix a la safata de compres d'administració sense enviar cap comunicació externa automàtica.  
  *Cadena de Test*:  
  `backend/.venv/bin/pytest backend/tests/test_033_backorder_ai.py -k "test_draft_email_sense_auto_enviament" -v`

- [ ] **T032 [Backend/ToolCalling] Eina `get_real_stock` Connectada a PostgreSQL** (~25 min)  
  *Dependència*: `T002`  
  *Requisits Funcionals*: `FR-003`, `US9`  
  *Skill Mandatòria*: `supabase-postgres-best-practices` ([`.agents/skills/supabase-postgres-best-practices/SKILL.md`](file:///.agents/skills/supabase-postgres-best-practices/SKILL.md))  
  *Eina MCP*: `postgres` (execució directa de consulta d'estoc real)  
  *Descripció*: Definició de la Tool de funció cridable pel model LLM que consulta la quantitat física disponible a `estocs_magatzem` sense dades simulades, registrant el log d'auditoria.  
  **Hecho cuando:** La IA invoca `get_real_stock(article_nom="Cable 6mm²")`, obté les unitats reals de PostgreSQL i guarda el registre de crida a la BD.  
  *Cadena de Test*:  
  `backend/.venv/bin/pytest backend/tests/test_phase3_copilot_eval.py -k "test_f3_01_tool_calling_stock_real" -v`

- [ ] **T033 [Backend/ToolCalling] Eina `get_closest_vehicle` mitjançant Càlcul Haversine** (~25 min)  
  *Dependència*: `T002`  
  *Requisits Funcionals*: `FR-003`, `US9`  
  *Skill Mandatòria*: `systematic-debugging` ([`.agents/skills/systematic-debugging/SKILL.md`](file:///.agents/skills/systematic-debugging/SKILL.md))  
  *Eina MCP*: `postgres` (càlcul geodèsic sobre coordenades reals de flota)  
  *Descripció*: Definició de la Tool que calcula la distància geodèsica Haversine entre les coordenades d'una avaria i la posició dels vehicles de la flota per proposar el recurs més proper.  
  **Hecho cuando:** Donats 2 vehicles reals (a 0.4 km i 25 km), l'agent selecciona autònomament el vehicle més proper a 0.4 km.  
  *Cadena de Test*:  
  `backend/.venv/bin/pytest backend/tests/test_phase3_copilot_eval.py -k "test_f3_02_tool_calling_vehicle_proper" -v`

- [ ] **T034 [Backend/API] Confirmació d'Accions Proposades per Tool Calling (`POST /action/confirm`)** (~20 min)  
  *Dependència*: `T032`, `T033`  
  *Requisits Funcionals*: `FR-002`, `US9`  
  *Skill Mandatòria*: `security-review` ([`.agents/skills/security-review/SKILL.md`](file:///.agents/skills/security-review/SKILL.md))  
  *Eina MCP*: `postgres` (execució de l'acció auditada)  
  *Descripció*: Endpoint que rep la confirmació humana de la proposta generada per Tool Calling abans d'executar qualsevol canvi d'assignació d'ordre o comanda de material.  
  **Hecho cuando:** L'acció s'executa exclusivament després de rebre la confirmació d'un usuari amb rol autoritzat.  
  *Cadena de Test*:  
  `backend/.venv/bin/pytest backend/tests/test_phase3_copilot_eval.py -k "test_f3_01_tool_calling_stock_real" -v`

- [ ] **T035 [Backend/AI] Generador de "Pressupost Intel·ligent" basat en Històric** (~25 min)  
  *Dependència*: `T032`  
  *Requisits Funcionals*: `US9`  
  *Skill Mandatòria*: `supabase-postgres-best-practices` ([`.agents/skills/supabase-postgres-best-practices/SKILL.md`](file:///.agents/skills/supabase-postgres-best-practices/SKILL.md))  
  *Eina MCP*: `postgres` (consulta a feines històriques tancades)  
  *Descripció*: Funció que analitza la descripció d'una tasca, cerca feines similars completades anteriorment pel tenant i omple les partides de mà d'obra i materials suggerits aplicant la barema de tarifes oficial.  
  **Hecho cuando:** El botó retorna les partides precompletades en estat d'esborrany sense inventar cap preu.  
  *Cadena de Test*:  
  `backend/.venv/bin/pytest backend/tests/test_phase3_copilot_eval.py -k "test_f3_01_tool_calling_stock_real" -v`

---

## 🛡️ Bloc 7: Copilot RAG Sectorial & Barrera Econòmica Doble Capa

- [ ] **T036 [Backend/Security] Capa 1 (Soft): Classificador Pydantic Anti-Veto Financer** (~25 min)  
  *Dependència*: `T002`  
  *Requisits Funcionals*: `FR-010`, `FR-013`, `US7`  
  *Skill Mandatòria*: `security-and-hardening` ([`.agents/skills/security-and-hardening/SKILL.md`](file:///.agents/skills/security-and-hardening/SKILL.md))  
  *Eina MCP*: `postgres` (registre d'intent denegat a auditoria)  
  *Descripció*: Classificador semàntic basat en esquemes Pydantic que analitza el prompt de l'usuari: si la intenció és econòmica (🔴) i el rol no és `BOSS`, bloqueja immediatament la inferència abans de cridar al model.  
  **Hecho cuando:** Un usuari amb rol `ENGINYER` que pregunta per salaris rep `HTTP 403 Forbidden` amb registre de `denegat_per_rol = True`.  
  *Cadena de Test*:  
  `backend/.venv/bin/pytest backend/tests/test_phase3_copilot_eval.py -k "test_f3_03_veto_financer" -v`

- [ ] **T037 [Backend/Security] Capa 2 (Hard): Infranquejabilitat RLS `economics_boss_only` a PostgreSQL** (~20 min)  
  *Dependència*: `T036`  
  *Requisits Funcionals*: `FR-013`, `US7`  
  *Skill Mandatòria*: `supabase-postgres-best-practices` ([`.agents/skills/supabase-postgres-best-practices/SKILL.md`](file:///.agents/skills/supabase-postgres-best-practices/SKILL.md))  
  *Eina MCP*: `postgres` (verificació de retorn de 0 files per a no-Boss)  
  *Descripció*: Garantir que, fins i tot si la Capa 1 fallés o fos eludida, les consultes SQL a taules financeres des del context del Copilot retornen 0 files davant de rols que no siguin `BOSS`.  
  **Hecho cuando:** La consulta d'agregació econòmica executada amb credencials d'enginyer retorna 0 resultats de forma nativa a la base de dades.  
  *Cadena de Test*:  
  `backend/.venv/bin/pytest backend/tests/test_security_rbac.py -k "test_enginyer_cannot_access_financial_data" -v`

- [ ] **T038 [Backend/Security] Inaccessibilitat Total del Copilot per al Rol Operari** (~20 min)  
  *Dependència*: `T036`  
  *Requisits Funcionals*: `FR-010`, `FR-013`  
  *Skill Mandatòria*: `security-review` ([`.agents/skills/security-review/SKILL.md`](file:///.agents/skills/security-review/SKILL.md))  
  *Eina MCP*: `postgres` (comprovació de bloqueig per rol)  
  *Descripció*: Rebutjar qualsevol petició als endpoints `/api/v1/gestio/copilot/*` provinent d'usuaris amb rol `OPERARI` o `CAP_DE_COLLA`.  
  **Hecho cuando:** L'operari rep HTTP 403 Forbidden taxatiu sense accés a la finestra d'interrogació de l'assistent.  
  *Cadena de Test*:  
  `backend/.venv/bin/pytest backend/tests/test_phase3_copilot_eval.py -k "test_f3_04_copilot_inaccessible_operari" -v`

- [ ] **T039 [Backend/RAG] Indexació i Cerca Semàntica Aïllada per Vertical (`/copilot/rag`)** (~25 min)  
  *Dependència*: `T002`  
  *Requisits Funcionals*: `FR-010`, `US7`  
  *Skill Mandatòria*: `supabase-postgres-best-practices` ([`.agents/skills/supabase-postgres-best-practices/SKILL.md`](file:///.agents/skills/supabase-postgres-best-practices/SKILL.md))  
  *Eina MCP*: `postgres` (emmagatzematge de documents vectorials/documents de coneixement)  
  *Descripció*: Endpoints `POST` i `GET /api/v1/gestio/copilot/rag` per carregar normatives i manuals privats del tenant filtrant consultes exclusivament a la vertical contractada (electricitat, reg, fontaneria).  
  **Hecho cuando:** La cerca RAG retorna fragments rellevants de la documentació pròpia de l'empresa sense barrejar sectors.  
  *Cadena de Test*:  
  `backend/.venv/bin/pytest backend/tests/test_telegram_rag.py -v`

- [ ] **T040 [Backend/API] Endpoint de Xat Tècnic Conversacional (`POST /copilot/xat`)** (~25 min)  
  *Dependència*: `T036`, `T039`  
  *Requisits Funcionals*: `FR-010`, `US7`  
  *Skill Mandatòria*: `security-and-hardening` ([`.agents/skills/security-and-hardening/SKILL.md`](file:///.agents/skills/security-and-hardening/SKILL.md))  
  *Eina MCP*: `postgres` + `chrome-devtools` (interrogació al xat i auditoria de resposta)  
  *Descripció*: Endpoint que orquestra el diàleg tècnic amb context de la feina o client actiu, aportant respostes basades en RAG i executant Tool Calling de forma controlada.  
  **Hecho cuando:** El xat respon en <3 segons citant els protocols de l'empresa i respectant els vetos de rol.  
  *Cadena de Test*:  
  `backend/.venv/bin/pytest backend/tests/test_copilot_xat.py -v`

- [ ] **T041 [Backend/Worker] Generador d'Informe Setmanal Automàtic (Dilluns 08:00 UTC, Boss Only)** (~25 min)  
  *Dependència*: `T037`, `T040`  
  *Requisits Funcionals*: `US11`  
  *Skill Mandatòria*: `security-review` ([`.agents/skills/security-review/SKILL.md`](file:///.agents/skills/security-review/SKILL.md))  
  *Eina MCP*: `postgres` (consulta i compilació d'informe)  
  *Descripció*: Tasca programada a Celery Beat que compila cada dilluns el resum en 3 blocs: 1) Operatiu (feines, incidències), 2) Econòmic (EBITDA, marges, desviacions) i 3) Alertes proactives, enviant-lo exclusivament als usuaris amb rol `BOSS`.  
  **Hecho cuando:** L'informe es genera i es diposita a la bústia de gerència sense que cap altre rol hi tingui accés.  
  *Cadena de Test*:  
  `backend/.venv/bin/pytest backend/tests/test_phase2_gestio.py -k "test_comptabilitat_dia0_i_veto_enginyer" -v`

---

## 📑 Bloc 8: Facturació Veri*factu, PDFs ReportLab & Outbox AEAT

- [ ] **T042 [Backend/PDF] Compilador de Factures Oficials en PDF amb ReportLab 4.1** (~25 min)  
  *Dependència*: `T001`  
  *Requisits Funcionals*: `FR-011`, `US8`  
  *Skill Mandatòria*: `systematic-debugging` ([`.agents/skills/systematic-debugging/SKILL.md`](file:///.agents/skills/systematic-debugging/SKILL.md))  
  *Eina MCP*: `postgres` (comprovació de ruta de fitxer a `/docs/`)  
  *Descripció*: Tasca `generar_factura_verifactu_pdf` a `queue_documents` que maqueta el document legal PDF amb tipografies corporatives, caixetí oficial, desglossament d'IVA i codi QR.  
  **Hecho cuando:** La tasca genera el fitxer PDF a `/docs/<empresa_id>/factures/` amb mida i estructura conformes a la normativa.  
  *Cadena de Test*:  
  `backend/.venv/bin/pytest backend/tests/test_051_factura_hash.py -v`

- [ ] **T043 [Backend/Crypto] Bloqueig Pessimista `SELECT FOR UPDATE` per a Hash SHA-256 Encadenat** (~25 min)  
  *Dependència*: `T042`  
  *Requisits Funcionals*: `FR-011`, `US8`  
  *Skill Mandatòria*: `security-and-hardening` ([`.agents/skills/security-and-hardening/SKILL.md`](file:///.agents/skills/security-and-hardening/SKILL.md))  
  *Eina MCP*: `postgres` (bloqueig de fila i encadenament a `factures_capcalera`)  
  *Descripció*: Garantir que durant l'emissió massiva concurrent de factures s'aplica bloqueig exclusiu sobre l'últim registre per calcular el hash encadenat SHA-256 sense salts ni duplicats.  
  **Hecho cuando:** Dues factures emeses en paral·lel obtenen números correlatius i hashes encadenats consecutius sense col·lisions.  
  *Cadena de Test*:  
  `backend/.venv/bin/pytest backend/tests/test_051_factura_hash.py -k "test_hash_chain" -v`

- [ ] **T044 [Backend/AEAT] Generació de Codi QR Tributari i Payload XML Reglamentari** (~25 min)  
  *Dependència*: `T043`  
  *Requisits Funcionals*: `FR-011`  
  *Skill Mandatòria*: `security-and-hardening` ([`.agents/skills/security-and-hardening/SKILL.md`](file:///.agents/skills/security-and-hardening/SKILL.md))  
  *Eina MCP*: `postgres` (emmagatzematge de dades QR i XML)  
  *Descripció*: Generar l'estructura XML reglamentària segons el reglament Veri*factu (RD 1007/2023) i calcular la cadena unívoca codificada al codi QR per a verificació fiscal.  
  **Hecho cuando:** El codi QR conté la URL de la seu tributària amb NIF, número de sèrie, data i empremta digital calculada.  
  *Cadena de Test*:  
  `backend/.venv/bin/pytest backend/tests/test_052_xml_aeat.py -v`

- [ ] **T045 [Backend/PDF] Generador Asíncron d'Informe Oficial Post-Obra amb Signatures** (~25 min)  
  *Dependència*: `T042`  
  *Requisits Funcionals*: `FR-011`  
  *Skill Mandatòria*: `systematic-debugging` ([`.agents/skills/systematic-debugging/SKILL.md`](file:///.agents/skills/systematic-debugging/SKILL.md))  
  *Eina MCP*: `postgres` (registre d'informe d'obra a la BD)  
  *Descripció*: Tasca Celery `generar_informe_post_obra` a `queue_documents` que compila el dossier final d'obra integrant materials reals, hores, fotos de qualitat i signatura del client.  
  **Hecho cuando:** La tasca produeix el document PDF de tancament d'obra vinculat a l'ordre de treball.  
  *Cadena de Test*:  
  `backend/.venv/bin/pytest backend/tests/test_phase4_telegram_portal_eval.py -k "test_f4_05_generacio_pdf_post_obra" -v`

- [ ] **T046 [Backend/Outbox] Cua Asíncrona `queue_critical` per a Tramesa AEAT amb Reintents** (~25 min)  
  *Dependència*: `T044`  
  *Requisits Funcionals*: `FR-011`  
  *Skill Mandatòria*: `systematic-debugging` ([`.agents/skills/systematic-debugging/SKILL.md`](file:///.agents/skills/systematic-debugging/SKILL.md))  
  *Eina MCP*: `postgres` (transició d'estat a `outbox_enviaments_aeat`)  
  *Descripció*: Tasca Celery `processar_outbox_aeat` que despatxa paquets de facturació cap a la seu tributària amb reintents exponencials (tenacity) si el servei extern cau.  
  **Hecho cuando:** Si la seu tributària no respon, la factura roman a la safata outbox i es reintenta sense congelar cap altre servei.  
  *Cadena de Test*:  
  `backend/.venv/bin/pytest backend/tests/test_024_workers_aeat_backups.py -k "test_processar_outbox_aeat" -v`

---

## ⏰ Bloc 9: Celery Beat Crons & Manteniment Sobirà

- [ ] **T047 [Backend/Cron] Alerta Matinal de Flota (06:00 UTC Diari)** (~20 min)  
  *Dependència*: `T001`  
  *Requisits Funcionals*: `FR-012`  
  *Skill Mandatòria*: `systematic-debugging` ([`.agents/skills/systematic-debugging/SKILL.md`](file:///.agents/skills/systematic-debugging/SKILL.md))  
  *Eina MCP*: `postgres` (verificació d'alertes generades a la BD)  
  *Descripció*: Tasca periòdica de Celery Beat que revisa caducitats d'ITV i assegurances a 30, 15, 5 i 1 dia, generant alertes a la safata de flota.  
  **Hecho cuando:** La tasca s'executa a les 06:00 i genera avisos per a vehicles amb documentació propera a expirar.  
  *Cadena de Test*:  
  `backend/.venv/bin/pytest backend/tests/test_006_gestio_flota.py -k "test_alertes_itv_flota" -v`

- [ ] **T048 [Backend/Cron] Cautela i Tancament de Jornades Obertes (23:59 UTC Diari)** (~20 min)  
  *Dependència*: `T001`  
  *Requisits Funcionals*: `FR-012`  
  *Skill Mandatòria*: `systematic-debugging` ([`.agents/skills/systematic-debugging/SKILL.md`](file:///.agents/skills/systematic-debugging/SKILL.md))  
  *Eina MCP*: `postgres` (actualització de torns anòmals a PostgreSQL)  
  *Descripció*: Tasca de mitjanit que detecta jornades laborals que han quedat obertes més de 12 hores per oblit de l'operari, marcant-les `ANOMALIA_REVISIO` per a RRHH.  
  **Hecho cuando:** Els registres oblidats queden tancats cautelarment amb l'avís d'anomalia sense pèrdua de dades.  
  *Cadena de Test*:  
  `backend/.venv/bin/pytest backend/tests/test_013_operari_jornada.py -k "test_jornada_mes_de_8h_permesa" -v`

- [ ] **T049 [Backend/Cron] Purga de Tokens Temporals Expirats de 24 Hores (Cada Hora)** (~20 min)  
  *Dependència*: `T001`, `T023`  
  *Requisits Funcionals*: `FR-003`, `FR-012`  
  *Skill Mandatòria*: `security-and-hardening` ([`.agents/skills/security-and-hardening/SKILL.md`](file:///.agents/skills/security-and-hardening/SKILL.md))  
  *Eina MCP*: `postgres` (eliminació de tokens caducats)  
  *Descripció*: Neteja periòdica dels enllaços efímers de descàrrega de factures i tokens d'invitació caducats per evitar acumulació a Redis i PostgreSQL.  
  **Hecho cuando:** Els tokens amb més de 24h d'antiguitat s'eliminen automàticament de la memòria cau i la BD.  
  *Cadena de Test*:  
  `backend/.venv/bin/pytest backend/tests/test_bot_telegram.py -k "test_enllac_efimer" -v`

- [ ] **T050 [Backend/Cron] Còpia de Seguretat Setmanal Sobirana amb `pg_dump` Xifrat** (~25 min)  
  *Dependència*: `T001`  
  *Requisits Funcionals*: `FR-003`  
  *Skill Mandatòria*: `security-and-hardening` ([`.agents/skills/security-and-hardening/SKILL.md`](file:///.agents/skills/security-and-hardening/SKILL.md))  
  *Eina MCP*: `postgres` (comprovació de dump complet per empresa)  
  *Descripció*: Tasca `generar_backup_pgdump` (diumenges 02:00 UTC) que genera un bolcat complet de la base de dades comprimit en gzip a `/data/<empresa_id>/backups/` excloent la pròpia carpeta per evitar recursió.  
  **Hecho cuando:** El fitxer `.sql.gz` es crea amb èxit al directori sobirà de l'empresa amb permisos restringits.  
  *Cadena de Test*:  
  `backend/.venv/bin/pytest backend/tests/test_024_workers_aeat_backups.py -k "test_generacio_backup_celery" -v`

---

## 🏆 Bloc 10: Suite d'Auditoria Zero Mock & Verificació en Viu

- [ ] **T051 [QA/Pytest] Execució de la Suite de Core IA, Copilot i Workers** (~25 min)  
  *Dependència*: `T001` fins a `T050`  
  *Requisits Funcionals*: `FR-001`, `FR-002`, `SC-001` a `SC-006`  
  *Skill Mandatòria*: `systematic-debugging` ([`.agents/skills/systematic-debugging/SKILL.md`](file:///.agents/skills/systematic-debugging/SKILL.md))  
  *Eina MCP*: `postgres` (aïllament RLS certificat)  
  *Descripció*: Executar tots els tests d'integració de Copilot, Tool Calling, Whisper, Celery i Veri*factu certificant que passen al 100% nets sense falsos positius ni dades simulades.  
  **Hecho cuando:** La suite completa de tests de la Spec 03 s'executa amb resultat `100% passed`.  
  *Cadena de Test*:  
  `backend/.venv/bin/pytest backend/tests/test_phase3_copilot_eval.py backend/tests/test_024_workers_aeat_backups.py backend/tests/test_024_celery_ping_async.py backend/tests/test_051_factura_hash.py backend/tests/test_052_xml_aeat.py -v`

- [ ] **T052 [QA/Pytest] Execució de la Suite del Bot de Telegram i Portal Client** (~25 min)  
  *Dependència*: `T016` fins a `T024`  
  *Requisits Funcionals*: `FR-008`, `FR-009`, `SC-004`  
  *Skill Mandatòria*: `security-review` ([`.agents/skills/security-review/SKILL.md`](file:///.agents/skills/security-review/SKILL.md))  
  *Eina MCP*: `postgres` (comprovació de callbacks i estats de pressupost)  
  *Descripció*: Executar els tests d'aprovació i rebuig de pressupostos per Telegram, gestió d'usuaris desconeguts i generació d'albarans post-obra.  
  **Hecho cuando:** Tots els tests de Telegram passen en verd (`100% passed`) cobrint tots els criteris d'acceptació.  
  *Cadena de Test*:  
  `backend/.venv/bin/pytest backend/tests/test_phase4_telegram_portal_eval.py backend/tests/test_bot_telegram.py -v`

- [ ] **T053 [QA/MCP] Verificació en Viu amb Chrome DevTools MCP (Albarà OCR i Xat Copilot)** (~25 min)  
  *Dependència*: `T007`, `T040`, `T051`  
  *Requisits Funcionals*: `FR-001`, `FR-002`  
  *Skill Mandatòria*: `frontend-design` ([`.agents/skills/frontend-design/SKILL.md`](file:///.agents/skills/frontend-design/SKILL.md))  
  *Eina MCP*: `chrome-devtools` (interacció real a la UI, pujada de fitxer i xat)  
  *Descripció*: Utilitzar `chrome-devtools` per navegar a `/gestio`, pujar un albarà real des de `/demo_docs`, comprovar la recepció de l'esborrany precompletat, obrir la finestra del Copilot i fer una consulta tècnica verificant que no hi ha errors a la consola (`list_console_messages`).  
  **Hecho cuando:** `chrome-devtools` captura pantalla de l'albarà preomplert i certifica que les dades viatgen exclusivament contra els endpoints de FastAPI en temps real.  
  *Cadena de Test*:  
  `mcp_chrome-devtools_navigate_page` (`http://localhost:3000/gestio`) + `mcp_chrome-devtools_take_screenshot`

- [ ] **T054 [QA/MCP] Auditoria de Persistència Física a PostgreSQL viu amb MCP `postgres`** (~20 min)  
  *Dependència*: `T051`, `T052`, `T053`  
  *Requisits Funcionals*: `FR-001`, `FR-003`  
  *Skill Mandatòria*: `supabase-postgres-best-practices` ([`.agents/skills/supabase-postgres-best-practices/SKILL.md`](file:///.agents/skills/supabase-postgres-best-practices/SKILL.md))  
  *Eina MCP*: `postgres` (consultes SQL d'auditoria Zero Mock)  
  *Descripció*: Executar consultes directes amb `postgres.query` per certificar la inserció de memoràndums, registres outbox AEAT, quotes de tiquets OCR i l'aïllament RLS estricte amb `SET LOCAL app.current_empresa_id = :id`.  
  **Hecho cuando:** Les consultes SQL confirmen que els registres existeixen a la base de dades i que cap usuari no-Boss pot llegir dades financeres.  
  *Cadena de Test*:  
  `mcp_postgres_query` amb `SELECT count(*) FROM memorandum_tecnic WHERE empresa_id = '...'`
