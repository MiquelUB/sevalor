# Auditoria Tècnica Exhaustiva del Panell `/gestio` — Sevalor Suite

> **Abast de l'auditoria:** Exclusivament el panell de Backoffice `/gestio` (`pwa/src/app/gestio/**`, `pwa/src/components/gestio/**`, `pwa/src/components/CopilotWidget.tsx`, els routers de `backend/app/api/v1/gestio/**` i `backend/app/services/subagents/dispatcher.py`, `backend/app/services/ocr_service.py`), comparant el codi real amb [AGENTS.md](file:///media/akaun/Project_1/SEVALOR/AGENTS.md), [constitution.md](file:///media/akaun/Project_1/SEVALOR/constitution.md), [plan.md](file:///media/akaun/Project_1/SEVALOR/plan.md) i les especificacions `Spec 01`, `Spec 03`, `Spec 05` i `Spec 007`.  
> **Exclusions:** No inclou `/operari` (PWA mòbil) ni `/superadmin`.  
> **Estat:** Auditat 100% sobre codi font real sense modificacions ni dades inventades.

---

## 1. Resum Executiu i Verificació Global d'Endpoints

L'auditoria revela que, tot i que el gruix dels routers de `/api/v1/gestio/**` tenen persistència real amb PostgreSQL (`asyncpg` + SQLAlchemy 2.0), hi ha **ruptures crítiques entre el que exigeixen `constitution.md` / `AGENTS.md` i la implementació real**, especialment en cinc àrees:

1. **Fulla de Feines, Alta d'OT i Botó Triple:** No existeix la ruta `/gestio/feines` definida a [plan.md](file:///media/akaun/Project_1/SEVALOR/plan.md#L112) (dona 404 des de Clients i Spotlight), el Mapa (`/gestio/mapa`) no té botó ni modal d'alta de feina, [CrearOTModal.tsx](file:///media/akaun/Project_1/SEVALOR/pwa/src/components/gestio/CrearOTModal.tsx#L1268-L1302) no implementa el Botó Triple (Principi IV) i el seu botó `"Copilot IA"` llança un `alert(...)` fals.
2. **Copilot IA Local simulant funcionament quan està apagat (Principi V) + Subagents i Túnel de Disc Dur Desacoblats:** Tant la UI ([layout.tsx](file:///media/akaun/Project_1/SEVALOR/pwa/src/app/gestio/layout.tsx#L178), [CopilotWidget.tsx](file:///media/akaun/Project_1/SEVALOR/pwa/src/components/CopilotWidget.tsx#L45)) com el backend ([dispatcher.py](file:///media/akaun/Project_1/SEVALOR/backend/app/services/subagents/dispatcher.py#L478-L532), [pressupostos.py](file:///media/akaun/Project_1/SEVALOR/backend/app/api/v1/gestio/pressupostos.py#L229-L251), [copilot.py](file:///media/akaun/Project_1/SEVALOR/backend/app/api/v1/gestio/copilot.py#L1316-L1716)) ignoren `node_ia_actiu` o fan fallback determinista/simulat a Hetzner quan la IA local està apagada. A més, l'auditoria dels **8 subagents** ([subagents](file:///media/akaun/Project_1/SEVALOR/backend/app/services/subagents)) i de la carpeta local `/media/akaun/Project_1/Sevalormante_docs` confirma que **cap dels 8 subagents llegeix ni escriu via [sovereign_storage.py](file:///media/akaun/Project_1/SEVALOR/backend/app/services/sovereign_storage.py)** (consulten només PostgreSQL d'Hetzner), que l'agent túnel [client_vault_agent.py](file:///media/akaun/Project_1/SEVALOR/scripts/client_vault_agent.py) (port `9001`) **no està arrencat ni enllaçat** al pont Docker [bridge_lm_studio.py](file:///media/akaun/Project_1/SEVALOR/scripts/bridge_lm_studio.py), i que l'empresa `Sevalormante SL` a BD té `node_ia_actiu = False` i `node_ia_url = None`.
3. **Magatzem i Control d'Estoc:** Impossibilitat de donar d'alta estoc inicial o fer ajustos manuals des de la UI (tot i existir endpoint al backend), `codi_barres` ignorat al backend, estoc físic confós amb estoc disponible (`quantitat_virtual_reservada` no restada), consultes de picking sense filtrar per `magatzem_id` i `confirmar_devolucio` que no descompta de `quantitat_fisica` el material realment consumit.
4. **Seguretat Multi-Tenant (RLS) i Barrera Econòmica (`ENGINYER` veto, Principi VI):** El cercador Spotlight ([cerca.py](file:///media/akaun/Project_1/SEVALOR/backend/app/api/v1/gestio/cerca.py#L31-L206)) no usa `get_db_with_tenant_context` ni filtra per `empresa_id`; `contractes.py` no té RBAC; i nombrosos endpoints/pantalles (`feines`, `magatzem`, `clients`, `flota`, `operaris`) exposen costos, marges, tarifes o IBAN al rol `ENGINYER`.
5. **Desacoblaments UI ↔ Backend i Mocks Residuals (`Zero Mock Data`):** Errors HTTP 422 per noms de camp diferents (`configuracio` Telegram, `copilot` RAG, `notificacions` xat), crides a rutes inexistents (`proveidors` BEC, `contractes/nou` adreces client), IBANs hardcodejats a Proveïdors, GPS fals a Lleida a Operaris, paleta/pujada de logo falses a Configuració i esborrat de carpetes a Plànols que provoca `IntegrityError` (HTTP 500).

### Mapa d'Estat dels Routers `/gestio` (Backend)

| Mòdul / Router | Persistència BD Real? | Estat Funcional i Observacions Crítiques |
|---|---|---|
| [feines.py](file:///media/akaun/Project_1/SEVALOR/backend/app/api/v1/gestio/feines.py) | Sí (`OrdreTreball`) | Funcional parcialment; manca picking atòmic a `alta_feina`, manca bloqueig `BLOQUEJAT_RISC` (423) i carnet (`FR-012`); `/intervencions-actives` té dades mock; exposa `45.0 €/h` a `ENGINYER`. |
| [pressupostos.py](file:///media/akaun/Project_1/SEVALOR/backend/app/api/v1/gestio/pressupostos.py) | Sí (`Pressupost`) | CRUD real, però `POST /gestio/pressupostos/generar-ia` és 100% mock (`100.0 €` fix) i no valida estat del node IA. |
| [copilot.py](file:///media/akaun/Project_1/SEVALOR/backend/app/api/v1/gestio/copilot.py) + [ia.py](file:///media/akaun/Project_1/SEVALOR/backend/app/api/v1/gestio/ia.py) | Mixt (BD + LM Studio) | Conté fallbacks hardcodejats (`85.50 €`, `1200.00 €`, `145.00 €`, `35.0 €/h`) i [dispatcher.py](file:///media/akaun/Project_1/SEVALOR/backend/app/services/subagents/dispatcher.py) respon encara que `node_ia_actiu` sigui `False`. Col·lisió/error 422 entre `/copilot/rag` (`ia.py`) i `/copilot/rag/document` (`copilot.py`). |
| [dashboard.py](file:///media/akaun/Project_1/SEVALOR/backend/app/api/v1/gestio/dashboard.py) | Sí | `/hud`, `/incidencies-drawer`, `/resoldre`, `/aprova-hitl` reals; però `critical_stock` no resta `quantitat_virtual_reservada`. |
| [magatzem.py](file:///media/akaun/Project_1/SEVALOR/backend/app/api/v1/gestio/magatzem.py) | Sí | CRUD i `SELECT FOR UPDATE` reals, però errors greus de càlcul d'estoc disponible/consumit, falta de filtre `magatzem_id`, `codi_barres` ignorat, falta `empresa_id` a dues queries d'Article i exposició econòmica a `ENGINYER`. |
| [cerca.py](file:///media/akaun/Project_1/SEVALOR/backend/app/api/v1/gestio/cerca.py) | Sí | **CRÍTIC:** Sense `get_db_with_tenant_context` ni filtre `empresa_id`; retorna URLs mortes i esquemes incompatibles amb `layout.tsx`. |
| [clients.py](file:///media/akaun/Project_1/SEVALOR/backend/app/api/v1/gestio/clients.py) | Sí | CRUD/Finques/CSV reals; però `Fitxa 360` filtra `iban_xifrat_simetric` i marges a `ENGINYER`. |
| [proveidors.py](file:///media/akaun/Project_1/SEVALOR/backend/app/api/v1/gestio/proveidors.py) | Sí | Té `PUT /{id}/iban`, però NO té `/canvi-iban` ni `/autoritzar-canvi-iban` que crida el frontend; queries sense filtre explícit `empresa_id`. |
| [flota.py](file:///media/akaun/Project_1/SEVALOR/backend/app/api/v1/gestio/flota.py) | Sí | CRUD, ITV, TCO i Haversine reals; `descartar_anomalia_consum` no persisteix estat; `VehicleProperItem` peta amb 500 si `lat/lng/distancia_km` és `None`; exposa TCO a `ENGINYER`. |
| [operaris.py](file:///media/akaun/Project_1/SEVALOR/backend/app/api/v1/gestio/operaris.py) | Sí | CRUD, OCR, fitxatges reals; fabrica GPS fals a Lleida (`41.6176, 0.6200`), suma odòmetre històric com a `km_conduits_mes` i exposa `cost_hora_eur` a `ENGINYER`. |
| [contractes.py](file:///media/akaun/Project_1/SEVALOR/backend/app/api/v1/gestio/contractes.py) | Sí | **CRÍTIC:** Zero protecció RBAC (accessible per `ENGINYER`/`OPERARI`); `generar_prefactura` hardcodeja `serie="PRE"`, `numero_factura=9999`, `hash_sha256="draft_hash"` i cobra `import_anual` complet. |
| [comptabilitat.py](file:///media/akaun/Project_1/SEVALOR/backend/app/api/v1/gestio/comptabilitat.py) + [economia.py](file:///media/akaun/Project_1/SEVALOR/backend/app/api/v1/gestio/economia.py) | Sí | Endpoints reals; desajust amb la UI en filtre `periode` i manca d'accions directes des de WIP/Factures. |
| [configuracio.py](file:///media/akaun/Project_1/SEVALOR/backend/app/api/v1/gestio/configuracio.py) | Sí | Els endpoints reals `/marca/adn`, `/logotip`, `/slots` existeixen, però el frontend o no els crida (fa mocks locals) o envia payload incompatible (Telegram 422). |
| [notificacions.py](file:///media/akaun/Project_1/SEVALOR/backend/app/api/v1/gestio/notificacions.py) | Sí | Persisteix a BD però `crear_missatge` no envia a Telegram (`send_telegram_direct_message`); payload incompatible amb UI; `TOKENS_FACTURA` en RAM; URL bot hardcodejada. |
| [planols.py](file:///media/akaun/Project_1/SEVALOR/backend/app/api/v1/gestio/planols.py) | Sí | Funcional; `eliminar_carpeta` dona error 500 (`IntegrityError`) si la carpeta té plànols o capes vectorials. |

---

## 2. Desglossament Detallat d'Errades i Solucions per Bloc

### BLOC 1 — Ordres de Treball, Fulla de Feines, Botó Triple, Mapa i Copilot IA

#### [B1-01] Ruta `/gestio/feines` inexistent (404) i Mapa sense botó d'Alta de Feina
* **Severitat:** Crítica
* **Norma vulnerada:** [plan.md](file:///media/akaun/Project_1/SEVALOR/plan.md#L112) (matriu de rutes frontend `/gestio/feines`) i usabilitat operativa bàsica.
* **Evidència al codi:**
  * A [plan.md](file:///media/akaun/Project_1/SEVALOR/plan.md#L112) s'especifica la ruta `/gestio/feines`, però no existeix cap carpeta `pwa/src/app/gestio/feines/`.
  * [clients/page.tsx](file:///media/akaun/Project_1/SEVALOR/pwa/src/app/gestio/clients/page.tsx#L484) enllaça a `/gestio/feines?c=...` i [cerca.py](file:///media/akaun/Project_1/SEVALOR/backend/app/api/v1/gestio/cerca.py#L119) genera rutes `/gestio/feines/{o.id}`, produint errors 404.
  * A la vista de mapa ([mapa/page.tsx](file:///media/akaun/Project_1/SEVALOR/pwa/src/app/gestio/mapa/page.tsx#L97-L256) i [Map.tsx](file:///media/akaun/Project_1/SEVALOR/pwa/src/components/gestio/Map.tsx#L537-L715)) es llisten les feines i operaris amb Drag & Drop, però **no hi ha cap botó ni invocació a `CrearOTModal`** per donar d'alta una feina.
* **Solució aconsellada:**
  1. Crear `pwa/src/app/gestio/feines/page.tsx` (la Fulla de Feines dedicada amb llistat complet, filtres per client `?c=...`, obertura directa de `?id=...` / `/gestio/feines/[id]` o drawer `Fulla360OTDrawer`, i botó principal `"+ Nova Feina"` que obri `CrearOTModal`).
  2. Afegir un botó `"+ Nova Feina"` a la capçalera o barra lateral de [mapa/page.tsx](file:///media/akaun/Project_1/SEVALOR/pwa/src/app/gestio/mapa/page.tsx) / [Map.tsx](file:///media/akaun/Project_1/SEVALOR/pwa/src/components/gestio/Map.tsx) connectat a [CrearOTModal.tsx](file:///media/akaun/Project_1/SEVALOR/pwa/src/components/gestio/CrearOTModal.tsx).

#### [B1-02] `CrearOTModal.tsx`: Botó Triple inexistent, botó `"Copilot IA"` fals i "Cap de Colla" forçat
* **Severitat:** Crítica
* **Norma vulnerada:** [constitution.md](file:///media/akaun/Project_1/SEVALOR/constitution.md#L1-L60) Principi I (Zero Mock Data), Principi IV (Botó Triple & HITL) i Principi V (Copilot IA Local).
* **Evidència al codi:**
  * [CrearOTModal.tsx](file:///media/akaun/Project_1/SEVALOR/pwa/src/components/gestio/CrearOTModal.tsx#L1268-L1302): Només renderitza `"Validar Ordre de Treball"`, `"Cancel·lar"` i un botó `"Copilot IA"` (`#L1289-L1300`) que executa:
    ```tsx
    onClick={() => alert("El Copilot IA ha pre-calculat l'estimació de materials i hores segons l'històric de la finca.")}
    ```
    No crida cap endpoint real ni comprova si el Copilot està actiu. Falten els 3 botons del Botó Triple: `[Generar Tasca]`, `[Generar Pressupost]` i `[Pressupost Intel·ligent (Copilot)]`.
  * [CrearOTModal.tsx](file:///media/akaun/Project_1/SEVALOR/pwa/src/components/gestio/CrearOTModal.tsx#L1092-L1094): `<select required value={formData.cap_de_colla_id} ...>` obliga per HTML a triar un Cap de Colla, tot i que a `#L1247` calcula l'estat `"ASSIGNADA"` vs `"PENDENT"` en funció de si hi ha `cap_de_colla_id` i [EditarOTModal.tsx](file:///media/akaun/Project_1/SEVALOR/pwa/src/components/gestio/EditarOTModal.tsx#L737) sí permet `"Pendent d'assignar"`.
* **Solució aconsellada:**
  1. Treure `required` del `<select>` de `cap_de_colla_id` a [CrearOTModal.tsx](file:///media/akaun/Project_1/SEVALOR/pwa/src/components/gestio/CrearOTModal.tsx#L1092-L1094) i incloure l'opció `"Pendent d'assignar"` (`""` -> `null`).
  2. Eliminar l'`alert(...)` fals i implementar el **Botó Triple**:
     * **Generar Tasca:** Crea l'OT en estat `PENDENT` o `ASSIGNADA` via `POST /gestio/feines`.
     * **Generar Pressupost:** Crea l'esborrany de pressupost associat mitjançant [pressupostos.py](file:///media/akaun/Project_1/SEVALOR/backend/app/api/v1/gestio/pressupostos.py).
     * **Pressupost Intel·ligent (Copilot):** Visible/habilitat **únicament** quan `feature_copilot_ia === true` i `node_ia_actiu === true` i connectat realment a `POST /gestio/copilot/pressupost-intelligent` (mostrant estat `Copilot desconnectat` o ocultant-lo si el node IA està apagat).

#### [B1-03] Alta d'OT no atòmica a `CrearOTModal.tsx` i `alta_feina`
* **Severitat:** Alta
* **Norma vulnerada:** Integritat transaccional a BD (`Spec 01` / `AGENTS.md`).
* **Evidència al codi:**
  * [CrearOTModal.tsx](file:///media/akaun/Project_1/SEVALOR/pwa/src/components/gestio/CrearOTModal.tsx#L287-L315) executa seqüencialment `POST /gestio/feines`, després `POST /gestio/magatzem/picking`, i després un bucle `POST /gestio/magatzem/picking/${createdPick.id}/linies`. Si falla qualsevol línia per estoc insuficient, l'OT ja ha quedat creada a la BD com a registre orfe.
  * Al backend, `FeinaCreate` ([feines.py](file:///media/akaun/Project_1/SEVALOR/backend/app/api/v1/gestio/feines.py#L67-L86)) i `alta_feina` (`#L340-L438`) no accepten `linies_picking` (a diferència de `FeinaUpdate` a `#L152` i `modificar_feina` a `#L845-L907`).
* **Solució aconsellada:**
  1. Afegir `linies_picking` a `FeinaCreate` i processar tota l'alta d'OT + creació de `FullaPicking` + reserva d'estoc (`SELECT FOR UPDATE`) dins una **única transacció atòmica** a `alta_feina`.
  2. Simplificar [CrearOTModal.tsx](file:///media/akaun/Project_1/SEVALOR/pwa/src/components/gestio/CrearOTModal.tsx#L287-L315) a una única petició `POST /gestio/feines`.

#### [B1-04] Validacions absents a `alta_feina` i dades mock/exposades a `feines.py`
* **Severitat:** Crítica
* **Norma vulnerada:** `Spec 007 RF-36` (bloqueig risc client), `Spec 01 FR-012` (permís de conduir), [constitution.md](file:///media/akaun/Project_1/SEVALOR/constitution.md#L1-L60) Principi I (Zero Mock Data) i Principi VI (`economics_boss_only`).
* **Evidència al codi:**
  * [feines.py](file:///media/akaun/Project_1/SEVALOR/backend/app/api/v1/gestio/feines.py#L340-L438): `alta_feina` no verifica si el client té `estat_risc == "BLOQUEJAT_RISC"` (hauria de retornar HTTP 423) ni si el conductor té el carnet compatible amb el vehicle (`FR-012`).
  * `FeinaResponse` ([feines.py](file:///media/akaun/Project_1/SEVALOR/backend/app/api/v1/gestio/feines.py#L123)) retorna per defecte `preu_venda_hora_aplicat = 45.0` (tarifa hardcodejada) i s'exposa fins i tot a `ENGINYER` tant a [gestio/page.tsx](file:///media/akaun/Project_1/SEVALOR/pwa/src/app/gestio/page.tsx#L459) (`#L1249`) com a [Fulla360OTDrawer.tsx](file:///media/akaun/Project_1/SEVALOR/pwa/src/components/gestio/Fulla360OTDrawer.tsx#L150) (`#L189-L194`).
  * `llistar_intervencions_actives` ([feines.py](file:///media/akaun/Project_1/SEVALOR/backend/app/api/v1/gestio/feines.py#L1026-L1069)) retorna camps mock: `"client": "Client " + str(o.client_id)[:8]`, `"cap_colla": "Capataz"`, `"sector": "Sector Operatiu"`, `"pressio_bar": 3.8`, `"codi_candat": "N/A"`, i coordenades per defecte `41.3851, 2.1734`.
* **Solució aconsellada:**
  1. Validar a `alta_feina` el `BLOQUEJAT_RISC` (HTTP 423) i el permís de conduir del vehicle.
  2. Obtenir `preu_venda_hora_aplicat` del barema real d'empresa/client i nul·lificar els camps econòmics quan `current_user.rol == "ENGINYER"`, ocultant-los a [Fulla360OTDrawer.tsx](file:///media/akaun/Project_1/SEVALOR/pwa/src/components/gestio/Fulla360OTDrawer.tsx) i [gestio/page.tsx](file:///media/akaun/Project_1/SEVALOR/pwa/src/app/gestio/page.tsx).
  3. Substituir els valors hardcodejats de `llistar_intervencions_actives` per `JOIN` real amb `Client`, `Usuari` (Cap de colla) i `Finca` (retornant `None` quan faltin dades reals en lloc de `3.8`, `"Capataz"` o `41.3851, 2.1734`).

#### [B1-05] Copilot IA fa veure que funciona quan està apagat (Backend i Frontend) + Mocks de Pressupostos
* **Severitat:** Crítica
* **Norma vulnerada:** [constitution.md](file:///media/akaun/Project_1/SEVALOR/constitution.md#L1-L60) Principi I (Zero Mock Data) i Principi V (Copilot IA Local: sense fallbacks a Hetzner si el node local està apagat).
* **Evidència al codi:**
  * [dispatcher.py](file:///media/akaun/Project_1/SEVALOR/backend/app/services/subagents/dispatcher.py#L422-L532): Calcula correctament `es_actiu = bool(empresa and getattr(empresa, "feature_copilot_ia", True) and empresa.node_ia_actiu and node_url)` (`#L422-L427`), però quan `es_actiu` és `False`, les línies `#L478-L532` executen igualment `primary_subagent.run_sovereign(...)` al servidor Hetzner de manera determinista, retornant respostes com si el Copilot funcionés.
  * [layout.tsx](file:///media/akaun/Project_1/SEVALOR/pwa/src/app/gestio/layout.tsx#L178) (`#L332`, `#L424`) i [CopilotWidget.tsx](file:///media/akaun/Project_1/SEVALOR/pwa/src/components/CopilotWidget.tsx#L45) només comproven `res.feature_copilot_ia !== false` i ignoren `node_ia_actiu`.
  * [pressupostos.py](file:///media/akaun/Project_1/SEVALOR/backend/app/api/v1/gestio/pressupostos.py#L229-L251) (`generar_pressupost_ia`): Conté `# Simulate LLM call returning structured JSON budget lines.` i retorna valors fixos `preu_unitari: 100.0`, `total: 100.0`, `total_estimat: 100.0` sense verificar el node IA.
  * [copilot.py](file:///media/akaun/Project_1/SEVALOR/backend/app/api/v1/gestio/copilot.py#L1316-L1434) (`peritar_incidencia_multimodal`) i `#L1556-L1716` (`reconciliar_post_obra`): Contenen imports fallback hardcodejats (`cost_estimat = 85.50 / 45.00`, `partides_inicials: 1200.00`, `desviacio_materials_import: 145.00`, `desviacio_hores * 35.0`) sense exigir `node_ia_actiu`.
* **Solució aconsellada:**
  1. Al backend ([dispatcher.py](file:///media/akaun/Project_1/SEVALOR/backend/app/services/subagents/dispatcher.py) i [copilot.py](file:///media/akaun/Project_1/SEVALOR/backend/app/api/v1/gestio/copilot.py)): si `not es_actiu` (és a dir, `feature_copilot_ia` fals, `node_ia_actiu` fals o `node_url` buit/inaccessible), **tallar immediatament** retornant HTTP 503 (`COPILOT_DESACTIVAT`) sense executar cap fallback ni cap càlcul hardcodejat.
  2. A [pressupostos.py](file:///media/akaun/Project_1/SEVALOR/backend/app/api/v1/gestio/pressupostos.py#L229-L251): eliminar la simulació `100.0 €`, exigir node IA actiu i consultar LM Studio o el barema real + catàleg d'articles.
  3. A [layout.tsx](file:///media/akaun/Project_1/SEVALOR/pwa/src/app/gestio/layout.tsx) i [CopilotWidget.tsx](file:///media/akaun/Project_1/SEVALOR/pwa/src/components/CopilotWidget.tsx): comprovar `Boolean(res.feature_copilot_ia) && Boolean(res.node_ia_actiu)` (idealment consultant també `/gestio/copilot/estat-node`). Si està apagat, desactivar/amagar el xat o mostrar clarament l'estat *"Node IA Local Apagat"* bloquejant l'enviament de missatges.

#### [B1-06] Formulari d'entrenament RAG trencat (HTTP 422)
* **Severitat:** Alta
* **Norma vulnerada:** Coherència contractual API ↔ UI.
* **Evidència al codi:**
  * [copilot/page.tsx](file:///media/akaun/Project_1/SEVALOR/pwa/src/app/gestio/copilot/page.tsx#L41) envia `{ titol, contingut, tags }` a `POST /gestio/copilot/rag`.
  * L'endpoint `POST /gestio/copilot/rag` de [ia.py](file:///media/akaun/Project_1/SEVALOR/backend/app/api/v1/gestio/ia.py#L41) (`consultar_ia_rag`) espera `RagQueryIn(prompt: str)`, provocant un error HTTP 422. L'endpoint correcte per ingestar documents és `POST /gestio/copilot/rag/document` ([copilot.py](file:///media/akaun/Project_1/SEVALOR/backend/app/api/v1/gestio/copilot.py#L2013)).
* **Solució aconsellada:** Apuntar el formulari de [copilot/page.tsx](file:///media/akaun/Project_1/SEVALOR/pwa/src/app/gestio/copilot/page.tsx#L41) a `POST /gestio/copilot/rag/document` validant que els camps coincideixin amb l'esquema Pydantic d'entrada.

#### [B1-07] Auditoria dels 8 Subagents, Túnel Unificat (`client_vault_agent.py`) i Disc Dur Local (`/media/akaun/Project_1/Sevalormante_docs`)
* **Severitat:** Crítica (Sobirania de Dades i Arquitectura Copilot Multi-Agent)
* **Norma vulnerada:** [constitution.md](file:///media/akaun/Project_1/SEVALOR/constitution.md#L1-L60) Principi V (Copilot IA Local), Principi IX / Sobirania de Disc, i [AGENTS.md](file:///media/akaun/Project_1/SEVALOR/AGENTS.md#L27-L28) (emmagatzematge al disc de l'empresa, zero retenció a Hetzner).
* **Estat real verificat del túnel i del disc dur `/media/akaun/Project_1/Sevalormante_docs`:**
  1. **Carpeta física existent i estructura creada:** `/media/akaun/Project_1/Sevalormante_docs` existeix al host i conté les 38 subcarpetes oficials (`CARPETES_OFICIALS` a [client_vault_agent.py](file:///media/akaun/Project_1/SEVALOR/scripts/client_vault_agent.py#L51-L90)), però només té **4 fitxers**: `05_planols/arxius_base/prova_connexio_real.dxf`, `08_flota_i_operaris/operaris/9b46bddd-1176-425a-adb6-c46b811963d0.json`, `11_configuracio_i_backups/identitat_camaleo/boss.json` i `11_configuracio_i_backups/identitat_camaleo/empresa.json` (ID `628f48ed-2eda-48aa-bf74-a0266f19344d`, `Sevalormante SL`).
  2. **Passarel·la de disc (`port 9001`) aturada i sense pont Docker:** LM Studio corre a `127.0.0.1:1234` (`Qwen2.5-VL-7B-Instruct-Q6_K.gguf`) amb [bridge_lm_studio.py](file:///media/akaun/Project_1/SEVALOR/scripts/bridge_lm_studio.py) escoltant a `172.17-23.0.1:1234`, però **[client_vault_agent.py](file:///media/akaun/Project_1/SEVALOR/scripts/client_vault_agent.py) (`PORT=9001`) no està arrencat**, no existeix `sevalor-vault-agent.service` a systemd, i `bridge_lm_studio.py` només reenvia el port `1234` (no el `9001`).
  3. **Configuració partida a la taula `empreses` i flux unificat incomplet:**
     * `Sevalormante SL` (`628f48ed-2eda-48aa-bf74-a0266f19344d`) té `disc_dur_url = 'http://host.docker.internal:9001'` i `vault_token = 'svlt_9f7cd7...'`, però té `node_ia_url = None`, `node_ia_actiu = False`, `feature_copilot_ia = False`.
     * `AgroServeis Demo SL` (`05299a76-94cf-4aca-bc7d-a291285d375f`) té `node_ia_url = 'http://127.0.0.1:1234/v1'`, `node_ia_actiu = True`, `feature_copilot_ia = True`, però té `disc_dur_url = None` i `vault_token = None`.
     * [client_vault_agent.py](file:///media/akaun/Project_1/SEVALOR/scripts/client_vault_agent.py#L203-L235) implementa un **túnel unificat** (`/entitats/*`, `/fitxers/*` + proxy `/v1/{llm_path:path}` cap a LM Studio `:1234`), però: (a) [dispatcher.py](file:///media/akaun/Project_1/SEVALOR/backend/app/services/subagents/dispatcher.py#L417-L427) només mira `node_ia_url` i ignora `disc_dur_url` quan l'empresa usa el túnel unificat `:9001`; (b) a [sovereign_storage.py](file:///media/akaun/Project_1/SEVALOR/backend/app/services/sovereign_storage.py#L203-L209), si `disc_dur_url` falta o porta `:1234`, escriu en `/tmp/sevalor_client_disks` dins del servidor/contenidor Hetzner!
* **Auditoria d'implementació dels 8 Subagents (`backend/app/services/subagents/`):**
  L'orquestrador [CopilotDispatcher](file:///media/akaun/Project_1/SEVALOR/backend/app/services/subagents/dispatcher.py#L64-L594) registra **8 subagents** (evolució dels 6 definits a [multiagent_subagents_architecture.md](file:///media/akaun/Project_1/SEVALOR/sevalor_AgentV2/docs/sdd/multiagent_subagents_architecture.md)) amb puntuació Top-2 i protecció financera parcial (`subagent_marge` limitat a `BOSS`). **Però cap dels 8 subagents importa ni utilitza [SovereignStorageGateway](file:///media/akaun/Project_1/SEVALOR/backend/app/services/sovereign_storage.py#L107)**:

  | Subagent (`backend/app/services/subagents/`) | Origen de Dades Actual | Carpetes del Disc Dur (`/media/akaun/Project_1/Sevalormante_docs`) que Hauria de Consultar / Escriure | Errades / Mancances Detectades |
  |---|---|---|---|
  | [subagent_general_rag.py](file:///media/akaun/Project_1/SEVALOR/backend/app/services/subagents/subagent_general_rag.py) (`SubagentGeneralRag`) | Només PostgreSQL Hetzner (`FaqCorporativaRag`, `Client`, `Finca`, `Pressupost`, `EinaCustodia`) | `01_clients/*`, `03_magatzem/eines_custodia`, `04_factures/prefactures_i_pressupostos`, `09_copilot_ia/index_vectorial_rag`, `10_protocols_i_manuals/*` | `tool_get_rag_knowledge` (`#L83-L104`) ignora les carpetes `10_protocols_i_manuals/*` on `copilot.py#L2034` desa els protocols. |
  | [subagent_planificacio_equip.py](file:///media/akaun/Project_1/SEVALOR/backend/app/services/subagents/subagent_planificacio_equip.py) (`SubagentPlanificacioEquip`) | Només PostgreSQL Hetzner (`OrdreTreball`, `Incidencia`, `RegistreJornadaLaboral`) | `06_ordres_treball/*`, `07_incidencies/registres`, `08_flota_i_operaris/*` | `feines.py` no sincronitza `ots_actives`/`ots_historic` al disc; el subagent mai llegeix carpetes d'OTs ni incidències locals. |
  | [subagent_logistica_estoc.py](file:///media/akaun/Project_1/SEVALOR/backend/app/services/subagents/subagent_logistica_estoc.py) (`SubagentLogisticaEstoc`) | Només PostgreSQL Hetzner (`Article`, `EstocMagatzem`, `MovimentEstoc`, `AlbaraProveidor`, `EinaCustodia`) | `02_proveidors/fitxes`, `03_magatzem/*`, `04_factures/factures_proveidors` | `magatzem.py#L906` escriu `/tmp/data/{empresa_id}/proveidors/{prov.id}` fora del `SovereignStorageGateway`; picking/eines/modificacions no sincronitzen; el subagent només llegeix BD. |
  | [subagent_flota_despatx.py](file:///media/akaun/Project_1/SEVALOR/backend/app/services/subagents/subagent_flota_despatx.py) (`SubagentFlotaDespatx`) | Només PostgreSQL Hetzner (`Vehicle`, `DocumentFlota`, `OrdreTreball`) | `08_flota_i_operaris/vehicles`, `alertes_flota`, `tiquets_despesa` | `tool_get_closest_vehicle` (`#L178`) posa fallback `41.3851, 2.1734`; no consulta fitxes/documents del disc local. |
  | [subagent_peritatge_camp.py](file:///media/akaun/Project_1/SEVALOR/backend/app/services/subagents/subagent_peritatge_camp.py) (`SubagentPeritatgeCamp`) | Només PostgreSQL Hetzner (`MemorandumTecnicCopilot`, `OrdreTreball`, `EinaCustodia`) | `07_incidencies/*`, `09_copilot_ia/autoaprenentatge/memorandums_tecnics`, `10_protocols_i_manuals/manuals_fabricants` | `tool_generar_memorandum_tecnic` (`#L142-L207`) té costos hardcodejats (`85.50 €`, `45.00 €`) i no desa `copilot_memorandums` al disc local. |
  | [subagent_auditoria_marge.py](file:///media/akaun/Project_1/SEVALOR/backend/app/services/subagents/subagent_auditoria_marge.py) (`SubagentAuditoriaMarge`) | Només PostgreSQL Hetzner (`OrdreTreball`, `LiniaPicking`, `FacturaLinia`, `AuditoriaPostObra`) | `04_factures/*`, `06_ordres_treball/informes_post_obra`, `09_copilot_ia/autoaprenentatge/historic_preus_i_mermes` | No consulta ni alimenta `historic_preus_i_mermes` ni `informes_post_obra` al disc de l'empresa. |
  | [subagent_ocr_vision.py](file:///media/akaun/Project_1/SEVALOR/backend/app/services/subagents/subagent_ocr_vision.py) (`SubagentOcrVision`) | Regex local sobre text (`tool_extract_*`) + Postgres `Proveidor` | `03_magatzem/albarans_compra`, `04_factures/factures_proveidors`, `08_flota_i_operaris/tiquets_despesa` | No crida el model multimodal LM Studio pel túnel ni desa els extracions OCR a les carpetes del disc. |
  | [subagent_client_telegram.py](file:///media/akaun/Project_1/SEVALOR/backend/app/services/subagents/subagent_client_telegram.py) (`SubagentClientTelegram`) | Mock parcial (`uuid.uuid4()`, `#L136`, `#L106-L123` retorna `enviat: True` sense enviar) | `01_clients/*`, `04_factures/prefactures_i_pressupostos`, `07_incidencies/fotos_camp` | `run_sovereign` inventa un `uuid4()` i `tool_send_interactive_budget` no envia realment via `telegram_service`. |

  * **Desconnexió de `prompt_sistema` i autoaprenentatge a [dispatcher.py](file:///media/akaun/Project_1/SEVALOR/backend/app/services/subagents/dispatcher.py):** No llegeix `09_copilot_ia/prompt_sistema/system_prompt.txt` des del disc local de l'empresa (`copilot_prompt`) ni persisteix el feedback de consultes a `09_copilot_ia/autoaprenentatge/converses_i_feedback` (`copilot_feedback`).
  * **Routers `/gestio` que encara NO sincronitzen cap fitxer al disc dur de l'empresa:** [feines.py](file:///media/akaun/Project_1/SEVALOR/backend/app/api/v1/gestio/feines.py) (`ots_actives`/`ots_historic`), [contractes.py](file:///media/akaun/Project_1/SEVALOR/backend/app/api/v1/gestio/contractes.py) (`contractes`), [pressupostos.py](file:///media/akaun/Project_1/SEVALOR/backend/app/api/v1/gestio/pressupostos.py) (`pressupostos`) i `crear_finca_client` a [clients.py](file:///media/akaun/Project_1/SEVALOR/backend/app/api/v1/gestio/clients.py#L648) (`finques`).
* **Solució aconsellada:** Vegeu el pla d'implementació i codi complet al Bloc 0 de [PLA_IMPLEMENTACIO_GESTIO_SEVALOR.md](file:///media/akaun/Project_1/SEVALOR/PLA_IMPLEMENTACIO_GESTIO_SEVALOR.md) (arrencada del túnel unificat `:9001` sobre `/media/akaun/Project_1/Sevalormante_docs`, lector sobirà als 8 subagents i sincronització completa de carpetes).

---

### BLOC 2 — Magatzem, Control d'Estoc, Picking i Eines

#### [B2-01] Impossibilitat de donar d'alta estoc inicial o ajustar estoc manualment a la UI + `codi_barres` ignorat
* **Severitat:** Crítica
* **Norma vulnerada:** Control d'estoc operatiu (`Spec 01` / `Spec 007`).
* **Evidència al codi:**
  * [magatzem.py](file:///media/akaun/Project_1/SEVALOR/backend/app/api/v1/gestio/magatzem.py#L80): `ArticleCreate` declara `codi_barres`, però `alta_article` (`#L260-L274`) i `modificar_article` (`#L1151-L1163`) l'ignoren completament. Tampoc hi ha input de codi de barres a [magatzem/page.tsx](file:///media/akaun/Project_1/SEVALOR/pwa/src/app/gestio/magatzem/page.tsx).
  * `alta_article` (`#L247-L308`) no crea cap registre `EstocMagatzem`, de manera que cada nou article neix sempre amb `estoc_real = 0`.
  * Ni el modal de creació ni el d'edició de [magatzem/page.tsx](file:///media/akaun/Project_1/SEVALOR/pwa/src/app/gestio/magatzem/page.tsx#L122-L141) (`#L445-L509`, `#L1634-L1680`, `#L1894-L1920`) permeten establir `estoc_inicial` / `quantitat_fisica`.
  * Al backend existeix `POST /gestio/magatzem/magatzems/{magatzem_id}/moviment` ([magatzem.py](file:///media/akaun/Project_1/SEVALOR/backend/app/api/v1/gestio/magatzem.py#L495)), però **no hi ha cap botó ni modal a [magatzem/page.tsx](file:///media/akaun/Project_1/SEVALOR/pwa/src/app/gestio/magatzem/page.tsx) que el cridi**.
* **Solució aconsellada:**
  1. Persistir `codi_barres` a `alta_article` i `modificar_article` i afegir el camp corresponent als formularis de [magatzem/page.tsx](file:///media/akaun/Project_1/SEVALOR/pwa/src/app/gestio/magatzem/page.tsx).
  2. Acceptar `estoc_inicial` i `magatzem_id` opcional a `alta_article` (o crear un registre a `EstocMagatzem` i `MovimentStock` d'obertura) i afegir el camp a `CrearArticleModal`.
  3. Crear un modal `"Ajust / Entrada d'Estoc"` a cada fila d'article a [magatzem/page.tsx](file:///media/akaun/Project_1/SEVALOR/pwa/src/app/gestio/magatzem/page.tsx) connectat a `POST /gestio/magatzem/magatzems/{magatzem_id}/moviment`.

#### [B2-02] Estoc físic confós amb disponible, Picking sense filtrar `magatzem_id` i consum no descomptat
* **Severitat:** Crítica
* **Norma vulnerada:** Integritat d'inventari i prevenció de condicions de carrera (`supabase-postgres-best-practices`).
* **Evidència al codi:**
  * `llistar_articles` ([magatzem.py](file:///media/akaun/Project_1/SEVALOR/backend/app/api/v1/gestio/magatzem.py#L184-L192)) i `critical_stock` ([dashboard.py](file:///media/akaun/Project_1/SEVALOR/backend/app/api/v1/gestio/dashboard.py#L108-L118)) calculen `func.sum(EstocMagatzem.quantitat_fisica)` **sense restar `quantitat_virtual_reservada`**. Això provoca que [CrearOTModal.tsx](file:///media/akaun/Project_1/SEVALOR/pwa/src/components/gestio/CrearOTModal.tsx#L604) (`#L697`, `#L718`) i [EditarOTModal.tsx](file:///media/akaun/Project_1/SEVALOR/pwa/src/components/gestio/EditarOTModal.tsx#L1094) mostrin unitats ja reservades com a disponibles. A més, [CrearOTModal.tsx](file:///media/akaun/Project_1/SEVALOR/pwa/src/components/gestio/CrearOTModal.tsx#L705-L719) només deshabilita amb `disabled={currentQty <= 0}` però no limita per l'estoc disponible real.
  * `afegir_linia_picking` ([magatzem.py](file:///media/akaun/Project_1/SEVALOR/backend/app/api/v1/gestio/magatzem.py#L682-L690)), `confirmar_devolucio` (`#L810-L818`) i `modificar_feina` ([feines.py](file:///media/akaun/Project_1/SEVALOR/backend/app/api/v1/gestio/feines.py#L830), `#L854`, `#L878`) consulten `EstocMagatzem` per `(empresa_id, article_id)` amb `.scalars().first()` **sense filtrar per `magatzem_id`** (barrejant Nau Central i Furgonetes aleatòriament).
  * `confirmar_pick_in` ([magatzem.py](file:///media/akaun/Project_1/SEVALOR/backend/app/api/v1/gestio/magatzem.py#L755-L780)) no modifica `EstocMagatzem`, i `confirmar_devolucio` (`#L819-L825`) resta `quantitat_prevista` de `quantitat_virtual_reservada` i `quantitat_mermada` de `quantitat_fisica`, però **mai descompta de `quantitat_fisica` el material realment consumit** (`quantitat_carregada_pick_in - quantitat_retornada_pick_out`).
* **Solució aconsellada:**
  1. Retornar explícitament `estoc_fisic`, `estoc_reservat` (`quantitat_virtual_reservada`) i `estoc_disponible` (`quantitat_fisica - quantitat_virtual_reservada`) tant a `llistar_articles` com a `dashboard.py` (`critical_stock`), validant contra `estoc_disponible` als modals d'OT.
  2. Emmagatzemar `magatzem_id` a la línia de picking / fulla de picking i filtrar sempre `EstocMagatzem` per `(empresa_id, article_id, magatzem_id)` amb `WITH FOR UPDATE`.
  3. A `confirmar_devolucio`, calcular `consumit = quantitat_carregada_pick_in - quantitat_retornada_pick_out` (més mermes no incloses o desglossades sense duplicar descompte) i restar-lo de `quantitat_fisica`, registrant el corresponent `MovimentStock`.

#### [B2-03] Filtre `empresa_id` omès a Article, exposició de costos a `ENGINYER` i desajust d'unitats / Eines / Recompra
* **Severitat:** Alta (Seguretat RLS/RBAC) / Mitjana (Operativa)
* **Norma vulnerada:** [AGENTS.md](file:///media/akaun/Project_1/SEVALOR/AGENTS.md) §3.1 (Multi-tenant), `Spec 01 Plan §3`, `Spec 007 §2` i `FR-010`.
* **Evidència al codi:**
  * `alta_article` ([magatzem.py](file:///media/akaun/Project_1/SEVALOR/backend/app/api/v1/gestio/magatzem.py#L255)) i `modificar_article` (`#L1145`) consulten `Article` sense incloure `Article.empresa_id == uuid.UUID(empresa_id)`.
  * [magatzem.py](file:///media/akaun/Project_1/SEVALOR/backend/app/api/v1/gestio/magatzem.py#L150-L244) i [magatzem/page.tsx](file:///media/akaun/Project_1/SEVALOR/pwa/src/app/gestio/magatzem/page.tsx#L813) (`#L860`, `#L1923-L1965`) exposen `preu_cost`, `pmp_actual` i `descompte_proveidor` al rol `ENGINYER`.
  * A [magatzem/page.tsx](file:///media/akaun/Project_1/SEVALOR/pwa/src/app/gestio/magatzem/page.tsx), el modal de creació (`#L1645-L1651`) usa `UNITAT`, `METRES_LINEALS`, `KG`, `LITRES`, `M2`, `M3`, mentre el d'edició (`#L1882-L1886`) usa `UNITAT`, `METRE`, `LITRE`, `QUILO`, `CAIXA`.
  * Eines ([magatzem/page.tsx](file:///media/akaun/Project_1/SEVALOR/pwa/src/app/gestio/magatzem/page.tsx#L870-L934), [magatzem.py](file:///media/akaun/Project_1/SEVALOR/backend/app/api/v1/gestio/magatzem.py#L1039), `#L1309-L1338`): L'OCR crea eines amb `numero_serie="PENDENT_SN_..."`; existeix `PUT /gestio/magatzem/eines/{eina_id}` al backend, però la taula només té Check-Out/Check-In i cap botó per editar el número de sèrie.
  * No hi ha cap bústia/pantalla a la UI per revisar i aprovar esborranys de `RECOMPRA_STOCK` (`FR-010`).
* **Solució aconsellada:**
  1. Afegir `.where(Article.empresa_id == uuid.UUID(empresa_id))` a `alta_article` i `modificar_article`.
  2. Ocultar `preu_cost`, `pmp_actual` i `descompte_proveidor` al backend i a la UI per a `ENGINYER`.
  3. Unificar l'`enum` d'unitats entre els modals de creació i edició d'articles.
  4. Afegir botó `"Editar"` a la taula d'eines connectat a `PUT /gestio/magatzem/eines/{eina_id}` i afegir una pestanya/bústia d'alertes `RECOMPRA_STOCK` per validar comandes pendents.

---

### BLOC 3 — Seguretat RLS, Spotlight i Navegació Global

#### [B3-01] `cerca.py` sense context RLS ni filtre `empresa_id`, URLs mortes i Spotlight trencat
* **Severitat:** Crítica (Seguretat Multi-Tenant + Funcional)
* **Norma vulnerada:** [AGENTS.md](file:///media/akaun/Project_1/SEVALOR/AGENTS.md) §3.1 (RLS obligatori al 100% de les taules amb `empresa_id`).
* **Evidència al codi:**
  * [cerca.py](file:///media/akaun/Project_1/SEVALOR/backend/app/api/v1/gestio/cerca.py#L31-L206): Tant `cerca_spotlight` (`#L38`) com `llistar_spotlight_items_inicials` (`#L185`) injecten `Depends(get_db)` en comptes de `Depends(get_db_with_tenant_context)` i **no filtren per `.where(Model.empresa_id == ...)`** a `Client`, `Vehicle`, `OrdreTreball`, `Article` ni `Usuari`. Això permet potencialment veure registres d'altres empreses.
  * `cerca_spotlight` retorna URLs inexistents (`/gestio/clients/{id}`, `/gestio/flota/{id}`, `/gestio/feines/{id}`, `/gestio/magatzem/articles/{id}`, `/gestio/equip/{id}`).
  * `llistar_spotlight_items_inicials` (`#L198-L205`) retorna `{ id, titol, desc, esFinancera }` (sense `ref` ni `tipus`).
  * [layout.tsx](file:///media/akaun/Project_1/SEVALOR/pwa/src/app/gestio/layout.tsx#L121-L140) (`#L448-L482`): No crida mai a `/gestio/cerca?q=...` quan l'usuari escriu al Spotlight, i a `#L459` executa `router.push(item.ref)` on `item.ref` és `undefined`.
* **Solució aconsellada:**
  1. Substituir `get_db` per `get_db_with_tenant_context` i afegir filtre explícit `Model.empresa_id == uuid.UUID(empresa_id)` a totes les consultes de [cerca.py](file:///media/akaun/Project_1/SEVALOR/backend/app/api/v1/gestio/cerca.py).
  2. Retornar sempre `ref` i `tipus` tant a `/spotlight/items` com a `/gestio/cerca`, apuntant a rutes reals (`/gestio/clients?id=...`, `/gestio/flota?id=...`, `/gestio/feines?id=...`, `/gestio/magatzem?id=...`, `/gestio/operaris?id=...`).
  3. Connectar el camp de cerca del modal Spotlight a [layout.tsx](file:///media/akaun/Project_1/SEVALOR/pwa/src/app/gestio/layout.tsx) amb *debounce* contra `GET /gestio/cerca?q=...`.

---

### BLOC 4 — Clients (`clients.py` i `clients/page.tsx`)

#### [B4-01] Fuita d'IBAN i marges a `ENGINYER`, exportació CSV trencada i modal reduït duplicat
* **Severitat:** Alta
* **Norma vulnerada:** [constitution.md](file:///media/akaun/Project_1/SEVALOR/constitution.md#L1-L60) Principi VI (`economics_boss_only`) i integritat de sessions (`AGENTS.md`).
* **Evidència al codi:**
  * [clients.py](file:///media/akaun/Project_1/SEVALOR/backend/app/api/v1/gestio/clients.py#L413-L415) (`#L518`, `obtenir_fitxa_360_client`): Retorna `iban_xifrat_simetric` en cru i dades econòmiques (`cost_material`, `ingres_facturat`, `marge_brut`) fins i tot a `ENGINYER`.
  * [clients/page.tsx](file:///media/akaun/Project_1/SEVALOR/pwa/src/app/gestio/clients/page.tsx#L247-L256): L'exportació CSV llegeix `localStorage.getItem('sevalor_token')` (que no existeix) i obre la URL hardcodejada `http://localhost:8000/api/v1/gestio/clients/export?token=...` sense usar `getApiBaseUrl()`, `getAuthToken()` ni `X-Empresa-ID`.
  * [clients/page.tsx](file:///media/akaun/Project_1/SEVALOR/pwa/src/app/gestio/clients/page.tsx#L418-L435) (`#L484`, `#L693-L847`):
    * Manca botó a la Fitxa 360 per donar d'alta una Finca (`POST /gestio/clients/{id}/finques` ja existeix a [clients.py](file:///media/akaun/Project_1/SEVALOR/backend/app/api/v1/gestio/clients.py#L648)).
    * Manca endpoint i formulari `PUT /gestio/clients/{id}` per editar dades del client.
    * Enllaç trencat a `/gestio/feines?c=` (`#L484`).
    * Té un mini-modal duplicat `"Assignar Tasca"` (`#L693-L847`) amb `Cap de Colla` obligatori i sense picking ni eines.
* **Solució aconsellada:**
  1. Emmascarar/ometre `iban_xifrat_simetric` i els totals financers quan el rol sigui `ENGINYER`.
  2. Fer l'exportació CSV via `fetch` autenticat amb `getApiBaseUrl()`, `Authorization: Bearer ...` i `X-Empresa-ID` generant un `Blob` descarregable.
  3. Afegir `PUT /gestio/clients/{id}` al backend, afegir el botó d'alta de Finca a la UI, i reemplaçar el mini-modal `"Assignar Tasca"` pel component unificat [CrearOTModal.tsx](file:///media/akaun/Project_1/SEVALOR/pwa/src/components/gestio/CrearOTModal.tsx) pre-omplint `client_id`.

---

### BLOC 5 — Proveïdors (`proveidors.py` i `proveidors/page.tsx`)

#### [B5-01] IBANs mock hardcodejats, flux BEC amb endpoints inexistents i modal d'edició inabastable
* **Severitat:** Crítica
* **Norma vulnerada:** [constitution.md](file:///media/akaun/Project_1/SEVALOR/constitution.md#L1-L60) Principi I (Zero Mock Data) i coherència API ↔ UI.
* **Evidència al codi:**
  * [proveidors/page.tsx](file:///media/akaun/Project_1/SEVALOR/pwa/src/app/gestio/proveidors/page.tsx#L312) (`#L694`, `#L757`): Injecta un IBAN inventat `"ES8200491823442819481920"` si es deixa buit a la creació (`#L312`), i un botó `"Simular BEC"` (`#L692-L701`) envia l'IBAN fals `"ES44 2100 1234 56 9988776655"`.
  * [proveidors/page.tsx](file:///media/akaun/Project_1/SEVALOR/pwa/src/app/gestio/proveidors/page.tsx#L212) (`#L252`): El flux BEC crida `/gestio/proveidors/canvi-iban` i `/gestio/proveidors/autoritzar-canvi-iban`, que **no existeixen** a [proveidors.py](file:///media/akaun/Project_1/SEVALOR/backend/app/api/v1/gestio/proveidors.py) (el qual només exposa `PUT /{proveidor_id}/iban`).
  * [proveidors/page.tsx](file:///media/akaun/Project_1/SEVALOR/pwa/src/app/gestio/proveidors/page.tsx#L99) (`#L676-L714`, `#L1067`): El modal `modalFitxaObert` (`#L1067`) mai s'obre des de cap botó de la taula (`#L676-L714`), i el modal CAE (`#L837-L929`) no inclou cap `<input type="file">`.
  * [proveidors.py](file:///media/akaun/Project_1/SEVALOR/backend/app/api/v1/gestio/proveidors.py#L62) (`#L110`, `#L117`, `#L262`): Consultes sense filtre explícit `Proveidor.empresa_id == uuid.UUID(empresa_id)`.
* **Solució aconsellada:**
  1. Eliminar l'IBAN per defecte `"ES8200..."` i el botó `"Simular BEC"` amb `"ES44 2100..."`.
  2. Connectar l'actualització d'IBAN i l'aprovació de doble verificació BEC directament a `PUT /gestio/proveidors/{proveidor_id}/iban` (o implementar al backend el flux complet de sol·licitud + autorització BEC amb traçabilitat SIF).
  3. Afegir botó d'obertura de `modalFitxaObert` a la taula, habilitar l'`<input type="file">` al modal CAE, i afegir `Proveidor.empresa_id == uuid.UUID(empresa_id)` a totes les queries de [proveidors.py](file:///media/akaun/Project_1/SEVALOR/backend/app/api/v1/gestio/proveidors.py).

---

### BLOC 6 — Flota (`flota.py` / `flota/page.tsx`) i Operaris (`operaris.py` / `operaris/page.tsx`)

#### [B6-01] Error Pydantic 500 a Flota `propers`, anomalia de consum no persistent i TCO exposat a `ENGINYER`
* **Severitat:** Alta
* **Norma vulnerada:** Estabilitat d'API i Principi VI (`economics_boss_only`).
* **Evidència al codi:**
  * [flota.py](file:///media/akaun/Project_1/SEVALOR/backend/app/api/v1/gestio/flota.py#L949-L958) (`#L1031-L1033`): `VehicleProperItem` tipa `distancia_km`, `lat`, `lng` com a `float` no opcionals, però s'hi passa `None` (`# type: ignore`) si el vehicle no té coordenades d'OT activa -> provoca HTTP 500 `ValidationError`.
  * [flota.py](file:///media/akaun/Project_1/SEVALOR/backend/app/api/v1/gestio/flota.py#L328-L330) (`#L900-L929`): `descartar_anomalia_consum` només afegeix una nota de text a `historial_reparacions` sense persistir un booleà `anomalia_consum_descartada = True`, de manera que l'alerta torna a aparèixer en recarregar.
  * [flota.py](file:///media/akaun/Project_1/SEVALOR/backend/app/api/v1/gestio/flota.py#L404-L421): Exposa `quota_mensual_eur`, `cost_total_acumulat_eur` i `cost_per_km_eur` a `ENGINYER`.
* **Solució aconsellada:**
  1. Tipar `distancia_km: float | None`, `lat: float | None`, `lng: float | None` a `VehicleProperItem`.
  2. Persistir `anomalia_consum_descartada` al registre de repostament / anomalia i filtrar-lo en consultar alertes.
  3. Ometre les dades TCO quan el rol sigui `ENGINYER`.

#### [B6-02] Coordenades GPS falses (Lleida), mètrica de quilòmetres errònia i exposició de `cost_hora_eur` a Operaris
* **Severitat:** Crítica
* **Norma vulnerada:** [constitution.md](file:///media/akaun/Project_1/SEVALOR/constitution.md#L1-L60) Principi I (Zero Mock Data) i Principi VI (`economics_boss_only`).
* **Evidència al codi:**
  * [operaris.py](file:///media/akaun/Project_1/SEVALOR/backend/app/api/v1/gestio/operaris.py#L460-L464): Fabrica coordenades falses al voltant de Lleida (`41.6176`, `0.6200`) quan l'operari no té coordenades reals d'OT activa.
  * [operaris.py](file:///media/akaun/Project_1/SEVALOR/backend/app/api/v1/gestio/operaris.py#L530-L534): Calcula `km_conduits_mes` sumant `Vehicle.odometre_acumulat` històric complet en comptes dels quilòmetres recorreguts durant el mes en curs.
  * [operaris.py](file:///media/akaun/Project_1/SEVALOR/backend/app/api/v1/gestio/operaris.py#L149) i [operaris/page.tsx](file:///media/akaun/Project_1/SEVALOR/pwa/src/app/gestio/operaris/page.tsx#L820) (`#L916-L935`): Exposen `cost_hora_eur` a `ENGINYER`.
* **Solució aconsellada:**
  1. Retornar `lat = None, lng = None` quan no hi hagi posició GPS real verificada (estat buit al mapa).
  2. Calcular `km_conduits_mes` a partir dels registres de repostaments/fitxatges o diferència d'odòmetre dins del mes natural actual.
  3. Filtrar `cost_hora_eur` per rol tant a l'API com a la vista [operaris/page.tsx](file:///media/akaun/Project_1/SEVALOR/pwa/src/app/gestio/operaris/page.tsx).

---

### BLOC 7 — Contractes (`contractes.py`, `contractes/page.tsx`, `nou/page.tsx`, `[id]/page.tsx`)

#### [B7-01] Router sense RBAC, prefactura amb dades mock i selector de finques trencat
* **Severitat:** Crítica (Seguretat RBAC + Facturació)
* **Norma vulnerada:** [constitution.md](file:///media/akaun/Project_1/SEVALOR/constitution.md#L1-L60) Principis I, VI i VII (Veri*factu).
* **Evidència al codi:**
  * [contractes.py](file:///media/akaun/Project_1/SEVALOR/backend/app/api/v1/gestio/contractes.py#L19) (`#L150-L160`, `#L295-L348`): El router no aplica control RBAC (`ENGINYER` o `OPERARI` poden consultar el MRR a `#L150` i executar `generar_prefactura` a `#L295`).
  * `generar_prefactura` (`#L322-L324`) hardcodeja `serie="PRE"`, `numero_factura=9999` i `hash_sha256="draft_hash"`, i factura sempre tot `import_anual` ignorant el camp `periodicitat`.
  * [contractes/nou/page.tsx](file:///media/akaun/Project_1/SEVALOR/pwa/src/app/gestio/contractes/nou/page.tsx#L47-L56): Fa una petició a un endpoint inexistent `GET /gestio/clients/${formData.client_id}` esperant `data.adreces` amb `nom_via`/`municipi`, en comptes de cridar `GET /gestio/clients/${client_id}/finques` (`nom`, `adreca`). Resultat: el selector de finques surt sempre buit.
  * [contractes/page.tsx](file:///media/akaun/Project_1/SEVALOR/pwa/src/app/gestio/contractes/page.tsx) i [contractes/[id]/page.tsx](file:///media/akaun/Project_1/SEVALOR/pwa/src/app/gestio/contractes/[id]/page.tsx#L138): Mostren l'UUID `client_id` en cru en comptes del nom del client, i no hi ha pujada OCR de contractes.
* **Solució aconsellada:**
  1. Restringir tot el router [contractes.py](file:///media/akaun/Project_1/SEVALOR/backend/app/api/v1/gestio/contractes.py) a `DIRECCIO` / `ADMIN` (`economics_boss_only`).
  2. Corregir `generar_prefactura` perquè calculi la quota proporcional segons `periodicitat`, generi una numeració seqüencial real per sèrie (sense `9999` ni `"draft_hash"`) i segueixi el flux d'esborrany HITL de Veri*factu.
  3. Corregir [contractes/nou/page.tsx](file:///media/akaun/Project_1/SEVALOR/pwa/src/app/gestio/contractes/nou/page.tsx#L47-L56) per consumir `GET /gestio/clients/${client_id}/finques` i resoldre els noms de client a les vistes de llistat i detall.

---

### BLOC 8 — Comptabilitat (`comptabilitat.py` i `comptabilitat/page.tsx`)

#### [B8-01] Filtre de període ignorat, input d'UUID manual i accions WIP/Rectificatives absents
* **Severitat:** Mitjana / Alta (Usabilitat i Compliment `Spec 007 RF-14`)
* **Evidència al codi:**
  * [comptabilitat/page.tsx](file:///media/akaun/Project_1/SEVALOR/pwa/src/app/gestio/comptabilitat/page.tsx#L231) (`#L276`, `#L315`): L'estat `periode` (`MES_ACTUAL`, etc.) consta a l'array de dependències de `useEffect` (`#L315`), però la petició `fetch` a `/gestio/comptabilitat/dashboard-economic?criteri_caixa=${criteriCaixa}` (`#L276`) no inclou el paràmetre `periode`.
  * [comptabilitat/page.tsx](file:///media/akaun/Project_1/SEVALOR/pwa/src/app/gestio/comptabilitat/page.tsx#L1210-L1220): El modal d'emissió de factura exigeix introduir manualment l'`"UUID Client"` (`xxxxxxxx-xxxx-...`) en text lliure.
  * La pestanya `WIP_CONTROL` (`#L760-L818`) no disposa d'un botó directe d'1 clic `"Convertir a Pre-factura"`, ni la taula de factures té botó per emetre rectificatives Sèrie R (`Spec 007 RF-14`).
* **Solució aconsellada:**
  1. Passar `&periode=${periode}` al endpoint del dashboard econòmic i suportar-lo al backend.
  2. Substituir l'input d'`UUID Client` per un selector real alimentat des de `GET /gestio/clients`.
  3. Afegir botons d'acció directa a `WIP_CONTROL` (convertir a pre-factura) i a les files de factures emeses (emetre rectificativa Sèrie R).

---

### BLOC 9 — Configuració, Notificacions i Plànols

#### [B9-01] `configuracio/page.tsx`: ADN de marca i pujada de logotip simulats, Telegram 422 i UI de Slots/Barema incompleta
* **Severitat:** Crítica
* **Norma vulnerada:** [constitution.md](file:///media/akaun/Project_1/SEVALOR/constitution.md#L1-L60) Principi I (Zero Mock Data), Principi VIII (Chameleon UI) i `Spec 01 FR-017`.
* **Evidència al codi:**
  * [configuracio/page.tsx](file:///media/akaun/Project_1/SEVALOR/pwa/src/app/gestio/configuracio/page.tsx#L238-L251) (`handleAnalitzarAdn`): Simula l'anàlisi amb `setTimeout(..., 1200)` retornant una paleta verda hardcodejada sense cridar l'endpoint real `POST /gestio/configuracio/marca/adn` ([configuracio.py](file:///media/akaun/Project_1/SEVALOR/backend/app/api/v1/gestio/configuracio.py#L464)) ni comprovar l'estat del Copilot.
  * [configuracio/page.tsx](file:///media/akaun/Project_1/SEVALOR/pwa/src/app/gestio/configuracio/page.tsx#L268-L292) (`handlePujarLogo`): Només fa `FileReader.readAsDataURL` en local a l'estat React i mostra un missatge fals d'èxit a Hetzner sense fer `POST /gestio/configuracio/logotip` ([configuracio.py](file:///media/akaun/Project_1/SEVALOR/backend/app/api/v1/gestio/configuracio.py#L563)).
  * [configuracio/page.tsx](file:///media/akaun/Project_1/SEVALOR/pwa/src/app/gestio/configuracio/page.tsx#L1378-L1381): Envia `{ token: telegramToken, secret: telegramSecret }`, però `TelegramConfigRequest` ([configuracio.py](file:///media/akaun/Project_1/SEVALOR/backend/app/api/v1/gestio/configuracio.py#L258-L260)) exigeix `{ telegram_bot_token, telegram_webhook_secret }` -> HTTP 422.
  * [configuracio/page.tsx](file:///media/akaun/Project_1/SEVALOR/pwa/src/app/gestio/configuracio/page.tsx#L1228-L1293): La pestanya `jornada` mostra `slots` però no té cap botó ni formulari per cridar `POST /gestio/configuracio/slots` ([configuracio.py](file:///media/akaun/Project_1/SEVALOR/backend/app/api/v1/gestio/configuracio.py#L1088)), i no hi ha interfície per configurar el Barema de Preus (`Spec 01 FR-017`).
* **Solució aconsellada:**
  1. Connectar `handleAnalitzarAdn` a `POST /gestio/configuracio/marca/adn` i `handlePujarLogo` (via `FormData`) a `POST /gestio/configuracio/logotip`.
  2. Corregir les claus JSON de Telegram a `{ telegram_bot_token, telegram_webhook_secret }`.
  3. Afegir el formulari de creació/edició de `slots` connectat a `POST /gestio/configuracio/slots` i afegir la sub-secció de Barema de Preus.

#### [B9-02] `notificacions`: Xat desconnectat de Telegram, camps incompatibles a la UI i tokens en RAM
* **Severitat:** Crítica
* **Norma vulnerada:** Fiabilitat de comunicacions (`Spec 05`) i integritat de payload API ↔ UI.
* **Evidència al codi:**
  * [notificacions.py](file:///media/akaun/Project_1/SEVALOR/backend/app/api/v1/gestio/notificacions.py#L117-L146) (`crear_missatge`): Desa el missatge a BD però **no crida `send_telegram_direct_message`**, deixant el canal de sortida mut.
  * [notificacions/page.tsx](file:///media/akaun/Project_1/SEVALOR/pwa/src/app/gestio/notificacions/page.tsx#L113-L115) envia `{ remitent: "OFICINA", canal: "WEB_PWA", contingut_text }`, que no coincideix amb `MissatgeCreate` (`contingut_text`, `tipus_esdeveniment`).
  * A [notificacions/page.tsx](file:///media/akaun/Project_1/SEVALOR/pwa/src/app/gestio/notificacions/page.tsx#L23-L27) (`#L286`, `#L302`), la UI llegeix `m.remitent === "OFICINA"` i `{m.remitent} • {m.canal}`, mentre que `MissatgeResponse` ([notificacions.py](file:///media/akaun/Project_1/SEVALOR/backend/app/api/v1/gestio/notificacions.py#L81-L86)) retorna `remitent_tipus` i `tipus_esdeveniment` -> s'avalua a `undefined`, alineant les bombolles al costat erroni i mostrant metadades buides.
  * [notificacions.py](file:///media/akaun/Project_1/SEVALOR/backend/app/api/v1/gestio/notificacions.py#L175) (`#L256`): `TOKENS_FACTURA` es guarda en memòria RAM del procés (es perd en reiniciar) i la URL del bot està hardcodejada a `campopro_bot`. A la UI manca el botó d'invitació a Telegram i es mostra `conversaActiva.id` en lloc del nom del client.
* **Solució aconsellada:**
  1. Invocar `send_telegram_direct_message` en segon pla (o Celery) des de `crear_missatge` quan el client tingui `telegram_chat_id`.
  2. Alinear el payload d'enviament i la interfície TypeScript de [notificacions/page.tsx](file:///media/akaun/Project_1/SEVALOR/pwa/src/app/gestio/notificacions/page.tsx) amb `remitent_tipus` i `tipus_esdeveniment`.
  3. Moure `TOKENS_FACTURA` a Redis (amb TTL), obtenir el `@bot_username` dinàmicament de la configuració d'empresa/bot, i mostrar el nom del client i el botó `"Convidar a Telegram"` a la UI.

#### [B9-03] `planols.py`: Error HTTP 500 en esborrar carpetes amb contingut
* **Severitat:** Mitjana
* **Evidència al codi:** [planols.py](file:///media/akaun/Project_1/SEVALOR/backend/app/api/v1/gestio/planols.py#L647-L670) (`eliminar_carpeta`): Executa la supressió de `CarpetaPlanol` directament sense esborrar ni desvincular prèviament `PlanolBase` i `CapaVectorial`, provocant `IntegrityError` (HTTP 500) quan la carpeta no està buida.
* **Solució aconsellada:** Esborrar en cascada controlada (o retornar 409 amb avís de confirmació / netejar prèviament `CapaVectorial` i `PlanolBase` dins la mateixa transacció).

---

## 3. Full de Ruta de Remediació Prioritzat (Segons `AGENTS.md`)

En compliment del protocol d'[AGENTS.md](file:///media/akaun/Project_1/SEVALOR/AGENTS.md) i de [Auditoria_i_Normativa_Tests_Backend.md](file:///media/akaun/Project_1/SEVALOR/sevalor_AgentV2/docs/sdd_sevalor_legacy/Auditoria_i_Normativa_Tests_Backend.md), el detall tècnic amb tot el codi i els tests per a cada bloc s'ha redactat a [PLA_IMPLEMENTACIO_GESTIO_SEVALOR.md](file:///media/akaun/Project_1/SEVALOR/PLA_IMPLEMENTACIO_GESTIO_SEVALOR.md). Cada bloc de correccions s'ha d'executar carregant prèviament les skills obligatòries (`supabase-postgres-best-practices`, `security-and-hardening`, `security-review`, `frontend-design`, `systematic-debugging`) i passant els tests sense mocks ni falsos positius (`pytest -v`, `ruff check .`, `mypy app/ --strict`, `npm run lint`, `npm run build` + validació en viu amb `chrome-devtools` i `postgres`):

1. **Prioritat P0 — Seguretat Multi-Tenant (RLS), RBAC i IA Sobirana:**
   * Blindar [cerca.py](file:///media/akaun/Project_1/SEVALOR/backend/app/api/v1/gestio/cerca.py) (`get_db_with_tenant_context` + `empresa_id`), [magatzem.py](file:///media/akaun/Project_1/SEVALOR/backend/app/api/v1/gestio/magatzem.py) (`Article` + `empresa_id`), [proveidors.py](file:///media/akaun/Project_1/SEVALOR/backend/app/api/v1/gestio/proveidors.py) i RBAC de [contractes.py](file:///media/akaun/Project_1/SEVALOR/backend/app/api/v1/gestio/contractes.py).
   * Aplicar el veto estricte `ENGINYER` (Principi VI) a `feines`, `magatzem`, `clients`, `flota`, `operaris` i `contractes`.
   * Tallar en sec el Copilot quan `node_ia_actiu` sigui `False` tant al backend ([dispatcher.py](file:///media/akaun/Project_1/SEVALOR/backend/app/services/subagents/dispatcher.py), [pressupostos.py](file:///media/akaun/Project_1/SEVALOR/backend/app/api/v1/gestio/pressupostos.py), [copilot.py](file:///media/akaun/Project_1/SEVALOR/backend/app/api/v1/gestio/copilot.py)) com al frontend ([layout.tsx](file:///media/akaun/Project_1/SEVALOR/pwa/src/app/gestio/layout.tsx), [CopilotWidget.tsx](file:///media/akaun/Project_1/SEVALOR/pwa/src/components/CopilotWidget.tsx)).
2. **Prioritat P1 — Fulla de Feines, Alta d'OT i Control Real d'Estoc:**
   * Crear `/gestio/feines/page.tsx`, afegir `"+ Nova Feina"` al Mapa, arreglar [CrearOTModal.tsx](file:///media/akaun/Project_1/SEVALOR/pwa/src/components/gestio/CrearOTModal.tsx) (Botó Triple real, Cap de Colla opcional, alta atòmica amb picking) i afegir `BLOQUEJAT_RISC` (423) + `FR-012` a [feines.py](file:///media/akaun/Project_1/SEVALOR/backend/app/api/v1/gestio/feines.py).
   * Corregir tot el cicle d'estoc a [magatzem.py](file:///media/akaun/Project_1/SEVALOR/backend/app/api/v1/gestio/magatzem.py) i [magatzem/page.tsx](file:///media/akaun/Project_1/SEVALOR/pwa/src/app/gestio/magatzem/page.tsx): estoc inicial, ajust manual UI, `codi_barres`, `estoc_disponible = fisica - reservada`, filtre per `magatzem_id`, descompte real en `confirmar_devolucio`, edició d'eines i bústia `RECOMPRA_STOCK`.
3. **Prioritat P2 — Correcció d'Endpoints Trencats, Mocks Residuals i Desacoblaments UI:**
   * Eliminar tots els mocks restants (`proveidors` IBANs/Simular BEC, `operaris` GPS Lleida, `configuracio` ADN i pujada logo, `feines` `/intervencions-actives`, `contractes` `PRE-9999`).
   * Arreglar els payloads incompatibles (`copilot` RAG, `configuracio` Telegram, `notificacions` xat + enviament Telegram + Redis tokens, `contractes/nou` finques, `clients` CSV export, `flota` `VehicleProperItem` i persistència d'anomalia consum, `comptabilitat` filtre `periode` + selector clients + WIP/Rectificatives, `planols` esborrat de carpetes).
