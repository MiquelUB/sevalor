# Walkthrough — Plànols, Xarxes Tècniques i Caixetí Oficial PDF (/gestio/planols — Spec 010)

Aquest document recull la implementació de la **Biblioteca de Plànols GIS, Delineació de Xarxes Tècniques i Generació de Caixetí Homologat PDF** d'acord amb la **Spec 010** de SEVALOR.

---

### I. Delineació de Plànols GIS & Caixetí Oficial PDF (`/gestio/planols` — Spec 010)
- **Biblioteca de Plànols Estructurada en 3 Categories RLS (RF-01 a RF-04)**:
  - *Clients i Parcel·les Privades* (`CLIENTS`).
  - *Infraestructures Comunitàries* (`INFRAESTRUCTURA_COMUNITARIA`).
  - *Municipal i Territorial* (`MUNICIPAL_TERRITORIAL`).
  - Cercador reactiu (<200 ms) i estat buit canònic Dia 0 (*Zero Mock Data*).
- **Matriu Híbrida de Formats & Seguretat (RF-05 a RF-08 / EDGE-02, EDGE-04)**:
  - Càrrega i registre de fitxers amb límit màxim de 50 MB (HTTP 413 davant fitxers superiors).
  - Validació de formats admesos (`.dxf`, `.dwg`, `.geojson`, `.kml`, `.pdf`, `.tiff`, `.png`) i rebuig d'executables (HTTP 415).
  - Formats georeferenciats projectats en WGS84 sobre ortofoto PNOA amb control d'opacitat del mapa base (0-100%).
  - Formats no georeferenciats (esquemes unifilars, manuals, TIFF) gestionats en visor documental vectorial d'alta resolució independent.
- **Arquitectura de Capes Vectorials & Immutabilitat Pericial (RF-09 a RF-13 / EDGE-05)**:
  - Edició no destructiva per capes amb control de visibilitat, color, gruix i opacitat.
  - **Bloqueig Pericial Estricte**: Quan una capa està associada a una Ordre de Treball tancada i facturada, queda marcada com a `IMMUTABLE`, rebutjant qualsevol intent de modificació amb HTTP 403 Forbidden (*"Capa bloquejada per traçabilitat pericial d'obra tancada"*).
  - **Concurrència Optimista (EDGE-01)**: Control de versionat atòmic amb `version_id`, retornant HTTP 409 Conflict davant col·lisions d'escriptura concurrent.
- **Delineació & Simbologia Normalitzada de Reg (RF-14 a RF-17)**:
  - Eines de delineació per a canonades PE-100 (polilínies), parcel·les SIGPAC (polígons) i cotes mètriques ancorades inalterablement.
  - Catàleg de símbols: hidràulica (vàlvules reguladores, hidrants d'alta pressió de 16 bar, ventoses trifuncionals, comptadors electromagnètics), obra civil (arquetes de formigó) i electricitat (quadres de bombament).
  - Pins d'incidència geolocalitzada amb suport per a fotos WebP i notes de veu WebM (RF-18, RF-20).
- **Caixetí Industrial Homologat PDF (RF-23, RF-25)**:
  - Generador de dossier oficial PDF amb caixetí segons norma UNE-EN ISO 5457 (logotip SEVALOR, títol d'obra, client, escala gràfica normalitzada 1:250 / 1:500 / 1:1000 / 1:2000, data, autor enginyer col·legiat, advertiment legal de propietat intel·lectual i llegenda de símbols).
  - **EXCLUSIÓ TOTAL DE CODIS QR D'EINES**: Compliment estricte de la Constitució v4.0 (les eines de treball no porten codi QR).
  - Exportació CAD GeoJSON WGS84 per a maquinària agrícola i d'obra civil (RF-26).
- **Veto de Secretaria (RF-10, RF-11)**:
  - Accés exclusiu de consulta i descàrrega documental.
  - Veto absolut (HTTP 403) a la creació de carpetes, pujada de plànols i delineació o alteració de capes CAD/GIS.
- **Sobirania de Dades**:
  - Emmagatzematge sobirà a servidors Hetzner Alemanya (`/docs/<empresa_id>/planols/`), amb zero dependències d'AWS S3.

---

## 3. Bateria de Proves i Auditoria de Qualitat

S'han executat les suites completes d'inspecció automatitzada:

### A. Proves de Delineació de Plànols GIS & Caixetí (`test_planols_audit.mjs` — Spec 010)
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

### B. Proves de Gestió d'Operaris i Control Horari (`test_operaris_audit.mjs` — Spec 008)
- **10/10 proves superades en verd**.

### C. Proves de Proveïdors, CAE i Frau BEC (`test_proveidors_audit.mjs` — Spec 003)
- **10/10 proves superades en verd**.

### D. Proves de Flota i ITV (`test_flota_audit.mjs` — Spec 006)
- **10/10 proves superades en verd**.

### E. Proves Superadmin Telemetria (`test_superadmin_audit.mjs` — Spec 022)
- **12/12 proves superades en verd**.

### F. Proves de Gestió Desktop (`test_gestio_audit.mjs` — Specs 001 a 007)
- **10/10 proves superades en verd**.

### G. Proves PWA de Camp (`test_pwa_audit.mjs` — Specs 013 a 020)
- **14/14 proves superades en verd**.

### H. Proves Backend de Regressió Docker (`backend/run_tests.py`)
- **48/48 proves d'integració en verd** a Docker:
  - 7 nous tests d'Spec 010 (carpetes, límits 50MB, veto secretaria, immutabilitat, concurrència, caixetí sense QR d'eines, CAD GeoJSON).
  - Tests d'Spec 008, control horari, RLS, SIF, operari auth i telemetria.

### I. Compilació de Producció Next.js (`npm run build`)
- **23/23 pàgines estàtiques generades amb èxit** a Next.js 14:
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
node pwa/test_planols_audit.mjs
```
- **10/10 comprovacions aprovades**:
  - Selector de categories RLS (Clients, Infraestructura Comunitària, Municipal).
  - Visor Leaflet/PostGIS amb capes vectorials (canonades, aspersors, electrovàlvules, hidrants).
  - Caixetí Oficial PDF generat al servidor amb segell de sobirania Hetzner i hash d'integritat SHA-256.
  - Bloqueig pericial per a obres tancades i facturades.
