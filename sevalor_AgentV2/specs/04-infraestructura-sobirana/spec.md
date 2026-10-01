# Especificació Funcional: Infraestructura Sobirana & Governança Superadmin

**Macro-Feature**: `04-infraestructura-sobirana`  
**Estat**: Implementat & Consolidat (Sprint V2)  
**Àmbit**: Governança SaaS Multi-Inquilí, Sobirania Europea de Dades, Onboarding i Salut de Plataforma  

> [!IMPORTANT]
> **Política Global: Alta Màgica OCR (Zero Data Entry)**  
> Tot el sistema implementa la funcionalitat d'Alta Màgica OCR, permetent l'alta d'entitats (Vehicles, Treballadors, Albarans, Factures, Contractes, Clients, Proveïdors) mitjançant l'anàlisi automatitzat de fotografies o PDFs documentals, sense necessitat de picar dades manualment.

---

## 1. Visió de Producte i Context de Negoci

La plataforma **SEVALOR** s'erigeix com el Sistema Operatiu Empresarial per a petites i mitjanes empreses d'instal·lacions tècniques, climatització, electricitat, fluidotècnia i manteniment d'edificis. Aquest mòdul de macro-infraestructura i governança (`04-infraestructura-sobirana`) constitueix el bastió de gestió global del servei i la garantia legal i operativa de sobirania de dades.

### Principis Rectors de Negoci
1. **Sobirania Digital Europea**: Tota la informació de les empreses associades resideix exclusivament en territori de la Unió Europea, complint amb el màxim rigor el RGPD i la LOPDGDD. Es rebutja qualsevol dependència de proveïdors de núvol públic forans o transferències transfrontereres opaces de dades.
2. **Filosofia Zero Mock Data (Dia 0 Real)**: Cap pantalla d'usuari ni panell de control admet dades simulades, generadors aleatoris o dades de prova en entorns operatius. Des del primer segon, el sistema treballa exclusivament sobre registres empresarials verídics.
3. **Segregació Zero-Trust i Privacitat Absoluta**: L'equip d'administració de la plataforma (Superadmin) té assignada la tasca exclusiva de garantir la disponibilitat, estabilitat, quotes i llicències del servei. Per disseny, el Superadmin té prohibit l'accés a les dades operatives privades dels inquilins (clients, feines d'obra, factures, plànols, fotografies o comunicacions).
4. **Governança Unificada i Cicle de Vida Transparent**: Facilitar l'onboarding àgil de noves empreses instal·ladores, la gestió de períodes de prova (Trial de 14 dies), la suspensió per impagament i la baixa certificada amb destrucció legal i irrevocable de les dades.

---

## 2. Històries d'Usuari & Escenaris d'Acceptació

### User Story 1 - Assistent d'Onboarding d'un Nou Tenant amb Marca Camaleònica (Prioritat: P1)

Com a **Superadministrador de la Plataforma**,  
vull donar d'alta una nova empresa instal·ladora mitjançant un assistent estructurat en passos d'alta densitat d'informació, **incloent-hi la configuració de la identitat visual camaleònica** (logotip corporatiu i paleta de colors primari/secundari/accent),  
perquè l'empresa disposi immediatament del seu entorn de treball dedicat, amb la seva vertical configurada, la seva marca visual aplicada a tota la plataforma i el compte arrel per al seu gerent.

**Per què aquesta prioritat**: És el canal fonamental d'ingrés de nous clients a la plataforma, l'origen de la segregació de recursos i el punt únic on es configura la identitat visual de l'empresa (que s'aplica automàticament a la PWA, Dashboard, PDFs i Telegram).  
**Test Independent**: Es pot validar completant el formulari d'onboarding d'una empresa amb dades reals de NIF, raó social, logotip i colors de marca, verificant que es genera el seu espai dedicat amb la identitat visual aplicada i l'enllaç d'invitació inicial per al gerent.

**Escenaris d'Acceptació**:
1. **Given** un Superadministrador autenticat a la consola de governança,  
   **When** introdueix les dades fiscals (Raó Social, NIF corporatiu vàlid, contacte de gerència), tria la vertical tècnica, el pla de llicència, **puja el logotip corporatiu i selecciona els colors de marca (Primary, Secondary, Accent)**,  
   **Then** el sistema valida que el subdomini sol·licitat estigui disponible, assigna l'identificador únic d'empresa, aplica els tokens CSS HSL de la marca camaleònica, crea l'usuari gerent arrel en estat actiu i genera un enllaç segur d'activació d'un sol ús amb validesa de 24 hores.
2. **Given** un intent d'onboarding amb un subdomini reservat pel sistema (com `admin`, `api`, `app` o `billing`) o ja registrat per una altra empresa,  
   **When** s'intenta continuar el procés,  
   **Then** el sistema rebutja immediatament l'operació indicant l'error específic de col·lisió i impedint qualsevol registre duplicat.

---

### User Story 2 - Segregació Zero-Trust i Privacitat Absoluta (Prioritat: P1)

Com a **Gerent d'una Empresa Instal·ladora Inquilina**,  
vull tenir la certesa absoluta que cap personal extern a la meva empresa (incloent els administradors globals de la plataforma) pot visualitzar les dades confidencials del meu negoci,  
perquè la privacitat dels meus clients, els meus marges comercials i els meus documents tècnics estiguin blindats per garanties estructurals.

**Per què aquesta prioritat**: Constitueix el pilar de confiança comercial i compliment del RGPD sobre el qual se sustenta el model SaaS de la companyia.  
**Test Independent**: Es pot provar intentant consultar informació comercial, factures o llistat de clients des de la consola de Superadmin, comprovant que aquests continguts no estan accessibles en cap vista ni informe global.

**Escenaris d'Acceptació**:
1. **Given** un Superadministrador que accedeix al tauler de governança de la plataforma,  
   **When** consulta la llista d'empreses registrades,  
   **Then** només pot visualitzar metadades de servei (raó social, pla contractat, volum d'operaris actius, consum d'emmagatzematge i estat del pagament), sense poder veure les dades operatives de l'empresa.
2. **Given** dos inquilins distints de la plataforma,  
   **When** un d'ells realitza qualsevol consulta des del seu panell de gestió o aplicació de camp,  
   **Then** el sistema garanteix l'aïllament absolut de la informació, sent impossible que dades d'un inquilí es barregin o filtrin a un altre.

---

### User Story 3 - Torre de Control de Salut i Rendiment Operatiu (Prioritat: P1)

Com a **Equip d'Operacions i Suport de Plataforma**,  
vull disposar d'un panell de control de salut en temps real amb indicadors clau de rendiment, concurrència i microserveis,  
perquè puguem anticipar-nos a qualsevol incidència tècnica o degradació de servei abans que afecti el treball dels operaris de camp.

**Per què aquesta prioritat**: Assegura la continuïtat de negoci del servei i la capacitat de resposta davant de pics de demanda o colls d'ampolla.  
**Test Independent**: Es valida accedint a la consola de salut i verificant que tots els indicadors (disponibilitat global, temps de resposta, ràtio d'èxit de peticions i estat dels subsistemes) mostren dades vives sense valors simulats.

**Escenaris d'Acceptació**:
1. **Given** el panell de telemetria operatiu obert,  
   **When** es produeix un augment massiu de peticions o càrrega d'operaris a primera hora del matí,  
   **Then** la torre de control reflecteix els canvis en els temps de resposta i el volum de sessions actives en temps real.
2. **Given** un temps de resposta que supera el llindar acceptable durant més de 3 minuts de forma continuada,  
   **When** es manté aquesta condició,  
   **Then** la consola activa un indicador visual preventiu de servei degradat sense que es registrin continguts personals dels usuaris en els informes d'incidència.

---

### User Story 4 - Governança del Cicle de Vida SaaS i Gestió de Morositat (Prioritat: P2)

Com a **Responsable de Facturació i Governança SaaS**,  
vull poder gestionar l'estat del cicle de vida de cada empresa (Període de Prova, Actiu, Suspès per Impagament, Manteniment, Baixa),  
perquè la plataforma pugui protegir els seus drets de cobrament sense destruir les dades legals del client abans d'hora.

**Per què aquesta prioritat**: Permet el control de les subscripcions i assegura el compliment dels contractes de servei.  
**Test Independent**: Es valida canviant l'estat d'un tenant a "Suspès per Impagament" i comprovant que cap usuari d'aquella empresa pot operar, mostrant-se una pantalla informativa formal, mentre que els seus arxius i registres romanen segurs i inalterats.

**Escenaris d'Acceptació**:
1. **Given** una empresa que excedeix els seus 14 dies de prova sense formalitzar la contractació,  
   **When** el sistema detecta la fi del període,  
   **Then** transiciona automàticament l'estat a Suspès per Impagament, permetent concloure les tasques que ja estaven obertes abans de tancar definitivament les sessions noves.
2. **Given** una empresa suspesa,  
   **When** un treballador o gestor intenta entrar a la seva aplicació,  
   **Then** rep un missatge informatiu d'estat de compte bloquejat, sense accés a les funcionalitats fins que es regularitzi la situació des de la consola de governança.

---

### User Story 5 - Control de Quotes de Llicència i Protecció de Downgrade (Prioritat: P2)

Com a **Superadministrador**,  
vull actualitzar el pla de llicència d'una empresa (Starter, Pro, Enterprise) de forma senzilla, bloquejant intents de reducció que entrin en conflicte amb els operaris actius reals,  
perquè es respectin els límits comercials de cada paquet sense generar inconsistències a l'empresa.

**Per què aquesta prioritat**: Evita situacions il·legals d'excés d'usuaris i protegeix l'empresa de perdre visibilitat dels seus treballadors de manera imprevista.  
**Test Independent**: Es comprova intentant aplicar una reducció de pla a una empresa que compta amb més operaris actius que els permesos pel nou límit, verificant que el canvi és denegat de forma transparent.

**Escenaris d'Acceptació**:
1. **Given** una empresa que sol·licita un increment de pla de Starter (fins a 5 operaris) a Pro (fins a 15 operaris),  
   **When** s'aprova el canvi a la consola,  
   **Then** el límit s'amplia immediatament sense necessitat d'aturar el servei ni reiniciar sessions.
2. **Given** una empresa amb 8 operaris en estat actiu que pretén passar a un pla amb límit de 5 operaris,  
   **When** s'intenta efectuar el canvi de pla,  
   **Then** el sistema bloqueja l'operació i informa clarament que cal donar de baixa prèviament els 3 operaris excedents des del panell de gestió abans de rebaixar la quota.

---

### User Story 6 - Interruptors Dinàmics de Mòduls per Inquilí (Prioritat: P2)

Com a **Superadministrador**,  
vull activar o desactivar mòduls específics (Copilot d'Intel·ligència Artificial, Flota Avançada, Plànols Tècnics, Bot de Telegram) de forma independent per a cada empresa,  
perquè puguem comercialitzar funcionalitats addicionals segons el contracte subscrit.

**Per què aquesta prioritat**: Aporta flexibilitat comercial per oferir extensions i funcionalitats opcionals.  
**Test Independent**: Es valida desactivant el mòdul d'intel·ligència artificial per a un tenant de prova i comprovant que l'assistent queda inhabilitat a la seva interfície, reactivant-se en commutar de nou l'interruptor.

**Escenaris d'Acceptació**:
1. **Given** una empresa que no ha contractat el servei de bot de missatgeria,  
   **When** el Superadministrador desactiva la funcionalitat corresponent,  
   **Then** l'opció deixa d'estar accessible per a l'empresa tant a l'oficina com per als seus clients.
2. **Given** una ampliació de contracte que inclou el visor de plànols tècnics,  
   **When** s'activa el mòdul des de la consola de governança,  
   **Then** la funcionalitat queda immediatament disponible per als tècnics d'oficina i camp sense cap incidència.

---

### User Story 7 - Baixa Certificada, Dret a l'Oblit i Certificat de Destrucció (Prioritat: P3)

Com a **Gerent d'una Empresa que rescindeix el contracte**,  
vull rebre una còpia íntegra de tots els meus fitxers i documents abans de la baixa, seguit de l'eliminació certificada i definitiva de totes les meves dades,  
perquè la meva empresa compleixi les normatives de custòdia documental i exercici del dret a l'oblit d'acord amb el RGPD.

**Per què aquesta prioritat**: Compleix el mandat legal europeu de portabilitat de dades i cancel·lació definitiva del tractament.  
**Test Independent**: Es valida executant el protocol d'offboarding, generant el paquet descarregable de documents i comprovant l'emissió del certificat de destrucció un cop expirat el període de custòdia de 30 dies.

**Escenaris d'Acceptació**:
1. **Given** una empresa en fase de baixa,  
   **When** sol·licita l'exportació sobirana dels seus actius,  
   **Then** el sistema genera un paquet complet i protegit amb tots els seus albarans, factures, fotos d'obra i plànols per a la seva descàrrega directa.
2. **Given** una sol·licitud d'esborrat definitiu completada,  
   **When** s'executa la purga de dades un cop passat el període de gràcia legal,  
   **Then** el sistema elimina de forma irrevocable els registres i fitxers físics, emetent un Certificat de Destrucció de Dades amb segell digital que s'arxiva durant 5 anys per a auditories legals.

---

## 3. Requisits Funcionals del Sistema (Sintaxi EARS)

### Assistent d'Onboarding i Provisionament
- **FR-001 (Ubiquitous)**: El sistema disposarà d'un assistent d'onboarding guiat per passos a la consola de governança que permeti registrar la totalitat dels paràmetres administratius, tècnics i de llicenciament d'una nova empresa.
- **FR-002 (Event-driven)**: Quan es registri una nova empresa, el sistema validarà formalment el NIF corporatiu espanyol i comprovarà la disponibilitat del subdomini sol·licitat en temps real.
- **FR-003 (Event-driven)**: Durant la configuració tècnica, el sistema exigirà la selecció d'una vertical de negoci (SEVALOR general, ELECTRICPRO, HYDROPRO, BUILDINGPRO, o una vertical personalitzada amb famílies de magatzem i directrius d'IA específiques).
- **FR-004 (Event-driven)**: En finalitzar el registre administratiu, el sistema crearà automàticament el compte del gerent arrel i emetrà un enllaç d'activació segur d'un sol ús amb validesa màxima de 24 hores.
- **FR-005 (State-driven)**: Mentre el gerent inicial no hagi definit la seva contrasenya d'alta seguretat i configurat el doble factor d'autenticació (2FA), el sistema denegarà qualsevol accés a l'espai de gestió de l'empresa.

### Segregació i Aïllament de Dades
- **FR-006 (Ubiquitous)**: El sistema garantirà l'aïllament absolut entre empreses mitjançant polítiques estrictes d'aïllament a nivell de registre, impedint que qualsevol consulta reveli informació d'un altre inquilí.
- **FR-007 (Ubiquitous)**: El sistema mantindrà segregats els registres de telemetria tècnica i errors de la plataforma respecte a les dades operatives privades de les empreses.
- **FR-008 (Unwanted-behaviour)**: El sistema prohibirà terminantment l'accés del Superadministrador a factures, clients, ordres de treball, costos, sous o imatges de camp de les empreses registrades.

### Emmagatzematge Sobirà i Gestió Documental
- **FR-009 (Event-driven)**: Quan s'activi un nou inquilí, el sistema inicialitzarà un arbre de carpetes d'emmagatzematge local dedicat a l'empresa sota territori sobirà europeu per allotjar incidències, vehicles, comptabilitat, plànols i còpies de seguretat.
- **FR-010 (Unwanted-behaviour)**: El sistema no farà ús de serveis d'emmagatzematge en núvols públics forans per a cap document, arxiu o imatge pertanyent a les empreses.

### Telemetria i Control de Salut
- **FR-011 (Ubiquitous)**: La consola de governança presentarà en temps real el percentatge de disponibilitat de la plataforma, les latències de resposta (mitjana i percentils alts) i la taxa d'èxit de les operacions.
- **FR-012 (Ubiquitous)**: El sistema reflectirà l'estat operatiu individual de cadascun dels subsistemes de la plataforma (interfície d'usuari, serveis centrals, motor de dades, cua de missatgeria, tasques en segon pla i bots auxiliars).
- **FR-013 (Ubiquitous)**: El sistema auditarà el volum de sessions simultànies actives (distingint entre tècnics de camp i personal d'oficina) i l'ocupació del conjunt de connexions de dades.
- **FR-014 (State-driven)**: Quan la concurrència o la càrrega de processament superi els límits de seguretat definits, el sistema activarà alertes visuals d'escalabilitat i protegirà l'execució de tasques crítiques.

### Cicle de Vida, Llicències i Baixes
- **FR-015 (Ubiquitous)**: Cada empresa estarà associada a un estat formal de cicle de vida: Període de Prova (Trial de 14 dies), Actiu, Suspès per Impagament, Manteniment o Baixa.
- **FR-016 (State-driven)**: Quan una empresa passi a estat de suspensió, el sistema revocarà de manera immediata totes les sessions actives dels seus usuaris i bloquejarà noves connexions, conservant la integritat de les seves dades.
- **FR-017 (Event-driven)**: Quan es sol·liciti una disminució de quota d'operaris que resulti inferior al nombre de treballadors actius actuals de l'empresa, el sistema refusarà l'operació fins que la situació s'hagi regularitzat prèviament.
- **FR-018 (Event-driven)**: Quan s'iniciï la baixa definitiva d'un inquilí, el sistema establirà un període de custòdia de 30 dies naturals durant el qual l'empresa podrà descarregar tots els seus fitxers abans de la seva eliminació irreversible.
- **FR-019 (Event-driven)**: En culminar la purga de dades d'una baixa, el sistema expedirà un certificat unívoc de destrucció de dades amb signatura digital de la plataforma, que quedarà custodiat durant 5 anys.

---

## 4. Entitats Clau del Domini de Governança

```text
+-------------------------------------------------------------+
|                       EMPRESA (Tenant)                      |
|-------------------------------------------------------------|
| Identificador Únic (UUID)                                   |
| Raó Social & NIF Corporatiu                                 |
| Subdomini Tècnic Assignat                                   |
| Vertical Especialitzada (SEVALOR, ELECTRICPRO, etc.)        |
| Pla de Llicència (Starter, Pro, Enterprise)                 |
| Estat del Cicle de Vida (Trial, Actiu, Suspès, Baixa)       |
| Quota d'Operaris Màxims Permesos                            |
| Quota d'Emmagatzematge Autoritzada & Utilitzada             |
| Interruptors de Mòduls Actius (Flags)                       |
| Data d'Onboarding & Timestamps                              |
+-------------------------------------------------------------+
                              | 1
                              |
                              | té 1..N
                              v
+-------------------------------------------------------------+
|                    USUARI (Boss / Operari)                  |
|-------------------------------------------------------------|
| Identificador Únic (UUID)                                   |
| Empresa de Pertinença (Referència a Tenant)                 |
| Nom, Cognoms & NIF Personal                                 |
| Correu Electrònic & Telèfon de Contacte                     |
| Rol Assignat (Boss, Gestor, Operari)                        |
| Estat d'Activació & Doble Factor (2FA) Habilitat            |
+-------------------------------------------------------------+

+-------------------------------------------------------------+
|            TRAÇA DE TELEMETRIA (Esquema Segregat)           |
|-------------------------------------------------------------|
| Identificador Únic d'Incidència                             |
| Punt de Servei Afectat                                      |
| Codi d'Estat del Sistema                                    |
| Traça Tècnica d'Execució (Sense dades privades de clients)  |
| Marca Temporal de l'Esdeveniment                            |
+-------------------------------------------------------------+

+-------------------------------------------------------------+
|              CERTIFICAT DE DESTRUCCIÓ DE DADES              |
|-------------------------------------------------------------|
| Identificador Únic de Certificació                          |
| Empresa Purgada & NIF                                       |
| Data d'Execució de la Purga Definitiva                      |
| Volum de Fitxers & Registres Eliminats                      |
| Empremta Criptogràfica de Validació (Hash Digital)          |
| Període de Custòdia del Rebut (5 anys)                      |
+-------------------------------------------------------------+
```

---

## 5. Criteris d'Èxit Mesurables

- **SC-001 (Zero Dades Simulades)**: El 100% de les dades visualitzades a la consola de governança i als panells operatius prové d'estats reals del sistema, sense cap ús de dades mock.
- **SC-002 (Inviolabilitat de Privacitat)**: 0 incidents de filtració o visibilitat de dades de negoci entre diferents empreses o cap al perfil de Superadministrador.
- **SC-003 (Temps d'Onboarding Integral)**: L'aprovisionament d'una nova empresa (registre de dades, creació del gerent arrel, preparació de carpetes dedicades i generació del token d'invitació) es completa en menys de 5 segons.
- **SC-004 (Disponibilitat Global del Servei)**: La plataforma manté una disponibilitat global igual o superior al 99.9% mensual.
- **SC-005 (Temps de Resposta de la Torre de Control)**: La càrrega dels indicadors de salut i la telemetria es produeix en menys de 800 ms per al percentil 95 (p95).
- **SC-006 (Garantia de Sobirania)**: El 100% dels arxius, documents, fotografies i còpies de seguretat s'emmagatzema exclusivament en centres de dades situats a la Unió Europea, sense dependència de magatzems cloud externs.

---

## 6. Casos Límit i Regles de Negoci

| Cas Límit | Condició Desencadenant | Comportament Esperat del Sistema |
| :--- | :--- | :--- |
| **Col·lisió de Subdomini** | S'intenta triar un subdomini que ja està en ús o és reservat pel sistema (`admin`, `api`, `app`). | L'assistent detecta la col·lisió en temps real i bloqueja el pas indicant el conflicte de forma clara. |
| **Dígit de Control Erroni al NIF** | El NIF corporatiu o del gerent no compleix l'algorisme de validació oficial espanyol. | L'assistent ressalta el camp afectat i no permet enviar el formulari fins a la correcció. |
| **Downgrade Forçat amb Excés d'Operaris** | Es vol reduir la llicència d'una empresa (ex. de 15 a 5) quan té més treballadors actius que el nou límit (ex. 8). | El sistema denega el canvi de quota de forma categòrica, exigint donar de baixa prèviament els operaris excedents. |
| **Token d'Invitació Caducat** | El gerent obre l'enllaç d'invitació transcorregudes més de 24 hores des de la seva emissió. | El portal indica la caducitat de l'enllaç i el Superadministrador pot regenerar-lo amb un sol clic des del panell. |
| **Accés d'Inquilí Suspès** | Un treballador d'una empresa en estat de suspensió per impagament intenta connectar-se. | L'accés queda bloquejat de forma opaca i es presenta una pantalla de requeriment de regularització de pagament. |
| **Retirada de Consentiment i Purga RGPD** | L'empresa sol·licita l'esborrat immediat abans de complir-se els 30 dies de custòdia. | El sistema exigeix doble confirmació fefaent de gerència, executa la purga irreversible i emet el certificat de destrucció de dades. |
