Spec 001 — Dashboard i Torre de Control Operativa (/gestio)
AVISO DE CONSOLIDACIÓN ARQUITECTÓNICA: Esta especificación representa el Centro de Control Unificado de CampoPro Suite. Integra y fusiona por completo el módulo de seguimiento territorial y cartografía de campo, asumiendo el rol de Cockpit Único y Torre de Control Geográfica en tiempo real. Todas las antiguas rutas secundarias /gestio/feines/mapa e /gestio/incidencies quedan unificadas y redirigidas dinámicamente dentro de la ruta centralizada /gestio.
--------------------------------------------------------------------------------
Contexto y objetivo
El Dashboard de Gestión (/gestio) es el Centro Neurálgico, Torre de Control Cartográfica y Cockpit Operativo Integral de la empresa técnica. Unifica en una sola interfaz interactiva y dinámica la supervisión de la jornada, la actividad en tiempo real de las cuadrillas en el terreno, la cartografía territorial con capas técnicas de infraestructura propia, el seguimiento de la flota móvil y el Centro de Resolución de Incidencias en Tiempo Real mediante un Drawer lateral no invasivo.
Actúa como radar de mando para la oficina técnica (ingenieros y supervisores) y la dirección general (Boss), permitiendo coordinar desvíos, solventar imprevistos críticos y optimizar rutas sin dispersión de pantallas ni duplicidades:

    Segregación Estricta de Métricas Financieras (Cero Fugas entre Roles): La Torre de Control Operativa (/gestio) está completamente libre de magnitudes financieras globales, facturación acumulada o balances contables. Todos los datos económicos globales, márgenes empresariales y módulos Veri*factu se segregan y confinan en la especificación contable (/gestio/comptabilitat), evitando cualquier riesgo de fuga de permisos o visualización indebida entre Boss e Ingeniero. El HUD superior se consagra con exclusividad al pulso operativo y técnico en tiempo real, operando como un indicador de pulso operativo global e inmutable de la empresa (independiente de los filtros locales del mapa).
    Cartografía Open Source, Soberanía de Datos y Redes Propias: Sustentada al 100% sobre tecnologías abiertas (Leaflet / MapLibre GL JS, OpenStreetMap y ortofotos satelitales PNOA del IGN España / ESRI), libre de costes por uso de APIs propietarias de terceros. Queda estrictamente prohibido el uso de APIs comerciales como Google Maps o Mapbox para evitar la filtración de la dirección IP de los ingenieros, coordenadas de las fincas de los clientes o telemetría de la flota fuera del territorio de la Unión Europea, garantizando el cumplimiento estricto del RGPD. Proyecta simultáneamente la ubicación de obras, el posicionamiento de furgonetas/cuadrillas y la Capa Vectorial de Infraestructura Técnica de la Empresa (tuberías, líneas de baja tensión, arquetas y válvulas en formato GeoJSON/KML custodiados localmente en /docs/<empresa_id>/planols/vectorials/), adaptada de forma dinámica según la vertical de la empresa.
    Paneles Colapsables Bajo Demanda y Diseño 100% Responsive: Para maximizar la visibilidad limpia y amplia de la cartografía, los paneles laterales permanecen ocultos por defecto:
        Panell Esquerre (Sota Demanda / Acordió de Quadrilles): Estructurado jerárquicamente por las cuadrillas activas que disponen de hoja de tarea (fulla de tasca) asignada para la fecha configurada en el filtro temporal. El personal de retén o guardia dispone de una hoja de tarea interna asignada a labores de almacén/base, garantizando su presencia en el panel para posibilitar asignaciones inmediatas por Drop and Go. Al hacer clic sobre una cuadrilla, se despliega el acordeón con la secuencia ordenada de tareas del día; al clicar sobre una orden, el mapa hace destellar (highlight) su posición y despliega sus detalles técnicos.
        Drawer Lateral Derecho (Emergencias e Incidencias en Vivo con Alerta No Invasiva): Permanece oculto por defecto. Ante la entrada de una nueva incidencia desde campo, no se despliega abruptamente para no interrumpir acciones de precisión en curso (como arrastres de tareas o inspección de planos); en su lugar, emite una alerta visual y acústica no bloqueante (banner flotante superior, campana destellando en rojo y aviso sonoro discreto) para que el supervisor abra el Drawer en el momento oportuno. Integra reproductor de audio nativo de notas de voz de campo, fotos periciales ampliables, informe técnico redactado por el Copilot IA, enlace telefónico urgente (tel:) y tramitación multicanal documentada.
    Canal Multicanal Riguroso con el Cliente: El Bot de Telegram actúa como un canal ágil y rápido de información, pero en ningún caso es de uso obligatorio para el cliente. Los canales principales de relación contractual son el teléfono y el email (incorporando este último un enlace web securizado con token para la aceptación formal del presupuesto extra). En llamadas telefónicas, el supervisor remite al cliente a la validación de dicho enlace o al Bot de Telegram: únicamente cuando se tiene la certeza fehaciente de la documentación aceptada mediante firma o clic con registro de IP, se libera y autoriza la reanudación de la faena en campo.
    Almacenamiento Soberano en Memoria Interna y Servidor Hetzner (Alemania): Todos los archivos (audios de voz, fotografías periciales, planos vectoriales y albaranes) residen en los discos locales de la empresa y en el servidor Hetzner Cloud (Falkenstein / Nuremberg, Alemania - UE) bajo /data/<empresa_id>/... y /docs/<empresa_id>/..., eliminando totalmente cualquier servicio cloud externo (como AWS S3) en cumplimiento estricto del RGPD.
    Tolerancia Cero a Datos Ficticios (Zero Mock Data): Prohibición absoluta de datos simulados o hardcodeados; en ausencia de datos reales el sistema opera en un Estado Día 0 real centrado en las coordenadas oficiales de la empresa provistas en el onboarding del SaaS.
    Mandato Constitucional Human-in-the-Loop (HITL): Albaranes, presupuestos de imprevistos redactados por Copilot e incidencias disciplinarias jamás se consolidarán ni saldrán de la plataforma sin la aprobación humana explícita del supervisor, responsable de RRHH o Boss antes de su envío al cliente, su pase a facturación o su anotación en el expediente del operario.

--------------------------------------------------------------------------------
Usuarios / actores y Matriz de Acceso (Zero-Trust)
El backend garantiza el aislamiento de datos por rol mediante endpoints específicos y esquemas segregados (la seguridad nunca recae en la mera ocultación visual de la interfaz):

    Boss (Gerencia / Propietario): Acceso total e irrestricto a la supervisión operativa de cuadrillas, telemetría de flota, mando operativo en mapa (Drop and Go, reasignaciones, cambio de prioridades), resolución de incidencias graves desde el Drawer lateral, llamada directa a capataces, autorización de compras extraordinarias en ferreterías locales, consulta histórica y futura de tareas, configuración de tarifas maestras (/gestio/configuracio/tarifes), y aprobación humana final de albaranes/presupuestos de Copilot para su derivación a facturación. Es el único rol con acceso a la pantalla de balances contables y KPIs macroeconómicos de la empresa (/gestio/comptabilitat).
    Ingeniero / Supervisor Técnico: Centro de mando técnico operativo bajo el principio de "Una cuadrilla, un supervisor". Seguimiento en vivo de obras, atención en el Drawer lateral ante alertas de incidencias, audición de notas de voz de operarios, revisión y aprobación humana previa del informe y presupuesto de Copilot antes de remitirlo al cliente, contacto telefónico directo canalizando la aceptación formal por email/Telegram, activación de grúas en averías de flota desacoplando tareas y coordinando transporte alternativo si no hay plazas suficientes, comprobación de disponibilidad de herramientas en furgonetas cercanas mediante la finalización de tareas matinales en la hoja de faena o localización cartográfica de ferreterías locales con llamada previa de reserva, despacho de vehículos de auxilio con hoja de tarea y GPS en PWA, y aprobación y ajuste humano de los presupuestos y liquidaciones finales de Copilot antes de remitirlos a facturación.
        Autorización Documental Específica: Autorizado a la búsqueda, apertura y lectura de facturas y presupuestos unitarios de clientes para contrastar mediciones, piezas y precios de la intervención técnica en obra. Bloqueo estricto a nivel de API sobre las metadatas contables de la empresa (libro mayor, balance de facturación global acumulada, cuentas de resultados, conciliación bancaria) y bloqueo de acceso al módulo /gestio/comptabilitat.
    Secretaria / RRHH: Perfil de solo lectura y consulta en el Dashboard cartográfico. Supervisión visual del despliegue para atención telefónica a clientes, verificación de presencia de cuadrillas en zonas de obra, canalización de avisos a mandos técnicos, consulta de incidencias de flota y obras activas en el Drawer en modo lectura, y recepción, evaluación objetiva individualizada y custodia confidencial en el expediente del trabajador de las incidencias disciplinarias (imputando al conductor real el siniestro vial según atestado oficial, al encargado de almacén/picking la omisión de materiales con stock, y al capataz como responsable inicial de omisiones de reporte o mala ejecución de la cuadrilla). No dispone de permisos para asignar tareas, reasignar órdenes, arrastrar Drop and Go, autorizar compras ni alterar prioridades.
    Responsable de Cuadrilla (Capataz / /operari): Opera desde su PWA móvil de campo. Emite telemetría GPS inteligente por eventos orientada al ahorro de batería. El principio Offline-First rige estrictamente para los datos técnicos de la hoja de tarea (notas de voz, fotos, horas, planos y consumos en IndexedDB cifrado con Web Crypto API); sin embargo, ante una incidencia imprevista urgente que bloquee el trabajo, tiene la obligación procedimental de desplazarse para buscar cobertura móvil y notificar el grado de la incidencia lo antes posible a la base. En trabajos ordinarios sin incidencias, la PWA sincroniza al recuperar cobertura para contrastar consumos frente al presupuesto inicial.
    Operario de Cuadrilla (/operari): Ejecuta la faena técnica en campo. Puede continuar con las fases viables de la obra mientras el capataz y la oficina técnica gestionan la aprobación de un imprevisto con el cliente. En caso de cancelarse la obra por rechazo del presupuesto por el cliente, la cuadrilla se retira ordenadamente, el pin pasa a Negro en el mapa y la cuadrilla se reasigna desde la base.
    Cliente Final (Canal Multicanal: Teléfono, Email y Bot de Telegram): Recibe avisos transaccionales de salida y llegada. Ante imprevistos de obra, recibe por Email (con enlace securizado y token de firma) o de forma complementaria por Telegram el informe técnico de Copilot (previamente revisado por el supervisor) con fotos y la hoja interactiva de aceptación. El supervisor puede contactarlo telefónicamente para explicar la situación, remitiéndole a validar formalmente la documentación. Al pulsar [Aprobar ampliación [Importe €]], la aceptación queda registrada de forma inmutable; si pulsa [Rechazar], la obra se detiene y se procede a la liquidación provisional.

--------------------------------------------------------------------------------
Historias de usuario

    H1: Como Ingeniero o Boss, quiero tener una pantalla de mando única que me ofrezca una visión instantánea de mis cuadrillas en ruta y el mapa comarcal con sus trabajos de hoy, con un HUD operativo global e inmutable sin magnitudes contables de la empresa.
    H2: Como Ingeniero, quiero que los paneles laterales permanezcan ocultos por defecto para disfrutar de una visión limpia del mapa, disponiendo de un panel izquierdo en acordeón por cuadrillas (incluyendo las de retén con faenas de almacén) y un discriminador multi-criterio por capas y colores con botones [Marcar tots] y [Desmarcar tots].
    H3: Como Ingeniero, cuando una cuadrilla reporte una avería oculta o necesidad de material extra en obra, quiero recibir una alerta visual y acústica no invasiva que me permita finalizar mi acción actual en el mapa antes de abrir el Drawer de Incidencias para escuchar el audio, revisar fotos periciales y validar el presupuesto de Copilot.
    H4: Como Ingeniero, quiero que el informe técnico suplementario de Copilot se remita al cliente por Email o Telegram con enlace de aceptación formal a 1 clic, pudiendo llamarlo telefónicamente para explicarle el caso, asegurando que la obra solo se reanuda con la certeza documental de la aceptación.
    H5: Como Ingeniero, cuando una cuadrilla llegue a una cancela cerrada, quiero que el operario pulse Start iniciando el cómputo en Verde, conmute a Rojo al abrir la incidencia y que el cronómetro corra ininterrumpidamente hasta que la cancela sea abierta (volviendo a Verde desde la PWA o el Dashboard) o hasta la cancelación/conclusión de la obra, aplicando el rollback del acumulador de horas a las 18:00 si se queda inconclusa de un día para otro.
    H6: Como Supervisor, cuando una furgoneta sufra una avería inmovilizante en carretera, quiero activar la grúa con un clic, sabiendo que el material de la furgoneta permanece custodiado bajo el seguro de responsabilidad del taller/grúa, y reasignar las tareas de la tarde mediante Drop and Go.
    H7: Como Ingeniero, quiero buscar en el meta-buscador universal cualquier factura o presupuesto unitario de un cliente para contrastar precios y unidades técnicas instaladas, sin tener acceso a los balances globales ni al módulo de contabilidad.
    H8: Como Boss, quiero disponer de una pantalla maestra de configuración (/gestio/configuracio/tarifes) donde definir los costes horarios de mano de obra por categoría, desplazamientos, horas extras y tarifas horarias de maquinaria pesada.
    H9: Como Capataz de campo, si mi terminal móvil se apaga o avería en zona sin cobertura, quiero saber que el protocolo me exige buscar cobertura para activar la incidencia de terminal afectado y permitir que la oficina técnica transfiera el rol a otro compañero.
    H10: Como Secretaria o Boss, quiero que el backend ingrese automáticamente toda incidencia en los historiales técnicos (orden, operario, vehículo), pero que cualquier calificación de falta o apertura de expediente disciplinario en RRHH dependa estrictamente de una decisión humana explícita y basada en criterios objetivos de atribución de responsabilidad.

--------------------------------------------------------------------------------
Requisitos Funcionales (Notación EARS Estricta)
Bloque 1: Cabecera, Meta-Buscador Universal y HUD Operativo No Financiero

    RF-01 (Ubiquitous): EL SISTEMA mantendrá visible en la cabecera superior un saludo dinámico según la franja horaria, la fecha actual en formato legible, el nombre y rol del usuario conectado, selector de idioma y un botón directo "?" de ayuda contextual y manual operativo.
    RF-02 (Event-driven): CUANDO el usuario introduce 2 o más caracteres en el meta-buscador universal de la cabecera, EL SISTEMA permitirá seleccionar chips de filtro por entidad (Todos, Clients, Factures, Operaris, Ordres, Vehicles, Almagatzem), desplegando los resultados coincidentes de forma insensible a mayúsculas y acentos con un tiempo de respuesta inferior a 250 ms.
    RF-03 (Event-driven): CUANDO el usuario selecciona un resultado del meta-buscador, EL SISTEMA redirigirá inmediatamente a la ficha, orden de trabajo o documento correspondiente:
        Acceso Técnico de Ingenieros a Facturas y Presupuestos Unitarios: El rol Ingeniero está explícitamente autorizado a buscar, abrir y consultar presupuestos y facturas unitarias individuales de clientes, visualizando la descripción de partidas, mediciones, materiales y precios facturados al cliente para comprobación técnica en obra.
        Desacoplamiento de Endpoints para Seguridad: SI el usuario tiene rol Ingeniero, ENTONCES la consulta se procesará a través de un endpoint desacoplado de operaciones técnicas (/api/v1/gestio/clients/{id}/factures-tecniques), serializado mediante FacturaConsultaTecnicaDTO que purga de forma obligatoria números de cuenta bancaria, mandatos SEPA, cuentas del Plan General Contable (PGC) y márgenes de rentabilidad de la empresa.
        Bloqueo Estricto de Metadatos Contables de Empresa: EL BACKEND bloqueará de forma estricta al rol Ingeniero la consulta de metadatos contables agregados (márgenes de beneficio de la empresa, libro mayor, balance de facturación global acumulada, conciliación bancaria) y denegará el acceso a la ruta /gestio/comptabilitat devolviendo un error HTTP 403 Forbidden.
    RF-04 (State-driven): SI la búsqueda en el meta-buscador no arroja coincidencias en la categoría seleccionada, ENTONCES EL SISTEMA mostrará un estado vacío real ("Sin resultados coincidentes") con opción de limpiar el filtro, sin inyectar datos simulados (Zero Mock Data).
    RF-05 (Event-driven): CUANDO el usuario hace clic sobre el botón "Crear Orden de Trabajo", EL SISTEMA abrirá la vista de creación completa (/gestio/feines/crear).
    RF-06 (Event-driven): CUANDO una cuadrilla registra una incidencia desde campo, EL SISTEMA activará en la cabecera una alerta visual y acústica no bloqueante: conmutará el icono de la campana a color rojo destellante, incrementará el contador numérico de pendientes y mostrará un banner flotante discreto superior, permitiendo al usuario continuar su interacción actual sin pérdida de foco.
    RF-07 (Ubiquitous): EL SISTEMA proyectará en la parte superior del Dashboard un HUD de Pulso Operativo en Tiempo Real estrictamente desprovisto de magnitudes financieras o devengos económicos, que actuará como indicador operativo global e inmutable de la empresa (independiente de los filtros locales aplicados sobre el mapa), conformado por:
        Cuadrillas Activas en Jornada: Contador y desglose de cuadrillas desplegadas (En Faena / Activas, En Camino / Desplazamiento, En Standby / Base de Retén).
        Órdenes de Trabajo de Hoy: Contador de tareas del día clasificadas en En Curso (Verde), Pendientes (Naranja) y Completadas (Blanco).
        Incidencias Urgentes Abiertas [Rojo]: Contador destacado de bloqueos en obra o paradas de flota no resueltas, con enlace directo para desplegar el Drawer de incidencias.
        Estado de Flota Móvil: Furgonetas activas en carretera (Azul), vehículos en espera/standby (Lila) y unidades con avería mecánica (Rojo).
        Alertas Preventivas Técnicas: Indicador de alertas urgentes de almacén (materiales con existencias físicas iguales o inferiores al stock mínimo de seguridad) y alertas inminentes de flota (ITV o revisiones técnicas a vencer en menos de 7 días).

Bloque 2: Arquitectura Cartográfica Open Source, Capas y Redes Propias

    RF-08 (Ubiquitous): EL SISTEMA renderizará en el área central de /gestio un mapa interactivo a pantalla completa basado en tecnología abierta (Leaflet / MapLibre GL JS), excluyendo de forma estricta cualquier dependencia, costes o cuotas financieras asociadas a claves de API comerciales privativas (como Google Maps o Mapbox).
    RF-09 (Ubiquitous): EL SISTEMA dispondrá en el mapa de un selector flotante para alternar de manera instantánea entre dos capas cartográficas base:
        Vista Callejero: Teselas vectoriales de OpenStreetMap / Carto para entornos urbanos e industriales.
        Vista Satélite / Ortofoto: Teselas aéreas de alta resolución procedentes de servidores públicos del PNOA (Plan Nacional de Ortofotografía Aérea - IGN España) o ESRI World Imagery abierto, alojados en el territorio de la Unión Europea, garantizando la soberanía de los datos.
    RF-10 (Ubiquitous): EL SISTEMA proyectará simultáneamente en el mapa dos capas operativas dinámicas e independientes en tiempo real (vía WebSockets/SSE):
        Capa de Obras y Clientes: Ubicaciones geográficas de las fincas, parcelas o inmuebles donde se ejecutan las órdenes de trabajo programadas.
        Capa de Cuadrillas y Flota: Posición geográfica en tiempo real de los vehículos y cuadrillas en jornada activa.
    RF-11 (Ubiquitous): EL SISTEMA integrará una Capa Vectorial de Infraestructura Técnica de la Empresa superpuesta y conmutable ("Mostrar Red Técnica"):
        El mapa web de supervisión renderizará la cartografía vectorial completa comarcal/empresarial cargando archivos estándar (GeoJSON / KML) custodiados en el servidor local (/docs/<empresa_id>/planols/vectorials/) representando trazados de tuberías, redes eléctricas de baja tensión, arquetas, hidrantes, colectores y válvulas de corte; dicha capa se adaptará dinámicamente según la vertical activa de la empresa.
        La PWA del operario (/operari) recibirá y procesará exclusivamente la porción de plano técnico y red vectorial acotada al ámbito geográfico específico de sus órdenes de trabajo asignadas en la jornada.
        CUANDO el usuario hace clic sobre un elemento de la red técnica, EL SISTEMA desplegará una etiqueta flotante con sus especificaciones de ingeniería (p. ej. Tubería PE Ø110 PN10 — Sector Norte).
        Las anotaciones gráficas y pines sobre el plano técnico quedarán estrictamente encapsulados dentro de la hoja de trabajo de la orden o canalizados como incidencias formales del operario, garantizando la integridad de la base cartográfica maestra.
    RF-12 (Ubiquitous): EL SISTEMA exigirá la Georreferenciación Obligatoria Previa de toda Orden de Trabajo, quedando prohibido agendar o planificar tareas sin coordenadas latitud/longitud contrastadas en base de datos:
        La captura de coordenadas se efectuará mediante el envío del pin de ubicación geográfica por el cliente a través del Bot de Telegram o Email, o mediante clic manual de la oficina técnica sobre la ortofoto aérea del mapa al crear la orden.
        Cada orden de trabajo dispondrá de una geovalla perimetral de 50 metros de cortesía para el control de presencia en obra en zonas rurales o fincas con Punto Cero en cancela de acceso. SI la señal GPS reporta una precisión (coords.accuracy) menor o igual a 20 metros, el sistema validará el fichaje dentro del radio inmediato del punto de intervención; la geovalla de 50 metros se mantendrá activa para absorber entornos rurales con menor precisión GNSS o accesos en cancelas perimetrales. Una vez cruzada la cancela de acceso (Punto Cero) y fichada la llegada, la cuadrilla permanecerá en estado Verde (En faena) computando el tiempo con independencia de desplazamientos internos por la finca.
    RF-13 (Ubiquitous): PROTOCOLO PUNTO CERO / CANCELA CERRADA, CRONÓMETRO CONTINUO Y TRANSICIONES DE ESTADO:
        Llegada y Activación: Al posicionarse la cuadrilla en la cancela o entrada (Punto Cero), el operario pulsa "Start" en la PWA; la orden adquiere estado Verde (En faena / En curso) y el cronómetro de tiempo de ejecución de la obra comienza a correr.
        Reporte de Acceso Bloqueado: SI el acceso físico está bloqueado (cancela con candado o cliente no comparecido), ENTONCES EL SISTEMA conmutará el marcador de la obra instantáneamente de Verde a Rojo al pulsar el capataz el botón "Incidencia" en la PWA.
        Cómputo Ininterrumpido: El cronómetro de tiempo de la orden continuará corriendo de forma ininterrumpida computando el tiempo de permanencia de la cuadrilla en el lugar. La incidencia no detiene el contador. El operario NO pausa el tiempo mientras aguarda la apertura.
        Rollback Funcional por Pernocta: SI la obra permanece en estado Rojo (Incidencia activa / Inconclusa) al finalizar la jornada laboral (18:00), ENTONCES EL SISTEMA detendrá administrativamente el acumulador de horas de la orden a las 18:00 para evitar facturar horas extras nocturnas ficticias. CUANDO sean las 08:00 AM del día siguiente (Día +1), EL SISTEMA cargará automáticamente dicha orden en la cabecera del panel de despacho para forzar la decisión humana de reanudación o reasignación del supervisor.
        Resolución de Acceso: Cuando la cancela es abierta por el cliente o se solventa el acceso, tanto el operario desde la PWA (marcando "Acceso Abierto") como el supervisor desde el Drawer web pueden resolver la incidencia, provocando que el pin de la obra conmute de nuevo de Rojo a Verde. El cronómetro continúa corriendo hasta que la tarea finalice formalmente (Completada en Blanco) o sea Cancelada definitivamente (Negro).
        Liquidación en Cancelación por Espera Inviable: SI el acceso resulta imposible tras el tiempo de espera, ENTONCES EL SISTEMA liquidará al cliente el coste del tiempo de permanencia más el coste del desplazamiento, tarificado según los precios maestros de mano de obra y maquinaria configurados en /gestio/configuracio/tarifes.
    RF-14 (State-driven): SI dos o más órdenes de trabajo coinciden en la misma finca, edificio o parcela muy próxima, ENTONCES EL SISTEMA agrupará los marcadores en una burbuja numérica de agrupación (clustering); CUANDO el usuario hace clic sobre la burbuja, EL SISTEMA desplegará un abanico permitiendo consultar y abrir cada orden de trabajo de forma completamente individual.
        Reconocimiento de Convivencia Operativa: SI coinciden dos cuadrillas en la misma parcela, ENTONCES EL SISTEMA reconocerá la convivencia física legítima en el mismo espacio para tareas distintas o colaboración técnica coordinada, suprimiendo alertas erróneas de conflicto en la campana de incidencias.

Bloque 3: Código Cromático de Estados y Popovers Informativos

    RF-15 (Ubiquitous): EL SISTEMA representará los marcadores (pins) en el mapa mediante una simbología cromática diferenciada por entidad (Obras vs. Vehículos), estrictamente funcional e independiente del tema camaleónico del software:
        Órdenes de Trabajo (Obras en el Terreno):
            Naranja: Pendiente / No iniciada (la cuadrilla aún no ha iniciado el desplazamiento).
            Azul: Cuadrilla en camino / En tránsito hacia la obra.
            Verde: En faena / En curso (al fichar llegada dentro de la geovalla de la obra).
            Rojo: Con incidencia activa / Parada técnica en obra (falta de material, avería in situ o imprevisto técnico reportado).
            Blanco: Completada (tarea finalizada, documentada con fotos y cerrada por la cuadrilla; incluye órdenes cerradas bajo "Cliente Ausente").
            Negro: Cancelada en cualquier momento (en ruta o durante la faena; se retira la cuadrilla y se emite albarán provisional).
        Vehículos y Flota Móvil:
            Azul: En tránsito con tarea asignada (desplazamiento hacia obra).
            Lila / Púrpura (Standby o Tránsito sin Tarea): Vehículos activos en jornada que no tienen ninguna orden en curso asignada (espera en nave, retorno a base o tras completarse/cancelarse una obra).
            Rojo: Avería mecánica o inmovilizado en carretera (pinchazo, auxilio o remolque).
            Inmóvil en Obra (Sin Color / Neutro): Cuando la cuadrilla está dentro de la obra executing la faena (Verde), el vehículo físico permanece estacionado e inmóvil en la parcela, por lo que no dispone de color cromático activo en el mapa (icono neutro integrado en la cuadrilla), evitando saturación visual hasta que reanude la marcha.
        Regla de Disociación Ontológica: Los estados Blanco y Negro aplican exclusivamente a las órdenes de trabajo. Cuando una orden se completa (Blanco) o se cancela (Negro), el vehículo no se completa ni se cancela: conmuta automáticamente a Lila (Standby) o pasa a Azul hacia la siguiente parada asignada.
    RF-16 (Event-driven): CUANDO el usuario hace clic sobre cualquier marcador del mapa, EL SISTEMA desplegará una tarjeta emergente (popover):
        Marcador de Obra: Detallará código de orden, cliente, teléfono directo (tel:), cuadrilla y vehículo asignados, estado operativo y enlace para abrir la hoja de trabajo completa.
        Marcador de Vehículo / Cuadrilla: Detallará matrícula/código de flota (con enlace a /gestio/flota), capataz responsable (enlace a su ficha), relación nominal de operarios a bordo, orden en curso y botón destacado de "Llamar al Capataz" (tel:).

Bloque 4: Paneles Colapsables Bajo Demanda y Navegación Temporal

    RF-17 (Ubiquitous): PRIORIDAD A LA VISIÓN LIMPIA DEL MAPA, APERTURA BAJO DEMANDA Y DISEÑO 100% RESPONSIVE:
        Todos los paneles laterales (panel izquierdo de cuadrillas y Drawer derecho de incidencias) permanecerán ocultos y colapsados por defecto para maximizar la visibilidad y supervisión global de la cartografía. No permanecen abiertos de forma continua; únicamente se despliegan cuando el usuario hace clic sobre su pestaña o cuando se recibe una nueva incidencia emergente.
        Coexistencia Visual y Adaptabilidad Responsive 100%: El Drawer de incidencias y el panel de órdenes diarias pueden coexistir visualmente sin destrucción mutua de estado:
            En pantallas de escritorio: coexisten en vista desacoplada (panel de órdenes a la izquierda, Drawer de incidencias a la derecha y mapa despejado en el centro).
            En dispositivos móviles o tablets de supervisores: la interfaz se adaptará de forma 100% responsive, presentándose los paneles como pestañas alternadas, modales deslizables o capas superpuestas, impidiendo que el mapa quede bloqueado y garantizando la fluidez táctil.
    RF-18 (Ubiquitous): PANELL ESQUERRE (SOTA DEMANDA / ACORDIÓ DE QUADRILLES PER FULLA DE TASCA):
        El panel lateral izquierdo se desplegará a voluntad del usuario haciendo clic sobre su pestaña lateral izquierda (compatible con pantallas táctiles, sin depender de eventos hover).
        Estructura Jerárquica por Cuadrillas: Agrupará y mostrará exclusivamente las cuadrillas activas que tengan una hoja de tarea asignada para la fecha seleccionada en el mapa.
        Inclusión de Personal en Retén / Standby: El personal de retén o guardia a disposición en nave contará con una hoja de tarea interna asignada a labores de almacén/base, figurando visible en el panel para poder consultar su composición y efectuar asignaciones directas por Drop and Go.
        Acordeón Desplegable: Al hacer clic sobre una cuadrilla, se desplegará su lista de tareas asignadas para la jornada configurada, ordenadas cronológicamente por secuencia planificada de ejecución, indicando código de tarea, cliente, horario previsto y estado cromático.
        Highlight y Apertura de Detalles: CUANDO el usuario hace clic sobre una orden de trabajo dentro del acordeón, EL SISTEMA hará destellar y parpadear visualmente (highlight) el marcador de la cuadrilla y de la obra asignada en el mapa (manteniendo inalterado el nivel de zoom para no desorientar el contexto geográfico global) y abrirá el popover con los detalles técnicos de la orden.
        Sección de Canceladas: Las órdenes canceladas en ruta o en faena se desplazarán automáticamente a una sección inferior colapsable ("Órdenes Canceladas / Historial").
    RF-19 (Ubiquitous): NAVEGACIÓN TEMPORAL (FILTRO DE FECHA):
        Filtro de Jornada Activa ("HOY"): Coexisten cuadrillas activas con telemetría GPS en vivo y órdenes de trabajo programadas para la jornada.
        Filtro de Días Pasados (Historial Retrospectivo): Renderiza estáticamente los puntos geográficos donde se cerraron o ejecutaron las obras de esa fecha seleccionada; las cuadrillas y furgonetas no se dibujan en fechas pasadas y en ningún caso se registrarán ni dibujarán trazas de carretera (privacidad laboral, cumplimiento estricto del RGPD).
        Filtro de Días Futuros: Proyecta la dispersión geográfica de las obras agendadas para planificar y optimizar rutas futuras; la capa de cuadrillas permanece desactivada al carecer de telemetría física anticipada.
        Persistencia Temporal de Incidencias: Las incidencias activas permanecen marcadas y visibles en el mapa hasta su efectiva resolución, independientemente de la fecha en que se abrieron o del filtro temporal seleccionado, garantizando que ninguna parada técnica quede desatendida.

Bloque 5: Filtros Rápidos y Discriminador de Capas del Mapa

    RF-20 (Ubiquitous): EL SISTEMA dispondrá de un Discriminador Flotante Multi-Criterio de Capas y Entidades, independiente del filtro temporal de fecha:
        Control Fino de Visibilidad: Permitirá activar o desactivar capas y entidades una a una, en grupo o ninguna, mediante casillas de selección (checkboxes) independientes:
            Obras por Estado / Color: Naranja (Pendientes), Azul (En tránsito), Verde (En faena), Rojo (Con incidencias), Blanco (Completadas), Negro (Canceladas).
            Flota Móvil: Azul (En tránsito), Lila (Standby / Retén), Rojo (Avería).
            Capa Vectorial de Red Técnica: Tuberías, baja tensión, arquetas y válvulas.
            Puntos de Suministro: Capa de ferreterías y distribuidores locales.
            Incidencias Persistentes de Días Anteriores: Permite aislar u ocultar incidencias heredadas para limpiar la vista.
        Botones de Acción Rápida: El discriminador incorporará en cabecera los botones [Marcar tots] (activa el 100% de las capas) y [Desmarcar tots] (limpia completamente el mapa dejando solo la base cartográfica).
        Buscador de Texto del Mapa: Localiza en tiempo real una orden de trabajo, cliente o dirección en el mapa.

Bloque 6: Mando Operativo, "Drop and Go" e Intervenciones Urgentes en Campo

    RF-21 (Ubiquitous): MANDO OPERATIVO, CONCOMITANCIA DE ROLES Y RESOLUCIÓN DE CONCURRENCIA:
        EL SISTEMA habilitará acciones de mando operativo en el mapa para los roles con permisos de escritura técnica (Boss e Ingeniero), manteniendo al rol Secretaria en modo estricto de solo lectura y consulta.
        Concomitancia Operativa y Protocolo de Reparto: Las cuadrillas se distribuyen operativamente entre los ingenieros bajo el protocolo de empresa "Una cuadrilla, un supervisor". Cada supervisor operará en su propia sesión independiente aunque síncrona en tiempo real (vía WebSockets). Si el Boss o un colega reasigna una orden o actúa sobre una cuadrilla asignada a otro supervisor, la acción se sincroniza en vivo en la pantalla de todos los mandos activos con una alerta visual de actualización, preservando la coherencia sin bloqueos destructivos.
        Resolución de Concurrencia en Backend (First-Come, First-Served): En caso de colisión simultánea al milisegundo (p. ej. dos ingenieros intentando reasignar la misma orden o actuar sobre la misma cuadrilla vía Drop and Go), el backend procesará estrictamente la primera petición confirmada (First-Write-Wins) mediante bloqueo pesimista en base de datos (SELECT FOR UPDATE) y control de versión optimista (version_id) sobre la orden, denegando la segunda y emitiendo en pantalla una notificación informativa no bloqueante ("La orden o cuadrilla ya ha sido actualizada por otro supervisor").
        Permite reasignar órdenes de trabajo arrastrándolas en el mapa o en el panel de cuadrillas.
        Permite alterar el orden de prioridad y secuencia de ejecución de las tareas pendientes de una cuadrilla.
        Restricción de Asignación Ordinaria: No permitirá asignar una obra ordinaria a una cuadrilla sin hoja de picking de nave cargada con el material necesario (Spec 004), salvo en cancelaciones previas con traspaso de stock consolidado (Spec 004 RF-25).
        Blindaje Operativo en Zonas de Sombra: Si una cuadrilla opera en zona de sombra, la orden permanecerá en estado Verde (En faena) y el supervisor no asignará ninguna otra tarea en esa franja horaria. Al recuperar cobertura, la PWA sincronizará automáticamente todos los datos hacia la base de datos central.
        Reactivación y Transición tras Incidencia: La resolución formal de una incidencia y la conmutación de estado en el sistema es una tarea exclusiva del supervisor desde el Drawer web o del operario desde la PWA; una vez resuelta y concluidos los trabajos técnicos en campo, el responsable de cuadrilla (capataz) podrá cerrar la tarea definitivamente desde la PWA.
    RF-22 (Event-driven): FUNCIONALIDAD "DROP AND GO" PARA CONTINGENCIAS:
        Ante una emergencia o incidencia no reparable en campo (avería mayor o cliente no comparecido), el supervisor podrá arrastrar la orden sobre el icono de una cuadrilla cercana.
        La orden se asignará inmediatamente activando el flag "Intervención Urgente (Sin Picking Previo de Nave)".
        Abrirá en la PWA la Hoja de Consumo de Emergencia, permitiendo imputar materiales de la Dotación Base (Spec 004 RF-14), sobrantes de tareas matinales (Spec 004 RF-22), traspasos autorizados (Spec 004 RF-25) o compras locales con tiquet fotográfico (Spec 004 RF-24).
    RF-23 (Ubiquitous): EN toda intervención urgente en campo, EL SISTEMA exigirá en la PWA un circuito formal de cierre:
        Apertura: Fichaje geolocalizado de llegada y fotografía de la avería.
        Imputación: Horas de intervención y piezas consumidas.
        Aceptación: Firma digital del cliente en PWA; si está físicamente ausente, el operario marca "Cliente Ausente" aportando reporte fotográfico completo. La orden pasa de inmediato a Blanco (Completada) en el mapa, remitiéndose el parte por Telegram o Email a efectos informativos sin bloquear el cierre administrativo.
        Cierre: Fotografía del resultado final.
    RF-24 (Event-driven): CUANDO el supervisor reasigne una tarea o altere el orden de prioridades desde el mapa:
        Con Cobertura: Actualiza Kanbans en PWA con señal acústica y notificación visual. Si estaba en Lila (Standby), permanecerá en Lila hasta que el capataz abra la notificación, conmutando entonces a Azul (En tránsito).
        Sin Cobertura: El sistema advierte del estado desconectado, facilitando la llamada telefónica directa de voz al capataz.
        Persistencia: Si tras un Drop and Go la cuadrilla entra en zona de sombra, la orden continúa asignada; solo el supervisor puede desasignarla o reubicarla manualmente.

Bloque 7: Telemetría GPS Eficiente ( Battery-Aware ) y Pérdida de Cobertura

    RF-25 (Ubiquitous): LA PWA ejecutará una política de telemetría GPS inteligente orientada al ahorro de batería, prohibiendo el rastreo por polling continuo:
        Emitida por defecto a través del dispositivo del Responsable de Cuadrilla (capataz). Todos los operarios disponen de la PWA instalada en sus terminales móviles individuales donde fichan el inicio y fin de su jornada laboral.
        Delegación Temporal por Avería o Batería Agotada: Si el terminal del capataz se queda sin batería, sufre rotura o se apaga durante la faena, el supervisor técnico puede, desde la pantalla de gestión del mapa, cambiar temporalmente el rol de uno de los operarios de la cuadrilla para otorgarle permisos de responsable de cuadrilla (capataz en funciones), transfiriendo de inmediato a su dispositivo la emisión de la telemetría GPS inteligente y el reporte de la faena sin interrumpir la visibilidad del equipo.
        Disparo prioritario por eventos de cambio de estado geográfico (inicio de jornada, inicio de ruta, proximidad a 50 m, fichaje de llegada, cierre de tarea y fin de jornada).
        En trayectos prolongados en carretera (estados Azul y Lila), muestreo periódico espaciado cada 10 a 15 minutos.
        Al fichar Fin de Jornada, la telemetría GPS se desactiva de inmediato (RGPD), quedando el marcador fijo en la última posición registrada hasta medianoche.
    RF-26 (Ubiquitous): PÉRDIDA DE COBERTURA EN CAMPO:
        Check de Tarea sin Conexión (En Faena): Si la cuadrilla está dentro de la geovalla en Verde (En faena) y pierde señal, el sistema suprime falsas alarmas y mantiene el estado Verde con el indicador de última posición en obra.
        Pérdida de Señal en Carretera (Azul y Lila) con Umbral de 25 Minutos: SI la ausencia de señal GPS en desplazamiento supera los 25 minutos (amortiguando con un margen de tolerancia de 10 a 15 minutos el intervalo regular de muestreo de 10-15 min para evitar falsas alarmas por latencia de red), ENTONCES EL SISTEMA atenuará el marcador a translúcido (opacidad 0.5), agregará la etiqueta "Sin señal hace [X] min" y disparará una alerta suave visual en el mapa y la campana. Al recuperar cobertura y emitir coordenada válida, se restaurará automáticamente la opacidad y se normalizará el estado.

Bloque 8: Protocolos de Incidencias en Campo (Flota, Red Técnica y Dotación)

    RF-27 (Ubiquitous): PROTOCOLO SECUENCIAL DE CONTINGENCIA DE FLOTA Y CUSTODIA ASEGURADA:
        Paso 1: Póliza del Vehículo: Consulta de aseguradora, póliza, matrícula y coberturas 24h (Spec 006).
        Paso 2: Llamada a la Grúa: Marcación directa facilitando coordenadas GPS exactas del punto de inmovilización.
        Paso 3: Registro de ETA de la Grúa: Registro del tiempo estimado con cuenta atrás visual sobre el icono del vehículo.
        Paso 4: Diagnóstico In Situ: Dictamen de reparación in situ rápida (20-30 min) o traslado en plataforma a taller.
        Paso 5: Desacoplamiento, Traslado y Custodia Asegurada:
            Custodia Legal y Seguros: El stock base de la furgoneta vive en el vehículo. Tanto la compañía de grúa como el taller mecánico concertado disponen legalmente de póliza de seguro de responsabilidad civil sobre los vehículos y contenidos que mantienen bajo su custodia, quedando cubiertos los materiales y herramientas a bordo.
            Material de Picking Específico: El material de picking específico de las tareas no realizadas se retirará si se reasigna la tarea inmediatamente a otra furgoneta, o se gestionará su devolución a almacén al resolverse la contingencia.
            Desacoplamiento y Reasignación: Las tareas de la tarde se desacoplan para Drop and Go y los operarios se trasladan mediante cuadrillas cercanas (respetando plazas homologadas) o transporte alternativo.
    RF-28 (Ubiquitous): PROTOCOLO DE CONTINUIDAD ANTE OBSTÁCULOS EN RED TÉCNICA:
        Aislamiento Inmediato: Consulta en la Capa Vectorial de la válvula de corte aguas arriba más cercana para cerrarla.
        Peritaje en PWA: Reporte fotográfico de la caseta u obstáculo sobre la traza y de la fuga, conmutando el pin a Rojo.
        By-pass Provisional de Emergencia: Tendido provisional en superficie con polietileno flexible para restablecer servicio en menos de 1 hora, imputando el tiempo a la orden como "Instalación de By-pass de Emergencia". Este caso excepcional lo determina el supervisor; se cobrarán y facturarán a la orden tanto las horas de mano de obra invertidas como los materiales y piezas consumidos, tarificados según los precios maestros de mano de obra y maquinaria configurados en /gestio/configuracio/tarifes.
        Negativa del Propietario: Registro fehaciente de la negativa en PWA; la cuadrilla se repliega y el supervisor consulta el asistente RAG para gestionar la respuesta contractual.
        Actualización de Traza: Incorporación del obstáculo y desvío en la Capa Vectorial, derivando el proyecto de variante definitiva a oficina técnica.
    RF-29 (Ubiquitous): TRANSFERENCIA DE OPERARIOS ENTRE CUADRILLAS EN CAMPO:
        Apertura de incidencia de dotación en el mapa seleccionando operarios y vehículo de destino.
        Actualización de la composición de la cuadrilla en el popover y registro de presencia.
        Imputación Horaria por Start / Stop en Obra: El operario dispone en su PWA de los botones de Start / Stop para computar su tiempo de permanencia efectiva en la obra de destino. Dicha directriz rige de forma estricta: al llegar a la obra asignada pulsa Start y al marcharse pulsa Stop, computándose esas horas a la orden correspondiente, independientemente de la duración del trayecto de traslado.
        Control de Plazas Homologadas y Prohibición de Imprudencias: Validación en backend que bloquea trasvases que superen los asientos físicos habilitados en el vehículo receptor (Spec 006 RF-28). En modo offline, la PWA advertirá expresamente al capataz del límite de plazas del vehículo. Rige el mandato estricto de que los capataces no deben incurrir en imprudencias, sobreocupaciones ni malas prácticas de seguridad vial. Si en la sincronización posterior se detectara un trasvase indebido que superó las plazas legales, el sistema registrará una incidencia disciplinaria grave de seguridad vial en el expediente del capataz para valoración de RRHH.

Bloque 9: Canal Multicanal de Aceptación con el Cliente (Teléfono, Email y Telegram)

    RF-30 (Ubiquitous): COMUNICACIÓN TRANSACCIONAL VÍA TELEGRAM, EMAIL Y TELÉFONO:
        Aviso de Salida y Aproximación: Al iniciar ruta (Azul), remite notificación por Email o Telegram con código OT, dirección y hora estimada de llegada (sin enlaces de rastreo continuo en vivo).
        Aviso de Llegada: Al llegar a la parcela o fichar en Punto Cero, notifica de inmediato al cliente el inicio de los trabajos.
        Aviso de Retraso Vial: En incidencias de tráfico o avería, notifica el retraso estimado de forma transparente.
        Validación en Cliente Ausente: Conmuta pin a Blanco y remite el parte con fotos y botón [✍️ Confirmar y Validar Recepción] a efectos informativos diferidos.
    RF-31 (Ubiquitous): GESTIÓN MULTICANAL DE IMPREVISTOS Y IDEMPOTENCIA TRANSACCIONAL:
        Prioridad de Canales y Carácter Opcional de Telegram: El Bot de Telegram es un canal complementario ágil; los canales principales de comunicación contractual son el Email y el Teléfono. En ningún caso se obligará al cliente a usar Telegram.
        Aprobación Previa del Supervisor (Human-in-the-Loop): El informe técnico redactado por Copilot (descripción, fotos periciales y propuesta económica extra) requerirá obligatoriamente de la revisión y aprobación humana explícita del supervisor antes de su envío al cliente.
        Canal Email con Enlace Web Securizado e Idempotencia: Al validarse el informe, EL SISTEMA remite un correo electrónico al cliente con el desglose del imprevisto y un enlace web securizado con token cifrado de un solo uso. CUANDO el cliente pulsa sobre la aprobación, EL SISTEMA aplicará un control de idempotencia transaccional mediante token único (token_aprobacio). SI se recibe una petición duplicada o concurrente con el mismo token, ENTONCES EL SISTEMA ignorará el procesamiento duplicado y retornará con éxito el estado ya consolidado en la primera transacción sin alterar acumuladores ni duplicar presupuestos suplementarios, registrando de forma inmutable la marca temporal (timestamp) y la IP del cliente en la primera ejecución.
        Canal Telefónico y Certidumbre Documental Mandatoria: El supervisor puede llamar directamente al cliente (tel:) para exponer el imprevisto técnico y coordinar la solución. La faena en campo no se autoriza ni se desbloquea verbalmente: ÚNICAMENTE cuando se tiene la certidumbre de la documentación aceptada formalmente mediante el clic en el enlace web o Telegram, se libera la tarea.
        Condición de Carrera y Reactivación post-cancelación: SI una tarea hubiera sido cancelada por el supervisor tras falta de acuerdo inicial (conmutando el pin a Negro), y posteriormente el cliente acepta formalmente el presupuesto (vía Email o Telegram), el supervisor contactará telefónicamente con la cuadrilla para reanudar los trabajos, y el pin de la obra conmutará de nuevo de Negro a Verde, restableciendo la orden en curso.
        Rechazo Definitivo: Si el cliente pulsa Rechazar, la obra se detiene definitivamente en Negro y se emite el albarán provisional con los costes devengados hasta la fecha.

Bloque 10: Cancelaciones, Reagendamientos y Gestión de Stock a Bordo

    RF-32 (Ubiquitous): GESTIÓN DE CANCELACIONES Y REAGENDAMIENTOS DE OBRA:
        Señal acústica y alerta visual de cancelación en PWA.
        Distinción entre los Dos Supuestos Operativos:
            Supuesto 1: Tarea Cancelada que se Reagenda en Nueva Fecha: Si la tarea no puede ejecutarse o completarse hoy pero se reprograma con el cliente, se recopilan todos los datos registrados en la PWA hasta el momento (fotos, piezas, horas) y se adjuntan a la orden de trabajo asignándole la nueva fecha acordada; en la nueva fecha futura la tarea figura con color Naranja (Pendiente). En el historial de hoy queda constancia de la reprogramación, pero la tarea no perdura como pin activo en el mapa de hoy.
            Supuesto 2: Tarea Cancelada Definitivamente: Si la obra se cancela de forma definitiva (en ruta o durante la faena en Verde), se recopilan los datos de la hoja de trabajo de la PWA para la liquidación y facturación de los trabajos y desplazamientos devengados hasta la cancelación, marcándose con color Negro (Cancelada).
        Cómputo de Desplazamiento de Retorno a Base: Al cancelarse forzosamente una obra, el supervisor validará los datos remitidos desde la PWA y determinará humanamente, según el protocolo de la empresa, si el tiempo de retorno a la base se imputa a la liquidación del cliente cancelado o se absorbe como coste estructural interno.
        Naturaleza No Persistente de las Cancelaciones: Las cancelaciones NO son incidencias activas y no perduran flotando en el tiempo en el mapa; quedan registradas y asentadas exclusivamente en el día en que sucedieron para la consulta retrospectiva del historial, así como en la hoja de tarea asignada al cliente.
        Gobierno de Stock en Furgoneta: Los materiales cargados quedan en custodia a bordo para reingreso en almacén central al cierre de jornada, salvo reubicación inmediata mediante Incidencia de Cambio de Asignación.
    RF-33 (Ubiquitous): RESOLUCIÓN DE HUECOS IMPRODUCTIVOS POR FINALIZACIÓN ANTICIPADA:
        Notificación a la base en el mapa /gestio.
        Tramitación en mapa mediante: a) Reasignación de tarea nueva mediante Drop and Go con stock compatible, o b) Apoyo y convergencia con cuadrilla cercana retrasada.

Bloque 11: Centro de Resolución de Incidencias en Drawer Lateral

    RF-34 (Ubiquitous): DRAWER LATERAL DE INCIDENCIAS EN /gestio CON ALERTA NO INVASIVA:
        Comportamiento por Defecto y Prioridad del Mapa: El Drawer lateral de incidencias (ubicado en el margen derecho de la pantalla) permanecerá oculto y colapsado por defecto, priorizando la visibilidad amplia, fluida y sin obstáculos de la cartografía y las cuadrillas activas.
        Alerta No Invasiva ante Nuevas Incidencias: Ante una nueva incidencia en campo, el Drawer NO se desplegará de forma abrupta e invasiva, evitando descolocar la pantalla o interrumpir acciones en curso (arrastres de tareas, lectura de planos). El sistema activará la alerta visual en cabecera (RF-06) y mostrará una pestaña flotante derecha pulsátil con el número de incidencias pendientes.
        Apertura Manual por Clic: El supervisor desplegará el Drawer a voluntad haciendo clic sobre la pestaña lateral derecha del mapa, sobre el banner de alerta, sobre la campana o sobre cualquier marcador rojo del mapa.
        Redirección Unificada de Rutas: La URL /gestio/incidencies redirigirá de forma automática y transparente a /gestio?incidencies=obertes, abriendo la interfaz del Dashboard con el Drawer de incidencias desplegado y enfocado. Las incidencias activas permanecerán marcadas y visibles en el mapa hasta su efectiva resolución, independientemente del filtro de fecha seleccionado.
        Gestión de Avalancha de Incidencias Simultáneas: Si concurren múltiples incidencias reportadas en un breve lapso de tiempo, el Drawer las listará en una columna lateral por estricto orden cronológico de llegada; el supervisor determinará humanamente cuál atiende en primer lugar ponderando el nivel de urgencia técnica y el peligro para la integridad física de los trabajadores.
        Contenido Estructurado del Drawer:
            Reproductor de audio nativo del operario (escucha directa e inmediata desde el primer segundo).
            Galería de fotografías periciales de campo ampliables.
            El Memorándum e Informe Técnico redactado por Copilot (diagnóstico, piezas estimadas y propuesta económica).
            Botones de acción operativa inmediata según la tipología de la incidencia.
    RF-35 (Ubiquitous): RESOLUCIÓN DE AVERÍAS DE FLOTA EN EL DRAWER, PLAZAS HOMOLOGADAS Y REASIGNACIÓN:
        CUANDO una cuadrilla reporte una avería mecánica inmovilizante o pinchazo en carretera, el Drawer de Incidencias activará las siguientes tres acciones coordinadas en un solo flujo:
            a) Activación de Grúa y Taller: Suministra la llamada directa con la aseguradora y datos de póliza (Spec 006), dirigiendo la grúa al Concesionario Oficial configurado (si es en garantía y dentro de la comarca base/adyacentes) o al taller concertado seleccionado.
            b) Notificación Automática de Demora al Cliente: EL SISTEMA remitirá un mensaje inmediato por Email o Telegram al cliente de la obra pendiente que estaba esperando a la furgoneta, informándole de forma proactiva del imprevisto técnico de transporte y recalculando la previsión.
            c) Desacoplamiento y Reasignación de Órdenes Pendientes: Las tareas que la cuadrilla averiada tenía programadas para la tarde se desacoplan de su furgoneta y quedan disponibles en el mapa como órdenes no asignadas para su reubicación mediante Drop and Go hacia otra cuadrilla cercana o reprogramadas en fecha si ninguna puede asumirlas. La cuadrilla receptora a la que se le asigne el trabajo deberá acudir a la nave/almacén a retirar el material correspondiente de la hoja de picking (Spec 004) para poder ejecutar adecuadamente la tarea asignada.
        Reasignación Manual y Búsqueda de Transporte Alternativo: El supervisor dispondrá en el Drawer de la opción de reasignación manual de los operarios de la furgoneta averiada. Si las cuadrillas cercanas no disponen de plazas físicas homologadas suficientes para acoger a los operarios (Spec 006 RF-28), el supervisor lo tendrá en cuenta y gestionará transporte alternativo (taxi concertado de la póliza de seguros, vehículo de auxilio desde almacén o retorno a la base).
    RF-36 (Ubiquitous): INCIDENCIAS DE HERRAMIENTAS, TRASPASOS CONDICIONALES, PROVEEDORES Y VEHÍCULO DE APOYO:
        CUANDO una cuadrilla reporte la rotura de una herramienta crítica o la falta de un accesorio/pieza no disponible en la dotación de la furgoneta:
        Traspaso Condicional Evaluado por Hoja de Tarea y Logística de Traslado:
            El Drawer analizará las furgonetas cercanas y comprobará si alguna dispone de la herramienta o recambio en su dotación de almacén (Spec 004).
            Condición Restrictiva Determinada por Hoja de Tarea: El sistema comprobará si la herramienta fue utilizada en una primera faena ya terminada por la Cuadrilla B y no figura en sus tareas posteriores de la jornada; de ser así, se determina disponible. En cualquier caso, se prioriza la consulta telefónica asistida por Copilot y el supervisor tiene siempre la última palabra para evitar perjuicios a la Cuadrilla B.
            Logística de Traslado Físico Determinada por Supervisor: El supervisor técnico determinará humanamente la operativa logística más eficiente para el desplazamiento físico de la herramienta traspasada entre cuadrillas (despacho del vehículo de auxilio desde almacén, instrucción a la cuadrilla cedente para entregarla al paso, o desplazamiento puntual de un operario), registrándose la nueva custodia en Magatzem.
        Capa Cartográfica de Proveedores Locales y Desabastecimiento:
            El supervisor dispondrá en el mapa de una capa conmutable de Puntos de Venta Técnicos y Ferreterías Locales cercanas a la zona de la obra con teléfono directo (tel:) para verificar y reservar stock previamente antes de desplazar al operario.
            Desabastecimiento Total: Si los proveedores locales carecen de la pieza o están cerrados, el supervisor tomará humanamente la determinación del siguiente paso operativo (suspensión de la obra, reasignación por Drop & Go o reprogramación de fecha).
        Operativa del Vehículo de Apoyo y Privacidad RGPD:
            Si se activa un vehículo de auxilio desde el almacén central, dicho vehículo dispondrá de presencia GPS a través de la PWA y operará con su propia hoja de tarea asignada.
            PRIVACIDAD ESTRICTA (RGPD): Para el vehículo de apoyo únicamente se registrará y almacenará el tiempo transcurrido y el kilometraje total recorrido; EN NINGÚN CASO se guardará ni dibujará la traza continua de la ruta viaria.
            Contingencias Aisladas: Si el vehículo de apoyo sufre un percance en ruta, se tratará de forma aislada como una incidencia ordinaria de flota (RF-35).
        Imputación de Incidencia en Herramienta Prestada e Inspección de Negligencia:
            Cuando una herramienta traspasada sufra rotura o avería, la incidencia técnica se asocia a la persona o cuadrilla que ostentaba la custodia física en ese momento.
            Inspección Pericial por el Supervisor: El supervisor técnico inspeccionará el fallo para determinar si obedeció a desgaste natural o fatiga. Únicamente si constata negligencia manifiesta, elevará el caso a RRHH.

Bloque 12: Protocolo Offline-First Delimitado, Contraste Presupuestario y Facturación

    RF-37 (Ubiquitous): ALCANCE ESTRICTO DE OFFLINE-FIRST VS BÚSQUEDA DE COBERTURA EN INCIDENCIAS:
        El principio Offline-First ampara estrictamente la persistencia local cifrada (IndexedDB con Web Crypto API derivado de PIN) de los datos de la hoja de tarea (notas de voz, fotos, horas, planos, mediciones y piezas consumidas).
        Por contraposición, las incidencias imprevistas no operan en modo offline diferido: como su propio nombre indica, una incidencia es un bloqueo crítico que exige resolución activa urgente, por lo que el operario responsable (cap de colla) tiene la obligación procedimental de desplazarse hasta encontrar cobertura móvil para notificar de inmediato el grado de la incidencia a la base, garantizando una resolución rápida.
    RF-38 (Ubiquitous): OBLIGATORIEDAD DOCUMENTAL DE LA PWA Y CONTRASTE PRESUPUESTARIO:
        Ningún albarán o liquidación de final de tarea podrá ser redactado sin la documentación y sincronización completa de la hoja de tarea de la PWA.
        Tras la sincronización del cierre, EL SISTEMA contrastará automáticamente los consumos reales frente al presupuesto inicial aprobado y partidas suplementarias aprobadas formalmente por Email o Telegram (las cuales permanecen bloqueadas e inmutables).
    RF-39 (Ubiquitous): SUPERVISIÓN HUMANA DE DESVIACIONES AL CIERRE (CERO IMPUTACIÓN AUTOMÁTICA):
        Al capataz NO se le imputará ningún sobrecoste o desviación de la obra a no ser que sea por causa demostrada de negligencia.
        Al cierre de una obra, el supervisor técnico revisará las desviaciones registradas en la hoja de tarea de la PWA frente a la previsión inicial. Es responsabilidad exclusiva del supervisor evaluar técnicamente dichas desviaciones en su contexto de obra; únicamente en caso de constatar negligencia injustificada, el supervisor elevará la incidencia al departamento de RRHH para su valoración.
    RF-40 (Ubiquitous): MANDATO CONSTITUCIONAL HUMAN-IN-THE-LOOP PARA FACTURACIÓN:
        El ingeniero o Copilot redactará la propuesta de presupuesto final de obra y albarán liquidando las desviaciones documentadas en la hoja de tarea.
        EN NINGÚN CASO se emitirá una factura ni se derivará automáticamente a Contabilidad sin la aprobación humana explícita: el supervisor técnico o Boss deberá revisar, ajustar y validar con firma digital/clic explícito el documento antes de su remisión a Facturación (/gestio/comptabilitat) bajo normativa Veri*factu.

Bloque 13: Trazabilidad Multinivel e Imputación Disciplinaria Humana en RRHH

    RF-41 (Ubiquitous): TRAZABILIDAD AUTOMÁTICA EN HISTORIALES TÉCNICOS:
        Registro Primario en la Hoja de Trabajo: Toda incidencia reportada se registrará e incorporará de forma indeleble en la hoja de tarea / orden de trabajo activa donde se haya producido el hecho (audio, transcripción, peritaje fotográfico, informe y resolución).
        Replicación en el Historial del Vehículo (Flota, Spec 006): Si la incidencia atañe a un vehículo (colisión, avería de motor, recarga omitida en EV o daño mecánico), el backend la replicará automáticamente en la ficha del vehículo en Flota (/gestio/flota/<identificador_actiu>).
        Registro Técnico en el Historial del Trabajador: El backend asociará automáticamente la incidencia técnica al historial de actividad del operario interviniente a efectos de auditoría técnica y control de calidad.
    RF-42 (Ubiquitous): DECISIÓN HUMANA EXPLÍCITA PARA EXPEDIENTE DISCIPLINARIO EN RRHH:
        CERO IMPUTACIÓN DISCIPLINARIA AUTOMÁTICA: Queda terminantemente prohibido que el backend anote faltas laborales o expedientes disciplinarios de forma desatendida. La clasificación de la incidencia como negligencia o mala praxis y la decisión de elevarla a expediente disciplinario laboral a RRHH (/gestio/treballadors) será SIEMPRE una acción 100% humana ejecutada por el Boss, el supervisor técnico o el responsable de RRHH.
        Criterios de Valoración Objetiva:
            Siniestro o Choque Vial Imputado según Atestado: La responsabilidad laboral se imputará estricta y exclusivamente de conformidad con el atestado oficial de tráfico (Guardia Civil / Policía / Mossos) o el parte amistoso de accidente contrastado y firmado, acreditando fehacientemente la identidad del conductor real en el momento del suceso.
            Falta de Material con Stock en Almacén: Se imputará a la persona responsable de la preparación de la hoja de picking de almacén (Spec 004).
            Falta Colectiva o Técnica: Valorada por RRHH oyendo al responsable de cuadrilla (capataz) y operarios involucrados.
        Custodia Confidencial: El expediente laboral permanece bajo custodia confidencial exclusiva para los roles Secretaria / RRHH y Boss.

Bloque 14: Configuración Maestra de Tarifas de Mano de Obra y Maquinaria

    RF-43 (Ubiquitous): CATÁLOGO MAESTRO DE TARIFAS Y COSTES HORARIOS (/gestio/configuracio/tarifes):
        EL SISTEMA incorporará un panel maestro de configuración accesible para los roles autorizados (Boss y mandos técnicos con permiso), estructurado en 3 áreas:
            Pestanya 1: Mà d'Obra per Categoria: Tarifas horarias ordinarias y de horas extras para: Peón, Oficial 2ª, Oficial 1ª, Técnico especialista, Cap de colla, Ingeniero técnico, Arquitecto / Dirección facultativa.
            Pestanya 2: Desplazamientos y Tiempo de Tránsito: Tarifa horaria de cuadrilla en tránsito, coste/km por tipología de vehículo (furgoneta estándar, camión grúa/pluma, vehículo eléctrico) y recargos por salidas de urgencia o zonas rurales aisladas.
            Pestanya 3: Maquinaria y Equipos Especiales: Coste horario de máquina (con o sin operador) para: Excavadora / Miniexcavadora, Dumper, Cuba de agua/riego, Máquina de alta presión, Equipo de electrofusión PE, Termofusión, Generador eléctrico autónomo.
        Consumo Automatizado para Liquidaciones: Los costes calculados en cancelaciones por accesos bloqueados (RF-13), by-pass de emergencia (RF-28) o presupuestos suplementarios consumirán de forma directa y de obligado cumplimiento las tarifas fijadas en este catálogo maestro, requiriendo en todo caso la validación humana final previa a facturación.

Bloque 15: Estado "Día 0" Real, Resiliencia y Chat IA Local

    RF-44 (Ubiquitous): ESTADO "DÍA 0" (TOLERANCIA CERO A DATOS FICTICIOS):
        Cámara del mapa centrada en las coordenadas de la sede o Almacén Central de la empresa provistas en el onboarding del SaaS.
        Mapa completamente limpio, sin cuadrillas simuladas ni pines dummy (Zero Mock Data).
        Panel lateral muestra estado vacío real ("Sin tareas programadas para esta fecha").
        HUD operativo muestra todos los contadores a 0.
    RF-45 [MARCA PARA ESPECIFICACIÓN COMPLETA FUTURA] (Ubiquitous): EL SISTEMA incorporará en el Dashboard un punto de anclaje de interfaz para un Chat Conversacional asistido por Inteligencia Artificial en nodo local (LLM ejecutado localmente en el servidor Hetzner / Mini PC de la empresa vía LM Studio / Ollama, preservando el RGPD y la soberanía del dato):
        RAG Documental Estricto: El LLM solo responderá basándose exclusiva y estrictamente en la documentación técnica, manuales, normativas y expedientes de la empresa (sin alucinaciones ni asunciones externas).
        Segregación Zero-Trust: Respetará el rol del usuario conectado, impidiendo fugas de datos no autorizadas.
        Postergación de Especificación Detallada: Este requisito establece la reserva arquitectónica; su especificación funcional completa se redactará en una fase posterior dedicada.
    RF-46 (Ubiquitous): RESILIENCIA Y RENOVACIÓN SILENCIOSA DE SESIÓN:
        MIENTRAS el Dashboard mantenga conexiones de telemetría en vivo o WebSocket activas, EL SISTEMA renovará el token de acceso JWT de forma silenciosa e imperceptible mediante la cookie segura de refresco (HttpOnly, SameSite=Strict), impidiendo bloqueos intempestivos o redirecciones forzadas a login.
        SI la conexión entre el Dashboard y el backend se interrumpe, ENTONCES EL SISTEMA mostrará una barra de advertencia no bloqueante ("Sin sincronización — Reintentando...") conservando en pantalla la última información recibida.

--------------------------------------------------------------------------------
Casos Límite y Resiliencia (EDGE-01 a EDGE-10)
Código
	
Tipo EARS
	
Módulo Afectado
	
Condición de Falla / Escenario Límite
	
Comportamiento Requerido del Sistema
EDGE-01
	
Unwanted
	
Concurrencia
	
Dos ingenieros intentan reasignar la misma orden de trabajo en el mismo instante (vía arrastre en mapa).
	
Aplica control de concurrencia optimista (version_id en la orden) y bloqueo pesimista en base de datos (SELECT FOR UPDATE). El primer commit consolida; el segundo falla con un 409 Conflict e instruye a refrescar pantalla de forma segura.
EDGE-02
	
Unwanted
	
Sincronización
	
El Boss reasigna un coche en el Dashboard mientras el capataz reporta el odómetro final en PWA de forma asíncrona.
	
El backend gestiona de forma idempotente. Si la asignación cambia, se asienta la traza con marca temporal secuencial inalterable y se actualiza la sesión en vivo de ambos terminales vía WebSocket.
EDGE-03
	
State-driven
	
Horarios
	
Una obra se queda en estado Rojo (Incidencia activa / Inconclusa) al finalizar la jornada de campo (18:00).
	
Detención automática de la acumulación de horas del cliente a las 18:00 (rollback funcional). A las 08:00 AM del Día +1, la orden aparece destacada en la cabecera del panel de despacho técnico para decisión humana.
EDGE-04
	
Event-driven
	
Telemetría
	
Un vehículo en ruta (Azul/Lila) pierde la señal GPS en carretera (por cañón o túnel largo) durante más de 25 minutos.
	
Al superar el buffer de 25 min, el mapa atenúa el icono (opacidad 0.5) con etiqueta de tiempo sin señal y alerta en campana. Al reconectar, la PWA vuelca los eventos acumulados discretos en IndexedDB de forma idempotente.
EDGE-05
	
Unwanted
	
Cartografía
	
Archivo vectorial GeoJSON/KML de infraestructura técnica cargado localmente presenta corrupción física o error de parseo.
	
El motor de renderizado JS intercepta la excepción del parser, desactiva la capa técnica afectada de forma segura para evitar el bloqueo del visor completo y emite una alerta no bloqueante al supervisor.
EDGE-06
	
Unwanted
	
PWA Offline
	
El capataz original se queda sin batería en zona rural sin cobertura y transfiere la PWA a otro operario físicamente.
	
Los datos se guardan localmente en la PWA (IndexedDB cifrado). Al recuperar señal, se realiza una validación simétrica en el backend y se delega el rol con marca temporal secuencial inalterable.
EDGE-07
	
Event-driven
	
Reubicación
	
El cliente rechaza la propuesta extra (obra pasa a Negro/Cancelada), pero acepta telemáticamente minutos después de que se retire el equipo.
	
El webhook de Email/Telegram procesa la aceptación idempotente, conmuta el pin a Verde en el mapa de Torre de Control y dispara una alerta acústica para que el supervisor reenvíe telefónicamente a la cuadrilla.
EDGE-08
	
Unwanted
	
Seguridad Vial
	
El supervisor arrastra operarios de un vehículo averiado a otros furgones cercanos en el mapa, superando el límite de plazas homologadas.
	
El backend valida las plazas operativas reales en base de datos de los vehículos receptores y bloquea la transacción con código 400 Overweight / Capacity Exceeded, exigiendo transporte alternativo.
EDGE-09
	
State-driven
	
Logística
	
El supervisor abre la capa de proveedores para resolver la rotura de una herramienta, pero la tienda local abierta carece de stock físico.
	
El sistema detecta el desabastecimiento en la capa del mapa (si hay integración de stock de socio comercial) u ofrece reasignar con una furgoneta lejana que disponga de la herramienta en standby.
EDGE-10
	
Event-driven
	
Aprobación
	
El cliente pulsa el botón con token de un solo uso por Email y se genera un intento de reenvío duplicado por refresco de navegador.
	
El backend aplica idempotencia atómica mediante token_aprobacio. El segundo commit se resuelve de forma transparente retornando la hoja de aceptación ya bloqueada e inmutable, sin generar alteraciones contables duplicadas.
--------------------------------------------------------------------------------
Requisitos No Funcionales

    Cartografía Soberana y Gratuita (Cero Costes de API): Visualización mediante Leaflet / MapLibre con capas libres (OpenStreetMap y PNOA/ESRI), sin cuotas de facturación por peticiones cartográficas ni fuga de datos a terceros fuera de la UE.
    Segregación Estricta de Datos Financieros: La pantalla /gestio NO consume ni expone métricas contables globales, balances de facturación ni devengos económicos, previniendo cualquier fisura de permisos entre roles técnicos y directivos.
    Rendimiento Ultrarrápido y Fluidez a 60 fps: La renderización de 50 marcadores de obra, 15 vehículos simultáneos, capas técnicas vectoriales y apertura reactiva de paneles responderá con latencia inferior a 200 ms y 60 fps estables en Next.js.
    Arquitectura Asíncrona (Celery + Redis): El procesamiento de audios de campo con Whisper v3, la generación del informe de Copilot y las notificaciones automáticas por Telegram a clientes y grúas se ejecutan en segundo plano en Celery, garantizando que el event loop de FastAPI nunca se bloquee.
    Seguridad Multi-Tenant (RLS): Aislamiento estricto por app.current_empresa_id en todas las tablas de obras, cuadrillas, incidencias, telemetría y capas vectoriales.
    Almacenamiento Seguro en Memoria Interna de la Empresa y Servidor Hetzner (Alemania): Todas las evidencias multimedia y documentales se alojan estrictamente en la memoria interna y discos duros locales de la empresa y en el servidor Hetzner Cloud (Alemania - UE) bajo el árbol:
        Audios de notas de voz de incidencias: /data/<empresa_id>/audios/incidencies/
        Fotografías periciales de incidencias: /data/<empresa_id>/imatges/incidencies/
        Fotografías de apertura y cierre de faenas: /data/<empresa_id>/imatges/obres/
        Planos técnicos y vectores de red: /docs/<empresa_id>/planols/vectorials/ Se elimina completamente cualquier servicio cloud externo (como AWS S3) para estricto cumplimiento del RGPD y soberanía absoluta de los datos.
    Privacidad Laboral y RGPD: Prohibido registrar o dibujar trazas de carretera continuas en el mapa histórico y vehículos de auxilio; solo se persisten eventos de presencia, kilometrajes y fichajes en obras y bases autorizadas.
    Diseño Camaleón en Plataforma vs Simbología Cartográfica Funcional: La interfaz de la plataforma web, los paneles colapsables y las notificaciones adoptan la paleta camaleónica corporativa (--color-primary, --color-secondary), mientras que los iconos y estados del mapa mantienen una simbología cartográfica fija, universal y de contraste funcional independiente.
    Diseño 100% Responsive y Adaptabilidad Multi-Dispositivo: La pantalla del Dashboard y sus paneles desacoplados se adaptan dinámicamente a cualquier factor de forma (monitores desktop, tablets de cabina o smartphones de supervisores), garantizando visibilidad despejada y plena operatividad táctil.

--------------------------------------------------------------------------------
Fuera de Alcance (Lo que NO hace este Dashboard)

    No emite facturas oficiales Veri*factu en PDF ni gestiona cobros contables (se efectúa en /gestio/comptabilitat).
    Código QR Legal: De conformidad con la legislación tributaria (RD 1007/2023), todas las facturas y albaranes de entrega emitidos de forma oficial por la empresa en /gestio/comptabilitat deben incorporar de forma obligatoria su respectivo código QR legal estructurado y encadenamiento criptográfico Hash SHA-256. Esta obligatoriedad legal en facturación convive con la exclusión total de códigos QR en las herramientas de campo (Spec 004 / Spec 008), las cuales se gestionan y transfieren exclusivamente mediante su número de referencia único.
    No muestra métricas de facturación global acumulada ni balances de rentabilidad empresarial (confinado a Spec 007).
    No es una herramienta de navegación GPS paso a paso en ruta (se delega en la PWA a apps nativas como Google Maps o Waze mediante enlace externo).
    No realiza trazado continuo de líneas de velocidad ni análisis de telemetría de frenadas (no es un sistema de tacógrafo pesado de carretera).
    No permite altas completas ni edición de datos maestros de clientes, vehículos o herramientas (se delega a sus pantallas maestras).
    No gestiona el picking físico de nave central (se gobierna en /gestio/magatzem).
    No mantiene pantallas separadas para /gestio/feines/mapa ni /gestio/incidencies; la ruta /gestio consolida la Torre de Control y redirige las rutas secundarias a sus vistas integradas.
    El Chat Conversacional con LLM local queda marcado como previsión arquitectónica (RF-45), difiriéndose su especificación y diseño detallado a una fase posterior.

--------------------------------------------------------------------------------
Criterios de Finalización (Definition of Done)

    Todos los requisitos funcionales (RF-01 al RF-46) redactados en sintaxis formal EARS respondiendo con un 100% de coherencia a la operativa real de oficina y campo.
    Eliminación total de magnitudes financieras globales en el HUD del Dashboard; HUD global e inmutable frente a filtros locales del mapa.
    Panel izquierdo en acordeón por cuadrillas que dispongan de hoja de tarea del día, incluyendo cuadrillas en retén/guardia con faenas internas de almacén.
    Drawer lateral derecho de incidencias con alerta no invasiva (banner y campana destellante) sin despliegues que interrumpan la manipulación activa del mapa.
    Arquitectura cartográfica 100% Open Source basada en Leaflet / MapLibre GL con capas OpenStreetMap y PNOA Ortofoto.
    Discriminador flotante multi-criterio de capas y colores con botones rápidos [Marcar tots] y [Desmarcar tots].
    Georreferenciación previa obligatoria y protocolo de Punto Cero en cancela con botón Start al llegar (Verde), paso a Rojo al abrir incidencia, cronómetro continuo ininterrumpido hasta conclusión o cancelación, y retorno a Verde por acción de operario o supervisor.
    Código cromático con distinción ontológica estricta: Órdenes (Naranja Pendiente, Azul En tránsito, Verde En faena, Rojo Incidencia activa en obra, Blanco Completada, Negro Cancelada) y Vehículos (Azul En tránsito con tarea, Lila Standby/tránsito sin tarea, Rojo Avería mecánica, Inmóvil en obra sin color / neutro; Blanco y Negro no aplican a vehículos; apertura matinal Día +1 con decisión humana del supervisor para continuar faena o reasignar).
    Mando multicanal riguroso con el cliente: teléfono y email como canales principales (Telegram opcional); aprobación formal obligatoria por enlace web securizado o Bot; prohibición estricta de reanudar faena sin certidumbre documental; condición de carrera con reactivación de Negro a Verde si el cliente acepta con posterioridad a la llamada.
    Protocolo de flota con custodia asegurada: el stock vive en la furgoneta, y tanto la grúa como el taller mecánico responden por responsabilidad civil de los vehículos y contenidos bajo custodia.
    Catálogo maestro de tarifas de mano de obra, desplazamientos y maquinaria configurado centralizadamente en /gestio/configuracio/tarifes.
    Resolución de concurrencia en backend bajo política First-Come, First-Served con aviso no bloqueante ante colisiones simultáneas.
    Trazabilidad automática de incidencias a nivel técnico (orden, operario, vehículo), con mandato de decisión 100% humana para cualquier calificación o elevación a expediente disciplinario en RRHH.
    Privacidad RGPD garantizada: el vehículo de auxilio computa únicamente tiempo y kilometraje, sin almacenar ni trazar la ruta de navegación viaria.
    Mandato Human-in-the-Loop innegociable: ningún presupuesto suplementario, albarán o factura se emite sin validación y aprobación humana explícita previa.
    Almacenamiento seguro soberano en memoria interna de la empresa y servidor Hetzner en Alemania (/data/<empresa_id>/... y /docs/<empresa_id>/...) con eliminación absoluta de AWS S3.
    Rendimiento <200 ms y 60 fps estables garantizado mediante arquitectura asíncrona Celery + Redis para Whisper, Copilot y Telegram.
    La política estricta de NO ejecutar comandos git sin permiso previo del usuario se cumple escrupulosamente.