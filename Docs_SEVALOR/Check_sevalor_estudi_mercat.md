Sí. Para hacerlo bien, yo no le pediría al agente una opinión general. Le daría un **protocolo de auditoría reproducible**, obligándole a recorrer la plataforma como si fuera una empresa real y a registrar evidencia.

Además, lo estructuraría para que después podamos cruzar sus resultados con el análisis de mercado. En España, por ejemplo, las soluciones actuales de mantenimiento compiten ya en áreas como órdenes de trabajo, incidencias, técnicos, fichajes, materiales, planificación y facturación/VeriFactu; por eso necesitamos comprobar **cómo lo hace SEVALOR en la práctica**, no solamente si "tiene" cada función. ([SeibiX][1])

## CHECKLIST MAESTRO — AUDITORÍA INTEGRAL DE SEVALOR

Pásale al agente **exactamente este protocolo**.

### REGLAS PARA EL AGENTE

1. No asumir que una función existe porque aparezca en un menú.
2. Cada función debe ser **probada**.
3. Si algo no puede probarse, marcar `NO VERIFICADO`.
4. No inventar resultados.
5. Registrar errores literalmente.
6. Registrar el número de clics/pasos cuando sea relevante.
7. Registrar problemas de UX aunque técnicamente la función funcione.
8. No modificar ni borrar datos reales.
9. Utilizar exclusivamente datos ficticios de prueba.
10. Al finalizar cada prueba clasificar:

* `PASS` = funciona correctamente.
* `PASS_CON_OBSERVACIONES` = funciona pero tiene problemas.
* `FAIL` = no funciona.
* `PARTIAL` = funciona parcialmente.
* `NO_VERIFICADO` = no se pudo comprobar.
* `UX_PROBLEM` = funciona pero la experiencia es deficiente.

---

# 0. ACCESO Y SEGURIDAD

### Gestión

* [ ] Login correcto
* [ ] Login incorrecto
* [ ] Recuperación de contraseña
* [ ] Logout
* [ ] Persistencia de sesión
* [ ] Expiración de sesión
* [ ] Acceso directo a URLs internas sin autenticación
* [ ] Protección de rutas
* [ ] Navegación atrás/adelante del navegador

### Operario

* [ ] Primer registro NIF
* [ ] PIN
* [ ] PIN incorrecto
* [ ] Logout
* [ ] Cambio de usuario
* [ ] Persistencia de sesión
* [ ] Acceso a información de otro operario

**CRÍTICO:** intentar comprobar si un operario puede acceder accidentalmente a información que no le corresponde.

---

# 1. EXPERIENCIA GENERAL DE LA OFICINA

* [ ] Dashboard inicial
* [ ] Claridad de la pantalla inicial
* [ ] Menú
* [ ] Jerarquía visual
* [ ] Navegación
* [ ] Breadcrumbs
* [ ] Botones
* [ ] Iconos
* [ ] Mensajes de error
* [ ] Mensajes de éxito
* [ ] Confirmaciones
* [ ] Estados de carga
* [ ] Pantallas vacías
* [ ] Formularios
* [ ] Validaciones
* [ ] Búsqueda
* [ ] Filtros
* [ ] Ordenación
* [ ] Paginación
* [ ] Exportación
* [ ] Responsive
* [ ] Rendimiento

### Pregunta crítica

> ¿Un gerente de una PYME puede entender qué debe hacer al entrar por primera vez sin formación?

---

# 2. CLIENTES

Crear un cliente ficticio completo.

* [ ] Crear cliente
* [ ] Editar
* [ ] Eliminar
* [ ] Buscar
* [ ] Filtrar
* [ ] Contactos
* [ ] Teléfono
* [ ] Email
* [ ] Dirección
* [ ] NIF/CIF
* [ ] Notas
* [ ] Documentos
* [ ] Histórico
* [ ] Trabajos asociados
* [ ] Presupuestos asociados
* [ ] Facturas asociadas
* [ ] Incidencias asociadas
* [ ] Instalaciones/finques asociadas

### Prueba

Crear:

**Cliente → instalación → trabajo → incidencia → presupuesto → factura**

y comprobar que todo queda relacionado.

---

# 3. INSTALACIONES / FINCAS / ACTIVOS

Si existe esta funcionalidad:

* [ ] Crear instalación
* [ ] Asociar cliente
* [ ] Dirección
* [ ] Geolocalización
* [ ] Equipos
* [ ] Documentación
* [ ] Fotografías
* [ ] Planos
* [ ] Histórico
* [ ] Incidencias
* [ ] Trabajos
* [ ] Mantenimiento

### Pregunta

> ¿Puedo abrir una instalación y conocer rápidamente todo lo que ha ocurrido allí?

---

# 4. PRESUPUESTOS

Crear un presupuesto realista.

* [ ] Crear presupuesto
* [ ] Cliente
* [ ] Conceptos
* [ ] Materiales
* [ ] Mano de obra
* [ ] Cantidades
* [ ] Precios
* [ ] IVA
* [ ] Descuentos
* [ ] Totales
* [ ] PDF/documento
* [ ] Envío
* [ ] Estado
* [ ] Aceptación
* [ ] Rechazo
* [ ] Modificación
* [ ] Histórico

### Prueba crítica

**Presupuesto aceptado → trabajo**

Comprobar qué información se conserva.

---

# 5. PLANIFICACIÓN / AGENDA

* [ ] Crear trabajo
* [ ] Fecha
* [ ] Hora
* [ ] Duración
* [ ] Cliente
* [ ] Instalación
* [ ] Técnico
* [ ] Vehículo
* [ ] Material
* [ ] Estado
* [ ] Reprogramar
* [ ] Cancelar
* [ ] Arrastrar/modificar
* [ ] Conflicto de horarios
* [ ] Trabajo simultáneo
* [ ] Vista diaria
* [ ] Vista semanal
* [ ] Vista mensual

### Prueba

Crear 10 trabajos y asignarlos a 4 técnicos.

Comprobar si el responsable puede entender la carga de trabajo rápidamente.

---

# 6. OPERARIO / PWA

Este bloque es **crítico**.

## Acceso

* [ ] NIF
* [ ] PIN
* [ ] Primer acceso
* [ ] Logout

## Jornada

* [ ] Inicio
* [ ] Pausa
* [ ] Reanudación
* [ ] Fin
* [ ] Estado visible
* [ ] Errores

## Trabajo

* [ ] Ver trabajos asignados
* [ ] Abrir trabajo
* [ ] Ver cliente
* [ ] Ver ubicación
* [ ] Ver instrucciones
* [ ] Cambiar estado
* [ ] Añadir comentario
* [ ] Añadir fotografía
* [ ] Añadir material
* [ ] Añadir horas
* [ ] Registrar incidencia
* [ ] Finalizar trabajo

## Offline

Desactivar conexión.

* [ ] Abrir aplicación
* [ ] Consultar trabajo
* [ ] Registrar información
* [ ] Hacer fotografía
* [ ] Registrar incidencia
* [ ] Cerrar trabajo

Volver a conectar:

* [ ] Sincronización automática
* [ ] Sincronización correcta
* [ ] Sin duplicados
* [ ] Sin pérdida de datos
* [ ] Resolución de conflictos

Este punto es especialmente importante porque la documentación define SEVALOR como **offline-first**. 

---

# 7. INCIDENCIAS

Crear una incidencia desde el operario.

* [ ] Crear
* [ ] Texto
* [ ] Foto
* [ ] Prioridad
* [ ] Estado
* [ ] Responsable
* [ ] Fecha
* [ ] Histórico
* [ ] Notificación
* [ ] Resolución
* [ ] Cierre

### Prueba crítica

Incidencia creada en campo:

**PWA → Oficina → responsable → resolución → técnico**

Comprobar el flujo completo.

---

# 8. MATERIALES / ALMACÉN

Crear:

* 20 productos
* 2 almacenes
* 4 vehículos
* stock inicial.

Comprobar:

* [ ] Alta producto
* [ ] SKU/referencia
* [ ] Stock
* [ ] Entrada
* [ ] Salida
* [ ] Ajuste
* [ ] Transferencia
* [ ] Picking
* [ ] Stock vehículo
* [ ] Consumo en trabajo
* [ ] Reposición
* [ ] Histórico
* [ ] Alertas
* [ ] Stock negativo

### Prueba crítica

**Stock almacén → vehículo → trabajo → consumo**

Comprobar que las cantidades se actualizan correctamente.

---

# 9. VEHÍCULOS / FLOTA

* [ ] Alta vehículo
* [ ] Matrícula
* [ ] Técnico/responsable
* [ ] Estado
* [ ] Ubicación
* [ ] Documentación
* [ ] Mantenimiento
* [ ] Incidencias
* [ ] Material asociado
* [ ] Histórico

### Pregunta

> ¿El responsable puede saber qué vehículos están operativos y qué llevan?

---

# 10. MAPA / GIS

* [ ] Abrir mapa
* [ ] Cargar clientes
* [ ] Cargar instalaciones
* [ ] Cargar operarios
* [ ] Cargar vehículos
* [ ] Cargar trabajos
* [ ] Zoom
* [ ] Filtros
* [ ] Selección
* [ ] Abrir ficha desde mapa
* [ ] Localización
* [ ] Rutas si existen
* [ ] Capas
* [ ] Planos

### Prueba

Crear 10 ubicaciones diferentes y comprobar si el mapa realmente ayuda a gestionar operaciones.

---

# 11. PLANOS / DOCUMENTACIÓN

* [ ] Subir documento
* [ ] Descargar
* [ ] Visualizar
* [ ] Asociar a cliente
* [ ] Asociar a instalación
* [ ] Asociar a trabajo
* [ ] Fotografías
* [ ] Versiones
* [ ] Eliminación
* [ ] Permisos

---

# 12. PROVEEDORES / CAE

* [ ] Crear proveedor
* [ ] Contacto
* [ ] Documentos
* [ ] CAE
* [ ] Caducidades
* [ ] Alertas
* [ ] Histórico
* [ ] Asociación a trabajos

---

# 13. EQUIPO / OPERARIOS

Crear 5 trabajadores ficticios.

* [ ] Alta
* [ ] Edición
* [ ] Baja
* [ ] Rol
* [ ] Permisos
* [ ] PIN
* [ ] Trabajos
* [ ] Jornada
* [ ] Estado
* [ ] Histórico

### Prueba crítica

Comprobar qué puede ver:

**administrador vs técnico vs otro usuario.**

---

# 14. COMUNICACIONES

## Notificaciones

* [ ] Incidencia
* [ ] Trabajo
* [ ] Cambio de estado
* [ ] Mensaje
* [ ] Alertas

## Chat

* [ ] Enviar
* [ ] Recibir
* [ ] Asociar conversación
* [ ] Historial
* [ ] Adjuntos

---

# 15. CLIENTE / TELEGRAM

Si está habilitado:

* [ ] Cliente identifica empresa
* [ ] Abrir incidencia
* [ ] Texto
* [ ] Foto
* [ ] Vídeo
* [ ] Consulta presupuesto
* [ ] Aceptar presupuesto
* [ ] Consultar estado
* [ ] Recibir respuesta

La documentación define este bot como canal para incidencias y consulta/aprobación de presupuestos. 

---

# 16. CONTABILIDAD

### Presupuesto

↓

### Trabajo

↓

### Hoja de campo

↓

### Validación

↓

### Factura

Comprobar:

* [ ] Generación
* [ ] Numeración
* [ ] IVA
* [ ] Totales
* [ ] Cliente
* [ ] Conceptos
* [ ] Estado
* [ ] PDF
* [ ] Histórico
* [ ] Anulación/corrección

---

# 17. VERI*FACTU

Comprobar técnicamente:

* [ ] Hash
* [ ] QR
* [ ] Encadenamiento
* [ ] Número de factura
* [ ] Fecha
* [ ] Datos fiscales
* [ ] Estado AEAT
* [ ] Outbox
* [ ] Reintento
* [ ] Error AEAT
* [ ] Trazabilidad

La documentación del proyecto especifica SHA-256, QR y cola Outbox hacia AEAT. 

---

# 18. COPILOT IA

Este bloque merece una auditoría específica.

Hacer exactamente estas preguntas:

### Operaciones

> ¿Qué trabajos tengo pendientes?

> ¿Qué trabajos tiene asignados cada técnico?

> ¿Qué incidencias están abiertas?

### Stock

> ¿Qué materiales están bajo mínimos?

> ¿Qué lleva actualmente cada vehículo?

### Economía

> ¿Qué presupuestos están pendientes de aceptar?

> ¿Qué trabajos están pendientes de facturar?

> ¿Cuál ha sido el gasto de este mes?

### Clientes

> ¿Qué incidencias tiene abiertas el cliente X?

### Análisis

> ¿Qué problemas operativos detectas actualmente en la empresa?

Registrar:

* respuesta;
* tiempo;
* exactitud;
* datos utilizados;
* datos inventados;
* capacidad de cruzar información;
* si reconoce que no sabe algo.

### CRÍTICO

Probar preguntas cuya respuesta **no esté explícitamente en una sola tabla**.

Ahí sabremos si realmente es un Copilot empresarial o simplemente un chatbot.

---

# 19. SEGURIDAD

Intentar:

* acceder a URL interna sin login;
* acceder como otro usuario;
* modificar ID de otro registro;
* acceder a documentos ajenos;
* acceder a datos de otro tenant si existe entorno multiempresa;
* introducir HTML;
* introducir scripts;
* subir archivos extraños;
* modificar parámetros desde URL.

**No realizar ataques destructivos.**

Registrar cualquier fuga de información.

---

# 20. RENDIMIENTO

Medir aproximadamente:

* login;
* dashboard;
* clientes;
* mapa;
* almacén;
* trabajos;
* PWA;
* Copilot.

Con:

* 10 registros;
* 100 registros;
* si el entorno lo permite, 1.000 registros.

Buscar:

* cargas lentas;
* bloqueos;
* errores;
* tablas que tardan;
* mapas lentos;
* fotografías pesadas.

---

# 21. RESPONSIVE

Probar:

### Desktop

1920×1080

### Laptop

1366×768

### Tablet

768 px

### Móvil

390×844

Especialmente:

* PWA;
* tablas;
* formularios;
* mapas;
* menús;
* botones;
* fotografías.

---

# 22. PRUEBA MÁS IMPORTANTE: EMPRESA REAL SIMULADA

Después de probar módulos individualmente, el agente debe realizar **un caso completo de principio a fin**.

Crear:

**Empresa Demo**

5 técnicos
4 vehículos
2 almacenes
20 productos
10 clientes
10 instalaciones.

Después:

### CASO 1

Cliente solicita instalación.

↓

Presupuesto.

↓

Aceptación.

↓

Trabajo.

↓

Asignación técnico.

↓

Picking.

↓

Vehículo.

↓

Técnico realiza trabajo.

↓

Material consumido.

↓

Fotografía.

↓

Incidencia.

↓

Resolución.

↓

Hoja de campo.

↓

Validación.

↓

Factura.

↓

Resultado económico.

---

### CASO 2

Avería urgente.

Cliente comunica incidencia.

↓

Asignación técnico.

↓

Técnico recibe aviso.

↓

Se desplaza.

↓

Sin cobertura.

↓

Trabaja offline.

↓

Fotografía.

↓

Material.

↓

Incidencia.

↓

Recupera conexión.

↓

Sincroniza.

↓

Oficina recibe información.

---

# 23. PRUEBA DE USUARIO NO EXPERTO

Esta es fundamental.

El agente debe comportarse como:

> **gerente de una empresa de instalaciones que nunca ha utilizado SEVALOR.**

Y responder:

1. ¿Entiendo qué hacer?
2. ¿Encuentro rápidamente clientes?
3. ¿Encuentro trabajos?
4. ¿Entiendo qué están haciendo los técnicos?
5. ¿Sé qué material tengo?
6. ¿Sé qué trabajos están pendientes?
7. ¿Sé qué tengo que facturar?
8. ¿Entiendo la situación económica?
9. ¿Necesito formación?
10. ¿Dónde me pierdo?

---

# 24. ESCALA DE EVALUACIÓN

Para cada prueba:

| Código      | Significado                 |
| ----------- | --------------------------- |
| PASS        | Correcto                    |
| PASS-OBS    | Correcto con observaciones  |
| PARTIAL     | Parcial                     |
| FAIL        | No funciona                 |
| UX          | Funciona pero UX deficiente |
| SECURITY    | Problema de seguridad       |
| PERFORMANCE | Problema de rendimiento     |
| NO-VERIFIED | No comprobable              |

Además:

**Severidad**

🔴 CRÍTICO
🟠 ALTO
🟡 MEDIO
🟢 BAJO

---

# 25. FORMATO DE RESULTADOS QUE QUIERO QUE ME DEVUELVAS

No quiero que el agente me entregue solamente:

> "La aplicación funciona bien."

Quiero datos estructurados.

Para cada prueba:

```text
ID:
MÓDULO:
PRUEBA:
RESULTADO:
SEVERIDAD:
PASOS REALIZADOS:
RESULTADO OBSERVADO:
ERROR:
TIEMPO APROXIMADO:
Nº DE CLICS/PASOS:
CAPTURA/EVIDENCIA:
OBSERVACIÓN UX:
```

Y al final:

```text
TOTAL PRUEBAS:
PASS:
PASS-OBS:
PARTIAL:
FAIL:
UX:
SECURITY:
PERFORMANCE:
NO-VERIFIED:
```

---

## Y HAY UNA ÚLTIMA PARTE QUE QUIERO QUE EL AGENTE HAGA

Que no evalúe solamente si **SEVALOR funciona**.

Que responda:

### "¿Por qué una empresa española de 10–30 trabajadores elegiría SEVALOR frente a seguir utilizando su sistema actual o comprar otro software?"

Y que lo justifique **exclusivamente con cosas que haya podido comprobar durante las pruebas**.

Esto nos dará algo mucho más valioso que una auditoría técnica:

**la radiografía real del producto que tenemos para salir al mercado.**

Además, el mercado actual ya muestra que los compradores de software de mantenimiento valoran conjuntamente operaciones, técnicos, incidencias, planificación, materiales y trazabilidad; por eso esta auditoría está diseñada alrededor de **flujos empresariales completos**, no de una simple lista de funcionalidades. ([grownu.es][2])

[1]: https://seibix.com/?utm_source=chatgpt.com "Software de gestión GMAO para empresas multiservicios - SeibiX"
[2]: https://grownu.es/sectores/servicios-campo/mantenimiento-instalaciones?utm_source=chatgpt.com "Software para mantenimiento de instalaciones | Grownu"
