# SEVALOR — Walkthrough d'Implementació de la Suite Desktop (/gestio)

Aquest document resumeix la importació, adaptació estricta i contrast de les pantalles d'escriptori del projecte Stitch cap a la Central d'Oficina Tècnica i Gestió Desktop (`/gestio`), complint les **Specs 001 a 007**, la Constitució v4.0 de SEVALOR, suport complet per a **Mode Clar i Fosc**, i verificació amb bateries de proves automatitzades.

---

## 1. Components Implementats a `/gestio`

### A. Capçalera d'Alta Densitat, Spotlight i Gestió de Rols (`layout.tsx`)
- **Spotlight Meta-Search (`Ctrl + K`)**: Meta-cercador reactiu amb temps de resposta inferior a 200 ms per indexar ordres de treball, clients, parcel·les i referències de magatzem.
- **Selector de Rol Actiu**: Permet commutar entre `Boss`, `Enginyer` i `Secretaria` per auditar i validar els permisos d'accés en temps real.
- **Veto d'Enginyer (Spec 001 RF-03 / Spec 007 RF-05)**: Ocultació automàtica d'elements financers a la cerca Spotlight i bloqueig absolut d'accés a comptabilitat.
- **Commutador de Mode Clar / Fosc**: Sincronitzat mitjançant `localStorage` i classes `.dark` de Tailwind CSS.
- **Telemetria RTK FIX**: Indicador de precisió centimètrica (0.02m WGS84).

---

### B. Torre de Control GIS & Cockpit Únic (`/gestio/mapa`)
*Basada en Stitch Screen `4f49a04952b141d2b8416bc46b280403` i Specs 001/005.*
- **Capa Cartogràfica Tàctica SVG**:
  - Xarxa de canonades PE-100 PN16 (alimentador primari, ramal secundari i tram en incidència per sobrepressió).
  - Polígon parcel·lari SIGPAC d'obra (Finca Els Arcs).
  - Marcador en directe de la **Colla 01** (Jordi Soler • En Obra) i sensors de pressió IoT (P-04 a 14.2 bar, P-07 a 2.1 bar amb alerta acústica/visual).
- **HUD Superior**: Selectors de manera de visualització (*Satèl·lit 2D*, *Topogràfic 3D*, *Cadastre*) i commutadors de capes (*SIGPAC*, *Canonades PE*, *Sensors IoT*, *Colles*).
- **Drawer d'Inspecció Tècnica Lateral**: Fitxa completa de l'actuació (coordenades WGS84 decimals, codi candat `4826-B`, telemetria IoT). Sota el rol `Enginyer`, s'oculten estrictament els marges de benefici i pressupostos.
- **Zero Mock Data**: Estat buit canònic: *"No hi ha intervencions actives sobre el mapa"*.

---

### C. Portal de Clients i Finques (`/gestio/clients`)
*Basada en Stitch Screen `4f8ba28a47ae413691f78f5458610c94` i Spec 002.*
- **Directori de Clients**: Codificació canònica `CLI-XXXX`, dades fiscals, NIF complet i canal Telegram de clients.
- **Dades Bancàries Segures**: Xifratge simètric AES-256 amb visualització emmascarada de l'IBAN (`ES82 •••• •••• •••• 4819`).
- **Inspecció de Finques**: Coordenades GPS en brut (WGS84) i claus de candats rústics.
- **Zero Mock Data**: Estat buit canònic: *"No hi ha clients registrats al directori"*.

---

### D. Magatzem Central & Inventari Industrial (`/gestio/magatzem`)
*Basada en Stitch Screen `cec82abe4bcc4391a374e57d34f53f8b` i Spec 004.*
- **Inventari Multilocació**: Taula comparativa de l'estoc físic a la Nau Central vs Furgonetes Taller (Vehicle 7482-LDK).
- **Format Continu i Retalls**: Comptabilització de retalls aprofitables (m) per evitar talls innecessaris de barres de 6 metres.
- **Reserva Pesimista**: Càlcul atòmic de $\text{Disponible Net} = \text{Estoc Físic} - \text{Estoc Reservat en OTs}$.
- **Zero Mock Data**: Estat buit canònic: *"Magatzem central sense moviments d'estoc"*.

---

### E. Comptabilitat, Tresoreria & Veri*factu (`/gestio/comptabilitat`)
*Basada en Stitch Screen `dbf509d1ecc54f25b637628958c2f1b3` i Spec 007.*
- **Veto d'Enginyer Actiu**: Quan el rol és `ENGINYER`, renderitza estrictament la pantalla canònica: **"HTTP 403 Forbidden — Veto d'Enginyer a Dades Financeres"**.
- **Facturació Veri\*factu Oficial**: Taula de factures emeses amb generació de codi QR reglamentari de l'AEAT i empremta de segellat SHA-256 encadenat.
- **Outbox Pattern Asíncron (Spec 024)**: Monitorització de l'estat d'enviament a la seu electrònica de l'AEAT (`ENVIAT_SOAP` / `PENDENT`).
- **Triple Conciliació (Three-Way Matching)**: Verificació matemàtica d'Albarà $\times$ Comanda $\times$ Factura (0% desviació $\rightarrow$ `CONCILIADA`).
- **Banc Norma 43**: Panell d'ingesta desduplicada per hash SHA-256 dels fitxers d'extracte bancari.
- **Zero Mock Data**: Estat buit canònic: *"No hi ha factures pendents ni emeses"*.

---

## 2. Bateria de Proves i Auditoria de Qualitat

S'han executat les suites completes d'inspecció automatitzada:

### A. Proves de Gestió Desktop (`test_gestio_audit.mjs`)
- **10/10 proves superades en verd**:
  - Veto d'Enginyer (HTTP 403 a comptabilitat i exclusió financera a Spotlight).
  - Rendiment Spotlight (<200 ms per a dataset de 5.000 registres).
  - Textos canònics Zero-Mock Data per a totes les pantalles de gestió.
  - Triple Conciliació i reserves pesimistes de magatzem.

### B. Proves PWA de Camp (`test_pwa_audit.mjs` + `test_crypto.mjs`)
- **14/14 proves superades en verd** (Specs 013 a 020).
- Desxifratge Web Crypto API `SEVALOR_SENTINEL` en 31 ms.

### C. Proves Backend de Regressió (`backend/run_tests.py`)
- **31/31 proves d'integració en verd** a Docker (RLS Multi-tenant, Veri*factu SIF, Outbox AEAT, Telegram anti-malware, Whisper INT8).

### D. Compilació de Producció Next.js (`npm run build`)
- **18/18 pàgines estàtiques generades amb èxit** a Next.js 14:
  - `/gestio/mapa`
  - `/gestio/clients`
  - `/gestio/magatzem`
  - `/gestio/comptabilitat`
  - Totes les rutes `/operari/*` i `/superadmin/*`.
