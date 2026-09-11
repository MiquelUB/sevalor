# AGENTS.md — Sevalor Suite (Manual Suprem de Desenvolupament i Regles de l'Agent)

> **NORMA SUPREMA:**  
> **LLEGEIX OBLIGATÒRIAMENT `constitution.md` I LA `spec.md` ACTIVA ABANS DE PROPOSAR O TOCAR CODI.**  
> Si detectes qualsevol contradicció entre el codi existent i l'especificació o la constitució, **l'especificació i la constitució SEMPRE prevalen.**

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

1. **Protocolo Previo de Lectura:**
   - Lee `constitution.md` y la `spec.md` correspondiente antes de tocar o generar código.
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
- [ ] La especificación activa (`spec.md`) se cumple en su totalidad según la notación EARS.
- [ ] Se cumple estrictamente la regla *Zero Mock Data* (sin datos ficticios).
- [ ] Todos los tests unitarios y de integración están en verde (`pytest -v`).
- [ ] `ruff check .` y `mypy app/` no arrojan advertencias ni errores.
- [ ] `npm run build` en el frontend compila sin errores.
- [ ] Se respetan el aislamiento RLS y el cifrado de tokens para modo offline.
- [ ] Se emite un informe final con: tarea completada, archivos modificados, resultados de los tests y estado de la especificación.

---

## 🛑 7. NORMATIVA D'AUDITORIA I TESTS (MANDATORI)

D'acord amb la resolució de la Fase 0 (Auditoria Zero Mock), queda establerta la següent regla de protocol d'obligat compliment per a l'Agent:

**Al finalitzar qualsevol fase i ABANS de procedir a l'execució i validació dels tests automatitzats (Pytest / Playwright), TENS L'OBLIGACIÓ ABSOLUTA de llegir el document `sdd_sevalor/Auditoria_i_Normativa_Tests_Backend.md`.**

Aquesta lectura prèvia garantirà que no es tornin a tolerar falsos positius, emmascaraments d'errors de connexió asíncrona (event loops) i vulneracions de la regla *Zero Mock* o *RLS*. Si no es compleix aquesta normativa, la validació de la fase serà nul·la.
