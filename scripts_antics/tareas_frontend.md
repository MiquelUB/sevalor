# Pla de Desenvolupament Frontend (PWA Next.js) - Sevalor

## FASE 1: Autenticació, Layouts i Zero-Trust (Specs 001, 019)
- [ ] **1.1. Contextos Globals:** Implementació de `AuthContext` i gestió de JWT. Redireccions d'autenticació (middleware.ts).
- [ ] **1.2. Login Gestió:** Pàgina de login d'oficina (Correu + Contrasenya) i selector de Tenant (per a superadmins).
- [ ] **1.3. Login Operari:** Pàgina de login ràpid (NIF + PIN de 4 dígits) dissenyada per a pantalles tàctils a peu d'obra.
- [ ] **1.4. Shell UI:** Layouts adaptatius (Sidebar per Gestió, Bottom Tab Navigation per Operaris).

## FASE 2: Motor Offline-First i Hook Sincronització (Spec 013)
- [ ] **2.1. Indicador d'Estat Xarxa:** Component UI persistent que mostra l'estat Online/Offline i els elements a la cua.
- [ ] **2.2. Hooks Dexie.js:** Creació de `useFeinesOffline`, `useFichajesOffline` per llegir/escriure de IndexedDB reactivament.
- [ ] **2.3. Gestor de Cues Workbox:** Interfície per forçar la sincronització manual (Sync_queue) des de la UI quan torna l'internet.

## FASE 3: Panells de Gestió - Oficina (Specs 002, 003, 004, 007)
- [ ] **3.1. Dashboard Principal (Empty States Reals):** Gràfiques de tresoreria (cash-flow) exclusivament basades en dades RLS.
- [ ] **3.2. CRM Bàsic (Clients / Proveïdors):** Taules DataGrid paginades via Server Actions (o SWR) per CRUD de clients i proveïdors.
- [ ] **3.3. Magatzem i Estoc:** Llistat d'articles amb alertes d'estat (quarantena).
- [ ] **3.4. Comptabilitat:** Llistat de factures i botó de descàrrega XML/PDF (Veri*factu).

## FASE 4: App d'Operari - Mobile-First (Specs 013, 016, 018)
- [ ] **4.1. Fichaje Laboral:** Pantalla gran amb botó "Iniciar Jornada" i "Finalitzar Jornada" guardant l'hora a IndexedDB.
- [ ] **4.2. Llistat de Feines i Rutes:** Targetes grans (Mobile UI) per a les Ordres de Treball assignades a l'operari.
- [ ] **4.3. Captura OCR de Tiquets:** Interfície que utilitza l'API de Càmera de la PWA per adjuntar despeses ràpidament.
