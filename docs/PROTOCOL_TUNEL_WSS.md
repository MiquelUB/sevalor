# Especificació del Protocol del Túnel Invers Natiu WSS (Fases 1, 2 i 3)

> **Fitxers implementats:**
> - Broker multi-tenant + pont Redis 7: [backend/app/services/vault_tunnel.py](../backend/app/services/vault_tunnel.py)
> - Endpoint WebSocket Zero-Trust: [backend/app/api/v1/vault_tunnel.py](../backend/app/api/v1/vault_tunnel.py)
> - Gateways d'emmagatzematge sobirà (Empresa + Superadmin): [backend/app/services/sovereign_storage.py](../backend/app/services/sovereign_storage.py)
> - Copilot IA Local, Subagents, OCR i Bot RAG sobre WSS: [backend/app/services/llm_client.py](../backend/app/services/llm_client.py), [backend/app/services/subagents/dispatcher.py](../backend/app/services/subagents/dispatcher.py), [backend/app/api/v1/gestio/copilot.py](../backend/app/api/v1/gestio/copilot.py)
> - Onboarding B2B 1-clic, diagnòstic i rotació WSS: [backend/app/api/v1/superadmin/tenants.py](../backend/app/api/v1/superadmin/tenants.py)
> - Agent Client WSS i Instal·lador 1-clic: [scripts/client_vault_agent.py](../scripts/client_vault_agent.py), [scripts/install_client_gateway.sh](../scripts/install_client_gateway.sh)
> - Suites de tests reals (Zero Mock): [backend/tests/test_fase1_vault_tunnel_broker.py](../backend/tests/test_fase1_vault_tunnel_broker.py), [backend/tests/test_fase2_client_vault_agent_wss.py](../backend/tests/test_fase2_client_vault_agent_wss.py), [backend/tests/test_fase3_backend_wss_migration.py](../backend/tests/test_fase3_backend_wss_migration.py)
> - ADR vinculat: [docs/ARQUITECTURA_TUNEL_SOBIRA_WSS.md](ARQUITECTURA_TUNEL_SOBIRA_WSS.md)

---

## 1. Endpoint i Handshake Zero-Trust

- **Endpoint:** `WS /api/v1/vault-tunnel/connect` (en producció: `wss://<SEVALOR_TUNNEL_PUBLIC_URL>/api/v1/vault-tunnel/connect`, valor per defecte configurable `https://sevalor-sevalor-backend.80opze.easypanel.host`).
- **Capçaleres obligatòries al handshake:**

| Capçalera | Perfil `EMPRESA` | Perfil `SUPERADMIN` | Validació |
|---|---|---|---|
| `X-Vault-Role` | `EMPRESA` | `SUPERADMIN` | Allowlist estricta (`EMPRESA` \| `SUPERADMIN`). |
| `X-Empresa-ID` | UUID v4 vàlid de l'empresa | **Prohibit** (ha d'estar buit) | Rebuig `4401` (absent/invàlid) o `4403` (enviat com a `SUPERADMIN`). |
| `X-Vault-Token` | `empreses.vault_token` (únic per empresa) | `SUPERADMIN_VAULT_SECRET` | Comparació en temps constant (`hmac.compare_digest`), sense fallback global per a tenants. |
| `X-Agent-Version` | Opcional (màx. 64 caràcters) | Opcional (màx. 64 caràcters) | Telemetria de versió de l'agent. |

### Codis de tancament WebSocket

| Codi | Motiu genèric | Quan s'aplica |
|---|---|---|
| `4401` | `Unauthorized` | Rol/UUID invàlid, token absent o incorrecte, spoofing cross-tenant, empresa inexistent. Mai filtra detalls interns; crea registre `AlertaSeguretat` (`WSS_TUNNEL_AUTH_FAILED`). |
| `4403` | `Forbidden` | Empresa en estat `ELIMINAT` / `SUSPES_PAGAMENT` / `BAIXA`, a la llista negra Redis, `SUPERADMIN` enviant `X-Empresa-ID`, o `SUPERADMIN_VAULT_SECRET` no configurat. Crea registre `AlertaSeguretat`. |
| `4009` | `Replaced` | Una reconnexió vàlida del mateix slot (`empresa:<uuid>` o `superadmin`) substitueix netament la sessió anterior. |
| `4008` | `Heartbeat timeout` | L'agent no ha respost al `ping` dins de `15 s`. |
| `1009` | `Message too big` | Trama JSON superior al límit autoritzat (`50 MB` en base64 + capçalera). |

---

## 2. Protocol de Trames Multiplexades (JSON per `req_id`)

### 2.1 Benvinguda i Salutació Inicial
1. **Servidor → Agent (`welcome`):**
   ```json
   {
     "type": "welcome",
     "target_key": "empresa:<uuid>",
     "role": "EMPRESA",
     "conn_id": "<uuidv4>",
     "heartbeat_interval_s": 25.0,
     "server_time": "2026-11-20T09:00:00+00:00"
   }
   ```
2. **Agent → Servidor (`hello`):**
   ```json
   {
     "type": "hello",
     "agent_version": "sevalor-agent/2.0",
     "health": { "disc_a_lliure_gb": 420.5, "models": ["qwen2.5-vl-7b-instruct"] }
   }
   ```

### 2.2 Petició / Resposta Multiplexada
- **Servidor → Agent (`request`):**
  ```json
  {
    "type": "request",
    "req_id": "<uuidv4>",
    "action": "json_put",
    "payload": { "subcarpeta": "01_clients/fitxes", "item_id": "cli_1", "content": {} },
    "timeout_s": 10.0
  }
  ```
- **Agent → Servidor (`response`):**
  ```json
  { "type": "response", "req_id": "<uuidv4>", "ok": true, "data": { "saved": "..." } }
  ```
  En cas d'error controlat a l'agent:
  ```json
  {
    "type": "response",
    "req_id": "<uuidv4>",
    "ok": false,
    "error_code": "PATH_TRAVERSAL",
    "status_code": 400,
    "detail": "Ruta fora del disc autoritzat."
  }
  ```

### 2.3 Allowlist d'Accions Autoritzades (`ALLOWED_TUNNEL_ACTIONS`)
Qualsevol acció fora d'aquesta llista és rebutjada amb `ValueError` abans d'enviar res al túnel:
- **Sistema:** `health`, `init_folders`, `backup_daily`, `ping`
- **Entitats JSON:** `json_put`, `json_get_list`, `json_delete`
- **Fitxers binaris (màx. 50 MB + integritat SHA-256):** `file_put`, `file_get`, `file_rename`, `file_delete`
- **Copilot IA Local (`127.0.0.1:1234` del PC):** `llm_models`, `llm_chat` (timeout fins a `120 s`)

### 2.4 Heartbeat Bidireccional (`ping` / `pong`)
- Cada **25 s**, el servidor envia `{"type": "ping", "req_id": "...", "action": "ping", "payload": {"ts": "..."}}`.
- L'agent respon `{"type": "pong", "req_id": "...", "health": {...}}` dins de **15 s**, refrescant la clau de presència Redis (TTL `75 s`).

---

## 3. Auto-Inicialització i Auto-Drenatge en Connectar

Quan un PC d'**`EMPRESA`** completa el handshake WSS, `_post_connect_empresa_bootstrap` executa en segon pla (sense bloquejar el bucle de recepció ni retenir connexions PostgreSQL obertes):
1. Executa `init_folders` per crear físicament les **38 carpetes oficials + mirall Disc B** al disc del client.
2. Actualitza a PostgreSQL `empreses`:
   - `disc_dur_url = "wss-tunnel://<empresa_id>"`
   - `node_ia_url = "wss-tunnel://<empresa_id>"`
   - `node_ia_actiu = True` únicament en la primera connexió WSS quan `feature_copilot_ia = True` (respecta qualsevol desactivació explícita posterior).
3. Assegura les fitxes inicials al disc si encara no existeixen (`empresa.json`, `boss.json` amb signatura HMAC anti-barreges, i `09_copilot_ia/prompt_sistema/system_prompt.txt`).
4. Drena automàticament tots els paquets xifrats **`SVENC1:`** retinguts a la cua de trànsit de Hetzner cap al disc físic del client i fa **`unlink` immediat** a Hetzner.

Quan connecta **`SUPERADMIN`**, s'executa automàticament `init_folders` per garantir les **20 carpetes oficials** del Disc Dur de Superadmin.

---

## 4. Pont Cross-Process via Redis 7 (`celery_worker`, `celery_beat`, `bot`)

| Clau Redis | Tipus | TTL | Funció |
|---|---|---|---|
| `sevalor:tunnel:online:<target_key>` | String (JSON) | `75 s` | Presència activa del túnel (`conn_id`, `role`, `pid`, `connected_at`, `health`), refrescada a cada heartbeat. |
| `sevalor:tunnel:rpc:<target_key>` | List (FIFO) | `timeout + 15 s` | Cua de peticions RPC enviades per processos externs (`RPUSH`) i consumides en paral·lel (`BLPOP`) pel procés `uvicorn` propietari del WebSocket. |
| `sevalor:tunnel:reply:<req_id>` | List (1 elem.) | `60 s` | Canal efímer de resposta per `req_id` que llegeix el procés origen (`BLPOP` amb timeout) i esborra immediatament. |

- Si el túnel és en memòria del mateix procés `uvicorn`, `VaultTunnelBroker.call()` usa el camí directe per `asyncio.Future` (latència sub-mil·lisegon).
- Si la crida ve de `celery_worker`, `celery_beat` o `bot`, `VaultTunnelBroker.call()` detecta la presència a Redis i enruta transparentment pel pont Redis cap al procés `uvicorn` que sosté el WebSocket.

---

## 5. Agent Client Sobirà WSS i Instal·lador 1-Clic (Fase 2)

> **Fitxers implementats:**
> - Daemon sortint WSS: [scripts/client_vault_agent.py](../scripts/client_vault_agent.py) (`sevalor-wss-agent/3.0.0`)
> - Instal·lador 1-clic `systemd`: [scripts/install_client_gateway.sh](../scripts/install_client_gateway.sh)
> - Tests reals OS subprocess + auto-reconnexió: [backend/tests/test_fase2_client_vault_agent_wss.py](../backend/tests/test_fase2_client_vault_agent_wss.py)

### 5.1 Garanties de l'Agent (`scripts/client_vault_agent.py`)
- **Zero ports entrants oberts:** eliminats completament FastAPI, Uvicorn i els ports `9001`/`9002`. Només requereix `websockets>=13.0` i `httpx>=0.27.0`.
- **Reconnexió automàtica exponencial:** `1 s → 2 s → 4 s → ... → 30 s` + jitter aleatori (`0..0.5 s`), amb reinici del backoff després de connexions estables i backoff llarg (`15 s`) davant codis `4401`/`4403`.
- **Execució concurrent de peticions:** cada `request` s'executa en tasca asíncrona independent (`asyncio.create_task`) perquè una inferència `llm_chat` llarga no bloquegi mai `ping`/`pong`, `health`, `json_put` ni `file_put`.
- **Escriptura atòmica i seguretat local:** escriptures via `.tmp` + `os.replace`, validació estricta contra Path Traversal (`is_relative_to`, profunditat mínima >= 1 per carpetes i >= 2 per fitxers), verificació SHA-256 i límit `50 MB`. Mai filtra `X-Vault-Token` cap al LM Studio / Ollama local (`127.0.0.1:1234`).
- **Backup diari dual (Disc A / Disc B):** `backup_daily` alterna Disc A (dies senars) i Disc B (`backups_jornada`, dies parells) generant ZIP + manifest `.sha256`.

### 5.2 Instal·lació 1-Clic (`scripts/install_client_gateway.sh`)
- **Empresa (38 carpetes + mirall B):**
  ```bash
  bash scripts/install_client_gateway.sh \
    --server https://sevalor-sevalor-backend.80opze.easypanel.host \
    --role EMPRESA \
    --empresa-id <UUID_EMPRESA> \
    --token <svlt_...> \
    --disk-a /ruta/al/disc_exclusiu \
    --llm-url http://127.0.0.1:1234
  ```
- **Superadmin (20 carpetes + mirall B):**
  ```bash
  bash scripts/install_client_gateway.sh \
    --server https://sevalor-sevalor-backend.80opze.easypanel.host \
    --role SUPERADMIN \
    --token <SUPERADMIN_VAULT_SECRET> \
    --disk-a /media/akaun/Project_1/Sevalor_Superadmin_docs \
    --llm-url http://127.0.0.1:1234
  ```
- Opcions prohibides per ADR-001 (`--tunnel-token`, `--port`, `--host`) són rebutjades explícitament amb codi de sortida `2`. L'arxiu `.env` es desa amb `chmod 600`.

---

## 6. Migració Total del Backend i Endpoints REST Associats (Fase 3)

### 6.1 Emmagatzematge Sobirà i Backup (`SovereignStorageGateway` i `SuperadminStorageGateway`)
- **Zero `HTTP_VAULT` i zero `httpx`:** totes les operacions sobre discos d'empresa (`empresa:<uuid>`) i de Superadmin (`superadmin`) viatgen pel `vault_tunnel_broker`:
  - `WSS_TUNNEL`: quan l'agent WSS del PC està `ONLINE`, lectura/escriptura directa sobre el disc físic + verificació roundtrip (`verificar_roundtrip_wss`).
  - `OFFLINE_TRANSIT` (empreses): quan el PC d'una empresa està temporalment desconnectat, les escriptures es xifren amb **`SVENC1:`** a la cua de trànsit i es drenen automàticament amb `unlink` immediat quan el PC reconnecta pel WSS.
  - `SuperadminStorageGateway`: opera sobre `SUPERADMIN_TARGET_KEY` (`superadmin`); quan el túnel Superadmin està desconnectat i no hi ha muntatge local configurat, retorna `503 NODE_SUPERADMIN_OFFLINE` (sense escriure mai fitxers de negoci al disc de Hetzner).
- **Backup diari dual (`executar_backup_sobira_empresa`):** invoca l'acció `backup_daily` pel túnel WSS generant el paquet `.zip` i el manifest `.sha256` tant a `Disc A` com al mirall `Disc B`.

### 6.2 Onboarding B2B 1-Clic, Verificació i Rotació de Credencials (`/api/v1/superadmin/tenants`)
- **`POST /api/v1/superadmin/tenants/onboarding`:**
  - Rebutja explícitament amb **`422 TUNEL_HTTP_PROHIBIT`** qualsevol `disc_dur_url` o `node_ia_url` amb esquema `http://` o `https://` (`ADR-001`).
  - Crea l'empresa immediatament encara que el PC del client estigui apagat, assignant `vault_token` (`svlt_...`), `disc_dur_url = "wss-tunnel://<id>"` i `node_ia_url = "wss-tunnel://<id>"`.
  - Encola xifrats (`SVENC1:`) els 4 arxius fundacionals (`empresa.json`, `boss.json`, `boss_<id>.json`, `09_copilot_ia/prompt_sistema/system_prompt.txt`) perquè es drenin automàticament juntament amb les 38 carpetes en l'instant que el PC connecta.
  - Retorna `tunnel_server_url` (per defecte `https://sevalor-sevalor-backend.80opze.easypanel.host`, configurable via `SEVALOR_TUNNEL_PUBLIC_URL`) i `comanda_install_wss` llesta per copiar i executar en 1 clic.
- **`GET /api/v1/superadmin/tenants/{empresa_id}/tunnel-status`:**
  - Retorna telemetria en viu del túnel WSS (`tunnel_online`, `tunnel_status`, `connected_at`, `last_pong_at`, `agent_version`, `cua_transit_pendent`, `health`).
- **`POST /api/v1/superadmin/tenants/verificar-disc-dur` i `POST /api/v1/superadmin/tenants/verificar-node-ia`:**
  - Rebutgen qualsevol URL `http(s)://` amb `422 TUNEL_HTTP_PROHIBIT`.
  - Executen sonda `health`, roundtrip real d'escriptura/lectura/esborrat sobre el disc físic (`DISC_OPERATIU`) i descoberta real de models IA (`llm_models`) pel túnel WSS (`CONNEXIO_ESTABLERTA` / `TUNEL_OFFLINE` / `LLM_OFFLINE`).
- **`POST /api/v1/superadmin/tenants/{empresa_id}/rotar-vault-token` (i àlies `/vault-token/rotate`):**
  - Rota criptogràficament `empreses.vault_token`, invoca `await vault_tunnel_broker.disconnect(empresa_target_key(empresa_id), code=4401, reason="Token rotated")` per tancar a l'instant la sessió WSS antiga (`sessio_anterior_tancada: true`) i retorna la nova `comanda_install_wss`.

### 6.3 Copilot IA Local, Subagents, OCR i Bot RAG (`/api/v1/gestio/copilot`)
- Totes les inferències (`llm_client.py`, `subagents/dispatcher.py`, `ocr_service.py`, `telegram_service.py`, `pressupostos.py`, `copilot.py`) viatgen exclusivament per `vault_tunnel_broker.call_llm_chat` i `call_llm_models`.
- **Codis de diagnòstic deterministes (`GET /api/v1/gestio/copilot/ia-status`, `GET /api/v1/gestio/copilot/estat-node`, `POST /api/v1/gestio/copilot/xat`):**
  - `FEATURE_COPILOT_DESACTIVAT`: el mòdul Copilot no està contractat per l'empresa.
  - `NODE_IA_INACTIU`: el node IA està desactivat per Superadmin.
  - `TUNEL_OFFLINE`: l'agent WSS del PC de l'empresa no està connectat al broker.
  - `LLM_OFFLINE`: el túnel WSS del PC està connectat (`tunnel_online: true`), però LM Studio / Ollama (`127.0.0.1:1234`) no respon o no té cap model carregat.
  - `ONLINE` (`ORDINADOR_DEDICAT_ACTIU`): túnel WSS actiu + motor LLM local operatiu amb llista de models verificada i latència mesurada en mil·lisegons.


