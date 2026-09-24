# Pla d'Implementació — Microservei Bot de Telegram per a Clients Finals (Spec 023)

Aquest pla detalla el disseny i implementació del microservei **Bot de Telegram per a Clients Finals** d'acord amb la **Spec 023**, la Constitució v4.0 de SEVALOR, la política de **Zero Mock Data**, el principi **Human-in-the-Loop (HITL)** i la sobirania absoluta de dades Hetzner.

---

## 🎯 Objectius del Microservei
1. **Arquitectura Microservei Aïllada & Webhook Securitzat (`RF-01`, `RF-02`)**:
   - Servei asíncron independent desenvolupat sobre Python 3.12 i `aiogram 3.x`.
   - Autenticació criptogràfica mitjançant capçalera `X-Telegram-Bot-Api-Secret-Token` en cada ingrés de webhook.
2. **Multi-Bot Dinàmic & Segregació RLS (`RF-03`, `RF-04`)**:
   - Capacitat d'executar múltiples instàncies de bot o una instància compartida amb enrutament rígid basat en `empresa_id`.
   - Injecció automàtica de la variable de sessió RLS (`SET LOCAL app.current_tenant_id`) a PostgreSQL per a qualsevol operació de base de dades.
3. **Deep-Linking & Blindatge d'Accés (`RF-05`, `RF-06`)**:
   - Vinculació del client mitjançant `/start <token_criptografic>` d'un sol ús.
   - Rebuig opac immediat a qualsevol usuari no convidat ("Aquest és un canal privat d'atenció. Per accedir-hi, utilitzeu l'enllaç d'invitació facilitat per l'empresa.").
4. **Rate Limiting & Resiliència Anti-Abús (`RF-07`)**:
   - Finestra lliscant de concurrència amb límit de 10 missatges per minut per usuari (`RateLimiterTelegram`), mitigant atacs de saturació.
5. **Tríada Operativa de Notificacions de Camp (`RF-08`, `RF-09`, `RF-10`)**:
   - Automatització exclusiva dels 3 esdeveniments operatius canònics:
     1. Sortida de nau / equip en camí amb ETA estimat.
     2. Arribada a la finca i inici dels treballs.
     3. Tancament de jornada i signatura de part amb resum d'intervenció.
6. **Mandat Human-in-the-Loop (HITL) per a Preus (`RF-11`)**:
   - Bloqueig estricte d'enviament autònom de pressupostos o imports per part de la IA: qualsevol xifra econòmica requereix validació prèvia d'un tècnic d'oficina.
7. **Aprovació de Pressupost a 1 Clic (`RF-12`, `RF-13`, `RF-14`)**:
   - Botonera interactiva inline ("✅ Acceptar Pressupost" / "📝 Demanar Canvis").
   - Transició atòmica a l'estat `ACCEPTAT` amb deshabilitació immediata dels botons per a evitar dobles clics.
   - Si demana canvis, activació d'estat FSM (Finite State Machine) i generació d'alerta urgent a l'oficina tècnica.
8. **Seguretat de Fitxers & Desat Sobirà Hetzner (`RF-15`, `RF-16`, `RF-17`)**:
   - Filtre rígid de doble extensió que bloqueja fitxers maliciosos (`.pdf.exe`, `.jpg.sh`, `.png.bat`, scripts executables).
   - Validació de signatura de fitxer (Magic Bytes) per a JPG, PNG, PDF i WebP.
   - Emmagatzematge estricte al sistema d'arxius local Hetzner Falkenstein (`/data/<empresa_id>/incidencies/`), sense sortida a servidors de tercers.
   - Commutació de l'expedient a estat vermell prioritari a la safata d'incidències en rebre fotografies d'avaria.

---

## 🛠️ Components Tècnics
### 1. Nucli de Seguretat (`bot/security.py`)
- `detectar_doble_extensio(nom_fitxer)`: Identificació heurística de dobles extensions, caràcters nuls i scripts camuflats.
- `validar_magic_bytes(header_bytes, extensio)`: Comprovació binària de formats autoritzats.
- `RateLimiterTelegram`: Gestor de quotes de missatges per finestra temporal.

### 2. Controlador Principal del Bot (`bot/main.py`)
- Gestió d'invitacions deep link `/start <token>`.
- Filtratge d'accés per llista blanca en memòria / PostgreSQL.
- Recepció d'imatges i documents d'avaria amb desat sobirà.
- Callback handlers per a aprovació o modificació de pressupostos suplementaris.

### 3. Bateria de Proves QA
- Backend / Mòdul Bot Tests: `backend/tests/test_bot_telegram.py` (7 proves unitàries).
- Protocol d'Auditoria Automatitzada: `pwa/test_bot_telegram_audit.mjs` (10 proves QA completes).

---

## 🧪 Pla de Verificació
- Executar `python -m unittest tests/test_bot_telegram.py` dins de Docker.
- Executar `node pwa/test_bot_telegram_audit.mjs`.
