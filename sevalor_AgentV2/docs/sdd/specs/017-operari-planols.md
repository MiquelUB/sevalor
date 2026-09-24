Spec 017 — Mòdul de Biblioteca, Visualització i Edició de Plànols de Camp a la PWA (/operari/planols) - v3
AVÍS D'ALINEACIÓ CONSTITUCIONAL I INTEGRACIÓ ARQUITECTÒNICA: Aquesta especificació tècnica es regeix de forma innegociable pels principis de la Constitució de CampoPro Suite (v4.0) i s'integra de forma transversal amb el Dashboard i la Torre de Control de Camp (Spec 001 i Spec 005), el Mòdul de Clients (Spec 002), el Mòdul de Magatzem (Spec 004), el Mòdul de Flota (Spec 006), el Mòdul d'Operaris (Spec 008), el Mòdul Contable (Spec 007), el Mòdul de Plànols (Spec 010) i el Mòdul d'Incidències de Camp de la PWA (Spec 016).
Es prohibeix taxativament l'ús de dades simulades o de prova (Zero Mock Data), partint d'un estat de "Dia 0" real i garantint de forma absoluta la sobirania de dades mitjançant l'emmagatzematge local/sobirà dels expedients de materials, plànols, albarans i inventaris en el servidor Hetzner de Falkenstein (Alemanya - UE), rebutjant completament qualsevol servei de núvol públic extern (como AWS S3) d'acord amb el compliment estricte de la LOPDGDD i el RGPD.
De conformitat amb la Constitució i el criteri de QA unificat, es recorda que s'exclou l'ús de codis QR per a la traçabilitat i transferència d'eines de camp (les quals es gestionen i es custodien nominalment pel seu número de referència, marca, model i número de sèrie de fàbrica sota la Spec 004 i Spec 008). Aquesta exclusió tècnica convive en perfecta harmonia amb la permanència del codi QR legal i tributari requerit obligatòriament a totes les factures i albarans de lliurament oficials (Veri*factu) emesos des del mòdul comptable.
--------------------------------------------------------------------------------
Context i Objectiu
El mòdul de Plànols de la PWA (/operari/planols) és la plataforma de consulta tècnica i edició cartogràfica de camp per a l'operari i el cap de colla. Proporciona accés directe a la informació espacial, hidràulica, elèctrica i estructural de les instal·lacions d'obra, facilitant tant la inspecció visual sobre el terreny com el registre d'anotacions As-Built de les reformes executades de forma 100% sintonitzada amb l'oficina central.
Aquest mòdul garanteix:

    Doble accés i biblioteca protegida: Els plànols vinculats a una feina apareixen a la pròpia fulla de tasca (Spec 013), mentre que a /operari/planols s'ofereix una biblioteca d'arxius en llista amb cercador, mostrant la correlació clara amb la tasca del dia assignada.
    Aïllament estricte de seguretat (Zero-Trust): L'operari té estrictament i exclusivament prohibit consultar o navegar per la base de dades general de plànols de l'empresa. Només pot obrir els plànols que estan directament vinculats a les tasques que té assignades per a la jornada actual. Tota petició de plànol extra s'ha de canalitzar formalment via Incidència de tipus "Sol·licitud de plànols" per a aprovació de l'enginyer.
    Estat buit net i amigable (Zero Mock Data): Si l'operari no tens cap plànol assignat a les seves feines de la jornada, el sistema no inyectarà croquis inventats. Renderitzarà un Empty State net i explícit amb el text canònic: "No tens cap plànol o xarxa tècnica assignada avui" per evitar confusions visuals o la sensació d'aplicació congelada.
    Visor adaptatiu i geolocalització sobre el terreny: Botó de "Posició GPS actual" per a plànols georeferenciats de parcel·la; la interfície admet també esquemes ràster sense geolocalització (esquemes unifilars, quadres o caixes elèctriques).
    Pop-up de consulta d'atributs tècnics: Possibilitat de tocar canonades, vàlvules o components per desplegar una fitxa emergent amb el diàmetre, pressió, material o referència programada per l'enginyer.
    Finestra d'edició simple i potent sota arquitectura de capes:
        Pins d'anomalia/incidència obligatoris: Amb associació directa de foto, nota de veu de camp i text (Spec 016).
        Dibuix de traçat ràpid amb vàries anotacions: Vermell, Blau, Verd i Negre.
        Mesurador de distàncies: Amb menció expressa del marge d'error GPS ("Aprox. X m").
        Eines de correcció: Botó de Desfer (Undo) i goma d'esborrar.
    Arquitectura de Capes No Destructives i Filtre de Visibilitat: Tota edició o anotació es desa de forma no destructiva en una Capa d'Anotacions de Camp / As-Built independent i filtrable, sense alterar mai ni sobreescriure el plànol mestre original de l'enginyer. Es proveeix un Selector de Capes per commutar la visibilitat individual (visible/invisible) i enfocar l'obra tècnica, prohibint la supressió física d'altres capes de traçabilitat pericial.
    Resiliència total Offline-First: Descàrrega preventiva automàtica de plànols i capes a memòria local xifrada d'IndexedDB de la PWA mòbil abans de sortir de la base, habilitant zoom, desplaçament i col·locació de marcadors localment en zones sense cobertura i sincronitzant de forma idempotent en recuperar connectivitat cel·lular.

--------------------------------------------------------------------------------
Usuaris / Actors i Matriu d'Interacció (Zero-Trust)
Totes les consultes d'arxius de plànols estan estrictament aïllades mitjançant Row Level Security (RLS) a nivell de base de dades PostgreSQL sota la variable d'inquilí app.current_empresa_id de l'operari autenticat.

    Operari / Cap de Colla (/operari/planols): Actor de camp principal. Consulta la llista de plànols assignats de la jornada, obre el visor, activa el GPS sobre parcel·la, consulta atributs tècnics mitjançant pop-ups, col·loca pins d'avaria, dibuixa amb els 4 colors i desa anotacions de camp no destructives.
    Enginyer / Supervisor Tècnic (/gestio/planols): Dibuixa i assigna els plànols a les ordres de treball, defineix les capes i atributs tècnics, rep avisos de "Plànol massa pesat", valida les peticions de plànols extres per incidència i audita la capa d'anotacions As-Built de camp per decidir de forma humana la seva fusió i consolidació definitiva al plànol mestre d'enginyeria.
    Delineant / Gabinet Tècnic: Carrega la cartografia vectorial DXF, KML, GeoJSON, gestiona georeferenciacions, resol transformacions afins de plànols rústics i manté actualitzades les capes base de les finques des del panell central de l'oficina.

Matriu de Responsabilitats per Àmbit
Funcionalitat de Plànols
	
Operari de Camp
	
Enginyer (/gestio)
	
Delineant / Suport
Accés a la Biblioteca
	
Consulta plànols de tasques assignades
	
Accés global a totes les finques de clients
	
Manteniment de fitxers CAD/GIS de l'empresa
Sol·licitud de Plànol Extra
	
Tramita via Incidència / Altres
	
Autoritza i adjunta a la feina
	
Genera extracte o georeferència si cal
Consulta d'Atributs Tècnics
	
Toca element per obrir pop-up
	
Defineix diàmetres i especificacions
	
Digitalitza atributs de capa en DXF
Marcatge GPS sobre Terreny
	
Activa botó de geoposicionament
	
Audita traçabilitat de posició
	
Ajusta calibració i bounds del mapa
Edició de Camp (Pins + 4 Colors)
	
Dibuixa i col·loca pins sobre capa As-Built
	
Revisa anotacions en vermell/blau/etc.
	
Incorpora correccions oficials
Desfer / Goma d'Esborrar
	
Corregeix traços propis en capa local
	
Sense accés a edicions en curs
	
Sense accés
Capa As-Built No Destructiva
	
Genera capa d'anotació a la tasca
	
Decideix fusió amb plànol mestre
	
Arxiu històric de versions de xarxa
Alerta de Pes Excessiu
	
Protegit contra saturació de memòria
	
Rep avís "Plànol massa pesat"
	
Optimitza o divideix el fitxer vectorial
--------------------------------------------------------------------------------
Requisits Funcionals (EARS Notation)
Àmbit 1: Biblioteca de Plànols, Accés Assignat i Estat Buit

    RF-01 (Ubiquitous): La pantalla /operari/planols renderitzarà la biblioteca d'arxius en format de llista neta amb cercador ràpid de text, mostrant per a cada plànol el seu nom descriptiu, tipologia i la correlació directa amb la tasca del dia a la qual està associat per facilitar la identificació de la feina.
    RF-02 (Unwanted-behaviour) — Bloqueig d'Accés General (Zero-Trust): EL SISTEMA denegarà qualsevol intent de l'operari d'accedir o navegar per la base de dades general de plànols de l'empresa o de projectes de tercers clients de la plataforma multi-tenant, restringint de forma estricta la biblioteca de la PWA als plànols que l'enginyer hagi vinculat de forma explícita a les ordres de treball assignades a la seva colla per a la jornada actual.
    RF-03 (Event-driven) — Flux de Sol·licitud de Plànol Extra: QUAN l'operari precisi consultar un plànol històric o d'una finca adjacent aliè a les seves tasques del dia, iniciarà una petició a la PWA enviant una "Incidència de Sol·licitud de Plànol"; EL SISTEMA notificarà de forma immediata a l'enginyer a la Torre de Control, qui n'autoritzarà la tramesa i enllaçarà de forma temporal el recurs a la bústia de l'operari.
    RF-04 (Unwanted-behaviour) — Estat Buit Sincer (Zero Mock Data): SI la colla d'operaris no té cap plànol o xarxa tècnica assignada a les tasques de la jornada, ENTONCES EL SISTEMA renderitzarà l'Empty State real de forma amigable, mostrant en Next.js el text: "No tens cap plànol o xarxa tècnica assignada avui" de forma 100% neta, prohibint carregar esquemes simulats o dibuixos de prova.

Àmbit 2: Visor de Plànols, Geoposicionament i Atributs Tècnics

    RF-05 (Event-driven): QUAN l'operari toqui sobre un plànol de la llista (o l'obri directament des de la fulla de tasca segons l'Spec 013), EL SISTEMA obrirà la Finestra d'Edició i Visualització de Plànols a pantalla completa a la PWA, amb suport per a zoom tàctil i desplaçament panoràmic (pan).
    RF-06 (State-driven) — Geoposicionament Actiu en Finca: SI el plànol seleccionat correspon a una finca o parcel·la rústica georeferenciada, ENTONCES EL SISTEMA renderitzarà al visor el botó "Posició GPS actual" (amb icona de mira), el qual situarà un indicador visual de rumb en temps real sobre el punt exacte de la finca on es troba l'operari respecte a les canonades o xarxes del mapa.
    RF-07 (State-driven) — Inhabilitació de GPS en Esquemes: SI el plànol obert correspon a un esquema unifilar elèctric, quadre de comandament, caixa de connexions o croquis d'interior sense georreferenciació real, ENTONCES EL SISTEMA inhabilitarà o ocultarà el botó de posicionament GPS del visor per evitar errors de geolocalització a l'operari.
    RF-08 (Event-driven) — Pop-up d'Atributs Tècnics d'Elements: QUAN l'operari premi sobre un element tècnic d'una capa activa (canonada, vàlvula, hidrant, comptador o línia elèctrica), EL SISTEMA desplegarà una targeta modal emergent amb els atributs tècnics de disseny (ex. "PE-100 Ø90mm — PN 10 bar" o "Cable RZ1-K 0.6/1kV 3x10mm²"), facilitant la identificació de materials abans de cavar.

Àmbit 3: Eines d'Edició de Camp i Marcatge

    RF-09 (Ubiquitous): La finestra d'edició a la PWA mòbil ha de proporcionar una barra d'eines senzilla, tàctil i ergonòmica que inclogui exactament quatre funcionalitats de marcatge de camp:
        Eina de Pins d'Incidència/Anomalia: Permet situar marcadors visuals sobre els punts calents del plànol per obrir de forma adjacent la plantilla d'incidència multimodal de camp, associant-hi fotografies, àudios Whisper i comentaris de text (Spec 016).
        Eina de Traçat Lliure / Línia: Permet dibuixar de forma ràpida desviacions d'obra, noves rases o modificacions d'itinerari de xarxa utilitzant exclusivament un màxim de 4 colors homologats d'enginyeria: Vermell, Blau, Verd i Negre per evitar dibuixos caòtics o confusions.
        Eina de Mesurament de Distàncies: Permet calcular de forma orientativa la distància en metres entre dos punts seleccionats del plànol, mostrant l'etiqueta de text amb l'advertiment del marge d'error del sensor GPS del mòbil: "Aprox. X m".
        Eines de Correcció: Botó de Desfer (Undo) per retirar l'últim traç de línia efectuat i eina de Goma d'esborrar per a netejar manualment línies particulars dibuixades per l'operari.

Àmbit 4: Arquitectura Universal de Capes, Filtres i Generació Ininterrompuda

    RF-10 (Ubiquitous): EL SISTEMA organitzarà i gestionarà tota la informació de disseny i dibuix del plànol (fons cartogràfic base, xarxa de reg hidràulica, línies de baixa tensió, límits de finca, incidències i les pròpies anotacions de camp) com a capes independents filtrables i superposades, garantint l'arquitectura de capes no destructiva.
    RF-10.1 (Event-driven) — Generació de Capes per Anotació (Evitar Col·lisions): QUAN un usuari (operari o enginyer) desi qualsevol esmena o traçat, el sistema generarà automàticament una capa nova independent que contingui el vector i les metadades de traçabilitat: operari_tasca_dia_planol_de_referencia o enginyer_tasca_dia_planol_de_referencia segons correspongui. Aquestes anotacions es pujaran a una cua temporal de sincronització asíncrona, assegurant que cap anotació es perdi ni es sobreescrigui, encara que es realitzin de forma simultània en el mateix mil·lisegon.
    RF-11 (Ubiquitous) — Filtre de Visibilitat i Bloqueig de Supressió: El visor de plànols de la PWA ha de proporcionar un panell desplegable de Selector de Capes que permeti a l'operari commutar de forma individual i independent la visibilitat (visible/invisible, activar o desactivar capes) per a netejar el mapa de soroll visual, bloquejant incondicionalment qualsevol intent d'esborrar o suprimir físicament les capes existents o històriques de traçabilitat.
    RF-12 (State-driven): El selector de capes de fons base permetrà commutar de forma instantània entre la Capa Satèl·lit / Ortofoto PNOA (per a visió aèria de l'entorn real de la finca rústica) i la Capa Vectorial Pura / Fons Blanc (per a màxima visibilitat i contrast d'esquemes en condicions de forta llum solar o brillantor).

Àmbit 5: Capa d'Anotacions As-Built i Traçabilitat de la Tasca

    RF-13 (State-driven) — Desat No Destructiu d'Anotacions (As-Built): Totes les edicions, traços, línies i pins d'incidència creats per l'operari a camp es desaran de forma strictly no destructiva dins de la seva respectiva Capa d'Anotacions de Camp / As-Built independent, de conformitat amb la RF-10.1, mantenint intacte el plànol base original per a posteriors reutilitzacions.
    RF-13.1 (State-driven) — Diàleg d'Esmena sobre Obres Tancades: SI l'operari intenta editar, reescriure o dibuixar una línia sobre una capa que pertany a una ordre de treball o feina ja tancada, facturada o cobrada (Spec 007), ENTONCES EL SISTEMA inhabilitarà la sobreescriptura directa i emetrà immediatament a la PWA un missatge interactiu de diàleg: "Capa tancada, vols crear una capa nova?". Si l'operari confirma la selecció, el sistema crearà automàticament una nova capa activa associant la seva respectiva traçabilitat per a possibiltar la nova anotació sense alterar el registre immutable.
    RF-14 (Event-driven) — Enllaç de Justificació d'Execució a la Fulla de Tasca: QUAN l'operari desi les seves anotacions de camp, EL SISTEMA registrarà automàticament a la fulla de tasca activa de la jornada l'entrada: "Anotació en plànol [Nom del Plànol]" acompanyada d'un enllaç (link) directe de visualització de la capa As-Built com a justificant documental dels treballs.
    RF-15 (Ubiquitous) — Audició i Fusió d'Anotacions As-Built: A la plataforma web de gestió d'oficina (/gestio/planols), EL SISTEMA permetrà a l'enginyer supervisor superposar de forma precisa la Capa d'Anotacions de Camp remesa per l'operari sobre el plànol mestre, facilitant la seva auditoria tècnica per decidir de forma humana (HITL) si es consoliden els canvis de forma oficial.

Àmbit 6: Prevenció de Saturació de Memòria i Formats Suportats

    RF-16 (Ubiquitous): El visor de la PWA mòbil ha de suportar l'obertura i el renderitzat fluid dels formats tècnics d'enginyeria: documents esquemàtics en PDF, imatges ràster comprimides (PNG, JPEG), gràfics vectorials escalables (SVG) i dades geoespacials GeoJSON/KML.
    RF-17 (Unwanted-behaviour) — Alerta de Pes Excessiu de Plànols: Per preservar la memòria RAM del telèfon de l'operari i evitar bloqueigs del terminal, QUAN l'enginyer intenti adjuntar un plànol o mapa rústic amb un pes de fitxer superior a 25 MB (en format ràster sense piràmide de tessel·les), ENTONCES EL SISTEMA bloquejarà la vinculació a l'ordre de treball i mostrarà l'alerta d'error a /gestio/planols: "Plànol massa pesat per a dispositiu mòbil. Si us plau, redueix la resolució o genera tessel·les abans d'assignar-lo", forçant a optimitzar el recurso.

Àmbit 7: Resiliència Offline i Sincronització de Canvis

    RF-18 (State-driven) — Descàrrega Preventiva Automàtica (IndexedDB xifrat): SI una ordre de treball està programada en una finca rural catalogada com a "Zona sense cobertura / Offline", ENTONCES la PWA mòbil de camp executarà de forma preventiva la descàrrega automàtica a la nau del plànol base i les seves capes a la memòria local xifrada d'IndexedDB sota el xifratge de seguretat AES-GCM de 256 bits abans d'iniciar el trajecte.
    RF-19 (State-driven) — Funcionament 100% Offline Autònom: MENTRE la colla es trobi a camp sense cobertura mòbil, EL VISOR de la PWA permetrà obrir el plànol de l'IndexedDB local, navegar, fer zoom fluid, consultar atributs tècnics de canonades, situar pins d'incidència georeferenciats i dibuixar línies de forma completament autònoma i transparent.
    RF-20 (Event-driven) — Sincronització Asíncrona Idempotent de Capes: QUAN el dispositiu mòbil de camp detecti connectivitat cel·lular activa (4G, 5G o Wi-Fi), el Service Worker de la PWA mòbil transmetrà el payload de la Capa d'Anotacions de Camp i els nous pins a la base de dades central de forma asíncrona i idempotent, actualitzant el marcador del mapa de l'oficina en Next.js.

--------------------------------------------------------------------------------
Taula de Casos Límit i Gestió d'Errors
Codi
	
Tipus EARS
	
Mòdul
	
Vector de Falla / Escenari d'Estrès
	
Comportament Requerit del Sistema
EDGE-01
	
Event-driven
	
Concurrència
	
Dos usuaris intenten dibuixar o desar modificacions sobre la mateixa referència de plànol de la finca al mateix mil·lisegon.
	
EL SISTEMA evita pèrdues de traçat i col·lisions de bloqueig; en lloc d'emetre error 409 Conflict o bloquejar per base de dades, cada anotació genera de forma immediata una capa nova independent (amb la traçabilitat: operari/enginyer, tasca, dia i plànol de referència) que s'enclava a la cua de sincronització asíncrona temporal, pujant-se ambdues aportacions de forma neta sense pèrdues d'informació.
EDGE-02
	
State-driven
	
Seguretat
	
S'intenta dibuixar, editar o reescriure una línia sobre una capa que pertany a una tasca ja tancada i facturada (Spec 007 / Spec 010).
	
EL SISTEMA inhabilita la mutació directa del fitxer congelat, obre de forma interactiva el pop-up de confirmació: "Capa tancada, vols crear una capa nova?". Si l'operari confirma, el sistema crea instantàniament una capa activa nova associada al seu respectiu flux i traçabilitat pericial, salvant de forma neta l'edició.
EDGE-03
	
Unwanted
	
PWA Quota
	
El buffer d'imatges d'albarans i fotos d'incidències del plànol de la PWA offline assoleix el límit de quota de seguretat del navegador del mòbil.
	
El Service Worker de la PWA mòbil bloqueja les captures de la càmera, prioritza l'escriptura immutable dels metadades de text del plànol i dels vectors de les canonades, i llança l'alerta crítica de canvi d'estat: "Falta de quota: Conecti a xarxa per buidar fotos locals".
EDGE-04
	
Event-driven
	
GIS
	
Es puja a la biblioteca un fitxer vectorial KML o GeoJSON que conté una projecció rústica local no-WGS84 (ex. ED50).
	
El parser de backend de l'oficina tècnica intercepta la projecció local, utilitza de forma asíncrona la biblioteca pyproj de python per a reprojectar totes les geometries a decimals WGS84, i projecta nítidament la xarxa sobre el mapa.
EDGE-05
	
State-driven
	
Clients
	
Es confirma la baixa lògica (actiu = false) d'un client que manté una biblioteca de plànols i projectes activa a l'empresa.
	
EL SISTEMA oculta les seves carpetes personals del navegador de plànols general, bloqueja noves assignacions de capes, pero preserva el seu historial de plànols i capes immutables sota RLS per a possibles auditories judicials de l'empresa.
EDGE-06
	
Event-driven
	
PWA Sync
	
Dos operaris de camp situen de forma simultània un PIN d'incidència sobre el mateix punt de reg d'un plànol mentre treballen offline.
	
Al sincronitzar, el backend unifica ambdues aportacions a la base de dades de conformitat amb la RF-10.1, generant capes vectorials independents que es guarden amb segell de temps i operari identificats per a la validació de l'Enginyer a la Torre de Control.
EDGE-07
	
Event-driven
	
CAD
	
Es puja a la biblioteca un fitxer CAD DXF que no disposa de coordenades georeferenciades reals en el seu disseny.
	
EL SISTEMA detecta l'absència de georeferenciació i obre el plànol base en format no-georeferenciat al visor, habilitant un formulari on l'Enginyer pot fixar 3 punts de control sobre el mapa per aplicar la translació geomètrica.
EDGE-08
	
Unwanted
	
Celery
	
El worker asíncron de Celery falla o es penja a mig processar l'exportació d'un PDF d'alta resolució.
	
El gestor de cues detecta la fallida del procés, realitza el rollback de la transacció a la bústia de descàrregues, commuta el fitxer a estat FALLIDA i notifica de forma no bloqueiadora a l'oficina tècnica per al reintent.
EDGE-09
	
Event-driven
	
Rendiment
	
Es puja un fitxer GeoJSON molt dens que conté més de 100.000 vèrtexs de xarxa rústica, amenaçant de congelar la PWA de camp.
	
El backend asíncron detecta el volum d'elements, aplica un algorisme de simplificació de traçats de geometries vectorials (Douglas-Peucker) per reduir la mida del payload abans d'enviar-lo a l'IndexedDB del mòbil, mantenint la visualització d'alta precisió només a Next.js web.
EDGE-10
	
Event-driven
	
PWA / Sync
	
La PWA mòbil de camp intenta sincronitzar una Capa d'Anotacions de plànol As-Built a mig camí d'un túnel o zona rústica amb microtalles cel·lulars.
	
El client de sincronització de la PWA aplica la política de reintents exponencials de connexió de forma transparent, reprenent la pujada de dades des de l'últim bit enviat de forma idempotent i evitant la duplicació del registre.
--------------------------------------------------------------------------------
Requisits No Funcionals (RNF)

    Almacenamiento Seguro Soberano Local (Sin AWS S3): Tots els plànols base ràster (PDF, TIFF, PNG), fitxers vectorials, llistats de capes d'obra i imatges de camp s'emmagatzemen exclusivament en repòs mitjançant el xifratge AES-256-GCM en el servidor sobirà Hetzner a Alemanya (UE) sota la ruta de l'inquilí /docs/<empresa_id>/planols/..., amb una validació rigurosa de Magic Bytes (filetype) que rebutja executables i una limitació estricta de 50 MB per fitxer per a estricte compliment de la LOPDGDD i el RGPD.
    Seguridad Multi-Tenant (RLS): Cada crida API de consulta, inserció o eliminació sobre les taules del mòdul de plànols s'aïlla de forma unívoca a nivell de PostgreSQL mitjançant la directiva FORCE ROW LEVEL SECURITY i l'ús de la variable de sessió d'inquilí app.current_empresa_id.
    Rendimiento y Escalabilidad: El temps de resposta del visor de plànols web Next.js no excedirà els 200 ms per a la càrrega i filtre de capes, mantenint una fluïdesa de 60 fps estables mitjançant la desnormalització de coordenades en PostgreSQL i precalculant la capsula delimitadora.
    Diseño Camaleón: La interfície de la biblioteca de plànols adopta de forma dinàmica les variables de marca corporativa (--color-primary, --color-secondary), mentre que els marcadors d'estat de capes mantenen codis cromàtics cartogràfics fixos i de contrast funcional universal.
    Tolerancia Cero a Datos Ficticios (Zero-Mock): Si l'empresa d'alta té 0 registres de plànols, l'arbre de navegació de la biblioteca de plànols es renderitzarà de forma 100% neta i buida (Empty State real), sense cap tipus de registre de prova ni dades simulades d'esquemes.

--------------------------------------------------------------------------------
Fora d'Abast (Out of Scope)

    No és un modelador tridimensional BIM 3D, ni processa fitxers de núvols de punts LiDAR o geometries 3D complexes (excloent-ne la visualització tridimensional).
    No incorpora mòduls de simulació o solvers fluidodinàmics actifs (como EPANET) ni de càlcul de xarxa elèctrica de potència (como CYPE o Caneco).
    No gestiona els visats col·legials telemàtics de projectes davant del col·legi oficial d'enginyers, limitant l'exportació de PDF a un lliurament tècnic d'obra per al client.
    No realitza canvis ni actualitza de forma desatendida o directa la xarxa cartogràfica vectorial mestra sense la validació explícita d'un enginyer supervisor (HITL).
    Queda estrictament exclosa la lectura de codis QR per a plànols i capes en camp, realitzant la traça per selecció de llista o número de sèrie de fàbrica de forma sintonitzada amb l'inventari (Spec 004 / Spec 008).

--------------------------------------------------------------------------------
Criteris de Finalització (Definition of Done) i Matriu de Traçabilitat
Per a poder certificar el tancament de la Spec 017 de Plànols de camp i habilitar la seva fase d'implementació, s'ha de garantir el compliment dels criteris següents:

    Els 20 Requisits Funcionals (RF-01 al RF-20) i els 10 Casos Límit (EDGE-01 al EDGE-10) redactats amb sintaxi formal EARS estricta en català i lliures d'ambigüitats tècniques o dades de prova fictícies sota l'estat Dia 0.
    Correspondència del 100% de la spec de la PWA mòbil amb una suite de proves d'integració automatitzada en verd amb PostgreSQL RLS actiu sota el tenant real d'empresa.
    Alineació total de la política de QR (Constitució v4.0): exclusió absoluta de codis QR per a les eines de camp (les quals es custodien i es traspassen per referència de fàbrica/SN), preservant el QR legal obligatori de facturació Veri*factu per a albarans i factures al tancament.
    Processament asíncron asimètric: integració d'un pipeline en segon pla (Celery + Redis) per a la conversió i simplificació geomètrica de fitxers DXF pesats, evitant bloquejar el event loop de FastAPI.
    Dibuix i traçat amb màxim de 4 colors de camp homologats per al dibuix a camp per ergononía i evitar desviaments visuals.

Matriu de Traçabilitat 1:1 de la Definition of Done (DoD)
Codi de la Spec
	
Cas Límit Vinculat
	
Assert / Criteri de Validació DoD (Zero-Mock)
RF-01 / RF-02
	
EDGE-05
	
Arbre de navegació tabular per clients; intent d'accés de l'operari a plànols d'altres tenants és vetat per RLS.
RF-03
	
-
	
Petició de plànol extra via Incidència; la confirmació és asíncrona i és validada per l'enginyer a la Torre.
RF-04
	
-
	
BD buida d'articles mostra Empty State funcional net de dades de prova mock d'esquemes.
RF-05 / RF-06
	
-
	
Modal a pantalla completa Next.js; botó GPS georeferenciat està actiu en rústic decimals WGS84.
RF-07 / RF-08
	
EDGE-07
	
Fitxer d'esquema unifilar elèctric s'obre en el visor documental Next.js; inabilita GPS de forma transparent.
RF-09
	
EDGE-03
	
Barra d'edició amb pins, regla i 4 colors; error de precisió GPS menor o igual a 15m es marca com a aprox.
RF-10 / RF-10.1 / RF-11
	
EDGE-01
	
Selector de capes; concurrència d'edició genera capes vectorials independents que s'envien a la cua temporal, evitant pèrdues de dades.
RF-12
	
EDGE-04
	
Commutació de fons base; càrrega de KML local (ED50) és reprojectada correctament a WGS84 decimals en base.
RF-13 / RF-13.1
	
EDGE-02
	
Desat As-Built no destructiu; intents de modificar capes d'obres tancades llança pop-up confirmatori i crea una nova capa activa si s'accepta.
RF-14 / RF-15
	
EDGE-06
	
Enllaç d'anotació actiu a la fulla d'obra; pins coincidents de dos operaris es guarden independentment amb timestamps en capes dedicades.
RF-16 / RF-17
	
EDGE-09
	
Visor de formats gràfics; càrrega de GeoJSON de >100k vèrtexs és simplificat per Douglas-Peucker a l'IndexedDB.
RF-18 / RF-19
	
EDGE-10
	
Sincronització de capes; pèrdua de xarxa a mig enviament de la capa és gestionada idempotentment.
RF-20
	
EDGE-08
	
Sincronització asíncrona de pins i mides en recuperar xarxa cel·lular; error de Celery PDF reverteix el lot.