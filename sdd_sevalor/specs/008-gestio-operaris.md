Spec 008 — Mòdul de Gestió d'Operaris i Rendiment de Camp (/gestio/operaris)
AVÍS D'ALINEACIÓ CONSTITUCIONAL I INTEGRACIÓ ARQUITECTÒNICA: Aquesta especificació tècnica es rigeix de forma innegociable pels principis de la Constitució de CampoPro Suite (v3.1) i s'integra de forma transversal amb la Torre de Control Geogràfica en temps real (Spec 001 i Spec 005), el Mòdul de Magatzem (Spec 004), el Mòdul de Flota (Spec 006) i el Mòdul Contable (Spec 007).
Es prohibeix taxativament l'ús de dades simulades o de prova (Zero Mock Data), partint d'un estat de "Dia 0" real i garantint de forma absoluta la sobirania de dades mitjançant l'emmagatzematge local/sobirà dels expedients de personal en el servidor Hetzner de Falkenstein (Alemanya - UE), rebutjant completament qualsevol servei de núvol públic extern (com AWS S3) d'acord amb el compliment estricte de la LOPDGDD i el RGPD.
--------------------------------------------------------------------------------
Context i Objectiu
El mòdul de Gestió d'Operaris i Rendiment de Camp (/gestio/operaris) és la Torre de Control de Recursos Humans Tècnics, Organització de Colles i Auditoria Laboral de CampoPro Suite. Centralitza la supervisió integral de la plantilla tècnica que opera sobre el terreny (5 a 50 operaris), connectant l'activitat realitzada a camp (fitxatges d'inici/fi, registre d'eines, fotos d'ordres de treball, consums i incidències) amb la direcció tècnica, recursos humans i administració de l'empresa.
Aquest mòdul no pretén ser un portal de nòmines o gestoria laboral externa (tasques que es mantenen en l'esfera comptable i sota el staging aïllat de la Spec 007), sinó l'eina de coordinació operativa i compliment legal en temps real que:

    Centralitza la Fitxa 360° de l'Operari estructurada en 8 dimensions tècniques: Dades Personals i Contacte, Control Horari Oficial (RDL 8/2019), Composició de Colles de Camp, Historial de Tasques Executades, Valoracions de Clients, Custòdia de Vehicles i Quilometratge, Eines Assignades (referenciades per número de sèrie, marca i model, i utilitzant el número de referència de l'eina per a la seva ràpida gestió en camp) i Historial d'Incidències de Camp.
    Garanteix el Compliment Estricte del Registre de Jornada Laboral (Reial Decret-Llei 8/2019): audita les hores treballades mitjançant la ingesta asíncrona dels fitxatges registrats a la PWA mòbil, aplica el tancament automàtic a les 8 hores en cas d'oblit de l'operari segons la modalitat de jornada de l'empresa (sencera o partida, parametritzada a /gestio/configuracio), i reserva la regularització d'anomalies i el còmput d'hores extraordinàries exclusivament a Secretaria / RRHH i Boss, aplicant un registre d'auditoria immutable.
    Permet a l'Enginyer Tècnic articular la composició operativa de colles per tasca: des de la figura del Cap de Colla pengen un o més operaris per a l'execució d'una ordre de treball concreta, bloquejant preventivament l'assignació d'aquells treballadors o caps que figurin en estat de VACANCES o BAIXA.
    Governa la custòdia de recursos corporatius (vehicles i eines) sota competència exclusiva de Secretaria/Boss: de conformitat amb la Constitució i la Spec 004, es recolza en el registre de la PWA mitjançant el número de referència de l'eina i de quilometratge per OCR, i s'assegura que qualsevol traspàs d'eina entre treballadors quedi registrat a Magatzem, inhabilitant automàticament als selectors aquells equips marcats com a EN_REPARACIO o PERDUDA.
    Canalitza la resolució d'incidències immediates de camp a càrrec de l'Enginyer: atenció a bloquejos d'accés, avaries de maquinària, petició de grua, sol·licitud de materials no previstos i reassignació dinàmica d'operaris mitjançant la creació o adaptació de la fulla de tasca, garantint una traçabilitat triple (historial d'incidències, fulla de tasca i historial de l'operari).
    Administra la seguretat de credencials i el cicle de vida del treballador: alta de treballadors, generació i tramesa de PIN d'accés a la PWA mitjançant SMS, bloqueig i desbloqueig administratiu després de 4 intents fallits, visibilitat interna del cost/hora a la web per a pressupostació d'obres amb edició restringida a RRHH/Boss, i procediment d'inactivació laboral amb traspàs de custòdia d'equipament al Cap de Colla i revocació criptogràfica immediata de sessions.
    Almacenamiento Seguro y Soberano: Tots els fitxers físics (fotos de permisos de conduir, acreditacions de PRL, o dades de personal) es guarden en local sota /docs/<empresa_id>/operaris/ i /data/<empresa_id>/operaris/ amb xifrat AES-256-GCM, inhabilitant l'accés directe a qualsevol agent no autoritzat i rebutjant serveis cloud com AWS S3.

--------------------------------------------------------------------------------
Usuaris / Actors i Matriu d'Accés (Zero-Trust)
El sistema garanteix l'aïllament multi-inquilí mitjançant Row Level Security (RLS) mandatori a nivell de base de dades (empresa_id) i una segregació estricta de responsabilitats (Separation of Duties):

    Boss (Gerència / Propietario): Accés complet i irrestricto a totes les funcionalitats de /gestio/operaris. Pot crear, editar, suspendre o desactivar operaris; visualitzar i editar el cost hora de la plantilla; modificar i auditar els registres del control horari; generar o restablir el PIN d'accés PWA; transferir eines i vehicles; i consultar els registres històrics d'operaris donats de baixa.
    Secretaria / RRHH: Responsable principal de l'administració de personal. Realitza l'alta i baixa d'operaris; edita dades personals, contacte i permisos de conduir; genera i envia el PIN d'accés per SMS; desbloqueja comptes suspesos per intents fallits; audita i rectifica fitxatges de jornada sota RDL 8/2019; gestiona el còmput d'hores extraordinàries; assigna vehicles habituals i eines de treball; i edita el cost hora laboral.
    Enginyer / Supervisor Tècnic: Responsable de la planificació i execució tècnica a camp. Pot visualitzar la llista d'operaris actius, les seves especialitats, el vehicle habitual, les eines operatives assignades i el cost hora de referència (necessari per al càlcul de pressupostos i costos de mà d'obra de projecte). Configura les colles operatives per tasca (assignant operaris sota un Cap de Colla). Resol incidències tècniques immediates a camp (reassignació d'operaris, adaptació de fulles de tasca, avís de grua o part de material perdut). VETO TOTAL I ESTRICTE a nivell de backend (HTTP 403 Forbidden) sobre l'accés o modificació del Control Horari (shifts), el restabliment de PIN/credencials, dades de nòmines i contractes (Spec 007), i l'edició del cost hora o dades salarials.
    Operari de Camp / Capataz (/operari): No té accés a la interfície web de gestió (/gestio/operaris). Opera exclusivament a través de la PWA mòbil de camp, des d'on registra la seva jornada, cronòmetres de tasca, fotos obligatòries, odòmetre de vehicles i notes d'incidència.
    Client Final (Canal Telegram / Web Externa): Receptor dels serveis executats. No accedeix a aquest mòdul.

Matriu de Permisos per Rol
Àmbit Funcional
	
Boss
	
Secretaria / RRHH
	
Enginyer Tècnic
	
Operari PWA
Llistat d'operaris i Fitxa 360°
	
Lectura / Escriptura
	
Lectura / Escriptura
	
Lectura
	
Sense accés web
Alta i Baixa d'Operaris (actiu)
	
Total
	
Total
	
Denegat (403)
	
Sense accés web
Control Horari Legal (RDL 8/2019)
	
Lectura / Edició / Auditoria
	
Lectura / Edició / Auditoria
	
Denegat (403)
	
Fitxatge PWA
Còmput d'Hores Extres
	
Lectura / Aprovació
	
Lectura / Càlcul
	
Denegat (403)
	
Sense accés web
Composició de Colles per Tasca
	
Total
	
Total
	
Creació / Assignació
	
Consulta PWA
Assignació de Vehicles i Eines
	
Total
	
Total
	
Denegat (403)
	
Custòdia PWA
Transferència d'Eines (Incidència)
	
Aprovació / Resolució
	
Tramitació
	
Consulta / Part
	
Report PWA
Generació / Reset de PIN (SMS)
	
Total
	
Total
	
Denegat (403)
	
Recepció SMS
Visualització Cost/Hora Treballador
	
Visible
	
Visible
	
Visible (Càlcul Obra)
	
Ocult
Edició Cost/Hora Treballador
	
Edició
	
Edició
	
Denegat (403)
	
Denegat
Resolució Incidències Immediates
	
Supervisió / Resolució
	
Recepció parts
	
Resolució Operativa
	
Report PWA
Consulta Historial Operaris Baixa
	
Total
	
Total
	
Denegat (Ocult)
	
Denegat
--------------------------------------------------------------------------------
Històries d'usuari

    H1: Com a Enginyer o Secretaria, vull visualitzar i buscar en temps real el directori d'operaris actius amb el seu estat de disponibilitat per assignar colles de forma òptima.
    H2: Com a Secretaria, vull realitzar l'alta manual dels operaris introduint les seves dades personals, acreditacions i carnet de conduir per disposar d'un registre legal correcte.
    H3: Com a Secretaria o Boss, vull restablir el PIN d'accés d'un operari a la PWA i que aquest es remeti de forma automàtica per SMS al seu telèfon mòbil per evitar la manipulació manual o verbal de credencials.
    H4: Com a Capataz de camp, vull registrar l'inici i la fi de la meva jornada a la PWA d'una manera offline-first per poder complir amb la llei en zones sense cobertura rústica.
    H5: Com a Secretaria o Boss, vull que el sistema tanqui automàticament les jornades de 8 hores que els operaris hagin oblidat tancar per evitar la generació d'hores extres inexistents, marcant el registre com a incidència per a la seva regularització manual.
    H6: Com a Enginyer, vull consultar el cost/hora teòric dels operaris per calcular de manera exacta el cost estimat de mà d'obra d'un pressupost, però sense tenir accés a les seves nòmines o condicions salarials reals de la gestoria.
    H7: Com a Enginyer, vull organitzar colles operatives sota la direcció d'un Cap de Colla per a una ordre de treball, inhabilitant automàticament de la selecció aquells operaris que estiguin de vacances o de baixa.
    H8: Com a Supervisor, vull assignar o desvincular les eines de treball de la fitxa de l'operari, permetent el seu registre mitjançant el número de referència de l'eina a la PWA en camp de conformitat amb la Constitució.
    H9: Com a Supervisor, vull que el sistema bloquegi l'ús i la planificació d'eines que es trobin marcades en estat "En reparació" o "Perduda" per evitar assignar equips defectuosos a les obres.
    H10: Com a Capataz, vull realitzar la transferència d'una eina a un altre operari a camp mitjançant un part ràpid d'incidència a la PWA per canviar la responsabilitat de la custòdia física a l'instant.
    H11: Com a Capataz, vull que la PWA em permeti registrar l'odòmetre de la furgoneta assignada fent una foto al quadre de comandaments al principi i al final del dia, i que la lectura es validi automàticament mitjançant l'OCR de base.
    H12: Com a Secretaria o Boss, vull que la baixa laboral d'un operari bloquegi de forma instantània les seves credencials, revoqui els tokens JWT de la PWA i transfereixi la custòdia del seu vehicle i eines al Cap de Colla del seu grup de manera asíncrona.
    H13: Com a Supervisor, vull que les tasques executades per l'operari estiguin acompanyades obligatòriament d'una galeria d'evidències de 3 etapes (foto inicial, intermèdia i final) per poder auditar de manera transparent el tancament tècnic.

--------------------------------------------------------------------------------
Requisitos Funcionals (Notación EARS Estricta)
Bloque 1: Fitxa 360° de l'Operari i Llistat de Plantilla

    RF-01 (Ubiquitous): EL SISTEMA renderitzarà a /gestio/operaris el directori complet d'operaris actius de l'empresa autenticada, mostrant per a cadascun: nom, NIF sencer, rol tècnic (Cap de Colla / Oficial), especialitat, telèfon corporatiu, estat operatiu (DISPONIBLE, EN_FEINA, VACANCES, BAIXA), vehicle habitual assignat i indicador de Cap de Colla (👑).
    RF-02 (Ubiquitous): EL SISTEMA calcularà i actualitzarà a la capçalera de /gestio/operaris les mètriques consolidades d'operacions (Total Operaris, Valoració Mitjana de Clients, % de Compliment del Control Horari d'avui, Km Conduïts aquest mes i Total d'Eines Assignades), operant estrictament sobre dades reals i mostrant estats buits ("—" o "0") en absència de registres (Zero Mock Data).
    RF-03 (Event-driven): QUAN el supervisor introdueixi un terme a la caixa de cerca del directori, EL SISTEMA filtrarà en temps real la quadrícula d'operaris de forma insensible a majúscules i accents per: nom del treballador, rol professional o especialitat tècnica en un temps de resposta inferior a 200 ms.
    RF-04 (Event-driven): QUAN l'usuari seleccioni la targeta o fila d'un operari, EL SISTEMA desplegarà la Fitxa 360° de l'empleat articulada en les 8 pestanyes independents: Dades Personals (info), Control Horari (shifts), Colla de Camp (crew), Tasques Realitzades (jobs), Ressenyes (reviews), Vehicles i Km (vehicles), Eines Assignades (tools) i Incidències (incidents).
    RF-05 (Ubiquitous): EL SISTEMA mostrarà a la pestanya info les dades personals i de contacte de l'operari, incloent-hi: NIF sencer, telèfon mòbil, correu electrònic, data d'alta, tipus de carnet de conduir amb categoria i vigència, i certificacions actives de riscos laborals (PRL), bloquejant qualsevol camp salarial o PDF de nòmina, els quals queden restringits a la Spec 007.

Bloque 2: Control Horari Legal (RDL 8/2019) i Gestió d'Anomalies

    RF-06 (Ubiquitous): EL SISTEMA registrarà els fitxatges de jornada laboral dels operaris de manera asíncrona, emmagatzemant a la base de dades central l'hora real de marcatge d'entrada i sortida, les coordenades geogràfiques i l'estat del registre (EN_CURS, COMPLERT, INCIDENCIA), un cop transmesos des de la memòria local de la PWA mòbil en disposar de cobertura.
    RF-07 (State-driven): SI un operari manté la seva jornada oberta de control horari durant més de 8 hores sense marcar la sortida, LLAVORS EL SISTEMA realitzarà el tancament automàtic de la jornada calculant les hores en base a la modalitat empresarial definida a /gestio/configuracio (jornada continuada o jornada partida), canviant l'estat de l'shift a INCIDENCIA i afegint de forma automatitzada l'etiqueta "Tancament automàtic per omissió de sortida" per a revisió administrativa.
    RF-08 (Event-driven): QUAN un usuari amb rol Secretaria, RRHH o Boss accedeixi a la pestanya shifts d'un operari, EL SISTEMA permetrà la revisió detallada de les entrades, sortides, hores netes de treball i geolocalització d'inici/fi, habilitant la rectificació manual de registres erronis o incomplets.
    RF-09 (Unwanted): SI un usuari amb rol Enginyer intenta accedir a la pestanya de Control Horari (shifts) o invocar qualsevol endpoint del registre de jornada, LLAVORS EL SISTEMA denegarà l'accés de forma immediata amb un codi d'error HTTP 403 Forbidden, mantenint la privacitat laboral del treballador.
    RF-10 (Ubiquitous): QUAN es produeixi una rectificació manual d'un registre horari per part de Secretaria/RRHH/Boss, EL SISTEMA enregistrarà una traça immutable d'auditoria amb l'identificador de l'usuari que modifica, la data i hora exacta de l'acció, els valors anteriors, els nous valors i el motiu justificatiu requerit, en compliment de les exigències de la Inspecció de Treball.
    RF-11 (Ubiquitous): EL SISTEMA calcularà i posar a disposició de Secretaria/RRHH el sumatori mensual d'hores efectives treballades per operari enfront del còmput teòric del conveni, totalitzant les hores extraordinàries registrades per a la seva compensació o liquidació en nòmina.

Bloque 3: Composició de Colles i Jerarquia per Tasca

    RF-12 (State-driven): SI un operari té actiu el rol de Cap de Colla (isTeamLeader = true), LLAVORS EL SISTEMA habilitará a la seva Fitxa 360° la pestanya crew ("Equip / Colla de Camp"), mostrant el llistat d'oficials i ajudants vinculats al seu grup de treball.
    RF-13 (Event-driven): QUAN un usuari amb rol Enginyer, Secretaria, RRHH o Boss planifiqui o adapti una ordre de treball, EL SISTEMA permetrà configurar la colla operativa necessària assignant un o més operaris sota la supervisió del Cap de Colla responsable d'aquella tasca.
    RF-14 (Event-driven): QUAN Secretaria, RRHH o Boss afegeixin o desvinculin un operari d'un Cap de Colla a la pestanya crew, EL SISTEMA actualitzarà el camp cap_de_grup_id del treballador a la base de dades i reflectirà la nova composició immediatament.
    RF-15 (State-driven): SI un Cap de Colla o un operari es troba en estat VACANCES o BAIXA, LLAVORS EL SISTEMA mostrará una insígnia visual destacada amb el motiu a la seva fitxa i inhabilitarà la seva selecció als desplegables d'assignació d'ordres de treball, impedint que se li programin noves tasques.

Bloque 4: Assignació i Custòdia de Recursos (Vehicles i Eines)

    RF-16 (Event-driven): QUAN un usuari amb rol Secretaria o Boss gestioni els actius d'un operari a les pestanyes vehicles i tools, EL SISTEMA permetrà assignar o desvincular el vehicle habitual de flota i les eines de treball de l'empresa.
    RF-17 (Unwanted): SI un usuari amb rol Enginyer intenta modificar o reassignar directament el vehicle habitual o les eines assignades a la fitxa de l'operari, LLAVORS EL SISTEMA bloquejarà l'acció amb un error HTTP 403 Forbidden.
    RF-18 (Ubiquitous): EL SISTEMA referenciarà totes les eines de treball de la fitxa de l'operari mitjançant el seu codi intern, número de sèrie de fabricant, marca, model, data d'assignació i estat operatiu (OPERATIVA, EN_REPARACIO, PERDUDA), vinculant obligatòriament a cada eina un número de referència de l'eina per possibilitar el check-in/out des de la PWA mòbil de conformitat amb la Constitució i la Spec 004.
    RF-19 (State-driven): MIENTRAS una eina assignada tingui l'estat EN_REPARACIO o PERDUDA, LLAVORS EL SISTEMA inhabilitarà la seva selecció als formularis de planificació de tasques, mostrant de forma visible l'avís de no disponibilitat per evitar assignacions a obres que en requereixin l'ús.
    RF-20 (Event-driven): QUAN es requereixi la transferència d'una eina d'un operari a un altre a camp, EL SISTEMA permetrà registrar aquesta acció de forma immediata en la PWA dels operaris, generant un registre d'incidència formal que canvia la custòdia d'equipament de forma atòmica al backend o la guarda en IndexedDB si estan sense cobertura de xarxa, sincronitzant amb Magatzem (Spec 004).
    RF-21 (Ubiquitous): EL SISTEMA registrarà i mostrarà a la pestanya vehicles l'historial de quilometratge conduït per l'operari, associant la seva designació com a Conductor de la jornada activa per visualitzar la data, matrícula del vehicle, quilòmetres d'inici i final de jornada, quilòmetres nets de ruta i la fotografia de l'odòmetre validada mitjançant el servei OCR del backend.

Bloque 5: Supervisió i Resolució d'Incidències de Camp

    RF-22 (Ubiquitous): EL SISTEMA recopilarà i mostrarà a la pestanya incidents de la Fitxa 360° totes les incidències reportades per l'operari des del terreny, mostrant el codi d'incidència, data i hora, títol, reproductor de la nota d'àudio nativa enregistrada a camp, fotografies associades, diagnòstic de l'assistent d'IA i partida de pressupost addicional si s'ha generat.
    RF-23 (Event-driven): QUAN l'Enginyer Tècnic rebi una incidència operativa que bloquegi la continuïtat d'una obra (ex. avaria de vehicle, accés impedit, necessitat de materials imprevistos), EL SISTEMA ha de facultar l'Enginyer per executar la resolució immediata: sol·licitar servei de grúa, trametre comunicació interna a Secretaria de materials/eines perdudes, o reassignar personal generant o modificant la fulla de tasca corresponent.
    RF-24 (Ubiquitous): EL SISTEMA ha de garantir la traçabilitat triple obligatòria de qualsevol incidència operativa, vinculant i reflectint automàticament l'esdeveniment i la seva resolució a:
        L'Historial Global d'Incidències de l'empresa.
        La Fulla de Tasca / Ordre de Treball afectada.
        L'Historial d'Incidències de la Fitxa 360° de l'operari implicat.

Bloque 6: Alta de Treballador, Seguretat de Credencials (PIN) y Cost Hora

    RF-25 (Event-driven): QUAN un usuari amb rol Secretaria, RRHH o Boss doni d'alta un nou operari a /gestio/operaris, EL SISTEMA registrarà les dades personals, NIF sencer, telèfon corporatiu, especialitat i rol, procedint a generar un PIN numèric de 4 dígits per a la PWA mòbil i enviant-lo automàticament al telèfon de l'operari mitjançant un missatge SMS securitzat.
    RF-26 (State-driven): SI un operari introdueix un PIN incorrecte 4 vegades consecutives a la seva PWA mòbil, LLAVORS EL SISTEMA registrarà l'estat de bloqueig de seguretat del compte i generarà una alerta a la central, destruint la sessió local i requerint que Secretaria/RRHH/Boss emeti un nou PIN des de /gestio/operaris, tramès exclusivament via SMS.
    RF-27 (Ubiquitous): EL SISTEMA permetrà a qualsevol usuari autenticat a la plataforma web (inclòs el rol Enginyer) visualitzar el cost/hora de referència de cada operari per a càlculs de pressupostació, assegurant un bloqueig absolut a nivell d'API sobre la documentació de nòmines i dades salarials reals de la Spec 007.
    RF-28 (Unwanted): SI un usuari amb rol Enginyer intenta modificar o desar un nou valor de cost/hora sobre la fitxa d'un treballador, LLAVORS EL SISTEMA rebutjarà la petició amb un error HTTP 403 Forbidden, reservant la capacitat d'edició exclusivament a Secretaria, RRHH i Boss.

Bloque 7: Inactivació / Baixa d'Operari i Reversió de Custòdia

    RF-29 (Event-driven): QUAN Secretaria, RRHH o Boss tramitin la baixa o desactivació d'un operari (actiu = false), EL SISTEMA transferirà automàticament la responsabilitat legal de custòdia del vehicle i les eines assignades al Cap de Colla del seu grup (o al nou Cap de Colla designat), el qual haurà de formalitzar el trasllat físic i devolució del material a la base de l'empresa.
    RF-30 (Event-driven): QUAN es confirmi la baixa de l'operari, EL SISTEMA revocarà de forma immediata totes les claus criptogràfiques, el PIN d'accés a la PWA i les sessions JWT actives registrades a la llista negra de Redis, impedint qualsevol accés o sincronització posterior des del seu dispositiu mòbil.
    RF-31 (State-driven): SI un operari es troba en estat inactiu o de baixa, LLAVORS EL SISTEMA d'ocultar el seu perfil dels desplegables operatius de planificació de feines i de composició de colles, preservant el seu historial complet a la base de dades per a fins d'auditoria i traçabilitat legal, accessible exclusivament per a consultes de Secretaria, RRHH i Boss.

Bloque 8: Auditoria de Feines Executades i Valoracions de Clients

    RF-32 (Ubiquitous): EL SISTEMA mostrarà a la pestanya jobs l'historial complet d'ordres de treball finalitzades per l'operari, incloent-hi la data d'execució, les hores reals computades, dades del client i l'enllaç de la galeria amb el protocol de 3 fotografies obligatòries d'obra (inicial, procés i final) d'acord amb la Constitució.
    RF-33 (Event-driven): QUAN l'usuari premi el botó "Veure Fitxa" sobre qualsevol tasca de l'historial de treballs, EL SISTEMA desplegará el modal amb el part tècnic de l'obra, coordenades GPS de la finca i enllaços a la fitxa del client o documentació de conformitat amb el RLS multi-tenant de base de dades.
    RF-34 (Ubiquitous): EL SISTEMA mostrarà a la pestanya reviews les puntuacions, estrelles i comentaris emesos pels clients respecte a l'operari, mostrant un estat buit explícit ("Sense ressenyes escrites registrades actualment") en absència de registres (Zero Mock Data).

--------------------------------------------------------------------------------
Taula de Casos Límit i Gestió d'Errors
Codi
	
Tipus EARS
	
Mòdul
	
Vector de Falla / Escenari d'Estrès
	
Comportament Requerit del Sistema
EDGE-01
	
Unwanted
	
Control Horari
	
Solapament de shifts per manca de sincronització offline de l'entrada.
	
El backend rep la marca temporal local del fitxatge offline i consolida la jornada. Si es rep una nova entrada abans de rebre la sortida anterior, LLAVORS el backend tanca de forma retrospectiva el shift anterior utilitzant la dada de l'auto-tancament nocturn (RF-07) de manera idempotent.
EDGE-02
	
Unwanted
	
PWA / GPS
	
El GPS del dispositiu mòbil reporta una precisió accuracy de localització superior a 20 metres.
	
Si després de 3 intents separats per 10 segons la precisió segueix essent feble, LLAVORS la PWA obre el mode de "Fitxatge Assistit per Foto Pericial", que exigeix capturar una foto del Punto Cero de l'obra i llança l' shift amb marca PENDENT_AUDITORIA.
EDGE-03
	
State-driven
	
Control Horari
	
L'auto-tancament de l' shift (8 hores) s'executa a les 18:00 de forma administrativa, però l'obra roman en "Verde" (activa).
	
EL SISTEMA atura l'acumulador de l' shift a les 18:00 (rollback de pernocta de la Spec 001/005), guarda el shift amb estat INCIDENCIA en l'expedient de l'operari, i manté inalterada la fulla d'obra per a decisió humana del supervisor al Dia +1.
EDGE-04
	
Unwanted
	
Seguretat
	
El PIN d'accés es bloqueja per 4 intents consecutius mentre l'operari es troba offline sense GSM.
	
La PWA de camp es bloqueja localment, destrueix les sessions JWT actives de memòria de forma interna i reté el buffer de fitxatges i fotos d' IndexedDB xifrat sota AES-GCM local fins que Secretaria restabeleixi el PIN i s'aconsegueixi cobertura.
EDGE-05
	
Unwanted
	
Seguretat Vial
	
El supervisor intenta assignar un vehicle pesat o conjunt que requereix tacògraf digital (Spec 006) com a actiu d'una cuadrilla, i el carnet de l'operari Conductor té categories caducades o incompletes.
	
El backend valida la llicència del conductor a la Fitxa 360 i bloqueja de manera immedita l'assignació amb un error de validació 400 Bad Request a la Torre de Control, impedint la sortida a carretera.
EDGE-06
	
Event-driven
	
Eines
	
Dos operaris executen una transferència ràpida d'eines mitjançant el número de referència de l'eina en zona de sombra offline.
	
Ambdós dispositius registren el traspàs en local (IndexedDB). En recuperar xarxa, si existeix discrepància de quantitats o serials, LLAVORS el backend suspèn la transferència directa i genera un estat de CONFLICTO_TRASPÀS de Spec 004 per a resolució manual de Secretaria.
EDGE-07
	
State-driven
	
Custòdia
	
Secretaria intenta tramitar la baixa o desactivació d'un operari que manté sota la seva custòdia un furgó o eines crítiques d'alt valor.
	
EL SISTEMA bloqueja la mutació del camp actiu a false, llança un error "Actius pendents de devolució" i exigeix realitzar el reingrés físic de les eines i el vehicle al Magatzem (Spec 004) de forma prèvia.
EDGE-08
	
Unwanted
	
Geovalla
	
L'operari intenta marcar "Start" d'obra fora del perímetre geogràfic de geovalla de 50 m.
	
La PWA inhabilita la marxa ordinària de l'ordre i obre l'opció "Sol·licitud d'Inici de Tasca per Desviació", forçant la pujada d'una foto de l'entorn com a evidència del motiu del desviament.
EDGE-09
	
Unwanted
	
Concurrència
	
Dos usuaris de RRHH intenten modificar el mateix shift de jornada al mateix mil·lisegon des de la web de gestió.
	
EL SISTEMA aplica control de concorrència optimista mitjançant version_id. El primer commit consolida els canvis; el segon commit es rebutja amb error HTTP 409 Conflict instant a refrescar la pantalla.
EDGE-10
	
Event-driven
	
Flota
	
El servei de reconeixement OCR del backend falla en processar la foto de l'odòmetre per condicions de llum o brillantor.
	
EL SISTEMA permet al capataz registrar els quilòmetres nets manualment a la PWA, però bloqueja l'actualització directa de l'actiu de furgoneta a Flota, marcant el registre com a PENDENT_AUDITORIA per al supervisor del parc mòbil.
--------------------------------------------------------------------------------
Requisits No Funcionals (RNF)

    Soberanía de Datos (Cumplimiento LOPDGDD / RGPD): S'elimina completament l'ús de serveis de núvol públics comercials (com AWS S3). Tota la informació personal, fotografies de permisos, acreditacions de PRL i expedients de personal es guarden exclusivament als discs locals i volums del servidor Hetzner a Alemanya (UE) sota /docs/<empresa_id>/operaris/ amb xifratge en repòs AES-256-GCM.
    Seguridad Multi-Tenant (RLS): Cada crida API, inserció o consulta de base de dades sobre les taules del mòdul d'operaris s'aïlla estrictamente a nivell de PostgreSQL mitjançant la directiva FORCE ROW LEVEL SECURITY i l'ús de la variable de sessió d'inquilí app.current_empresa_id.
    Tolerancia Cero a Datos Ficticios (Zero Mock Data): Si la base de dades té 0 registres d'empleats d'una empresa (Día 0 real), la interfície es carregarà completament buida i mostrarà els botons d'acció reals de forma inalterable, sense inyectar dades falses.
    Rendimiento y Escalabilidad: El servei web de gestió /gestio/operaris respondrà de forma asíncrona en menys de 200 ms, processant les fotografies mitjançant pipelines en segon pla (Celery + Redis) per evitar bloqueigs de l' event loop de FastAPI.
    Diseño Camaleón: La visualització de l'aplicació s'adapta de forma dinàmica a les variables CSS corporatives de l'empresa instal·ladora (--color-primary, --color-secondary), mentre que les insígnies d'estat mantenen codis de color fixos i cartogràfics universals (Verde Disponible, Vermell Incidència/Baixa, Lila Crew).

--------------------------------------------------------------------------------
Fora d'Abast (Out of Scope)

    No realitza el càlcul de nòmines des de zero, deduccions d'IRPF o seguretat social d'empleats (gestió externa importada en format DTO staging sota la Spec 007).
    No realitza la contractació legal ni la gestió jurídica o l'alta al sistema RED de la Seguretat Social de cap empleat.
    No es recolza en dispositius de maquinari dedicat de control d'accessos biomètrics (com lectors d'empremtes o sensors facials corporatius en base).
    No s'admeten dades de prova ni insercions simulades a cap nivell de codi.
    Codis QR per a Eines: Queda formalment exclòs el suport, generació o lectura de codis QR sobre eines de treball (les quals s'identifiquen i es custodien estrictament pel seu número de referència, marca i model de fabricant). Aquesta exclusió tècnica d'eines NO afecta de cap manera els codis QR de caràcter legal i tributari que per llei (normativa Veri*factu / TicketBAI, RD 1007/2023 i Ordre HAC/1177/2024) han d'incorporar-se de forma obligatòria a les factures i albarans de lliurament.

--------------------------------------------------------------------------------
Criterios de Finalización (Definition of Done) i Matriu de Traçabilitat

    Els 34 Requisits Funcionals (RF-01 al RF-34) i els 10 Casos Límit (EDGE-01 al EDGE-10) redactats en sintaxi formal EARS estricta i sense errors, constituint el contracte de desenvolupament del programari.
    Correspondència del 100% de la spec amb una suite de proves d'integració automatitzada en verd, lliure de dades hardcodejades o simulades i amb PostgreSQL RLS actiu.
    Alineació constitucional total (Constitució v3.1): les eines de l'operari es gestionen mitjançant el número de referència de l'eina en la PWA mòbil, enllaçant de forma directa amb l'inventari en camp de la Spec 004 i Spec 001.
    Segregació Zero-Trust de rols: veto total de l'Enginyer tècnic a la pestanya Shifts d'operaris, al restabliment de credencials de personal o a dades de nòmines i cost laboral real, mantenint únicament visible el cost hora teòric de projecte per a pressupostació.
    Doble auditoria de Control Horari: registres asíncrons de jornada, control d'anomalies de tancament automàtic a les 8 hores, i traça immutable d'auditoria per a rectificacions de l'administració d'acord amb la Inspecció de Treball (RDL 8/2019).
    Custòdia i seguretat vial: control estricte del carnet de conduir en l'assignació de furgonetes o camions (Spec 006), i prevenció de trasvases que superin el límit de places físiques o capacitat de càrrega útil del vehicle.
    Baixa de personal amb revocació asíncrona de seguretat: inactivació de treballadors (actiu = false) amb canvi de custòdia de furgó i eines al Cap de Colla del grup, neteja de tokens JWT de Redis, i arxiu històric de nòmines i dades durant 5 anys per a auditories.

Matriu de Traçabilitat 1:1 de la Definition of Done (DoD)
Codi de la Spec
	
Cas Límit Vinculat
	
Assert / Criteri de Validació DoD (Zero-Mock)
RF-01 / RF-02
	
-
	
Renderitzat tabular en base en menys de 200 ms. L'arrencada en Dia 0 mostra contadors a zero sense mocks.
RF-03
	
EDGE-09
	
Búsqueda per coincidencia de text sensible; el control de concurrencia optimista llança 409 davant col·lisions.
RF-04 / RF-05
	
EDGE-07
	
Obertura modal 360 en 8 pestanyes; RLS denega l'accés a dades d'operaris d'altres tenants.
RF-06
	
EDGE-01
	
Entrada asíncrona de shift en IndexedDB; processament robust davant solapaments temporals a camp.
RF-07
	
EDGE-03
	
Tancament automàtic de shift superat el límit; detenció de l'acumulador de l'OT a les 18:00 (rollback).
RF-08 / RF-09
	
EDGE-04
	
Peticions d'Enginyer sobre endpoints shifts retornen HTTP 403 Forbidden a la API.
RF-10 / RF-11
	
-
	
Inserció d'auditoria immutable a la base de dades; totalització d'hores extres mensuals de plantilla.
RF-12 / RF-13
	
EDGE-05
	
Assignació de colles sota Cap de Colla; bloqueig de la transacció si el conductor no té carnet vigent.
RF-14 / RF-15
	
-
	
Actualització de cap_de_grup_id en BD; inhabilitació de personal de baixa o vacances als selectors.
RF-16 / RF-17
	
EDGE-07
	
El canvi d'actius per Enginyer llança HTTP 403; la baixa d'operari bloqueja si manté eines actives.
RF-18 / RF-19
	
EDGE-06
	
Eina amb número de referència associat; la planificació en camp bloqueja l'ús de material danyat o de baix de SN.
RF-20 / RF-21
	
EDGE-10
	
Traspàs formal d'eines; l'odòmetre per OCR processa i valida km o deriva a verificació manual.
RF-22 / RF-23
	
EDGE-08
	
L'inici de tasca lluny de la geovalla de 50 m és bloquejat excepte pujada de foto de desviació.
RF-24
	
-
	
Traçabilitat de la incidència: s'insereix el registre al diari global, a la tasca i a l'operari vinculat.
RF-25 / RF-26
	
EDGE-04
	
Generació de PIN i enviament via SMS; el bloqueig per 4 intents suspèn sessió i IndexedDB es xifra.
RF-27 / RF-28
	
-
	
Visualització de cost/hora autoritzada per a pressupostació; el PUT/PATCH de l'Enginyer llança 403.
RF-29 / RF-30
	
-
	
Protocol d'inactivitat del treballador; revocació immediata de tokens JWT actius en Redis.
RF-31
	
-
	
Ocultació de treballadors inactius als desplegables; preservació històrica de dades per 5 anys.
RF-32 / RF-33
	
-
	
Protocol de 3 fotos obligatòries d'obra; accés a modal de jobs limitat per tenant i context de sessió.
RF-34
	
EDGE-10
	
Ressenyes mostren dades de clients reals; estat buit funcional lliure de mocks.