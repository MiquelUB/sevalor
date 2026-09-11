# Pla d'Implementació: Central d'Oficina Tècnica i Gestió Desktop (/gestio)

Aquest pla estableix la importació, adaptació estricta i contrast de les pantalles d'escriptori del projecte Stitch (`11736019592508996999`) cap a la suite **SEVALOR**, governat per la Constitució v4.0, les especificacions tècniques (**Specs 001, 002, 004, 005 i 007**), el suport complet per a **Mode Clar i Mode Fosc**, el compliment innegociable de **Zero Mock Data** i el principi de sobirania de dades Hetzner.

---

## User Review Required

> [!IMPORTANT]
> **Veto d'Enginyer (Specs 001, 002 i 007)**: La interfície de gestió incorpora un selector de rol actiu (Boss, Enginyer, Secretaria). Quan el rol actiu sigui **Enginyer**, qualsevol intent d'accedir a `/gestio/comptabilitat` o visualitzar mètriques financeres a la Torre de Control serà bloquejat de forma estricta amb una pantalla canònica d'error **HTTP 403 Forbidden** (amb DTO desacoblat).

> [!NOTE]
> **Alineació de Marques i Proveïdors Cloud**: Totes les mencions a "CampoPro" s'actualitzen a **SEVALOR**. Es descarten completament serveis privatius externs (AWS S3, Wasabi, Google Maps privatiu); la cartografia opera amb vectors SVG tàctics sobre ortofoto PNOA/Dusk i el disc sobirà Hetzner a Falkenstein (Alemanya).

---

## Proposed Changes

### Component 1: Layout d'Oficina i Spotlight Meta-Search (`/gestio/layout.tsx`)

#### [NEW] `pwa/src/app/gestio/layout.tsx`
- **Capçalera Superior d'Alta Densitat**:
  - Logo SEVALOR GIS i subtítol industrial.
  - Indicador de telemetria RTK FIX (0.02m / WGS84).
  - Selector de Rol actiu (Boss / Enginyer / Secretaria) per a validar els permisos RLS i el Veto 403 en temps real.
  - Commutador de Mode Clar / Mode Fosc (`localStorage` + classe `.dark`).
  - Botó ràpid de cerca **Spotlight Meta-Search** (`Ctrl + K`) amb temps de resposta <200ms.
- **Barra Lateral de Navegació (Sidebar Desktop)**:
  - `Torre de Control GIS` (`/gestio/mapa`)
  - `Clients i Finques` (`/gestio/clients`)
  - `Magatzem & Inventari` (`/gestio/magatzem`)
  - `Flota & Vehicles` (`/gestio/flota`)
  - `Comptabilitat & Veri*factu` (`/gestio/comptabilitat`)
  - Indicador d'Organització amb CIF i dades del tenant.

---

### Component 2: Torre de Control GIS & Cockpit Únic (`/gestio/mapa`)
*Contrast amb Stitch `4f49a04952b141d2b8416bc46b280403` i Specs 001 / 005.*

#### [NEW] `pwa/src/app/gestio/mapa/page.tsx`
- **Visor Cartogràfic Tàctic GIS**:
  - Capa base d'ortofoto Dusk satel·lital.
  - Vectors SVG tàctics d'alta precisió: Xarxa de canonades PE-100 PN16, polígons SIGPAC de parcel·les d'obra.
  - Tickers HUD superiors: Sector hidràulic, RTK fix, conmutadors de capes (SIGPAC, Canonades PE, Sensors IoT, Colles de Camp).
  - Selector de manera de visualització: Satèl·lit 2D, Topogràfic 3D, Cadastre.
- **Drawer Lateral d'Inspecció Tècnica**:
  - Detall d'actius i colles de camp en directe (coordenades decimals WGS84, cap de colla, estat de feina).
  - Telemetria de pressió de xarxa (sensors IoT) i registre d'incidències de camp en temps real.
  - **Zero Mock Data Empty State**: Botó per a netejar o carregar les intervencions actives.
  - **Veto d'Enginyer**: Absència total de marges de benefici, preus/hora de treballadors o dades de facturació.

---

### Component 3: Portal de Clients i Finques (`/gestio/clients`)
*Contrast amb Stitch `4f8ba28a47ae413691f78f5458610c94` i Spec 002.*

#### [NEW] `pwa/src/app/gestio/clients/page.tsx`
- **Directori Mestre de Clients**:
  - Codificació formal `CLI-XXXX`, dades fiscals, NIF complet i canal Telegram de clients (vinculat/desvinculat).
  - Dades bancàries xifrades simètricament (IBAN AES-256).
- **Inspecció de Finques i Accessos**:
  - Coordenades GPS en brut (WGS84 decimals).
  - Custòdia segura de codis de cadenats i claus de finques rústiques.
- **Zero Mock Data Empty State**: Text canònic: *"No hi ha clients registrats al directori"*.

---

### Component 4: Magatzem Central & Inventari Industrial (`/gestio/magatzem`)
*Contrast amb Stitch `cec82abe4bcc4391a374e57d34f53f8b` i Spec 004.*

#### [NEW] `pwa/src/app/gestio/magatzem/page.tsx`
- **Inventari Multilocació**:
  - Taula comparativa de stock físic a la Nau Central vs Furgonetes Taller mòbils.
  - Gestió de materials de format continu: Detecció de retalls parcials vs bobines/barres de 6 metres senceres.
  - Reserves pesimistes de stock per a ordres de treball programades.
- **Zero Mock Data Empty State**: Text canònic: *"Magatzem central sense moviments d'estoc"*.

---

### Component 5: Comptabilitat, Tresoreria & Veri*factu (`/gestio/comptabilitat`)
*Contrast amb Stitch `dbf509d1ecc54f25b637628958c2f1b3` i Spec 007.*

#### [NEW] `pwa/src/app/gestio/comptabilitat/page.tsx`
- **Facturació Veri\*factu & Outbox SOAP**:
  - Llistat de factures oficials emeses amb codi QR Veri*factu i petjada SHA-256.
  - Monitor de l'Outbox Pattern per a enviaments a la seu electrònica de l'AEAT (PENDENT / ENVIAT / REBUTJAT).
- **Triple Conciliació (Three-Way Matching)**:
  - Conciliació automàtica: Albarà de Proveïdor $\times$ Comanda de Compra $\times$ Factura.
- **Veto d'Enginyer Actiu**:
  - Si l'usuari té el rol `ENGINYER`, la pàgina renderitza directament la pantalla d'accés denegat: **"HTTP 403 Forbidden — Veto d'Enginyer a Dades Financeres (Spec 001 RF-03 / Spec 007 RF-05)"**.
- **Zero Mock Data Empty State**: Text canònic: *"No hi ha factures pendents ni emeses"*.

---

## Verification Plan

### Automated Tests
1. **Compilació Next.js**:
   - `npm run build` a `pwa/` per verificar que les noves rutes `/gestio/mapa`, `/gestio/clients`, `/gestio/magatzem` i `/gestio/comptabilitat` compilen a 100% amb tipatge TypeScript net.
2. **Suite de Proves d'Integració Desktop (`test_gestio_audit.mjs`)**:
   - Validació del Veto d'Enginyer (HTTP 403 davant accés de comptabilitat).
   - Validació de Zero Mock Data als Empty States d'oficina.
   - Validació del Spotlight Meta-Search (<200ms de filtrat).
   - Validació de la fórmula de Triple Conciliació.
3. **Banc de Proves Backend Docker**:
   - `docker run --rm -v ... backend:/app python run_tests.py` mantenint 31/31 tests verds.

### Manual Verification
- Comprovació visual a l'aplicació web del canvi de Mode Clar a Mode Fosc mitjançant el selector de la capçalera.
- Comprovació del canvi de rol d'usuari a la capçalera (Boss vs Enginyer) i verificació del bloqueig de seguretat 403 a `/gestio/comptabilitat`.
