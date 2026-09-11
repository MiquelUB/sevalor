# Walkthrough — Sevalor Suite (Fundació, RLS i Nucli d'Autenticació)

S'han completat amb èxit totes les tasques del **Bloc 1 (Fundació)** i del **Bloc 2 (Backend Core i Autenticació)** seguint la [Constitució](file:///media/akaun/Project_1/SEVALOR/sdd_sevalor/constitution.md) de Sevalor Suite i el pla de tasques atòmiques.

---

## 🚀 Canvis Principals Realitzats

### 1. Unificació de Marca i Governança Documental
- Adaptació de la documentació mestre a `sdd_sevalor`:
  - [`AGENTS.md`](file:///media/akaun/Project_1/SEVALOR/sdd_sevalor/AGENTS.md): Unificació sota Sevalor Suite i directrius d'agent.
  - [`constitution.md`](file:///media/akaun/Project_1/SEVALOR/sdd_sevalor/constitution.md): Els 7 mandats innegociables (Zero Mock Data, RLS, Web Crypto API, Veri*factu SHA-256, Sobirania Hetzner, etc.).
  - [`sevalor-guardian.md`](file:///media/akaun/Project_1/SEVALOR/sdd_sevalor/skills/sevalor-guardian.md): Guia de blindatge i compliment tècnic.
  - [`tareas-implementacio-sevalor.md`](file:///media/akaun/Project_1/SEVALOR/sdd_sevalor/tareas-implementacio-sevalor.md): Traçabilitat de tasques atòmiques.

---

### 2. Infraestructura i Docker Compose (Tasca 1.1)
- Fitxer [`docker-compose.yml`](file:///media/akaun/Project_1/SEVALOR/docker-compose.yml):
  - `sevalor_db`: PostgreSQL 16 amb extensions PostGIS i pgvector sobre el port `5433` (evitant col·lisions de ports locals).
  - `sevalor_redis`: Redis 7 sobre el port `6380`.
  - `sevalor_postgrest`: Capa REST PostgREST v12.
  - `sevalor_whisper`: faster-whisper INT8 CPU-only per a Hetzner CPX21.
  - `sevalor_backend`: Servei FastAPI asíncron.
- Fitxers [`env.example`](file:///media/akaun/Project_1/SEVALOR/.env.example) i `.env`.

---

### 3. Esquema Físic de Base de Dades i RLS Global (Tasques 1.2 a 1.7)
A [db/migrations/](file:///media/akaun/Project_1/SEVALOR/db/migrations):
- `001_core_multitenant.sql`: Taules `empreses`, `slots_jornada` i `usuaris` amb UUIDs, checks de rols i clau única composta `UNIQUE (empresa_id, nif)`. Creació del rol `sevalor_app` sense atributs superusuari.
- `002_rls_global.sql`: `FORCE ROW LEVEL SECURITY` a totes les taules amb aïllament estricte per `app.current_empresa_id`.
- `003_clients_finques.sql`: `clients` amb IBAN xifrat simètric i `finques` amb tipus geomètric `coords_gps GEOMETRY(Point, 4326)` i índex espacial GiST.
- `004_magatzem.sql`: `articles` amb `parent_material_id` autorreferencial per a retalls continus de tubs/cables, `magatzems`, `estocs_magatzem` i `eines_custodia`.
- `005_flota.sql`: `vehicles`, `estancies_substitucio` i `tiquets_carburant` amb mandat de doble evidència fotogràfica (`tiquet_foto_path` i `odometre_foto_path`).
- `006_sif_inmutable.sql`: `registre_esdeveniments_sif` (Veri*factu RD 1007/2023) amb trigger PL/pgSQL `trg_sif_block_modifications` que bloca de forma atòmica qualsevol intent d'`UPDATE` o `DELETE`.

---

### 4. Backend FastAPI i Middleware Multi-Tenant (Tasques 2.1, 2.3, 2.5)
A [backend/](file:///media/akaun/Project_1/SEVALOR/backend):
- `app/core/db.py`: Conexió asíncrona SQLAlchemy 2.0 (`asyncpg`) i funció `set_tenant_context` que commuta de forma segura al rol `sevalor_app` i injecta `app.current_empresa_id`.
- `app/middleware/tenant.py`: Middleware que intercepta cada petició i resol l'empresa a partir de capçaleres, JWT o subdomini.
- `app/api/v1/health.py`: Healthcheck de base de dades i serveis.
- `app/api/v1/operari_auth.py`:
  - `POST /api/v1/operari/enrolar`: Generació d'OTP de 6 dígits i enrolament de dispositiu.
  - `POST /api/v1/operari/login-pin`: Login amb PIN de 4 dígits i emissió de JWT.
  - `POST /api/v1/operari/recuperar-pin`: Generació de PIN temporal i registre d'incidència.

---

### 5. Client Offline i Web Crypto API (Tasca 2.4)
- [`pwa/src/lib/crypto.ts`](file:///media/akaun/Project_1/SEVALOR/pwa/src/lib/crypto.ts):
  - Derivació de claus amb **PBKDF2 (100.000 iteracions, SHA-256)** a partir del PIN de 4 dígits.
  - Xifratge simètric **AES-GCM de 256 bits** amb IV aleatori de 12 bytes.
  - Generació i verificació de seguretat contra el bloc sentinella `SEVALOR_SENTINEL`.
  - Xifratge de tokens per a persistència segura a IndexedDB (Zero Plaintext Tokens).

---

## 🧪 Resultats de les Proves de Verificació

### Suite de Tests de Backend (11 tests passats en verd)
Comanda d'execució:
```bash
docker run --rm --network host -v /media/akaun/Project_1/SEVALOR/backend:/app -w /app -e POSTGRES_PORT=5433 -e POSTGRES_SERVER=localhost campopro-backend:latest python run_tests.py
```
Sortida de resultats:
```text
test_health_check_endpoint (test_api.TestAPIEndpoints) ... ok
test_root_endpoint (test_api.TestAPIEndpoints) ... ok
test_enrolar_operari_existent (test_operari_auth.TestOperariAuth) ... ok
test_enrolar_operari_inexistent (test_operari_auth.TestOperariAuth) ... ok
test_login_pin_incorrecte (test_operari_auth.TestOperariAuth) ... ok
test_login_pin_valid (test_operari_auth.TestOperariAuth) ... ok
test_recuperar_pin (test_operari_auth.TestOperariAuth) ... ok
test_tenant_isolation_rls (test_rls.TestMultiTenantRLS) ... ok
test_sif_delete_is_forbidden (test_sif.TestSIFImmutability) ... ok
test_sif_record_integrity (test_sif.TestSIFImmutability) ... ok
test_sif_update_is_forbidden (test_sif.TestSIFImmutability) ... ok

Ran 11 tests in 3.118s
OK
```

### Prova Criptogràfica Offline Web Crypto API (Tasca 2.4)
Comanda d'execució:
```bash
node test_crypto.mjs
```
Sortida de resultats:
```text
=== INICIANT TEST CRIPTOGRÀFIC TASCA 2.4 (SEVALOR_SENTINEL) ===
1. Generant bloc sentinella xifrat amb PBKDF2 (100.000 iteracions) + AES-GCM-256...
   Bloc generat en 29.97 ms. IV: d83c3ceb126e117e02afc435
2. Verificant desbloqueig offline amb PIN correcte (4826)...
   -> OK! Desxifratge del sentinella 'SEVALOR_SENTINEL' reeixit.
3. Verificant bloqueig amb PIN incorrecte (1234)...
   -> OK! Accés denegat correctament per fallada d'autenticitat AES-GCM.
4. Verificant xifratge de token JWT d'operari per a IndexedDB...
   -> OK! Token JWT xifrat i desxifrat amb integritat absoluta.

✅ TOTS ELS CRITERIS DE LA TASCA 2.4 S'HAN VALIDAT AMB ÈXIT.
```
