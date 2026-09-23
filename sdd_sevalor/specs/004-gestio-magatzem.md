Spec 004 — Mòdul de Magatzem i Inventari (/gestio/magatzem)
AVÍS D'ALINEACIÓ CONSTITUCIONAL I INTEGRACIÓ ARQUITECTÒNICA: Aquesta especificació tècnica es regeix de forma innegociable pels principis de la Constitució de CampoPro Suite (v4.0) i s'integra de forma transversal amb la Torre de Control Geogràfica en temps real (Spec 001 i Spec 005), el Mòdul de Clients (Spec 002), el Mòdul de Proveïdors (Spec 003), el Mòdul de Flota (Spec 006), el Mòdul de Treballadors/Operaris (Spec 008) i el Mòdul Contable (Spec 007).
Es prohibeix taxativament l'ús de dades simulades o de prova (Zero Mock Data), partint d'un estat de "Dia 0" real i garantint de forma absoluta la sobirania de dades mitjançant l'emmagatzematge local/sobirà dels expedients de materials, plànols, albarans i inventaris en el servidor Hetzner de Falkenstein (Alemanya - UE), rebutjant completament qualsevol servei de núvol públic extern (com AWS S3) d'acord amb el compliment estricte de la LOPDGDD i el RGPD.
De conformitat amb la Constitució i el criteri de QA unificat, es fa l'exclusió absoluta de codis QR per a la traçabilitat i transferència d'eines de camp (les quals es gestionen estrictament mitjançant el número de referència únic de fabricant, marca i model). Aquesta decisió de disseny de l'inventari convive en perfecta harmonia amb la permanència del codi QR legal i tributari requerit obligatòriament a totes les factures i albarans de lliurament oficials (Veri*factu).
--------------------------------------------------------------------------------
Context i Objectiu
El mòdul de Magatzem i Inventari (/gestio/magatzem) és el pulmó operatiu, logístic i de control de materials de CampoPro Suite. Centralitza la supervisió de l'estoc de l'empresa, connectant directament l'entrada de subministraments dels proveïdors (Spec 003) amb la preparació de les furgonetes de camp pel picking matinal, el control d'equips en trànsit, les transferències d'eines entre treballadors i la imputació del material instal·lat a cada obra de client (Spec 001/002/005).
Aquest mòdul resol els següents àmbits clau d'eficiència i resiliència:

    Arquitectura Multimagatzem sota RLS: Control unificat en viu de la nau (Almacén Central), el stock rodant per vehicle (furgonetes considerades tallers mòbils amb dotació base) i les eines sota la custòdia nominal de treballadors individuals (Spec 008).
    Gestió de Materials de Format Continu: Distinció operativa de tractament per a productes que es subministren per format rígid (barra) o format flexible (bobines/rotllos continus), habilitant l'ús obligatori de retalls o mermes parcials prèvies abans de permetre el tall de noves unitats, amb valoració proporcional.
    Traçabilitat sense Mocks d'Eines i Maquinària: Seguiment unívoc de cada exemplar d'eina mitjançant el patró [Nombre Herramienta] [Nº Ejemplar] = [Número de Serie/Referència], inhabilitant de forma inalterable i perenne aquells equips donats de baixa per robatori o pèrdua per evitar que es puguin tornar a planificar.
    Bloqueig Transaccional s'evitació de Condicions de Carrera: Implementació del bloqueig pesimista a nivell de PostgreSQL (SELECT FOR UPDATE) durant el procés de planificació d'obres, garantint que si dos enginyers planifiquen obres concurrentment amb el mateix material al mateix mil·lisegon, el sistema bloquegi l'estoc virtual per a la primera transacció i impedeixi l'assignació d'estoc inexistent per a la segona.
    Recepció OCR Multicomanda i Gestió de Backorders: Enllaç asíncron amb el mòdul de proveïdors (Spec 003) per a l'entrada assistida d'albarans mitjançant Copilot IA, amb capacitat de digerir albarans parcials que resolguin línies de comandes de compra diferents i actualitzin de forma asíncrona els preus mitjans ponderats (PMP) sense alterar proformes passades.
    Facturació d'Anticipos i Cierre en Partida Doble Segregada: Gestió dels dipòsits de garantia de materials de client amb emissió de factures d'anticip d'obligat compliment (mínim 45%) d'acord amb Veri*factu, permetent el reingrés físic de sobrants en camp però imputant el 100% contable de mermes o envasos desprecintats a l'obra del client.

--------------------------------------------------------------------------------
Usuaris / Actors i Matriu d'Accés (Zero-Trust)
El sistema garanteix l'aïllament multi-inquilí mitjançant Row Level Security (RLS) mandatori a nivell de base de dades (empresa_id) i una segregació de responsabilitats total (Separation of Duties):

    Boss (Gerència / Propietario): Accés complet a totes les funcionalitats de /gestio/magatzem. Pot aprovar compres suggerides per la IA, modificar els llindars de stock mínim de seguretat, autoritzar baixes directes per pèrdues de materials danyats o robatoris d'eines (amb signatura d'auditoria), visualitzar la valoració comptable agregada de l'inventari basat en el darrer preu de compra i mètode PMP, i tancar l'inventari general anual d'obra.
    Secretaria / Administració: Gestió operativa de l'estoc. Processa les entrades d'albarans per OCR, concilia entregues parcials de proveïdors (backorders), tramita mermes, reingresa envasos retornables amb fianza, i emet factures de venda d'anticips de materials o facturació de chatarra/residus de camp. Accedeix a preus de compra, despeses i valoracions de stock.
    Enginyer / Supervisor Tècnic: Executa la planificació i reserva d'estoc per a obres, consulta la disponibilitat de stock rodant o materials de la nau central per a reassignacions, i gestiona les incidències tècniques (rotures d'eines o substitucions a tajo). El sistema aplica un bloqueig estricte (HTTP 403 Forbidden) a nivell d'API i oculta del DOM qualsevol preu d'adquisició, costos de proveïdors, albarans de compra o valoració de stock agregat en euros (€), podent pressupostar l'obra exclusivament mitjançant tarifes de preu final de venda amb marge configurat.
    Cap de Colla (Capataz) i Operari (/operari): No tenen accés web a /gestio/magatzem. Utilitzen la PWA mòbil de camp per a validar la fulla de picking matinal assigned (1 tasca = 1 fulla de picking), registrar devolucions de materials sobrants (marcant el check parcial de tubos/cables), reportar mermes o averies d'eines, i tramitar traspassos ràpids en camp offline sense codes QR de conformitat amb la Constitució.

Matriu de Permisos per Rol
Àmbit Funcional
	
Boss
	
Secretaria / RRHH
	
Enginyer Tècnic
	
Cap de Colla / Operari
Catàleg, Stock Físic i Ubicacions
	
Lectura / Escriptura
	
Lectura / Escriptura
	
Solo Lectura
	
Lectura (PWA)
Planificació, Reserves i Bloqueig
	
Total
	
Total
	
Escriptura / Transaccional
	
Sense accés
Fulla de Picking i Devolució Parcial
	
Total
	
Total
	
Solo Lectura
	
Escriptura (PWA)
Preus de Venda (Marges Presupost)
	
Lectura completa
	
Lectura completa
	
Lectura completa
	
Sense accés
Preus de Compra i Factures Proveïdor
	
Lectura completa
	
Lectura completa
	
Bloqueig Total (403)
	
Sin acceso
Valoració Econòmica d'Inventari (PMP)
	
Lectura completa
	
Lectura completa
	
Bloqueig Total (403)
	
Sin acceso
Baixes per Siniestre i Auditories
	
Total / Signat
	
Tramitació
	
Denegat (403)
	
Sin acceso
Emissió Factura d'Anticipo Veri*factu
	
Redirecció
	
Emet / Envia
	
Denegat (403)
	
Sin acceso
Gestió i Venda Residus / Chatarra
	
Total
	
Total
	
Denegat (403)
	
Sin acceso
Estat inactiu d'actius (Soft-Delete)
	
Permès
	
Permès
	
Denegat (403)
	
Sin acceso
--------------------------------------------------------------------------------
Històries d'Usuari

    H1: Com a Enginyer, quan planifiqui una nova ordre de treball, vull que el sistema apliqui un bloqueig pesimista (SELECT FOR UPDATE) a la base de dades durant el desat per garantir que si un company guarda una altra obra concurrentment no es pugui reservar el mateix stock físic.
    H2: Com a Enginyer, vull veure de forma transparent els preus de venda finals dels productes de magatzem per fer pressupostos idonis a client, sense tenir visibilitat de les factures o preus de cost de proveïdor que queden restringits a administració.
    H3: Com a Enginyer, quan l'estoc estigui baix o en camí de rotura, vull que el Copilot d'IA em mostre visualment el stock en trànsit parcial d'un albarà o Backorder pendent d'entrega per saber si podrem executar l'obra a temps.
    H4: Com a Cap de Colla, quan reculli materials lineals continus com tubs o cables, vull que el sistema em detalli a la PWA si és una barra o bobina, obligant-me a recollir abans un retall parcial existent sota custòdia abans d'iniciar el tall d'un format nou.
    H5: Com a Operari, vull registrar el picking i l'inici d'obra sense cobertura GSM, confiant que IndexedDB i el Service Worker escripturin de forma segura en local sota xifrat AES-GCM i em llancin una alerta si el buffer de fotos aproxima el límit d'emmagatzematge mòbil de la quota del navegador.
    H6: Com a Boss o Secretaria, quan una eina (bomba, generador) sigui robada o danyada irremeiablement, vull procedir a la seva Baixa Definitiva bloquejant per sempre el seu Número de Sèrie a la base de dades per evitar qualsevol reactivació o frau posterior d'inventari.
    H7: Com a Secretaria, vull poder emetre la Factura d'Anticipo Veri*factu (mínim 45% de materials) al client quan aquest confirmi el pressupost, reingressant a stock el material intacto de camp i liquidant el saldo de tancament segons la modalitat del contracte d'obra.
    H8: Com a Supervisor, quan dues quadrilles a camp es traspassin una eina o material a tajo rural sense cobertura, vull que es registri a la PWA mitjançant el seu número de referència, canviant de forma bilateral la custòdia i reconciliant el moviment síncron al recuperar xarxa.

--------------------------------------------------------------------------------
Requisits Funcionals (Notació EARS Estricta)
Bloque 1: Directori General de Magatzem i Estat "Día 0"

    RF-01 (Ubiquitous): EL SISTEMA renderitzarà a /gestio/magatzem un llistat tabular de materials nets i eines de treball, utilitzant paginació del costat del servidor (Server-Side PaginationLIMIT/OFFSET) per garantir una resposta ràpida en Next.js, mostrant per a cadascun: Referència, Nom/Descripció, Proveïdor habitual, Ubicació física, Estoc Total Actual, Estoc Mínim, i Estat de comanda.
    RF-02 (Ubiquitous): EL SISTEMA disposarà a la part superior d'un cercador de text reactiu que filtrarà de forma asíncrona la quadrícula en menys de 200 ms per coincidencia sobre: Referència d'article, Nom del producte, Marca, Model, Proveïdor o Ubicació física (Gaveta/Palé), insensitive a tildes i majúscules.
    RF-03 (Ubiquitous): EL SISTEMA habilitarà filtres de segmentació ràpids per aïllar de forma dinàmica: stock sota mínims, eines i maquinària pròpia, stock rodant de furgonetes, materials en dipòsit de proveïdor, slot de residus/chatarra i envasos retornables amb fianza.
    RF-04 (State-driven): SI la base de dades del tenant es troba buida sense articles actius (Estat Día 0 real), ENTONCES EL SISTEMA renderitzarà la interfície buida, inhabilitarà el cercador i els desplegables, i oferirà exclusivament els botons primaris d'acció: [Alta manual d'article] i [Entrada assistida per IA (OCR)], sense inserir en cap cas dades de prova fictícies o dades demo (Zero Mock Data).

Bloque 2: Alta de Materials, Format Continu, Atributs Tècnics i OCR

    RF-05 (Event-driven): QUAN l'usuari prepa l'acció "Alta manual d'article", EL SISTEMA desplegará el modal d'alta requerint: Referència unívoca d'inventari, Nom, Unitat de mesura, Família, Estoc Óptim i Mínim de seguretat, i Ubicació Dual (Gaveta per a recollida ràpida i Palet de stock per a mermes generals).
    RF-05.1 (Ubiquitous): EL SISTEMA forçarà el tancament de camps normalitzats i especificacions tècniques en base a la vertical de l'empresa (p. ej. DN, PN, secció de cable mm², tensió o capacitat de caudal), validant tipologies i rebutjant entrades textuals caòtiques.
    RF-06 (Ubiquitous) — Gestió de Materials de Format Continu i Retalls: EN materials de tall lineal de format continu (tuberies, mangueres, cables elèctrics), EL SISTEMA estructurarà el stock diferenciant entre format d'origen sencer (bobina, rotllo sencer, barra de 6 m) i retalls o porcions parcials de camp (tubs o cables de menor longitud):
        El sistema calcularà de forma proporcional el cost i preu de venda dels retalls per metre lineal.
        El backend de la PWA del operari obligarà a seleccionar i exhaurir de forma prioritària els retalls parcials existents de l'estoc del vehicle abans de permetre o registrar el tall d'una bobina o barra rígida sencera.
    RF-07 (Ubiquitous) — Traçabilitat d'Eines d'Almacén i Custòdia sense QR: EL SISTEMA referenciarà de forma innegociable qualsevol eina o maquinària de treball mitjançant el seu codi de referència de fabricant, model i el seu Número de Sèrie (SN) únic, vinculant de forma transaccional la seva possessió i custòdia legal a un destí concret (Almacén Central o Responsable de furgoneta). Es prohibeix qualsevol ús o generació de codis QR corporatius per a eines en camp.
    RF-08 (Unwanted behavior) — Recepció de stock sense justificació documental: QUADA totalment prohibida la recepció física de material o entrada de stock sense albarà o factura de proveïdor associada sota el SIF. QUAN el de Secretaria seleccioni "Entrada assistida per IA", EL SISTEMA processará el document PDF mitjançant el motor OCR de Copilot, identificant les línies, unitats, preu de cost de compra, desglossaments i els associarà asíncronament a l'estoc, validant albarans multi-pedido que pertanyin a comandes de compra diferents.
        - **Detall Tècnic d'Integració Asíncrona:** L'endpoint receptor (`POST /api/v1/gestio/magatzem/albara/ocr`) enxamparà la sol·licitud, encolarà la tasca a Celery i retornarà de forma immediata un HTTP 202 Accepted amb la càrrega útil `{"task_id": "<uuid>"}`. Mai blocarà el fil del servidor esperant la resposta de l'OCR de la IA.
    RF-09 (Event-driven): SI durant la recepció física es reporta material trencat, danyat o que no concorda amb el packing list, LLAVORS el backend blocarà l'entrada de les unitats afectades al stock de venda de l'empresa, redirigint el lot a un estat de "Cuarentena" i llançant una alerta immediata de no-conformitat a Secretaria.
    RF-10 (Event-driven): SI es detecta un defecte mecànic en un producte emmagatzemat a la nau, LLAVORS EL SISTEMA generarà el Volant de RMA de Proveïdor, reduirà de forma virtual l'estoc de l'Almacén Central i arxivarà el justificant digital sota la ruta local /docs/<empresa_id>/almacen/incidencies/.
    RF-11 (State-driven) — Materials en Dipòsit i Valoració: MIENTRAS el stock d'un producte estigui marcat com a "Material en Dipòsit" (consignació sota propietat del proveïdor), LLAVORS EL SISTEMA permetrà el seu consum operatiu normal per a obres, però el seu valor econòmic quedarà estrictament exclòs de la valoració anual total de l'inventari propietat de l'empresa (RF-46). SI s'executa la devolució de stock no utilitzat per finalització de contracte de dipòsit, EL SISTEMA reduirà l'estoc a 0 sense implicar despeses contables.
    RF-12 (Event-driven): SI el material en dipòsit pateix un sinistre, inundació o dany a la nau de l'empresa, LLAVORS EL SISTEMA processarà la baixa definitiva de les peces i obligarà a Secretaria a tramitar la Factura de Compra forçada pel deute amb el proveïdor, imputant el cost contra l'assegurança.

Bloque 3: Estructura Multimagatzem, Ubicació Dual i Dotació de Furgonetes

    RF-13 (Ubiquitous): EL SISTEMA processarà l'estoc de l'empresa dividit en tres nivells d'ubicació real: Almacén Central (nau física), Tallers Mòbils (vehicles de cuadrilla en ruta on l'estoc i herramientas queden sota custòdia del Cap de Colla) i Eines assignades nominalment a treballadors individuals sota RLS multi-tenant.
    RF-14 (Ubiquitous): EL SISTEMA mantindrà un llistat de "Dotació Base de Furgoneta" amb els elements consumibles i de seguretat indispensables per vehicle. Habilitarà un formulari interactiu a la PWA de l'operari per a una revisió ràpida setmanal per excepció, on el capataz registrarà únicament aquells equips o furgons que presentin faltants per a la seva recàrrega ràpida a base.
    RF-15 (Event-driven): SI un responsable de vehicle precisa recarregar materials fungibles durant la setmana, LLAVORS EL SISTEMA tramitarà de forma immediata la "Fulla de Reposició de Furgoneta", reduint el stock del magatzem central de la nau i transferint el volum al furgó de destí a la base de dades.
    RF-16 (State-driven): MIENTRAS un vehicle o maquinària especial estigui llogat temporalment (renting rústic d'obra), LLAVORS EL SISTEMA el tractarà operativament com un servei de subcontrata extern, vinculant de forma prèvia el seu control a la validació de la pòlissa RC de proveïdors (Spec 003) i excloent-lo del llistat d'actius fixos de la flota.

Bloque 4: Planificació Transaccional, Bloqueig pesimista i Fulla de Picking FEFO

    RF-17 (Event-driven) — Control de Concurrència i Bloqueig Pesimista en reserves: QUAN un enginyer o supervisor planifiqui o desi una obra en /gestio, EL SISTEMA executarà la reserva de stock sota el següent flux transaccional atòmic d'evitació de condicions de carrera:
        La interfície web utilitzarà el control de concurrencia optimista (version_id) per validar que ningú hagi alterat la fitxa de l'obra.
        En desar els canvis al servidor, EL SISTEMA obrirà una transacció de base de dades PostgreSQL real, executant de forma obligatòria la clàusula SELECT ... FOR UPDATE sobre les files de stock de les taules del magatzem corresponents a les unitats reservades.
        El backend comprovarà la disponibilitat física neta de materials. SI hi ha prou estoc, LLAVORS el sistema consolidarà el canvi en el COMMIT, alliberant de forma immediata el bloqueig de base de dades. SI l'estoc és insuficient degut a que una transacció concurrent prèvia el va exhaurir en el mateix mil·lisegon, LLAVORS el sistema executarà un ROLLBACK complet rebutjant la reserva virtual i llançarà l'error "Estoc insuficient per concurrència".
        SI la planificació es cancel·la posteriorment o es reprograma a un estat pendent, EL SISTEMA alliberarà virtualment les unitats tornant-les a la bossa de materials disponibles.
    RF-18 (Event-driven): SI s'intenta planificar una feina utilitzant material pendent de recepció, LLAVORS Copilot IA detectarà la comanda de compra de proveïdors en trànsit, mostrarà l'avís "Comanda amb entrega parcial: X unitats disponibles físiques, Y en trànsit pendent de comanda [Codi]" i bloquejarà el picking físic matinal fins que l'albarà no estigui signat a la nau.
    RF-19 (Ubiquitous) — Criteri FEFO per a Productes Caducables: EN productes subjectes a venciment tècnic o data de caducitat (químics, silicones, resines, pintures), la fulla de picking matinal del sistema obligarà de forma mandatoria i prioritària a recollir el lot de l'estoc amb la data de caducitat més propera (Criteri FEFO - First Expired, First Out), bloqueant la sortida dels lots nous fins a exhaurir els vells. Els materials caducats es transferiran automàticament al slot de Residus.
    RF-20 (Ubiquitous): EL SISTEMA articularà la logística de camp sota la regla procedimental d'associació unívoca: Una Tarea de l'Ordre de Treball = Una Fulla de Picking / Devolució de Sobrants, impedint l'acumulació desordenada de materials de talls o obres diferents en una sola fulla.
    RF-21 (State-driven): MIENTRAS una furgoneta i materials de picking estiguin vinculats a dues o més ordres de treball del mateix client en la mateixa jornada, LLAVORS EL SISTEMA mantindrà l'actiu del vehicle en estat Reservat d'obra fins al tancament de l'última tasca, sense aixecar alertes de conflicte de solapament.
    RF-22 (Ubiquitous) — Validació PWA de Picking en Camp: DENTRO de la interfície de la PWA del operari (/operari), la fulla de picking digital contindrà exclusivament tres accions:
        Retirada: Check interactiu dels materials retirats físicament del vehicle per iniciar la feina.
        Devolució de Sobrants: Camp de quantitats per introduir materials intactes que es retornen a furgoneta, incloent el check de retalls "Parcial" per a porcions de tubs o cables.
        Incidències: Camp de text lliure i foto per registrar mermes de materials danyats o eines trencades.
        - **Detall Tècnic de Cuarentena (Pick-out):** Qualsevol `quantitat_mermada` reportada al confirmar la devolució (Pick-out) es descomptarà de l'estoc net disponible i s'inserirà en un registre de Base de Dades amb estat de `CUARENTENA`, bloquejant totalment el seu ús futur en noves ordres de treball.
    RF-23 (Event-driven): QUAN el Cap de Colla prèn el botó "Validar Recollida" a la PWA matinal, EL SISTEMA de forma automàtica descontarà el stock de l'Almacén Central de la nau, bloquejarà de forma immutable els valors d'entrega de material i l'historial quedarà segellat. Qualsevol modificació posterior s'haurà de registrar com una Incidència de Picking de camp.
    RF-24 (Event-driven) — Sortides Blanques de Urgència: SI es produeix un incident crític a la xarxa que requereixi la sortida immediata del vehicle de retén sense una fulla de picking planificada (ex. rebentada de tubería principal), LLAVORS l'operari registrarà una "Salida Blanca de Urgència" a la PWA, obrint directament la fulla de consums de camp que descomptarà l'estoc físic en l'instant de marcar Stop, permetent a la oficina tècnica conciliar de forma humana les unitats utilitzades al tancament de la incidència.
    RF-25 (Event-driven) — Traspàs Offline de Recursos entre Furgonetes: QUAN dos capatassos decideixin transferir-se materials o eines a camp en una zona rústica sense cobertura GSM (zona blanca):
        Ambdós registraran el traspàs unívoc a les seves respectives PWAs mitjançant la selecció dels números de referència dels actius en IndexedDB.
        El capataz receptor assumirà de forma instantània la custòdia legal dels equips sota xifratge de la PWA, podent utilitzar-los en la seva feina d'avui.
        QUAN qualsevol dels dos dispositius mòbils recuperi la cobertura de xarxa celular, el Service Worker enviarà el payload de traspàs offline al servidor i el backend actualitzarà les directrius de custòdia de Flota i Magatzem de forma idempotent, llançant una alerta de conciliació "CONFLICTO_TRASPÀS" (EDGE-02) a Secretaria en cas de discrepància de serials o pesos.
    RF-26 (Event-driven) — Factures d'Anticipo, Cobraments i Reingrés: QUAN el client accepti un pressupost d'obra, el sistema obligarà a Secretaria/Administració a emetre la Factura d'Anticipo legal (Veri*factu) pel 100% o un mínim del 45% del valor dels materials d'inventari reservats. Al tancament de l'obra, els materials intactes retornats pel cap de colla a la PWA es reingressaran a l'estoc de la nau, i Secretaria ajustarà manualment el preu de tancament de la factura final del client.
    RF-27 (Ubiquitous): EL SISTEMA diferenciarà estrictamente el stock físic d'inventari dels circuits de facturació comercial: si el capataz retorna a base un retall de tub de 2 metres d'una barra sencera de 6 metres facturada íntegrament al client original, LLAVORS el sistema reingressarà el retall de 2 metres al catàleg de retalls de la nau, deixant inalterat el valor facturat al primer client per evitar mermes dobles.
    RF-28 (State-driven): SI una eina especial (ej. equip de termofusió) es retornada i validada favorablement per Secretaria sense report d'incidències al tancament de la jornada, LLAVORS EL SISTEMA alliberarà de forma automàtica la custòdia de l'operari, fent-la disponible de forma general per a noves assignacions.
    RF-29 (Event-driven): SI una eina es trenca o es detecta defectuosa a mig tajo a camp, LLAVORS el capataz podrà polsar el botó "Pausa per avaria" a la seva PWA mòbil, deturar el temporizador d'hores d'execució d'obra, reportar la incidència de l'eina (enllaçant la referència), acudir a la nau central a recollir un recanvi disponible i reanudar el cronòmetre de la faena sense falsejar les hores d'imputació de mà d'obra.
    RF-30 (Event-driven): SI un Cap de Colla pateix un accident o baixa sobrevinguda durant el tajo, LLAVORS el supervisor podrà activar des del Dashboard del mapa de la Spec 001 la "Incidència de Relleu de Responsable", transferint immediatament i de forma asíncrona la custòdia nominal de la furgoneta i materials a l'operari substitut que acudeixi de guàrdia.
    RF-31 (State-driven) — Alerta de Cuota d'Emmagatzematge en la PWA: SI la mida acumulada d'imatges d'albarans, fotos d'obres o incidències desades a l' IndexedDB de la PWA mòbil rural aproxima el 80% del límit de quota assignat pel navegador del mòbil, LLAVORS la PWA inhabilitarà temporalment la captura d'imatges de la càmera i emetrà l'alerta "Conecti a xarxa per buidar fotos locals", forçant a sincronitzar metadades de text lleugeres per protegir el sistema.

Bloque 5: Filtre d'Evitació de Duplicats per IA en Compres

    RF-32 (Ubiquitous): EL SISTEMA assignarà a cada comanda de reposició un codi visual unívoc compost sota el patró [Referència_Inquilin]+00#[Correlatiu] immutable.
    RF-33 (Event-driven): AL FINALITZAR el picking matinal de cada vehicle de l'empresa, l'assistent Copilot IA analitzarà en segon pla les rotures de stock o productes sota mínims. SI detecta que ja existeix una comanda en trànsit o un Backorder actiu amb el mateix proveïdor que cobreix la despesa de materials del mes, LLAVORS la IA deturarà la generació de comandes de compra redundants per evitar duplicació d'inventari, llançant una alerta de seguiment de la comanda en trànsit si supera els 7 dies d'espera.
    RF-34 (State-driven): EL SISTEMA permetrà el fraccionament i recepció d'un mateix pedido de compra mitjançant múltiples albarans parcials de proveïdors (backorders). El circuit contable del Three-Way Matching (Spec 003) conciliarà exclusivament els albarans físics registrats en camp contra les factures mensuals parcials de compra del proveïdor, mantenint actiu i pendent d'entrega el saldo restant de la comanda de compra matriu.

Bloque 6: Auditories d'Inventari General, Residus RAEE i ISP d'IVA (0€)

    RF-35 (Ubiquitous): EL SISTEMA disposarà d'un mòdul de control per a l'execució d' Inventaris Generals Periòdics, requerint que tota la plantilla d'operaris i administració realitzi el recompte físic sencer de materials de la nau central i furgonetes tallers.
    RF-36 (Event-driven): AL canviar el mòdul d'inventari general a estat actiu, EL SISTEMA paralitzarà de forma immediata tots els moviments ordinaris i transaccions de reserva de materials de la plataforma web, per evitar descuadres durant el recompte. Quedaran lliures d'aquest bloqueig exclusivament aquells productes llançats com a "Incidències de Nivel 1" (Urgències de canonades principals), els quals es desaran en una cua síncrona paral·lela que regularitzarà el stock físic automàticament al tancament de l'auditoria.
    RF-37 (Event-driven): EL SISTEMA permetrà la "Baixa Directa per Merma" d'aquells materials danyats o retalls inútils de camp, extraient de forma definitiva les unitats i transferint el producte al slot de residus o ferralla de l'empresa.
    RF-38 (Event-driven) — Gestió RAEE i Facturació de Chatarra amb Inversió de Subjecte Pasiu (ISP): EL SISTEMA organitzarà el catàleg de la bústia de residus segons les normes vigents, analitzant asíncronament els certificats NIMA i codis de residu LER mitjançant la IA. QUAN es realitzi la venda dels residus metàl·lics (chatarra de canonades PE o coure) a un gestor autoritzat de residus, el motor de facturació de comptabilitat (Spec 007) processarà l'operació sota el règim d' Inversió de Subjecte Pasiu (Art. 84.Uno.2n.c de la LIVA):
        Fixarà el tipus d'IVA de l'albarà de residus al 0,00% de forma automàtica.
        Generarà el document PDF amb el QR legal i la legenda tributària corresponent sense intervenció manual del de Secretaria.
        Validarà el CIF de l'empresa compradora mitjançant el VIES abans de segellar el RFA de Veri*factu.
    RF-39 (Event-driven): EL SISTEMA facultarà la sortida de materials de stock cap al taller intern per a "Banc de Ensayo Tècnic" (proves de canonades o bombes), imputant el preu de cost a despeses operatives generals de l'empresa sense necessitat d'inventar fitxes de clients fictícies (Zero Mock Data).
    RF-40 (Ubiquitous): EN consumibles menors del magatzem (envasos de silicona, caixes de tornilleria), EL SISTEMA només permetrà el seu reingrés a stock disponible si el capataz certifica a la PWA que l'envàs retorna completament precintat de fàbrica. Els envasos desprecintats o oberts a camp es consideraran consumits de forma atòmica i es mermaran al 100% com a cost a l'obra del client.
    RF-41 (Event-driven): QUAN l'ingrés d'un albarà de compra registri una variació de preu de cost de material respecte a l'històric:
        SI la variació supera els llindars i incompleix la "Clàusula de preu ferme" (Spec 003), LLAVORS el backend llançarà l'Alerta de No Conformitat, blocarà l'actualització del PMP i demanarà intervenció manual.
        SI el canvi és correcte i validat per Secretaria, LLAVORS el sistema actualitzarà el preu de referència de la fitxa per a nous pressupostos de venda amb marge, i de forma simultània recalcularà el nou Precio Medio Ponderado (PMP) de l'inventari per a les valoracions comptables, mantenint totalment inalterables i inmutables els pressupostos i obres ja facturades a clients en el passat en compliment del principi de seguretat jurídica.

Bloque 7: Ficha de Artículo, Bloqueo de Talleres y Baja Definitiva de Seriales

    RF-42 (Ubiquitous): La fitxa de cada article a la web de gestió mostrarà el número de referència, detalls tècnics, proveïdor històric, llistat de línies amb Número de Sèrie per a maquinària, existències desglossades multimagatzem (nau central vs furgoneta), botó de comanda ràpida i l'historial d'auditoria, omital del payload de l'Enginyer els preus de cost de compra.
    RF-43 (State-driven): MIENTRAS una eina de treball sigui marcada per Secretaria o el capataz com a "En Taller / Defectuosa", LLAVORS EL SISTEMA bloquejarà incondicionalment el seu llistat de selecció als desplegables, impedint de forma infranquejable que es pugui planificar o assignar en una fulla de picking matinal.
    RF-44 (Event-driven): SI una eina especial és catalogada com a irreparable o ha patit una sostracció física (robatori documentat):
        El Boss de l'empresa validarà la documentació d'auditoria i signarà la Baixa Definitiva de l'actiu.
        EL SISTEMA col·locarà de forma inalterable i perenne el seu Número de Sèrie (SN) a la llista de baixes de la base de dades, bloquejant de per vida qualsevol intent futur de donar d'alta una eina amb el mateix serial per evitar fraus o duplicacions de mermes.
    RF-45 (State-driven): MIENTRAS una eina especial tingui programada una data de calibració periòdica o revisió reglamentaria al calendari, LLAVORS EL SISTEMA inhabilitarà el seu Número de Sèrie als formularis de picking matinal exclusivament durant els dies agendats de revisió.

Bloque 8: Segregación Financiera, Facturación y Retornables

    RF-46 (Ubiquitous): MIENTRAS l'usuari connectat disposi del rol Boss o Secretaria, EL SISTEMA mostrarà la valoració total del stock de l'empresa en euros (€) basat en la sumatoria dels preus PMP de cada article actiu, excloent de forma absoluta el valor dels materials sota "Dipòsit de proveïdor" o equips llogats temporals.
    RF-47 (Ubiquitous): EL ROL Enginyer tindrà accés en el magatzem exclusivament a la disponibilitat física i als preus finals de venda de catàleg per a presupostació técnica. El backend blocarà amb HTTP 403 Forbidden qualsevol consulta des del seu rol cap a endpoints que retornin preus de cost d'adquisició de proveïdors o el balanç macroeconòmic d'inventari de la nau central.
    RF-48 (Event-driven): LA EMISIÓN de qualsevol factura oficial d'anticip o albarà de liquidació final de materials Veri*factu serà una acció restringida del sistema realitzada exclusivament per usuaris amb rol Boss o Secretaria, bloquejant-se al rol Enginyer.
    RF-49 (Event-driven): QUAN l'operari finalitzi la instal·lació d'un equip tècnic de valor en camp (inversor elèctric, caldera, bomba de pou), LLAVORS capturarà mitjançant la càmera de la PWA la fotografia de la placa de fàbrica. EL SISTEMA realitzarà el procés de reconeixement OCR i enllaçarà de forma inmutable el Número de Sèrie a la fulla final de l'obra, registrant la data exacte i matrícula del vehicle a l'expedient del client per a la gestió directa de legalitzacions i garanties de proveïdors.
    RF-50 (Unwanted behavior) — Eliminació física de catàleg actiu: EL SISTEMA denegarà de forma universal qualsevol sol·licitud d'eliminació física (DELETE) de línies de productes de la base de dades per preservar la traçabilitat històrica. CUANDO un material quedi obsolet, el sistema permetrà la seva baixa lògica (actiu = false) únicament si es valida que el seu stock és estrictament zero (0) a la nau central i a totes les furgonetes de la flota.
    RF-51 (State-driven) — Envases Retornables amb Fianza: MIENTRAS es rebi stock que contingui envasos o suports retornables (palets EPAL, bobines buides de cable amb fianza), LLAVORS EL SISTEMA registrarà el saldo de fiances pendents de cobrament. SI un operari trenca o malmet un palet a obra, el sistema realitzarà la baixa de fianza per pèrdua i imputarà de forma transparent el cost com a major despesa operativa contra el centre de cost de l'obra associat.
    RF-52 (Event-driven) — Custòdia Temporal de RMA de Clients: QUAN es rebi física de la nau central d'un equip de client danyat per a la gestió de la seva garantia davant del proveïdor (RMA de Clients), EL SISTEMA obrirà el Ticket de Reparació, registrarà el Número de Sèrie de fàbrica de l'actiu i el catalogarà com a "Material en Custòdia Temporal", inhabilitant de forma total la seva suma dins la valoració econòmica d'inventari propietat de l'empresa.

--------------------------------------------------------------------------------
Clàusules Canòniques de Casos Límit i Resiliència (EDGE-01 a EDGE-20)
Codi
	
Tipus EARS
	
Mòdul
	
Vector de Fallada / Escenari Límit
	
Comportament Requerit del Sistema
EDGE-01
	
Unwanted
	
Concurrència
	
Dos enginyers intenten reservar concurrentment la darrera unitat de stock per a dues obres diferents al mateix mil·lisegon.
	
PostgreSQL aplica SELECT FOR UPDATE dins la transacció ACID; el primer request s'enregistra correctament i exhaureix el stock, i el segon commit és rebutjat llançant excepció 400 Bad Request amb error "Estoc insuficient per concurrència".
EDGE-02
	
Event-driven
	
PWA Sync
	
Dues furgonetes offline a camp es traspassen eines per SN i a la sincronització els dispositius aporten quantitats asimètriques o serials erronis.
	
El backend de la nau detecta la discrepància estructural, congela el moviment d'actius i genera de forma automàtica la incidència lògica de "CONFLICTO_TRASPÀS" a la safata de Secretaria, requerint intervenció manual per corregir la custòdia.
EDGE-03
	
Unwanted
	
Picking
	
L'operari intenta escanejar o registrar la devolució d'una eina el número de sèrie de la qual no pertany a la llista de custòdia de la seva furgoneta.
	
La PWA mòbil bloca el marcatge de devolució al terminal de camp i emet l'avís "Herramienta ajena. Sol·liciti traspàs formal des del propietari actual", evitant barreges de recursos.
EDGE-04
	
Event-driven
	
RMA Client
	
El client refusa el pressupost de reparació de la IA d'un equip propi fora de garantia rebut a la nau de l'empresa per RMA temporal.
	
El sistema tanca el Ticket de Reparació del magatzem, emet l'ordre de devolució física del terminal al seu propietari i purga de forma de forma atòmica el registre del catàleg d'actius temporals.
EDGE-05
	
Unwanted
	
PWA Quota
	
El navegador mòbil d'un capataz offline bloqueja l'escriptura fotogràfica de la càmera a l' IndexedDB de la PWA degut a haver-se assolit la quota de seguretat del dispositiu.
	
El Service Worker de la PWA bloca les captures de la càmera de camp, prioritza l'escriptura immutable dels metadades de text del picking i llança l'alerta crítica "Falta de quota: Conecti a xarxa per buidar fotos locals".
EDGE-06
	
Event-driven
	
FEFO
	
La fulla de picking del sistema obliga a retirar un lot de resina o silicona caducable, però en acudir a la gaveta l'envàs físic presenta pèrdua de líquids o s'ha danyat.
	
El capataz marca la casella d'Incidència a la PWA mòbil indicant "Lote danyat in situ"; el sistema passa el lot afectat directament al slot de Residus i autoritza de forma immediata la recollida del següent lot FEFO de recanvi.
EDGE-07
	
Unwanted
	
Inventari
	
Secretaria intenta realitzar la Baixa Lógica (actiu = false) d'un producte obsolet, però el sistema detecta stock real actiu superior a 0 en una furgoneta de la flota.
	
El backend bloca la petició de soft-delete, responent amb l'alerta de validació "Impossible descatalogar: Existeixen N unitats actives al vehicle X".
EDGE-08
	
Unwanted
	
Picking
	
L'operari escaneja la devolució de sobrants indicant un retall d'un tub (p. ej. 2 metres) però en base de dades el comptador de retalls indica 0 unitats.
	
El sistema exigeix enregistrar la incidència expressa de magatzem a la PWA mòbil, llança un procés d'ajust i autoritza excepcionalment el tall de la barra sota un registre d'auditoria.
EDGE-09
	
Event-driven
	
Compras
	
Es rep a la nau un únic albarà multi-pedido de proveïdor que conté 5 unitats que pertanyen a la Comanda de Compra A i 5 unitats que resolen la Comanda de Compra B.
	
El motor de consolidació de stock de l'empresa processa el document, actualitza de forma asíncrona ambdues comandes vinculades a la base de dades i unifica el stock total disponible al magatzem de forma idempotent.
EDGE-10
	
Event-driven
	
Taller
	
L'eina de camp es danyat de forma imprevista; l'operari pausa el cronòmetre d'obra per retornar a la base, però en arribar a la nau central no hi ha exemplar disponible per al seu recanvi.
	
El sistema conmutarà l'estat de l'actiu danyat a "En Taller", i transformarà administrativament el cronòmetre d'obra aturat en un estat "Obra Paralizada - Causa de Fuerza Mayor", notificant a l'enginyer de guàrdia.
EDGE-11
	
Unwanted
	
Dipòsits
	
La empresa rescindeix el contracte de dipòsit de materials, però el recompte físic de mermes de consignació d'un producte és menor al stock esperat contablement pel proveïdor.
	
El sistema bloca el tancament de la devolució de consignació, obligant a Secretaria a tramitar la Factura de Compra de l'article faltant per pagar el deute comercial amb el proveïdor de forma prèvia a la baixa física.
EDGE-12
	
Event-driven
	
Planificació
	
Una ordre de treball que disposava de reserva transaccional física de stock es posposada o suspesa de forma indefinida pel client.
	
El backend de la plataforma allibera de forma immediata els materials bloquejats a la base de dades, retornant el stock a la bossa de materials comuns per a noves obres.
EDGE-13
	
Unwanted
	
Herramientas
	
Es planifica l'ús d'una eina especial per a una obra d'avui, però el seu Número de Sèrie té agendada una calibració tècnica o manteniment reglamentari per a avui.
	
L'algorisme de picking matinal detecta el conflicte de data, remou visualment l'eina del llistat de selecció i impedeix l'assignació al capataz per prevalència de manteniment.
EDGE-14
	
Event-driven
	
Residus
	
Es realitza la venda d'un lot de ferralla PE/coure del slot de Residuos de l'empresa a un gestor internacional que no aporta un CIF-IVA europeu vàlid sota el VIES per a l'Inversió de Subjecte Pasivo.
	
El motor de facturació Veri*factu de CampoPro bloca de forma atòmica la generació del PDF i del fitxer de facturació XML, obligant a reingressar l'IVA repercutit de l'operació davant de la AEAT.
EDGE-15
	
Unwanted
	
Preus
	
L'OCR de l'albarà comet un error d'ingesta digital i llegeix un preu unitari de compra de material d'una unió de PE un 300% superior al històric (ex. 150€ en lloc de 1,50€).
	
El motor d'alertes de compres del backend detecta la desviació estadística (més de 3 desviacions estàndard del z-score), bloca l'actualització de preu de referència i de PMP i aixeca l'alerta d'auditoria.
EDGE-16
	
Unwanted
	
Fianza
	
El proveïdor de la nau de l'empresa rebutja la devolució d'una bobina de fons buida de cable al·legant danys estructurals de l'operari, negant-se a retornar l'import de fianza registrat.
	
Secretaria executa la incidència de "Pérdida de Fianza de Envàs Retornable"; el cost de la fianza perduda es liquida contablement imputant-se com a major despesa de la nau central.
EDGE-17
	
Unwanted
	
Seguretat
	
Un usuari amb rol Operari o Enginyer intenta invocar mitjançant POSTman un endpoint del magatzem per consultar els preus d'adquisició o els costos de compra agregats de materials.
	
El PostgreSQL interposa de forma immediata la política de Row Level Security (FORCE ROW LEVEL SECURITY sota app.current_empresa_id) i l'endpoint del backend de seguretat de rols retorna un error 403 Forbidden bloquejant l'accés.
EDGE-18
	
Unwanted
	
Facturació
	
Secretaria intenta comptabilitzar una factura d'anticip de materials per un valor inferior al mínim del 45% exigit pels controls administratius.
	
El sistema bloca el commit i genera una alerta d'excepció administrativa, la qual només es desbloquejarà sota la signatura digital d'aprovació del Boss de l'empresa.
EDGE-19
	
Event-driven
	
Urgència
	
Es rep una incidència urgent de fuita d'aigua (Nivel 1) i el furgó retén surt de la base sense poder registrar la comanda de picking ordinària.
	
La PWA mòbil en camp registra el treball sota el mode "Salida Blanca de Urgència", descompta de forma local l'estoc consumit del vehicle i forçarà de forma idempotent la conciliació del stock central en tancar la tasca.
EDGE-20
	
Event-driven
	
Consumibles
	
El cap de colla retorna un envàs de silicona o cola començat a la meitat, juntament amb 2 envasos completament tancats de fàbrica.
	
El sistema reingresa els dos envasos tancats sumant +2 al stock disponible de la nau, i mermará de forma atòmica l'envàs començat al 100% com a cost a l'obra del client original.
--------------------------------------------------------------------------------
Requisits No Funcionals (RNF)

    Almacenamiento Local Seguro Multi-Tenant (Soberano): Tots els albarans, documents ambientals NIMA, fitxers de mermes, certificats de destrucció de bateries d'eines i expedients PDF es guarden de forma xifrada en repòs mitjançant el xifrat AES-256-GCM en el servidor sobirà Hetzner a Alemanya sota /docs/<empresa_id>/almacen/..., descartant completament AWS S3 per a estricte compliment del RGPD.
    Seguridad Multi-Tenant (RLS): Cada consulta, actualització o modificació aplicada sobre les taules d'inventari, mermes i moviments de stock es realitzarà sota el Row Level Security (RLS) mandatori a nivell de PostgreSQL mitjançant la variable d'inquilí app.current_empresa_id de forma universal.
    Protección de Datos Macroeconómicos (Zero-Trust): El quadre macroeconòmic global, els albaranes de compra de proveïdors i la valoració econòmica d'inventari agregat s'ofuscaran a la API per al rol Enginyer, la qual respondrà amb error 403 Forbidden a les seves sol·licituds, visualitzant només preus finals de venda de catàleg per a presupostació tècnica.
    Tolerancia Cero a Mock Data (Zero-Mock): Si no hi ha materials, la interfície tabular es renderitzarà de forma 100% buida (Empty State), mostrant els botons reals d'acció de forma inalterable sense cap tipus de registre simulat d'inventari.
    Rendimiento y Escalabilidad: El llistat i filtre del magatzem respondrà asíncronament en Next.js en un temps d'execució inferior a 200 ms, processant les fotografies mitjançant Celery + Redis per evitar bloquejar el event loop de FastAPI.

--------------------------------------------------------------------------------
Fora d'Abast (Out of Scope)

    No gestiona els terminis de manteniment, ITV o assegurances de la flota mòbil (es governa a la Spec 006 de Flota).
    No realitza la contractació ni el pagament a subcontrates o maquinària de lloguer exterior (pertany a la Spec 003 de Proveïdors).
    No s'admet la importació masiva de catàlegs de preus teòrics per CSV de proveïdors; el catàleg s'actualitza i es popula exclusivament mitjançant entrades reals d'albarans.
    No realitza la presentació telemàtica de l'IVA o mermes de ferralla directament a l'Agència Tributària, encarregant-se de generar els fitxers d'exportació XML PGC per a la gestoria contable externa de la Spec 007.

--------------------------------------------------------------------------------
Criteris de Finalització (Definition of Done) i Matriu de Traçabilitat

    Els 52 Requisits Funcionals (RF-01 al RF-52) i els 20 Casos Límit (EDGE-01 al EDGE-20) redactats amb sintaxi formal EARS estricta i sense errors, constituint el contracte de desenvolupament de CampoPro.
    Correspondència del 100% de la spec d'inventari amb una suite de proves d'integració automatitzada en verd, lliure de dades hardcodejades o simulades i amb PostgreSQL RLS actiu sota el tenant real.
    Alineació total de la política de QR: exclusió absoluta de codis QR per a les eines de camp (les quals es custodien i es traspassen per referència de fàbrica/SN), preservant el QR legal obligatori d'alta Veri*factu per a albarans i factures.
    Implementació del bloqueig pesimista de stock mitjançant la transacció SQL SELECT FOR UPDATE per garantir la consistència relacional davant planificacions d'obres concurrents.
    Tractament analític dels consums continuats: diferenciació nítida entre bobines/barres senceres i retalls, obligant al operari a exhaurir abans el stock parcial de camp sota PWA IndexedDB mòbil.
    Baixes per sinistre amb inhabilitació de sèrie permanent d'eines a la base de dades, evitant fraus.
    Segregació RLS Zero-Trust de rols: veto complet de l'Enginyer tècnic a preus de cost, albarans de compra o balanços contables agregats de magatzem.

Matriu de Traçabilitat 1:1 de la Definition of Done (DoD)
Codi RF / Spec
	
Cas Límit Vinculat
	
Assert / Criteri de Validació DoD (Zero-Mock)
RF-01 / RF-02
	
EDGE-17
	
Server-Side Pagination LIMIT/OFFSET actiu. Test de intrusió RLS retorna [] a inquilins diferents.
RF-03 / RF-04
	
-
	
BD buida d'articles mostra Empty State funcional net de mocks.
RF-05 / RF-06
	
EDGE-08
	
Inserció de devolució de stock parcial fragmenta la unitat i calcula PMP, obligant FEFO.
RF-07 / RF-08
	
EDGE-09 / EDGE-15
	
Ingesta asíncrona OCR de albarans multi-pedido resol múltiples línies de comandes diferents.
RF-09 / RF-10
	
-
	
Materials trencats enviats a quarantena; es bloca la seva assignació a obres.
RF-11 / RF-12
	
EDGE-11
	
Materials en dipòsit exclosos de la valoració total contable de stock propi.
RF-13 / RF-14
	
-
	
Reposició de dotació base per excepció setmanal recalcula exclusivament diferències.
RF-15 / RF-16
	
-
	
Lloguer de maquinària temporal hereda validació de pòlissa RC de Spec 003.
RF-17
	
EDGE-01 / EDGE-12
	
PostgreSQL SELECT FOR UPDATE assegura exclusivitat concurrent; cancel·lació allibera estoc virtual.
RF-18 / RF-19
	
EDGE-06
	
Hoja de Picking matinal assigna prioritàriament lot amb caducitat menor (FEFO); mermes enviades a residus.
RF-20 / RF-21
	
-
	
Assignació de múltiples fulles d'obra al mateix vehicle d'avui es gestiona de forma adjacent.
RF-22 / RF-23
	
EDGE-03
	
Escaneig de SN d'eina ajena bloca petició a la PWA de camp i exigeix trasllat formal de custòdia.
RF-24 / RF-25
	
EDGE-02 / EDGE-19
	
Sincronització de traspassos offline asimètrics llança excepció CONFLICTO_TRASPÀS per a Secretaria.
RF-26 / RF-27
	
EDGE-18
	
Factura d'anticip de materials per <45% requereix validació administratia i firma del Boss.
RF-28 / RF-29
	
EDGE-10
	
Pausa PWA de tajo per avaria atura temporitzador i envia eina a estat Taller a la nau.
RF-30 / RF-31
	
EDGE-05
	
StorageManager API de PWA rural detecta >80% de quota i deshabilita de forma local el botó de càmera.
RF-32 / RF-33
	
-
	
Inferencia IA en segon pla detecta comanda en trànsit vigent i bloca ordre de compra duplicada.
RF-34
	
EDGE-20
	
Entrada de unitats inferiors d'albarà parcial genera Backorder mantinguent vivo el saldo.
RF-35 / RF-36
	
EDGE-19
	
Activació de mòdul d'inventari general atura reserves; cua paral·lela habilitada per a mermes de Nivel 1.
RF-37 / RF-38
	
EDGE-14
	
Venda de ferralla a gestor sense VIES vàlid bloca de forma atòmica la Inversió de Subjecte Pasiu (IVA 0€).
RF-39 / RF-40
	
EDGE-20
	
Materials precintats retornats sumen stock disponible; silicones començades es comptabilitzen com a cost.
RF-41
	
EDGE-15
	
Desviació de preus (z-score) en nou albarà de proveïdor bloca actualització de PMP i aixeca alerta.
RF-42
	
EDGE-17
	
Detall de fitxa d'article aïlla dades i omiteix preus de cost al rol Enginyer sota RLS.
RF-43 / RF-44
	
-
	
Baixa definitiva de maquinària irremeiable per Boss afegeix SN a llista negra immutadora.
RF-45 / RF-46
	
EDGE-13
	
Eines agendades per calibració en la data actual no es renderitzen als selectors matinals.
RF-47 / RF-48
	
EDGE-17
	
Crida HTTP directe d'Enginyer a endpoints de balanç o costos agregats retorna HTTP 403.
RF-49 / RF-50
	
EDGE-07
	
Baixa lògica d'article de catàleg denegat si el stock físic o en trànsit és > 0.
RF-51 / RF-52
	
EDGE-04 / EDGE-16
	
Fiança de palet Epal danyat es liquida com a despesa de la nau; RMA de client rebutjat es purga.