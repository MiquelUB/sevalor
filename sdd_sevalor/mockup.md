# Mockup & Design Specification — Dashboard i Torre de Control (/gestio)

> **Document de Definició Visual i Estructural per a Stitch (Projecte `CampoPro Gestio Dashboard` - ID: `588164796876803558`)**  
> Basat en la **Constitució de CampoPro Suite (v3.1)** i la **Spec 001 (`001-gestio-dashboard.md`)**.  
> **Sense dades fictícies hardcodejades en codi**: Estructura de components i patrons de disseny per a entorn de producció.

---

## 🎨 1. Sistema de Disseny (Design Tokens — Industrial Precision)

Aquest disseny aplica l'estètica **Industrial Precision & Corporate Modern**, orientada a l'alta densitat d'informació tècnica per a enginyers i comandaments d'oficina:

- **Canvas / Superfície:** Clean Slate (`#F8FAFC` / `#F1F5F9`) per a fons estructurals.
- **Color Primari Estructural:** Dark Navy (`#022448` / `#1E3A5F`) per a la capçalera, accions primàries i jerarquia d'ancoratge.
- **Accents i Funcionalitat:** Industrial Amber (`#D97706`) per a estats d'atenció i avisos; Cyan/Blue elèctric per a seleccions actives.
- **Tipografia:** Família `Inter` (sans-serif), des de 12px (metadades/etiquetes) fins a 24px (títols d'àrea) i 32px (KPIs numèrics).
- **Ràdio de vora:** 4px (inputs, botons i targetes de dades) i 8px (contenidors principals desacoblats).
- **Codi Cromàtic Funcional del Mapa (Independent del tema camaleònic de la web):**
  * *Taronja:* Obra Pendent / No iniciada.
  * *Blau:* Cuadrilla o vehicle en trànsit cap a l'obra.
  * *Verd:* Obra En faena / En curs (temps comptant).
  * *Vermell:* Obra o vehicle amb Incidència Activa / Parada tècnica.
  * *Blanc:* Obra Completada / Tancada.
  * *Negre:* Obra Cancel·lada.
  * *Lila:* Vehicle en Standby / Retén a base sense tasca externa.

---

## 🖥️ 2. Distribució Espacial (Layout Desktop 1440x900 / 1920x1080)

La pantalla està concebuda com una **Torre de Control integrada a pantalla completa** dividida en 3 nivells principals:

```
+----------------------------------------------------------------------------------------------------+
| [Logo] CampoPro Gestio  |  [🔍 Cerca universal: Clients, Factures, Ordres...]  | [Bon dia, Enric] 🔔3 |
+----------------------------------------------------------------------------------------------------+
| HUD OPERATIU: [8 Quadrilles]  [14 Ordres Avui]  [2 Incidències ⚠️]  [9 Flota]  [2 Alertes Stock/ITV]|
+----------------------------------------------------------------------------------------------------+
| [👥] PANELL ESQUERRE    |                                                | [⚠️] DRAWER INCIDÈNCIES  |
| (Sota Demanda: 300px)   |       MAPA CARTOGRÀFIC CENTRAL OPEN SOURCE     | (Alerta no invasiva:     |
|                         |            (OpenStreetMap / PNOA Satèl·lit)    |  380px sota demanda)     |
| - Quadrilla 1 [Verd]    |                                                |                          |
|   ↳ OT-101: Mas Nou     |   [🗺️/🛰️ Capes]        [🎯 Discriminador Capes]| - Audio natiu [▶ 0:42]   |
|   ↳ OT-102: Sector Nord |                         [📅 Filtre Temporal]   | - Informe Copilot IA     |
| - Quadrilla 2 [Vermell] |   Pins d'obra (Verd, Vermell, Taronja, Blau)   | - Foto pericial cancela  |
| - Quadrilla Retén [Lila]|   Icons de vehicle (Blau ruta, Lila retén)     | - [📞 Trucar Client]     |
|   ↳ Tasques magatzem    |   Capa Vectorial de canonades i vàlvules       | - [✉️ Enllaç Aprovació]  |
+----------------------------------------------------------------------------------------------------+
```

---

## 🧩 3. Especificació Detallada dels Components

### 3.1 Capçalera Superior (Global Header — 64px alçada)
- **Extrem Esquerre:**
  * Logotip corporatiu dinàmic de l'empresa instal·ladora.
  * Títol d'aplicació: `Torre de Control Operativa`.
  * Rellotge i data en temps real (format: `Dilluns, 7 de Setembre de 2026 — 09:42`).
- **Centre (Meta-Buscador Universal):**
  * Barra de cerca tipus *Spotlight* (`Ctrl+K`) amb icona de lupa.
  * Chips seleccionables de filtratge: `[Tots]` `[Clients]` `[Factures/Pressupostos]` `[Operaris]` `[Ordres]` `[Vehicles]` `[Magatzem]`.
  * *Accés Enginyer:* Obertura de factures/pressupostos de client sense dades financeres globals.
- **Extrem Dret:**
  * Salutació dinàmica: *"Bon dia, Enric (Enginyer Tècnic)"*.
  * Botó d'acció ràpida primari: `[+ Nova Ordre de Treball]` (Dark Navy amb icona blanca).
  * Selector d'idioma: `[CA | ES]`.
  * Accés al manual i benvinguda: `[?]`.
  * **Campana d'Incidències:** Icona de campana amb insígnia vermella pulsant `[🔔 2]` que indica bloquejos actius en temps real.

### 3.2 HUD Operatiu Superior (Global & Immutable — 72px alçada)
Cinta horitzontal amb 5 targetes d'indicadors tècnics d'alta densitat (**estrictament sense imports en € ni facturació**):
1. **Quadrilles en Jornada:** `8 Actives` (Desglossament subtil: `5 en faena` • `2 en trànsit` • `1 retén/nau`).
2. **Ordres de Treball Avui:** `14 Programades` (`4 en curs [Verd]` • `7 pendents [Taronja]` • `3 completades [Blanc]`).
3. **Incidències Obertes [Targeta Vermella Urgent]:** `2 Parades Tècniques` (Fons suau vermell, vora vermella d'alerta i botó d'accés directe al Drawer).
4. **Estat de la Flota:** `9 Vehicles` (`6 en ruta [Blau]` • `2 a base [Lila]` • `1 avariat en grua [Vermell]`).
5. **Alertes Preventives:** `2 Avisos` (`1 stock mínim magatzem` • `1 ITV propera <7 dies`).

### 3.3 El Mapa Central (Pantalla Completa — Leaflet / MapLibre)
- **Motor Cartogràfic:** Suport de teseles OpenStreetMap (urbanisme) i PNOA de l'IGN (ortofoto satel·litària d'alta resolució per a finques rústiques i rases).
- **Controls Flotants Superiors:**
  * **Selector de Capa Base:** Botons commutables `[🗺️ Carrerer]` / `[🛰️ Satèl·lit PNOA]`.
  * **Discriminador de Capes Multi-Criteri (Panell Flotant Desplegable):**
    - Capçalera amb botons ràpids: `[Marcar tots]` i `[Desmarcar tots]`.
    - Checkboxes independents:
      * `[x] Obres per estat (Taronja, Blau, Verd, Vermell, Blanc, Negre)`
      * `[x] Flota mòbil (Blau trànsit, Lila standby, Vermell avaria)`
      * `[x] Capa Vectorial de Xarxa (tuberíes PE, BT, vàlvules)`
      * `[x] Proveïdors i Ferreteries locals`
      * `[x] Incidències persistents d'altres dies`
  * **Navegador Temporal de Data:** Selector amb fletxes `[◀ Ahir] [📅 AVUI] [Demà ▶]`.
- **Elements Representats al Mapa:**
  * *Pins d'Obra:* Cercles amb icona d'eina amb vora de color segons estat (Verd en execució, Vermell per cancela tancada).
  * *Icons de Flota:* Furgonetes amb indicador de rumb (Blau desplaçament cap a obra, Lila standby a magatzem).
  * *Traçat Vectorial:* Línies de xarxa soterrada en blau cian (aigua/reg) o groc industrial (baixa tensió), amb arquetes i vàlvules clicables.
  * *Popovers Interactius:* Targeta emergent en clicar un pin amb client, adreça, telèfon `tel:`, quadrilla i botó *"Obrir Fulla de Tasca"*.

### 3.4 Panell Esquerre Sota Demanda (Acordió per Quadrilles — 300px)
- **Pestanya Col·lapsable:** Pestanya fixa vertical a l'extrem esquerre `[👥 Quadrilles (8)]`.
- **Estructura en Acordió:**
  * Llistat de les quadrilles que tenen fulla de tasca del dia seleccionat.
  * **Quadrilla de Retén:** Apareix explícitament amb la seva fulla interna de feines de magatzem per poder rebre feines per *Drop and Go*.
  * En clicar sobre una quadrilla, es desplega la llista cronològica de feines assignades (Codi, Client, Horari, Estat cromàtic).
  * En clicar sobre una tasca, el mapa fa un efecte de **destelleig visual (*highlight*)** sobre el pin de l'obra i la quadrilla sense moure el zoom.

### 3.5 Drawer Lateral Dret (Resolució d'Incidències — 380px)
- **Comportament No Invasiu:** No s'obre automàticament de cop; mostra un banner flotant superior no bloquejant:  
  `⚠️ Nova incidència reportada: OT-2026-092 (Accés Bloquejat - Mas Nou) [Obrir Drawer]`
- **Contingut del Drawer quan s'obre:**
  * **Capçalera d'Urgència:** Codi d'incidència, temps transcorregut de cronòmetre corrent ininterromput, client i ubicació.
  * **Reproductor d'Àudio Natiu:** Forma d'ona interactiva amb botó `[▶ Reproduir nota de veu del capataz (0:42)]`.
  * **Informe de Copilot IA (Draft Tècnic):** Transcripció resumida, diagnòstic preliminar i partida addicional proposada.
  * **Fotografia Pericial:** Miniatura ampliable de la cancel·la tancada amb cadenat.
  * **Botons d'Acció Immediata:**
    - `[📞 Trucar Client (tel:)]`: Avís telefònic directe instantani.
    - `[✉️ Enviar Enllaç d'Aprovació Web / Telegram]`: Remissió del formulari amb token xifrat d'acceptació a 1 clic.
    - `[🔄 Resoldre Incidència (Retorn a Verd)]`: Commuta l'estat a Verd en obrir-se la cancel·la.
    - `[❌ Cancel·lar Tasca]`: Retirada de la quadrilla i emissió d'albarà de devengos.

---

## 🚀 4. Prompt Estructurat per a Stitch (Generació de Pantalla Desktop)

Aquest és el text preparat per executar a la crida `generate_screen_from_text` de Stitch:

```text
A professional, high-density desktop operations dashboard (1440x900) for a field service technical engineering company named "CampoPro - Torre de Control".

Aesthetic: Industrial Precision, Corporate Modern, clean slate canvas (#F8FAFC), dark navy header (#022448), amber and semantic status indicators, crisp Inter typography, 4px/8px borders, zero clutter.

Layout:
1. Top Global Header (Dark Navy #022448):
   - Company logo on left with title "CampoPro Suite | Torre de Control".
   - Center: Universal search bar with filter chips ("Tots", "Clients", "Factures", "Operaris", "Ordres", "Vehicles", "Magatzem").
   - Right: "Bon dia, Enric (Enginyer)", Primary CTA button "+ Nova Ordre", language toggle "CA", help icon, and red alert bell badge "🔔 2".

2. Operational Pulse Ribbon / HUD (No financial data, pure operations):
   - 5 compact metric cards in a row:
     Card 1: "Quadrilles en Jornada" -> "8 Actives" (5 feina, 2 trànsit, 1 retén).
     Card 2: "Ordres d'Avui" -> "14 Programades" (4 en curs [Green], 7 pendents [Orange], 3 fetes [White]).
     Card 3 (Red Accent Card): "Incidències Urgents" -> "2 Parades Tècniques" with pulse dot and view button.
     Card 4: "Flota Mòbil" -> "9 Vehicles" (6 ruta, 2 base, 1 avariat).
     Card 5: "Alertes Preventives" -> "2 Avisos" (Stock mínim magatzem, ITV).

3. Main View Area (Full-bleed Geographic Map):
   - Open-source map background (styled street & aerial satellite toggle on top-left).
   - Overlay: Colored technical pipe/wire vector network lines (cyan PE pipe lines with valve icons).
   - Top-right floating controls: Layer Discriminator dropdown ("Marcar tots", "Desmarcar tots", toggles for Orders by Color, Fleet, Vector Network, Suppliers) and Date Navigator ("[◀] AVUI (7 Set) [▶]").
   - Map markers: Green circle with tools icon (active work), Red marker with alert (blocked gate incident), Blue van icon (in transit), Purple van at base (standby).
   - Interactive popover on one marker showing job details, client phone, crew name, and "Obrir Fulla" button.

4. Left Collapsible Accordion Drawer (300px, semi-open):
   - "Quadrilles del Dia" accordion list:
     * Quadrilla 1 (Capataz: M. Vila) [Green En Faena] -> Expanded with 2 assigned jobs.
     * Quadrilla 2 (Capataz: J. Soler) [Red Incidència].
     * Quadrilla Retén Base (2 operaris) [Purple Feines Magatzem].

5. Right Emergency Drawer (380px, slide-in overlay):
   - Title: "Incidència #INC-042: Accés Bloquejat (Cancela tancada)".
   - Audio waveform player with "▶ 0:42".
   - Photo thumbnail of padlock on gate.
   - Copilot technical report summary.
   - Action buttons: "📞 Trucar Client", "✉️ Enviar Enllaç d'Aprovació", "🔄 Resoldre (Retorn a Verd)".
```

---

## 📋 5. Comprovació de Connexió Stitch MCP

- **Servidor MCP:** `stitch` (actiu i operatiu).
- **Eina verificada:** `list_projects` ha retornat els projectes de l'usuari correctament.
- **Projecte vinculat:** `projects/588164796876803558` (*CampoPro Gestio Dashboard*, dispositiu DESKTOP, tema *Industrial Precision*).
- **Estat de pantalles:** Actualment lliure de pantalles prèvies, llest per rebre la crida de generació.
