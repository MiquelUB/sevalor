# Feature Specification: Sevalor V2 - High Level Definition

**Feature Branch**: `main`

**Created**: 2026-09-24

**Status**: Draft

**Input**: User description: "Sevalor V2 High Level Definition with Fitxa360, Operational Dashboard HUD, Copilot AI RAG, Zero Mock Data, and RLS Multi-tenant improvements."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Torre de Control (Gestió) (Priority: P1)

Com a gestor (Backoffice), vull veure un "Dashboard HUD" complet només entrar a `/gestio`, amb indicadors clau (Alertes, Operaris Actius, Feines Obertes) i un mapa en temps real de les incidències.

**Why this priority**: És el centre neuràlgic de l'aplicació per a l'equip d'oficina.
**Independent Test**: Pot ser validat obrint la ruta `/gestio` i comprovant que cap de les dades mostra *mocks* i totes s'obtenen via API, i que el mapa incrustat es renderitza bé.

**Acceptance Scenarios**:
1. **Given** un gestor autenticat, **When** obre el Dashboard, **Then** veu el resum de KPIs sense dades *hardcoded*.

---

### User Story 2 - Digital Twin / Fitxa 360 (Priority: P1)

Com a gestor, quan consulto un Client, vull veure la seva Fitxa 360 viva (Digital Twin), que engloba les seves Instal·lacions (Finques), Actius i Peces, Històric d'Intervencions (OTs) i Incidències.

**Why this priority**: Aquest és el "Pilar 1" de les millores, converteix el programari d'un simple CRM a un Digital Twin.
**Independent Test**: Visitar `/gestio/clients`, obrir el detall d'un client i comprovar que hi ha informació real (Rao Social) + els blocs de Finques, Actius, OTs i Incidències del client, agafades de l'endpoint `/fitxa360`.

**Acceptance Scenarios**:
1. **Given** la llista de clients, **When** selecciono un client, **Then** el panell lateral mostra la Fitxa 360 completa i viva.

---

### User Story 3 - Copilot IA Integrat (Priority: P2)

Com a usuari (Gestor o Operari), vull poder consultar l'Agent IA Copilot mitjançant xat, demanant informació sobre stock o diagnòstics.

**Why this priority**: L'IA (RAG/Agent) agilitza processos complexos i consulta de la base de coneixement i stock.
**Independent Test**: Realitzar una petició al Copilot preguntant "Quin stock tenim de bombes d'aigua?" i rebre una resposta raonada des de l'API.

**Acceptance Scenarios**:
1. **Given** la interfície de Copilot oberta, **When** li faig una pregunta, **Then** busca la resposta usant RAG sense al·lucinar, amb fonts reals.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST strictly operate with Zero Mock Data.
- **FR-002**: System MUST render all user interfaces primarily in Catalan.
- **FR-003**: System MUST isolate all customer data using Row Level Security (RLS) over PostgreSQL.
- **FR-004**: System MUST offer a PWA (Progressive Web App) for Operaris (field workers) that works efficiently.
- **FR-005**: System MUST run intensive background processes asynchronously via Celery (no blocking web requests).

### Key Entities

- **Client**: Entitat principal, conté informació fiscal.
- **Finca (Instal·lació)**: Pertany a un client, és on es fan les feines.
- **Ordre de Treball (OT / Feina)**: Assignada a un operari, feta en una finca.
- **Incidència**: Report d'un problema vinculat a un equip (Actiu) d'una finca.
- **Article / Producte**: Material del magatzem usat a les feines.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% de les pantalles obtenen dades reals del backend (0 mocks).
- **SC-002**: El temps de càrrega del Dashboard (Torre de Control) i la Fitxa 360 no supera els 2 segons de mitjana.
- **SC-003**: No existeixen rutes on es filtri informació d'un Tenant (RLS) cap a un altre.

## Assumptions

- Es compta amb l'arquitectura prèviament establerta (FastAPI, Next.js, Redis, Celery).
- Els models i models de la base de dades suporten completament la visió 360 i el Tenant ID.


### User Story 4 - Agent IA Operatiu (Tools & Live Data) (Priority: P0)

Com a gestor, vull que el Copilot IA no sigui només un chatbot, sinó un "Agent" que tingui accés a eines (Tools/Funcions) per consultar dades en temps real (API/SQL) sobre agenda, operaris, stock i economia. Vull que l'agent pugui creuar dades, raonar i executar accions (prèvia confirmació).

**Why this priority**: L'agent operatiu és el nucli intel·ligent (P0) que diferencia Sevalor.
**Independent Test**: Demanar a l'agent "Qui és el millor tècnic per a l'avaria X?" i que aquest creui ubicación, disponibilitat i SLA, proposant una assignació accionable.

**Acceptance Scenarios**:
1. **Given** un usuari xatejant, **When** fa una pregunta operativa complexa (ex: "Quants treballs acabats no s'han facturat?"), **Then** l'agent utilitza la Tool corresponent de dades vives i retorna l'anàlisi exacte.

---

### User Story 5 - IA Multimodal (Priority: P1)

Com a operari al camp, vull poder fer una fotografia a la placa de característiques d'una màquina (chiller, UTA) perquè l'IA multimodal n'identifiqui el model exacte i m'ofereixi automàticament els manuals o protocols de manteniment relacionats des del RAG documental.

**Why this priority**: Redueix dràsticament el temps d'identificació i cerca de manuals en intervencions sobre el terreny.
**Independent Test**: Pujar una imatge d'una etiqueta, verificar que l'IA extreu el model i fa una cerca semàntica correcta al RAG.

**Acceptance Scenarios**:
1. **Given** una avaria, **When** l'operari puja la foto de la màquina al xat, **Then** l'agent reconeix la màquina i enllaça el manual tècnic.

---

### User Story 6 - Stock Intel·ligent Predictiu (Priority: P1)

Com a responsable de magatzem, vull que el sistema creui els pròxims treballs programats amb els materials necessaris, el stock del magatzem i el stock als vehicles dels operaris, generant alertes predictives si faltarà material.

**Why this priority**: Evita que els operaris arribin a la finca sense el material necessari.

### Functional Requirements (Ampliats)

- **FR-006**: L'Agent IA MUST suportar **RAG Híbrid**: Documental (protocols, manuals via RAG) i Dades Vives (SQL/API via Tools) de manera transparent per a l'usuari.
- **FR-007**: El sistema MUST tenir capacitat **Multimodal** per processar imatges de plaques i avaries (OCR i anàlisi visual).
- **FR-008**: Totes les accions destructives o que canviïn dades operatives generades per l'Agent (assignar, tancar feina, moure stock) MUST requerir un pas explícit de confirmació humana (`PROPUESTA -> CONFIRMACIÓN -> ACCIÓN`).
- **FR-009**: L'Agent IA MUST executar-se de manera local (Appliance Local 32GB/64GB) per garantir la sobirania absoluta de les dades del client.
