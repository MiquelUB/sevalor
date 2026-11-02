"""Utilitats de xarxa per a la resolució d'adreces de nodes locals i contenidors."""

import os
import socket
import struct
import urllib.parse
from typing import List, Optional


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
        if hostname in ("127.0.0.1", "localhost"):
            gateways = get_docker_host_gateways()
            port_suffix = f":{parsed.port}" if parsed.port else ""
            scheme = parsed.scheme or "http"
            path = parsed.path or ""
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
