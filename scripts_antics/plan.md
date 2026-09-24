# SEVALOR SUITE - Plan Arquitectónico Integral

Este documento establece la base arquitectónica de la plataforma Sevalor Suite (v4.0), emanando estrictamente de los principios de su Constitución y las 24 Especificaciones de diseño (SDDs). Actúa como guía suprema para la codificación, evitando el deute técnico y la "Síndrome del Esqueleto".

---

## 1. Módulos del Sistema y Trazabilidad (RFs)

La plataforma está dividida en 4 grandes capas de acceso, cada una gobernando un grupo específico de especificaciones y sus respectivos Requisitos Funcionals (RFs).

### A. Capa PWA (Operarios de Campo - Offline First)
*Centrada en la ejecución de obra y recolección de datos sin conexión.*
- **Autenticación Segura & PIN:** Spec 019 (24 RFs).
- **Ejecución de Obras & Jornada:** Spec 013 (24 RFs).
- **Materiales y Traspasos de Furgoneta:** Spec 014 (27 RFs).
- **Gestión de Flota (Vehículos & Combustible):** Spec 015 (22 RFs) y Spec 018 (21 RFs).
- **Planos y Marcadores en Obra:** Spec 017 (20 RFs).
- **Incidencias y Cámara/OCR de Tickets:** Spec 016 (24 RFs) y Spec 020 (22 RFs).

### B. Capa Gestió (Oficina Técnica, Secretaría e Ingenieros)
*Centrada en la gobernanza, planificación, stock central y contabilidad.*
- **Dashboard Global:** Spec 001 (46 RFs).
- **Despliegue y Obras en Mapa:** Spec 005 (34 RFs) y Spec 002 (22 RFs).
- **Inventario Central, Compras y Proveedores:** Spec 004 (52 RFs) y Spec 003 (29 RFs).
- **Flota y Mantenimiento de Vehículos:** Spec 006 (29 RFs).
- **RRHH y Cuadrantes de Operarios:** Spec 008 (34 RFs).
- **Contabilidad, Facturación y Veri*factu:** Spec 007 (25 RFs).
- **Planos Base y Capas Técnicas:** Spec 010 (26 RFs).
- **Configuración y Personalización Camaleónica:** Spec 011 (22 RFs).

### C. Capa Superadmin (SaaS y Plataforma)
*Gestión de arrendatarios (Tenants) y monitorización.*
- **Onboarding de Empresas (Tenants) y RLS:** Spec 021 (19 RFs).
- **KPIs y Telemetría del Sistema:** Spec 022 (19 RFs).

### D. Capa de Servicios Asíncronos & IA Soberana
*Motores desvinculados del Event Loop para tareas pesadas.*
- **Copilot IA (LM Studio Local):** Spec 012 (22 RFs) y Spec Auxiliar (14 RFs).
- **Workers y Colas (Celery/Redis):** Spec 024 (20 RFs).
- **Notificaciones Push y Bot de Telegram:** Spec 009 (30 RFs) y Spec 023 (23 RFs).

---

## 2. Modelo de Datos (Entidades Centrales)

El ORM (SQLAlchemy) sostiene la lógica transaccional. Todas las tablas críticas deben incluir un campo `empresa_id` como clave para el RLS.

*   **Identidad y Seguridad:**
    *   `Empresa`: Tenant principal (Configuración Camaleónica, Estado SaaS).
    *   `Usuari`: Credenciales, Rol (Operari, Enginyer, Boss), PIN Criptográfico.
*   **Gestión del Servicio (Field Service):**
    *   `Client`, `Finca`, `OrdreTreball`: Jerarquía para la ejecución del servicio.
    *   `Incidencia`, `PlanolBase`, `CapaVectorial`: Documentación in situ.
*   **Inventario y Logística (Spec 004):**
    *   `Article`, `Magatzem` (Central vs Furgoneta).
    *   `EstocMagatzem` (Cantidades físicas y reservas virtuales).
    *   `MovimentEstoc`, `AlbaraProveidor`, `Proveidor`: Trazabilidad PMP y recepciones OCR.
    *   `FullaPicking`, `LiniaPicking`: Órdenes de carga matinal de las furgonetas.
*   **Operativa HR y Flota:**
    *   `Vehicle`, `TiquetCarburant`: Control de costes.
    *   `RegistreJornadaLaboral`: Fichajes (Flujo de 30 segundos).
*   **Facturación Legal:**
    *   `FacturaCapcalera`, `FacturaLinia`, `OutboxEnviamentAEAT`: Cumplimiento inmutable de hash encadenado (RD 1007/2023).

---

## 3. Decisiones Arquitectónicas Justificadas (ADR)

### Decisión 1: Aislamiento Multi-Tenant
*   **Elegida:** Row Level Security (RLS) nativo de PostgreSQL activado para todos los roles.
*   **Alternativa Descartada (1):** *Filtrado lógico en la capa de aplicación (FastAPI `where empresa_id=X`).* **Justificación del rechazo:** Viola el Principio Zero-Trust; un error humano de omisión del filtro causaría un Data Leak catastrófico.
*   **Alternativa Descartada (2):** *Base de Datos por Tenant.* **Justificación del rechazo:** Overhead de mantenimiento y migraciones inasumible para el volumen de micro-pymes (5-50 operarios) objetivo de la plataforma.

### Decisión 2: Arquitectura Móvil Offline-First (Operarios)
*   **Elegida:** Progressive Web App (PWA) reactiva usando IndexedDB (LocalFirst) + Service Workers (Workbox) + Sync API Asimétrica.
*   **Alternativa Descartada:** *Desarrollo nativo (Swift/Kotlin) o Flutter/React Native con SQLite.* **Justificación del rechazo:** Requiere instalación de stores, excluye a operarios con móviles antiguos personales, y requiere un doble mantenimiento de código; la PWA cumple perfectamente gracias a la Web Crypto API exigida en la Constitución (Cifrado de tokens local).

### Decisión 3: Infraestructura de la Inteligencia Artificial
*   **Elegida:** Despliegue de nodos locales con LM Studio / Ollama en Servidor Soberano (Hetzner, Alemania) apoyado por RAG aislado por Tenant.
*   **Alternativa Descartada:** *APIs de terceros (OpenAI GPT-4, Anthropic, AWS Bedrock).* **Justificación del rechazo:** Prohibido por la Constitución (Punto 4 y 6). Extraer información de planos de seguridad de empresas o datos personales vulnera la LOPDGDD y el AI Act europeo para casos de uso de alta confidencialidad B2B.

### Decisión 4: Gestión de Tareas Asíncronas
*   **Elegida:** Celery y Redis (Workers externos paralelos).
*   **Alternativa Descartada:** *FastAPI BackgroundTasks.* **Justificación del rechazo:** Extraer texto de PDFs (PyMuPDF) o inferencias de LLM requiere un uso intensivo de CPU. Si se usa el Event Loop del servidor web, se degrada drásticamente la latencia de las respuestas a los clientes (requeridas a <200ms).

---

## 4. Estrategia de Tests (QA y Blindaje TDD)

Para garantizar la "Tolerancia Cero a Mock Data", se define la siguiente pirámide de pruebas automatizadas que bloquean integraciones defectuosas:

1.  **Unit Tests Lógicos (Pytest):**
    *   *Objetivo:* Validar pura algoritmia y reglas de negocio aisladas.
    *   *Ejemplo RF (Magatzem 004, Comptabilitat 007):* Calcular correctamente el PMP (Preu Mitjà Ponderat) al integrar albaranes parciales, o validar los cálculos del IVA / Inversión de Sujeto Pasivo en AEAT.
2.  **Integration Tests Transaccionales y de Seguridad (Pytest-Asyncio + Test DB):**
    *   *Objetivo:* Validar la protección RLS y los *Deadlocks*.
    *   *Ejemplo RF (Onboarding 021):* Realizar una petición a `/api/v1/gestio/clients` autenticados como Tenant A y garantizar que la BBDD intercepta y filtra cualquier registro del Tenant B devolviendo `0 results`.
    *   *Ejemplo RF (Feines 005):* Simular dos peticiones concurrentes de reserva de stock para comprobar que el bloqueo pesimista (`SELECT FOR UPDATE`) impide inventarios negativos.
3.  **Tests de Integración de IA (Contract Testing):**
    *   *Objetivo:* Prevenir *Alucinaciones* en las respuestas de Copilot.
    *   *Ejemplo RF (Copilot 012):* Testear el endpoint OCR mandando un PDF controlado y exigir que la respuesta se parsee forzosamente a través de un esquema estricto Pydantic, garantizando el JSON de salida.
4.  **End-to-End (E2E) Network Tests (Playwright / Cypress):**
    *   *Objetivo:* Certificar el comportamiento Offline-First de la PWA.
    *   *Ejemplo RF (Operari 013 a 020):* Interceptar la red en el test (simular *Offline*), ejecutar fichajes de operario, consumo de materiales de la furgoneta y cierre de la OT. Simular retorno *Online* y certificar que `/api/v1/operari_pwa/sync/push` sincroniza los datos en lote ordenadamente usando IndexedDB.
