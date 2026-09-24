# Pla Director de Desplegament: Frontend i PWA (Fase UI)

Havent completat i auditat amb èxit absolut l'escut multitenant i els fonaments del Backend (PostgreSQL RLS + FastAPI), procedim a planificar la construcció de les interfícies gràfiques (UI).

Seguint l'estricta política del **Zero Mock** i respectant les **Speccs oficials** com a única font de veritat, el Frontend no simularà dades. Totes les pantalles s'alimentaran directament de l'API i els tests automatitzats (E2E) interactuaran amb instàncies reals de la BBDD.

## 🏗️ Pila Tecnològica Recomanada
Donades les capacitats reactives, Offline-First per a la PWA i cartografia interactiva, la pila base recomanada és:
* **Framework Web & PWA:** Next.js (React) o Nuxt (Vue) amb mode Offline-First (Service Workers + IndexedDB).
* **Estilització:** TailwindCSS + components accessibles (ex: shadcn/ui).
* **Cartografia (Feines i Rutes):** Mapbox GL JS / Leaflet.
* **Testing E2E (Zero Mock):** Playwright (simulant dispositius mòbils per a la PWA i navegadors desktop per a l'Oficina).
* **Estat:** Zustand (React) o Pinia (Vue) + React Query/TanStack per sincronització de l'API.

---

## 🗺️ Fases de Desplegament Seqüencial

Igual que al backend, avançarem validant les dependències abans de construir processos complexos.

### Fase 1: Arquitectura Base i Autenticació
Construcció de les "carcasses" d'aplicació (Shells) i passarel·les d'entrada.
* **Spec 021:** Onboarding de SuperAdmin (Dashboard Global).
* **Spec 019:** Login de la PWA (Pantalla mòbil de PIN numèric de 4 dígits).
* **Configuració UI:** Interceptors JWT, rutes protegides i layouts responsius.
* 🧪 **Auditoria de Test 1:** *Playwright E2E testejant login invàlid, bloqueig al 4t intent i login reeixit injectant JWT al navegador.*

### Fase 2: Taulers de Comandament i Entitats Mestres (Oficina)
Construcció dels panells d'administració per omplir la base de dades.
* **Spec 008, 002, 003:** Taules CRUD per a Operaris, Clients i Proveïdors.
* **Spec 006, 004:** Gestió de la Flota (Vehicles) i Control d'Estoc (Almagatzem i Articles).
* 🧪 **Auditoria de Test 2:** *Creació end-to-end d'un Article, un Client i un Vehicle des de la UI d'oficina validant que l'API retorna HTTP 201.*

### Fase 3: Operativa i Cartografia de l'Oficina
El cor visual del cap i dels enginyers.
* **Spec 001 i 005:** Dashboard de Mapes, ubicació geogràfica de les "Ordres de Treball", i llistat de Feines amb prioritats de colors.
* **Spec 010:** Gestor de Plànols (PDF/CAD visualitzadors web).
* 🧪 **Auditoria de Test 3:** *Assignació visual d'una Feina a un Operari des del Frontend i verificació de la rendició del mapa base.*

### Fase 4: Operativa de Camp (PWA Mòbil Offline-First)
El sistema tàctic usat pels operaris al carrer.
* **Spec 013 i 015:** Pantalla d'inici de jornada (Start/Stop) i assignació del Vehicle diari.
* **Spec 014 i 017:** Pantalla de "Picking" (escanejar/validar materials) i visualització de plànols des del mòbil.
* **Spec 016, 018, 020:** Botó d'emergència (Incidències i Avaries), fer fotografies (Camera API) i tiquets de dieta.
* 🧪 **Auditoria de Test 4:** *Simulació de dispositiu mòbil: l'operari fa login, pica material, inicia la feina i dispara una incidència "VERMELL". S'audita que els botons reaccionin a l'estat.*

### Fase 5: Tancament, IA i Comunicacions
Les eines financeres i d'assistència predictiva.
* **Spec 007:** Facturació i visualització de la base imposable i Veri*Factu.
* **Spec 009 i 012:** Safata d'entrada de Notificacions i la interfície gràfica de xat de Copilot (Celery/RAG UI).
* 🧪 **Auditoria de Test 5:** *Finalització del flux financer E2E i generació visual de l'esborrany de la factura.*

---

## 🛠️ Regles de Desenvolupament (SDD + Zero Mock Frontend)
1. **Sense Dades Estàtiques (No Mocking):** Cap component UI usarà llistats `json` inventats als arxius per dissenyar l'aspecte. Es nodrirà tot directament de trucades reals a l'API amb una BBDD `TESTING=1`.
2. **Components Guiats per Especificacions:** "Si la UI contradiu l'especificació, l'especificació preval". Qualsevol omissió en disseny de la Spec s'ha de refer i auditar abans de donar el component per bo.
3. **Passos de Qualitat:** No es permetrà passar de la Fase N a la N+1 sense presentar un *Trace d'Auditoria E2E (Playwright)* en verd 100%.
