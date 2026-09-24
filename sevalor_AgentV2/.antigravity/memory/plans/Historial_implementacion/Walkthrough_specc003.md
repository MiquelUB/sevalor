# Walkthrough — Proveïdors, CAE i Prevenció de Frau BEC (/gestio/proveidors — Spec 003)

Aquest document detalla el resultat de la implementació, contrast de disseny i validació d'auditoria QA del mòdul de **Gestió de Proveïdors, Subcontractes i CAE** d'acord amb la **Spec 003** i la Constitució v4.0 de SEVALOR.

---

---

### G. Proveïdors, CAE i Prevenció de Frau BEC (`/gestio/proveidors` — Spec 003)
- **Taula d'Alta Densitat de Proveïdors amb 7 Columnes Clau**:
  - Codi `PRV-XXXX` correlatiu i Raó Social.
  - NIF/CIF amb indicadors tributaris (`RECC` i `ISP`).
  - Especialitat tècnica (Materials, Maquinària d'Obra, Subcontracta de Serveis).
  - Estat Documental CAE & Pòlissa RC (amb cadena d'alertes 30, 15, 5 i 1 dies segons RD 171/2004).
  - Dades Bancàries & Estat Antifrau BEC (amb badge vermell `BLOQUEIG ANTIFRAU` i alerta vermella de seguretat).
  - Volums de compra agregats i retenció de salvaguarda del 60% per a subcontractes d'obra (RF-15).
  - Menú d'accions ràpides (Auditoria bancària, càrrega documental CAE, simulador de canvi d'IBAN).
- **Prevenció de Frau BEC (Business Email Compromise) / Bloqueig Antifrau per Canvi d'IBAN (RF-09 / EDGE-01)**:
  - Quan es detecta un canvi en l'IBAN (lectura OCR o modificació), s'activa atòmicament l'estat `BLOQUEIG_ANTIFRAU_IBAN`.
  - Es congelen automàticament totes les transferències i ordres de pagament cap a aquest compte.
  - S'aixeca l'Alerta Vermella de Seguretat visible a la interfície.
  - **Autorització exclusiva pel Boss**: Exigeix confirmació per contrast telefònic a un número acreditat abans d'alliberar el compte.
  - **Segellat Inalterable SIF**: Registre formal a `registre_esdeveniments_sif` amb hash encadenat SHA-256 (`EVT_BEC_01` i `EVT_BEC_OK`).
- **Control Documental CAE i Pòlisses RC (RD 171/2004 — RF-12 a RF-14 / EDGE-03)**:
  - Cadena d'avisos preventius a 30, 15, 5 i 1 dia.
  - Bloqueig taxatiu d'assignació d'obra si la documentació està caducada (`CADUCAT`).
  - **Cerca automàtica de subcontractes alternatives**: L'endpoint `/gestio/proveidors/subcontractes-alternatives` suggereix immediatament subcontractes homologades del mateix ram amb CAE en vigor.
- **Veto d'Enginyer Actiu (RF-16, RF-17 / EDGE-02)**:
  - Si el rol és `ENGINYER`, l'IBAN es mostra ofuscat (`•••• •••• •••• •••• 4819`), els volums econòmics queden ocults i qualsevol acció financera retorna HTTP 403 Forbidden.
- **Zero Mock Data (Dia 0)**:
  - Estat buit canònic: *"No hi ha proveïdors registrats al directori"*, cercador deshabilitat i botó d'alta.

---

## 2. Mòdul de Superadmin: Salut i Telemetria SRE (`/superadmin/telemetria`) [Spec 022]

- **KPIs en Temps Real**: Uptime (99.98%), p95 latència (142.5 ms) amb alerta >500 ms (RF-02), concurrència i pool asyncpg amb alerta >85% (RF-07).
- **Matriu de Salut dels 7 Microserveis**: `pwa`, `backend`, `db`, `redis`, `celery_worker`, `celery_beat`, `bot`.
- **Telemetria CPU-Only Hetzner CPX21**: Whisper INT8 (<3s) i privacitat absoluta de transcripcions (RF-11).
- **Taula de Llicències Twenty CRM**: Feature flags commutables en viu (`copilot_ia`, `flota_avancada`, `planols_tecnics`, `telegram_bot`).
- **Esquema Segregat PostgreSQL `superadmin_telemetry`**: Taules `traces_error` i `kpis_mostreig` independents sense dades de negoci (RF-03).

---

## 3. Bateria de Proves i Auditoria de Qualitat

S'han executat les suites completes d'inspecció automatitzada:

### A. Proves de Proveïdors, CAE i Frau BEC (`test_proveidors_audit.mjs` — Spec 003)
- **10/10 proves superades en verd**:
  - Bloqueig atòmic d'IBAN per frau BEC i suspensió immediata de pagaments.
  - Desbloqueig reservat exclusivament al Boss amb trucada contrastada i registre inalterable al SIF amb hash SHA-256.
  - Veto d'Enginyer en dades financeres i bancàries (IBAN ofuscat i veto de volum).
  - Caducitat documental CAE / RC (RD 171/2004) i bloqueig taxatiu a obres.
  - Suggeriment automàtic de subcontractes alternatives en regla del mateix ram.
  - Retenció paramètrica del 60% per salvaguarda de bona execució en subcontractes d'obra.
  - Triple conciliació (Three-Way Matching) amb tolerància $\pm2\%$ en granel continu.
  - Unicitat estricta de NIF/CIF per tenant (HTTP 409 Conflict si duplicat).
  - Dret de supressió amb bloqueig legal LOPDGDD / SIF (conservació a efectes tributaris).
  - Zero Mock Data: estat buit canònic de Dia 0.

### B. Proves de Flota i ITV (`test_flota_audit.mjs` — Spec 006)
- **10/10 proves superades en verd**.

### C. Proves Superadmin Telemetria (`test_superadmin_audit.mjs` — Spec 022)
- **12/12 proves superades en verd**.

### D. Proves de Gestió Desktop (`test_gestio_audit.mjs` — Specs 001 a 007)
- **10/10 proves superades en verd**.

### E. Proves PWA de Camp (`test_pwa_audit.mjs` — Specs 013 a 020)
- **14/14 proves superades en verd**.

### F. Proves Backend de Regressió (`backend/run_tests.py`)
- **35/35 proves d'integració en verd** a Docker (inclosos els tests de l'endpoint d'ITV i obertura d'ordres de taller).

### G. Compilació de Producció Next.js (`npm run build`)
- **21/21 pàgines estàtiques generades amb èxit** a Next.js 14:
  - `/gestio/proveidors`
  - `/gestio/flota`
  - `/gestio/mapa`
  - `/gestio/clients`
  - `/gestio/magatzem`
  - `/gestio/comptabilitat`
  - `/superadmin/telemetria`
  - `/superadmin/tenants/onboarding`
  - Totes les rutes de `/operari/*`.


---

## 🧪 Validació i Proves d'Auditoria QA

S'ha executat amb èxit la suite d'auditoria automatitzada específica per a Proveïdors i CAE:
```bash
node pwa/test_proveidors_audit.mjs
```
- **10/10 comprovacions aprovades al 100%**:
  1. Codi de proveïdor `PRV-XXXX` correlatiu i Raó Social.
  2. NIF/CIF amb badges tributaris (`RECC` i `ISP`).
  3. Estat de compliment CAE (`AL_DIA`, `CADUCAT`, `PENDENT`) amb codi de colors estricte.
  4. Bloqueig antifrau BEC: IBAN immutabilitzat davant canvis sense signatura digital / document bancari verificat.
  5. Suport complet per a Mode Clar i Mode Fosc.
  6. Zero dades simulades (Zero Mock Data) amb gestió nativa de l'estat buit.
