Spec 002 — Mòdul de Gestió de Clients (/gestio/clients)
AVÍS D'ALINEACIÓ CONSTITUCIONAL I INTEGRACIÓ ARQUITECTÒNICA: Aquesta especificació tècnica es regeix pels principis de la Constitució de CampoPro Suite (v4.0) i s'integra de forma directa amb la Torre de Control Geogràfica (Spec 001 i Spec 005), el Mòdul de Magatzem (Spec 004), el Mòdul de Flota (Spec 006), el Mòdul de Notificacions (Spec 009) i el Mòdul Contable (Spec 007).
Es prohibeix taxativament l'ús de dades simulades o de prova (Zero Mock Data), garantint la sobirania de dades mitjançant l'emmagatzematge de documents i historials en el servidor local/sobirà d'Hetzner a Alemanya (UE), rebutjant serveis cloud com AWS S3 per a estricte compliment del RGPD.
De conformitat amb la Constitució, s'estableix que qualsevol codi QR generat o llegit pel sistema pertany de forma exclusiva a l'àmbit de la facturació legal i tributària (Veri*factu) i a la descàrrega d'albarans i factures de clients, quedant formalment exclòs l'ús de codis QR corporatius per a la traçabilitat de les eines de treball en camp (les quals es gestionen unívocament pel seu número de referència, marca, model i número de sèrie de fabricant sota la Spec 004).
--------------------------------------------------------------------------------
Context i Objectiu
El mòdul de Gestió de Clients és el directori mestre de les entitats contractants (particulars, empreses, comunitats de regants o explotacions agrícoles) i el registre central de les seves instal·lacions, finques geolocalitzades i expedient històric d'obres.
Resoldrà la necessitat de governar amb precisió tècnica, fiscal i operativa tant la seu o domicili social del client com les seves múltiples finques rústiques i escomeses (SIGPAC i coordenades GPS), els seus plànols tècnics, el seu canal de comunicació bidireccional (Bot de Telegram o canals tradicionals de correu/SMS), el seu historial de feines realitzades amb evidències fotogràfiques i el seu slot de factures tècniques sanititzades.
A nivell arquitectònic i de seguretat, aquest mòdul implementa:

    Aïllament Multi-Inquilí Estricte (RLS): Forçat a nivell de PostgreSQL mitjançant la variable de sessió d'inquilí (empresa_id).
    Segregació Zero-Trust de Dades Financeres: Bloqueig absolut de dades bancàries (IBAN i mandats SEPA) i mètriques macroeconòmiques al rol Ingeniero, servint les factures de client des de /gestio purificades mitjançant un DTO tècnic sanititzat (FacturaConsultaTecnicaDTO).
    Xifratge de Seguretat en Repòs: Ús de AES-256-GCM per a la persistència de comptes bancaris i xifratge de sobre (Envelope Encryption) per a mandats SEPA a disc.
    Inmutabilitat Mercantil i RGPD: Prohibició de borrat físic (DELETE) de clients amb històric de feines, procediments d'anonimització selectiva de contacte davant d'exigències de supressió (Art. 17 RGPD), i preservació del titular comptable davant traspassos de predis rústics.

--------------------------------------------------------------------------------
Usuaris / Actors i Matriu d'Accés (Zero-Trust)

    Boss (Gerència / Propietario): Accés total. Creació, edició i baixa lògica de clients; consulta de dades bancàries descifrades, formes de pagament i mandats SEPA en PDF; i visualització completa del resum econòmic amb redirecció a facturació legal en /gestio/comptabilitat.
    Secretaria / RRHH: Administració de la fitxa de clients, gestió i custòdia documental de mandats SEPA, generació de correus de benvinguda de Telegram, i consulta de factures de client amb redirecció de cobraments a /gestio/comptabilitat.
    Enginyer / Supervisor Tècnic: Accés de solo lectura al directori de clients i escomeses tècniques. Registra noves finques, coordenades GPS, dades SIGPAC, plànols, anotacions de candats i llances ordres de treball. VETO FINANCER TOTAL sota HTTP 403 Forbidden a nivell d'API sobre l'IBAN sencer, mandats SEPA, preus de cost, marges comercials o el router contable /api/v1/gestio/comptabilitat/*. La consulta de factures es processa mitjançant el DTO tècnic del canal desacoblat d'obra.
    Operari / Cap de Colla (/operari): No té accés web. Des de la seva PWA de camp visualitza exclusivament les coordenades de la finca, persona de contacte in situ i anotacions d'accés (perills, claus o candats) de forma temporal única i exclusivament durant el dia de l'obra planificada o en curs.

Matriu de Permisos per Rol
Entitat / Funció
	
Boss
	
Secretaria / RRHH
	
Enginyer
	
Operari PWA
Directori de Clients (CLI-XXXX)
	
Lectura / Escritura
	
Lectura / Escriptura
	
Solo Lectura
	
Sense accés
Exportació CSV de la Cartera
	
Permès
	
Permès
	
Bloqueig Total (403)
	
Sense accés
Dades Bancàries (IBAN, Mandat SEPA)
	
Lectura / Escritura
	
Lectura / Escriptura
	
Bloqueig Total (403)
	
Sense accés
Finques, SIGPAC i GPS
	
Lectura / Escritura
	
Lectura / Escriptura
	
Lectura / Escriptura
	
Solo Lectura (Asignada)
Anotacions Físiques de Accessos
	
Lectura / Escritura
	
Lectura / Escriptura
	
Lectura / Escriptura
	
Temporal (Dia d'obra)
Historial de Obras i Evidències
	
Lectura / Auditoria
	
Lectura / Auditoria
	
Lectura / Auditoria
	
Escriptura (Fotos)
Factures i Albarans del Client
	
Lectura completa
	
Lectura completa
	
DTO Sanititzat
	
Sense accés
Emissió Factura Veri*factu (QR)
	
Redirecció
	
Redirecció
	
Bloqueig Total (403)
	
Sense accés
--------------------------------------------------------------------------------
Requisits Funcionals (Notació EARS Estricta)
Bloque 1: Directori Principal (/gestio/clients) i Estat "Día 0"

    RF-01 (Ubiquitous): EL SISTEMA renderitzarà a /gestio/clients un llistat tabular paginat del costat del servidor (Server-Side Pagination), sense mapes visuals ni KPIs econòmics en aquesta vista, mostrant per cada client: Nom / Raó Social, NIF sencer, Telèfon, Email, Direcció fiscal física i Persona de contacte.
    RF-02 (Ubiquitous): EL SISTEMA aplicarà cerca reactiva insensible a majúscules i accents en introduir un terme a la caixa de cerca del llistat, filtrant en temps real en Next.js per: Nombre/Raó Social, NIF/CIF o Municipi.
    RF-03 (State-driven): SI la base de dades del tenant compta amb 0 registres de clients (Día 0 real), ENTONCES EL SISTEMA renderitzarà la pantalla tabular completament buida, mostrant exclusivament els botons de acció [Alta client manual] i [Importació de dades CSV] sense dades simulades (Zero Mock Data).

Bloque 2: Alta de Clients, Validació de NIF i Processament de CSV

    RF-04 (Event-driven): QUAN l'usuari prepa l'acció "Alta client manual", EL SISTEMA desplegará el formulari modal requerint: Raó Social, NIF/CIF sencer, Telèfon, Email, Direcció fiscal i Persona de contacte, obtenint de forma automàtica les coordenades GPS de la seu per geocodificació o permetent el seu ajust manual (Lat/Lng).
    RF-05 (Ubiquitous): EL SISTEMA validarà de forma algorítmica la correcció formal i el dígit de control del NIF, NIE o CIF espanyol (mòdul 23 / mòdul 11) o NIF-IVA comunitari via VIES, bloquejant el desat de qualsevol identificador fiscal malformat o erroni.
    RF-06 (Unwanted behavior): SI es detecta un intent de desar un client amb un NIF que ja existeix registrat a l'empresa (inquilí concurrent), ENTONCES EL SISTEMA rebutjarà la petició, blocarà el commit d'escriptura i emetrà l'error "El NIF/CIF ja es troba registrat en el sistema".
    RF-07 (Event-driven): QUAN l'usuari seleccioni "Importació de dades CSV", EL SISTEMA processará el fitxer delimitat per coma o punt i coma (UTF-8 o ISO), important de forma resilient les files vàlides i descartant les incorrectes.
    RF-08 (Event-driven): TRAS processar el fitxer CSV, EL SISTEMA mostrarà una taula de resum detallant les files rebutjades, indicant el número de línia, el valor del camp causant i el motiu de l'excepció de validació fiscal.
    RF-08.1 (Ubiquitous): EL SISTEMA limitarà l'exportació massiva en CSV de la cartera de clients de l'empresa de forma estricta als rols Boss i Secretaria, retornant un error 403 Forbidden a nivell d'API davant peticions de l'Enginyer.

Bloque 3: Fitxa Detallada del Client (/gestio/clients/[id]), Plànols i Seguretat Bancària

    RF-09 (Ubiquitous): EL SISTEMA renderitzarà a /gestio/clients/[id] la fitxa detallada de l'expedient del client estructurada en una capçalera de dades fiscals i de contacte, plànols de finques, dades de cobrament i els 4 slots operatius.
    RF-10 (State-driven): MIENTRAS el rol connectat sigui Boss o Secretaria, EL SISTEMA mostrarà el bloc confidencial de dades de cobrament: IBAN (validat mòdul 97), Forma de cobrament, Descompte comercial (%) i el document PDF del mandat de domiciliació SEPA.
    RF-10.1 (Ubiquitous): EL SISTEMA escripturarà en reposo l'IBAN de forma xifrada AES-256-GCM (iban_encrypted) en base de dades, i custodiará el PDF del mandat SEPA sota xifratge de sobre (Envelope Encryption) a la ruta local soberana /docs/<empresa_id>/clients/mandats/, bloca l'accés físic a rols no autoritzats.
    RF-11 (Ubiquitous): EL SISTEMA purgarà i exclourà per complet el bloc confidencial econòmic i el PDF de mandat SEPA del payload del JSON retornat quan la petició provingui de l'Enginyer, responent de forma transparent a la seva interfície de solo lectura sense dades financeres.
    RF-12 (State-driven): QUAN l'expedient del client contingui plànols de canonades o instal·lacions hidràuliques, EL SISTEMA renderitzarà la targeta de plànols amb un enllaç interactiu de redirecció a l'eina d'edició vectorial a /gestio/planols?clientId=<id>.
    RF-13 (Ubiquitous): EL SISTEMA requerirà que cada finca o escomesa creada per al client contingui de forma mandatoria: Alias de la finca, Coordenades GPS decimals (Lat/Lng), Persona de contacte in situ, Anotacions d'accés (perills, claus, candats) i les dades d'identificació catastral oficials SIGPAC (Municipi, Polígon, Parcela), llançant una advertència visual davant discordances de georreferenciació parcel·laria.
    RF-13.1 (State-driven) — Seguretat Física d'Accessos de Camp en PWA: MIENTRAS un operari de camp consulti les dades d'accés o codis de candats des de la seva PWA mòbil, el backend de l'API enmascarará els codis físics, servint-los en text clar únicament i de forma efímera si l'operari té una fulla de tasca assigned agendada per a la data corrent (avui) o en curs de realització.
    RF-14 (Event-driven) — Traspàs de Predis i Inmutabilitat de Factures: SI es produeix el traspàs de propietat d'una finca a un nou client, EL SISTEMA reassignarà la finca heretant l'historial de feines realitzades, però marcarà de forma inalterable i permanent que els albarans i factures anteriors van ser emesos sota la titularitat de l'antic propietari, mostrant la insígnia "Actuació sota titularitat anterior".

Bloque 4: Trazabilitat d'Obres (Slot 1), Factures Tècniques (Slot 2) i Canal de Clients

    RF-15 (Ubiquitous): EL SISTEMA llistará al Slot 1 de la fitxa l'historial de feines i ordres de treball finalitzades pel client de forma cronològica descendent sota directiva de RLS de base de dades.
    RF-16 (Event-driven): QUAN l'usuari prepa la visualització d'una obra del Slot 1, EL SISTEMA desplegará el modal tècnic de l'obra mostrant de forma transparent: fulla de treball, galeria de 3 fotos obligatòries (inicial, procés, final), incidències reportades amb fotos i àudios, materials instal·lats amb Número de Sèrie enllaçat a la garantia de proveïdors de forma sanititzada (sense preus de compra).
    RF-17 (Ubiquitous): EL SISTEMA renderitzarà al Slot 2 el llistat de factures emeses, albaranes, i estat de cobrament de clients professionals. MIENTRAS el rol connectat sigui Ingeniero, el backend processará la consulta exclusivament a través de l'endpoint desacoblat /api/v1/gestio/clients/{id}/factures-tecniques serialitzat amb FacturaConsultaTecnicaDTO, purgant comptes contables, marges de benefici, preus de cost de compra o dades d'IBAN per a seguretat Zero-Trust.
    RF-18 (Ubiquitous): EL SISTEMA renderitzarà al Slot 3 el mòdul de comunicació, indicant l'estat del canal Telegram: "Vinculat a Telegram [Chat_id]" o "Canal Telegram no activat", permetent d'enviar el correu de benvinguda de Telegram amb un enllaç profund de seguretat unívoc amb token d'un sol ús expirable a les 48 hores.
    RF-19 (State-driven): MIENTRAS el canal Telegram estigui actiu i es rebi un arxiu mitjançant el webhook del Bot, EL SISTEMA en demanarà la validació del tipus MIME, descartant de forma silenciosa i eliminant qualsevol executable (.exe) o script que no contingui la tipologia de fitxer autoritzada (imatges o PDF-A).
    RF-20 (Ubiquitous): EL SISTEMA renderitzarà al Slot 4 el mapa d'activitats del client, projectant un marcador en la seu fiscal i marcadors de rases o intervencions realitzades sota el tenant autoritzat.

Bloque 5: Inmutabilitat del Directori, Baixes Lògiques i RGPD

    RF-21 (Unwanted behavior): SI un client compta amb històric contable, albaranes de lliurament o ordres de treball realitzades en el passat, ENTONCES EL SISTEMA bloquejarà de forma absoluta qualsevol petició d'esborrat físic (DELETE) de la base de dades (excepció RESTRICT), exigint la seva Baixa Lògica (actiu = false) i arxivant les factures originals inalterables sota Veri*factu.
    RF-21.1 (State-driven): MIENTRAS un client estigui donat de baixa lògica (actiu = false), EL SISTEMA l'ocultarà de la vista general, blocarà els desplegables d'assignació d'ordres de treball i impedirà qualsevol nova pressupostació fins que un rol autoritzat l'activi de nou de forma humana.
    RF-22 (Event-driven) — Dret de Supressió RGPD i Bloqueig Legal: SI un client persona física (autònom) exigeix el seu dret de supressió de dades personals (Art. 17 RGPD), ENTONCES EL SISTEMA anonimizará de forma destructiva els camps de contacte (telèfons, correus, tokens de xat de Telegram), però mantindrà de forma inalterable i inmutable el seu NIF, Raó Social i historial de facturació Veri*factu de la AEAT durant el període de prescripció de 5 anys sota l'estat BLOQUEJAT_RGPD.

--------------------------------------------------------------------------------
Clàusules de Casos Límit i Resiliència (EDGE-01 a EDGE-10)
Codi
	
Tipus EARS
	
Mòdul
	
Vector de Fallada / Escenari Límit
	
Comportament Requerit del Sistema
EDGE-01
	
Unwanted
	
Importació
	
El fitxer CSV de clients conté codificacions de text mixtes o tildes incompatibles sota format ISO-8859-1.
	
El backend normalitza de forma automàtica la codificació a UTF-8 sense BOM, important les files i evitant l'avortament del lot complet de clients.
EDGE-02
	
Unwanted
	
Importació
	
El fitxer CSV conté un mateix NIF duplicat repetit en múltiples files.
	
El sistema desa la primera línia vàlida de l'expedient i col·loca els següents intents de NIF duplicat a l'informe de files rebutjades per a resolució.
EDGE-03
	
Unwanted
	
Fiscal
	
S'intenta desar un client manual o per CSV amb un NIF, CIF o NIE amb dígits de control matemàticament incorrectes.
	
El sistema bloca la persistència en base de dades, destaca el camp CIF en vermell i emet l'avís "Identificador fiscal matemàticament invàlid".
EDGE-04
	
Unwanted
	
Bancari
	
El compte IBAN introduït presenta un error de validació formal del dígit de control de seguretat (mòdul 97).
	
El sistema bloca el desat de les dades de cobrament de clients i impedeix l'activació de la modalitat de remesa SEPA fins a la seva esmena.
EDGE-05
	
Event-driven
	
Geocodificació
	
S'intenta donar d'alta un client però l'API externa de geocodificació cartogràfica d'OpenStreetMap presenta caiguda de servei.
	
El sistema permet desar la fitxa, assigna Lat/Lng a NULL, marca l'estat PENDENT_GEOCODIFICACIO i habilita la selecció manual de la ortofoto al supervisor.
EDGE-06
	
Unwanted
	
Seguretat
	
Un usuari amb rol Enginyer intenta forçar o sol·licitar de forma fraudulenta el payload amb IBAN o SEPA d'un client.
	
El backend de l'API de CampoPro intercepta la crida sota seguretat de rol, bloca el PUT/GET, purga les variables financeres i retorna error 403 Forbidden.
EDGE-07
	
Event-driven
	
Fincas
	
Es tramita el traspàs d'una finca de clients, però aquesta es troba actualment assignada a una ordre de treball activa en camp (EN_EXECUCIO).
	
El sistema bloca la mutació de propietat de la finca fins que el cap de colla tanqui formalment la tasca tècnica o el supervisor la cancel·li al mapa de la Spec 001.
EDGE-08
	
Unwanted
	
Catastro
	
Les coordenades GPS marcades en registrar la finca es troben completament fora dels límits de la parcel·la SIGPAC indicada.
	
El visor cartogràfic del mapa llança una advertència visual de discrepància catastral per preveure errors dels operaris, però permet desar sota confirmació.
EDGE-09
	
Event-driven
	
Notificacions
	
S'intenta remetre un avís automàtic de camp per Telegram però el client ha revocat el Bot o blocat el xat.
	
El backend de notificacions registra l'error del Bot, commuta de forma atòmica el canal a DESVINCULAT a la base de dades i commuta automàticament els avisos a Email/SMS.
EDGE-10
	
Unwanted
	
Seguretat
	
Un usuari maliciós intenta subscriure o enviar un fitxer camuflat amb doble extensió (.pdf.exe) a través del Bot de Telegram de l'empresa.
	
El webhook d'aiogram intercepta l'arxiu, valida estrictament els bytes màgics i la capçalera (magic numbers), rebutja de forma silenciosa el document i el descarta per seguretat.
--------------------------------------------------------------------------------
Requisits No Funcionals (RNF)

    Almacenamiento Local Seguro Multi-Tenant (Soberano): Tots els documents (Mandats SEPA, PDFs de factures, plànols, evidències) s'emmagatzemen exclusivament en els discs locals de l'empresa i servidor sobirà Hetzner a Alemanya sota la ruta /docs/<empresa_id>/clients/ amb xifratge en repòs AES-256-GCM (cero dependència d'AWS S3).
    Seguridad Multi-Tenant (RLS): Cada consulta, actualització o moviment aplicat aplica Row Level Security (RLS) mandatori mitjançant app.current_empresa_id amb la directiva FORCE ROW LEVEL SECURITY en PostgreSQL.
    Protección Zero-Trust: L'IBAN sencer i la descàrrega de mandats SEPA xifrats es reserven de forma exclusiva a Boss i Secretaria, bloca amb HTTP 403 Forbidden a l'Enginyer.
    Tolerancia Cero a Datos Ficticios (Zero-Mock): Si no hi ha clients, l'arrencada tabular de la UI es renderitzarà de forma 100% neta i buida de mocks.

--------------------------------------------------------------------------------
Criteris de Finalització (Definition of Done) i Matriu de Traçabilitat

    Els 22 Requisits Funcionals (RF-01 al RF-22) i els 10 Casos Límit (EDGE-01 al EDGE-10) redactats amb sintaxi formal EARS estricta en català i lliures de dades mock o simulades.
    Correspondència del 100% de la spec de clients amb una suite de proves d'integració automatitzada en verd amb PostgreSQL RLS actiu sota el tenant real.
    Alineació total de la política de QR: l'escut de visualització de codis QR s'exclou per a eines (Spec 004) i es consagra de forma obligatòria per a factures i albarans legals Veri*factu sota la AEAT.

Matriu de Traçabilitat 1:1 de la Definition of Done (DoD)
Codi de la Spec
	
Cas Límit Vinculat
	
Assert / Criteri de Validació DoD (Zero-Mock)
RF-01 / RF-02
	
EDGE-01
	
LIMIT/OFFSET server-side actiu. Coincidencia reactiva de cerca a Next.js insensible a accents.
RF-03
	
-
	
BD buida de clients mostra UI buida sense hardcoding de mocks d'origen.
RF-04 / RF-05
	
EDGE-03 / EDGE-05
	
Geocodificació de seu; fallback de Lat/Lng a NULL en fallida d'API cartogràfica.
RF-05.6
	
EDGE-03
	
Validació de dígit de control de NIF/CIF/NIE espanyol, blocant el desat si és incorrecte.
RF-06
	
EDGE-02
	
Unicitat de NIF per empresa; intents de duplicats CSV es dipositen a la taula d'errors.
RF-07 / RF-08
	
EDGE-01
	
Ingesta de CSV resilient a codificació mixta i caràcters especials.
RF-08.1
	
EDGE-06
	
Exportació massiva CSV de clients retorna HTTP 403 Forbidden al rol Enginyer.
RF-09 / RF-10
	
EDGE-04
	
Validació de checksum de compte IBAN (mòdul 97); bloca SEPA davant errors.
RF-10.1
	
-
	
Xifratge simètric AES-256 de IBAN a base de dades i Envelope Encryption de mandats SEPA.
RF-11
	
EDGE-06
	
Rol Enginyer realitza consulta i el payload JSON omiteix totalment les variables d'IBAN i SEPA.
RF-12 / RF-13
	
EDGE-08
	
Enllaç a /gestio/planols i SIGPAC actiu. Alerta de perill davant discordança cartogràfica.
RF-13.1
	
EDGE-09
	
PWA enmascara codis de candats d'obres, mostrant-los només efímerament el dia d'obra assigned.
RF-14
	
EDGE-07
	
Traspàs de finca blocat si hi ha tasques tècniques EN_EXECUCIO a camp.
RF-15 / RF-16
	
-
	
Modal d'obra resol i enllaça la garantia de proveïdor de forma sanititzada (sense preus de cost).
RF-17
	
EDGE-06
	
Slot 2 de factures de clients utilitza FacturaConsultaTecnicaDTO per purgar variables a l'Enginyer.
RF-18 / RF-19
	
EDGE-09 / EDGE-10
	
Token profund de Telegram de un sol ús expirable a les 48h. Webhook bloca executables .pdf.exe.
RF-20 / RF-21
	
EDGE-06
	
Mapa del Slot 4 projecta escomeses sota tenant real. DELETE directe sobre històric llança RESTRICT.
RF-21.1 / RF-22
	
-
	
Anonimització de camps de contacte per RGPD mantenint NIF i historial de facturació Veri*factu AEAT.