# ROADMAP DE EJECUCIÓN (Tareas <30 min por dependencia)

Este desglose traduce el `plan.md` en unidades de trabajo atómicas, estrictamente ordenadas desde los cimientos arquitectónicos (BD y Seguridad) hasta la capa visual y de sincronización offline.

## FASE 1: Seguridad y Cimientos (Superadmin & BD)

- [x] **1.1. Inyección de Tenant de BD (Dependency)**
  - **RFs:** Spec 021 (Gestión Multi-tenant RLS).
  - **Hecho cuando:** Exista un *Dependency Injector* en FastAPI que intercepte el JWT, extraiga el `empresa_id` y ejecute `SET app.current_tenant` en la sesión de SQLAlchemy.
- [x] **1.2. Activación RLS en Tablas Core (PostgreSQL)**
  - **RFs:** Spec 021, Constitución Puntos 1 y 7.
  - **Hecho cuando:** Las tablas `Client`, `Article`, `OrdreTreball` tengan la política `CREATE POLICY` en base a `current_setting('app.current_tenant')` y pase el test automatizado de aislamiento.
- [x] **1.3. Limpieza de `where(empresa_id)` en Repositorios**
  - **RFs:** Refactor Transversal de Seguridad.
  - **Hecho cuando:** Se hayan borrado todos los filtros manuales por `empresa_id` en las consultas de `magatzem.py` y `proveidors.py`, delegando el filtrado íntegramente al motor SQL.

## FASE 2: Motores Asíncronos e Infraestructura IA (Celery & Redis)

- [x] **2.1. Configuración de Base Celery/Redis**
  - **RFs:** Spec 024 (Workers Asíncronos).
  - **Hecho cuando:** `docker-compose` levante un worker de Celery conectado a Redis y exista un task `ping()` de prueba funcionando.
- [x] **2.2. Migración del Endpoint OCR de Albaranes a Background**
  - **RFs:** Spec 004 (RF-08), Spec 012 (IA).
  - **Hecho cuando:** `POST /api/v1/gestio/magatzem/albara/ocr` no espere la lectura de la IA, sino que retorne un HTTP 202 con un `task_id` válido de Celery.
- [x] **2.3. Endpoint de Sondeo de Estado (Status Polling / WebSockets)**
  - **RFs:** Spec 024.
  - **Hecho cuando:** El frontend pueda hacer un `GET /api/v1/workers/status/{task_id}` y recibir `{estado: "COMPLETADO", datos: {...}}`.

## FASE 3: Lógica Crítica de Dominio (Almacén y Proveedores)

- [x] **3.1. Bloqueo Pesimista en Picking (SELECT FOR UPDATE)**
  - **RFs:** Spec 004 (RF-17).
  - **Hecho cuando:** Un test concurrente intente extraer stock simultáneamente desde dos hilos y la BD arroje error por stock insuficiente en el segundo intento (evitando inventario negativo).
- [x] **3.2. Restricción FEFO (Caducidad) y Cuarentenas**
  - **RFs:** Spec 004 (RF-18, RF-19).
  - **Hecho cuando:** Al confirmar un Pick-out (devolución) de un artículo "roto", el sistema lo marque como cuarentena y bloquee su uso futuro en otras órdenes de trabajo.
- [x] **3.3. IA Copilot: Detección de Backorders en Tránsito**
  - **RFs:** Spec 004 (RF-32, RF-33).
  - **Hecho cuando:** Si el stock de un material requerido es 0, Celery evalúe las facturas pendientes y la API devuelva una alerta inteligente (HTTP 422 con mensaje estructurado) evitando la creación del pedido.

## FASE 4: Arquitectura PWA Offline-First (Operarios)

- [x] **4.1. Configuración Inicial Dexie.js (IndexedDB)**
  - **RFs:** Constitución Punto 2, Spec 013 (Ejecución Offline).
  - **Hecho cuando:** El frontend (PWA) instancie una DB local capaz de almacenar un Draft de "Fichaje Laboral" sin requerir internet.
- [x] **4.2. Motor de Sincronización (Service Worker - Workbox)**
  - **RFs:** Constitución Punto 2.
  - **Hecho cuando:** El navegador intercepte llamadas fallidas a la API (modo avión) y las ponga en una "Cola de Sincronización" (Sync Queue).
- [x] **4.3. API Endpoint para Bulk Sync (Resolución de Conflictos)**
  - **RFs:** Spec 014, Spec 013.
  - **Hecho cuando:** Exista un `POST /api/v1/operari_pwa/sync/push` capaz de recibir un JSON array con 5 acciones diferentes, procesarlas secuencialmente y devolver 200 OK.

## FASE 5: Contabilidad Inmutable (Veri*factu)

- [x] **5.1. Esquemas Pydantic y Hash Encadenado**
  - **RFs:** Spec 007 (Facturación), Constitución Punto 5.
  - **Hecho cuando:** La creación de una factura genere automáticamente un Hash SHA-256 inmutable que incluya el hash de la factura anterior.
- [x] **5.2. Generador de XML AEAT (Inversión Sujeto Pasivo)**
  - **RFs:** Spec 007.
  - **Hecho cuando:** El backend exporte un archivo `.xml` estructurado que valide exitosamente contra los esquemas XSD públicos de Hacienda española.
