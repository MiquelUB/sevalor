#!/usr/bin/env bash
# Instal·lador 1-Clic de l'Agent Sobirà WSS de Sevalor Suite (Disc Dur + Copilot IA Local)
# ADR-001 (Fase 2): Connexió SORTINT WSS port 443 cap al backend de Hetzner.
# ZERO Cloudflare Tunnel, ZERO ports entrants oberts, ZERO Uvicorn local.
#
# Ús EMPRESA:
#   bash scripts/install_client_gateway.sh \
#     --server https://sevalor-sevalor-backend.80opze.easypanel.host \
#     --role EMPRESA \
#     --empresa-id <UUID_EMPRESA> \
#     --token <svlt_...> \
#     --disk-a /mnt/disc_principal/sevalor_docs \
#     --disk-b /mnt/disc_mirall/sevalor_backup \
#     --llm-url http://127.0.0.1:1234
#
# Ús SUPERADMIN:
#   bash scripts/install_client_gateway.sh \
#     --server https://sevalor-sevalor-backend.80opze.easypanel.host \
#     --role SUPERADMIN \
#     --token <SUPERADMIN_VAULT_SECRET> \
#     --disk-a /media/akaun/Project_1/Sevalor_Superadmin_docs \
#     --llm-url http://127.0.0.1:1234

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
AGENT_SRC="${SCRIPT_DIR}/client_vault_agent.py"

SERVER_URL="${SEVALOR_SERVER_URL:-https://sevalor-sevalor-backend.80opze.easypanel.host}"
VAULT_ROLE="${SEVALOR_VAULT_ROLE:-EMPRESA}"
EMPRESA_ID="${SEVALOR_EMPRESA_ID:-}"
VAULT_TOKEN="${SEVALOR_VAULT_SECRET:-}"
DISK_A="${SEVALOR_VAULT_PATH_A:-}"
DISK_B="${SEVALOR_VAULT_PATH_B:-}"
LLM_URL="${SEVALOR_LOCAL_LLM_URL:-http://127.0.0.1:1234}"
INSTALL_DIR=""
ENABLE_SYSTEMD=1

usage() {
  cat <<'EOF'
Ús: install_client_gateway.sh --token <token> --disk-a <ruta_A> [--empresa-id <uuid>] [opcions]

Opcions obligatòries:
  --token <token>         Token únic del túnel (vault_token de l'empresa o SUPERADMIN_VAULT_SECRET)
  --disk-a <ruta>         Carpeta del Disc Dur Primari A (ex. /mnt/empresa/docs)
  --empresa-id <uuid>     UUID de l'empresa (obligatori si --role EMPRESA; prohibit si SUPERADMIN)

Opcions recomanades:
  --server <url>          URL pública del backend Sevalor (defecte: https://sevalor-sevalor-backend.80opze.easypanel.host)
  --role <EMPRESA|SUPERADMIN>
                          Perfil del node (defecte: EMPRESA -> 38 carpetes; SUPERADMIN -> 20 carpetes)
  --disk-b <ruta>         Carpeta del Disc Secundari B mirall (defecte: <disk-a>_backup_B)
  --llm-url <url>         URL del motor IA local LM Studio/Ollama (defecte: http://127.0.0.1:1234)
  --install-dir <ruta>    Directori d'instal·lació de l'agent i venv
  --no-systemd            Prepara venv, carpetes i .env sense registrar servei systemd
  -h, --help              Mostra aquesta ajuda
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --server)
      SERVER_URL="${2:-}"
      shift 2
      ;;
    --role)
      VAULT_ROLE="${2:-}"
      shift 2
      ;;
    --empresa-id)
      EMPRESA_ID="${2:-}"
      shift 2
      ;;
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
    --install-dir)
      INSTALL_DIR="${2:-}"
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
      echo "Opció desconeguda o prohibida per ADR-001: $1" >&2
      usage
      exit 2
      ;;
  esac
done

VAULT_ROLE="$(printf '%s' "${VAULT_ROLE}" | tr '[:lower:]' '[:upper:]')"
if [[ "${VAULT_ROLE}" != "EMPRESA" && "${VAULT_ROLE}" != "SUPERADMIN" ]]; then
  echo "ERROR: --role ha de ser EMPRESA o SUPERADMIN (rebut: ${VAULT_ROLE})." >&2
  exit 2
fi

if [[ -z "${VAULT_TOKEN}" || -z "${DISK_A}" || -z "${SERVER_URL}" ]]; then
  echo "ERROR: Cal indicar --token, --disk-a i --server." >&2
  usage
  exit 2
fi

if [[ "${VAULT_ROLE}" == "EMPRESA" ]]; then
  if [[ -z "${EMPRESA_ID}" ]]; then
    echo "ERROR: Cal indicar --empresa-id <UUID> quan --role és EMPRESA." >&2
    usage
    exit 2
  fi
  if [[ ! "${EMPRESA_ID}" =~ ^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$ ]]; then
    echo "ERROR: --empresa-id ha de ser un UUID vàlid (rebut: ${EMPRESA_ID})." >&2
    exit 2
  fi
else
  if [[ -n "${EMPRESA_ID}" ]]; then
    echo "ERROR: --empresa-id no es pot utilitzar amb --role SUPERADMIN." >&2
    exit 2
  fi
fi

if [[ ! -f "${AGENT_SRC}" ]]; then
  echo "ERROR: No s'ha trobat ${AGENT_SRC}." >&2
  exit 1
fi

if [[ -z "${DISK_B}" ]]; then
  DISK_B="${DISK_A%/}_backup_B"
fi

if [[ "${VAULT_ROLE}" == "SUPERADMIN" ]]; then
  ENV_BASENAME="vault-superadmin.env"
  SERVICE_AGENT="sevalor-superadmin-vault-agent"
  DEFAULT_SUBDIR="sevalor-superadmin-gateway"
else
  ENV_BASENAME="vault-agent.env"
  SERVICE_AGENT="sevalor-vault-agent"
  DEFAULT_SUBDIR="sevalor-gateway"
fi

if [[ "$(id -u)" -eq 0 ]]; then
  INSTALL_DIR="${INSTALL_DIR:-/opt/${DEFAULT_SUBDIR}}"
  ENV_DIR="/etc/sevalor"
  SERVICE_MODE="system"
else
  INSTALL_DIR="${INSTALL_DIR:-${HOME}/.local/share/${DEFAULT_SUBDIR}}"
  ENV_DIR="${HOME}/.config/sevalor"
  SERVICE_MODE="user"
fi

ENV_FILE="${ENV_DIR}/${ENV_BASENAME}"
VENV_DIR="${INSTALL_DIR}/.venv"

echo "[1/5] Preparant directoris del disc dur sobirà (${VAULT_ROLE})..."
mkdir -p "${DISK_A}" "${DISK_B}" "${INSTALL_DIR}" "${ENV_DIR}"
chmod 700 "${ENV_DIR}"

echo "[2/5] Instal·lant client_vault_agent.py i dependències WSS lleugeres a ${VENV_DIR}..."
cp "${AGENT_SRC}" "${INSTALL_DIR}/client_vault_agent.py"

if ! command -v python3 >/dev/null 2>&1; then
  echo "ERROR: python3 no està instal·lat en aquest equip." >&2
  exit 1
fi

if [[ ! -d "${VENV_DIR}" ]]; then
  python3 -m venv "${VENV_DIR}"
fi

"${VENV_DIR}/bin/pip" install --quiet --upgrade pip
"${VENV_DIR}/bin/pip" install --quiet "websockets>=13.0" "httpx>=0.27.0"

echo "[3/5] Desant configuració segura a ${ENV_FILE} (permisos 600)..."
umask 077
{
  printf 'SEVALOR_SERVER_URL=%s\n' "${SERVER_URL}"
  printf 'SEVALOR_VAULT_ROLE=%s\n' "${VAULT_ROLE}"
  if [[ -n "${EMPRESA_ID}" ]]; then
    printf 'SEVALOR_EMPRESA_ID=%s\n' "${EMPRESA_ID}"
  fi
  printf 'SEVALOR_VAULT_SECRET=%s\n' "${VAULT_TOKEN}"
  printf 'SEVALOR_VAULT_PATH_A=%s\n' "${DISK_A}"
  printf 'SEVALOR_VAULT_PATH_B=%s\n' "${DISK_B}"
  printf 'SEVALOR_LOCAL_LLM_URL=%s\n' "${LLM_URL}"
} > "${ENV_FILE}"
chmod 600 "${ENV_FILE}"

echo "[4/5] Verificant l'agent i la inicialització de carpetes (${VAULT_ROLE})..."
set -a
# shellcheck disable=SC1090
source "${ENV_FILE}"
set +a
"${VENV_DIR}/bin/python" "${INSTALL_DIR}/client_vault_agent.py" --init-only

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

echo "[5/5] Registrant servei systemd (${SERVICE_MODE} - ${SERVICE_AGENT})..."
if [[ "${SERVICE_MODE}" == "system" ]]; then
  UNIT_DIR="/etc/systemd/system"
  SYSTEMCTL=(systemctl)
else
  UNIT_DIR="${HOME}/.config/systemd/user"
  mkdir -p "${UNIT_DIR}"
  SYSTEMCTL=(systemctl --user)
fi

cat > "${UNIT_DIR}/${SERVICE_AGENT}.service" <<EOF
[Unit]
Description=Sevalor ${VAULT_ROLE} Sovereign WSS Agent (Disc Dur + Copilot IA Local)
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
WorkingDirectory=${INSTALL_DIR}
EnvironmentFile=${ENV_FILE}
ExecStart=${VENV_DIR}/bin/python ${INSTALL_DIR}/client_vault_agent.py
Restart=always
RestartSec=3

[Install]
WantedBy=default.target
EOF

"${SYSTEMCTL[@]}" daemon-reload
"${SYSTEMCTL[@]}" enable --now "${SERVICE_AGENT}.service"

echo "✅ Agent Sobirà WSS Sevalor (${VAULT_ROLE}) instal·lat i connectant a ${SERVER_URL} (zero ports entrants)."
if [[ "${SERVICE_MODE}" == "user" ]]; then
  echo "Consell producció: executa 'sudo loginctl enable-linger ${USER}' perquè el servei segueixi actiu sense sessió oberta."
fi
