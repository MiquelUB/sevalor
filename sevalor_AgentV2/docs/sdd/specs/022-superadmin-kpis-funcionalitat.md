Spec 022 — Mòdul de Superadmin: Salut del Sistema, KPIs Funcionals de Plataforma i Control de Llicències SaaS (/superadmin) - v2
AVÍS D'ALINEACIÓ CONSTITUCIONAL I INTEGRACIÓ ARQUITECTÒNICA: Aquesta especificació tècnica es regeix de forma innegociable pels principis de la Constitució de CampoPro Suite (v4.0) i s'integra de forma transversal amb el Dashboard i la Torre de Control Geogràfica (Spec 001 i Spec 005), el Mòdul de Magatzem i Inventari (Spec 004), el Mòdul de Flota i Vehicles de la PWA (Spec 015), el Mòdul de Treballadors/Operaris (Spec 008), el Mòdul Contable (Spec 007), i l'especificació d'Aprovisionament de Tenants (Spec 021).
Es prohibeix taxativament l'ús de dades simulades o de prova (Zero Mock Data), partint d'un estat de "Dia 0" real i garantint de forma absoluta la sobirania de dades mitjançant l'emmagatzematge local/sobirà d'arxius i configs en el servidor Hetzner de Falkenstein (Alemanya - UE), rebutjant completament qualsevol servei de núvol públic extern (com AWS S3) d'acord amb el compliment estricte de la LOPDGDD i el RGPD.
--------------------------------------------------------------------------------
Context i Objectiu
El mòdul de Superadmin (/superadmin) és la Torre de Control Tècnica, Funcional i de Governança de Plataforma de CampoPro Suite. Concebut sota el patró arquitectònic modern i d'alt rendiment de plataformes de referència com Twenty CRM, actua exclusivament com a quadre de comandament per a l'equip d'enginyeria de sistemes i la propietat del SaaS, amb l'objectiu de monitoritzar la disponibilitat, estabilitat, concurrència i compliment de llicències de tot el parc d'aplicacions.
Aquest mòdul opera sota tres principis rectors innegociables:

    Principi de Privacitat Absoluta i Zero Intrusió en Dades de Negoci: El Superadmin té terminantment prohibit per arquitectura i disseny accedir a la informació privada o de negoci de les empreses inquilines o dels seus clients finals. El Superadmin mai pot consultar llistats de clients, adreces de finques, croquis privats, preus d'obra, facturació de treballs, números d'IBAN o fotografies de camp.
    Soberania i Segregació de Telemetria: Les dades d'auditoria de rendiment, temps de resposta de l'API, taxes d'error 500, estats de cues i logs de Celery s'emmagatzemen en un esquema de base de dades totalment independent (superadmin_telemetry) sota una connexió de PostgreSQL aïllada. Hetzner actua com a entorn d'execució sobirà, mantenint les metadades de l'aplicació lluny de qualsevol creuament de dades d'empreses clients.
    Enfocament Estricte en KPIs de Salut de Software: La telemetria del Superadmin se centra al 100% en la salut funcional, temps de resposta, ràtio d'errors d'API, gestió de cues, rendiment d'inferència de la IA local sota CPU-only i respecte a les quotes de llicència contractades.

--------------------------------------------------------------------------------
Usuaris / Actors i Matriu d'Interacció (Zero-Trust)
L'accés a /superadmin està completament segregat de les rutes de gestió empresarial (/gestio) i d'operaris (/operari):

    Superadministrador de Plataforma (HQ CampoPro): Accedeix amb credencials d'alta seguretat, IP Allowlist estricta i 2FA TOTP mandatori. Consulta la telemetria de salut, audita latències, supervisa l'estat de les cues en segon pla i gestiona les llicències dels tenants.
    Sistema de Telemetria i Mètriques (Prometheus / FastAPI Middleware): Recol·lecta mètriques anònimes d'ús, latències de peticions HTTP, estats de resposta (2xx, 4xx, 5xx) i consum de recursos sense registrar payloads amb dades personals.
    Atacant / IP No Autoritzada: Bloquejat de forma opaca i automàtica abans d'arribar a la pantalla de login de superadmin mitjançant tallafocs natius i IP Allowlist.

Matriu de Responsabilitats per Àmbit de Control
Àmbit de Control
	
Superadmin HQ
	
Empresa Inquilina
	
Motor de Telemetria
	
Accés a Dades Privades
Uptime i Latències d'API
	
Monitoritza disponibilitat i p95
	
Usuari del servei
	
Mesura temps en ms
	
❌ PROHIBIT
Errors de Programari (5xx)
	
Rep alertes de bugs o caigudes
	
Rep avís de servei degradat
	
Captura traces d'error tècniques
	
❌ PROHIBIT
Cues Celery i Redis
	
Supervisa tasques/min i cues
	
Envia feines des de l'app
	
Monitoritza workers actius
	
❌ PROHIBIT
Rendiment IA Local (CPU)
	
Monitoritza temps d'inferència
	
Envia àudios per processar
	
Mesura durada de càlcul en segons
	
❌ PROHIBIT
Quotes de Llicència
	
Assigna límit d'operaris (5, 15, 50)
	
Registra treballadors
	
Compta usuaris vs quota
	
❌ PROHIBIT
Mòduls Actius (Feature Flags)
	
Habilita/Inhabilita funcionalitats
	
Gaudeix dels mòduls actius
	
Restringeix accés a rutes
	
❌ PROHIBIT
Seguretat i IP Allowlist
	
Administra IPs autoritzades
	
Sense accés a superadmin
	
Valida origen de petició
	
❌ PROHIBIT
--------------------------------------------------------------------------------
Requisits Funcionals (EARS Notation)
Àmbit 1: Panell Central de Salut del Sistema, Disponibilitat i Latències

    RF-01 (Ubiquitous): La pantalla principal de /superadmin presentarà un tauler de control d'alta densitat d'estil Twenty CRM, mostrant els indicadors clau de disponibilitat de la plataforma en temps real: Uptime Global de la Plataforma (%), Latència Mitjana de l'API (ms, p50, p95 i p99), i Ràtio d'Èxit de Peticions HTTP (2xx/3xx vs 4xx/5xx).
    RF-02 (State-driven): SI la latència p95 de l'API supera els 500 ms de forma sostinguda durant més de 3 minuts, ENTONCES EL SISTEMA activarà un indicador visual d'alerta groga ("Rendiment degradat de l'API").
    RF-03 (Event-driven) — Segregació de Traces d'Error: QUAN es produeixi un error 500 no controlat, EL SISTEMA registrarà l'esdeveniment a la taula de telemetria tècnica de l'esquema d'usuari separat superadmin_telemetry (capturant la ruta de l'endpoint, l'stack trace de Python i la marca de temps ISO, sense registrar mai payloads ni dades de negoci del client).

Àmbit 2: Monitorització de Microserveis i Estat dels Contenidors

    RF-04 (Ubiquitous): El Superadmin mostrarà una matriu d'estat en viu (Health Check) dels 7 microserveis que componen CampoPro Suite: pwa (Next.js 14), backend (FastAPI / Uvicorn), db (PostgreSQL 16), redis (Redis 7), celery_worker (asíncron), celery_beat (tasques programades), i bot (Aiogram 3).
    RF-05 (State-driven): QUAN qualsevol dels microserveis deixi de respondre al seu endpoint intern de /health durant més de 30 segons, EL SISTEMA passarà el servei a estat Vermell Crític i emetrà una notificació de fallada.

Àmbit 3: Concurrència, Sessions Operatives i Pool de Base de Dades

    RF-06 (Ubiquitous): El sistema monitoritzarà el volum de concurrència de la plataforma, reflectint: Sessions Simultànies Actives (operaris i supervisors), i Estat del Pool de Connexions asíncron (asyncpg d'alta densitat).
    RF-07 (State-driven): SI l'ocupació del pool de connexions de PostgreSQL supera el 85% de la seva capacitat màxima, ENTONCES EL SISTEMA emetrà una alerta de "Saturació imminent de connexions de base de dades".

Àmbit 4: Rendiment de Cues de Tasques en Segon Pla (Celery / Redis)

    RF-08 (Ubiquitous): El Superadmin oferirà visibilitat en temps real del rendiment de les cues de tasques asíncronas gestionades per Celery i Redis: Volum de Tasques Processades per minut, Temps Mitjà a la Cua (Queue Wait Time), i Tasques Fallides.
    RF-09 (State-driven): SI la cua de Celery acumula més de 50 tasques pendents sense processar en la cua queue_sync o queue_media durant més de 2 minuts, ENTONCES EL SISTEMA alertarà de la necessitat d'escalar workers concurrents.

Àmbit 5: Telemetria de Rendiment de la IA Local sota CPU-Only (CPX21)

    RF-10 (Ubiquitous) — Constrangiment CPU-Only (Hetzner CPX21): El mòdul monitoritzarà el funcionament del node local d'IA (model Whisper v3 i Ollama) operant sota la restricció de la CPU-only d'Hetzner (3 vCPUs, sense GPU dedicada), avaluant:
        Temps d'inferència de transcripció Whisper (calculat mitjançant biblioteques optimitzades per a CPU com faster-whisper sota quantificació INT8).
        Ús de CPU i memòria RAM pel node d'IA.
        Taxa de Timeouts (>15 segons), disparant el fallback de Spec 012.
        Alerta de saturació de CPU de la màquina si se supera el 90% d'ús sostingut.
    RF-11 (Unwanted-behaviour): EL SISTEMA té la prohibició absoluta de registrar, interceptar, llegir o emmagatzemar el text de les transcripcions d'àudio de camp o de les consultes RAG sectorials sota el panell de Superadmin per privacitat.

Àmbit 6: Gestió de Llicències, Quotes d'Ús i Feature Flags

    RF-12 (Ubiquitous): El Superadmin disposarà d'una vista de gestió de llicències de tenants estil taula de Twenty CRM, detallant: Nom d'inquilí i subdomini, vertical tècnica contractada (CAMPOPRO, ELECTRICPRO, etc.), estat de llicència i dates de renovació.
    RF-13 (State-driven): EL SISTEMA verificarà que cada tenant respecta la seva quota d'operaris actius en base a PostgreSQL RLS, bloquejant altes extres a /gestio/operaris si se supera el pla (5, 15, o 50).
    RF-15 (Ubiquitous): El panell de Superadmin exposarà interruptors de control (Feature Flags) per a cada tenant, de manera que es pugui habilitar o inhabilitar dinàmicament l'accés a: copilot_ia, flota_avancada, planols_tecnics, i telegram_bot.

Àmbit 7: Compatibilitat de Versions i Desplegaments

    RF-16 (Ubiquitous): El Superadmin monitoritzarà la versió exacta del codi en execució tant per al frontend PWA com per al backend FastAPI, verificant la compatibilitat de versions entre tots els tenants.
    RF-17 (State-driven): SI un navegador mòbil executa una versió de Service Worker obsoleta, ENTONCES EL SISTEMA emetrà una directiva d'actualització forçada de memòria cache (Cache Busting).

Àmbit 8: Seguretat Zero-Trust, IP Allowlist i 2FA

    RF-18 (State-driven): L'accés a qualsevol ruta de /superadmin estarà restrictament capat per una IP Allowlist de base de dades, rebutjant intents externs de connexió de forma opaca amb codi HTTP 403.
    RF-19 (Ubiquitous): L'inici de sessió de superadministrador exigirà de forma obligatòria l'autenticació de doble factor basada en temps (2FA TOTP) de forma síncrona.

--------------------------------------------------------------------------------
Taula de Casos Límit i Gestió d'Errors
Cas Límit / Situació d'Error
	
Condició Desencadenant
	
Comportament Esperat del Sistema
Saturació d'API Matinal
	
Check-in massiu de furgonetes a les 08:00h satura el pool.
	
El Superadmin detecta un increment de p95; la cua de Celery absorbeix les sol·licituds i el pool de connexions asyncpg manté l'estabilitat sense rebutjar peticions.
Saturació de CPU per Whisper
	
Múltiples operaris envien àudios Whisper que saturen el CPU-only.
	
El sistema commuta a cua de reintent de baixa prioritat, activa el timeout d'IA local de 15s i aixeca alerta de saturació de CPU.
Downgrade Forçat
	
S'intenta aplicar el pla Starter (5) a un tenant amb 8 operaris actius.
	
El sistema bloca la modificació, emet l'avís d'excedent d'operaris i manté la quota de llicència fins al purgat.
Accés des d'IP No Autoritzada
	
Un atacant intenta accedir a /superadmin/login des d'una IP externa.
	
La petició es denega de forma fulminant a nivell de middleware/tallafocs abans de carregar cap recurs de la interfície.
--------------------------------------------------------------------------------
Criteris de Finalització (Definition of Done) i Matriu de Traçabilitat

    Els 20 Requisits Funcionals (RF-01 al RF-20) i els 4 Casos Límit redactats amb sintaxi formal EARS estricta en català i lliures d'ambigüitats.
    Segregació de dades de telemetria: les taules de KPIs d'uptime i traces d'error resideixen estrictament a l'esquema separat superadmin_telemetry de PostgreSQL, independent del tenant.
    Verificació de CPU-only: optimització asíncrona de Whisper amb faster-whisper a CPU INT8 per sota de 8 segons de cua, sense al·lucinacions.