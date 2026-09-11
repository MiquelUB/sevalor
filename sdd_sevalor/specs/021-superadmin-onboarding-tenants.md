Spec 021 — Mòdul de Superadmin: Aprovisionament de Tenants, Onboarding i Cicle de Vida SaaS (/superadmin/tenants) - v2
AVÍS D'ALINEACIÓ CONSTITUCIONAL I INTEGRACIÓ ARQUITECTÒNICA: Aquesta especificació tècnica es regeix de forma innegociable pels principis de la Constitució de CampoPro Suite (v4.0) i s'integra de forma transversal amb el Dashboard i la Torre de Control Geogràfica (Spec 001 i Spec 005), el Mòdul de Clients (Spec 002), el Mòdul de Magatzem i Inventari (Spec 004), el Mòdul d'Operaris (Spec 008), el Mòdul Contable (Spec 007), el Mòdul d'IA Copilot i RAG (Spec 012), i el Mòdul de Plànols de Camp (Spec 017).
Es prohibeix taxativament l'ús de dades simulades o de prova (Zero Mock Data), partint d'un estat de "Dia 0" real i garantint de forma absoluta la sobirania de dades mitjançant l'emmagatzematge local/sobirà en el servidor Hetzner de Falkenstein (Alemanya - UE), rebutjant completament qualsevol servei de núvol públic extern (com AWS S3) d'acord amb el compliment estricte de la LOPDGDD i el RGPD.
--------------------------------------------------------------------------------
Context i Objectiu
El mòdul d'Aprovisionament de Tenants, Onboarding i Cicle de Vida SaaS (/superadmin/tenants) constitueix el Motor de Governança Multi-Inquilí i Creixement Corporatiu de CampoPro Suite. Ubicat sota la ruta protegida /superadmin/tenants i dissenyat amb el patró d'alta densitat de Twenty CRM, permet a l'equip d'enginyeria i operacions de la plataforma donar d'alta, configurar, mantenir i gestionar el cicle de vida complet de cada empresa instal·ladora que contracta el servei.
Aquest mòdul materialitza la separació estricta entre la governança de la infraestructura SaaS i la privacitat del negoci dels clients:

    Aïllament Arquitectònic Absolut (Zero-Trust): El Superadmin gestiona els metadades de contracte, el subdomini tècnic, la quota d'operaris i els interruptors de funcionalitats (Feature Flags), però no té mai visibilitat ni accés a les dades operatives de l'empresa (clients, ordres de treball, finques, preus, factures o fotografies de camp), les quals queden aïllades per Row Level Security (RLS) a la base de dades PostgreSQL sota la directiva FORCE ROW LEVEL SECURITY.
    Aprovisionament Sobirà d'Emmagatzematge: En crear-se un nou tenant, el sistema inicialitza de forma atòmica i asíncrona (via Celery) l'arbre de directoris d'emmagatzematge sobirà dedicat al disc local del servidor (/data/<empresa_id>/... i /docs/<empresa_id>/...), garantint que els documents i imatges no es barregin ni s'allotgin en serveis cloud de tercers.
    Bootstrapping Segur del Compte Arrel (Boss): El procés d'onboarding genera la primera identitat administrativa de l'empresa mitjançant un enllaç d'activació criptogràfic d'un sol ús, imposant canvi de contrasenya d'alta seguretat i activació obligatòria d'autenticació de doble factor basada en temps (2FA TOTP) abans del primer accés al panell de gestió (/gestio).

--------------------------------------------------------------------------------
Usuaris / Actors i Matriu d'Interacció (Zero-Trust)

    Superadministrador de Plataforma (HQ CampoPro): Accedeix amb IP Allowlist i 2FA TOTP a /superadmin/tenants. Completa l'assistent d'onboarding, assigna la vertical de negoci, defineix el pla de llicència i supervisa l'estat del cicle de vida. Té vetada la lectura de les dades del negoci de l'inquilí per Postgres RLS.
    Sistema de Provisionament Asíncron (FastAPI + Celery): Executa les tasques atòmiques d'inicialització: creació del registre a PostgreSQL, generació de carpetes al disc sobirà, configuració del proxy Nginx per al subdomini i enviament del correu d'invitació xifrat.
    Gerent de l'Empresa Inquilina (Boss Inicial): Recull l'enllaç d'invitació, activa el seu compte configurant el 2FA TOTP de forma obligatòria i pren el control exclusiu de la seva instància a /gestio.

Matriu de Responsabilitats i Segregació de Privilegis
Operació de Governança
	
Superadmin HQ
	
Boss d'Empresa
	
Backend / Celery
	
Motor RLS (PostgreSQL)
Crear Empresa (Onboarding Wizard)
	
Executa formulari
	
Receptor d'invitació
	
Provisiona recursos
	
Assigna nou empresa_id
Assignar Vertical Tècnica
	
Selecciona vertical
	
Consulta a la UI
	
Configura RAG i Prompts
	
Inalterable per inquilí
Configurar Subdomini
	
Valida i assigna
	
Utilitza per accedir
	
Actualitza Nginx i SSL (Celery)
	
Segrega rutes per Host
Modificar Quota d'Operaris
	
Modifica pla
	
Rep límit d'altes
	
Actualitza restricció
	
Bloqueja a /gestio/operaris
Habilitar / Inhabilitar Feature Flags
	
Commuta flags
	
Gaudeix o no de mòdul
	
Aplica límits a l'API
	
Aïlla endpoints
Canviar Estat (Activar/Suspendre)
	
Canvia estat
	
Rep pantalla d'estat
	
Invalida tokens a Redis
	
Rebutja peticions d'inquilí
Accedir a Factures / Feines d'Obra
	
❌ PROHIBIT
	
Totalment autoritzat
	
Filtra per empresa_id
	
✅ Aïllament inviolable
--------------------------------------------------------------------------------
Requisits Funcionals (EARS Notation)
Àmbit 1: Assistent d'Alta i Provisionament d'un Nou Tenant (Onboarding Wizard)

    RF-01 (Ubiquitous): La vista /superadmin/tenants renderitzarà un assistent d'onboarding estructurat en passos (Wizard) d'alta densitat d'estil Twenty CRM que guiï l'equip d'operacions a través dels requisits administratius, tècnics i de llicenciament.
    RF-02 (Event-driven): QUAN el Superadmin iniciï l'alta d'una nova empresa, EL SISTEMA requerirà els camps administratius bàsics: Raó Social, NIF/CIF Corporatiu (validació algorítmica de format), Persona de Contacte, Correu Electrònic de Gerència (destinatari del Boss inicial) i Telèfon Corporatiu de Contacte (+34 per defecte).
    RF-03 (Event-driven): MENTRE es configuri la part tècnica del tenant, l'assistent exigirà la selecció d'una única Vertical Tècnica Especialitzada, la qual determinarà els models de RAG del Copilot d'IA, les plantilles d'ordres de treball i els formularis tècnics (CAMPOPRO, ELECTRICPRO, HYDROPRO, o BUILDINGPRO).
    RF-04 (Event-driven) — Configuració de Subdomini i Certificat SSL Asíncron: QUAN el Superadmin processi l'adreça de xarxa per al tenant, EL SISTEMA permetrà definir:
        Un subdomini estàndard del tipus <identificador>.campopro.cat (alfanumèric i guions, lliure de noms reservats com admin, superadmin, api, etc.).
        Un domini personalitzat opcional (ex. gestio.empresa.com).
        Sincronització asíncrona: La generació de la configuració de Nginx i l'obtenció del certificat TLS/SSL de Let's Encrypt mitjançant Certbot s'encuarà de forma strictly asíncrona a la cua de Celery queue_periodic per a evitar timeouts de Next.js, actualitzant l'estat a la pantalla de l'onboarding via WebSockets.
    RF-05 (Event-driven): QUAN es triï el pla de llicenciament, EL SISTEMA sol·licitarà el volum màxim d'operaris actius concurrents: Pla Starter (màxim 5 operaris a /gestio/operaris), Pla Pro (màxim 15 operaris), o Pla Enterprise (màxim 50 operaris).
    RF-06 (Ubiquitous): El formulari d'onboarding permetrà commutar de forma atòmica els Feature Flags per inquilí per activar/desactivar els mòduls de: copilot_ia, flota_avancada, planols_tecnics, i telegram_bot.

Àmbit 2: Aprovisionament Tècnic, Estructura de Volums i Aïllament RLS

    RF-07 (Event-driven): En confirmar el formulari d'alta d'un tenant, EL SISTEMA executarà una transacció de base de dades atòmica que insereixi el registre a la taula mestra empreses (UUID v4 d'empresa_id) i habiliti les polítiques de Row Level Security (RLS) vinculades.
    RF-08 (Event-driven) — Inicialització d'Arbre de Volums Sobirans: QUAN s'aprovi el tenant, EL SISTEMA delegarà a Celery la creació física local a Hetzner del directori sobirà de l'empresa sota les rutes:
        /data/<empresa_id>/incidencies/ (Fotos d'incidències i tiquets).
        /data/<empresa_id>/vehicles/ (Fotos d'odòmetres i tiquets de gasoil).
        /data/<empresa_id>/comptabilitat/ (Tiquets de despeses).
        /docs/<empresa_id>/planols/ (Plànols en PDF o vectorials).
        /docs/<empresa_id>/factures/ (Documents legals amb QR Veri*factu).
        /docs/<empresa_id>/backups/ (Backups setmanals xifrats, exclosos del zip recursiu).
    RF-09 (Unwanted-behaviour): SI falla qualsevol pas del provisionament tècnic (BD o disc), EL SISTEMA farà un rollback integral, esborrant les dades i directoris orfes i emetent una alerta d'error.

Àmbit 3: Creació del Compte Arrel de Gerència (Bootstrapping del Boss)

    RF-10 (Event-driven): En concloure el provisionament del tenant, EL SISTEMA crearà automàticament l'usuari arrel administratiu amb rol Boss assignat a l'adreça de gerència.
    RF-11 (Event-driven): El backend generarà un token d'activació criptogràfic de un sol ús (One-Time Activation Token) amb validesa de 24 hores i l'enviarà via correu transaccional segur.
    RF-12 (State-driven): QUAN el gerent accedeixi a l'enllaç d'invitació, EL SISTEMA exigirà de forma mandatoria abans de donar accés a /gestio:
        Definició de contrasenya d'alta seguretat de mínim 12 caràcters.
        Enrolament i validació obligatòria del secret 2FA TOTP escanejant el codi QR estàndard.

Àmbit 4: Governança del Cicle de Vida del Tenant (Lifecycle Management)

    RF-14 (Ubiquitous): Cada tenant es classificarà en un dels següents estats de llicència: TRIAL (14 dies), ACTIU (al corrent de pagament), SUSPÈS_PAGAMENT (bloquejat per deute), MANTENIMENT (aturat per actualització/migració), o BAIXA_OFFBOARDING (offboarding actiu).
    RF-15 (State-driven) — Bloqueig Immediat de Sessions: QUAN el Superadmin commuti un tenant a SUSPÈS_PAGAMENT, EL SISTEMA afegirà atòmicament tots els tokens JWT de la sessió del tenant a la llista negra de Redis, bloquejant rutes a /gestio i /operari, mantenint les dades i fitxers preservats de forma intacta al disc.
    RF-16 (State-driven) — Transició TRIAL a Suspès: SI un tenant TRIAL excedeix els 14 dies de prova sense formalitzar contractació, EL SISTEMA executarà de forma automàtica la transició asíncrona (via Celery Beat diari) a SUSPÈS_PAGAMENT, permetent liquidar les tasques o shifts en curs abans de bloquejar noves sessions.

Àmbit 5: Modificació de Quotes d'Operaris i Canvis de Pla

    RF-17 (Event-driven) — Upgrade i Downgrade de Llicències: EL SISTEMA permetrà canviar la quota de llicència des del panell lateral de Twenty CRM:
        Upgrade: S'aplica de forma immediata sense temps d'aturada.
        Downgrade: SI el Superadmin intenta reduir la quota de llicència (ex. de 15 a 5 operaris) quan el tenant té actualment registrats 8 operaris en estat actiu a /gestio/operaris, ENTONCES EL SISTEMA bloquejarà de forma taxativa la mutació, exigint donar de baixa primer els 3 treballadors sobrants.

Àmbit 6: Procediment de Baixa Certificada i Offboarding (RGPD)

    RF-18 (Event-driven): QUAN un tenant demani la baixa del servei, el Superadmin commutarà l'estat a BAIXA_OFFBOARDING, iniciant un període de gràcia legal de custòdia de 30 dies naturals.
    RF-19 (Event-driven) — Exportació Sobirana i Certificat de Destrucció: Durant la fase d'offboarding, EL SISTEMA proporcionarà una eina d'exportació que generi un paquet ZIP xifrat amb AES-256 amb els fitxers de l'empresa (/data i /docs). Una vegada confirmat l'offboarding i executada la supressió definitiva de dades, EL SISTEMA generarà un Certificat de Destrucció de Dades unívol i digitalment signat per la plataforma que certifiqui el purgat del RGPD, arxivant el receipt durant 5 anys.

--------------------------------------------------------------------------------
Taula de Casos Límit i Gestió d'Errors
Cas Límit / Situació d'Error
	
Condició Desencadenant
	
Comportament Esperat del Sistema
Col·lisió de Subdomini
	
Es tria un subdomini que ja està en ús o és reservat.
	
L'assistent valida en temps real via AJAX i bloqueja el pas indicant "El subdomini indicat ja es troba assignat".
CIF / NIF Erroni
	
El NIF corporatiu de l'empresa no compleix el dígit de control espanyol.
	
L'assistent bloqueja el commit destacant el camp en vermell.
Downgrade Invàlid
	
Es redueix la llicència a un llindar inferior d'operaris actius reals.
	
El backend bloqueja l'escriptura, exigint desactivar operaris prèviament a /gestio/operaris.
Caducitat d'Invitació
	
El gerent obre l'enllaç d'invitació Boss transcorregudes 24 hores.
	
El portal mostra "Invitació caducada" i habilita al Superadmin regenerar el token amb 1 clic des del panell.
Accés de Tenant Suspès
	
Un operari o supervisor d'un tenant en estat SUSPÈS_PAGAMENT intenta connectar.
	
L'API FastAPI intercepta el middleware i retorna error 403 opac amb pantalla de suspensió de dades.
Caiguda de Certbot en SSL
	
Certbot falla per DNS no propagat en crear el domini personalitzat.
	
La tasca asíncrona de Celery Beat rep l'error, fa reintent amb backoff, i en cas d'exhaurir-se, commuta l'estat a PENDENT_SSL alertant a suport de CampoPro.
--------------------------------------------------------------------------------
Criteris de Finalització (Definition of Done) i Matriu de Traçabilitat

    Els 22 Requisits Funcionals (RF-01 al RF-22) i els 6 Casos Límit redactats amb sintaxi formal EARS estricta en català i lliures de dades mock o simulades.
    Aïllament PostgreSQL RLS provat unítariament: un supervisor o Superadmin de la plataforma té estrictament prohibit realitzar SELECT sobre dades d'altres inquilins (empresa_id).
    Certificat de Destrucció de Dades digital: l' offboarding purga els volums i schemas en cascada, guardant l'assegurança criptogràfica del procés d'esborrat de forma persistent.