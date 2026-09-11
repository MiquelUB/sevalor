# Pla d'Implementació — Spec 012: Mòdul d'IA Copilot de Camp i Gestió (/gestio/copilot & PWA)

El Copilot d'IA de CampoPro Suite és el **motor pericial, assistent tècnic i cor intel·ligent** de la plataforma. Assisteix en temps real als quatre actors (Operari a la PWA, Enginyer a l'Oficina Tècnica, Secretaria/Boss a Administració i Client Final). Aquest pla detalla la implementació sota els tres principis innegociables:
1. **Principi Innegociable Human-in-the-Loop (HITL)**: El Copilot audita, transcriu, calcula i proposa; mai emet factures ni comandes a proveïdors sense confirmació humana explícita.
2. **Sobirania i Processament 100% Local**: Node d'IA local allotjat a Hetzner Falkenstein (Alemanya - UE) amb Whisper v3 INT8 en CPU. Zero fuita de dades a núvols públics privatius (OpenAI, Anthropic, AWS S3).
3. **Tolerància Zero a Dades Fictícies (Zero Mock Data)**: Estat inicial de Dia 0 real. Davant d'elements sense historial, declara estrictament: *"No tinc informació registrada sobre aquest element"*.

---

## Canvis Proposats

### 1. Base de Dades i Migració SQL (`db/migrations/014_copilot_ia.sql`)
- Ampliació de la taula `empreses`:
  - `vertical VARCHAR(50) NOT NULL DEFAULT 'CAMPOPRO' CHECK (vertical IN ('CAMPOPRO', 'ELECTRICPRO', 'HYDROPRO', 'BUILDINGPRO'))`
  - `node_ia_url VARCHAR(255) DEFAULT 'http://localhost:11434'`
  - `node_ia_actiu BOOLEAN NOT NULL DEFAULT true`
- Creació de la taula `memorandums_tecnics_copilot`:
  - Peritatge multimodal de veu i foto d'incidències de camp (RF-08, RF-09).
  - Camps: `id`, `empresa_id`, `ordre_treball_id`, `incidencia_id`, `transcripcio_audio`, `confianca_acustica` (NUMERIC), `avis_soroll_sever` (BOOLEAN, EDGE-03), `analisi_visual`, `dictamen_pericial` (`EXTRA_FACTURABLE`, `COST_NO_IMPUTABLE`), `motiu_dictamen`, `estimacio_temps_extra_minuts`, `estimacio_materials_extra` (JSONB), `cost_estimat_total`, `validat_per_enginyer` (BOOLEAN), `enginyer_validador_id`, `data_validacio`, `observacions_enginyer`, `estat` (`PROPOSTA`, `APROVAT`, `REBUTJAT`, `EDITAT`), `created_at`, `updated_at`.
- Creació de la taula `auditories_post_obra`:
  - Reconciliació integral dels 4 pilars del cost real post-feina (RF-11, RF-12).
  - Camps: `id`, `empresa_id`, `ordre_treball_id`, `desviacio_hores`, `desviacio_materials` (JSONB), `desviacio_km`, `despeses_camp`, `marge_previst_percentatge`, `marge_real_liquidat_percentatge`, `alerta_merma_operativa` (BOOLEAN), `detall_merma`, `bloqueig_consum_excessiu` (BOOLEAN, EDGE-08), `bloqueig_sync_pendent` (BOOLEAN, EDGE-04), `pressupost_corregit_proposta` (JSONB), `estat` (`PENDENT_CONFIRMACIO`, `APROVAT_ENGINYER`, `ENVIAT_FACTURACIO`, `REBUTJAT`), `enginyer_id`, `data_aprovacio`, `created_at`, `updated_at`.
- Creació de la taula `alertes_garantia_recompra`:
  - Detecció preventiva de garanties de fabricant i comandes de reposició de stock per assignació (RF-05, RF-06, RF-07, RF-14, RF-15, EDGE-06, EDGE-07).
  - Camps: `id`, `empresa_id`, `ordre_treball_id`, `tipus_alerta` (`GARANTIA_FABRICANT`, `GARANTIA_INTERNA_SERVEI`, `CORTESIA_EXPIRADA`, `RECOMPRA_STOCK`), `article_id`, `numero_serie`, `proveidor_id`, `missatge`, `data_fi_garantia`, `estat` (`ACTIVA`, `RESOLTA`, `DESCARTADA`), `dades_comanda_proposta` (JSONB), `created_at`, `updated_at`.
- Creació de la taula `consultes_xat_copilot`:
  - Registre de converses del xat tècnic amb RAG multinivell, mètrica d'inferència i aïllament de domini (RF-16, RF-19, RF-20, RF-20.1, EDGE-05, EDGE-10).
  - Camps: `id`, `empresa_id`, `usuari_id`, `pregunta`, `resposta`, `vertical`, `temps_inferencia_ms`, `enllacos_relacionats` (JSONB), `es_error_timeout` (BOOLEAN), `denegat_per_rol` (BOOLEAN), `created_at`.
- Directiva `FORCE ROW LEVEL SECURITY` i polítiques multi-tenant per a totes les taules.
- Triggers d'actualització de timestamps `update_updated_at_column`.

---

### 2. Models ORM SQLAlchemy (`backend/app/models/models.py`)
- Afegir `vertical`, `node_ia_url`, `node_ia_actiu` al model `Empresa`.
- Declarar les classes:
  - `MemorandumTecnicCopilot`
  - `AuditoriaPostObra`
  - `AlertaGarantiaRecompra`
  - `ConsultaXatCopilot`

---

### 3. API Router FastAPI (`backend/app/api/v1/gestio/copilot.py`)
- **Node i Telemetria IA**:
  - `GET /gestio/copilot/estat-node`: Retorna l'estat operatiu del node Hetzner Falkenstein, model Whisper v3 INT8 en CPU, latència de resposta i vertical activa.
- **Memòria Històrica i Garanties**:
  - `GET /gestio/copilot/garanties/auditoria`: Audita finques (365 dies d'historial) i equips per número de sèrie. Detecta garanties de fabricant (2-3 anys), garantia interna de mà d'obra (<3 mesos, 0 €) i cortesia de proveïdor si fa poc que ha expirat (EDGE-07). Davant d'elements sense historial, retorna fidelment el text Zero Mock Data (EDGE-09).
- **Peritatge Multimodal d'Incidències (Veu i Foto)**:
  - `POST /gestio/copilot/incidencies/peritatge`: Processa nota de veu i fotografia. Si la confiança acústica és < 40%, afegeix advertència de soroll sever de tractor/vent (EDGE-03). Classifica en `EXTRA_FACTURABLE` vs `COST_NO_IMPUTABLE` i genera el memoràndum tècnic en estat proposta.
  - `PUT /gestio/copilot/memorandums/{id}/validacio`: Validació HITL de l'Enginyer (RF-10) per aprovar, editar o rebutjar el memoràndum abans de cap tramesa al client.
  - `GET /gestio/copilot/memorandums`: Llistat de memoràndums tècnics registrats.
- **Reconciliació Post-Obra i Pressupost Corregit**:
  - `POST /gestio/copilot/reconciliacio/post-obra`: Reconcilia els 4 pilars (materials magatzem, presència horària, km flota i tiquets de camp). Detecta caiguda de marge comercial. Si hi ha sincronització pendent offline (EDGE-04), bloca la generació de pre-factura. Si hi ha consum > 250% de material continu sense incidència prèvia (EDGE-08), emet alerta de merma operativa i bloca. Genera la proposta de pressupost corregit.
  - `PUT /gestio/copilot/reconciliacio/{id}/aprovar-pressupost`: Confirmació humana indispensable de l'Enginyer (RF-13) abans d'enviar el document a facturació.
- **Alerta Preventiva de Stock en Assignació**:
  - `POST /gestio/copilot/stock/verificacio-assignacio`: Comprova estoc disponible en assignar ordre. Utilitza `SELECT FOR UPDATE` per protecció de concurrència (EDGE-06). Genera esborrany de comanda de reposició si cau sota mínims de seguretat (RF-14, RF-15).
- **Xat Tècnic amb RAG Local i Veto de Rols**:
  - `POST /gestio/copilot/xat`: Respon consultes operatives (flota, ITV, normatives d'ofici, protocols RAG).
  - **Veto Financer d'Enginyer (RF-20.1 / EDGE-05)**: Si l'usuari amb rol `ENGINYER` demana dades de salaris, nòmines, llibre major o comptes bancaris de proveïdors, l'endpoint retorna `HTTP 403 Forbidden` amb `"Consulta no autoritzada per política de rols de seguretat"`.
  - **Aïllament de Vertical (EDGE-10)**: Si es formulen preguntes creuades entre sectors (ex. baixa tensió elèctrica REBT sota empresa de reg o viceversa), el Copilot declina indicant l'acotació exclusiva al seu domini.
  - `GET /gestio/copilot/alertes`: Llistat d'alertes actives de garantia i reposició de stock.
- Registre del router a `backend/app/main.py`.

---

### 4. Bateria de Proves de Backend (`backend/tests/test_copilot.py`)
Suite exhaustiva en Docker (`campopro-backend:latest`) amb 11 casos de prova per verificar el 100% dels requisits i casos límit:
1. `test_estat_node_ia_sobirana_cpu_only`: RF-01, RF-02.
2. `test_auditoria_garanties_fabricant_i_cortesia`: RF-05, RF-06, EDGE-07.
3. `test_garantia_interna_servei_cost_zero`: RF-07.
4. `test_zero_mock_data_finca_sense_historial`: RF-21, RF-22, EDGE-09.
5. `test_peritatge_multimodal_i_soroll_sever`: RF-08, RF-09, EDGE-03.
6. `test_hitl_validacio_memorandum_enginyer`: RF-10.
7. `test_reconciliacio_desviacio_marge_i_sync_pendent`: RF-11, RF-12, EDGE-04.
8. `test_bloqueig_merma_excessiva_250_percent`: EDGE-08.
9. `test_hitl_confirmacio_pressupost_corregit`: RF-13.
10. `test_alerta_stock_assignacio_i_concurrencia_select_for_update`: RF-14, RF-15, EDGE-06.
11. `test_xat_veto_enginyer_403_i_aillament_vertical`: RF-16, RF-17, RF-20.1, EDGE-05, EDGE-10.

---

### 5. Interfície d'Usuari Frontend (`pwa/src/app/gestio/copilot/page.tsx`) & Navegació
- Modificació de `pwa/src/app/gestio/layout.tsx`:
  - Afegir enllaç a `navLinks`: `{ label: "Copilot IA & Peritatge", href: "/gestio/copilot", icon: Sparkles, badge: "IA" }`.
  - Afegir element a `itemsSpotlight` per accés ràpid via Ctrl+K.
- Pàgina `/gestio/copilot/page.tsx`:
  - **Barra de Telemetria Superior**: Estat del node local Hetzner Falkenstein, model Whisper v3 INT8 en CPU, latència de resposta, vertical activa (`CAMPOPRO`) i selector interactiu de rol per comprovar en viu el Veto d'Enginyer (403).
  - **Pestanya 1: Memòria Tècnica & Garanties**: Selector de finques (amb historial de 365 dies), escaneig per número de sèrie, targeta d'avís de garantia oficial de fabricant amb proposta RMA a proveïdor, garantia interna de servei (3 mesos, 0 €), alerta de cortesia per recent expiració, i estat buit canònic Dia 0 ("No tinc informació registrada sobre aquest element").
  - **Pestanya 2: Peritatge d'Incidències (Veu & Foto)**: Bústia d'incidències de camp amb reproductor d'àudio, transcripció Whisper, xip de confiança acústica amb avís de soroll de tractor/vent, dictamen Extra Facturable vs Error Intern, estimació d'hores/materials i panell de revisió humana (HITL) amb botons d'aprovació, edició i descart.
  - **Pestanya 3: Reconciliació Post-Obra & Pre-Facturació**: Taula comparativa dels 4 pilars de cost real vs pressupostat, comptador visual de desviació de marge ($30\% \to 18.5\%$), indicador d'Alerta de Merma Operativa (>250% consum continu sense incidència), bloqueig per sync de camp pendent, i esborrany de nou pressupost corregit amb botó d'aprovació per enviar a facturació.
  - **Pestanya 4: Xat Tècnic Especialitzat & Reposició Stock**: Finestra de xat conversacional amb el Copilot, preguntes freqüents ràpides (cobertura de furgoneta, ITV de camió, protocols d'actuació RAG), demostrador interactiu de bloqueig de veto financer 403 Forbidden quan el rol és Enginyer, alertes de comanda de reposició per estoc sota mínims i validació d'aïllament per vertical.

---

### 6. Suite d'Auditoria QA Frontend (`pwa/test_copilot_audit.mjs`)
Script de validació automatitzada en 10 proves independents:
1. `Test 1`: Sobirania Hetzner i Telemetria CPU-only Whisper v3 INT8 (RF-01, RF-02).
2. `Test 2`: Memòria històrica de finca (365 dies) i detecció de garantia oficial de fabricant per SN (RF-04, RF-05, RF-06).
3. `Test 3`: Gestió de garantia interna de servei (<3 mesos) a cost 0 € (RF-07).
4. `Test 4`: Alerta de cortesia comercial per garantia expirada fa pocs dies (EDGE-07).
5. `Test 5`: Zero Mock Data: resposta fidel "No tinc informació prèvia" davant finca nova (RF-21, RF-22, EDGE-09).
6. `Test 6`: Peritatge multimodal amb transcripció Whisper i advertència de soroll de vent/tractor (RF-08, RF-09, EDGE-03).
7. `Test 7`: Principi Human-in-the-Loop (HITL): aprovació i edició de memoràndums tècnics (RF-10, RF-13).
8. `Test 8`: Reconciliació dels 4 pilars, desviació de marge comercial i alerta de merma >250% (RF-11, RF-12, EDGE-08).
9. `Test 9`: Alerta de recompra de stock en assignació i concurrència SELECT FOR UPDATE (RF-14, RF-15, EDGE-06).
10. `Test 10`: Xat tècnic: Veto d'Enginyer (HTTP 403 Forbidden) en consultes salarials/comptables i aïllament de vertical (RF-16, RF-20.1, EDGE-05, EDGE-10).

---

## Pla de Verificació

### Proves Automatitzades
- **SQL Migration**: Aplicar `db/migrations/014_copilot_ia.sql` al contenidor `sevalor_db` i comprovar taules i RLS.
- **Backend Unit & Integration Tests**: Executar `python run_tests.py` dins del contenidor Docker amb PostgreSQL en port 5433 (objectiu: 74/74 tests en verd).
- **Frontend QA Audit**: Executar `node test_copilot_audit.mjs` i tota la bateria `for f in test_*_audit.mjs; do node "$f"; done` (objectiu: 106/106 tests en verd).
- **Next.js Production Build**: Executar `npm run build` a `pwa/` (objectiu: 26/26 pàgines estàtiques generades sense fallades de tipat).
