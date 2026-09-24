# Pla d'Implementació SEVALOR V2: Agent IA & PWA Multimodal

Aquest document detalla l'execució pas a pas de les funcionalitats mancants per aconseguir la visió del "Sevalor AI Agent (P0)". Cada tasca i fase conté el seu propi Test d'Aprovació (Acceptance Criteria) que s'haurà de superar abans de continuar.

---

## FASE 1: Agent d'Escriptura (Tool Execution & Confirmacions)
Dotar el Copilot (que actualment només llegeix) de l'habilitat per executar accions operatives a la base de dades sota estricta confirmació humana.

### Tasca 1.1: Desenvolupament de Tools de Modificació (Backend)
Crear les `TOOLS_SCHEMA` i funcions d'execució asíncrones per a:
- Re-planificar una Ordre de Treball (canviar tècnic o data).
- Tancar/Facturar una feina.
- Reservar material del magatzem.
* **Test d'aprovació 1.1:** Les eines estan registrades al `copilot.py` de FastAPI i poden ser cridades internament generant logs sense errors de sintaxi o dependències.

### Tasca 1.2: Flux "Proposta -> Confirmació -> Acció" (Frontend Gestió)
Adaptar el `CopilotWidget` de React perquè, quan el model vulgui executar una Tool destructiva, renderitzi una targeta interactiva (generació d'UI) demanant l'OK a l'usuari ("El model suggereix reassignar l'OT-14 al tècnic Marc. Aproves?").
* **Test d'aprovació 1.2:** En fer clic a "Aprovar" a la UI, la petició viatja al backend amb un `execution_token` i la base de dades s'actualitza realment.

**✅ TEST D'APROVACIÓ DE LA FASE 1:** 
Demanar per xat al Copilot de Gestió: "Assigna la feina d'avaries de la Finca Nord al tècnic més proper". L'agent localitzarà el tècnic (Haversine), prepararà la Tool de re-agendament, la UI mostrarà el botó de confirmació, l'usuari farà clic i la base de dades (PostgreSQL) quedarà actualitzada sense usar *mock data*.

---

## FASE 2: IA Multimodal & Inclusió a la PWA (Operaris)
Portar l'Agent a la trinxera. Integrar el Copilot a la interfície mòbil dels tècnics i donar-li capacitat visual (reconeixement d'equips).

### Tasca 2.1: Injecció del Copilot a la PWA Mòbil
Afegir un accés directe o botó flotant optimitzat per a mòbils al fitxer `pwa/src/app/operari/layout.tsx`.
* **Test d'aprovació 2.1:** L'operari autenticat veu la icona del Copilot. En prémer, s'obre un xat a pantalla completa (Full-sheet) responsiu que no trenca la navegació Bottom Bar.

### Tasca 2.2: Endpoint Multimodal per Imatges (Backend)
Ampliar la ruta `/gestio/copilot/xat` per acceptar fragments d'imatges codificades en Base64 o *multipart/form-data* per passar-les a l'LLM local (Appliance).
* **Test d'aprovació 2.2:** Un script Python de test (via CURL o Requests) pot enviar una imatge d'una etiqueta i rebre la transcripció o identificació del model de màquina per part del servidor.

### Tasca 2.3: Interfície de Càmera al Copilot Widget (Frontend PWA)
Afegir un botó "Fer Foto" a l'input del xat del Copilot que activi la càmera del mòbil (`<input type="file" accept="image/*" capture="environment">`).
* **Test d'aprovació 2.3:** Des d'un dispositiu mòbil (o simulador), l'operari pot adjuntar la imatge directament dins la bombolla del xat de la PWA.

**✅ TEST D'APROVACIÓ DE LA FASE 2:** 
L'operari entra a la PWA, obre el Copilot, fa una foto a una placa de característiques d'una caldera. L'agent llegeix la imatge, extreu que és el model "BaxiRoca X100" i busca al RAG Documental, retornant a l'operari l'enllaç del manual de reparació.

---

## FASE 3: Mòdul Econòmic i Detector de Diners (Fitxa 360)
Tancar el cicle creuant l'operació tècnica amb els costos i habilitar l'Agent per auditar forats de facturació.

### Tasca 3.1: Càlcul de Marge a la Fitxa 360 (Backend & Frontend)
Afegir l'agrupació de costos (Hores + Material + Desplaçament) respecte a l'Ingrés de cada Ordre de Treball, per mostrar el "Marge Real" al panell `/gestio/clients/{id}/fitxa360`.
* **Test d'aprovació 3.1:** El Dashboard del client mostra els indicadors financers generats purament des de consultes (SQL) reals, complint l'exigència de Zero Mock Data.

### Tasca 3.2: Tool Agent - Diners No Facturats
Crear una Tool per a l'Agent (`get_unbilled_money`) que llegeixi treballs tancats sense factura vinculada, o materials utilitzats però no carregats al pressupost base.
* **Test d'aprovació 3.2:** La Tool retorna un JSON amb el sumatori exacte del diner que s'està perdent en un mes concret.

**✅ TEST D'APROVACIÓ DE LA FASE 3:** 
Demanar a l'Agent: "Quant de diner estem perdent en material no facturat aquest mes?". L'IA ha de mostrar l'import amb els albarans relacionats extrets del motor SQL, demostrant una consciència econòmica total sobre l'empresa.

---

## 🚀 TEST D'APROVACIÓ FINAL DEL CONJUNT (END-TO-END)
Per declarar el desenvolupament totalment finalitzat amb èxit sota la metodologia Spec-Kit, s'ha de poder completar el següent flux (End-to-End) en un entorn integrat:

1. El Gestor (des de `/gestio`) obre la Torre de Control i el mapa en directe, veu incidències operatives. **(Passa la Validació HUD)**
2. Un Operari (des de la PWA `/operari`) fa una foto a una vàlvula trencada. L'Agent IA multimodal detecta el model i l'assisteix. L'Operari utilitza material de l'estoc predictiu del seu vehicle. **(Passa la Validació Multimodal i PWA)**
3. El Gestor, setmanes després, pregunta a l'Agent IA de Backoffice: *"Comprova si el treball d'aquella vàlvula està cobrat i com ha impactat el marge d'aquest client"*. 
4. L'Agent creua la Fitxa 360, el RAG de Dades Vives, i retorna el balanç total del treball, proposant de generar la factura. El Gestor aprova (**Proposta -> Confirmació**) i l'acció s'executa. **(Passa la Validació Agent + Financer)**.

Si aquest flux flueix sense mock data, complint RLS i els temps de càrrega, **el Sistema Operatiu Empresarial Sevalor V2 queda donat per vàlid i completat.**
