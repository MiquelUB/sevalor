# Pla d'Implementació: Magatzem Central & Inventari Continu (/gestio/magatzem — Spec 004)

Aquest pla defineix la implementació del mòdul de **Magatzem Central & Inventari Industrial** (`/gestio/magatzem`) d'acord amb la **Spec 004**, la Constitució v4.0 de SEVALOR, la política de **Zero Mock Data** i el seguiment estricte d'existències.

---

## 🎯 Objectius i Requisits
1. **Control d'Inventari Continu**: Seguiment d'estoc físic, estoc reservat per a ordres de treball i estoc disponible.
2. **Punt de Comanda i Alerta de Ruptura**: Alerta visual quan l'estoc baixa del llindar crític de reposició.
3. **Traçabilitat de Moviments**: Entrades de comandes de proveïdors, sortides cap a colles de camp i devolucions.
4. **Valoració de Magatzem**: Càlcul de preu mitjà ponderat (PMP) i valor total de l'estoc per al balanç financer.
5. **Zero Mock Data**: Estat buit per a nous magatzems sense materials registrats.

---

## 🛠️ Canvis Tècnics
- **Frontend**: [`pwa/src/app/gestio/magatzem/page.tsx`](file:///media/akaun/Project_1/SEVALOR/pwa/src/app/gestio/magatzem/page.tsx)
- **Base de Dades**: Esquema `004_magatzem.sql` amb taules de productes, lots i moviments.

---

## 🧪 Pla de Verificació
- Execució de la suite: `node pwa/test_gestio_audit.mjs`.
- Proves d'aïllament RLS al backend: `python3 backend/run_tests.py`.
