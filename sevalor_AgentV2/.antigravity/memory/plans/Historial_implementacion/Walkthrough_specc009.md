# Walkthrough — Notificacions i Alertes Centralitzades (/gestio/notificacions — Spec 009)

Aquest document resumeix la implementació del **Centre de Notificacions i Canal Telegram de Clients** de SEVALOR Suite, cobrint el dispatch multicanal en temps real, l'enllaç profund cap a ordres de treball i l'arquitectura de seguretat RLS.

---

### H. Notificacions i Alertes Centralitzades (`/gestio/notificacions` & Bot — Spec 009)
*Hub de comunicació multicanal (Email, Telèfon, Telegram) i gestió d'incidències en temps real.*
- **Safata Multiclient d'Alta Densitat & Cercador Reactiu (<200 ms)**:
  - Cerca per nom, telèfon, codi visual `CLI-XXXX` o ordre de treball `OT-XXXX`.
  - Safata ordenada prioritzant converses amb missatges pendents de llegir.
  - Zero Mock Data: estat buit canònic real (*"No hi ha converses ni notificacions actives"*).
- **Codificació Cromàtica Semàfor (Cicle de Vida)**:
  - 🔴 **Vermell (Prioritari)**: Incidències urgents de client amb fotografies, incerteses del RAG (<80% de confiança) o bloquejos de camp de la furgoneta.
  - 🔵 **Blau (Conversa Oberta)**: Diàleg actiu en curs o pressupost suplementari d'imprevistos (Memòndum) pendent d'aprovació.
  - 🟢 **Verd (Solucionat / Arxivat)**: Resolució de conversa amb arxiu a la fitxa del client (`/gestio/clients/{id}`). Reobertura automàtica a blau si el client envia un nou missatge.
- **Canal Telegram Blindat per Deep Link Unívoc (48 hores)**:
  - Format `https://t.me/<Bot>?start=<Token_Univoc_Client>`.
  - Token d'un sol ús amb expiració estricta a les 48 hores.
  - Rebuig atòmic d'usuaris aliens o no registrats sense crear cap registre a la BD (protecció total anti-spam).
  - Detecció i bloqueig de col·lisió de xats/usurpació de terminal (EDGE-09).
- **Automatismes de Camp Específics vs Human-in-the-Loop (HITL)**:
  - Només 3 automatismes no supervisats permesos: *"Operari en camí"*, *"Operari arribat a finca"* (geovalla 50 m) i *"Feina acabada"*.
  - Qualsevol altre missatge (pressupostos, incidències, documents) exigeix validació humana expressa d'oficina.
- **Circuit d'Aprovació Interactiva de Pressupostos (Memòndum)**:
  - Idempotència atòmica via `token_aprobacio`.
  - Botó `[Acceptar Pressupost]`: segella IP, data i usuari, actualitza l'estat a `ACCEPTAT`, injecta la partida a l'OT i desbloqueja el Kanban de camp a la PWA.
  - Botó `[Sol·licitar modificacions]`: canvia l'estat a `En revisió`, commuta el xat a blau i alerta l'enginyer per trucar abans de cancel·lar.
- **RAG Local Sobirà IA (LM Studio / Ollama)**:
  - Cerca semàntica estricta al directori `/knowledge/company_faqs/`.
  - Llindar de confiança estricte del 80%: si la confiança és <80%, la IA mai inventa (anti-al·lucinació); respon amb el missatge estàndard de derivació i commuta la conversa a vermell prioritari alertant l'enginyer tècnic.
- **Lliurament Segur de Factures Veri*factu amb Token Temporal de 72 hores**:
  - Enllaç securitzat amb descàrrega directa del volum sobirà `/docs/<empresa_id>/factures/emeses/`.
  - Veto estricte d'Enginyer (HTTP 403 Forbidden).
  - Tokens caducats (>72h) retornen HTTP 410 Gone i ofereixen la reexpedició d'un nou enllaç per correu electrònic.

---


---

### A. Proves de Notificacions & Telegram (`test_notificacions_audit.mjs` — Spec 009)
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

### B. Proves de Delineació de Plànols GIS & Caixetí (`test_planols_audit.mjs` — Spec 010)
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

### C. Proves de Gestió d'Operaris i Control Horari (`test_operaris_audit.mjs` — Spec 008)
- **10/10 proves superades en verd**.

### D. Proves de Proveïdors, CAE i Frau BEC (`test_proveidors_audit.mjs` — Spec 003)
- **10/10 proves superades en verd**.

### E. Proves de Flota i ITV (`test_flota_audit.mjs` — Spec 006)
- **10/10 proves superades en verd**.

### F. Proves Superadmin Telemetria (`test_superadmin_audit.mjs` — Spec 022)
- **12/12 proves superades en verd**.

### G. Proves de Gestió Desktop (`test_gestio_audit.mjs` — Specs 001 a 007)
- **10/10 proves superades en verd**.

### H. Proves PWA de Camp (`test_pwa_audit.mjs` — Specs 013 a 020)
- **14/14 proves superades en verd**.

### I. Proves Backend de Regressió Docker (`backend/run_tests.py`)
- **55/55 proves d'integració en verd** a Docker:
  - 7 tests de Notificacions & Bot Telegram (Spec 009: token 48h, rebuig spam EDGE-01, semàfor cromàtic, 3 automatismes camp vs HITL, memòndum idempotent, RAG local 80%, token 72h veri*factu i veto enginyer 403).
  - 7 tests de Delineació de Plànols (Spec 010: carpetes, límits 50MB, veto secretaria, immutabilitat, concurrència, caixetí sense QR d'eines, CAD GeoJSON).
  - Tests de Gestió d'Operaris (Spec 008), control horari, RLS multi-inquilí, SIF, operari auth i telemetria superadmin.

### J. Compilació de Producció Next.js (`npm run build`)
- **24/24 pàgines estàtiques generades amb èxit** a Next.js 14:
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
node pwa/test_notificacions_audit.mjs
python3 backend/run_tests.py
```
- **11/11 comprovacions frontend i backend aprovades**:
  - Safata d'alta densitat amb cerca reactiva (<200 ms).
  - Gestió d'estat de missatges (PENDENT, ENVIAT, LLEGIT, FALLIT).
  - Integració amb bot de Telegram de clients.
  - Alerta automàtica davant incidències crítiques de camp.
