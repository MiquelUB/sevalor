#!/usr/bin/env bash
# Instal·lador de Producció de la Passarel·la Sobirana de Sevalor Suite (Disc Dur + Proxy Copilot IA)
# Apte per a qualsevol empresa client amb ordinador dedicat Linux (systemd).
#
# Ús recomanat:
#   bash scripts/install_client_gateway.sh \
#     --token svlt_... \
#     --disk-a /mnt/disc_principal/sevalor_docs \
#     --disk-b /mnt/disc_mirall/sevalor_backup \
#     --llm-url http://127.0.0.1:1234 \
#     --tunnel-token <CLOUDFLARE_TUNNEL_TOKEN>

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
AGENT_SRC="${SCRIPT_DIR}/client_vault_agent.py"

VAULT_TOKEN="${SEVALOR_VAULT_SECRET:-}"
DISK_A="${SEVALOR_VAULT_PATH_A:-}"
DISK_B="${SEVALOR_VAULT_PATH_B:-}"
LLM_URL="${SEVALOR_LOCAL_LLM_URL:-http://127.0.0.1:1234}"
PORT="${PORT:-9001}"
HOST="${HOST:-127.0.0.1}"
INSTALL_DIR=""
TUNNEL_TOKEN="${CLOUDFLARE_TUNNEL_TOKEN:-}"
ENABLE_SYSTEMD=1

usage() {
  cat <<'EOF'
Ús: install_client_gateway.sh --token <svlt_...> --disk-a <ruta_A> [opcions]

Opcions obligatòries:
  --token <token>         Token únic de l'empresa (vault_token del Superadmin)
  --disk-a <ruta>         Carpeta del Disc Dur Primari A (ex. /mnt/empresa/docs)

Opcions recomanades:
  --disk-b <ruta>         Carpeta del Disc Secundari B mirall (defecte: <disk-a>_backup_B)
  --llm-url <url>         URL del motor IA local LM Studio/Ollama (defecte: http://127.0.0.1:1234)
  --tunnel-token <tok>    Token d'un Cloudflare Tunnel persistent (recomanat en producció)
  --port <port>           Port local de la passarel·la (defecte: 9001)
  --host <ip>             IP d'escolta (defecte: 127.0.0.1; usa 0.0.0.0 sense túnel)
  --install-dir <ruta>    Directori d'instal·lació de l'agent i venv
  --no-systemd            Prepara venv i .env sense registrar serveis systemd
  -h, --help              Mostra aquesta ajuda
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --token)
      VAULT_TOKEN="${2:-}"
      shift 2
      ;;
    --disk-a)
      DISK_A="${2:-}"
      shift 2
      ;;
    --disk-b)
      DISK_B="${2:-}"
      shift 2
      ;;
    --llm-url)
      LLM_URL="${2:-}"
      shift 2
      ;;
    --port)
      PORT="${2:-}"
      shift 2
      ;;
    --host)
      HOST="${2:-}"
      shift 2
      ;;
    --install-dir)
      INSTALL_DIR="${2:-}"
      shift 2
      ;;
    --tunnel-token)
      TUNNEL_TOKEN="${2:-}"
      shift 2
      ;;
    --no-systemd)
      ENABLE_SYSTEMD=0
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Opció desconeguda: $1" >&2
      usage
      exit 2
      ;;
  esac
done

if [[ -z "${VAULT_TOKEN}" || -z "${DISK_A}" ]]; then
  echo "ERROR: Cal indicar --token i --disk-a." >&2
  usage
  exit 2
fi

if [[ ! -f "${AGENT_SRC}" ]]; then
  echo "ERROR: No s'ha trobat ${AGENT_SRC}." >&2
  exit 1
fi

if [[ -z "${DISK_B}" ]]; then
  DISK_B="${DISK_A%/}_backup_B"
fi

if [[ "$(id -u)" -eq 0 ]]; then
  INSTALL_DIR="${INSTALL_DIR:-/opt/sevalor-gateway}"
  ENV_DIR="/etc/sevalor"
  SERVICE_MODE="system"
else
  INSTALL_DIR="${INSTALL_DIR:-${HOME}/.local/share/sevalor-gateway}"
  ENV_DIR="${HOME}/.config/sevalor"
  SERVICE_MODE="user"
fi

ENV_FILE="${ENV_DIR}/vault-agent.env"
VENV_DIR="${INSTALL_DIR}/.venv"

echo "[1/5] Preparant directoris del disc dur sobirà..."
mkdir -p "${DISK_A}" "${DISK_B}" "${INSTALL_DIR}" "${ENV_DIR}"
chmod 700 "${ENV_DIR}"

echo "[2/5] Instal·lant client_vault_agent.py i dependències Python a ${VENV_DIR}..."
cp "${AGENT_SRC}" "${INSTALL_DIR}/client_vault_agent.py"

if ! command -v python3 >/dev/null 2>&1; then
  echo "ERROR: python3 no està instal·lat en aquest equip." >&2
  exit 1
fi

if [[ ! -d "${VENV_DIR}" ]]; then
  python3 -m venv "${VENV_DIR}"
fi

"${VENV_DIR}/bin/pip" install --quiet --upgrade pip
"${VENV_DIR}/bin/pip" install --quiet "fastapi>=0.110.0" "uvicorn[standard]>=0.29.0" "httpx>=0.27.0" "python-multipart>=0.0.9"

echo "[3/5] Desant configuració segura a ${ENV_FILE} (permisos 600)..."
umask 077
{
  printf 'SEVALOR_VAULT_SECRET=%s\n' "${VAULT_TOKEN}"
  printf 'SEVALOR_VAULT_PATH_A=%s\n' "${DISK_A}"
  printf 'SEVALOR_VAULT_PATH_B=%s\n' "${DISK_B}"
  printf 'SEVALOR_LOCAL_LLM_URL=%s\n' "${LLM_URL}"
  printf 'HOST=%s\n' "${HOST}"
  printf 'PORT=%s\n' "${PORT}"
  if [[ -n "${TUNNEL_TOKEN}" ]]; then
    printf 'TUNNEL_TOKEN=%s\n' "${TUNNEL_TOKEN}"
  fi
} > "${ENV_FILE}"
chmod 600 "${ENV_FILE}"

echo "[4/5] Verificant l'agent i la inicialització de carpetes..."
"${VENV_DIR}/bin/python" -c "
import os, sys
sys.path.insert(0, '${INSTALL_DIR}')
os.environ['SEVALOR_VAULT_PATH_A'] = '${DISK_A}'
os.environ['SEVALOR_VAULT_PATH_B'] = '${DISK_B}'
os.environ['SEVALOR_VAULT_SECRET'] = '${VAULT_TOKEN}'
import client_vault_agent as cva
cva.inicialitzar_estructura_disc()
print(f'Carpetes inicialitzades: {len(cva.CARPETES_OFICIALS)} a ${DISK_A}')
"

if [[ "${ENABLE_SYSTEMD}" -eq 0 ]]; then
  echo "[5/5] Mode --no-systemd actiu. Arrencada manual:"
  echo "  set -a && source '${ENV_FILE}' && set +a && '${VENV_DIR}/bin/python' '${INSTALL_DIR}/client_vault_agent.py'"
  exit 0
fi

if ! command -v systemctl >/dev/null 2>&1; then
  echo "AVÍS: systemctl no disponible; arrencada manual:"
  echo "  set -a && source '${ENV_FILE}' && set +a && '${VENV_DIR}/bin/python' '${INSTALL_DIR}/client_vault_agent.py'"
  exit 0
fi

echo "[5/5] Registrant serveis systemd (${SERVICE_MODE})..."
if [[ "${SERVICE_MODE}" == "system" ]]; then
  UNIT_DIR="/etc/systemd/system"
  SYSTEMCTL=(systemctl)
else
  UNIT_DIR="${HOME}/.config/systemd/user"
  mkdir -p "${UNIT_DIR}"
  SYSTEMCTL=(systemctl --user)
fi

cat > "${UNIT_DIR}/sevalor-vault-agent.service" <<EOF
[Unit]
Description=Sevalor Client Sovereign Gateway (Disc Dur + Proxy Copilot IA)
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
WorkingDirectory=${INSTALL_DIR}
EnvironmentFile=${ENV_FILE}
ExecStart=${VENV_DIR}/bin/uvicorn client_vault_agent:app --host ${HOST} --port ${PORT}
Restart=always
RestartSec=3

[Install]
WantedBy=default.target
EOF

if [[ -n "${TUNNEL_TOKEN}" ]]; then
  CF_BIN="$(command -v cloudflared || true)"
  if [[ -z "${CF_BIN}" ]]; then
    CF_BIN="${INSTALL_DIR}/cloudflared"
    if [[ ! -x "${CF_BIN}" ]]; then
      echo "Descarregant cloudflared a ${CF_BIN}..."
      ARCH="$(uname -m)"
      case "${ARCH}" in
        x86_64|amd64) CF_ARCH="amd64" ;;
        aarch64|arm64) CF_ARCH="arm64" ;;
        *)
          echo "ERROR: Arquitectura no suportada automàticament per cloudflared: ${ARCH}" >&2
          exit 1
          ;;
      esac
      curl -fsSL "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-${CF_ARCH}" -o "${CF_BIN}"
      chmod 755 "${CF_BIN}"
    fi
  fi

  cat > "${UNIT_DIR}/sevalor-vault-tunnel.service" <<EOF
[Unit]
Description=Sevalor Cloudflare Tunnel cap a la Passarel·la Client (127.0.0.1:${PORT})
After=network-online.target sevalor-vault-agent.service
Requires=sevalor-vault-agent.service

[Service]
Type=simple
EnvironmentFile=${ENV_FILE}
ExecStart=${CF_BIN} tunnel --no-autoupdate run
Restart=always
RestartSec=5

[Install]
WantedBy=default.target
EOF
fi

"${SYSTEMCTL[@]}" daemon-reload
"${SYSTEMCTL[@]}" enable --now sevalor-vault-agent.service
if [[ -n "${TUNNEL_TOKEN}" ]]; then
  "${SYSTEMCTL[@]}" enable --now sevalor-vault-tunnel.service
fi

echo "✅ Passarel·la Sevalor instal·lada i activa a http://${HOST}:${PORT}"
if [[ "${SERVICE_MODE}" == "user" ]]; then
  echo "Consell producció: executa 'sudo loginctl enable-linger ${USER}' perquè el servei segueixi actiu sense sessió oberta."
fi
