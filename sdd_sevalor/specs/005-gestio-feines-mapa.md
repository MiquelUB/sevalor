Spec 005 — Seguiment Feines / Mapa (/gestio/feines/mapa)
AVISO DE CONSOLIDACIÓN ARQUITECTÓNICA: Esta especificación está totalmente fusionada e integrada dentro de 001-gestio-dashboard.md (Spec 001 — Dashboard i Torre de Control Operativa /gestio), que asume el rol de Cockpit Único y Torre de Control Geográfica en tiempo real. Todas las rutas /gestio/feines/mapa e /gestio/incidencies quedan unificadas en la ruta centralizada /gestio.
--------------------------------------------------------------------------------
Contexto y objetivo
La pantalla de Seguimiento de Trabajos y Mapa (/gestio/feines/mapa) es la Torre de Control Geográfica en Tiempo Real y el Centro Operativo de Resolución de Incidencias de la empresa técnica. Conecta la actividad diaria de las cuadrillas en campo con el equipo de supervisión y gestión en oficina técnica.
Proporciona una visión territorial unificada donde conviven simultáneamente dos capas dinámicas principales:

    La ubicación física georreferenciada de las obras/clientes.
    La posición GPS en tiempo real de las furgonetas/cuadrillas en jornada activa.

Se superpone a estas capas una capa técnica vectorial propia de la empresa (redes de tuberías, cables, hidrantes y válvulas) y una capa de puntos de venta de suministros técnicos locales (proveedores y ferreterías).
Integra en su propia interfaz el Centro de Resolución de Incidencias en Tiempo Real a través de un Drawer lateral emergente con un diseño e interacciones gobernados por principios de control no invasivo, robustez offline-first, inmutabilidad transaccional, y el mandato constitucional Human-in-the-Loop para todas las derivaciones presupuestarias, albaranes, y penalizaciones disciplinarias.
Toda la cartografía se sustenta sobre motores y capas abiertas (Open Source vía Leaflet / MapLibre GL JS, OpenStreetMap y ortofotos satelitales PNOA/ESRI), sin dependencias de APIs comerciales de pago (Google Maps, Mapbox) ni fuga de datos fuera de la UE, garantizando la soberanía de los datos.

    Independencia del Estilo Camaleónico en el Mapa: El diseño camaleónico rige la apariencia corporativa del software web y PWA (variables CSS HSL de marca para botones, barras y navegación), mientras que los colores de los iconos del mapa son estrictamente funcionales, cartográficos y universales, garantizando que los estados operativos sean inequívocos con independencia de los colores corporativos de la empresa cliente.
    Almacenamiento Seguro Soberano: Toda la información multimedia y documental reside directamente en la memoria interna y discos locales de la empresa y en el servidor Hetzner Cloud (Alemania - UE) bajo el árbol de rutas relativas:
        Audios de notas de voz de incidencias: /data/<empresa_id>/audios/incidencies/
        Fotografías periciales de incidencias: /data/<empresa_id>/imatges/incidencies/
        Fotografías de apertura y cierre de faenas: /data/<empresa_id>/imatges/obres/
        Planos técnicos y vectores de red: /docs/<empresa_id>/planols/vectorials/ Se elimina completamente cualquier servicio cloud externo (como AWS S3) para estricto cumplimiento del RGPD. La base de datos almacena exclusivamente rutas relativas locales y metadatos técnicos con aislamiento multi-tenant mandatorio (RLS).

--------------------------------------------------------------------------------
Usuarios / actores y Matriz de Acceso
En la web de gestión (/gestio), esta pantalla es el centro de operaciones adaptando sus acciones según la función:

    Boss (Gerencia / Propietario): Supervisión integral de la flota y despliegue territorial, resolución de incidencias graves desde el Drawer lateral, autorización de compras extraordinarias en ferreterías locales, asignación y reasignación de órdenes mediante Drop and Go, cambio de prioridades sobre la marcha, llamada directa a capataces, consulta de órdenes históricas y futuras, y aprobación humana final de albaranes/presupuestos de Copilot para su derivación a facturación.
    Ingeniero / Supervisor Técnico: Centro de mando técnico operativo bajo el principio de "Una cuadrilla, un supervisor": seguimiento de la ejecución de obras, atención en el Drawer lateral ante incidencias emergentes (gestionando la lista por orden de urgencia y seguridad laboral), audición de notas de voz de operarios, revisión y aprobación humana previa del informe y presupuesto de Copilot antes de remitirlo al cliente, llamada urgente al cliente ante imprevistos críticos, activación de grúas en averías de flota desacoplando tareas y coordinando transporte alternativo si las furgonetas cercanas no tienen plazas suficientes, comprobación de disponibilidad de herramientas en furgonetas cercanas mediante la finalización de tareas previas en la hoja de faena o localización cartográfica de ferreterías locales llamando previamente para asegurar stock, despacho de vehículos de auxilio con hoja de tarea y GPS en PWA, aprobación y ajuste humano de los presupuestos y liquidaciones finales de Copilot antes de remitirlos a facturación, y acceso a la hoja de trabajo en vivo.
        Autorización Documental Limitada: Autorizado a la búsqueda y lectura de facturas y presupuestos unitarios de clientes para comprobar mediciones y piezas, con bloqueo estricto a nivel de API sobre la información contable agregada de la empresa (libro mayor, balances, cuentas) y denegación de acceso a la ruta /gestio/comptabilitat.
    Secretaria / RRHH: Perfil de solo lectura y consulta en la Torre de Control. Supervisión visual del despliegue para atención telefónica a clientes, consulta de incidencias activas desde el Drawer en modo lectura, verificación de presencia de cuadrillas en zonas de obra, canalización de avisos a mandos técnicos, y recepción, evaluación objetiva individualizada y custodia confidencial en el expediente del trabajador de las incidencias disciplinarias (imputando al conductor el siniestro vial según atestado oficial, al encargado de almacén/picking la omisión de materiales con stock, y al capataz como responsable inicial de omisiones de reporte o mala ejecución colectiva). No dispone de permisos para asignar tareas, reasignar órdenes, arrastrar Drop and Go, autorizar compras ni alterar prioridades.
    Responsable de Cuadrilla (Capataz / /operari): Opera desde su PWA móvil de campo. Emite telemetría GPS inteligente por eventos. El principio Offline-First rige estrictamente para los datos técnicos de la hoja de tarea (notas de voz, fotos, horas, planos y consumos en IndexedDB cifrado); sin embargo, ante una incidencia imprevista urgente que bloquee el trabajo, tiene la obligación procedimental de desplazarse para buscar cobertura móvil y notificar el grado de la incidencia lo antes posible a la base. En trabajos ordinarios sin incidencias, la PWA sincroniza al recuperar cobertura para contrastar consumos frente al presupuesto inicial.
    Operario de Cuadrilla (/operari): Ejecuta la faena técnica en campo. Puede continuar con las fases viables de la obra mientras el capataz y la oficina técnica gestionan la aprobación de un imprevisto con el cliente. En caso de cancelarse la obra por rechazo del presupuesto por el cliente, la cuadrilla se retira ordenadamente, el pin pasa a Negro en el mapa y la cuadrilla queda libre para reasignación desde la base.
    Cliente Final (Canal Multicanal): Recibe avisos transaccionales de salida y llegada. Ante imprevistos de obra, recibe por Email (con enlace securizado y token de firma) o de forma complementaria por Telegram el informe técnico de Copilot (previamente revisado por el supervisor) con fotos y la hoja de aceptación interactiva. El supervisor puede contactarlo telefónicamente para explicar la situación, remitiéndole a validar formalmente la documentación. Al pulsar [Aprobar ampliación [Importe €]], la aceptación queda registrada de forma inmutable; si pulsa [Rechazar], la obra se detiene y se procede a la liquidación provisional de los costes devengados.

--------------------------------------------------------------------------------
Historias de usuario

    H1: Como Ingeniero o Boss, quiero ver sobre el mapa comarcal la ubicación de todas mis cuadrillas y el estado de sus trabajos de hoy, con un HUD operativo superior libre de magnitudes financieras, para coordinar desvíos, optimizar rutas y resolver imprevistos sin dispersión de pantallas.
    H2: Como Ingeniero, quiero que los paneles laterales permanezcan ocultos por defecto para disfrutar de una visión limpia del mapa, y que ante una nueva incidencia se genere una alerta visual y acústica no invasiva, permitiéndome abrir el Drawer de Incidencias manualmente para escuchar el audio, revisar fotos periciales y validar el informe de Copilot en el momento oportuno.
    H3: Como Ingeniero, quiero que el informe técnico suplementario de Copilot se remita al cliente por Email o Telegram con enlace de aceptación formal a 1 clic, pudiendo llamarlo telefónicamente para explicarle el caso, asegurando que la obra solo se reanuda con la certeza documental de la aceptación.
    H4: Como Ingeniero, cuando una furgoneta sufra una avería inmovilizante en ruta, quiero activar la grúa con un clic desde el Drawer, avisar automáticamente al cliente por Telegram/Email de la demora, desacoplar las tareas de la tarde para reasignarlas por Drop and Go y coordinar transporte alternativo para los operarios si las furgonetas cercanas no tienen plazas suficientes.
    H5: Como Supervisor, cuando a una cuadrilla se le rompa una herramienta o falte una pieza, quiero comprobar si una cuadrilla cercana la tiene disponible al haber concluido sus tareas matinales, o consultar en el mapa los distribuidores locales para llamar y asegurar stock antes de enviar al operario o despachar un vehículo de auxilio con GPS.
    H6: Como Capataz de campo, cuando surja un imprevisto grave en una zona rural sin cobertura, quiero que la PWA guarde de forma segura los datos en local y, siguiendo el protocolo operativo, desplazarme hasta encontrar cobertura móvil para activar de inmediato la alerta en la base.
    H7: Como Ingeniero, cuando una cuadrilla finalice una jornada ordinaria sin incidencias, quiero que al sincronizar los datos de la PWA el sistema contraste automáticamente los consumos reales frente al presupuesto inicial aprobado (manteniendo inmutables las partidas aprobadas por Telegram/Email), requiriendo obligatoriamente mi aprobación humana antes de pasar el presupuesto final y albarán a Facturación.
    H8: Como Secretaria o Boss, quiero que toda incidencia quede registrada automáticamente a nivel técnico (hoja de tarea, historial del vehículo), pero que cualquier anotación disciplinaria laboral o expediente en RRHH dependa estrictamente de una decisión humana explícita y objetiva (conductor real del siniestro vial según atestado oficial; encargado de almacén ante omisión de picking; o capataz en faltas colectivas).

--------------------------------------------------------------------------------
Requisitos Funcionales (Notación EARS Estricta)
Bloque 1: Arquitectura Cartográfica Open Source, Capas y Redes Propias

    RF-01 (Ubiquitous): EL SISTEMA renderizará en /gestio un mapa cartográfico interactivo a pantalla completa basado en Leaflet y MapLibre GL JS, excluyendo cualquier dependencia o cuotas financieras vinculadas a claves de API comerciales privativas (como Google Maps o Mapbox).
    RF-02 (Ubiquitous): EL SISTEMA dispondrá en el mapa de un selector flotante para alternar instantáneamente entre la capa base 'Callejero' (teselas vectoriales OpenStreetMap/Carto) y la capa base 'Satélite' (teselas aéreas de alta resolución del PNOA - IGN España o ESRI World Imagery).
    RF-03 (Ubiquitous): EL SISTEMA proyectará reactivamente en el mapa una Capa de Obras y Clientes (pines de órdenes programadas) y una Capa de Cuadrillas y Flota (telemetría GPS de vehículos) en tiempo real.
    RF-04 (Ubiquitous): EL SISTEMA integrará una Capa Vectorial de Infraestructura Técnica de la empresa superpuesta y conmutable.
        RF-04.1 (Ubiquitous): EL SISTEMA renderizará el trazado vectorial comarcal de red cargando archivos GeoJSON o KML locales desde la ruta de almacenamiento /docs/<empresa_id>/planols/vectorials/.
        RF-04.2 (Ubiquitous): EL SISTEMA filtrará y transmitirá a la PWA del operario (/operari) de manera exclusiva la porción de red técnica vectorial comprendida dentro del radio de influencia geográfica de sus órdenes de trabajo asignadas en el día.
        RF-04.3 (Event-driven): CUANDO el usuario haga clic sobre un elemento vectorial de la red técnica en el mapa, EL SISTEMA desplegará un popover flotante detallando sus especificaciones técnicas de ingeniería (por ejemplo, Tubería PE Ø110 PN10 — Sector Norte).
        RF-04.4 (Ubiquitous): EL SISTEMA encapsulará las anotaciones gráficas y pines técnicos de campo dentro de la hoja de trabajo activa o de incidencias de la orden, bloqueando cualquier alteración desatendida o directa sobre la capa cartográfica maestra de red.
    RF-05 (Ubiquitous): EL SISTEMA exigirá la Georreferenciación Obligatoria Previa de toda Orden de Trabajo, bloqueando el agendamiento o planificación de tareas en base de datos si carecen de coordenadas válidas de latitud y longitud.
        RF-05.1 (Event-driven): CUANDO se registre una orden de trabajo, EL SISTEMA capturará sus coordenadas geográficas a partir del pin de ubicación enviado por el cliente (vía Telegram/Email) o de la pulsación manual del técnico de oficina sobre la ortofoto del mapa.
        RF-05.2 (State-driven): SI la precisión de la señal GPS reportada por la PWA (atributo coords.accuracy) es menor o igual a 20 metros, ENTONCES EL SISTEMA validará el fichaje de llegada del operario dentro de un radio de geovalla de 50 metros de cortesía establecido en el Punto Cero de acceso.
        RF-05.3 (State-driven): SI la señal GPS reportada tiene una precisión mayor a 20 metros (debido a condiciones climatológicas o cañones geográficos), ENTONCES EL SISTEMA mantendrá activa la geovalla de 50 metros para absorber la imprecisión GNSS rústica.
        RF-05.4 (State-driven): SI el operario se encuentra dentro del perímetro de geovalla y ejecuta el fichaje de llegada, ENTONCES EL SISTEMA conmutará la orden a estado Verde (En faena) y mantendrá el cómputo de tiempo con independencia de desplazamientos locales dentro de la parcela.
        RF-05.5 (Unwanted): SI la cuadrilla llega a la cancela de acceso (Punto Cero) y encuentra el paso bloqueado, ENTONCES el operario iniciará el cronómetro pulsando 'Start' en la PWA y registrará de forma inmediata una 'Incidencia de Acceso Bloqueado' sin pausar el contador.
        RF-05.6 (State-driven): SI la orden de trabajo es cancelada por el supervisor tras una espera inviable en la cancela, ENTONCES el operario detendrá el cronómetro pulsando 'Pausa/Stop' en la PWA y EL SISTEMA liquidará al cliente el tiempo real de permanencia y el coste de desplazamiento tarificado en base al catálogo maestro de precios horariales de /gestio/configuracio/tarifes.
    RF-06 (State-driven): SI dos o más órdenes de trabajo coinciden en coordenadas geográficas idénticas o adyacentes, ENTONCES EL SISTEMA agrupará los marcadores mediante un cluster geográfico.
        RF-06.1 (Event-driven): CUANDO el usuario haga clic sobre un cluster geográfico, EL SISTEMA desplegará un abanico interactivo con accesos directos independientes a cada orden de trabajo agrupada.
        RF-06.2 (State-driven): SI coinciden físicamente dos o más cuadrillas dentro de la misma parcela de obra, ENTONCES EL SISTEMA reconocerá la convivencia técnica legítima de actividades y suprimirá el disparo de alarmas de colisión en el panel de incidencias.

Bloque 2: Código Cromático de Estados y Popovers Informativos

    RF-07 (Ubiquitous): EL SISTEMA representará los marcadores geográficos mediante un código cromático estrictamente funcional, universal e independiente de la personalización CSS camaleónica de la empresa cliente.
        RF-07.1 (Ubiquitous): EL SISTEMA asignará a las Órdenes de Trabajo los estados cromáticos exclusivos:
            Naranja: Pendiente / No iniciada (cuadrilla en base o sin iniciar ruta).
            Azul: Cuadrilla en camino / En tránsito (desplazamiento activo).
            Verde: En faena / En curso (fichaje validado dentro de la geovalla).
            Rojo: Con incidencia activa / Obra parada (bloqueos técnicos o averías reportadas).
            Blanco: Completada (tarea concluida, documentada con fotos y cerrada por el capataz).
            Negro: Cancelada definitivamente (retirada de cuadrilla con emisión de albarán provisional).
        RF-07.2 (Ubiquitous): EL SISTEMA asignará a la Flota de Vehículos los estados cromáticos exclusivos en ruta:
            Azul: En tránsito con tarea programada asignada.
            Lila / Púrpura: Standby o desplazamiento sin tarea asignada (espera en nave, retornos).
            Rojo: Avería mecánica o inmovilizado en carretera.
            Icono Neutro (Sin Color): Vehículo estacionado dentro de la obra activa en estado Verde (En faena), suprimiendo su color dinámico para limpiar la cartografía.
        RF-07.3 (Event-driven): CUANDO una orden de trabajo cambie a estado completada (Blanco) o cancelada (Negro), EL SISTEMA conmutará automáticamente el marcador del vehículo correspondiente a Lila (Standby) o Azul (En tránsito hacia la siguiente parada).
        RF-07.4 (State-driven): SI una orden de trabajo permanece en estado Rojo (Incidencia activa / Inconclusa) al finalizar la jornada laboral (18:00), ENTONCES EL SISTEMA detendrá administrativamente el acumulador de horas facturables a las 18:00, ejecutando un rollback funcional para evitar la acumulación ficticia de horas extras nocturnas.
        RF-07.5 (Event-driven): CUANDO sean las 08:00 AM del día siguiente (Día +1), EL SISTEMA cargará la orden roja inconclusa en la cabecera del panel de despacho de 'HOY' para forzar la decisión y asignación humana del supervisor técnico.
    RF-08 (Event-driven): CUANDO el usuario haga clic sobre el marcador de una orden de trabajo en el mapa, EL SISTEMA desplegará un popover interactivo con el código de orden, cliente, enlace telefónico directo (tel:), cuadrilla, vehículo asignado, estado activo y el enlace a la hoja de trabajo completa.
    RF-09 (Event-driven): CUANDO el usuario haga clic sobre el marcador de un vehículo o cuadrilla en el mapa, EL SISTEMA desplegará un popover interactivo con el identificador del activo, enlace de flota (/gestio/flota), capataz a cargo, relación nominal de operarios a bordo, orden en curso y botón destacado de marcación telefónica directa (tel:) al capataz.

Bloque 3: Interfaz Limpia, Paneles Ocultos y Navegación Temporal

    RF-10 (Ubiquitous): EL SISTEMA colapsará y mantendrá ocultos por defecto los paneles de planificación (izquierdo) y el Drawer de incidencias (derecho) al cargar la interfaz cartográfica.
        RF-10.1 (Ubiquitous): EL SISTEMA renderizará la pantalla en formato responsive adaptándose automáticamente a anchos de pantalla móviles o tablets, presentando los paneles laterales como capas táctiles superpuestas o modales para evitar el bloqueo del mapa.
        RF-10.2 (Event-driven): CUANDO el supervisor pulse la pestaña lateral izquierda, EL SISTEMA desplegará el panel lateral de planificación con la secuencia ordenada de tareas.
        RF-10.3 (Ubiquitous): EL SISTEMA agrupará y enviará de forma automática las órdenes canceladas del día a una sección inferior colapsable del panel izquierdo denominada 'Historial de Cancelaciones'.
    RF-11 (Event-driven): CUANDO el supervisor seleccione una orden de trabajo en el panel lateral, EL SISTEMA emitirá un destello visual intermitente (highlight) sobre la obra y el vehículo asignado en el mapa, manteniendo fijo el nivel de zoom actual.
    RF-12 (Ubiquitous): EL SISTEMA limitará la telemetría en vivo de la flota y el cálculo de trayectos activos exclusivamente a la jornada seleccionada en el filtro de navegación temporal como 'HOY'.
        RF-12.1 (State-driven): SI una incidencia técnica permanece en estado abierto, ENTONCES EL SISTEMA mantendrá visible su marcador rojo en el mapa de forma persistente, con independencia de la fecha de su apertura o del filtro temporal de fecha activo.
    RF-13 (Event-driven): CUANDO el supervisor conmute a una fecha diferente en el filtro de navegación temporal:
        RF-13.1 (State-driven): SI se selecciona una fecha pasada, ENTONCES EL SISTEMA proyectará estáticamente las obras completadas en sus ubicaciones finales, ocultará la capa de flota y bloqueará la generación de trazas de carreteras históricas de los vehículos (RGPD).
        RF-13.2 (State-driven): SI se selecciona una fecha futura, ENTONCES EL SISTEMA proyectará la distribución territorial de las obras agendadas y desactivará la visualización de la capa de flota móvil.

Bloque 4: Filtros Rápidos de Mando y Búsqueda

    RF-14 (Ubiquitous): EL SISTEMA dispondrá de un panel flotante de control de capas para alternar de forma independiente la visualización de las obras por estado, vehículos por estado, red técnica, puntos de suministros locales e incidencias heredadas.
        RF-14.1 (Event-driven): CUANDO el usuario pulse el botón 'Marcar todos' o 'Desmarcar todos', EL SISTEMA conmutará de forma masiva el estado de visibilidad de todas las capas seleccionables.
        RF-14.2 (Event-driven): CUANDO el supervisor introduzca un término en la caja de búsqueda, EL SISTEMA filtrará dinámicamente en el mapa y en el panel lateral las obras por su código, cliente o dirección física.

Bloque 5: Mando Operativo, "Drop and Go" e Intervenciones Urgentes en Campo

    RF-15 (Ubiquitous): EL SISTEMA limitará las acciones de arrastre (Drop and Go), reasignación técnica y resolución de incidencias en el mapa exclusivamente a los roles autorizados Boss e Ingeniero, restringiendo al rol Secretaria a un acceso de solo lectura y consulta.
        RF-15.1 (Event-driven): CUANDO un supervisor realice una modificación en la planificación u ordenación del mapa, EL SISTEMA transmitirá instantáneamente la actualización en tiempo real a todas las sesiones de supervisión activas vía WebSockets con una notificación visual no invasiva en el Dashboard de los otros usuarios concurrentes.
        RF-15.2 (Event-driven): CUANDO un supervisor arrastre una orden de trabajo sobre el marcador de una cuadrilla en el mapa o en el panel de cuadrillas, EL SISTEMA ejecutará la reasignación de forma inmediata en base de datos.
        RF-15.3 (Event-driven): CUANDO se altere la secuencia de un ítem en el acordeón de planificación de una cuadrilla, EL SISTEMA reordenará la prioridad de ejecución en la base de datos central.
        RF-15.4 (State-driven): SI una orden de trabajo ordinaria carece de una hoja de picking firmada y consolidada en /gestio/magatzem, ENTONCES EL SISTEMA bloqueará la asignación de la tarea a la cuadrilla en el mapa.
        RF-15.5 (State-driven): SI la cuadrilla activa entra en zona de sombra (sin conectividad móvil) en estado Verde (En faena), ENTONCES EL SISTEMA bloqueará cualquier asignación de tareas concurrentes sobre esa misma franja horaria en el backend central, marcando la orden como Verde persistente.
        RF-15.6 (Event-driven): CUANDO el supervisor confirme la resolución de una incidencia técnica en el Drawer lateral web, EL SISTEMA actualizará el marcador de la orden de Rojo a su color operativo correspondiente en tiempo real en la cartografía.
    RF-16 (Event-driven): CUANDO el supervisor arrastre una orden de emergencia sobre una cuadrilla activa en campo, EL SISTEMA ejecutará un Drop and Go de urgencia asignándole el flag 'Intervención Urgente (Sin Picking Previo)'.
        RF-16.1 (State-driven): SI la orden de emergencia es reasignada vía Drop and Go, ENTONCES EL SISTEMA desbloqueará en la PWA la Hoja de Consumo de Emergencia y habilitará la imputación de materiales procedentes de la dotación base (furgoneta), materiales sobrantes de tareas matinales o compras locales facturadas con tiquet de caja fotográfico.
    RF-17 (Ubiquitous): EL SISTEMA exigirá en la PWA el registro geolocalizado con fotografía de inicio de avería e imputación de horas reales y materiales para el circuito de cierre de intervenciones de urgencia.
        RF-17.1 (State-driven): SI el cliente se encuentra ausente físicamente al finalizar la reparación de urgencia, ENTONCES el operario registrará la orden como 'Cliente Ausente' en la PWA adjuntando el parte fotográfico pericial de los trabajos ejecutados.
        RF-17.2 (Event-driven): CUANDO el operario firme localmente o registre como 'Cliente Ausente' el cierre de la obra en la PWA, EL SISTEMA conmutará el marcador del mapa a Blanco (Completada) y remitirá de forma automática el parte firmado por Telegram o Email al cliente, desbloqueando el cierre administrativo diferido.
    RF-18 (Event-driven): CUANDO el supervisor reasignará una tarea o alterará el orden de prioridades desde el mapa de mando:
        RF-18.1 (State-driven): SI la cuadrilla receptora dispone de conectividad móvil activa, ENTONCES EL SISTEMA actualizará instantáneamente su Kanban de la PWA emitiendo una señal acústica y visual de notificación.
        RF-18.2 (State-driven): SI la cuadrilla receptora se encuentra offline (zona de sombra), ENTONCES EL SISTEMA registrará la asignación localmente en el backend, advertirá visualmente al supervisor de la falta de cobertura y habilitará un botón interactivo de marcación directa por voz (tel:) al capataz.
        RF-18.3 (State-driven): SI un vehículo con una orden reasignada vía Drop and Go entra en zona de sombra, ENTONCES EL SISTEMA mantendrá de forma persistente la asignación en el servidor, permitiendo únicamente al supervisor desasignarla o moverla de forma explícita.

Bloque 6: Telemetría GPS Eficiente ( Battery-Aware ) y Resiliencia de Red

    RF-19 (Ubiquitous): EL SISTEMA ejecutará el script de seguimiento en la PWA del capataz emitiendo telemetría GPS inteligente orientada al ahorro de batería, bloqueando estrictamente el rastreo continuo por polling de alta frecuencia.
        RF-19.1 (Event-driven): CUANDO el supervisor asigne temporalmente el rol de responsable de cuadrilla a otro operario (vía Dashboard debido a rotura o batería agotada del terminal del capataz), EL SISTEMA transferirá inmediatamente los permisos de reporte y la emisión de GPS inteligente a su terminal móvil.
        RF-19.2 (Event-driven): CUANDO ocurra un evento de cambio de estado geográfico (fichajes, aproximación a 50m de la obra, inicio o fin de jornada), EL SISTEMA activará el receptor GPS a máxima precisión y transmitirá la coordenada georreferenciada de forma prioritaria.
        RF-19.3 (State-driven): SI el vehículo se mantiene en ruta prolongada (estado Azul o Lila), ENTONCES EL SISTEMA espaciará periódicamente la captura de telemetría a un intervalo de 10 a 15 minutos de forma automática.
        RF-19.4 (Event-driven): CUANDO el capataz fiche el 'Fin de Jornada' en la PWA, EL SISTEMA desactivará inmediatamente el tracking GPS de la furgoneta y fijará su marcador estático en la última coordenada válida hasta la medianoche (RGPD).
    RF-20 (Ubiquitous): EL SISTEMA aplicará mecanismos automáticos de resiliencia y filtrado de alertas visuales ante la pérdida de cobertura GPS o celular de las cuadrillas.
        RF-20.1 (State-driven): SI la cuadrilla se encuentra en estado Verde (En faena) y pierde la cobertura móvil, ENTONCES EL SISTEMA mantendrá la visualización activa en Verde de forma persistente y suprimirá falsas alarmas de desconexión en el Dashboard.
        RF-20.2 (State-driven): SI un vehículo en desplazamiento (Azul o Lila) deja de emitir señal GPS, ENTONCES EL SISTEMA mantendrá el marcador original con su opacidad normal durante un buffer de resiliencia de red de 25 minutos (amortiguando el intervalo de muestreo regular de 10-15 min para evitar falsas alarmas por latencia técnica).
        RF-20.3 (Event-driven): CUANDO el intervalo sin emisión de coordenadas GPS de un vehículo en desplazamiento supere los 25 minutos, EL SISTEMA atenuará el marcador del vehículo a translúcido en el mapa, incorporará la etiqueta 'Sin señal hace X min' y disparará una alerta visual en la campana de incidencias.
        RF-20.4 (Event-driven): CUANDO el terminal recupere cobertura celular y transmita una coordenada válida, EL SISTEMA restaurará de forma automática la opacidad del marcador al 100% y actualizará el estado y traza en el mapa.

Bloque 7: Protocolos de Incidencias en Campo (Flota, Red Técnica y Dotación)

    RF-21 (Ubiquitous): EL SISTEMA desplegará el protocolo de contingencia de flota en el mapa facilitando el acceso inmediato a los datos de póliza y coberturas del vehículo averiado configurados en /gestio/flota.
        RF-21.1 (Event-driven): CUANDO el supervisor haga clic en el botón 'Llamar Grúa', EL SISTEMA abrirá la llamada de voz suministrando las coordenadas GPS exactas del punto de inmovilización.
        RF-21.2 (Event-driven): CUANDO el supervisor registre el ETA de la grúa en el Drawer lateral, EL SISTEMA activará una cuenta atrás visual sobre el marcador del vehículo.
        RF-21.3 (State-driven): SI el diagnóstico dictamina traslado del vehículo averiado en plataforma, ENTONCES EL SISTEMA habilitará el flujo de custodia legal y seguros sobre la dotación base y stock a bordo en base a las pólizas de responsabilidad civil contratadas con talleres y grúas de /gestio/proveidors.
        RF-21.4 (Event-driven): CUANDO se inicie el traslado de la furgoneta averiada, EL SISTEMA desacoplará de forma automática las tareas de la tarde colocándolas como no asignadas en el mapa, y exigirá a la cuadrilla receptora de reasignación la retirada física del material de picking específico en la nave (Spec 004).
    RF-22 (Ubiquitous): EL SISTEMA integrará herramientas de continuidad operativa ante obstáculos no autorizados sobre la red técnica o fugas detectadas.
        RF-22.1 (Ubiquitous): EL SISTEMA proyectará en el mapa el elemento de aislamiento (válvula de corte aguas arriba) más cercano a la zona de fuga o rotura en la capa de red técnica GeoJSON local.
        RF-22.2 (Event-driven): CUANDO el operario reporte visualmente un obstáculo o fuga sobre la traza en la PWA, EL SISTEMA conmutará de forma inmediata el pin de la obra a Rojo.
        RF-22.3 (State-driven): SI el supervisor autoriza un by-pass provisional de emergencia con manguera de polietileno flexible, ENTONCES EL SISTEMA registrará la instalación en la orden de trabajo, imputará el tiempo y materiales consumidos a la orden, y tarificará dichos devengos en base a la lista central de precios de /gestio/configuracio/tarifes.
        RF-22.4 (Event-driven): CUANDO se registre formalmente la negativa de acceso de un propietario rústico en la PWA, EL SISTEMA replegará la cuadrilla y habilitará en el mapa la consulta asistida al RAG contractual.
    RF-23 (Ubiquitous): EL SISTEMA gobernará la transferencia y trasvase de operarios entre cuadrillas en campo validando la normativa de seguridad vial.
        RF-23.1 (Event-driven): CUANDO el supervisor ejecute una transferencia de operarios entre cuadrillas en el mapa, EL SISTEMA actualizará de forma instantánea la composición nominal de ambas cuadrillas en los popovers correspondientes de la flota.
        RF-23.2 (Ubiquitous): EL SISTEMA exigirá el fichaje individual de presencia de los operarios trasladados mediante los botones Start / Stop en la PWA para computar el tiempo de permanencia efectiva en la obra de destino, con independencia de la duración del trayecto de traslado.
        RF-23.3 (State-driven): SI un trasvase supera la capacidad de plazas físicas homologadas del vehículo receptor según la Spec 006 (RF-28), ENTONCES el backend del SISTEMA bloqueará la transacción emitiendo la alerta en el Dashboard.
        RF-23.4 (State-driven): SI el sistema se encuentra offline, ENTONCES la PWA mostrará una advertencia expresa al capataz bloqueando el registro del trasvase que exceda el límite de plazas del vehículo, alertando de la prohibición de incurrir en sobreocupaciones de seguridad vial.

Bloque 8: Canal de Comunicación Multicanal con el Cliente Final

    RF-24 (Ubiquitous): EL SISTEMA mantendrá la comunicación automatizada de alertas y aprobaciones con el cliente final por Telegram o Email.
        RF-24.1 (Event-driven): CUANDO la cuadrilla inicie la ruta (estado Azul), EL SISTEMA remitirá una notificación por Email o Telegram al cliente con la hora estimada de llegada, omitiendo enlaces de rastreo continuo en vivo.
        RF-24.2 (Event-driven): CUANDO el capataz registre el fichaje en Punto Cero de llegada, EL SISTEMA notificará de inmediato el inicio de la faena al cliente.
        RF-24.3 (Event-driven): CUANDO se reporte una incidencia que demore el inicio de los trabajos, EL SISTEMA enviará un mensaje de retraso estimado de forma automática al cliente.
        RF-24.4 (Event-driven): CUANDO el supervisor valide y apruebe el informe pericial redactado por Copilot, EL SISTEMA remitirá al Bot de Telegram (o Email con token cifrado de un solo uso si no utiliza Telegram) la propuesta presupuestaria suplementaria con botones interactivos de aprobación y rechazo.
        RF-24.5 (State-driven): SI el cliente pulsa el botón de aprobación (vía Telegram o enlace web cifrado de un solo uso), ENTONCES EL SISTEMA procesará la aceptación de forma atómica e idempotente: registrará el timestamp de aceptación e IP de origen, conmutará el estado de la incidencia a aprobada, e inyectará de forma inmutable la partida presupuestaria suplementaria en la orden de trabajo, desbloqueando el Kanban de la PWA del operario.
        RF-24.6 (State-driven): SI se reciben peticiones concurrentes o duplicadas para la misma aprobación de presupuesto, ENTONCES EL SISTEMA retornará de forma idempotente el estado ya consolidado en la primera transacción sin alterar los acumuladores financieros ni registrar transacciones repetidas en el backend.
        RF-24.7 (Event-driven): CUANDO el cliente pulse el botón de rechazar la ampliación presupuestaria, EL SISTEMA disparará una alerta roja en el Drawer de incidencias destacando el teléfono del cliente (tel:) para requerir la llamada telefónica urgente del supervisor antes de ordenar cualquier cancelación o retirada de cuadrilla.
        RF-24.8 (State-driven): SI la cuadrilla opera en un área rural sin cobertura móvil (zona blanca) tras reportar una incidencia, ENTONCES la PWA guardará localmente los datos y firmas en IndexedDB cifrada, permitiendo proseguir la faena offline hasta recuperar conectividad celular o finalizar la jornada.

Bloque 9: Contingencias de Jornada y Gestión de Stock a Bordo

    RF-25 (Ubiquitous): EL SISTEMA gobernará los procesos de cancelación y reprogramación de obras en campo de forma diferenciada.
        RF-25.1 (Event-driven): CUANDO se procese la cancelación de una orden de trabajo, EL SISTEMA emitirá una señal acústica y alerta visual de retirada en la PWA de la cuadrilla.
        RF-25.2 (State-driven): SI la orden de trabajo cancelada se reagenda con el cliente para una fecha futura (Supuesto 1), ENTONCES EL SISTEMA adjuntará las fotos, horas y mediciones previas a la orden, la programará en la nueva fecha con estado Naranja (Pendiente) y la retirará del mapa activo de hoy.
        RF-25.3 (State-driven): SI la orden de trabajo se cancela definitivamente (Supuesto 2), ENTONCES EL SISTEMA recopilará los datos de la PWA para emitir un albarán de liquidación con los costes devengados y desplazamientos hasta el momento, conmutando el pin a Negro (Cancelada).
        RF-25.4 (Ubiquitous): EL SISTEMA prohibirá la persistencia de pines de cancelación como incidencias activas, asentándolos exclusivamente en el registro histórico del día en que acontecieron.
        RF-25.5 (Ubiquitous): EL SISTEMA mantendrá el stock de materiales cargados bajo custodia en la furgoneta para su retorno a almacén al cierre de la jornada, salvo reasignación formal por Drop and Go.
    RF-26 (Ubiquitous): EL SISTEMA gestionará las alertas de finalización anticipada de faena y sugerencias de reasignación.
        RF-26.1 (Event-driven): CUANDO se registre una finalización anticipada de obra, EL SISTEMA notificará la alerta en el mapa de /gestio sugiriendo la reasignación mediante Drop and Go con stock compatible o la convergencia de apoyo hacia otra cuadrilla retrasada.

Bloque 10: Estado "Día 0" y Control de Mando

    RF-27 (Ubiquitous): EL SISTEMA ejecutará controles de tolerancia cero a datos ficticios en la cartografía en caso de estar en Día 0 (sin tareas programadas).
        RF-27.1 (Ubiquitous): EL SISTEMA centrará la cámara del mapa en las coordenadas reales de la sede o Almacén Central de la empresa provistas en el onboarding del SaaS en caso de estar en Día 0 (sin tareas programadas).
        RF-27.2 (Ubiquitous): EL SISTEMA bloqueará la interfaz de la cartografía si no se completan las coordenadas reales de la empresa en el onboarding, prohibiendo estrictamente la visualización de datos simulados o dummy.
        RF-27.3 (Ubiquitous): EL SISTEMA mostrará un panel lateral con el mensaje 'Sin tareas programadas para esta fecha' y colocará todos los contadores del HUD superior a 0.
    RF-28 (Ubiquitous): EL SISTEMA gobernará los accesos y permisos mediante la matriz de roles técnica.
        RF-28.1 (Ubiquitous): EL SISTEMA limitará los permisos del rol Secretaria a solo lectura y consulta telefónica en la interfaz del mapa, bloqueando toda acción de arrastre, reasignación o aprobación presupuestaria.
        RF-28.2 (Ubiquitous): EL SISTEMA otorgará permisos de escritura completos para Drop and Go, conmutación de estados, edición de prioridades y resolución de incidencias en el Drawer únicamente a los roles Boss e Ingeniero.

Bloque 11: Centro de Resolución de Incidencias en el Mapa (Drawer Lateral Emergente)

    RF-29 (Ubiquitous): EL SISTEMA centralizará la gestión de alertas e incidencias mediante el Drawer lateral emergente de forma no invasiva.
        RF-29.1 (Ubiquitous): EL SISTEMA mantendrá el Drawer lateral de incidencias oculto y colapsado por defecto en la parte derecha del mapa.
        RF-29.2 (Event-driven): CUANDO se reciba una nueva incidencia de campo, EL SISTEMA activará una alerta visual en la cabecera (campana roja parpadeante, incremento de contador y banner superior discreto) sin desplegar automáticamente el Drawer para evitar la interrupción del mapa.
        RF-29.3 (Event-driven): CUANDO el supervisor haga clic sobre la pestaña derecha del mapa, sobre el banner de alerta, sobre la campana o sobre un marcador rojo, EL SISTEMA desplegará el Drawer lateral de incidencias.
        RF-29.4 (Event-driven): CUANDO se acceda a la URL /gestio/incidencies, EL SISTEMA redirigirá de manera transparente a /gestio?incidencies=obertes, abriendo el Drawer enfocado y manteniendo visibles de forma persistente todas las incidencias abiertas de la empresa.
        RF-29.5 (Ubiquitous): EL SISTEMA ordenará cronológicamente las incidencias de llegada en la columna del Drawer, requiriendo que el supervisor determine el orden de atención según criterios humanos de urgencia técnica y seguridad.
    RF-30 (Ubiquitous): EL SISTEMA estructurará el flujo interactivo de resolución de imprevistos con el cliente incorporando el filtro humano previo de ingeniería.
        RF-30.1 (State-driven): SI el supervisor requiere la aprobación de una tarea suplementaria, ENTONCES EL SISTEMA mostrará en el Drawer el teléfono directo del cliente con botón de marcación urgente (tel:) para la autorización verbal de contingencias.
        RF-30.2 (Ubiquitous): EL SISTEMA bloqueará la remisión de cualquier propuesta de presupuesto extra o informe pericial redactado por Copilot al cliente si carece de la validación y firma digital explícita de aprobación humana por parte del supervisor.
        RF-30.3 (Event-driven): CUANDO el supervisor apruebe el informe pericial, EL SISTEMA enviará la hoja interactiva de aceptación con botones de aprobación y rechazo vía Bot de Telegram o Email con token cifrado de un solo uso.
        RF-30.4 (State-driven): SI el cliente pulsa el botón de aprobación, ENTONCES EL SISTEMA registrará la transacción de forma inmutable, conmutará la incidencia a aprobada, e inyectará de forma atómica la partida suplementaria en la orden de trabajo, desbloqueando la PWA del operario en campo.
        RF-30.5 (Event-driven): CUANDO el cliente pulse el botón de rechazar la ampliación presupuestaria, EL SISTEMA activará de forma prioritaria en el Drawer el teléfono directo del cliente (tel:) para gestionar una llamada directa antes de suspender.
    RF-31 (Ubiquitous): EL SISTEMA automatizará las tareas asociadas al reporte de averías mecánicas o colisiones.
        RF-31.1 (Event-driven): CUANDO se reporte una avería inmovilizante de flota, EL SISTEMA habilitará en el Drawer de incidencias la llamada a grúa en un clic, el envío automático de notificaciones de demora a clientes afectados por Telegram/Email, y el desacoplamiento de las tareas de la tarde.
        RF-31.2 (State-driven): SI las cuadrillas cercanas carecen de plazas físicas homologadas suficientes en base a la Spec 006 (RF-28) para el traslado de operarios, ENTONCES el backend del SISTEMA bloqueará la asignación de plazas y el supervisor gestionará transporte de apoyo alternativo.
    RF-32 (Ubiquitous): EL SISTEMA gobernará la disponibilidad e intercambio de herramientas y mermas en campo.
        RF-32.1 (State-driven): SI una furgoneta reporta la rotura o falta de una herramienta crítica, ENTONCES EL SISTEMA analizará mediante un chequeo algorítmico si alguna furgoneta cercana dispone de la herramienta libre, validando si figura en sus tareas matinales ya concluidas y no en tareas posteriores.
        RF-32.2 (Ubiquitous): EL SISTEMA registrará de forma obligatoria la nueva custodia en el módulo de Almacén al ejecutarse el traslado físico de una herramienta.
        RF-32.3 (Ubiquitous): EL SISTEMA proyectará de forma conmutable la capa de proveedores y ferreterías locales con sus teléfonos directos (tel:) para validar stock previamente.
        RF-32.4 (Event-driven): CUANDO se active un vehículo de auxilio, EL SISTEMA proyectará su telemetría GPS mediante la PWA y le asignará su propia hoja de tarea, procesando sus averías o contingencias de forma aislada e independiente.
        RF-32.5 (Ubiquitous): EL SISTEMA asociará y registrará de forma indeleble las incidencias técnicas de roturas de herramientas a la cuadrilla o persona que ostentaba la custodia de la herramienta en el momento del fallo.
        RF-32.6 (State-driven): SI el supervisor constata negligencia manifiesta o mala praxis tras la inspección pericial del fallo, ENTONCES EL SISTEMA registrará la elevación a RRHH; en caso contrario, se procesará como merma ordinaria de almacén.

Bloque 12: Alcance de Protocolo Offline-First, Contraste Presupuestario y Mandato Human-in-the-Loop al Cierre

    RF-33 (Ubiquitous): EL SISTEMA delimitará de forma rigurosa la frontera de persistencia offline frente a la necesidad física de conexión móvil.
        RF-33.1 (Ubiquitous): EL SISTEMA amparará la persistencia local cifrada (IndexedDB con Web Crypto API) únicamente de los datos técnicos de la hoja de tarea en la PWA (notas de voz, fotos, horas, planos, consumos), obligando al capataz a desplazarse para buscar cobertura móvil para reportar incidencias imprevistas.
        RF-33.2 (Ubiquitous): EL SISTEMA bloqueará la redacción o emisión de cualquier albarán o liquidación de obra si carece de la documentación completa de la hoja de tarea sincronizada desde la PWA.
        RF-33.3 (State-driven): SI se detecta una desviación en los consumos tras la sincronización, ENTONCES EL SISTEMA contrastará automáticamente los consumos reales frente al presupuesto base aprobado, el cual permanece inmutable.
        RF-33.4 (Ubiquitous): EL SISTEMA prohibirá imputar de forma automática desviaciones financieras al expediente del capataz en RRHH, requiriendo obligatoriamente que el supervisor técnico constate negligencia grave demostrada.
        RF-33.5 (Ubiquitous): EL SISTEMA bloqueará la derivación automática de presupuestos finales de obra, albaranes o liquidaciones a Contabilidad (/gestio/comptabilitat), requiriendo de forma obligatoria la firma digital y aprobación humana explícita del supervisor o Boss.

Bloque 13: Trazabilidad Multinivel e Imputación Disciplinaria Objetiva en RRHH

    RF-34 (Ubiquitous): EL SISTEMA garantizará la trazabilidad completa y la inmutabilidad de los registros disciplinarios de la empresa técnica.
        RF-34.1 (Ubiquitous): EL SISTEMA registrará todas las incidencias reportadas de forma indeleble en la hoja de tarea activa correspondiente.
        RF-34.2 (Event-driven): CUANDO una incidencia afecte directamente a un vehículo, EL SISTEMA replicará la información en el historial de la ficha del vehículo en /gestio/flota.
        RF-34.3 (Ubiquitous): EL SISTEMA bloqueará la anotación de faltas laborales o expedientes disciplinarios de forma automática, reservando dicha decisión al análisis de un supervisor, Boss o responsable de RRHH.
        RF-34.4 (Ubiquitous): EL SISTEMA exigirá para las anotaciones disciplinarias de RRHH criterios de valoración objetiva: atestado oficial o parte de accidente contrastado para siniestros viales; responsable de la hoja de picking de almacén para olvidos de material; y capataz para faltas colectivas.
        RF-34.5 (Ubiquitous): EL SISTEMA limitará el acceso y visualización de las anotaciones disciplinarias en el expediente laboral exclusivamente a los roles Secretaria / RRHH y Boss.

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
	
Dos ingenieros reasignan la misma orden a diferentes cuadrillas vía arrastre en el mismo milisegundo.
	
Aplica control de concurrencia optimista (version_id en la orden) y bloqueo pesimista en base de datos (SELECT FOR UPDATE). El primer commit tiene éxito, el segundo es rechazado con excepción HTTP 409 y alerta no bloqueante para refrescar pantalla.
EDGE-02
	
Unwanted
	
PWA / GPS
	
El operario intenta fichar en el Punto Cero de la cancela, pero el GPS reporta precisión accuracy > 20 metros.
	
Si tras 3 reintentos separados por 10s la precisión sigue siendo baja, la PWA habilita "Fichaje Asistido por Foto Pericial", requiriendo foto del entorno. Se inicia el crono y se genera una alerta de verificación manual para el supervisor.
EDGE-03
	
State-driven
	
Horarios
	
Una orden de trabajo permanece en estado Rojo (Incidencia activa) al finalizar la jornada de trabajo (18:00) y pasa de un día para otro.
	
Rollback Funcional: EL SISTEMA detiene administrativamente el acumulador de horas de la orden en base de datos a las 18:00 para evitar imputar horas extras nocturnas ficticias. CUANDO sean las 08:00 (Día +1), EL SISTEMA carga la orden roja en la cabecera de despacho matinal de 'HOY' para forzar la decisión humana del supervisor.
EDGE-04
	
Event-driven
	
Telemetría
	
Un vehículo en ruta (Azul o Lila) entra en túnel o zona de sombra prolongada y interrumpe la emisión GPS durante más de 25 minutos.
	
Resiliencia en Ruta: EL SISTEMA mantiene el marcador original con opacidad normal durante un buffer de resiliencia de 25 minutos. CUANDO la falta de emisión supere los 25 minutos, EL SISTEMA atenuará el marcador a translúcido, añadirá la etiqueta "Sin señal hace X min" y disparará alerta en campana.
EDGE-05
	
Event-driven
	
Logística
	
El vehículo de apoyo despachado de emergencia con herramientas de repuesto sufre una avería mecánica en ruta.
	
Desacopla la hoja de tarea del vehículo de apoyo, emite una alerta roja en el Drawer del supervisor y le sugiere alternativas de re-enrutamiento (localizar otra cuadrilla cercana o derivar compra a ferretería local mediante capa cartográfica).
EDGE-06
	
Unwanted
	
Sincronización
	
El operario conmuta a Verde desde PWA al mismo milisegundo en que el supervisor conmuta a Verde desde el Dashboard.
	
Idempotencia Transaccional: El backend gestiona de forma idempotente la transición de estados mediante tokens únicos de petición. Si la orden ya se encuentra en Verde, se ignora la segunda petición retornando éxito con el estado consolidado actual sin lanzar errores de duplicidad.
EDGE-07
	
Event-driven
	
Facturación
	
Una obra cancelada por falta de acuerdo pasa a Negro, pero minutos después el cliente aprueba el presupuesto extra por Telegram/Email.
	
El webhook procesa la aceptación, cambia el estado a Verde, bloquea el presupuesto como inmutable, lanza alerta acústica al supervisor y este contacta telefónicamente con la cuadrilla en retirada para reanudar los trabajos.
EDGE-08
	
Unwanted
	
Seguridad Vial
	
El supervisor reasigna operarios de un vehículo averiado a furgonetas cercanas, pero se superan las plazas físicas homologadas.
	
El backend bloquea el trasvase que exceda las plazas reales del vehículo receptor. Advierte en PWA al capataz y en Dashboard al supervisor, exigiéndole gestionar un transporte alternativo (taxi de póliza, auxilio o retorno).
EDGE-09
	
Unwanted
	
Custodia
	
Una herramienta transferida en campo entre cuadrillas se rompe durante la jornada tras el traspaso.
	
La incidencia técnica se asocia a la cuadrilla receptora que ostentaba la custodia física responsable en ese momento según el registro de traspaso. El supervisor realiza inspección pericial previa a cualquier elevación de negligencia a RRHH.
EDGE-10
	
Event-driven
	
Canal Cliente
	
El cliente no tiene Telegram y aprueba la ampliación presupuestaria pulsando el botón desde el correo electrónico.
	
Aprobación de Un Solo Uso e Idempotencia: El clic en la página de aprobación web mediante token cifrado de un solo uso ejecuta la misma lógica atómica de idempotencia que el Bot de Telegram: registra timestamp de aceptación e IP, bloquea el presupuesto, conmuta la incidencia a aprobada, desbloquea la PWA y bloquea peticiones de firma concurrentes para la misma transacción.
--------------------------------------------------------------------------------
Requisitos No Funcionales

    Cartografía Soberana y Gratuita (Cero Costes de API): Visualización mediante Leaflet / MapLibre GL JS con capas de teselas libres (OpenStreetMap y PNOA/ESRI), sin cuotas de facturación por peticiones cartográficas ni filtración de datos de clientes o coordenadas fuera de la UE.
    Rendimiento Ultrarrápido y Fluidez a 60 fps: La renderización de 50 marcadores de obra, 15 vehículos simultáneos, capas técnicas vectoriales y apertura reactiva del Drawer de incidencias responderá con latencia inferior a 200 ms y 60 fps estables en Next.js.
    Procesamiento Asíncrono en Segundo Plano (Celery + Redis): El procesamiento de audios de campo con Whisper v3, la generación del informe de Copilot y las notificaciones automáticas por Telegram a clientes y grúas se ejecutan en segundo plano en Celery, garantizando que el event loop de FastAPI nunca se bloquee.
    Seguridad Multi-Tenant (RLS): Aislamiento estricto por app.current_empresa_id en todas las tablas de obras, cuadrillas, incidencias, telemetría y capas vectoriales a nivel de PostgreSQL.
    Almacenamiento Seguro Local y Soberano: Todas las evidencias multimedia y documentales se alojan estrictamente en la memoria interna y discos duros locales de la empresa y en el servidor Hetzner Cloud (Alemania - UE) bajo el árbol /data/<empresa_id>/... y /docs/<empresa_id>/..., eliminando totalmente cualquier servicio cloud externo (como AWS S3).
    Privacidad Laboral y RGPD: Prohibido registrar o registrar trazas de carretera continuas en el mapa histórico; solo se persisten eventos de presencia y fichajes en obras y bases autorizadas.
    Diseño Camaleón en Software vs Simbología Cartográfica Funcional: La interfaz de la plataforma web, el Drawer lateral y las notificaciones adoptan la paleta camaleónica corporativa (--color-primary, --color-secondary), mientras que los iconos y estados del mapa mantienen una simbología cartográfica fija, universal y de contraste funcional independiente.
    Diseño 100% Responsive y Adaptabilidad Multi-Dispositivo: La pantalla del mapa y sus paneles desacoplados se adaptan dinámicamente a cualquier factor de forma (monitores desktop, tablets de cabina o smartphones de supervisores), garantizando visibilidad despejada y plena operatividad táctil.

--------------------------------------------------------------------------------
Fuera de Alcance (Lo que NO hace este módulo)

    No es una herramienta de navegación GPS paso a paso en ruta (se delega en la PWA a apps nativas como Google Maps o Waze mediante enlace externo).
    No realiza trazado continuo de líneas de velocidad ni análisis de telemetría de frenadas (no es un sistema de tacógrafo pesado de carretera).
    No emite facturas oficiales ni efectúa cobros bancarios desde el mapa (se canaliza a /gestio/comptabilitat).
    No gestiona el picking físico de nave central (se gobierna en /gestio/magatzem).
    No mantiene una pantalla separada e inconexa para /gestio/incidencies; la ruta redirige a /gestio/feines/mapa?incidencies=obertes para resolución unificada en el mapa.

--------------------------------------------------------------------------------
Criterios de Finalización (Definition of Done)

    Todos los Requisitos Funcionales (RF-01 al RF-34) y todas las cláusulas de Casos Límite (EDGE-01 a EDGE-10) redactados en sintaxis formal EARS respondiendo fielmente al QUÉ y al POR QUÉ de la operativa real.
    Correspondencia del 100% de los requisitos funcionales y casos límite con una suite de pruebas automatizada, ejecutada en verde contra base de datos PostgreSQL real con RLS activo y sin datos simulados (Zero-Mock Policy).
    Arquitectura cartográfica 100% Open Source basada en Leaflet / MapLibre GL con capas OpenStreetMap y PNOA Ortofoto sin dependencias comerciales de API.
    Capa vectorial propia de infraestructura técnica integrable mediante GeoJSON/KML local en /docs/<empresa_id>/planols/vectorials/.\
    Georreferenciación obligatoria previa con geovalla de 50 metros y validación con precisión GPS de 20 metros.
    Código cromático con distinción ontológica estricta: Órdenes (Naranja Pendiente, Azul En tránsito, Verde En faena, Rojo Incidencia activa en obra, Blanco Completada, Negro Cancelada) y Vehículos (Azul En tránsito con tarea, Lila Standby/tránsito sin tarea, Rojo Avería mecánica, Inmóvil en obra sin color / neutro).
    Prioridad absoluta a la visión despejada del mapa y paneles laterales bajo demanda con diseño 100% responsive adaptable a monitores, tablets y smartphones.
    Coexistencia pacífica de paneles: el Drawer de incidencias y el panel de órdenes del día coexisten sin destrucción mutua de estado según el factor de forma del dispositivo.
    Convivencia operativa legítima: coexistencia física de dos cuadrillas en la misma parcela para tareas distintas o colaborativas sin disparo de falsas alarmas ni conflictos.
    Persistencia temporal de incidencias: todas las incidencias abiertas permanecen marcadas en el mapa y en el Drawer hasta su efectiva resolución, unificando la ruta /gestio/incidencies.
    Gestión de imprevistos con el cliente: informe de Copilot con mandato Human-in-the-Loop antes de enviar a Telegram/Email; pulsación de rechazar o dudas dispara prioritariamente llamada urgente para buscar acuerdo o reparar antes de que el supervisor decida cancelar.
    Cancelaciones y reagendamientos con distinción nítida: Supuesto 1 (Reagendada a fecha futura Naranja) y Supuesto 2 (Cancelada definitivamente Negro liquidando devengos); las cancelaciones no perduran como pines activos en el mapa, quedando registradas en el historial del día.
    Principio de distribución y concomitancia operativa: sesiones síncronas concurrentes entre Boss e Ingenieros con sincronización en vivo y alertas visuales.
    Resolución de averías de flota en el Drawer: llamada a grúa en 1 clic, aviso automático a clientes de tareas pendientes por Telegram/Email, desacoplamiento de órdenes para Drop & Go retirando la cuadrilla receptora el material de picking en nave (Spec 004), y gestión de transporte alternativo ante incompatibilidad de plazas.
    Resolución de rotura de herramientas y piezas: traspaso condicional evaluado algorítmicamente según la finalización de tareas matinales en la hoja de faena de la Cuadrilla B, logística de transporte físico determinada por el supervisor, capa de proveedores locales con verificación telefónica de stock, e imputación de incidencia técnica a quien ostenta la custodia física con inspección pericial del supervisor previa a cualquier valoración de negligencia en RRHH.
    Operativa del vehículo de auxilio/apoyo: dotado de presencia GPS mediante la PWA y asignación de su propia hoja de tarea; contingencias y averías del vehículo de auxilio tratadas como eventos aislados e independientes.
    Protocolo Offline-First delimitado: rige para datos técnicos de la hoja de tarea y traspasos en IndexedDB cifrado con Web Crypto API; las incidencias imprevistas exigen búsqueda de cobertura para desbloquear la faena; ante apagón total prolongado la cuadrilla prosigue en faena 100% offline.
    Obligatoriedad documental de la PWA: ningún albarán de final de tarea se redacta sin la documentación completa de la PWA.
    Supervisión humana de desviaciones al cierre: cero imputación automática al capataz sin negligencia de obra constatada por el supervisor técnico.
    Mandato Human-in-the-Loop innegociable: todos los albaranes y liquidaciones finales de obra exigen validación y aprobación humana explícita del supervisor o Boss antes de pasar a Facturación (/gestio/comptabilitat).
    Trazabilidad disciplinaria objetiva: siniestros viales imputados estricta y exclusivamente según atestado oficial de tráfico o parte amistoso verificado, picking en almacén, y capataz en faltas colectivas.
    Funcionalidad "Drop and Go" como recurso de contingencias con Hoja de Consumo de Emergencia.
    Telemetría GPS eficiente ( Battery-Aware ) emitida exclusivamente por el capataz con apagado al fin de jornada, buffer de 25 minutos para alertas de pérdida de señal GPS en carretera, y delegación temporal de rol de capataz a un operario en caso de apagón o rotura de terminal.
    Imputación horaria de operario por Start / Stop en obra de destino, con independencia de la duración del trayecto de traslado.
    Prohibición estricta de imprudencias y sobreocupaciones de plazas en modo offline bajo apercibimiento disciplinario grave de seguridad vial.
    Protocolo de continuidad de red técnica ante obstáculos no autorizados: by-pass provisional de emergencia facturando mano de obra y materiales consumidos a la orden, con soporte de RAG local.
    Reactivación y transición de incidencias formalizada: el supervisor reactiva y resuelve en el Drawer web; el capataz cierra la tarea técnica en la PWA.
    Tolerancia Cero a Datos Ficticios ( Zero Mock Data ) con Estado Día 0 real centrado en base de empresa provista en onboarding.
    Almacenamiento seguro soberano en memoria interna de la empresa y servidor Hetzner en Alemania (/data/<empresa_id>/... y /docs/<empresa_id>/...) con eliminación absoluta de AWS S3, garantizando privacidad y cumplimiento RGPD.
    Rendimiento <200 ms y 60 fps estables garantizado mediante arquitectura asíncrona Celery + Redis para Whisper, Copilot y Telegram.