# Pla d'Implementació — PWA: Agenda, Ruta i Feines d'Obra (/operari/feines — Spec 013)

Aquest pla formalitza la implementació del mòdul de camp **Agenda, Ruta i Ordres de Treball** d'acord amb la **Spec 013**, la Constitució v4.0 de SEVALOR, la política de **Zero Mock Data** i el paradigma **Offline-First**.

---

## 🎯 Objectius del Mòdul
1. **Targetes de Feina del Dia (`RF-01` a `RF-05`)**:
   - Llistat cronològic d'ordres de treball assignades a la colla per a la jornada d'avui.
   - Detalls essencials: codi OT, client, finca, descripció de l'avaria o instal·lació, i telèfon d'atenció directa.
2. **Botó "Iniciar Trajecte" & Commutació a Blau (`RF-06`, `RF-07`)**:
   - En prémer "Iniciar Trajecte", la targeta commuta visualment a estat blau ("En Camí").
   - Disparador de notificació push/Telegram al client amb hora estimada d'arribada (ETA).
3. **Geovalla de 50 m & Activació Automàtica a Verd (`RF-08` a `RF-10`)**:
   - Monitorització de geolocalització WGS84 mitjançant l'API HTML5 Geolocation.
   - En creuar el radi de 50 m de la parcel·la, l'estat commuta automàticament a verd ("En Feina").
   - Inici automàtic del cronòmetre de feina per al còmput horari d'obra.
4. **Resolució de la Feina & Signatura del Part (`RF-11` a `RF-15`)**:
   - Formulari de resolució tècnica, checklist d'actuació i recollida de signatura tàctil del client.
   - Tancament de la feina amb aturada del temporitzador i enviament a la cua de sincronització outbox.
5. **Zero Mock Data & Mode Fosc (`RF-21` a `RF-24`)**:
   - Estat buit canònic si no hi ha ordres assignades ("No teniu feines assignades per avui").
   - Suport complet per a Mode Fosc (`dark:`) per a visualització en exteriors amb contrast alt.

---

## 🛠️ Components Tècnics
- **Frontend PWA**: `pwa/src/app/operari/feines/page.tsx`
- **Gestor Offline**: Persistència a IndexedDB amb esquema per a ordres, geovalles i estats temporals.
- **Auditoria QA**: `pwa/test_pwa_audit.mjs`
