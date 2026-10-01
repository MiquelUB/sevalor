# Recerca, Regles d'Or & Lliçons Apreses: Infraestructura Sobirana

**Macro-Feature**: `04-infraestructura-sobirana`  
**Estat**: Vigent & Obligatori  
**Referència**: `sevalor_AgentV2/specs/04-infraestructura-sobirana/`  

---

## 1. Les Tres Regles d'Or Inviolables (Golden Rules)

Qualsevol desenvolupament, refactorització o nou component relacionat amb el nucli del sistema i la governança ha de complir de manera taxativa aquestes tres directrius:

### 🌟 Regla d'Or 1: 100% Zero Mock Data (Dia 0 Real)
- **Principi**: Queda estrictament prohibit utilitzar biblioteques generadores de dades simulades (com `faker`), estructures estàtiques *hardcoded* o respostes simulades en entorns operatius.
- **Justificació**: SEVALOR és un Sistema Operatiu Empresarial per a instal·ladores on cada decisió d'assignació d'operaris, control de material o facturació té implicacions directes de negoci. L'estat inicial d'un tenant en alta és un **Dia 0 Real** buit i expectant de dades operatives verídiques.
- **Comprovació**: Tot panell (inclosos els indicadors de la Torre de Control de Superadmin) ha de nodrir-se directament de consultes a PostgreSQL, Redis o Celery. Si un comptador val `0`, ha de renderitzar `0` sense inventar usuaris ni feines fictícies.

### 🌟 Regla d'Or 2: Row Level Security (RLS) Mandatory
- **Principi**: L'aïllament multi-tenant és responsabilitat exclusiva del motor PostgreSQL mitjançant la directiva `FORCE ROW LEVEL SECURITY` aplicada a totes les taules que contenen `empresa_id`.
- **Prohibició de Filtratge Manual**: Queda TERMINANTMENT PROHIBIT afegir clàusules manuals com `WHERE empresa_id = :val` a les consultes SQLAlchemy dels repositoris de negoci. El filtratge manual a nivell d'aplicació és propens a oblits i bugs crítics de seguretat.
- **Mecanisme d'Injecció**:
  1. El middleware (`TenantMiddleware`) extreu l'`empresa_id` del token JWT firmat.
  2. La dependència de sessió (`get_db`) executa `SET ROLE sevalor_app;` per impedir que la sessió tingui privilegis de superusuari que eludeixin el RLS.
  3. S'injecta la variable de sessió mitjançant `SELECT set_config('app.current_empresa_id', :val, true);`.
  4. La política `CREATE POLICY tenant_isolation_<taula> ON <taula> USING (empresa_id = current_setting('app.current_empresa_id')::uuid)` aïlla els registres de forma inviolable.
- **Accés de Superadmin**: Quan un Superadministrador accedeix a la plataforma per a tasques de manteniment o telemetria, s'executa `RESET ROLE;` i s'activa `app.is_superadmin = true`. El Superadmin només accedeix a metadades i a l'esquema segregat `superadmin_telemetry`, mantenint un aïllament Zero-Trust respecte a les taules de clients, factures o feines.

### 🌟 Regla d'Or 3: Local Sovereign Cloud (Hetzner) — No AWS S3
- **Principi**: La totalitat dels fitxers binaris, documents legals, plànols, fotografies de camp i còpies de seguretat s'allotgen en emmagatzematge físic local sobirà a Hetzner (Falkenstein / Nuremberg - Alemanya, Unió Europea), sota les rutes `/data/<empresa_id>/...` i `/docs/<empresa_id>/...`.
- **Rebuig de Núvols Públics**: Es rebutja taxativament l'ús de serveis d'objectes externs com AWS S3, Google Cloud Storage o Microsoft Azure Blob per a dades de clients.
- **Justificació Legal i Operativa**: Garanteix el compliment escrupolós del Reglament General de Protecció de Dades (RGPD) i la LOPDGDD, suprimeix costos d'egress de xarxa impredictibles i blinda la sobirania tecnològica de la plataforma.

---

## 2. Registre d'Incidències Històriques & Lliçons Apreses

A continuació es detallen els problemes reals detectats durant les fases de desenvolupament i integració contínua (CI/CD), així com la solució definitiva implementada per evitar regressions.

### Incidència 1: Errors de Compilació a Next.js per Extensions `.ts` i Rutes Absolutes
- **Símptoma**: Les tasques de compilació de producció fallaven amb l'error:
  `An import path can only end with a '.ts' extension when 'allowImportingTsExtensions' is enabled.`
- **Causa Arrel**: Alguns fitxers de test i utilitats incloïen rutes amb extensions explícites com `import { ... } from "./src/lib/crypto.ts"`.
- **Regla d'Aplicació**:
  - En TypeScript estàndard i Next.js App Router, mai s'ha d'incloure l'extensió `.ts` ni `.js` en les importacions.
  - S'ha de respectar la configuració d'àlies de rutes definida a `tsconfig.json` (`@/...`) i evitar navegacions relatives profundes de tipus `../../../../`.

### Incidència 2: Mòduls d'Arrel No Localitzats a GitHub Actions (`PYTHONPATH`)
- **Símptoma**: Les suites de proves de backend fallaven a CI amb `ModuleNotFoundError: No module named 'bot'`.
- **Causa Arrel**: El runner de GitHub Actions executava Pytest des del directori `./backend`, de manera que els paquets situats a l'arrel del repositori (com el bot d'assistència) quedaven fora del camí de cerca de Python.
- **Regla d'Aplicació**:
  - El fitxer de flux de treball `.github/workflows/ci.yml` ha de declarar explícitament la variable d'entorn `PYTHONPATH: ${{ github.workspace }}`.
  - Els tests s'han d'executar des de l'arrel o assegurar que tots els mòduls transversals estiguin instal·lats en mode editable (`pip install -e .`).

### Incidència 3: Mòduls d'Emulació Absents a les Dependències de PWA
- **Símptoma**: Les proves del mòdul fora de línia fallaven amb `Cannot find module 'fake-indexeddb/auto'`.
- **Causa Arrel**: S'havia utilitzat el paquet per simular IndexedDB en l'entorn de Node.js sense haver-lo declarat prèviament al `package.json`.
- **Regla d'Aplicació**:
  - Qualsevol dependència utilitzada en suites de test de frontend ha de quedar fixada a `devDependencies` (com `npm install -D fake-indexeddb`).
  - No assumir mai que paquets globals o d'emulació estan disponibles per defecte al runner de CI.

### Incidència 4: Ús Obligatori de la Dependència `get_db` amb Context RLS
- **Símptoma**: Consultes de backend que retornaven resultats d'altres empreses o sessions bloquejades sense context de seguretat.
- **Causa Arrel**: Alguns endpoints feien servir directament `AsyncSessionLocal()` sense cridar la injecció de context `set_tenant_context`.
- **Regla d'Aplicació**:
  - Tots els endpoints FastAPI han d'injectar la sessió mitjançant `db: AsyncSession = Depends(get_db_with_tenant_context)` (o el seu àlies `get_db`).
  - Cap ruta de negoci pot instanciar sessions verges al marge de la dependència del contenidor FastAPI.

### Incidència 5: Oblits d'Importació d'`UploadFile` i Gestió de Fitxers Temporals
- **Símptoma**: Errors `NameError: name 'UploadFile' is not defined` en endpoints que processen documents per a l'Alta Màgica OCR.
- **Causa Arrel**: Oblit de la importació de tipus de FastAPI en afegir funcionalitats de pujada de documents.
- **Regla d'Aplicació**:
  - Sempre importar `UploadFile, File` directament des de `fastapi`.
  - Processar fitxers temporals mitjançant context managers asíncrons (`aiofiles` o escriptura en streaming) directament a la ruta sobirana `/data/<empresa_id>/...`, evitant deixar fitxers orfes a `/tmp` que saturin l'espai d'emmagatzematge del servidor.

### Incidència 6: Constrangiments de CPU-Only a Hetzner CPX21 per a IA Local (Whisper)
- **Símptoma**: Bloqueig de la instància i timeouts de més de 30 segons en sol·licitar transcripcions d'àudio durant els check-ins dels operaris.
- **Causa Arrel**: Intent d'executar models de Whisper estàndard que esperaven acceleració per maquinari GPU CUDA inexistent al node CPX21 (3 vCPUs, 4GB RAM).
- **Regla d'Aplicació**:
  - S'ha d'utilitzar exclusivament la biblioteca `faster-whisper` sota quantificació `INT8` (`compute_type="int8"`).
  - Limitar el nombre de fils de processament de la inferència per reservar CPU al servidor web Uvicorn i als workers de Celery.
  - Imposar un temps límit estricte de 15 segons (`timeout=15.0`) amb fallback textual immediat si el model no respon, per no degradar l'experiència del treballador de camp.

### Incidència 7: Downgrade Guard en la Gestió de Quotes
- **Símptoma**: Pèrdua de visibilitat o errors 500 quan un Superadministrador rebaixava el pla d'una empresa de `PRO` (15 operaris) a `STARTER` (5 operaris) tenint l'empresa 8 treballadors en actiu.
- **Causa Arrel**: Modificació directa del camp `pla_subscripcio` a la base de dades sense validar prèviament el recompte d'usuaris actius de la taula `usuaris`.
- **Regla d'Aplicació**:
  - L'endpoint `PUT /superadmin/tenants/{id}/quota` executa obligatòriament una consulta de recompte (`SELECT count(*) FROM usuaris WHERE empresa_id = :id AND estat = 'ACTIU' AND rol = 'OPERARI'`).
  - Si el nombre actiu supera la nova quota, es rebutja la petició amb codi HTTP `422 Unprocessable Entity` especificant el nombre exacte de treballadors que cal donar de baixa prèviament a `/gestio/operaris`.

### Incidència 8: Inicialització Asíncrona de Volums Sobirans (Celery Rollback)
- **Símptoma**: Registre d'empreses amb carpetes inexistents al disc quan l'operació d'onboarding coincidia amb altes taxes d'escriptura.
- **Causa Arrel**: Intent de crear les carpetes físiques de forma síncrona en el cicle de vida de la petició HTTP.
- **Regla d'Aplicació**:
  - L'onboarding insereix el registre a PostgreSQL de manera atòmica i delega la creació de carpetes a Celery (`crear_directoris_sobirans_task.delay(empresa_id)`).
  - Si la transacció de base de dades falla, s'executa un `rollback()` immediat i s'evita la creació d'arbres de directoris orfes.

---

## 3. Taula de Validacions Crítiques per al Desenvolupador

| Àmbit | Validació Obligatòria | Comportament Requerit |
| :--- | :--- | :--- |
| **API Endpoints** | Protecció per rols | `@require_roles(["SUPERADMIN"])` en tots els endpoints de governança i telemetria. |
| **Consultes DB** | Aïllament RLS | MAI incloure clàusules manuals `WHERE empresa_id = ...`. Confiar sempre en `tenant_isolation_policy`. |
| **Fitxers & Docs** | Emmagatzematge Hetzner | Tots els camins han de començar per `/data/<empresa_id>/` o `/docs/<empresa_id>/`. Prohibit S3. |
| **Subdominis** | Noms Reservats | Bloquejar `api`, `admin`, `www`, `app`, `superadmin`, `billing`, `mail`. |
| **NIF Corporatiu** | Dígit de Control | Validació algorítmica de NIF/CIF espanyol abans d'inserir a la taula `empreses`. |
| **Sessions i JWT** | Revocació a Redis | En suspendre un tenant (`SUSPES_PAGAMENT`), invalidar immediatament els tokens a la llista negra de Redis. |
| **Telemetria** | Privacitat de Dades | Prohibició estricta de desar payloads o transcripcions d'àudio a `superadmin_telemetry`. |
