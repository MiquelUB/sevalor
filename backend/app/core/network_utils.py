"""Utilitats sobiranes de xarxa i identificació del Túnel Invers Natiu WSS (ADR-001).

Prohibició taxativa de túnels HTTP entrants, ponts Docker (`host.docker.internal` /
`172.x.0.1`) i túnels Cloudflare manuals per empresa. Totes les empreses i Superadmin
s'identifiquen mitjançant `wss-tunnel://<target>` i `vault_token`.
"""

import os
from typing import Any, Dict, Optional

WSS_TUNNEL_SCHEME = "wss-tunnel://"
DEFAULT_PUBLIC_TUNNEL_SERVER_URL = "https://sevalor-sevalor-backend.80opze.easypanel.host"


def get_public_tunnel_server_url() -> str:
    """Retorna la URL pública base del servidor de túnels WSS (configurable via entorn)."""
    raw = (
        os.getenv("SEVALOR_TUNNEL_PUBLIC_URL", "").strip()
        or os.getenv("SEVALOR_SERVER_URL", "").strip()
        or DEFAULT_PUBLIC_TUNNEL_SERVER_URL
    )
    return raw.rstrip("/")


def build_wss_tunnel_uri(target: Any) -> str:
    """Construeix l'identificador canònic `wss-tunnel://<target>` per a una empresa o superadmin."""
    clean = str(target).strip()
    if clean.startswith(WSS_TUNNEL_SCHEME):
        return clean.rstrip("/")
    return f"{WSS_TUNNEL_SCHEME}{clean}"


def is_wss_tunnel_uri(raw_url: Optional[str]) -> bool:
    """Indica si una adreça correspon al Túnel Invers Natiu WSS."""
    return isinstance(raw_url, str) and raw_url.strip().startswith(WSS_TUNNEL_SCHEME)


def extract_wss_tunnel_target(raw_url: Optional[str]) -> Optional[str]:
    """Extreu l'identificador de destí d'un URI `wss-tunnel://<target>`."""
    if not is_wss_tunnel_uri(raw_url):
        return None
    assert raw_url is not None
    target = raw_url.strip()[len(WSS_TUNNEL_SCHEME) :].strip("/")
    return target or None


def normalize_tunnel_url(raw_url: Optional[str]) -> Optional[str]:
    """Normalitza una URL o URI de túnel sense aplicar heurístiques de passarel·les Docker."""
    if not isinstance(raw_url, str):
        return None
    cleaned = raw_url.strip().rstrip("/")
    return cleaned or None


def resoldre_url_tunel_ia(
    node_ia_url: Optional[str],
    disc_dur_url: Optional[str] = None,
) -> Optional[str]:
    """Resol l'adreça configurada del node IA/túnel prioritzant sempre `wss-tunnel://`."""
    node_clean = normalize_tunnel_url(node_ia_url)
    disc_clean = normalize_tunnel_url(disc_dur_url)

    if is_wss_tunnel_uri(node_clean):
        return node_clean
    if is_wss_tunnel_uri(disc_clean):
        return disc_clean
    if node_clean:
        return node_clean
    if disc_clean and disc_clean.startswith(("http://", "https://")):
        return disc_clean
    return None


def resolve_empresa_vault_token(empresa: Any) -> Optional[str]:
    """Resol el token d'autenticació de passarel·la per a l'empresa amb fallbacks segurs."""
    if empresa is None:
        return os.getenv("SEVALOR_VAULT_SECRET") or None
    vault_tok = getattr(empresa, "vault_token", None)
    if isinstance(vault_tok, str) and vault_tok.strip():
        return vault_tok.strip()
    legacy_tg_tok = getattr(empresa, "telegram_webhook_secret", None)
    if isinstance(legacy_tg_tok, str) and legacy_tg_tok.strip().startswith("svlt_"):
        return legacy_tg_tok.strip()
    env_secret = os.getenv("SEVALOR_VAULT_SECRET")
    return env_secret.strip() if isinstance(env_secret, str) and env_secret.strip() else None


def build_node_ia_headers(
    api_key: Optional[str] = None,
    vault_token: Optional[str] = None,
    extra: Optional[Dict[str, str]] = None,
) -> Dict[str, str]:
    """Construeix les capçaleres d'autenticació cap al node IA / passarel·la sobirana."""
    headers: Dict[str, str] = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    if vault_token and vault_token.strip():
        headers["X-Vault-Token"] = vault_token.strip()
    if extra:
        headers.update(extra)
    return headers
