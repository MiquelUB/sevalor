Spec 010 — Mòdul de Plànols, Xarxes Tècniques i Arquitectura de Capes (/gestio/planols)
AVÍS D'ALINEACIÓ CONSTITUCIONAL I INTEGRACIÓ ARQUITECTÒNICA: Aquesta especificació tècnica es regeix pels principis fonamentals de la Constitució de CampoPro Suite (v4.0) i s'integra de forma transversal amb la Torre de Control Geogràfica en temps real (Spec 001 i Spec 005), el Mòdul de Clients (Spec 002), el Mòdul de Proveïdors (Spec 003), el Mòdul de Magatzem (Spec 004), el Mòdul de Flota (Spec 006), el Mòdul d'Operaris (Spec 008), el Mòdul de Notificacions (Spec 009) i el Mòdul Contable (Spec 007).
De conformitat amb la Constitució i el criteri de QA unificat, es fa l'exclusió absoluta de codis QR per a la traçabilitat i transferència d'eines de camp (les quals es gestionen i custodien estrictament mitjançant el número de referència, marca, model i número de sèrie de fabricant sota la Spec 004 / Spec 008). Aquesta exclusió tècnica convive en perfecta harmonia amb la permanència del codi QR legal i tributari requerit obligatòriament a totes les factures i albarans de lliurament oficials (Veri*factu) emesos des del mòdul comptable.
Es prohibeix taxativament l'ús de dades simulades o de prova (Zero Mock Data), partint d'un estat de "Dia 0" real i garantint de forma absoluta la sobirania de dades mitjançant l'emmagatzematge local/sobirà dels fitxers vectorials CAD, raster PDF/TIFF i registres d'incidències en el servidor Hetzner de Falkenstein (Alemanya - UE), rebutjant completament qualsevol servei de núvol públic extern (com AWS S3) d'acord amb el compliment estricte de la LOPDGDD i el RGPD.
--------------------------------------------------------------------------------
Context i Objectiu
El mòdul de Plànols, Xarxes Tècniques i Arquitectura de Capes (/gestio/planols) és el Visor Tècnic Cartogràfic, Biblioteca de Projectes i Registre Pericial d'Instal·lacions de CampoPro Suite. Centralitza la custòdia, consulta, edició gràfica i gestió documental de la infraestructura física (canonades de reg, xarxes de baixa tensió, rases, instal·lacions hidràuliques i edificacions) intervinguda per les empreses de serveis tècnics sobre el terreny.
Aquest mòdul no pretén ser un modelador BIM 3D ni un programari d'animació complex, sinó una eina àgil d'enginyeria cartogràfica i d'obra 2D que:

    Estructura una Biblioteca Documental basada en Carpetes Editables: organitzada de forma personalitzable per Clients (amb assignació obligatòria de client_id sota RLS), Projectes Generals / Infraestructures Comunitàries (comunitats de regants, xarxes de polígons) i Municipis/Zones geogràfiques.
    Admet una Matriu Híbrida de Formats Tècnics:
        Fitxers vectorials CAD/GIS amb suport de georeferenciació nativa (DXF, GeoJSON, KML): projectats automàticament sobre la cartografía satel·litària (PNOA / OpenStreetMap). Els fitxers DXF es processen de forma asíncrona al backend per a convertir-se a SVG/GeoJSON optimitzats, evitant sobrecarregar el client.
        Documents tècnics i esquemes sense projecció geogràfica obligatòria (PDF, TIFF, PNG, JPG): visualitzats en un visor de Next.js d'alta resolució independent del mapa, per a esquemes unifilars, quadres elèctrics o croquis d'obra.
    Implanta una Arquitectura Estricta basada en Capes Superposades:
        Elimina la sobreescriptura destructiva d'arxius: cada revisió, modificació tècnica o incidència és una capa vectorial superposada al plànol base original.
        Cada capa està unívocament referenciada a una Ordre de Treball / Fulla de Tasca o a una edició manual d'un Enginyer.
        Permet el control independent de visibilitat i opacitat (0% a 100%) mitjançant el discriminador de capes del mapa.
    Equipa l'Enginyer Tècnic amb Eines de Marcatge Normalitzat:
        Dibuix d'elements geomètrics 2D: polilínies (canonades, rases, cables), polígons i rectangles de sectorització.
        Anotacions de text tècnic i cotes (ex. "PE Ø63 PN10", "fondària 80cm"), ancorades inalterablement al traçat.
        Inserció de punts d'interès amb simbologia tècnica normalitzada: vàlvules de pas, hidrants, arquetes, comptadors, bombes d'impulsió, quadres elèctrics i transformadors.
    Integra la Comprovació Pericial de Camp (PWA /operari/planols):
        Permet al Cap de Colla o operari situar sobre el terreny un PIN d'Incidència georeferenciat sobre la capa de la seva fulla de tasca assigned.
        Associa directament al PIN del plànol fotografies d'evidència, notes de veu de camp compressos en format WebM/WebP per a estalvi de bateria i dades, i descripcions de text de la realitat trobada a camp.
    Garanteix la Immutabilitat i Traçabilitat de Capes Tancades:
        Tota capa generada arran d'una incidència o d'una ordre de treball tancada i facturada (Spec 007) queda bloquejada com a immutable (només lectura), conservant la integritat pericial de la intervenció física.
    Facilita l'Exportació Tècnica Personalitzada en PDF:
        En confeccionar el Report Final de Feina per al client o l'administració, l'Enginyer pot triar exactament quines capes i plànols incloure a l'informe d'entrega generat en PDF d'alta resolució, incloent-hi un caixetí de precisió industrial homologat amb escala de contrast, llegenda, dades fiscals, client i data d'emissió.
    Garanteix el Suport Offline-First a Camp:
        La PWA descarrega preventivament el fitxer vectorial i les capes assignades a la tasca per a la seva consulta i marcatge in situ sense cobertura mòbil mitjançant IndexedDB xifrat.

--------------------------------------------------------------------------------
Usuaris / Actors i Matriu d'Accés (Zero-Trust)
El backend aïlla les dades mitjançant Row Level Security (RLS) mandatori a la taula planols (empresa_id) i una segregació estricta de privilegis (Separation of Duties):

    Boss (Gerència / Propietari): Accés total a tota la biblioteca de plànols. Pot crear, editar, reassignar i suprimir carpetes, plànols base i capes; consultar capes immutables d'auditoria; autoritzar l'exportació oficial de dossiers tècnics; i accedir a plànols restringits d'alta seguretat.
    Enginyer / Supervisor Tècnic: Editor tècnic principal del mòdul web (/gestio/planols). Pot estructurar carpetes, pujar nous plànols base (DXF, GeoJSON, KML, PDF, TIFF), georeferenciar fitxers, dibuixar noves capes amb eines vectorials i simbologia normalitzada, adjuntar capes específiques a les fulles de tasca dels operaris, revisar pins d'incidència reportats des del camp i editar la composició de capes per a l'exportació del PDF final.
    Secretaria / Administració: Permisos de consulta i descàrrega documental. Pot visualitzar la biblioteca per carpetes, descarregar els PDFs tècnics per adjuntar-los a factures o pressupostos, i consultar la fitxa de plànols des de /gestio/clients/{id}. Té bloquejada l'edició gràfica de vectors o supressió de capes.
    Cap de Colla / Operari (/operari/planols): Consulta a través de la PWA mòbil el plànol base i les capes expressament adjuntades per l'Enginyer a la seva ordre de treball. Disposa de permisos per crear Pins d'Incidència georeferenciats sobre la capa de la seva tasca, adjuntant fotografies de camp, notes de veu i text per documentar l'estat real de la rasa o instal·lació. No pot editar ni esborrar capes de l'Enginyer.
    Client Final: Receptor dels plànols i reports tècnics resultants en format PDF d'alta resolució a través de correu electrònic o enllaç segur de Telegram. No té accés d'edició ni consulta directa a la biblioteca web de plànols de l'empresa.

Matriu de Permisos per Rol
Àmbit Funcional
	
Boss
	
Enginyer Tècnic
	
Secretaria
	
Cap de Colla (PWA)
	
Operari PWA
Creació / Edició de Carpetes
	
Total
	
Total
	
Denegat (403)
	
Denegat
	
Denegat
Càrrega de Plànols Base (DXF, PDF, GIS)
	
Total
	
Total
	
Denegat (403)
	
Denegat
	
Denegat
Dibuix i Edició de Capes Vectorials (Web)
	
Total
	
Total
	
Denegat (403)
	
Denegat
	
Denegat
Simbologia Tècnica Normalitzada
	
Total
	
Total
	
Denegat (403)
	
Denegat
	
Denegat
Assignació de Capes a Fulla de Tasca
	
Total
	
Total
	
Denegat (403)
	
Denegat
	
Denegat
Creació de Pins d'Incidència (Geofotos)
	
Total
	
Total
	
Denegat (403)
	
Escriptura (PWA)
	
Lectura (PWA)
Consulta de Plànols Offline (PWA)
	
Sense accés web
	
Sense accés web
	
Sense accés web
	
Lectura / Zoom
	
Lectura / Zoom
Modificació de Capes de Tasques Tancades
	
Denegat (Immutable)
	
Denegat (Immutable)
	
Denegat (Immutable)
	
Denegat (Immutable)
	
Denegat (Immutable)
Exportació de Report Tècnic en PDF
	
Total
	
Configuració / Exporta
	
Descàrrega PDF
	
Denegat
	
Denegat
Supressió de Plànols Base o Carpetes
	
Total
	
Autor / Sense dependència
	
Denegat (403)
	
Denegat
	
Denegat
--------------------------------------------------------------------------------
Requisits Funcionals (Notació EARS Estricta)
Bloque 1: Estructura de la Biblioteca i Organització per Carpetes

    RF-01 (Ubiquitous): EL SISTEMA renderitzarà a /gestio/planols una biblioteca documental jeràrquica basada en un sistema de carpetes editables, organitzades en tres categories principals: Carpetes de Clients (vinculades de forma obligatòria a un client_id sota RLS de base de dades), Carpetes Generals d'Infraestructures Comunitàries, i Carpetes Municipals o Territorials.
    RF-02 (Event-driven): QUAN un usuari amb rol Enginyer o Boss creï, reanomeni o mogui una carpeta a la biblioteca, EL SISTEMA actualitzarà l'arbre de navegació en temps real, validant de forma asíncrona la unicitat de noms i registrant un log immutable de l'autor de la modificació.
    RF-03 (Ubiquitous): EL SISTEMA mantindrà un cercador en temps real al panell lateral de la biblioteca que permetrà filtrar instantàniament carpetes i plànols per: nom del fitxer, codi de client, municipi, tipus d'instal·lació, o codi de tasca activa.
    RF-04 (State-driven): SI la base de dades del tenant es troba buida sense cap plànol ni carpeta registrats (Estat Dia 0 real), ENTONCES EL SISTEMA renderitzarà la interfície completament buida mostrant l'Empty State real i oferint els botons primaris d'acció sense inserir dades simulades o de prova d'inventari (Zero Mock Data).

Bloque 2: Gestió de Formats Tècnics i Georeferenciació

    RF-05 (Event-driven): QUAN l'Enginyer pugi un fitxer a la biblioteca, EL SISTEMA de forma asíncrona comprovarà que l'extensió coincideixi amb la tipologia de fitxer (Magic Bytes reals) i que la mida no superi el límit rígid de 50 MB, rebutjant-lo amb excepció HTTP 415 (Unsupported Media Type) o HTTP 413 (Payload Too Large) si es vulneren aquests paràmetres de seguretat.
    RF-06 (State-driven): SI es carrega un fitxer vectorial georeferenciat (GeoJSON o KML), ENTONCES EL SISTEMA projectarà de forma automàtica la xarxa vectorial sobre la capa cartogràfica activa calculant la capsa delimitadora (bounds_json) i desant les coordenades decimals en format WGS84.
    RF-07 (State-driven): SI el fitxer carregat és un plànol, tall de rasa o esquema no georeferenciat (PDF, TIFF, PNG, JPG), ENTONCES EL SISTEMA obrirà el fitxer en un visor documental independent de Next.js d'alta resolució que permeti zoom i desplaçament sense forçar la superposició sobre el mapa cartogràfic.
    RF-08 (Ubiquitous): EL VISOR inclourà un control flotant d'opacitat (0% a 100%) que permetrà ajustar la transparència del plànol base sobre les ortofotos satel·litàries del PNOA per verificar la alineació tècnica en camp.

Bloque 3: Arquitectura de Capes i Governança

    RF-09 (Ubiquitous): EL SISTEMA estructurarà qualsevol edició gràfica, incidència o anotació mitjançant capes vectorials superposades, bloquejant de forma innegociable la sobreescriptura destructiva sobre els fitxers de plànol base originals per preservar l'estat inicial del projecte.
    RF-10 (Event-driven): QUAN un Enginyer o Boss creï una nova capa a /gestio/planols, EL SISTEMA obligarà a introduir un nom identificatiu, tipus de disciplina tècnica (Aigua, Electricitat, Obra), data de creació i la vinculació opcional a una Ordre de Treball activa.
    RF-11 (Ubiquitous): EL SISTEMA renderitzarà un selector de capes flotant que permetrà commutar de forma independent la visibilitat i l'ordre de superposició de cadascuna de les capes actives sobre el mapa.
    RF-12 (State-driven): MIENTRAS una capa estigui vinculada a una Ordre de Treball o incidència tècnica que hagi estat tancada i facturada (Spec 007), EL SISTEMA bloquejarà la capa com a immutable (només lectura), impedint qualsevol edició o commit posterior a base de dades.
    RF-13 (Unwanted): SI un usuari intenta editar, redibuixar o eliminar una capa marcada com a immutable, ENTONCES EL SISTEMA denegarà l'operació llançant l'avís de seguretat de dades closes sota RLS i impedint qualsevol commit físic a PostgreSQL.

Bloque 4: Eines d'Edició Vectorial i Simbologia Normalitzada

    RF-14 (Event-driven): QUAN l'Enginyer editi una capa vectorial activa, EL SISTEMA habilitarà eines de dibuix geomètric 2D per a la inserció de polilínies (canonades o rases) i polígons de sectorització, permetent ajustar de forma dinàmica l'estil, color i gruix de la traça.
    RF-15 (Event-driven): QUAN es situï una cota dimensional o anotació de text sobre un traçat, EL SISTEMA ancorarà l'etiqueta de text tècnic al vector corresponent de forma inalterable.
    RF-16 (Ubiquitous): EL SISTEMA integrará una biblioteca de punts d'interès amb simbologia tècnica normalitzada per a hidràulica (vàlvules, hidrants, ventoses, comptadors, bombes d'impulsió), electricitat (quadres de comandament, comptadors, piquetes de terra, caixes de connexió, transformadors) i obra civil (arquetes, pous de registre) per a la seva ràpida col·locació a les capes de plànols.
    RF-17 (Event-driven): QUAN l'usuari faci clic sobre qualsevol símbol o traçat d'una capa activa, EL SISTEMA desplegarà la targeta de propietats tècniques per consultar i editar el diàmetre, material, fabricant, data d'instal·lació i estat.

Bloque 5: Comprovació de Camp i Pins d'Incidència (PWA)

    RF-18 (Event-driven): QUAN l'Enginyer assigni una ordre de treball a una cuadrilla, EL SISTEMA permetrà assignar de forma explícita les capes i plànols de referència a la fulla de tasca dels operaris, mostrant-los de forma read-only en el seu Kanban si la capa és immutable.
    RF-19 (State-driven): MIENTRAS el Cap de Colla operi a la PWA offline sense cobertura mòbil, EL SISTEMA utilitzarà la còpia vectorial dels plànols i capes descarregats preventivament a la memòria IndexedDB, habilitant zoom, desplaçament i col·locació de marcadors localment sota xifrat AES-GCM.
    RF-20 (Event-driven): QUAN el Cap de Colla detecti una discrepància o avaria sobre el terreny, EL SISTEMA permetrà col·locar un PIN d'Incidència georeferenciat sobre la capa de la seva ordre de treball a la PWA.
    RF-21 (Ubiquitous): EL SISTEMA permetrà adjuntar directament al PIN d'Incidència de camp: notes d'àudio comprimides en WebM de forma nativa per a estalvi d'emmagatzematge, fotografies de camp georeferenciades WebP i comentaris de text descriptius.
    RF-22 (Event-driven): QUAN el dispositiu mòbil recuperi la cobertura cellular, EL SISTEMA sincronitzarà asíncronament els pins d'incidència locals de l'IndexedDB amb el backend central de Next.js/FastAPI, projectant els nous elements a /gestio/planols i a la Torre de Control (Spec 001).

Bloque 6: Exportació Tècnica i Report Final de Tasca

    RF-23 (Event-driven): QUAN l'Enginyer demani generar el Dossier Tècnic d'Exportació, EL SISTEMA compilarà de forma asíncrona (Celery + Redis) un document PDF d'alta resolució fusionant el plànol base amb les capes de detall seleccionades.
    RF-24 (Event-driven): QUAN es configuri el formulari d'exportació, EL SISTEMA permetrà seleccionar o deseleccionar mitjançant caselles quines capes vectorials d'incidències resoltes o de treball intern queden excloses del report final per al client.
    RF-25 (Ubiquitous): EL SISTEMA imprimirà a la base del PDF d'exportació un caixetí de precisió industrial homologat que conté el logotip de l'empresa, dades del client, escala gràfica de contrast, data d'emissió, llegenda de símbols utilitzats, autor de l'enginyeria i data d'emissió, estant completament lliure de codis QR corporatius per a eines.
    RF-26 (Event-driven): QUAN l'Enginyer sol·liciti l'exportació nativa CAD/GIS de les capes, EL SISTEMA convertirà les geometries vectorials de la base de dades a fitxers estàndard DXF o GeoJSON per a la seva descàrrega directa.

--------------------------------------------------------------------------------
Taula de Casos Límit i Gestió d'Errors
Codi
	
Tipus EARS
	
Mòdul
	
Vector de Fallada / Escenari d'Estrès
	
Comportament Requerit del Sistema
EDGE-01
	
Unwanted
	
Concurrència
	
Dos enginyers intenten dibuixar o desar canvis sobre la mateixa capa de plànol al mateix mil·lisegon.
	
EL SISTEMA aplica control de concorrència optimista (version_id de la capa) i bloqueig pesimista (SELECT FOR UPDATE). El primer commit consolida; el segon es rebutja llançant error HTTP 409 Conflict amb avís d'actualització simultània.
EDGE-02
	
Unwanted
	
Seguretat
	
Usuari intenta forçar la càrrega d'un fitxer maliciós camuflat d'extensió falsa (ex. .exe canviat a .pdf).
	
El backend analitza els Magic Bytes (filetype) i la capçalera de l'arxiu, detecta la inconsistència, cancel·la la transferència a disc de Hetzner de forma atòmica i retorna excepció HTTP 415 Unsupported Media Type.
EDGE-03
	
Unwanted
	
PWA Quota
	
El buffer de fotografies de camp emmagatzemades offline a l'IndexedDB assoleix el límit de quota del navegador.
	
El Service Worker de la PWA bloca les captures de la càmera, prioritza l'escriptura dels metadades de text del plànol i dels vectors, i emet l'alerta crítica de canvi d'estat: "Falta de quota: Conecti a xarxa per buidar fotos locals".
EDGE-04
	
Event-driven
	
GIS
	
Es puja un fitxer vectorial GeoJSON o KML que conté una projecció rústica local no-WGS84 (ex. ED50).
	
El parser de backend intercepta la projecció local, utilitza la biblioteca pyproj per a reprojectar de forma automàtica totes les geometries a WGS84 decimals, i projecta de forma neta la xarxa sobre el mapa.
EDGE-05
	
State-driven
	
Custòdia
	
Un usuari intenta editar o esborrar un traçat d'una capa que pertany a una obra tancada i facturada fa mesos.
	
El sistema manté la capa en format de només lectura, bloca l'edició gràfica i llança l'avís: "Capa bloquejada per traçabilitat pericial d'obra tancada". Si cal un ajust posterior, l'Enginyer ha de superposar una nova capa vinculada a una nova tasca.
EDGE-06
	
Event-driven
	
PWA Sync
	
Dos operaris de camp situen de forma simultània un PIN d'incidència sobre el mateix punt de reg mentre treballen offline.
	
Al sincronitzar, el backend unifica ambdues aportacions a la base de dades mantenint ambdós marcadors de forma independent amb segell de temps i operari identificats, per a la validació de l'Enginyer a la Torre de Control.
EDGE-07
	
State-driven
	
Clients
	
Es produeix la baixa lògica (actiu = false) d'un client que té una biblioteca de plànols i projectes activa.
	
EL SISTEMA oculta les seves carpetes personals del navegador de plànols general, bloqueja noves assignacions de capes, però preserva el seu historial de plànols i capes immutables sota RLS per a possibles auditories judicials de l'empresa.
EDGE-08
	
Event-driven
	
CAD
	
Es puja un fitxer CAD DXF que no disposa de coordenades georeferenciades reals en el seu disseny.
	
EL SISTEMA detecta l'absència de georeferenciació i obre el plànol base en format no-georeferenciat al visor, habilitant un formulari on l'Enginyer pot fixar 3 punts de control sobre el mapa per aplicar la translació geomètrica.
EDGE-09
	
Unwanted
	
Celery
	
El worker asíncron de Celery falla o es penja a mig processar l'exportació d'un PDF d'alta resolució.
	
El gestor de cues detecta la fallida del procés, realitza el rollback de la transacció a la bústia de descàrregues, commuta el fitxer a estat FALLIDA i notifica de forma no bloquejant a l'oficina tècnica per al reintent.
EDGE-10
	
Event-driven
	
Rendiment
	
Es puja un fitxer GeoJSON molt dens que conté més de 100.000 vèrtexs de xarxa rústica, amenaçant de congelar la PWA de camp.
	
El backend asíncron detecta el volum d'elements, aplica un algorisme de simplificació de traçats de geometries vectorials (Douglas-Peucker) per reduir la mida del payload abans d'enviar-lo a l'IndexedDB del mòbil, mantenint la visualització d'alta precisió només a Next.js web.
--------------------------------------------------------------------------------
Requisits No Funcionals (RNF)

    Almacenamiento Seguro Soberano Local (Sin AWS S3): Tots els plànols base ràster (PDF, TIFF, PNG), fitxers vectorials, llistats de capes d'obra i imatges de camp s'emmagatzemen exclusivament en repòs mitjançant el xifratge AES-256-GCM en el servidor sobirà Hetzner a Alemanya (UE) sota /docs/<empresa_id>/planols/..., amb una validació rigurosa de Magic Bytes (filetype) que rebutja executables i una limitació estricta de 50 MB per fitxer per a estricte compliment de la LOPDGDD i el RGPD.
    Seguridad Multi-Tenant (RLS): Cada crida API de consulta, inserció o eliminació sobre les taules del mòdul de plànols s'aïlla de forma unívoca a nivell de PostgreSQL mitjançant la directiva FORCE ROW LEVEL SECURITY i l'ús de la variable de sessió d'inquilí app.current_empresa_id.
    Rendimiento y Escalabilidad: El temps de resposta del visor de plànols web Next.js no excedirà els 200 ms per a la càrrega i filtre de capes, mantenint una fluïdesa de 60 fps estables mitjançant la desnormalització de coordenades en PostgreSQL i precalculant la capsula delimitadora.
    Diseño Camaleón: La interfície de la biblioteca de plànols adopta de forma dinàmica les variables de marca corporativa (--color-primary, --color-secondary), mentre que els marcadors d'estat de capes mantenen codis cromàtics cartogràfics fixos i de contrast funcional universal.
    Tolerancia Cero a Datos Ficticios (Zero-Mock): Si l'empresa d'alta té 0 registres de plànols, l'arbre de navegació de la biblioteca de plànols es renderitzarà de forma 100% neta i buida (Empty State real), sense cap tipus de registre de prova ni dades simulades d'esquemes.

--------------------------------------------------------------------------------
Fora d'Abast (Out of Scope)

    No és un modelador tridimensional BIM 3D, ni processa fitxers de núvols de punts LiDAR o geometries 3D complexes (excloent-ne la visualització tridimensional).
    No incorpora mòduls de simulació o solvers fluidodinàmics actius (com EPANET) ni de càlcul de xarxa elèctrica de potència (como CYPE o Caneco).
    No gestiona els visats col·legials telemàtics de projectes davant del col·legi oficial d'enginyers, limitant l'exportació de PDF a un lliurament tècnic d'obra per al client.
    No realitza canvis ni actualitza de forma desatendida o directa la xarxa cartogràfica vectorial mestra sense la validació explícita d'un enginyer supervisor.

--------------------------------------------------------------------------------
Criteris de Finalització (Definition of Done) i Matriu de Traçabilitat

    Els 26 Requisits Funcionals (RF-01 al RF-26) i els 10 Casos Límit (EDGE-01 al EDGE-10) redactats amb sintaxi formal EARS estricta en català i lliures d'ambigüitats tècniques o dades de prova fictícies sota l'estat Dia 0.
    Correspondència del 100% de la spec de plànols amb una suite de proves d'integració automatitzada en verd amb PostgreSQL RLS actiu sota el tenant real d'empresa.
    Alineació total de la política de QR: exclusió absoluta de codis QR per a les eines de camp (les quals es custodien i es traspassen per referència de fàbrica/SN), preservant el QR legal obligatori de facturació Veri*factu per a albarans i factures.
    Processament asíncron asimètric: integració d'un pipeline en segon pla (Celery + Redis) per a la conversió i simplificació geomètrica de fitxers DXF pesats, evitant bloquejar el event loop de FastAPI.

Matriu de Traçabilitat 1:1 de la Definition of Done (DoD)
Codi de la Spec
	
Cas Límit Vinculat
	
Assert / Criteri de Validació DoD (Zero-Mock)
RF-01 / RF-02
	
-
	
Arbre de navegació tabular per clients. L'arrencada en Dia 0 mostra Empty State real sense mocks.
RF-03
	
EDGE-01
	
Cerca i llistat de plànols; el control de concurrencia optimista d'escriptures llança 409 Conflict.
RF-04 / RF-05
	
EDGE-02
	
Pujada de fitxer; comprovació de Magic Bytes i bloqueig rígid de petició davant fitxers >50MB.
RF-06
	
EDGE-04
	
Càrrega de KML rústic local (ED50) és reprojectada correctament a WGS84decimals a base de dades.
RF-07 / RF-08
	
EDGE-08
	
Fitxer de quadre unifilar elèctric s'obre directament en el visor documental de Next.js d'alta resolució.
RF-09 / RF-10
	
-
	
Inserció de capa superposada de rases de reg sense danyar ni sobreescriure el plànol original de la finca.
RF-11 / RF-12
	
EDGE-05
	
Capa de canonades vinculada a tasca ja tancada i facturada passa a immutable amb estat només lectura.
RF-13
	
EDGE-05
	
Put o Patch de modificació directe sobre capa immutable sota tasca closa retorna HTTP 403.
RF-14 / RF-15
	
-
	
Traçat d'elements geomètrics 2D i fixació de cotes textuals ancorades inalterablement al vector.
RF-16 / RF-17
	
EDGE-06
	
Càrrega de marcadors hidràulics/elèctrics; selecció radial (spiderfy) davant col·lisió visual extrema.
RF-18 / RF-19
	
EDGE-03 / EDGE-05
	
Descàrrega vectorial a l'IndexedDB; consulta i zoom fluid en mode avió sense cobertura de camp.
RF-20 / RF-21
	
EDGE-06
	
Inserció de PIN d'incidència d'avaria sota IndexedDB xifrat AES-GCM local en PWA.
RF-22
	
EDGE-06
	
Sync asíncron; sincronització de pins i fotos en recuperar cobertura celular a camp de forma idempotent.
RF-23 / RF-24
	
EDGE-09
	
Exportació PDF; fallida d'exportació asíncrona Celery reverteix el lot de forma segura i llança alerta.
RF-25
	
-
	
Dossier final d'obra en PDF conté el caixetí corporatiu, esclaes, llegenda, dades fiscals i és lliure de QR d'eines.
RF-26
	
-
	
Descàrrega de capes vectorials d'obra en format estàndard DXF o GeoJSON per a programari tècnic extern.