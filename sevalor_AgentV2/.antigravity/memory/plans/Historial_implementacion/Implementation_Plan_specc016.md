# Pla d'Implementació — PWA: Bústia d'Incidències i SOS 112 (/operari/incidencies — Spec 016)

Aquest pla defineix la implementació del mòdul de **Notificació d'Incidències de Camp i Protocol d'Emergència SOS 112** d'acord amb la **Spec 016**, la Constitució v4.0 de SEVALOR i la política de **Zero Mock Data**.

---

## 🎯 Objectius del Mòdul
1. **Bústia d'Incidències Multimodal (`RF-01` a `RF-08`)**:
   - Comunicació d'incidents operatius: bloqueig d'accés a finca, sobrepressió de canonada, trencament de vàlvula o dany mecànic.
   - Suport per a captura de fotografia geolocalitzada en alta resolució i gravació d'àudio nativa WebM.
2. **Priorització Cromàtica Immediata (`RF-09` a `RF-12`)**:
   - La tramesa d'incidència commuta immediatament l'expedient a **VERMELL PRIORITARI** a la Torre de Control GIS i a la safata de l'enginyer.
3. **Protocol d'Emergència Mèdica SOS 112 (`RF-13` a `RF-18`)**:
   - Botó vermell d'emergència de gran format (>60px) accessible des de qualsevol pantalla de la PWA.
   - En prémer SOS:
     1. Obre immediatament l'enllaç de veu directa al `tel:112`.
     2. Emet una alerta màxima acústica i visual a l'oficina tècnica amb les coordenades GPS exactes decimals WGS84 del treballador.
4. **Gravació de Veu i Transcripció Whisper INT8 (`RF-19`, `RF-20`)**:
   - Enregistrament de veu natiu en català/castellà enviat al servei local Hetzner CPU-only faster-whisper.
5. **Zero Mock Data & Mode Fosc (`RF-21` a `RF-24`)**:
   - Estat buit canònic sense alertes fictícies.

---

## 🛠️ Components Tècnics
- **Frontend PWA**: `pwa/src/app/operari/incidencies/page.tsx`
- **Protocol SOS**: Enllaç directe del sistema operatiu mòbil a l'equip d'emergències mèdiques i transmissió per websocket/REST.
- **Auditoria QA**: `pwa/test_pwa_audit.mjs`
