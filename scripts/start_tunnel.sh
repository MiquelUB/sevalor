#!/usr/bin/env bash
# Script per exposar LM Studio local (port 1234) a EasyPanel / Hetzner Cloud mitjançant Cloudflare Tunnel

if [ ! -f /tmp/cloudflared ]; then
  echo "Descarregant cloudflared..."
  curl -sL https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64 -o /tmp/cloudflared
  chmod +x /tmp/cloudflared
fi

echo "Iniciant túnel per a LM Studio (http://127.0.0.1:1234)..."
/tmp/cloudflared tunnel --url http://127.0.0.1:1234
