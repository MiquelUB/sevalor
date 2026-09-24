# Pla d'Implementació: Plànols, Xarxes Tècniques i Caixetí Oficial PDF (/gestio/planols — Spec 010)

Aquest pla defineix la implementació integral del mòdul de **Plànols, Xarxes Tècniques i Arquitectura de Capes** (`/gestio/planols`) d'acord amb la **Spec 010**, la Constitució v4.0 de SEVALOR, la política de **Zero Mock Data**, el suport complet per a **Mode Clar i Mode Fosc**, la matriu híbrida de formats (CAD/GIS vs Documental), la immutabilitat de capes pericials d'obres tancades (Spec 007), la generació del **Caixetí Industrial Homologat PDF**, i la custòdia sobirana de fitxers sota Hetzner Alemanya.

---

## User Review Required

> [!IMPORTANT]
> **Immutabilitat i Traçabilitat Pericial de Capes Tancades (RF-12, RF-13 / EDGE-05)**:
> - Tota capa vectorial vinculada a una Ordre de Treball o incidència tècnica que hagi estat **tancada i facturada** (Spec 007) queda bloquejada com a **immutable (només lectura)**.
> - El sistema denega qualsevol intent d'edició, modificació de geometries o eliminació d'una capa immutable amb un error **HTTP 403 Forbidden** (*"Capa bloquejada per traçabilitat pericial d'obra tancada"*).
> - Si cal reflectir nous ajustos en camp a posteriori, l'Enginyer ha de superposar una **nova capa independent** associada a una nova ordre de treball, eliminant la sobreescriptura destructiva sobre el plànol base original (RF-09).

> [!WARNING]
> **Seguretat de Fitxers, Magic Bytes i Límit de Mida (RF-05 / EDGE-02)**:
> - Es rebutgen fitxers que superin el límit rígid de **50 MB** (`HTTP 413 Payload Too Large`).
> - S'analitzen de forma asíncrona els **Magic Bytes reals** (filetype) per detectar i avortar atòmicament qualsevol intent de pujada de fitxers executables o maliciosos camuflats amb extensions falses (`HTTP 415 Unsupported Media Type`).

> [!NOTE]
> **Caixetí Industrial Homologat PDF i Política de Codis QR (RF-25 / Constitució v4.0)**:
> - El PDF d'exportació tècnica oficial incorpora a la base un **caixetí industrial homologat** amb: logotip corporatiu, dades fiscals, dades del client i finca, escala gràfica de contrast, data d'emissió, llegenda de símbols utilitzats i autor de l'enginyeria.
> - De conformitat estricta amb la Constitució v4.0 de SEVALOR, el caixetí i els plànols d'obra estan **completament lliures de codis QR per a eines de treball** (les quals es custodien per número de referència/SN).

---

## Proposed Changes

### Base de Dades PostgreSQL (`db/migrations/011_planols_capes_caixeti.sql`)

#### [NEW] `db/migrations/011_planols_capes_caixeti.sql`
- Taula `carpetes_planols`:
  - `id UUID PRIMARY KEY`, `empresa_id UUID REFERENCES empreses(id)`, `nom VARCHAR(100)`, `categoria VARCHAR(30)` (`CLIENTS`, `INFRAESTRUCTURA_COMUNITARIA`, `MUNICIPAL_TERRITORIAL`), `client_id UUID REFERENCES clients(id)`, `municipi VARCHAR(100)`, `parent_id UUID REFERENCES carpetes_planols(id)`.
- Taula `planols_base`:
  - `id UUID PRIMARY KEY`, `empresa_id UUID REFERENCES empreses(id)`, `carpeta_id UUID REFERENCES carpetes_planols(id)`, `client_id UUID REFERENCES clients(id)`, `titol VARCHAR(150)`, `codi_referencia VARCHAR(50)`, `tipus_fitxer VARCHAR(20)` (`DXF`, `GEOJSON`, `KML`, `PDF`, `TIFF`, `PNG`, `JPG`), `es_georeferenciat BOOLEAN`, `fitxer_path VARCHAR(500)`, `mida_bytes BIGINT`, `bounds_wgs84 JSONB`, `projeccio_origen VARCHAR(30)`.
- Taula `capes_vectorials`:
  - `id UUID PRIMARY KEY`, `empresa_id UUID REFERENCES empreses(id)`, `planol_base_id UUID REFERENCES planols_base(id)`, `nom VARCHAR(100)`, `disciplina VARCHAR(30)` (`AIGUA_REG`, `ELECTRICITAT`, `OBRA_CIVIL`, `INCIDENCIA_PERICIAL`), `ordre_treball_id UUID REFERENCES ordres_treball(id)`, `es_immutable BOOLEAN DEFAULT false`, `color_hex VARCHAR(10)`, `gruix_linia INTEGER`, `opacitat_percent INTEGER DEFAULT 100`, `visible BOOLEAN DEFAULT true`, `geometries_geojson JSONB`, `version_id INTEGER DEFAULT 1` (control concurrència EDGE-01).
- Taula `pins_incidencia_planol`:
  - `id UUID PRIMARY KEY`, `empresa_id UUID REFERENCES empreses(id)`, `capa_id UUID REFERENCES capes_vectorials(id)`, `latitud NUMERIC(10, 7)`, `longitud NUMERIC(10, 7)`, `titol VARCHAR(150)`, `descripcio TEXT`, `simbol VARCHAR(50)`, `estat VARCHAR(20)`, `audio_nota_path VARCHAR(500)`, `foto_evidencia_path VARCHAR(500)`, `operari_id UUID REFERENCES usuaris(id)`.
- Taula `exportacions_pdf_planol`:
  - `id UUID PRIMARY KEY`, `empresa_id UUID REFERENCES empreses(id)`, `planol_base_id UUID REFERENCES planols_base(id)`, `titol_report VARCHAR(200)`, `client_id UUID REFERENCES clients(id)`, `capes_incloses_ids UUID[]`, `escala_grafica VARCHAR(30)`, `pdf_generat_path VARCHAR(500)`, `estat VARCHAR(20)`, `caixeti_dades JSONB`.
- Polítiques RLS forçades per a totes les noves taules.

---

### Backend Models & Router (`backend/app/models/models.py` i `backend/app/api/v1/gestio/planols.py`)

#### [MODIFY] `backend/app/models/models.py`
- Afegir classes SQLAlchemy `CarpetaPlanol`, `PlanolBase`, `CapaVectorial`, `PinIncidenciaPlanol`, `ExportacioPdfPlanol`.

#### [NEW] `backend/app/api/v1/gestio/planols.py`
- `GET /gestio/planols/carpetes`: llistat jeràrquic de carpetes agrupades per categoria amb RLS.
- `POST /gestio/planols/carpetes`: creació de carpeta (Enginyer/Boss; Secretaria 403 Forbidden).
- `GET /gestio/planols`: llistat de plànols base filtrables per carpeta, client, municipi o tipus de fitxer.
- `POST /gestio/planols/upload`: recepció de fitxer plànol amb verificació de Magic Bytes i mida <= 50MB (RF-05 / EDGE-02).
- `GET /gestio/planols/{id}`: recuperació de plànol base amb les seves capes vectorials i càlcul de capsa WGS84 (RF-06).
- `POST /gestio/planols/{id}/capes`: creació de nova capa vectorial per l'Enginyer.
- `PUT /gestio/planols/capes/{capa_id}`: edició de geometries vectorials; **si la capa és immutable per estar tancada, retorna HTTP 403 Forbidden** (RF-12, RF-13 / EDGE-05), amb comprovació de `version_id` (EDGE-01).
- `POST /gestio/planols/capes/{capa_id}/pins`: col·locació de PIN d'incidència amb foto WebP i nota de veu WebM (RF-20, RF-21).
- `POST /gestio/planols/{id}/exportar-pdf`: generació del PDF oficial d'alta resolució fusionant plànol i capes seleccionades amb caixetí homologat (RF-23, RF-25).
- `GET /gestio/planols/{id}/exportar-cad`: exportació directa de les capes en format estàndard GeoJSON / DXF (RF-26).

#### [MODIFY] `backend/app/main.py`
- Registrar `planols_router` sota `/api/v1`.

---

### Layout Desktop (`pwa/src/app/gestio/layout.tsx`)

#### [MODIFY] `pwa/src/app/gestio/layout.tsx`
- Afegir l'enllaç de navegació a la barra lateral:
  `{ label: "Plànols & Xarxes GIS", href: "/gestio/planols", icon: MapPin, badge: "CAD" }`
- Afegir plànols, xarxes de reg i caixetins al meta-cercador Spotlight (`Ctrl + K`).

---

### Pàgina Desktop de Plànols i Xarxes GIS (`pwa/src/app/gestio/planols/page.tsx`)

#### [NEW] `pwa/src/app/gestio/planols/page.tsx`
- **Arbre de Carpetes i Biblioteca Lateral (RF-01, RF-02, RF-03)**:
  - 3 categories principals: Clients, Infraestructures Comunitàries, Municipal / Territorial.
  - Cercador reactiu (<200 ms) per nom de plànol, client, municipi o ordre de treball.
- **Visor Cartogràfic & Documental Híbrid (RF-06, RF-07, RF-08)**:
  - Format Georeferenciat (WGS84): Canvas interactiu SVG amb xarxa de canonades (alimentador primari PE-100 Ø110, ramals secundaris Ø63), rases, polígons SIGPAC de sectorització, sensors IoT i ortofoto de contrast.
  - Format Esquema / Croquis No Georeferenciat: Visor documental Next.js per a esquemes unifilars i quadres elèctrics amb zoom i desplaçament fluid.
  - Control lliscant d'Opacitat (0% a 100%) sobre la cartografia.
- **Selector de Capes Flotant (RF-09 a RF-13)**:
  - Commutador de visibilitat (ull) i opacitat per a cada capa.
  - Indicador de capa activa de treball.
  - Insígnia de seguretat `IMMUTABLE (OBRA TANCADA)` per a capes consolidades pericialment (amb bloqueig d'edició).
- **Barra d'Eines d'Enginyeria i Delineació (RF-14, RF-15, RF-16, RF-17)**:
  - Eines de dibuix: Polilínia (canonades/rases), Polígon (sector), Cotes dimensionals i Anotacions de text ancorades inalterablement al traçat.
  - Simbologia normalitzada: Vàlvules de pas, Hidrants, Ventoses, Bombes d'impulsió, Comptadors, Quadres elèctrics, Arquetes.
  - Targeta desplegable de propietats tècniques en fer clic a un element.
  - Veto de Secretaria: accés de només lectura; eines d'edició gràfica desactivades.
- **Modal d'Exportació de Dossier Oficial PDF amb Caixetí Industrial (RF-23, RF-24, RF-25)**:
  - Selector de capes a incloure/excloure.
  - Vista prèvia del **Caixetí Industrial Homologat**: logotip SEVALOR, dades fiscals, client, escala gràfica, data, autor i llegenda tècnica de símbols (sense codis QR en eines segons la Constitució).
  - Botons de descàrrega de PDF i exportació CAD GeoJSON / DXF.
- **Zero Mock Data (Dia 0 Canònic)**:
  - Text buit canònic: *"No hi ha plànols ni carpetes registrats a la biblioteca tècnica"*.
- **Suport complet per a Mode Clar i Mode Fosc (`dark:`)**.

---

### Protocol de Proves i Auditoria QA (`pwa/test_planols_audit.mjs`)

#### [NEW] `pwa/test_planols_audit.mjs`
- Prova 1: Estructura de carpetes per categories i estat buit canònic Dia 0 (RF-01, RF-04 / Zero Mock Data).
- Prova 2: Validació estricta de Magic Bytes i rebuig de fitxers >50 MB (RF-05 / EDGE-02).
- Prova 3: Projecció georeferenciada WGS84 i reprojectació automàtica des de KML local ED50 (RF-06 / EDGE-04).
- Prova 4: Visor documental de Next.js per a esquemes unifilars elèctrics no georeferenciats (RF-07 / EDGE-08).
- Prova 5: Arquitectura de capes superposades no destructives sobre el plànol base (RF-09, RF-10).
- Prova 6: Bloqueig taxatiu (HTTP 403) d'edició de capes immutables d'obres tancades (RF-12, RF-13 / EDGE-05).
- Prova 7: Delineació vectorial de traçats i ancoratge inalterable de cotes tècniques (RF-14, RF-15).
- Prova 8: Simbologia tècnica normalitzada hidràulica i elèctrica amb targeta de propietats (RF-16, RF-17).
- Prova 9: Pins d'incidència de camp amb evidència d'àudio WebM i foto WebP (RF-20, RF-21).
- Prova 10: Caixetí Industrial Homologat d'exportació PDF exempt de QR en eines (RF-23, RF-25).

---

## Verification Plan

### Automated Tests
1. **Bateria Backend a Docker**:
   ```bash
   docker run --rm --network host -v /media/akaun/Project_1/SEVALOR/backend:/app -w /app campopro-backend:latest python run_tests.py
   ```
2. **Auditoria QA de Plànols GIS**:
   ```bash
   node pwa/test_planols_audit.mjs
   ```
3. **Bateria Global Frontend (Totes les 7 suites)**:
   ```bash
   node pwa/test_pwa_audit.mjs && node pwa/test_gestio_audit.mjs && node pwa/test_flota_audit.mjs && node pwa/test_superadmin_audit.mjs && node pwa/test_proveidors_audit.mjs && node pwa/test_operaris_audit.mjs && node pwa/test_planols_audit.mjs
   ```
4. **Compilació de Producció Next.js**:
   ```bash
   cd pwa && npm run build
   ```
