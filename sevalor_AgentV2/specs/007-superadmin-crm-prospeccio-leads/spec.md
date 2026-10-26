# Especificació Funcional: Motor de Prospecció Atòmica per Codi Postal, Lead Scoring Evolutiu, Seqüències de 3 Emails amb Calendari i Correu Bidireccional per al CRM Superadmin

**Macro-Feature**: `007-superadmin-crm-prospeccio-leads`  
**Estat**: En Revisió amb Feedback d'Usuari (SDD)  
**Àmbit**: Exclusiu Consola de Governança `/superadmin/crm` (Prospecció B2B de Sevalor Suite, Qualificació Evolutiva, Calendari Comercial i Outbound HITL)  
**Data d'Actualització**: 2026-10-26  

> [!IMPORTANT]
> **Alineació amb el CRM Existent i la Constitució v4.0:**  
> Aquesta especificació amplia el mòdul actual de CRM de Superadmin (`backend/app/api/v1/superadmin/crm_prospeccio.py` i `pwa/src/app/superadmin/crm/page.tsx`) connectant l'adquisició proactiva de prospectes amb el Pipeline Kanban de 7 etapes (`PROSPECCIO` → `QUALIFICACIO` → `DEMO_7_DIES` → `PROPOSTA` → `NEGOCIACIO` → `GUANYAT` / `PERDUT`), un **Calendari Comercial Integrat**, i el motor ja operatiu de **Demos Reals Aïllades de 7 Dies**. Es manté el principi innegociable de **Zero Mock Data**, **Human-in-the-Loop (HITL)** absolut en l'enviament de correus i **Segregació Zero-Trust** exclusiva per al rol `SUPERADMIN`.

---

## 1. Visió de Producte i Context de Negoci

Perquè el CRM comercial de **Sevalor Suite** sigui impecable en la captació d'empreses de serveis tècnics, manteniment i instal·lacions (5 a 50 operaris), necessita un motor d'adquisició i seguiment quirúrgic que alimenti el Pipeline comercial amb precisió, aprengui tant dels descarts com dels tancaments d'èxit, i organitzi el ritme comercial sobre un **Calendari integrat**.

### Principis Rectors del Mòdul

1. **Execució Atòmica per Codi Postal i Vertical Oberta (Definida per l'Humà)**:
   - Cercar una província sencera de cop és inviable. Les cerques s'executen per unitats atòmiques `(Codi Postal + Vertical escrita per l'humà + Mínim d'Operaris)`.
   - **Vertical 100% oberta i lliure**: Les verticals no venen predefinides ni tancades en un desplegable rígid; és l'operador humà qui escriu lliurement el sector o activitat que vol prospectar (ex. *"Manteniment industrial"*, *"Instal·lacions de climatització"*, *"Reg agrícola"*, *"Electricitat baixa tensió"*, *" Manteniment d'edificis"*, etc.).
   - Quan el lot d'un Codi Postal (ex. `25001`) finalitza, el sistema s'atura, notifica el resultat i espera la decisió humana abans de passar al següent CP (`25002`).

2. **Deduplicació Multi-Validació (Domini Web, Adreça Física o CIF)**:
   - Com que en una prospecció oberta sovint no és possible extreure el CIF d'una empresa, el sistema aplica una **multi-validació per Domini Web normalitzat, Adreça Física normalitzada i CIF**.
   - Si **un o més d'aquests tres valors coincideix** amb un prospecte o client ja existent a la base de dades, el sistema entén que l'empresa està duplicada i omet la creació d'un registre repetit.

3. **Ús Exclusiu a `/superadmin`**:
   - Aquesta eina pertany exclusivament al centre de comandament del propietari del SaaS (`/superadmin/crm`) per comercialitzar Sevalor Suite. Cap inquilí (`/gestio` o `/operari`) hi té accés.

4. **Raonament Avançat (OpenRouter DeepSeek) i Doble Bucle d'Aprenentatge (Descarts Justificats + Tancaments Replicables)**:
   - **Bucle 1 — Transparència i Justificació Humana Obligatòria en Corrections**: El sistema exposa el 100% de les empreses analitzades al CP —tant les **seleccionades** com les **descartades**— amb la seva puntuació (`0–100`) i el motiu de la IA. Si l'humà inverteix la decisió (*"Corregir Criteri"* cap a seleccionat o descartat), **és obligatori que l'humà escrigui la justificació del descart o selecció** perquè la IA tingui una referència exacta en futures cerques.
   - **Bucle 2 — Aprenentatge dels Tancaments d'Èxit (`GUANYAT`) i Replicació**: Quan una empresa es tanca amb èxit i ens contracta (`GUANYAT`), el Superadmin registra la **Raó del Tancament** (per què ens ha contractat, quin dolor clau tenia i quin argument va ser decisiu) i marca si el cas és **Replicable**. El motor utilitza aquests perfils d'èxit per buscar i prioritzar empreses que compleixin els mateixos requisits i replicar l'enfocament guanyador.

5. **Campanya Seqüencial de 3 Emails amb Tempo d'Enviament + Calendari Comercial Integrat (100% HITL)**:
   - Per a cada prospecte qualificat, la IA prepara una **seqüència completa de 3 emails amb el seu tempo d'enviament** planificat al **Calendari del CRM**:
     - **Email 1 (Dia $T_0$ — Contacte Inicial Quirúrgic en 5 Passos)**:
       1. *Gatekeeper / Decisor*: Identificació del Gerent, Propietari, Administrador o Director Tècnic.
       2. *Fita Recent (Cerca Àmplia Multi-Canal)*: Menció d'una fita real recent obtinguda ampliant la cerca més enllà del web corporatiu cap a **LinkedIn, Instagram, notícies de premsa local, adjudicacions o publicacions recents** (obra executada, nova certificació, ampliació de flota, aniversari).
       3. *Punt de Dolor Operatiu*: Alineat amb els 4 angles B2B de Sevalor (*Angle A: Visibilitat en temps real entre oficina, camp i client via PWA + Bot de Telegram*, *Angle B: Control d'estoc a les furgonetes i magatzem*, *Angle C: Del parte de camp a la factura Veri\*factu sense picar dades*, *Angle D: Coneixement tècnic centralitzat i Copilot IA*).
       4. *Solució Sevalor*: Com Sevalor Suite resol aquest coll d'ampolla amb el flux de 30 segons dels operaris i el canal directe de Telegram amb el client final.
       5. *CTA Sense Fricció*: Invitació directa a veure una Demo de 10 minuts o activar l'entorn de prova de 7 dies.
     - **Email 2 (Dia $T_0 + 4$ — Seguiment d'Autoritat i Cas Replicable)**:
       - Aporta un exemple pràctic o patró d'èxit replicable d'una empresa similar que ha resolt el mateix dolor operatiu.
     - **Email 3 (Dia $T_0 + 8$ — Tancament de Seqüència / Diagnòstic Ràpid)**:
       - Últim contacte breu i directe oferint la **Demo Real de 7 Dies** o tancant cordialment el fil per no resultar invasiu.
   - **Calendari Indispensable al CRM**: Tots els tempos d'enviament dels 3 correus, les trucades de seguiment, les alertes de `"Parlar més endavant"` i els venciments de Demos de 7 dies es visualitzen i gestionen des del **Calendari integrat de `/superadmin/crm`**. Cap correu s'envia sol: l'humà valida i dispara els enviaments del dia des del Calendari o la fitxa.

6. **Autoritat de Correu (`tecnic@sevalor.net`), Stalwart + Thunderbird, MX Shield i RGPD/LSSI**:
   - Verificació prèvia obligatòria de registres DNS **MX** i descart de rebots abans d'acceptar un lead.
   - Servidor de correu sobirà **Stalwart Mail Server** a Hetzner combinat amb un **Relay SMTP Europeu d'IP neta** i sincronització bidireccional via **IMAP / SMTP** amb **Mozilla Thunderbird** (`Message-ID` i `In-Reply-To`).
   - Compliment estricte RGPD i LSSI amb llista negra universal d'opt-out (`saas_exclusio_rgpd`).

---

## 2. Històries d'Usuari & Escenaris d'Acceptació

### User Story 1 — Execució Atòmica per Codi Postal amb Vertical Lliure i Deduplicació Multi-Criteri (Prioritat: P1)

Com a **Superadministrador de Sevalor**,  
vull llançar una cerca de prospectes per a un únic Codi Postal escrivint jo mateix el nom de la vertical/sector i definint el mínim d'operaris (ex. *CP `25001`, Vertical escrita per l'humà: `"Manteniment industrial i climatització"`, mínim `5` operaris*), seguint el progrés en viu via SSE i evitant duplicats mitjançant la validació de domini web, adreça física o CIF,  
perquè pugui prospectar qualsevol nínxol de mercat pas a pas sense llistes predefinides rígides ni empreses repetides.

**Per què aquesta prioritat**: Permet atacar qualsevol sub-sector tècnic amb control total per Codi Postal i garanteix que les empreses sense CIF públic al web tampoc es dupliquin gràcies a la coincidència per domini o adreça física.  
**Test Independent**: Llançar una tasca per al CP `25001` escrivint una vertical lliure, observar els esdeveniments SSE fins a `COMPLETAT`, i verificar que una empresa amb el mateix domini web o la mateixa adreça física no es duplica en executar un segon lot.

**Escenaris d'Acceptació**:
1. **Given** un Superadministrador autenticat a `/superadmin/crm` (pestanya *"Explorador de Leads per CP"*),  
   **When** introdueix el Codi Postal `25001`, escriu lliurement el nom de la vertical (ex. `"Empreses de manteniment"`) i defineix `operaris_minims = 5`, i prem *"Executar Lot CP"*,  
   **Then** el sistema crea un registre a `saas_prospeccio_tasques` amb la vertical introduïda per l'humà, inicia la cerca (web + xarxes socials públiques com LinkedIn i Instagram) i emet el progrés en temps real via Server-Sent Events (SSE).
2. **Given** una tasca de prospecció del CP `25001` que finalitza l'anàlisi de les empreses descobertes al codi postal,  
   **When** el worker processa l'últim candidat del lot,  
   **Then** la tasca passa a estat `COMPLETAT`, mostra el balanç final i ofereix el botó manual *"Preparar següent CP (`25002`)"*, sense iniciar cap nova cerca de manera autònoma.
3. **Given** una empresa descoberta durant la prospecció,  
   **When** el sistema en valida la unicitat contra la base de dades existent (`saas_leads` i `empreses`),  
   **Then** aplica la **multi-validació sobre 3 camps: Domini Web normalitzat, Adreça Física normalitzada i CIF**; si **un o més d'aquests tres valors coincideix** amb un registre existent, el sistema classifica l'empresa com a `DUPLICAT` i evita crear un lead repetit.

---

### User Story 2 — Auditoria Transparent, Justificació Obligatòria de Descarts i Aprenentatge per Tancaments d'Èxit (Prioritat: P1)

Com a **Superadministrador de Sevalor**,  
vull auditar totes les empreses analitzades en cada Codi Postal (seleccionades i descartades), corregir les decisions de la IA introduint obligatòriament la justificació humana del descart o selecció, i registrar la raó d'èxit quan una empresa ens contracta (`GUANYAT`) per replicar el seu perfil en futures cerques,  
perquè l'algorisme de qualificació aprengui tant del que no ens interessa com dels perfils exactes que es converteixen en clients reals.

**Per què aquesta prioritat**: La IA necessita referències explícites: saber per què un humà descarta una empresa concreta i saber per què un client real ha signat el contracte permet replicar l'èxit comercial de manera sistemàtica.  
**Test Independent**: Intentar descartar un candidat sense escriure justificació (comprovant que el sistema ho exigeix), desar el descart amb justificació, i posteriorment tancar una oportunitat com a `GUANYAT` amb la raó de contractació marcada com a replicable, verificant que ambdós aprenentatges s'incorporen al context del motor IA.

**Escenaris d'Acceptació**:
1. **Given** un lot de prospecció d'un Codi Postal,  
   **When** el Superadministrador obre la taula d'auditoria del lot,  
   **Then** visualitza tant les **Empreses Seleccionades** com les **Empreses Descartades**, amb la puntuació (`0–100`), operaris estimats, decisor, fita trobada (web/LinkedIn/Instagram), punt de dolor i la justificació detallada de DeepSeek.
2. **Given** una empresa seleccionada o descartada per la IA amb la qual l'operador humà no està d'acord,  
   **When** el Superadministrador prem *"Corregir Criteri"* (per descartar-la o per seleccionar-la),  
   **Then** el sistema **exigeix obligatòriament que l'humà escrigui la justificació detallada** (`motiu_correccio_humana`, mínim 10 caràcters) abans de confirmar l'acció, guardant aquesta regla com a referència negativa o positiva a `saas_criteris_feedback`.
3. **Given** una oportunitat del CRM que es tanca amb èxit i passa a l'etapa `GUANYAT` (l'empresa contracta Sevalor Suite),  
   **When** el Superadministrador registra el tancament,  
   **Then** el sistema sol·licita la **Raó del Tancament (`rao_tancament_exit`)**, el dolor decisiu que va motivar la compra i un marcador **`es_replicable = True`**, emmagatzemant aquest **Patró d'Èxit Replicable** perquè el motor de prospecció prioritzi empreses amb els mateixos requisits i repliqui l'argumentari en noves campanyes.

---

### User Story 3 — Campanya de 3 Emails amb Tempo d'Enviament i Calendari Comercial Integrat al CRM (Prioritat: P1)

Com a **Superadministrador de Sevalor**,  
vull que per a cada lead qualificat es generi una campanya personalitzada de **3 emails amb el seu tempo d'enviament** (basada en el decisor, fites recents a web/LinkedIn/Instagram, punt de dolor, solució amb PWA + Telegram i casos d'èxit replicables) i disposar d'un **Calendari integrat al CRM** on veure, revisar i aprovar els enviaments programats de cada dia,  
perquè pugui executar un seguiment comercial impecable i estructurat en el temps sense perdre el control humà de cada enviament.

**Per què aquesta prioritat**: Un únic correu aïllat té baixa conversió en B2B; una seqüència de 3 impactes espaiats en el temps i governada des d'un Calendari visual dins del CRM assegura constància comercial sense enviaments automàtics cecs.  
**Test Independent**: Qualificar un lead, comprovar que es generen els 3 esborranys de la seqüència amb les seves dates de tempo (`Dia 1`, `Dia +4`, `Dia +8`), visualitzar-los al Calendari del CRM i aprovar manualment l'enviament del primer correu.

**Escenaris d'Acceptació**:
1. **Given** un candidat que supera el filtre de qualificació i té registres DNS **MX vàlids**,  
   **When** s'incorpora com a `SaasLead` al CRM,  
   **Then** el sistema genera automàticament una **Campanya de 3 Emails en estat `ESBORRANY_PROGRAMAT`** amb el seu tempo d'enviament:
   - **Email 1 (Tempo: Dia $T_0$ — Contacte Inicial 5 Passos)**: Dirigit al Gatekeeper/Decisor, esmentant la fita recent detectada (web, LinkedIn, Instagram o notícies), el punt de dolor operatiu, la solució Sevalor (connexió oficina-camp i bot de Telegram per al client) i el CTA per a Demo.
   - **Email 2 (Tempo: Dia $T_0 + 4$ — Valor i Cas Replicable)**: Seguiment centrat en com empreses del mateix perfil/vertical han eliminat el coll d'ampolla (aprofitant els patrons d'èxit replicables registrats al CRM).
   - **Email 3 (Tempo: Dia $T_0 + 8$ — Diagnòstic / Demo 7 Dies)**: Últim impacte breu proposant activar l'entorn de prova de 7 dies o tancant el cicle amb elegància.
2. **Given** el panell `/superadmin/crm`,  
   **When** el Superadministrador obre la pestanya **"Calendari Comercial"**,  
   **Then** visualitza en una vista de calendari (mensual, setmanal i agenda diària) tots els esderanys de la seqüència de 3 emails segons el seu tempo (`Email 1`, `Email 2`, `Email 3`), juntament amb les reunions de demo, els recordatoris d'objeccions de temps i els venciments de Demos de 7 dies.
3. **Given** un email programat al Calendari per al dia d'avui,  
   **When** el Superadministrador hi fa clic des del Calendari, en revisa/edita el text i prem *"Aprovar i Enviar des de tecnic@sevalor.net"*,  
   **Then** el correu s'envia via Stalwart + Relay SMTP, es marca com a `ENVIAT` al Calendari i es programa la visibilitat del següent pas del tempo (`Email 2` o `Email 3`).
4. **Given** un lead que té l'`Email 2` i l'`Email 3` pendents al Calendari,  
   **When** el sistema detecta que el lead ha respost a l'`Email 1`,  
   **Then** el sistema pausa/cancel·la automàticament els correus restants de la seqüència al Calendari (`PAUSAT_PER_RESPOSTA`) perquè mai s'enviï un correu de seguiment fred a un prospecte que ja ha iniciat conversa.

---

### User Story 4 — Connexió Bidireccional de Correu (Stalwart + Thunderbird) i Qualificació Automàtica de Respostes (Prioritat: P1)

Com a **Superadministrador de Sevalor**,  
vull que el CRM estigui connectat de forma bidireccional amb el servidor de correu `tecnic@sevalor.net` (accessible des de Mozilla Thunderbird i des de `/superadmin/crm`), llegint les respostes entrants, emparellant-les pel fil de conversa (`Message-ID` / `In-Reply-To`), classificant-ne la intenció amb IA i actualitzant el Kanban i el Calendari,  
perquè tota l'activitat de correu quedi sincronitzada i qualificada en temps real.

**Per què aquesta prioritat**: Tanca el bucle entre la bústia de correu, el Pipeline Kanban i el Calendari Comercial.  
**Test Independent**: Processar un correu entrant amb `In-Reply-To` vinculat a un lead amb seqüència activa, i verificar que es classifica per intenció, s'aturen els enviaments pendents de la seqüència al Calendari i s'actualitza l'oportunitat al Kanban.

**Escenaris d'Acceptació**:
1. **Given** un correu entrant a `tecnic@sevalor.net` amb capçalera `In-Reply-To` / `References` o provinent del domini d'un lead,  
   **When** el sincronitzador IMAP processa el missatge,  
   **Then** el vincula al `SaasLead`, atura qualsevol pas pendent de la seqüència de 3 correus al Calendari i afegeix el missatge al fil de conversa.
2. **Given** una resposta entrant vinculada a un lead,  
   **When** OpenRouter (DeepSeek) n'analitza la intenció,  
   **Then** la classifica i executa l'acció corresponent al Kanban i al Calendari:
   - `INTERESSAT_DEMO`: Mou el lead a `DEMO_DEMANADA`, l'oportunitat Kanban a `QUALIFICACIO` i crea una alerta d'acció al Calendari del dia per activar la Demo de 7 Dies.
   - `INTERESSAT_INFO`: Mou el lead a `QUALIFICAT`, l'oportunitat a `QUALIFICACIO` i prepara un esborrany de resposta tècnica per a revisió humana.
   - `OBJECCIO_TEMPS` (*"Parleu-nos el mes que ve"*): Extreu la data suggerida pel prospecte i **crea automàticament un esdeveniment de seguiment al Calendari del CRM** en la data indicada.
   - `NO_INTERESSAT`: Mou el lead a `DESCARTAT`, l'oportunitat a `PERDUT` i cancel·la els passos pendents al Calendari.
   - `BAIXA_OPTOUT`: Mou el lead a `DESCARTAT`, l'oportunitat a `PERDUT`, cancel·la qualsevol esdeveniment futur al Calendari i insereix l'email i el domini a `saas_exclusio_rgpd`.
   - `OUT_OF_OFFICE`: Registra l'absència temporal i, si indica data de retorn, posposa el tempo del següent correu al Calendari fins després d'aquella data.

---

## 3. Requisits Funcionals del Sistema (Sintaxi EARS)

### Execució Atòmica per Codi Postal, Vertical Lliure i Cerca Multi-Canal
- **FR-001 (Ubiquitous)**: El sistema restringirà tots els endpoints i vistes del motor de prospecció, scoring, calendari comercial i correu exclusivament als usuaris amb rol `SUPERADMIN`.
- **FR-002 (Event-driven)**: Quan el Superadministrador iniciï una cerca de leads per Codi Postal, el sistema permetrà introduir:
  1. `codi_postal` (5 dígits).
  2. `vertical` com a **camp de text lliure definit per l'humà** (sense limitar-lo a una llista tancada).
  3. `operaris_minims` (enter $\ge 1$, per defecte `5`).
- **FR-003 (Unwanted-behaviour)**: El sistema no encadenarà mai de forma automàtica l'execució del següent Codi Postal en finalitzar el lot actual; tota transició al següent Codi Postal requerirà una acció explícita de l'operador humà.
- **FR-004 (Event-driven)**: Durant l'execució d'un lot de Codi Postal, el sistema realitzarà una **investigació multi-canal àmplia** per a cada empresa candidata, combinant el rastreig del seu **web corporatiu** amb la cerca de mencions i perfils públics a **LinkedIn, Instagram, notícies de premsa i adjudicacions recents** mitjançant Firecrawl per descobrir el decisor i les fites recents reals.
- **FR-005 (State-driven)**: Mentre una tasca de Codi Postal estigui en estat `EXECUTANT`, el sistema emetrà esdeveniments en temps real via **Server-Sent Events (SSE)** informant del progrés d'inspecció multi-canal, validació de duplicats, verificació MX i puntuació.
- **FR-006 (Event-driven)**: Quan s'analitzi una empresa candidata, el sistema executarà una **multi-validació de duplicitat sobre tres vectors: Domini Web normalitzat, Adreça Física normalitzada i CIF**; si **un o més d'aquests tres valors coincideix** amb un registre existent a `saas_leads`, a `empreses` o a `saas_exclusio_rgpd`, el sistema marcarà l'empresa com a `DUPLICAT` i n'ometrà la creació.

### Validació DNS MX Shield
- **FR-007 (Event-driven)**: Abans de qualificar com a enviables els correus d'una empresa, el sistema verificarà la sintaxi RFC 5322, descartarà dominis genèrics o temporals i consultarà asíncronament els registres DNS **MX** del domini per confirmar que té servidors de correu actius (`mx_validat = True`).
- **FR-008 (Unwanted-behaviour)**: Si un domini no disposa de registres DNS MX vàlids o figura a `saas_exclusio_rgpd`, el sistema bloquejarà qualsevol intent d'enviament SMTP per protegir la reputació de `sevalor.net`.

### Qualificació amb OpenRouter (DeepSeek) i Doble Bucle d'Aprenentatge
- **FR-009 (Event-driven)**: Per a cada empresa candidata, el sistema invocarà l'API d'**OpenRouter** (DeepSeek) exigint una resposta estructurada amb **Pydantic** que contingui:
  1. `operaris_estimats`, `decisor_nom`, `decisor_carrec` i `fonts_consultades` (web, LinkedIn, Instagram, premsa).
  2. `fita_recent` (fita real detectada en qualsevol dels canals analitzats).
  3. `punt_dolor` i `angle_atac` (`ANGLE_A_VISIBILITAT_TELEGRAM`, `ANGLE_B_ESTOC_FURGONETES`, `ANGLE_C_CAMP_FACTURA`, `ANGLE_D_CONEIXEMENT_IA`).
  4. `score` (`0` a `100`), `estat_decisio` (`SELECCIONAT` o `DESCARTAT`) i `motiu_detallat_ia`.
  5. Si és `SELECCIONAT`, els **3 esborranys de la campanya d'email màrqueting** amb el seu tempo (`Email 1 [Dia 0]`, `Email 2 [Dia +4]`, `Email 3 [Dia +8]`).
- **FR-010 (Ubiquitous)**: El sistema persistirà a `saas_prospeccio_candidats` el 100% de les empreses avaluades en cada Codi Postal —tant les seleccionades com les descartades— amb la seva justificació completa.
- **FR-011 (Event-driven)**: Quan el Superadministrador utilitzi l'acció *"Corregir Criteri"* sobre qualsevol candidat (especialment en descartar una empresa seleccionada per la IA o en seleccionar-ne una de descartada), el sistema **exigirà com a camp obligatori la justificació humana (`motiu_correccio_humana`)**, la desarà a `saas_criteris_feedback` i la injectarà com a referència obligatòria en les següents crides a la IA.
- **FR-012 (Event-driven)**: Quan una oportunitat al CRM passi a l'etapa **`GUANYAT`** (empresa tancada que ens contracta), el sistema permetrà registrar la **Raó del Tancament (`rao_tancament_exit`)**, els requisits clau que complia l'empresa i si és un **Cas Replicable (`es_replicable = True`)**; el motor d'IA utilitzarà aquests perfils d'èxit per prioritzar empreses amb idèntics atributs en futures prospeccions i replicar els arguments que van portar a la venda.

### Campanya de 3 Emails, Tempo d'Enviament i Calendari Comercial del CRM
- **FR-013 (Ubiquitous)**: Per a tot lead qualificat, el sistema estructurarà una campanya seqüencial de **3 correus** en estat `ESBORRANY_PROGRAMAT`:
  - **Email 1 (Dia $T_0$)**: Estructura de 5 passos (Gatekeeper $\rightarrow$ Fita recent multi-canal $\rightarrow$ Dolor operatiu $\rightarrow$ Solució Sevalor amb PWA i Bot de Telegram $\rightarrow$ CTA Demo).
  - **Email 2 (Dia $T_0 + 4$)**: Seguiment d'autoritat amb cas pràctic / patró d'èxit replicable del seu mateix sector.
  - **Email 3 (Dia $T_0 + 8$)**: Últim impacte de diagnòstic ràpid o invitació a activar la Demo de 7 dies.
- **FR-014 (Ubiquitous)**: El CRM de Superadmin (`/superadmin/crm`) disposarà d'un **Calendari Comercial Integrat** on es visualitzaran i gestionaran tots els esdeveniments temporals: tempos d'enviament dels 3 correus (`Email 1`, `Email 2`, `Email 3`), demos agendades, venciments de Demos de 7 dies i recordatoris de seguiment futur.
- **FR-015 (Unwanted-behaviour)**: Cap dels 3 correus de la campanya s'enviarà de forma automàtica en arribar la seva data al Calendari; l'arribada del tempo destacarà el correu com a `PENDENT_APROVACIO_AVUI` al Calendari perquè l'operador humà el revisi i en dispari l'enviament.
- **FR-016 (Event-driven)**: Quan es rebi una resposta d'un lead que tingui correus posteriors de la seqüència (`Email 2` o `Email 3`) programats al Calendari, el sistema cancel·larà o pausarà automàticament els enviaments pendents d'aquella seqüència.

### Servidor de Correu (Stalwart + Thunderbird) i Qualificació Inbound
- **FR-017 (Ubiquitous)**: El sistema utilitzarà la bústia `tecnic@sevalor.net` sobre **Stalwart Mail Server** a Hetzner (compatible per IMAP/SMTP amb **Mozilla Thunderbird**) i enrutarà la sortida SMTP a través d'un relay autoritzat amb **DKIM, SPF i DMARC** vàlids.
- **FR-018 (Event-driven)**: Tot correu enviat inclourà capçaleres RFC 5322 (`Message-ID`, `In-Reply-To`, `References`) i el peu legal de transparència B2B (RGPD / LSSI) amb opció de baixa.
- **FR-019 (Event-driven)**: Quan es rebi una resposta (`INBOUND`) a `tecnic@sevalor.net`, el sistema l'emparellarà amb el lead, en classificarà la intenció amb DeepSeek (`INTERESSAT_DEMO`, `INTERESSAT_INFO`, `OBJECCIO_TEMPS`, `NO_INTERESSAT`, `BAIXA_OPTOUT`, `OUT_OF_OFFICE`), actualitzarà l'etapa del Kanban i programarà o cancel·larà els esdeveniments corresponents al **Calendari del CRM**.

---

## 4. Entitats Clau del Domini

```text
+-----------------------------------------------------------------------+
|                     SAAS_PROSPECCIO_TASQUES                           |
|-----------------------------------------------------------------------|
| id (UUID PK)                                                          |
| codi_postal (VARCHAR 10) — ex. '25001'                                |
| vertical (VARCHAR 150) — Text lliure definit per l'humà               |
| operaris_minims (INT) — ex. 5                                         |
| estat (VARCHAR 30) — PENDENT, EXECUTANT, COMPLETAT, PAUSAT, ERROR     |
| total_trobats, total_seleccionats, total_descartats, total_duplicats  |
| created_at, completed_at (TIMESTAMPTZ)                                |
+-----------------------------------------------------------------------+
                                   | 1
                                   | genera 1..N
                                   v
+-----------------------------------------------------------------------+
|                    SAAS_PROSPECCIO_CANDIDATS                          |
|        (Transparència Total: Seleccionats + Descartats del CP)        |
|-----------------------------------------------------------------------|
| id (UUID PK), tasca_id (FK)                                           |
| nom_empresa, cif, web_url, domini_normalitzat                         |
| adreca_fisica, adreca_normalitzada, codi_postal                       |
| vertical (VARCHAR 150 — lliure)                                       |
| fonts_investigades (JSON/TEXT — web, linkedin, instagram, premsa)     |
| email_detectat, telefon_detectat, mx_validat (BOOL)                   |
| operaris_estimats (INT), decisor_nom, decisor_carrec                  |
| fita_recent, punt_dolor, angle_atac                                   |
| score (INT 0..100), estat_decisio (SELECCIONAT|DESCARTAT|DUPLICAT)    |
| motiu_detallat_ia (TEXT)                                              |
| corregit_huma (BOOL), decisio_humana, motiu_correccio_humana (OBLIG.) |
| lead_id (UUID FK -> saas_leads.id NULLABLE)                           |
+-----------------------------------------------------------------------+
          |                                                |
          | Bucle 1: Descarts/Correccions                  | si SELECCIONAT
          | Bucle 2: Tancaments GUANYAT Replicables        v
          v                                  +--------------------------------------+
+-----------------------------------+        |        SAAS_LEADS (Ampliada)         |
|      SAAS_CRITERIS_FEEDBACK       |        |--------------------------------------|
|  (Descarts + Tancaments d'Èxit)   |        | + cif, web_url, domini_normalitzat   |
|-----------------------------------|        | + adreca_fisica, adreca_normalitzada |
| id (UUID PK)                      |        | + codi_postal, carrec_contacte       |
| tipus_aprenentatge:               |        | + fita_recent, fonts_fita            |
|   CORRECCIO_DESCART |             |        | + punt_dolor_detectat, angle_atac    |
|   CORRECCIO_SELECCIO |            |        | + score_qualificacio, justificacio_ia|
|   TANCAMENT_EXIT_REPLICABLE       |        | + rao_tancament_exit, es_replicable  |
| vertical (VARCHAR 150)            |        +--------------------------------------+
| nom_empresa, perfil_requisits     |                      | 1
| explicacio_humana_o_rao_exit(TEXT)|                      | té Campanya 3 Emails + Esdeveniments
| es_replicable (BOOL)              |                      v
+-----------------------------------+        +--------------------------------------+
                                             |   SAAS_CALENDARI_I_SEQUENCIA_EMAIL   |
+-----------------------------------+        |  (Campanya 3 Emails + Calendari CRM) |
|        SAAS_EXCLUSIO_RGPD         |        |--------------------------------------|
|   (Llista Negra Opt-Out / Bounces)|        | id (UUID PK), lead_id (FK)           |
|-----------------------------------|        | pas_sequencia (1, 2, 3) o ESDEVENIM. |
| id (UUID PK), email, domini, cif  |        | data_programada (TIMESTAMPTZ)        |
| motiu (OPTOUT, REBOT_HARD, MANUAL)|        | estat (ESBORRANY_PROGRAMAT, ENVIAT,  |
+-----------------------------------+        |   PAUSAT_PER_RESPOSTA, CANCEL_LAT)   |
                                             | assumpte, cos_text, message_id       |
                                             | in_reply_to, intencio_ia_resposta    |
                                             +--------------------------------------+
```

---

## 5. Criteris d'Èxit Mesurables

- **SC-001 (Aïllament Atòmic per Codi Postal i Vertical Oberta)**: El 100% de les tasques de prospecció accepten qualsevol vertical escrita per l'operador humà, s'executen sobre un únic Codi Postal i finalitzen sense encadenar el següent CP automàticament.
- **SC-002 (Deduplicació Multi-Validació 3 Vectors)**: 0 leads duplicats quan una empresa candidata coincideix en **Domini Web**, **Adreça Física** o **CIF** amb un registre ja existent.
- **SC-003 (Justificació Humana Obligatòria i Aprenentatge de Tancaments)**: El 100% de les correccions de criteri exigeixen justificació textual de l'humà, i el 100% dels tancaments marcats com a `GUANYAT` i replicables s'incorporen al motor de cerca per prioritzar empreses bessones (*lookalikes*).
- **SC-004 (Campanya de 3 Emails i Calendari Comercial Operatiu)**: El 100% dels leads qualificats reben la proposta dels 3 correus amb el seu tempo (`Dia 0`, `Dia +4`, `Dia +8`) planificats al **Calendari del CRM**, i els passos pendents s'aturen automàticament si el prospecte respon.
- **SC-005 (Protecció MX Shield i Human-in-the-Loop)**: 0 correus enviats sense registres DNS MX vàlids, 0 correus enviats a dominis de `saas_exclusio_rgpd` i 0 correus llançats sense aprovació humana explícita.

---

## 6. Casos Límit i Regles de Negoci

| Cas Límit | Condició Desencadenant | Comportament Esperat del Sistema |
| :--- | :--- | :--- |
| **Empresa sense CIF al web però amb mateixa Adreça o Domini** | En prospectar un CP es troba una empresa que no publica el seu CIF, però el seu domini web o la seva adreça física ja consta a la base de dades. | La multi-validació (`Domini Web` $\lor$ `Adreça Física` $\lor$ `CIF`) detecta la coincidència i la marca immediatament com a `DUPLICAT`. |
| **Fita Recent a LinkedIn / Instagram i no al Web** | El web corporatiu és antic i estàtic, però l'empresa ha publicat recentment una obra o nova furgoneta a LinkedIn, Instagram o premsa local. | El motor de cerca multi-canal recull la fita de les xarxes/notícies públiques i la utilitza al Pas 2 de l'`Email 1`, citant la font real sense inventar dades. |
| **Intent de Descartar sense Justificació Humana** | L'operador humà prem *"Corregir Criteri → Descartar"* però deixa el camp de motiu buit. | El sistema bloqueja l'acció i exigeix explicar per què es descarta l'empresa perquè la IA pugui aprendre la regla d'exclusió. |
| **Resposta del Prospecte després de l'Email 1** | El prospecte respon a l'`Email 1` abans que arribi la data programada de l'`Email 2` (Dia +4) al Calendari. | El sistema cancel·la/pausa automàticament l'`Email 2` i l'`Email 3` al Calendari Comercial, classifica la resposta i actualitza l'etapa del Kanban. |
| **Resposta amb Objecció de Temps ("Truqueu-nos a l'octubre")** | El prospecte respon que ara tenen pic de feina i demana parlar més endavant. | La IA classifica `OBJECCIO_TEMPS`, pausa la seqüència actual i agenda automàticament un esdeveniment de reactivació al **Calendari del CRM** en la data sol·licitada. |
