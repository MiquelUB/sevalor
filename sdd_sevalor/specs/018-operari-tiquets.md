Spec 018 — Mòdul de Captura, Gestió i Check-out de Tiquets de Despesa a la PWA (/operari/tiquets) - v2
AVÍS D'ALINEACIÓ CONSTITUCIONAL I INTEGRACIÓ ARQUITECTÒNICA: Aquesta especificació tècnica es regeix de forma innegociable pels principis de la Constitució de CampoPro Suite (v4.0) i s'integra de forma transversal amb el Dashboard i la Torre de Control de Camp (Spec 001 i Spec 005), el Mòdul de Clients (Spec 002), el Mòdul de Proveïdors (Spec 003), el Mòdul de Magatzem (Spec 004), el Mòdul de Flota (Spec 006), el Mòdul d'Operaris (Spec 008), el Mòdul Contable (Spec 007) i el Mòdul de Flota de la PWA mòbil (Spec 015).
Es prohibeix taxativament l'ús de dades simulades o de prova (Zero Mock Data), partint d'un estat de "Dia 0" real i garantint de forma absoluta la sobirania de dades mitjançant l'emmagatzematge local/sobirà dels expedients de tiquets, imatges de comprovants i metadades en el servidor Hetzner de Falkenstein (Alemanya - UE), rebutjant completament qualsevol servei de núvol públic extern (como AWS S3) d'acord amb el compliment estricte de la LOPDGDD i el RGPD.
De conformitat amb la Constitució i el criteri de QA unificat, es recorda que s'exclou l'ús de codis QR per a la traçabilitat i transferència d'eines i vehicles de camp (les quals es gestionen i es custodien nominalment pel seu número de referència, marca, model i número de sèrie de fàbrica sota la Spec 004, Spec 006 i Spec 008). Aquesta exclusió tècnica convive en perfecta harmonia amb la permanència del codi QR legal i tributari requerit obligatòriament a totes les factures i albarans de lliurament oficials (Veri*factu) emesos pel mòdul comptable.
--------------------------------------------------------------------------------
Context i Objectiu
El mòdul de Tiquets de la PWA (/operari/tiquets) és la sub-interfície de despeses de camp, registre ràpid de rebuts de combustible i justificació de despeses menors de la quadrilla. Està dissenyat estrictament sota el principi ergonòmic del "Flujo de los 30 segundos": l'operari no ha de teclejar dades manualment a la pantalla del telèfon mòbil en condicions de forta brillantor o fred; només selecciona de forma tàctil la tipologia, fa la fotografia del comprovant físic i continua amb la feina ordinària.
Aquest mòdul garanteix:

    Tipologies completes de despesa: Compra de material d'urgència / Ferreteria (imputat a obra), Peatges / Pàrquings (desplaçaments), Dietes / Àpats de camp (despeses generals), Carburant (flota) i un camp obert d'Altres per a imprevistos justificats de ruta.
    Captura ràpida amb suport per a segona imatge condicional: Botó d'accés directe a la càmera del telèfon, amb capacitat per adjuntar una segona fotografia condicional (ex. comptaquilòmetres del vehicle en carburant de conformitat amb la Spec 015, albarà de lliurament de la ferreteria o justificant de descàrrega de residus).
    Zero camps obligatoris de tecleig per l'operari (OCR d'assistència): El motor d'OCR (executat en segon pla al servidor Hetzner) processarà la imatge, extreient automàticament l'import net en euros, la data d'emissió, el NIF de l'establiment i el concepte d'adquisició de forma transparent.
    Reanomenament dinàmic de fitxers sense col·lisions (Multi-Tenant): La imatge es puja amb un identificador temporal; en processar-se l'OCR, el backend de l'API renomena el fitxer sota l'estàndard d'auditoria unificat per a evitar col·lisions entre tenants.
    Evitació de saturació de memòria RAM (Llista lleugera): La safata del dia no carrega miniatures de fotos a la memòria del telèfon mòbil de l'operari, mostrant únicament l'estat del tiquet i el nom del fitxer descriptiu com a confirmació de sincronització asíncrona.
    Estat buit amigable sota Zero Mock Data: Si l'operari no ha registrat cap comprovant, es mostra un Empty State real i clar amb el text canònic: "No tens cap tiquet registrat avui", prohibint finestres fosques que indueixin a pensar en errors de l'aplicació.
    Sintonització de control de límit de seguretat (100 €/dia): Si una compra requereix superar el límit de la targeta de camp de la quadrilla, es genera una incidència de tiquet de camp que bloqueja l'aprovació automatitzada de la despesa fins que Secretaria o el Boss l'autoritzen des d'oficina.
    Protocol de Check-out diari i lliurament físic: Al final de la jornada a la base, l'operari executa el tancament de despeses de camp, rep el recordatori de dipositar els comprovants físics de paper a la bústia de seguretat de Secretaria i la PWA mòbil executa un reset complet buidant la safata per a la següent jornada.
    Resiliència total Offline-First: Tot el cicle opera sobre IndexedDB mòbil xifrat amb AES-GCM 256 bits, comprimint imatges en client a format WebP i sincronitzant-les idempotentment en recuperar cobertura cel·lular.

--------------------------------------------------------------------------------
Usuaris / Actors i Matriu d'Interacció (Zero-Trust)
Totes les dades de tiquets i moviments de caixa estan aïllades a nivell de base de dades PostgreSQL mitjançant Row Level Security (RLS) sota l'inquilí autenticat (empresa_id).

    Operari / Cap de Colla (/operari/tiquets): Actor de camp principal. Selecciona la categoria, fa la foto del comprovant, adjunta la segona foto condicional, associa el tiquet a una de les tasques del dia, custodia el paper físic de la transacció i confirma el Check-out de despeses al vespre.
    Secretaria / Administració: Responsable principal de la bústia de tiquets. Recull els comprovants de paper físics de la bústia de base, valida la concordança de les dades amb les lectures del motor d'OCR, resol incidències de tiquets il·legibles o desclou desglossaments mixtos, i tramita augments excepcionals de límit de targeta.
    Enginyer / Supervisor Tècnic (/gestio/feines): Consulta els tiquets de materials i ferreteria imputats per la quadrilla a cadascuna de les seves obres per a determinar amb exactitud el cost real del projecte, mantenint el veto complet de la Spec 007 a la resta del router financer d'oficina.
    Gerència (Boss): Supervisa el volum acumulat de despeses del parc mòbil de camp, autoritza tancaments d'incidències per excedències superiors al límit diari i audita desviacions de caixa analítiques.

Matriu de Responsabilitats per Categoria de Despesa
Tipologia de Tiquet
	
Captura Operari
	
Segona Imatge Condicional
	
Imputació Comptable Mestre
	
Resolució d'Incidència / Límit
Ferreteria / Material
	
Foto comprovant obligatòria
	
Opcional (Albarà signat de camp)
	
Imputat a l'Obra d'origen (compte 60X)
	
Si >100 €, demana autorització central
Peatges / Pàrquings
	
Foto comprovant obligatòria
	
No requerida
	
Despesa de desplaçament / Obra
	
Validada per Secretaria
Dietes / Àpats de Camp
	
Foto comprovant obligatòria
	
No requerida
	
Segregada a Despeses Generals (629)
	
Supervisada segons conveni
Carburant (Dièsel / AdBlue)
	
Foto comprovant obligatòria
	
Obligatòria (Odòmetre/Km PWA)
	
Imputada a Flota / Vehicle (Spec 006)
	
Encreuada amb odòmetre final de PWA
Altres Contingències
	
Foto justificant obligatòria
	
Opcional
	
Determinada per Administració
	
Revisada cas per cas pel Boss
--------------------------------------------------------------------------------
Requisits Funcionals (EARS Notation)
Àmbit 1: Interfície de Captura, Tipologies de Despesa i Estat Buit (Zero-Mock)

    RF-01 (Ubiquitous): La pantalla /operari/tiquets renderitzarà a la capçalera superior un selector ràpid de categories de despesa format de manera tàctil per a ús amb guants, compost exclusivament per cinc opcions: a) Ferreteria / Material d'Urgència, b) Peatges / Pàrquings, c) Dietes / Àpats, d) Carburant i e) Altres.
    RF-02 (Ubiquitous): La interfície mostrarà un botó prominent i de fàcil accés d'activació directa de la Càmera del dispositiu mòbil per a la captura instantània del rebut o tiquet de paper.
    RF-03 (Unwanted-behaviour) — Estat Buit Sincer (Zero Mock Data): SI la colla d'operaris no ha registrat cap tiquet o despesa durant la jornada de treball actual, ENTONCES EL SISTEMA renderitzarà l'Empty State de forma neta i amigable, mostrant el text canònic de control d'UX: "No tens cap tiquet registrat avui", descartant llistes completament buides o injeccions de dades simulades.

Àmbit 2: Protocol Fotogràfic i Segona Imatge Condicional

    RF-04 (Event-driven): QUAN l'operari premi el botó de càmera de la PWA, EL SISTEMA obrirà el sensor de captura fotogràfic, obligant a capturar la imatge en format horitzontal o vertical d'alta nitidesa.
    RF-05 (State-driven) — Segona Foto Obligatòria de Carburant: SI la categoria de despesa seleccionada és Carburant, ENTONCES EL SISTEMA bloquejarà incondicionalment el botó "Desar Tiquet", exigint de forma prèvia capturar la segona fotografia condicional obligatòria de l'odòmetre del vehicle en el instant exacte del repostatge, garantint la traçabilitat analítica exigida a la Spec 006 i 015.
    RF-05.1 (Event-driven): Per a la resta de categories, EL SISTEMA habilitará de forma completament opcional el botó d'afegir segona imatge (ex. foto de l'albarà signat de ferreteria o justificant del peatge de l'autopista) per a suport de Secretaria, permetent desar la despesa amb una sola imatge si no és carburant.
    RF-06 (Unwanted-behaviour) — Absència de Camps Manuals de Tecleig a Camp: Per estricte compliment de l'ergonomia en mobilitat, EL SISTEMA prohibirà i denegarà qualsevol formulari que demani teclejar manualment de forma obligatòria l'import, la data o el NIF del tiquet a l'operari; el cap de colla es limitarà exclusivament a fotografiar i desar per no aturar el ritme de treball a camp.

Àmbit 3: Extracció OCR en Segon Pla, Segregació de Multitenancy i Noms de Fitxer

    RF-07 (State-driven): Al desar-se la imatge del tiquet a la PWA, EL SISTEMA li assignarà inicialment un identificador temporal genèric compost pel timestamp (ex. tiquet_tmp_[timestamp].jpg) i el mostrarà a la llista de camp en estat "Pendent de processament" com a confirmació de recepció de l'arxiu.
    RF-08 (Event-driven) — Ingesta asíncrona i Reanomenament Criptogràfic d'Auditoria: QUAN el dispositiu del operari recuperi la connexió de dades mòbils, el Service Worker enviarà l'arxiu a la base. El backend processarà la imatge utilitzant el motor OCR de Copilot IA per extreure: l'import net final (€), el nom fiscal del proveïdor, el NIF de l'emissor i la data real de la transacció, executant les directrius següents:
        Aïllament de Disc: Emmagatzemar el comprovant físic sota xifratge en repòs AES-256-GCM en el directori sobirà local d'Hetzner sota la ruta de l'inquilí: /docs/<empresa_id>/tiquets/.
        Evitació de Col·lisions: Reanomenar el fitxer al disc de forma unívoca utilitzant un UUID de seguretat sota l'estàndard d'auditoria: [empresa_id]_[UUID_tiquet]_[proveidor]_[import]_[data].jpg de forma 100% transparent.
        Actualització del Visor: Sincronitzar el nom de l'arxiu amigable a la llista de la PWA de l'operari substituint el nom temporal genèric (ex. Ferreteria_Garcia_45.20EUR_1410.jpg).
    RF-08.1 (State-driven) — Desglossament de Repostatges Mixtos: SI l'OCR de Copilot IA detecta que el tiquet de la gasolinera correspon a una despesa mixta de carburant tèrmic (dièsel) i líquid AdBlue de forma conjunta (Spec 015 EDGE-10), ENTONCES el backend de l'API bloquejarà la integració automatitzada de la despesa al consum mitjà de Flota i marcarà el tiquet en estat "Pendent de desglose manual", obligant a Secretaria a segregar ambdós conceptes abans de consolidar-los.
    RF-09 (Ubiquitous): Per garantir la màxima celeritat d'ús i evitar col·lapsar la memòria RAM del telèfon mòbil de l'operari, la llista de tiquets de la PWA mòbil no renderitzarà miniatures gràfiques de les fotografies pujades, mostrant de forma exclusiva el text de l'estat i el nom del fitxer.

Àmbit 4: Vinculació Flexible a Tasca i Segregació de Despeses

    RF-10 (Ubiquitous): La pantalla /operari/tiquets ha de permetre vincular qualsevol tiquet de materials o ferreteria a una de les ordres de treball actives de la colla mitjançant un selector de caselles (check) que llisti les tasques assignades del dia (Tasca A, Tasca B, Tasca C).
    RF-11 (Ubiquitous): Els tiquets corresponents a Dietes / Àpats de camp i Carburants s'han de processar de forma completament segregada de les obres, quedant dipositats a la safata d'Administració perquè la comptabilitat central en determini la imputació a despeses generals d'explotació (compte 629/62X) o a la rendibilitat d'un projecte en particular sota directiva de RLS.

Àmbit 5: Mètodes de Pagament i Incidències per Límit de Seguretat (>100 €/dia)

    RF-12 (Ubiquitous): La PWA mòbil de camp permetrà seleccionar el mètode de pagament realitzat per la colla, mostrant exclusivament els autoritzats per l'empresa: Targeta de Camp corporativa, Targeta Solred/DKV, Efectiu de caixa o fons de maniobra.
    RF-13 (State-driven) — Control de Límit diari de Camp: SI l'import detectat del tiquet supera el llindar diari de seguretat configurat per a la targeta de camp de la quadrilla (límit estàndard de 100 €/dia), ENTONCES EL SISTEMA bloquejarà l'actualització automàtica del saldo i generarà la "Incidència de Tiquet per Excedència de Límit", commutant la conversa amb el client a /gestio/notificacions en blau i bloquejant la targeta del furgó fins que Secretaria/Boss n'elevin el límit des d'oficina.

Àmbit 6: Protocol de Check-out Diari i Custòdia Física del Paper

    RF-14 (Ubiquitous): L'operari té l'obligació reglamentària de custodiar físicament tots els tiquets de paper originals capturats durant la jornada laboral de camp.
    RF-15 (Event-driven): Al final de la jornada de treball en retornar a la nau central de base, l'operari accedirà a /operari/tiquets i pitjarà de forma conscient el botó "Confirmar Check-out de Tiquets".
    RF-16 (State-driven): QUAN l'operari premi el botó de Check-out, la PWA mòbil renderitzarà un diàleg modal de gran format mostrant el recompte total (ex. "Check-out de despeses: 3 tiquets processats correctament avui. Total: 64,80 €") i llançarà l'avís de seguretat contable: "Recorda dipositar els tiquets físics de paper originals a la bústia de seguretat de Secretaria per a la seva revisió i tancament d'auditoria".

Àmbit 7: Incidències per comprovació manual i paper deteriorat

    RF-17 (State-driven) — Fallida de Lectura OCR per paper gastat: SI el comprovant de paper tèrmic es troba arrugat, deteriorat o presenta taques d'oli de furgoneta que impedeixin al motor d'OCR de la IA de base llegir els camps amb una fiabilitat superior al 70%, ENTONCES la PWA mòbil de camp registrarà la "Incidència de Tiquet per Comprovació Manual".
    RF-18 (Ubiquitous): La incidència per comprovació manual alertarà immediatament a la bústia de Secretaria de l'oficina central amb l'avís: "El motor d'OCR no ha pogut llegir el tiquet per mal estat del paper. Comprovació manual requerida sobre el comprovant de paper físic dipositat al Check-out de la colla", evitant bloquejos in situ al operari a camp.

Àmbit 8: Resiliència Offline-First, IndexedDB i Reset de la PWA

    RF-19 (State-driven) — Emmagatzematge Local xifrat (IndexedDB): SI l'operari registra o afegeix un tiquet de despesa en una parcel·la rural sense cobertura de xarxa, la PWA mòbil de camp encriptarà i emmagatzemarà la imatge WebP i les metadades localment a l'IndexedDB sota el xifratge de seguretat AES-GCM de 256 bits per protegir la integritat d'informació financera.
    RF-20 (State-driven) — Bloqueig Preventiu de Reset: EL SISTEMA inhabilitarà de forma ràpida i bloquejarà el Reset automàtic de la PWA si es detecta algun arxiu de tiquet pendent de transmissió o si el Service Worker no ha confirmat l'emissió del 100% de la bústia local cap al servidor Hetzner, evitant qualsevol pèrdua accidental de justificants de despesa.
    RF-21 (Event-driven): QUAN l'operari hagi completat el Check-out i s'hagi garantit la salvaguarda total dels arxius al servidor de l'empresa, la PWA mòbil d'operaris executarà un reset atòmic i complet de la safata /operari/tiquets, eliminant els temporals IndexedDB de camp de forma destructiva per seguretat multi-tenant i deixant la llista completament en blanc per a la jornada de l'endemà.

--------------------------------------------------------------------------------
Taula de Casos Límit i Gestió d'Errors
Codi
	
Tipus EARS
	
Mòdul
	
Vector de Falla / Escenari Límit
	
Comportament Requerit del Sistema
EDGE-01
	
Unwanted
	
PWA OCR
	
El comprovant tèrmic de la gasolinera està tacat d'oli o gastat pel sol, fent-se il·legible per a l'OCR.
	
El sistema no bloquejarà la jornada de l'operari; desa el fitxer i emet la Incidència de Tiquet per Comprovació Manual a la bústia de Secretaria perquè verifiqui el paper físic lliurat a la bústia de base.
EDGE-02
	
Unwanted
	
Targetes
	
Una compra de ferreteria d'urgència de 320 € supera el llindar preventiu de seguretat de 100 € de la targeta de camp de la colla.
	
La PWA mòbil bloqueja la confirmació directa i genera la Incidència de Tiquet per Excedència de Límit dirigida a Secretaria i Boss. La targeta del furgó es manté bloquejada a la base de dades fins que RRHH/Supervisor autoritzi l'ampliació extraordinària de crèdit.
EDGE-03
	
Unwanted
	
Carburant
	
L'operari registra un repostatge de dièsel a la gasolinera però oblida capturar la segona fotografia de l'odòmetre requerida.
	
La PWA mòbil bloqueja incondicionalment el botó de desar i llança l'avís visual a la pantalla: "Despesa de carburant: S'exigeix capturar de forma obligatòria la segona foto de l'odòmetre per a verificar quilometratge".
EDGE-04
	
Event-driven
	
PWA Sync
	
L'operari paga a la ferreteria d'un poble rústic sense senyal i la PWA perd la xarxa cel·lular a mig enviament de la imatge.
	
El client de sincronització de la PWA mòbil aplica la política de reintents exponencials de connexió de forma transparent, reprenent la pujada de dades des de l'últim bit enviat tan bon punt detecti cobertura i evitant duplicacions de tiquets.
EDGE-05
	
Unwanted
	
Check-out
	
L'operari arriba a la nau al vespre i prem el Check-out de despeses mentre dues fotografies pesades segueixen pujant-se.
	
La PWA mòbil bloqueja el Reset temporalment i desactiva el tancament mostrant l'indicador: "Sincronitzant tiquets amb el servidor... Espera la confirmació de pujada abans de tancar", evitant pèrdues de dades.
EDGE-06
	
Event-driven
	
Justificants
	
L'operari realitza la foto del tiquet al matí a la gasolinera però el paper físic de la transacció es perd o cau a una rasa durant la feina de camp.
	
El cap de colla obre la Incidència de Justificant Físic Extraviat; Secretaria audita la fotografia digital emmagatzemada a Hetzner per determinar si s'admet de forma excepcional sota el SIF registrant la traça a la base.
EDGE-07
	
State-driven
	
Seguretat
	
Un usuari amb rol Operari o Enginyer intenta accedir mitjançant POSTman o API directa a la taula de despeses o de tiquets d'un altre tenant d'empresa.
	
PostgreSQL interposa de forma immediata la política de Row Level Security (FORCE ROW LEVEL SECURITY sota app.current_empresa_id) i el middleware del backend de l'API de CampoPro retorna un error HTTP 403 Forbidden bloquejant l'escriptura.
EDGE-08
	
Unwanted
	
Mitigació
	
L'operari puja un tiquet de peatge de camp on el motor d'OCR del backend detecta l'absència del NIF corporatiu de l'empresa.
	
D'acord amb la Spec 007, el sistema calcula de forma automàtica un IVA del 0% no-deduible, integra l'import total com a major despesa de la subcuenta comptable 62X de l'obra associada, i canvia l'estat a PENDENT_DE_CANJE per alertar de reclamar factura completa abans del tancament de desembre.
EDGE-09
	
State-driven
	
Seguretat
	
Es confirma la baixa lògica (actiu = false) d'un operari de camp que manté tiquets registrats a l'IndexedDB pendents de pujar.
	
El Service Worker de la PWA mòbil intercepta immediatament la revocació JWT, bloqueja qualsevol petició d'API, purga de forma destructiva l'IndexedDB local (comprovants, clients, plànols, claus d'accessos) i tanca la sessió a l'acte per seguretat d'informació de l'inquilí.
EDGE-10
	
Unwanted
	
Concurrència
	
Dos administradors de Secretaria modifiquen i guarden al mateix mil·lisegon l'estat o l'import validat de la línia de conciliació del mateix tiquet a /gestio.
	
El backend de l'API de CampoPro aplica control de concurrència optimista mitjançant version_id. El primer commit s'asenta de forma idempotent a la base de dades; el segon commit es rebutja amb error HTTP 409 Conflict, forçant a actualitzar la vista per evitar pèrdues de dades.
--------------------------------------------------------------------------------
Requisits No Funcionals (RNF)

    Almacenamiento Seguro Soberano Local (Sin AWS S3): Totes les fotografies de tiquets de paper de camp, imatges de segona foto de control i metadades extretes es guarden de forma xifrada en repòs mitjançant el xifrat AES-256-GCM en el servidor sobirà Hetzner a Alemanya (UE) sota la ruta local de l'inquilí /docs/<empresa_id>/tiquets/, amb una validació ràpida de Magic Bytes (filetype) i una limitació estricta de 10 MB per arxiu per a estricte compliment de la LOPDGDD i el RGPD.
    Seguridad Multi-Tenant (RLS): Cada crida API de consulta, inserció o eliminació sobre les taules del mòdul de tiquets s'aïlla de forma innegociable a nivell de PostgreSQL mitjançant la directiva FORCE ROW LEVEL SECURITY i l'ús de la variable de sessió d'inquilí app.current_empresa_id.
    Rendimiento y Escalabilidad: El temps de processament OCR d'ingesta de tiquets per Celery + Redis no excedirà els 8 segons de temps d'execució, oferint una latència en Next.js per a l'actualització de dades del llistat de la PWA inferior a 150 ms via WebSockets.
    Diseño Camaleón: La interfície de la PWA de tiquets adopta de forma dinàmica les variables de marca corporativa (--color-primary, --color-secondary) definides a la Spec 011, previsualitzant els estats sota codis de color fixos d'alta visibilitat.
    Tolerancia Cero a Datos Ficticios (Zero-Mock): Si l'empresa d'alta té 0 registres de tiquets en el dia actual, la llista de la PWA es renderitzarà de forma 100% neta i buida (Empty State real), sense cap tipus de registre de prova ni dades simulades d'esquemes.

--------------------------------------------------------------------------------
Fora d'Abast (Out of Scope)

    No gestiona la conciliació de tiquets de gasoil ni la deducció del model d'IVA (es liquida, desgrava i aprova a /gestio/comptabilitat sota la Spec 007).
    No realitza el cobrament de factures de proveïdors, devolucions de diners reals ni transferències SEPA des de la PWA mòbil de camp.
    No gestiona la compresa a WebP de les fotos en el servidor web; la PWA mòbil realitza la compressió de forma síncrona en el client abans del push de IndexedDB.
    No s'admeten dades de prova ni insercions simulades a cap nivell de codi de tiquets, partint d'un entorn de Dia 0 real (Zero Mock Data).

--------------------------------------------------------------------------------
Criteris de Finalització (Definition of Done) i Matriu de Traçabilitat
Per a poder certificar el tancament de la Spec 018 de Tiquets de camp i habilitar la seva fase d'implementació, s'ha de garantir el compliment dels criteris següents:

    Els 21 Requisits Funcionals (RF-01 al RF-21) i els 10 Casos Límit (EDGE-01 al EDGE-10) redactats amb sintaxi formal EARS estricta en català i lliures d'ambigüitats tècniques o dades de prova fictícies sota l'estat Dia 0.
    Correspondència del 100% de la spec de tiquets de la PWA amb una suite de proves d'integració automatitzada en verd amb PostgreSQL RLS actiu sota el tenant d'empresa.
    Alineació total de la política de QR (Constitució v4.0): exclusió absoluta de codis QR per a les eines de camp (les quals es custodien i es traspassen per referència de fàbrica/SN), preservant el QR legal obligatori de facturació Veri*factu per a albarans i factures al tancament de l'obra.
    Doble fotografia obligatòria de repostatge: implementació de la restricció de la RF-05, bloquejant de forma incondicional el desat si es tracta de carburant i manca la segona imatge de l'odòmetre.
    Empty State explícit sota Zero-Mock: la bústia de tiquets sense registres mostrarà un Empty State interactiu i de gran format, descartant pantalles fosques o injeccions.

Matriu de Traçabilitat 1:1 de la Definition of Done (DoD)
Codi de la Spec
	
Cas Límit Vinculat
	
Assert / Criteri de Validació DoD (Zero-Mock)
RF-01 / RF-02
	
EDGE-07
	
Selector de categories Next.js; intent de d'accés des d'altres tenants és vetat per RLS.
RF-03
	
-
	
BD buida d'articles de despesa de la jornada llança Empty State lliure de dades hardcodejades.
RF-04 / RF-05
	
EDGE-03
	
Segona foto de carburant és mandatoria; intents de desar repostatges sense odòmetre és bloquejat.
RF-05.1 / RF-06
	
-
	
Desament de comprovant es realitza a 1 clic, prohibint injecció de text i tecleig obligatori.
RF-07
	
-
	
Assignació inicial d'identificador temporal de fitxer sota format genèric transparent.
RF-08 / RF-08.1
	
EDGE-10
	
Ingesta asíncrona OCR de comprovants; rebuts mixtes de dièsel+AdBlue es desvien a desglose manual.
RF-09 / RF-10
	
EDGE-01
	
Reanomenament dinàmic d'arxius en disc Hetzner de forma unívoca; llista mòbil omet fotos RAM.
RF-11 / RF-12
	
-
	
Selector de tasques del dia de la colla; peatges i dietes es segreguen a despeses generals.
RF-13
	
EDGE-02
	
Compras >100 €/dia bloquen de forma atòmica la targeta contable i requereixen ampliació de central.
RF-14 / RF-15
	
EDGE-06
	
Custòdia física del comprovant; incidència de paper perdut es resol per Secretaria validant la foto digital.
RF-16 / RF-17
	
EDGE-01
	
Check-out de tancament visualitza imports consolidats del dia; paper deteriorat demana comprovació manual.
RF-18 / RF-19
	
EDGE-05
	
Incidència de comprovació manual per paper deteriorat; reset mòbil es bloca si queden tiquets en cua.
RF-20 / RF-21
	
EDGE-09
	
Desament local d'incidències a l'IndexedDB xifrat; baixa lògica de l'operari purga l'IndexedDB de forma destructiva.