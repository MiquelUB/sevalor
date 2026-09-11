# Pla d'Implementació: Comptabilitat, Tresoreria & Veri*factu (/gestio/comptabilitat — Spec 007)

Aquest pla defineix la implementació del mòdul de **Comptabilitat, Tresoreria i Sistema Informàtic de Facturació Inmutable (SIF / Veri*factu)** (`/gestio/comptabilitat`) d'acord amb la **Spec 007**, la Llei Antifrau 11/2021, el RD 1007/2023 i la Constitució v4.0 de SEVALOR.

---

## 🎯 Objectius i Requisits
1. **Facturació Inmutable i Cadena de Hash SHA-256**: Cada factura emesa conté el hash de la factura anterior, garantint la no-alteració posterior.
2. **Codi QR Tributari & Indicador Veri*factu**: Generació de QR oficial per a comprovació tributària ciutadana segons especificacions AEAT.
3. **Tresoreria i Cash Flow**: Previsió de cobraments i pagaments a 30/60/90 dies amb alertes d'impagats.
4. **Integració Bancària Segura**: Control de remeses SEPA i bloqueig antifrau per canvi d'IBAN.
5. **Zero Mock Data**: Si no hi ha factures emeses en el tenant, es mostra l'estat inicial preparat per al primer cicle comptable.

---

## 🛠️ Canvis Tècnics
- **Frontend**: [`pwa/src/app/gestio/comptabilitat/page.tsx`](file:///media/akaun/Project_1/SEVALOR/pwa/src/app/gestio/comptabilitat/page.tsx)
- **Base de Dades**: Esquema `006_sif_inmutable.sql` amb triggers d'integritat criptogràfica i registre Outbox AEAT.

---

## 🧪 Pla de Verificació
- Execució de la suite de gestió: `node pwa/test_gestio_audit.mjs`.
- Proves unitàries de SIF i encadenament SHA-256 al backend: `python3 backend/run_tests.py`.
