#!/usr/bin/env python3
"""Bridge local per a LM Studio (127.0.0.1:1234) i Agents Sobirans (9001 Empresa, 9002 Superadmin) cap a Docker.

Permet que els contenidors Docker de Sevalor Suite (sevalor_backend, celery_worker)
connectin de forma transparent amb LM Studio, la Passarel·la d'Empresa (9001) i la
Passarel·la Dedicada de Superadmin (9002) executats a 127.0.0.1 a l'ordinador host.
"""
import os
import re
import socket
import subprocess
import threading
import time
from typing import Tuple

TARGET_HOST = "127.0.0.1"
DEFAULT_TARGET_PORTS: Tuple[int, ...] = (1234, 9001, 9002)


def get_target_ports() -> Tuple[int, ...]:
    """Retorna la tupla de ports locals a reenviar des del bridge Docker."""
    raw = os.getenv("SEVALOR_BRIDGE_PORTS", "").strip()
    if not raw:
        return DEFAULT_TARGET_PORTS
    ports = []
    for item in raw.split(","):
        s = item.strip()
        if not s:
            continue
        port = int(s)
        if not (1 <= port <= 65535):
            raise ValueError(f"Port invàlid a SEVALOR_BRIDGE_PORTS: {port}")
        ports.append(port)
    return tuple(ports) if ports else DEFAULT_TARGET_PORTS


TARGET_PORTS: Tuple[int, ...] = get_target_ports()


def get_bridge_ips() -> list[str]:
    """Detecta totes les IPs de passarel·la Docker a l'ordinador host."""
    ips = set()
    try:
        out = subprocess.check_output(["ip", "-o", "-4", "addr", "show"], text=True)
        for line in out.splitlines():
            parts = line.split()
            if len(parts) >= 4:
                cidr = parts[3]
                ip = cidr.split("/")[0]
                # Xarxes privades de Docker (172.16.0.0/12)
                if re.match(r"^172\.(1[6-9]|2[0-9]|3[0-1])\.", ip):
                    ips.add(ip)
    except Exception:
        pass

    # Valors per defecte comuns a Sevalor
    for fallback in ["172.23.0.1", "172.17.0.1", "172.18.0.1", "172.20.0.1"]:
        ips.add(fallback)

    return sorted(list(ips))


def pipe(s1: socket.socket, s2: socket.socket) -> None:
    try:
        while True:
            data = s1.recv(8192)
            if not data:
                break
            s2.sendall(data)
    except Exception:
        pass
    finally:
        try:
            s1.close()
        except Exception:
            pass
        try:
            s2.close()
        except Exception:
            pass


def handle_client(client_sock: socket.socket, target_port: int) -> None:
    try:
        remote_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        remote_sock.connect((TARGET_HOST, target_port))
        t1 = threading.Thread(target=pipe, args=(client_sock, remote_sock), daemon=True)
        t2 = threading.Thread(target=pipe, args=(remote_sock, client_sock), daemon=True)
        t1.start()
        t2.start()
    except Exception:
        try:
            client_sock.close()
        except Exception:
            pass


def listen_on_ip(ip: str, port: int) -> None:
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        server.bind((ip, port))
        server.listen(50)
        print(f"[*] Bridge actiu a {ip}:{port} -> {TARGET_HOST}:{port}", flush=True)
        while True:
            client, _ = server.accept()
            threading.Thread(target=handle_client, args=(client, port), daemon=True).start()
    except Exception as e:
        print(f"[-] No s'ha pogut vincular {ip}:{port}: {e}", flush=True)


def main() -> None:
    ips = get_bridge_ips()
    ports = get_target_ports()
    print(f"[*] Inicialitzant bridge Sevalor per a IPs: {ips} | Ports: {ports}", flush=True)
    threads = []
    for ip in ips:
        for port in ports:
            t = threading.Thread(target=listen_on_ip, args=(ip, port), daemon=True)
            t.start()
            threads.append(t)

    while True:
        time.sleep(1)


if __name__ == "__main__":
    main()
