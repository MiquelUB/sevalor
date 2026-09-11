# Pla d'Implementació: Torre de Control GIS & Cockpit Únic (/gestio/mapa — Spec 005)

Aquest pla defineix la implementació del mòdul de **Torre de Control GIS i Cockpit Tàctic** (`/gestio/mapa`) d'acord amb la **Spec 005**, la Constitució v4.0 de SEVALOR, suport complet per a **Mode Clar i Mode Fosc**, i rendering de parcel·les PostGIS en temps real.

---

## 🎯 Objectius i Requisits
1. **Visor Cartogràfic Tàctic WGS84**: Renderització de polígons de finques rústiques i punts d'ordres de treball actives.
2. **Cockpit Split-View**: Panell lateral d'alta densitat amb mètriques operatives (colles actives, alertes de seguretat, feines en curs).
3. **Filtres Tècnics Ràpids**: Filtrar per client, colla, prioritat (Crítica, Urgent, Normal) o estat d'obra.
4. **Privacitat Hetzner**: Càrrega de capes cartogràfiques des de servidors cartogràfics sobirans i tiles OSM sense rastrejadors comercials.

---

## 🛠️ Canvis Tècnics
- **Frontend**: [`pwa/src/app/gestio/mapa/page.tsx`](file:///media/akaun/Project_1/SEVALOR/pwa/src/app/gestio/mapa/page.tsx) amb Leaflet / PostGIS GeoJSON.

---

## 🧪 Pla de Verificació
- Execució de l'auditoria desktop: `node pwa/test_gestio_audit.mjs`.
