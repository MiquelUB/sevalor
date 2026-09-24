# INFORME EXECUTIU CTO: Estat de Desenvolupament per Rols

Aquest document dissecciona l'estat d'implementació del projecte SEVALOR agrupant-ho en les 3 grans àrees o rols principals definits a l'arquitectura: **Admin (Gestió)**, **PWA (Camp/Operari)** i **Superadmin (Plataforma)**. S'ha contrastat el codi existent (PWA i Backend) amb els Requisits Funcionals (RFs) de les 24 Especificacions.

---

## 1. Àmbit ADMIN / BACKOFFICE (Ruta: `/gestio`)
**Usuaris objectiu:** Enginyers, Secretaria, Direcció.
**Specs Associades:** 001 a 012.

### Veredicte CTO: ⚠️ MOCK / ESQUELET (Superficial)
Aquest és l'àmbit amb més codi escrit, però la gran majoria és pur "teatre" visual (*Mocking*) i operacions CRUD (Crear/Llegir/Editar/Esborrar) desconnectades de la lògica de negoci real.

* **El que HI ÉS:**
  * Les taules de la Base de Dades estan ben dissenyades.
  * Totes les pantalles existeixen a `pwa/src/app/gestio/...` amb fitxers de React monolítics (+1.000 línies).
  * Els endpoints del backend (`backend/app/api/v1/gestio/...`) guarden i llegeixen registres.
  * *Excepció positiva:* S'han lligat algunes lògiques estrictes avui (PMP de Magatzem, Edició de Proveïdors, Bloqueig OCR PWA), que ja són Zero-Mock.

* **El que FALTA (Falsos "Acabats"):**
  * **Comptabilitat (Spec 007):** Només hi ha llistats i sumes visuals. Cap de les integracions XML de l'AEAT està programada (exportacions d'Inversió de Subjecte Passiu, generació de lots...).
  * **Clients / Feines (Spec 002/005):** Cap control d'Estats de Certificació, facturació de fites, ni el bloqueig pesimista en planificacions recurrents.
  * **Flota / Notificacions:** No hi ha processos automàtics (Workers) de manteniment ni ITV al darrere. Les notificacions són simples missatges en BBDD sense lògica Push/WebSocket sòlida.
  * **Copilot (Spec 012):** En la seva gran part el motor IA és de "cartró pedra" (Mocks), a excepció del que acabem d'implementar a Magatzem. No processa auditories asíncrones de forma transversal com exigeix la Spec.

---

## 2. Àmbit PWA / OPERARI (Ruta: `/operari`)
**Usuaris objectiu:** Operaris de Camp, Caps de Colla.
**Specs Associades:** 013 a 020.

### Veredicte CTO: ❌ INCOMPLET (Alta Fragilitat)
Aquest camp hauria de ser l'aplicació "Mobile First" dissenyada per a ús sense connexió (Offline) segons la Spec, però no compleix l'arquitectura.

* **El que HI ÉS:**
  * Hi ha arxius backend creats sota `api/v1/operari_pwa/` (Feines, Picking, Vehicles, Incidències, Tiquets).
  * Pantalles React com `feines`, `vehicles`, `login`, `tiquets`.

* **El que FALTA (Incompliments Greus):**
  * **Offline/IndexedDB:** La Spec exigeix que la PWA d'operari funcioni sense cobertura (sincronitzant per IndexedDB de manera asimètrica, ex. Spec 014 i 015). Aquest sistema local i la gestió de conflictes (ex. `CONFLICTO_TRASPÀS`) no s'ha començat a programar. És totalment Cloud-Dependent i caurà si no hi ha dades 5G.
  * **Mode "Cambra / Escàner" (Spec 020):** La captura de QR de maquinària, NIMA o tiquets des del mòbil per identificar directament la base de dades no té lògica Backend ni crides d'IA establertes al servidor.
  * **Inventari Ceg (Spec 014):** Els traspassos de material entre furgonetes per Bluetooth o offline (recolzats als `EDGE` cases) són 100% absents.

---

## 3. Àmbit SUPERADMIN / PLATAFORMA (Ruta: `/superadmin`)
**Usuaris objectiu:** Propietari de la plataforma (SaaS), Devs.
**Specs Associades:** 021, 022, 023, 024.

### Veredicte CTO: ❌ NO IMPLEMENTAT / ORFE
La gestió multitenant és on més mancances crítiques de seguretat s'han deixat a l'aire.

* **El que HI ÉS:**
  * Només un endpoint bàsic: `tenants.py` per llistar empreses.
  * Fitxer de `telemetria.py` pel consum de dades, completament mock.

* **El que FALTA:**
  * **Seguretat Multi-Tenant (RLS PostgreSQL):** Tota la plataforma assumeix que està filtrant les dades manualment via Python (`where empresa_id == ...`). La Spec exigeix obligatòriament la injecció de variables al nucli de PostgreSQL `app.current_empresa_id` per evitar fuites de dades (*Data Leaks*). Això posa en risc la base de dades multitenant.
  * **Superadmin KPIs (Spec 022):** Absent. No hi ha taulers reals agregats d'ús.
  * **Bot de Telegram (Spec 023):** Zero codi per al bot de client final.
  * **Workers Asíncrons (Spec 024):** Tot es fa síncron des de FastAPI (bloquejant l'usuari). Celery/Redis, exigit per a la IA i els PDF, no està muntat.

---

## CONCLUSIÓ TÈCNICA FINAL
El sistema pateix la "Síndrome de l'Esquelet". Totes les pantalles d'usuari existeixen i el sistema permet fer demostracions fàcils (perquè es pot navegar, clicar i veure llistats). 
Però tan bon punt s'intenta forçar els límits de negoci reals del carrer (quedar-se sense internet a l'obra, auditar l'IA amb dades autèntiques, o fer tancaments trimestrals AEAT), el sistema trenca perquè la Base (Mocks i Crides Directes) no suporta la càrrega funcional. Cal abandonar la creació visual i dedicar un sprint exclusiu al **Blindatge del Backend** (RLS, IndexedDB Sync, i Asincronia).
