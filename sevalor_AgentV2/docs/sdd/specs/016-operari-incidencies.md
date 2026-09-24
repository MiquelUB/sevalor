Spec 016 — Mòdul de Bústia, Gestió i Seguiment d'Incidències de Camp a la PWA (/operari/incidencies) - v3
AVÍS D'ALINEACIÓ CONSTITUCIONAL I INTEGRACIÓ ARQUITECTÒNICA: Aquesta especificació tècnica es regeix de forma innegociable pels principis de la Constitució de CampoPro Suite (v4.0) i s'integra de forma transversal amb la Torre de Control Geogràfica en temps real (Spec 001 i Spec 005), el Mòdul de Clients (Spec 002), el Mòdul de Magatzem (Spec 004), el Mòdul de Flota (Spec 006), el Mòdul d'Operaris (Spec 008), el Mòdul Contable (Spec 007), el Mòdul de Plànols (Spec 010) i el Mòdul d'IA Copilot de Camp i Gestió (Spec 012).
Es prohibeix taxativament l'ús de dades simulades o de prova (Zero Mock Data), partint d'un estat de "Dia 0" real i garantint de forma absoluta la sobirania de dades mitjançant l'emmagatzematge local/sobirà dels expedients de materials, fotos d'obra, incidències i fitxatges en el servidor Hetzner de Falkenstein (Alemanya - UE), rebutjant completament qualsevol servei de núvol públic extern (com AWS S3) d'acord amb el compliment estricte de la LOPDGDD i el RGPD.
De conformitat amb la Constitució i el criteri de QA unificat, es recorda que s'exclou l'ús de codis QR per a la traçabilitat i transferència d'eines de camp (les quals es gestionen i es custodien nominalment pel seu número de referència, marca, model i número de sèrie de fàbrica sota la Spec 004 i Spec 008). Aquesta exclusió tècnica convive en perfecta harmonia amb la permanència del codi QR legal i tributari requerit obligatòriament a totes les factures i albarans de lliurament oficials (Veri*factu) emesos pel mòdul comptable.
--------------------------------------------------------------------------------
Context i Objectiu
El mòdul d'Incidències de la PWA (/operari/incidencies) és el canal d'alerta i coordinació bidireccional en temps real entre els equips tècnics que operen al terreny i l'oficina tècnica central (/gestio). Està dissenyat sota el principi ergonòmic del "Flujo de los 30 segundos" per donar resposta immediata a imprevistos operatius, bloquejos logístics, incidències de flota i situacions d'emergència mèdica sense interrompre la marxa de les obres i evitant qualsevol mena de fricció burocràtica.
Aquest mòdul garanteix:

    Alerta acústica i visual persistent a la capçalera: Campana d'incidències al header de la PWA que canvia a vermell brillant i activa un senyal acústic sonor quan l'enginyer emet una ordre d'urgència o resolució.
    Doble sentit operatiu a la safata centralitzada:
        Incidències enviades per l'operari: Classificades per àmbit: vinculades a fulla de tasca (manca de material, porta tancada), de vehicle (punxades, avaries, xocs) o altres contingències (accidents laborals, meteorologia adversa).
        Incidències rebudes de base: Ordres urgents o comunicacions d'enginyeria, mostrades a pantalla completa a la PWA de forma immediata i prioritària perquè el conductor s'adoni de l'alerta i pugui aturar el vehicle en un lloc segur per respondre, amb botó obligatori de confirmació de rebuda.
    Protocol d'emergències mèdiques i laborals (SOS): Marcatge d'incidència d'alta prioritat amb alerta directa a la Torre de Control i botó visible d'accés directe al 112 (Emergències), el qual ha de ser polsat manualment per l'operari (mai de forma automatitzada).
    Plantilla multimodal flexible, capes independents i plànols pinejats: Captura d'incidències mitjançant nota de veu (Whisper local), imatge (compressió WebP en client), nota de text i plànols interactius pinejats (on el sistema crea una nova capa gràfica independent per reflectir l'incidència mantenint net el plànol base per a posteriors reutilitzacions, permetent situar-hi el pin georeferenciat sense possibilitat d'esborrar cap altra capa però facilitant-ne el seu filtratge i conmutació de visibilitat). La tramesa és vàlida amb l'aportació d'un sol canal per facilitar la mobilitat.
    Cicle de resolució cromàtic (Vermell a Verd) amb seguretat: Les incidències romanen en vermell (obertes) fins a la seva resolució. L'operari pot passar a verd les incidències de camp solucionades aportant foto de solució; les incidències econòmiques (excedències de targeta >100 €) o de seguretat (accidents) estan reservades exclusivament al supervisor o secretaria.
    Processament pericial d'àudio pel Copilot IA: Transcripció automàtica local (Whisper al servidor Hetzner) perquè l'enginyer pugui llegir el resum de la nota de veu en text o escoltar l'arxiu d'àudio original.
    Resiliència total Offline: Visualització d'estat "Pendent de pujada / En cua local (Offline)" i sincronització automàtica i transparent en segon pla en recuperar connexió mòbil, protegint l'emmagatzematge mòbil en cas de manca de quota.

--------------------------------------------------------------------------------
Usuaris / Actors i Matriu d'Interacció (Zero-Trust)
Totes les dades d'incidències estan protegides mitjançant Row Level Security (RLS) a la base de dades sota la sessió de l'empresa_id de l'operari autenticat:

    Operari / Cap de Colla (/operari/incidencies): Genera incidències de camp multimodals, col·loca pins al plànol, activa el botó SOS en accidents, rep les instruccions de base a pantalla completa, confirma recepcions i tanca incidències operatives a verd.
    Enginyer / Supervisor Tècnic (/gestio/feines / Torre de Control): Rep en temps real les incidències a la Torre de Control, llegeix transcripcions d'àudio, audita plànols pinejats, resol contingències, eleva peticions a Secretaria i emet incidències urgents cap a les quadrilles.
    Secretaria / Administració: Tramita les incidències que comporten ampliació de límit de targetes de camp de 100 € o gestió de parts d'accidents laborals amb la mútua.
    Serveis d'Emergència (112): Receptors de la trucada de veu directa de l'operari, iniciada manualment des del dispositiu mòbil.

Matriu de Responsabilitats per Tipus d'Incidència
Tipologia d'Incidència
	
Origen / Emissor
	
Canals d'Entrada
	
Resolució a Camp (Operari)
	
Resolució Central (Enginyer/Base)
Manca de Material / Cadenat
	
Operari a la tasca
	
Foto, Veu, Pin plànol
	
Pot passar a Verd en solucionar
	
Valida canvi d'assignació
Avaria de Vehicle / Punxada
	
Operari de vehicle
	
Foto dany, Veu, Text
	
Pot passar a Verd si canvia roda
	
Coordina grua o assistència (Spec 006)
Compra Urgent Ferreteria (>100 €)
	
Operari de tasca
	
Foto tiquet/pressupost
	
No pot tancar a Verd
	
Supervisor deriva a Secretaria (Spec 007)
Accident Laboral / Mèdic (SOS)
	
Operari (Manual)
	
Veu, Foto, Botó 112
	
Prohibit tancar a Verd
	
Supervisor gestiona protocol mútua (Spec 008)
Meteorologia Adversa / Aturada
	
Operari o Base
	
Nota veu, Text
	
Pot passar a Verd si reprèn
	
Replanifica rutes de la colla
Ordre Urgent de Base
	
Enginyer (/gestio)
	
Instruccions text/àudio
	
Confirma rebuda a pantalla completa
	
Tanca en verd un cop executada
--------------------------------------------------------------------------------
Requisits Funcionals (EARS Notation)
Àmbit 1: Capçalera, Campana Acústica i Safata Centralitzada

    RF-01 (Ubiquitous): La PWA mòbil de camp renderitzarà a la capçalera superior (header) un component visual de Campana d'Incidències, visible i persistent des de qualsevol secció de l'aplicació mòbil de l'operari.
    RF-02 (Event-driven): QUAN el backend transmeti una nova incidència, ordre urgent o actualització d'estat des de la base cap a l'operari, EL SISTEMA commutarà immediatament el color de la campana a vermell intens i reproduirà un senyal acústic sonor (to d'alerta de camp d'alta audibilitat).
    RF-03 (Ubiquitous): La pantalla /operari/incidencies renderitzarà una safata centralitzada de dades reals estructurada en dos blocs clarament diferenciats:
        Incidències enviades per la colla: Registres de contingències creats pels membres de la colla durant la jornada actual.
        Incidències rebudes de base: Instruccions, avisos urgents, canvis de prioritat d'itinerari o alertes remeses per l'oficina tècnica.
    RF-04 (Unwanted-behaviour): SI durant la jornada de treball de la colla no s'ha registrat cap incidència (enviada ni rebuda), ENTONCES EL SISTEMA renderitzarà la safata completament buida, mostrant l'Empty State real: "No hi ha incidències registrades avui", sense inyectar dades de prova ni registres de simulació (Zero Mock Data).

Àmbit 2: Selector d'Origen i Classificació d'Incidències

    RF-05 (Event-driven): QUAN l'operari premi el botó "+ Nova Incidència", EL SISTEMA obrirà un formulari de selecció d'origen per determinar la naturalesa de la incidència:
        Incidència de Tasca / Feina: Associa la incidència de forma directa a una ordre de treball activa del dia mitjançant desplegable (ex. manca de material, cadenat/porta tancat, escomesa obstruïda).
        Incidència de Vehicle / Remolc: Associa l'avaria al vehicle habitual o de substitució assignat a la colla per a la jornada de conformitat amb la Spec 006 i 015 (ex. punxada de roda, avaria de motor, trencament d'enganxament).
        Incidència General / Altres: Contingències que afecten la jornada de forma independent de les tasques (ex. temporal de pluja extrema que inunda l'accés rural, accident laboral, pèrdua física de terminal mòbil).

Àmbit 3: Protocol d'Emergències i Accident Laboral (SOS / 112)

    RF-06 (Event-driven): La PWA mòbil de camp incorporarà un botó d'alta prioritat de color vermell parpellejant amb l'etiqueta "SOS Emergència", destinat exclusivament a situacions d'accidents de treball greus, descàrregues elèctriques, caigudes de cabina o urgències mèdiques.
    RF-07 (State-driven): QUAN l'operari seleccioni la incidència de tipus SOS, EL SISTEMA transmetrà una alerta d'alta prioritat en temps real via WebSocket/SSE a la Torre de Control d'oficina i obrirá a la pantalla del mòbil el protocol SOS, renderitzant un botó de gran format de trucada telefònica de veu directa al 112 (Emergències).
    RF-08 (Unwanted-behaviour) — Prohibició de Trucada Automàtica: Per estricte compliment de la seguretat vial i protocols de seguretat de sistemes, EL SISTEMA mai realitzarà la trucada al 112 de forma automatitzada o desatesa; el botó obrirà exclusivament el marcador telefònic natiu del telèfon mòbil, requerint la pulsació conscient de l'operari per iniciar la trucada de veu.

Àmbit 4: Plantilla Multimodal i Plànols Pinejats

    RF-09 (Ubiquitous): La plantilla de creació d'incidències de la PWA mòbil oferirà quatre canals d'entrada d'informació estructurada:
        Nota de veu: Enregistrament directe d'àudio des del micròfon de la PWA mòbil.
        Fotografia: Captura d'imatges des de la càmera (tiquet de ferreteria, paret danyada, avaria de bomba).
        Plànol interactiu: Croquis tècnic vectorial de la finca o instal·lació d'obra descarregat sota la Spec 010.
        Nota de text: Observacions de text lliure per a comentaris tècnics de l'operari.
    RF-10 (State-driven): MIENTRAS la incidència provingui d'un bloqueig de camp, EL SISTEMA considerarà vàlida i autoritzarà la tramesa de la incidència aportant un sol dels canals d'entrada (ex. només la gravació d'àudio del capataz), sense forçar a omplir camps o formularis buits en mobilitat.
    RF-11 (Event-driven) — Pins d'Incidència sobre Plànols Tècnics via Capes: QUAN l'operari seleccioni l'opció de Plànol interactiu per a un PIN d'incidència, EL SISTEMA obrirà el visualitzador de plànols i crearà de forma automàtica una nova capa independent dedicada a l'incidència, mantenint net i inalterat el plànol base per a posteriors reutilitzacions. EL SISTEMA permetrà a l'operari col·locar el PIN georeferenciat sobre aquesta nova capa gràfica de l'incidència, associant fotos pericials, textos i notes d'àudio d'acord amb la Spec 010, sense possibilitat d'esborrar cap altra capa ja existent però permetent el seu filtratge per conmutar-ne la visibilitat.

Àmbit 5: Incidències Rebudes de Base a Pantalla Completa i Seguretat Vial

    RF-12 (Event-driven): QUAN el backend rebi una ordre de base prioritària o incidència remesa per l'enginyer de l'oficina, EL SISTEMA projectarà de forma immediata la instrucció en una vista modal a pantalla completa a la PWA, garantint la màxima llegibilitat de les ordres de modificació o seguretat tècnica.
    RF-12.1 (State-driven) — Recepció de Notificacions Prioritària en Ruta: SI el vehicle assignat es troba en estat Blau (En trànsit) (en marxa de conformitat amb la Spec 013), ENTONCES EL SISTEMA rebrà i mostrarà immediatament la notificació o modal prioritària d'incidència a la pantalla per tal de possibilitar que el conductor cerqui un lloc segur per aturar el vehicle i respondre, eliminant qualsevol filtre de bloqueig o retard en la recepció de l'alerta.
    RF-13 (Ubiquitous): La vista modal prioritària a pantalla completa romandrà visible a la PWA de camp, inhabilitant qualsevol interacció amb la resta de mòduls, fins que l'operari pitgi de forma conscient el botó d'Acusament de Recepció ("Confirmar Rebuda / Entès").
    RF-14 (Event-driven): QUAN l'operari premi "Confirmar Rebuda / Entès", EL SISTEMA transmetrà la confirmació de lectura de forma asíncrona cap a /gestio, registrant la marca temporal (timestamp ISO) i la geolocalització exacta per al control d'auditoria.

Àmbit 6: Cicle de Resolució Cromàtic (Vermell a Verd) i Permisos de Seguretat

    RF-15 (State-driven): Tota incidència de camp s'iniciarà incondicionalment en estat Vermell (Oberta / En curs), tant a la safata de la PWA mòbil com a la bústia de la Torre de Control de l'oficina central.
    RF-16 (Event-driven): Per a incidències de camp operatives ordinàries (porta de cancela ja oberta pel client, canvi de roda del vehicle finalitzat, material de recanvi rebut), el cap de colla disposarà del botó "Marcar com a Resolta / Passar a Verd", podent adjuntar una foto de solució o nota explicativa abans del desat.
    RF-17 (Unwanted-behaviour) — Bloqueig de Resolució d'Incidències Complexes: SI la incidència és de tipus d'accident laboral (SOS), temporal meteorològic d'aturada de jornada, o comporta una excedència de crèdit per compra d'urgència (>100 €), ENTONCES la PWA mòbil de camp mantindrà el botó "Marcar com a Resolta / Passar a Verd" estrictament inhabilitat i bloquejat per a l'operari, essent innegociable que el tancament formal a verd el realitzi el supervisor o secretaria des del Dashboard d'oficina.
    RF-18 (Ubiquitous): La bústia mòbil de la PWA permetrà filtrar instantàniament els registres de contingències mitjançant dues pestanyes de selecció: "Incidències Actives" (en color Vermell) per a les resolucions immediates i "Historial de Resoltes" (en color Verd) per a consulta de dades històriques.

Àmbit 7: Integració amb el Copilot d'IA Local i RAG (Spec 012)

    RF-19 (Event-driven): QUAN el cap de colla enregistri una nota de veu d'incidència d'obra, EL SISTEMA transferirà l'arxiu d'àudio (.webm) al pipeline asíncron de Celery per al seu processament local mitjançant Whisper v3 al servidor Hetzner a Alemanya, generant la transcripció textual en català i castellà tècnic en menys de 8 segons.
    RF-20 (Ubiquitous): A la Torre de Control de l'oficina central, EL SISTEMA oferirà a l'enginyer el doble canal de gestió tècnica: podrà llegir de forma instantània el text transcrit i el diagnòstic proposat pel Copilot d'IA (Memoràndum) al Drawer d'incidències, o escoltar directament l'àudio original de camp des del reproductor de veu natiu, per assegurar el compliment del principi de veracitat.

Àmbit 8: Resiliència Offline-First, IndexedDB i Manca de Quota Mòbil

    RF-21 (State-driven): SI l'operari genera o resol una incidència des d'una zona rústica sense cobertura de xarxa mòbil, la PWA mòbil de camp emmagatzemarà de forma segura el paquet de dades de la incidència (àudios, fotos WebP, textos i georeferenciació) a la base de dades local xifrada IndexedDB sota el xifratge de seguretat AES-GCM de 256 bits.
    RF-22 (State-driven): MIENTRAS la incidència estigui en cua local pendent de transmissió, la PWA mòbil la mostrarà a la safata de camp acompanyada d'una insígnia visible i un text indicador: "Pendent de pujada / En cua local (Offline)", per a tranquil·litat de la colla.
    RF-23 (Event-driven): Tan bon punt el Service Worker de la PWA detecti connexió de xarxa mòbil activa (4G, 5G o Wi-Fi), transmetrà el payload offline de forma asíncrona i idempotent al backend central de FastAPI, alliberant la cua d'IndexedDB de camp i actualitzant el marcador del mapa de la Torre de Control.
    RF-24 (State-driven) — Control de Quota d'Emmagatzematge en Incidències: SI la grandària total d'àudios i fotos d'incidències emmagatzemats localment a l'IndexedDB de la PWA frega el 80% del límit de quota assignat pel navegador mòbil, ENTONCES la PWA inhabilitarà temporalment el botó d'obertura de la càmera i de gravació de veu per a noves incidències, alertant a l'operari: "Falta de quota: Conecti a xarxa per buidar fotos locals" i permetent de forma exclusiva reportar mermes o incidències mitjançant text pla de pocs bytes per protegir el sistema mòbil.

--------------------------------------------------------------------------------
Taula de Casos Límit i Gestió d'Errors
Codi
	
Tipus EARS
	
Mòdul
	
Vector de Falla / Escenari Límit
	
Comportament Requerit del Sistema
EDGE-01
	
Unwanted
	
PWA SOS
	
Accident greu de camp en un barranc rústic profund sense cobertura cel·lular.
	
El cap de colla activa el flag SOS Emergència. La PWA mòbil mostra el botó d'accés directe per trucar al 112 de veu (utilitzant serveis d'emergència de ràdio-frecuencia telefònica tradicional del mòbil) i desa el paquet de dades a l'IndexedDB xifrat en camp local sota la insígnia "En cua local (Offline)". En recuperar xarxa de dades, es transmet a base automàticament.
EDGE-02
	
State-driven
	
Seguretat
	
S'intenta realitzar o editar modificacions gràfiques (pins d'incidència) sobre un plànol o capa associat a una ordre de treball tancada i facturada (Spec 007 / Spec 010).
	
EL SISTEMA bloca incondicionalment l'escriptura local a camp i el backend retorna un error HTTP 403 Forbidden, mostrant el plànol estrictament en mode només lectura: "Capa bloquejada per traçabilitat pericial d'obra tancada".
EDGE-03
	
Unwanted
	
PWA Quota
	
El navegador mòbil d'un cap de colla offline bloqueja l'escriptura de fotos o àudio de veu a l'IndexedDB per haver-se superat la quota de seguretat del dispositiu.
	
El Service Worker de la PWA bloqueja les captures de la càmera de camp, prioritza l'escriptura immutable dels metadades de text de la incidència i el dibuix de pins del plànol, i llança l'alerta: "Falta de quota: Conecti a xarxa per buidar fotos locals".
EDGE-04
	
Event-driven
	
PWA / Sync
	
La PWA intenta sincronitzar una incidència urgent resolta a camp, però la xarxa cel·lular presenta microtalles o canvis ràpids de 3G/4G a mig camí d'enviar l'àudio Whisper.
	
El client de sincronització aplica de forma idempotent la política de reintents exponencials de connexió (tenacity), de manera que l'enviament de l'àudio pesat es reprèn des del punt d'interrupció sense perdre les dades locals i evitant la duplicació del tiquet a la Torre de Control d'oficina.
EDGE-05
	
Unwanted
	
Seguretat
	
Un usuari amb rol Operari o Enginyer intenta forçar directament via crida API (Postman) el tancament a verd d'una incidència SOS d'accident o d'excedència contable.
	
El PostgreSQL interposa de forma immediata la política de Row Level Security (FORCE ROW LEVEL SECURITY sota app.current_empresa_id) i l'endpoint de seguretat de rols del backend bloqueja la transacció de mutació retornant un error HTTP 403 Forbidden.
EDGE-06
	
Event-driven
	
PWA / OCR
	
L'operari puja la foto d'una tiquet de caixa de compra urgent d'eines a ferreteria local on hi ha taques d'oli o brillantor que fan il·legible l'OCR.
	
El backend processa el rebut a Comptabilitat (Spec 007) mitjançant el motor OCR de Copilot, detecta la baixa confiança d'ingesta, accepta la càrrega manual de text pel capataz a la PWA per no bloquejar el tancament de l' shift, però marca el tiquet a /gestio en estat PENDENT_AUDITORIA de Secretaria.
EDGE-07
	
State-driven
	
Seguretat
	
Es confirma la baixa lògica (actiu = false) d'un operari que manté la PWA mòbil oberta i amb incidències pendents de sincronització a IndexedDB local.
	
El Service Worker intercepta la revocació del token JWT de Redis, bloqueja qualsevol petició d'API, purga de forma destructiva l'IndexedDB local (dades de clients, incidències, plànols, claus d'accessos de furgonetes) i tanca la sessió a l'acte per seguretat d'informació de l'inquilí.
EDGE-08
	
Event-driven
	
Seguretat Vial
	
L'enginyer envia una ordre urgent o incidència a la colla mentre aquesta es troba circulant per carretera (estat Blau / En trànsit).
	
La PWA mòbil rep i renderitza de forma instantània la notificació acústica i el modal visual a la pantalla, facilitant que el conductor s'adoni de l'urgència de l'alerta i s'aturi de forma segura en un lloc apropiat per respondre, evitant retards en la coordinació.
EDGE-09
	
Unwanted
	
Concurrència
	
Dos enginyers d'oficina obren el Drawer d'incidències del Dashboard i intenten prémer simultàniament el botó "Resoldre Incidència" de la mateixa contingència de camp.
	
El backend de l'API de CampoPro aplica control de concurrència optimista mitjançant version_id. El primer commit consolida la resolució a la base de dades; el segon commit es rebutja amb error HTTP 409 Conflict, forçant a actualitzar la vista i notificant que l'incidència ja ha estat resolta.
EDGE-10
	
Event-driven
	
PWA / SOS
	
Un operari d'oficina intenta simular un xat lliure o social des del mòdul d'incidències per a converses informals.
	
El sistema bloqueja la injecció de text genèric o elements de xat informal, restringint strictly el motor operatiu d'incidències a la plantilla multimodal de contingències tècniques (Zero Mock Data / Fora d'Abast).
--------------------------------------------------------------------------------
Requisits No Funcionals (RNF)

    Almacenamiento Local Seguro Multi-Tenant (Soberano): Tots els albarans, documents ambientals NIMA, fotografies de mermes, notes d'àudio d'incidències de camp i expedients PDF es guarden de forma xifrada en repòs mitjançant el xifrat AES-256-GCM en el servidor sobirà Hetzner a Alemanya sota la ruta local de l'inquilí /docs/<empresa_id>/almacen/incidencies/..., descartant completament AWS S3 per a estricte compliment de la LOPDGDD i el RGPD.
    Seguridad Multi-Tenant (RLS): Cada consulta, actualització o modificació aplicada sobre les taules d'incidències i moviments de la safata de notificacions es realitzarà sota el Row Level Security (RLS) mandatori a nivell de PostgreSQL mitjançant la variable d'inquilí app.current_empresa_id de forma universal.
    Velocitat de Resposta Operativa d'IA: L'anàlisi de fotografies d'odòmetres i horòmetres de furgonetes, l' OCR d'ingesta de tiquets, i la transcripció Whisper d'àudios locals per Celery + Redis no excedirà els 8 segons de temps d'execució, oferint una latència en Next.js per a l'actualització de dades del xat inferior a 150 ms via WebSockets.
    PWA Offline Cache: El Service Worker mantindrà actiu el cache d'actius, previsualitzador d'estoc de furgonetes i formularis de check-in/out en IndexedDB mòbil sota el protocol de Cache-First, garantint la independència de xarxa i el funcionament d'emergències en camp.

--------------------------------------------------------------------------------
Fora d'Abast (Out of Scope)

    No gestiona els terminis de manteniment, ITV o assegurances de la flota mòbil (es governa a la Spec 006 de Flota).
    No realitza trucades de veu automatitzades desateses cap al 112; el botó del protocol SOS requereix imperativament la pulsació física i conscient de l'operari de camp.
    No incorpora centraletes telefòniques IP, serveis de veu interactiva (IVR) ni sistemes d'atenció al client telefònica automatitzats. Les trucades de l'enginyer es realitzen per terminal mòbil tradicional.
    No és un mòdul de xat social, xarxa social o fòrum per a la plantilla; es restringeix estrictament a la comunicació pericial de contingències laborals i d'obra.
    No s'admeten dades de prova ni insercions simulades a cap nivell de codi d'incidències, partint d'un entorn de Dia 0 real (Zero Mock Data).

--------------------------------------------------------------------------------
Criteris de Finalització (Definition of Done) i Matriu de Traçabilitat
Per a poder certificar el tancament de la Spec 016 d'Incidències de camp i habilitar la seva fase d'implementació, s'ha de garantir el compliment dels criteris següents:

    Els 24 Requisits Funcionals (RF-01 al RF-24) i els 10 Casos Límit (EDGE-01 al EDGE-10) redactats amb sintaxi formal EARS estricta en català i lliures d'ambigüitats tècniques o dades de prova fictícies sota l'estat Dia 0.
    Correspondència del 100% de la spec de la PWA mòbil amb una suite de proves d'integració automatitzada en verd amb PostgreSQL RLS actiu sota el tenant real d'empresa.
    Alineació total de la política de QR (Constitució v4.0): exclusió absoluta de codis QR per a les eines i vehicles de camp, preservant el QR legal obligatori de facturació Veri*factu per a albarans i factures al tancament.
    Tractament analític dels consums continuats: diferenciació nítida entre bobines/barres senceres i retalls, obligant al operari a exhaurir abans el stock parcial de camp sota la PWA mòbil.
    Recepció prioritària de notificacions en ruta: el sistema de notificacions i l'avís de base a pantalla completa de la PWA s'ha de rebre i visualitzar a l'acte de forma ininterrompuda encara que el vehicle es trobi en ruta (estat Blau / En trànsit), assegurant que el conductor pugui aturar el vehicle de forma immediata en un lloc segur per respondre.

Matriu de Traçabilitat 1:1 de la Definition of Done (DoD)
Codi de la Spec
	
Cas Límit Vinculat
	
Assert / Criteri de Validació DoD (Zero-Mock)
RF-01 / RF-02
	
-
	
Renderitzat de capçalera Next.js d' shift. El fitxatge de camp sota incidència és idempotent.
RF-03
	
-
	
Safata dual d'incidències en Next.js. El directori buit de tiquets llança Empty State lliure de mocks.
RF-04
	
-
	
BD buida d'incidències de camp mostra Empty State de forma 100% neta de dades mock.
RF-05
	
EDGE-09
	
Selector d'origen d'incidències; el control de concurrència optimista d'escriptures sobre la mateixa incidència llança 409.
RF-06 / RF-07
	
EDGE-01
	
SOS Emergència actiu; polsar SOS sense cobertura cel·lular desa a IndexedDB offline i habilita el 112 per ràdio-frecuencia.
RF-08
	
EDGE-01
	
Trucada al 112 requereix imperativament la pulsació conscient de l'operari conductor, prohibint marcatges automatitzats.
RF-09 / RF-10
	
EDGE-06
	
Plantilla multimodal d'incidències accepta càrregues parcials d'entrada (ex. només la foto d'avaria o àudio Whisper).
RF-11
	
EDGE-02
	
Pins d'incidència georeferenciats sobre plànols; el sistema crea una nova capa per a l'incidència sense possibilitat d'esborrar cap altra capa, permetent el filtratge d'aquestes per seguretat d'auditoria.
RF-12 / RF-12.1
	
EDGE-08
	
Ordre urgent o incidència a pantalla completa; es rep i es visualitza de forma prioritària i immediata en estat Blau (En trànsit) per indicar l'aturada de seguretat del vehicle.
RF-13 / RF-14
	
EDGE-07
	
Modal prioritari immobilitza la PWA fins a prémer Acusament de Recepció; baixa de l'operari purga de forma destructiva l'IndexedDB.
RF-15 / RF-16
	
-
	
Estat inicial en Vermell (Obert); l'operari de camp pot conmutar a Verd incidències operatives aportant foto de solució.
RF-17
	
EDGE-05
	
Incidències SOS o >100 € bloca el botó de tancar a verd per a l'operari; el PUT de resolució per operari llança 403.
RF-18
	
-
	
Pestanyes de filtratge entre Incidències Actives (Vermell) i Resoltes (Verd) de camp actiu.
RF-19 / RF-20
	
EDGE-04
	
Transcripció Whisper de notes d'àudio; pèrdua de xarxa cel·lular a mig enviament és gestionada de forma idempotent.
RF-21 / RF-22
	
EDGE-03
	
Desament local d'incidències a l'IndexedDB xifrat sota insígnia "Pendent de pujada"; quota >80% bloca càmera i àudio.
RF-23 / RF-24
	
EDGE-03
	
Service Worker executa la sincronització en segon pla en recuperar cobertura; quota >80% permet només text de pocs bytes.