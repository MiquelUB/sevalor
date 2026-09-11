Spec 020 — Mòdul de Càmera Tècnica, Biblioteca d'Imatges de Camp i Sincronització Atòmica a la PWA (/operari/camera) - v2
AVÍS D'ALINEACIÓ CONSTITUCIONAL I INTEGRACIÓ ARQUITECTÒNICA: Aquesta especificació tècnica es regeix de forma innegociable pels principis de la Constitució de CampoPro Suite (v4.0) i s'integra de forma transversal amb el Dashboard i la Torre de Control Geogràfica (Spec 001 i Spec 005), el Mòdul de Clients (Spec 002), el Mòdul de Magatzem i Inventari (Spec 004), el Mòdul de Flota i Vehicles de la PWA (Spec 015), el Mòdul de Treballadors/Operaris (Spec 008), el Mòdul Contable (Spec 007) i el Mòdul d'Incidències de Camp de la PWA (Spec 016).
Es prohibeix taxativament l'ús de dades simulades o de prova (Zero Mock Data), partint d'un estat de "Dia 0" real i garantint de forma absoluta la sobirania de dades mitjançant l'emmagatzematge local/sobirà de les imatges, comprovants i metadades en el servidor Hetzner de Falkenstein (Alemanya - UE), rebutjant completament qualsevol servei de núvol públic extern (com AWS S3) d'acord amb el compliment estricte de la LOPDGDD i el RGPD.
De conformitat amb la Constitució i el criteri de QA unificat, es recorda que s'exclou l'ús de codis QR per a la traçabilitat i transferència d'eines de camp (les quals es gestionen i es custodien nominalment pel seu número de referència, marca, model i número de sèrie de fàbrica sota la Spec 004 i Spec 008). Aquesta exclusió tècnica de camp convive en perfecta harmonia amb la permanència del codi QR legal i tributari requerit obligatòriament a totes les factures i albarans de lliurament oficials (Veri*factu) emesos pel mòdul comptable. Per a la seguretat d'accés, s'autoritza de forma exclusiva l'ús de codis QR de configuració 2FA TOTP (Google Authenticator) durant el procés d'alta o enrolament de l'usuari d'oficina (Spec 011).
--------------------------------------------------------------------------------
Context i Objectiu
El mòdul de Càmera de la PWA (/operari/camera) és la plataforma pericial de captures, control d'evidències tècniques i balanç d'imatges utilitzada pels operaris i caps de colla sobre el terreny. Governat pel principi del "Flujo de los 30 segundos", elimina totalment la fricció burocràtica, optimitzant els controls d'obres, justificació de tiquets de despesa, canvis d'odòmetres i informes de desperfectes de furgonetes de camp en rústic de forma unificada.
Aquest mòdul garanteix:

    Biblioteca centralitzada d'imatges d'alta densitat: Totes les fotografies preses durant la jornada resideixen temporalment a la biblioteca mòbil de la PWA, vinculades unívocament a la seva destinació operativa: fulla de tasca (inicial, intermèdia, final o detall), incidències, vehicles o tiquets de despesa.
    Regla d'or d'integritat fotogràfica (Zero Imatges Orfes): No pot quedar cap imatge sense assignar al final de la jornada. Si l'operari intenta fer el tancament de la jornada havent deixat fotos soltes, el sistema bloqueja el tancament mostrant l'avís de seguretat contable corresponent.
    Eines de llanterna contínua (Torch): Accés ergonòmic directe des del visor de la càmera Next.js per activar la llanterna del telèfon, facilitant la inspecció tècnica d'arquetes, pous, quadres elèctrics foscos o rases fondes.
    Geotagging GPS i Marca Temporal ISO Inalterable: Enregistrament automàtic i pericial de la latitud, longitud i estampat de temps en els fitxers; davant de pèrdues de senyal GPS (soterranis o mines), s'injecta la data/hora ISO de seguretat del dispositiu mòbil.
    Compressió intel·ligent en client a format WebP: Reducció automàtica de pes per sota d'1 MB (mitjançant Web Canvas/Web Worker) abans del desat local a IndexedDB, garantint el mínim consum d'emmagatzematge de quota sense sacrificar la resolució de fallades o lectures OCR.
    Prohibició de càrrega des de Galeries locals (Antifraude): Per seguretat pericial, el visor restringeix de forma rígida l'accés a fitxers antics mitjançant l'ús de controls HTML5 de captura en viu, garantint que tota evidència es prengui sobre el terreny.
    Sincronització per Blocs Atòmics: Les fotografies mai es transmeten soltes o de forma transparent sense justificació; s'envien al servidor Hetzner de forma idempotent agrupades strictly en el seu respectiu bloc d'acció (completar feina, enviar incidència, check-out de flota o tiquets).

--------------------------------------------------------------------------------
Usuaris / Actors i Matriu d'Interacció (Zero-Trust)
Totes les peticions, sincronitzacions i metadades d'imatges estan protegides mitjançant Row Level Security (RLS) a la base de dades PostgreSQL sota la sessió de l'empresa_id de l'operari connectat:

    Operari / Cap de Colla (/operari/camera): Actor de camp principal. Dispara la càmera tècnica, activa la llanterna en zones fosques, valida les captures, assigna fotografies a feines/incidències/vehicles/tiquets, elimina imatges danyades i confirma el tancament de la bústia al vespre.
    Enginyer / Supervisor Tècnic (/gestio): Reclama i audita els blocs d'imatges de les ordres de treball, avaluant la geolocalització, marca temporal i el peritatge d'incidències per a decidir la seva fusió o pressupostació amb dret de HITL.
    Secretaria / Administració: Audita les imatges de tiquets d'urgència i comprovants de caixa encreuats amb les dates i justificants físics de paper.
    Client Final (Canal Telegram / Email): Receptor passiu de les 3 fotografies obligatòries validades (inicial, intermèdia i final) de l'informe d'entrega de feina acabada de la colla.

Matriu de Destinacions d'Assignació
Destinació de l'Assignació
	
Tipologia de Foto Permesa
	
Mòdul de la PWA Vinculat
	
Moment de Sincronització (Bloc Atòmic)
Feina / Tasca Activa
	
Foto Inicial, Intermèdia, Final o Detall
	
/operari/feines (Spec 013)
	
Al prémer "Finalitzar Feina"
Incidència de Camp
	
Prova d'avaria, trencament o obstacle rústic
	
/operari/incidencies (Spec 016)
	
En transmetre la incidència
Flota / Vehicles
	
Odòmetre/horòmetre d'shift o desperfecte
	
/operari/vehicles (Spec 015)
	
Al Check-in / Check-out de la furgoneta
Tiquet de Despesa
	
Comprovant físic de tiquet o albarà de caixa
	
/operari/tiquets (Spec 018)
	
Al tancar el Check-out de tiquets
--------------------------------------------------------------------------------
Requisits Funcionals (EARS Notation)
Àmbit 1: Biblioteca Centralitzada d'Imatges i Estat Buit Sincer (Zero Mock Data)

    RF-01 (Ubiquitous): La pantalla /operari/camera funcionarà com una Biblioteca Centralitzada d'Imatges de Camp, llistant de forma tabular vertical la totalitat de les fotografies preses pel terminal de la colla durant la jornada actual, mostrant per a cadascuna el seu identificador temporal genèric i el seu estat: "Pendent d'assignar" o la destinació adjudicada.
    RF-02 (Unwanted-behaviour) — Estat Buit Sincer (Zero Mock Data): SI la colla d'operaris no ha registrat ni capturat cap fotografia durant el dia de treball actual, ENTONCES EL SISTEMA renderitzarà l'Empty State real de forma amigable, mostrant el text canònic de control d'UX: "No tens cap imatge registrada avui" de forma 100% neta, descartant la visualització de panells negres confussos o injeccions d'imatges dummy de mostra.
    RF-03 (Ubiquitous): Cada fotografia present a la biblioteca mòbil permetrà ser inspeccionada a pantalla completa Next.js en fer-hi clic, renderitzant sobre la imatge una capa de metadades transparent de només lectura amb les dades GPS, marca de temps, autor de la presa i la destinació d'assignació.

Àmbit 2: Assignació Obligatòria i Bloqueig de Tancament de Jornada

    RF-04 (Event-driven): QUAN una imatge es trobi en l'estat "Pendent d'assignar", EL SISTEMA renderitzarà un botó d'acció destacat de "Assignar a...", obrint un selector modal de gran format amb els 4 destins del catàleg regulats:
        Feina / Tasca: Permet enllaçar la foto a l'ordre de treball activa triant l'etiqueta de fase reglada (Foto Inicial, Foto Intermèdia, Foto Final o Foto de Detall).
        Incidència: Permet associar-la de forma adjacent a una incidència en curs o obrir el tiquet d'una nova de conformitat amb la Spec 016.
        Vehicle / Flota: Permet associar-la a l'informe d'avaria de furgoneta o a captures d'odòmetre d'shift segons la Spec 015.
        Tiquet de Despesa: Permet enllaçar el rebut com a justificant de caixa de la colla de la Spec 018.
    RF-05 (Event-driven): EL SISTEMA permetrà a l'operari purgar o eliminar qualsevol fotografia danyada, borrosa o descartada de la biblioteca mitjançant el botó de paperera de la previsualització de Next.js, alliberant de forma immediata l'espai d'IndexedDB de camp.
    RF-06 (State-driven) — Bloqueig Preventiu de Final de Jornada: SI en el moment en què l'operari premi el botó "Finalitzar Jornada Laboral" (Spec 013) existís com a mínim una imatge a la biblioteca mòbil en estat "Pendent d'assignar", ENTONCES EL SISTEMA bloquejarà incondicionalment el tancament de l'shift, mostrant la pantalla d'advertència visual i exigint buidar, assignar o esborrar les imatges soltes abans de permetre el fitxatge legal.

Àmbit 3: Visor de Càmera Tècnica, Llanterna (Torch) i Flux Ergonomic (Numpad)

    RF-07 (Ubiquitous): La interfície del visor de càmera Next.js estarà optimitzada sota el criteri ergonòmic per a ús amb una sola mà, renderitzant botons d'acció ràpida de gran format tàctil aptes per a la seva ràpida pulsació amb dits mullats, bruts o amb guants de camp.
    RF-08 (Event-driven) — Control de Llanterna Contínua (Torch): El visor de la càmera de la PWA mòbil incorporarà un botó flotant d'accés directe per commutar de forma contínua la Llanterna de l'dispositiu mòbil (Torch / Linterna) mitjançant la Web API de vídeo natiu (MediaTrackConstraints.advanced = [{ torch: true }]), facilitant al capataz il·luminar i verificar vàlvules, arquetes, quadres elèctrics o canonades fosques abans de disparar.
    RF-09 (Event-driven) — Previsualització Instantània de Seguretat: Just després de prémer el disparador, EL SISTEMA obrirà el visor de previsualització a un sol clic amb dos controls únics:
        Botó "Acceptar / Guardar": Confirma la presa com a nítida, procedint a la compressió local de l'arxiu i el seu desat a IndexedDB.
        Botó "Repetir": Descarta de forma destructiva la imatge de la memòria volàtil de Next.js i reobre de forma instantània la càmera per a una nova presa, evitant acumular residus de disc.

Àmbit 4: Geotagging GPS d'Obra i Fallback de Seguretat ISO

    RF-10 (Ubiquitous): EL SISTEMA registrarà i incrustarà automàticament de forma inalterable a les metadades de cada imatge capturada la posició GPS exacta (latitud i longitud en decimals WGS84) obtinguda del sensor de geolocalització natiu de la PWA mòbil de camp.
    RF-11 (State-driven) — Fallback per a zones sense Cobertura Satèl·lit: SI el dispositiu de l'operari es troba en un soterrani d'edifici, pou sec profund, mina o rasa rural tancada on no es detecti senyal de satèl·lits GPS actiu, ENTONCES la PWA mòbil bypassarà el bloqueig de geolocalització, registrant de forma atòmica i com a garantia pericial la marca de temps ISO (data, hora, minut i segon UTC) del rellotge de seguretat del dispositiu mòbil a l'expedient.
    RF-12 (Ubiquitous) — Immutabilitat de Metadades: Les variables internes de posició GPS, timestamp ISO de captura i identificador de dispositiu seran d'estricta només lectura i no manipulables pel treballador a la interfície de la PWA mòbil, assegurant la traçabilitat forense de l'obra.

Àmbit 5: Compressió Intel·ligent en Client (WebP) i Resolució Pericial

    RF-13 (Ubiquitous) — Compressió Automàtica en Client a WebP: Abans d'escriure qualsevol arxiu fotogràfic a l'IndexedDB persistent del dispositiu mòbil, la PWA mòbil de camp (utilitzant Web Canvas, Web Workers i mètodes de compressió del navegador) processarà i redimensionarà la imatge comprimint-la en format WebP, amb un límit de pes net de fitxer inferior o igual a 1 MB.
    RF-14 (Ubiquitous) — Assegurament de la Nitidesa Pericial: L'algoritme de compressió (RF-13) aplicarà una ràtio de qualitat que asseguri de forma innegociable la perfecta llegibilitat pericial dels detalls crítics de camp: codis de canonades, lectures de números de sèrie de maquinària (SN), esquerdes o falles físiques i dígits nets d'odòmetres analògics, evitant mermes de visualització.
    RF-15 (State-driven): Tota imatge comprimida per la PWA es desarà localment a l'IndexedDB xifrada de camp mitjançant el xifratge simètric AES-GCM de 256 bits (utilitzant claus derivades pel PBKDF2 del PIN d'accés de l'operari de la Spec 019), garantint el Zero-Trust davant pèrdues de terminals.

Àmbit 6: Controls de Càmera de Camp, Permisos i Càrrega de Galeria

    RF-16 (State-driven): SI el navegador de la PWA mòbil o el sistema operatiu del terminal mantenen blocat el permís d'accés físic a la càmera de fotos, ENTONCES la PWA inhabilitarà el visor i renderitzarà una pantalla explicativa clara de bloqueig amb instruccions tècniques per a activar el sensor als ajustos.
    RF-17 (Unwanted-behaviour) — Prohibició de Càrrega des de Galeries locals (Antifraude): EL SISTEMA restringirà strictly l'accés a fitxers o imatges desades de forma local a la galeria interna o àlbums del dispositiu mòbil per evitar fraus o càrrega d'evidències de dies anteriors. Per a complir aquesta clàusula, l'input HTML5 de captura utilitzarà de forma mandatoria els atributs exclusius accept="image/*" capture="environment", forçant a obrir strictly la càmera nativa en temps real.
    RF-18 (Event-driven) — Reset de Carret al Tancament de Jornada: QUAN s'hagi validat de forma correcta la sincronització de la totalitat dels tiquets, ordres de treball i vehicles de la colla al servidor Hetzner de l'empresa, la PWA mòbil d'operaris executarà la purga destructiva de la biblioteca temporal /operari/camera de l'IndexedDB local, deixant l'aplicació mòbil neta de fitxers temporals per a la jornada de l'endemà.

Àmbit 7: Sincronització per Blocs Atòmics i Seguretat de Red

    RF-19 (Unwanted-behaviour) — Prohibició d'Imatges Orfes o Transmeses Soltes: EL SISTEMA té la prohibició absoluta de transmetre o sincronitzar fotografies de camp de forma independent o solta al backend; tota imatge s'enviarà de forma unificada i adjacent en el seu corresponent lot d'acció.
    RF-20 (State-driven) — Sincronització per Blocs Atòmics d'Acció: La transmissió de fotografies comprimides cap al servidor central de Hetzner s'activarà strictly en format de Bloc Atòmic sota les següents directrius exclusives d'acció de la PWA mòbil de camp:
        Les fotos de tasca es transmeten strictly en prémer "Finalitzar Feina" (Spec 013).
        Les fotos d'incidència es transmeten strictly en prémer "Enviar Incidència" (Spec 016).
        Les fotos de vehicle es transmeten strictly al confirmar el Check-in o Check-out de Flota (Spec 015).
        Les fotos de tiquet es transmeten strictly en executar el Check-out de despeses de camp (Spec 018).
    RF-21 (State-driven) — Retenció en IndexedDB davant pèrdues de xarxa: SI la colla d'operaris opera en rústic profunda sense connectivitat de dades mòbils, ENTONCES la PWA mòbil retindrà de forma segura les imatges a l'IndexedDB local, i el Service Worker de camp forçarà la seva sincronització de dades de forma idempotent un cop recuperat el senyal i confirmat el tancament del bloc operatiu.

Àmbit 8: Flux de Captura Secuencial de Repostatges de Combustible (Antifraude)

    RF-22 (State-driven) — Protocol de Doble Foto de Repostatge de Carburant: SI l'operari de la PWA mòbil de camp selecciona la categoria de despesa Carburant (Spec 015 / Spec 018) per a registrar un proveïment de combustible, ENTONCES la PWA mòbil guiarà l'operari a través d'un flux de captura secuencial obligatori:
        El visor s'obrirà per demanar de forma exclusiva la Foto 1 (Tiquet de servei de benzinera).
        Un cop validada la primera captura, la PWA mòbil llançarà de forma atòmica i automàtica el segon visor sol·licitant la Foto 2 (Odòmetre en viu del vehicle tractor).
        EL SISTEMA empaquetarà ambdues imatges sota un únic codi d'identificació de bloc de carburant transaccional, impedint que el tiquet quedi com a imatge orfe o deslligada.

--------------------------------------------------------------------------------
Taula de Casos Límit i Gestió d'Errors
Codi
	
Tipus EARS
	
Mòdul
	
Vector de Falla / Escenari d'Estrès
	
Comportament Requerit del Sistema
EDGE-01
	
Unwanted
	
PWA Càmera
	
L'operari ha pres captures de camp ràpides al matí i se n'ha oblidat; a la tarda prem "Finalitzar Jornada Laboral".
	
La PWA mòbil de camp bloca incondicionalment el tancament, destaca l'advertència visual i emet l'alerta: "Imatges sense assignar, assigna abans de tancar". L'operari ha d'accedir a /operari/camera, assignar els recursos o esborrar-los de forma explícita per a desbloquejar l' shift.
EDGE-02
	
State-driven
	
PWA Càmera
	
Es realitza la captura visual d'una vàlvula a l'interior d'un pou cec profund o soterrani rústic sense cap senyal de satèl·lit GPS actiu.
	
La PWA mòbil intercepta el fallback del sensor, desactiva el bloqueig de georreferenciació, incrusta de forma automàtica la marca de temps ISO de seguretat de ràdio-frecuencia (UTC) del terminal mòbil a les metadades i permet desar la imatge de forma neta i pericial.
EDGE-03
	
Unwanted
	
PWA Càmera
	
L'operari pren la fotografia d'un tiquet de caixa de ferreteria o odòmetre en moviment de forma borrosa, moguda o il·legible.
	
Al visor de previsualització instantània, l'operari detecta la feble qualitat i pitja el botó "Repetir"; el sistema purga de forma destructiva l'arxiu danyat de la RAM i de Next.js i reobre de forma síncrona el visor de la càmera per a una presa nítida.
EDGE-04
	
Event-driven
	
PWA Càmera
	
Es requereix fotografiar la connexió d'un comptador d'aigua en rústic profund o habitació tancada en condicions de foscor absoluta.
	
L'operari pitja el botó de llanterna contínua (Torch) al visor; el sistema commuta de forma immediata l'estat del flaix de forma permanent via Web API, il·luminant l'habitació i possibilitant l'enfocament tècnic precís abans de disparar.
EDGE-05
	
Unwanted
	
PWA Càmera
	
El telèfon de l'operari es queda sense bateria o s'apaga intempestivament a mig camí de comprimir la imatge o desar-la en IndexedDB.
	
En reiniciar-se el terminal mòbil i obrir la PWA, el sistema detecta la inconsistència del bloc temporal a IndexedDB local, restaura el visor inactiu i demana a l'operari fer de nou la presa de seguretat sense generar fitxers danyats de 0 bytes.
EDGE-06
	
Unwanted
	
PWA Càmera
	
El navegador de camp mòbil de l'operari bloca les captures de la càmera a IndexedDB per haver-se exhaurit la quota de seguretat de dades (memòria interna plena).
	
El Service Worker de la PWA mòbil de camp bloqueja de forma local les captures de la càmera, prioritza de forma immutable l'escriptura de dades de text i cotes del plànol de pocs bytes, i llança l'alerta explicativa visual de canvi d'estat: "Falta de quota: Conecti a xarxa per buidar fotos locals".
EDGE-07
	
State-driven
	
Seguretat
	
Es confirma la baixa lògica (actiu = false) d'un operari de camp que té fotos de tiquets o d'obres pendents de sincronització a l'IndexedDB local.
	
El Service Worker de la PWA mòbil de camp intercepta la revocació del token JWT de Redis, bloqueja qualsevol transacció d'API, purga de forma destructiva l'IndexedDB local sencera (fotos, comprovants, plànols, claus, accessos) i tanca la sessió a l'acte per privacitat de dades de l'inquilí.
EDGE-08
	
Unwanted
	
PWA Càmera
	
Es detecta un intent de d'injectar text maliciós o injeccions SQL/XSS camuflats a les metadades EXIF d'una fotografia de camp.
	
El backend de l'API de CampoPro rep el fitxer a Hetzner, analitza sota Celery el payload del document, purga i neteja de forma de forma atòmica qualsevol etiqueta o camp de comentari d'usuari a les metadades de la imatge, i llança un log al SIF.
EDGE-09
	
Unwanted
	
Seguretat
	
Un usuari amb rol Operari intenta invocar directament via Postman o petició externa la pujada o escriptura d'imatges d'un altre tenant d'empresa.
	
PostgreSQL i el middleware del backend de l'API de CampoPro interposen de forma immediata la directiva de Row Level Security (FORCE ROW LEVEL SECURITY sota app.current_empresa_id) i bloquegen de forma atòmica la petició retornant un error HTTP 403 Forbidden.
EDGE-10
	
Event-driven
	
PWA Sync
	
Es demana sincronitzar un bloc massiu de 10 fotografies WebP comprimides de tancament d'obra, però la xarxa cel·lular presenta microtalles o canvis de 3G/4G.
	
El client de sincronització asíncrona de la PWA mòbil de camp (tenacity) aplica de forma idempotent la política de reintents exponencials de connexió de forma transparent, reprenent la pujada de dades des de l'últim byte confirmat sense pèrdues de dades i evitant duplicacions al backend.
--------------------------------------------------------------------------------
Requisits No Funcionals (RNF)

    Almacenamiento Seguro Soberano Local (Sin AWS S3): Totes les fotografies d'evidències d'obra, captures d'odòmetres, tiquets de despeses de camp i imatges d'incidències es guarden exclusivament de forma xifrada en repòs mitjançant el xifrat AES-256-GCM en el servidor sobirà Hetzner a Alemanya (UE) de l'inquilí sota la ruta /docs/<empresa_id>/planols/evidencies/ per a obres i /data/<empresa_id>/imatges/incidencies/ per a incidències de la Spec 016, rebutjant completament AWS S3 per a estricte compliment del RGPD.
    Seguridad Multi-Tenant (RLS): Cada consulta, actualització o modificació aplicada sobre les taules d'imatges i metadades es realitzarà sota el Row Level Security (RLS) mandatori a nivell de PostgreSQL mitjançant la variable d'inquilí app.current_empresa_id de forma síncrona i innegociable.
    Velocitat de Resposta i Latència: El llistat d'imatges de la biblioteca mòbil respondrà de forma asíncrona en Next.js en un temps inferior a 150 ms, processant les fotografies del client en WebP abans de fer el push a l'API per a optimització de red.
    Diseño Camaleón: La interfície de la biblioteca de càmera i el selector modal adopten de forma dinàmica les variables de marca corporativa (--color-primary, --color-secondary) definides a la Spec 011, previsualitzant els estats sota codis de color fixos d'alta visibilitat.
    Tolerancia Cero a Datos Ficticios (Zero-Mock): Si l'empresa d'alta té 0 registres d'imatges, la llista de la biblioteca de camp es renderitzarà de forma 100% neta i buida sota Next.js (Empty State real), sense inserir dades demostratives ni fotos de prova.

--------------------------------------------------------------------------------
Fora d'Abast (Out of Scope)

    No és un mòdul d'edició estètica de fotos, ni realitza retocs de color, modificacions de brillantor, ni aplica filtres artístics sobre els comprovants o obres.
    No realitza la compressió d'imatges en el servidor web; per a optimització de red i d'emmagatzematge, el processat a WebP es realitza strictly de forma síncrona en el client mòbil abans de qualsevol desat local.
    No gestiona de forma directa l'enviament de fotografies de desperfectes a les companyies d'assegurances de flota (es limita a allotjar el fitxer a l'expedient del vehicle de la Spec 006).
    No s'admeten dades de prova ni fotografies d'exemple d'arquitectura sota cap concepte (Zero Mock Data).

--------------------------------------------------------------------------------
Criteris de Finalització (Definition of Done) i Matriu de Traçabilitat
Per a poder certificar el tancament de la Spec 020 de Càmera de camp i habilitar la seva fase d'implementació, s'ha de verificar el compliment estricte de la següent matriu de traçabilitat:

    Els 22 Requisits Funcionals (RF-01 al RF-22) i els 10 Casos Límit (EDGE-01 al EDGE-10) redactats amb sintaxi formal EARS estricta en català i lliures d'ambigüitats tècniques o dades de prova fictícies sota l'estat Dia 0.
    Correspondència del 100% de la spec de càmera amb una suite de proves d'integració automatitzada en verd amb PostgreSQL RLS actiu sota el tenant d'empresa de CampoPro.
    Alineació total de la política de QR (Constitució v4.0): exclusió absoluta de codis QR per a les eines de camp (les quals es custodien i es traspassen per referència de fàbrica/SN), preservant el QR legal obligatori de facturació Veri*factu per a albarans i factures al tancament de l'obra.
    Enrolament de Càmera en captures en viu obligatòries: implementació del control d'input programàtic accept="image/*" capture="environment" (RF-17), bloquejant l'accés a galeries locals del mòbil.
    Empty State explícit sota Zero-Mock: la biblioteca de càmera sense registres mostrarà un Empty State interactiu i de gran format, descartant pantalles fosques o injeccions.

Matriu de Traçabilitat 1:1 de la Definition of Done (DoD)
Codi de la Spec
	
Cas Límit Vinculat
	
Assert / Criteri de Validació DoD (Zero-Mock)
RF-01 / RF-02
	
EDGE-09
	
Selector de biblioteca Next.js; intent de d'accés des d'altres tenants és vetat per RLS.
RF-03
	
-
	
BD buida d'imatges de la jornada llança Empty State lliure de dades hardcodejades.
RF-04 / RF-05
	
EDGE-01
	
Selector d'assignació d'imatges actiu; eliminació de preses de la biblioteca mòbil de camp.
RF-06
	
EDGE-01
	
Bloqueig de tancament de jornada si es detecten imatges orfes sense destí; atura l' shift de la Spec 013.
RF-07 / RF-08
	
EDGE-04
	
Visor de càmera Next.js ergonòmic; botó de llanterna activa contínuament el led mitjançant la Web API Torch.
RF-09
	
EDGE-03
	
Previsualització instantània de tret; repetir purga l'arxiu mogut de la RAM Next.js sota transacció neta.
RF-10 / RF-11
	
EDGE-02
	
Geotagging automàtic GPS decimals WGS84; pèrdua de senyal en pou incrusta marca temporal ISO de seguretat.
RF-12
	
-
	
Metadades EXIF (GPS, temps, model) són d'estricta només lectura, bloquejant qualsevol mutació d'usuari.
RF-13 / RF-14
	
EDGE-05
	
Compressió en client a WebP <1MB; control de ràtio de qualitat preserva llegibilitat de falles d'obra o d'odòmetres.
RF-15
	
-
	
Desament de fotos xifrat amb AES-GCM de 256 bits a l'IndexedDB persistent derivat pel PBKDF2 del PIN d'accés.
RF-16 / RF-17
	
EDGE-08
	
Avís de càmera bloquejada; input HTML5 capture="environment" inhabilita la galeria del terminal (Antifraude).
RF-18
	
EDGE-07
	
Reset de carret de la PWA mòbil en finalitzar la jornada; baixa lògica de l'operari purga l'IndexedDB de forma destructiva.
RF-19 / RF-20
	
EDGE-10
	
Prohibició de fotos soltes; la pujada s'executa strictly com a part integrant del Bloc Atòmic del mòdul finalitzat.
RF-21
	
EDGE-05
	
Retenció local de fotos en IndexedDB xifrada offline; microtalles de red cel·lular són resoltes de forma idempotent.
RF-22
	
EDGE-03
	
Flux de repostatge secuencial de carburant exigeix Foto 1 (Tiquet) i Foto 2 (Odòmetre) de forma atòmica i indissoluble.