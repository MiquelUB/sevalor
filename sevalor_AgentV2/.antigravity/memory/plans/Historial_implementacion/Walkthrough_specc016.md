# Walkthrough d'Auditoria i Verificació — PWA: Bústia d'Incidències i SOS 112 (/operari/incidencies — Spec 016)

Aquest document certifica la implementació i auditories del mòdul **PWA Bústia d'Incidències i SOS 112** d'acord amb la **Spec 016**.

---

## 🎯 Proves i Regles de Negoci Verificades
1. **Tramesa Multimodal d'Incidències (`RF-01` a `RF-08`)**:
   - Verificada la càrrega de fotografia i àudio d'avaria vinculats a l'ordre de treball.
2. **Commutació a Vermell Prioritari (`RF-09` a `RF-12`)**:
   - Comprovada la propagació reactiva de l'alerta urgent cap a la Torre de Control GIS.
3. **Protocol SOS 112 (`RF-13` a `RF-18`)**:
   - Verificat el llançador directe a trucada mèdica 112 i la transmissió de telemetria WGS84.
4. **Transcripció de Veu Whisper Sobirana**:
   - Verificada la integració amb el servei local sense enviament a APIs externes.

---

## 📊 Resultats de la Suite de Proves QA
- **Suite PWA QA**: `node pwa/test_pwa_audit.mjs` (Incidències i SOS 112 superats al 100%).
