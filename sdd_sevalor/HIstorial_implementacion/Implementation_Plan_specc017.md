# Pla d'Implementació — PWA: Plànols Vectorials i Capes As-Built (/operari/planols — Spec 017)

Aquest pla defineix la implementació del mòdul de **Visualització i Anotació de Plànols de Camp (As-Built)** d'acord amb la **Spec 017**, la Constitució v4.0 de SEVALOR i la política de **Zero Mock Data**.

---

## 🎯 Objectius del Mòdul
1. **Visor de Plànols Cartogràfics Offline (`RF-01` a `RF-06`)**:
   - Càrrega de plànols vectorials de la finca sobre ortofoto PNOA descarregada prèviament a IndexedDB.
   - Visualització de capes de canonades, arquetes, hidrants i vàlvules de sectorització.
2. **Anotacions de Camp sobre Capa Independent As-Built (`RF-07` a `RF-12`)**:
   - Inserció de marcadors, rectificacions de traçat o canvis d'emplaçament detectats a peu de rasa.
   - **Preservació absoluta del plànol mestre original**: les anotacions es desen estrictament en una nova capa `As-Built` sense sobreescriure el disseny d'enginyeria.
3. **Bloqueig d'Obra Tancada (`RF-13` a `RF-16`)**:
   - Si l'ordre de treball està tancada o facturada, el visor impedeix l'edició directa i mostra el diàleg de confirmació: *"Capa tancada per peritatge. Voleu crear una nova capa d'anotació independent?"*.
4. **Simbologia Normalitzada de Reg (`RF-17`, `RF-18`)**:
   - Iconografia tècnica unificada per a vàlvules reguladores de pressió, ventoses i bombaments.
5. **Zero Mock Data & Suport Dark Mode (`RF-19`, `RF-20`)**:
   - Estat buit si la parcel·la no té plànols cadastrals o cartogràfics associats.

---

## 🛠️ Components Tècnics
- **Frontend PWA**: `pwa/src/app/operari/planols/page.tsx`
- **Motor Gràfic**: Renderitzat vectorial sobre SVG / Leaflet WGS84 adaptat a mòbil.
- **Auditoria QA**: `pwa/test_pwa_audit.mjs` i `test_planols_audit.mjs`
