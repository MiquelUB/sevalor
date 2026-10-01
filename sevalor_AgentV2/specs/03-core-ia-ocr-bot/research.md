# Research & Lessons Learned: Core IA, OCR, Bot de Telegram & Workers Asíncrons

**Macro-Feature**: `03-core-ia-ocr-bot`  
**Date**: 2026-09-29  
**Status**: Active Knowledge Base & Engineering Guidelines  

---

## 1. Executive Summary

Durant el desenvolupament i manteniment dels mòduls d'Intel·ligència Artificial, digitalització OCR, microservei de Telegram i processament en segon pla (Celery / Redis), s'han identificat diversos vectors crítics de fallada, colls d'ampolla i problemes de dependències creuades. 

Aquest document recopila les **lliçons apreses**, els **errors històrics detectats i esmenats**, i les **regles d'or d'enginyeria** que tot desenvolupador ha de complir estrictament en intervenir sobre aquest subsistema.

---

## 2. Lliçons Apreses i Regles Crítiques d'Arquitectura

### 📌 Lliçó 1: "OCR must be fully asynchronous or stubbed sync correctly"
- **Context i Problema Històric**:  
  Els processos d'anàlisi de visió artificial i OCR (reconeixement de text en albarans, tiquets de despesa o fitxes tècniques de vehicles) tenen un temps d'execució impredictible que oscil·la entre 1.5 i 8 segons per pàgina. Executar aquest processament de forma síncrona dins del cicle de vida de la petició HTTP a FastAPI bloquejava els workers de Uvicorn, provocant caigudes per timeout (`504 Gateway Timeout`) a la PWA d'operaris i al panell de gestió.
- **Resolució i Regla**:  
  1. **Mode Asíncron en Producció (Celery)**: L'endpoint d'API (`POST /albara/ocr`, etc.) ha de desar el fitxer al directori temporal segur de l'inquilí, disparar la tasca asíncrona de Celery (`processar_ocr_document_task.delay(temp_path, str(empresa_id))`) i retornar immediatament un codi `HTTP 202 Accepted` amb el `task_id`. El frontend consulta l'estat via polling a `/api/v1/workers/status/{task_id}`.
  2. **Mode Esborrany Síncron (Draft / Stub)**: En aquells formularis interactius que requereixen un retorn ràpid a l'usuari (ex. `/gestio/flota/ocr-draft`, `/gestio/proveidors/ocr-draft`), el servei ha d'estar perfectament preparat per retornar una estructura de dades canònica i completa (Zero Data Entry) sense bloquejar. Si s'utilitza un stub o simulació durant proves locals, l'objecte retornat ha de contenir obligatòriament totes les claus esperades pel frontend (ex. `linies` amb `referencia`, `nom`, `quantitat`, `preu`, `descompte_percent` i `tipus`), evitant errors de tipus `KeyError` o pantalles en blanc a Next.js (com va succeir a `fix_mock_ocr.py`).

---

### 📌 Lliçó 2: "Celery tasks require queue_media"
- **Context i Problema Històric**:  
  Inicialment, totes les tasques en segon pla es despatxaven a una única cua genèrica de Celery (`celery`). Quan un operari pujava diversos albarans pesats o s'iniciava la transcripció d'un lot d'àudios de veu de camp, aquestes tasques lentes monopolitzaven els 4 processos concurrents del worker. Com a conseqüència, les notificacions urgents de Telegram ("Operari en camí") i els avisos d'incidència d'emergència quedaven retinguts en cua durant minuts (problema de *Head-of-Line Blocking*).
- **Resolució i Regla**:  
  1. Tota tasca de reconeixement òptic (`processar_ocr_document_task`), transcripció fonètica amb Whisper (`transcriure_audio_task`) o compressió d'imatges a format WebP **ha d'anar adscrita explícitament a `queue_media`**:
     ```python
     @celery_app.task(name="app.workers.tasks.processar_ocr_document_task", queue="queue_media")
     def processar_ocr_document_task(file_path: str, empresa_id: str):
         ...
     ```
  2. Les notificacions a Telegram i comprovacions de salut han de romandre aïllades a `queue_critical`.
  3. El contenidor `celery_worker` s'ha d'iniciar sempre consumint les cinc cues amb la prioritat configurada:  
     `-Q queue_critical,queue_documents,queue_sync,queue_media,queue_periodic`.

---

### 📌 Lliçó 3: "Do not forget UploadFile import"
- **Context i Problema Històric**:  
  En afegir nous endpoints per a la pujada d'arxius OCR en mòduls existents (com a `proveidors.py` o `flota.py`), es van produir fallades en temps d'arrencada (`NameError: name 'UploadFile' is not defined` o `name 'File' is not defined`), perquè l'arxiu d'endpoints originalment només manipulava esquemes JSON de Pydantic i no tenia importades aquestes classes de FastAPI. (Evidenciat a `fix_proveidors_imports.py`).
- **Resolució i Regla**:  
  Quan s'afegeixi suport per a fitxers binaris o formularis multipart, cal assegurar sempre la importació explícita des de FastAPI:
  ```python
  from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile, status
  ```
  A més, cal verificar que `python-multipart` estigui instal·lat al contenidor Docker.

---

### 📌 Lliçó 4: "Use get_db_with_tenant_context"
- **Context i Problema Històric**:  
  L'ús indiscriminat de la dependència bàsica `get_db` en lloc de `get_db_with_tenant_context` obria sessions asíncrones de SQLAlchemy a PostgreSQL sense injectar la variable de sessió `app.current_empresa_id`. Això provocava que les consultes a taules protegides per Row Level Security (RLS) retornessin conjunts de dades buits o, en el pitjor dels casos si l'RLS no estava en mode `FORCE`, podien provocar fuites de dades creuades entre empreses inquilines.
- **Resolució i Regla**:  
  1. En tots els endpoints del Copilot, OCR i gestió, la sessió de base de dades s'ha d'obtenir a través de:
     ```python
     from app.core.db import get_db_with_tenant_context
     
     @router.post("/reconciliacio/post-obra")
     async def reconciliar(db: AsyncSession = Depends(get_db_with_tenant_context)):
         ...
     ```
  2. Dins de les tasques de Celery, que no disposen del cicle de dependències de FastAPI, el worker ha d'executar manualment i atòmicament abans de qualsevol consulta:
     ```python
     await session.execute(text(f"SET LOCAL app.current_empresa_id = '{empresa_id}';"))
     ```

---

### 📌 Lliçó 5: "Beware Next.js absolute paths"
- **Context i Problema Històric**:  
  En el frontend de Next.js (panell `/gestio` i aplicació d'operaris `/operari`), es van detectar errors de xarxa perquè certes crides a endpoints del Copilot o del bot feien servir URLs absolutes que assumien l'amfitrió local (`http://localhost:8000/api/...`) o rutes sense el prefix de base requerit per Nginx sota el domini sobirà.
- **Resolució i Regla**:  
  1. Totes les crides `fetch` o clients API han d'utilitzar rutes relatives configurades mitjançant la variable d'entorn `NEXT_PUBLIC_API_URL` o els serveis centralitzats de l'aplicació (`apiClient`), sense hardcodejar mai URLs de domini complet.
  2. S'ha de respectar el subpath `/api/v1/...` configurat en el reverse-proxy d'Nginx.

---

### 📌 Lliçó 6: "Evitar NameError en dependències d'autenticació (valida_uuid vs require_roles)"
- **Context i Problema Històric**:  
  Com es va documentar a `fix_flota_ocr_valida_uuid.py`, es va injectar un paràmetre `tenant: dict = Depends(valida_uuid)` en endpoints d'esborrany OCR quan aquesta funció no estava definida ni importada en aquell mòdul, causant errors `500 Internal Server Error`.
- **Resolució i Regla**:  
  El context de l'empresa s'extreu netament a través de `request.state.empresa_id` (injectat pel middleware de seguretat) i l'autorització es gestiona a nivell de router amb `dependencies=[Depends(require_roles(["BOSS", "SECRETARIA", "ENGINYER"]))]`. No s'han d'inventar dependències fantasmes a les signatures dels endpoints.

---

### 📌 Lliçó 7: "Consistència de signatures del Copilot (agent_prompt_system)"
- **Context i Problema Històric**:  
  A la Spec 012 / Phase 3, es va incorporar la funcionalitat de directrius de sistema personalitzades per empresa (RF-46). En alterar la funció interna `cridar_lm_studio_amb_tools`, es van produir errors de tipus `TypeError: missing required argument 'agent_prompt_system'` en crides auxiliars (resolt a `fix_copilot_signature.py`).
- **Resolució i Regla**:  
  Qualsevol paràmetre afegit a les funcions centrals d'inferència del Copilot ha de declarar un valor per defecte (`agent_prompt_system: Optional[str] = None`) per mantenir compatibilitat retroactiva amb crides de mòduls antics o proves unitàries.

---

### 📌 Lliçó 8: "Prevenció del bucle de recursió infinit en els Backups de Celery Beat"
- **Context i Problema Històric**:  
  La tasca de còpia de seguretat setmanal executada per Celery Beat comprimia de forma recursiva tot el directori `/docs/<empresa_id>/`. Com que el fitxer resultant `backup_<data>.zip` es desava a `/docs/<empresa_id>/backups/`, el procés de compressió intentava comprimir els arxius de còpies anteriors i el propi fitxer en generació, omplint el disc dur del servidor Hetzner en qüestió de minuts per un bucle infinit de recursió.
- **Resolució i Regla**:  
  L'escaneig de directoris de la tasca de backup ha d'excloure programàticament i de forma innegociable la subcarpeta de destí (`backups/`) i qualsevol fitxer amb extensió `.zip` o `.tar.gz`:
  ```python
  if "backups" in root.split(os.sep) or file.endswith((".zip", ".tar.gz", ".pgdump")):
      continue
  ```

---

### 📌 Lliçó 9: "Seguretat del Bot de Telegram (Double Extension & Tokens Efímers)"
- **Context i Problema Històric**:  
  Com que el bot de Telegram accepta fitxers de clients externs, existia el risc de càrrega d'arxius maliciosos o atacs de doble extensió (ex. `factura.pdf.exe`). A més, enviar PDFs de factures directament com a documents de fitxer a Telegram violava la sobirania de dades i impedia traçar qui i quan havia descarregat el document legal.
- **Resolució i Regla**:  
  1. El middleware d'aiogram i el backend analitzen el nom del fitxer i en rebutgen qualsevol que contingui múltiples extensions, contrastant a més els Magic Bytes reals del fitxer binari.
  2. Les factures legals no s'envien mai en binari per Telegram: es transmet un enllaç de descàrrega temporal segellat amb un token JWT vàlid durant un màxim de 24 hores allotjat al servidor sobirà.

---

### 📌 Lliçó 10: "Concurrència i Idempotència en Veri*factu i Estoc"
- **Context i Problema Històric**:  
  En situacions de final de mes, múltiples usuaris d'administració emetien factures de la mateixa sèrie al mateix segon, generant col·lisions en l'encadenament de Hash SHA-256 de la normativa Veri*factu (RD 1007/2023). De manera similar, en assignar obres simultànies, dos enginyers podien reservar les mateixes existències crítiques d'un article de magatzem.
- **Resolució i Regla**:  
  S'ha d'aplicar sempre bloqueig pessimista a PostgreSQL dins de la transacció ACID (`SELECT ... FOR UPDATE`). Això serialitza atòmicament el càlcul del Hash precedent i la deducció d'estoc, rebutjant la segona petició concurrent amb un error controlat i evitant inconsistències a la base de dades.

---

## 3. Resum de Bones Pràctiques per a Noves Implementacions

| Àmbit | Pràctica Obligatòria | Què cal evitar estrictament |
| :--- | :--- | :--- |
| **OCR & Imatges** | Retornar esborrany ràpid o encolar a `queue_media` amb polling de `task_id`. | Bloquejar el fil HTTP amb crides pesades de visió artificial. |
| **Cues de Celery** | Assignar sempre la cua correcta (`queue_critical`, `queue_documents`, `queue_media`...). | Encolar tasques a la cua genèrica per defecte. |
| **Imports FastAPI** | Importar `UploadFile` i `File` quan es manegin peticions `multipart/form-data`. | Donar per fet que estan al scope global del mòdul. |
| **Base de Dades** | Emprar `get_db_with_tenant_context` o injectar `SET LOCAL app.current_empresa_id`. | Utilitzar sessions directes sense context de tenant (RLS bypass). |
| **Bot de Telegram** | Validar dobles extensions, magic bytes i generar enllaços de descàrrega de 24h. | Pujar arxius PDF directament al xat de Telegram. |
| **Copilot & IA** | Declarar "No tinc informació registrada" si no hi ha antecedents (Zero Mock Data). | Al·lucinar peces, preus o números de sèrie en instal·lacions noves. |
| **Facturació Veri*factu** | Utilitzar el patró Outbox i `SELECT FOR UPDATE` per a l'encadenament SHA-256. | Fer crides SOAP síncrones a la seu de l'AEAT durant la generació de la factura. |
