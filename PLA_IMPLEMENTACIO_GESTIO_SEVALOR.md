# Pla d'Implementació Integral (Arquitectura Zero-Storage Total) — Túnel Copilot, Disc de Superadmin, Disc d'Empresa, Subagents Sobirans, `/gestio` i Tests per Bloc

> **Normativa obligatòria:** [AGENTS.md](file:///media/akaun/Project_1/SEVALOR/AGENTS.md), [constitution.md](file:///media/akaun/Project_1/SEVALOR/constitution.md), [ADR-001 Túnel Sobirà WSS](file:///media/akaun/Project_1/SEVALOR/docs/ARQUITECTURA_TUNEL_SOBIRA_WSS.md), [AUDITORIA_GESTIO_SEVALOR.md](file:///media/akaun/Project_1/SEVALOR/AUDITORIA_GESTIO_SEVALOR.md) i [Auditoria_i_Normativa_Tests_Backend.md](file:///media/akaun/Project_1/SEVALOR/sevalor_AgentV2/docs/sdd_sevalor_legacy/Auditoria_i_Normativa_Tests_Backend.md).  
> **Skills obligatòries abans de tocar codi:** `supabase-postgres-best-practices`, `security-and-hardening`, `security-review`, `frontend-design`, `systematic-debugging`.

> [!IMPORTANT]
> **ACTUALITZACIÓ ARQUITECTÒNICA OBLIGATÒRIA (2026-11-20 — ADR-001, ZERO DUALITAT):**  
> **El túnel HTTP/HTML entrant (`http://127.0.0.1:9001`, `http://host.docker.internal:9001`, `http://host.docker.internal:9002`, `bridge_lm_studio.py`, Cloudflare Tunnel per empresa i qualsevol fallback `LOCAL_FS` a Hetzner) NO ÉS UNA OPCIÓ i queda formalment descartat i prohibit.**  
> Mantenir dualitat entre HTTP entrant i WebSocket genera errors, falsos positius als tests i trenca l'escalabilitat i la sobirania UE del SaaS.
>
> **Opció adoptada en exclusiva (tots els entorns: producció Hetzner, local i tests):** **Túnel Invers Natiu per WebSocket (`WSS` sortint per port 443)** des de `client_vault_agent.py` a cada PC d'empresa i del Superadmin cap a `WS /api/v1/vault-tunnel/connect` dins del propi FastAPI de Hetzner, amb broker multi-tenant aïllat (`VaultTunnelBroker`) i pont cross-process via Redis 7 per a Celery/Bot.
>
> **Problemes concrets que resol obligatòriament:**
> 1. Escalabilitat SaaS real (1 a 1.000+ empreses sense crear túnels Cloudflare ni subdominis manuals per client).
> 2. Sobirania total dels discos durs (les dades i fitxers de cada empresa viuen exclusivament al seu disc dur local, i les del Superadmin al seu; zero retenció a Hetzner).
> 3. Travessar NAT, CGNAT, tallafocs i IPs dinàmiques d'oficina sense obrir cap port entrant al router del client.
> 4. Aïllament infranquejable 1 Empresa = 1 Copilot IA local exclusiu (`127.0.0.1:1234` intern del seu PC) + 1 Disc Dur exclusiu (38 carpetes + mirall B).
> 5. Connexió persistent i auto-reconnexió resilient (sense desactivar-se en canviar de pàgina) amb auto-drenatge i `unlink` immediat de la cua xifrada `SVENC1:`.
> 6. Paritat 100% real entre tests i producció (desmuntant primer tot el túnel HTTP antic abans d'implantar el WSS únic).  
>
> Els fragments del Bloc 0 i Bloc 1 d'aquest document que feien referència a `:9001`/`:9002` HTTP, `bridge_lm_studio.py` o `HTTP_VAULT` queden **substituïts** per [docs/ARQUITECTURA_TUNEL_SOBIRA_WSS.md](file:///media/akaun/Project_1/SEVALOR/docs/ARQUITECTURA_TUNEL_SOBIRA_WSS.md).

---

## Principi Arquitectònic Rector (Hetzner = Passarel·la Cega Zero-Storage + Túnel Invers Natiu WSS)

Per garantir la màxima rendibilitat del SaaS i el compliment estricte de la protecció de dades:
1. **Servidor Hetzner (Passarel·la Cega, Broker WSS i Buffer Efímer Xifrat):**
   - **Només conserva de forma permanent:** `empresa_id`, `subdomini`/`domini_custom`, colors HSL de marca, flags de funcionalitat (`feature_*`, `estat_pagament`), identificador de canal WSS (`wss-tunnel://<empresa_id>`, `vault_token`), i credencials mínimes d'accés pseudonimitzades (`usuari_id`, `empresa_id`, `rol`, índexs HMAC cecs de login `email_hmac`/`ident_hmac`, `password_hash`, `pin_hash`, `secret_2fa`).
   - **Zero dades de negoci, zero PII en text pla, zero facturació SaaS B2B, zero CRM, zero rascador de prospecció.**
   - Quan l'operari (`/operari`) no té cobertura, desa al mòbil xifrat amb **AES-GCM 256 (IndexedDB)**; en recuperar cobertura, ho envia a Hetzner. Si el PC de l'empresa té el túnel **WSS** actiu, Hetzner ho reenvia al moment sense desar res al disc; si el PC està apagat, ho reté xifrat amb **`SVENC1:`** a `transit_queue/<empresa_id>` i executa **`unlink` + purga immediata** tan bon punt el PC es reconnecta pel WSS i drena el paquet al seu disc dur.
2. **Disc Dur Dedicat de cada Empresa** (ex: `/media/akaun/Project_1/Sevalormante_docs` via **túnel invers WSS sortint** amb `empresa_id` + `vault_token`): Emmagatzema el 100% de les dades operatives en **38 carpetes oficials** (`01_clients` fins a `11_configuracio_i_backups`) + mirall B i alimenta en exclusiva els **8 Subagents del Copilot** mitjançant el LM Studio local del propi PC.
3. **Disc Dur Dedicat del Superadmin** (al teu ordinador: `/media/akaun/Project_1/Sevalor_Superadmin_docs` via **túnel invers WSS sortint** amb `role=SUPERADMIN` + `SUPERADMIN_VAULT_SECRET` + mirall B): Emmagatzema el **CRM comercial, rascador de prospecció, facturació B2B SaaS, correu/suport i fitxes completes de clients del SaaS** en **20 carpetes oficials**.

---

## BLOC 0 — Passarel·la Unificada (`client_vault_agent.py`), Creació de Carpetes de Superadmin i Empresa, i Pont Docker

### 0.1 Fitxers afectats
- [client_vault_agent.py](file:///media/akaun/Project_1/SEVALOR/scripts/client_vault_agent.py)
- [bridge_lm_studio.py](file:///media/akaun/Project_1/SEVALOR/scripts/bridge_lm_studio.py)
- [sovereign_storage.py](file:///media/akaun/Project_1/SEVALOR/backend/app/services/sovereign_storage.py)
- [install_client_gateway.sh](file:///media/akaun/Project_1/SEVALOR/scripts/install_client_gateway.sh)

### 0.2 Implementació de Carpetes de Superadmin (`20`) i Mode Dual (`EMPRESA` / `SUPERADMIN`)

Afegir a [client_vault_agent.py](file:///media/akaun/Project_1/SEVALOR/scripts/client_vault_agent.py) el perfil `SEVALOR_VAULT_ROLE=SUPERADMIN|EMPRESA` amb les **20 carpetes del Superadmin**, exposant per al Superadmin l'endpoint de creació/inicialització de ruta de carpetes:

```python
# Afegeix a scripts/client_vault_agent.py (i replica el diccionari a sovereign_storage.py)
VAULT_ROLE = os.getenv("SEVALOR_VAULT_ROLE", "EMPRESA").strip().upper()

CARPETES_SUPERADMIN: List[str] = [
    "01_tenants_b2b/fitxes_empreses",
    "01_tenants_b2b/llicencies_i_contractes",
    "02_facturacio_saas/factures_b2b_json",
    "02_facturacio_saas/factures_b2b_pdf",
    "02_facturacio_saas/factures_b2b_xml",
    "03_crm_comercial/leads",
    "03_crm_comercial/oportunitats",
    "03_crm_comercial/activitats",
    "04_rascador_prospeccio/tasques",
    "04_rascador_prospeccio/candidats",
    "04_rascador_prospeccio/criteris_feedback",
    "04_rascador_prospeccio/exclusions_rgpd",
    "05_correu_i_suport/missatges",
    "05_correu_i_suport/tiquets_suport",
    "06_telemetria_i_seguretat/auditoria",
    "06_telemetria_i_seguretat/alertes_seguretat",
    "06_telemetria_i_seguretat/certificats_baixa",
    "07_copilot_superadmin/prompt_sistema",
    "07_copilot_superadmin/memoria_ia",
    "08_backups_superadmin/backups_locals",
]

MAPA_CARPETES_SUPERADMIN: Dict[str, str] = {
    "tenants_fitxes": "01_tenants_b2b/fitxes_empreses",
    "tenants_llicencies": "01_tenants_b2b/llicencies_i_contractes",
    "saas_factures_json": "02_facturacio_saas/factures_b2b_json",
    "saas_factures_pdf": "02_facturacio_saas/factures_b2b_pdf",
    "saas_factures_xml": "02_facturacio_saas/factures_b2b_xml",
    "crm_leads": "03_crm_comercial/leads",
    "crm_oportunitats": "03_crm_comercial/oportunitats",
    "crm_activitats": "03_crm_comercial/activitats",
    "rascador_tasques": "04_rascador_prospeccio/tasques",
    "rascador_candidats": "04_rascador_prospeccio/candidats",
    "rascador_criteris": "04_rascador_prospeccio/criteris_feedback",
    "rascador_exclusions": "04_rascador_prospeccio/exclusions_rgpd",
    "correu_missatges": "05_correu_i_suport/missatges",
    "suport_tiquets": "05_correu_i_suport/tiquets_suport",
    "auditoria": "06_telemetria_i_seguretat/auditoria",
    "alertes_seguretat": "06_telemetria_i_seguretat/alertes_seguretat",
    "baixes_rgpd": "06_telemetria_i_seguretat/certificats_baixa",
    "copilot_prompt": "07_copilot_superadmin/prompt_sistema",
    "copilot_memoria": "07_copilot_superadmin/memoria_ia",
    "backups": "08_backups_superadmin/backups_locals",
}

def inicialitzar_estructura_disc() -> List[str]:
    """Crea físicament les 38 carpetes d'Empresa o les 20 de Superadmin + Disc B mirall."""
    carpetes = CARPETES_SUPERADMIN if VAULT_ROLE == "SUPERADMIN" else CARPETES_OFICIALS
    for sub in carpetes:
        (VAULT_PRIMARY_A / sub).mkdir(parents=True, exist_ok=True)
    (VAULT_SECONDARY_B / "backups_jornada").mkdir(parents=True, exist_ok=True)
    return carpetes

@app.post("/admin/inicialitzar-ruta", dependencies=[Depends(verificar_token_passarella)])
async def endpoint_inicialitzar_ruta_carpetes() -> Dict[str, Any]:
    """Permet al Superadmin disparar la creació física completa de l'arbre de carpetes via túnel."""
    carpetes = inicialitzar_estructura_disc()
    return {
        "status": "OK",
        "role": VAULT_ROLE,
        "vault_root": str(VAULT_PRIMARY_A),
        "carpetes_count": len(carpetes),
        "carpetes": carpetes,
    }
```

**Actualització de [bridge_lm_studio.py](file:///media/akaun/Project_1/SEVALOR/scripts/bridge_lm_studio.py) (ports `1234`, `9001` Empresa, `9002` Superadmin):**

```python
TARGET_HOST = "127.0.0.1"
TARGET_PORTS = (1234, 9001, 9002)

def handle_client(client_sock, target_port: int):
    try:
        remote_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        remote_sock.connect((TARGET_HOST, target_port))
        threading.Thread(target=pipe, args=(client_sock, remote_sock), daemon=True).start()
        threading.Thread(target=pipe, args=(remote_sock, client_sock), daemon=True).start()
    except Exception:
        client_sock.close()

def main():
    ips = get_bridge_ips()
    for ip in ips:
        for port in TARGET_PORTS:
            threading.Thread(target=listen_on_ip, args=(ip, port), daemon=True).start()
    while True:
        time.sleep(1)
```

**Arrencada dels dos agents al teu equip:**

```bash
# 1. Agent d'Empresa (Sevalormante SL -> port 9001 -> /media/akaun/Project_1/Sevalormante_docs)
SEVALOR_VAULT_ROLE=EMPRESA \
SEVALOR_VAULT_SECRET="svlt_9f7cd7bb26a19bd17dc15f8bd2626c1000cbb3f8bf373d8809eff83e64e91e3a" \
SEVALOR_VAULT_PATH_A="/media/akaun/Project_1/Sevalormante_docs" \
SEVALOR_VAULT_PATH_B="/media/akaun/Project_1/Sevalormante_docs_backup_B" \
SEVALOR_LOCAL_LLM_URL="http://127.0.0.1:1234" \
PORT=9001 HOST=127.0.0.1 python3 scripts/client_vault_agent.py &

# 2. Agent de Superadmin (CRM/Facturació/Rascador -> port 9002 -> /media/akaun/Project_1/Sevalor_Superadmin_docs)
SEVALOR_VAULT_ROLE=SUPERADMIN \
SEVALOR_VAULT_SECRET="${SUPERADMIN_VAULT_SECRET}" \
SEVALOR_VAULT_PATH_A="/media/akaun/Project_1/Sevalor_Superadmin_docs" \
SEVALOR_VAULT_PATH_B="/media/akaun/Project_1/Sevalor_Superadmin_docs_backup_B" \
SEVALOR_LOCAL_LLM_URL="http://127.0.0.1:1234" \
PORT=9002 HOST=127.0.0.1 python3 scripts/client_vault_agent.py &
```

**Afegir a [sovereign_storage.py](file:///media/akaun/Project_1/SEVALOR/backend/app/services/sovereign_storage.py) un `SuperadminStorageGateway` específic (CRM, Facturació SaaS, Rascador i Fitxes B2B fora d'Hetzner):**

```python
class SuperadminStorageGateway:
    """Passarel·la exclusiva del propietari SaaS cap al seu disc dur local (/media/akaun/Project_1/Sevalor_Superadmin_docs)."""

    @staticmethod
    def _resolve_target() -> Tuple[str, str, Optional[str]]:
        url = os.getenv("SUPERADMIN_VAULT_URL", "http://host.docker.internal:9002").strip()
        secret = os.getenv("SUPERADMIN_VAULT_SECRET", "").strip()
        if url.startswith(("http://", "https://")):
            effective = resolve_effective_node_url(url) or url
            return ("HTTP_VAULT", effective.rstrip("/"), secret)
        inicialitzar_arbre_carpetes_superadmin(url)
        return ("LOCAL_FS", str(Path(url).resolve()), None)

    @classmethod
    async def inicialitzar_rutes_superadmin(cls, ruta_personalitzada: Optional[str] = None) -> Dict[str, Any]:
        """Crea les 20 carpetes oficials del Superadmin (en LOCAL_FS o via HTTP POST /admin/inicialitzar-ruta)."""
        if ruta_personalitzada and not ruta_personalitzada.startswith(("http://", "https://")):
            creades = inicialitzar_arbre_carpetes_superadmin(ruta_personalitzada)
            return {"mode": "LOCAL_FS", "vault_root": ruta_personalitzada, "carpetes_count": len(creades)}

        mode, base_target, secret = cls._resolve_target()
        if ruta_personalitzada and ruta_personalitzada.startswith(("http://", "https://")):
            mode, base_target = "HTTP_VAULT", (resolve_effective_node_url(ruta_personalitzada) or ruta_personalitzada).rstrip("/")
        if mode == "LOCAL_FS":
            creades = inicialitzar_arbre_carpetes_superadmin(base_target)
            return {"mode": "LOCAL_FS", "vault_root": base_target, "carpetes_count": len(creades)}

        async with httpx.AsyncClient(timeout=8.0) as client:
            resp = await client.post(
                f"{base_target}/admin/inicialitzar-ruta",
                headers={"X-Vault-Token": secret or ""},
            )
            resp.raise_for_status()
            return resp.json()
```

### 0.3 Test del Bloc 0 (`backend/tests/test_bloc0_disc_empresa_i_superadmin.py`)

```python
import sys
from pathlib import Path
from fastapi.testclient import TestClient

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))
import scripts.client_vault_agent as vault_agent


def test_bloc0_disc_empresa_i_disc_superadmin_carpetes(tmp_path: Path, monkeypatch):
    """Verifica creació de les 38 carpetes d'Empresa i les 20 carpetes del Disc Dur de Superadmin."""
    # 1. Prova Disc Empresa (/media/akaun/Project_1/Sevalormante_docs)
    emp_a = tmp_path / "Sevalormante_docs"
    emp_b = tmp_path / "Sevalormante_docs_backup_B"
    monkeypatch.setattr(vault_agent, "VAULT_ROLE", "EMPRESA")
    monkeypatch.setattr(vault_agent, "VAULT_PRIMARY_A", emp_a)
    monkeypatch.setattr(vault_agent, "VAULT_SECONDARY_B", emp_b)
    monkeypatch.setattr(vault_agent, "VAULT_SECRET", "svlt_emp_token")

    with TestClient(vault_agent.app) as client:
        r_init = client.post("/admin/inicialitzar-ruta", headers={"X-Vault-Token": "svlt_emp_token"})
        assert r_init.status_code == 200
        assert r_init.json()["carpetes_count"] == 38
        assert (emp_a / "09_copilot_ia/index_vectorial_rag").is_dir()
        assert client.get("/v1/models").status_code == 403  # Auth obligatòria

    # 2. Prova Disc Superadmin (/media/akaun/Project_1/Sevalor_Superadmin_docs)
    sup_a = tmp_path / "Sevalor_Superadmin_docs"
    sup_b = tmp_path / "Sevalor_Superadmin_docs_backup_B"
    monkeypatch.setattr(vault_agent, "VAULT_ROLE", "SUPERADMIN")
    monkeypatch.setattr(vault_agent, "VAULT_PRIMARY_A", sup_a)
    monkeypatch.setattr(vault_agent, "VAULT_SECONDARY_B", sup_b)
    monkeypatch.setattr(vault_agent, "VAULT_SECRET", "svlt_superadmin_token")

    with TestClient(vault_agent.app) as client:
        r_sup = client.post("/admin/inicialitzar-ruta", headers={"X-Vault-Token": "svlt_superadmin_token"})
        assert r_sup.status_code == 200
        assert r_sup.json()["carpetes_count"] == 20
        assert (sup_a / "02_facturacio_saas/factures_b2b_json").is_dir()
        assert (sup_a / "04_rascador_prospeccio/candidats").is_dir()
        assert (sup_a / "03_crm_comercial/leads").is_dir()
```

---

## BLOC 1 — Alta d'Empresa amb Túnel Copilot + Disc Dur Verificat Obligatori, Creació de Rutes per Superadmin i Hetzner Zero-Storage

### 1.1 Fitxers afectats
- [tenants.py](file:///media/akaun/Project_1/SEVALOR/backend/app/api/v1/superadmin/tenants.py) (`crear_nou_tenant` `#L938-L1245`, `inicialitzar_disc_empresa` `#L1887`, nou endpoint `POST /superadmin/tenants/disc-superadmin/inicialitzar`)
- [auth.py](file:///media/akaun/Project_1/SEVALOR/backend/app/api/v1/auth.py) / [operari_auth.py](file:///media/akaun/Project_1/SEVALOR/backend/app/api/v1/operari_auth.py) (índexs cecs HMAC per mantenir login sense PII en text pla a Hetzner)
- [tasks.py](file:///media/akaun/Project_1/SEVALOR/backend/app/workers/tasks.py) (`drenar_cua_transit_task`, auto-purga post-sincronització)

### 1.2 Implementació de l'Alta Blindada (`crear_nou_tenant`) i Endpoints del Disc Superadmin

1. **Endpoint de Superadmin per crear la ruta de carpetes del propi Superadmin i de qualsevol nova empresa:**
   - `POST /api/v1/superadmin/tenants/disc-superadmin/inicialitzar` -> crida `SuperadminStorageGateway.inicialitzar_rutes_superadmin(...)`.
   - `POST /api/v1/superadmin/tenants/{empresa_id}/inicialitzar-disc` -> verifica roundtrip i crea les 38 carpetes al disc dur de l'empresa remota via `POST /admin/inicialitzar-ruta` + `inicialitzar_dades_onboarding_empresa` + `drenar_cua_transit_empresa`.
2. **Validació obligatòria del túnel Copilot + Disc Dur en l'alta (`crear_nou_tenant`):**
   - Unificar URL del túnel:
     ```python
     tunel_url_final = (
         (payload.disc_dur_url or "").strip()
         or (payload.node_ia_url or "").strip()
     ) or None
     if payload.estat_inicial == "ACTIU" and not tunel_url_final:
         raise HTTPException(
             status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
             detail="Cal indicar la URL del túnel sobirà (client_vault_agent.py) per donar d'alta una empresa activa.",
         )
     ```
   - Verificar **roundtrip real** abans d'acceptar el túnel com a funcional:
     ```python
     if tunel_url_final and tunel_url_final.startswith(("http://", "https://")):
         # Comprovar /health, PUT/GET/DELETE a /entitats i estat proxy IA /v1/models
         roundtrip_ok = False
         ia_proxy_ok = False
         for base in (get_candidate_node_urls(tunel_url_final) or [tunel_url_final.rstrip("/")]):
             try:
                 chk = await SovereignStorageGateway.verificar_roundtrip_http_vault(base, vault_token_unic)
                 if chk.get("ok"):
                     roundtrip_ok = True
                     ia_proxy_ok = bool(chk.get("ia_proxy_ok"))
                     # Inicialitzar les 38 carpetes oficials directament al PC de l'empresa
                     async with httpx.AsyncClient(timeout=8.0) as client:
                         await client.post(
                             f"{base}/admin/inicialitzar-ruta",
                             headers={"X-Vault-Token": vault_token_unic},
                         )
                     break
             except Exception:
                 continue

         if not roundtrip_ok:
             raise HTTPException(
                 status_code=status.HTTP_502_BAD_GATEWAY,
                 detail="El túnel de disc dur no respon o el vault_token no coincideix. Alta bloquejada segons Zero-Storage.",
             )
         if copilot_actiu and not ia_proxy_ok:
             raise HTTPException(
                 status_code=status.HTTP_502_BAD_GATEWAY,
                 detail="El túnel respon, però el proxy Copilot (/v1/models) a LM Studio no està operatiu.",
             )
     ```
3. **Minimització Zero-Storage a Hetzner dins `crear_nou_tenant`, `auth.py` i `operari_auth.py`:**
   - **A Hetzner (`Empresa` i `Usuari`) només s'hi guarden valors pseudonimitzats, índexs HMAC cecs de login, hashes criptogràfics (`password_hash`/`pin_hash`/`secret_2fa`) i punters d'enrutament:**
     ```python
     def _blind_hmac(valor: str) -> str:
         return hmac.new(
             settings.SECRET_KEY.encode("utf-8"),
             valor.strip().lower().encode("utf-8"),
             hashlib.sha256,
         ).hexdigest()

     # A PostgreSQL d'Hetzner (Taula empreses):
     nova_empresa = Empresa(
         id=nou_id,
         nom=f"Tenant-{subdomini_norm}",           # Pseudonimitzat: sense raó social real a Hetzner
         nif=f"H-{_blind_hmac(nif_norm)[:18]}",    # Hash cec (20 chars): sense NIF real a Hetzner
         adreca=None,                              # Zero adreces a Hetzner
         subdomini=subdomini_norm,
         domini_custom=domini_custom_norm,
         estat_domini=estat_domini,
         pla_subscripcio=pla_norm,
         estat_pagament=payload.estat_inicial,
         quota_operaris=quota_op_inicial,
         quota_buffer_mb=payload.quota_buffer_mb,
         tarifa_llicencia_base=0.0,                # Tarifes/CRM/Facturació -> al Disc Superadmin!
         tarifa_per_operari=0.0,
         tarifa_config_ia=0.0,
         equips_ia_venuts=[],
         notes_crm=None,
         vertical=vertical_norm,
         agent_prompt_system=None,                 # Viu a 09_copilot_ia/prompt_sistema/system_prompt.txt
         node_ia_url=tunel_url_final,
         disc_dur_url=tunel_url_final,
         vault_token=vault_token_unic,
         node_ia_actiu=bool(tunel_url_final),
         feature_copilot_ia=bool(copilot_actiu and tunel_url_final),
         primari_hsl=payload.primari_hsl or "210 100% 15%",
         secundari_hsl=payload.secundari_hsl or "38 92% 50%",
         accent_hsl=payload.accent_hsl or "190 90% 50%",
     )

     # A PostgreSQL d'Hetzner (Taula usuaris - Boss/Operaris):
     nou_boss = Usuari(
         id=boss_id,
         empresa_id=nou_id,
         nif=f"H-{_blind_hmac(payload.boss_nif)[:18]}",                  # Zero NIF real
         nom="Usuari",                                                    # Zero nom/cognoms en text pla
         cognoms="",
         email=f"{_blind_hmac(payload.boss_email)[:32]}@blind.sevalor",   # Índex cec de login O(1)
         telefon=f"T-{_blind_hmac(payload.boss_telefon)[:18]}" if getattr(payload, "boss_telefon", None) else None,
         password_hash=hash_password(boss_password),
         rol="BOSS",
         estat="ACTIU",
     )
     ```
   - **[auth.py](file:///media/akaun/Project_1/SEVALOR/backend/app/api/v1/auth.py) i [operari_auth.py](file:///media/akaun/Project_1/SEVALOR/backend/app/api/v1/operari_auth.py):** En autenticar, calculen `_blind_hmac(login_data.email)` / `_blind_hmac(identificador)` i cerquen coincidència per l'índex cec (`or_(Usuari.email == blind_email, func.lower(Usuari.email) == raw_email)`), permetent login amb zero PII a Hetzner i retrocompatibilitat neta.
   - **[sovereign_storage.py](file:///media/akaun/Project_1/SEVALOR/backend/app/services/sovereign_storage.py) (`inicialitzar_dades_onboarding_empresa`):** Rep `dades_empresa_reals` i `dades_boss_reals` (extretes del `payload` abans de pseudonimitzar a Hetzner) per escriure la identitat real i el `system_prompt.txt` al **Disc Dur de l'Empresa** (`11_configuracio_i_backups/identitat_camaleo/empresa.json`, `boss.json`, `08_flota_i_operaris/operaris/<boss_id>.json`, `09_copilot_ia/prompt_sistema/system_prompt.txt`).
   - **Al Disc Dur de Superadmin (`/media/akaun/Project_1/Sevalor_Superadmin_docs`) s'hi desen totes les dades B2B/CRM/tarifes** (`01_tenants_b2b/fitxes_empreses/<nou_id>.json` i `01_tenants_b2b/llicencies_i_contractes/<nou_id>.json`), mentre que `saas_factures_b2b`, `crm` i `prospeccio` passen a usar `SuperadminStorageGateway`. També s'afegeix al panell `/superadmin` el botó d'inicialització directa de carpetes (`Inicialitzar Disc Superadmin` i `Inicialitzar Disc Empresa`).
   - **Buffer efímer xifrat (`SVENC1:`):** Si el PC de l'empresa és offline, Hetzner reté temporalment el paquet xifrat amb `SVENC1:` dins `transit_queue/<empresa_id>` i executa `unlink` + eliminació de carpeta tan bon punt `drenar_cua_transit_empresa` confirma la recepció HTTP `<400` al disc del client.
   - **No invocar** `crear_directoris_sobirans_task.delay(...)` quan s'ha inicialitzat un túnel remot `HTTP_VAULT` (per no crear carpetes residuals dins `/tmp/sevalor_client_disks` d'Hetzner!).

### 1.3 Test del Bloc 1 (`backend/tests/test_bloc1_onboarding_zero_storage.py`)

```python
import json
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx
import jwt
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.core.config import settings
from app.main import app
from app.models.models import Empresa, Usuari
from app.services.sovereign_storage import SovereignStorageGateway

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))
import scripts.client_vault_agent as vault_agent


def _build_token(usuari_id: uuid.UUID, empresa_id: uuid.UUID, rol: str, **extra) -> str:
    payload = {
        "sub": str(usuari_id),
        "rol": rol,
        "empresa_id": str(empresa_id),
        "exp": datetime.now(timezone.utc) + timedelta(minutes=20),
        **extra,
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


@pytest.mark.asyncio
async def test_bloc1_onboarding_tunel_funcional_i_hetzner_zero_storage(admin_session, tmp_path: Path, monkeypatch):
    """Verifica: (1) bloqueig HTTP 502 si túnel no respon, (2) creació de carpetes per Superadmin, (3) zero PII/tarifes a Hetzner, (4) volcat al Disc Superadmin i Disc Empresa."""
    sup_dir = tmp_path / "Sevalor_Superadmin_docs"
    emp_dir = tmp_path / "NovaEmpresa_docs"
    sup_dir.mkdir()
    emp_dir.mkdir()
    monkeypatch.setenv("SUPERADMIN_VAULT_URL", str(sup_dir))

    super_tok = _build_token(uuid.uuid4(), uuid.uuid4(), "SUPERADMIN", totp_activat=True, ip_allowlist=["*"])
    headers = {"Authorization": f"Bearer {super_tok}"}
    payload_base = {
        "rao_social": "Instal·lacions Ebre SL",
        "nif": "B12345678",
        "adreca": "Carrer Major 10, Tortosa",
        "subdomini": "ebre-" + uuid.uuid4().hex[:6],
        "vertical": "HYDROPRO",
        "estat_inicial": "ACTIU",
        "pla_subscripcio": "PRO",
        "tarifa_llicencia_base": 199.0,
        "notes_crm": "Client VIP captat per prospecció",
        "boss_nif": "12345678Z",
        "boss_nom": "Joan",
        "boss_cognoms": "Garcia",
        "boss_email": f"joan.{uuid.uuid4().hex[:5]}@ebre.cat",
        "feature_flags": {"copilot_ia": True},
        "agent_prompt_system": "Prioritza materials de reg homologats.",
        "disc_dur_url": "http://127.0.0.1:59999",
        "node_ia_url": "http://127.0.0.1:59999",
        "vault_token": "svlt_nou_client_123456",
    }

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # 0. Superadmin crea la seva pròpia estructura de 20 carpetes al seu Disc Dedicat
        r_sup_init = await ac.post("/api/v1/superadmin/tenants/disc-superadmin/inicialitzar", headers=headers)
        assert r_sup_init.status_code == 200
        assert (sup_dir / "02_facturacio_saas/factures_b2b_json").is_dir()

        # 1. Si el túnel HTTP no respon, l'alta ACTIVA ha de quedar bloquejada (HTTP 502)
        res_fail = await ac.post("/api/v1/superadmin/tenants/onboarding", json=payload_base, headers=headers)
        assert res_fail.status_code == 502

        # 2. Amb ruta vàlida, crea les 38 carpetes i desa B2B al Disc Superadmin + real a Disc Empresa
        payload_ok = {**payload_base, "disc_dur_url": str(emp_dir), "node_ia_url": str(emp_dir)}
        res_onb = await ac.post("/api/v1/superadmin/tenants/onboarding", json=payload_ok, headers=headers)
        assert res_onb.status_code == 201
        emp_id = res_onb.json()["tenant"]["id"]

    # Comprovar que a Hetzner PostgreSQL (Empresa i Usuari) NO hi ha PII ni tarifes en text pla
    emp_db = (await admin_session.execute(select(Empresa).where(Empresa.id == uuid.UUID(emp_id)))).scalar_one()
    assert emp_db.nom != "Instal·lacions Ebre SL"
    assert emp_db.nif != "B12345678"
    assert emp_db.adreca is None
    assert float(emp_db.tarifa_llicencia_base) == 0.0
    assert emp_db.notes_crm is None

    boss_db = (await admin_session.execute(select(Usuari).where(Usuari.empresa_id == uuid.UUID(emp_id), Usuari.rol == "BOSS"))).scalar_one()
    assert boss_db.nom != "Joan"
    assert boss_db.email != payload_base["boss_email"]
    assert boss_db.nif != "12345678Z"

    # Comprovar que les dades comercials B2B/CRM estan al Disc del Superadmin
    fitxa_super = sup_dir / f"01_tenants_b2b/fitxes_empreses/{emp_id}.json"
    assert fitxa_super.is_file()
    dades_super = json.loads(fitxa_super.read_text(encoding="utf-8"))
    assert dades_super["rao_social"] == "Instal·lacions Ebre SL"
    assert float(dades_super["tarifa_llicencia_base"]) == 199.0

    # Comprovar que el Disc de l'Empresa té les 38 carpetes + identitat + prompt_sistema
    assert (emp_dir / "09_copilot_ia/prompt_sistema/system_prompt.txt").is_file()
    assert (emp_dir / "11_configuracio_i_backups/identitat_camaleo/empresa.json").is_file()


@pytest.mark.asyncio
async def test_bloc1_cua_transit_xifrada_svenc1_i_auto_purga(admin_session, tmp_path: Path, monkeypatch):
    """Verifica que amb el PC apagat Hetzner només reté SVENC1: xifrat i fa unlink immediat en recuperar connexió."""
    queue_dir = tmp_path / "transit_queue"
    emp_vault_a = tmp_path / "vault_a"
    emp_vault_b = tmp_path / "vault_b"
    emp_vault_a.mkdir(); emp_vault_b.mkdir()
    monkeypatch.setenv("SOVEREIGN_TRANSIT_QUEUE_DIR", str(queue_dir))

    emp_id = uuid.uuid4()
    admin_session.add(Empresa(
        id=emp_id, nom="Tenant-Offline", nif=f"H-{uuid.uuid4().hex[:8]}", subdomini="off-" + uuid.uuid4().hex[:5],
        disc_dur_url="http://127.0.0.1:59998", node_ia_url="http://127.0.0.1:59998", vault_token="svlt_transit_ok",
    ))
    await admin_session.flush()

    # 1. PC empresa desconnectat -> Hetzner desa temporalment xifrat amb SVENC1: (sense text pla)
    ref = await SovereignStorageGateway.desar_entitat_json(
        admin_session, emp_id, "clients", "cli_off_1",
        {"rao_social": "Finca Secreta Offline", "observacions": "Codi alarma 9988"},
    )
    assert ref.startswith("transit://")
    bins = list((queue_dir / str(emp_id)).glob("*.bin"))
    assert len(bins) == 1
    raw_enc = bins[0].read_bytes()
    assert raw_enc.startswith(b"SVENC1:")
    assert b"Finca Secreta Offline" not in raw_enc

    # 2. PC empresa torna a estar en línia (client_vault_agent ASGI) -> buidat i purga (unlink) total d'Hetzner
    monkeypatch.setattr(vault_agent, "VAULT_ROLE", "EMPRESA")
    monkeypatch.setattr(vault_agent, "VAULT_PRIMARY_A", emp_vault_a)
    monkeypatch.setattr(vault_agent, "VAULT_SECONDARY_B", emp_vault_b)
    monkeypatch.setattr(vault_agent, "VAULT_SECRET", "svlt_transit_ok")
    vault_agent.inicialitzar_estructura_disc()

    orig_async_client = httpx.AsyncClient
    monkeypatch.setattr(
        httpx, "AsyncClient",
        lambda *args, **kwargs: orig_async_client(transport=ASGITransport(app=vault_agent.app), base_url="http://vault-test"),
    )
    emp_db = (await admin_session.execute(select(Empresa).where(Empresa.id == emp_id))).scalar_one()
    emp_db.disc_dur_url = "http://vault-test"
    await admin_session.flush()

    res_drain = await SovereignStorageGateway.drenar_cua_transit_empresa(admin_session, emp_id)
    assert res_drain["enviats"] == 1
    assert res_drain["pendents"] == 0
    assert not (queue_dir / str(emp_id)).exists()
    assert (emp_vault_a / "01_clients/directoris_clients/cli_off_1.json").is_file()
```

---

## BLOC 2 — Orquestrador (`CopilotDispatcher`) i 8 Subagents Llegint Exclusivament del Disc de Cada Empresa amb Aïllament Anti-Barreja

### 2.1 Fitxers afectats
- [sovereign_storage.py](file:///media/akaun/Project_1/SEVALOR/backend/app/services/sovereign_storage.py)
- [base.py](file:///media/akaun/Project_1/SEVALOR/backend/app/services/subagents/base.py)
- [dispatcher.py](file:///media/akaun/Project_1/SEVALOR/backend/app/services/subagents/dispatcher.py)
- Els 8 subagents: [subagent_general_rag.py](file:///media/akaun/Project_1/SEVALOR/backend/app/services/subagents/subagent_general_rag.py), [subagent_logistica_estoc.py](file:///media/akaun/Project_1/SEVALOR/backend/app/services/subagents/subagent_logistica_estoc.py), [subagent_planificacio_equip.py](file:///media/akaun/Project_1/SEVALOR/backend/app/services/subagents/subagent_planificacio_equip.py), [subagent_flota_despatx.py](file:///media/akaun/Project_1/SEVALOR/backend/app/services/subagents/subagent_flota_despatx.py), [subagent_peritatge_camp.py](file:///media/akaun/Project_1/SEVALOR/backend/app/services/subagents/subagent_peritatge_camp.py), [subagent_auditoria_marge.py](file:///media/akaun/Project_1/SEVALOR/backend/app/services/subagents/subagent_auditoria_marge.py), [subagent_ocr_vision.py](file:///media/akaun/Project_1/SEVALOR/backend/app/services/subagents/subagent_ocr_vision.py), [subagent_client_telegram.py](file:///media/akaun/Project_1/SEVALOR/backend/app/services/subagents/subagent_client_telegram.py).

### 2.2 Implementació de Signatura Anti-Barreja i Lectura Sobirana Única

1. **Seguretat anti-barreja per `empresa_id` a [sovereign_storage.py](file:///media/akaun/Project_1/SEVALOR/backend/app/services/sovereign_storage.py):**
   - Cada entitat escrita amb `desar_entitat_json` rep una signatura HMAC lligada a `empresa_id`:
     ```python
     @staticmethod
     def _sign_meta(empresa_id: str | uuid.UUID, categoria: str, subcarpeta: str, item_id: str) -> Dict[str, Any]:
         msg = f"{empresa_id}:{subcarpeta}:{item_id}".encode("utf-8")
         sig = hmac.new(settings.SECRET_KEY.encode("utf-8"), msg, hashlib.sha256).hexdigest()
         return {
             "empresa_id": str(empresa_id),
             "categoria": categoria,
             "subcarpeta": subcarpeta,
             "item_id": str(item_id),
             "hmac_tenant": sig,
             "synced_at": datetime.now(timezone.utc).isoformat(),
         }
     ```
   - Quan `llegir_entitats_json` llegeix fitxers del disc de l'empresa, **rebutja automàticament** qualsevol JSON amb `_sovereign_meta.empresa_id != str(empresa_id)` o firma HMAC manipulable/invàlida (`hmac.compare_digest`), garantint que encara que dues carpetes compartissin muntatge, **és impossible barrejar registres d'Empresa A i Empresa B**:
     ```python
     meta = item.get("_sovereign_meta") or {}
     if meta.get("empresa_id"):
         if str(meta["empresa_id"]) != str(empresa_id):
             logger.error("VIOLACIÓ AÏLLAMENT DISC: fitxer de %s trobat al disc de %s", meta["empresa_id"], empresa_id)
             continue
         sig_rebuda = meta.get("hmac_tenant")
         if sig_rebuda:
             sub_m = str(meta.get("subcarpeta") or subcarpeta)
             it_m = str(meta.get("item_id") or item.get("id") or "")
             expected = hmac.new(
                 settings.SECRET_KEY.encode("utf-8"),
                 f"{empresa_id}:{sub_m}:{it_m}".encode("utf-8"),
                 hashlib.sha256,
             ).hexdigest()
             if not hmac.compare_digest(str(sig_rebuda), expected):
                 logger.error("SIGNATURA HMAC INVÀLIDA al disc de %s (%s)", empresa_id, it_m)
                 continue
     ```
2. **Prohibició de Fallback d'Hetzner a [dispatcher.py](file:///media/akaun/Project_1/SEVALOR/backend/app/services/subagents/dispatcher.py):**
   - Si `node_ia_actiu == False` o `feature_copilot_ia == False` o el túnel (`node_ia_url` / `disc_dur_url`) no respon -> llançar immediatament **HTTP 503 (`COPILOT_DESACTIVAT` / `NODE_IA_OFFLINE`)**.
   - **Zero `run_sovereign(...)` amb dades de PostgreSQL d'Hetzner:** totes les eines dels 8 subagents llegeixen de `self.read_sovereign_category(db, empresa_id, categoria)` i `self.search_sovereign_categories(...)`.
   - En cada resposta, l'orquestrador llegeix `09_copilot_ia/prompt_sistema/system_prompt.txt` del disc de l'empresa i desa l'aprenentatge a `09_copilot_ia/autoaprenentatge/converses_i_feedback`.

3. **Lectura dels 8 subagents exclusivament sobre les carpetes del disc de l'empresa:**
   - `SubagentGeneralRag`: llegeix `protocols_interns`, `manuals_fabricants`, `normativa_prl`, `copilot_rag_index`, `clients`, `finques`, `pressupostos`, `magatzem_eines`.
   - `SubagentLogisticaEstoc`: llegeix `magatzem_articles`, `magatzem_eines`, `albarans`, `picking`, `proveidors`.
   - `SubagentPlanificacioEquip`: llegeix `ots_actives`, `ots_historic`, `incidencies_registres`, `operaris`, `jornades`.
   - `SubagentFlotaDespatx`: llegeix `vehicles`, `alertes_flota`, `tiquets_despesa` (sense fallback fals `41.3851, 2.1734`).
   - `SubagentPeritatgeCamp`: llegeix `incidencies_registres`, `manuals_fabricants`, `ots_historic`, calcula sense costos hardcodejats (`85.50`/`45.00`) i desa a `copilot_memorandums`.
   - `SubagentAuditoriaMarge`: llegeix `factures_pdf`, `pressupostos`, `ots_historic`, `ots_informes`, `copilot_mermes_preus` (veto estricte `BOSS`).
   - `SubagentOcrVision`: processa pel VLM del túnel i desa resultats a `albarans` / `tiquets_despesa` / `factures_proveidors`.
   - `SubagentClientTelegram`: llegeix `clients` / `pressupostos` del disc de l'empresa i dispara notificació real via Telegram.

### 2.3 Test del Bloc 2 (`backend/tests/test_bloc2_subagents_aillament_disc.py`)

```python
import json
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import jwt
import pytest
from httpx import ASGITransport, AsyncClient

from app.core.config import settings
from app.main import app
from app.models.models import Empresa, Usuari
from app.services.sovereign_storage import SovereignStorageGateway
from app.services.subagents.subagent_general_rag import SubagentGeneralRag
from app.services.subagents.subagent_logistica_estoc import SubagentLogisticaEstoc


def _token(usuari_id: uuid.UUID, empresa_id: uuid.UUID, rol: str, **extra) -> str:
    payload = {
        "sub": str(usuari_id),
        "rol": rol,
        "empresa_id": str(empresa_id),
        "exp": datetime.now(timezone.utc) + timedelta(minutes=20),
        **extra,
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


@pytest.mark.asyncio
async def test_bloc2_subagents_nomes_disc_empresa_i_aillament_anti_barreja(admin_session, tmp_path: Path):
    """Verifica: (1) Lectura exclusiva del disc de cada empresa, (2) rebuig de fitxers d'un altre tenant o HMAC manipulat, (3) 503 si node apagat."""
    emp_a, emp_b = uuid.uuid4(), uuid.uuid4()
    disc_a, disc_b = tmp_path / "Disc_Empresa_A", tmp_path / "Disc_Empresa_B"
    disc_a.mkdir(); disc_b.mkdir()

    for eid, nom, sub, disc, actiu in [
        (emp_a, "Tenant A", "a-" + uuid.uuid4().hex[:5], str(disc_a), True),
        (emp_b, "Tenant B", "b-" + uuid.uuid4().hex[:5], str(disc_b), False),
    ]:
        admin_session.add(
            Empresa(
                id=eid, nom=nom, nif="H-" + uuid.uuid4().hex[:8], subdomini=sub,
                pla_subscripcio="ENTERPRISE", estat_pagament="ACTIU",
                disc_dur_url=disc, node_ia_url=disc, node_ia_actiu=actiu, feature_copilot_ia=actiu,
            )
        )
    await admin_session.flush()

    # Escrivim un article i un protocol només al disc d'Empresa A i al disc d'Empresa B
    await SovereignStorageGateway.desar_entitat_json(
        admin_session, emp_a, "magatzem_articles", "art_a1",
        {"nom": "Cable Solar A 6mm", "referencia_inventari": "SOL-A6", "estoc_disponible": 250.0, "unitat_mesura": "METRES_LINEALS"},
    )
    await SovereignStorageGateway.desar_entitat_json(
        admin_session, emp_b, "protocols_interns", "proto_b",
        {"titol": "Secret Exclusiu B", "contingut": "Codi secret intern nomes empresa B"},
    )

    # Simulació d'injecció/barreja física: copiem el fitxer de B dins la carpeta d'A i un amb HMAC falsificat
    intrus_path = disc_a / "10_protocols_i_manuals/procediments_interns/proto_b.json"
    intrus_path.parent.mkdir(parents=True, exist_ok=True)
    raw_b = json.loads((disc_b / "10_protocols_i_manuals/procediments_interns/proto_b.json").read_text(encoding="utf-8"))
    intrus_path.write_text(json.dumps(raw_b), encoding="utf-8")

    forged = {**raw_b, "titol": "Manipulat A", "_sovereign_meta": {**raw_b["_sovereign_meta"], "empresa_id": str(emp_a), "hmac_tenant": "0" * 64}}
    (disc_a / "10_protocols_i_manuals/procediments_interns/forged.json").write_text(json.dumps(forged), encoding="utf-8")

    # 1. SubagentGeneralRag per a Empresa A HA D'IGNORAR el fitxer de B i l'HMAC falsificat
    sub_rag = SubagentGeneralRag()
    res_a = await sub_rag.tool_get_rag_knowledge(admin_session, emp_a, "Secret Exclusiu B")
    assert res_a["trobat"] is False
    res_forged = await sub_rag.tool_get_rag_knowledge(admin_session, emp_a, "Manipulat A")
    assert res_forged["trobat"] is False

    # 2. SubagentLogisticaEstoc per a Empresa A llegeix del disc d'A tot i que la taula articles d'Hetzner està buida
    sub_estoc = SubagentLogisticaEstoc()
    res_est = await sub_estoc.tool_get_real_stock(admin_session, emp_a, "Cable Solar A 6mm")
    assert res_est["trobat"] is True
    assert res_est["total_disponible"] == pytest.approx(250.0)

    # 3. Si node_ia_actiu=False (Empresa B), el Copilot ha de retornar 503 sense fallback a Hetzner
    boss_b = uuid.uuid4()
    admin_session.add(Usuari(id=boss_b, empresa_id=emp_b, nom="B", cognoms="B", nif="BB-" + uuid.uuid4().hex[:4], rol="BOSS", estat="ACTIU"))
    await admin_session.flush()
    tok_b = _token(boss_b, emp_b, "BOSS")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        res_503 = await ac.post(
            "/api/v1/gestio/copilot/xat",
            json={"pregunta": "Quin estoc tenim?"},
            headers={"Authorization": f"Bearer {tok_b}", "X-Empresa-ID": str(emp_b)},
        )
        assert res_503.status_code == 503
```

---

## BLOC 3 — Fulla de Feines (`/gestio/feines`), Botó Triple, Mapa, RAG i Alta Atòmica amb Sincronització a `06_ordres_treball`

### 3.1 Fitxers i canvis principals
- **[feines.py](file:///media/akaun/Project_1/SEVALOR/backend/app/api/v1/gestio/feines.py):**
  - `FeinaCreate` rep `linies_picking` i `magatzem_id`.
  - Validació `Client.estat_risc_operatiu == "BLOQUEJAT_RISC"` -> `HTTP 423 Locked`.
  - Validació carnet vehicle (`FR-012`), reserva atòmica `SELECT FOR UPDATE` amb `magatzem_id`, sense `await db.refresh(nova_feina)`, veto `ENGINYER` a `preu_venda_hora_aplicat`, eliminació de mocks de `/intervencions-actives`.
  - Sincronització immediata a `ots_actives` (`06_ordres_treball/actives_buffer`) / `ots_historic` (`historic_tancades`). En confirmar que `SYNCED`, purgar qualsevol payload temporal de trànsit a Hetzner.
- **[pressupostos.py](file:///media/akaun/Project_1/SEVALOR/backend/app/api/v1/gestio/pressupostos.py#L229-L251):** Eliminar `# Simulate LLM call` (`100.0 €`); exigir node IA actiu (503 si apagat) i sincronitzar a `pressupostos` (`04_factures/prefactures_i_pressupostos`).
- **Frontend:**
  - Crear `pwa/src/app/gestio/feines/page.tsx` (suport `?c=` i `?id=`, drawer `Fulla360OTDrawer` i botó `"+ Nova Feina"`).
  - Afegir botó `"+ Nova Feina"` a [mapa/page.tsx](file:///media/akaun/Project_1/SEVALOR/pwa/src/app/gestio/mapa/page.tsx).
  - A [CrearOTModal.tsx](file:///media/akaun/Project_1/SEVALOR/pwa/src/components/gestio/CrearOTModal.tsx): `cap_de_colla_id` opcional, `POST /gestio/feines` únic atòmic, i **Botó Triple real** (`Generar Tasca` / `Generar Pressupost` / `Pressupost Intel·ligent (Copilot)` visible només amb `feature_copilot_ia && node_ia_actiu`).
  - A [layout.tsx](file:///media/akaun/Project_1/SEVALOR/pwa/src/app/gestio/layout.tsx) i [CopilotWidget.tsx](file:///media/akaun/Project_1/SEVALOR/pwa/src/components/CopilotWidget.tsx): validar `feature_copilot_ia && node_ia_actiu`.
  - A [copilot/page.tsx](file:///media/akaun/Project_1/SEVALOR/pwa/src/app/gestio/copilot/page.tsx#L41): apuntar a `POST /gestio/copilot/rag/document`.

### 3.2 Test del Bloc 3 (`backend/tests/test_bloc3_feines_boto_triple_rag.py`)

```python
import uuid
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import jwt
import pytest
from httpx import ASGITransport, AsyncClient

from app.core.config import settings
from app.main import app
from app.models.models import Article, Client, Empresa, EstocMagatzem, Magatzem, Usuari


def _token(usuari_id: uuid.UUID, empresa_id: uuid.UUID, rol: str, **extra) -> str:
    payload = {
        "sub": str(usuari_id),
        "rol": rol,
        "empresa_id": str(empresa_id),
        "exp": datetime.now(timezone.utc) + timedelta(minutes=20),
        **extra,
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


@pytest.mark.asyncio
async def test_bloc3_alta_feina_atomica_risc_i_rag_disc(admin_session, tmp_path: Path):
    """Verifica 423 per BLOQUEJAT_RISC, rollback atòmic d'OT+picking, escriptura a 06_ordres_treball i RAG a 10_protocols_i_manuals."""
    emp_id, boss_id, mag_id, art_id = uuid.uuid4(), uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    cli_ok, cli_blk = uuid.uuid4(), uuid.uuid4()
    disc = tmp_path / "Disc_Bloc3"
    disc.mkdir()

    admin_session.add(Empresa(id=emp_id, nom="T-B3", nif="H-B3", subdomini="b3-" + uuid.uuid4().hex[:5], disc_dur_url=str(disc), node_ia_url=str(disc), node_ia_actiu=True, feature_copilot_ia=True))
    admin_session.add(Usuari(id=boss_id, empresa_id=emp_id, nom="B3", cognoms="Admin", nif="B3-" + uuid.uuid4().hex[:5], rol="BOSS", estat="ACTIU"))
    admin_session.add(Client(id=cli_ok, empresa_id=emp_id, codi="C1", rao_social="Client OK", nif="B11111111", estat_risc_operatiu="APTE"))
    admin_session.add(Client(id=cli_blk, empresa_id=emp_id, codi="C2", rao_social="Client Risc", nif="B22222222", estat_risc_operatiu="BLOQUEJAT_RISC"))
    admin_session.add(Magatzem(id=mag_id, empresa_id=emp_id, nom="Nau Central", tipus="NAU_CENTRAL"))
    admin_session.add(Article(id=art_id, empresa_id=emp_id, referencia_inventari="TUB-32", nom="Tub 32mm", preu_cost=2.0, preu_venda=5.0))
    admin_session.add(EstocMagatzem(empresa_id=emp_id, magatzem_id=mag_id, article_id=art_id, quantitat_fisica=10.0, quantitat_virtual_reservada=4.0))
    await admin_session.flush()

    headers = {"Authorization": f"Bearer {_token(boss_id, emp_id, 'BOSS')}", "X-Empresa-ID": str(emp_id)}
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        r_blk = await ac.post("/api/v1/gestio/feines", json={"codi": "OT-BLK", "client_id": str(cli_blk), "titol": "Test", "adreca": "Camí 1", "data_planificacio": date.today().isoformat()}, headers=headers)
        assert r_blk.status_code == 423

        r_ok = await ac.post(
            "/api/v1/gestio/feines",
            json={"codi": "OT-ATOM", "client_id": str(cli_ok), "titol": "Reg Sector 1", "adreca": "Camí 2", "data_planificacio": date.today().isoformat(), "magatzem_id": str(mag_id), "linies_picking": [{"article_id": str(art_id), "quantitat_prevista": 3.0}]},
            headers=headers,
        )
        assert r_ok.status_code in (200, 201)
        ot_id = r_ok.json()["id"]
        assert (disc / f"06_ordres_treball/actives_buffer/{ot_id}.json").is_file()

        r_rag = await ac.post("/api/v1/gestio/copilot/rag/document", json={"titol": "Norma reg", "contingut": "Purgar aire abans de tancar", "tags": "reg"}, headers=headers)
        assert r_rag.status_code == 201
```

---

## BLOC 4 — Magatzem, Control d'Estoc Real (`físic - reservat`), Picking per `magatzem_id`, Eines i Sincronització a `03_magatzem`

### 4.1 Fitxers i canvis principals
- Migració `a023_picking_linia_magatzem.py` (sobre `a022_ordres_treball_trams_temps.py`): afegeix `magatzem_id` a `linies_picking`.
- **[magatzem.py](file:///media/akaun/Project_1/SEVALOR/backend/app/api/v1/gestio/magatzem.py) + [dashboard.py](file:///media/akaun/Project_1/SEVALOR/backend/app/api/v1/gestio/dashboard.py):**
  - `ArticleCreate` accepta `estoc_inicial` i `magatzem_id`; `alta_article` i `modificar_article` filtren per `Article.empresa_id == emp_uuid` i persisteixen `codi_barres`.
  - `llistar_articles` i `critical_stock` retornen `estoc_fisic`, `estoc_reservat`, `estoc_disponible = quantitat_fisica - quantitat_virtual_reservada`.
  - `afegir_linia_picking` i `confirmar_devolucio` filtren per `(empresa_id, article_id, magatzem_id)` amb `WITH FOR UPDATE`; `confirmar_devolucio` descompta de `quantitat_fisica` el consum real (`quantitat_carregada_pick_in - quantitat_retornada_pick_out`) + mermes, i sincronitza `magatzem_articles` i `picking` al disc de l'empresa.
  - Veto `ENGINYER` sobre `preu_cost`, `pmp_actual`, `descompte_proveidor`.
  - Substituir `/tmp/data/{empresa_id}/proveidors/{prov.id}` (`#L906`) per `SovereignStorageGateway`.
- **[magatzem/page.tsx](file:///media/akaun/Project_1/SEVALOR/pwa/src/app/gestio/magatzem/page.tsx):** Camps `codi_barres` i `estoc_inicial`, unitats unificades, modal `"Ajustar Estoc"` (`POST /magatzem/magatzems/{id}/moviment`), botó editar Eines (`PUT /magatzem/eines/{id}`), pestanya `RECOMPRA_STOCK` i ocultació de costos a `ENGINYER`.

### 4.2 Test del Bloc 4 (`backend/tests/test_bloc4_magatzem_estoc_picking.py`)

```python
import uuid
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import jwt
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.core.config import settings
from app.main import app
from app.models.models import Client, Empresa, LiniaPicking, Magatzem, Usuari


def _token(usuari_id: uuid.UUID, empresa_id: uuid.UUID, rol: str, **extra) -> str:
    payload = {
        "sub": str(usuari_id),
        "rol": rol,
        "empresa_id": str(empresa_id),
        "exp": datetime.now(timezone.utc) + timedelta(minutes=20),
        **extra,
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


@pytest.mark.asyncio
async def test_bloc4_magatzem_estoc_inicial_disponible_picking_i_veto_enginyer(admin_session, tmp_path: Path):
    """Verifica: codi_barres + estoc_inicial a alta_article, càlcul fisic-reservat, descompte real en pick-out i veto Enginyer."""
    emp_id, boss_id, eng_id, mag_id, cli_id = uuid.uuid4(), uuid.uuid4(), uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    disc = tmp_path / "Disc_Mag"
    disc.mkdir()
    admin_session.add(Empresa(id=emp_id, nom="T-Mag", nif="H-MG", subdomini="mg-" + uuid.uuid4().hex[:5], disc_dur_url=str(disc)))
    admin_session.add(Usuari(id=boss_id, empresa_id=emp_id, nom="Boss", cognoms="M", nif="BM-" + uuid.uuid4().hex[:4], rol="BOSS", estat="ACTIU"))
    admin_session.add(Usuari(id=eng_id, empresa_id=emp_id, nom="Eng", cognoms="M", nif="EM-" + uuid.uuid4().hex[:4], rol="ENGINYER", estat="ACTIU"))
    admin_session.add(Magatzem(id=mag_id, empresa_id=emp_id, nom="Nau Central", tipus="NAU_CENTRAL"))
    admin_session.add(Client(id=cli_id, empresa_id=emp_id, codi="CLI-M", rao_social="Finca M", nif="B33333333"))
    await admin_session.flush()

    h_boss = {"Authorization": f"Bearer {_token(boss_id, emp_id, 'BOSS')}", "X-Empresa-ID": str(emp_id)}
    h_eng = {"Authorization": f"Bearer {_token(eng_id, emp_id, 'ENGINYER')}", "X-Empresa-ID": str(emp_id)}

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        r_art = await ac.post(
            "/api/v1/gestio/magatzem/articles",
            json={"referencia_inventari": "VLV-99", "codi_barres": "8411112223334", "nom": "Vàlvula 99", "preu_cost": 15.0, "preu_venda": 35.0, "estoc_inicial": 50.0, "magatzem_id": str(mag_id)},
            headers=h_boss,
        )
        assert r_art.status_code == 201
        art_data = r_art.json()
        assert art_data["codi_barres"] == "8411112223334"
        assert art_data["estoc_disponible"] == pytest.approx(50.0)
        assert (disc / f"03_magatzem/articles_i_estoc/{art_data['id']}.json").is_file()

        # Enginyer NO pot veure preu_cost ni pmp_actual
        r_eng = await ac.get("/api/v1/gestio/magatzem/articles", headers=h_eng)
        assert r_eng.status_code == 200
        assert r_eng.json()[0]["preu_cost"] is None

        # Picking -> Pick-in (10 carregades) -> Pick-out (3 retornades) => 7 consumides -> estoc_disponible = 43.0
        r_ot = await ac.post(
            "/api/v1/gestio/feines",
            json={"codi": "OT-PK", "client_id": str(cli_id), "titol": "Picking test", "adreca": "Camí 9", "data_planificacio": date.today().isoformat(), "magatzem_id": str(mag_id), "linies_picking": [{"article_id": art_data["id"], "quantitat_prevista": 10.0}]},
            headers=h_boss,
        )
        assert r_ot.status_code in (200, 201)
        linia = (await admin_session.execute(select(LiniaPicking).where(LiniaPicking.empresa_id == emp_id, LiniaPicking.article_id == uuid.UUID(art_data["id"])))).scalars().first()
        assert (await ac.put(f"/api/v1/gestio/magatzem/picking/linies/{linia.id}/pick-in", headers=h_boss)).status_code == 200
        assert (await ac.put(f"/api/v1/gestio/magatzem/picking/linies/{linia.id}/pick-out?quantitat_retornada=3.0&quantitat_mermada=0.0", headers=h_boss)).status_code == 200

        r_after = await ac.get("/api/v1/gestio/magatzem/articles", headers=h_boss)
        assert r_after.json()[0]["estoc_disponible"] == pytest.approx(43.0)
```

---

## BLOC 5 — Seguretat Multi-Tenant (RLS Spotlight `cerca.py`), Veto `ENGINYER` i Resta de Mòduls `/gestio`

### 5.1 Fitxers i canvis principals
- **[cerca.py](file:///media/akaun/Project_1/SEVALOR/backend/app/api/v1/gestio/cerca.py) & [layout.tsx](file:///media/akaun/Project_1/SEVALOR/pwa/src/app/gestio/layout.tsx):** Usar `get_db_with_tenant_context`, filtrar explícitament per `Model.empresa_id == emp_uuid` a `Client`, `Vehicle`, `OrdreTreball`, `Article` i `Usuari`, retornar `ref`/`tipus` cap a rutes reals (`/gestio/feines?id=...`, etc.) i connectar l'input Spotlight a `/gestio/cerca?q=...`.
- **[contractes.py](file:///media/akaun/Project_1/SEVALOR/backend/app/api/v1/gestio/contractes.py):** Protegir amb `Depends(require_financial_access)`, corregir `generar_prefactura` (sense `PRE-9999` ni `"draft_hash"`, prorratejat segons `periodicitat`) i sincronitzar `01_clients/contractes_manteniment`. Corregir [contractes/nou/page.tsx](file:///media/akaun/Project_1/SEVALOR/pwa/src/app/gestio/contractes/nou/page.tsx) per cridar `/gestio/clients/${id}/finques`.
- **Clients i Proveïdors:** Veto IBAN/marges per a `ENGINYER` a [clients.py](file:///media/akaun/Project_1/SEVALOR/backend/app/api/v1/gestio/clients.py), export CSV autenticat amb `Blob` a [clients/page.tsx](file:///media/akaun/Project_1/SEVALOR/pwa/src/app/gestio/clients/page.tsx); filtre `empresa_id` a [proveidors.py](file:///media/akaun/Project_1/SEVALOR/backend/app/api/v1/gestio/proveidors.py) i eliminar IBANs falsos / `"Simular BEC"` a [proveidors/page.tsx](file:///media/akaun/Project_1/SEVALOR/pwa/src/app/gestio/proveidors/page.tsx).
- **Flota i Operaris:** `VehicleProperItem` nullable `Optional[float]`, persistir `anomalia_consum_descartada` a [flota.py](file:///media/akaun/Project_1/SEVALOR/backend/app/api/v1/gestio/flota.py); eliminar GPS simulat de Lleida (`41.6176, 0.6200`) i corregir `km_conduits_mes` + veto `cost_hora_eur` a [operaris.py](file:///media/akaun/Project_1/SEVALOR/backend/app/api/v1/gestio/operaris.py).
- **Comptabilitat, Configuració, Notificacions, Plànols:** Passar `&periode=` i selector real de clients a [comptabilitat/page.tsx](file:///media/akaun/Project_1/SEVALOR/pwa/src/app/gestio/comptabilitat/page.tsx); eliminar mocks d'ADN/logo i corregir claus Telegram `{ telegram_bot_token, telegram_webhook_secret }` + UI Slots/Barema a [configuracio/page.tsx](file:///media/akaun/Project_1/SEVALOR/pwa/src/app/gestio/configuracio/page.tsx); connectar `send_telegram_direct_message`, alinear `remitent_tipus`/`tipus_esdeveniment` i passar `TOKENS_FACTURA` a Redis a [notificacions.py](file:///media/akaun/Project_1/SEVALOR/backend/app/api/v1/gestio/notificacions.py) + [notificacions/page.tsx](file:///media/akaun/Project_1/SEVALOR/pwa/src/app/gestio/notificacions/page.tsx); esborrar fills abans de `CarpetaPlanol` a [planols.py](file:///media/akaun/Project_1/SEVALOR/backend/app/api/v1/gestio/planols.py).

### 5.2 Test del Bloc 5 (`backend/tests/test_bloc5_rls_spotlight_veto_moduls.py`)

```python
import uuid
from datetime import datetime, timedelta, timezone

import jwt
import pytest
from httpx import ASGITransport, AsyncClient

from app.core.config import settings
from app.main import app
from app.models.models import CarpetaPlanol, Client, Empresa, PlanolBase, Usuari


def _token(usuari_id: uuid.UUID, empresa_id: uuid.UUID, rol: str, **extra) -> str:
    payload = {
        "sub": str(usuari_id),
        "rol": rol,
        "empresa_id": str(empresa_id),
        "exp": datetime.now(timezone.utc) + timedelta(minutes=20),
        **extra,
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


@pytest.mark.asyncio
async def test_bloc5_rls_cerca_veto_contractes_i_planols_delete(admin_session):
    """Verifica aïllament Tenant A vs Tenant B a /cerca, veto 403 Enginyer a Contractes i eliminació carpeta amb plànols."""
    emp_a, emp_b, eng_a, boss_a = uuid.uuid4(), uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    admin_session.add(Empresa(id=emp_a, nom="T-A", nif="HA", subdomini="ta-" + uuid.uuid4().hex[:5]))
    admin_session.add(Empresa(id=emp_b, nom="T-B", nif="HB", subdomini="tb-" + uuid.uuid4().hex[:5]))
    admin_session.add(Usuari(id=eng_a, empresa_id=emp_a, nom="Eng", cognoms="A", nif="EA-" + uuid.uuid4().hex[:4], rol="ENGINYER", estat="ACTIU"))
    admin_session.add(Usuari(id=boss_a, empresa_id=emp_a, nom="Boss", cognoms="A", nif="BA-" + uuid.uuid4().hex[:4], rol="BOSS", estat="ACTIU"))
    admin_session.add(Client(empresa_id=emp_b, codi="SEC", rao_social="Client Privat B", nif="B99999999"))
    carp_id = uuid.uuid4()
    admin_session.add(CarpetaPlanol(id=carp_id, empresa_id=emp_a, nom="Carpeta Finca A", categoria="GENERAL"))
    await admin_session.flush()
    admin_session.add(PlanolBase(empresa_id=emp_a, carpeta_id=carp_id, titol="Plànol 1", codi_referencia="PL-1", tipus_fitxer="PDF", fitxer_path="vault://05_planols/arxius_base/p1.pdf", mida_bytes=1024))
    await admin_session.flush()

    h_eng = {"Authorization": f"Bearer {_token(eng_a, emp_a, 'ENGINYER')}", "X-Empresa-ID": str(emp_a)}
    h_boss = {"Authorization": f"Bearer {_token(boss_a, emp_a, 'BOSS')}", "X-Empresa-ID": str(emp_a)}
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        r_cerca = await ac.get("/api/v1/gestio/cerca?q=Privat", headers=h_eng)
        assert r_cerca.status_code == 200
        assert r_cerca.json() == []

        r_mrr = await ac.get("/api/v1/gestio/contractes/mrr", headers=h_eng)
        assert r_mrr.status_code == 403

        r_del_carp = await ac.delete(f"/api/v1/gestio/planols/carpetes/{carp_id}", headers=h_boss)
        assert r_del_carp.status_code == 204
```

---

## Ordre d'Execució i Comandes de Validació Neta (`AGENTS.md`)

```bash
cd backend
.venv/bin/pytest \
  tests/test_bloc0_disc_empresa_i_superadmin.py \
  tests/test_bloc1_onboarding_zero_storage.py \
  tests/test_bloc2_subagents_aillament_disc.py \
  tests/test_bloc3_feines_boto_triple_rag.py \
  tests/test_bloc4_magatzem_estoc_picking.py \
  tests/test_bloc5_rls_spotlight_veto_moduls.py -v
.venv/bin/ruff check .
.venv/bin/mypy app/ --strict

cd ../pwa
npm run lint
npm run build
```
