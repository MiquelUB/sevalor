# INFORME DE EVALUACIÓN DE SEVALOR

**Versión evaluada:** septiembre de 2026
**Producto:** SEVALOR
**Tipo:** SaaS de gestión integral para empresas con equipos y operaciones de campo
**Mercado analizado:** España
**Segmento prioritario:** PYMES de instalaciones y mantenimiento técnico

---

## 1. RESUMEN EJECUTIVO

SEVALOR no debe presentarse comercialmente como un simple programa de gestión de partes, un CRM, un ERP ligero ni como otra plataforma de Field Service.

La arquitectura y el alcance del producto muestran una propuesta mucho más amplia:

> **SEVALOR es una central de operaciones para empresas técnicas con personal de campo.**

El producto conecta en un mismo entorno:

* oficina;
* operarios;
* clientes y fincas;
* trabajos;
* incidencias;
* materiales;
* almacenes;
* vehículos;
* documentación;
* planos;
* comunicaciones;
* presupuestos;
* facturación;
* contabilidad;
* información geográfica;
* IA.

La diferencia importante no está en tener muchas pantallas, sino en que **los diferentes elementos del negocio están conectados entre sí**.

La propuesta de valor potencialmente más fuerte es:

> **Lo que ocurre en el campo se convierte inmediatamente en información operativa y económica para la empresa.**

Esto sitúa a SEVALOR en una posición diferente de muchas soluciones que se concentran principalmente en:

* partes de trabajo;
* planificación;
* CRM;
* mantenimiento;
* facturación;
* o gestión de empleados.

### Valoración global provisional

**Producto:** 8,5/10
**Amplitud funcional:** 9/10
**Potencial diferencial:** 8,5/10
**Adecuación al segmento elegido:** 9/10
**Madurez comercial:** 6,5/10
**Claridad del posicionamiento actual:** 6/10
**Potencial competitivo en España:** alto, condicionado a demostrar la experiencia de uso y los flujos completos.

La principal debilidad que detecto actualmente **no parece ser la falta de funcionalidades**.

El riesgo principal es exactamente el contrario:

> **SEVALOR puede tener tantas funcionalidades que el cliente no entienda rápidamente qué problema le resuelve.**

---

# 2. QUÉ ES REALMENTE SEVALOR

La estructura actual permite interpretar SEVALOR como cinco capas conectadas.

### 2.1 PERSONAS

* empleados;
* operarios;
* equipos;
* jornadas;
* fichajes;
* trabajos asignados.

### 2.2 ACTIVOS

* vehículos;
* almacenes;
* materiales;
* herramientas/equipamiento;
* instalaciones;
* fincas;
* planos;
* redes.

### 2.3 OPERACIONES

* clientes;
* trabajos;
* incidencias;
* partes/hojas de campo;
* picking;
* desplazamientos;
* planificación;
* comunicaciones.

### 2.4 ECONOMÍA

* presupuestos;
* validación;
* facturación;
* proveedores;
* gastos;
* contabilidad;
* Veri*factu;
* información económica.

### 2.5 INFORMACIÓN

* GIS;
* documentación;
* planos;
* fotografías;
* comunicaciones;
* histórico;
* Copilot IA.

La arquitectura documentada confirma precisamente esta integración entre gestión, PWA de operarios, almacén, flota, contabilidad, IA y comunicaciones con clientes.

---

# 3. EL ELEMENTO MÁS IMPORTANTE: OFICINA + CAMPO

Uno de los aspectos más interesantes del producto es que existen dos experiencias claramente diferenciadas.

## SEVALOR Oficina

Es la **central de mando**.

Desde aquí se controla:

* clientes;
* instalaciones;
* almacén;
* vehículos;
* proveedores;
* personal;
* planos;
* comunicaciones;
* IA;
* contabilidad.

## SEVALOR Operari

Es el **terminal de trabajo del técnico**.

La documentación especifica una PWA mobile-first con:

* autenticación mediante NIF + PIN;
* funcionamiento offline;
* jornadas;
* pausas;
* finalización de turno;
* picking;
* trabajos;
* incidencias;
* fotografías.

Esto es comercialmente importante.

No estamos ante:

> "un programa que también tiene una app móvil".

La concepción es más cercana a:

> **una misma empresa funcionando desde oficina y desde campo sobre el mismo sistema.**

Este debería ser uno de los pilares de la comunicación comercial.

---

# 4. EL FLUJO DE NEGOCIO ES EL VERDADERO DIFERENCIAL

La funcionalidad individual de cada módulo no es necesariamente diferencial.

Lo interesante es el flujo completo.

El modelo que debería utilizarse para explicar SEVALOR es:

**CLIENTE**

↓

**PRESUPUESTO**

↓

**TRABAJO**

↓

**OPERARIO**

↓

**MATERIALES**

↓

**INCIDENCIAS**

↓

**HOJA DE CAMPO**

↓

**VALIDACIÓN**

↓

**FACTURACIÓN**

↓

**RESULTADO ECONÓMICO**

Cada acción del técnico puede tener consecuencias sobre:

* stock;
* costes;
* tiempo;
* incidencias;
* facturación;
* rentabilidad;
* histórico del cliente.

Este concepto es mucho más potente que decir:

> "Tenemos CRM + ERP + app de técnicos + almacén + IA."

---

# 5. GESTIÓN DE STOCK Y VEHÍCULOS

Esta es una de las funcionalidades que considero especialmente relevante para el segmento seleccionado.

Una empresa de instalaciones no solamente tiene:

**almacén central.**

Puede tener:

* almacén;
* vehículos;
* técnicos;
* materiales desplazados;
* materiales consumidos;
* reposiciones.

Por tanto, el verdadero problema es:

> **¿Dónde está realmente el material de la empresa en este momento?**

SEVALOR plantea precisamente una gestión que conecta almacén, picking, operarios y vehículos.

Esto puede convertirse en un argumento comercial muy fuerte.

Ejemplo:

> "Sabes qué tienes en el almacén, qué lleva cada vehículo y qué material se ha utilizado en cada trabajo."

Mucho más comprensible que:

> "Gestión avanzada de inventario multiubicación."

---

# 6. LA PWA DE OPERARIOS

La PWA tiene un planteamiento adecuado para el tipo de empresa objetivo.

Especialmente interesantes:

### Mobile-first

La aplicación está pensada para utilizarse en movilidad y no simplemente como una versión reducida del escritorio.

### Offline-first

Es especialmente relevante para:

* sótanos;
* instalaciones industriales;
* polígonos;
* zonas rurales;
* edificios con mala cobertura;
* desplazamientos.

La documentación especifica Dexie/IndexedDB para mantener información local y sincronizarla posteriormente.

### NIF + PIN

Reduce la fricción frente a sistemas de autenticación complejos.

### Fotografías e incidencias

Es especialmente útil para instalaciones y mantenimiento.

Un técnico puede documentar:

* problema;
* situación;
* solución;
* material utilizado;
* evidencia fotográfica.

Esto conecta directamente el mundo físico con la gestión administrativa.

---

# 7. COPILOT IA

Este puede convertirse en uno de los elementos de mayor valor de SEVALOR.

Pero hay que cambiar la forma de venderlo.

No vendería:

> "SEVALOR incorpora inteligencia artificial."

Eso ya no diferencia suficientemente.

El concepto realmente interesante es:

> **Una IA que conoce la información operativa de tu empresa.**

Por ejemplo, si la implementación final lo permite, un responsable podría preguntar:

* ¿Qué trabajos tenemos pendientes?
* ¿Qué técnicos están disponibles?
* ¿Qué incidencias están abiertas?
* ¿Qué vehículos están trabajando?
* ¿Qué presupuestos todavía no se han convertido en trabajo?
* ¿Qué trabajos están pendientes de facturar?
* ¿Qué materiales faltan?
* ¿Cuánto hemos gastado este mes?
* ¿Qué clientes tienen incidencias abiertas?

La diferencia está en el contexto.

No es simplemente un chatbot.

Es un posible:

> **copiloto operativo de la empresa.**

---

# 8. IA LOCAL Y PROTECCIÓN DE DATOS

La utilización de IA local puede ser un argumento comercial especialmente interesante para determinados clientes.

Sin embargo, la comunicación debe ser jurídicamente cuidadosa.

No recomiendo afirmar:

> "SEVALOR es 100 % RGPD."

La utilización de IA local no garantiza por sí sola el cumplimiento completo del RGPD.

Sí puede comunicarse algo mucho más sólido:

> **"La IA puede funcionar sobre la infraestructura y los datos de la empresa, reduciendo la necesidad de enviar información operativa a servicios externos."**

Y posteriormente documentar:

* dónde se almacenan los datos;
* quién puede acceder;
* cómo se controla el acceso;
* conservación;
* trazabilidad;
* copias de seguridad;
* tratamiento de datos;
* proveedores;
* seguridad;
* aislamiento entre empresas.

El RLS multi-tenant documentado es un buen elemento técnico de seguridad.

---

# 9. VERI*FACTU

La integración de facturación normativa añade una dimensión importante.

La documentación especifica:

* cadena de hashes SHA-256;
* QR;
* Outbox;
* comunicación con AEAT.

Esto hace que la facturación no sea simplemente un módulo añadido al final.

Puede formar parte del flujo:

**trabajo → validación → facturación → cumplimiento fiscal.**

Para el mercado español es un argumento importante.

No obstante, antes de utilizar afirmaciones comerciales definitivas sobre cumplimiento normativo, habría que realizar una auditoría específica de la implementación final y de los requisitos vigentes.

---

# 10. SEGMENTO DE CLIENTE MÁS ADECUADO

Después de analizar la estructura de SEVALOR, mantendría la decisión de comenzar por:

## EMPRESAS DE INSTALACIONES Y MANTENIMIENTO TÉCNICO

Especialmente:

### 1. Climatización / HVAC

Muy interesante porque combina:

* técnicos móviles;
* vehículos;
* materiales;
* instalaciones;
* incidencias;
* trabajos;
* clientes;
* presupuestos;
* mantenimiento;
* facturación.

### 2. Instalaciones eléctricas

También encaja muy bien:

* equipos de campo;
* materiales;
* vehículos;
* presupuestos;
* ejecución;
* documentación;
* incidencias;
* facturación.

### 3. Mantenimiento técnico de instalaciones

Especialmente empresas con varios técnicos desplazándose continuamente.

### 4. Fontanería / instalaciones

Puede encajar muy bien cuando existe una estructura empresarial de varios operarios.

### 5. Instalaciones industriales / SAT

Potencialmente uno de los perfiles de mayor valor para SEVALOR debido a:

* complejidad;
* materiales;
* desplazamientos;
* documentación;
* incidencias;
* trazabilidad.

---

# 11. TAMAÑO DE EMPRESA

Mantendría inicialmente el universo:

**5–50 trabajadores.**

Pero comercialmente concentraría el esfuerzo inicial en:

## 10–30 trabajadores

No como una regla absoluta, sino como hipótesis comercial a validar.

El motivo es que una empresa de 3–5 personas puede solucionar gran parte de sus problemas mediante:

* WhatsApp;
* Excel;
* Google Drive;
* programas de facturación.

Cuando aumenta el número de técnicos empiezan a aparecer problemas de:

* coordinación;
* materiales;
* vehículos;
* planificación;
* información;
* incidencias;
* control económico.

Ahí SEVALOR empieza a tener mucho más sentido.

---

# 12. CLIENTE IDEAL

El cliente ideal que se desprende de la aplicación sería aproximadamente:

**Empresa española de instalaciones o mantenimiento técnico**

con:

* 10–30 trabajadores;
* 5–20 técnicos desplazados;
* varios vehículos;
* almacén;
* materiales;
* múltiples trabajos simultáneos;
* presupuestos;
* facturación;
* incidencias;
* necesidad de controlar económicamente la actividad.

Y especialmente:

> **Una empresa que ya ha superado Excel + WhatsApp pero todavía considera demasiado complejos o caros los grandes ERP.**

Este puede ser un espacio comercial interesante para SEVALOR.

---

# 13. QUIÉN NO ES EL CLIENTE IDEAL

No intentaría vender inicialmente a todo el mundo.

Evitaría como primer objetivo:

### Microempresas

1–3 trabajadores.

Probablemente tienen poca necesidad de una plataforma tan completa.

### Grandes empresas

+50/100 trabajadores.

Pueden requerir:

* integraciones;
* procesos corporativos;
* ERP existentes;
* compras;
* BI;
* sistemas de RRHH;
* infraestructura IT;
* procedimientos de homologación.

No significa que SEVALOR no pueda servirles, sino que el ciclo comercial será diferente.

### Empresas puramente administrativas

No necesitan la fortaleza de SEVALOR.

### Transporte/logística

Aunque el producto tiene componentes logísticos, no lo utilizaría como segmento inicial.

---

# 14. POSICIONAMIENTO FRENTE A LA COMPETENCIA

El principal error sería intentar competir diciendo:

> "Tenemos más funcionalidades."

Los competidores también pueden presentar largas listas.

SEVALOR debería competir conceptualmente con:

> **integración operacional.**

La pregunta comercial no debería ser:

> "¿Cuántos módulos tienes?"

Sino:

> **"¿Puedes ver qué está pasando en tu empresa ahora mismo, desde el técnico que está en la calle hasta la factura?"**

Ese es el terreno donde SEVALOR tiene una historia que contar.

---

# 15. DIFERENCIA ENTRE SEVALOR Y UN FIELD SERVICE TRADICIONAL

Un Field Service tradicional puede centrarse principalmente en:

* agenda;
* técnicos;
* partes;
* clientes;
* órdenes de trabajo.

SEVALOR añade capas que permiten construir una visión más amplia:

**CAMPO**

→ operario

→ trabajo

→ incidencia

→ material

→ vehículo

→ fotografía

→ documentación

↓

**OFICINA**

→ cliente

→ presupuesto

→ stock

→ costes

→ facturación

→ contabilidad

↓

**DIRECCIÓN**

→ información económica

→ estado operativo

→ Copilot

Esta conexión es probablemente el núcleo de la propuesta.

---

# 16. EXPERIENCIA DE USUARIO: PRINCIPAL PUNTO A VALIDAR

Aquí es donde no puedo dar todavía una valoración definitiva.

La página pública permite comprobar la estructura de la aplicación, pero no completar el acceso interno desde esta herramienta.

Por tanto, quedan por validar experimentalmente:

* velocidad;
* navegación;
* coherencia visual;
* facilidad de aprendizaje;
* número de clics;
* formularios;
* creación de trabajos;
* asignación de técnicos;
* uso de mapas;
* gestión de almacén;
* flujo de incidencias;
* uso de la PWA;
* experiencia offline;
* sincronización;
* gestión de errores;
* experiencia del cliente final;
* Copilot;
* facturación.

Esta parte puede modificar bastante la valoración comercial final.

---

# 17. POSIBLE PROBLEMA DE PRODUCTO

La aplicación contiene muchos módulos.

Esto es una fortaleza tecnológica.

Pero puede convertirse en una debilidad comercial.

Un gerente que entra y encuentra:

* GIS;
* clientes;
* almacén;
* flota;
* proveedores;
* RRHH;
* CAD;
* chat;
* IA;
* contabilidad;

puede pensar:

> "Esto parece enorme."

Y una PYME no quiere comprar complejidad.

Quiere solucionar problemas.

Por eso recomiendo que la experiencia inicial se estructure alrededor de **procesos**, no alrededor de módulos.

Por ejemplo:

### Hoy

**¿Qué está pasando en mi empresa?**

* trabajos de hoy;
* técnicos;
* incidencias;
* vehículos;
* materiales;
* alertas;
* facturación pendiente.

### Operaciones

**Gestionar el trabajo**

### Recursos

**Personas + vehículos + materiales**

### Clientes

**Clientes + instalaciones + histórico**

### Economía

**Presupuestos + facturas + costes**

### Inteligencia

**Copilot**

Los módulos pueden existir internamente, pero el usuario debería pensar en problemas empresariales.

---

# 18. PROPUESTA DE MENSAJE COMERCIAL

No utilizaría como mensaje principal:

> "ERP para empresas."

Ni:

> "Software de gestión empresarial."

Ni:

> "Field Service Management."

Son demasiado genéricos.

La dirección que recomiendo investigar es:

> ## La central de operaciones de tu empresa.

Subtítulo:

> **Gestiona oficina, técnicos, vehículos, materiales, trabajos y facturación desde un único sistema.**

Y después:

> **Lo que ocurre en el campo llega directamente a la gestión de tu empresa.**

---

# 19. SEGUNDA PROPUESTA DE POSICIONAMIENTO

Otra posibilidad:

> ## Todo lo que pasa en tu empresa, en un solo lugar.

Pero esta frase es menos diferenciadora porque muchos competidores utilizan conceptos similares.

Por eso considero más interesante:

> ## De la oficina al campo. Del campo a la factura.

Esta frase comunica el flujo diferencial de SEVALOR.

---

# 20. FUNCIONES QUE MÁS DEBEN DESTACARSE

No todas las funcionalidades tienen el mismo valor comercial.

Priorizaría:

### NIVEL 1 — Diferenciadores

1. Gestión oficina + campo.
2. Stock real de almacén y vehículos.
3. Incidencias desde campo.
4. Integración trabajo → materiales → costes → facturación.
5. Visión global de técnicos y operaciones.
6. Copilot con contexto empresarial.
7. IA/localización de datos cuando esté plenamente implementada y auditada.

### NIVEL 2 — Argumentos de compra

8. GIS.
9. Planos.
10. Gestión de vehículos.
11. Gestión documental.
12. Comunicaciones con clientes.
13. Veri*factu.

### NIVEL 3 — Funciones de soporte

14. RLS.
15. Docker.
16. FastAPI.
17. PostgreSQL.
18. Redis.
19. arquitectura de microservicios.

Las últimas son importantes para ingeniería y seguridad, pero **no deben ser protagonistas de la venta al gerente**.

---

# 21. FORTALEZAS ACTUALES

### Muy fuerte

**Amplitud funcional**

El producto cubre una parte extraordinariamente amplia de las operaciones de una empresa técnica.

### Muy fuerte

**Arquitectura oficina/campo**

Está claramente pensada para empresas con trabajadores desplazados.

### Muy fuerte

**Integración de recursos físicos**

Materiales + vehículos + trabajadores + trabajos.

### Fuerte

**Orientación española**

Veri*factu/AEAT y contexto fiscal español pueden facilitar el posicionamiento frente a determinadas alternativas internacionales.

### Fuerte

**Offline**

Muy relevante para técnicos.

### Fuerte

**IA contextual**

Potencialmente diferencial si realmente puede consultar y utilizar toda la información empresarial.

### Fuerte

**Seguridad multi-tenant**

La utilización de RLS es técnicamente relevante.

---

# 22. RIESGOS

### Riesgo 1 — Exceso de complejidad

Es el principal.

### Riesgo 2 — Posicionamiento demasiado amplio

Si SEVALOR intenta ser:

> ERP + CRM + Field Service + GIS + IA + contabilidad + logística + RRHH...

el mensaje pierde fuerza.

### Riesgo 3 — Intentar vender todas las funcionalidades

No es necesario.

Hay que vender el problema principal y después demostrar que SEVALOR resuelve muchos problemas secundarios.

### Riesgo 4 — IA como reclamo

La IA debe demostrar utilidad concreta.

### Riesgo 5 — Prometer cumplimiento RGPD absoluto

Debe evitarse.

### Riesgo 6 — Mercado muy fragmentado

Existen numerosos productos especializados y generalistas.

SEVALOR necesita una diferenciación clara, no simplemente más funcionalidades.

---

# 23. VALORACIÓN DEL PRODUCTO

| Área                          | Evaluación |
| ----------------------------- | ---------: |
| Amplitud funcional            |       9/10 |
| Cobertura del ciclo operativo |       9/10 |
| Gestión de campo              |     8,5/10 |
| Gestión de recursos           |       9/10 |
| Potencial para instalaciones  |       9/10 |
| Potencial para mantenimiento  |       9/10 |
| Diferenciación conceptual     |     8,5/10 |
| IA                            |      8/10* |
| Seguridad/arquitectura        |     8,5/10 |
| Claridad comercial actual     |       6/10 |
| Simplicidad percibida         |      6/10* |
| Potencial comercial           |    8,5/10* |

* Pendiente de validación mediante uso real.

---

# 24. CONCLUSIÓN

Después de revisar la arquitectura, la documentación y la interfaz pública, mi valoración cambia respecto a la percepción inicial de SEVALOR.

**No considero que el problema principal sea que falten funcionalidades.**

De hecho, la situación parece ser la contraria.

SEVALOR tiene suficiente producto para competir en serio en un segmento concreto.

El reto ahora es:

> **convertir la complejidad tecnológica y funcional en una propuesta extremadamente sencilla de entender.**

El producto debería entrar en el mercado como:

# SEVALOR

## La central de operaciones para empresas de instalaciones y mantenimiento.

Y la promesa fundamental debería ser:

> **Controla lo que ocurre en el campo, lo que tienes en tus vehículos y almacenes y cómo afecta todo ello al negocio.**

El segmento inicial que considero más coherente con el producto es:

> **PYMES españolas de instalaciones y mantenimiento técnico de aproximadamente 10–30 trabajadores, con varios técnicos de campo, vehículos, materiales y actividad suficiente para necesitar coordinación operativa y control económico.**

No recomendaría abrir inicialmente diez verticales.

Empezaría con **instalaciones y mantenimiento técnico**, demostraría casos reales y posteriormente ampliaría hacia:

* climatización;
* electricidad;
* fontanería;
* SAT;
* instalaciones industriales;
* energía;
* mantenimiento especializado;
* jardinería profesional.

---

# 25. SIGUIENTE FASE RECOMENDADA

Antes de empezar a gastar dinero en publicidad, haría una segunda evaluación específicamente comercial.

### FASE 1

Identificar exactamente:

**¿Qué empresas españolas tienen el problema que SEVALOR resuelve mejor?**

### FASE 2

Construir el mercado:

* CNAE;
* número de empresas;
* tamaño;
* comunidades autónomas;
* concentración geográfica;
* número aproximado de empresas objetivo.

### FASE 3

Analizar competidor por competidor:

* precio;
* funciones;
* segmento;
* posicionamiento;
* puntos fuertes;
* puntos débiles;
* modelo comercial.

### FASE 4

Construir el **ICP definitivo de SEVALOR**.

### FASE 5

Diseñar:

* oferta;
* precio;
* landing;
* argumento comercial;
* demo;
* campaña de captación;
* outbound;
* LinkedIn;
* email;
* partners.

### FASE 6

Crear una lista inicial de empresas reales españolas que encajen con el ICP.

**Esta es la fase que yo haría ahora. No empezaría todavía con campañas publicitarias.**

Primero localizaría exactamente **qué tipo de empresa tiene más probabilidad de comprar SEVALOR y por qué**.
