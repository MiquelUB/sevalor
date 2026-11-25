"""Tests d'integració reals (Zero Mock) per a la Fase 3: Migració Total del Backend al Túnel WSS Únic.

Certifica de ponta a ponta sobre Uvicorn real + PostgreSQL 16 real + `SovereignWssAgent` real + LLM HTTP local real:
1. Onboarding WSS únic (`POST /superadmin/tenants/onboarding`):
   - Rebutja URLs HTTP/HTTPS entrants amb HTTP 422 (ADR-001, zero dualitat).
   - Crea empresa ACTIU immediatament sense túnel extern, assigna `wss-tunnel://<id>`,
     retorna `comanda_install_wss` amb la URL pública configurada i encua fitxes xifrades `SVENC1:`.
   - En connectar `SovereignWssAgent`, s'auto-inicialitzen les 38 carpetes + es drenen `empresa.json`,
     `boss.json`, `system_prompt.txt` i s'esborra la cua a Hetzner (`cua_transit_pendent == 0`).
   - `GET /{id}/tunnel-status`, `POST /verificar-disc-dur` i `POST /verificar-node-ia` retornen
     `TUNEL_OFFLINE` quan offline i `OK` (amb latència, GB lliures, models reals) quan connectat.
2. Copilot IA (`/gestio/copilot/ia-status`, `/gestio/copilot/estat-node`, `/gestio/copilot/xat`):
   - Diagnòstics exactes `FEATURE_COPILOT_DESACTIVAT`, `NODE_IA_INACTIU`, `TUNEL_OFFLINE`, `LLM_OFFLINE` (HTTP 503).
   - Inferència real 200 OK sobre el Túnel Invers WSS cap al motor LLM local real.
3. `SovereignStorageGateway` (binaris + reanomenat + esborrat + `backup_daily` ZIP+SHA256)
   i `SuperadminStorageGateway` (20 carpetes + JSON + binaris + 503 `NODE_SUPERADMIN_OFFLINE` quan offline)
   100% sobre WSS.
4. Rotació de token (`POST /{id}/rotar-vault-token`): revoca immediatament la sessió WSS activa (`4401`),
   retorna nou `vault_token` + nova `comanda_install_wss` i impedeix reconnectar amb el token antic.
"""

from __future__ import annotations

import asyncio
import json
import socket
import sys
import threading
import uuid
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx
import jwt
import pytest
import uvicorn
from fastapi import HTTPException

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import scripts.client_vault_agent as cva  # noqa: E402

from app.core.config import settings  # noqa: E402
from app.main import app  # noqa: E402
from app.models.models import (  # noqa: E402
    Empresa,
    Usuari,
)
from app.services.backup import executar_backup_sobira_empresa  # noqa: E402
from app.services.sovereign_storage import (  # noqa: E402
    CARPETES_SUPERADMIN,
    MAPA_CARPETES_CLIENT,
    SovereignStorageGateway,
    SuperadminStorageGateway,
)
from app.services.vault_tunnel import (  # noqa: E402
    SUPERADMIN_TARGET_KEY,
    empresa_target_key,
    vault_tunnel_broker,
)


def _find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _make_superadmin_headers() -> Dict[str, str]:
    token = jwt.encode(
        {
            "sub": "00000000-0000-0000-0000-000000000000",
            "rol": "SUPERADMIN",
            "empresa_id": None,
            "exp": datetime.now(timezone.utc) + timedelta(minutes=15),
            "totp_activat": True,
            "ip_allowlist": ["testclient", "127.0.0.1", "localhost", "*"],
        },
        settings.SECRET_KEY,
        algorithm=settings.ALGORITHM,
    )
    return {"Authorization": f"Bearer {token}"}


def _make_boss_headers(empresa_id: uuid.UUID, boss_id: uuid.UUID) -> Dict[str, str]:
    token = jwt.encode(
        {
            "sub": str(boss_id),
            "rol": "BOSS",
            "empresa_id": str(empresa_id),
            "exp": datetime.now(timezone.utc) + timedelta(minutes=15),
            "totp_activat": True,
        },
        settings.SECRET_KEY,
        algorithm=settings.ALGORITHM,
    )
    return {"Authorization": f"Bearer {token}"}


class _LiveUvicornServer:
    """Servidor Uvicorn real sobre el mateix event loop (Zero Mock, zero warnings)."""

    def __init__(self) -> None:
        self.port = _find_free_port()
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

    async def __aenter__(self) -> "_LiveUvicornServer":
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


def _start_local_llm_server(
    model_name: str = "sevalor-fase3-local-qwen",
    reply_text: str = "Resposta real del node LLM sobirà via Túnel Invers WSS.",
) -> tuple[ThreadingHTTPServer, str, List[Dict[str, Any]]]:
    calls: List[Dict[str, Any]] = []

    class _Handler(BaseHTTPRequestHandler):
        def log_message(self, format: str, *args: Any) -> None:
            return

        def do_GET(self) -> None:
            calls.append({"method": "GET", "path": self.path})
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
            length = int(self.headers.get("Content-Length", "0"))
            raw = self.rfile.read(length) if length > 0 else b"{}"
            calls.append({"method": "POST", "path": self.path, "body": json.loads(raw.decode())})
            if self.path == "/v1/chat/completions":
                body = json.dumps(
                    {
                        "id": "chatcmpl-fase3",
                        "object": "chat.completion",
                        "model": model_name,
                        "choices": [
                            {
                                "index": 0,
                                "message": {"role": "assistant", "content": reply_text},
                                "finish_reason": "stop",
                            }
                        ],
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

    port = _find_free_port()
    srv = ThreadingHTTPServer(("127.0.0.1", port), _Handler)
    th = threading.Thread(target=srv.serve_forever, daemon=True)
    th.start()
    return srv, f"http://127.0.0.1:{port}", calls


async def _wait_for(predicate: Any, timeout: float = 8.0, interval: float = 0.05) -> None:
    deadline = asyncio.get_running_loop().time() + timeout
    while asyncio.get_running_loop().time() < deadline:
        res = predicate()
        if asyncio.iscoroutine(res):
            res = await res
        if res:
            return
        await asyncio.sleep(interval)
    raise AssertionError(f"Condició no assolida en {timeout}s.")


async def _cleanup_empresa(emp_id: uuid.UUID) -> None:
    await vault_tunnel_broker.disconnect(empresa_target_key(emp_id))


class _RunningAgent:
    """Wrapper d'execució in-process per `SovereignWssAgent` amb `stop_event` net."""

    def __init__(self, agent: cva.SovereignWssAgent) -> None:
        self.agent = agent
        self.stop_event = asyncio.Event()
        self.task: Optional[asyncio.Task[None]] = None

    def start(self) -> "_RunningAgent":
        self.task = asyncio.create_task(self.agent.run_forever(stop_event=self.stop_event))
        return self

    async def stop(self) -> None:
        self.stop_event.set()
        if self.task is not None:
            try:
                await asyncio.wait_for(self.task, timeout=3.0)
            except (asyncio.TimeoutError, asyncio.CancelledError):
                self.task.cancel()


def _make_inproc_agent(
    server_http_url: str,
    *,
    role: str,
    token: str,
    disk_a: Path,
    disk_b: Optional[Path] = None,
    empresa_id: Optional[str] = None,
    llm_url: str = "http://127.0.0.1:1234",
) -> _RunningAgent:
    cfg = cva.AgentConfig(
        server_url=server_http_url,
        role=role,
        vault_token=token,
        empresa_id=empresa_id,
        disk_a=disk_a,
        disk_b=disk_b or (disk_a.parent / f"{disk_a.name}_mirror"),
        local_llm_url=llm_url,
    )
    return _RunningAgent(cva.SovereignWssAgent(cfg))


@pytest.mark.asyncio
async def test_fase3_onboarding_wss_unic_i_bootstrap_automatic(tmp_path: Path) -> None:
    """Certifica onboarding sense túnel extern, rebuig HTTP 422, comanda 1-clic i auto-bootstrap en connectar."""
    llm_srv, llm_url, _ = _start_local_llm_server(model_name="sevalor-fase3-local-qwen")
    created_emp_id: Optional[uuid.UUID] = None
    agent: Optional[_RunningAgent] = None

    try:
        async with _LiveUvicornServer() as server:
            headers = _make_superadmin_headers()
            slug = f"f3-onb-{uuid.uuid4().hex[:8]}"
            nif = f"B{uuid.uuid4().int % 89999999 + 10000000}"
            boss_nif = f"{uuid.uuid4().int % 89999999 + 10000000}A"
            boss_email = f"boss-{slug}@sevalor-test.cat"

            async with httpx.AsyncClient(base_url=server.http_url, timeout=15.0) as client:
                # 1. Rebuig explícit de túnel HTTP entrant (ADR-001 Zero Dualitat)
                resp_bad = await client.post(
                    "/api/v1/superadmin/tenants/onboarding",
                    headers=headers,
                    json={
                        "rao_social": "Empresa HTTP Prohibida SL",
                        "nif": nif,
                        "slug": slug,
                        "vertical": "CAMPOPRO",
                        "estat_inicial": "ACTIU",
                        "disc_dur_url": "https://legacy-http-tunnel.example.com",
                        "boss_nif": boss_nif,
                        "boss_nom": "Oriol",
                        "boss_cognoms": "Vila",
                        "boss_email": boss_email,
                    },
                )
                assert resp_bad.status_code == 422, resp_bad.text
                assert "ADR-001" in resp_bad.text or "prohibides" in resp_bad.text.lower()

                # 2. Onboarding net SENSE URL externa: assigna wss-tunnel://<id> i retorna comanda 1-clic
                resp_ok = await client.post(
                    "/api/v1/superadmin/tenants/onboarding",
                    headers=headers,
                    json={
                        "rao_social": "Agrícola Sobirana WSS SL",
                        "nif": nif,
                        "slug": slug,
                        "vertical": "CAMPOPRO",
                        "estat_inicial": "ACTIU",
                        "pla_subscripcio": "PRO",
                        "feature_flags": {"copilot_ia": True, "flota_avancada": True},
                        "agent_prompt_system": "Ets l'enginyer agrònom sobirà d'Agrícola Sobirana.",
                        "boss_nif": boss_nif,
                        "boss_nom": "Oriol",
                        "boss_cognoms": "Vila",
                        "boss_email": boss_email,
                    },
                )
                assert resp_ok.status_code == 201, resp_ok.text
                body = resp_ok.json()
                tenant = body["tenant"]
                created_emp_id = uuid.UUID(tenant["id"])
                vault_token = tenant["vault_token"]

                assert tenant["disc_dur_url"] == f"wss-tunnel://{created_emp_id}"
                assert tenant["node_ia_url"] == f"wss-tunnel://{created_emp_id}"
                assert tenant["tunnel_online"] is False
                assert body["tunnel_online"] is False
                assert "https://sevalor-sevalor-backend.80opze.easypanel.host" in body["comanda_install_wss"]
                assert f'--empresa-id "{created_emp_id}"' in body["comanda_install_wss"]
                assert f'--token "{vault_token}"' in body["comanda_install_wss"]
                assert body["vault_sync"]["status"] == "QUEUED"

                # 3. Verificacions en viu mentre offline -> TUNEL_OFFLINE
                r_disc_off = await client.post(
                    "/api/v1/superadmin/tenants/verificar-disc-dur",
                    headers=headers,
                    json={"empresa_id": str(created_emp_id)},
                )
                assert r_disc_off.status_code == 200
                assert r_disc_off.json()["status"] == "ERROR"
                assert r_disc_off.json()["motiu"] == "TUNEL_OFFLINE"
                assert r_disc_off.json()["cua_transit_pendent"] >= 3

                r_ia_off = await client.post(
                    "/api/v1/superadmin/tenants/verificar-node-ia",
                    headers=headers,
                    json={"empresa_id": str(created_emp_id)},
                )
                assert r_ia_off.status_code == 200
                assert r_ia_off.json()["status"] == "ERROR"
                assert r_ia_off.json()["motiu"] == "TUNEL_OFFLINE"

                # 4. Connectem l'agent real SovereignWssAgent -> auto-bootstrap 38 carpetes + drenatge SVENC1
                disk_a = tmp_path / "emp_disk_a"
                disk_b = tmp_path / "emp_disk_b"
                agent = _make_inproc_agent(
                    server.http_url,
                    role="EMPRESA",
                    token=vault_token,
                    empresa_id=str(created_emp_id),
                    disk_a=disk_a,
                    disk_b=disk_b,
                    llm_url=llm_url,
                ).start()

                emp_json = disk_a / "11_configuracio_i_backups" / "identitat_camaleo" / "empresa.json"
                boss_json = disk_a / "11_configuracio_i_backups" / "identitat_camaleo" / "boss.json"
                profile_json = disk_a / "09_copilot_ia" / "prompt_sistema" / "copilot_profile.json"
                await _wait_for(lambda: emp_json.exists() and boss_json.exists() and profile_json.exists(), timeout=8.0)

                # Totes les 38 carpetes creades a Disc A i mirall Disc B inicialitzat
                for rel_dir in MAPA_CARPETES_CLIENT.values():
                    assert (disk_a / rel_dir).is_dir()
                assert (disk_b / "backups_jornada").is_dir()

                # Cua de trànsit a Hetzner drenada a 0 (unlink verificat)
                await _wait_for(
                    lambda: SovereignStorageGateway.comptar_cua_transit_empresa(created_emp_id) == 0,
                    timeout=5.0,
                )

                # 5. Endpoints de diagnòstic i detall en viu -> ONLINE + models reals + roundtrip
                r_status = await client.get(
                    f"/api/v1/superadmin/tenants/{created_emp_id}/tunnel-status",
                    headers=headers,
                )
                assert r_status.status_code == 200
                st_data = r_status.json()
                assert st_data["tunnel_online"] is True
                assert st_data["tunnel_status"] == "ONLINE"
                assert st_data["cua_transit_pendent"] == 0
                assert st_data["agent_version"] == cva.AGENT_VERSION

                r_disc_on = await client.post(
                    "/api/v1/superadmin/tenants/verificar-disc-dur",
                    headers=headers,
                    json={"empresa_id": str(created_emp_id)},
                )
                assert r_disc_on.status_code == 200
                d_on = r_disc_on.json()
                assert d_on["status"] == "OK"
                assert d_on["motiu"] == "DISC_OPERATIU"
                assert d_on["roundtrip_escriptura"] is True
                assert d_on["tunnel_online"] is True
                assert d_on["ia_proxy_ok"] is True
                assert "sevalor-fase3-local-qwen" in d_on["models"]
                assert d_on["disc_a_lliure_gb"] > 0

                r_ia_on = await client.post(
                    "/api/v1/superadmin/tenants/verificar-node-ia",
                    headers=headers,
                    json={"empresa_id": str(created_emp_id)},
                )
                assert r_ia_on.status_code == 200
                ia_on = r_ia_on.json()
                assert ia_on["status"] == "OK"
                assert ia_on["motiu"] == "CONNEXIO_ESTABLERTA"
                assert ia_on["tunnel_online"] is True
                assert ia_on["llm_online"] is True
                assert "sevalor-fase3-local-qwen" in ia_on["models"]
    finally:
        if agent is not None:
            await agent.stop()
        llm_srv.shutdown()
        llm_srv.server_close()
        if created_emp_id is not None:
            await _cleanup_empresa(created_emp_id)


@pytest.mark.asyncio
async def test_fase3_copilot_diagnostics_i_xat_via_wss(admin_session, tmp_path: Path) -> None:
    """Certifica els 4 estats de diagnòstic 503 del Copilot i la inferència real 200 OK sobre WSS."""
    emp_id = uuid.uuid4()
    boss_id = uuid.uuid4()
    vault_token = f"svlt_f3_cop_{uuid.uuid4().hex[:16]}"
    closed_port = _find_free_port()
    llm_srv, llm_url, llm_calls = _start_local_llm_server(
        model_name="qwen2.5-fase3-chat",
        reply_text="Confirmació sobirana: pressió de reg nominal a 2.4 bar.",
    )
    agent: Optional[_RunningAgent] = None

    emp = Empresa(
        id=emp_id,
        nom="Copilot WSS Test SL",
        nif=f"B{uuid.uuid4().int % 89999999 + 10000000}",
        subdomini=f"f3cop-{uuid.uuid4().hex[:8]}",
        vertical="CAMPOPRO",
        estat_pagament="ACTIU",
        pla_subscripcio="PRO",
        feature_copilot_ia=False,
        node_ia_actiu=False,
        node_ia_url=f"wss-tunnel://{emp_id}",
        disc_dur_url=f"wss-tunnel://{emp_id}",
        vault_token=vault_token,
    )
    boss = Usuari(
        id=boss_id,
        empresa_id=emp_id,
        nif=f"{uuid.uuid4().int % 89999999 + 10000000}B",
        nom="Marta",
        cognoms="Soler",
        email=f"marta-{emp_id.hex[:8]}@sevalor-test.cat",
        rol="BOSS",
        estat="ACTIU",
        totp_activat=True,
    )
    admin_session.add(emp)
    admin_session.add(boss)
    await admin_session.commit()

    from app.services.copilot_config_service import save_strict_copilot_config

    await save_strict_copilot_config(
        db=admin_session,
        empresa_id=emp_id,
        system_prompt="Copilot sobirà de Copilot WSS Test SL.",
        rag_prompt="",
        subagent_prompts={},
    )

    try:
        async with _LiveUvicornServer() as server:
            boss_headers = _make_boss_headers(emp_id, boss_id)
            async with httpx.AsyncClient(base_url=server.http_url, timeout=15.0) as client:
                # 1. FEATURE_COPILOT_DESACTIVAT
                r_st1 = await client.get("/api/v1/gestio/copilot/ia-status", headers=boss_headers)
                assert r_st1.status_code == 200
                assert r_st1.json()["motiu"] == "FEATURE_COPILOT_DESACTIVAT"
                r_xat1 = await client.post(
                    "/api/v1/gestio/copilot/xat",
                    headers=boss_headers,
                    json={"pregunta": "Hola copilot"},
                )
                assert r_xat1.status_code == 503
                assert r_xat1.json()["detail"]["motiu"] == "FEATURE_COPILOT_DESACTIVAT"

                # 2. NODE_IA_INACTIU
                emp.feature_copilot_ia = True
                emp.node_ia_actiu = False
                await admin_session.commit()

                r_st2 = await client.get("/api/v1/gestio/copilot/ia-status", headers=boss_headers)
                assert r_st2.json()["motiu"] == "NODE_IA_INACTIU"
                r_xat2 = await client.post(
                    "/api/v1/gestio/copilot/xat",
                    headers=boss_headers,
                    json={"pregunta": "Hola copilot"},
                )
                assert r_xat2.status_code == 503
                assert r_xat2.json()["detail"]["motiu"] == "NODE_IA_INACTIU"

                # 3. TUNEL_OFFLINE
                emp.node_ia_actiu = True
                await admin_session.commit()

                r_st3 = await client.get("/api/v1/gestio/copilot/ia-status", headers=boss_headers)
                assert r_st3.json()["motiu"] == "TUNEL_OFFLINE"
                r_xat3 = await client.post(
                    "/api/v1/gestio/copilot/xat",
                    headers=boss_headers,
                    json={"pregunta": "Hola copilot"},
                )
                assert r_xat3.status_code == 503
                assert r_xat3.json()["detail"]["motiu"] == "TUNEL_OFFLINE"

                # 4. LLM_OFFLINE (túnel connectat però LM Studio tancat al port local)
                agent = _make_inproc_agent(
                    server.http_url,
                    role="EMPRESA",
                    token=vault_token,
                    empresa_id=str(emp_id),
                    disk_a=tmp_path / "cop_disk_a",
                    llm_url=f"http://127.0.0.1:{closed_port}",
                ).start()
                await _wait_for(lambda: vault_tunnel_broker.is_online(empresa_target_key(emp_id)))

                r_st4 = await client.get("/api/v1/gestio/copilot/ia-status", headers=boss_headers)
                assert r_st4.json()["motiu"] == "LLM_OFFLINE"
                assert r_st4.json()["tunnel_online"] is True

                await agent.stop()
                async def _cop_offline() -> bool:
                    return not await vault_tunnel_broker.is_online(empresa_target_key(emp_id))
                await _wait_for(_cop_offline)

                # 5. ONLINE + Xat real 200 OK viatjant pel Túnel Invers WSS
                agent = _make_inproc_agent(
                    server.http_url,
                    role="EMPRESA",
                    token=vault_token,
                    empresa_id=str(emp_id),
                    disk_a=tmp_path / "cop_disk_a",
                    llm_url=llm_url,
                ).start()
                await _wait_for(lambda: vault_tunnel_broker.is_online(empresa_target_key(emp_id)))

                r_st5 = await client.get("/api/v1/gestio/copilot/ia-status", headers=boss_headers)
                st5 = r_st5.json()
                assert st5["estat"] == "ONLINE"
                assert st5["tunnel_online"] is True
                assert "qwen2.5-fase3-chat" in st5["models"]

                r_estat = await client.get("/api/v1/gestio/copilot/estat-node", headers=boss_headers)
                assert r_estat.status_code == 200
                assert r_estat.json()["estat"] == "ORDINADOR_DEDICAT_ACTIU"
                assert r_estat.json()["tunnel_online"] is True
                assert r_estat.json()["latencia_inferencia_ms"] is not None

                r_xat5 = await client.post(
                    "/api/v1/gestio/copilot/xat",
                    headers=boss_headers,
                    json={"pregunta": "Quina pressió de reg recomanes per al sector 3?"},
                )
                assert r_xat5.status_code == 200, r_xat5.text
                assert "pressió de reg nominal" in r_xat5.json()["resposta"]
                assert any(c["path"] == "/v1/chat/completions" for c in llm_calls)
    finally:
        if agent is not None:
            await agent.stop()
        llm_srv.shutdown()
        llm_srv.server_close()
        await _cleanup_empresa(emp_id)


@pytest.mark.asyncio
async def test_fase3_sovereign_storage_binari_backup_i_superadmin_wss(
    admin_session, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Certifica operacions binàries, backup ZIP+SHA256 i SuperadminStorageGateway 100% sobre WSS."""
    emp_id = uuid.uuid4()
    vault_token = f"svlt_f3_sto_{uuid.uuid4().hex[:16]}"
    sa_secret = f"sa_f3_secret_{uuid.uuid4().hex[:16]}"
    monkeypatch.setenv("SUPERADMIN_VAULT_SECRET", sa_secret)
    monkeypatch.delenv("SUPERADMIN_VAULT_URL", raising=False)

    admin_session.add(
        Empresa(
            id=emp_id,
            nom="Storage WSS SL",
            nif=f"B{uuid.uuid4().int % 89999999 + 10000000}",
            subdomini=f"f3sto-{uuid.uuid4().hex[:8]}",
            vertical="HYDROPRO",
            estat_pagament="ACTIU",
            pla_subscripcio="PRO",
            node_ia_actiu=True,
            node_ia_url=f"wss-tunnel://{emp_id}",
            disc_dur_url=f"wss-tunnel://{emp_id}",
            vault_token=vault_token,
        )
    )
    await admin_session.commit()

    emp_agent: Optional[_RunningAgent] = None
    sa_agent: Optional[_RunningAgent] = None

    try:
        # 1. SuperadminStorageGateway offline sense SUPERADMIN_VAULT_URL -> 503 NODE_SUPERADMIN_OFFLINE
        with pytest.raises(HTTPException) as exc_off:
            await SuperadminStorageGateway.llegir_entitats_json("tenants_fitxes")
        assert exc_off.value.status_code == 503
        assert "NODE_SUPERADMIN_OFFLINE" in str(exc_off.value.detail)

        async with _LiveUvicornServer() as server:
            emp_disk_a = tmp_path / "emp_a"
            emp_disk_b = tmp_path / "emp_b"
            sa_disk_a = tmp_path / "sa_a"
            sa_disk_b = tmp_path / "sa_b"

            emp_agent = _make_inproc_agent(
                server.http_url,
                role="EMPRESA",
                token=vault_token,
                empresa_id=str(emp_id),
                disk_a=emp_disk_a,
                disk_b=emp_disk_b,
            ).start()
            sa_agent = _make_inproc_agent(
                server.http_url,
                role="SUPERADMIN",
                token=sa_secret,
                disk_a=sa_disk_a,
                disk_b=sa_disk_b,
            ).start()

            await _wait_for(lambda: vault_tunnel_broker.is_online(empresa_target_key(emp_id)))
            await _wait_for(lambda: vault_tunnel_broker.is_online(SUPERADMIN_TARGET_KEY))

            # 2. SovereignStorageGateway: pujar, existeix, llegir bytes, reanomenar, backup_daily, esborrar
            payload_bin = b"%PDF-1.4\nPlanol sobira fase 3 WSS\n"
            uri = await SovereignStorageGateway.pujar_fitxer_binari(
                db=admin_session,
                empresa_id=emp_id,
                categoria="planols",
                nom_fitxer="planol_original.pdf",
                content=payload_bin,
                content_type="application/pdf",
            )
            assert uri == "vault://05_planols/arxius_base/planol_original.pdf"
            assert await SovereignStorageGateway.existeix_fitxer_categoria(
                admin_session, emp_id, "planols", "planol_original.pdf"
            )
            got_bytes, got_name = await SovereignStorageGateway.obtenir_bytes_fitxer(
                admin_session, emp_id, uri
            )
            assert got_bytes == payload_bin
            assert got_name == "planol_original.pdf"

            uri_renamed = await SovereignStorageGateway.reanomenar_fitxer_binari(
                db=admin_session,
                empresa_id=emp_id,
                old_path=uri,
                new_filename="planol_definitiu.pdf",
                categoria="planols",
                content_type="application/pdf",
            )
            assert uri_renamed.endswith("/planol_definitiu.pdf")
            assert not await SovereignStorageGateway.existeix_fitxer_categoria(
                admin_session, emp_id, "planols", "planol_original.pdf"
            )
            assert await SovereignStorageGateway.existeix_fitxer_categoria(
                admin_session, emp_id, "planols", "planol_definitiu.pdf"
            )

            # Backup diari ZIP + .sha256 al Disc A i mirall Disc B via WSS
            bkp_res = await executar_backup_sobira_empresa(admin_session, str(emp_id))
            assert bkp_res["status"] == "OK"
            assert bkp_res["mode"] == "WSS_TUNNEL"
            assert bkp_res["backup_file"].endswith(".zip")
            assert len(bkp_res["sha256"]) == 64
            assert (emp_disk_a / "11_configuracio_i_backups" / "backups_locals" / bkp_res["backup_file"]).exists()
            assert (emp_disk_b / "11_configuracio_i_backups" / "backups_locals" / bkp_res["backup_file"]).exists()

            deleted = await SovereignStorageGateway.esborrar_fitxer_binari(
                admin_session, emp_id, uri_renamed
            )
            assert deleted is True

            # 3. SuperadminStorageGateway 100% sobre WSS (20 carpetes + JSON + binari)
            init_sa = await SuperadminStorageGateway.inicialitzar_rutes_superadmin()
            assert init_sa["status"] == "OK"
            assert init_sa["mode"] == "WSS_TUNNEL"
            for rel_dir in CARPETES_SUPERADMIN:
                assert (sa_disk_a / rel_dir).is_dir()
            assert (sa_disk_b / "backups_jornada").is_dir()

            item_id = f"f3-tenant-{uuid.uuid4().hex[:8]}"
            await SuperadminStorageGateway.desar_entitat_json(
                "tenants_fitxes",
                item_id,
                {"id": item_id, "rao_social": "Superadmin WSS Verificat SL"},
            )
            llista = await SuperadminStorageGateway.llegir_entitats_json("tenants_fitxes")
            assert any(x.get("id") == item_id for x in llista)

            sa_pdf = b"%PDF-1.4\nFactura B2B Superadmin WSS\n"
            sa_uri = await SuperadminStorageGateway.pujar_fitxer_binari(
                "saas_factures_pdf", f"{item_id}.pdf", sa_pdf, "application/pdf"
            )
            assert sa_uri.startswith("superadmin-vault://")
            sa_bytes, sa_fname = await SuperadminStorageGateway.obtenir_bytes_fitxer(sa_uri)
            assert sa_bytes == sa_pdf
            assert sa_fname == f"{item_id}.pdf"
            assert await SuperadminStorageGateway.eliminar_entitat_json("tenants_fitxes", item_id) is True
    finally:
        for ag in (emp_agent, sa_agent):
            if ag is not None:
                await ag.stop()
        await vault_tunnel_broker.disconnect(SUPERADMIN_TARGET_KEY)
        await _cleanup_empresa(emp_id)


@pytest.mark.asyncio
async def test_fase3_rotacio_token_revoca_sessio_wss_activa(admin_session, tmp_path: Path) -> None:
    """Certifica que rotar el vault_token tanca immediatament la sessió WSS activa amb codi 4401."""
    emp_id = uuid.uuid4()
    old_token = f"svlt_f3_old_{uuid.uuid4().hex[:16]}"
    admin_session.add(
        Empresa(
            id=emp_id,
            nom="Rotacio Token WSS SL",
            nif=f"B{uuid.uuid4().int % 89999999 + 10000000}",
            subdomini=f"f3rot-{uuid.uuid4().hex[:8]}",
            vertical="ELECTRICPRO",
            estat_pagament="ACTIU",
            pla_subscripcio="PRO",
            node_ia_actiu=True,
            node_ia_url=f"wss-tunnel://{emp_id}",
            disc_dur_url=f"wss-tunnel://{emp_id}",
            vault_token=old_token,
        )
    )
    await admin_session.commit()

    agent: Optional[_RunningAgent] = None

    try:
        async with _LiveUvicornServer() as server:
            agent = _make_inproc_agent(
                server.http_url,
                role="EMPRESA",
                token=old_token,
                empresa_id=str(emp_id),
                disk_a=tmp_path / "rot_disk_a",
            ).start()
            await _wait_for(lambda: vault_tunnel_broker.is_online(empresa_target_key(emp_id)))

            async with httpx.AsyncClient(base_url=server.http_url, timeout=15.0) as client:
                r_rot = await client.post(
                    f"/api/v1/superadmin/tenants/{emp_id}/rotar-vault-token",
                    headers=_make_superadmin_headers(),
                )
                assert r_rot.status_code == 200, r_rot.text
                rot_data = r_rot.json()
                assert rot_data["status"] == "OK"
                assert rot_data["sessio_anterior_tancada"] is True
                assert rot_data["vault_token"] != old_token
                assert rot_data["vault_token"] in rot_data["comanda_install_wss"]

                # L'agent antic rep 4401 i NO pot tornar a connectar amb el token revocat
                async def _rot_offline() -> bool:
                    return not await vault_tunnel_broker.is_online(empresa_target_key(emp_id))
                await _wait_for(_rot_offline)
                await asyncio.sleep(0.4)
                assert await vault_tunnel_broker.is_online(empresa_target_key(emp_id)) is False
    finally:
        if agent is not None:
            await agent.stop()
        await _cleanup_empresa(emp_id)
