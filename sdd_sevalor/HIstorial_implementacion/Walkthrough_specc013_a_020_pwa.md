# SEVALOR — Matriu d'Auditoria i Contrast QA de la PWA (/operari)

Aquest document detalla el contrast rigorós de totes les pantalles de la PWA mòbil de camp contra les especificacions tècniques (**Specs 013 a 020**), la Constitució v4.0 de SEVALOR, el suport complet per a **Mode Clar i Mode Fosc**, el compliment innegociable de **Zero Mock Data** i els protocols d'auditoria automatitzats.

---

## 1. Taula de Contrast 1:1 de Pantalles PWA vs Especificacions

| Ruta PWA | Especificació Vinculada | Funcionalitats Clau Contrasted | Estat Zero-Mock | Suport Clar/Fosc | Estat QA |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `/operari/login` | **Spec 019** (Login PIN & Seguretat) | Numpad tàctil gran format, auto-submit al 4t dígit, Web Crypto API (PBKDF2 100k it. + AES-GCM-256 `SEVALOR_SENTINEL`), circuit SMS oblit de PIN. | Dia 0 real / OTP | Implementat (`dark:`, botó de canvi) | **VALIDAT (100%)** |
| `/operari/feines` | **Spec 013** (Feines i Ordres de Treball) | Capçalera de jornada, "Iniciar Trajecte" (transició Blau + avís ETA), Geovalla 50m ("Inici per Desviació"), botó SOS i campana d'avisos acústica. | *"No hi ha feines assignades per a avui"* | Implementat (`dark:bg-slate-950`, targetes adaptades) | **VALIDAT (100%)** |
| `/operari/material` | **Spec 014** (Picking, Balanç i Mermes) | Pick In matinal (bloqueig sense 100% check o desquadrament a nau), consolidació d'eines (1 sola per jornada), Pick Out ($\text{Consum} = \text{In} - \text{Out}$), restricció tall format continu, "Afegir de furgoneta" sense QR. | *"Aquesta tasca no té materials ni eines programades"* | Implementat (`dark:`, badges d'eina i estats) | **VALIDAT (100%)** |
| `/operari/vehicles` | **Spec 015** (Flota, Carburant i Estoc) | Check-in matinal (foto odòmetre per càmera + selector buit/1/4/1/2/3/4/ple + horòmetre màquina), registre carburant amb **doble foto obligatòria** (tiquet + odòmetre en viu), estoc furgoneta reactiu amb indicador de "Material Faltant", Check-out amb càlcul idempotent ($\text{Km Nets} = \text{Final} - \text{Inicial}$). | *"No tens cap vehicle ni remolc assignat per a avui"* | Implementat (`dark:`, tabs adaptats, indicadors) | **VALIDAT (100%)** |
| `/operari/incidencies`| **Spec 016** (Bústia i Contingències) | Botó directe **SOS EMERGÈNCIA (112)**, formulari multimodal flexible (vàlid amb 1 sol canal: àudio Whisper, foto en viu o text), derivació síncrona a Torre de Control. | Cua buida Dia 0 | Implementat (`dark:`, alerta contrastada) | **VALIDAT (100%)** |
| `/operari/planols` | **Spec 017** (Plànols As-Built) | Capes independents no destructives, conmutador de visibilitat (Eye/EyeOff), pins georeferenciats, diàleg obligatori d'esmena sobre feines tancades (*"Capa tancada, vols crear una capa nova?"*). | *"No tens cap plànol o xarxa tècnica assignada avui"* | Implementat (`dark:`, selector de capes) | **VALIDAT (100%)** |
| `/operari/tiquets` | **Spec 018** (Tiquets de Despesa) | Categories (Carburant, Dietes, Material), doble foto obligatòria per carburant, recordatori de lliurament físic a la bústia de Secretaria al vespre. | *"No tens cap tiquet registrat avui"* | Implementat (`dark:`, formularis d'alt contrast) | **VALIDAT (100%)** |
| `/operari/*` (Media) | **Spec 020** (Càmera Tècnica) | Prohibició estricta de galeria (`accept="image/*" capture="environment"`), compressió client Canvas a WebP (<1MB), desat segur a IndexedDB. | Zero imatges orfes | Transversal a tota la PWA | **VALIDAT (100%)** |

---

## 2. Disseny Unificat i Navegació Ergonòmica de Camp (`layout.tsx`)

S'ha implementat el nou layout comú per a `/operari` (`pwa/src/app/operari/layout.tsx`):
1. **Barra Superior Tècnica**:
   - **Campana Acústica** (Spec 013 RF-04 / Spec 016 RF-01): Reprodueix un to d'alerta natiu mitjançant Web Audio API (880 Hz).
   - **Commutador de Mode Clar / Fosc**: Sincronitzat amb `localStorage` i la classe `.dark` de Tailwind CSS, accessible en qualsevol moment.
2. **Barra de Navegació Inferior (Bottom Bar)**:
   - Botons tàctils de gran format amb iconografia d'alta llegibilitat: `Feines`, `Material`, `Vehicles`, `Plànols`, `Tiquets`, `SOS (112)`.
   - Ocultació automàtica a la pantalla de Login (`/operari/login`) per mantenir el flux d'accés lliure de distraccions.

---

## 3. Protocol de Proves Automatitzades (Resultats)

### A. Banc de Proves PWA (`node pwa/test_pwa_audit.mjs`)
```
================================================================================
  SEVALOR SUITE — PROTOCOL D'AUDITORIA QA PWA (/operari) [SPECS 013 a 020]
================================================================================

--- AUDITORIA SPEC 013: FEINES DE CAMP I GEOVALLA ---
  [PASS] Test 1: Spec 013 RF-07: Text canònic d'Empty State (Zero Mock Data)
  [PASS] Test 2: Spec 013 RF-12.1 / EDGE-07: Validació Geovalla (<50m permesa, >50m desviació)

--- AUDITORIA SPEC 014: MATERIALS, EINES I BALANÇ ---
  [PASS] Test 3: Spec 014 RF-03: Text canònic d'Empty State (Zero Mock Data)
  [PASS] Test 4: Spec 014 RF-10 / RF-11: Càlcul de balanç Consum = Pick In - Pick Out
  [PASS] Test 5: Spec 014 RF-13: Restricció de tall per a format continu (Tub PE/Cable)

--- AUDITORIA SPEC 015: FLOTA, VEHICLES I CARBURANT ---
  [PASS] Test 6: Spec 015 RF-02: Text canònic d'Empty State (Zero Mock Data)
  [PASS] Test 7: Spec 015 RF-07: Doble fotografia obligatòria per a tiquets de carburant
  [PASS] Test 8: Spec 015 RF-20: Càlcul idempotent de Km totals (Final - Inicial)

--- AUDITORIA SPEC 016: INCIDÈNCIES DE CAMP I SOS ---
  [PASS] Test 9: Spec 016 RF-21: Flexibilitat multimodal (1 sol canal autoritza l'enviament)

--- AUDITORIA SPEC 017: PLÀNOLS AS-BUILT I CAPES ---
  [PASS] Test 10: Spec 017 Context: Text canònic d'Empty State de Plànols
  [PASS] Test 11: Spec 017 RF-13.1: Diàleg d'esmena sobre capa tancada/facturada

--- AUDITORIA SPEC 018: TIQUETS DE DESPESA I COMPROVANTS ---
  [PASS] Test 12: Spec 018 Context: Text canònic d'Empty State de Tiquets

--- AUDITORIA SPEC 019: LOGIN PIN 4 DÍGITS ---
  [PASS] Test 13: Spec 019 RF-02: Auto-submit immediat en prémer el 4t dígit

--- AUDITORIA SPEC 020: CÀMERA TÈCNICA I ANTIFRAUDE ---
  [PASS] Test 14: Spec 020 RF-15 / RF-17: Bloqueig de galeria i forçat de càmera en viu (environment)

================================================================================
  RESULTAT GLOBAL DE L'AUDITORIA: 14/14 PROVES SUPERADES EN VERD
================================================================================
```

### B. Proves Criptogràfiques i de Càmera (`test_crypto.mjs` + `test_pwa_logic.mjs`)
- Derivació PBKDF2 (100.000 iteracions) + AES-GCM-256 completada en ~31 ms.
- Autenticació offline mitjançant `SEVALOR_SENTINEL` validada.
- Bloqueig absolut d'arxius de galeria local confirmat mitjançant paràmetres HTML5 anti-frau.

### C. Proves Backend de Regressió (`docker run ... run_tests.py`)
- **31/31 proves d'integració en verd (0 fallades, 0 errors)** cobrint RLS Multi-Tenant, Veri*factu, immutabilitat SIF, outbox AEAT i seguretat Telegram/Whisper.

### D. Compilació de Producció Next.js (`npm run build`)
- **13/13 pàgines estàtiques generades amb èxit** sense cap error de tipus ni d'estils.
