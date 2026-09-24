# Walkthrough d'Auditoria i Verificació — PWA: Materials, Picking i Sobrants (/operari/material — Spec 014)

Aquest document certifica la implementació i verificació del mòdul **PWA Materials, Picking i Sobrants** d'acord amb la **Spec 014**.

---

## 🎯 Proves i Regles de Negoci Verificades
1. **Checklist de Pick In Matinal (`RF-01` a `RF-06`)**:
   - Verificat el marcatge de materials carregats a la furgoneta abans de sortir de la base.
2. **Equació de Balanç de Consum (`RF-07` a `RF-12`)**:
   - Comprovació del càlcul automàtic $\text{Consum} = \text{Pick In} - \text{Pick Out}$ i imputació directa a la comanda d'obra.
3. **Salides Blanques d'Emergència (`RF-13` a `RF-18`)**:
   - Verificada la creació de línies de consum extraordinari per a incidents de Nivell 1.
4. **Custòdia Nominal d'Eines (`RF-19`, `RF-20`)**:
   - Verificat el control per marca, model i número de sèrie amb compliment estricte de la no utilització de codis QR.
5. **Estat Buit Canònic**:
   - Interfície neta en Dia 0 sense elements fantasma.

---

## 📊 Resultats de la Suite de Proves QA
- **Suite PWA QA**: `node pwa/test_pwa_audit.mjs` (Mòdul de materials i balanç validat al 100%).
