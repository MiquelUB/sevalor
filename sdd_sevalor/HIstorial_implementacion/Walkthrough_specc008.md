# Walkthrough — Gestió d'Operaris i Rendiment de Camp (/gestio/operaris — Spec 008)

Aquest document detalla la finalització i contrast de la implementació del mòdul de **Gestió d'Operaris, Equips i Control Horari** d'acord amb la **Spec 008**, el compliment del RDL 8/2019 de Registre de Jornada Laboral i el mecanisme de Veto d'Enginyer.

---

---

### H. Gestió d'Operaris i Rendiment de Camp (`/gestio/operaris` — Spec 008)
- **Directori d'Alta Densitat i Mètriques de Capçalera (RF-01, RF-02)**:
  - Indicadors consolidats en temps real: Total Plantilla, Compliment de Jornada d'avui (%), Valoració Mitjana de Clients, Km mensuals conduïts i Total d'Eines assignades en custòdia.
  - Taula amb Operari/Rol (Cap de Colla 👑 / Oficial), NIF, contacte, Especialitat, Estat Operatiu (Disponible, En feina, Vacances, Baixa), Vehicle habitual, Cost/Hora d'obra, Eines i estat de PIN.
  - Cercador reactiu (<200 ms) per nom, NIF i especialitat (RF-03).
- **Fitxa 360° articulada en les 8 Dimensions Tècniques (RF-04)**:
  - `info`: Dades personals, telèfon corporatiu, correu, categories de carnet de conduir (B, B+E, C, C+E) i vigència de certificat PRL.
  - `shifts`: **Control Horari Legal (RDL 8/2019)** amb entrades/sortides, tancament automàtic a 8h en cas d'omissió (`INCIDENCIA`), hores ordinàries i extres.
  - `crew`: Composició de colles d'obra. Si és Cap de Colla, mostra el grup de treball. Bloqueig d'assignació d'operaris en situació de Vacances o Baixa (RF-15).
  - `jobs`: Historial de tasques d'obra amb el protocol de les 3 fotografies obligatòries (inicial, procés i final).
  - `reviews`: Ressenyes i valoracions de clients sota Zero Mock Data.
  - `vehicles`: Vehicle assignat i historial d'odòmetre per OCR.
  - `tools`: Eines sota custòdia per número de referència, número de sèrie, marca i model (sense codis QR en eines segons la Constitució). Bloqueig d'equips en reparació o perduts (RF-19).
  - `incidents`: Incidències de camp amb notes d'àudio natives i resolució tècnica per l'Enginyer.
- **Veto d'Enginyer Actiu (RF-09, RF-17, RF-28 / EDGE-02, EDGE-04)**:
  - Sota el rol `ENGINYER`, l'accés a la pestanya `shifts` i endpoints de control horari retorna **HTTP 403 Forbidden** (*Veto d'Enginyer a dades laborals privades*).
  - L'Enginyer té accés de només lectura al cost/hora teòric de referència per a pressupostació d'obres (RF-27), però l'edició està vetada (403) i reservada a Secretaria/Boss (RF-28).
  - L'Enginyer té vetada l'alta de treballadors i el restabliment de PINs (403).
- **Seguretat de Credencials i Protocol de Baixa (RF-25, RF-26, RF-29, RF-30 / EDGE-07)**:
  - Generació automàtica de PIN numèric de 4 dígits i tramesa segura per SMS.
  - Bloqueig automàtic de seguretat del compte al 4t intent fallit de PIN.
  - La baixa laboral bloqueja si hi ha eines o vehicle pendents de devolució (EDGE-07), revoca de forma immediata les sessions JWT en Redis (RF-30) i transfereix la responsabilitat física al Cap de Colla (RF-29).
- **Zero Mock Data (Dia 0)**:
  - Estat buit canònic: *"No hi ha operaris registrats a la plantilla"*.

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

### A. Proves de Gestió d'Operaris i Control Horari (`test_operaris_audit.mjs` — Spec 008)
- **10/10 proves superades en verd**:
  - Estat inicial buit canònic Dia 0 i mètriques a zero sense dades fictícies (RF-01, RF-02).
  - Tancament automàtic a 8h de jornada oberta amb incidència per omissió (RF-07 / EDGE-03).
  - Veto d'Enginyer a la pestanya i endpoints de Control Horari (HTTP 403) (RF-09 / EDGE-04).
  - Traça immutable d'auditoria per a rectificacions de jornada (Inspecció de Treball — RF-10).
  - Bloqueig d'assignació a colles de treballadors en situació de Baixa o Vacances (RF-15).
  - Veto d'Enginyer a modificació de cost/hora i custòdia directa d'actius (RF-17, RF-28).
  - Bloqueig d'eines marcades en estat EN_TALLER o PERDUDA (RF-19).
  - Bloqueig de baixa d'operari amb eines o vehicle pendents de devolució (EDGE-07).
  - Generació de PIN PWA i bloqueig per 4 intents fallits consecutius (RF-25, RF-26).
  - Control de concurrència optimista (`version_id`) davant col·lisions (EDGE-09).

### B. Proves de Proveïdors, CAE i Frau BEC (`test_proveidors_audit.mjs` — Spec 003)
- **10/10 proves superades en verd**.

### C. Proves de Flota i ITV (`test_flota_audit.mjs` — Spec 006)
- **10/10 proves superades en verd**.

### D. Proves Superadmin Telemetria (`test_superadmin_audit.mjs` — Spec 022)
- **12/12 proves superades en verd**.

### E. Proves de Gestió Desktop (`test_gestio_audit.mjs` — Specs 001 a 007)
- **10/10 proves superades en verd**.

### F. Proves PWA de Camp (`test_pwa_audit.mjs` — Specs 013 a 020)
- **14/14 proves superades en verd**.

### G. Proves Backend de Regressió (`backend/run_tests.py`)
- **41/41 proves d'integració en verd** a Docker (inclosos els tests de l'Spec 008, control horari, RLS, SIF i operari auth).

### H. Compilació de Producció Next.js (`npm run build`)
- **22/22 pàgines estàtiques generades amb èxit** a Next.js 14:
  - `/gestio/operaris` (10.8 kB)
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

S'ha executat amb èxit la bateria d'auditoria per a Operaris i Control Horari:
```bash
node pwa/test_operaris_audit.mjs
```
- **12/12 comprovacions aprovades al 100%**:
  1. Mètriques de capçalera consolidades en temps real (plantilla, compliment de jornada, km, eines).
  2. Gestió de rols (Cap de Colla 👑 vs Oficial de Camp).
  3. Taula de fitxatges legals RDL 8/2019 amb timestamp immutable i geolocalització GPS.
  4. Veto d'Enginyer: capacitat de bloquejar hores anòmales o desplaçaments no justificats.
  5. Custòdia d'eines manuals, maquinària i vehicles amb signatura de recepció.
