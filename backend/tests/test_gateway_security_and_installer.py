"""Proves reals de seguretat Zero-Trust per a l'Agent Sobirà WSS (Copilot + Disc Dur) i l'instal·lador 1-clic."""

from __future__ import annotations

import json
import secrets
import socket
import subprocess
import sys
import threading
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict, List

import pytest

ROOT_DIR = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = ROOT_DIR / "scripts"
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import scripts.client_vault_agent as vault_agent  # noqa: E402


def _find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


def _start_local_llm_http_server() -> tuple[ThreadingHTTPServer, str, List[Dict[str, str]]]:
    """Servidor HTTP real en port efímer que simula LM Studio local i registra capçaleres rebudes."""
    recorded_headers: List[Dict[str, str]] = []

    class _Handler(BaseHTTPRequestHandler):
        def log_message(self, format: str, *args: Any) -> None:
            return

        def do_GET(self) -> None:
            recorded_headers.append({k.lower(): v for k, v in self.headers.items()})
            if self.path == "/v1/models":
                body = json.dumps({"data": [{"id": "qwen2.5-vl-7b-instruct"}]}).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            else:
                self.send_response(404)
                self.end_headers()

        def do_POST(self) -> None:
            recorded_headers.append({k.lower(): v for k, v in self.headers.items()})
            length = int(self.headers.get("Content-Length", "0"))
            _ = self.rfile.read(length) if length > 0 else b""
            if self.path == "/v1/chat/completions":
                body = json.dumps(
                    {
                        "choices": [
                            {"message": {"role": "assistant", "content": "Resposta IA sobirana OK"}}
                        ]
                    }
                ).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            else:
                self.send_response(404)
                self.end_headers()

    server = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    port = server.server_address[1]
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()
    return server, f"http://127.0.0.1:{port}", recorded_headers


@pytest.mark.asyncio
async def test_vault_agent_wss_llm_no_filtra_x_vault_token_cap_a_llm(tmp_path: Path) -> None:
    """L'agent WSS ha d'enrutar llm_models i llm_chat al motor local sense filtrar mai el token del túnel."""
    llm_srv, llm_url, recorded_headers = _start_local_llm_http_server()
    secret = f"svlt_{secrets.token_urlsafe(16)}"

    agent = vault_agent.SovereignWssAgent(
        vault_agent.AgentConfig(
            server_url="https://sevalor-sevalor-backend.80opze.easypanel.host",
            role="EMPRESA",
            empresa_id=str(uuid.uuid4()),
            vault_token=secret,
            disk_a=tmp_path / "a",
            disk_b=tmp_path / "b",
            local_llm_url=llm_url,
        )
    )

    try:
        models_res = await agent.execute_action("llm_models", {})
        assert models_res["data"][0]["id"] == "qwen2.5-vl-7b-instruct"

        chat_res = await agent.execute_action(
            "llm_chat",
            {
                "model": "qwen2.5-vl-7b-instruct",
                "messages": [{"role": "user", "content": "hola"}],
                "x-vault-token": secret,
            },
        )
        assert chat_res["choices"][0]["message"]["content"] == "Resposta IA sobirana OK"

        assert len(recorded_headers) >= 2
        for hdrs in recorded_headers:
            assert "x-vault-token" not in hdrs
            assert secret not in json.dumps(hdrs)
    finally:
        llm_srv.shutdown()
        llm_srv.server_close()


def test_install_client_gateway_script_validacio_arguments() -> None:
    """Verifica el contracte 1-clic WSS de scripts/install_client_gateway.sh (Zero Cloudflare, Zero ports)."""
    script_path = SCRIPTS_DIR / "install_client_gateway.sh"
    assert script_path.is_file()
    script_src = script_path.read_text(encoding="utf-8")

    # ADR-001 (Fase 2): Zero Cloudflare Tunnel, zero Uvicorn/FastAPI, zero ports TCP entrants
    assert "cloudflared" not in script_src
    assert "--tunnel-token" not in script_src
    assert "uvicorn" not in script_src
    assert "fastapi" not in script_src
    assert "websockets" in script_src

    r_help = subprocess.run(
        ["bash", str(script_path), "--help"],
        capture_output=True,
        text=True,
        timeout=5,
    )
    assert r_help.returncode == 0
    for required_flag in ("--server", "--role", "--empresa-id", "--token", "--disk-a", "--llm-url"):
        assert required_flag in r_help.stdout
    for forbidden_flag in ("--tunnel-token", "--port", "--host"):
        assert forbidden_flag not in r_help.stdout

    # Opcions prohibides (Cloudflare / port entrant) rebutjades amb codi 2
    for bad_args in (
        ["--tunnel-token", "cf_fake", "--token", "svlt_1", "--disk-a", "/tmp/x"],
        ["--port", "9001", "--token", "svlt_1", "--disk-a", "/tmp/x"],
        ["--role", "EMPRESA", "--token", "svlt_1", "--disk-a", "/tmp/x"],  # falta --empresa-id
        ["--role", "EMPRESA", "--empresa-id", "no-uuid", "--token", "svlt_1", "--disk-a", "/tmp/x"],
        [
            "--role",
            "SUPERADMIN",
            "--empresa-id",
            str(uuid.uuid4()),
            "--token",
            "sa_tok",
            "--disk-a",
            "/tmp/x",
        ],
    ):
        r_bad = subprocess.run(
            ["bash", str(script_path), *bad_args],
            capture_output=True,
            text=True,
            timeout=5,
        )
        assert r_bad.returncode == 2, f"Hauria de rebutjar {bad_args}, obtingut {r_bad.returncode}"

    r_missing = subprocess.run(
        ["bash", str(script_path)],
        capture_output=True,
        text=True,
        timeout=5,
    )
    assert r_missing.returncode == 2
