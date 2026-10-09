# Arquitectura Multi-Agent Especialitzada — Sevalor Suite

**Estat:** Document d'Especificació per a Implementació  
**Objectiu:** Disseny del sistema multi-agent (Hub & Spokes) per maximitzar la precisió, seguretat i velocitat de la IA local a Sevalor Suite.  
**Norma Suprema:** Zero Mock Data, Aïllament Multi-Tenant (RLS PostgreSQL), Human-in-the-Loop (HITL).

---

## 1. Visió General i Justificació Estratègica

Actualment, el copilot tècnic opera com una entitat unitària amb un conjunt ampli d'eines (*tools*) registrades al mateix esquema. Quan s'executa un model local (com `deepseek-coder-v2-lite-instruct` a LM Studio), exposar massa eines simultàniament degrada la precisió, augmenta el consum de memòria/context i pot induir al·lucinacions.

L'**Arquitectura Multi-Agent (Orchestrator-Workers)** segmenta les competències en **6 subagents d'alta especialització**, governats per un **Orquestrador Central (Copilot Dispatcher)**.

### Avantatges Competitius Clau
1. **Finestra de Context Reduïda (<2.000 tokens):** Cada subagent rep únicament el prompt de la seva disciplina i 2 o 3 eines concretes, garantint respostes en temps real i màxima precisió en el tool calling.
2. **Seguretat Blindada per Disseny (Zero-Trust & RBAC):** Les eines financeres (salari, marge brut, costos) només existeixen físicament al context del subagent auditor de Direcció (`BOSS`), impedint qualsevol fuita de dades a operaris o enginyers.
3. **Desacoblament Modular:** Permet millorar o retocar el comportament d'un domini (p. ex. gestió d'albarans OCR) sense cap risc de trencar la lògica de flotes o incidències.
4. **Human-in-the-Loop Estricte:** Els subagents preparen, redacten i calculen propostes estructurades; mai executen accions financeres o contractuals sense confirmació humana explícita.

---

## 2. Topologia del Sistema (Hub & Spokes)

```
                            [ Usuari / Xat / PWA / Telegram ]
                                           │
                         ┌─────────────────▼─────────────────┐
                         │       ORQUESTRADOR CENTRAL        │
                         │       (Copilot Dispatcher)        │
                         │  - Verificació de Rol (RBAC)      │
                         │  - Classificació d'Intenció       │
                         │  - Context RLS (:empresa_id)      │
                         └─────────────────┬─────────────────┘
         ┌───────────────┬─────────────────┼─────────────────┬───────────────┬───────────────┐
         ▼               ▼                 ▼                 ▼               ▼               ▼
   ┌───────────┐   ┌───────────┐     ┌───────────┐     ┌───────────┐   ┌───────────┐   ┌───────────┐
   │ Subagent  │   │ Subagent  │     │ Subagent  │     │ Subagent  │   │ Subagent  │   │ Subagent  │
   │  PERIT    │   │ MAGATZEM  │     │   FLOTA   │     │ AUDITORIA │   │    OCR    │   │ CONCIERGE │
   │  DE CAMP  │   │  I ESTOC  │     │  I RUTES  │     │ FINANCERA │   │  VISIÓ    │   │ TELEGRAM  │
   └───────────┘   └───────────┘     └───────────┘     └───────────┘   └───────────┘   └───────────┘
```

---

## 3. Catàleg dels 6 Subagents Especialitzats

### 3.1 Subagent Perit Tècnic de Camp (`subagent_peritatge_camp`)
* **Rols Autoritzats:** `OPERARI`, `CAP_DE_COLLA`, `ENGINYER`.
* **Missió:** Atendre incidències sobre el terreny en menys de 30 segons.
* **Entrades:** Notes de veu (Whisper INT8), fotografies d'avaries i ID de l'ordre de treball.
* **Eines (Tools) Assignades:**
  * `get_warranty_status(finca_id, client_id, numero_serie)`: Audita garanties oficials o de mà d'obra vigents (<90 dies).
  * `generar_memorandum_tecnic(transcripcio, foto, ordre_id)`: Genera dictamen pericial esborrany.
* **Sortida / Comportament:** Proposta de Memoràndum Tècnic classificant l'avaria com a "Extra Facturable" (imprevist) o "Cost No Imputable" (garantia interna). L'enginyer ho valida a 1 clic (HITL).

---

### 3.2 Subagent de Magatzem i Proveïment (`subagent_logistica_estoc`)
* **Rols Autoritzats:** `CAP_DE_MAGATZEM`, `ENGINYER`, `SECRETARIA`, `BOSS`.
* **Missió:** Garantir que cap colla surti sense material i evitar trencaments d'estoc.
* **Eines (Tools) Assignades:**
  * `get_real_stock(article_ref)`: Consulta quantitat física disponible vs. virtual reservada.
  * `check_allocation_safety(ordre_id, materials_list)`: Comprova si una assignació reduirà el saldo sota el mínim.
  * `propose_purchase_order(article_id, quantitat)`: Prepara comanda al proveïdor habitual a preu pactat.
* **Sortida / Comportament:** Diagnòstic d'existències en temps real i bloqueig preventiu de picking si es detecta manca de material crític.

---

### 3.3 Subagent de Flota i Desplaçaments (`subagent_flota_despatx`)
* **Rols Autoritzats:** `SECRETARIA`, `ENGINYER`, `BOSS`.
* **Missió:** Optimització geogràfica de recursos mòbils i control legal dels vehicles.
* **Eines (Tools) Assignades:**
  * `get_closest_vehicle(lat, lng)`: Càlcul Haversine en temps real per posicionar la furgoneta més propera a una urgència.
  * `get_vehicle_info(matricula)`: Fitxa tècnica, consum mitjà, odòmetre i càrrega permesa.
  * `audit_itv_insurance_fleet()`: Alertes preventives de caducitat d'ITV o pòlisses d'assegurança.
* **Sortida / Comportament:** Assignació de ruta òptima i avís automàtic de venciments de manteniment preventiu.

---

### 3.4 Subagent Auditor Financer i Post-Obra (`subagent_auditoria_marge`)
* **Rols Autoritzats:** `BOSS` exclusivament (amb veto estricte a altres rols segons RF-20.1).
* **Missió:** Protegir la rendibilitat i el marge comercial de cada projecte.
* **Eines (Tools) Assignades:**
  * `get_unbilled_money(mes)`: Identifica material consumit i hores d'obra tancades que encara no s'han facturat.
  * `reconcile_post_obra(ordre_id)`: Comparativa "Previst vs. Real" de costos de mà d'obra, materials i carburant.
  * `detect_margin_leak(ordre_id)`: Alerta de merma operativa (>250% del consum previst).
* **Sortida / Comportament:** Esborrany de pre-facturació corregit amb desviacions econòmiques desglossades abans d'emetre la factura oficial Veri*factu.

---

### 3.5 Subagent de Digitalització OCR "Zero Data Entry" (`subagent_ocr_vision`)
* **Rols Autoritzats:** Tots els rols d'administració i camp.
* **Missió:** Transformar documents físics en dades estructurades a la base de dades sense picar res a mà.
* **Eines (Tools) Assignades:**
  * `extract_albara_lines(file_bytes)`: Reconeixement de capçalera, NIF proveïdor i graella de partides.
  * `extract_vehicle_tech_card(file_bytes)`: Extracció de matrícula, bastidor (VIN) i característiques tècniques.
  * `extract_fuel_receipt(file_bytes)`: Extracció de litres, import total i estació de servei.
* **Sortida / Comportament:** Formulari preomplert llest per a validació humana en 1 sol clic, amb comprovació de variacions de preu de compra respecte a l'històric.

---

### 3.6 Subagent Concierge de Clients (`subagent_client_telegram`)
* **Rols Autoritzats:** Clients finals autenticats via token efímer a Telegram.
* **Missió:** Comunicació asíncrona, segura i sense fricció amb el client de la finca o habitatge.
* **Eines (Tools) Assignades:**
  * `notify_technician_arrival(ot_id)`: Avisar d'arribada de l'equip a la finca.
  * `send_interactive_budget(extra_id)`: Enviament de pressupost d'imprevist amb botonera [Acceptar / Rebutjar].
  * `receive_client_media(file_id)`: Emmagatzematge sobirà de fotos d'avaria enviades pel client.
* **Sortida / Comportament:** Aprovació instantània d'extres en temps real amb registre immutable d'auditoria. Aïllament total respecte a dades internes de l'empresa.

---

## 4. Matriu de Rols i Eines per Subagent

| Subagent | Rol d'Usuari | Eines Principals | Font de Dades |
| :--- | :--- | :--- | :--- |
| **Peritatge de Camp** | `OPERARI`, `CAP_DE_COLLA`, `ENGINYER` | `get_warranty_status`, `generar_memorandum_tecnic` | Postgres + Whisper |
| **Magatzem i Estoc** | `CAP_DE_MAGATZEM`, `ENGINYER`, `SECRETARIA`, `BOSS` | `get_real_stock`, `check_allocation_safety` | `estocs_magatzem`, `articles` |
| **Flota i Rutes** | `SECRETARIA`, `ENGINYER`, `BOSS` | `get_closest_vehicle`, `get_vehicle_info` | `vehicles`, `ordres_treball` |
| **Auditoria Financer** | `BOSS` | `get_unbilled_money`, `reconcile_post_obra` | `factures`, `ordres_treball`, `linies_picking` |
| **OCR i Digitalització** | TOTS | `extract_albara_lines`, `extract_fuel_receipt` | Magatzem / Flota / Proveïdors |
| **Concierge Telegram** | `CLIENT_FINAL` | `send_interactive_budget`, `receive_client_media` | Bot Telegram (Aiogram) |

---

## 5. Full de Ruta d'Implantació Tècnica

1. **Fase 1 — Encaminador d'Intencions (Dispatcher):**
   * Crear la funció de routing que avalua el text de l'usuari i selecciona el subagent òptim.
   * Aplicar la barrera de veto de rol abans d'instanciar el subagent.

2. **Fase 2 — Modularització de Prompts i Schemas:**
   * Dividir `TOOLS_SCHEMA` en mini-esquemes aïllats per cada subagent.
   * Assignar a cada subagent un System Prompt concís (<150 paraules) amb l'ADN de la vertical.

3. **Fase 3 — Integració amb LM Studio i Fallback Sobirà:**
   * Les crides a `http://127.0.0.1:1234/v1` s'executen amb el mini-esquema del subagent seleccionat.
   * Si la IA local no crida eina de forma nativa, el subagent executa la lògica determinista de PostgreSQL sense al·lucinacions.

4. **Fase 4 — Mètriques i Telemetria d'Inferència:**
   * Registrar a `consultes_xat_copilot` el camp `subagent_utilitzat`, la latència d'execució i l'eina invocada per a auditoria completa del sistema.
