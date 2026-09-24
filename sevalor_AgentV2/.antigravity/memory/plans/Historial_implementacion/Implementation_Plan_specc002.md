# Pla d'Implementació: Portal de Clients i Finques Rústiques (/gestio/clients — Spec 002)

Aquest pla defineix la implementació del mòdul de **Portal de Clients i Finques** (`/gestio/clients`) d'acord amb la **Spec 002**, la Constitució v4.0 de SEVALOR, la política de **Zero Mock Data**, el disseny responsive d'alta densitat amb suport per a **Mode Clar i Mode Fosc**, i l'aïllament multi-tenant RLS.

---

## 🎯 Objectius Funcionalitats Clau
1. **Fitxa de Client d'Alta Densitat**: Codi identificador visual (`CLI-XXXX`), raó social, NIF/CIF, contacte principal i domicili fiscal.
2. **Finques Rústiques i Parcel·les**: Llistat de parcel·les associades a cada client, referència cadastral, polígon, parcel·la i superfície (ha / m²).
3. **Cerca Ràpida i Filtres**: Filtre instantani per nom, CIF, referència cadastral o municipi.
4. **Seguretat Multi-Tenant RLS**: Aïllament taxatiu a nivell de PostgreSQL, evitant fuites d'informació entre arrendataris.
5. **Zero Mock Data**: Si l'arrendatari és nou, es mostra l'estat buit de benvinguda amb botó de creació del primer client.

---

## 🛠️ Canvis Tècnics
- **Frontend**: [`pwa/src/app/gestio/clients/page.tsx`](file:///media/akaun/Project_1/SEVALOR/pwa/src/app/gestio/clients/page.tsx)
- **Backend**: Integració amb endpoints de gestió de clients i parcel·les.
- **Base de Dades**: Esquema `003_clients_finques.sql` amb polítiques RLS.

---

## 🧪 Pla de Verificació
- Execució de la suite de gestió desktop: `node pwa/test_gestio_audit.mjs`.
- Proves de regressió backend: `python3 backend/run_tests.py`.
