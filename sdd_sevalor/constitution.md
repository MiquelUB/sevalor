# Sevalor Suite — Constitució del Projecte (v3.1 Definitiva)

> **Lema Fundacional:** *"Invisible per al treballador, omniscient per a l'enginyer."*

---

## 📌 Context: Què és Sevalor Suite?

**Sevalor Suite** (plataforma multi-vertical que inclou: *CampoPro*, *ElectricPro*, *HydroPro*, *BuildingPro*) és un sistema B2B integral dissenyat per a **empreses d'instal·lacions, manteniment i serveis tècnics que operen amb quadrilles al terreny (5-50 treballadors)**.

No es un simple software agrícola: es una suite de gestión de campo adaptable que conecta en tiempo real a **4 actores clave**:
1. **Operario en Campo (`/operari`)**: Utiliza una PWA móvil ultrarrápida, 100% offline-first, gobernada por el **"Flujo de los 30 segundos"** (fichaje, fotos geolocalizadas, check-in/out de herramientas con QR, kilometraje de vehículos y reporte por voz).
2. **Ingeniero / Oficina Técnica (`/gestio`)**: Dashboard web para planificar obras, versionar planos técnicos, controlar stock de almacén, auditar garantías, elaborar presupuestos y facturas proforma técnicas, y consultar facturas y albaranes asociados a sus clientes (la emisión de facturas legales definitivas con Veri*factu y el acceso a `/gestio/comptabilitat` quedan estrictamente reservados a Secretaría y Boss; el menú de contabilidad/facturación no se muestra al rol Ingeniero y la API bloquea su acceso con 403 Forbidden).
3. **Cliente Final (Canal Telegram Bot)**: Sin necesidad de instalar aplicaciones ni registrarse, el cliente recibe notificaciones de llegada de la cuadrilla, aprueba presupuestos de imprevistos con 1 clic y valida firmas de entrega.
4. **Superadmin Propietario (`/superadmin`)**: Centro de mando para el dueño del software: control de contratos SaaS (MRR), facturación B2B, licencias por cuadrilla y monitorización en tiempo real de los Nodos de IA locales.

---

## ⚖️ Principios Innegociables del Sistema

### 1. Tolerancia Cero a Datos Ficticios (Zero Mock Data)
*Regla de oro absoluta de desarrollo:* **Queda terminantemente prohibido introducir datos simulados ("dummy"), registros hardcodeados o mocks en cualquier parte del código o interfaz.**
- Toda la UI debe prepararse para producción mostrando estados vacíos reales (*"Sin datos disponibles"*, *"Sin tareas asignadas"*).
- Ninguna funcionalidad se dará por completada si depende de datos falsos para aparentar funcionamiento.

### 2. Offline-First Criptográfico (Web Crypto API)
Las cuadrillas operan en sótanos, zonas rurales o polígonos sin cobertura.
- La PWA debe garantizar la persistencia local de todas las acciones en IndexedDB y sincronización en segundo plano con Workbox al recuperar la conexión.
- **Seguridad de Tokens:** Queda prohibido guardar credenciales o JWT en texto plano en `localStorage` o `IndexedDB`. Los tokens persistidos deben cifrarse localmente mediante la **Web Crypto API (AES-GCM 256 bits)** derivando la clave criptográfica del PIN de 4 dígitos del operario o biometría local.

### 3. Diseño Camaleónico (Chameleon UI Engine)
La plataforma no tiene una identidad visual fija por vertical. Actúa como un **camaleón corporativo**:
- Cada empresa cliente sube su propio logotipo y selecciona sus colores de marca (*Primary, Secondary, Accent*).
- El sistema inyecta dinámicamente estos tokens en variables CSS HSL, transformando automáticamente la PWA del operario, el Dashboard web, los PDFs de facturas y los mensajes de Telegram para que parezca su propio software corporativo exclusivo.

### 4. IA Especializada por Vertical y RAG Multinivel (LM Studio / Ollama)
Para evitar alucinaciones críticas (como aplicar fórmulas de caudal de agua al cálculo de secciones de cables eléctricos), el motor de IA local se rige por un **aislamiento estricto de dominio y contexto empresarial**:
1. **System Prompts Especializados:** Instrucciones operativas y tono técnico según la vertical (`CAMPOPRO`, `ELECTRICPRO`, `HYDROPRO`, `BUILDINGPRO`).
2. **RAG Multinivel (Normativa Técnica + Protocolos Propios de Empresa):**
   - *Nivel Sectorial (Compartido por vertical):* Normativas técnicas y tablas de cálculo del oficio (`/knowledge/<vertical>/`: REBT de baja tensión, diámetros de tuberías PE, tablas de presión y caudales).
   - *Nivel Empresa (Privado por cliente):* Ingesta de documentación y protocolos internos de la empresa (normas de seguridad laboral, manuales de procedimientos operativos, listas de verificación de calidad y guías de actuación ante incidencias específicas de su plantilla).
3. **Historial de Obras Aislado:** `/data/historial/<vertical>/` para evitar comparaciones absurdas entre sectores distintos y preservar la privacidad entre empresas.
4. **Mandato Human-in-the-Loop:** La IA audita desviaciones, transcribe incidencias de voz, busca garantías, aplica los protocolos internos y propone pedidos de stock, pero **NUNCA** emite una factura legal (requiere confirmación y emisión explícita de Secretaría o Boss) ni un pedido a proveedor o presupuesto vinculante (requiere confirmación del ingeniero u oficina técnica).

### 5. Facturación Inmutable y Legal (RD 1007/2023 Veri*factu)
El motor de facturación debe cumplir con los requisitos de la normativa española:
- Todo PDF emitido incluirá su respectivo código QR estructurado y encadenamiento inmutable mediante **Hash SHA-256** referenciando el registro de la factura anterior.
- Modo de conservación local seguro e inalterable.

### 6. Arquitectura Asíncrona y Almacenamiento Local Seguro
- **FastAPI Asíncrono (`asyncpg`)**: Ningún endpoint HTTP debe bloquear el event loop.
- **Procesamiento en Segundo Plano**: Las tareas pesadas (generación de informes PDF con ReportLab, peticiones OCR a LM Studio, envíos al Bot de Telegram) se delegan obligatoriamente a **Celery + Redis**.
- **Gestión de Archivos (Memoria Interna de la Empresa y Servidor Hetzner en Alemania):** Se elimina completamente cualquier dependencia de servicios cloud externos como AWS S3 para garantizar el estricto cumplimiento de protección de datos (RGPD) y máxima seguridad operativa. Todos los datos del cliente, facturas, órdenes de pedido, imágenes de incidencias, fotos de odómetros y planos técnicos versionados se almacenan directamente en la memoria interna y discos duros locales de la empresa y en el servidor Hetzner Cloud en Alemania (UE), implementando copias de seguridad semanales automáticas cada domingo. La base de datos almacena exclusivamente metadatos, rutas locales relativas y geolocalizaciones.

### 7. Gobernanza SDD (Spec-Driven Development)
Ninguna línea de código de producción o refactorización se escribirá sin seguir el ciclo:
**Constitución ➔ Actualización de Spec (Mostrar Diff al CTO) ➔ Clarificación (QA) ➔ Plan de Arquitectura ➔ Tareas Atómicas (TDD) ➔ Validación.**
Si el código contradice la especificación aprobada, la especificación prevalece.
**Regla Estricta de IA:** Queda terminantemente prohibido tocar el código fuente sin actualizar primero la Spec correspondiente y mostrar un `diff` de los cambios para la aprobación del CTO.
