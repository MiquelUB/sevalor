# Feature Specification: Core IA, OCR, Bot de Telegram & Processament Asíncron

**Feature Branch**: `03-core-ia-ocr-bot`  
**Created**: 2026-09-29  
**Status**: Stable Specification  
**Macro-Feature**: Motor Intel·ligent Pericial, Digitalització Transversal OCR, Canal Bidireccional Telegram per a Clients i Execució Asíncrona de Tasques Pesades  

---

> [!IMPORTANT]
> ### Política Global: Alta Màgica OCR (Zero Data Entry)
> **Tot el sistema implementa de forma obligatòria i transversal la funcionalitat d'Alta Màgica OCR.**
> Qualsevol entitat operativa o de gestió (Vehicles, Treballadors/Operaris, Albarans de material, Factures de compra/venda, Contractes de manteniment, Clients i Proveïdors) ha de poder donar-se d'alta i digitalitzar-se de manera immediata mitjançant l'anàlisi automatitzada de fotografies o arxius PDF, eliminant completament la necessitat de picar o transcriure les dades a mà ("Zero Data Entry").  
> L'assistent extreu les dades estructurades (números de sèrie, matrícules, imports, bases imposables, CIF/NIF, línies d'articles i venciments) i presenta un esborrany precompletat llest per a la validació humana amb un sol clic.

---

## 1. Visió del Producte i Principis Rectors

El macro-mòdul de **Core IA, OCR, Bot de Telegram i Processament Asíncron** constitueix el cor analític, el cervell pericial i el sistema nerviós d'automatització de la suite corporativa. Connecta en temps real els quatre grans actors del negoci: l'operari a peu d'obra, l'enginyer a l'oficina tècnica, la gerència/administració i el client final.

Aquest mòdul es governa per quatre principis fundacionals innegociables:

1. **Principi Human-in-the-Loop (HITL)**:  
   L'assistent d'intel·ligència artificial i els automatismes analitzen, transcriuen, periten, reconcilien consums i generen propostes d'acció. Mai prenen decisions contractuals o financeres de forma autònoma ni emeten factures legals, comandes de compra a proveïdors o tancaments d'incidència sense la revisió i aprovació explícita d'un supervisor humà autoritzat.
2. **Sobirania Absoluta i Privacitat Local de Dades**:  
   Totes les dades d'obra, fotografies d'instal·lacions de clients, notes de veu de camp, xats de clients i documents comptables es processen i s'emmagatzemen exclusivament en la infraestructura sobirana de l'empresa situada a la Unió Europea. Queda estrictament rebutjat l'enviament de qualsevol dada privada a proveïdors de núvol públic externs, assegurant el compliment estricte del RGPD i la Llei d'IA de la UE.
3. **Tolerància Zero a Dades Fictícies (Zero Mock Data)**:  
   L'assistent té prohibit inventar diagnòstics, peces, referències o historials d'actuació. Si una finca, instal·lació o component no disposa d'antecedents previs al sistema, l'assistent declararà amb veracitat: *"No tinc informació registrada sobre aquest element"*, evitant al·lucinacions que puguin comprometre la seguretat o la relació comercial.
4. **Desacoblament i Reactivitat Operativa (Zero Blocking)**:  
   Cap càrrega intensiva (anàlisi pericial de fotografies, transcripció de notes d'àudio, generació de documents PDF de facturació o enviaments massius) pot retenir ni degradar l'experiència en temps real dels usuaris mòbils o d'oficina. Totes les tasques pesades s'executen en segon pla de forma garantida i idempotent.

---

## 2. Actors i Matriu d'Interacció

| Actor | Canal d'Accés | Rol Operatiu respecte a la IA i l'Automatització |
| :--- | :--- | :--- |
| **Operari / Cap de Colla** | Aplicació Mòbil de Camp (PWA) | Captura incidències en 30 segons (foto + nota de veu), puja tiquets de despesa de camp via OCR, tanca ordres de treball amb fotografies i rep assistència pericial immediata. |
| **Enginyer / Supervisor Tècnic** | Panell de Gestió Web (`/gestio`) | Principal interlocutor tècnic. Valida memoràndums d'incidències (extra facturable vs. garantia interna), revisa alertes de garanties de fabricant, audita desviacions post-obra i aprova pressupostos corregits. |
| **Secretaria / Administració** | Panell de Gestió Web (`/gestio`) | Rep propostes de recompra preventiva de material sota mínims, valida tiquets de despesa extrets per OCR i gestiona l'emissió de factures legals contrastades. |
| **Boss / Gerència** | Panell de Gestió Web (`/gestio`) | Supervisa auditories de rendibilitat i caiguda de marge comercial, confirma compres estratègiques i controla la salut dels serveis de processament. |
| **Client Final** | Bot Interactiu de Telegram / Email | Rep avisos d'arribada d'operaris a finca, aprova pressupostos d'extres a 1 clic, adjunta fotos d'avaries, descarrega factures segures i atorga conformitat post-obra sense necessitat d'instal·lar aplicacions dedicades. |

---

## 3. User Scenarios & Testing (Històries d'Usuari Prioritzades)

### User Story 1 – Alta Màgica OCR Transversal "Zero Data Entry" (Prioritat: P1)

**Com a** usuari de gestió (Enginyer, Secretaria o Cap de Magatzem) o operari de camp,  
**vull** carregar una fotografia o document PDF d'un albarà de proveïdor, factura, fitxa tècnica de vehicle o tiquet de despesa,  
**per a** que el sistema reconegui i estructuri automàticament totes les dades clau i ompli el formulari d'alta d'entitat sense haver d'escriure manualment cap camp.

- **Per què aquesta prioritat**: És el pilar fonamental d'estalvi de temps administratiu i fiabilitat del registre de dades transversals de tota la plataforma.
- **Test d'Independència**: Carregant la imatge d'un albarà o fitxa tècnica, el sistema ha de retornar l'esborrany amb referències d'articles, quantitats, preus o matrícules llest per acceptar sense teclejar.

#### Criteris d'Acceptació:
1. **Given** un usuari a la pantalla d'alta de materials, vehicles o proveïdors,  
   **When** puja un document (PDF o imatge) de l'albarà o fitxa tècnica,  
   **Then** el sistema processa l'arxiu i retorna les dades reconegudes (identificació fiscal/matrícula, llistat de partides, preus i unitats) preomplertes a la interfície.
2. **Given** un document parcialment malmès o amb baixa qualitat òptica,  
   **When** l'anàlisi no assoleix una certesa completa d'un camp concret,  
   **Then** el sistema deixa aquest camp en blanc o marcat per a revisió manual sense inventar dades fictícies (Zero Mock Data).

---

### User Story 2 – Peritatge Multimodal d'Incidències de Camp (Veu + Foto) i Memoràndum Tècnic HITL (Prioritat: P1)

**Com a** operari a peu d'obra,  
**vull** prémer un botó d'incidència d'emergència a la meva aplicació mòbil, enregistrar una nota de veu de 15 segons explicant un imprevist i adjuntar una fotografia de l'avaria,  
**per a** que la intel·ligència assistent transcrigui el meu àudio, analitzi la imatge i generi un Memoràndum Tècnic d'Incidència per a l'oficina sense que jo hagi d'escriure text al telèfon.

- **Per què aquesta prioritat**: Respecta la política de camp dels "30 segons", eliminant la burocràcia per a l'operari i oferint un dictamen pericial immediat a l'oficina tècnica.
- **Test d'Independència**: Gravant una nota de veu i foto d'una canonada trencada, l'oficina tècnica rep en segons el memoràndum transcrit amb una proposta de dictamen pericial (Extra Facturable vs. Cost Intern).

#### Criteris d'Acceptació:
1. **Given** una nota d'àudio enregistrada en un entorn d'obra en català o castellà tècnic acompanyada d'una foto,  
   **When** es transmet des de l'aplicació mòbil,  
   **Then** el sistema transcriu l'àudio fonèticament, avalua els patrons visuals de fallada i redacta el memoràndum per a l'enginyer classificant l'esdeveniment com a "Extra Facturable" (imprevist de la finca) o "Cost No Imputable al Client" (error d'execució).
2. **Given** el memoràndum generat a la safata de l'oficina tècnica,  
   **When** l'enginyer revisa el dictamen,  
   **Then** pot modificar lliurement els materials o la qualificació abans d'emetre qualsevol pressupost addicional al client (Human-in-the-Loop estricte).

---

### User Story 3 – Canal Interactiu de Telegram per a Clients Finals (Prioritat: P1)

**Com a** client final d'una instal·lació o manteniment,  
**vull** interactuar amb l'empresa a través d'un bot privat de Telegram sense necessitat d'instal·lar aplicacions corporatives ni recordar contrasenyes,  
**per a** rebre avisos en temps real de l'arribada de l'equip tècnic, aprovar pressupostos d'extres a 1 clic i adjuntar fotos d'avaries de forma segura.

- **Per què aquesta prioritat**: Canal de comunicació directe, asíncron i sense barreres d'adopció que agilitza l'aprovació d'imprevistos a peu d'obra.
- **Test d'Independència**: Enviar una invitació amb enllaç profund al client; aquest s'hi vincula immediatament, rep un pressupost interactiu i en prémer [Acceptar] es registra l'aprovació al sistema instantàniament.

#### Criteris d'Acceptació:
1. **Given** un client que accedeix mitjançant l'enllaç d'invitació unívoc facilitat per l'empresa,  
   **When** obre el bot de Telegram,  
   **Then** queda automàticament vinculat a la seva fitxa corporativa sense demanar credencials addicionals.
2. **Given** un usuari desconegut sense token d'invitació vàlid que intenta conversar amb el bot,  
   **When** envia qualsevol missatge,  
   **Then** el sistema rebutja l'accés de forma opaca i no obre cap fil de conversa al panell de gestió.
3. **Given** un pressupost d'extra enviat amb botonera interactiva ([Acceptar] / [Demanar Canvis]),  
   **When** el client prem [Acceptar],  
   **Then** l'estat passa a "Acceptat", la botonera desapareix per evitar dobles clics i es notifica a l'enginyer i a la quadrilla de camp.

---

### User Story 4 – Memòria Històrica 360° i Auditoria Automàtica de Garanties (Prioritat: P2)

**Com a** enginyer de planificació,  
**vull** que quan seleccioni un client o finca, l'assistent m'informi de totes les intervencions dels darrers 365 dies i auditi si els equips o la instal·lació estan sota garantia vigent,  
**per a** evitar facturar erròniament al client peces que cobreix el fabricant o tasques que cobreix la garantia de servei de la nostra empresa.

- **Per què aquesta prioritat**: Protegeix la reputació de l'empresa, evita reclamacions legals i garanteix el cobrament correcte a proveïdors mitjançant tramitació de garanties (RMA).
- **Test d'Independència**: Seleccionant un equip instal·lat fa 1 any amb garantia de 2 anys, el sistema ha de mostrar una alerta destacada advertint que la peça és coberta i proposant tramitar RMA amb el fabricant.

#### Criteris d'Acceptació:
1. **Given** la planificació d'una tasca sobre un equip amb data de compra inferior al període de garantia de fabricant (2 o 3 anys segons el número de sèrie),  
   **When** l'enginyer afegeix el component a l'ordre de treball,  
   **Then** el sistema mostra una advertència destacada informant del proveïdor original i data límit de garantia, proposant no repercutir el cost de la peça al client.
2. **Given** una actuació sobre una instal·lació intervinguda per l'empresa en els darrers 3 mesos per la mateixa causa,  
   **When** es genera la tasca,  
   **Then** el sistema alerta de la Garantia de Mà d'Obra de l'empresa, permetent assignar la mà d'obra a cost 0 € per al client.

---

### User Story 5 – Reconciliació Post-Obra, Control de Desviacions i Pre-Facturació (Prioritat: P2)

**Com a** enginyer o supervisor tècnic,  
**vull** que en finalitzar una obra es reconciliïn automàticament els materials consumits, les hores efectives dels treballadors, el quilometratge del vehicle i els tiquets de despesa,  
**per a** detectar desviacions de marge comercial i disposar d'un esborrany de pre-factura corregit abans de l'emissió definitiva.

- **Per què aquesta prioritat**: Garantiu que cap material oblidat a la furgoneta o hora extra quedi sense facturar o auditar, evitant pèrdues de benefici operatiu.
- **Test d'Independència**: Al tancament d'una feina amb més hores i material del previst, el sistema mostra la comparativa visual "Previst vs. Real" i genera la proposta de pre-facturació editable.

#### Criteris d'Acceptació:
1. **Given** el tancament de l'ordre de treball a l'aplicació mòbil,  
   **When** es consoliden les dades reals de materials retornats, fitxatges geolocalitzats i despeses,  
   **Then** el sistema presenta a l'enginyer una matriu comparativa de desviacions econòmiques i el nou marge comercial calculat.
2. **Given** una caiguda significativa de rendibilitat o un consum desproporcionat de material sense incidència prèvia registrada,  
   **When** es genera la reconciliació,  
   **Then** el sistema emet una Alerta de Merma Operativa i bloqueja l'emissió directa de la factura fins a la revisió explícita de l'enginyer.

---

### User Story 6 – Alerta Preventiva de Recompra de Stock en Assignació (Prioritat: P2)

**Com a** supervisor o persona d'administració,  
**vull** que quan s'assigni una ordre de treball que consumirà materials crítics de magatzem, l'assistent verifiqui si el saldo caurà sota el mínim de seguretat,  
**per a** generar automàticament un esborrany de comanda de reposició al proveïdor habitual abans que es produeixi una rotura d'estoc.

- **Per què aquesta prioritat**: Evita aturades operatives a camp per falta de materials essencials a la nau central.
- **Test d'Independència**: Assignant una obra que consumeix les darreres existències d'un producte, a la safata de compres apareix immediatament l'esborrany de reposició dirigit al proveïdor habitual.

#### Criteris d'Acceptació:
1. **Given** l'assignació d'una feina a una quadrilla a la planificació d'obra,  
   **When** el consum previst redueix el saldo virtual d'un article per sota del seu llindar mínim de seguretat,  
   **Then** el sistema genera una Alerta Preventiva de Recompra i diposita un esborrany de comanda a la safata d'administració per a la seva aprovació amb 1 clic.

---

### User Story 7 – Assistència Tècnica Conversacional RAG Aïllada per Vertical (Prioritat: P3)

**Com a** enginyer o membre d'administració,  
**vull** formular preguntes en llenguatge natural a la finestra de xat de l'oficina tècnica sobre normatives del sector, procediments corporatius o dades d'equips,  
**per a** rebre respostes precises fonamentades en la documentació de l'empresa sense barretjar sectors ni accedir a dades confidencials restringides al meu rol.

- **Per què aquesta prioritat**: Resol dubtes normatius i de procediment a l'acte, reduint temps de recerca documental.
- **Test d'Independència**: Fent una consulta sobre el reglament aplicable o la pòlissa d'un vehicle, el sistema respon citant la clàusula o protocol oficial corresponent.

#### Criteris d'Acceptació:
1. **Given** una empresa contractada sota una vertical tècnica concreta (ex. regadiu, baixa tensió o fontaneria),  
   **When** un usuari fa una consulta tècnica al xat,  
   **Then** l'assistent respon exclusivament amb la normativa i manuals del sector corresponent, declinant preguntes d'altres àmbits.
2. **Given** un usuari amb rol tècnic que intenta preguntar per salaris de companys, nòmines o marges globals confidencials,  
   **When** envia la petició,  
   **Then** el sistema bloqueja la resposta informant que la informació està vetada pel seu nivell de seguretat.

---

### User Story 8 – Processament Asíncron Desacoblat i Emissió Legal Veri*factu (Prioritat: P3)

**Com a** persona d'administració o gerència,  
**vull** emetre factures oficials que compleixin la normativa legal de facturació inalterable (Veri*factu / RD 1007/2023) sense que la plataforma quedi bloquejada durant la generació de documents pesats,  
**per a** assegurar la validesa tributària amb codis QR oficials, encadenament criptogràfic de registres i sincronització telemàtica transparent.

- **Per què aquesta prioritat**: Compliment legal tributari obligatori i garantia d'alta disponibilitat de la plataforma per a tots els usuaris.
- **Test d'Independència**: Sol·licitant l'emissió massiva de factures de final de mes, la interfície continua completament fluida mentre els documents es generen i encadenen en segon pla.

#### Criteris d'Acceptació:
1. **Given** l'emissió d'una factura definitiva,  
   **When** s'inicia el procés de generació,  
   **Then** el document PDF s'elabora en segon pla incloent el codi QR legal Veri*factu, la signatura d'encadenament amb la factura precedent i la marca corporativa de l'empresa.
2. **Given** una caiguda temporal del servei telemàtic de l'administració tributària,  
   **When** es despatxa el registre de facturació,  
   **Then** el sistema emmagatzema el paquet a la safata de sortida local i reintenta la tramesa de forma automàtica sense afectar l'operativa diària de l'empresa.

---

### User Story 9 – Pressupost Intel·ligent via Copilot (Prioritat: P1)

**Com a** usuari de l'oficina tècnica o enginyer,  
**vull** que quan premi el botó [✨ Pressupost Intel·ligent] al formulari d'OT, el Copilot analitzi l'historial (feines similars, barema de preus, proveïdors),  
**per a** generar un esborrany de pressupost amb partides i preus suggerits que jo pugui revisar i confirmar (HITL).

- **Per què aquesta prioritat**: Maximitza la productivitat a l'hora de pressupostar tasques repetitives o amb patrons coneguts basant-se en l'històric de l'empresa.
- **Test d'Independència**: En prémer el botó de generació en una OT de substitució de caldera, el sistema ha d'omplir les partides de mà d'obra i materials suggerits sense inventar preus, basant-se en l'històric.

#### Criteris d'Acceptació:
1. **Given** una ordre de treball oberta i en estat de pressupostació,  
   **When** l'usuari fa clic a [✨ Pressupost Intel·ligent],  
   **Then** l'assistent avalua l'historial i suggereix una llista de partides amb els preus de barem, quedant en estat d'esborrany per a validació manual.

---

### User Story 10 – Aprenentatge Progressiu del Copilot (Prioritat: P2)

**Com a** gerent de l'empresa (Boss),  
**vull** que el Copilot evolucioni progressivament: Dia 0 (regles bàsiques + RAG normativa), Mes 1-3 (aprèn barema + primeres feines), Mes 3-6 (suggereix partides i durades), i Mes 6+ (prediccions de facturació, estacionalitat, rendibilitat),  
**per a** tenir un assistent que aporti cada vegada més valor cognitiu segons el volum de dades històriques acumulades de forma segura i local.

- **Per què aquesta prioritat**: Escala el retorn d'inversió en IA de manera realista, evitant expectatives inassolibles al llançament i garantint una maduració estable del sistema.
- **Test d'Independència**: Depenent del temps i dades acumulades, l'assistent desbloqueja progressivament noves funcionalitats de suggeriment en la interfície de gestió.

#### Criteris d'Acceptació:
1. **Given** l'evolució temporal de l'ús de la plataforma,  
   **When** s'assoleixen els llindars de dades definits (ex. Mes 1-3 o Mes 6+),  
   **Then** les noves capacitats de predicció i suggeriment s'activen de manera automatitzada i fiable sense requerir configuracions complexes addicionals.

---

### User Story 11 – Informe Setmanal Automàtic (Boss Only) (Prioritat: P2)

**Com a** Boss / Gerència,  
**vull** rebre automàticament cada dilluns a les 8:00 un resum executiu exclusiu per a mi generat pel Copilot,  
**per a** revisar en 5 minuts el Bloc operatiu (feines, incidències, operaris), el Bloc econòmic (facturació, EBITDA, marges, desviacions) i el Bloc d'alertes proactives.

- **Per què aquesta prioritat**: Concentra l'analítica directiva de forma accessible al començament de la setmana sense haver de navegar per informes complexos.
- **Test d'Independència**: El dilluns a les 8:00 només els usuaris amb rol de direcció reben la notificació amb l'informe compilat.

#### Criteris d'Acceptació:
1. **Given** la programació setmanal establerta,  
   **When** és dilluns a les 8:00,  
   **Then** el Copilot genera un informe detallat en 3 blocs (operatiu, econòmic, alertes) i l'envia de forma segura exclusivament als usuaris amb permís directiu.

---

### User Story 12 – Signatura Digital del Client via Telegram (Prioritat: P3)

**Com a** client final,  
**vull** rebre un enllaç al meu Telegram quan l'operari acabi la feina,  
**per a** poder signar digitalment la conformitat de l'actuació des del meu mòbil sense haver d'imprimir paper.

- **Per què aquesta prioritat**: Agilitza el cobrament posterior i el tancament administratiu d'expedients amb garanties de conformitat immediates.
- **Test d'Independència**: L'operari tanca la feina, el client rep l'enllaç i en signar amb el dit o ratolí, la rúbrica queda integrada i encriptada al tancament oficial de l'obra.

#### Criteris d'Acceptació:
1. **Given** un canvi d'estat a "Finalitzat" per part de l'operari a camp,  
   **When** el sistema notifica el tancament al client,  
   **Then** s'envia un missatge via Telegram amb un enllaç interactiu de signatura digital legalitzada.

---

## 4. Casos Límit i Gestió d'Anomalies (Edge Cases)

- **Àudio amb soroll acústic sever a camp**: Si un operari grava una nota de veu a prop d'un tractor o amb vent fort i la claredat de l'àudio és molt baixa, el sistema transcriu els fragments audibles, afegeix l'avís *"⚠️ Àudio amb soroll de fons sever"* i sol·licita a l'enginyer que prioritzi la revisió visual de la fotografia adjunta.
- **Interrupció o indisponibilitat temporal del motor d'anàlisi**: Si el servei d'intel·ligència artificial no respon en el temps límit establert (< 15 segons), l'aplicació no bloqueja l'usuari; mostra el missatge informatiu *"Copilot provisionalment no disponible"* i presenta immediatament la fotografia i àudio originals a l'enginyer per a la seva gestió manual directa.
- **Intrusió al canal de Telegram sense invitació**: Si un compte extern desconegut inicia conversa amb el bot sense haver fet clic a l'enllaç d'invitació oficial de l'empresa, el sistema descarta la interacció de forma opaca i no obre cap registre per evitar spam.
- **Arxius maliciosos o amb doble extensió al xat**: Si un usuari intenta adjuntar un document amb patrons sospitosos (per exemple, `imatge.jpg.exe` o scripts camuflats), el sistema analitza l'estructura real del fitxer, bloqueja la càrrega a l'instant i alerta de fitxer no permès.
- **Enllaç de descàrrega de factura caducat al bot**: Si un client obre l'enllaç segur d'una factura més de 24 hores després d'haver-lo rebut, el sistema denega la descàrrega per motius de seguretat i ofereix l'opció de sol·licitar un nou enllaç renovat per correu electrònic.
- **Tancament d'obra en zona sense cobertura mòbil**: Quan una quadrilla tanca una feina en una parcel·la sense connexió, les dades de tancament i fotografies es retenen al dispositiu. El sistema no permet tramitar la factura de liquidació definitiva fins que es produeixi la sincronització completa un cop recuperada la xarxa, evitant cobrar partides incompletes.
- **Reserva simultània d'un mateix article crític d'estoc**: Si dos enginyers assignen al mateix instant dues obres que competeixen per les darreres unitats d'un material a magatzem, el sistema processa les reserves de forma ordenada: la primera adjudica el material i la segona alerta immediatament d'estoc insuficient per concurrència.
- **Finca nova sense antecedents històrics**: Quan s'obra una ordre de treball per a una parcel·la que mai havia estat atesa per l'empresa, l'assistent indica clarament *"Primer servei registrat en aquesta instal·lació; sense historial previ"*, rebutjant qualsevol generació d'informació simulada.

---

## 5. Requisits Funcionals Globals (EARS Notation)

- **FR-001 (Ubiquitous)**: El sistema implementarà de manera transversal l'Alta Màgica OCR per a la digitalització automatitzada de fotografies i documents PDF (albarans, tiquets, vehicles, operaris i factures) sense entrada manual de dades.
- **FR-002 (Ubiquitous)**: Tota actuació de l'assistent d'IA en matèria de pre-facturació, compres de reposició o dictàmens pericials es regirà pel principi Human-in-the-Loop, requerint la confirmació expressa d'un supervisor humà autoritzat.
- **FR-003 (Ubiquitous)**: Totes les dades multimèdia, documents legals i converses es conservaran exclusivament en l'emmagatzematge sobirà local de l'empresa, sense reenviar informació confidencial a serveis externs de núvol comercial.
- **FR-004 (Event-driven)**: Quan un operari enviï una nota de veu i fotografia des de camp, el sistema processarà asíncronament l'arxiu i redactarà un Memoràndum Tècnic proposant la catalogació d'Extra Facturable o Cost Intern.
- **FR-005 (Event-driven)**: Quan un supervisor consulti una instal·lació o finca, el sistema recopilarà l'històric d'intervencions dels últims 365 dies i auditarà la vigència de garanties oficials de fabricant i garanties internes de mà d'obra.
- **FR-006 (Event-driven)**: Quan es formalitzi el tancament d'una ordre de treball, el sistema conciliarà automàticament els materials consumits, les hores presencials, el quilometratge del vehicle i els tiquets de despesa, calculant la desviació sobre el pressupost aprovat.
- **FR-007 (State-driven)**: Si l'assignació d'una ordre de treball projecta que un article caurà per sota del seu estoc mínim de seguretat, el sistema generarà immediatament una alerta i un esborrany de comanda de compra de reposició.
- **FR-008 (Event-driven)**: Quan un client accedeixi al bot de Telegram mitjançant un enllaç d'invitació vàlid, el sistema l'associarà de forma transparent a la seva fitxa corporativa i li permetrà aprovar pressupostos complementaris a 1 clic.
- **FR-009 (Unwanted-behaviour)**: Si un usuari no convidat intenta interactuar amb el bot de Telegram o un arxiu rebut presenta anomalies d'extensió, el sistema rebutjarà la petició i protegirà la integritat del canal.
- **FR-010 (Ubiquitous)**: El sistema aplicarà directrius de llenguatge i coneixement especialitzat segons la vertical tècnica de l'empresa, bloquejant consultes sobre informació confidencial o aliena al perfil de l'usuari.
- **FR-011 (Event-driven)**: Quan s'emeti una factura definitiva, el sistema generarà el document legal inalterable d'acord amb la normativa Veri*factu, encadenant el registre criptogràfic i incorporant el codi QR tributari.
- **FR-012 (Ubiquitous)**: El sistema proporcionarà una consulta de seguiment en temps real de l'estat de qualsevol procés en segon pla (Pendent, Processant, Completat o Error).
- **FR-013 (Security)**: Barrera de Seguretat Doble Capa del Copilot per blindar dades econòmiques. 
  - Capa 1 (Soft): Classificador IA que detecta si la pregunta és operativa (🟢) o econòmica (🔴). Si 🔴 i rol ≠ Boss → rebuig immediat.
  - Capa 2 (Hard): RLS (Row Level Security) a PostgreSQL amb la policy `economics_boss_only`. Si el rol no és Boss, retorna 0 rows per a taules econòmiques, sent infranquejable.
  - Resposta estàndard en cas de rebuig: "Aquesta informació és restringida a la Direcció de l'empresa."

---

## 6. Entitats Clau de Negoci (Zero Tech Details)

- **Memoràndum Tècnic Pericial**: Registre documental resultant de l'anàlisi d'un imprevist a camp. Inclou transcripció fidel de la veu de l'operari, avaluació visual de l'avaria, proposta de dictamen (Extra vs. Cost Intern), estimació de recursos necessaris i estat de validació de l'enginyer.
- **Auditoria de Reconciliació Post-Obra**: Document de contrast econòmic que consolida les hores efectives, el material extret de magatzem menys el retornat, els quilòmetres de transport i les compres menors, comparant-ho amb el pressupost acceptat i calculant la variació del marge de benefici.
- **Alerta de Garantia i Recompra**: Notificació preventiva que identifica components protegits per garantia de fabricant/empresa per a no cobrar-los indegudament, o bé adverteix de la necessitat imminent de fer una comanda de reposició de material.
- **Canal de Client (Telegram)**: Connexió corporativa personalitzada amb la marca de l'empresa que permet el bescanvi d'estats d'obra, l'acceptació contractual d'imprevistos amb signatura digital i el suport continuat al client final.
- **Registre de Facturació Inalterable (Veri*factu)**: Documentació tributària oficial que conté el segell de temps, el codi QR de validació fiscal i la traça d'encadenament ininterrompuda que en garanteix la integritat davant de revisions administratives.

---

## 7. Criteris d'Èxit Mesurables (Success Criteria)

- **SC-001 (Zero Data Entry)**: El 90% de les dades d'alta d'albarans de materials i fitxes de vehicles es completen automàticament a través de l'anàlisi OCR sense necessitat d'edició manual per part de l'usuari.
- **SC-002 (Velocitat a Camp)**: Un operari a peu d'obra completa el registre complet d'una incidència amb foto i nota de veu en menys de 30 segons.
- **SC-003 (Temps de Resposta de la IA)**: El memoràndum d'incidència d'una nota de veu de 30 segons està redactat i disponible per a l'enginyer en menys de 8 segons des del seu enviament.
- **SC-004 (Interacció a 1 Clic del Client)**: El client final pot aprovar un pressupost d'extra des del seu telèfon mòbil en menys de 5 segons des de la recepció del missatge a Telegram.
- **SC-005 (Protecció Financera de Garanties)**: El sistema detecta el 100% dels components instal·lats que es troben en període de garantia oficial, evitant el cobrament indegut a clients i tramitant la reclamació al proveïdor.
- **SC-006 (Zero Bloqueig d'Interfície)**: El 100% de les operacions lentes (PDFs, OCR i enviaments massius) s'executen de forma asíncrona sense congelar la navegació de cap usuari.

---

## 8. Supòsits i Condicions de Context

- Es parteix d'un escenari real de "Dia 0" sense dades simulades; tot l'històric i arxius s'alimenten de l'activitat autèntica de l'empresa.
- Les eines de camp es gestionen i s'identifiquen exclusivament pel seu número de sèrie, referència de fàbrica, marca i model (d'acord amb la política constitucional de no fer servir codis QR físics en eines manuals).
- L'únic codi QR vàlid i admès és el codi QR de caràcter legal i tributari obligatori per a la facturació oficial Veri*factu.
- Els usuaris disposen de connexió mòbil a camp; en cas de pèrdua temporal de cobertura, les accions s'encuen al dispositiu i es consoliden de forma atòmica i sense duplicats en recuperar la connexió.
