Spec 011 — Mòdul de Configuració de l'Empresa, Jornada Laboral, Marca Camaleònica i Rols (/gestio/configuracio)
AVÍS D'ALINEACIÓ CONSTITUCIONAL I INTEGRACIÓ ARQUITECTÒNICA: Aquesta especificació tècnica es regeix de forma innegociable pels principis de la Constitució de CampoPro Suite (v4.0) i s'integra de forma transversal amb la Torre de Control Geogràfica en temps real (Spec 001 i Spec 005), el Mòdul de Clients (Spec 002), el Mòdul de Proveïdors (Spec 003), el Mòdul de Magatzem (Spec 004), el Mòdul de Flota (Spec 006), el Mòdul d'Operaris (Spec 008) i el Mòdul Contable (Spec 007).
Es prohibeix taxativament l'ús de dades simulades o de prova (Zero Mock Data), partint d'un estat de "Dia 0" real i garantint de forma absoluta la sobirania de dades mitjançant l'emmagatzematge local/sobirà dels perfils d'usuaris, dades de personal, logs de control horari, registres d'activitat i claus criptogràfiques de marca en el servidor Hetzner de Falkenstein (Alemanya - UE), rebutjant completament qualsevol servei de núvol públic extern (com AWS S3) d'acord amb el compliment estricte de la LOPDGDD i el RGPD.
De conformitat amb la Constitució i el criteri de QA unificat, es fa l'exclusió absoluta de codis QR per a la traçabilitat i transferència d'eines de camp (les quals es gestionen unívocament pel seu número de referència, marca, model i número de sèrie de fàbrica sota la Spec 004 / Spec 008). Aquesta decisió de disseny de l'inventari convive en perfecta harmonia amb la permanència del codi QR legal i tributari requerit obligatòriament a totes les factures i albarans de lliurament oficials (Veri*factu). Per a la seguretat d'accés, s'autoritza de forma exclusiva l'ús de codis QR estàndard de configuració 2FA TOTP (Google Authenticator) durant el procés d'alta o enrolament de l'usuari d'oficina.
--------------------------------------------------------------------------------
Context i Objectiu
El mòdul de Configuració de l'Empresa, Jornada Laboral, Marca Camaleònica i Rols (/gestio/configuracio) és el Panell d'Ajustos Estratègics, Identitat Corporativa i Governança Laboral de CampoPro Suite. Centralitza els paràmetres estructurals que regeixen el funcionament operatiu, la seguretat d'accés dels usuaris administratius d'oficina i l'aspecte visual camaleònic de la instància de l'empresa instal·ladora.
Seguint la decisió de disseny arquitectònic d'unificar totes les APIs financeres sota un mateix sostre, es trasllada tota la gestió de tresoreria (comptes IBAN, passarel·la Bizum, tiquets de despeses de camp i targetes corporatives) al mòdul de Comptabilitat (/gestio/comptabilitat - Spec 007), concentrant /gestio/configuracio exclusivament en:

    Gestió de Personal Administratiu i Rols Web: Administració de la plantilla d'oficina (Boss, Secretaria, Enginyer, Comptabilitat), assignació de credencials alfanumèriques securitzades i segregació estricta entre accés al Dashboard Web i accés a la PWA Mòbil de camp.
    Seguretat d'Accés Web i 2FA TOTP Mandatori: Compliment del principi Zero-Trust exigit per la Constitució de CampoPro, imposant autenticació de doble factor (2FA TOTP) per a tots els perfils d'oficina i proporcionant un mecanisme de recuperació i reinici de clau pel Boss en cas de pèrdua de dispositiu mòbil d'un empleat.
    Slots de Jornada Laboral Individualitzats: Sistema de configuració d'horaris individual per a cada usuari de la plataforma (sigui operari, enginyer o gerent), totalment editable per admetre qualsevol modalitat (jornada continuada, jornada partida, intensiva d'estiu o torns especials), el qual alimenta directament el motor de compliment del RDL 8/2019 i el tancament automàtic a les 8 hores definit a la Spec 008.
    Motor Camaleònic (Chameleon UI Engine) i ADN de Marca sota Mandat HITL:
        Capacitat de càrrega de la guia d'estil o "ADN de marca" de l'empresa de forma supervisada: el Copilot IA analitza el document i proposa una paleta de colors que requereix la validació i aprovació explícita (Human-in-the-Loop) del Boss abans d'aplicar-se.
        Selector visual de colors (Color Picker) que permet definir manualment els colors primari, secundari i d'accent, aplicant-se de forma immediata sobre les variables CSS HSL de la web i la PWA mòbil amb previsualització en viu (live preview) per a un entorn controlat.
    Gestió i Redimensionament del Logotip Corporatiu: Slot dedicat per a la càrrega del logotip oficial (en format PNG o JPG) amb transformació i redimensionament automàtic per a la capçalera del Dashboard web, icona instal·lable de la PWA mòbil, favicon i caixetins de documents oficials (factures Veri*factu, albarans i plànols PDF).
    Connexió del Bot de Telegram Corporatiu: Administració de credencials del bot d'atenció al client (Token de Bot i Webhook Secret) articulat amb el servei de notificacions definit a la Spec 009.
    Aïllament Multi-Inquilí Estricte i Blindatge davant de Superadmin: Cada instància d'empresa (empresa_id) és completament autònoma mitjançant Row Level Security (RLS); les dades corporatives estan completament blindades de manera que el rol Superadmin mai tindrà accés a les dades privades de l'empresa.
    Tolerància Zero a Dades Fictícies (Zero Mock Data): La interfície opera exclusivament sobre configuracions reals de base de dades, mostrant formularis buits en l'arrencada Dia 0 sense cap dada dummy.

--------------------------------------------------------------------------------
Usuaris / Actors i Matriu d'Accés (Zero-Trust)
El sistema manté l'aïllament multi-inquilí mitjançant Row Level Security (RLS) mandatori a nivell de PostgreSQL (empresa_id) i una delimitació de competències estricta:

    Boss (Gerència / Propietari): Màxima autoritat de configuració. Pot editar qualsevol paràmetre corporatiu, assignar rols a usuaris, modificar el motor camaleònic i logotip, configurar slots de jornada de qualsevol empleat, reiniciar secrets 2FA TOTP bloquejats i configurar el bot de Telegram.
    Secretaria / RRHH: Co-gestor de la configuració operativa (autoritzat conjuntament amb el Boss). Pot donar d'alta i editar usuaris administratius d'oficina, editar slots de jornada laboral d'operaris i personal d'oficina, i actualitzar paràmetres corporatius bàsics de contacte.
    Enginyer / Supervisor Tècnic: Accés de només lectura a les seves pròpies dades personals i a la consulta del seu slot de jornada assignat. VETO TOTAL (HTTP 403 Forbidden) sobre l'edició de rols, modificació de colors de marca, alteració del logotip o canvis en usuaris d'oficina.
    Operari de Camp / Cap de Colla (/operari): Sense accés a /gestio/configuracio. La seva jornada laboral es regeix pel slot configurat des d'aquest mòdul, executat des de la seva PWA mòbil sota les pautes de la Spec 008.
    Superadmin (Plataforma SaaS): BLINDATGE TOTAL. El superadmin només governa el CRM d'infraestructura global de servidors a /superadmin; té vetat per disseny constitucional i polítiques RLS l'accés o lectura a les configuraciones, usuaris, jornades o dades de negoci de qualsevol empresa_id.

Matriu de Permisos per Rol
Àmbit Funcional
	
Boss
	
Secretaria / RRHH
	
Enginyer Tècnic
	
Superadmin (SaaS)
	
Operari PWA
Consulta de Paràmetres d'Empresa
	
Total
	
Total
	
Només Lectura
	
Denegat (RLS Blindat)
	
Sense accés web
Modificació de Marca Camaleònica (HSL)
	
Total
	
Total
	
Denegat (403)
	
Denegat (RLS Blindat)
	
Sense accés web
Càrrega / Canvi de Logotip Corporatiu
	
Total
	
Total
	
Denegat (403)
	
Denegat (RLS Blindat)
	
Sense accés web
Alta i Modificació de Personal Web
	
Total
	
Total
	
Denegat (403)
	
Denegat (RLS Blindat)
	
Sense accés web
Reinici de 2FA TOTP d'Empleats
	
Total
	
Denegat (403)
	
Denegat (403)
	
Denegat (RLS Blindat)
	
Sense accés web
Configuració d'Slots de Jornada Laboral
	
Total
	
Total
	
Consulta Pròpia
	
Denegat (RLS Blindat)
	
Consulta PWA
Paràmetres del Bot de Telegram
	
Total
	
Total
	
Denegat (403)
	
Denegat (RLS Blindat)
	
Sense accés web
Gestió Financera (IBAN, Bizum, Targetes)
	
Reubicat Spec 007
	
Reubicat Spec 007
	
Reubicat Spec 007
	
Reubicat Spec 007
	
Reubicat Spec 007
--------------------------------------------------------------------------------
Requisits Funcionals (Notació EARS Estricta)
Àmbit 1: Gestió de Personal Administratiu i Rols Web

    RF-01 (Ubiquitous): EL SISTEMA presentarà a /gestio/configuracio el llistat complet d'usuaris administratius de l'empresa autenticada, mostrant per a cadascun: nom complet, NIF, correu electrònic corporatiu, telèfon, rol d'oficina (Boss, Secretaria, Enginyer, Comptabilitat), tipus d'accés (Dashboard Web) i data de l'últim inici de sessió.
    RF-02 (Event-driven): QUAN un usuari amb rol Boss o Secretaria doni d'alta o editi un empleat administratiu, EL SISTEMA ha de registrar les dades personals, validar el format del NIF i correu electrònic, i generar una contrasenya alfanumèrica d'alta seguretat de 12 caràcters per a l'accés al Dashboard Web.
    RF-03 (Unwanted behavior): SI un usuari amb rol Enginyer intenta crear, editar o donar de baixa un compte d'usuari o modificar l'accés d'un empleat, ENTONCES EL SISTEMA rebutjarà la petició i retornarà un d'error HTTP 403 Forbidden.
    RF-04 (Ubiquitous): EL SISTEMA s'ajustarà estrictament al principi Zero Mock Data, mostrant de forma real el llistat tabular buit o amb dades físiques introduïdes sense inyectar dades dummy o simulades en l'arrencada del sistema.

Àmbit 2: Seguretat 2FA TOTP i Polítiques d'Accés Zero-Trust

    RF-05 (Ubiquitous): EL SISTEMA imposarà l'activació obligatòria d'autenticació de doble factor basada en temps (2FA TOTP) per a tots els perfils que accedeixen al Dashboard Web (Boss, Secretaria, Enginyer, Comptabilitat), exigint el codi de 6 dígits en cada inici de sessió posterior a la verificació de contrasenya.
    RF-06 (Event-driven): QUAN un usuari administratiu perdi o canviï el seu dispositiu mòbil i no pugui introduir el codi 2FA, EL SISTEMA ha de facultar exclusivament el rol Boss per executar el reinici del secret TOTP des de /gestio/configuracio, permetent a l'usuari vincular un nou autenticador (Google Authenticator) en el seu proper accés mitjançant l'escaneig d'un codi QR estàndard de seguretat.
    RF-07 (State-driven): MIENTRAS un compte d'usuari estigui donat de baixa o contingui l'estat d'inactiu (actiu = false), EL SISTEMA invalidarà immediatament el seu accés al Dashboard Web i PWA mòbil, inyectant de forma atòmica els seus tokens JWT actius a la llista negra de revocació de Redis.

Àmbit 3: Slots de Jornada Laboral Individualitzats i Sincronització amb Spec 008

    RF-08 (Ubiquitous): EL SISTEMA proporcionarà a /gestio/configuracio un Slot de Configuració de Jornada Laboral assignable de forma individual i independent a cada usuari de la plataforma (sigui operari, enginyer, administratiu o gerent).
    RF-09 (Event-driven): QUAN Secretaria o Boss configurin o modifiquin l'slot de jornada d'un empleat, EL SISTEMA permetrà seleccionar i editar lliurement:
        Modalitat de jornada: Jornada Continuada, Jornada Partida o Torn Especial.
        Rangs horaris oficials (hora d'entrada teòrica, sortida per dinar, represa i sortida definitiva).
        Còmput setmanal d'hores estipulat segons el conveni col·lectiu d'aplicació.
    RF-10 (Event-driven): QUAN Secretaria o Boss activin la modalitat de Jornada Intensiva d'Estiu per a un usuari o col·lectiu, EL SISTEMA processará el canvi requerint de forma obligatòria les dates d'inici i final de vigència i els nous horaris aplicables (ex. 07:00 a 15:00).
    RF-11 (State-driven): EL SISTEMA governarà el control horari i l'auto-tancament de la jornada de la Spec 008 prenent com a referència vinculant el slot horari i modalitat (continuada o partida) assignat individualment a la fitxa de l'operari, realitzant el tancament de shift de forma atòmica i idempotent.

Àmbit 4: Motor Camaleònic (Chameleon UI Engine) i Identitat de Marca

    RF-12 (Event-driven): QUAN l'usuari pengi la guia d'estil o "ADN de marca" de l'empresa, EL COPILOT IA n'analitzarà semànticament el contingut i proposarà una paleta de colors corporatius com a esborrany de treball.
    RF-13 (Event-driven): QUAN el supervisor o Boss aprovi manualment l'esborrany de la paleta proposat per la IA, o defineixi manualment els colors primari, secundari i d'accent mitjançant el selector visual de colors (Color Picker), EL SISTEMA calcularà els valors HSL i actualitzarà la interfície.
    RF-14 (Ubiquitous): EL SISTEMA ha d'injectar automàticament els colors seleccionats a les variables CSS dinàmiques de Next.js (--color-primary, --color-secondary, --color-accent), modificant en temps real la interfície del Dashboard Web i de la PWA mòbil sense necessitat de reiniciar el contenidor ni desconnectar sessions.
    RF-15 (Ubiquitous): EL SISTEMA renderitzarà una finestra de previsualització en viu (live preview) al formulari de configuració de marca, mostrant el contrast i l'aspecte real que adoptaran els botons, encapçalaments i components abans de desar el canvi de forma permanent.

Àmbit 5: Gestió i Redimensionament del Logotip Corporatiu

    RF-16 (Event-driven): QUAN Secretaria o Boss pugin una imatge per al logotip oficial de l'empresa, EL SISTEMA validarà estrictament que l'arxiu estigui sota format PNG o JPG i que el seu pes total no superi els 10 MB, procedint a la seva ingesta en cas d'èxit.
    RF-17 (Ubiquitous): EL SISTEMA processarà i redimensionarà sobiràment al servidor Hetzner a Alemanya qualsevol logotip carregat amb èxit, generant i sobreescribint de forma automàtica les variants per a:
        Capçalera superior del Dashboard Web (versió horitzontal optimitzada).
        Icona de la PWA Mòbil (formats quadrat 192x192 i 512x512).
        Favicon per a la pestanya del navegador.
        Encapçalament i caixetí dels documents PDF oficials (factures Veri*factu, albarans de lliurament d'obra i plànols tècnics).
    RF-18 (Ubiquitous): EL SISTEMA renderitzarà un monograma tipogràfic net basat en les inicials de la raó social sobre fons corporatiu en absència d'imatge de logotip carregat pel client, assegurant el compliment innegociable de Zero Mock Data.

Àmbit 6: Paràmetres del Bot de Telegram Corporatiu

    RF-19 (Event-driven): QUAN Secretaria o Boss modifiquin les credencials del Bot de Telegram de notificacions (Spec 009), EL SISTEMA en demanarà el desat sol·licitant de forma obligatòria: Token de Bot proporcionat per BotFather i Webhook Secret Token per a la seguretat de trucades.
    RF-20 (Event-driven): QUAN l'usuari prepa el botó "Provar Connexió Bot", EL SISTEMA transmetrà una petició de comprovació asíncrona contra l'API de Telegram (mètode getMe) i en mostrarà el diagnòstic operatiu instantani (OPERATIU o ERROR DE CONNEXIÓ).

Àmbit 7: Aïllament Multi-Inquilí i Blindatge davant de Superadmin

    RF-21 (Ubiquitous): EL SISTEMA aplicarà Row Level Security (RLS) mandatori a nivell de PostgreSQL mitjançant la variable de sessió d'inquilí (empresa_id), garantint que les dades de configuració, usuaris, rols i logotips s'aïllin de forma hermètica entre empreses concurrents sota la plataforma.
    RF-22 (Ubiquitous): EL SISTEMA vetarà completament l'accés del rol de plataforma Superadmin a la visualització, edició o canvi de dades corporatives, usuaris o configuracions de l'empresa, limitant les seves accions de forma exclusiva a la ruta central de /superadmin (mètodes de MRR, llicències i pagaments SaaS) per disseny de seguretat constitucional.

--------------------------------------------------------------------------------
Taula de Casos Límit i Gestió d'Errors
Codi
	
Tipus EARS
	
Mòdul
	
Vector de Fallada / Escenari Límite
	
Comportament Requerit del Sistema
EDGE-01
	
Unwanted
	
Seguretat
	
L'únic usuari amb rol Boss de l'empresa perd el seu dispositiu de doble factor (2FA TOTP) i no pot accedir.
	
EL SISTEMA permetrà l'accés d'emergència exclusivament mitjançant la introducció d'un dels 8 codis de recuperació estàtics generats unívocament durant l'onboarding de l'empresa, bloquejant de forma absoluta qualsevol override per via de superadmin per evitar injeccions de seguretat RLS.
EDGE-02
	
Unwanted
	
Marca
	
L'usuari intenta desar un patró de colors primari/secundari que presenta un ràtio de contrast inferior a 4.5:1.
	
EL SISTEMA comprovarà de forma algorítmica els components HSL segons les directrius de contrast de l'accessibilitat WCAG 2.1 AA, rebutjarà el desat del canvi, mostrarà un error d'il·legibilitat visual i mantindrà actius els darrers colors vàlids o la paleta per defecte (Industrial Precision).
EDGE-03
	
Unwanted
	
Imatges
	
Es puja un logotip maliciós camuflat amb extensió falsa (ex. script executable canviat a .png).
	
El backend analitza estrictament els Magic Bytes (filetype) reals en el processament de Celery. Si es detecta una incongruència de capçalera de fitxer, ENTONCES avorta de forma atòmica la transferència física, manté el darrer monograma actiu i llança l'error de format imatge.
EDGE-04
	
Event-driven
	
Jornades
	
Secretaria modifica l'slot de jornada d'un operari que es troba realitzant un shift de jornada activa en camp offline.
	
El backend de la plataforma processarà el canvi de forma que el shift en curs continuï regint-se per les condicions horàries de l'slot vigent a l'inici d'aquella jornada (per al càlcul del tancament automàtic a les 8h), aplicant el nou slot configurat exclusivament a les jornades de treball futures.
EDGE-05
	
Unwanted
	
Seguretat
	
Secretaria o l'usuari intenta realitzar la baixa o esborrat lògic de l'últim compte Boss de l'empresa.
	
El backend de l'API de CampoPro intercepta la crida i bloqueja la transacció de modificació a la base de dades, emetent un codi d'error 400 Bad Request per prevenir de forma infranquejable l'orfandat de l'administració de l'inquilí.
EDGE-06
	
State-driven
	
Jornades
	
El shift de control horari d'un torn especial nocturn creua de forma exacta el canvi d'hora d'estiu/hivern (DST).
	
EL SISTEMA calcularà les hores de treball net efectiu basant-se de forma estricta i prioritària en les marques de temps absolutes de registre en format UTC (timestamps absoluts de base), evitant desviaments d'imputació o càlculs d'hores extres inexistents.
EDGE-07
	
Unwanted
	
Colles
	
Dos enginyers intenten programar de forma concurrent el mateix operari a dues colles diferents en el mateix interval de dates.
	
El backend detectarà la col·lisió de calendari de l'operari, bloquejarà la segona reserva a nivell transaccional de base de dades i retornarà un error HTTP 409 Conflict instant a revisar la disponibilitat.
EDGE-08
	
Unwanted
	
Jornades
	
S'introdueix un slot de jornada partida amb rangs horaris de pausa incoherents (ex. hora d'inici de dinar posterior a la represa).
	
El formulari web Next.js i l'API FastAPI validaran la coherència cronològica, marcant el rang en vermell i bloquejant el save fins a la seva esmena manual.
EDGE-09
	
Event-driven
	
Telegram
	
El servidor de l'API externa de Telegram presenta caiguda temporal en prémer "Provar Connexió Bot".
	
EL SISTEMA en gestionarà el timeout d'espera (màxim 5 segons) de forma asíncrona, commutarà l'estat provisional a ERROR DE CONNEXIÓ i mostrarà el registre detallat de fallida sense bloquejar l' event loop de FastAPI.
EDGE-10
	
Unwanted
	
Seguretat
	
Un usuari amb rol Enginyer intenta invocar directament via POSTman qualsevol endpoint d'edició d'usuaris o de marca.
	
El PostgreSQL interposa de forma immediata la política de Row Level Security (FORCE ROW LEVEL SECURITY sota app.current_empresa_id) i el middleware de seguretat de rols retorna un error HTTP 403 Forbidden bloquejant l'escriptura.
--------------------------------------------------------------------------------
Requisits No Funcionals (RNF)

    Almacenamiento Local Seguro Multi-Tenant (Soberano): Tots els logotips processats, arxius de marca, manuals d'ADN, certificats de 2FA i metadades es guarden exclusivament en els discs locals de l'empresa i servidor sobirà Hetzner a Alemanya sota la ruta de seguretat /docs/<empresa_id>/configuracio/ amb xifratge en repòs AES-256-GCM (cero dependència d'AWS S3).
    Seguridad Multi-Tenant (RLS): Cada consulta, modificació o alta sobre les taules del mòdul de configuració s'aïlla de forma innegociable mitjançant Row Level Security (RLS) mandatori a nivell de PostgreSQL de forma síncrona sota la variable d'inquilí app.current_empresa_id.
    Protección de Datos Macroeconómicos (Zero-Trust): La gestió financera de la remesa de targetes corporatives i accounts comptables d'oficina s'ha bifurcat de forma total d'aquest directori, estant reubicada de forma exclusiva a la Spec 007 sota veto estricte amb HTTP 403 Forbidden al rol Enginyer.
    Tolerancia Cero a Datos Ficticios (Zero-Mock): Si no hi ha personal web donat d'alta a l'empresa a excepció del Boss creador, el llistat es renderitzarà de forma neta de mocks d'origen, respectant l'estat de Dia 0 de l'onboarding.
    Rendimiento y Escalabilidad: El temps de resposta per a l'actualització de variables CSS i visualització en viu de la previsualització de marca no excedirà els 200 ms, assegurant un processament gràfic asíncron (Celery + Redis) per a canvis de logo pesats.

--------------------------------------------------------------------------------
Fora d'Abast (Out of Scope)

    No gestiona la creació massiva de comandes o llicències SaaS de la plataforma multi-empresa (es delega exclusivament a /superadmin).
    No realitza la conciliació ni s'encarrega d'interaccionar directament amb bancs o passarel·les de pagament de targetes corporatives (governat a /gestio/comptabilitat - Spec 007).
    No es recolza en la instal·lació d'aplicacions de mètodes d'autenticació biomètrics (ex. FaceID) en Next.js web, limitant la seguretat d'oficina a 2FA TOTP i credencials de contrasenya forts de 12 caràcters sota bcrypt.
    No s'admeten dades de prova ni insercions simulades a cap nivell de codi de configuració.

--------------------------------------------------------------------------------
Criteris de Finalització (Definition of Done) i Matriu de Traçabilitat

    Els 22 Requisits Funcionals (RF-01 al RF-22) i els 10 Casos Límit (EDGE-01 al EDGE-10) redactats amb sintaxi formal EARS estricta en català i lliures d'ambigüitats o condicions d'errors desateses.
    Correspondència del 100% de la spec de configuració amb una suite de proves d'integració automatitzada en verd amb PostgreSQL RLS actiu sota el tenant real.
    Alineació total de la política de QR: existència obligatòria del QR legal Veri*factu per a facturació en Comptabilitat (Spec 007), lliure d'ús de QR per a les eines de camp (Spec 004 / Spec 008) que s'identifiquen per marca, model i número de sèrie, i habilitació de QR estàndard de configuració TOTP de seguretat en enrolament 2FA d'oficina.
    Processament asíncron de logotip: integració del pipeline Celery + Redis per al redimensionament gràfic sobirà a Hetzner, convertint l'arxiu fins a 10MB en múltiples imatges optimitzades.
    Mandat Human-in-the-Loop d'ADN de Marca: la IA és capaç de proposar una paleta de colors corporatius basada en la guia d'estil carregada, però el canvi del stylesheet CSS exigeix la confirmació i firma digital/clic d'aprovació del Boss de l'empresa.

Matriu de Traçabilitat 1:1 de la Definition of Done (DoD)
Codi de la Spec
	
Cas Límit Vinculat
	
Assert / Criteri de Validació DoD (Zero-Mock)
RF-01 / RF-02
	
EDGE-05
	
Renderitzat tabular d'usuaris actius; intent d'esborrat de l'últim Boss llança excepció de base de dades.
RF-03
	
EDGE-10
	
Put/Post d'Enginyer tècnic sobre endpoints d'usuaris retorna de forma transparent un error 403.
RF-04
	
-
	
Llistat buit real si el tenant compta amb 0 dades de personal sense dades fictícies hardcodejades.
RF-05 / RF-06
	
EDGE-01
	
Flux d'autenticació 2FA; pèrdua de dispositiu Boss es resol amb codi de recuperació estàtic d'onboarding.
RF-07
	
-
	
Inactivació de compte JWT llista negra activa en Redis; expulsió immediata del Dashboard i de la PWA.
RF-08 / RF-09
	
EDGE-08
	
Slot de jornada individualitzat; intents de desat de jornada partida incoherents marquen i bloquegen el formulari.
RF-10
	
-
	
Activació de Jornada Intensiva d'Estiu per dates d'inici i final de calendari.
RF-11
	
EDGE-04 / EDGE-06
	
Integració d'slot individual amb Spec 008 per auto-tancament de shift; canvi de DST UTC calcula hores nets reals.
RF-12 / RF-13
	
EDGE-02
	
Inferencia de colors d'ADN via Copilot; selector visual bloca ràtios de contrast baixos <4.5:1 sota WCAG.
RF-14 / RF-15
	
-
	
Injecció dinàmica de variables CSS HSL a Web i PWA; live preview visualitza canvis abans de desar.
RF-16 / RF-17
	
EDGE-03
	
Càrrega de logo PNG/JPG; validació de Magic Bytes de format real i redimensionament asíncron en Celery.
RF-18
	
-
	
Monograma tipogràfic net basat en raó social actiu en absència d'imatge de logotip corporatiu.
RF-19 / RF-20
	
EDGE-09
	
Paràmetres del Bot d'atenció al client; provar connexió getMe gestiona asíncronament timeouts d'espera.
RF-21 / RF-22
	
EDGE-05
	
Aïllament PostgreSQL RLS per empresa_id; el Superadmin d'infraestructura té prohibit l'accés a dades corporatives.