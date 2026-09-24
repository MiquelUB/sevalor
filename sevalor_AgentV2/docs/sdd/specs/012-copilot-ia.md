Spec 012 — Mòdul d'IA Copilot de Camp i Gestió (/gestio/copilot & PWA)
AVÍS D'ALINEACIÓ CONSTITUCIONAL I INTEGRACIÓ ARQUITECTÒNICA: Aquesta especificació tècnica es regeix de forma innegociable pels principis de la Constitució de CampoPro Suite (v4.0) i s'integra de forma transversal amb la Torre de Control Geogràfica en temps real (Spec 001 i Spec 005), el Mòdul de Clients (Spec 002), el Mòdul de Proveïdors (Spec 003), el Mòdul de Magatzem (Spec 004), el Mòdul de Flota (Spec 006), el Mòdul d'Operaris (Spec 008) i el Mòdul Contable (Spec 007).
Es prohibeix taxativament l'ús de dades simulades o de prova (Zero Mock Data), partint d'un estat de "Dia 0" real i garantint de forma absoluta la sobirania de dades mitjançant el processament i emmagatzematge 100% local de la IA en el servidor Hetzner de Falkenstein (Alemanya - UE), rebutjant completament qualsevol servei de núvol públic extern (com OpenAI, Anthropic o AWS S3) d'acord amb el compliment estricte de la LOPDGDD, la Llei d'Intel·ligència Artificial de la UE (AI Act) i el RGPD.
De conformitat amb la Constitució v4.0, es recorda que s'exclou l'ús de codis QR per a les eines de camp (les quals es traçabilitzen i es custodien exclusivament pel seu número de referència, marca i model de fàbrica), mantenint-se únicament el codi QR de caràcter legal i tributari obligatori per a la facturació Veri*factu sota la AEAT (Spec 007).
--------------------------------------------------------------------------------
Context i Objectiu
El mòdul d'IA Copilot de Camp i Gestió (/gestio/copilot) és el Motor Pericial, Assistent Tècnic i Cor Intel·ligent de CampoPro Suite. Assisteix en temps real als quatre actors de la plataforma (Operari a la PWA, Enginyer a l'Oficina Tècnica, Administració/Boss i Client Final).
Aquest mòdul no actua com un generador genèric de text conversacional ni redacta paràgrafs buits que ningú llegirà: el seu valor rau estrictament en l'auditoria operativa de camp, la memòria tècnica històrica de finques, l'alerta de garanties, el peritatge d'incidències de camp per veu/foto, el control de desviacions pressupostàries i la proposta de pressupostos corregits post-obra.
El Copilot opera sota tres principis rectors absoluts:

    Principi Innegociable Human-in-the-Loop (HITL): El Copilot és estrictament un assistent que analitza, transcriu, perita, calcula i proposa; mai bloqueja operacions crítiques (sempre avisa i informa) i mai emet factures, comandes a proveïdors ni tanca incidències de forma desatesa sense la confirmació humana explícita de l'Enginyer, de la Secretaria o del Boss.
    Sobirania de Dades i Processament 100% Local: Totes les inferències de llenguatge (LM Studio / Ollama), transcripció de veu (Whisper) i visió artificial s'executen al servidor Hetzner a Alemanya dins de la xarxa sobirana de l'empresa, sense enviar mai dades confidencials de clients, preus ni fotografies d'instal·lacions a núvols públics privatius de tercers, garantint el compliment estricte de la RGPD i la seguretat de secrets comercials.
    Tolerància Zero a Dades Fictícies (Zero Mock Data): El Copilot té terminantment prohibit inventar o al·lucinar informació. Davant de finques noves o absència d'antecedents, té l'ordre estricta de declarar amb veracitat: "No tinc informació registrada sobre aquest element", sense inventar mai avaries ni peces anteriors.

--------------------------------------------------------------------------------
Usuaris / Actors i Matriu d'Interacció (Zero-Trust)
El backend aïlla les dades de la IA mitjançant Row Level Security (RLS) mandatori a nivell de base de dades i carpetes privades per inquilí (empresa_id):

    Boss (Gerència / Propietari): Supervisa el rendiment operatiu i les alertes de desviació econòmica d'obra. Rep les propostes de comandes de reposició preventiva de stock generades pel Copilot quan s'assignen feines, supervisa els marges comercials liquidats i disposa d'accés a les auditories de peritatge.
    Enginyer / Supervisor Tècnic (/gestio): Principal interlocutor del Copilot. Rep les alertes del Memoràndum Tècnic d'incidències de camp, revisa les advertències de garanties de peces i mà d'obra abans de planificar, audita la comparativa entre la fulla de tasca inicial i la realitat de camp rebent el pressupost corregit proposat, i interactua amb la finestra de xat tècnic per a consultes de normativa d'ofici o protocols corporatius.
    Secretaria / Administració: Rep les propostes de compra anticipada a proveïdors generades pel Copilot quan l'estoc cau sota mínims, consulta el dictamen d'incidències pericials i tramita les factures oficials Veri*factu un cop l'Enginyer ha aprovat el pressupost corregit.
    Responsable de Colla i Operari (/operari): Interacció minimalista governada pel Flujo de los 30 segundos. En detectar un imprevist o anomalia, prem el botó 🚨 Foto Incidència i enregistra una nota de veu (.webm/.ogg) acompanyada de la foto de l'avaria, sense haver d'escriure text a la pantalla del mòbil.
    Client Final (Canal Telegram / Email): Receptor passiu de notificacions quirúrgicament precises generades pel sistema i supervisades per l'Enginyer (avisos d'arribada, pressupostos d'extres per incidència amb botons d'aprovació i parts de feina conclosa).

Matriu de Responsabilitats i Validacions de la IA
Àmbit d'Actuació de la IA
	
Rol del Copilot IA
	
Interlocutor Humà Responsable
	
Validació Obligatòria
Detecció de Garanties
	
Alerta i Informa (Sense Bloquejar)
	
Enginyer Tècnic
	
Revisor Humà decideix aplicació
Peritatge d'Incidència
	
Transcriu, Analitza i Redacta Memoràndum
	
Enginyer Tècnic
	
Enginyer edita i aprova enviament
Avaluació de Sobrecost
	
Proposa dictamen d'Extra vs Error Intern
	
Enginyer Tècnic
	
Prevalença Human-in-the-Loop
Reconciliació Post-Obra
	
Compara fulla inicial vs PWA i incidències
	
Enginyer Tècnic
	
Supervisió de qualsevol desviació
Tancament de Feina
	
Proposa Nou Pressupost Corregit
	
Enginyer / Secretaria
	
Enginyer envia a facturació
Alerta de Recompra
	
Genera Esborrany de Comanda
	
Secretaria / Boss
	
Emissió oficial a 1 clic
Consultes Tècniques
	
Respon via Xat Tècnic amb RAG Local
	
Enginyer / Secretaria
	
Consulta informativa
--------------------------------------------------------------------------------
Requisits Funcionals (Notació EARS Estricta)
Bloque 1: Infraestructura d'IA Local, Cues i Tolerància a Fallades

    RF-01 (Ubiquitous): EL SISTEMA executarà totes les tasques d'inferència de llenguatge natural, transcripció de veu (Whisper v3) i anàlisi de visió pericial al node local d'IA de la pròpia empresa allotjat al servidor Hetzner de Falkenstein (Alemanya - UE) amb xifrat en repòs AES-256-GCM, quedant completament prohibit l'enviament de dades d'obra, àudios o fotos a serveis d'IA al núvol públic privatiu (com OpenAI o Anthropic).
    RF-02 (State-driven): MIENTRAS el servei de cues Celery processi peticions concurrents al node d'IA local, EL SISTEMA prioritzarà de forma estricta les tasques operatives de camp (transcripcions d'incidències d'operaris i tancaments de fulles de tasca de la PWA) per davant de les consultes informatives del xat web d'enginyeria d'oficina.
    RF-03 (Unwanted-behaviour): SI el motor d'IA local pateix una caiguda, sobrecàrrega o un temps de resposta superior al límit de seguretat (timeout > 15 segons), EL SISTEMA no bloquejarà mai l'operativa d'obra i mostrarà immediatament el missatge "Copilot provisionalment no disponible (Timeout)", deixant accessible a la Torre de Control de l'Enginyer l'arxiu d'àudio natiu i la fotografia per a la seva resolució manual de forma síncrona.

Bloque 2: Memòria Històrica de Finca i Auditoria de Garanties

    RF-04 (Event-driven): QUAN l'Enginyer seleccioni un client, finca o parcel·la a /gestio/feines o /gestio/clients/{id}, EL SISTEMA recopilarà cronològicament totes les intervencions tècniques, peces instal·lades i incidències registrades en aquell emplaçament durant els últims 365 dies (1 any natural), estructurant una visió 360° per a l'Enginyer.
    RF-05 (Event-driven): QUAN es planifiqui la intervenció sobre un component prèviament instal·lat, EL SISTEMA auditará si la peça disposa de Garantia Oficial de Fabricant vigent (2 o 3 anys) a partir de la seva data d'adquisició o número de sèrie, marca i model (registrats a les Specs 004 i 008).
    RF-06 (State-driven): SI el Copilot detecta que un component es troba en període de garantia oficial de fabricant, EL SISTEMA llançarà una alerta destacada a l'Enginyer: "⚠️ ATENCIÓ: L'equip [Model, Nº Sèrie] instal·lat el [Data] disposa de garantia oficial del fabricant vigent fins al [Data Fi]. Es proposa tramitar garantia/RMA amb el proveïdor [Nombre] en lloc de facturar la peça nova al client", mantenint la planificació completament operativa i evitant el cobrament erroni.
    RF-07 (Event-driven): QUAN es planifiqui una actuació sobre una instal·lació que va ser intervinguda per la nostra pròpia empresa en un termini inferior a 3 mesos (o el període pactat per conveni), EL SISTEMA informarà a l'Enginyer de l'existència de la Garantia de Mà d'Obra de l'Empresa, facilitant la seva catalogació com a garantia interna de servei a cost 0 € per al client si es tracta de la mateixa avaria.

Bloque 3: Peritatge d'Incidències Multimodal i Memoràndum Tècnic

    RF-08 (Event-driven): QUAN un operari a camp activi el botó 🚨 Foto Incidència a la PWA mòbil i registri una nota de veu (.webm/.ogg) acompanyada d'una fotografia geolocalitzada, EL SISTEMA executarà en segon pla (Celery) la transcripció fonètica precisa de l'àudio (reconeixent català i castellà tècnic d'obra amb Whisper v3) i l'anàlisi de patrons de fallada de la imatge.
    RF-09 (Event-driven): A partir de l'àudio i la imatge transmesos, EL SISTEMA redactará el Memoràndum Tècnic d'Incidència per a l'Enginyer, avaluant l'anomalia per determinar si concorre un sobrecost:
        Imprevist / Dany Preexistent de la Finca: Proposa qualificar-lo com a Extra Facturable per al client (ex. arrels externes que estrangulen un ramal, terreny rocós imprevist).
        Contingència Operativa / Error de la Quadrilla: Proposa qualificar-lo com a Cost No Imputable al Client (assumit internament per l'empresa).
    RF-10 (Ubiquitous): EL SISTEMA mantindrà la validació humana prèvia (HITL) sota estricta condició: el dictamen del Memoràndum Tècnic és una proposta que l'Enginyer ha de revisar, podent alterar la qualificació pericial, modificar les quantitats de material proposades o ajustar l'import abans que s'emeti cap comunicació o pressupost d'extra cap al client via Telegram o Email (Spec 009).

Bloque 4: Reconciliació Post-Obra, Desviacions i Pressupost Corregit

    RF-11 (Event-driven): QUAN el Cap de Colla tanqui una ordre de treball a la PWA mòbil, EL SISTEMA reconciliarà automàticament els quatre pilars del cost real:
        Materials de Magatzem: Unitats extretes al picking matinal menys devolucions reals verificades a nau o furgoneta (Spec 004).
        Mà d'Obra Efectiva: Minuts exactes de presència dels operaris a la finca segons els fitxatges de la jornada (Spec 008).
        Quilometratge de Flota: Km recorreguts segons el registre d'odòmetre per fotografia de la PWA validada per OCR (Spec 006).
        Tiquets de Despesa de Camp: Imports i fotos de compres d'urgència o despeses de ruta associades a la tasca (Spec 007).
    RF-12 (Ubiquitous): EL SISTEMA compararà de forma atòmica la fulla de tasca inicial amb el part executat a la PWA i les incidències ocorregudes, informant visualment al supervisor de qualsevol desviació de mà d'obra, materials consumits o impacte sobre el marge comercial previst de l'empresa.
    RF-13 (Ubiquitous): EL SISTEMA bloquejarà qualsevol emissió o facturació automatitzada de documents: en finalitzar l'auditoria post-obra, el Copilot proposarà un nou pressupost corregit que reculli les partides reals i els suplements aprovats, el qual serà transmès a facturació (Secretaria/Boss) sota format de previsualització inmutable fins a la confirmació humana de l'Enginyer.

Bloque 5: Alerta Preventiva de Recompra de Stock en Assignació

    RF-14 (Event-driven): EN el moment en què un Enginyer assigni una ordre de treball a una quadrilla a /gestio/feines, EL SISTEMA calcularà el consum estimat de materials i restarà virtualment la quantitat del saldo d'existències del magatzem central de la nau.
    RF-15 (State-driven): SI el saldo restant de materials projecta que un article crític quedarà per sota del seu Umbral Mínim de Seguretat configurat, EL SISTEMA emetrà immediatament una Alerta Preventiva de Recompra Anticipada i generará un esborrany de comanda de reposició de stock dirigit al proveïdor habitual (amb preus pactats de la Spec 003), col·locant-lo a la safata de compres de Secretaria/Boss per a la seva emissió a 1 clic, amb control d'idempotència transaccional de canvi de stock (EDGE-06).

Bloque 6: Aïllament Estricte per Vertical i RAG Multinivell

    RF-16 (Ubiquitous): EL SISTEMA proveirà un RAG d'IA local i aïllat per a cada empresa client sota la injecció de la variable app.current_empresa_id a PostgreSQL, configurant el motor d'intel·ligència en base a la vertical tècnica contractada:
        CAMPOPRO: Vocabulario agronómico, regadíos, presiones de bombas, fertirrigación, zanjas en suelo rústico y maquinaria agrícola.
        ELECTRICPRO: Vocabulario electrotécnico, estricta conformidad con el REBT (Reglamento Electrotécnico de Baja Tensión), intensidades de corte, caídas de tensión por sección de cable (mm²) y curvas de magnetotérmicos.
        HYDROPRO: Fontanería técnica, depuración, pérdidas de carga por accesorios y caudales (m³/h).
        BUILDINGPRO: Edificación, albañilería, estructuras y acabados técnicos.
    RF-17 (Ubiquitous): EL SISTEMA prohibirà estrictament el creuament o utilització de vocabularis, fórmules, preus o directrius tècniques entre verticals diferents.
    RF-18 (Ubiquitous): EL SISTEMA protegirà l'aïllament multi-tenant en reposo i en memòria: totes les cerques semàntiques, anàlisi de documents i recuperació de mermes del Copilot injectaran obligatòriament la variable app.current_empresa_id, impedint qualsevol accés de la IA a dades de terceres empreses clientes.

Bloque 7: Finestra de Xat Tècnic Web (/gestio) i Veto de Rols

    RF-19 (Ubiquitous): EL SISTEMA habilitarà al panell web /gestio de supervisió de l'oficina una Finestra de Xat Tècnic amb el Copilot accessible per als rols autoritzats (Enginyers, Secretaria i Boss).
    RF-20 (Event-driven): QUAN un usuari realitzi una consulta operativa o de normativa en llenguatge natural, EL SISTEMA generarà una resposta concisa i quirúrgica fonamentant-se en el RAG local (Normativa sectorial + Protocols de l'empresa), facilitant enllaços directes a les fitxes o documents del sistema relacionats.
    RF-20.1 (Unwanted-behaviour): SI un usuari amb rol Enginyer de Camp intenta consultar a través del Xat d'IA dades confidencials agregades de comptabilitat, llibre major, salaris, nòmines de personal o comptes bancaris de proveïdors, EL SISTEMA denegarà l'acció amb un missatge d'error de seguretat, aplicant el veto financer i de rols a nivell d'API (HTTP 403 Forbidden).

Bloque 8: Tolerància Zero a Dades Fictícies (Zero Mock Data)

    RF-21 (Ubiquitous): EL SISTEMA vetarà qualsevol intent o ordre del Copilot de simular, inventar o omplir dades tècniques, números de sèrie d'eines o llistes de recanvis de forma fictícia sota el principi d'auditoria pericial del negoci.
    RF-22 (State-driven): SI el Copilot no disposa d'informació documental o antecedents reals a la base de dades sobre una finca, client, vehicle o component, EL SISTEMA respondrà de forma directa i categòrica: "No tinc informació registrada sobre aquest element", sense realitzar asuncions o hipòtesis.

--------------------------------------------------------------------------------
Taula de Casos Límit i Gestió d'Errors
Codi
	
Tipus EARS
	
Mòdul
	
Vector de Falla / Escenari d'Estrès
	
Comportament Requerit del Sistema
EDGE-01
	
Unwanted
	
Celery
	
Saturació del node d'IA local per crides concurrents al tancament de jornades.
	
La cua de Celery prioritza strictly les tasques operatives de camp (transcripcions Whisper i tancaments de fulles de tasca PWA) per davant de les consultes informatives del xat web d'enginyeria, evitant retards en camp.
EDGE-02
	
Unwanted
	
Backend
	
Timeout o caiguda del servei d'IA local (>15 segons).
	
La interfície web mostra el missatge de fallida no bloquejant: "Copilot provisionalment no disponible (Timeout)". L'àudio original i les fotografies de camp es presenten immediatament a l'Enginyer a la Torre de Control perquè pugui actuar manualment de forma síncrona.
EDGE-03
	
Unwanted
	
Whisper
	
Àudio de nota de veu d'operari inaudible per soroll extrem de tractors o vent.
	
Whisper detecta un coeficient de confiança acústica inferior al 40%, transcriu els fragments comprensibles, afegeix de forma automatitzada la marca: "⚠️ L'àudio conté soroll de fons sever" i recomana a l'Enginyer fer un contrast visual mitjançant la fotografia pericial adjunta.
EDGE-04
	
State-driven
	
PWA
	
L'operari tanca una obra de camp offline en zona blanca i la sincronització de fotos es retarda fins al dia següent.
	
EL SISTEMA bloquejarà la redacció de la factura de liquidació final de materials a Comptabilitat (Spec 007), mantenint la línia de Triple Conciliació en estat "Pendiente de Campo" fins que el capataz realitzi el sync complet a la nau, evitant descuidats comercials.
EDGE-05
	
Unwanted
	
Seguretat
	
L'Enginyer de Camp utilitza el xat del Copilot per demanar informació confidencial de nòmines (Spec 007) o preus d'adquisició (Spec 004).
	
El backend de seguretat de rols intercepta la intenció, bloca el PUT/GET de dades salarials o balances i retorna un error HTTP 403 Forbidden amb la resposta: "Consulta no autoritzada per política de rols de seguretat".
EDGE-06
	
Event-driven
	
Stock
	
Dos enginyers executen simultàniament la reserva de stock del mateix material crític que cau sota mínims.
	
PostgreSQL aplica la clàusula SELECT FOR UPDATE dins la transacció ACID; el primer request s'enregistra correctament i exhaureix el stock virtual d'almacén, i el segon commit es rebutja generant excepció HTTP 400 Bad Request amb error: "Estoc insuficient per concurrència de reserves".
EDGE-07
	
Event-driven
	
Garantia
	
Un component (bomba de reg) es danyat de forma imprevista 2 anys i 5 dies després de la compra (garantia de fabricant de 2 anys recent expirada).
	
El Copilot alerta a l'Enginyer: "La garantia oficial de 2 anys va expirar el [Data Fa 5 Dies]. Es suggereix consultar comercialment amb el proveïdor si admet l'esmena de la peça per deferència abans de pressupostar nova peça al client".
EDGE-08
	
Unwanted
	
Desviacions
	
Es tanca una obra a camp reportant un consum de materials de format continu >250% del previst sense cap incidència de camp prèvia registrada.
	
El Copilot emet una Alerta de Merma Operativa no Justificada: "Consum de tub PE-32 excedit en +25m (+250%) sense cap incidència de camp reportada a la fulla de tasca", requerint revisió humana obligatòria del supervisor abans de poder procedir al tancament.
EDGE-09
	
State-driven
	
Zero-Mock
	
L'Enginyer obre una ordre de treball per a una finca que mai ha estat intervinguda per l'empresa.
	
El Copilot respon estrictament: "No tinc informació prèvia d'aquesta finca. Primer servei registrat", complint amb el principi Zero Mock Data i sense inventar peces ni esquemes d'obra.
EDGE-10
	
Event-driven
	
RAG
	
Un operari d'una vertical elèctrica realitza preguntes de disseny hidràulic o cabal de bombes al seu assistent.
	
El Copilot declina la resposta de forma sobirana, indicant que la seva base de coneixement i context s'acoten de forma exclusiva al sector REBT i baixa tensió de l'empresa, evitant l'ús erroni o injecció de variables creuades.
--------------------------------------------------------------------------------
Requisits No Funcionals (RNF)

    Privatitat i Processament Soberà d'IA (Sense APIs al Núvol): Totes les inferències de text, transcripcions de veu amb Whisper i anàlisi de visió pericial s'executen de forma local i sobirana al servidor Hetzner de Falkenstein (Alemanya - UE), inhabilitant l'accés a nubes públiques com OpenAI, Anthropic o AWS S3 per garantir el compliment del RGPD.
    Soberania i Aïllament Multi-Tenant (RLS): Aïllament absolut de dades per empresa mitjançant la directiva FORCE ROW LEVEL SECURITY sota PostgreSQL. Tota consulta a la base de coneixement o als logs de transcripció inyectarà de forma mandatoria la variable app.current_empresa_id.
    Velocitat de Resposta Operativa d'IA:
        Inferència de consultes de xat i verificació de garanties: temps de resposta inferior a 2.5 segons.
        Processament asíncron en segon pla (Whisper + Celery) de notes de veu d'incidències de 30 segons: inferior a 8 segons.
    Format de dades inalterable (Zero-Mock): Els logs d'auditories i respostes de seguretat s'emmagatzemen a la base de dades local i s'exposen de forma tabular neta sota Next.js, sense dades demo hardcodejades en codi.

--------------------------------------------------------------------------------
Fora d'Abast (Out of Scope)

    No realitza canvis, actualitzacions o tancaments de fulles de treball o comandes a proveïdors de forma automàtica o desatesa; la decisió final és exclusivament humana (HITL).
    No és un modelador tridimensional BIM, ni realitza representacions 3D de rases o canonades a la biblioteca de plànols de l'empresa.
    No gestiona la contabilitat de tiquets ni la presentació del Model 303 directament a la AEAT, encarregant-se de generar els arxius de regularització sota la Spec 007.
    No s'admeten dades de prova ni insercions simulades a cap nivell de codi d'IA, partint d'un entorn de Dia 0 real.

--------------------------------------------------------------------------------
Criteris de Finalització (Definition of Done) i Matriu de Traçabilitat

    Els 22 Requisits Funcionals (RF-01 al RF-22) i els 10 Casos Límit (EDGE-01 al EDGE-10) redactats amb sintaxi formal EARS estricta en català i lliures d'ambigüitats o dades de prova fictícies sota l'estat Dia 0.
    Correspondència del 100% de la spec de plànols amb una suite de proves d'integració automatitzada en verd amb PostgreSQL RLS actiu sota el tenant real d'empresa.
    Alineació total de la política de QR (Constitució v4.0): exclusió absoluta de codis QR per a les eines de camp (les quals es custodien i es traspassen per referència de fàbrica/SN), preservant el QR legal obligatori de facturació Veri*factu per a albarans i factures.
    Priorització asíncrona Celery: implementació d'una arquitectura asíncrona d'alta densitat que prioritza l'operativa de camp per davant de les consultes informatives de la web.

Matriu de Traçabilitat 1:1 de la Definition of Done (DoD)
Codi de la Spec
	
Cas Límit Vinculat
	
Assert / Criteri de Validació DoD (Zero-Mock)
RF-01 / RF-02
	
EDGE-01
	
Cua de Celery prioritària; consultes de camp es processen abans que les peticions del xat d'oficina.
RF-03
	
EDGE-02
	
Timeout d'IA superior a 15s retorna missatge d'error de seguretat sense bloquejar l'accés a l'àudio.
RF-04
	
-
	
Ingesta cronològica d'intervencions, peces i incidències del client de la finca en un any natural.
RF-05 / RF-06
	
EDGE-07
	
Alerta d'avís de garantia de fàbrica per SN; peca danyada a dia 5 d'expiració llança suggeriment de cortesia.
RF-07
	
-
	
Alerta de garantia interna de mà d'obra de l'empresa (<3 mesos) davant reparacions de la mateixa avaria.
RF-08 / RF-09
	
EDGE-03
	
Transcripció Whisper i visió de fotos; baix coeficient llança advertència acústica de vent/tractor.
RF-10
	
-
	
Modificació i validació manual de l'Enginyer de la qualificació del Memoràndum (Extra vs Error).
RF-11 / RF-12
	
EDGE-04 / EDGE-08
	
Reconciliació post-feina; materials sota sync diferida bloquegen la pre-factura. Merma >250% bloca.
RF-13
	
-
	
Proposta de nou pressupost corregit sota Next.js; PUT de facturació automàtica llança excepció.
RF-14 / RF-15
	
EDGE-06
	
Càlcul de stock estimat i injecció de comanda de reposició; comandes concurrents es bloquegen per SQL.
RF-16 / RF-17
	
EDGE-10
	
Aïllament de prompts per vertical; pregunta elèctrica realitzada sota vertical d'aigua és rebutjada.
RF-18
	
-
	
Aïllament multi-inquilí; consultes semàntiques del RAG filtren strictly sota app.current_empresa_id.
RF-19 / RF-20
	
EDGE-05
	
Finestra de xat web actiu; consultes d'Enginyer sobre endpoints comptables retornen HTTP 403 Forbidden.
RF-21 / RF-22
	
EDGE-09
	
Finca nova sense historial respon categòricament "No tinc informació prèvia", sense inventari mock.
"""
		
Ensure the output directory exists
os.makedirs("/workspace/scratch/012-copilot-ia-v2", exist_ok=True) os.makedirs("/workspace/out", exist_ok=True)
Write to scratch
scratch_path = "/workspace/scratch/012-copilot-ia-v2/012-copilot-ia-v2.md" with open(scratch_path, "w", encoding="utf-8") as f: f.write(content)
Write to out
out_path = "/workspace/out/012-copilot-ia-v2.md" with open(out_path, "w", encoding="utf-8") as f: f.write(content)
print("Spec 012 v2 written and published.")