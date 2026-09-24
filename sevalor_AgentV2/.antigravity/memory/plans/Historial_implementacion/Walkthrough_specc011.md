# Walkthrough — Configuració de l'Empresa, Jornada Laboral, Marca Camaleònica i Rols (/gestio/configuracio — Spec 011)

Aquest document resumeix la implementació del panell d'ajustos estratègics, identitat corporativa, governança laboral i motor camaleònic de CampoPro / SEVALOR Suite v4.0.

---

### I. Configuració de l'Empresa, Jornada Laboral, Marca Camaleònica i Rols (`/gestio/configuracio` — Spec 011)
*Panell d'ajustos estratègics, identitat corporativa, governança laboral i motor camaleònic.*
- **Motor Camaleònic HSL & Termòmetre de Contrast WCAG 2.1 AA (RF-12 a RF-15, EDGE-02)**:
  - Selector visual per a colors primari, secundari i accent en format HSL.
  - Validació algorítmica WCAG 2.1 AA en viu: bloqueig taxatiu (HTTP 422) si el ràtio de contrast contra fons blanc és inferior a 4.5:1.
  - Finestra de Live Preview interactiva en temps real.
  - Assistent IA d'ADN de marca amb anàlisi semàntic de la guia d'estil corporativa i mandat Human-in-the-Loop (HITL) amb aprovació explícita del Boss.
- **Logotip Oficial & Monograma Tipogràfic Net (RF-16 a RF-18, EDGE-03)**:
  - Càrrega de logotip en format PNG o JPG (límit màxim de 10 MB).
  - Validació estricta de Magic Bytes reals de capçalera (rebuig d'executables camuflats).
  - Generació automàtica de monograma net basat en les inicials de la raó social en absència de logotip (Zero Mock Data).
  - Emmagatzematge sobirà a servidors dedicats Hetzner Falkenstein (`/docs/<empresa_id>/configuracio/`), amb prohibició total d'AWS S3.
- **Personal d'Oficina & Seguretat 2FA TOTP (RF-01 a RF-07, EDGE-01, EDGE-05)**:
  - Taula de personal administratiu (Boss, Secretaria, Enginyer, Comptabilitat) amb contrasenya segura de 12 caràcters sota bcrypt.
  - 2FA TOTP obligatori per a tots els perfils que accedeixen al Dashboard Web.
  - Reinici de secret 2FA facultat exclusivament al Boss amb generació de codi QR estàndard de seguretat (Google Authenticator).
  - Protecció d'orfandat de l'inquilí (EDGE-05): bloqueig atòmic (HTTP 400) davant de qualsevol intent de baixa o eliminació de l'últim Boss de l'empresa.
  - Protocol d'emergència per l'últim Boss amb un dels 8 codis de recuperació estàtics d'onboarding (EDGE-01), blindat contra qualsevol override per Superadmin.
- **Slots de Jornada Laboral Individualitzats & Intensiva d'Estiu (RF-08 a RF-11, EDGE-04, EDGE-08)**:
  - Configuració de modalitats: Jornada Continuada, Jornada Partida i Torn Especial.
  - Validació cronològica coherent de pauses de dinar (inici < fi de dinar i dins del torn laboral).
  - Suport complet per a Jornada Intensiva d'Estiu amb dates de vigència.
  - Sincronització amb Spec 008 per al tancament automàtic a les 8h de jornada (càlcul absolut en timestamps UTC per a canvis DST).
- **Paràmetres del Bot de Telegram Corporatiu (RF-19, RF-20, EDGE-09)**:
  - Gestió de Token de BotFather i Webhook Secret.
  - Test asíncron de getMe amb gestió de timeout a 5 segons sense bloquejar el cicle d'esdeveniments.
- **Veto d'Enginyer (RF-03, EDGE-10)**:
  - Accés de només lectura als paràmetres corporatius i al seu propi slot de jornada.
  - Veto absolut (HTTP 403 Forbidden) sobre l'edició de marca, logotips, usuaris, 2FA i Telegram.

---

---

### A. Proves de Configuració, Marca i Rols (`test_configuracio_audit.mjs` — Spec 011)
- **10/10 proves superades en verd**:
  - Llistat de personal administratiu, generació de contrasenya forta de 12 caràcters i Zero Mock Data Dia 0 (RF-01, RF-02, RF-04).
  - Veto d'Enginyer (HTTP 403 Forbidden) en qualsevol mutació corporativa d'empresa, marca o personal (RF-03, EDGE-10).
  - Protecció d'orfandat de l'inquilí: rebuig atòmic (HTTP 400) de l'eliminació o baixa de l'últim Boss (EDGE-05).
  - 2FA TOTP mandatori, reinici facultat exclusivament al Boss i codis de recuperació estàtics d'onboarding per a l'últim Boss (RF-05, RF-06, EDGE-01).
  - Inactivació de compte amb expulsió immediata i revocació de JWT a Redis (RF-07).
  - Slots de jornada individualitzats, validació cronològica coherent de jornada partida i suport d'intensiva d'estiu (RF-08 a RF-11, EDGE-08).
  - Motor Camaleònic HSL, validació algorítmica WCAG 2.1 AA (mínim 4.5:1) i mandat HITL d'ADN de marca (RF-12 a RF-15, EDGE-02).
  - Càrrega de logotip <=10MB, validació de Magic Bytes de capçalera i monograma tipogràfic net (RF-16 a RF-18, EDGE-03).
  - Paràmetres del Bot de Telegram i prova asíncrona getMe amb gestió de timeout a 5s (RF-19, RF-20, EDGE-09).
  - Sobirania Hetzner Alemanya (`/docs/<empresa_id>/configuracio/`), zero dependències d'AWS S3 i Mode Fosc (`dark:`).

### B. Proves de Notificacions & Telegram (`test_notificacions_audit.mjs` — Spec 009)
- **10/10 proves superades en verd**:
  - Cerca multiclient reactiva (<200 ms) i Zero Mock Data Dia 0 (RF-01, RF-02, RF-05).
  - Cicle de vida de converses: semàfor cromàtic (Vermell, Blau, Verd), arxiu automàtic i reobertura per nou missatge (RF-06 a RF-09, EDGE-08).
  - Accés blindat al Bot de Telegram: deep link unívoc, expiració de 48h, rebuig d'usuaris no registrats sense generar spam (EDGE-01), bloqueig de col·lisió (EDGE-09) i revocació per baixa de client (EDGE-10).
  - Automatismes de camp: restricció exclusiva als 3 automatismes permesos i bloqueig de qualsevol altre enviament sense aprovació humana HITL (RF-14 a RF-17).
  - Aprovació interactiva de pressupostos (Memòndum): idempotència atòmica via token, injecció a OT, desbloqueig de Kanban mòbil, i sol·licitud de modificacions amb commutació a blau i alerta a enginyer (RF-18 a RF-20, EDGE-05).
  - Incidències i adjunts multimèdia: validació de límit de 15 MB, tipus MIME i commutació immediata a Vermell prioritari (RF-21 a RF-23, EDGE-07).
  - RAG local sobirà (LM Studio / Ollama): llindar de confiança del 80%, anti-al·lucinació estricta i escalada urgent a l'enginyer sota incertesa (RF-24 a RF-27, EDGE-04).
  - Factures Veri*factu: enllaç temporal de descàrrega de màxim 72 hores, Veto estricte d'Enginyer (HTTP 403) i bloqueig amb HTTP 410 Gone si el token ha caducat (RF-28 a RF-30, EDGE-06).
  - Sobirania de dades Hetzner Falkenstein i prohibició taxativa d'AWS S3.
  - Disseny camaleònic i suport integral de Mode Fosc (`dark:`).

### C. Proves de Delineació de Plànols GIS & Caixetí (`test_planols_audit.mjs` — Spec 010)
- **10/10 proves superades en verd**:
  - Estructura de carpetes per categories i Zero Mock Data Dia 0 (RF-01, RF-04).
  - Validació de límit de 50 MB i rebuig d'executables (RF-05, EDGE-04).
  - Visor híbrid WGS84 vs Documental unifilar (RF-06, RF-07).
  - Veto de Secretaria llança 403 a la delineació (RF-10, RF-11).
  - Immutabilitat de capa d'obra tancada amb bloqueig 403 (RF-12, EDGE-05).
  - Control de concurrència optimista amb version_id (EDGE-01).
  - Catàleg de símbols normalitzats de reg i obra civil (RF-14, RF-16).
  - Pins d'incidència amb fotos WebP i veu WebM (RF-18, RF-20).
  - Caixetí oficial homologat i exclusió estricta de QR d'eines segons Constitució v4.0 (RF-23, RF-25).
  - Exportació CAD GeoJSON WGS84 i sobirania Hetzner Alemanya (RF-26).

### D. Proves de Gestió d'Operaris i Control Horari (`test_operaris_audit.mjs` — Spec 008)
- **10/10 proves superades en verd**.

### E. Proves de Proveïdors, CAE i Frau BEC (`test_proveidors_audit.mjs` — Spec 003)
- **10/10 proves superades en verd**.

### F. Proves de Flota i ITV (`test_flota_audit.mjs` — Spec 006)
- **10/10 proves superades en verd**.

### G. Proves Superadmin Telemetria (`test_superadmin_audit.mjs` — Spec 022)
- **12/12 proves superades en verd**.

### H. Proves de Gestió Desktop (`test_gestio_audit.mjs` — Specs 001 a 007)
- **10/10 proves superades en verd**.

### I. Proves PWA de Camp (`test_pwa_audit.mjs` — Specs 013 a 020)
- **14/14 proves superades en verd**.

### J. Proves Backend de Regressió Docker (`backend/run_tests.py`)
- **63/63 proves d'integració en verd** a Docker:
  - 8 tests de Configuració, Marca i Rols (Spec 011: dades corporatives, monograma net, veto enginyer 403, contrast WCAG 4.5:1, magic bytes de logo, protecció últim Boss 400, reinici 2FA per Boss, slots jornada coherents i estiu, Telegram getMe).
  - 7 tests de Notificacions & Bot Telegram (Spec 009: token 48h, rebuig spam EDGE-01, semàfor cromàtic, 3 automatismes camp vs HITL, memòndum idempotent, RAG local 80%, token 72h veri*factu i veto enginyer 403).
  - 7 tests de Delineació de Plànols (Spec 010: carpetes, límits 50MB, veto secretaria, immutabilitat, concurrència, caixetí sense QR d'eines, CAD GeoJSON).
  - Tests de Gestió d'Operaris (Spec 008), control horari, RLS multi-inquilí, SIF, operari auth i telemetria superadmin.

### K. Compilació de Producció Next.js (`npm run build`)
- **25/25 pàgines estàtiques generades amb èxit** a Next.js 14:
  - `/gestio/configuracio` (12.4 kB)
  - `/gestio/notificacions` (9.3 kB)
  - `/gestio/planols` (12.3 kB)
  - `/gestio/operaris` (10.8 kB)
  - `/gestio/proveidors` (8.52 kB)
  - `/gestio/flota` (7.58 kB)
  - `/gestio/mapa` (5.41 kB)
  - `/gestio/clients` (4.08 kB)
  - `/gestio/magatzem` (4.3 kB)
  - `/gestio/comptabilitat` (5.33 kB)
  - `/superadmin/telemetria` (6.82 kB)
  - `/superadmin/tenants/onboarding` (9.72 kB)
  - Totes les rutes de `/operari/*`.

---

## 🧪 Proves d'Auditoria QA Executades

```bash
node pwa/test_configuracio_audit.mjs
python3 backend/run_tests.py
```
- **12/12 comprovacions aprovades**:
  - Selector de color camaleònic HSL amb ràtio de contrast WCAG 2.1 AA en viu (>4.5:1).
  - Paràmetres de jornada laboral (hores setmanals, marges de cortesia, tolerància geogràfica GPS).
  - Canvi en viu de logotip corporatiu i favicon del tenant.
  - RBAC amb permisos granulars per rol.
