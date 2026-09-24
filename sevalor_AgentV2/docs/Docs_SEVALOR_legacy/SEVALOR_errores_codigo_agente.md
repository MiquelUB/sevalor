# SEVALOR — Incidencias técnicas y errores detectados

**Fecha:** 23/09/2026  
**Base documental:** `audit_funcional.py`, `audit_runner.py`, `audit_log_funcional.md` y resultados de exploración funcional aportados por el agente.

## 0. Alcance

Este documento **no afirma errores del código interno de SEVALOR que no hayan sido demostrados**.

Los archivos aportados corresponden principalmente a scripts de auditoría Selenium y a sus resultados. Por tanto, las incidencias que siguen son:

1. problemas/inconsistencias demostrables en la automatización de auditoría;
2. limitaciones de prueba que pueden producir falsos `PASS`;
3. funcionalidades de SEVALOR que el agente no consiguió verificar.

No debe interpretarse como una auditoría del repositorio de SEVALOR.

---

# 1. INCIDENCIAS EN LOS SCRIPTS DE AUDITORÍA

## 1.1. Uso excesivo de `except` genéricos y silenciosos

### Problema

Los scripts contienen varios bloques equivalentes a:

```python
except:
    return False
```

o:

```python
except:
    pass
```

Esto provoca que una excepción real pueda convertirse silenciosamente en:

- botón no encontrado;
- prueba no ejecutada;
- resultado incompleto;
- ausencia de resultado.

### Impacto

**Alto para la calidad de la auditoría.**

Puede ocultar errores del propio agente y generar una falsa sensación de cobertura.

### Acción recomendada

Sustituir por excepciones explícitas y registrar siempre:

- excepción;
- selector;
- URL;
- pantalla;
- paso que falló.

---

# 2. `time.sleep()` como mecanismo principal de sincronización

## Problema

La automatización utiliza repetidamente esperas fijas como:

```python
time.sleep(3)
time.sleep(4)
time.sleep(5)
```

aunque también importa `WebDriverWait` y `expected_conditions`.

### Impacto

**Medio/alto.**

Puede producir:

- falsos negativos;
- tiempos artificialmente largos;
- fallos intermitentes;
- resultados diferentes según la carga del servidor.

### Acción recomendada

Esperar condiciones concretas: URL, presencia/visibilidad del elemento, elemento clicable, desaparición de loaders o contenido esperado.

---

# 3. Localizadores demasiado frágiles

## Problema

Se buscan elementos mediante textos y placeholders concretos, por ejemplo:

```python
contains(text(), 'Nou Client')
```

y:

```python
contains(@placeholder, 'Cercar')
```

Además, el helper de botones busca entre `button`, `a`, `span` y `div`.

### Impacto

**Medio.**

Cambios pequeños de idioma, copy, HTML o diseño pueden romper la auditoría.

### Acción recomendada

Priorizar identificadores estables:

1. `id` / `name`;
2. `data-testid`;
3. atributos semánticos;
4. CSS estable;
5. XPath como recurso posterior.

---

# 4. `btn()` puede devolver elementos que no son botones

## Problema

El helper busca:

```text
button / a / span / div
```

y devuelve el primer elemento visible que coincide con el texto.

### Consecuencia

Un `span` o `div` puede contener el texto de un botón sin ser el elemento interactivo.

Puede provocar:

- click incorrecto;
- excepción;
- comportamiento diferente según DOM;
- falsos `NO_VERIFICADO`.

### Acción recomendada

Buscar primero `button`, después `a` y utilizar contenedores únicamente cuando se haya confirmado que son clicables.

---

# 5. Navegación sin validación suficiente

## Problema

El helper de navegación hace click y espera unos segundos, pero no valida de forma robusta:

- URL resultante;
- título/encabezado;
- contenido distintivo;
- ausencia de error.

### Impacto

**Medio.**

### Acción recomendada

Cada navegación debe validar:

```text
URL esperada
+
encabezado/título
+
elemento distintivo del módulo
```

---

# 6. El resumen `PASS` sobreestima la cobertura

El primer informe declara **27 PASS / 1 NO_VERIFICADO**, pero varios `PASS` solo demuestran que:

- el módulo abre;
- existe un botón;
- existe un formulario;
- existe una etiqueta.

No demuestran la funcionalidad completa.

Ejemplos claros: inventario, flota, planos, proveedores, contabilidad y Copilot.

### Acción recomendada

Usar tres niveles separados:

```text
PRESENTE
INTERACTIVO
FLUJO VERIFICADO
```

No utilizar `PASS` como equivalente de los tres.

---

# 7. La prueba de seguridad basada en Pydantic no demuestra seguridad integral

## Problema

El script registra que el backend valida schemas Pydantic y considera `PASS` una prueba de entradas maliciosas rechazadas.

### Problema conceptual

Eso demuestra únicamente que una determinada entrada fue rechazada.

No demuestra:

- autorización por rol;
- control de acceso por registro;
- aislamiento entre tenants;
- seguridad documental;
- seguridad de sesión.

### Estado

**No hay un fallo de seguridad de SEVALOR confirmado por estos archivos.**

La incidencia es de criterio de auditoría.

---

# 8. Persistencia/expiración de sesión no verificada

El runner marca explícitamente esta prueba como `NO_VERIFICADO`, ya que no cierra y reabre realmente el navegador con la misma sesión.

No es un bug confirmado.

---

# 9. PWA: comprobación incompleta

Se confirmó el acceso y la existencia de las áreas de la PWA, pero no se verificaron:

- ciclo completo de trabajo;
- fotografía;
- materiales;
- horas;
- incidencias;
- modo offline;
- sincronización.

No existe evidencia suficiente para afirmar que estos flujos fallen.

---

# 10. Copilot: funcionalidad no verificada

Se ha comprobado la interfaz y la pantalla de entrenamiento local, pero no se han ejecutado las pruebas operativas.

Estado:

```text
INTERFAZ                 CONFIRMADA
RAG                      NO VERIFICADO
DATOS VIVOS              NO VERIFICADO
TOOL CALLING             NO VERIFICADO
ACCIONES                 NO VERIFICADAS
```

---

# 11. Presupuestos, trabajos y agenda no localizados

La exploración no encontró claramente:

- módulo de presupuestos;
- módulo de trabajos de oficina;
- agenda/calendario;
- módulo de incidencias de oficina;
- hoja de campo.

Esto **no demuestra que no existan**. Solo que no han sido localizados en la exploración realizada.

---

# 12. Rendimiento: datos a investigar

El agente obtuvo aproximadamente:

- login: ~5 s;
- navegación: ~4 s;
- mapa: ~4 s.

El runner los marca como `PASS`.

No debe tratarse como bug confirmado, pero sí como punto de optimización y medición posterior.

---

# 13. Inconsistencia entre los dos runners

`audit_funcional.py` y `audit_runner.py` no tienen exactamente el mismo alcance ni los mismos criterios de resultado.

Ejemplos:

- algunas pruebas existen en un runner y no en el otro;
- comunicaciones aparece como `PARTIAL` en uno;
- Copilot aparece con criterios distintos;
- el esquema de resultados no es completamente homogéneo.

### Impacto

**Medio.**

Los resultados de ejecuciones distintas no son perfectamente comparables.

### Acción recomendada

Crear un único runner oficial y un único esquema de estados.

---

# 14. Falta de evidencia visual sistemática

Los scripts registran principalmente texto, URL, resultado, clics y tiempos.

No existe un sistema consistente de:

- screenshot por prueba;
- HTML de fallo;
- consola;
- trazas de red.

Para una auditoría repetible sería recomendable generar evidencia automática en cada fallo y en cada flujo crítico.

---

# 15. CONCLUSIÓN

Con la documentación disponible **no existe base suficiente para afirmar una lista de bugs del código interno de SEVALOR**.

Sí existen problemas claros en el propio sistema de auditoría:

1. excepciones silenciosas;
2. sleeps excesivos;
3. selectores frágiles;
4. clicks sobre elementos no necesariamente interactivos;
5. falta de validación post-navegación;
6. criterio `PASS` demasiado permisivo;
7. runners no homogéneos;
8. falta de evidencia visual;
9. cobertura incompleta de flujos.

La prioridad es mejorar el **auditor automático** para que sus resultados sean fiables, repetibles y comparables entre versiones de SEVALOR.
