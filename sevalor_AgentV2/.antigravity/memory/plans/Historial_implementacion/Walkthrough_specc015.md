# Walkthrough d'Auditoria i Verificació — PWA: Control Horari de Flota (/operari/vehicles — Spec 015)

Aquest document certifica la implementació i verificació del mòdul **PWA Control de Flota i Carburant** d'acord amb la **Spec 015**.

---

## 🎯 Proves i Regles de Negoci Verificades
1. **Odòmetre per Foto Obligatòria (`RF-01` a `RF-06`)**:
   - Verificat el bloqueig de teclat numèric per a introduir km manuals; l'única via admesa és la captura fotogràfica del quadre.
2. **Doble Foto de Repostatge (`RF-07` a `RF-12`)**:
   - Comprovada la validació atòmica exigint foto de tiquet + foto simultània d'odòmetre.
3. **Consum Real L/100km (`RF-13` a `RF-16`)**:
   - Verificat el càlcul matemàtic de consum i la segregació de consumibles AdBlue.
4. **Sobirania de Fitxers Hetzner**:
   - Comprovada la persistència local al volum de disc de l'arrendatari a Falkenstein (Alemanya).

---

## 📊 Resultats de la Suite de Proves QA
- **Suite PWA QA**: `node pwa/test_pwa_audit.mjs` (Control de vehicles i repostatges 100% en verd).
