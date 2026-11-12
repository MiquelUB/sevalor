"""Proves reals de seguretat Zero-Trust per a la passarel·la unificada (Copilot + Disc Dur) i l'instal·lador."""

from __future__ import annotations

import json
import os
import secrets
import socket
import subprocess
import sys
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict, List

import httpx
import pytest
from fastapi.testclient import TestClient
from httpx import ASGITransport, AsyncClient

ROOT_DIR = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = ROOT_DIR / "scripts"
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import scripts.client_vault_agent as vault_agent  # noqa: E402

from app.api.v1.gestio.copilot import cridar_lm_studio  # noqa: E402
from app.core.db import set_tenant_context  # noqa: E402
from app.core.security import create_access_token  # noqa: E402
from app.main import app  # noqa: E402
from app.models.models import Empresa  # noqa: E402
from app.services.llm_client import LLMClient  # noqa: E402


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


def test_vault_agent_v1_proxy_exigeix_x_vault_token_i_l_elimina_cap_a_llm(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`/v1/*` ha de rebutjar sense token (403), acceptar amb token vàlid i no filtrar el secret a LM Studio."""
    llm_srv, llm_url, recorded_headers = _start_local_llm_http_server()
    secret = f"svlt_{secrets.token_urlsafe(16)}"

    monkeypatch.setattr(vault_agent, "VAULT_PRIMARY_A", tmp_path / "a")
    monkeypatch.setattr(vault_agent, "VAULT_SECONDARY_B", tmp_path / "b")
    monkeypatch.setattr(vault_agent, "VAULT_SECRET", secret)
    monkeypatch.setattr(vault_agent, "LOCAL_LLM_BASE_URL", llm_url)

    try:
        client = TestClient(vault_agent.app)

        # 1. Sense token -> 403
        r_no_tok = client.get("/v1/models")
        assert r_no_tok.status_code == 403

        # 2. Token incorrecte -> 403
        r_bad_tok = client.post(
            "/v1/chat/completions",
            json={"model": "local", "messages": [{"role": "user", "content": "hola"}]},
            headers={"X-Vault-Token": "svlt_incorrecte"},
        )
        assert r_bad_tok.status_code == 403

        # 3. Token vàlid -> 200 i `x-vault-token` eliminat abans d'arribar al LLM local
        r_models = client.get("/v1/models", headers={"X-Vault-Token": secret})
        assert r_models.status_code == 200
        assert r_models.json()["data"][0]["id"] == "qwen2.5-vl-7b-instruct"

        r_chat = client.post(
            "/v1/chat/completions",
            json={"model": "local", "messages": [{"role": "user", "content": "hola"}]},
            headers={"X-Vault-Token": secret},
        )
        assert r_chat.status_code == 200
        assert r_chat.json()["choices"][0]["message"]["content"] == "Resposta IA sobirana OK"
        assert len(recorded_headers) == 2
        for hdrs in recorded_headers:
            assert "x-vault-token" not in hdrs
    finally:
        llm_srv.shutdown()
        llm_srv.server_close()


@pytest.mark.asyncio
async def test_backend_copilot_i_verificar_node_ia_envien_vault_token_real(
    tmp_path: Path,
    db_session: Any,
) -> None:
    """Verifica E2E que verificar-node-ia, cridar_lm_studio i LLMClient envien X-Vault-Token a la passarel·la real."""
    llm_srv, llm_url, _ = _start_local_llm_http_server()
    token_emp = f"svlt_{secrets.token_urlsafe(20)}"
    port_agent = _find_free_port()
    env = os.environ.copy()
    env["PYTHONPATH"] = str(SCRIPTS_DIR) + os.pathsep + env.get("PYTHONPATH", "")
    env["SEVALOR_VAULT_PATH_A"] = str(tmp_path / "disc_a")
    env["SEVALOR_VAULT_PATH_B"] = str(tmp_path / "disc_b")
    env["SEVALOR_VAULT_SECRET"] = token_emp
    env["SEVALOR_LOCAL_LLM_URL"] = llm_url
    env["HOST"] = "127.0.0.1"
    env["PORT"] = str(port_agent)

    proc = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "client_vault_agent:app",
            "--host",
            "127.0.0.1",
            "--port",
            str(port_agent),
            "--log-level",
            "warning",
        ],
        cwd=str(SCRIPTS_DIR),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    gateway_url = f"http://127.0.0.1:{port_agent}"

    try:
        for _ in range(50):
            if proc.poll() is not None:
                _, err = proc.communicate(timeout=2)
                raise RuntimeError(f"Agent caigut: {err.decode()}")
            try:
                if httpx.get(f"{gateway_url}/health", timeout=0.5).status_code == 200:
                    break
            except Exception:
                time.sleep(0.1)

        emp_id = uuid.uuid4()
        await set_tenant_context(db_session, str(emp_id), is_superadmin=True)
        emp = Empresa(
            id=emp_id,
            nom="Empresa Passarela Test SL",
            nif=f"B{secrets.randbelow(90000000) + 10000000}",
            subdomini=f"passarela-{uuid.uuid4().hex[:8]}",
            node_ia_url=gateway_url,
            disc_dur_url=gateway_url,
            node_ia_actiu=True,
            feature_copilot_ia=True,
            vault_token=token_emp,
        )
        db_session.add(emp)
        await db_session.commit()

        sa_token = create_access_token(
            {
                "sub": str(uuid.uuid4()),
                "email": "sa-gateway@sevalor.app",
                "rol": "SUPERADMIN",
                "empresa_id": None,
                "totp_activat": True,
                "ip_allowlist": ["*"],
            }
        )
        sa_headers = {"Authorization": f"Bearer {sa_token}"}

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            # 1. Token erroni -> TOKEN_INVALID
            bad_probe = await ac.post(
                "/api/v1/superadmin/tenants/verificar-node-ia",
                json={"node_ia_url": gateway_url, "vault_token": "svlt_dolent"},
                headers=sa_headers,
            )
            assert bad_probe.status_code == 200
            assert bad_probe.json()["status"] == "ERROR"
            assert bad_probe.json()["motiu"] == "TOKEN_INVALID"

            # 2. Via empresa_id (llegeix vault_token de PostgreSQL) -> OK
            good_probe = await ac.post(
                "/api/v1/superadmin/tenants/verificar-node-ia",
                json={"node_ia_url": gateway_url, "empresa_id": str(emp_id)},
                headers=sa_headers,
            )
            assert good_probe.status_code == 200
            assert good_probe.json()["status"] == "OK"
            assert "qwen2.5-vl-7b-instruct" in good_probe.json()["models"]

        # 3. cridar_lm_studio amb empresa passa X-Vault-Token
        resposta = await cridar_lm_studio("Test connexió", empresa=emp)
        assert resposta == "Resposta IA sobirana OK"

        # 4. LLMClient directe amb vault_token passa X-Vault-Token
        llm_client = LLMClient(base_url=f"{gateway_url}/v1", vault_token=token_emp)
        chat_res = await llm_client.chat_completion(
            messages=[{"role": "user", "content": "Test LLMClient"}]
        )
        assert chat_res["choices"][0]["message"]["content"] == "Resposta IA sobirana OK"
    finally:
        if proc.poll() is None:
            proc.terminate()
            proc.wait(timeout=5)
        llm_srv.shutdown()
        llm_srv.server_close()


def test_install_client_gateway_script_validacio_arguments() -> None:
    """Verifica que l'instal·lador valida --help i rebutja execucions sense --token/--disk-a."""
    script_path = SCRIPTS_DIR / "install_client_gateway.sh"
    assert script_path.is_file()

    r_help = subprocess.run(
        ["bash", str(script_path), "--help"],
        capture_output=True,
        text=True,
        timeout=5,
    )
    assert r_help.returncode == 0
    assert "--token" in r_help.stdout
    assert "--tunnel-token" in r_help.stdout

    r_missing = subprocess.run(
        ["bash", str(script_path)],
        capture_output=True,
        text=True,
        timeout=5,
    )
    assert r_missing.returncode == 2
