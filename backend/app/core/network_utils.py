"""Utilitats de xarxa per a la resolució d'adreces de nodes locals i contenidors."""

import ipaddress
import os
import socket
import struct
import urllib.parse
from typing import Any, Dict, List, Optional


def get_docker_host_gateways() -> List[str]:
    """Descobreix les IPs de passarel·la per connectar al host des de dins de Docker."""
    gateways: List[str] = []
    # 1. Llegir la taula de rutes del kernel de Linux si existeix
    try:
        if os.path.exists("/proc/net/route"):
            with open("/proc/net/route", "r") as f:
                for line in f:
                    fields = line.strip().split()
                    if len(fields) >= 3 and fields[1] == "00000000":
                        gw_ip = socket.inet_ntoa(struct.pack("<L", int(fields[2], 16)))
                        if gw_ip and gw_ip != "0.0.0.0" and gw_ip not in gateways:
                            gateways.append(gw_ip)
    except Exception:
        pass

    # 2. Afegir noms i IPs estàndard de Docker host
    for candidate in ["172.23.0.1", "host.docker.internal", "172.17.0.1", "172.18.0.1"]:
        if candidate not in gateways:
            gateways.append(candidate)
    return gateways


def get_candidate_node_urls(raw_url: Optional[str]) -> List[str]:
    """Retorna una llista de variants d'URL per testejar connectivitat (loopback + gateways Docker)."""
    if not raw_url or not str(raw_url).strip():
        return []

    base = str(raw_url).strip().rstrip("/")
    candidates = [base]

    try:
        parsed = urllib.parse.urlparse(base)
        hostname = (parsed.hostname or "").lower()
        if hostname in ("127.0.0.1", "localhost", "host.docker.internal"):
            gateways = get_docker_host_gateways()
            port_suffix = f":{parsed.port}" if parsed.port else ""
            scheme = parsed.scheme or "http"
            path = parsed.path or ""
            if hostname == "host.docker.internal" and not os.path.exists("/.dockerenv"):
                local_cand = f"{scheme}://127.0.0.1{port_suffix}{path}".rstrip("/")
                if local_cand not in candidates:
                    candidates.insert(0, local_cand)
            for gw in gateways:
                gw_base = f"{scheme}://{gw}{port_suffix}{path}".rstrip("/")
                if gw_base not in candidates:
                    candidates.append(gw_base)

            # Si estem dins de Docker, prioritzar les passarel·les del host per sobre del loopback
            if os.path.exists("/.dockerenv") and len(candidates) > 1:
                external = [c for c in candidates if "127.0.0.1" not in c and "localhost" not in c]
                internal = [c for c in candidates if "127.0.0.1" in c or "localhost" in c]
                candidates = external + internal
    except Exception:
        pass

    return candidates


def is_private_or_loopback_url(raw_url: Optional[str]) -> bool:
    """Determina si una URL apunta a loopback o adreça privada de xarxa local."""
    if not raw_url or not str(raw_url).strip():
        return False
    try:
        parsed = urllib.parse.urlparse(str(raw_url).strip())
        hostname = (parsed.hostname or "").lower()
        if not hostname:
            return False
        if hostname in ("127.0.0.1", "localhost", "host.docker.internal", "::1"):
            return True
        ip_obj = ipaddress.ip_address(hostname)
        return ip_obj.is_private or ip_obj.is_loopback or ip_obj.is_link_local
    except ValueError:
        return hostname.endswith(".local")
    except Exception:
        return False


def resoldre_url_tunel_ia(
    node_ia_url: Optional[str],
    disc_dur_url: Optional[str] = None,
) -> Optional[str]:
    """Retorna la URL HTTP del node IA (o el túnel unificat disc_dur_url `:9001` que proxieja `/v1/*`)."""
    node_clean = node_ia_url.strip() if isinstance(node_ia_url, str) and node_ia_url.strip() else ""
    disc_clean = (
        disc_dur_url.strip()
        if isinstance(disc_dur_url, str) and disc_dur_url.strip().startswith(("http://", "https://"))
        else ""
    )

    # Si node_ia_url és loopback/LAN privada però disc_dur_url és un túnel HTTP(S) públic,
    # prioritzar sempre el túnel públic cap a client_vault_agent.py (:9001 que proxieja /v1/*).
    if (
        node_clean
        and disc_clean
        and is_private_or_loopback_url(node_clean)
        and not is_private_or_loopback_url(disc_clean)
    ):
        return disc_clean

    if node_clean:
        return node_clean
    if disc_clean:
        return disc_clean
    return None


def get_candidate_ia_tunnel_urls(
    node_ia_url: Optional[str],
    disc_dur_url: Optional[str] = None,
) -> List[str]:
    """Retorna totes les URLs candidates d'HTTP(S) per contactar la IA local de l'empresa."""
    node_clean = (
        node_ia_url.strip()
        if isinstance(node_ia_url, str) and node_ia_url.strip().startswith(("http://", "https://"))
        else ""
    )
    disc_clean = (
        disc_dur_url.strip()
        if isinstance(disc_dur_url, str) and disc_dur_url.strip().startswith(("http://", "https://"))
        else ""
    )

    ordered_sources: List[str] = []
    if (
        node_clean
        and disc_clean
        and is_private_or_loopback_url(node_clean)
        and not is_private_or_loopback_url(disc_clean)
    ):
        ordered_sources = [disc_clean, node_clean]
    else:
        if node_clean:
            ordered_sources.append(node_clean)
        if disc_clean and disc_clean != node_clean:
            ordered_sources.append(disc_clean)

    candidates: List[str] = []
    for src in ordered_sources:
        for cand in get_candidate_node_urls(src) or [src.rstrip("/")]:
            if cand not in candidates:
                candidates.append(cand)
    return candidates


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


def resolve_effective_node_url(raw_url: Optional[str]) -> Optional[str]:
    """Resol l'adreça efectiva per connectar a un node dedicat (en cas d'estar en contenidor Docker)."""
    if not raw_url:
        return None

    candidates = get_candidate_node_urls(raw_url)
    if len(candidates) <= 1:
        return candidates[0] if candidates else None

    # Si estem dins de Docker, prioritzar la passarel·la per sortir del contenidor
    if os.path.exists("/.dockerenv"):
        for c in candidates:
            if "127.0.0.1" not in c and "localhost" not in c:
                return c

    return candidates[0]


def build_node_ia_headers(
    api_key: Optional[str] = None,
    vault_token: Optional[str] = None,
    extra: Optional[Dict[str, str]] = None,
) -> Dict[str, str]:
    """Construeix les capçaleres HTTP cap al node IA / passarel·la sobirana de l'empresa."""
    headers: Dict[str, str] = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    if vault_token and vault_token.strip():
        headers["X-Vault-Token"] = vault_token.strip()
    if extra:
        headers.update(extra)
    return headers
