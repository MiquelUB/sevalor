# PLA D'ACCIÓ CTO: Refactorització Iterativa per Fases

Aquest pla defineix el full de ruta tècnic per transformar els "Esquelets/Mocks" actuals en un codi de producció real, seguint les especificacions arquitectòniques de SEVALOR. Cada fase és autònoma, aborda un problema estructural, defineix els endpoints implicats, i exigeix la creació d'un test real.

---

## FASE 1: Blindatge Estructural (Row Level Security - RLS)
**Objectiu:** Evitar fuites de dades (*Data Leaks*) entre empreses (Tenants) a nivell de PostgreSQL, eliminant la dependència de filtrar manualment amb `empresa_id` a cada línia de codi de FastAPI.
**Specs Associades:** 021 (Superadmin).

* **Impacte al Codi:** Afecta a absolutament TOTS els arxius de `backend/app/api/v1/gestio/` i `operari_pwa/`. Simplificarà les consultes SQLAlchemy (traient `where empresa_id == ...`) i injectarà el context mitjançant `SET app.current_tenant`.
* **Endpoints a Validar:** Tots els GET/POST existents hauran d'utilitzar el nou *Dependency Injector* de BBDD.
* **Test de Validació Real (TDD):**
  * *Acció:* Crear un test automatitzat a `pytest` on el Tenant A intenta fer un `GET /api/v1/gestio/clients/{id_del_tenant_B}`.
  * *Resultat Esperat:* La base de dades (no Python) ha de retornar *NotFound* (0 rows) automàticament, verificant l'aïllament.

---

## FASE 2: Motor Asíncron (Workers & Redis)
**Objectiu:** Desbloquejar l'API síncrona actual. La IA del Copilot, el processament de PDF/Imatges i les notificacions push han de córrer en segon pla (Celery + Redis) per garantir respostes de l'API menors a 200ms.
**Specs Associades:** 024 (Workers), 012 (Copilot), 009 (Notificacions).

* **Impacte al Codi:** Refactorització d'`api/v1/gestio/copilot.py` i de l'endpoint OCR (`magatzem.py`). Creació del directori `backend/app/workers/`.
* **Endpoints a Validar:**
  * Modificar `POST /api/v1/gestio/magatzem/albara/ocr` perquè retorni un `task_id` HTTP 202 Accepted.
  * Crear `GET /api/v1/workers/status/{task_id}`.
* **Test de Validació Real (TDD):**
  * *Acció:* Enviar 5 albarans PDF massius simultanis.
  * *Resultat Esperat:* L'API retorna el 202 a l'instant. Un test monitoritza el Redis per veure com Celery processa els 5 fitxers a la vegada. Si es penja un fitxer, Celery el reintenta (*Retry Strategy*) sense tombar el backend de SEVALOR.

---

## FASE 3: Motor Offline-First (Sincronització de PWA)
**Objectiu:** Complir l'estricte requeriment de la Spec d'Operaris que exigeix poder treballar sense connexió a la xarxa a les obres.
**Specs Associades:** 013 a 020 (Operaris Camp).

* **Impacte al Codi:** Els endpoints d'`operari_pwa/` (com `feines.py` i `picking.py`) s'han d'adaptar per rebre lots asíncrons (*Bulk Sync*). Al frontend, cal integrar `IndexedDB` i *Service Workers* veritables per emmagatzemar la cua d'accions (Drafts).
* **Endpoints a Validar:**
  * Crear `POST /api/v1/operari_pwa/sync/push` (Puja els canvis de la IndexedDB al núvol resolent conflictes per UUID).
  * Crear `GET /api/v1/operari_pwa/sync/pull` (Descarrega la dotació del dia abans de perdre cobertura).
* **Test de Validació Real (QA):**
  * *Acció:* Activar mode *Offline* al navegador Chrome. L'operari tanca 2 feines i gasta 5 unitats de material. Connectar de nou a *Online*.
  * *Resultat Esperat:* El sistema descarrega de cop el material de la Base de Dades i verifica el conflicte si mentrestant l'estoc central s'havia quedat a zero (generant un avís d'inventari).

---

## FASE 4: Refactor Lògica "Core" - Magatzem i Proveïdors
**Objectiu:** Deslliurar-se dels fitxers React de +1000 línies i programar les regles EDGE exactes d'inventari.
**Specs Associades:** 003 i 004.

* **Impacte al Codi:** Refactor de components a `pwa/src/app/gestio/magatzem/` dividint `page.tsx` en `MagatzemTaula.tsx`, `ModalOcr.tsx`, etc. Al backend, implementar: control FEFO (First Expire First Out), quarantena de materials retornats trencats (EDGE-10) i bloquejos de proveïdor per caducitat de pòlisses (Document CAE).
* **Endpoints a Validar:**
  * Modificar `POST /picking/linies/{id}/pick-out` (Devolucions).
  * Afegir comprovacions de CAE a `POST /api/v1/gestio/proveidors/`.
* **Test de Validació Real (TDD):**
  * *Acció:* Un operari retorna un article fraccionable parcialment consumit (ex. Meitat d'un tub de silicona).
  * *Resultat Esperat:* El Backend ha d'assumir-ho com a despesa de l'obra al 100%, rebutjar tornar a posar el mig tub a l'estoc de venda i moure-ho virtualment a "Dotació Operari", just tal com diu la Spec 004.

---

## FASE 5: Tancament Comptable & AEAT (Zero-Mock Final)
**Objectiu:** Subministrar dades autèntiques a la gestoria.
**Specs Associades:** 007 i 002.

* **Impacte al Codi:** Reescriptura total d'`api/v1/gestio/comptabilitat.py`. Integració amb la llibreria oficial per signatura de factures (Veri*factu / Antifrau) exigida per Hisenda.
* **Endpoints a Validar:**
  * Crear `GET /api/v1/gestio/comptabilitat/export/aeat`
* **Test de Validació Real (TDD):**
  * *Acció:* Cridar l'exportació d'IVA mensual amb casos de "Inversió del Subjecte Passiu" on s'ha comprat ferralla a un proveïdor determinat.
  * *Resultat Esperat:* El Backend genera un XML que passa de forma perfecta la validació XSD (Schema) oficial de l'AEAT, rebutjant la factura si falta el NIF o no és VIES vàlid.
