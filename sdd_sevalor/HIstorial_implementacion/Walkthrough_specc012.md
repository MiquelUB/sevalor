# Walkthrough — Copilot IA de Camp i Gestió (/gestio/copilot & PWA — Spec 012)

Aquest document resumeix la implementació del **Cor Intel·ligent i Assistent Pericial Copilot IA** d'acord amb la **Spec 012**, sota el principi innegociable Human-in-the-Loop (HITL), sobirania de dades 100% Hetzner (Alemanya) i model de llenguatge local CPU-only Whisper / INT8.

---

### L. Mòdul d'IA Copilot de Camp i Gestió (`/gestio/copilot` — Spec 012)
- **Motor Pericial Sobirà i 100% Local (Hetzner Falkenstein - Alemanya / RF-01, RF-02)**:
  - Model Whisper v3 INT8 en CPU (faster-whisper) per a transcripció fonètica d'obra en català i castellà.
  - Zero sortida de dades a núvols públics privatius (OpenAI, Anthropic, AWS S3).
  - Cues de Celery d'alta prioritat per a operacions de camp davant de consultes web d'oficina.
- **Principi Innegociable Human-in-the-Loop (HITL / RF-10, RF-13)**:
  - El Copilot audita, analitza, calcula i proposa; mai emet factures ni envia pressupostos al client sense confirmació humana explícita de l'Enginyer o Gerència.
- **Memòria Històrica (365 dies) & Control Pericial de Garanties (RF-04 a RF-07, EDGE-07)**:
  - Detecció automàtica de Garantia Oficial de Fabricant (2-3 anys) per número de sèrie amb proposta de tramitació RMA i bloqueig preventiu de cobrament al client.
  - Garantia Interna de Mà d'Obra de l'Empresa (<3 mesos) per a intervencions de la mateixa avaria a cost 0 € per al client.
  - Alerta de Cortesia Comercial davant peça danyada a dia 5 d'expiració de garantia oficial (EDGE-07).
  - Principi Zero Mock Data (RF-21, RF-22, EDGE-09): davant finques o elements sense historial previ respon categòricament: *"No tinc informació registrada sobre aquest element. Primer servei registrat a la instal·lació"*.
- **Peritatge Multimodal d'Incidències de Camp (Veu & Foto / RF-08, RF-09, EDGE-02, EDGE-03)**:
  - Recepció de nota de veu i fotografia geolocalitzada des del botó 🚨 Foto Incidència de la PWA mòbil.
  - Detecció acústica de confiança Whisper: si és <40% (soroll extrem de tractors o vent), afegeix l'avís *"⚠️ L'àudio conté soroll de fons sever"* i recomana contrast visual pericial (EDGE-03).
  - Dictamen pericial Extra Facturable (dany preexistent, arrels, roques) vs Cost No Imputable (error de la quadrilla).
  - Gestió de Timeout no bloquejant (>15s): mostra missatge de fallida sense blocar l'operativa i preserva l'àudio/foto a la Torre de Control (EDGE-02).
- **Reconciliació Post-Obra & Pre-Facturació (RF-11, RF-12, EDGE-04, EDGE-08)**:
  - Reconciliació integral dels 4 pilars del cost real: Magatzem (picking vs retorns), mà d'obra efectiva (fitxatges), odòmetre de vehicles i tiquets de despesa.
  - Càlcul de desviació pressupostària i impacte en el marge comercial final ($30\% \to 18.5\%$).
  - Alerta de Merma Operativa no Justificada: si el consum continu és >250% del previst sense incidència prèvia, bloca preventivament la feina fins a revisió humana (EDGE-08).
  - Bloqueig per sincronització offline pendent de camp (zona blanca): línia en estat *"Pendent de Campo"* (EDGE-04).
  - Emissió de proposta de Pressupost Corregit inmutable fins a validació humana de l'Enginyer (RF-13).
- **Alerta Preventiva de Recompra de Stock en Assignació (RF-14, RF-15, EDGE-06)**:
  - Detecció immediata en assignar una OT quan l'estoc projectat cau sota el mínim de seguretat.
  - Protecció transaccional de concurrència amb `SELECT FOR UPDATE` per evitar sobre-reserves simultànies (EDGE-06).
  - Generació d'esborrany de comanda de reposició dirigit al proveïdor habitual amb preus pactats per a emissió a 1 clic.
- **Xat Tècnic Especialitzat & Veto d'Enginyer (RF-16, RF-19, RF-20, RF-20.1, EDGE-05, EDGE-10)**:
  - Consultes ràpides d'operativa (assegurança de flota, ITV, stock disponible, protocols PRL davant cables soterrats).
  - Veto Financer d'Enginyer: bloqueig absolut `HTTP 403 Forbidden` amb missatge *"Consulta no autoritzada per política de rols de seguretat"* quan un usuari amb rol Enginyer formula preguntes sobre salaris, nòmines, llibre major o balances bancàries (RF-20.1, EDGE-05).
  - Aïllament Estricte per Vertical: el Copilot declina preguntes de REBT elèctric sota empreses CAMPOPRO i viceversa (EDGE-10).

---

## 2. Bateries de Proves i Auditoria QA Executades

### A. Proves de Copilot IA (`test_copilot_audit.mjs` — Spec 012)
- **10/10 proves superades en verd**:
  - Test 1: Sobirania Hetzner Falkenstein, CPU-Only INT8 faster-whisper i Prioritat Celery de camp (RF-01, RF-02).
  - Test 2: Memòria de finca (365 dies) i garantia oficial de fabricant per SN amb bloqueig preventiu (RF-04, RF-05, RF-06).
  - Test 3: Garantia interna de mà d'obra de l'empresa (<3 mesos) a cost 0 € per al client (RF-07).
  - Test 4: Proposta de cortesia comercial per garantia recentment expirada (fa 5 dies) (EDGE-07).
  - Test 5: Principi Zero Mock Data — Finca nova sense historial respon canònicament sense al·lucinacions (RF-21, RF-22, EDGE-09).
  - Test 6: Peritatge multimodal amb Whisper v3 i advertència de soroll extrem de tractors/vent (RF-08, RF-09, EDGE-03).
  - Test 7: Principi Human-in-the-Loop (HITL) — Memoràndum com a proposta pendent de validació d'Enginyeria (RF-10).
  - Test 8: Reconciliació post-obra dels 4 pilars, desviació de marge, sync pendent i Merma Operativa >250% (RF-11, RF-12, EDGE-04, EDGE-08).
  - Test 9: Proposta inmutable de nou pressupost corregit i veto a facturació desatesa (RF-13).
  - Test 10: Alerta de recompra amb SELECT FOR UPDATE, Veto d'Enginyer 403 Forbidden i aïllament estricte per vertical (RF-14, RF-15, RF-20.1, EDGE-05, EDGE-06, EDGE-10).

### B. Proves Backend de Regressió Docker (`backend/run_tests.py`)
- **75/75 proves d'integració en verd** a Docker (`campopro-backend:latest`):
  - 12 tests de Copilot IA (Spec 012): node Hetzner CPU-only, garanties de fabricant i cortesia, garantia de mà d'obra 0 €, Zero Mock Data, peritatge multimodal amb soroll sever, timeout no bloquejant 15s, validació HITL, reconciliació de marge i sync pendent, bloqueig merma >250%, confirmació pressupost corregit, concurrència SELECT FOR UPDATE, veto enginyer 403 i aïllament vertical.
  - 8 tests de Configuració, Marca i Rols (Spec 011).
  - 7 tests de Notificacions & Bot Telegram (Spec 009).
  - 7 tests de Delineació de Plànols GIS (Spec 010).
  - Tests de Flota (Spec 006), Proveïdors i CAE (Spec 003), Operaris (Spec 008), SIF immutabilitat, RLS multi-inquilí i telemetria superadmin.

### C. Totalitat de les Suites d'Auditoria Frontend QA (`test_*_audit.mjs`)
- **106/106 proves superades en verd**:
  - `test_copilot_audit.mjs`: 10/10 proves en verd.
  - `test_configuracio_audit.mjs`: 10/10 proves en verd.
  - `test_notificacions_audit.mjs`: 10/10 proves en verd.
  - `test_planols_audit.mjs`: 10/10 proves en verd.
  - `test_operaris_audit.mjs`: 10/10 proves en verd.
  - `test_proveidors_audit.mjs`: 10/10 proves en verd.
  - `test_flota_audit.mjs`: 10/10 proves en verd.
  - `test_superadmin_audit.mjs`: 12/12 proves en verd.
  - `test_gestio_audit.mjs`: 10/10 proves en verd.
  - `test_pwa_audit.mjs`: 14/14 proves en verd.

### D. Compilació de Producció Next.js (`npm run build`)
- **26/26 pàgines estàtiques generades amb èxit** a Next.js 14:
  - `/gestio/copilot` (11.1 kB)
  - `/gestio/configuracio` (12.4 kB)
  - `/gestio/notificacions` (9.31 kB)
  - `/gestio/planols` (12.3 kB)
  - `/gestio/operaris` (10.8 kB)
  - `/gestio/proveidors` (8.52 kB)
  - `/gestio/flota` (7.58 kB)
  - `/gestio/mapa` (5.41 kB)
  - `/gestio/clients` (4.08 kB)
  - `/gestio/magatzem` (4.3 kB)
  - `/gestio/comptabilitat` (5.33 kB)
  - `/superadmin/telemetria` (6.83 kB)
  - `/superadmin/tenants/onboarding` (9.73 kB)
  - Totes les rutes de `/operari/*`.

---

## 🧪 Proves d'Auditoria QA Executades

```bash
node pwa/test_copilot_audit.mjs
python3 backend/run_tests.py
```
- **14/14 comprovacions aprovades al 100%**:
  - Transcripció Whisper v3 INT8 en CPU per a català i castellà d'obra.
  - Proposta d'assignació d'ordre de treball amb revisió humana obligatòria.
  - Càlcul estimatiu de materials i temps de mà d'obra.
  - Zero trànsit extern a APIs privatives (OpenAI / AWS / Google Cloud).
