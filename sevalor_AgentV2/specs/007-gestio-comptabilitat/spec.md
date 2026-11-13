# Spec 007 — Mòdul de Comptabilitat, Facturació, Tresoreria i Suite de Control Financer (`/gestio/comptabilitat`) — v5.0

**AVÍS D'ALINEACIÓ CONSTITUCIONAL I INTEGRACIÓ ARQUITECTÒNICA:** Aquesta especificació tècnica es regeix de forma innegociable pels principis de la **Constitució de CampoPro / Sevalor Suite (v4.0)** i s'integra de forma transversal amb la Torre de Control Geogràfica (**Spec 001** i **Spec 005**), el Mòdul de Clients (**Spec 002**), el Mòdul de Proveïdors (**Spec 003**), el Mòdul de Magatzem (**Spec 004**), el Mòdul de Flota (**Spec 006**), el Mòdul d'Operaris (**Spec 008**), el Mòdul de Notificacions (**Spec 009**) i els Workers Asíncrons (**Spec 024**).

Es prohibeix taxativament l'ús de dades simulades o de prova (**Zero Mock Data**), partint d'un estat de "Dia 0" real i garantint de forma absoluta la sobirania de dades mitjançant l'emmagatzematge local/sobirà al servidor dedicat Hetzner a Falkenstein (Alemanya - UE) sota xifratge **AES-256-GCM**, descartant qualsevol núvol públic extern (com AWS S3).

---

## 1. Context i Objectiu Executiu

El mòdul `/gestio/comptabilitat` és el **Hub Operatiu Financer, Motor de Facturació Legal Veri*factu i Suite de Control Econòmic en Temps Real** de l'empresa. El seu objectiu és que el rol `BOSS` pugui respondre en menys de 10 segons a quatre preguntes crítiques amb dades 100% reals:
1. **Quant guanyem realment?** (Compte d'Explotació P&L en temps real, Marge Brut vs. Net, EBITDA i Punt d'Equilibri).
2. **On perdem marge o liquiditat oculta?** (Erosió de preus de proveïdors, Merma d'obra, Obra en Curs no facturada — *WIP*, Cost Hora Efectiu d'operaris indexat a improductivitat i Sinistralitat de contractes MRR).
3. **Quants diners tindrem al banc d'aquí a 30/60/90 dies?** (Predicció de *Burn Rate*, Guardacaixa Fiscal d'IVA Model 303, Retencions de garantia del $5\%$ i recuperació d'IVA d'incobrables segons Art. 80 LIVA).
4. **Quins clients representen un risc operatiu?** (Semàfor d'*Aging* connectat amb bloqueig preventiu d'Ordres de Treball i *Picking* de magatzem).

---

## 2. Usuaris / Actors i Matriu d'Accés (Resolució Oficial Conflicte C-05 Zero-Trust)

Totes les taules financeres apliquen `FORCE ROW LEVEL SECURITY` a PostgreSQL sota `app.current_empresa_id`. Per resoldre qualsevol contradicció entre pressupostació tècnica i confidencialitat financera:

| Rol | Accés a `/api/v1/gestio/comptabilitat/*` | Visibilitat de Costos i Dades Bancàries | Endpoints Tècnics Sanititzats (`/api/v1/gestio/operativa-financera/*`) |
| :--- | :--- | :--- | :--- |
| **BOSS** | Total (Lectura / Escriptura / Aprovació / Desbloqueig de Risc) | 100% visible: IBAN desxifrat, Nòmines d'alta direcció, Marges nets, EBITDA, Salari real operaris. | Accés complet. |
| **SECRETARIA** | Total Operatiu (Facturació, Conciliació CSB 43, Tiquets, Nòmines base) | IBAN i preus de compra visibles. Salaris d'alta direcció ofuscats (`***`). Sense permís per desbloquejar risc crític sense signatura `BOSS`. | Accés complet. |
| **ENGINYER** | **VETO TOTAL (`HTTP 403 Forbidden`)** | Bloqueig absolut a P&L, EBITDA, IBAN, SEPA, preus de cost de proveïdors (`preu_cost_ultim`, `preu_cost_mitja`) i salari real d'operaris. | Accés exclusiu a DTOs sanititzats: `FacturaConsultaTecnicaDTO`, `estat_risc_operatiu` (`APTE` / `BLOQUEJAT_RISC` sense imports) i `cost_hora_referencia` (tarifa teòrica estàndard per pressupostar obres). |
| **OPERARI** | **VETO TOTAL (`HTTP 403 Forbidden`)** | Zero accés financer d'oficina. | Només puja tiquets propis via `/api/v1/operari/tiquets` (Spec 018). |
| **SUPERADMIN** | **VETO TOTAL (`HTTP 403 Forbidden`)** | Blindatge constitucional (Spec 011 RF-22). | Cap accés a dades del tenant. |

---

## 3. Requisits Funcionals (Notació EARS Estricta)

### Bloc 1: Entorn de Gestió, Filtres, Segregació Zero-Trust i Fiscalitat Base
* **RF-01 (Ubiquitous):** EL SISTEMA presentarà a `/gestio/comptabilitat` un selector temporal global configurable (`MES_ACTUAL`, `TRIMESTRE_ACTUAL`, `YTD`, `EXERCICI_FISCAL` o rang personalitzat), actualitzant reactivament tots els KPIs, gràfiques i taules en menys de $200\text{ ms}$.
* **RF-02 (Event-driven):** QUAN l'usuari commuti entre el *Criteri de Meritació (Devengo)* i el *Criteri de Caixa Analític*, EL SISTEMA recalcularà en memòria els resultats analítics en base a `data_cobrament_real` i `data_pagament_real`, sense alterar els llibres oficials d'IVA ni modificar els assentaments del llibre diari, i controlarà separadament el RECC Passiu de proveïdors al compte transitori $4729$ fins al pagament efectiu.
* **RF-03 (Ubiquitous) — Disseny de Doble Nivell (Capçalera vs. Línies) per a Multiobra:**
  1. *Capçalera (`factures_capcalera`):* Centralitza el crèdit fiscal i deute comercial únic amb el client (compte $430$), bases, quotes d'IVA i estat de cobrament (`obra_id IS NULL`).
  2. *Línies (`factures_linies`):* Hereten obligatòriament `centre_de_cost_id`, `obra_id` i `cost_unitari_historic` congelat en el moment de l'albarà, imputant al grup $70$.
* **RF-04 (State-driven) — Zero Mock Data:** SI la base de dades conté $0$ registres financers en el període (Dia 0 real), LLAVORS EL SISTEMA retornarà estructures JSON vàlides amb tots els comptadors numèrics a $0.00\text{ EUR}$ i renderitzarà un *Empty State* real amb els botons d'acció habilitats, prohibint qualsevol dada fictícia o *hardcodejada*.
* **RF-05 (Ubiquitous):** EL BACKEND denegarà qualsevol petició dels rols `ENGINYER`, `OPERARI` o `SUPERADMIN` cap a `/api/v1/gestio/comptabilitat/*` responent amb `HTTP 403 Forbidden`.
* **RF-05.1 (Ubiquitous) — Inversió del Subjecte Passiu (ISP):** EL SISTEMA permetrà emetre factures sota règim ISP fixant la quota d'IVA al $0.00\%$ (`ISP_0%`) i estampant al PDF i XML la llegenda legal: *"Operació amb inversió del subjecte passiu d'acord amb l'art. 84.U.2n.f de la Llei 37/1992 de l'IVA"*.
* **RF-05.2 (Ubiquitous):** EL SISTEMA imputarà les retencions d'IRPF suportades de clients al compte d'actiu $473$, bloquejant escriptures al compte de passiu $4751$ (reservat a retencions practicades a treballadors i professionals proveïdors).
* **RF-05.3 (Ubiquitous):** EL SISTEMA calcularà el saldo deutor líquid exigible al compte $430$ (descomptant també qualsevol retenció per garantia d'obra del compte $4308$) mitjançant la fórmula exacta:
  $$\text{Líquid Exigible (430)} = \sum \text{Base}_i + \sum \text{IVA}_i + \sum \text{Suplerts (554)} - \text{Retenció IRPF (473)} - \text{Retenció Garantia (4308)}$$
* **RF-05.4 (Ubiquitous):** EL SISTEMA servirà les consultes tècniques d'albarans i estat de client per al rol `ENGINYER` a través de `/api/v1/gestio/operativa-financera/*` utilitzant `FacturaConsultaTecnicaDTO` i `ClientRiscSanititzatDTO`, purgant al $100\%$ IBAN, comptes PGC, preus de cost i saldos en euros.

### Bloc 2: Facturació Agrupada, Anticips, Suplerts i Veri*factu (AEAT)
* **RF-06 (Event-driven):** QUAN es generi una factura agrupada d'albarans multiobra, EL SISTEMA consolidarà totes les línies validades mantenint la traçabilitat `albara_origen_id` i `obra_id` a cada línia.
* **RF-07 (Ubiquitous):** EL SISTEMA aplicarà l'arrodoniment d'IVA amb `ROUND_HALF_UP` a 2 decimals sobre la suma de bases per tipus impositiu; si existeix discrepància de $\pm 0.01\text{ EUR}$ respecte a la suma d'IVAs línia a línia, regularitzarà el cèntim a la línia de major import.
* **RF-08 / RF-09 (Event-driven) — *Bucket Matching* d'Anticips:** QUAN es liquidi una obra amb factures d'anticip prèvies (compte $4380$), EL SISTEMA deduirà la base imposable de forma acotada per cada cub d'IVA ($10\%$ i $21\%$ separadament), impedint bases negatives.
* **RF-10 / RF-11 (State-driven) — Suplerts (Compte 554):** MENTRE una factura contingui línies de suplerts exempts d'IVA (taxes pagades en nom del client), EL SISTEMA bloquejarà l'emissió definitiva (`EMESA`) fins que s'adjunti el PDF del justificant oficial de pagament a nom del client.
* **RF-12 / RF-13 (Event-driven) — Encadenament Veri*factu:** QUAN s'emeti una factura definitiva, EL SISTEMA adquirirà un bloqueig pessimista (`SELECT FOR UPDATE`) sobre la sèrie fiscal del tenant, calcularà l'empremta `SHA-256` encadenada amb el `hash_factura_anterior`, generarà el codi QR tributari oficial amb ReportLab i desarà l'XML a la taula `outbox_enviaments_aeat`.
* **RF-14 / RF-15 (Event-driven) — Factures Rectificatives (Sèrie R):** QUAN s'emeti una factura rectificativa (Sèrie `R-YYYY-XXXX`), EL SISTEMA exigirà informar `factura_rectificada_id` i `motiu_rectificacio`, traslladant el saldo a retornar o compensar al subcompte $4309$.

### Bloc 3: Nòmines (Envelope Encryption), Tiquets OCR i Conciliació CSB 43
* **RF-16 / RF-17 (Event-driven):** QUAN s'ingereixi una remesa de nòmines en PDF, EL SISTEMA les xifrarà en repòs amb *Envelope Encryption* (`AES-256-GCM`) sota `/docs/<empresa_id>/nominas/`.
* **RF-18 / RF-19 (State-driven):** MENTRE l'usuari connectat sigui `SECRETARIA`, EL SISTEMA ofuscarà amb `***` els imports salarials d'usuaris marcats amb `es_alta_direccio = true`, generant una remesa SEPA Norma 34 bifurcada d'accés exclusiu per al `BOSS`, i validarà la quadratura de l'assentament de nòmines:
  $$\text{ Devengat } (640 + 642) = \text{SS Creditora } (476) + \text{IRPF } (4751) + \text{Remuneracions Pendents } (465) + \text{Bestretes } (460)$$
* **RF-20 (Event-driven):** QUAN un operari capturi un tiquet a la PWA i l'OCR detecti que manca el NIF corporatiu de l'empresa o del proveïdor (factura simplificada no deduïble, Art. 97 LIVA), EL SISTEMA fixarà `quota_iva = 0.00`, integrarà el total com a major cost a la subcompta $62\text{X}$ i marcarà el tiquet com a `PENDENT_BESCANVI`. Si `import_total > 100.00 EUR`, activarà `requereix_aprovacio_boss = true`.
* **RF-21 (State-driven):** Durant els últims 30 dies de l'exercici fiscal (desembre), EL SISTEMA mostrarà l'alerta de *Precancilleria Fiscal* sumant tots els tiquets en estat `PENDENT_BESCANVI` abans de commutar-los automàticament a `NO_DEDUIBLE_IS`.
* **RF-22 / RF-23 (Event-driven) — Conciliació Norma 43:** QUAN es pugi un fitxer CSB 43, EL SISTEMA generarà l'empremta única per moviment:
  $$\text{Hash Moviment} = \text{SHA-256}(\text{empresa\_id} \parallel \text{data\_operacio} \parallel \text{import} \parallel \text{divisa} \parallel \text{saldo\_resultant})$$
  rebutjant duplicats de forma idempotent, verificant la continuïtat del saldo inicial/final i executant el creuament proposat sota confirmació HITL de `SECRETARIA`.
* **RF-24 / RF-25 (Ubiquitous) — Registre Immutable SIF:** EL SISTEMA enregistrarà tots els esdeveniments crítics (`EV-01` a `EV-07`) a `registre_esdeveniments_sif` amb restricció estricta *Append-Only* a nivell de trigger PostgreSQL que impedeixi qualsevol `UPDATE` o `DELETE`.

### Bloc 4: Suite Econòmica — P&L en Temps Real, Marges de Producte i Tresoreria 30/60/90d
* **RF-26 (Ubiquitous) — Compte d'Explotació (P&L) i Break-Even en Temps Real:** EL SISTEMA calcularà en temps real per al període seleccionat:
  1. **Facturació Neta ($\text{FN}$):** $\sum \text{base\_imposable}$ de factures emeses menys rectificatives.
  2. **Cost Directe d'Obra ($\text{CDO}$):** $\text{Cost Materials Consumits (PMP històric + Mermes)} + \text{Cost Mà d'Obra Directa Imputada} + \text{Tiquets d'Obra i Desplaçaments}$.
  3. **Marge Brut Global ($\text{MB}$):** $\text{MB}_{\text{EUR}} = \text{FN} - \text{CDO}$ i $\text{MB}_{\%} = \left(\frac{\text{MB}_{\text{EUR}}}{\text{FN}}\right) \times 100$.
  4. **EBITDA Operatiu:** $\text{EBITDA}_{\text{EUR}} = \text{MB}_{\text{EUR}} - \sum \text{Despeses Fixes d'Estructura Devengades (`DespesaFixaRecurrent` prorratejada)}$.
  5. **Punt d'Equilibri Mensual (*Break-Even Point*):**
     $$\text{Facturació Break-Even} = \frac{\text{Despeses Fixes Mensuals Totals}}{\text{Ràtio de Marge Brut Mitjà } (\text{MB}_{\%} / 100)}$$
     indicant el dia exacte del mes en què la facturació acumulada supera el punt d'equilibri.
* **RF-27 (Ubiquitous) — Marge Brut vs. Marge Net de Productes i Alerta d'Erosió:** EL SISTEMA calcularà per a cada producte i família del catàleg:
  $$\text{Marge Brut Producte (\%)} = \frac{\text{preu\_venda\_tarifa} - \text{preu\_cost\_mitja}}{\text{preu\_venda\_tarifa}} \times 100$$
  $$\text{Marge Net Real Producte (EUR)} = \sum (\text{Imports Facturats amb Descompte}) - \sum (\text{Unitats Venudes} \times \text{cost\_unitari\_historic}) - \sum (\text{quantitat\_merma} \times \text{cost\_unitari\_historic})$$
* **RF-28 (Event-driven) — Detector d'Erosió de Marge per OCR:** QUAN s'ingereixi una factura o albarà de proveïdor on $\text{preu\_cost\_ultim} > \text{preu\_cost\_mitja}$ provocant que el marge teòric respecte a `preu_venda_tarifa` caigui per sota del llindar mínim configurat per la família (per defecte $25\%$), EL SISTEMA aixecarà una **Alerta d'Erosió de Marge** a `/gestio/comptabilitat` proposant l'actualització automàtica del PVP de tarifa.
* **RF-29 (Ubiquitous) — Rotació d'Estoc i Capital Immobilitzat:** EL SISTEMA calcularà el valor en euros ($\text{quantitat\_estoc} \times \text{preu\_cost\_mitja}$) dels materials al magatzem central i furgonetes que acumulin més de $90\text{ dies}$ sense cap moviment de sortida.
* **RF-30 (Ubiquitous) — Predicció de Tresoreria (30/60/90 dies), *Burn Rate* i Guardacaixa Fiscal (Model 303):** EL SISTEMA projectarà el saldo bancari futur a $30$, $60$ i $90\text{ dies}$ integrant:
  1. **Entrades Previstes:** Factures emeses pendents segons `data_venciment` (ajustades pel DSO històric del client si supera el venciment).
  2. **Sortides Previstes (*Burn Rate* Mensual):**
     $$\text{Burn Rate} = \sum \text{Despeses Fixes (`DespesaFixaRecurrent`)} + \sum \text{Nòmines i SS (`Usuari`)} + \sum \text{Rèntings (`Vehicle`)} + \sum \text{Venciments Proveïdors (`FacturaProveidor`)} + \text{Mitjana Mòbil 3 Mesos Tiquets Variables}$$
  3. **Guardacaixa Fiscal d'IVA (Reserva AEAT Model 303):**
     $$\text{Guardacaixa IVA} = \max\left(0, \sum \text{IVA Repercutit Devengat} - \sum \text{IVA Suportat Deduïble (Proveïdors + Tiquets amb NIF vàlid)}\right)$$
     descomptant aquest import del "Saldo Lliure Disponible" perquè el `BOSS` sàpiga quina part del saldo bancari pertany a l'AEAT.

### Bloc 5: Les 6 Millores Estratègiques d'Alt Impacte Operatiu i Financer
* **RF-31 (Ubiquitous) — Millora 1: Control i Valoració del WIP (*Work In Progress* — Obra en Curs no Facturada):** EL SISTEMA identificarà i valorarà econòmicament totes les Ordres de Treball (OT) en estat `EXECUTADA_PENDENT_VALIDACIO` o `ALBARA_SIGNAT` que no tinguin `factura_id` associada, calculant:
  $$\text{Valor WIP Valorat (PVP)} = \sum (\text{Hores Imputades} \times \text{Preu Venda Hora}) + \sum (\text{Materials Consumits} \times \text{PVP Aplicat})$$
  $$\text{Cost WIP Avançat per l'Empresa} = \sum (\text{Hores Imputades} \times \text{Cost Hora Efectiu}) + \sum (\text{Materials Consumits} \times \text{PMP}) + \sum \text{Tiquets OT}$$
* **RF-32 (State-driven) — Alerta de WIP Envellit:** SI una OT completada a camp o albarà tancat supera els $7\text{ dies}$ naturals sense haver estat facturat (`dies_en_wip > 7`), EL SISTEMA la destacarà en vermell a la safata de *Fuites de Caixa (WIP Envellit)* i permetrà convertir-la en pre-factura a 1 clic.
* **RF-33 (Event-driven) — Millora 2: Gestió Comptable i Venciments de Retencions per Garantia d'Obra ($5\%$):** QUAN s'emeti una factura a client amb retenció per garantia d'obra (habitualment el $5\%$ en obra civil/industrial) o es registri una factura de subcontracta amb retenció de salvaguarda (Spec 003 RF-16), EL SISTEMA registrarà un objecte a la taula `retencions_garantia`, imputarà l'import retingut al compte $4308$ (Clients, retencions per garantia) o $4008$ (Proveïdors, retencions per garantia), i **exclourà aquest import del saldo morós ordinari a l'Aging d'Impagats**.
* **RF-34 (State-driven) — Alerta Automàtica de Alliberament de Garantia (365 dies):** MENTRE existeixin registres a `retencions_garantia` en estat `RETINGUDA` i la seva `data_venciment_garantia` es trobi a menys de $15\text{ dies}$ de la data actual (o ja hagi vençut), EL SISTEMA executarà una tasca diària a Celery que generarà una alerta prioritària a Secretaria i pre-generarà la carta/factura d'exigibilitat d'alliberament de fiança.
* **RF-35 (Event-driven) — Millora 3: Semàfor de Risc de Crèdit Dinàmic amb Bloqueig Operatiu a Camp:** QUAN un client tingui qualsevol factura vençuda i impagada amb antiguitat $> 90\text{ dies}$ (tram `CRITIC_MES_90` de l'*Aging*, excloent retencions de garantia no vençudes) O el seu deute total pendent superi el seu `limit_risc_credit` configurat, EL SISTEMA commutarà automàticament el camp `estat_risc_operatiu` del client a `BLOQUEJAT_RISC`.
* **RF-36 (State-driven) — Bloqueig Transversal a Torre de Control (Spec 001) i Magatzem (Spec 004):** MENTRE un client es trobi en estat `BLOQUEJAT_RISC`, EL SISTEMA bloquejarà amb `HTTP 423 Locked` la creació de noves Ordres de Treball ordinàries i el *Picking* de sortida de material de magatzem per a aquest client, mostrant a l'`ENGINYER` la insígnia sanititzada `"BLOQUEJAT PER RISC ADMINISTRATIU"` sense revelar imports. Només el rol `BOSS` podrà executar un desbloqueig cautelar (`OVERRIDE_BOSS`) indicant un motiu justificat que quedarà segellat de forma immutable al `registre_esdeveniments_sif` (`EV-06`).
* **RF-37 (Event-driven) — Millora 4: Motor de Recuperació d'IVA d'Incobrables (Art. 80.Tres i Quatre LIVA):** QUAN una factura emesa en estat `IMPAGADA` o `PENDENT` compleixi exactament $180\text{ dies}$ ($6\text{ mesos}$) des de la seva `data_emissio` sense haver estat cobrada íntegrament, el worker diari de Celery canviarà el seu estat de seguiment fiscal a `FINESTRA_ART80_OBERTA`, calcularà la data límit improrrogable de $90\text{ dies}$ posteriors (`data_limit_art80 = data_emissio + 270 dies`), crearà una alerta crítica al Dashboard i pre-generarà l'esborrany de la **Factura Rectificativa per Crèdit Incobrable (Sèrie R)** per recuperar el $21\%$ d'IVA davant l'AEAT.
* **RF-38 (State-driven):** MENTRE una factura estigui en `FINESTRA_ART80_OBERTA`, EL SISTEMA exigirà adjuntar el document de reclamació judicial o requeriment notarial (`justificant_reclamacio_art80_path`) abans de consolidar l'emissió Veri*factu de la factura rectificativa d'incobrable.
* **RF-39 (Ubiquitous) — Millora 5: Cost Real per Hora d'Operari Dinàmic (Indexat a Improductivitat i Absentisme):** EL SISTEMA mantindrà dos indicadors de cost horari per operari estrictament diferenciats:
  1. `cost_hora_referencia` (Estàtic / Teòric): Visible per a l'`ENGINYER` en pressupostació tècnica, calculat sobre hores de conveni.
  2. `cost_hora_efectiu_mensual` (Dinàmic / Confidencial `BOSS` i `SECRETARIA`): Calculat en temps real dividint el cost laboral total del mes entre les hores **efectivament imputades i facturables en Ordres de Treball**:
     $$\text{Cost Hora Efectiu Mensual} = \frac{\text{salari\_mensual\_brut} + \text{cost\_ss\_mensual} + \sum \text{Dietes i Tiquets Operari}}{\sum \text{Hores Imputades a OTs Facturables en el Mes}}$$
     utilitzant aquest valor dinàmic per calcular el Marge Net Real de les obres al P&L.
* **RF-40 (Ubiquitous) — Ràtio d'Eficiència d'Operari i Cost de Flota per Km:** EL SISTEMA calcularà per a cada operari el seu $\text{Ràtio d'Eficiència (\%)} = \left(\frac{\text{Hores Imputades a OT}}{\text{Hores Fitxades en Jornada (`RegistreJornadaLaboral`)}}\right) \times 100$, i per a cada vehicle el seu cost real per quilòmetre:
  $$\text{Cost Flota (EUR/km)} = \frac{\text{quota\_renting\_mensual} + \text{Despeses Taller/ITV} + \sum \text{Tiquets Carburant}}{\text{Km Finals Odòmetre Mes} - \text{Km Inicials Odòmetre Mes}}$$
* **RF-41 (Ubiquitous) — Millora 6: Auditoria de Rendibilitat i Sinistralitat de Contractes de Manteniment (MRR):** EL SISTEMA gestionarà la taula `contractes_manteniment_mrr` i creuarà en temps real la quota recurrent facturada amb la suma de costos reals de totes les OTs vinculades al contracte (mà d'obra a `cost_hora_efectiu_mensual` + materials a PMP + desplaçaments a $\text{EUR/km}$), calculant el **Ràtio de Sinistralitat del Contracte**:
  $$\text{Sinistralitat MRR (\%)} = \frac{\sum \text{Costos Reals OTs del Contracte}}{\text{Quota Fixa Devengada en el Període}} \times 100$$
  classificant el contracte amb semàfor automàtic: ` RENDIBLE` ($< 65\%$), ` ALERTA_EROSIO` ($65\% - 90\%$) i ` DEFICITARI_CRITIC` ($> 90\%$).
* **RF-42 (Ubiquitous) — Gràfiques Analítiques Interactives i Concentració Pareto:** EL SISTEMA alimentarà mitjançant un endpoint agregat `/api/v1/gestio/comptabilitat/dashboard-economic` les 5 gràfiques executives (Evolució 12M + EBITDA, *Waterfall Chart* mensual del Benefici Net, Projecció de Tresoreria 30/60/90d amb Guardacaixa IVA, Donut de Marges per Vertical/Producte, i *Aging* + Risc de Concentració Pareto si un sol client supera el $25\%$ de la facturació total).

---

## 4. Casos Límit i Excepcions (Edge Cases)

* **EDGE-01 (Arrodoniment IVA Multi-línia):** Desquadrament de $\pm 0.01\text{ EUR}$ entre suma d'IVAs individuals i IVA sobre base agregada; es resol ajustant la línia de major import amb `ROUND_HALF_UP`.
* **EDGE-02 (Anticip Mixt Superat):** Intent de descomptar un anticip del $10\%$ sobre una factura final amb base únicament al $21\%$; el motor de *Bucket Matching* bloqueja la compensació creuada entre tipus d'IVA diferents (`HTTP 400`).
* **EDGE-03 (Divisió per Zero en Cost Hora Efectiu):** Si un operari ha estat de baixa tot el mes o té $0$ hores imputades a OTs facturables ($\sum \text{Hores OT} = 0$), el sistema evita `ZeroDivisionError`, retorna `cost_hora_efectiu_mensual = NULL`, marca l'operari amb insígnia `100% IMPRODUCTIU / BAIXA` i imputa tot el seu cost salarial mensual directament a "Estructura Improductiva" al *Waterfall Chart*.
* **EDGE-04 (Odòmetre Sense Recorregut al Mes):** Si un vehicle té $0\text{ km}$ recorreguts en el mes seleccionat, el sistema evita la divisió per zero en el càlcul d'$\text{EUR/km}$ i imputa la `quota_renting_mensual` íntegra com a cost fix de flota no assignat.
* **EDGE-05 (Concurrència en Emissió Veri*factu):** Dues peticions simultànies d'emissió de factura pel mateix tenant s'encuen mitjançant `SELECT FOR UPDATE` sobre la fila de sèrie fiscal, garantint una cadena de `hash_sha256` sense bifurcacions ni salts de numeració.
* **EDGE-06 (Tiquet > 100 EUR sense NIF):** Activa simultàniament el bloqueig d'aprovació del `BOSS` i la no-deduibilitat de l'IVA ($0\%$ a Guardacaixa Fiscal, $100\%$ a despesa $62\text{X}$).
* **EDGE-07 (Fals Positiu de Bloqueig de Risc per Retenció de Garantia):** Un client té un saldo pendent al compte $4308$ (Retenció del $5\%$ per garantia d'obra) amb antiguitat de $200\text{ dies}$, però la `data_venciment_garantia` és als $365\text{ dies}$ i la resta de la factura ($95\%$) es va cobrar al dia. El sistema **NO** bloqueja el client (`estat_risc_operatiu = APTE`) perquè la retenció encara no és exigible.
* **EDGE-08 (Suplert sense Justificant):** Bloqueig atòmic del pas a estat `EMESA` (`HTTP 422`) si existeix una línia amb compte $554$ i manca el PDF del comprovant públic.
* **EDGE-09 (Intrusió d'Enginyer a Costos Dinàmics):** Si un `ENGINYER` intenta consultar `/api/v1/gestio/comptabilitat/operaris-cost-efectiu`, rep `HTTP 403 Forbidden`. Quan consulta la fitxa d'obra per pressupostar, només rep `cost_hora_referencia`.
* **EDGE-10 (Intent de Mutació del Registre SIF):** Qualsevol `UPDATE` o `DELETE` directe a PostgreSQL sobre `registre_esdeveniments_sif` llança excepció de trigger `SIF_IMMUTABLE_VIOLATION` i fa rollback de la transacció.
* **EDGE-11 (Expiració de Finestra Art. 80 LIVA):** Si passen els $270\text{ dies}$ ($6\text{ mesos} + 3\text{ mesos}$) sense haver emès la factura rectificativa d'incobrable, el sistema commuta l'estat a `FINESTRA_ART80_EXPIRADA_PERDUA_FISCAL` i bloqueja l'emissió per evitar sancions de l'AEAT per fora de termini.
* **EDGE-12 (Cobraments Parcials i DSO):** Si una factura de $10,000\text{ EUR}$ rep un cobrament parcial de $4,000\text{ EUR}$, l'*Aging* i la projecció de tresoreria computen exclusivament el saldo viu restant ($6,000\text{ EUR}$), i el DSO final només es consolida quan `import_cobrat == liquid_exigible`.

---

## 5. Matriu de Traçabilitat 1:1 de la Definition of Done (DoD)

| Codi RF | Cas Límit | Criteri de Validació Automatitzada Pytest (Zero-Mock & Zero-Orphan) |
| :--- | :--- | :--- |
| **RF-01 a RF-04** | - | Arrencada en Dia 0 retorna JSON complet amb todos els KPIs i sèries de gràfiques a `0.00` sense mocks. Filtre temporal commuta resultats en `<200ms`. |
| **RF-05 a RF-05.4** | **EDGE-09** | Rol `ENGINYER` i `OPERARI` reben `403` a tot `/comptabilitat/*`. L'endpoint `/operativa-financera/client/{id}/estat-risc` retorna `estat_risc_operatiu` sense cap camp monetari. |
| **RF-06 a RF-11** | **EDGE-01 / 02 / 08** | Factura agrupada aplica `ROUND_HALF_UP`, *Bucket Matching* d'anticips per tipus d'IVA i bloqueja suplerts sense PDF adjunt. |
| **RF-12 a RF-15** | **EDGE-05** | `SELECT FOR UPDATE` encadena `hash_sha256` Veri*factu sense col·lisions concurrents i inserta a `outbox_enviaments_aeat`. |
| **RF-16 a RF-25** | **EDGE-06 / 10** | Nòmines d'alta direcció ofuscades per a `SECRETARIA`. Tiquet sense NIF va a $62\text{X}$ amb IVA $0\%$. Trigger SIF avorta qualsevol `UPDATE`/`DELETE`. |
| **RF-26 a RF-30** | - | Càlcul exacte SQL de P&L, Marge Brut vs. Net (descomptant `quantitat_merma`), Alerta d'Erosió de Marge, Break-Even, Guardacaixa IVA i Cash Flow 30/60/90d. |
| **RF-31 / RF-32** | - | OTs tancades sense factura sumen al KPI de WIP; si `dies > 7`, apareixen a la safata d'alerta de WIP envellit. |
| **RF-33 / RF-34** | **EDGE-07** | Retenció del $5\%$ va al compte $4308$, no contamina l'*Aging* ordinari i dispara alerta als $350\text{ dies}$ ($15\text{ dies}$ abans de l'any). |
| **RF-35 / RF-36** | **EDGE-07** | Factura ordinària impagada $>90\text{ dies}$ posa el client a `BLOQUEJAT_RISC`, retornant `HTTP 423 Locked` en crear OT o Picking fins a `OVERRIDE_BOSS` amb traça SIF. |
| **RF-37 / RF-38** | **EDGE-11** | Factura impagada als $180\text{ dies}$ obre `FINESTRA_ART80_OBERTA` i pre-crea esborrany Sèrie R; als $271\text{ dies}$ bloqueja per expiració legal. |
| **RF-39 / RF-40** | **EDGE-03 / 04** | Cost Hora Efectiu divideix cost salarial real entre hores OT facturables (controlant `div/0`); Flota calcula $\text{EUR/km}$ real. |
| **RF-41 / RF-42** | - | Contracte MRR amb costos d'OTs $>90\%$ de la quota es marca com a `DEFICITARI_CRITIC`. Les 5 gràfiques reben dades 100% SQL. |
