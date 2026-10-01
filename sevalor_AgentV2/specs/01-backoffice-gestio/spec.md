# Feature Specification: Backoffice Gestió

**Feature Branch**: `01-backoffice-gestio`
**Created**: 2026-09-29
**Status**: Draft

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Torre de Control, Feines i Mapa Operatiu (Priority: P1)
Com a Enginyer o Boss, vull disposar d'una pantalla única amb un mapa cartogràfic interactiu (que mostri coordenades o adreces físiques reals), KPIs de gestió de tasques i un accés ràpid per crear feines. El cor del sistema és la descripció completa de la feina (materials, operaris, vehicles). Vull poder reassignar treballs mitjançant "Drop & Go" i conèixer l'estat d'execució d'un sol cop d'ull.
**Why this priority**: És el nucli de coordinació diària de l'empresa.
**Independent Test**: Creació d'una feina amb operaris i materials, visualització d'aquesta al mapa amb les seves adreces, i reassignació de l'operari.

### User Story 2 - Fitxa 360 i Alta Operaris via DNI OCR (Priority: P1)
Com a RRHH o Secretaria, vull donar d'alta els treballadors usant l'OCR del seu DNI (Alta Màgica), disposar d'una fitxa 360 de l'operari (amb incidències reportades, carnet de conduir) i gestionar el control horari. Tots els treballadors (secretaria, enginyer, operari) han de fitxar entrada i sortida adjuntant sempre les coordenades (sense tancament automàtic a les 8h per permetre hores extres o incidències).
**Why this priority**: Compliment legal de control horari i RRHH.
**Independent Test**: Pujada d'un DNI real per crear l'operari. Fitxatge manual d'inici i final adjuntant coordenades reals.

### User Story 3 - Magatzem, Mermes i Alta Proveïdors OCR (Priority: P1)
Com a Responsable de Compres, vull donar d'alta proveïdors i albarans via OCR, revisant les dades extretes (comptes, descomptes per article) abans de consolidar. Vull gestionar l'estoc de peces amb codis de barres (EAN, Code128) o números de referència alfanumèrica (sense QR). Pels materials continus, vull considerar un % de merma. Si l'estoc baixa, vull que el sistema redacti (però no enviï) un esborrany d'email al proveïdor.
**Why this priority**: Evitar trencament d'estocs i agilitzar les entrades logístiques.
**Independent Test**: Escanejar un codi de barres per treure material. Pujar un PDF d'albarà de proveïdor, verificar les dades i validar-lo manualment.

### User Story 4 - Flota i Manteniment Integral (Priority: P2)
Com a Responsable de Flota, vull inventariar els vehicles determinant el tipus de carnet necessari, portar el bloc de manteniment complet (historial de reparacions, canvis d'oli, taller principal, estat de garantia oficial) i poder derivar vehicles a grua o reparació. Vull alertes de manteniment i control d'odòmetre per càmera.
**Why this priority**: Seguretat viària i control del capítol d'amortitzacions.
**Independent Test**: Afegir un manteniment real d'un vehicle, comprovar que el carnet requerit bloqueja operaris sense llicència adequada.

### User Story 5 - Facturació Veri*factu i Menú Econòmic Exclusiu (Priority: P1)
Com a Boss, vull un accés exclusiu al menú "Economics" amb el dashboard financer (gràfiques, previsions). La comptabilitat inclourà el seguiment de factures vençudes o impagades. Per emetre factures, sempre cal revisar prèviament el full de tasca, pressupostos i incidències, generant primer un albarà/pre-factura. Un cop humà el valida, es passa a factura inalterable (amb possibilitat de factures rectificatives).
**Why this priority**: Segregació Zero-Trust total i seguretat fiscal.
**Independent Test**: Logatge com a Operari (accés denegat a Economics). Logatge com a Boss, creació de pre-factura a partir de feina tancada, i generació de factura Veri*factu.

### User Story 6 - Edició de Plànols GIS No Destructiva (Priority: P2)
Com a Enginyer Tècnic o Operari, vull obrir plànols a la biblioteca i editar-los afegint capes amb colors i formes preestablertes (canonades, cables, incidències) sense malmetre o sobreescriure mai el plànol original, sinó creant una nova capa de modificacions.
**Why this priority**: Evita la degradació documental dels actius ("As-Built").
**Independent Test**: Obrir plànol, pintar nova canonada vermella i desar-la com a nova capa. El PDF original ha de romandre intacte.

### User Story 7 - Copilot IA Integrat i Notificacions Telegram (Priority: P3)
Com a Boss o Enginyer, vull interrogar el Copilot IA per trobar informació creuada de factures, operaris i materials. Com a Supervisor, vull poder disparar notificacions d'incidències directament cap al Telegram del client (Human-in-the-Loop).
**Why this priority**: Maximitza la productivitat de l'oficina i la comunicació directa.
**Independent Test**: Obrir el Copilot, preguntar sobre l'estoc d'un article i l'historial d'un vehicle. Enviar missatge d'una incidència d'obra a un client per Telegram.

### User Story 8 - Pressupostos amb Botó Triple (Priority: P1)
Com a usuari creant una Ordre de Treball (OT), vull que el formulari tingui 3 botons: [Generar Tasca], [Generar Pressupost] (manual) i [✨ Pressupost Intel·ligent (Copilot)] on la IA suggereixi preus basant-se en l'historial. El pressupost generat s'enviarà al client via Telegram o Email i, un cop acceptat, es convertirà automàticament en una OT amb el picking de materials pre-assignat.
**Why this priority**: Automatitza i agilitza enormement la presentació de pressupostos usant històrics de l'empresa.
**Independent Test**: Fer clic a "Pressupost Intel·ligent", enviar-lo per email i simular l'acceptació per verificar que l'OT es crea amb el material llest.

### User Story 9 - Fitxa 360° del Client (Priority: P2)
Com a usuari gestor, vull accedir a una Fitxa 360° per client on visualitzar el seu historial complet, incloent-hi feines passades i actives, pressupostos enviats, factures emeses, incidències, contractes actius i un registre de les comunicacions per Telegram.
**Why this priority**: Permet un context total i ràpid sobre l'estat d'un client.
**Independent Test**: Entrar a la fitxa d'un client recurrent i verificar la llista consolidada de factures, incidències i missatgeria.

### User Story 10 - Dashboard Economics Detallat (NOMÉS Boss) (Priority: P1)
Com a Boss, vull tenir un menú 'Economics' exclusiu amb indicadors de rendiment empresarial: EBITDA, facturació mensual/YTD, cobraments vs facturació, factures impagades (>30/>90 dies), marge brut per feina, cost d'hora per operari, cost de flota per km, desviació de material, MRR (Monthly Recurring Revenue) de contractes i la previsió de tresoreria a 30, 60 i 90 dies. Tot amb segregació Zero-Trust total.
**Why this priority**: És fonamental per a la direcció i estratègia financera.
**Independent Test**: Accedir com a Boss a la pestanya Economics i validar que es mostrin el MRR i la previsió a 90 dies; entrar com a Enginyer o Operari i confirmar que la ruta no existeix ni retorna dades.

---

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001 (Zero Mock Data & Testing)**: Durant la implementació, el sistema redactarà una llista dels documents reals necessaris per testejar la funcionalitat implementada (ex. fotocòpia de DNI per altes, albarans reals, permisos de circulació). Després d'executar els tests, l'usuari validarà la implementació basant-se en els documents d'aquesta llista, complint la regla de tolerància zero a dades fictícies.
- **FR-002 (Configuració de l'Empresa)**: El Backoffice de Gestió gestionarà els paràmetres locals (horaris laborals, torns intensius, etc.). Aquesta secció queda oberta per incorporar altres aspectes de configuració empresarial per part del Boss, separant-ho de la identitat visual camaleònica (que es farà exclusivament via Superadmin en l'onboarding).
- **FR-003 (Economics & Segregació)**: Existirà un apartat "Economics" on NOMÉS el rol de Boss podrà visualitzar gràfiques de control total, cerca global financera i previsió de tresoreria. Qualsevol altre perfil tècnic o operatiu serà bloquejat de soca-rel a nivell d'API.
- **FR-004 (Control Horari Fefaent)**: TOT usuari actiu (incloent-hi Secretaria, Enginyeria, etc.) haurà de fitxar inici i final de jornada. Pels perfils mòbils de camp (operaris, cap de colla), el registre incorporarà OBLIGATÒRIAMENT les coordenades físiques tant a l'entrada com a la sortida. El sistema permetrà que les jornades superin les 8 hores (per registrar hores extres i imprevistos) limitant-se a prendre nota i custodiar els registres omesos (sense tancament brusc del servidor).
- **FR-005 (Finques i Georeferenciació)**: La creació d'ordres de treball exigirà sempre localització, ja sigui aportant coordenades lat/long o bé traduint una adreça física completa de pisos, cases o naus per al seu mapatge.
- **FR-006 (Clients i SEPA)**: L'emplenament de l'IBAN i el mandat SEPA per a un client no serà requerit obligatòriament per a la seva creació; no obstant això, en cas de subministrar-se, haurà de superar la validació formativa corresponent.
- **FR-007 (Eines i Traçabilitat)**: Tot l'inventari i eina en custòdia es traçarà ÚNICAMENT mitjançant codis de barres (EAN, Code128) o referències alfanumèriques del fabricant. Es prohibeix la creació o gestió interna amb codis QR per logística.
- **FR-008 (Tolerància de Mermes)**: El consum de materials de longitud contínua (ex. tubs, cables) acceptarà la declaració d'un percentatge de merma (residu descartable) per tal d'ajustar el balanç de magatzem amb la realitat de l'obra. Aquesta operació d'ajustament la farà progressivament el Copilot (IA) aprenent dels registres històrics.
- **FR-009 (Albarans OCR Proveïdors)**: Tota extracció OCR d'albarans presentarà una graella amb el llistat d'articles i possibles descomptes. Aquesta informació romandrà en un estat transitori fins a la validació manual i definitiva de l'usuari humà.
- **FR-010 (Draft d'Email per Trencament d'Estoc)**: Quan l'estoc baixi d'un nivell d'alerta, el sistema construirà automàticament un esborrany d'email dirigit al proveïdor preferent agrupant els materials mancats. Sota cap concepte aquest email s'enviarà sense la pulsació conscient de confirmació per part de l'usuari encarregat.
- **FR-011 (Flota i Manteniments Taller)**: La fitxa de Vehicle incorporarà l'historial del taller, les reparacions efectuades, els canvis d'oli pautats, l'estat de la garantia oficial de la marca i fluxos operatius per derivar el vehicle a grua si cal.
- **FR-012 (Carnets per Vehicles)**: Es definirà taxonòmicament el tipus de permís de conducció exigit (B, C, C1+E, etc.) per cada recurs mòbil i es bloquejarà qualsevol assignació d'operari l'expedient del qual no satisfaci aquest requisit.
- **FR-013 (Facturació Validada)**: Tot procés de facturació exigirà el pas previ i ineludible de revisió i validació del full de la tasca, el pressupost vinculat i les incidències ocorregudes (generant un pre-albarà). El sistema denegarà taxativament la producció d'una factura final directament a partir de dades automàtiques omeses de supervisió humana. Es permetrà l'emissió de factures rectificatives.
- **FR-014 (Seguiment Tresoreria)**: El panell de comptabilitat registrarà i destacarà gràficament l'estat de factures vençudes o impagades, per permetre a Secretaria o Direcció exercir les accions de pagament o reclamació necessàries.
- **FR-015 (Edició GIS per Capes i Traçabilitat)**: L'edició de qualsevol plànol de la base documental es realitzarà sota una metodologia no destructiva: totes les anotacions (fletxes, línies, formes geomètriques) s'emmagatzemaran en una nova capa abstracta separada. Aquesta nova capa anirà lligada a la fulla de tasca corresponent per garantir-ne la traçabilitat absoluta, deixant sempre el fitxer original font incorrupte.
- **FR-016 (IA Copilot i Notificacions Clients)**: S'integrarà l'accés al Copilot IA (basat en el RAG global de l'empresa). El supervisor de gestió tindrà una acció ràpida a les ordres de treball per notificar l'estat o una incidència directament al client a través d'una alerta de Telegram.
- **FR-017 (Barema de Preus dins Configuració Empresa)**: Un catàleg de preus unitaris (mà d'obra per hora, desplaçament, materials comuns) haurà d'estar disponible i gestionat pel rol de Boss directament des de la configuració de l'empresa.
- **FR-018 (KPIs de Gestió Operativa)**: El dashboard principal de la torre de control inclourà indicadors clau (KPIs) com ara: tasques actives, completades i endarrerides; operaris al camp; incidències obertes; estoc crític; vehicles amb alerta; i pressupostos pendents de confirmació.

## Success Criteria *(mandatory)*

- **SC-001 (Zero Data Entry onboarding)**: El 95% de les altes d'operaris i la introducció d'albarans de proveïdors es fan mitjançant la captura d'un arxiu físic usant la IA (OCR) estalviant més de 3 minuts per document introduït en comparació a la picada manual.
- **SC-002 (Fiabilitat Documental As-Built)**: El 100% de les edicions de mapes generen noves capes de contingut sense perdre mai un sol fitxer original aportat pel client o l'arquitectura.
- **SC-003 (Eficàcia Econòmica i Control)**: Reducció de les incidències d'estoc trencades a prop del 0% amb la presentació de l'esborrany pre-email de trencament d'estoc per al proveïdor. Traçabilitat 100% d'hores i ubicacions de la plantilla.

## Assumptions

- No s'enviaran emails automàtics a proveïdors, la responsabilitat darrera del reenviament cau en l'usuari (HITL).
- La validació final d'un pressupost per factura sempre la fa una persona (no màquines automatitzades).
- Es disposa de les fotocòpies de DNI reals necessaris i arxius autèntics per testejar els fluxes per la intolerància total a les dades sintètiques (faker).
