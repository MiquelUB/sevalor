# Walkthrough d'Auditoria i Verificació — PWA: Agenda, Ruta i Feines (/operari/feines — Spec 013)

Aquest document certifica la implementació i auditories de conformitat del mòdul **PWA Agenda, Ruta i Feines** d'acord amb la **Spec 013**.

---

## 🎯 Proves i Regles de Negoci Verificades
1. **Llistat de Feines & Zero Mock Data (`RF-01` a `RF-05`)**:
   - Verificat el renderitzat de targetes d'obra i l'estat buit canònic davant l'absència d'ordres assignades.
2. **Commutació d'Estat a Blau en Trajecte (`RF-06`, `RF-07`)**:
   - L'acció "Iniciar Trajecte" actualitza atòmicament l'estat de la feina i emet l'avís de desplaçament.
3. **Geovalla de 50 metres & Inici a Verd (`RF-08` a `RF-10`)**:
   - Comprovació del canvi automàtic a estat verd en detectar coordenades dins de la geovalla de la finca.
4. **Còmput Temporal i Finalització d'Obra (`RF-11` a `RF-15`)**:
   - Còmput precís dels temps de desplaçament i intervenció efectiva amb signatura tàctil sobre pantalla.
5. **Resiliència Offline-First**:
   - Totes les transicions funcionen en zones blanques sense cobertura mòbil i s'encuen a l'Outbox local.

---

## 📊 Resultats de la Suite de Proves QA
- **Suite PWA QA**: `node pwa/test_pwa_audit.mjs` (Proves d'agenda, geovalla i transicions superades).
