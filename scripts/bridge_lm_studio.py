#!/usr/bin/env python3
"""Bridge local per a LM Studio (127.0.0.1:1234) cap a interfícies de xarxa de Docker.

Permet que els contenidors Docker de Sevalor Suite (sevalor_backend, celery_worker)
connectin de forma transparent amb LM Studio executat a l'ordinador host encara que
LM Studio estigui vinculat exclusivament a 127.0.0.1.
"""
import os
import re
import socket
import subprocess
import threading
import time

TARGET_HOST = "127.0.0.1"
TARGET_PORT = 1234


def get_bridge_ips():
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


def pipe(s1, s2):
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


def handle_client(client_sock):
    try:
        remote_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        remote_sock.connect((TARGET_HOST, TARGET_PORT))
        t1 = threading.Thread(target=pipe, args=(client_sock, remote_sock), daemon=True)
        t2 = threading.Thread(target=pipe, args=(remote_sock, client_sock), daemon=True)
        t1.start()
        t2.start()
    except Exception:
        try:
            client_sock.close()
        except Exception:
            pass


def listen_on_ip(ip, port):
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        server.bind((ip, port))
        server.listen(50)
        print(f"[*] Bridge actiu a {ip}:{port} -> {TARGET_HOST}:{TARGET_PORT}", flush=True)
        while True:
            client, _ = server.accept()
            threading.Thread(target=handle_client, args=(client,), daemon=True).start()
    except Exception as e:
        print(f"[-] No s'ha pogut vincular {ip}:{port}: {e}", flush=True)


def main():
    ips = get_bridge_ips()
    print(f"[*] Inicialitzant bridge LM Studio per a IPs: {ips}", flush=True)
    threads = []
    for ip in ips:
        t = threading.Thread(target=listen_on_ip, args=(ip, TARGET_PORT), daemon=True)
        t.start()
        threads.append(t)

    while True:
        time.sleep(1)


if __name__ == "__main__":
    main()
