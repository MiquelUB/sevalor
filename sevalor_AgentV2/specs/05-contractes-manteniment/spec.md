# Feature Specification: Contractes de Manteniment Recurrent

**Feature Branch**: `05-contractes-manteniment`
**Creat**: 2026-09-30
**Estat**: Draft

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Alta i Gestió de Contractes de Manteniment (Prioritat: P1)
Com a Boss o Enginyer, vull crear contractes de manteniment anuals per a un client i una o més finques, definint la periodicitat de les revisions (mensual, trimestral, semestral, anual), el preu pactat i els serveis inclosos, per tal de generar ingressos recurrents predictibles i garantir el compliment de les revisions obligatòries.
**Test Independent**: Crear un contracte de manteniment de climatització per a un client amb revisió trimestral. Verificar que es generen automàticament les 4 ordres de treball preventives al calendari.

### User Story 2 - Generació Automàtica d'Ordres de Treball Preventives (Prioritat: P1)
Com a Enginyer, vull que el sistema generi automàticament les ordres de treball de manteniment preventiu segons el calendari pactat al contracte, per tal que les colles sempre tinguin visibilitat de les revisions que s'apropen sense que ningú les hagi de crear manualment.
**Test Independent**: Avançar la data del sistema al dia de la revisió trimestral i verificar que l'OT apareix a la llista de tasques planificades amb el client, finca i materials associats.

### User Story 3 - Alertes de Revisions Imminents i Vençudes (Prioritat: P2)
Com a Enginyer o Secretaria, vull rebre alertes quan una revisió obligatòria s'apropa (15 dies, 5 dies, 1 dia) o quan ja ha vençut sense executar-se, per evitar incompliments contractuals i legals.
**Test Independent**: Simular un contracte amb una revisió vençuda fa 3 dies i verificar que l'alerta és visible al dashboard.

### User Story 4 - Renovació i Baixa de Contractes (Prioritat: P2)
Com a Boss o Secretaria, vull poder renovar tàcitament un contracte (amb actualització de preu si cal) o donar-lo de baixa amb un motiu registrat, per mantenir un historial complet del cicle de vida comercial amb cada client.
**Test Independent**: Renovar un contracte amb un increment del 3% de preu. Verificar que les noves OT preventives es regeneren amb la nova tarifa.

### User Story 5 - Dashboard de Contractes i Facturació Recurrent (Prioritat: P2)
Com a Boss, vull veure un panell amb tots els contractes actius, els pròxims a vèncer, els ingressos recurrents mensuals (MRR) i la facturació acumulada per contracte, per tal de conèixer la salut del negoci recurrent d'un cop d'ull.
**Test Independent**: Verificar que la xifra de MRR al dashboard coincideix amb la suma dels contractes actius dividida per 12.

---

## Requirements *(mandatory)*

### Requisits Funcionals

- **FR-001 (Alta de Contracte)**: El sistema PERMETRÀ crear un contracte de manteniment vinculat a un client, una o més finques, amb periodicitat configurable (mensual, bimensual, trimestral, semestral, anual), preu anual pactat, serveis inclosos i data d'inici/fi.
- **FR-002 (Generació Automàtica d'OT)**: El sistema GENERARÀ automàticament ordres de treball preventives segons el calendari del contracte, assignant-les com a planificades amb la descripció, materials habituals i finca corresponent.
- **FR-003 (Alertes de Venciment)**: El sistema EMETRÀ alertes visuals al dashboard a 15, 5 i 1 dia d'una revisió planificada, i alertes vermelles si la revisió ha vençut sense executar-se.
- **FR-004 (Renovació Tàcita)**: El sistema PERMETRÀ renovar un contracte amb un sol clic, amb opció d'ajustar el preu (% d'increment o nou import), regenerant les OT preventives del nou període.
- **FR-005 (Baixa de Contracte)**: El sistema REGISTRARÀ la baixa d'un contracte amb data efectiva, motiu (finalització natural, insatisfacció, impagament, canvi de proveïdor) i conservarà l'historial complet.
- **FR-006 (MRR i Dashboard)**: El sistema CALCULARÀ els Ingressos Recurrents Mensuals (MRR) com la suma dels contractes actius / 12 i els mostrarà al dashboard Economics del Boss.
- **FR-007 (Facturació Recurrent)**: El sistema PERMETRÀ generar factures periòdiques (mensuals, trimestrals o anuals) vinculades al contracte, seguint el flux estàndard de pre-factura → validació humana → factura Veri*factu.
- **FR-008 (Historial per Finca)**: El sistema VINCULARÀ cada revisió preventiva executada a la fitxa de la finca, permetent consultar l'historial complet de manteniments des de la Fitxa 360° del Client.
- **FR-009 (Zero Mock Data)**: En absència de contractes, el sistema mostrarà una pantalla buida amb guia d'acció per crear el primer contracte.

---

## Success Criteria *(mandatory)*

- **SC-001 (Automatització Preventiva)**: El 100% de les revisions contractuals generen la seva OT automàticament sense intervenció manual.
- **SC-002 (Zero Revisions Oblidades)**: Cap revisió planificada queda sense executar-se sense haver generat almenys una alerta visible al dashboard.
- **SC-003 (Predicibilitat Financera)**: El Boss pot consultar en tot moment la xifra de MRR i la previsió d'ingressos recurrents a 30/60/90 dies.

---

## Assumptions

- Un contracte pot cobrir múltiples finques del mateix client.
- La periodicitat més freqüent és trimestral (climatització) i anual (calefacció/calderes).
- La facturació dels contractes segueix el mateix flux HITL que qualsevol altra factura (pre-factura → validació → Veri*factu).
- El Copilot podrà alertar proactivament al Boss sobre contractes amb baixa rendibilitat o renovacions imminents.
