# Pla d'Implementació — PWA: Materials, Picking i Sobrants (/operari/material — Spec 014)

Aquest pla defineix la implementació del mòdul de **Gestió de Materials de Camp, Picking Matinal i Control de Sobrants** d'acord amb la **Spec 014**, la Constitució v4.0 de SEVALOR i la política de **Zero Mock Data**.

---

## 🎯 Objectius del Mòdul
1. **Checklist de Pick In Matinal a la Nau (`RF-01` a `RF-06`)**:
   - Llistat de materials previstos per a les ordres de treball del dia carregades a la furgoneta.
   - Verificació per caselles de selecció de canonades, accessoris d'electrofusió, hidrants i vàlvules.
2. **Pick Out de Devolució de Sobrants al Tancament (`RF-07` a `RF-12`)**:
   - Recompte al final de la jornada de material no utilitzat per a retornar a la nau central.
   - Aplicació matemàtica del balanç canònic: $\text{Consum Efectiu} = \text{Pick In} - \text{Pick Out}$.
3. **Salides Blanques d'Urgència per a Avaries de Nivell 1 (`RF-13` a `RF-18`)**:
   - Protocol d'extracció directa de material del magatzem fora de comanda davant d'avaries crítiques de xarxa.
   - Imputació immediata a l'ordre d'emergència amb traça d'auditoria.
4. **Custòdia d'Eines de Treball (`RF-19`, `RF-20`)**:
   - Registre d'eines assignades al vehicle i verificació d'estat (operatiu / defectuós).
   - **Exclusió de codis QR a les eines** segons la Constitució v4.0 (identificació per número de sèrie o referència física).
5. **Zero Mock Data & Suport Dark Mode (`RF-21` a `RF-24`)**:
   - Estat buit canònic quan el vehicle no té càrrega assignada.

---

## 🛠️ Components Tècnics
- **Frontend PWA**: `pwa/src/app/operari/material/page.tsx`
- **Sincronització amb Magatzem Central**: Endpoints de descomptes d'estoc amb control pessimista.
- **Auditoria QA**: `pwa/test_pwa_audit.mjs`
