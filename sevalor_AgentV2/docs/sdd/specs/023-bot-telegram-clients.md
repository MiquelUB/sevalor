Spec 023 — Microservei del Bot de Telegram per a Clients Finals (aiogram 3.x) - v2
AVÍS D'ALINEACIÓ CONSTITUCIONAL I INTEGRACIÓ ARQUITECTÒNICA: Aquesta especificació tècnica es regeix de forma innegociable pels principis de la Constitució de CampoPro Suite (v4.0) i s'integra de forma transversal amb el Dashboard i la Torre de Control Geogràfica (Spec 001 i Spec 005), el Mòdul de Clients (Spec 002), el Mòdul de Magatzem i Inventari (Spec 004), el Mòdul de Flota (Spec 006), el Mòdul de Treballadors/Operaris (Spec 008), el Mòdul Contable (Spec 007), i el Mòdul de Plànols (Spec 010).
Es prohibeix taxativament l'ús de dades simulades o de prova (Zero Mock Data), partint d'un estat de "Dia 0" real i garantint de forma absoluta la sobirania de dades mitjançant l'emmagatzematge local/sobirà d'arxius, tiquets, plànols i incidències en el servidor Hetzner de Falkenstein (Alemanya - UE), rebutjant completament qualsevol servei de núvol públic extern (com AWS S3) d'acord amb el compliment estricte de la LOPDGDD i el RGPD.
--------------------------------------------------------------------------------
Context i Objectiu
El microservei del Bot de Telegram per a Clients Finals (023-bot-telegram-clients.md) constitueix el Canal Bidireccional Asíncron, Interactiu i sense Barreres d'Instal·lació de CampoPro Suite. Implementat com un servei independent en Python 3.12 utilitzant el framework asíncron aiogram 3.x, permet als clients de les empreses instal·ladores rebre avisos d'obra en temps real, aprovar pressupostos d'imprevistos a 1 clic, reportar incidències amb fotografies i consultar informació freqüent mitjançant IA local, sense necessitat de descarregar cap app ni memoritzar usuaris o contrasenyes.
Aquest microservei s'articula sota els següents principis rectors:

    Zero Fricció per al Client Final: El client no ha de crear cap compte ni recordar credencials. L'accés s'estableix exclusivament mitjançant enllaços profunds unívocs (deep linking) transmesos per correu electrònic corporatiu (t.me/<BotUsername>?start=<token_segur>), associant de forma immediata el seu telegram_chat_id amb la seva fitxa de client a la base de dades.
    Blindatge davant d'Usuaris No Convidats (Zero-Trust): Qualsevol intent d'interacció procedent d'un compte de Telegram sense token d'invitació vàlid o no registrat a l'empresa es rebutja de forma opaca i automàtica, evitant l'obertura de converses no desitjades o intents de saturació de spam.
    Sobirania i Localitat de Dades: Els documents, factures i fotografies trameses pel client a través del bot no s'emmagatzemen a servidors de de tercers ni a instàncies públiques de núvol estrangeres. Les imatges rebudes es descarreguen atòmicament al volum dedicat d'emmagatzematge de l'empresa (/data/<empresa_id>/incidencies/), complint estrictament el RGPD.
    Interacció Human-in-the-Loop i Automatismes Restringits: Només tres esdeveniments de camp s'emeten de forma 100% automàtica cap al xat del client ("Operari en camí", "Operari arribat a finca" i "Feina acabada"). Tota la resta de comunicacions (pressupostos, incidències complexes i lliurament de documents) requereixen aprovació humana o supervisió tècnica pericial.
    Identitat Camaleònica (Chameleon Branding): Els missatges, encapçalaments, botons interactius i signatures del bot adopten automàticament la identitat corporativa, nom comercial i estil de l'empresa instal·ladora contractant del SaaS, sense referències visuals a CampoPro Suite.

--------------------------------------------------------------------------------
Usuaris / Actors i Matriu d'Interacció (Zero-Trust)

    Client Final de l'Empresa (Usuari de Telegram): Rep avisos d'arribada, visualitza fitxes de tasca, aprova pressupostos complementaris a 1 clic, adjunta fotografies d'avaries i resol dubtes freqüents mitjançant l'assistent.
    Microservei bot (aiogram 3.x en contenidor Docker): Gestiona les connexions entrants via Webhook segur des dels servidors de Telegram, processa callbacks d'inline keyboards, descarrega arxius multimèdia i manté l'estat conversacional (FSM) a Redis 7.
    Backend FastAPI (backend): Proporciona l'API REST asíncrona per consultar la informació del client, verificar tokens d'onboarding, segellar aprovacions de pressupostos i rebre alertes d'incidències per a la safata de /gestio/notificacions.
    Cua de Missatgeria Celery / Redis: Gestiona l'enviament asíncron de notificacions programades cap al bot de Telegram, garantint reintents automàtics i rate-limiting per no excedir els límits de l'API de Telegram (30 missatges/segon globals).

Matriu de Responsabilitats i Flux de Comunicació
Acció al Canal Telegram
	
Client Final
	
Microservei bot (aiogram)
	
Backend FastAPI / Celery
	
Dashboard /gestio
Vinculació per start
	
Obre deep-link
	
Valida token amb backend
	
Associa telegram_chat_id
	
Mostra client connectat
Avisos d'Estat de Camp
	
Llegeix missatge
	
Formata amb marca camaleó
	
Dispara tasca Celery
	
Reflicteix enviament
Aprovació de Pressupost
	
Clica botó verd
	
Captura callback query
	
Segella aprovació a BD
	
Actualitza a "Acceptat"
Petició de Canvis
	
Clica botó vermell
	
Obre estat FSM per al·legacions
	
Registra canvi d'estat
	
Alerta blava a safata
Enviament de Fotos
	
Adjunta foto/vídeo
	
Descarrega a disc sobirà
	
Registra metadades i RLS
	
Alerta vermella prioritària
Consulta FAQ d'Atenció
	
Escriu dubte
	
Consulta endpoint RAG local
	
Genera resposta en català
	
Registra al fil històric
Escalada per Incertesa
	
Escriu dubte complex
	
Detecta incertesa IA
	
Genera avís d'escalat
	
Alerta vermella urgent
Descàrrega Factura
	
Clica enllaç segur
	
Genera URL amb token 24h
	
Serveix PDF des de Hetzner
	
Registra descàrrega
--------------------------------------------------------------------------------
Requisits Funcionals (EARS Notation)
Àmbit 1: Arquitectura del Microservei, Webhooks i Aïllament Multi-Inquilí

    RF-01 (Ubiquitous): El servei de bot s'ha d'executar com un procés asíncron Python 3.12 independent sota el contenidor Docker bot, utilitzant el framework aiogram 3.x i el gestor d'estats finits (FSM) articulat sobre Redis 7, xifrant les claus d'FSM de forma aïllada per inquilí sota el patró fsm:{empresa_id}:{user_id}.
    RF-02 (Ubiquitous): La recepció de missatges de Telegram es realitzarà mitjançant Webhooks securitzats sobre HTTPS a través d'Nginx, verificant la capçalera de firma: X-Telegram-Bot-Api-Secret-Token == <webhook_secret_configurat> i rebutjant immediatament qualsevol crida sense ella amb un HTTP 403.
    RF-03 (State-driven): El microservei ha de proveir l'arquitectura multi-bot / multi-tenant on cada empresa inquilina pot disposar del seu propi token de bot configurat a /gestio/configuracio, enrutant-se les peticions a la ruta dinàmica /api/v1/telegram/webhook/{empresa_id}.
    RF-04 (Ubiquitous): Tota consulta del bot de Telegram a la base de dades s'aïllarà mitjançant Row Level Security (RLS) de PostgreSQL, injectant l'empresa_id a la connexió.

Àmbit 2: Vinculació per Deep-Linking i Blindatge d'Accés

    RF-05 (Event-driven): QUAN un client obri el bot amb el deep-link d'activació (/start <token_univoc>), EL SISTEMA demanarà la validació del token al backend: si és vàlid, registrarà el telegram_chat_id a la taula clients del tenant i retornarà benvinguda camaleònica Next.js; si és invàlid o ha superat les 48 hores d'emissió, blocarà la vinculació.
    RF-06 (Unwanted-behaviour): SI un usuari desconegut envia un missatge o el comandament /start sense token de vinculació vàlid, ENTONCES el bot respondrà de forma opaca: "Aquest és un canal privat d'atenció. Per accedir-hi, utilitzeu l'enllaç d'invitació facilitat per l'empresa" i descartarà el missatge sense obrir cap conversa al Dashboard.
    RF-07 (Ubiquitous) — Rate Limiting de Seguretat: EL SISTEMA aplicarà un control de concurrència i rate limiting ràpid sota Redis de màxim 10 missatges per minut per cada usuari de Telegram, ignorant peticions d'spam o flood.

Àmbit 3: Notificacions Automàtiques d'Estat de Camp (Tríada Operativa)

    RF-08 (Event-driven): QUAN l'operari marqui l'inici del desplaçament a la seva PWA, Celery instruirà el bot per a transmetre immediatament el missatge: "🚚 El nostre equip tècnic es troba en camí cap a les vostres instal·lacions. Temps estimat d'arribada: [ETA] minuts."
    RF-09 (Event-driven): QUAN la quadrilla confirmi l'arribada geolocalitzada a la geovalla de 50 m de la finca i activi el cronòmetre de feina, el bot enviarà automàticament: "📍 L'equip tècnic ha arribat a la vostra finca i comença els treballs (OT Ref #[REF])."
    RF-10 (Event-driven): QUAN l'operari tanqui la feina amb el protocol de 3 fotos, el bot enviarà: "✅ Treballs finalitzats satisfactòriament. Podeu consultar el resum." acompanyat d'un enllaç interactiu.
    RF-11 (Ubiquitous): Tota notificació fora de la tríada de camp (RF-08, RF-09, RF-10) requereix validació humana (Human-in-the-Loop).

Àmbit 4: Circuit d'Aprovació de Pressupostos i Imprevistos (Memòndum)

    RF-12 (Event-driven): QUAN l'oficina tècnica trameti un suplement o pressupost extra, el bot mostrarà el missatge interactiu amb el teclat integrat (Inline Keyboard): [📄 Consultar Memòndum], [✅ Acceptar Pressupost] i [❌ Sol·licitar modificacions].
    RF-13 (Event-driven) — Aprovació Atòmica i Idempotent: QUAN el client premi [✅ Acceptar Pressupost], el microservei capturarà el callback query amb el token_aprobacio, enllaçarà al backend per consolidar a ACCEPTAT, i editarà el missatge a Telegram de forma immutable substituint la botonera per un text permanent: "✅ Pressupost acceptat el [Data] a les [Hora]."
    RF-14 (Event-driven): QUAN el client premi [❌ Sol·licitar modificacions], el bot obrirà l'estat FSM a Redis (WAITING_BUDGET_FEEDBACK), retransmetent els aclariments del client a /gestio/notificacions en color blau (obert).

Àmbit 5: Obertura d'Incidències pel Client, Seguretat de Fitxers i Double-Extension Validation

    RF-15 (Event-driven): QUAN el client informi d'una avaria pel xat, el bot obrirà una incidència i el convidarà a adjuntar fotografies d'avaria per a anàlisi tècnica.
    RF-16 (Event-driven) — Descarrega Sobirana, Magic Bytes i Double-Extension Filter: QUAN el client enviï una fotografia o vídeo pel xat de Telegram, EL SISTEMA aplicarà les següents regles de seguretat abans de desar l'arxiu al disc local Hetzner (/data/<empresa_id>/incidencies/):
        El middleware d'aiogram analitzarà el nom del fitxer, rebutjant i blocant a l'acte qualsevol arxiu que contingui dobles extensions (ex. .pdf.exe, .jpg.sh, .png.bat) o qualsevol script amagat.
        El parser de backend verificarà els Magic Bytes (filetype) reals, descartant binaris brossa.
        Es prohibeix qualsevol ús de serveis cloud com AWS S3 per emmagatzematge dels xats, guardant-se de forma 100% sobirana en local.
    RF-17 (State-driven): En rebre fotos d'avaries, el bot commutarà immediatament la conversa a Vermell Prioritari a d'oficina.

Àmbit 6: Assistent Intel·ligent amb RAG Local, Sincronització de Rutes i Escalada Urgent

    RF-18 (Ubiquitous) — Unificació de Rutes d'Emmagatzematge RAG: El bot d'IA local connectarà semànticament les preguntes amb la base de coneixement d'FAQs corporatives de l'inquilí, configurant-se de forma estrictament aïllada sota el directori sobirà de l'empresa: /docs/<empresa_id>/knowledge/faqs/, rebutjant creuaments de dades de diferents tenants.
    RF-19 (Event-driven): QUAN el client demani tarifes, horaris o protocols de fuites, la IA respondrà de forma concisa i en català tècnic d'obra sense al·lucinar dades.
    RF-20 (State-driven) — Escalada Urgent per Baixa Confiança: SI el RAG retorna una confiança inferior al llindar de seguretat (Confidence Score < 0.75) o s'utilitzen paraules d'urgència ("urgent", "fuita", "foc"), ENTONCES el bot respondrà: "He traslladat la vostra consulta de forma urgent al nostre equip" i commutarà la conversa a Vermell Urgent a /gestio/notificacions.

Àmbit 7: Lliurament Segur de Factures Veri*factu

    RF-21 (Event-driven) — Factures de seguretat (Token Temporal de 24 Hores): QUAN Secretaria decideixi enviar una factura legal, el bot transmetrà un enllaç de descàrrega segur amb token temporal de seguretat amb una validesa màxima de 24 hores (establert com a estàndard de seguretat anti-leak d'oficina), allotjat a /docs/<empresa_id>/factures/emeses/.
    RF-22 (Unwanted-behaviour): Queda taxativament prohibit enviar o adjuntar la factura PDF com a document de fitxer directament a Telegram, assegurant la traçabilitat de descàrrega d'Hetzner i el RGPD.

Àmbit 8: Conformitat i Signatura Digital de Treballs

    RF-23 (Event-driven): En concloure una obra, el bot permetrà al client signar la conformitat de forma interactiva mitjançant el botó [✅ Donar Conformitat de la Feina], enllaçant directament amb el tancament de la fulla de tasca de camp de l'operari.

--------------------------------------------------------------------------------
Taula de Casos Límit i Gestió d'Errors
Cas Límit / Situació d'Error
	
Condició Desencadenant
	
Comportament Esperat del Sistema
Intrusió sense Token
	
Un usuari de Telegram desconegut escriu /start.
	
El bot rebutja l'accés, no desa res a la base de dades i no obre cap conversa per evitar spam.
Double Extension Attack
	
S'envia un document d'avaria amb nom reparacio.pdf.sh o similar.
	
El middleware d'aiogram detecta la doble extensió, bloqueja la pujada, purga l'arxiu i adverteix l'usuari.
Token de Factura Caducat
	
El client obre la factura de Hetzner 48 hores després del rebut.
	
El servidor denega la descàrrega i ofereix en una landing segura demanar un enllaç nou de 24h addicionals per email.
Caiguda d'IA local (LM Studio)
	
El client realitza una pregunta de FAQs i Ollama no respon en 10 segons.
	
El microservei aplica el timeout, demana disculpes indicant que un tècnic respondrà, i llança alerta a d'oficina.
--------------------------------------------------------------------------------
Criteris de Finalització (Definition of Done) i Matriu de Traçabilitat

    Els 23 Requisits Funcionals (RF-01 al RF-23) i els 4 Casos Límit redactats amb sintaxi formal EARS estricta en català i lliures d'ambigüitats.
    MIME & Double Extension validation: el programari compta amb proves pytest d'integració simulant atacs de format imatge amb injeccions de fitxers, blocant-los correctament.
    Lliurament de factura estrictament per enllaç temporal de 24 hores: s'exclou la pujada del PDF a Telegram per disseny de seguretat de l'inquilí.