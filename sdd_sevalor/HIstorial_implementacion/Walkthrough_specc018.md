# Walkthrough d'Auditoria i Verificació — PWA: Tiquets de Despesa de Camp (/operari/tiquets — Spec 018)

Aquest document certifica la implementació i auditories del mòdul **PWA Tiquets de Despesa de Camp** d'acord amb la **Spec 018**.

---

## 🎯 Proves i Regles de Negoci Verificades
1. **Captura de Comprovants per Càmera (`RF-01` a `RF-06`)**:
   - Verificada la captura de tiquets amb foto en directe.
2. **Control del Límit Diari de 100 € (`RF-07` a `RF-10`)**:
   - Comprovada l'activació de l'alerta d'autorització superior en excedir la quota diària de seguretat.
3. **Imputació a l'Expedient d'Obra (`RF-16`, `RF-17`)**:
   - Verificada la transferència de la despesa al balanç de costos reals de la comanda.
4. **Persistència Sobirana Hetzner**:
   - Comprovada la transferència i arxivament local a Falkenstein.

---

## 📊 Resultats de la Suite de Proves QA
- **Suite PWA QA**: `node pwa/test_pwa_audit.mjs` (Tiquets de despesa 100% en verd).
