# Pla d'Implementació: Flota i Manteniment ITV (/gestio/flota — Spec 006)

Aquest pla defineix la implementació del mòdul de **Gestió de Flota i Parc Mòbil** (`/gestio/flota`) d'acord amb la **Spec 006**, la Constitució v4.0 de SEVALOR, la política de **Zero Mock Data**, el disseny responsive amb suport complet per a **Mode Clar i Mode Fosc**, i la integració sòlida amb el backend FastAPI i PostgreSQL.

---

## User Review Required

> [!IMPORTANT]
> **Resolució d'ITV en 4 Veredictes (Spec 006 RF-18 / Test 4.5)**:
> 1. **Favorable Limpia**: El vehicle recupera l'estat `OPERATIU` [Verd].
> 2. **Favorable amb Defectes Lleus (DL)**: Estat `LEVE` [Verd Clar / Lima]. El vehicle roman 100% operatiu per llei i pot ser assignat a rutes; els defectes s'incorporen a la llista de tasques del proper manteniment preventiu.
> 3. **Desfavorable**: Estat `DESFAVORABLE` [Vermell Fosc]. El vehicle queda automàticament immobilitzat, s'obre la finestra de 2 mesos de termini de subsanació i es genera automàticament una Ordre de Treball (OT) interna a taller. Alerta crítica al dia 61 amb proposta de baixa d'ofici DGT segons RD 920/2017.
> 4. **Negativa**: Estat `INACTIVAT` [Vermell Fosc]. Immobilització total immediata amb avís obligatori de transport en grua al taller i obertura d'OT interna.

> [!NOTE]
> **Anàlisi de Consum Real i Desglossament d'AdBlue (Spec 006 RF-16)**:
> - El consum es calcula contrastant el combustible dels tiquets contra el diferencial d'odòmetre ($\text{L/100km} = \frac{\text{Litres}}{\Delta\text{Km}} \times 100$).
> - En vehicles dièsel, l'**AdBlue** es desglossa en una línia independent purament informativa, sense alterar la fórmula ni generar falses alertes.
> - La mitjana històrica consolidada comença a partir del **primer mes de rodatge actiu (30 dies)**.
> - Si el consum supera en més d'un **10%** la mitjana consolidada, es dispara una alerta d'anomalia resoluble amb un **botó de descarte manual tipificat** (Càrrega pesada/remolc, Climatologia adversa, Ruta de muntanya, Fuga mecànica revisada, Altres).

> [!TIP]
> **Control Contractual de Rènting / Lísing (Spec 006 RF-06 / RF-29)**:
> - Seguiment del quilometratge o hores de contracte amb alertes deterministes de proximitat al **90%**, **95%** i **100%**.
> - Suport de 3 règims: **Propietat** (amb quota d'amortització contable mensual), **Rènting/Leasing** (amb quotes i límits), i **Vehicle de Sustitució Temporal** (relació 1 a N d'estancies_substitucio sense col·lisió de claus).

---

## Proposed Changes

### Backend FastAPI (`backend/app/api/v1/gestio/flota.py`)

#### [MODIFY] `backend/app/api/v1/gestio/flota.py`
- Afegir endpoint `GET /gestio/flota/vehicles` per recuperar el llistat de vehicles amb la seva telemetria de consum, alertes de rènting, estat d'ITV i dades de manteniment.
- Afegir endpoint `POST /gestio/flota/vehicles` per donar d'alta nous vehicles (furgonetes, pick-ups, camions, elèctrics EV, híbrids PHEV, maquinària amb horòmetre i remolcs exents de consum).
- Afegir endpoint `POST /gestio/flota/descartar-anomalia-consum` per enregistrar la justificació tipificada d'una desviació de consum superior al 10%.
- Mantenir i refermar l'endpoint existent `POST /gestio/flota/registrar-itv` per als 4 veredictes amb generació automàtica d'OT de taller per a Desfavorable i Negativa.

---

### Layout Desktop (`pwa/src/app/gestio/layout.tsx`)

#### [MODIFY] `pwa/src/app/gestio/layout.tsx`
- Incorporar l'enllaç de navegació a la barra lateral (Sidebar):
  `{ label: "Flota & Vehicles", href: "/gestio/flota", icon: Truck, badge: "FLT" }`
- Afegir entitats de vehicles a l'índex del cercador Spotlight Meta-Search (`Ctrl + K`).

---

### Pàgina Principal de Flota (`pwa/src/app/gestio/flota/page.tsx`)

#### [NEW] `pwa/src/app/gestio/flota/page.tsx`
- **Taula General d'Alta Densitat amb les 8 Columnes Essencials (RF-01)**:
  1. Identificador / Matrícula.
  2. Tipologia, Propulsió i Distintiu Ambiental DGT oficial (0, ECO, C, B, Sense Distintiu).
  3. Marca, Model i Versió.
  4. Règim d'Adquisició (Propietat, Rènting/Leasing o Sustitució) amb barres de progrés i alertes al 90/95/100%.
  5. Custodi / Conductor Habitual assignat.
  6. Mètrica d'Ús Acumulada (km d'odòmetre o h d'horòmetre sota historial únic continu, o N/A en remolcs).
  7. Estat Operatiu (7 estats canònics: Operatiu, Operatiu DL, En Ruta, En Taller, Incidència, Retirat ITV, Baixa).
  8. Estat Legal, Anomalies i Cadena d'Alertes (30-15-5-1 dies).
- **Mòdul de Resolució d'ITV en 4 Veredictes (Modal Interactivu)**:
  - Favorable (Operatiu Verd).
  - Favorable amb Defectes Lleus (Operatiu Verd Clar / Lima + trasllat a manteniment).
  - Desfavorable (Immobilitzat + 2 mesos de termini + generació d'OT a taller).
  - Negativa (Immobilitzat + grua obligatòria).
- **Mòdul d'Anàlisi de Consum i Descarte d'Anomalies**:
  - Càlcul de L/100km i L/h amb històric d'AdBlue independent.
  - Alerta d'anomalia >10% respecte a la mitjana consolidada (>30 dies).
  - Diàleg de descarte tipificat amb els 5 motius homologats.
- **Selector de Filtres i Cercador en Temps Real**:
  - Filtres per tipologia, propulsió, distintiu DGT, estat d'ITV, alertes de rènting i anomalies legals.
- **Zero Mock Data (Dia 0 Canònic)**:
  - Si no hi ha vehicles: *"No hi ha vehicles registrats a la flota"*, cercador deshabilitat i botó d'alta.
- **Suport complet per a Mode Clar i Mode Fosc (`dark:`)**.

---

### Protocols de Proves i Auditoria QA

#### [NEW] `pwa/test_flota_audit.mjs`
- Prova 1: Els 4 veredictes d'ITV (Favorable, Favorable DL, Desfavorable, Negativa).
- Prova 2: Immobilització automàtica i generació d'OT en ITV desfavorable.
- Prova 3: Termini de 2 mesos i alerta crítica al dia 61.
- Prova 4: Càlcul de consum L/100km i segregació informativa d'AdBlue.
- Prova 5: Detecció d'anomalia de consum (>10%) a partir dels 30 dies de rodatge actiu.
- Prova 6: Botó de descarte manual amb motius tipificats.
- Prova 7: Llindars deterministes de rènting al 90%, 95% i 100%.
- Prova 8: Historial únic acumulatiu davant de canvi de quadre d'instruments.
- Prova 9: Distintius ambientals DGT inmutables sense caducitat.
- Prova 10: Zero Mock Data: estat buit canònic de Dia 0.

#### [MODIFY] `backend/tests/test_bloc4_gestio.py`
- Validació que els tests existents i nous de flota s'executin al 100% en verd a Docker.

---

## Verification Plan

### Automated Tests
1. **Bateria Backend a Docker**:
   ```bash
   docker run --rm --network host -v /media/akaun/Project_1/SEVALOR/backend:/app -w /app campopro-backend:latest python run_tests.py
   ```
2. **Auditoria QA de Flota**:
   ```bash
   node pwa/test_flota_audit.mjs
   ```
3. **Bateries Globals QA**:
   ```bash
   node pwa/test_pwa_audit.mjs && node pwa/test_gestio_audit.mjs && node pwa/test_superadmin_audit.mjs
   ```
4. **Compilació Next.js**:
   ```bash
   cd pwa && npm run build
   ```

### Manual Verification
- Comprovar que la pàgina `/gestio/flota` carrega correctament en mode clar i mode fosc.
- Comprovar el canvi d'estat a la taula quan es resol una ITV en qualsevol dels 4 veredictes.
- Verificar l'alerta visual de rènting quan un vehicle supera el 90% i 95% del contracte.
