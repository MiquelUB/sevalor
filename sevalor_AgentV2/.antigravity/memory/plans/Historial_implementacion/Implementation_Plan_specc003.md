# Pla d'Implementació: Proveïdors, CAE i Prevenció de Frau BEC (/gestio/proveidors — Spec 003)

Aquest pla defineix la implementació del mòdul de **Gestió de Proveïdors, Subcontractes i CAE** (`/gestio/proveidors`) d'acord amb la **Spec 003**, la Constitució v4.0 de SEVALOR, la política de **Zero Mock Data**, el suport complet per a **Mode Clar i Mode Fosc**, i les mesures de seguretat bancària i laboral (RD 171/2004).

---

## User Review Required

> [!IMPORTANT]
> **Prevenció de Frau BEC (Business Email Compromise) / Bloqueig Antifrau per Canvi d'IBAN (Spec 003 RF-09 / EDGE-01)**:
> - Quan el sistema detecta un canvi en l'IBAN d'un proveïdor (per lectura OCR de factura o edició administrativa):
>   1. El proveïdor queda en estat `BLOQUEIG_ANTIFRAU_IBAN`.
>   2. Es bloquegen de forma automàtica i atòmica totes les transferències, remeses i ordres de pagament cap a aquest compte.
>   3. S'aixeca una **Alerta Vermella de Seguretat** visible per a Gerència i Secretaria.
>   4. El desbloqueig requereix de forma obligatòria la confirmació protocol·lària de seguretat (trucada de contrast telefònic a número acreditat) i l'autorització expressa del **Boss**.
>   5. Es registra un esdeveniment inalterable al SIF (`registre_esdeveniments_sif`, Spec 007) amb hash SHA-256 encadenat que documenta l'IBAN vell, l'IBAN nou, l'usuari autoritzant i la marca temporal de l'auditoria.

> [!WARNING]
> **Control Documental CAE i Assegurances de Subcontractes (RD 171/2004 — RF-12 a RF-14 / EDGE-03)**:
> - Totes les subcontractes han de disposar de la Pòlissa de Responsabilitat Civil (RC) i certificats CAE/PRL en vigor.
> - El sistema manté una cadena preventiva d'alertes a 30, 15, 5 i 1 dia abans de la data de caducitat.
> - Si la documentació està caducada, el sistema **bloqueja taxativament** l'assignació de la subcontracta a cap obra o ordre de treball a la Torre de Control GIS, i suggereix de forma automàtica subcontractes alternatives en regla del mateix sector.

> [!NOTE]
> **Veto d'Enginyer (RF-16, RF-17 / EDGE-02)**:
> - Els usuaris amb rol `ENGINYER` només poden consultar la informació operativa i d'especialitat tècnica. L'IBAN complet, les dades bancàries i els imports o volums de compra agregats retornen estrictament HTTP 403 Forbidden a nivell d'API i es mostren ofuscats (`•••• •••• •••• •••• 4819`) a la interfície.

---

## Proposed Changes

### Backend FastAPI (`backend/app/api/v1/gestio/proveidors.py`)

#### [MODIFY] `backend/app/api/v1/gestio/proveidors.py`
- Afegir endpoint `GET /gestio/proveidors`: llistat de proveïdors del tenant amb estat documental CAE i estat antifrau de l'IBAN. Si el rol és `ENGINYER`, l'IBAN es purga i només es retornen els últims 4 dígits emmascarats.
- Afegir endpoint `POST /gestio/proveidors`: alta manual amb generació de codi correlatiu `PRV-XXXX` i comprovació estricta d'unicitat de NIF/CIF (RF-05).
- Afegir endpoint `POST /gestio/proveidors/canvi-iban`: detecció de variació d'IBAN que activa immediatament l'estat `BLOQUEIG_ANTIFRAU_IBAN` i genera l'esdeveniment d'alerta al SIF.
- Afegir endpoint `POST /gestio/proveidors/autoritzar-canvi-iban`: reservat exclusivament al rol `BOSS` per autoritzar el nou compte bancari després de verificació telefònica protocol·lària, amb registre formal al SIF.
- Afegir endpoint `GET /gestio/proveidors/{id}/documents-cae` i `POST /gestio/proveidors/{id}/documents-cae` per a la gestió de pòlisses RC i certificats laborals sota Hetzner sobirà.
- Afegir endpoint `GET /gestio/proveidors/subcontractes-alternatives` per trobar subcontractes homologades si una està bloquejada per CAE caducat.
- Mantenir intacte `POST /gestio/proveidors/conciliar` (Triple Conciliació de l'Spec 003 / Bloc 4).

---

### Layout Desktop (`pwa/src/app/gestio/layout.tsx`)

#### [MODIFY] `pwa/src/app/gestio/layout.tsx`
- Afegir l'enllaç de navegació a la barra lateral (Sidebar):
  `{ label: "Proveïdors & CAE", href: "/gestio/proveidors", icon: Factory, badge: "PRV" }`
- Afegir referències de proveïdors a l'índex del meta-cercador Spotlight (`Ctrl + K`).

---

### Pàgina Principal de Proveïdors (`pwa/src/app/gestio/proveidors/page.tsx`)

#### [NEW] `pwa/src/app/gestio/proveidors/page.tsx`
- **Taula General d'Alta Densitat de Proveïdors**:
  - Codi `PRV-XXXX` i Raó Social.
  - NIF / CIF i indicadors tributaris (`RECC`, `ISP`).
  - Especialitat tècnica (Materials, Maquinària d'Obra, Subcontracta de Serveis).
  - Estat Documental CAE & Pòlissa RC (amb comptador de dies restants i alertes 30-15-5-1 dies).
  - Dades Bancàries & Estat Antifrau BEC (amb badge vermell `BLOQUEIG ANTIFRAU` si hi ha un canvi d'IBAN no autoritzat).
  - Estat d'activitat i botons d'acció ràpida.
- **Modal d'Alerta Vermella de Frau BEC i Autorització Boss**:
  - Contrast visual d'IBAN anterior vs nou.
  - Protocol de verificació telefònica obligatòria.
  - Botó d'autorització i signatura digital del Boss amb segellat SIF.
  - Veto actiu: si l'usuari és `ENGINYER`, aquestes accions estan estrictament bloquejades.
- **Modal de Gestió Documental CAE / RC (RD 171/2004)**:
  - Pujada de pòlissa RC en vigor i certificats CAE.
  - Alerta de bloqueig d'assignació d'obra si la documentació està caducada.
  - Panell de subcontractes alternatives homologades.
- **Modal d'Alta Manual de Proveïdor**:
  - Codi correlatiu automàtic, dades fiscals, RECC, ISP i especialitat.
- **Zero Mock Data (Dia 0 Canònic)**:
  - Si no hi ha proveïdors: *"No hi ha proveïdors registrats al directori"*, cercador deshabilitat i botó d'alta.
- **Suport complet per a Mode Clar i Mode Fosc (`dark:`)**.

---

### Protocols de Proves i Auditoria QA

#### [NEW] `pwa/test_proveidors_audit.mjs`
- Prova 1: Bloqueig atòmic per canvi d'IBAN (frau BEC) i alerta vermella de seguretat (RF-09 / EDGE-01).
- Prova 2: Autorització exclusiva de canvi d'IBAN per a rol Boss amb registre inalterable al SIF.
- Prova 3: Veto d'Enginyer (IBAN ofuscat i HTTP 403 en operacions financeres).
- Prova 4: Caducitat documental CAE / RC (RD 171/2004) i bloqueig taxatiu d'assignació a obra (RF-12, RF-13).
- Prova 5: Suggeriment automàtic de subcontractes alternatives en regla del mateix sector (RF-14).
- Prova 6: Retenció paramètrica del 60% per salvaguarda de bona execució (RF-15).
- Prova 7: Triple Conciliació (Three-Way Matching) amb tolerància $\pm2\%$ en granel continu (RF-24, RF-24.1).
- Prova 8: Unicitat estricta de CIF/NIF a l'alta manual (RF-05).
- Prova 9: Dret de supressió de proveïdors autònoms amb bloqueig legal LOPDGDD / SIF (RF-28).
- Prova 10: Zero Mock Data: estat buit canònic de Dia 0 (RF-03).

---

## Verification Plan

### Automated Tests
1. **Bateria Backend a Docker**:
   ```bash
   docker run --rm --network host -v /media/akaun/Project_1/SEVALOR/backend:/app -w /app campopro-backend:latest python run_tests.py
   ```
2. **Auditoria QA de Proveïdors**:
   ```bash
   node pwa/test_proveidors_audit.mjs
   ```
3. **Bateries Globals Frontend QA**:
   ```bash
   node pwa/test_pwa_audit.mjs && node pwa/test_gestio_audit.mjs && node pwa/test_flota_audit.mjs && node pwa/test_superadmin_audit.mjs
   ```
4. **Compilació Next.js**:
   ```bash
   cd pwa && npm run build
   ```
