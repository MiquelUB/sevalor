# Tasks: Motor de Prospecció Atòmica per Codi Postal, Lead Scoring Evolutiu, Seqüències de 3 Emails amb Calendari i Correu Bidireccional (Spec 007)

**Feature Path**: `sevalor_AgentV2/specs/007-superadmin-crm-prospeccio-leads`  
**Prerequisites**: [`spec.md`](file:///media/akaun/Project_1/SEVALOR/sevalor_AgentV2/specs/007-superadmin-crm-prospeccio-leads/spec.md), [`plan.md`](file:///media/akaun/Project_1/SEVALOR/sevalor_AgentV2/specs/007-superadmin-crm-prospeccio-leads/plan.md), [`constitution.md`](file:///media/akaun/Project_1/SEVALOR/constitution.md)  
**Norma Suprema**: Zero Mock Data, Human-in-the-Loop (HITL) absolut en correus, Segregació Zero-Trust (`SUPERADMIN`), absència de `db.refresh()`, i validació 100% en verd de tots els tests segons [`Auditoria_i_Normativa_Tests_Backend.md`](file:///media/akaun/Project_1/SEVALOR/sevalor_AgentV2/docs/sdd_sevalor_legacy/Auditoria_i_Normativa_Tests_Backend.md).  
**Skills Mandatòries a Activar**: `supabase-postgres-best-practices`, `security-and-hardening`, `frontend-design`, `systematic-debugging`, `security-review`.

---

## Phase 1: Model de Dades i Migracions PostgreSQL (`supabase-postgres-best-practices`)

- [x] **T001** Ampliar els models SQLAlchemy [`SaasLead`](file:///media/akaun/Project_1/SEVALOR/backend/app/models/models.py#L2143) i [`SaasOportunitat`](file:///media/akaun/Project_1/SEVALOR/backend/app/models/models.py#L2183) a `backend/app/models/models.py`:
  - A `SaasLead`: `cif`, `web_url`, `domini_normalitzat`, `adreca_fisica`, `adreca_normalitzada`, `codi_postal`, `carrec_contacte`, `fonts_investigades`, `fita_recent`, `punt_dolor_detectat`, `angle_atac`, `score_qualificacio`, `justificacio_ia`, `mx_validat`, `rao_tancament_exit`, `es_tancament_replicable` i `tasca_prospeccio_id`.
  - A `SaasOportunitat`: `rao_tancament_exit`, `requisits_replicables` i `es_replicable`.
- [x] **T002** Crear a `backend/app/models/models.py` els nous models SQLAlchemy per al CRM de Superadmin:
  - `SaasProspeccioTasca` (`saas_prospeccio_tasques` — amb `vertical` de text lliure i comptador `total_duplicats`).
  - `SaasProspeccioCandidat` (`saas_prospeccio_candidats` — amb `adreca_fisica`, `adreca_normalitzada`, `fonts_investigades`, `vector_duplicitat` i `motiu_correccio_humana`).
  - `SaasCriteriFeedback` (`saas_criteris_feedback` — suportant tant `CORRECCIO_DESCART` / `CORRECCIO_SELECCIO` com `TANCAMENT_EXIT_REPLICABLE`).
  - `SaasCorreuMissatge` (`saas_correu_missatges` — suportant la campanya de 3 correus amb `pas_sequencia` `1..3`, `tempo_dies_offset` `0, 4, 8`, `data_programada` per al Calendari Comercial i esdeveniments de seguiment).
  - `SaasExclusioRgpd` (`saas_exclusio_rgpd`).
- [x] **T003** Crear i aplicar la migració SQL idempotent a PostgreSQL amb índexs sobre `codi_postal`, `domini_normalitzat`, `adreca_normalitzada`, `cif`, `data_programada`, `message_id` i `in_reply_to`.
- [x] **T004** Afegir variables de configuració a [`backend/app/core/config.py`](file:///media/akaun/Project_1/SEVALOR/backend/app/core/config.py) per a `FIRECRAWL_API_URL`, `OPENROUTER_API_KEY`, `OPENROUTER_MODEL` (`deepseek/deepseek-chat`), i credencials de `STALWART_SMTP_HOST`, `STALWART_IMAP_HOST` i `SUPERADMIN_OUTREACH_EMAIL` (`tecnic@sevalor.net`).

---

## Phase 2: Serveis Core — Cerca Multi-Canal, Deduplicació 3 Vectors, MX Shield i DeepSeek (`security-and-hardening`)

- [x] **T005** [US1] Implementar `backend/app/services/firecrawl_service.py`:
  - **Cerca Multi-Canal Àmplia**: Extracció tant del web corporatiu com de perfils i publicacions públiques a **LinkedIn, Instagram, premsa local i adjudicacions** per descobrir el Gatekeeper i fites recents.
  - **Deduplicació Multi-Validació per 3 Vectors (`verificar_duplicitat_multivector`)**: Comprovació normalitzada de **Domini Web**, **Adreça Física** i **CIF**; si un o més coincideix amb un registre existent (`saas_leads`, `empreses` o `saas_exclusio_rgpd`), retorna `DUPLICAT` indicant quin vector ha coincidit.
- [x] **T006** [US3] Implementar `backend/app/services/mx_shield_service.py`:
  - Validació RFC 5322, filtre de dominis temporals/genèrics, comprovació contra `saas_exclusio_rgpd` i verificació asíncrona de registres DNS `MX`.
- [x] **T007** [US2/US3] Implementar `backend/app/services/openrouter_prospecting_service.py`:
  - Integració amb OpenRouter (DeepSeek) sobre qualsevol **vertical escrita lliurement per l'humà**.
  - **Doble Bucle d'Aprenentatge al System Prompt**:
    1. Injecció de les regles i justificacions humanes de descarts/seleccions (`CORRECCIO_DESCART`, `CORRECCIO_SELECCIO`).
    2. Injecció dels **Tancaments d'Èxit Replicables (`TANCAMENT_EXIT_REPLICABLE`)** per donar prioritat a empreses que compleixin els mateixos requisits (*lookalike matching*) i replicar la raó d'èxit.
  - **Generació de la Campanya de 3 Emails amb Tempo**:
    - `Email 1 (Dia 0)`: 5 passos (Gatekeeper $\rightarrow$ Fita recent Web/LinkedIn/Instagram $\rightarrow$ Dolor operatiu $\rightarrow$ Solució Sevalor amb PWA `/operari`, `/gestio` i Bot Oficial de Telegram $\rightarrow$ CTA Demo, sense cap menció a WhatsApp).
    - `Email 2 (Dia +4)`: Seguiment d'autoritat amb cas d'èxit replicable del seu sector.
    - `Email 3 (Dia +8)`: Últim impacte de diagnòstic i proposta d'activació de la Demo Real de 7 Dies.

---

## Phase 3: Servei de Correu Bidireccional (Stalwart + Thunderbird) i Calendari Comercial (`security-and-hardening`)

- [x] **T008** [US3/US4] Implementar `backend/app/services/stalwart_mail_service.py`:
  - Programació automàtica dels **3 correus de la campanya al Calendari Comercial** (`ESBORRANY_PROGRAMAT` a $T_0$, $T_0 + 4\text{d}$ i $T_0 + 8\text{d}$) en qualificar un lead.
  - Enviament SMTP des de `tecnic@sevalor.net` exclusivament sota aprovació humana (HITL), amb generació de `Message-ID` RFC 5322, encadenament `In-Reply-To` / `References` i sincronització IMAP amb **Mozilla Thunderbird**.
- [x] **T009** [US4] Implementar la qualificació automàtica de respostes entrants (`INBOUND`) i la seva acció sobre el Calendari i el Kanban:
  - **Pausa automàtica de seqüència**: Quan un lead respon a l'`Email 1` (o `Email 2`), tots els correus pendents d'aquell lead al Calendari passen automàticament a `PAUSAT_PER_RESPOSTA`.
  - Classificació d'intenció amb DeepSeek (`INTERESSAT_DEMO`, `INTERESSAT_INFO`, `OBJECCIO_TEMPS`, `NO_INTERESSAT`, `BAIXA_OPTOUT`, `OUT_OF_OFFICE`).
  - Si és `OBJECCIO_TEMPS`, creació automàtica d'un esdeveniment `SEGUIMENT_CALENDARI` en la data sol·licitada pel prospecte.
  - Si és `BAIXA_OPTOUT`, cancel·lació de tots els esdeveniments del Calendari, pas a `DESCARTAT` / `PERDUT` i registre permanent a `saas_exclusio_rgpd`.
- [x] **T010** Configurar el servei `stalwart-mail` a `docker-compose.yml` per al desplegament sobirà a Hetzner.

---

## Phase 4: Endpoints API REST i Streaming SSE a `/superadmin/crm/prospeccio`

- [x] **T011** [US1] Ampliar [`backend/app/api/v1/superadmin/crm_prospeccio.py`](file:///media/akaun/Project_1/SEVALOR/backend/app/api/v1/superadmin/crm_prospeccio.py) amb els endpoints de lots atòmics per Codi Postal i Vertical Lliure:
  - `POST /tasques-cp`: Accepta qualsevol `vertical` escrita per l'humà + `codi_postal` + `operaris_minims`.
  - `GET /tasques-cp`, `GET /tasques-cp/{tasca_id}` i `GET /tasques-cp/{tasca_id}/stream` (SSE en temps real).
- [x] **T012** [US2] Afegir els endpoints del Doble Bucle d'Aprenentatge:
  - `POST /candidats/{candidat_id}/corregir-criteri`: **Valida obligatòriament que `motiu_correccio_humana` no estigui buit ($\ge 10$ caràcters)**, inverteix la decisió, crea/descarta el lead amb la seva campanya de 3 correus i registra l'aprenentatge a `saas_criteris_feedback`.
  - `POST /oportunitats/{oportunitat_id}/registrar-exit`: Marca l'oportunitat com a `GUANYAT`, desa la **Raó del Tancament (`rao_tancament_exit`)**, els requisits clau i `es_replicable = True` a `saas_criteris_feedback` (`TANCAMENT_EXIT_REPLICABLE`).
  - `GET /criteris-feedback`: Llista les regles de descart i els patrons d'èxit replicables.
- [x] **T013** [US3/US4] Afegir els endpoints del **Calendari Comercial Integrat**, Campanya de 3 Emails i Correu Bidireccional:
  - `GET /calendari`: Retorna tots els esdeveniments del Calendari Comercial (els 3 correus amb el seu tempo `Dia 0`, `Dia +4`, `Dia +8`, les demos agendades, els seguiments d'objeccions de temps i els venciments de Demos de 7 dies).
  - `POST /calendari/esdeveniments`: Permet agendar manualment un seguiment o reunió al Calendari.
  - `PUT /correus/{correu_id}/esborrany`: Edita assumpte, cos o `data_programada` d'un correu de la seqüència.
  - `POST /correus/{correu_id}/enviar`: **Acció HITL** que aprova i envia el correu programat des de `tecnic@sevalor.net`.
  - `GET /leads/{lead_id}/correus`, `POST /leads/{lead_id}/validar-mx`, `POST /correu/sincronitzar-inbound`, i `GET` / `POST /exclusio-rgpd`.

---

## Phase 5: Interfície d'Usuari a `/superadmin/crm` (`frontend-design`)

- [x] **T014** [US1/US2] Ampliar [`pwa/src/app/superadmin/crm/page.tsx`](file:///media/akaun/Project_1/SEVALOR/pwa/src/app/superadmin/crm/page.tsx) amb la pestanya **"Explorador de Leads per CP"**:
  - Input de text lliure per a la **Vertical / Sector escrit per l'humà**, input `Codi Postal` i `Mínim Operaris`.
  - Consola SSE en temps real amb l'avanç d'investigació multi-canal (Web, LinkedIn, Instagram, Premsa) i deduplicació multi-validació.
  - Taula d'auditoria transparent (`Seleccionades`, `Descartades`, `Duplicades`) i modal **"Corregir Criteri"** amb **camp de justificació humana obligatori**.
- [x] **T015** [US3/US4] Crear la nova pestanya indispensable **"Calendari Comercial & Campanyes"** a [`pwa/src/app/superadmin/crm/page.tsx`](file:///media/akaun/Project_1/SEVALOR/pwa/src/app/superadmin/crm/page.tsx):
  - Vista de Calendari visual i Agenda Diària mostrant els **3 emails de cada campanya segons el seu tempo** (`Pas 1 [D0]`, `Pas 2 [D+4]`, `Pas 3 [D+8]`), reunions, seguiments per objecció de temps i Demos de 7 dies.
  - Revisió, edició i botó **"Aprovar i Enviar des de tecnic@sevalor.net"** directament des del Calendari i des de la fitxa del prospecte.
- [x] **T016** [US2] Afegir al Kanban i a la fitxa del prospecte el modal **"Registrar Tancament d'Èxit Replicable (`GUANYAT`)"** per capturar la raó per la qual l'empresa ens ha contractat i activar la cerca d'empreses bessones (*lookalikes*).

---

## Phase 6: Suite de Tests Automatitzats (Pytest Backend & Playwright E2E)

- [x] **T017** Crear `backend/tests/test_crm_leads_outreach.py` verificant contra PostgreSQL real (sense mocks de BD ni `db.refresh()`):
  1. `test_execucio_atomica_cp_vertical_lliure_i_cerca_multicanal`: Verifica que l'operador pot enviar qualsevol nom de vertical escrit lliurement (ex. `"Manteniment de climatització industrial"`), registra candidats seleccionats i descartats amb fonts multi-canal (`web`, `linkedin`, `instagram`) i finalitza el CP `25001` sense encadenar el `25002`.
  2. `test_deduplicacio_multivalidacio_3_vectors`: Verifica que un candidat sense CIF però amb el mateix **Domini Web** o la mateixa **Adreça Física** (o el mateix **CIF**) que un registre existent es detecta com a `DUPLICAT` i no crea un lead repetit.
  3. `test_corregir_criteri_exigeix_justificacio_humana_obligatoria`: Verifica que intentar descartar o seleccionar un candidat sense `motiu_correccio_humana` retorna error de validació (`400`/`422`), i que en aportar la justificació s'actualitza el candidat i es desa la regla a `saas_criteris_feedback`.
  4. `test_aprenentatge_tancament_exit_guanyat_replicable`: Verifica que en tancar una oportunitat com a `GUANYAT` indicant la `rao_tancament_exit` i `es_replicable = True`, es crea el patró `TANCAMENT_EXIT_REPLICABLE` i s'inclou al context d'aprenentatge per buscar empreses amb els mateixos requisits.
  5. `test_campanya_3_emails_tempo_i_calendari_comercial`: Verifica que en qualificar un lead es generen els **3 correus de la campanya** amb el seu tempo (`Dia 0`, `Dia +4`, `Dia +8`) sense mencions a WhatsApp (utilitzant PWA + Telegram), i que tots 3 apareixen consultables a l'endpoint `/calendari`.
  6. `test_enviament_hitl_i_pausa_automatica_sequencia_en_respondre`: Verifica que l'`Email 1` s'envia només amb aprovació humana (`Message-ID` RFC 5322) i que, quan entra una resposta `INBOUND` (`In-Reply-To`), l'`Email 2` i l'`Email 3` programats al Calendari passen automàticament a `PAUSAT_PER_RESPOSTA`.
  7. `test_inbound_objeccio_temps_agenda_al_calendari_i_optout_rgpd`: Verifica que una resposta classificada com a `OBJECCIO_TEMPS` agenda automàticament un esdeveniment de seguiment al Calendari Comercial, i que una resposta `BAIXA_OPTOUT` cancel·la el calendari i afegeix el domini a `saas_exclusio_rgpd`.
  8. `test_zero_trust_rbac_prospeccio_i_calendari`: Verifica que qualsevol usuari amb rol `BOSS`, `GESTOR` o `OPERARI` rep `403 Forbidden` en tots els nous endpoints.
- [x] **T018** Crear/ampliar el test E2E de Playwright per verificar a `/superadmin/crm`: la cerca per CP amb vertical lliure, la justificació obligatòria en descartar, la vista del **Calendari Comercial** amb la seqüència de 3 correus i el registre de tancament d'èxit replicable.

---

## Phase 7: Auditoria Final i Validació Neta (Definition of Done)

- [x] **T019** Llegir obligatòriament [`Auditoria_i_Normativa_Tests_Backend.md`](file:///media/akaun/Project_1/SEVALOR/sevalor_AgentV2/docs/sdd_sevalor_legacy/Auditoria_i_Normativa_Tests_Backend.md) i executar tots els tests del mòdul CRM:
  - `cd backend && pytest tests/test_crm_prospeccio.py tests/test_crm_leads_outreach.py -v`
- [x] **T020** Executar validació d'estil i tipat estricte al backend:
  - `cd backend && ruff check app/api/v1/superadmin/ app/services/ tests/test_crm_*.py`
  - `cd backend && mypy app/api/v1/superadmin/crm_prospeccio.py`
- [x] **T021** Executar compilació estricta del frontend Next.js:
  - `cd pwa && npm run build`
