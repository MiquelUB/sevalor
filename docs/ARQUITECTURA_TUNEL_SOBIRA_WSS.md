# ADR-001: Arquitectura de Túnel Invers Natiu WSS Sobirà (Prohibició del Túnel HTTP/HTML Entrant i Zero Dualitat)

> **Estat:** Ratificat — Fase 0, Fase 1, Fase 2 i Fase 3 implementades i verificades (2026-11-20)  
> **Àmbit:** Copilot IA Local, Discos Durs Exclusius d'Empresa (38 carpetes + mirall B) i Disc Dur Exclusiu de Superadmin (20 carpetes + mirall B).  
> **Protocol de trames, Agent Client i Endpoints Backend (Fases 1–3):** [docs/PROTOCOL_TUNEL_WSS.md](PROTOCOL_TUNEL_WSS.md)  
> **Normativa vinculada:** [constitution.md](../constitution.md) (Principis V, IX i X), [AGENTS.md](../AGENTS.md), [plan.md](../plan.md).

---

## 1. Decisió Arquitectònica Taxativa: El Túnel HTTP/HTML Entrant NO ÉS UNA OPCIÓ

Queda **descartat i prohibit definitivament** qualsevol esquema basat en connexions **HTTP/HTML entrants** iniciades des del servidor Hetzner cap a l'ordinador d'una empresa o del Superadmin, incloent-hi:

- **Prohibit:** Exposar ports HTTP locals (`http://127.0.0.1:9001`, `http://127.0.0.1:9002`, `http://127.0.0.1:1234`, `http://host.docker.internal:9001`) com a transport entre Hetzner i els PCs.
- **Prohibit:** Crear túnels externs manuals de tercers per cada empresa (Cloudflare Tunnel, ngrok, subdominis DNS de túnel per client, o obertura de ports entrants als routers de les empreses).
- **Prohibit:** Mantenir una **dualitat** de transports (`http://...` + `wss://...`) ni fallbacks silenciosos a `LOCAL_FS` (`/tmp/sevalor_client_disks` o `/data/disc_*`) dins el servidor Hetzner.
- **Prohibit:** Escriure dades de negoci, fitxers operatius, documents ni dades de CRM/facturació SaaS al disc permanent de Hetzner.

### Per què el túnel HTTP/HTML entrant i Cloudflare trenquen la filosofia del SaaS?
1. **Inviable per escalar un SaaS:** Obligar a configurar manualment un Cloudflare Tunnel, un registre DNS o regles de router per cada nova empresa trenca l'automatització del SaaS (inviable per a 50, 200 o 1.000 empreses).
2. **Trencament de sobirania UE (Constitució §2.IX):** Introduir Cloudflare o túnels de tercers nord-americans com a intermediari obligatori contradiu l'arquitectura 100% sobirana europea sobre Hetzner + PC del client.
3. **Dualitat font d'errors silenciosos:** Tenir un camí HTTP local (`127.0.0.1` / `host.docker.internal` / `bridge_lm_studio.py`) per desenvolupament i un altre per producció genera falsos positius en tests, configuracions que es perden en recarregar, sondes que responen al navegador local però fallen al servidor, i arxius que mai arriben al disc dur real del client.

---

## 2. Opció Escollida: Túnel Invers Natiu per WebSocket (`WSS`) Únic dins de FastAPI (Hetzner)

Tots els entorns (desenvolupament local, tests automatitzats i producció a Hetzner) utilitzen **exactament el mateix i únic protocol**:

```text
[PC Exclusiu Empresa A]  ──(WSS sortint port 443, empresa_id_A + vault_token_A)──▶ ┌───────────────────────────────────────┐
  • Disc A (38 carpetes + Mirall B)                                                 │   Hetzner Cloud UE (Passarel·la Cega) │
  • LM Studio / Ollama local (127.0.0.1:1234)                                       │   FastAPI: WS /api/v1/vault-tunnel/   │
                                                                                    │            connect                    │
[PC Exclusiu Empresa B]  ──(WSS sortint port 443, empresa_id_B + vault_token_B)──▶ │   • VaultTunnelBroker aïllat per ID   │
  • Disc B (38 carpetes + Mirall B)                                                 │   • Pont Redis 7 (Celery / Bot)       │
  • LM Studio / Ollama local (127.0.0.1:1234)                                       │   • Cua trànsit xifrada SVENC1:       │
                                                                                    │     (auto-drenatge + unlink immediat) │
[PC Propietari Superadmin] ─(WSS sortint port 443, SUPERADMIN + secret)──────────▶ └───────────────────────────────────────┘
  • Disc Superadmin (20 carpetes + Mirall B)
  • LM Studio local (127.0.0.1:1234)
```

### Com funciona l'opció escollida
1. **Connexió SORTINT des del PC cap a Hetzner:** `client_vault_agent.py` actua com a daemon client lleuger (sense obrir cap port TCP ni servidor HTTP entrant) que obre una connexió **WSS xifrada TLS (port 443)** cap a `wss://<backend-hetzner>/api/v1/vault-tunnel/connect`.
2. **Autenticació Zero-Trust al handshake:**
   - Perfil `EMPRESA`: presenta `X-Vault-Role: EMPRESA`, `X-Empresa-ID: <uuid>` i `X-Vault-Token: <svlt_...>`. Hetzner valida contra `empreses.vault_token` amb comparació en temps constant (`hmac.compare_digest`) i comprova que l'empresa no estigui suspesa ni eliminada.
   - Perfil `SUPERADMIN`: presenta `X-Vault-Role: SUPERADMIN` i `X-Vault-Token: <SUPERADMIN_VAULT_SECRET>`, validat en temps constant.
3. **Broker multi-tenant estrictament aïllat (`VaultTunnelBroker`):**
   - Cada empresa ocupa un canal exclusiu `empresa:<uuid>`; Superadmin ocupa el canal `superadmin`.
   - Totes les operacions de **Disc Dur** (`json_put`, `json_get_list`, `json_delete`, `file_put`, `file_get`, `file_rename`, `file_delete`, `init_folders`, `health`) i de **Copilot IA Local** (`llm_models`, `llm_chat`) es multiplexen per `req_id` sobre el canal WSS exclusiu d'aquella empresa.
   - Les tasques asíncrones (`celery_worker`, `celery_beat`, `bot`) despatxen de manera transparent cap al túnel WSS sostingut per `uvicorn` a través d'un **pont RPC sobre Redis 7**.
4. **Sobirania absoluta dels discos durs (Zero-Storage Hetzner):**
   - Tota la informació operativa de cada empresa (clients, proveïdors, estoc, factures, plànols, OTs, incidències, flota, operaris, memòria i prompts del Copilot) es guarda **exclusivament al disc dur de l'empresa**.
   - Tota la informació comercial i legal del propietari del SaaS (fitxes B2B d'empreses, llicències, facturació SaaS, CRM, rascador, suport) es guarda **exclusivament al disc dur de Superadmin**.
   - Si el PC d'una empresa està temporalment apagat (p. ex. de nit mentre un operari sincronitza), Hetzner reté únicament un paquet efímer xifrat amb **`SVENC1:`** a la cua de trànsit i executa **drenatge automàtic + `unlink` immediat** tan bon punt l'agent del PC es reconnecta pel WSS.

---

## 3. Problemes Concrets que Aquesta Solució Ha de Resoldre

| # | Problema detectat anteriorment | Com el resol el Túnel Invers Natiu WSS |
|---|---|---|
| **1** | **Inviabilitat SaaS amb Cloudflare Tunnel per empresa** (calia crear un túnel i subdomini manual per cada nou client). | Zero Cloudflare i zero DNS per PC. Cada empresa nova rep el seu `(empresa_id, vault_token)` i una comanda d'instal·lació 1-clic; el seu PC es connecta directament al backend de Hetzner. |
| **2** | **Bloqueig per NAT / router d'oficina / IP dinàmica** (Hetzner no podia arribar a `127.0.0.1:1234` ni `9001` del PC local). | La connexió WSS és **sortint** (port 443), travessa qualsevol router, NAT, CGNAT o IP dinàmica sense obrir ports entrants. |
| **3** | **Connexió que "es desactiva" en sortir de la pàgina o recarregar** i pèrdua d'estat `node_ia_actiu` / `node_ia_url`. | L'estat real del túnel ve determinat per la sessió WSS viva al servidor (`ONLINE`/`OFFLINE` real amb heartbeat cada 25 s) i l'agent es reconnecta sol automàticament després de talls o reinicis. |
| **4** | **Arxius mai creats a les carpetes físiques del disc dur del client** (o escrits per error a `/tmp` dins Hetzner per fallback `LOCAL_FS`). | Eliminat el fallback `LOCAL_FS` a Hetzner. Tota lectura/escriptura passa obligatòriament pel WSS cap al disc físic exclusiu de l'empresa (o cua xifrada `SVENC1:` si el PC és apagat, drenada en reconnectar). |
| **5** | **Dualitat entre desenvolupament (`http://host.docker.internal` / `bridge_lm_studio.py`) i producció (Hetzner)** provocant falsos positius als tests. | Desmuntatge total del túnel HTTP entrant i dels ponts Docker. Un únic protocol WSS a tots els entorns: el que passa els tests és exactament el que corre a Hetzner. |
| **6** | **Risc de contaminació creuada entre empreses o amb Superadmin** (un disc o un Copilot barrejant dades). | Cada empresa només té el seu canal `empresa:<uuid>` autenticat pel seu `vault_token` únic, apuntant al seu disc dur exclusiu i al seu LM Studio local exclusiu. Superadmin té el seu canal i disc propis separats. |
| **7** | **Dependència de tercers fora de la UE** (Cloudflare / núvols públics). | 100% sobirà europeu: trànsit directe xifrat TLS entre el PC del client i el servidor Hetzner (Alemanya). |
