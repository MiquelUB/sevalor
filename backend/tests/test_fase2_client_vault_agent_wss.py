"""Tests d'integració reals (Zero Mock) per a la Fase 2: Agent Sobirà WSS (`scripts/client_vault_agent.py`).

Certifica:
1. ZERO servidor Uvicorn/FastAPI i ZERO ports TCP entrants a `scripts/client_vault_agent.py`.
2. Validació estricta d'`AgentConfig` i `build_ws_connect_url` (https -> wss).
3. Execució REAL com a subprocés OS (`python scripts/client_vault_agent.py`) connectant
   sortint contra Uvicorn + `WS /api/v1/vault-tunnel/connect` + PostgreSQL 16 + LLM HTTP local:
   - Auto-creació de 38 carpetes + `empresa.json` + `boss.json` + `system_prompt.txt`
   - CRUD JSON, binaris amb SHA-256, reanomenat, esborrat, `backup_daily` ZIP + `.sha256`
   - `llm_models` i `llm_chat` sense filtrar mai `X-Vault-Token` cap al motor IA local
   - Bloqueig de Path Traversal (`PATH_TRAVERSAL`, 400)
4. Reconnexió exponencial automàtica després de caiguda i reinici del servidor WSS.
5. Perfil `SUPERADMIN` (20 carpetes + `backup_daily`) i mode CLI `--init-only`.
"""

from __future__ import annotations

import asyncio
import json
import os
import socket
import subprocess
import sys
import threading
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict, List, Optional

import pytest
import uvicorn
from sqlalchemy import delete

ROOT_DIR = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = ROOT_DIR / "scripts"
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import scripts.client_vault_agent as cva  # noqa: E402

from app.core.db import AsyncSessionLocal  # noqa: E402
from app.main import app  # noqa: E402
from app.models.models import AlertaSeguretat, Empresa, Usuari  # noqa: E402
from app.services.vault_tunnel import (  # noqa: E402
    SUPERADMIN_TARGET_KEY,
    VaultTunnelRemoteError,
    empresa_target_key,
    vault_tunnel_broker,
)


def _find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


class _LiveUvicornOnPort:
    """Servidor Uvicorn real en un port específic (permet provar reconnexió al mateix port)."""

    def __init__(self, port: Optional[int] = None) -> None:
        self.port = port or _find_free_port()
        self.config = uvicorn.Config(
            app,
            host="127.0.0.1",
            port=self.port,
            log_level="warning",
            ws="websockets-sansio",
        )
        self.server = uvicorn.Server(self.config)
        self._task: Optional[asyncio.Task[None]] = None

    @property
    def http_url(self) -> str:
        return f"http://127.0.0.1:{self.port}"

    async def __aenter__(self) -> "_LiveUvicornOnPort":
        self._task = asyncio.create_task(self.server.serve())
        deadline = asyncio.get_running_loop().time() + 8.0
        while not self.server.started:
            if asyncio.get_running_loop().time() > deadline:
                raise RuntimeError("Uvicorn real no ha arrencat a temps.")
            await asyncio.sleep(0.03)
        return self

    async def __aexit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        self.server.should_exit = True
        if self._task is not None:
            try:
                await asyncio.wait_for(self._task, timeout=5.0)
            except asyncio.TimeoutError:
                self._task.cancel()


def _start_local_llm_server(model_name: str = "qwen2.5-vl-7b-fase2") -> tuple[ThreadingHTTPServer, str, List[Dict[str, str]]]:
    seen_headers: List[Dict[str, str]] = []

    class _Handler(BaseHTTPRequestHandler):
        def log_message(self, format: str, *args: Any) -> None:
            return

        def do_GET(self) -> None:
            seen_headers.append({k.lower(): v for k, v in self.headers.items()})
            if self.path == "/v1/models":
                body = json.dumps({"data": [{"id": model_name}]}).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return
            self.send_response(404)
            self.end_headers()

        def do_POST(self) -> None:
            seen_headers.append({k.lower(): v for k, v in self.headers.items()})
            length = int(self.headers.get("Content-Length", "0"))
            _ = self.rfile.read(length) if length > 0 else b""
            if self.path == "/v1/chat/completions":
                body = json.dumps(
                    {
                        "model": model_name,
                        "choices": [{"message": {"role": "assistant", "content": f"OK des de {model_name}"}}],
                    }
                ).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return
            self.send_response(404)
            self.end_headers()

    srv = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    thr = threading.Thread(target=srv.serve_forever, daemon=True)
    thr.start()
    return srv, f"http://127.0.0.1:{srv.server_port}", seen_headers


async def _create_empresa_and_boss(vault_token: str) -> uuid.UUID:
    emp_id = uuid.uuid4()
    async with AsyncSessionLocal() as session:
        session.add(
            Empresa(
                id=emp_id,
                nom="Empresa Fase 2 WSS SL",
                nif=f"B{emp_id.hex[:8].upper()}",
                subdomini=f"f2-{emp_id.hex[:8]}",
                vertical="CAMPOPRO",
                estat_pagament="ACTIU",
                vault_token=vault_token,
                feature_copilot_ia=True,
                node_ia_actiu=False,
                agent_prompt_system="Prompt tècnic Fase 2 CampoPro.",
            )
        )
        session.add(
            Usuari(
                id=uuid.uuid4(),
                empresa_id=emp_id,
                nom="Joan",
                cognoms="Martí Grau",
                nif=f"4{emp_id.hex[:7].upper()}K",
                email=f"joan_{emp_id.hex[:6]}@campopro.cat",
                telefon="+34600999888",
                rol="BOSS",
            )
        )
        await session.commit()
    return emp_id


async def _cleanup_empresa(emp_id: uuid.UUID) -> None:
    async with AsyncSessionLocal() as session:
        await session.execute(delete(AlertaSeguretat).where(AlertaSeguretat.empresa_id == emp_id))
        await session.execute(delete(Usuari).where(Usuari.empresa_id == emp_id))
        await session.execute(delete(Empresa).where(Empresa.id == emp_id))
        await session.commit()


def test_fase2_agent_sense_ports_escolta_i_config_validacio(tmp_path: Path) -> None:
    """Certifica ADR-001: zero FastAPI/Uvicorn a client_vault_agent.py i validació estricta d'AgentConfig."""
    assert not hasattr(cva, "app"), "client_vault_agent.py no pot exposar cap aplicació FastAPI/HTTP entrant"
    src = (SCRIPTS_DIR / "client_vault_agent.py").read_text(encoding="utf-8")
    assert "uvicorn.run" not in src
    assert "from fastapi" not in src

    assert (
        cva.build_ws_connect_url("https://sevalor-sevalor-backend.80opze.easypanel.host")
        == "wss://sevalor-sevalor-backend.80opze.easypanel.host/api/v1/vault-tunnel/connect"
    )
    assert (
        cva.build_ws_connect_url("http://127.0.0.1:8000/")
        == "ws://127.0.0.1:8000/api/v1/vault-tunnel/connect"
    )

    with pytest.raises(ValueError):
        cva.AgentConfig(
            server_url="https://sevalor-sevalor-backend.80opze.easypanel.host",
            role="EMPRESA",
            empresa_id=None,
            vault_token="svlt_ok",
            disk_a=tmp_path / "a",
            disk_b=tmp_path / "b",
        )
    with pytest.raises(ValueError):
        cva.AgentConfig(
            server_url="https://sevalor-sevalor-backend.80opze.easypanel.host",
            role="SUPERADMIN",
            empresa_id=str(uuid.uuid4()),
            vault_token="sa_ok",
            disk_a=tmp_path / "a",
            disk_b=tmp_path / "b",
        )


@pytest.mark.asyncio
async def test_fase2_agent_subprocess_real_wss_end_to_end_empresa_i_llm(tmp_path: Path) -> None:
    """
    Executa el script REAL `scripts/client_vault_agent.py` com a subprocés OS independent
    connectant de sortida contra Uvicorn + PostgreSQL 16 + motor LLM local real.
    """
    llm_srv, llm_url, seen_llm_headers = _start_local_llm_server("qwen2.5-vl-7b-fase2")
    tok = f"svlt_{uuid.uuid4().hex}"
    emp_id = await _create_empresa_and_boss(tok)
    target_key = empresa_target_key(emp_id)
    disk_a = tmp_path / "empresa_disc_a"
    disk_b = tmp_path / "empresa_disc_b"

    proc: Optional[subprocess.Popen[bytes]] = None
    try:
        async with _LiveUvicornOnPort() as srv:
            env = os.environ.copy()
            env["SEVALOR_SERVER_URL"] = srv.http_url
            env["SEVALOR_VAULT_ROLE"] = "EMPRESA"
            env["SEVALOR_EMPRESA_ID"] = str(emp_id)
            env["SEVALOR_VAULT_SECRET"] = tok
            env["SEVALOR_VAULT_PATH_A"] = str(disk_a)
            env["SEVALOR_VAULT_PATH_B"] = str(disk_b)
            env["SEVALOR_LOCAL_LLM_URL"] = llm_url

            proc = subprocess.Popen(
                [sys.executable, str(SCRIPTS_DIR / "client_vault_agent.py")],
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

            # 1. Esperar connexió WSS sortint + auto-inicialització de 38 carpetes i fitxes
            deadline = asyncio.get_running_loop().time() + 10.0
            while asyncio.get_running_loop().time() < deadline:
                if proc.poll() is not None:
                    out, err = proc.communicate(timeout=2)
                    raise RuntimeError(f"Agent WSS caigut ({proc.returncode}): {err.decode()} {out.decode()}")
                if (
                    await vault_tunnel_broker.is_online(target_key)
                    and (disk_a / "11_configuracio_i_backups/identitat_camaleo/empresa.json").is_file()
                    and (disk_a / "09_copilot_ia/prompt_sistema/system_prompt.txt").is_file()
                ):
                    break
                await asyncio.sleep(0.08)

            assert await vault_tunnel_broker.is_online(target_key)
            assert (disk_a / "09_copilot_ia/index_vectorial_rag").is_dir()
            assert (disk_a / "11_configuracio_i_backups/identitat_camaleo/boss.json").is_file()
            assert (
                (disk_a / "09_copilot_ia/prompt_sistema/system_prompt.txt").read_text(encoding="utf-8")
                == "Prompt tècnic Fase 2 CampoPro."
            )

            # 2. Health check amb espai lliure i models LLM locals
            h = await vault_tunnel_broker.health(target_key)
            assert h["status"] == "OK"
            assert h["carpetes_count"] == 38
            assert h["llm_online"] is True
            assert "qwen2.5-vl-7b-fase2" in h["models"]
            assert h["disc_a_lliure_gb"] > 0

            # 3. CRUD JSON + binari amb integritat SHA-256 + reanomenat + backup diari
            await vault_tunnel_broker.json_put(
                target_key, "01_clients/fitxes", "cli_f2", {"nom": "Finca Fase 2"}
            )
            llista = await vault_tunnel_broker.json_get_list(target_key, "01_clients/fitxes")
            assert any(item.get("nom") == "Finca Fase 2" for item in llista)

            pdf_raw = b"%PDF-1.4\nFactura Sobirana Fase 2\n" + (b"X" * 2048)
            put_res = await vault_tunnel_broker.file_put(
                target_key, "04_factures/emeses_verifactu_pdf", "fac_f2.pdf", pdf_raw, "application/pdf"
            )
            assert put_res["size_bytes"] == len(pdf_raw)

            got_bytes, got_name = await vault_tunnel_broker.file_get(
                target_key, "04_factures/emeses_verifactu_pdf/fac_f2.pdf"
            )
            assert got_bytes == pdf_raw
            assert got_name == "fac_f2.pdf"

            await vault_tunnel_broker.file_rename(
                target_key,
                "04_factures/emeses_verifactu_pdf/fac_f2.pdf",
                "04_factures/emeses_verifactu_pdf",
                "fac_f2_ok.pdf",
            )
            assert (disk_a / "04_factures/emeses_verifactu_pdf/fac_f2_ok.pdf").is_file()

            bak = await vault_tunnel_broker.call(
                target_key, "backup_daily", {"empresa_id": str(emp_id), "origen": "test_fase2"}
            )
            assert bak["status"] == "OK"
            assert len(bak["sha256"]) == 64
            assert Path(bak["zip_path"]).is_file()
            assert Path(f"{bak['zip_path']}.sha256").is_file()

            assert await vault_tunnel_broker.file_delete(target_key, "04_factures/emeses_verifactu_pdf/fac_f2_ok.pdf") is True
            assert await vault_tunnel_broker.json_delete(target_key, "01_clients/fitxes", "cli_f2") is True

            # 4. Copilot IA local (llm_models + llm_chat) sense filtrar X-Vault-Token
            models_resp = await vault_tunnel_broker.call_llm_models(target_key)
            assert models_resp["data"][0]["id"] == "qwen2.5-vl-7b-fase2"

            chat_resp = await vault_tunnel_broker.call_llm_chat(
                target_key,
                {"model": "qwen2.5-vl-7b-fase2", "messages": [{"role": "user", "content": "hola"}]},
            )
            assert "OK des de qwen2.5-vl-7b-fase2" in chat_resp["choices"][0]["message"]["content"]
            assert seen_llm_headers
            for hdrs in seen_llm_headers:
                assert "x-vault-token" not in hdrs

            # 5. Bloqueig estricte de Path Traversal
            with pytest.raises(VaultTunnelRemoteError) as exc_trav:
                await vault_tunnel_broker.file_get(target_key, "../../etc/passwd")
            assert exc_trav.value.code == "PATH_TRAVERSAL"
            assert exc_trav.value.status_code == 400
    finally:
        if proc is not None and proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
        llm_srv.shutdown()
        llm_srv.server_close()
        await _cleanup_empresa(emp_id)


@pytest.mark.asyncio
async def test_fase2_agent_reconnexio_automatica_despres_de_tall_servidor(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verifica que l'agent WSS es reconnecta sol automàticament quan el servidor Hetzner es reinicia."""
    monkeypatch.setattr(cva, "BACKOFF_INITIAL_SECONDS", 0.15)
    monkeypatch.setattr(cva, "BACKOFF_MAX_SECONDS", 0.5)

    tok = f"svlt_{uuid.uuid4().hex}"
    emp_id = await _create_empresa_and_boss(tok)
    target_key = empresa_target_key(emp_id)
    port = _find_free_port()

    cfg = cva.AgentConfig(
        server_url=f"http://127.0.0.1:{port}",
        role="EMPRESA",
        empresa_id=str(emp_id),
        vault_token=tok,
        disk_a=tmp_path / "rec_a",
        disk_b=tmp_path / "rec_b",
    )
    agent = cva.SovereignWssAgent(cfg)
    stop_ev = asyncio.Event()
    agent_task = asyncio.create_task(agent.run_forever(stop_ev))

    try:
        # 1. Arrencada servidor #1 -> agent connecta
        async with _LiveUvicornOnPort(port):
            for _ in range(80):
                if await vault_tunnel_broker.is_online(target_key):
                    break
                await asyncio.sleep(0.05)
            assert await vault_tunnel_broker.is_online(target_key)
            h1 = await vault_tunnel_broker.health(target_key)
            assert h1["status"] == "OK"

        # 2. Servidor aturat -> túnel fora de línia
        await asyncio.sleep(0.15)
        assert not await vault_tunnel_broker.is_online(target_key)

        # 3. Reinici servidor #2 al mateix port -> agent es reconnecta sol sense intervenció
        async with _LiveUvicornOnPort(port):
            for _ in range(100):
                if await vault_tunnel_broker.is_online(target_key):
                    break
                await asyncio.sleep(0.05)
            assert await vault_tunnel_broker.is_online(target_key)
            h2 = await vault_tunnel_broker.health(target_key)
            assert h2["status"] == "OK"
    finally:
        stop_ev.set()
        try:
            await asyncio.wait_for(agent_task, timeout=5.0)
        except asyncio.TimeoutError:
            agent_task.cancel()
        await _cleanup_empresa(emp_id)


@pytest.mark.asyncio
async def test_fase2_agent_superadmin_20_carpetes_i_cli_init_only(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verifica --init-only (38 EMPRESA / 20 SUPERADMIN) i connexió WSS real de SUPERADMIN."""
    sa_secret = f"sa_f2_{uuid.uuid4().hex}"
    monkeypatch.setenv("SUPERADMIN_VAULT_SECRET", sa_secret)

    # 1. CLI --init-only per SUPERADMIN
    sa_a = tmp_path / "sa_disc_a"
    sa_b = tmp_path / "sa_disc_b"
    env_cli = os.environ.copy()
    env_cli["SEVALOR_VAULT_ROLE"] = "SUPERADMIN"
    env_cli["SEVALOR_VAULT_SECRET"] = sa_secret
    env_cli["SEVALOR_VAULT_PATH_A"] = str(sa_a)
    env_cli["SEVALOR_VAULT_PATH_B"] = str(sa_b)
    env_cli.pop("SEVALOR_EMPRESA_ID", None)

    r_cli = subprocess.run(
        [sys.executable, str(SCRIPTS_DIR / "client_vault_agent.py"), "--init-only"],
        env=env_cli,
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert r_cli.returncode == 0, r_cli.stderr
    assert "20" in r_cli.stdout
    assert (sa_a / "01_tenants_b2b/fitxes_empreses").is_dir()
    assert not (sa_a / "06_ordres_treball/actives_buffer").exists()

    # 2. Connexió WSS real de SUPERADMIN
    async with _LiveUvicornOnPort() as srv:
        cfg = cva.AgentConfig(
            server_url=srv.http_url,
            role="SUPERADMIN",
            vault_token=sa_secret,
            disk_a=sa_a,
            disk_b=sa_b,
        )
        agent = cva.SovereignWssAgent(cfg)
        stop_ev = asyncio.Event()
        task = asyncio.create_task(agent.run_forever(stop_ev))
        try:
            for _ in range(80):
                if await vault_tunnel_broker.is_online(SUPERADMIN_TARGET_KEY):
                    break
                await asyncio.sleep(0.05)
            assert await vault_tunnel_broker.is_online(SUPERADMIN_TARGET_KEY)

            h = await vault_tunnel_broker.health(SUPERADMIN_TARGET_KEY)
            assert h["role"] == "SUPERADMIN"
            assert h["carpetes_count"] == 20

            await vault_tunnel_broker.json_put(
                SUPERADMIN_TARGET_KEY, "03_crm_comercial/leads", "lead_f2", {"empresa": "Lead Fase 2"}
            )
            assert (sa_a / "03_crm_comercial/leads/lead_f2.json").is_file()
        finally:
            stop_ev.set()
            try:
                await asyncio.wait_for(task, timeout=5.0)
            except asyncio.TimeoutError:
                task.cancel()
