# Walkthrough — Comptabilitat, Tresoreria & Veri*factu (/gestio/comptabilitat — Spec 007)

Aquest document resumeix la implementació del mòdul de **Comptabilitat, Tresoreria & Veri*factu** (`/gestio/comptabilitat`) d'acord amb la **Spec 007** de SEVALOR.

---

### E. Comptabilitat, Tresoreria & Veri*factu (`/gestio/comptabilitat`)
*Basada en Stitch Screen `dbf509d1ecc54f25b637628958c2f1b3` i Spec 007.*
- **Veto d'Enginyer Actiu**: Quan el rol és `ENGINYER`, renderitza estrictament la pantalla canònica: **"HTTP 403 Forbidden — Veto d'Enginyer a Dades Financeres"**.
- **Facturació Veri\*factu Oficial**: Taula de factures emeses amb generació de codi QR reglamentari de l'AEAT i empremta de segellat SHA-256 encadenat.
- **Outbox Pattern Asíncron (Spec 024)**: Monitorització de l'estat d'enviament a la seu electrònica de l'AEAT (`ENVIAT_SOAP` / `PENDENT`).
- **Triple Conciliació (Three-Way Matching)**: Verificació matemàtica d'Albarà $\times$ Comanda $\times$ Factura (0% desviació $\rightarrow$ `CONCILIADA`).
- **Banc Norma 43**: Panell d'ingesta desduplicada per hash SHA-256 dels fitxers d'extracte bancari.
- **Zero Mock Data**: Estat buit canònic: *"No hi ha factures pendents ni emeses"*.

---

## 🧪 Validació i Proves d'Auditoria QA

```bash
node pwa/test_gestio_audit.mjs
python3 backend/run_tests.py
```
- Verificació del registre inmutable de factures, càlcul del hash SHA-256, format QR Veri*factu i tauler de tresoreria.
