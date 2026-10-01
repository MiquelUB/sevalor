# Feature Specification: Frontline Operaris

**Feature Branch**: `02-frontline-operaris`
**Creat**: 2026-09-30
**Estat**: Draft

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Morning Briefing (Prioritat: P1)
Com a Operari de Camp, vull fer un 'Morning Briefing' seqüencial en iniciar el meu torn:
1. Fer login a la PWA amb el meu DNI i un PIN segur de 4 dígits (sense rebre cap SMS, el registre inicial el faig amb el meu DNI i un codi d'activació facilitat per l'empresa).
2. Si tinc un vehicle assignat, el sistema em demana una fotografia de l'odòmetre i completar un checklist visual del vehicle.
3. Si tinc una tasca assignada, el sistema em mostra un resum de la feina (adreça, client, materials necessaris).
4. Si la tasca requereix material, el sistema em guia per fer un picking (Pick In) des del magatzem.
**Test Independent**: Registre inicial amb DNI i codi d'activació, i posterior login diari amb DNI + PIN. Completar tot el flux seqüencial del 'Morning Briefing' (odòmetre, checklist, resum de tasca i picking guiats).

### User Story 2 - Execució de Feines amb Control de Qualitat 3-Fases (Prioritat: P1)
Com a Cap de Colla, vull visualitzar les tasques assignades, desplaçar-me a l'adreça, marcar l'arribada i, durant l'execució de la feina, aportar de manera ineludible 3 fotografies de qualitat (Abans, Durant, Després) directament des de la càmera. El tancament de la feina es bloqueja si falten les 3 fotos obligatòries.
**Test Independent**: Execució completa d'una feina capturant i enviant les 3 fotografies obligatòries durant la tasca (bloqueig del tancament si en falta alguna).

### User Story 3 - Evening Checkout (Prioritat: P1)
Com a Operari, vull fer un tancament de jornada ('Evening Checkout') guiat al final del dia:
1. Fer un Pick Out dels materials no consumits cap al magatzem.
2. Capturar una fotografia final de l'odòmetre del vehicle.
3. Revisar un resum dels tiquets de despesa del dia i confirmar la custòdia dels papers físics.
4. Fer el fitxatge de sortida registrant automàticament les meves coordenades GPS.
**Test Independent**: Executar el flux 'Evening Checkout' completant el Pick Out, la foto final de l'odòmetre, la validació de tiquets i fitxar la sortida amb coordenades capturades correctament.

### User Story 4 - Resolució d'Incidències "Cicle Vermell-Verd" (Prioritat: P2)
Com a Operari, vull obrir una incidència al camp aportant fotografies o notes de veu per informar d'un bloqueig (Estat Vermell), i posteriorment rebre instruccions o tancar-la en verd (Estat Verd).
**Test Independent**: Creació d'incidència amb àudio (i la seva transcripció automàtica), resolució i canvi d'estat a verd.

### User Story 5 - Gestió i Custòdia de Tiquets de Despesa (Prioritat: P3)
Com a Operari, vull fer una fotografia ràpida als tiquets de gasolinera o peatge i categoritzar-los sense picar text. Si superen els 100€ s'han de marcar per aprovació. Durant l'Evening Checkout faré la confirmació de la custòdia del paper.
**Test Independent**: Registre d'un tiquet de 120€, verificació que s'aixeca el flag (Limit Flag) i confirmació de la custòdia a final de jornada.

### User Story 6 - Edició de Plànols As-Built (GIS) i Exportació a Incidències (Prioritat: P3)
Com a Cap de Colla, vull obrir el plànol de la xarxa, veure la meva posició GPS, i dibuixar línies de colors sobre la canonada real que acabo d'instal·lar per desar-ho en una nova capa sense modificar el plànol base. També vull poder exportar aquesta vista del plànol amb anotacions com a imatge per adjuntar-la directament a una incidència oberta.
**Test Independent**: Obrir un plànol, dibuixar 2 canonades noves, confirmar que s'ha generat una Capa d'Anotació, i exportar-la com a imatge adjunta en una incidència oberta.

---

## Requirements *(mandatory)*

### Requisits Funcionals

- **FR-001 (Zero Mock Data)**: L'aplicació MOSTRARÀ pantalles buides honestes i guies d'acció quan no hi hagi dades assignades (dia 0), prohibint l'ús de dades de prova.
- **FR-002 (Accés Offline)**: El sistema PERMETRÀ el registre de jornada, lectura de plànols, captura de fotos, creació d'incidències i tiquets operant 100% fora de línia, sincronitzant-se quan hi hagi cobertura.
- **FR-003 (Autenticació DNI + Codi i PIN)**: El sistema OBLIGARÀ a fer un registre inicial del dispositiu amb el DNI i un codi d'activació facilitat per l'empresa (SENSE SMS). Posteriorment, només es demanarà el DNI i un PIN diari de 4 dígits (comprovat offline criptogràficament).
- **FR-004 (Control Horari Fefaent)**: El sistema OBLIGARÀ a capturar les coordenades GPS exactes i l'hora (UTC) tant a l'inici com al fitxatge de sortida (Evening Checkout).
- **FR-005 (Fotos Quality Assurance)**: El sistema OBLIGARÀ a prendre fotografies DURANT la tasca oberta (no en bloc al final). El tancament d'una feina es BLOQUEJARÀ si no s'han aportat les 3 fotografies obligatòries (Abans, Durant, Després).
- **FR-006 (Càmera Tècnica Directa)**: El sistema EXIGIRÀ la presa de fotografies directament des del component càmera del dispositiu, PROHIBINT pujar fotos prèvies des de la galeria per evitar fraus.
- **FR-007 (Georeferenciació Immediata)**: Tota fotografia, incidència o tiquet haurà de portar incrustada la dada de coordenades GPS inalterables.
- **FR-008 (Cicle d'Incidències)**: El sistema EMPRARÀ un model de semàfor: tota incidència neix bloquejant (Vermell) i ha de ser transicionada a resolt (Verd).
- **FR-009 (Tiquets Sense Text)**: El sistema ELIMINARÀ la necessitat de teclejar dades numèriques o text als tiquets al camp; només caldrà foto, categoria i un "check" de custòdia de paper a la tarda durant l'Evening Checkout.
- **FR-010 (Edició de Plànols No Destructiva)**: El sistema EMMAGATZEMARÀ qualsevol marca feta sobre un plànol com una capa abstracta aïllada, lligada a la fulla de tasca, deixant l'arxiu PDF original incorrupte.
- **FR-011 (Llanterna Integrada)**: El sistema DISPOSARÀ d'un botó per activar el flash/llanterna contínuament mentre es miren plànols o es capturen dades en entorns foscos.
- **FR-012 (Compressió Intel·ligent)**: El sistema COMPRIMIRÀ les fotografies al client a menys d'1 MB mantenint la definició visual per llegir matrius i números de sèrie.
- **FR-013 (Transcripció de Veu Automàtica)**: El sistema TRANSCRIURÀ automàticament les notes de veu gravades per l'operari i les enviarà juntament amb la imatge a l'oficina tècnica quan es creïn incidències o s'afegeixin notes.
- **FR-014 (Exportar Plànol Anotat a Incidència)**: El sistema PERMETRÀ exportar la vista del plànol amb les anotacions com a imatge i adjuntar-la directament a una incidència oberta des de la mateixa eina de plànols.

---

## Success Criteria *(mandatory)*

- **SC-001 (Autenticació Sense Friccions)**: Els tècnics poden desbloquejar la PWA i començar el Morning Briefing de tasques en menys de 5 segons.
- **SC-002 (Tolerància Offline Total)**: El 100% de les operacions de camp es mantenen funcionals en mode "Avió" o sense cobertura de xarxa cel·lular.
- **SC-003 (Compliance QA)**: El 100% de les feines finalitzades contenen les 3 fotografies pericials fetes durant la feina, prevenint reclamacions posteriors.
- **SC-004 (Sense Fotos Orfes)**: Es garanteix un 0% de fotografies no lligades a una entitat (feina, incidència o vehicle) al moment de tancar la jornada.
- **SC-005 (Tancament de Jornada Integral)**: El 100% dels operaris finalitzen la jornada complint l'Evening Checkout amb coordenades GPS i balanç de materials.
