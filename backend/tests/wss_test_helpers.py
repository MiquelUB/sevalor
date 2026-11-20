"""Helpers reals (Zero Mock) per a tests d'integració sobre el Túnel Invers Sobirà WSS.

Permet a qualsevol test aixecar un servidor Uvicorn real al mateix event loop,
connectar un `SovereignWssAgent` real (EMPRESA o SUPERADMIN) amb Disc A + mirall Disc B
i un servidor HTTP LLM local real (OpenAI-compatible `/v1/models` i `/v1/chat/completions`).
"""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
import json
import socket
import sys
import threading
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, AsyncIterator, Callable, Dict, List, Optional

import uvicorn

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import scripts.client_vault_agent as cva  # noqa: E402

from app.main import app  # noqa: E402
from app.services.vault_tunnel import (  # noqa: E402
    SUPERADMIN_TARGET_KEY,
    empresa_target_key,
    vault_tunnel_broker,
)


def find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


class LiveUvicornServer:
    """Servidor Uvicorn real sobre el mateix event loop de pytest-asyncio (zero conflictes)."""

    def __init__(self, asgi_app: Any = app, port: Optional[int] = None) -> None:
        self.port = port or find_free_port()
        self.config = uvicorn.Config(
            asgi_app,
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

    async def __aenter__(self) -> "LiveUvicornServer":
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


class RunningWssAgent:
    """Executa un `SovereignWssAgent` real in-process amb parada neta via `stop_event`."""

    def __init__(
        self,
        server_http_url: str,
        *,
        role: str,
        token: str,
        disk_a: Path,
        disk_b: Optional[Path] = None,
        empresa_id: Optional[str] = None,
        llm_url: str = "http://127.0.0.1:1234",
    ) -> None:
        cfg = cva.AgentConfig(
            server_url=server_http_url,
            role=role,
            vault_token=token,
            empresa_id=empresa_id,
            disk_a=disk_a,
            disk_b=disk_b or (disk_a.parent / f"{disk_a.name}_mirror"),
            local_llm_url=llm_url,
        )
        self.agent = cva.SovereignWssAgent(cfg)
        self.stop_event = asyncio.Event()
        self.task: Optional[asyncio.Task[None]] = None

    def start(self) -> "RunningWssAgent":
        self.task = asyncio.create_task(self.agent.run_forever(stop_event=self.stop_event))
        return self

    async def stop(self) -> None:
        self.stop_event.set()
        if self.task is not None:
            try:
                await asyncio.wait_for(self.task, timeout=3.0)
            except (asyncio.TimeoutError, asyncio.CancelledError):
                self.task.cancel()

    async def __aenter__(self) -> "RunningWssAgent":
        self.start()
        return self

    async def __aexit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        await self.stop()


async def wait_for(predicate: Callable[[], Any], timeout: float = 8.0, interval: float = 0.05) -> None:
    deadline = asyncio.get_running_loop().time() + timeout
    while asyncio.get_running_loop().time() < deadline:
        res = predicate()
        if asyncio.iscoroutine(res):
            res = await res
        if res:
            return
        await asyncio.sleep(interval)
    raise AssertionError(f"Condició no assolida en {timeout}s.")


def start_local_llm_server(
    model_name: str = "sevalor-test-local-qwen",
    reply_builder: Optional[Callable[[Dict[str, Any]], Dict[str, Any]]] = None,
    default_reply: str = "Resposta real del node LLM sobirà via WSS.",
) -> tuple[ThreadingHTTPServer, str, List[Dict[str, Any]]]:
    """Aixeca un servidor HTTP local OpenAI-compatible (`/v1/models`, `/v1/chat/completions`)."""
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
            req_body = json.loads(raw.decode())
            calls.append({"method": "POST", "path": self.path, "body": req_body})
            if self.path == "/v1/chat/completions":
                if reply_builder is not None:
                    resp_obj = reply_builder(req_body)
                else:
                    resp_obj = {
                        "id": "chatcmpl-sevalor-wss",
                        "object": "chat.completion",
                        "model": model_name,
                        "choices": [
                            {
                                "index": 0,
                                "message": {"role": "assistant", "content": default_reply},
                                "finish_reason": "stop",
                            }
                        ],
                    }
                body = json.dumps(resp_obj).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return
            self.send_response(404)
            self.end_headers()

    port = find_free_port()
    srv = ThreadingHTTPServer(("127.0.0.1", port), _Handler)
    th = threading.Thread(target=srv.serve_forever, daemon=True)
    th.start()
    return srv, f"http://127.0.0.1:{port}", calls


@asynccontextmanager
async def live_empresa_wss_context(
    empresa_id: uuid.UUID | str,
    vault_token: str,
    disk_a: Path,
    *,
    disk_b: Optional[Path] = None,
    model_name: str = "sevalor-test-local-qwen",
    reply_builder: Optional[Callable[[Dict[str, Any]], Dict[str, Any]]] = None,
    default_reply: str = "Resposta real del node LLM sobirà via WSS.",
    start_llm: bool = True,
) -> AsyncIterator[Dict[str, Any]]:
    """Context manager tot-en-un: Uvicorn real + LLM HTTP local real + SovereignWssAgent EMPRESA."""
    llm_srv: Optional[ThreadingHTTPServer] = None
    llm_url = f"http://127.0.0.1:{find_free_port()}"
    llm_calls: List[Dict[str, Any]] = []
    if start_llm:
        llm_srv, llm_url, llm_calls = start_local_llm_server(
            model_name=model_name,
            reply_builder=reply_builder,
            default_reply=default_reply,
        )
    emp_str = str(empresa_id)
    target_key = empresa_target_key(emp_str)
    try:
        async with LiveUvicornServer() as server:
            async with RunningWssAgent(
                server.http_url,
                role="EMPRESA",
                token=vault_token,
                empresa_id=emp_str,
                disk_a=disk_a,
                disk_b=disk_b,
                llm_url=llm_url,
            ) as agent:
                await wait_for(lambda: vault_tunnel_broker.is_online(target_key), timeout=8.0)
                yield {
                    "server": server,
                    "http_url": server.http_url,
                    "agent": agent,
                    "llm_url": llm_url,
                    "llm_calls": llm_calls,
                    "disk_a": disk_a,
                    "disk_b": disk_b or (disk_a.parent / f"{disk_a.name}_mirror"),
                }
    finally:
        await vault_tunnel_broker.disconnect(target_key)
        if llm_srv is not None:
            llm_srv.shutdown()
            llm_srv.server_close()


@asynccontextmanager
async def live_superadmin_wss_context(
    secret: str,
    disk_a: Path,
    *,
    disk_b: Optional[Path] = None,
) -> AsyncIterator[Dict[str, Any]]:
    """Context manager tot-en-un: Uvicorn real + SovereignWssAgent SUPERADMIN."""
    try:
        async with LiveUvicornServer() as server:
            async with RunningWssAgent(
                server.http_url,
                role="SUPERADMIN",
                token=secret,
                disk_a=disk_a,
                disk_b=disk_b,
            ) as agent:
                await wait_for(
                    lambda: vault_tunnel_broker.is_online(SUPERADMIN_TARGET_KEY),
                    timeout=8.0,
                )
                yield {
                    "server": server,
                    "http_url": server.http_url,
                    "agent": agent,
                    "disk_a": disk_a,
                    "disk_b": disk_b or (disk_a.parent / f"{disk_a.name}_mirror"),
                }
    finally:
        await vault_tunnel_broker.disconnect(SUPERADMIN_TARGET_KEY)
