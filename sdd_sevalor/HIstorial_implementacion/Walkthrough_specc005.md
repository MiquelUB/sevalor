# Walkthrough — Torre de Control GIS & Cockpit Únic (/gestio/mapa — Spec 005)

Aquest document resumeix la implementació del mòdul de **Torre de Control GIS i Cockpit Únic** (`/gestio/mapa`) d'acord amb la **Spec 005** de SEVALOR.

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

---

## 🧪 Validació i Proves d'Auditoria QA

```bash
node pwa/test_gestio_audit.mjs
```
- Verificació del visor de mapa, renderització de parcel·les GeoJSON, split-view d'alta densitat i filtratge per colles.
