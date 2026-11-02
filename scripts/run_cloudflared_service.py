#!/usr/bin/env python3
"""Llançador persistent de Cloudflare Tunnel per al node local d'IA de Sevalor Suite."""

import os
import re
import subprocess
import sys
import time

CLOUDFLARED_BIN = "/media/akaun/Project_1/SEVALOR/scripts/cloudflared"
URL_FILE = "/media/akaun/Project_1/SEVALOR/scripts/CURRENT_TUNNEL_URL.txt"

def main():
    if not os.path.exists(CLOUDFLARED_BIN):
        print(f"Error: No s'ha trobat {CLOUDFLARED_BIN}", file=sys.stderr)
        sys.exit(1)

    cmd = [CLOUDFLARED_BIN, "tunnel", "--url", "http://127.0.0.1:1234"]
    print(f"Iniciant túnel Cloudflare: {' '.join(cmd)}")

    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )

    url_found = False
    url_pattern = re.compile(r"https://[a-zA-Z0-9-]+\.trycloudflare\.com")

    for line in iter(proc.stdout.readline, ""):
        sys.stdout.write(line)
        sys.stdout.flush()

        if not url_found:
            match = url_pattern.search(line)
            if match:
                tunnel_url = match.group(0)
                url_found = True
                print(f"\n=======================================================")
                print(f"TÚNEL CLOUDFLARE ACTIU: {tunnel_url}")
                print(f"=======================================================\n")
                with open(URL_FILE, "w") as f:
                    f.write(tunnel_url.strip())

    proc.wait()
    sys.exit(proc.returncode)

if __name__ == "__main__":
    main()
