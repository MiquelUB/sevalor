# SEVALOR — Mejoras propuestas y roadmap

**Fecha:** 23/09/2026  
**Objetivo:** reforzar la diferenciación de SEVALOR para PYMES de instalaciones y mantenimiento técnico.

---

# 1. PRINCIPIO DE PRODUCTO

No añadir módulos indiscriminadamente.

La diferenciación debe construirse sobre:

> **OPERACIÓN + DATOS + CONOCIMIENTO + IA**

La evolución propuesta es pasar de una plataforma integral de gestión a:

> **el sistema operativo de una empresa técnica.**

---

# 2. PRIORIDAD P0 — SEVALOR AI AGENT

Convertir Copilot en un agente empresarial, no en un chatbot.

Debe poder:

- consultar información;
- combinar datos;
- razonar;
- detectar problemas;
- proponer acciones;
- ejecutar acciones después de confirmación.

Ejemplos:

```text
¿Qué trabajos tenemos pendientes?
```

```text
¿Qué técnico está mejor situado para la avería del cliente X?
```

```text
¿Qué material falta para el trabajo de mañana?
```

```text
¿Qué trabajos terminados todavía no están facturados?
```

```text
¿Por qué ha aumentado el coste del cliente X?
```

```text
¿Quieres que reprograme el trabajo?
```

---

# 3. ARQUITECTURA DE IA

No crear un LLM independiente desde cero para cada cliente.

Construir un **SEVALOR AI CORE** común:

```text
SEVALOR AI CORE
│
├── System Prompt maestro
├── Reglas agenticas
├── Tools
├── Permisos
├── RAG Engine
├── Embeddings
├── Reranker
└── LLM
```

Cada empresa tendrá su propio tenant con:

- datos;
- documentos;
- configuración;
- conocimiento;
- índice RAG.

El software es común; el conocimiento es específico de la empresa.

---

# 4. RAG HÍBRIDO

No utilizar RAG para todo.

## RAG documental

Para:

- protocolos;
- manuales;
- procedimientos;
- documentación técnica;
- contratos;
- normativa;
- planos;
- fichas de producto;
- documentación interna.

## Datos vivos

Usar SQL/API/tools para:

- clientes;
- proveedores;
- trabajos;
- agenda;
- stock;
- vehículos;
- operarios;
- incidencias;
- presupuestos;
- facturas;
- costes.

### Regla

```text
DOCUMENTO → RAG
DATO ACTUAL → TOOL / SQL / API
```

El agente decide qué fuente necesita.

---

# 5. MÓDULOS RAG RECOMENDADOS

## RAG Empresa

- procedimientos;
- políticas;
- tarifas;
- organización;
- reglas internas.

## RAG Técnico

- protocolos;
- manuales;
- checklists;
- instrucciones.

## RAG Cliente/Instalación

- contratos;
- instrucciones;
- documentación;
- histórico documental.

## RAG Material

- fichas;
- catálogos;
- equivalencias;
- instrucciones.

## RAG Proveedores

- contratos;
- documentación;
- condiciones.

## RAG Normativa

- normativa;
- procedimientos reglamentarios.

---

# 6. MEMORIA OPERATIVA

Crear una capa diferente al RAG documental.

Debe representar:

```text
Cliente
→ Instalación
→ Activos
→ Trabajos
→ Incidencias
→ Materiales
→ Técnicos
→ Costes
→ Histórico
```

Objetivo:

> que SEVALOR conozca el historial operativo de cada cliente e instalación.

Ejemplos:

```text
¿Cuántas averías ha tenido esta instalación?
```

```text
¿Qué piezas se han sustituido?
```

```text
¿Cuánto nos ha costado mantenerla?
```

---

# 7. DIGITAL TWIN DE CLIENTE / INSTALACIÓN

Crear una ficha 360º:

```text
CLIENTE
│
└── INSTALACIÓN
    │
    ├── Activos
    ├── Trabajos
    ├── Incidencias
    ├── Materiales
    ├── Documentos
    ├── Fotografías
    ├── Planos
    ├── Costes
    └── Histórico
```

Debe convertirse en una pieza central del producto.

---

# 8. PLANIFICACIÓN INTELIGENTE

La agenda debería evolucionar hacia asignación inteligente.

No solamente:

> ¿Qué técnico está libre?

Sino:

> **¿Qué técnico es el más adecuado?**

Criterios posibles:

- especialidad;
- ubicación;
- disponibilidad;
- carga;
- urgencia;
- SLA;
- histórico;
- material;
- vehículo.

Flujo:

```text
PROPUESTA
↓
CONFIRMACIÓN
↓
ACCIÓN
```

No automatizar completamente decisiones laborales sensibles.

---

# 9. CONTROL ECONÓMICO REAL POR TRABAJO

Crear una visión:

```text
INGRESO
-
HORAS
-
MATERIAL
-
DESPLAZAMIENTO
-
VEHÍCULO
-
SUBCONTRATACIÓN
=
MARGEN
```

El gerente debe poder conocer:

- coste;
- ingreso;
- margen;
- desviación.

Y consultarlo mediante el agente.

---

# 10. DETECTOR DE DINERO NO FACTURADO

Crear un servicio o dashboard de:

> **Dinero pendiente**

Detectar:

- trabajos terminados no facturados;
- materiales consumidos no facturados;
- horas no repercutidas;
- extras no presupuestados;
- presupuestos aprobados pendientes;
- trabajos fuera de contrato;
- incidencias que generan coste.

Generar alertas.

---

# 11. STOCK INTELIGENTE

Evolucionar desde stock a:

> **stock operativo predictivo.**

Cruzar:

- trabajos próximos;
- materiales necesarios;
- stock de almacén;
- stock de vehículos;
- consumo histórico.

Ejemplo:

> El trabajo de mañana necesita 4 válvulas; el vehículo lleva 2 y el almacén central dispone de 10.

---

# 12. IMPORTACIÓN MASIVA

Implementar desde la interfaz:

## Importar CSV

Como mínimo:

- clientes;
- proveedores;
- artículos;
- stock;
- operarios;
- vehículos;
- instalaciones;
- otros maestros necesarios.

Proceso:

```text
CSV
↓
MAPEAR COLUMNAS
↓
VALIDAR
↓
DUPLICADOS / ERRORES
↓
CONFIRMAR
↓
IMPORTAR
```

Mostrar resultados:

```text
247 registros válidos
8 duplicados
3 errores
```

---

# 13. PORTABILIDAD DE DATOS

Implementar:

## Exportar datos

Como mínimo:

- clientes;
- proveedores;
- productos;
- stock;
- operarios;
- vehículos;
- instalaciones;
- trabajos;
- incidencias;
- presupuestos;
- facturas;
- documentos;
- configuración.

Formatos:

- CSV;
- JSON;
- ZIP de documentos/fotos.

Mensaje comercial posible:

> **Tus datos son tuyos. Puedes llevártelos cuando quieras.**

---

# 14. BACKUP COMPLETO DEL TENANT

Crear:

```text
SEVALOR_BACKUP_YYYY-MM-DD.zip
```

Contenido:

```text
database/
documents/
photos/
configuration/
rag_metadata/
manifest.json
```

Política propuesta:

- incremental diario;
- completo semanal;
- snapshot mensual.

Mostrar en administración el último backup correcto.

---

# 15. APPLIANCE LOCAL

No utilizar estaciones GPU de varios miles de euros para empresas pequeñas.

Modelo recomendado:

> **el cliente compra su propio mini-PC.**

Configuración estándar inicial:

- Ryzen 7 o equivalente;
- 32 GB RAM;
- 1 TB NVMe;
- LAN 2,5 GbE;
- ampliación hasta 64 GB.

16 GB queda como versión Lite.

---

# 16. ESCALADO LLM

## SEVALOR AI Lite

**16 GB**

Modelo pequeño para IA básica + RAG ligero.

## SEVALOR AI Standard

**32 GB**

Modelo de aproximadamente 9B.

Configuración recomendada para la mayoría de PYMES.

## SEVALOR AI Pro

**64 GB**

Modelo mayor para más documentación, usuarios o razonamiento.

## Enterprise

GPU dedicada / memoria superior cuando exista una necesidad real.

---

# 17. BACKUP LOCAL

Utilizar dos unidades externas:

```text
SSD A
SSD B
```

Alternarlas semanalmente.

Idealmente mantener una unidad fuera de la ubicación principal.

---

# 18. SAI / UPS

Añadir un SAI para:

- mini-PC;
- almacenamiento;
- red.

Flujo:

```text
CORTE
↓
UPS
↓
detectar batería
↓
apagado controlado
↓
protección de datos
```

Configurar arranque automático cuando vuelva la electricidad.

---

# 19. MODELO COMERCIAL DE IA

Separar:

### 1. Software SEVALOR
Cuota recurrente.

### 2. Implantación
Pago único.

### 3. IA Local — configuración
Pago único.

### 4. Mantenimiento IA
Cuota recurrente.

### 5. Hardware
Compra del cliente.

No utilizar leasing/renting del hardware como modelo estándar inicial.

---

# 20. PORTABILIDAD COMO ARGUMENTO COMERCIAL

Utilizar:

> **Tus datos son tuyos. Puedes exportarlos cuando quieras.**

La retención debe proceder del valor de SEVALOR, no de dificultar la salida.

---

# 21. PORTAL CLIENTE

Crear una experiencia para el cliente final con:

- incidencias;
- presupuestos;
- aceptación;
- documentos;
- partes;
- histórico;
- instalaciones;
- firma;
- estado del servicio.

Objetivo:

> elevar la percepción profesional de la empresa que utiliza SEVALOR.

---

# 22. INFORME AUTOMÁTICO DE INTERVENCIÓN

Al cerrar una intervención:

```text
Trabajo
+
horas
+
material
+
fotografías
+
incidencias
+
observaciones
```

generar automáticamente un informe profesional para el cliente.

---

# 23. IA MULTIMODAL

Aprovechar visión para:

- fotografías de averías;
- etiquetas de equipos;
- placas de características;
- documentos;
- imágenes técnicas.

Ejemplo:

> fotografía de una placa → identificar modelo → recuperar manual/protocolo desde RAG.

Debe tratarse como asistencia, no como diagnóstico infalible.

---

# 24. CONOCIMIENTO DE LA EMPRESA

En Configuración → IA:

```text
Conocimiento de mi empresa
```

Permitir:

- subir documentos;
- clasificar;
- reindexar;
- ver estado;
- eliminar;
- consultar origen.

Mostrar:

```text
Documentos: 348
Protocolos: 27
Manual de equipos: 63
Última indexación: ...
Estado: Operativo
```

---

# 25. SYSTEM PROMPT DEL AGENTE

Crear un System Prompt maestro común que defina:

- identidad;
- límites;
- permisos;
- fuentes;
- cuándo consultar datos;
- cuándo usar RAG;
- cuándo usar tools;
- cuándo pedir confirmación;
- cuándo decir "no lo sé";
- evitar inventar;
- mostrar fuentes cuando la respuesta provenga de documentos.

Cada tenant añade su configuración empresarial.

---

# 26. TOOLS DEL AGENTE

### Operaciones

- listar trabajos;
- consultar trabajo;
- asignar;
- reprogramar;
- cerrar.

### Stock

- consultar stock;
- reservar;
- localizar material.

### Clientes

- consultar cliente;
- instalaciones;
- histórico.

### Economía

- presupuestos;
- facturas;
- costes;
- margen.

### Recursos

- técnicos;
- vehículos;
- disponibilidad.

### Documentación

- buscar documentos;
- recuperar protocolo.

Toda acción que cambie datos debería requerir confirmación cuando tenga consecuencias operativas o económicas.

---

# 27. PRIORIZACIÓN

## P0 — imprescindible

1. Agente IA real.
2. RAG híbrido.
3. Tools sobre datos vivos.
4. Digital Twin cliente/instalación.
5. Coste/margen por trabajo.
6. Importación CSV.
7. Exportación/portabilidad.
8. Backup.
9. Appliance local 32 GB.

## P1 — alto valor

10. Planificador inteligente.
11. Stock predictivo.
12. Portal cliente.
13. Informes automáticos.
14. Contratos/SLA/recurrencia.
15. IA multimodal.

## P2 — expansión

16. Modelos mayores.
17. Automatizaciones avanzadas.
18. Predicciones.
19. BI conversacional avanzado.
20. Verticalizaciones específicas.

---

# 28. OBJETIVO FINAL

La evolución buscada es:

```text
SEVALOR ACTUAL
Gestión integral
        ↓
SEVALOR OPERATIVO
Gestión + datos conectados
        ↓
SEVALOR INTELIGENTE
Gestión + datos + RAG + agente
        ↓
SEVALOR AI LOCAL
Sistema operativo empresarial privado
```

El objetivo no es tener más módulos que la competencia.

El objetivo es que, para una empresa técnica, **SEVALOR sea el lugar donde están sus operaciones y el sistema que las entiende**.
