# 📋 CHECKLIST OFICIAL DE DOCUMENTS DE PROVA REAL (Zero Mock Data)

> **🎯 Objectiu (El Club de l'1%):**  
> Disposar d'un banc de documents reals i verídics (amb dades personals anonimitzades o de prova d'entorn real) per sotmetre la suite **Sevalor** a una validació implacable sense cap dada simulada (*Zero Mock*).  
> Aquests documents permetran verificar la precisió dels motors **OCR** (extracció de caràcters, patrons tabulars i Llama-Vision), la concordança de regles de negoci (NIF, IBAN, matrícules, ITV, dates de caducitat) i la inserció física a PostgreSQL sota regles RLS.

---

## 🗂️ Estructura de Carpetes del Banc Documental (`/demo_docs`)

Diposita cada document a la seva subcarpeta corresponent:

```
demo_docs/
├── 01_operaris_rrhh/          # DNI, carnet de conduir, PRL, salut laboral
├── 02_flota_vehicles/         # ITV, permís circulació, tiquets benzina, km
├── 03_magatzem_compres/       # Albarans de proveïdor, factures, fitxes CE
├── 04_clients_financer/       # Mandats SEPA, pressupostos signats, contractes
├── 05_enginyeria_obres/       # Plànols tècnics, butlletins CIE, partes de feina
└── 06_incidencies_camp/       # Fotos d'avaries, danys i auditories amb GPS
```

---

## 👷 1. Operaris i Recursos Humans (`01_operaris_rrhh/`)

Mòduls vinculats: **Spec 008 (Gestió Operaris)**, **Spec 019 (Login Operaris)** i **Spec 01-backoffice-gestio (US2 - Alta Màgica)**.

| Estat | Document Requerit | Subcarpeta | Mètode | Formats | Camps a Extreure / Validar | Criteris de Validació |
| :---: | :--- | :--- | :---: | :---: | :--- | :--- |
| [ ] | **DNI / NIE (Anvers i Revers)** | `01_operaris_rrhh/dni/` | **OCR (Alta Màgica)** | `.jpg`, `.png`, `.pdf` | • **NIF / NIE**<br>• **Nom complet**<br>• **Primer Cognom**<br>• **Segon Cognom**<br>• **Data de Naixement**<br>• **Sexe**<br>• **Nacionalitat**<br>• **Data de Caducitat**<br>• **Núm. Suport (IDESP)** | • Algorisme mòdul 23 per a NIF/NIE espanyol.<br>• Alerta automàtica si caduca en < 30 dies.<br>• Zero Data Entry a la fitxa 360 de l'operari. |
| [ ] | **Carnet de Conduir Espanyol (Anvers i Revers)** | `01_operaris_rrhh/carnet_conduir/` | **OCR / Validació** | `.jpg`, `.png`, `.pdf` | • **Núm. Permís de Conduir**<br>• **Classes autoritzades** (B, B+E, C1, C)<br>• **Data d'expedició**<br>• **Data de caducitat** per classe<br>• **Codis d'adaptació** (ex: 01 ulleres) | • Habilitació automàtica per a conduir furgonetes o camions de la flota.<br>• Alerta de caducitat a la fitxa de l'operari. |
| [ ] | **Certificats de Formació PRL & Habilitacions** | `01_operaris_rrhh/prl_habilitacions/` | **Validació Documental** | `.pdf` | • **Especialitat PRL** (20h Conveni Metall/Construcció, 60h Recurs Preventiu)<br>• **Habilitació Treballs en Alçada**<br>• **Carnet Plataformes Elevadores (PEMP)**<br>• **Carnet Instal·lador Autoritzat REBT / RITE**<br>• **Entitat Certificadora / Centre Formació**<br>• **Data d'emissió i validesa** | • Bloqueig d'assignació d'Ordres de Treball (OTs) amb risc elèctric o d'alçada si l'operari no té la certificació en vigor. |
| [ ] | **Certificat de Reconeixement Mèdic (Vigilància Salut)** | `01_operaris_rrhh/reconeixements_medics/` | **Validació Documental** | `.pdf` | • **Aptitud laboral** (APTE / APTE AMB RESTRICCIONS)<br>• **Data de reconeixement**<br>• **Data de propera revisió (caducitat 1 any)** | • Avís a Secretaria/RRHH 45 dies abans del venciment anual. |
| [ ] | **Dada Laboral: Núm. Afiliació Seguretat Social (NAF)** | *Anotar a fitxa / Contracte* | **Validació Administrativa** | `.pdf` / Text | • **Codi de província (2 dígits)**<br>• **Número de seqüència (8 dígits)**<br>• **Dígits de control (2 dígits)** | • Verificació matemàtica del dígit de control de la Seguretat Social. |

---

## 🚐 2. Flota de Vehicles i Despeses de Mobilitat (`02_flota_vehicles/`)

Mòduls vinculats: **Spec 006 (Gestió Flota)**, **Spec 015 (Operari Vehicles)** i **Spec 02-frontline-operaris (Tiquets Carburant & Odòmetre)**.

| Estat | Document Requerit | Subcarpeta | Mètode | Formats | Camps a Extreure / Validar | Criteris de Validació |
| :---: | :--- | :--- | :---: | :---: | :--- | :--- |
| [ ] | **Fitxa Tècnica del Vehicle (Targeta ITV)** | `02_flota_vehicles/fitxes_tecniques_itv/` | **OCR / Validació** | `.pdf`, `.jpg` | • **Matrícula**<br>• **Número de Bastidor (VIN - 17 caràcters)**<br>• **Marca i Model**<br>• **Cilindrada (cc) i Potència (kW)**<br>• **Tipus Combustible** (Dièsel, Gasolina, Híbrid, Elèctric)<br>• **Tara i Massa Màxima Autoritzada (MMA)** | • Format de matrícula: `0000-XXX` o provincial antiga.<br>• Validació de VIN (sense caràcters I, O, Q). |
| [ ] | **Informe d'Inspecció ITV & Adhesiu en Vigor** | `02_flota_vehicles/fitxes_tecniques_itv/` | **OCR (Caducitats)** | `.pdf`, `.jpg` | • **Data d'inspecció realitzada**<br>• **Resultat** (FAVORABLE / AMB DEFECTES LLEUS / DESFAVORABLE)<br>• **Data límit de vigència (Data pròxima ITV)**<br>• **Quilometratge anotat a l'estació ITV** | • Sincronització de l'alerta d'ITV al tauler de gestió de flota (30 dies d'antelació).<br>• Comprovació que els km de la ITV siguin inferiors als actuals. |
| [ ] | **Permís de Circulació del Vehicle** | `02_flota_vehicles/permisos_circulacio/` | **Validació Documental** | `.pdf`, `.jpg` | • **Titular del vehicle** (CIF de l'empresa o rènting)<br>• **Data de primera matriculació**<br>• **Servei al qual es destina** (Públic / Mercaderies) | • Comprovació de titularitat multi-tenant. |
| [ ] | **Pòlissa d'Assegurança & Rebut Bancari Pagat** | `02_flota_vehicles/assegurances/` | **Validació Documental** | `.pdf` | • **Companyia Asseguradora**<br>• **Número de Pòlissa**<br>• **Data d'efecte i data de venciment**<br>• **Tipus de Cobertura** (Tercers + Llunes + Robatori / Tot Risc)<br>• **Comprovant de pagament bancari** | • Alerta de renovació anual de pòlissa.<br>• Veto a la sortida del vehicle si no té assegurança vigent. |
| [ ] | **Tiquets de Carburant i Despeses de Ruta** | `02_flota_vehicles/tiquets_carburant/` | **OCR (Crucial)** | `.jpg`, `.png`, `.pdf` | • **Raó Social i NIF de la benzinera**<br>• **Data i hora exacta de subministrament**<br>• **Tipus de combustible** (Gasoli A, AdBlue, Gasolina 95)<br>• **Litres subministrats (L)**<br>• **Preu unitari per litre (€/L)**<br>• **Import total pagat (€)**<br>• **Matrícula del vehicle associat** | • Detecció automàtica de compra mixta (Gasoli + AdBlue).<br>• Càlcul de consum mitjà (L/100km) encreuant amb els km de l'odòmetre.<br>• Imputació de cost al centre de despesa del vehicle. |
| [ ] | **Foto del Comptaquilòmetres (Odòmetre del Tauler)** | `02_flota_vehicles/odometres_km/` | **OCR Vision (AI)** | `.jpg`, `.png` | • **Lectura numèrica de quilòmetres reals** al quadre digital o analògic del vehicle.<br>• **Metadades EXIF** (timestamp de la captura). | • Verificació de continuïtat (els km nous no poden ser inferiors a l'últim registre).<br>• Disparador de manteniment preventiu (canvi d'oli/filtres cada 15.000 / 20.000 km). |

---

## 📦 3. Magatzem, Compres i Proveïdors (`03_magatzem_compres/`)

Mòduls vinculats: **Spec 003 (Proveïdors)**, **Spec 004 (Magatzem)**, **Spec 014 (Operari Material)** i **Spec 01-backoffice-gestio (US3 - Alta Proveïdors & Albarans OCR)**.

| Estat | Document Requerit | Subcarpeta | Mètode | Formats | Camps a Extreure / Validar | Criteris de Validació |
| :---: | :--- | :--- | :---: | :---: | :--- | :--- |
| [ ] | **Albarà d'Entrega de Proveïdor (Material Elèctric / Reg / Fontaneria)** | `03_magatzem_compres/albarans_proveidor/` | **OCR Tabular Avançat** | `.pdf`, `.jpg`, `.png` | • **Número d'albarà**<br>• **Data d'entrega**<br>• **Dades del proveïdor** (Raó Social, NIF/CIF, Adreça)<br>• **Adreça de descàrrega** (Magatzem central o Obra directa)<br>• **Taula d'articles**: Codi article proveïdor, Descripció del material, Quantitat lliurada, Unitat (m, u, kg, bobina), Preu unitari, Descompte per línia (%), Import subtotal | • El resultat OCR es desa com a esborrany (`PENDENT_AUDITORIA`).<br>• L'humà valida abans de consolidar l'estoc.<br>• Càlcul automàtic de % de merma en materials continus (bobines de cable, canonades de polietilè). |
| [ ] | **Factura Oficial de Proveïdor** | `03_magatzem_compres/factures_proveidor/` | **OCR Comptable / Veri\*factu** | `.pdf` | • **Número de Factura**<br>• **Data d'emissió**<br>• **NIF/CIF Proveïdor i Client receptor**<br>• **Base Imposable** (desglossada per tipus 4%, 10%, 21%)<br>• **Quotes d'IVA** i Retencions (IRPF)<br>• **Import Total Factura**<br>• **Termini de Pagament** i **IBAN del proveïdor** | • Conciliació automàtica contra els albarans prèviament registrats.<br>• Validació de suma aritmètica (`Base + IVA - Retencions == Total`). |
| [ ] | **Fitxa Tècnica de Material / Datasheet CE** | `03_magatzem_compres/fitxes_materials_ce/` | **Validació Tècnica** | `.pdf` | • **Codi de Barres de referència (EAN-13, Code 128)** (Nota: sense QR segons spec)<br>• **Descripció tècnica i especificacions** (Voltatge, Secció mm², Pressió bar)<br>• **Segell de Marcatge CE / Homologació UNE** | • Validació de conformitat normativa per als butlletins i projectes REBT/reg. |

---

## 💼 4. Clients, Vendes i Gestió Financera (`04_clients_financer/`)

Mòduls vinculats: **Spec 002 (Clients)**, **Spec 007 (Comptabilitat)** i **Spec 05-contractes-manteniment**.

| Estat | Document Requerit | Subcarpeta | Mètode | Formats | Camps a Extreure / Validar | Criteris de Validació |
| :---: | :--- | :--- | :---: | :---: | :--- | :--- |
| [ ] | **Dades Fiscals de Clients (Particulars o Empreses)** | `04_clients_financer/` | **OCR / Validació Dades** | `.pdf`, `.jpg` | • **Raó Social o Nom i Cognoms**<br>• **NIF / CIF / NIE**<br>• **Adreça Fiscal completa (Carrer, CP, Població, Província)**<br>• **Persona de contacte tècnic / administratiu**<br>• **Telèfon i Email per a facturació electrònica** | • Algorisme de NIF/CIF vigent a Espanya.<br>• Validació de Codi Postal coincident amb municipi. |
| [ ] | **Mandat de Domiciliació Bancària SEPA (B2B o Core)** | `04_clients_financer/mandats_sepa/` | **OCR / Extracció IBAN** | `.pdf`, `.jpg` | • **Referència Única del Mandat (RUM)**<br>• **Nom del titular del compte**<br>• **NIF del deutor**<br>• **IBAN complet (Format ESxx xxxx xxxx xxxx xxxx xxxx)**<br>• **Codi BIC / SWIFT** de l'entitat<br>• **Tipus de pagament** (Recurrent / Únic)<br>• **Data de signatura i signatura física/digital** | • Validació checksum de l'IBAN espanyol (mòdul 97).<br>• Obligatori per a la generació de fitxers de remesa bancària XML SEPA ISO 20022 (Norma 19 / XML pain.008). |
| [ ] | **Pressupost Oficial Acceptat i Signat pel Client** | `04_clients_financer/pressupostos_signats/` | **Validació / Token** | `.pdf` | • **Codi de Pressupost** (ex: `PRES-2026-0042`)<br>• **Data d'acceptació**<br>• **Import Total acceptat (€)**<br>• **Signatura del client** o **Token digital** (ex: `TG-APROV-...` des de Telegram)<br>• **Condicions de pagament pactades** (% a l'inici, % a final d'obra) | • Canvi d'estat automàtic a `APROVAT`.<br>• Habilitació per a la creació immediata de l'Ordre de Treball (OT). |
| [ ] | **Contracte de Manteniment Preventiu Signat** | `04_clients_financer/contractes_manteniment/` | **Validació Contractual** | `.pdf` | • **Periodicitat del manteniment** (mensual, trimestral, semestral, anual)<br>• **Equips i màquines coberts** (amb número de sèrie, marca, ubicació)<br>• **Quota recurrent periòdica (€)**<br>• **Condicions de temps de resposta (SLA)** per a avaries d'urgència | • Generació automàtica del calendari d'OTs preventives recurrents al planificador. |

---

## ⚡ 5. Enginyeria, Obres i Plànols Tècnics (`05_enginyeria_obres/`)

Mòduls vinculats: **Spec 005 (Feines & Mapa GIS)**, **Spec 010 (Plànols)**, **Spec 013 (Operari Feines)** i **Spec 017 (Operari Plànols)**.

| Estat | Document Requerit | Subcarpeta | Mètode | Formats | Camps a Extreure / Validar | Criteris de Validació |
| :---: | :--- | :--- | :---: | :---: | :--- | :--- |
| [ ] | **Plànol Tècnic d'Instal·lació (Elèctric / Reg / Edificació)** | `05_enginyeria_obres/planols_tecnics/` | **Visor / Capes Tècniques** | `.pdf`, `.dwg`, `.dxf`, `.png` | • **Codi de Projecte / Obra**<br>• **Títol del Plànol** (Esquema unifilar, xarxa de reg sectoritzada, traçat BT)<br>• **Escala tècnica** (1:50, 1:100, 1:500)<br>• **Número de revisió / versió del plànol**<br>• **Capes tècniques d'elements** | • Visualització fluida tant al navegador web (`/gestio/planols`) com a la PWA offline de l'operari al terreny (`/operari/planols`). |
| [ ] | **Certificat Oficial d'Instal·lació Elèctrica (CIE / Butlletí BT)** | `05_enginyeria_obres/butlletins_cie_industria/` | **Validació Tècnica Oficial** | `.pdf` | • **Número de Registre d'Indústria (Generalitat / CCAA)**<br>• **Potència Màxima Admissible (kW)** i **Tensió nominal (V)**<br>• **Dades de l'Instal·lador Autoritzat** (Nom, NIF, Núm. Carnet Instal·lador)<br>• **Empresa Instal·ladora Habilitada**<br>• **Referència Cadastral o adreça del subministrament** | • Validació de coherència tècnica segons el REBT (Reglament Electrotècnic de Baixa Tensió) abans de tramitació a la companyia distribuïdora. |
| [ ] | **Parte de Treball d'Operari / Albarà d'Intervenció Signat** | `05_enginyeria_obres/partes_treball_signats/` | **Validació Signatura / Hores** | `.pdf`, `.jpg` | • **Codi d'Ordre de Treball (OT)**<br>• **Data i hores d'inici i finalització** (temps de mà d'obra)<br>• **Llistat de materials i recanvis utilitzats** (amb sortida de furgoneta)<br>• **Observacions tècniques de l'operari**<br>• **Signatura digital o hològrafa del client in-situ** | • Deducció automàtica de l'estoc del vehicle de l'operari.<br>• Generació de l'informe post-obra per a facturació. |

---

## 📸 6. Incidències i Qualitat al Terreny (`06_incidencies_camp/`)

Mòduls vinculats: **Spec 016 (Operari Incidències)** i **Spec 020 (Operari Càmera)**.

| Estat | Document Requerit | Subcarpeta | Mètode | Formats | Camps a Extreure / Validar | Criteris de Validació |
| :---: | :--- | :--- | :---: | :---: | :--- | :--- |
| [ ] | **Fotografia d'Avaria / Dany amb Metadades GPS** | `06_incidencies_camp/fotografies_danys/` | **Extracció EXIF + Classificació IA** | `.jpg`, `.jpeg` | • **Geolocalització exacta** (Latitud i Longitud reals per metadades EXIF)<br>• **Data i hora de la captura** (Timestamp original)<br>• **Grau de severitat** (BAIXA, MITJANA, CRÍTICA)<br>• **Descripció visual del dany** (canonada trencada, quadre cremat, cablejat deficient) | • Ubicació automàtica sobre el mapa GIS de la Torre de Control (`/gestio/mapa`).<br>• Verificació de Magic Bytes de seguretat (rebuig de fitxers maliciosos o reanomenats). |

---

## 🛠️ Com Executar les Proves Reals una Vegada Afegits els Documents

Quan dipositis els documents en aquestes carpetes:

1. **Proves OCR de Backend:**
   ```bash
   cd backend
   # Execució dels tests de serveis OCR amb els documents reals dipositats
   pytest tests/test_phase3_copilot_eval.py -v
   pytest tests/api/ -k "ocr" -v
   ```

2. **Proves d'Interfície Web amb Chrome DevTools MCP:**
   L'agent utilitzarà directament el servidor MCP `chrome-devtools` (`upload_file`, `fill_form`, `take_screenshot`) per carregar els documents a la PWA o al Dashboard i verificar l'extracció i consolidació en temps real.

3. **Comprovació de Base de Dades amb PostgreSQL MCP:**
   L'agent utilitzarà `postgres.query` per certificar que les dades extretes s'han desat a les taules reals (`albarans`, `tiquets_carburant`, `operaris`, `flota`) amb el tenant `empresa_id` correctament aïllat per RLS.
