# AGENTS.md — Sevalor Suite (Manual Suprem de Desenvolupament i Regles de l'Agent)

> **NORMA SUPREMA:**  
> **1. LLEGEIX OBLIGATÒRIAMENT `constitution.md`, LA `spec.md` ACTIVA, EL `plan.md` I LES `tasks.md` ESPECÍFIQUES DE CADA SPEC ABANS DE PROPOSAR O TOCAR CODI.**  
> Si detectes qualsevol contradicció entre el codi existent i l'especificació o la constitució, **l'especificació i la constitució SEMPRE prevalen.**  
> **2. REALITZACIÓ I VALIDACIÓ NETA DE TESTS (MANDATORI):** És obligatori executar tots els tests de la fase o mòdul i passar-los al 100% nets (sense falsos positius, sense mocks prohibits, sense errors d'event loop i verificant RLS) abans de donar cap tasca per tancada.  
> **3. ACTIVACIÓ MANDATÒRIA DE SKILLS:** És mandatori carregar i aplicar la skill especialitzada corresponent (`frontend-design`, `systematic-debugging`, `security-and-hardening`, `security-review`, `supabase-postgres-best-practices`) segons el tipus de tasca abans de tocar codi (veure §8).

---

## 🏗️ 1. Identitat, Arquitectura i Desplegament

### 1.1 El Projecte
**Sevalor Suite** és una plataforma B2B integral multi-vertical (*CampoPro* per a agricultura i reg, *ElectricPro* per a baixa tensió REBT, *HydroPro* per a fontaneria, *BuildingPro* per a edificació) dissenyada per a empreses de serveis tècnics amb quadrilles al terreny (5 a 50 operaris).

### 1.2 Infraestructura y Despliegue en Producción
- **Proveedor Cloud:** **Hetzner Cloud** (instancia CPX21 en Falkenstein / Nuremberg, Alemania). Cumplimiento estricto del RGPD/GDPR (datos siempre en la UE).
- **Orquestador:** **EasyPanel** sobre Docker.
- **Topología de Microservicios:**
  1. `pwa` (Next.js 14): Servidor frontend que entrega las 3 interfaces: `/operari` (móvil offline), `/gestio` (dashboard técnico) y `/superadmin` (CRM SaaS).
  2. `backend` (FastAPI + Uvicorn): API REST asíncrona (`asyncpg`).
  3. `db` (PostgreSQL 15): Base de datos con Row Level Security (RLS) mandatorio.
  4. `redis` (Redis 7): Cola de tareas, caché de sesiones, lista negra de JWT y rate-limiting.
  5. `celery_worker` + `celery_beat`: Procesamiento en segundo plano (PDFs con ReportLab, OCR, webhooks).
  6. `bot` (aiogram 3.x): Servicio asíncrono para el canal de Telegram con el cliente final.
  7. `nginx`: Reverse Proxy con SSL automático (Let's Encrypt), cabeceras CSP y filtrado.
- **Almacenamiento de Archivos:** **Memoria interna de la empresa y servidor Hetzner Cloud en Alemania** (volúmenes en disco local del servidor bajo `/data/<empresa_id>/...` y `/docs/<empresa_id>/...`, con copias de seguridad semanales automáticas cada domingo; eliminación total de AWS S3 para estricto cumplimiento del RGPD y soberanía de datos).

---

## 🐍 2. Ecosistema Python (Backend & Workers)

### 2.1 Entorno y Versión
- **Python 3.12+** obligatorio.
- Estándar **PEP8** riguroso, tipado estático completo (**Type Hints** estrictos) y docstrings en formato Google.

### 2.2 Librerías de Desarrollo (`requirements.txt`)
| Librería | Versión | Uso / Justificación |
|---|---|---|
| `fastapi` | `>=0.110.0` | Framework web reactivo y asíncrono |
| `uvicorn[standard]` | `>=0.29.0` | Servidor ASGI de alto rendimiento |
| `pydantic` & `pydantic-settings` | `>=2.0.0` | Validación estricta de esquemas de datos y settings |
| `asyncpg` | `>=0.29.0` | Driver nativo y ultraveloz para PostgreSQL (pool asíncrono) |
| `SQLAlchemy` | `>=2.0.28` | Capa ORM / Core para consultas tipadas |
| `celery` | `>=5.3.0` | Gestión de colas asíncronas para trabajos pesados |
| `redis` | `>=5.0.0` | Conexión a Redis para Celery, caché y tokens |
| `slowapi` | `>=0.1.9` | Rate limiting de endpoints acoplado a Redis |
| `PyJWT` | `>=2.8.0` | Generación y verificación de tokens JWT |
| `passlib[bcrypt]` & `bcrypt` | `>=4.1.2` | Hashing seguro de contraseñas y PINs de operario |
| `aiogram` | `>=3.4.1` | Framework asíncrono para el Bot de Telegram |
| `reportlab` | `>=4.0.0` | Generación de facturas Veri*factu e informes en PDF |
| `httpx` | `>=0.27.0` | Cliente HTTP asíncrono (comunicación con LM Studio y APIs internas) |
| `bleach` | `>=6.1.0` | Sanitización HTML contra ataques XSS e inyecciones |
| `filetype` | `>=1.2.0` | Detección real de MIME types por Magic Bytes |
| `tenacity` | `>=8.2.3` | Reintentos exponenciales para conexiones a BD e IA local |
| `python-multipart` | `>=0.0.9` | Procesamiento de formularios y subida de ficheros |

### 2.3 Librerías de Testing y Calidad de Código
| Herramienta | Uso / Comando |
|---|---|
| `pytest` | Framework de pruebas unitarias y de integración |
| `pytest-asyncio` | Soporte nativo para tests asíncronos (`@pytest.mark.asyncio`) |
| `pytest-cov` | Medición y reporte de cobertura de código (mínimo 80% exigido) |
| `httpx` (`AsyncClient`) | Cliente de testing para lanzar peticiones a endpoints FastAPI sin levantar servidor |
| `ruff` | Linter y formateador ultrarrápido (`ruff check .` y `ruff format .`) |
| `mypy` | Comprobador de tipos estáticos (`mypy app/ --strict`) |

---

## 🔒 3. Especificaciones Críticas de Seguridad (Zero-Trust)

### 3.1 Base de Datos & Multi-Tenant (RLS)
- **RLS activado obligatoriamente en el 100% de las tablas que posean `empresa_id`.**
- Cada petición autenticada debe inyectar la variable de sesión:  
  `SET LOCAL app.current_empresa_id = '<uuid>';`  
  Queda prohibido confiar en filtros manuales `WHERE empresa_id = ...` en el código de FastAPI; el aislamiento lo garantiza PostgreSQL.

### 3.2 Autenticación y Criptografía de Tokens
- **Técnicos de Campo (PWA):** Autenticación por PIN (4 dígitos) + Teléfono.  
  *Seguridad Offline:* Al operar sin conexión, los tokens almacenados en IndexedDB **NUNCA irán en texto plano**. Se cifran mediante **AES-GCM 256 bits (Web Crypto API)** derivando la clave criptográfica mediante PBKDF2 del PIN del usuario.
- **Ingeniería y Superadmin:** Email + Password fuerte (bcrypt) + **2FA TOTP obligatorio**.
- **Superadmin:** IP Allowlist estricta en base de datos. Las sesiones de impersonación tienen una duración máxima de 2 horas, quedan registradas en la tabla `auditoria` y operan en modo solo lectura sobre datos bancarios.
- **Ciclo de Vida JWT:** Access Tokens de 15 minutos de caducidad. Refresh Tokens almacenados en cookies `HttpOnly`, `Secure`, `SameSite=Strict`. Lista negra activa en Redis para revocación inmediata en logout.

### 3.3 Rate Limiting y CORS
- Rate Limiting mediante `slowapi`:
  - Endpoints generales: máx. 100 req/min por IP.
  - Endpoints de login/autenticación: máx. 5 intentos/min.
  - Endpoints de inferencia IA (LM Studio): máx. 10 req/min por usuario.
- CORS restringido exclusivamente a los dominios configurados en `empreses.domini_custom` y al frontend de EasyPanel.

### 3.4 Subida Segura de Archivos
- Validación obligatoria mediante **Magic Bytes** (`filetype`), rechazando archivos basados únicamente en la extensión.
- Nombres de archivo sanitizados y reemplazados por UUIDs v4 (nunca conservar nombres originales del cliente).
- Límites estrictos: Fotos máx. 10MB, Planos técnicos máx. 50MB.

### 3.5 Blindaje de la IA Local (Anti Prompt-Injection)
- Prohibido concatenar directamente entradas de usuario sin validar en el System Prompt.
- Sanitización de strings antes de llamar a LM Studio (eliminación de caracteres de control y límite de caracteres).
- Salidas del modelo validadas obligatoriamente contra esquemas **Pydantic**.
- Principio **Human-in-the-Loop**: La IA propone y redacta, pero ninguna orden de compra o factura se emite sin autorización humana explícita.

---

## 📜 4. Reglas Innegociables de Desarrollo

1. **Protocol Previ de Lectura i Tasques:**
   - Lee `constitution.md`, la `spec.md` correspondiente, `plan.md` y el fichero `tasks.md` de cada especificación antes de tocar o generar código.
   - Si vas a resolver un bug, consulta previamente la documentación en `docs/errors/ERRORS.md`.
2. **ZERO MOCK DATA (Tolerancia Cero a Datos Ficticios):**
   - **PROHIBIDO introducir datos hardcodeados o "dummy" en componentes o endpoints.**
   - Si no existen datos en la base de datos o en la caché offline, la interfaz debe mostrar estados vacíos reales (*Empty States*).
3. **Diseño Camaleón (Chameleon UI Engine):**
   - Prohibido hardcodear colores de marca (`#1b4332`, `#0284c7`, etc.) en Tailwind.
   - Usar variables CSS HSL dinámicas (`--color-primary`, `--color-secondary`, `--color-accent`) inyectadas según la empresa compradora.
4. **Respeto a las Fases del SDD:**
   - Prohibido saltar a una nueva fase o escribir código si la fase previa no ha sido validada explícitamente por el usuario.
   - Todo cambio en el código debe estar respaldado por su tarea (`tasks.md`) y su especificación (`spec.md`).

---

## 🛠️ 5. Comandos de Verificación y Testing

### Ejecución de Pruebas Unitarias y Cobertura (Backend)
```bash
cd backend
# Ejecutar toda la suite de tests
pytest -v

# Ejecutar con reporte de cobertura
pytest --cov=app tests/ --cov-report=term-missing

# Ejecutar tests asíncronos específicos
pytest tests/api/test_auth.py -k "test_login_pin" -v
```

### Calidad, Linter y Tipos
```bash
cd backend
# Linter y chequeo de estilo
ruff check .
# Comprobación estricta de tipos
mypy app/ --strict
```

### Verificación del Frontend (PWA / Next.js)
```bash
cd pwa
# Linter de Next.js
npm run lint
# Compilación y verificación estricta de tipos TypeScript
npm run build
```

---

## 🏁 6. Definición de Hecho (Definition of Done)

Para que el agente pueda dar por concluida cualquier tarea:
- [ ] La especificación activa (`spec.md`), `plan.md` y `tasks.md` se cumplen en su totalidad según la notación EARS.
- [ ] Se cumple estrictamente la regla *Zero Mock Data* (sin datos ficticios).
- [ ] **TESTS NETS MANDATORIS:** Todos los tests unitarios y de integración se han ejecutado y están 100% en verde (`pytest -v`), sin warnings de event loop y con aislamiento RLS certificado según la normativa de la Fase 0.
- [ ] `ruff check .` y `mypy app/` no arrojan advertencias ni errores.
- [ ] `npm run build` en el frontend compila sin errores.
- [ ] Se respetan el aislamiento RLS y el cifrado de tokens para modo offline.
- [ ] Se emite un informe final con: tarea completada, archivos modificados, resultados de los tests y estado de la especificación.

---

## 🛑 7. NORMATIVA D'AUDITORIA I TESTS (MANDATORI)

D'acord amb la resolució de la Fase 0 (Auditoria Zero Mock), queda establerta la següent regla de protocol d'obligat compliment per a l'Agent:

**Al finalitzar qualsevol fase i ABANS de procedir a l'execució i validació dels tests automatitzats (Pytest / Playwright), TENS L'OBLIGACIÓ ABSOLUTA de llegir el document `sdd_sevalor/Auditoria_i_Normativa_Tests_Backend.md`.**

Aquesta lectura prèvia garantirà que no es tornin a tolerar falsos positius, emmascaraments d'errors de connexió asíncrona (event loops) i vulneracions de la regla *Zero Mock* o *RLS*. Si no es compleix aquesta normativa, la validació de la fase serà nul·la.

---

## 🧩 8. Matriu d'Activació Mandatòria de Skills per Tipus de Tasca

Per garantir la màxima excel·lència tècnica, seguretat i coherència arquitectònica, l'agent té l'OBLIGACIÓ d'activar i seguir els procediments de la skill especialitzada corresponent en cadascun dels següents escenaris:

| Tipus de Tasca d'Implementació | Skill Mandatòria | Ruta del recurs | Objectiu i Protocol Obligatori |
| :--- | :--- | :--- | :--- |
| **Disseny, Maquetació o Redisseny de Frontend (PWA / Dashboard / Superadmin)** | `frontend-design` | [`.agents/skills/frontend-design/SKILL.md`](file:///.agents/skills/frontend-design/SKILL.md) | **Prohibició d'estètica genèrica d'IA.** Aplicar el disseny camaleònic amb tokens HSL (`--color-primary`), tipografia intencional, ritme vertical i micro-interaccions deliberades. Estats buits reals obligatoris. |
| **Resolució de Bugs, Fallades de Tests o Comportaments Inesperats** | `systematic-debugging` | [`.agents/skills/systematic-debugging/SKILL.md`](file:///.agents/skills/systematic-debugging/SKILL.md) | **Llei de Ferro: "NO FIXES WITHOUT ROOT CAUSE".** Prohibit aplicar pegats superficials o pal·liar símptomes. Cal aïllar científicament la causa arrel, documentar la hipòtesi i arreglar d'arrel abans de tocar codi. |
| **Autenticació, Sessions, Criptografia, Pujada d'Arxius i Endpoints Sensibles** | `security-and-hardening` | [`.agents/skills/security-and-hardening/SKILL.md`](file:///.agents/skills/security-and-hardening/SKILL.md) | **Blindatge preventiu Zero-Trust.** Xifratge AES-GCM 256 bits a IndexedDB (derivat per PBKDF2 del PIN), llista negra Redis per JWT, validació estricta de fitxers (magic bytes, doble extensió) i prevenció d'injecció. |
| **Auditoria de Codi, Control d'Accessos i Verificació de Vulnerabilitats** | `security-review` | [`.agents/skills/security-review/SKILL.md`](file:///.agents/skills/security-review/SKILL.md) | **Checklist sistemàtic OWASP Top 10.** Verificació de blindatge RBAC per rols (Boss vs. Enginyer vs. Operari) i aïllament d'endpoints financers. |
| **Modelat de Base de Dades, Migracions Alembic i Polítiques RLS de PostgreSQL** | `supabase-postgres-best-practices` | [`.agents/skills/supabase-postgres-best-practices/SKILL.md`](file:///.agents/skills/supabase-postgres-best-practices/SKILL.md) | **PostgreSQL 16 & RLS segur.** Disseny idempotent de taules, regles RLS multi-tenant infranquejables (`economics_boss_only`), ús correcte de bloquejos concurrents (`SELECT FOR UPDATE`) i prevenció de deadlocks. |

> **Regla d'or:** Abans d'iniciar qualsevol tasca de `tasks.md`, l'agent ha d'identificar quina d'aquestes skills governa la intervenció, consultar el seu `SKILL.md` i executar el desenvolupament sota les seves directrius.

---

## 🔌 9. Eines MCP per a la Validació Zero Mock en Viu

Per fer complir de manera implacable la **Regla d'Or Zero Mock**, l'agent disposa i ha d'utilitzar els següents servidors MCP integrats a la plataforma:

1. **`chrome-devtools` (Google Chrome Headless + PWA):**
   - **Objectiu:** Provar en navegador real (no simulat) la interfície web i PWA de Sevalor (`/operari`, `/gestio`, `/superadmin`).
   - **Casos d'ús obligatoris:**
     - Validar fluxos de login reals (PIN de 4 dígits per a operaris, contrasenya + 2FA per a gestió).
     - Comprovar formularis crítics com les entrades a magatzem, creació d'albarans, assignació d'ordres de treball i fitxatge.
     - Inspeccionar les peticions de xarxa en viu (`list_network_requests`) per verificar que les dades viatgen contra l'API FastAPI real i no provenen d'objectes mock.
     - Detectar errors de JavaScript a la consola (`list_console_messages`) i validar el renderitzat visual del Chameleon UI (`take_screenshot`).

2. **`postgres` (PostgreSQL 15/16 Multi-Tenant):**
   - **Objectiu:** Accés directe en viu a la instància PostgreSQL (`postgresql://postgres:postgres@127.0.0.1:5433/sevalor`).
   - **Casos d'ús obligatoris:**
     - Comprovar que les dades creades a través de la UI o de l'API s'han persistit físicament i amb la integritat referencial esperada.
     - Validar que les regles RLS bloquegen l'accés creuat entre empreses executant consultes amb `SET LOCAL app.current_empresa_id = '<uuid>';`.
     - Confirmar que els *Empty States* del frontend reflecteixen l'estat real d'una taula buida a la base de dades.

