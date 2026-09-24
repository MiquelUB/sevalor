Spec 019 — Mòdul d'Autenticació de Camp, Seguretat Offline i Gestió de Sessió a la PWA (/operari/login) - v2
AVÍS D'ALINEACIÓ CONSTITUCIONAL I INTEGRACIÓ ARQUITECTÒNICA: Aquesta especificació tècnica es regeix de forma innegociable pels principis de la Constitució de CampoPro Suite (v4.0) i s'integra de forma transversal amb el Dashboard i la Torre de Control Geogràfica (Spec 001 i Spec 005), el Mòdul de Clients (Spec 002), el Mòdul de Magatzem (Spec 004), el Mòdul d'Operaris (Spec 008), el Mòdul Contable (Spec 007) i el Mòdul de Plànols de Camp (Spec 017).
Es prohibeix taxativament l'ús de dades simulades o de prova (Zero Mock Data), partint d'un estat de "Dia 0" real i garantint de forma absoluta la sobirania de dades mitjançant l'emmagatzematge local/sobirà dels tokens de dispositiu, claus d'IndexedDB i dades de camp en el servidor Hetzner de Falkenstein (Alemanya - UE), rebutjant completament qualsevol servei de núvol públic extern (com AWS S3) d'acord amb el compliment estricte de la LOPDGDD i el RGPD.
De conformitat amb la Constitució i el criteri de QA unificat, es recorda que s'exclou l'ús de codis QR per a la traçabilitat i transferència d'eines de camp (les quals es gestionen i es custodien nominalment pel seu número de referència, marca, model i número de sèrie de fàbrica sota la Spec 004 i Spec 008). Aquesta exclusió tècnica de camp convive en perfecta harmonia amb la permanència del codi QR legal i tributari requerit obligatòriament a totes les factures i albarans de lliurament oficials (Veri*factu) emesos pel mòdul comptable. Per a la seguretat d'accés, s'autoritza de forma exclusiva l'ús de codis QR estàndard de configuració 2FA TOTP (Google Authenticator) durant el procés d'alta o enrolament exclusively per als usuaris d'oficina (Spec 011).
--------------------------------------------------------------------------------
Context i Objectiu
El mòdul d'Autenticació de la PWA (/operari/login) és la porta d'accés segura, ultraràpida i resilient per als operaris tècnics i caps de colla que treballen en el terreny. Governat pel principi del "Flujo de los 30 segundos", elimina completament la fricció d'haver d'introduir correus electrònics o contrasenyes alfanumèriques complexes en dispositius mòbils de camp (ús amb guants, condicions climàtiques adverses o mobilitat extrema), oferint una experiència basada en un teclat numèric tàctil de gran format (numpad) i un codi PIN secret de 4 dígits.
Aquest mòdul garanteix:

    Disseny Camaleó i personalització de marca: Pantalla d'inici adaptada de forma automàtica al logotip i a la paleta de colors de l'empresa compradora (variables CSS HSL injectades dinàmicament segons el tenant).
    Identificació segura per Enrolament de Dispositiu Únic: Per seguretat sandbox del navegador (que impedeix llegir la targeta SIM o el número de telèfon directament des d'una PWA web), el sistema implementa un procés d'enrolament inicial transparent via SMS OTP, lligant el dispositiu de l'operari al seu PIN de 4 dígits de forma unívoca.
    Desbloqueig i xifratge sobirà 100% Offline (Zero-Trust): Validació criptogràfica local mitjançant la Web Crypto API (PBKDF2 + AES-GCM 256 bits). Es deriva la clau mestre del PIN per a verificar un bloc sentinella criptogràfic i desxifrar la memòria local IndexedDB in zones rurals sense cobertura, sense emmagatzemar mai credencials en text pla.
    Protecció anti-força bruta amb avís a central: Bloqueig temporal de 30 segons després de 3 intents erronis consecutius i generació d'una alerta de seguretat automàtica transmesa de forma asíncrona a la Torre de Control de l'oficina tècnica.
    Circuit de recuperació de PIN obligat i preventiu: Botó d'accés directe "Has oblidat el teu PIN?" que permet trucar a Secretaria per generar un nou PIN temporal enviat strictly per SMS, deixant traça immutable d'incidència de seguretat a l'historial de l'operari i re-xifrant l'IndexedDB local al següent accés amb cobertura.
    Tancament de jornada com a bloqueig automàtic de seguretat: Quan l'operari finalitza la jornada laboral (Spec 013), la PWA es bloqueja d'immediat retornant a la pantalla de login del PIN.
    Suport per a dispositius i furgonetes compartides: Opció de tancament de sessió (Logout) que purga les claus de la memòria RAM i permet el canvi d'operari introduint o seleccionant un altre número de telèfon autoritzat al terminal.
    Bloqueig intel·ligent d'Estat de Segon Pla (Background) i inactivitat: Auto-bloqueig por inactivitat (30 minuts) que s'inhabilita de forma intencionada a les pantalles de feina activa i visor de plànols, coordinat amb un bloqueig segur de 5 minuts de cortesia si l'aplicació s'envia a segon pla mentre hi ha una tasca en curs.
    Aïllament multi-inquilí estricte (Zero-Trust): Rebuig immediat i opac davant peticions des d'empreses clients diferents, evitant qualsevol revelació d'identitats o creuament de dades en el SaaS.

--------------------------------------------------------------------------------
Usuaris / Actors i Matriu d'Interacció (Zero-Trust)
Tota la capa d'autenticació, sessions d'usuari i emmagatzematge de claus està protegida mitjançant Row Level Security (RLS) a la base de dades sota la sessió de l'empresa_id de l'operari autenticat.

    Operari / Cap de Colla (/operari/login): Actor principal de camp. Executa l'enrolament inicial del seu terminal, introdueix el seu PIN de 4 dígits de forma diària, desbloqueja la base IndexedDB local offline, tanca la sessió o commuta de perfil en dispositius compartits i sol·licita l'enviament de PIN temporal en cas d'oblit.
    Secretaria / Administració: Dona d'alta el telèfon corporatiu a la fitxa 360 de l'operari (Spec 008), rep la trucada de recuperació, genera de forma manual el PIN temporal enviat per SMS i supervisa les incidències de seguretat d'accés des del panell d'oficina.
    Enginyer / Supervisor Tècnic (/gestio): Rep a la Torre de Control de la Spec 001 les alertes per intents fallits consecutius o intents de força bruta en dispositius de camp per a la seva coordinació.
    Atacant / Dispositiu no autoritzat: Rebutjat immediatament mitjançant rate-limiting sever a nivell d'API i bloqueig local AES-GCM d'IndexedDB sense revelar cap informació del tenant.

Matriu de Responsabilitats per Estat d'Accés
Situació d'Accés
	
Operari de Camp
	
Supervisor / Enginyer
	
Secretaria / Administració
	
Sistema (PWA / Backend)
Accés Diari Normal
	
Introdueix PIN de 4 dígits al numpad
	
Consulta fitxatge de jornada
	
Sense accés
	
Valida PBKDF2 localment, desxifra IndexedDB i obre sessió JWT
Enrolament de Dispositiu
	
Introdueix Telèfon/NIF + SMS OTP
	
Sense accés
	
Registra telèfon a la fitxa 360
	
Genera clau de dispositiu única a IndexedDB i enllaça al tenant
Accés 100% Offline
	
Introdueix PIN a la parcel·la
	
Rep sincronització a posteriori
	
Sense accés
	
Desxifra sentinella via Web Crypto API localment
3 Intents Erronis
	
Espera bloqueig de 30 segons
	
Visualitza alerta de seguretat
	
Registra possible sabotatge
	
Inhabilita numpad, inicia temporitzador i envia alerta a base
PIN Oblidat
	
Prem botó SOS-PIN i truca a base
	
Revisa motiu de bloqueig
	
Genera nou PIN temporal via SMS
	
Re-xifra IndexedDB amb la nova clau derivada al primer inici
Finalització Jornada
	
Prem "Finalitzar Jornada Laboral"
	
Revisa hora de tancament RDL
	
Liquida el registre d'shift
	
Tanca shift, purga claus de la RAM i bloca la PWA a la pantalla PIN
Dispositiu Compartit
	
Prem "Tancar Sessió" (Logout)
	
Reassigna equip o flota si cal
	
Revisa canvis de custòdia
	
Purga IndexedDB, demana nou telèfon/enrolament per a segon torn
Estat de Segon Pla
	
Recupera PWA o reintrodueix PIN
	
Monitoritza feina activa
	
Sense accés
	
Bloqueja la PWA si passa >5 minuts en segon pla (mantenint cronòmetres actius)
--------------------------------------------------------------------------------
Requisits Funcionals (EARS Notation)
Àmbit 1: Disseny Camaleó, Teclat Numèric de Gran Format i Enrolament de Dispositiu

    RF-01 (Ubiquitous): La pantalla d'inici de /operari/login renderitzarà el Disseny Camaleó, injectant de forma dinàmica i sense retard (evitant parpelleigs visuals FOUC) el logotip de l'empresa compradora i les variables CSS HSL de marca (--color-primary, --color-secondary), adaptant de forma immediata l'aspecte visual de Next.js al tenant de conformitat amb la Spec 011.
    RF-02 (Ubiquitous): La interfície de login de la PWA ha de proporcionar un teclat numèric tàctil de gran format (numpad) integrat directament a la pantalla, amb 10 botons de dígits (0-9) i un control d'esborrat de caràcters (delete), optimitzat ergonòmicament per a la seva ràpida pulsació amb una sola mà, guants o en mobilitat de camp.
    RF-03 (State-driven) — Enrolament de Dispositiu Únic per SMS OTP: SI l'operari obre la PWA per primera vegada en un terminal (o es detecta purga d'IndexedDB), ENTONCES EL SISTEMA bloquejarà la pantalla de PIN i forçarà el flux d'Enrolament de Dispositiu, requerint que l'operari introdueixi el seu número de telèfon mòbil registrat, enviant de forma automatitzada un SMS amb codi OTP de 6 dígits i generant a l'IndexedDB local un token criptogràfic de dispositiu unívoc associat a l'empresa_id de l'inquilí, evitant introduccions manuals futures.
    RF-04 (Event-driven): QUAN l'operari introdueixi el quart dígit del seu codi PIN de 4 dígits, EL SISTEMA de la PWA executarà de forma immediata i de forma interna la comprovació de credencials, sans requenir la pulsació de cap botó addicional d'"Entrar" o "Confirmar".

Àmbit 2: Autenticació Criptogràfica Offline (PBKDF2 + AES-GCM 256 bits)

    RF-05 (State-driven) — Autenticació Autònoma 100% Offline: SI l'operari es troba a una finca rústica o zona de sombra profunda sense connectivitat de xarxa mòbil, ENTONCES la PWA mòbil de camp utilitzarà de forma exclusiva la Web Crypto API nadiua del navegador mòbil per a validar el PIN i obrir la sessió de treball de camp de forma completament local.
    RF-06 (Ubiquitous) — Derivació PBKDF2 i Sentinella Criptogràfica: Per a validar el PIN de forma offline sense comprometre dades de camp, EL SISTEMA realitzarà les següents accions:
        Derivarà una clau mestre a partir del PIN de 4 dígits de l'operari mitjançant l'algorisme PBKDF2 (amb 100.000 iteracions i una sal criptogràfica pròpia del dispositiu mòbil).
        Utilitzarà aquesta clau derivada per intentar desxifrar mitjançant AES-GCM de 256 bits un bloc d'informació estàtic sentinella emmagatzemat a IndexedDB (ex. el text lliure "CAMPOPRO_SENTINEL").
        SI la descompressió i desxifratge del bloc sentinella coincideix exactament amb el valor esperat, LLAVORS el sistema donarà el PIN per vàlid i procedirà a desxifrar de forma segura la base de dades general d'IndexedDB (plànols, clients, materials) per iniciar l'agenda.
    RF-07 (Unwanted-behaviour): EL SISTEMA té la prohibició absoluta d'emmagatzemar a la memòria local persistent del mòbil (localStorage, IndexedDB no xifrat, o cookies) tokens d'accés JWT actius, el PIN de l'operari en text pla, o dades de finques sense el blindatge del xifratge de seguretat AES-GCM derived de PBKDF2.

Àmbit 3: Protecció Anti-Força Bruta, Bloqueig i Alerta a la Torre de Control

    RF-08 (State-driven): SI s'introdueix un codi PIN incorrecte, ENTONCES la PWA mostrarà immediatament una alerta visual d'error en vermell, reproduirà un to acústic suau d'advertència i netejara de forma atòmica les caselles del numpad per a un nou intent.
    RF-09 (State-driven) — Bloqueig Temporal de Seguretat: QUAN es registrin 3 intents d'introducció de PIN incorrectes consecutius al mateix dispositiu, EL SISTEMA de la PWA bloquejarà incondicionalment el teclat numèric (numpad) durant un període obligatori de 30 segons, mostrant un comptador regressiu visual a la pantalla i impedint qualsevol interacció física.
    RF-10 (Event-driven) — Notificació de Seguretat Asíncrona a Torre de Control: QUAN es produeixi el tercer intent fallit consecutiu, EL SISTEMA generarà de forma automatitzada una "Alerta de Seguretat per Intents Fallits de PIN" enviant-la cap a la central de gestió (/gestio), o encuant-la en segon pla a l'IndexedDB si estan offline per a la seva transmissió idempotent tan bon punt es recuperi la connectivitat cellular.

Àmbit 4: Enrolament Inicial i Cicle de Vida davant Canvis de Dispositiu

    RF-11 (State-driven): SI l'operari canvia de telèfon mòbil físic però manté el seu número de línia corporativa actiu, ENTONCES només haurà d'accedir a l'adreça web corporativa de la PWA, executar el procés d'enrolament inicial via SMS OTP (RF-03) i introduir el seu PIN secret de 4 dígits habitual, descarregant les seves ordres i mantenint la custòdia d'actius sense requerir gestions tècniques.
    RF-12 (State-driven): SI l'operari canvia el seu número de telèfon mòbil de referència de l'empresa, ENTONCES EL SISTEMA exigirà que Secretaria o RRHH actualitzi de forma prèvia el nou número a la fitxa 360° de l'operari (Spec 008) abans de permetre qualsevol enrolament o accés de PIN en Next.js.

Àmbit 5: Recuperació de PIN Oblidat i Re-xifratge d'IndexedDB

    RF-13 (Ubiquitous): La pantalla de /operari/login incorporarà de forma prominent i visible a sota del numpad el botó d'assistència tècnica amb el text de seguretat: "Has oblidat el teu PIN?".
    RF-14 (Event-driven): QUAN l'operari premi el botó "Has oblidat el teu PIN?", la PWA mòbil obrirà el marcador telefònic natiu del dispositiu amb el número directe de la central de Secretaria per facilitar que l'operari sol·liciti l'assistència de l'administració de base de l'empresa.
    RF-15 (Event-driven) — Restabliment de PIN i Incidència de Seguretat: QUAN Secretaria restableixi el PIN d'un operari a /gestio/operaris (Spec 008), el backend de l'API de CampoPro generarà un codi PIN temporal de 4 dígits, enviant-lo exclusivament al telèfon de l'operari via un missatge SMS securitzat i creant de forma atòmica la "Incidència de Seguretat per Restabliment de PIN" en el seu expedient d'operari de base.
    RF-16 (State-driven) — Re-xifratge d'IndexedDB: En el primer inici de sessió que l'operari realitzi amb el PIN temporal sota cobertura mòbil activa, EL SISTEMA de la PWA executarà el re-xifratge complet i atòmic de la base IndexedDB local, derivant la nova clau de seguretat a partir del nou PIN i desant el nou bloc sentinella criptogràfic (RF-06) per restablir el Zero-Trust.

Àmbit 6: Tancament de Jornada, Tancament de Sessió (Logout) i Terminals Compartits

    RF-17 (Event-driven) — Bloqueig de PWA per Finalització de Jornada: QUAN el cap de colla o operari premi "Finalitzar Jornada Laboral" a la capçalera de feines (Spec 013) complint el RDL 8/2019, EL SISTEMA registrarà la sortida de la jornada, bloquejarà de forma automàtica la PWA mòbil i la redirigirà a /operari/login, evitant que el dispositiu quedi obert de forma vulnerable.
    RF-18 (Event-driven) — Logout segur i purga de memòria RAM: QUAN l'operari seleccioni l'opció "Tancar Sessió" (Logout) del menú mòbil, la PWA mòbil purgarà i eliminarà de forma destructiva les claus criptogràfiques temporals de la memòria RAM del navegador i revocarà les claus JWT, registrant-les de forma asíncrona a la llista negra de Redis de base de dades.
    RF-19 (State-driven) — Suport per a Dispositius Compartits de Flota: MIENTRAS el terminal mòbil de camp s'utilitzi de forma compartida (ex. furgonetes on l'oficial del torn de matí relleva al de la tarda, Spec 006 / 015), la interfície de login permetrà commutar de forma àgil d'usuari a la pantalla, oferint un botó "Canviar d'Operari" que purgui IndexedDB del torn anterior i demani el enrolament o PIN de l'operari entrant de forma idempotent.

Àmbit 7: Bloqueig d'Estat de Segon Pla (Background) i Inactivitat de Pantalla

    RF-20 (State-driven): La PWA de camp implementarà un temporitzador d'auto-bloqueig de seguretat per inactivitat de pantalla desatesa, sol·licitant de nou el PIN de 4 dígits un cop transcorregut un llindar màxim de 30 minuts de pantalla inactiva.
    RF-21 (Unwanted-behaviour) — Inhabilitació del Bloqueig en Obras Actives i Plànols: EL SISTEMA mantindrà estrictament inactiu i deshabilitat el temporitzador de bloqueig per inactivitat (RF-20) de la PWA mòbil MIENTRE l'operari es trobi visualitzant la llista de tasques en execució (Spec 013), utilitzant la fulla de picking/materials (Spec 014), o visualitzant plànols tècnics o xarxes de finques a /operari/planols (Spec 017), evitant interrupcions molestes durant la manipulació de rases o instal·lacions.
    RF-22 (State-driven) — Status de Segon Pla i Finestra de Cortesia: SI la PWA és enviada a segon pla (App Background) o es bloqueja físicament la pantalla del terminal de camp pel botó del mòbil, ENTONCES el sistema regeix el bloqueig sota les següents dues regles transaccionals de seguretat:
        Amb Tasca Activa (Start corrent): EL SISTEMA mantindrà desxifrada la base IndexedDB en la RAM durant un període de cortesia màxim de 5 minuts. Si l'operari reobre la PWA dins d'aquest interval, continuarà la seva tasca de forma immediata; si excedeix els 5 minuts, la PWA es bloquejarà demanant el PIN (mantenint el cronòmetre de la feina actiu calculant els temps correctament en segon pla).
        Sense Tasca Activa (En espera): EL SISTEMA bloquejarà immediatament la PWA en tancar o minimitzar l'aplicació, obligant a introduir el PIN de 4 dígits en reobrir per protegir dades sensibles davant robatoris físics de terminals.

Àmbit 8: Aïllament Multi-Inquilí Estricte (Zero-Trust) i Row Level Security

    RF-23 (Unwanted-behaviour) — Rebuig Opac Multi-Tenant: SI un dispositiu mòbil associat a un inquilí A de la plataforma multi-tenant intenta fer login o enrolament apuntant contra l'adreça de domini d'un inquilí B (empresaB.campopro.cat), ENTONCES el backend de l'API de CampoPro rebutjarà de forma automàtica la petició mitjançant un error genèric opac de credencials (ex. "Credencials no vàlides"), evitant qualsevol revelació d'identitat o fuga de dades d'altres tenants i registrant l'incident de seguretat al SIF.
    RF-24 (Ubiquitous) — Enllaç de Seguretat PostgreSQL RLS: Cada transacció, sincronització de shift de jornada o descàrrega de dades d'obra confirmada amb èxit per un operari, injectarà de forma obligatòria la variable d'inquilí app.current_empresa_id a nivell de PostgreSQL, garantint que el Row Level Security (RLS) s'apliqui amb la directiva FORCE ROW LEVEL SECURITY a tot l'arbre de dades de l'empresa.

--------------------------------------------------------------------------------
Taula de Casos Límit i Gestió d'Errors
Codi
	
Tipus EARS
	
Mòdul
	
Vector de Falla / Escenari d'Estrès
	
Comportament Requerit del Sistema
EDGE-01
	
Unwanted
	
PWA Sync
	
Pèrdua total de la bateria del terminal de camp mentre l'operari tenia una feina activa.
	
En recarregar el mòbil a la furgoneta i obrir la PWA, l'operari posa el PIN; el sistema desxifra l'IndexedDB xifrat, valida el sentinella PBKDF2 local, recupera l'estat exactat de la tasca en curs i manté el cronòmetre calculant el temps transcorregut sense pèrdues de dades d'hores de camp.
EDGE-02
	
Unwanted
	
PWA Seguretat
	
L'operari oblida el seu codi PIN de camp a la meitat d'una parcel·la rural rústica profunda sense cap mena de cobertura de xarxa GSM.
	
L'operari prem "Has oblidat el teu PIN?"; la PWA obre el marcador telefònic nadiu per realitzar la trucada per veu (ràdio-frecuencia) a Secretaria. Secretaria genera el PIN temporal; un cop el furgó surt de la zona de sombra rural i detecta connexió, l'operari accedeix i re-xifra l'IndexedDB de forma idempotent.
EDGE-03
	
Unwanted
	
Seguretat
	
L'operari tecleja ràpidament el seu PIN secret amb guants o mans mullades a camp, cometent 3 errors consecutius de pulsació.
	
La PWA mòbil de camp bloqueja incondicionalment el numpad durant 30 segons mostrant un cronòmetre de compte enrere visual a pantalla. En expirar els 30 segons, el teclat s'activa de nou de forma automàtica per permetre un nou intent físic.
EDGE-04
	
State-driven
	
Seguretat
	
Es produeix una consulta de plànols extremadament complexa a camp que manté l'operari inspeccionant capes durant 45 minuts sense interaccionar amb la pantalla.
	
La PWA mòbil de camp manté el temporitzador de bloqueig per inactivitat deshabilitat i inactiu (RF-21), evitant tancar la sessió a mig tajo i facilitant que l'operari continuï treballant sobre el terreny amb total fluïdesa.
EDGE-05
	
Unwanted
	
Seguretat
	
Sostracció o pèrdua física del terminal mòbil de l'operari durant la nit o fora de l'horari laboral de l'empresa.
	
La jornada de l'operari estava completament finalitzada i la PWA es troba bloquejada demanant PIN (RF-17). Totes les dades d'obra d'IndexedDB romanen xifrades sota l'algorisme AES-GCM derivat per PBKDF2, essent completament inaccessibles i opacs per a qualsevol agent no autoritzat.
EDGE-06
	
Unwanted
	
Seguretat
	
Un usuari maliciós o pertanyent a una empresa competidora de la plataforma intenta fer login utilitzant el telèfon d'un operari a un tenant diferent.
	
El backend de l'API de CampoPro rep la petició, detecta la manca de coincidència d'inquilí per subdomini o número a la taula, denega l'accés enviant un error genèric d'autenticació sense dades reveladores (RF-23), i llança rate-limiting (màx 5 intents/min).
EDGE-07
	
State-driven
	
Seguretat
	
Secretaria executa la baixa immediata (actiu = false) d'un operari des del panell de gestió de l'oficina mentre aquest té dades d'obra pendents de pujar.
	
El Service Worker de la PWA mòbil intercepta la revocació del token JWT de seguretat de Redis, bloqueja qualsevol transacció de camp, purga de forma destructiva l'IndexedDB local (dades de clients, plànols, codis de candats de furgonetes) i tanca la sessió a l'acte per protegir la propietat d'informació de l'inquilí.
EDGE-08
	
Event-driven
	
Seguretat
	
S'intenta realitzar un atac d'injecció SQL o de cross-site scripting (XSS) a través del numpad de la pantalla de login de la PWA mòbil.
	
El component Next.js de la pantalla de login filtra i restringeix les entrades del teclat exclusivament a caràcters numèrics simples de 4 caràcters, descartant i purificant qualsevol payload o text introduït de forma maliciosa.
EDGE-09
	
State-driven
	
Seguretat
	
Es dóna d'alta un operari d'oficina però s'intenta donar-li accés a la PWA de camp sota la Spec 008 sense dispositiu de referència.
	
El backend de l'API de seguretat de CampoPro rebutja la transacció i bloqueja el commit d'accés a camp de l'operari, forçant que tot compte operatiu contingui un dispositiu vàlid associat abans de la seva utilització.
EDGE-10
	
Event-driven
	
Seguretat
	
El servei asíncron de Redis o la llista negra de tokens de seguretat pateix una caiguda temporal de connexió al backend.
	
El backend de FastAPI commuta de forma transparent les consultes cap a un sistema de validació de signatures de tokens JWT de seguretat local no-bloquejant, garantint l'operació diària de l'empresa sense aturar els accessos de camp.
--------------------------------------------------------------------------------
Requisits No Funcionals (RNF)

    Almacenamiento Local Seguro Multi-Tenant (Soberano): Tots els tokens, secrets de dispositiu, claus de xifratge d'IndexedDB, i dades d'obra es guarden exclusivament sota l'algorisme de xifratge AES-256-GCM en el servidor sobirà Hetzner a Alemanya sota /docs/<empresa_id>/operaris/login/..., descartant completament AWS S3 per a estricte compliment de la LOPDGDD i el RGPD.
    Seguridad Multi-Tenant (RLS): Cada consulta, escriptura o modificació aplicada sobre les taules del mòdul d'autenticació i sessions s'aïlla de forma innegociable mitjançant Row Level Security (RLS) mandatori a nivell de PostgreSQL sota la variable d'inquilí app.current_empresa_id de forma universal sota la directiva FORCE ROW LEVEL SECURITY.
    Protección de Datos Macroeconómicos (Zero-Trust): Queda prohibit l'emmagatzematge de credencials administratives d'oficina (que compten amb seguretat 2FA TOTP i control salarial de la Spec 007 i Spec 011) a la base de dades local de la PWA mòbil de camp, segregant completament ambdós entorns de seguretat a l'API.
    Tolerancia Cero a Datos Ficticios (Zero-Mock): Si no hi ha personal operatiu donat d'alta al tenant d'onboarding, el llistat d'operaris compartits es renderitzarà de forma 100% neta de dades demostratives d'exemple o PINs predeterminats d'arquitectura.
    Rendimiento y Escalabilidad: El temps de resposta per a la validació de credentials del PIN de 4 caràcters al backend respondrà en Next.js en un temps inferior a 150 ms, processant les alertes de seguretat asíncronament via Celery + Redis per a no bloquejar l'event loop de FastAPI.

--------------------------------------------------------------------------------
Fora d'Abast (Out of Scope)

    No gestiona la creació de llicències SaaS o alta de dominis corporatius de la plataforma multi-inquilí (es governa al panell Superadmin).
    No realitza la integració o configuració del 2FA TOTP per als operaris de camp (es restringeix strictly als usuaris de Dashboard d'oficina sota la Spec 011).
    No suporta ni admet mètodes de validació biomètrics (com FaceID o reconeixements facials/dactilars) en dispositius PWA web mòbils per motius de privacitat i legalitat de dades del personal (RGPD).
    No es dóna suport a la introducció de dades de prova ni insercions simulades a cap nivell de codi del mòdul d'accés de camp (Zero Mock Data).

--------------------------------------------------------------------------------
Criteris de Finalització (Definition of Done) i Matriu de Traçabilitat
Per a poder certificar el tancament de la Spec 019 d'Autenticació i Sessió de camp i habilitar la seva fase de programació, s'ha de verificar el compliment estricte de la següent matriu de traçabilitat:

    Els 24 Requisits Funcionals (RF-01 al RF-24) i els 10 Casos Límit (EDGE-01 al EDGE-10) redactats amb sintaxi formal EARS estricta en català i lliures d'ambigüitats tècniques o dades de prova fictícies sota l'estat Dia 0.
    Correspondència del 100% de la spec d'autenticació de la PWA amb una suite de proves d'integració automatitzada en verd amb PostgreSQL RLS actiu sota el tenant real.
    Alineació total de la política de QR (Constitució v4.0): exclusió absoluta de codis QR per a les eines de camp (les quals es custodien i es traspassen per referència de fàbrica/SN), reservant el QR legal obligatori de facturació Veri*factu per a albarans i factures al tancament.
    Enrolament de Dispositiu via SMS OTP: implementació de la validació de registre de terminals mestre per a dispositius de camp (RF-03), evitant limitacions d'accessos de ràdio-frecuencia.
    Doble estat de Segon Pla (Background) segur: bloqueig de la sessió de camp transcorreguts 5 minuts de cortesia si hi ha feina activa o de forma instantània si la PWA es tanca en espera (RF-22).

Matriu de Traçabilitat 1:1 de la Definition of Done (DoD)
Codi de la Spec
	
Cas Límit Vinculat
	
Assert / Criteri de Validació DoD (Zero-Mock)
RF-01 / RF-02
	
-
	
Renderitzat de capçalera Camaleó en Next.js. El numpad tàctil és visible i operable.
RF-03
	
EDGE-09
	
Enrolament de dispositiu per SMS OTP. Intent d'assignar comptes sense furgó o terminal llança excepció 400.
RF-04
	
-
	
Entrada de PIN de 4 caràcters; l'autenticació s'activa a l'instant de completar el darrer dígit de forma transparent.
RF-05 / RF-06
	
EDGE-01
	
PBKDF2 (100k iteracions) i desat de sentinella criptogràfica; caiguda de connexió de la parcel·la és resolta localment.
RF-07
	
EDGE-05
	
Prohibició estricta de credencials en text pla. Robatori de mòbil conserva la privacitat d'IndexedDB xifrada.
RF-08
	
EDGE-03
	
Error de PIN neteja caselles i mostra avís vermell; intents de forcejar numpad llança neteja visual.
RF-09 / RF-10
	
EDGE-03
	
Bloqueig de seguretat de 30 segons; la notificació d'intents erronis és enviada asíncronament a central.
RF-11 / RF-12
	
-
	
Canvi de telèfon transparent per SMS OTP; modificació de número per Secretaria actualitza la PWA.
RF-13 / RF-14
	
EDGE-02
	
Botó d'assistència "Has oblidat el teu PIN?" obre marcador telefònic de veu per a trucar a Secretaria.
RF-15 / RF-16
	
EDGE-02
	
Nou PIN temporal via SMS genera incidència en fitxa 360 i el primer inici re-xifra l'IndexedDB local.
RF-17 / RF-18
	
EDGE-07
	
Tancament de jornada bloca la PWA; Logout purga les claus de la RAM de forma destructiva i JWT a Redis.
RF-19
	
-
	
Selector d'operaris al login de terminals de flota compartits; purga IndexedDB del torn anterior abans de tancar.
RF-20 / RF-21
	
EDGE-04
	
Auto-bloqueig de 30 minuts de pantalla desatesa; s'inhibeix en feines actives i visors de plànols.
RF-22
	
EDGE-01
	
Segon pla bloca la PWA als 5 min de cortesia si hi ha feina activa; manté els cronòmetres actius.
RF-23 / RF-24
	
EDGE-06
	
Rebuig opac d'accés des d'altres subdominis concurrents sota control PostgreSQL RLS de l'inquilí.