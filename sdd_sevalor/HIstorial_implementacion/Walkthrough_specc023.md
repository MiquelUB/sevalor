# Walkthrough d'Auditoria i Verificació — Microservei Bot de Telegram per a Clients Finals (Spec 023)

Aquest document certifica la implementació, proves de seguretat i auditories de conformitat del microservei **Bot de Telegram per a Clients Finals** d'acord amb la **Spec 023**.

---

## 🎯 Proves i Regles de Negoci Verificades

### 1. Webhook Securitzat i Secret Token (`RF-01`, `RF-02`)
- Verificat que qualsevol petició entrant de Telegram sense la capçalera `X-Telegram-Bot-Api-Secret-Token` coincident és rebutjada amb codi HTTP 403 Forbidden.

### 2. Multi-Bot Dinàmic i Segregació RLS (`RF-03`, `RF-04`)
- Verificat que cada instància de conversa injecta de manera aïllada el context d'arrendatari (`SET LOCAL app.current_tenant_id = '<tenant_uuid>'`), garantint l'estricta estanquitat de dades entre empreses a PostgreSQL.

### 3. Deep-Linking i Blindatge d'Accés (`RF-05`, `RF-06`)
- Verificat mitjançant `test_deep_linking_vinculacio_exitosa`:
  - L'usuari accedeix amb `/start <token>` i s'associa unívocament al seu `client_id` i `empresa_id`.
  - Rebuda del missatge de benvinguda camaleònic personalitzat amb la marca de l'arrendatari.
- Verificat mitjançant `test_rebuig_opac_usuaris_no_convidats`:
  - Qualsevol usuari extern que interactua amb el bot sense token previ rep una resposta opaca de seguretat, impedint la fuga d'informació de l'empresa.

### 4. Rate Limiting de Seguretat (`RF-07`)
- Verificat mitjançant `test_rate_limiter_telegram`:
  - La finestra de control permet fins a la quota màxima de missatges per minut i bloqueja automàticament peticions addicionals.

### 5. Tríada Operativa de Camp (`RF-08`, `RF-09`, `RF-10`)
- Verificada l'emissió automàtica exclusiva dels 3 esdeveniments de camp:
  1. *Equip en camí*: notificació amb hora prevista d'arribada.
  2. *Arribada a finca*: confirmació d'inici dels treballs.
  3. *Tancament de jornada*: informe resum i comunicació de finalització.

### 6. Mandat Human-in-the-Loop (HITL) (`RF-11`)
- Comprovació del bloqueig de generació o enviament de preus per part d'algoritmes d'IA sense aprovació explícita d'un usuari amb rol d'administració o enginyeria.

### 7. Aprovació de Pressupost a 1 Clic (`RF-12`, `RF-13`, `RF-14`)
- Verificat mitjançant `test_aprovacio_pressupost_1_clic`:
  - L'acció "ACCEPTAR" commuta l'estat a `ACCEPTAT`, enregistra la data/hora immutable i bloqueja noves interaccions.
  - L'acció "MODIFICAR" obre l'estat FSM de recollida de canvis i envia una alerta immediata d'atenció al client.

### 8. Filtre de Doble Extensió i Sobirania Hetzner (`RF-15`, `RF-16`, `RF-17`)
- Verificat mitjançant `test_filtre_doble_extensio_maliciosa` i `test_magic_bytes_validation`:
  - Bloqueig immediat de fitxers com `.pdf.exe`, `.jpg.sh`, `.png.py`, `.pdf.js` o executables camuflats.
  - Permissió de formats legítims: JPG, PNG, PDF i WebP.
  - Els fitxers acceptats es desen exclusivament al directori Hetzner sobirà local (`/data/<empresa_id>/incidencies/`).
  - Commutació automàtica a vermell prioritari a la safata de treball d'oficina.

---

## 📊 Resultats de la Suite de Proves QA
- **Suite Backend Unit & Integration Tests**:
  - Fitxer: `backend/tests/test_bot_telegram.py`
  - 7/7 proves superades (100% OK).
- **Suite Auditoria Automatitzada PWA/API**:
  - Fitxer: `pwa/test_bot_telegram_audit.mjs`
  - 10/10 proves superades (100% OK).
