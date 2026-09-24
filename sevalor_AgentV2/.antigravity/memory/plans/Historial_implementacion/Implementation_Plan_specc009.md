# Pla d'Implementació — Notificacions i Alertes Centralitzades (`/gestio/notificacions` — Spec 009)

Aquest pla defineix l'arquitectura, el modelat de dades i la interfície del mòdul de **Notificacions i Canal Telegram de Clients** de SEVALOR Suite, d'acord amb la **Spec 009**, la **Constitució SEVALOR v4.0**, els principis d'aïllament multi-tenant RLS, **Zero Mock Data** i sobirania d'emmagatzematge Hetzner (Alemanya - UE).

---

## 1. Visió General i Objectius

El mòdul actua com a **Hub de Comunicació Multicanal, Traçabilitat d'Avisos i Interacció Interactiva amb el Client**:
1. **Canals Principals Permanents (Email i Telèfon)**: El correu corporatiu i les trucades es mantenen com els canals oficials universals de relació contractual.
2. **Canal Àgil Complementari (Bot de Telegram)**: Via ràpida per a seguiment de feines, enviament de fotografies d'avaries (&le; 15 MB), consultes a l'assistent de FAQs locals i aprovació digital de pressupostos a 1 clic.
3. **Accés Blindat per Invitació Unívoca (Deep Linking)**: Enllaç `https://t.me/<Bot>?start=<token>` d'un sol ús i caducitat obligatòria de 48 hores. Rebuig immediat i bloqueig de qualsevol usuari no vinculat (EDGE-01).
4. **Codificació Cromàtica de Converses**:
   - 🔴 **Vermell (Prioritari)**: Incidències tècniques urgents, fotografies d'avaries, consultes amb incertesa de la IA o bloqueig de feina.
   - 🔵 **Blau (Conversa Oberta)**: Diàleg actiu en curs o pressupost suplementari (Memòndum) pendent d'aprovació.
   - 🟢 **Verd (Solucionat / Arxivat)**: Resolució i arxiu automàtic cap a la fitxa del client (`/gestio/clients/{id}`). Reobertura automàtica si el client torna a escriure.
5. **Automatismes de Camp Exclusius vs Human-in-the-Loop (HITL)**:
   - Només 3 esdeveniments poden disparar notificació automàtica sense intervenció humana:
     1. *"Operari en camí"* (hora estimada d'arribada).
     2. *"Operari arribat a finca"* (geovalla de 50 m o marcatge d'arribada a la PWA).
     3. *"Feina acabada"* (tancament de tasca amb protocol de 3 fotos obligatòries).
   - Tota la resta de comunicacions requereix aprovació humana d'oficina (RF-17).
6. **Aprovació Interactiva de Pressupostos (Memòndum)**:
   - Botons: `[Llegir Memòndum]`, `[✅ Acceptar Pressupost]` i `[❌ Sol·licitar modificacions]`.
   - Idempotència atòmica en base de dades amb `token_aprobacio`. Si accepta: injecció a l'OT i desbloqueig del Kanban de camp. Si demana canvis: passa a "En revisió", commuta a xat blau i alerta a l'enginyer per trucada de negociació (RF-19, RF-20, EDGE-05).
7. **RAG IA Local en Servidors Hetzner (Anti-Al·lucinacions)**:
   - Consulta a documents de `/knowledge/company_faqs/`.
   - Si la confiança és inferior al 80% o la consulta surt del corpus: no inventa res, respon la derivació estàndard i escala la conversa a l'Enginyer en Vermell Prioritari (RF-26, EDGE-04).
8. **Lliurament Segur de Factures Veri\*factu amb Token Temporal (72 hores)**:
   - Enllaç securitzat amb caducitat de 72 hores des del directori sobirà `/docs/<empresa_id>/factures/emeses/`.
   - Veto absolut d'Enginyer a l'emissió/enviament de factures (HTTP 403 Forbidden).
   - Si expira el token: bloqueig de descàrrega i opció de sol·licitar un nou enllaç per email (RF-30, EDGE-06).
9. **Zero Mock Data & Mode Clar/Fosc**: Interfície camaleònica d'alta densitat amb suport complet `dark:`.

---

## 2. Canvis Proposats

### A. Base de Dades: Migració SQL (`db/migrations/012_notificacions_telegram_xat.sql`)
- Creació de taules amb RLS forçada (`ALTER TABLE ... FORCE ROW LEVEL SECURITY`):
  - `tokens_invitacio_telegram`: Registre de tokens d'invitació unívocs deep linking (client_id, token_hash, expira_a 48h, utilitzat, utilitzat_a).
  - `converses_notificacio`: Fil de conversa per client/OT (client_id, ordre_treball_id, estat [VERMELL_PRIORITARI, BLAU_OBERT, VERD_SOLUCIONAT], titol, ultim_missatge_text, ultim_missatge_data, num_sense_llegir, es_arxivada).
  - `missatges_notificacio`: Historial cronològic de missatges (conversa_id, remitent_tipus [OFICINA, CLIENT, BOT_IA, SISTEMA_CAMP], canal [TELEGRAM, EMAIL, SMS, WEB_PWA], contingut_text, tipus_esdeveniment, adjunt_url, adjunt_mida_bytes, token_aprobacio, estat_aprobacio, token_descarrega_factura, token_descarrega_expira_a).
  - `faqs_corporatives_rag`: Base de coneixement per al RAG local d'assistència (pregunta, resposta, paraules_clau, actiu).
- Índexs optimitzats per empresa, client, data i estat per garantir cerques < 200 ms.

### B. Backend ORM: Models SQLAlchemy (`backend/app/models/models.py`)
- Afegir classes SQLAlchemy 2.0:
  - `TokenInvitacioTelegram`
  - `ConversaNotificacio`
  - `MissatgeNotificacio`
  - `FaqCorporativaRag`

### C. Backend API: Endpoints Core (`backend/app/api/v1/gestio/notificacions.py`)
- `GET /gestio/notificacions/converses`: Llistat de converses amb cerca reactiva, filtres cromàtics i mètriques agregades.
- `POST /gestio/notificacions/converses`: Creació d'un nou fil de comunicació (HITL).
- `GET /gestio/notificacions/converses/{id}`: Detall complet de la conversa i missatges cronològics.
- `POST /gestio/notificacions/converses/{id}/missatges`: Enviament de missatge manual (HITL) per Telegram o Email/SMS.
- `POST /gestio/notificacions/converses/{id}/solucionar`: Marcar com a verd solucionat i arxivar a la fitxa del client.
- `POST /gestio/notificacions/invitar-telegram/{client_id}`: Generació de token d'un sol ús (48h) per deep linking.
- `POST /gestio/notificacions/telegram/webhook`: Recepció d'esdeveniments Telegram (validació d'usuari desconegut EDGE-01, foto d'avaria &le;15MB, RAG local).
- `POST /gestio/notificacions/pressupost/resposta`: Aprovació atòmica o sol·licitud de canvis de pressupost (Memòndum).
- `POST /gestio/notificacions/factura/enviar`: Lliurament amb token temporal de 72h (amb Veto d'Enginyer 403).
- `GET /gestio/notificacions/factura/descarregar/{token}`: Descàrrega segura amb control d'expiració 72h.
- `POST /gestio/notificacions/automatisme-camp`: Injecció exclusiva dels 3 automatismes permesos ("Operari en camí", "Operari arribat", "Feina acabada").

### D. Registre a `backend/app/main.py`
- Importar i registrar el router sota `/api/v1/gestio/notificacions`.

### E. Frontend: Pàgina de Gestió de Notificacions (`pwa/src/app/gestio/notificacions/page.tsx`)
- **Capçalera d'Alta Densitat**: Cercador reactiu (<200 ms) per nom, telèfon, codi `CLI-XXXX` i `OT-XXXX`.
- **Selector de Filtres**: Totes, 🔴 Prioritàries (Vermell), 🔵 Obertes (Blau), 🟢 Solucionades (Verd/Arxivades).
- **Llista Lateral de Converses**: Indicador de missatges no llegits, avís d'escalada d'IA, insígnia de canal (Telegram / Email).
- **Panell Central de Xat Unificat**:
  - Missatges cronològics amb diferenciació per remitent (Oficina, Client, Bot IA, Esdeveniments de camp).
  - Targetes de Pressupost (Memòndum) amb estat en viu i botons d'acció.
  - Imatges d'avaries rebudes amb miniatura ampliable i validació MIME.
  - Avisos d'arribada d'operari i tancament d'obra.
- **Barra de Resposta & Accions Ràpides**:
  - Caixa de text per a intervenció manual de l'oficina (HITL).
  - Botó "Marcar com a Solucionat" (converteix a verd i arxiva).
  - Botó "Enviar Invitació Telegram" (genera deep link 48h).
  - Botó "Enviar Memòndum Pressupost".
- **Zero Mock Data**: Estat buit canònic ("No hi ha converses ni notificacions actives").

### F. Integració Global (`pwa/src/app/gestio/layout.tsx`)
- Afegir accés al menú de navegació: `Notificacions & Alertes` (`badge: CHAT`).
- Indicador visual d'alertes pendents a la capçalera (campana amb comptador vermell).
- Indexació al cercador Spotlight (`Ctrl + K`).

---

## 3. Pla de Verificació

### A. Proves Automatitzades de Backend (`backend/tests/test_notificacions.py`)
1. `test_llistar_converses_i_dia_zero`: Llistat buit inicial i mètriques a zero sota RLS.
2. `test_invitacio_telegram_deep_linking_48h`: Generació de token d'un sol ús que caduca en 48h.
3. `test_rebuig_usuari_desconegut_spam_edge01`: Usuari no vinculat a Telegram rep rebuig i no s'afegeix cap registre a la BD.
4. `test_cicle_vida_conversa_vermell_blau_verd`: Transicions d'estat cromàtic i arxiu/reobertura.
5. `test_automatismes_camp_exclusius_hitl`: Verificació que només els 3 esdeveniments autoritzats es disparen sense supervisió humana.
6. `test_aprovacio_pressupost_idempotencia`: Aprovació atòmica de pressupost amb `token_aprobacio`.
7. `test_factura_token_temporal_72h_i_veto_enginyer`:
   - Enginyer rep HTTP 403 en intentar trametre factures.
   - Token temporal caduca a les 72 hores i bloqueja la descàrrega.
8. `test_escalada_ia_incertesa_rag`: Consulta dubtosa de la IA s'escalarà en Vermell Prioritari a l'Enginyer.

### B. Protocol d'Auditoria QA Frontend (`pwa/test_notificacions_audit.mjs`)
- Suite de 10 proves en Node.js verificant tots els RFs i EDGEs de l'Spec 009.

### C. Compilació de Producció Next.js
- `npm run build` a `pwa/` (objectiu: 24/24 pàgines estàtiques generades netament).
