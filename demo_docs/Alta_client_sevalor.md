# Alta d'Ordinador Dedicat d'Empresa (Túnel Invers Natiu WSS — Zero Cloudflare / Zero HTTP Entrant)

> **Norma Arquitectònica (ADR-001):** El **túnel HTTP/HTML entrant** (`http://127.0.0.1:9001`, `host.docker.internal`, ports oberts al router) i els **túnels Cloudflare manuals per empresa NO són una opció** i queden prohibits. Totes les empreses es connecten mitjançant l'únic **Túnel Invers Natiu per WebSocket (`WSS` sortint port 443)** contra el servidor FastAPI de Hetzner.

### Comanda d'instal·lació a l'ordinador dedicat de cada empresa
A l'ordinador físic de l'empresa (darrere de qualsevol router/NAT, sense obrir ports), executar una única comanda amb el seu `empresa_id` i `vault_token` generats a `/superadmin`:

```bash
bash scripts/install_client_gateway.sh \
  --server https://sevalor-sevalor-backend.80opze.easypanel.host \
  --role EMPRESA \
  --empresa-id <UUID_EMPRESA> \
  --token <vault_token> \
  --disk-a <ruta_disc_exclusiu_empresa> \
  --llm-url http://127.0.0.1:1234
```

Tan bon punt l'agent connecti el túnel WSS sortint cap a Hetzner:
1. Inicialitza automàticament les **38 carpetes oficials** (+ mirall Disc B) exclusivament al disc dur de l'empresa (mai a Hetzner).
2. Activa el canal del **Copilot IA local** exclusiu de l'empresa sense necessitat d'introduir URLs manuals ni crear túnels Cloudflare.
3. Drena i esborra automàticament (`unlink`) qualsevol paquet xifrat (`SVENC1:`) que hagués quedat pendent a la cua de trànsit mentre el PC estava apagat.

Vegeu l'especificació completa a [docs/ARQUITECTURA_TUNEL_SOBIRA_WSS.md](../docs/ARQUITECTURA_TUNEL_SOBIRA_WSS.md).
