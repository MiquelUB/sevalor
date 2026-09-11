# Pla d'Implementació — PWA Operaris de Camp (Specs 013 a 020)

Aquest document estableix el pla tècnic d'implementació per al mòdul mòbil de camp (**PWA `/operari`**), cobrint de manera exhaustiva les especificacions tècniques **Specs 013 a 020**, la Constitució v4.0 de SEVALOR, la política de **Zero Mock Data** i el funcionament Offline-First.

---

## 📱 Abast de les Especificacions Cobrtes

1. **Spec 013 (`/operari/feines`)**: Llista d'ordres de treball assignades, canvi d'estat (EN_CURS, PAUSADA, COMPLETADA), cronòmetre de tasca i fitxatge de feina.
2. **Spec 014 (`/operari/material`)**: Sol·licitud de material a magatzem, càrrec de consumibles a l'ordre de treball, devolució d'eines.
3. **Spec 015 (`/operari/vehicles`)**: Checklist pre-viatge de seguretat de vehicles, registre de quilometratge, incidències mecàniques.
4. **Spec 016 (`/operari/incidencies`)**: Notificació immediata d'incidències tècniques o de seguretat amb foto geolocalitzada.
5. **Spec 017 (`/operari/planols`)**: Visor offline de plànols de parcel·les, capes de reg, arquetes i vàlvules.
6. **Spec 018 (`/operari/tiquets`)**: Captura de tiquets de despesa, combustible o ferreteria amb foto de rebut.
7. **Spec 019 (`/operari/login`)**: Autenticació ràpida per PIN de 4 dígits i suport multi-colla.
8. **Spec 020 (`/operari/camera`)**: Càmera integrada amb geolocalització EXIF, estampa temporal i signatura digital del client sobre pantalla.

---

## 🏗️ Arquitectura i Components Tècnics

### 1. Offline-First & Sincronització Outbox
- Persistència local amb IndexedDB / Dexie.js.
- Cua de tasques outbox que s'executa automàticament en recuperar la connectivitat.
- Resolució de conflictes basada en timestamps d'última escriptura (`updated_at`).

### 2. Seguretat i Multi-Tenancy
- Token JWT emmagatzemat de manera segura amb aïllament d'arrendatari via PostgreSQL RLS.
- Encriptació simètrica local per a dades sensibles en repòs.

### 3. Interfície i Disseny
- Disseny adaptat a pantalla tàctil per a ús amb guants (botons >48px).
- Suport natiu per a Mode Clar i Mode Fosc.
- Zero mock data: estat buit net si no hi ha dades assignades.

---

## 🧪 Pla de Verificació
- Suite de contrast QA de la PWA: `node pwa/test_pwa_audit.mjs`.
- Suite de criptografia offline: `node pwa/test_crypto.mjs`.
