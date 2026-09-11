# Walkthrough d'Auditoria i Verificació — PWA: Càmera Tècnica i Evidències WebP (/operari/camera — Spec 020)

Aquest document certifica la implementació i verificació del mòdul **PWA Càmera Tècnica i Evidències WebP** d'acord amb la **Spec 020**.

---

## 🎯 Proves i Regles de Negoci Verificades
1. **Bloqueig de Galeria & Forçat de Càmera en Directe (`RF-01` a `RF-06`)**:
   - Verificat el comportament del control de captura per a garantir que només s'accepten fotografies preses en el moment.
2. **Compressió WebP < 1 MB (`RF-07` a `RF-12`)**:
   - Comprovada la reducció automàtica de mida preservant la claredat pericial de les captures.
3. **Metadades WGS84 i Estampa Temporal (`RF-13` a `RF-16`)**:
   - Verificada la traçabilitat geogràfica de cada evidència fotogràfica.
4. **Sobirania de Dades Hetzner**:
   - Comprovat el desat directe al servidor alemany de Falkenstein.

---

## 📊 Resultats de la Suite de Proves QA
- **Suite PWA QA**: `node pwa/test_pwa_audit.mjs` (Càmera tècnica i evidències WebP 100% en verd).
