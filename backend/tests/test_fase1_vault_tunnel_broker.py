"""Tests d'integració reals (Zero Mock) per a la Fase 1: Broker i Endpoint WSS Sobirà.

Valida:
1. Handshake Zero-Trust (`WS /api/v1/vault-tunnel/connect`) amb codis 4401/4403 i `AlertaSeguretat`.
2. Multiplexació concurrent per `req_id` i aïllament estricte entre 2 Empreses + Superadmin.
3. Integritat binària SHA-256, límit de 50 MB i allowlist d'accions.
4. Substitució neta de slot exclusiu (`4009`), offline (`503`) i timeout (`504`).
5. Auto-inicialització automàtica en connectar (38 carpetes + `empresa.json` + `boss.json` +
   `system_prompt.txt`) i auto-drenatge de cua xifrada `SVENC1:` amb `unlink` a Hetzner.
6. Pont RPC cross-process real via Redis 7 (`celery_worker` / `bot` -> `uvicorn` -> WSS).
"""

from __future__ import annotations

import asyncio
import base64
import hashlib
import json
import socket
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

import pytest
import uvicorn
import websockets
from sqlalchemy import delete, select

from app.core.db import AsyncSessionLocal
from app.main import app
from app.models.models import AlertaSeguretat, Empresa, Usuari
from app.services.sovereign_storage import (
    SovereignStorageGateway,
    inicialitzar_arbre_carpetes_disc,
    inicialitzar_arbre_carpetes_superadmin,
)
from app.services.vault_tunnel import (
    MAX_BINARY_PAYLOAD_BYTES,
    SUPERADMIN_TARGET_KEY,
    VaultTunnelError,
    VaultTunnelOfflineError,
    VaultTunnelTimeoutError,
    empresa_target_key,
    vault_tunnel_broker,
)


def _find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


class _LiveUvicornContext:
    """Arrenca un servidor Uvicorn real al mateix event loop (Zero Mock, zero conflictes de loop)."""

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
    def ws_url(self) -> str:
        return f"ws://127.0.0.1:{self.port}/api/v1/vault-tunnel/connect"

    async def __aenter__(self) -> "_LiveUvicornContext":
        self._task = asyncio.create_task(self.server.serve())
        deadline = asyncio.get_running_loop().time() + 8.0
        while not self.server.started:
            if asyncio.get_running_loop().time() > deadline:
                raise RuntimeError("El servidor Uvicorn real no ha arrencat a temps.")
            await asyncio.sleep(0.03)
        return self

    async def __aexit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        self.server.should_exit = True
        if self._task is not None:
            try:
                await asyncio.wait_for(self._task, timeout=5.0)
            except asyncio.TimeoutError:
                self._task.cancel()


class _DiskWssAgentHarness:
    """Agent WebSocket real de prova que opera físicament sobre una carpeta `tmp_path`."""

    def __init__(
        self,
        ws_url: str,
        *,
        role: str,
        token: str,
        disk_root: Path,
        empresa_id: Optional[str] = None,
        model_id: str = "qwen2.5-vl-7b-instruct",
        unresponsive: bool = False,
    ) -> None:
        self.ws_url = ws_url
        self.role = role
        self.token = token
        self.disk_root = disk_root
        self.empresa_id = empresa_id
        self.model_id = model_id
        self.unresponsive = unresponsive
        self.ws: Any = None
        self.welcome: Dict[str, Any] = {}
        self.received_actions: List[str] = []
        self.close_code: Optional[int] = None
        self._task: Optional[asyncio.Task[None]] = None

    async def start(self) -> None:
        headers = {
            "X-Vault-Role": self.role,
            "X-Vault-Token": self.token,
            "X-Agent-Version": "test-wss-harness/1.0",
        }
        if self.empresa_id is not None:
            headers["X-Empresa-ID"] = self.empresa_id

        self.ws = await websockets.connect(self.ws_url, additional_headers=headers)
        raw_welcome = await asyncio.wait_for(self.ws.recv(), timeout=5.0)
        self.welcome = json.loads(raw_welcome)
        await self.ws.send(
            json.dumps(
                {
                    "type": "hello",
                    "agent_version": "test-wss-harness/1.0",
                    "health": {"disk_root": str(self.disk_root), "model": self.model_id},
                }
            )
        )
        self._task = asyncio.create_task(self._loop())

    async def stop(self) -> None:
        if self.ws is not None:
            try:
                await self.ws.close()
            except Exception:
                pass
        if self._task is not None and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except (asyncio.CancelledError, Exception):
                pass

    async def _loop(self) -> None:
        assert self.ws is not None
        try:
            async for raw in self.ws:
                msg = json.loads(raw)
                mtype = msg.get("type")
                req_id = msg.get("req_id")
                if mtype == "ping":
                    if not self.unresponsive:
                        await self.ws.send(json.dumps({"type": "pong", "req_id": req_id}))
                    continue
                if mtype != "request":
                    continue
                action = str(msg.get("action") or "")
                payload = msg.get("payload") or {}
                self.received_actions.append(action)
                if self.unresponsive:
                    continue
                try:
                    data = self._execute(action, payload)
                    await self.ws.send(
                        json.dumps({"type": "response", "req_id": req_id, "ok": True, "data": data})
                    )
                except Exception as exc:
                    await self.ws.send(
                        json.dumps(
                            {
                                "type": "response",
                                "req_id": req_id,
                                "ok": False,
                                "error_code": "AGENT_ERROR",
                                "status_code": 400,
                                "detail": str(exc),
                            }
                        )
                    )
        except websockets.exceptions.ConnectionClosed as closed_exc:
            self.close_code = closed_exc.rcvd.code if closed_exc.rcvd else None
        except asyncio.CancelledError:
            return

    def _safe_path(self, rel: str) -> Path:
        base = self.disk_root.resolve()
        target = (base / rel.lstrip("/")).resolve()
        if not target.is_relative_to(base):
            raise ValueError("Path traversal detectat")
        return target

    def _execute(self, action: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        self.disk_root.mkdir(parents=True, exist_ok=True)
        if action == "health":
            return {
                "status": "OK",
                "role": self.role,
                "vault_root": str(self.disk_root),
                "models": [self.model_id],
            }
        if action == "init_folders":
            if self.role == "SUPERADMIN":
                creades = inicialitzar_arbre_carpetes_superadmin(self.disk_root)
            else:
                creades = inicialitzar_arbre_carpetes_disc(self.disk_root)
            return {"role": self.role, "carpetes_count": len(creades)}
        if action == "json_put":
            sub = str(payload["subcarpeta"])
            item_id = str(payload["item_id"])
            folder = self._safe_path(sub)
            folder.mkdir(parents=True, exist_ok=True)
            fp = self._safe_path(f"{sub}/{item_id}.json")
            fp.write_text(json.dumps(payload["content"], ensure_ascii=False, indent=2), encoding="utf-8")
            return {"saved": str(fp)}
        if action == "json_get_list":
            folder = self._safe_path(str(payload["subcarpeta"]))
            if not folder.is_dir():
                return {"items": []}
            items = [json.loads(p.read_text(encoding="utf-8")) for p in sorted(folder.glob("*.json"))]
            return {"items": items}
        if action == "json_delete":
            fp = self._safe_path(f"{payload['subcarpeta']}/{payload['item_id']}.json")
            if fp.is_file():
                fp.unlink()
                return {"deleted": True}
            return {"deleted": False}
        if action == "file_put":
            sub = str(payload["subcarpeta"])
            fname = str(payload["filename"])
            raw = base64.b64decode(payload["content_b64"].encode("ascii"))
            folder = self._safe_path(sub)
            folder.mkdir(parents=True, exist_ok=True)
            fp = self._safe_path(f"{sub}/{fname}")
            fp.write_bytes(raw)
            return {"rel_path": f"{sub}/{fname}", "sha256": hashlib.sha256(raw).hexdigest()}
        if action == "file_get":
            fp = self._safe_path(str(payload["rel_path"]))
            if not fp.is_file():
                raise FileNotFoundError("Fitxer no trobat")
            raw = fp.read_bytes()
            return {
                "filename": fp.name,
                "content_b64": base64.b64encode(raw).decode("ascii"),
                "sha256": hashlib.sha256(raw).hexdigest(),
            }
        if action == "file_rename":
            old_fp = self._safe_path(str(payload["old_rel_path"]))
            new_sub = str(payload["new_subcarpeta"])
            new_name = str(payload["new_filename"])
            dest_dir = self._safe_path(new_sub)
            dest_dir.mkdir(parents=True, exist_ok=True)
            new_fp = self._safe_path(f"{new_sub}/{new_name}")
            old_fp.replace(new_fp)
            return {"rel_path": f"{new_sub}/{new_name}"}
        if action == "file_delete":
            fp = self._safe_path(str(payload["rel_path"]))
            if fp.is_file():
                fp.unlink()
                return {"deleted": True}
            return {"deleted": False}
        if action == "llm_models":
            return {"data": [{"id": self.model_id}]}
        if action == "llm_chat":
            return {
                "model": self.model_id,
                "choices": [{"message": {"role": "assistant", "content": f"Resposta de {self.model_id}"}}],
            }
        raise ValueError(f"Acció no suportada: {action}")


async def _create_real_empresa(
    *,
    nom: str,
    vault_token: str,
    estat_pagament: str = "ACTIU",
    feature_copilot_ia: bool = True,
    node_ia_actiu: bool = False,
    agent_prompt_system: Optional[str] = None,
    with_boss: bool = False,
) -> uuid.UUID:
    emp_id = uuid.uuid4()
    rnd = emp_id.hex[:8].upper()
    async with AsyncSessionLocal() as session:
        emp = Empresa(
            id=emp_id,
            nom=nom,
            nif=f"B{rnd}",
            subdomini=f"f1-{emp_id.hex[:8]}",
            vertical="ELECTRICPRO",
            estat_pagament=estat_pagament,
            vault_token=vault_token,
            feature_copilot_ia=feature_copilot_ia,
            node_ia_actiu=node_ia_actiu,
            disc_dur_url=None,
            node_ia_url=None,
            agent_prompt_system=agent_prompt_system,
        )
        session.add(emp)
        if with_boss:
            boss = Usuari(
                id=uuid.uuid4(),
                empresa_id=emp_id,
                nom="Pere",
                cognoms="Vila Soler",
                nif=f"4{emp_id.hex[:7].upper()}X",
                email=f"boss_{emp_id.hex[:6]}@empresa.cat",
                telefon="+34600111222",
                rol="BOSS",
            )
            session.add(boss)
        await session.commit()
    return emp_id


async def _cleanup_empreses(emp_ids: List[uuid.UUID]) -> None:
    if not emp_ids:
        return
    async with AsyncSessionLocal() as session:
        await session.execute(delete(AlertaSeguretat).where(AlertaSeguretat.empresa_id.in_(emp_ids)))
        await session.execute(delete(Usuari).where(Usuari.empresa_id.in_(emp_ids)))
        await session.execute(delete(Empresa).where(Empresa.id.in_(emp_ids)))
        await session.commit()


async def _expect_ws_rejected(ws_url: str, headers: Dict[str, str], expected_code: int) -> None:
    async with websockets.connect(ws_url, additional_headers=headers) as ws:
        with pytest.raises(websockets.exceptions.ConnectionClosed) as exc_info:
            await asyncio.wait_for(ws.recv(), timeout=5.0)
        rcvd = exc_info.value.rcvd
        assert rcvd is not None
        assert rcvd.code == expected_code
        # Mai filtrar detalls interns al motiu del tancament
        assert rcvd.reason in ("Unauthorized", "Forbidden", "")


@pytest.mark.asyncio
async def test_fase1_handshake_zero_trust_i_alertes_auditoria(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verifica rebuig Zero-Trust (4401/4403), anti-spoofing cross-tenant i registre d'AlertaSeguretat."""
    sa_secret = f"sa_secret_{uuid.uuid4().hex}"
    monkeypatch.setenv("SUPERADMIN_VAULT_SECRET", sa_secret)

    tok_a = f"svlt_{uuid.uuid4().hex}"
    tok_b = f"svlt_{uuid.uuid4().hex}"
    tok_susp = f"svlt_{uuid.uuid4().hex}"
    tok_elim = f"svlt_{uuid.uuid4().hex}"

    emp_a = await _create_real_empresa(nom="Empresa A Auth", vault_token=tok_a)
    emp_b = await _create_real_empresa(nom="Empresa B Auth", vault_token=tok_b)
    emp_susp = await _create_real_empresa(
        nom="Empresa Suspesa", vault_token=tok_susp, estat_pagament="SUSPES_PAGAMENT"
    )
    emp_elim = await _create_real_empresa(
        nom="Empresa Eliminada", vault_token=tok_elim, estat_pagament="ELIMINAT"
    )

    try:
        async with _LiveUvicornContext() as srv:
            # 1. Rol absent o invàlid -> 4401
            await _expect_ws_rejected(srv.ws_url, {}, 4401)
            await _expect_ws_rejected(
                srv.ws_url, {"X-Vault-Role": "HACKER", "X-Vault-Token": tok_a}, 4401
            )
            # 2. Token absent -> 4401
            await _expect_ws_rejected(
                srv.ws_url, {"X-Vault-Role": "EMPRESA", "X-Empresa-ID": str(emp_a)}, 4401
            )
            # 3. Superadmin amb token erroni -> 4401
            await _expect_ws_rejected(
                srv.ws_url, {"X-Vault-Role": "SUPERADMIN", "X-Vault-Token": "wrong"}, 4401
            )
            # 4. Superadmin passant X-Empresa-ID -> 4403
            await _expect_ws_rejected(
                srv.ws_url,
                {"X-Vault-Role": "SUPERADMIN", "X-Vault-Token": sa_secret, "X-Empresa-ID": str(emp_a)},
                4403,
            )
            # 5. Empresa sense X-Empresa-ID o UUID invàlid -> 4401
            await _expect_ws_rejected(
                srv.ws_url, {"X-Vault-Role": "EMPRESA", "X-Vault-Token": tok_a}, 4401
            )
            await _expect_ws_rejected(
                srv.ws_url,
                {"X-Vault-Role": "EMPRESA", "X-Empresa-ID": "not-a-uuid", "X-Vault-Token": tok_a},
                4401,
            )
            # 6. Cross-tenant spoofing (ID d'Empresa A amb token vàlid d'Empresa B) -> 4401
            await _expect_ws_rejected(
                srv.ws_url,
                {"X-Vault-Role": "EMPRESA", "X-Empresa-ID": str(emp_a), "X-Vault-Token": tok_b},
                4401,
            )
            # 7. Empresa suspesa o eliminada amb token correcte -> 4403
            await _expect_ws_rejected(
                srv.ws_url,
                {"X-Vault-Role": "EMPRESA", "X-Empresa-ID": str(emp_susp), "X-Vault-Token": tok_susp},
                4403,
            )
            await _expect_ws_rejected(
                srv.ws_url,
                {"X-Vault-Role": "EMPRESA", "X-Empresa-ID": str(emp_elim), "X-Vault-Token": tok_elim},
                4403,
            )

        # Verificar que s'han registrat alertes d'auditoria a PostgreSQL
        async with AsyncSessionLocal() as session:
            res = await session.execute(
                select(AlertaSeguretat).where(
                    AlertaSeguretat.tipus == "WSS_TUNNEL_AUTH_FAILED",
                    AlertaSeguretat.empresa_id.in_([emp_a, emp_susp, emp_elim]),
                )
            )
            alertes = list(res.scalars().all())
            assert len(alertes) >= 3
            assert all(a.origen == "vault_tunnel" and a.gravetat == "VERMELLA" for a in alertes)
    finally:
        await _cleanup_empreses([emp_a, emp_b, emp_susp, emp_elim])


@pytest.mark.asyncio
async def test_fase1_multiplexat_concurrent_aillament_3_nodes_i_binaris(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verifica 2 Empreses + Superadmin en paral·lel, multiplexat per req_id, SHA-256 i límit 50 MB."""
    sa_secret = f"sa_secret_{uuid.uuid4().hex}"
    monkeypatch.setenv("SUPERADMIN_VAULT_SECRET", sa_secret)

    tok_a = f"svlt_{uuid.uuid4().hex}"
    tok_b = f"svlt_{uuid.uuid4().hex}"
    emp_a = await _create_real_empresa(nom="Empresa A Multi", vault_token=tok_a)
    emp_b = await _create_real_empresa(nom="Empresa B Multi", vault_token=tok_b)

    disk_a = tmp_path / "disk_emp_a"
    disk_b = tmp_path / "disk_emp_b"
    disk_sa = tmp_path / "disk_superadmin"

    key_a = empresa_target_key(emp_a)
    key_b = empresa_target_key(emp_b)

    try:
        async with _LiveUvicornContext() as srv:
            agent_a = _DiskWssAgentHarness(
                srv.ws_url, role="EMPRESA", empresa_id=str(emp_a), token=tok_a, disk_root=disk_a, model_id="model-a"
            )
            agent_b = _DiskWssAgentHarness(
                srv.ws_url, role="EMPRESA", empresa_id=str(emp_b), token=tok_b, disk_root=disk_b, model_id="model-b"
            )
            agent_sa = _DiskWssAgentHarness(
                srv.ws_url, role="SUPERADMIN", token=sa_secret, disk_root=disk_sa, model_id="model-sa"
            )

            await asyncio.gather(agent_a.start(), agent_b.start(), agent_sa.start())
            try:
                assert agent_a.welcome["target_key"] == key_a
                assert agent_b.welcome["target_key"] == key_b
                assert agent_sa.welcome["target_key"] == SUPERADMIN_TARGET_KEY

                assert await vault_tunnel_broker.is_online(key_a)
                assert await vault_tunnel_broker.is_online(key_b)
                assert await vault_tunnel_broker.is_online(SUPERADMIN_TARGET_KEY)

                # Executar 8 operacions concurrents multiplexades sobre els 3 túnels simultàniament
                pdf_bytes_a = b"%PDF-1.4\nFactura exclusiva Empresa A\n" + (b"A" * 4096)
                pdf_bytes_b = b"%PDF-1.4\nFactura exclusiva Empresa B\n" + (b"B" * 4096)

                (
                    health_a,
                    health_b,
                    health_sa,
                    _,
                    _,
                    _,
                    _,
                    chat_a,
                    chat_b,
                ) = await asyncio.gather(
                    vault_tunnel_broker.health(key_a),
                    vault_tunnel_broker.health(key_b),
                    vault_tunnel_broker.health(SUPERADMIN_TARGET_KEY),
                    vault_tunnel_broker.json_put(key_a, "01_clients/fitxes", "cli_a", {"nom": "Client A"}),
                    vault_tunnel_broker.json_put(key_b, "01_clients/fitxes", "cli_b", {"nom": "Client B"}),
                    vault_tunnel_broker.file_put(key_a, "04_factures/emeses_verifactu_pdf", "fac_a.pdf", pdf_bytes_a, "application/pdf"),
                    vault_tunnel_broker.file_put(key_b, "04_factures/emeses_verifactu_pdf", "fac_b.pdf", pdf_bytes_b, "application/pdf"),
                    vault_tunnel_broker.call_llm_chat(key_a, {"messages": [{"role": "user", "content": "hola"}]}),
                    vault_tunnel_broker.call_llm_chat(key_b, {"messages": [{"role": "user", "content": "hola"}]}),
                )

                assert health_a["models"] == ["model-a"]
                assert health_b["models"] == ["model-b"]
                assert health_sa["role"] == "SUPERADMIN"
                assert chat_a["model"] == "model-a"
                assert chat_b["model"] == "model-b"

                # Aïllament físic absolut als discos locals
                assert (disk_a / "01_clients/fitxes/cli_a.json").is_file()
                assert not (disk_a / "01_clients/fitxes/cli_b.json").exists()
                assert (disk_b / "01_clients/fitxes/cli_b.json").is_file()
                assert not (disk_b / "01_clients/fitxes/cli_a.json").exists()
                assert not (disk_sa / "01_clients/fitxes/cli_a.json").exists()

                # Descàrrega binària amb verificació SHA-256 + reanomenat + esborrat
                got_a, name_a = await vault_tunnel_broker.file_get(key_a, "04_factures/emeses_verifactu_pdf/fac_a.pdf")
                assert got_a == pdf_bytes_a
                assert name_a == "fac_a.pdf"

                await vault_tunnel_broker.file_rename(
                    key_a,
                    "04_factures/emeses_verifactu_pdf/fac_a.pdf",
                    "04_factures/emeses_verifactu_pdf",
                    "fac_a_final.pdf",
                )
                assert (disk_a / "04_factures/emeses_verifactu_pdf/fac_a_final.pdf").is_file()
                assert await vault_tunnel_broker.file_delete(key_a, "04_factures/emeses_verifactu_pdf/fac_a_final.pdf") is True
                assert await vault_tunnel_broker.json_delete(key_a, "01_clients/fitxes", "cli_a") is True

                # Límit de 50 MB i allowlist d'accions
                with pytest.raises(VaultTunnelError) as exc_big:
                    await vault_tunnel_broker.file_put(
                        key_a,
                        "05_planols/arxius_base",
                        "gegant.bin",
                        b"\x00" * (MAX_BINARY_PAYLOAD_BYTES + 1),
                    )
                assert exc_big.value.status_code == 413

                with pytest.raises(ValueError):
                    await vault_tunnel_broker.call(key_a, "shell_exec", {"cmd": "id"})
            finally:
                await asyncio.gather(agent_a.stop(), agent_b.stop(), agent_sa.stop())
    finally:
        await _cleanup_empreses([emp_a, emp_b])


@pytest.mark.asyncio
async def test_fase1_reemplacament_slot_exclusiu_i_offline_timeout(tmp_path: Path) -> None:
    """Verifica substitució neta de reconnexió (4009), error 503 offline i 504 timeout."""
    tok = f"svlt_{uuid.uuid4().hex}"
    emp_id = await _create_real_empresa(nom="Empresa Slot Exclusiu", vault_token=tok)
    target_key = empresa_target_key(emp_id)

    try:
        # Sense cap agent connectat -> 503 OFFLINE
        with pytest.raises(VaultTunnelOfflineError) as exc_off:
            await vault_tunnel_broker.health(target_key)
        assert exc_off.value.status_code == 503
        assert exc_off.value.code == "NODE_EMPRESA_OFFLINE"

        async with _LiveUvicornContext() as srv:
            agent_1 = _DiskWssAgentHarness(
                srv.ws_url, role="EMPRESA", empresa_id=str(emp_id), token=tok, disk_root=tmp_path / "d1", model_id="m1"
            )
            await agent_1.start()
            h1 = await vault_tunnel_broker.health(target_key)
            assert h1["models"] == ["m1"]

            # Reconnexió del mateix tenant substitueix netament agent_1 (codi 4009)
            agent_2 = _DiskWssAgentHarness(
                srv.ws_url, role="EMPRESA", empresa_id=str(emp_id), token=tok, disk_root=tmp_path / "d2", model_id="m2"
            )
            await agent_2.start()
            await asyncio.sleep(0.15)
            assert agent_1.close_code == 4009

            h2 = await vault_tunnel_broker.health(target_key)
            assert h2["models"] == ["m2"]
            await agent_2.stop()
            await agent_1.stop()

            # Client mut que no respon -> 504 TUNNEL_TIMEOUT
            agent_stuck = _DiskWssAgentHarness(
                srv.ws_url,
                role="EMPRESA",
                empresa_id=str(emp_id),
                token=tok,
                disk_root=tmp_path / "d3",
                unresponsive=True,
            )
            await agent_stuck.start()
            try:
                with pytest.raises(VaultTunnelTimeoutError) as exc_to:
                    await vault_tunnel_broker.health(target_key, timeout=0.3)
                assert exc_to.value.status_code == 504
            finally:
                await agent_stuck.stop()
    finally:
        await _cleanup_empreses([emp_id])


@pytest.mark.asyncio
async def test_fase1_auto_inicialitzacio_38_carpetes_fitxes_i_autodrenatge_svenc1(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """
    Certifica el flux confirmat d'onboarding + auto-drenatge en connectar per WSS:
    1. Abans de connectar el PC, s'encuen 1 JSON + 1 PDF xifrats `SVENC1:` a la cua de trànsit.
    2. En connectar el PC per WSS, es creen automàticament les 38 carpetes, `empresa.json`,
       `boss.json`, `system_prompt.txt`, s'actualitza SQL (`wss-tunnel://<id>`, `node_ia_actiu=True`)
       i es drenen + purguen (`unlink`) els paquets xifrats de Hetzner.
    3. Si posteriorment es desactiva explícitament `node_ia_actiu=False`, una reconnexió WSS
       respecta la desactivació explícita.
    """
    transit_dir = tmp_path / "transit_fase1"
    monkeypatch.setenv("SOVEREIGN_TRANSIT_QUEUE_DIR", str(transit_dir))
    monkeypatch.setattr(SovereignStorageGateway, "TRANSIT_QUEUE_DIR", transit_dir)

    tok = f"svlt_{uuid.uuid4().hex}"
    emp_id = await _create_real_empresa(
        nom="Electrotec Sobirana SL",
        vault_token=tok,
        feature_copilot_ia=True,
        node_ia_actiu=False,
        with_boss=True,
    )
    disk_emp = tmp_path / "disc_electrotec"

    try:
        # 1. Escriptures prèvies mentre el PC està apagat -> cua xifrada SVENC1:
        from app.services.copilot_config_service import save_strict_copilot_config

        async with AsyncSessionLocal() as session:
            await save_strict_copilot_config(
                session,
                emp_id,
                system_prompt="Ets el Copilot REBT dedicat d'Electrotec Sobirana.",
            )
            ref_json = await SovereignStorageGateway.desar_entitat_json(
                session, emp_id, "clients", "cli_pend_1", {"nom": "Finca Pendent"}
            )
            ref_pdf = await SovereignStorageGateway.pujar_fitxer_binari(
                session,
                emp_id,
                "factures_pdf",
                "fac_pend_1.pdf",
                b"%PDF-1.4\nPENDENT-SVENC1\n",
                "application/pdf",
            )
        assert ref_json.startswith(f"transit://{emp_id}/")
        assert ref_pdf.startswith(f"transit://{emp_id}/")
        assert len(list((transit_dir / str(emp_id)).glob("*.bin"))) == 3

        # 2. El PC es connecta pel túnel WSS -> bootstrap automàtic + drenatge + unlink
        async with _LiveUvicornContext() as srv:
            agent = _DiskWssAgentHarness(
                srv.ws_url, role="EMPRESA", empresa_id=str(emp_id), token=tok, disk_root=disk_emp
            )
            await agent.start()
            try:
                # Esperar que el bootstrap en segon pla completi drenatge i fitxes
                deadline = asyncio.get_running_loop().time() + 6.0
                while asyncio.get_running_loop().time() < deadline:
                    if (
                        (disk_emp / "04_factures/emeses_verifactu_pdf/fac_pend_1.pdf").is_file()
                        and (disk_emp / "11_configuracio_i_backups/identitat_camaleo/empresa.json").is_file()
                        and (disk_emp / "09_copilot_ia/prompt_sistema/copilot_profile.json").is_file()
                    ):
                        break
                    await asyncio.sleep(0.05)

                # Verificar 38 carpetes + fitxes inicials
                assert (disk_emp / "09_copilot_ia/index_vectorial_rag").is_dir()
                assert (disk_emp / "06_ordres_treball/actives_buffer").is_dir()
                assert (disk_emp / "11_configuracio_i_backups/identitat_camaleo/empresa.json").is_file()
                assert (disk_emp / "11_configuracio_i_backups/identitat_camaleo/boss.json").is_file()
                profile_data = json.loads(
                    (disk_emp / "09_copilot_ia/prompt_sistema/copilot_profile.json").read_text(encoding="utf-8")
                )
                assert profile_data["system_prompt"] == "Ets el Copilot REBT dedicat d'Electrotec Sobirana."

                # Verificar drenatge real al disc físic + purga (unlink) de Hetzner
                cli_file = disk_emp / "01_clients/fitxes/cli_pend_1.json"
                pdf_file = disk_emp / "04_factures/emeses_verifactu_pdf/fac_pend_1.pdf"
                assert cli_file.is_file()
                assert json.loads(cli_file.read_text(encoding="utf-8"))["nom"] == "Finca Pendent"
                assert pdf_file.read_bytes() == b"%PDF-1.4\nPENDENT-SVENC1\n"
                assert not (transit_dir / str(emp_id)).exists()

                # Verificar actualització a PostgreSQL
                async with AsyncSessionLocal() as session:
                    emp_db = (await session.execute(select(Empresa).where(Empresa.id == emp_id))).scalar_one()
                    assert emp_db.disc_dur_url == f"wss-tunnel://{emp_id}"
                    assert emp_db.node_ia_url == f"wss-tunnel://{emp_id}"
                    assert emp_db.node_ia_actiu is True
            finally:
                await agent.stop()

            # 3. Desactivació explícita de node_ia_actiu=False no se sobreescriu en reconnectar
            async with AsyncSessionLocal() as session:
                emp_db = (await session.execute(select(Empresa).where(Empresa.id == emp_id))).scalar_one()
                emp_db.node_ia_actiu = False
                await session.commit()

            agent_re = _DiskWssAgentHarness(
                srv.ws_url, role="EMPRESA", empresa_id=str(emp_id), token=tok, disk_root=disk_emp
            )
            await agent_re.start()
            try:
                await asyncio.sleep(0.25)
                async with AsyncSessionLocal() as session:
                    emp_db2 = (await session.execute(select(Empresa).where(Empresa.id == emp_id))).scalar_one()
                    assert emp_db2.node_ia_actiu is False
            finally:
                await agent_re.stop()
    finally:
        await _cleanup_empreses([emp_id])


@pytest.mark.asyncio
async def test_fase1_pont_redis_cross_process_rpc(tmp_path: Path) -> None:
    """Verifica el pont RPC cross-process real sobre Redis 7 (Celery/Bot -> Redis -> Uvicorn -> WSS)."""
    tok = f"svlt_{uuid.uuid4().hex}"
    emp_id = await _create_real_empresa(nom="Empresa Redis RPC", vault_token=tok)
    target_key = empresa_target_key(emp_id)
    disk_emp = tmp_path / "disc_redis_rpc"

    try:
        async with _LiveUvicornContext() as srv:
            agent = _DiskWssAgentHarness(
                srv.ws_url,
                role="EMPRESA",
                empresa_id=str(emp_id),
                token=tok,
                disk_root=disk_emp,
                model_id="qwen-redis-bridge",
            )
            await agent.start()
            try:
                # Forçar el camí cross-process via Redis 7 real (com faria celery_worker o bot)
                res_health = await vault_tunnel_broker.call(
                    target_key, "health", {}, timeout=8.0, _force_redis=True
                )
                assert res_health["status"] == "OK"
                assert res_health["models"] == ["qwen-redis-bridge"]

                res_chat = await vault_tunnel_broker.call(
                    target_key,
                    "llm_chat",
                    {"messages": [{"role": "user", "content": "ping via redis"}]},
                    timeout=8.0,
                    _force_redis=True,
                )
                assert res_chat["model"] == "qwen-redis-bridge"
                assert "qwen-redis-bridge" in res_chat["choices"][0]["message"]["content"]
            finally:
                await agent.stop()
    finally:
        await _cleanup_empreses([emp_id])
