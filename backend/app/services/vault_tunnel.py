"""Broker Multi-Tenant del Túnel Invers Natiu WSS Sobirà (ADR-001 — Fase 1).

Gestiona les connexions WebSocket sortints dels PCs dedicats d'empresa (`empresa:<uuid>`)
i del PC propietari de Superadmin (`superadmin`), multiplexant operacions de Disc Dur
i Copilot IA local per `req_id`, amb pont RPC cross-process transparent via Redis 7 per
a `celery_worker`, `celery_beat`, `bot` i múltiples processos `uvicorn`.
"""

from __future__ import annotations

import asyncio
import base64
import hashlib
import json
import logging
import math
import os
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import redis.asyncio as aioredis
from fastapi import WebSocket

from app.core.config import settings

logger = logging.getLogger("sevalor.vault_tunnel")

SUPERADMIN_TARGET_KEY = "superadmin"

# Allowlist estricta d'accions RPC permeses pel túnel WSS (security-and-hardening)
ALLOWED_TUNNEL_ACTIONS: frozenset[str] = frozenset(
    {
        "health",
        "init_folders",
        "json_put",
        "json_get_list",
        "json_delete",
        "file_put",
        "file_get",
        "file_rename",
        "file_delete",
        "backup_daily",
        "llm_models",
        "llm_chat",
        "ping",
    }
)

MAX_BINARY_PAYLOAD_BYTES: int = 50 * 1024 * 1024  # 50 MB (Constitució & AGENTS.md §3.4)
MAX_B64_CHARS: int = int(math.ceil(MAX_BINARY_PAYLOAD_BYTES * 4 / 3)) + 4096
HEARTBEAT_INTERVAL_SECONDS: float = 25.0
HEARTBEAT_TIMEOUT_SECONDS: float = 15.0
PRESENCE_TTL_SECONDS: int = 75
DEFAULT_RPC_TIMEOUT_SECONDS: float = 15.0
LLM_RPC_TIMEOUT_SECONDS: float = 120.0

REDIS_PRESENCE_PREFIX = "sevalor:tunnel:online:"
REDIS_RPC_QUEUE_PREFIX = "sevalor:tunnel:rpc:"
REDIS_RPC_REPLY_PREFIX = "sevalor:tunnel:reply:"


def empresa_target_key(empresa_id: str | uuid.UUID) -> str:
    """Retorna la clau canònica exclusiva `empresa:<uuid>` validant estricte format UUID."""
    canonical = str(uuid.UUID(str(empresa_id)))
    return f"empresa:{canonical}"


def parse_target_key(target_key: str) -> Tuple[str, Optional[str]]:
    """Analitza una clau de túnel en `(role, empresa_id)` validant-ne la sintaxi."""
    clean = str(target_key).strip()
    if clean == SUPERADMIN_TARGET_KEY:
        return ("SUPERADMIN", None)
    if clean.startswith("empresa:"):
        raw_id = clean[len("empresa:") :]
        canonical = str(uuid.UUID(raw_id))
        return ("EMPRESA", canonical)
    raise ValueError(f"Clau de túnel WSS invàlida: {target_key!r}")


class VaultTunnelError(Exception):
    """Error base del túnel invers WSS sobirà."""

    def __init__(self, detail: str, *, code: str = "TUNNEL_ERROR", status_code: int = 503) -> None:
        super().__init__(detail)
        self.detail = detail
        self.code = code
        self.status_code = status_code


class VaultTunnelOfflineError(VaultTunnelError):
    """El node sobirà (empresa o superadmin) no té cap sessió WSS activa."""

    def __init__(
        self,
        detail: str = "L'ordinador dedicat no està connectat al túnel WSS de Sevalor.",
        *,
        code: str = "NODE_EMPRESA_OFFLINE",
    ) -> None:
        super().__init__(detail, code=code, status_code=503)


class VaultTunnelTimeoutError(VaultTunnelError):
    """La petició enviada pel túnel WSS ha excedit el temps màxim d'espera."""

    def __init__(self, detail: str = "Temps d'espera esgotat al túnel WSS del node.") -> None:
        super().__init__(detail, code="TUNNEL_TIMEOUT", status_code=504)


class VaultTunnelRemoteError(VaultTunnelError):
    """L'agent sobirà del PC ha retornat un error controlat en executar l'acció."""

    def __init__(
        self,
        detail: str,
        *,
        code: str = "TUNNEL_REMOTE_ERROR",
        status_code: int = 502,
    ) -> None:
        super().__init__(detail, code=code, status_code=status_code)


@dataclass
class TunnelConnection:
    """Estat en memòria d'una connexió WSS activa autenticada."""

    target_key: str
    role: str
    websocket: WebSocket
    conn_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    empresa_id: Optional[str] = None
    agent_version: Optional[str] = None
    remote_ip: Optional[str] = None
    connected_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    last_seen_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    last_health: Dict[str, Any] = field(default_factory=dict)
    send_lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    pending: Dict[str, asyncio.Future[Dict[str, Any]]] = field(default_factory=dict)
    redis_listener_task: Optional[asyncio.Task[None]] = None
    heartbeat_task: Optional[asyncio.Task[None]] = None
    bootstrap_task: Optional[asyncio.Task[None]] = None
    closed: bool = False


def _resolve_redis_url() -> str:
    redis_pass = os.getenv("REDIS_PASSWORD", "sevalor_redis_pass")
    auth_part = f":{redis_pass}@" if redis_pass else ""
    default_url = f"redis://{auth_part}{settings.REDIS_HOST}:{settings.REDIS_PORT}/0"
    return str(os.getenv("REDIS_URL") or settings.REDIS_URL or default_url)


async def _create_redis_client(*, socket_timeout: Optional[float] = 5.0) -> Optional[aioredis.Redis]:
    """Obre una connexió dedicada a Redis 7 amb timeout controlat."""
    try:
        client = aioredis.from_url(
            _resolve_redis_url(),
            socket_connect_timeout=1.5,
            socket_timeout=socket_timeout,
            decode_responses=True,
        )
        await client.ping()
        return client
    except Exception as exc:
        logger.debug("Redis no disponible per al pont RPC del túnel WSS: %s", exc)
        return None


class VaultTunnelBroker:
    """Broker multi-tenant que enruta RPCs cap als agents WSS locals o via pont Redis 7."""

    def __init__(self) -> None:
        self._connections: Dict[str, TunnelConnection] = {}
        self._registry_lock = asyncio.Lock()

    async def register(
        self,
        target_key: str,
        role: str,
        websocket: WebSocket,
        *,
        empresa_id: Optional[str] = None,
        agent_version: Optional[str] = None,
        remote_ip: Optional[str] = None,
        heartbeat_interval: float = HEARTBEAT_INTERVAL_SECONDS,
        welcome_payload: Optional[Dict[str, Any]] = None,
    ) -> TunnelConnection:
        """Registra una nova connexió WSS exclusiva substituint netament qualsevol sessió prèvia.

        Manté `conn.send_lock` bloquejat des de la inserció a `_connections` fins a enviar la trama
        inicial `welcome`, garantint que `welcome` sigui sempre el primer missatge al cable i que
        cap petició RPC concurrent (local, Redis o heartbeat) pugui avançar-s'hi.
        """
        parse_target_key(target_key)
        conn = TunnelConnection(
            target_key=target_key,
            role=role,
            websocket=websocket,
            empresa_id=empresa_id,
            agent_version=agent_version,
            remote_ip=remote_ip,
        )

        old_conn: Optional[TunnelConnection] = None
        send_error: Optional[Exception] = None
        async with conn.send_lock:
            async with self._registry_lock:
                old_conn = self._connections.get(target_key)
                self._connections[target_key] = conn

            if old_conn is not None:
                logger.info(
                    "Substituint connexió WSS prèvia per %s (old=%s -> new=%s).",
                    target_key,
                    old_conn.conn_id,
                    conn.conn_id,
                )
                await self._teardown_connection(old_conn, close_code=4009, close_reason="Replaced")

            await self._publish_presence(conn)
            conn.heartbeat_task = asyncio.create_task(
                self._heartbeat_loop(conn, interval=heartbeat_interval),
                name=f"wss-hb-{target_key}-{conn.conn_id[:8]}",
            )
            conn.redis_listener_task = asyncio.create_task(
                self._redis_rpc_loop(conn),
                name=f"wss-redis-{target_key}-{conn.conn_id[:8]}",
            )
            if welcome_payload is not None:
                try:
                    await websocket.send_json({**welcome_payload, "conn_id": conn.conn_id})
                except Exception as exc:
                    conn.closed = True
                    send_error = exc

        if send_error is not None:
            await self.unregister(target_key, conn.conn_id)
            raise send_error

        logger.info(
            "Túnel WSS registrat: target=%s role=%s conn_id=%s agent_version=%s",
            target_key,
            role,
            conn.conn_id,
            agent_version or "unknown",
        )
        return conn

    async def unregister(self, target_key: str, conn_id: str) -> None:
        """Deregistra la connexió només si continua sent la vigent (protecció contra condicions de cursa)."""
        target_conn: Optional[TunnelConnection] = None
        async with self._registry_lock:
            current = self._connections.get(target_key)
            if current is not None and current.conn_id == conn_id:
                target_conn = self._connections.pop(target_key)

        if target_conn is not None:
            await self._teardown_connection(target_conn, close_code=None, close_reason=None)
            await self._clear_presence_if_owner(target_key, conn_id)
            logger.info("Túnel WSS desconnectat: target=%s conn_id=%s", target_key, conn_id)

    async def disconnect(
        self,
        target_key: str,
        *,
        code: int = 4401,
        reason: str = "Session revoked",
    ) -> bool:
        """Tanca immediatament la connexió WSS activa d'un destí (rotació de token o suspensió)."""
        target_conn: Optional[TunnelConnection] = None
        async with self._registry_lock:
            target_conn = self._connections.pop(target_key, None)

        if target_conn is None:
            return False

        await self._teardown_connection(target_conn, close_code=code, close_reason=reason)
        await self._clear_presence_if_owner(target_key, target_conn.conn_id)
        logger.info(
            "Túnel WSS revocat explícitament: target=%s conn_id=%s code=%s reason=%s",
            target_key,
            target_conn.conn_id,
            code,
            reason,
        )
        return True

    async def _teardown_connection(
        self,
        conn: TunnelConnection,
        *,
        close_code: Optional[int],
        close_reason: Optional[str],
    ) -> None:
        conn.closed = True
        current_task = asyncio.current_task()
        for task in (conn.heartbeat_task, conn.redis_listener_task, conn.bootstrap_task):
            if task is not None and task is not current_task and not task.done():
                task.cancel()

        offline_code = (
            "NODE_SUPERADMIN_OFFLINE"
            if conn.target_key == SUPERADMIN_TARGET_KEY
            else "NODE_EMPRESA_OFFLINE"
        )
        for req_id, fut in list(conn.pending.items()):
            conn.pending.pop(req_id, None)
            if not fut.done():
                fut.set_exception(
                    VaultTunnelOfflineError(
                        "La connexió WSS s'ha tancat abans de rebre resposta.",
                        code=offline_code,
                    )
                )

        if close_code is not None:
            try:
                await conn.websocket.close(code=close_code, reason=close_reason or "")
            except Exception:
                pass

    async def _publish_presence(self, conn: TunnelConnection) -> None:
        client = await _create_redis_client(socket_timeout=2.0)
        if client is None:
            return
        try:
            meta = {
                "conn_id": conn.conn_id,
                "target_key": conn.target_key,
                "role": conn.role,
                "empresa_id": conn.empresa_id,
                "agent_version": conn.agent_version,
                "connected_at": conn.connected_at.isoformat(),
                "last_seen_at": conn.last_seen_at.isoformat(),
                "pid": os.getpid(),
                "health": conn.last_health,
            }
            await client.set(
                f"{REDIS_PRESENCE_PREFIX}{conn.target_key}",
                json.dumps(meta, ensure_ascii=False),
                ex=PRESENCE_TTL_SECONDS,
            )
        except Exception as exc:
            logger.debug("Error publicant presència Redis per %s: %s", conn.target_key, exc)
        finally:
            await client.aclose()

    async def _clear_presence_if_owner(self, target_key: str, conn_id: str) -> None:
        client = await _create_redis_client(socket_timeout=2.0)
        if client is None:
            return
        try:
            key = f"{REDIS_PRESENCE_PREFIX}{target_key}"
            raw = await client.get(key)
            if raw:
                parsed = json.loads(raw)
                if isinstance(parsed, dict) and parsed.get("conn_id") == conn_id:
                    await client.delete(key)
        except Exception as exc:
            logger.debug("Error netejant presència Redis per %s: %s", target_key, exc)
        finally:
            await client.aclose()

    async def _heartbeat_loop(self, conn: TunnelConnection, *, interval: float) -> None:
        """Manté viva la connexió WSS darrere Traefik/NAT i refresca la presència a Redis."""
        try:
            while not conn.closed:
                await asyncio.sleep(interval)
                if conn.closed:
                    break
                try:
                    await self._dispatch_local(
                        conn,
                        action="ping",
                        payload={"ts": datetime.now(timezone.utc).isoformat()},
                        timeout=HEARTBEAT_TIMEOUT_SECONDS,
                    )
                    await self._publish_presence(conn)
                except Exception as exc:
                    logger.warning(
                        "Heartbeat fallit per %s (conn=%s): %s. Tancant sessió.",
                        conn.target_key,
                        conn.conn_id,
                        exc,
                    )
                    try:
                        await conn.websocket.close(code=4008, reason="Heartbeat timeout")
                    except Exception:
                        pass
                    break
        except asyncio.CancelledError:
            return

    async def _redis_rpc_loop(self, conn: TunnelConnection) -> None:
        """Escolta peticions RPC de processos externs (Celery/Bot) a Redis i les reenvia pel WSS."""
        queue_key = f"{REDIS_RPC_QUEUE_PREFIX}{conn.target_key}"
        client: Optional[aioredis.Redis] = None
        try:
            client = await _create_redis_client(socket_timeout=5.0)
            if client is None:
                return
            while not conn.closed:
                try:
                    item = await client.blpop([queue_key], timeout=2)
                except asyncio.CancelledError:
                    raise
                except Exception as exc:
                    logger.debug("Error BLPOP Redis per %s: %s", conn.target_key, exc)
                    await asyncio.sleep(1.0)
                    continue

                if not item:
                    continue
                _, raw_req = item
                req_text = raw_req.decode("utf-8") if isinstance(raw_req, bytes) else str(raw_req)
                asyncio.create_task(
                    self._handle_redis_rpc_request(conn, req_text),
                    name=f"wss-rpc-exec-{conn.target_key}",
                )
        except asyncio.CancelledError:
            return
        finally:
            if client is not None:
                try:
                    await client.aclose()
                except Exception:
                    pass

    async def _handle_redis_rpc_request(self, conn: TunnelConnection, raw_req: str) -> None:
        """Executa una petició rebuda via Redis sobre el WebSocket local i publica la resposta."""
        reply_key: Optional[str] = None
        req_id: str = ""
        try:
            envelope = json.loads(raw_req)
            if not isinstance(envelope, dict):
                return
            reply_key = str(envelope.get("reply_key") or "")
            req_id = str(envelope.get("req_id") or "")
            action = str(envelope.get("action") or "")
            payload = envelope.get("payload")
            timeout_s = float(envelope.get("timeout_s") or DEFAULT_RPC_TIMEOUT_SECONDS)

            if not reply_key or action not in ALLOWED_TUNNEL_ACTIONS:
                return

            data = await self._dispatch_local(
                conn,
                action=action,
                payload=payload if isinstance(payload, dict) else {},
                timeout=timeout_s,
            )
            reply_obj: Dict[str, Any] = {"ok": True, "req_id": req_id, "data": data}
        except VaultTunnelError as exc:
            reply_obj = {
                "ok": False,
                "req_id": req_id,
                "error_code": exc.code,
                "status_code": exc.status_code,
                "detail": exc.detail,
            }
        except Exception as exc:
            reply_obj = {
                "ok": False,
                "req_id": req_id,
                "error_code": "TUNNEL_BRIDGE_ERROR",
                "status_code": 502,
                "detail": str(exc),
            }

        if not reply_key:
            return

        client = await _create_redis_client(socket_timeout=3.0)
        if client is None:
            return
        try:
            await client.rpush(reply_key, json.dumps(reply_obj, ensure_ascii=False))
            await client.expire(reply_key, 60)
        except Exception as exc:
            logger.debug("Error escrivint resposta RPC Redis %s: %s", reply_key, exc)
        finally:
            await client.aclose()

    async def handle_incoming_message(self, conn: TunnelConnection, message: Any) -> None:
        """Processa qualsevol trama JSON rebuda de l'agent WSS del PC."""
        if not isinstance(message, dict):
            return
        conn.last_seen_at = datetime.now(timezone.utc)
        msg_type = str(message.get("type") or "").strip().lower()

        if msg_type == "ping":
            pong_payload: Dict[str, Any] = {
                "type": "pong",
                "ts": datetime.now(timezone.utc).isoformat(),
            }
            if message.get("req_id"):
                pong_payload["req_id"] = str(message["req_id"])
            async with conn.send_lock:
                await conn.websocket.send_json(pong_payload)
            return

        if msg_type == "pong":
            req_id = str(message.get("req_id") or "")
            if isinstance(message.get("health"), dict):
                conn.last_health = message["health"]
            if req_id:
                fut = conn.pending.pop(req_id, None)
                if fut is not None and not fut.done():
                    fut.set_result({"ok": True, "data": {"pong": True, "ts": message.get("ts")}})
            return

        if msg_type == "hello":
            version = message.get("agent_version")
            if isinstance(version, str) and version.strip():
                conn.agent_version = version.strip()[:64]
            if isinstance(message.get("health"), dict):
                conn.last_health = message["health"]
            await self._publish_presence(conn)
            return

        if msg_type == "response":
            req_id = str(message.get("req_id") or "")
            if not req_id:
                return
            fut = conn.pending.pop(req_id, None)
            if fut is not None and not fut.done():
                fut.set_result(message)
            return

    async def _dispatch_local(
        self,
        conn: TunnelConnection,
        *,
        action: str,
        payload: Dict[str, Any],
        timeout: float,
    ) -> Dict[str, Any]:
        """Envia una petició multiplexada al WebSocket local i espera la resposta per `req_id`."""
        if conn.closed:
            offline_code = (
                "NODE_SUPERADMIN_OFFLINE"
                if conn.target_key == SUPERADMIN_TARGET_KEY
                else "NODE_EMPRESA_OFFLINE"
            )
            raise VaultTunnelOfflineError(code=offline_code)

        req_id = str(uuid.uuid4())
        loop = asyncio.get_running_loop()
        fut: asyncio.Future[Dict[str, Any]] = loop.create_future()
        conn.pending[req_id] = fut

        frame: Dict[str, Any] = {
            "type": "ping" if action == "ping" else "request",
            "req_id": req_id,
            "action": action,
            "payload": payload,
            "timeout_s": timeout,
        }

        try:
            async with conn.send_lock:
                if conn.closed:
                    offline_code = (
                        "NODE_SUPERADMIN_OFFLINE"
                        if conn.target_key == SUPERADMIN_TARGET_KEY
                        else "NODE_EMPRESA_OFFLINE"
                    )
                    raise VaultTunnelOfflineError(code=offline_code)
                await conn.websocket.send_json(frame)
            resp = await asyncio.wait_for(fut, timeout=timeout)
        except asyncio.TimeoutError as exc:
            conn.pending.pop(req_id, None)
            raise VaultTunnelTimeoutError(
                f"Temps d'espera esgotat ({timeout:.1f}s) executant '{action}' a {conn.target_key}."
            ) from exc
        except VaultTunnelError:
            conn.pending.pop(req_id, None)
            raise
        except Exception as exc:
            conn.pending.pop(req_id, None)
            offline_code = (
                "NODE_SUPERADMIN_OFFLINE"
                if conn.target_key == SUPERADMIN_TARGET_KEY
                else "NODE_EMPRESA_OFFLINE"
            )
            raise VaultTunnelOfflineError(
                f"Error de connexió WSS amb {conn.target_key}: {exc}",
                code=offline_code,
            ) from exc

        if not bool(resp.get("ok", False)):
            err_code = str(resp.get("error_code") or "TUNNEL_REMOTE_ERROR")
            err_status = int(resp.get("status_code") or 502)
            err_detail = str(resp.get("detail") or f"Error remot executant '{action}'.")
            raise VaultTunnelRemoteError(err_detail, code=err_code, status_code=err_status)

        data = resp.get("data")
        if action == "health" and isinstance(data, dict):
            conn.last_health = data
        return data if isinstance(data, dict) else {"value": data}

    async def _dispatch_via_redis(
        self,
        target_key: str,
        *,
        action: str,
        payload: Dict[str, Any],
        timeout: float,
    ) -> Dict[str, Any]:
        """Despatxa una petició RPC cap al procés que sosté el WebSocket usant Redis 7."""
        offline_code = (
            "NODE_SUPERADMIN_OFFLINE"
            if target_key == SUPERADMIN_TARGET_KEY
            else "NODE_EMPRESA_OFFLINE"
        )
        client = await _create_redis_client(socket_timeout=timeout + 3.0)
        if client is None:
            raise VaultTunnelOfflineError(
                "El node dedicat no està connectat en aquest procés i Redis no respon.",
                code=offline_code,
            )

        req_id = str(uuid.uuid4())
        presence_key = f"{REDIS_PRESENCE_PREFIX}{target_key}"
        queue_key = f"{REDIS_RPC_QUEUE_PREFIX}{target_key}"
        reply_key = f"{REDIS_RPC_REPLY_PREFIX}{req_id}"

        try:
            present = await client.get(presence_key)
            if not present:
                raise VaultTunnelOfflineError(
                    "L'ordinador dedicat no està connectat al túnel WSS de Sevalor.",
                    code=offline_code,
                )

            envelope = {
                "req_id": req_id,
                "action": action,
                "payload": payload,
                "timeout_s": timeout,
                "reply_key": reply_key,
            }
            await client.rpush(queue_key, json.dumps(envelope, ensure_ascii=False))
            await client.expire(queue_key, max(30, int(math.ceil(timeout)) + 15))

            res = await client.blpop([reply_key], timeout=max(1, int(math.ceil(timeout))))
            await client.delete(reply_key)
            if not res:
                raise VaultTunnelTimeoutError(
                    f"Temps d'espera esgotat ({timeout:.1f}s) al pont Redis RPC per '{action}' ({target_key})."
                )
            _, raw_reply = res
            reply = json.loads(raw_reply)
            if not isinstance(reply, dict):
                raise VaultTunnelRemoteError("Resposta RPC invàlida del pont Redis.")

            if not bool(reply.get("ok", False)):
                err_code = str(reply.get("error_code") or "TUNNEL_REMOTE_ERROR")
                err_status = int(reply.get("status_code") or 502)
                err_detail = str(reply.get("detail") or "Error executant acció remota via túnel WSS.")
                if err_code in ("NODE_EMPRESA_OFFLINE", "NODE_SUPERADMIN_OFFLINE"):
                    raise VaultTunnelOfflineError(err_detail, code=err_code)
                if err_code == "TUNNEL_TIMEOUT":
                    raise VaultTunnelTimeoutError(err_detail)
                raise VaultTunnelRemoteError(err_detail, code=err_code, status_code=err_status)

            data = reply.get("data")
            return data if isinstance(data, dict) else {"value": data}
        finally:
            await client.aclose()

    async def call(
        self,
        target_key: str,
        action: str,
        payload: Optional[Dict[str, Any]] = None,
        *,
        timeout: float = DEFAULT_RPC_TIMEOUT_SECONDS,
        _force_redis: bool = False,
    ) -> Dict[str, Any]:
        """Executa una acció RPC autenticada al node destí (via memòria local o pont Redis)."""
        parse_target_key(target_key)
        if action not in ALLOWED_TUNNEL_ACTIONS:
            raise ValueError(f"Acció de túnel WSS no autoritzada: {action!r}")

        body = payload or {}
        raw_b64 = body.get("content_b64")
        if isinstance(raw_b64, str) and len(raw_b64) > MAX_B64_CHARS:
            raise VaultTunnelError(
                "El fitxer supera el límit màxim de 50 MB autoritzat pel túnel WSS.",
                code="PAYLOAD_TOO_LARGE",
                status_code=413,
            )

        if not _force_redis:
            conn = self._connections.get(target_key)
            if conn is not None and not conn.closed:
                return await self._dispatch_local(
                    conn,
                    action=action,
                    payload=body,
                    timeout=timeout,
                )

        return await self._dispatch_via_redis(
            target_key,
            action=action,
            payload=body,
            timeout=timeout,
        )

    async def is_online(self, target_key: str) -> bool:
        """Comprova si el túnel WSS destí està en línia (en aquest procés o en un altre via Redis)."""
        conn = self._connections.get(target_key)
        if conn is not None and not conn.closed:
            return True
        client = await _create_redis_client(socket_timeout=1.5)
        if client is None:
            return False
        try:
            return bool(await client.exists(f"{REDIS_PRESENCE_PREFIX}{target_key}"))
        except Exception:
            return False
        finally:
            await client.aclose()

    async def get_status(self, target_key: str) -> Dict[str, Any]:
        """Retorna telemetria en viu de l'estat del túnel WSS sense exposar mai credencials."""
        conn = self._connections.get(target_key)
        if conn is not None and not conn.closed:
            return {
                "online": True,
                "target_key": target_key,
                "role": conn.role,
                "conn_id": conn.conn_id,
                "connected_at": conn.connected_at.isoformat(),
                "last_seen_at": conn.last_seen_at.isoformat(),
                "agent_version": conn.agent_version,
                "health": conn.last_health,
                "transport": "WSS_LOCAL",
            }

        client = await _create_redis_client(socket_timeout=1.5)
        if client is not None:
            try:
                raw = await client.get(f"{REDIS_PRESENCE_PREFIX}{target_key}")
                if raw:
                    parsed = json.loads(raw)
                    if isinstance(parsed, dict):
                        return {
                            "online": True,
                            "target_key": target_key,
                            "role": parsed.get("role"),
                            "conn_id": parsed.get("conn_id"),
                            "connected_at": parsed.get("connected_at"),
                            "last_seen_at": parsed.get("last_seen_at"),
                            "agent_version": parsed.get("agent_version"),
                            "health": parsed.get("health") or {},
                            "transport": "WSS_REDIS_BRIDGE",
                        }
            except Exception:
                pass
            finally:
                await client.aclose()

        return {
            "online": False,
            "target_key": target_key,
            "transport": "OFFLINE",
            "health": {},
        }

    def list_local_targets(self) -> List[str]:
        """Llista les claus de túnel connectades localment en aquest procés."""
        return sorted(k for k, c in self._connections.items() if not c.closed)

    # ── Helpers tipats d'alt nivell per a Disc Dur i Copilot IA Local ─────────

    async def health(self, target_key: str, *, timeout: float = 8.0) -> Dict[str, Any]:
        t0 = time.perf_counter()
        data = await self.call(target_key, "health", {}, timeout=timeout)
        return {**data, "latencia_ms": int((time.perf_counter() - t0) * 1000)}

    async def init_folders(self, target_key: str, *, timeout: float = 15.0) -> Dict[str, Any]:
        return await self.call(target_key, "init_folders", {}, timeout=timeout)

    async def json_put(
        self,
        target_key: str,
        subcarpeta: str,
        item_id: str,
        content: Dict[str, Any],
        *,
        timeout: float = 10.0,
    ) -> Dict[str, Any]:
        return await self.call(
            target_key,
            "json_put",
            {"subcarpeta": subcarpeta, "item_id": item_id, "content": content},
            timeout=timeout,
        )

    async def json_get_list(
        self,
        target_key: str,
        subcarpeta: str,
        *,
        timeout: float = 12.0,
    ) -> List[Dict[str, Any]]:
        res = await self.call(
            target_key,
            "json_get_list",
            {"subcarpeta": subcarpeta},
            timeout=timeout,
        )
        items = res.get("items")
        return items if isinstance(items, list) else []

    async def json_delete(
        self,
        target_key: str,
        subcarpeta: str,
        item_id: str,
        *,
        timeout: float = 10.0,
    ) -> bool:
        res = await self.call(
            target_key,
            "json_delete",
            {"subcarpeta": subcarpeta, "item_id": item_id},
            timeout=timeout,
        )
        return bool(res.get("deleted", False))

    async def file_put(
        self,
        target_key: str,
        subcarpeta: str,
        filename: str,
        content_bytes: bytes,
        content_type: str = "application/octet-stream",
        *,
        timeout: float = 30.0,
    ) -> Dict[str, Any]:
        if len(content_bytes) > MAX_BINARY_PAYLOAD_BYTES:
            raise VaultTunnelError(
                "El fitxer supera el límit màxim de 50 MB.",
                code="PAYLOAD_TOO_LARGE",
                status_code=413,
            )
        sha256_hex = hashlib.sha256(content_bytes).hexdigest()
        b64 = base64.b64encode(content_bytes).decode("ascii")
        return await self.call(
            target_key,
            "file_put",
            {
                "subcarpeta": subcarpeta,
                "filename": filename,
                "content_type": content_type,
                "content_b64": b64,
                "sha256": sha256_hex,
                "size_bytes": len(content_bytes),
            },
            timeout=timeout,
        )

    async def file_get(
        self,
        target_key: str,
        rel_path: str,
        *,
        timeout: float = 30.0,
    ) -> Tuple[bytes, str]:
        res = await self.call(
            target_key,
            "file_get",
            {"rel_path": rel_path},
            timeout=timeout,
        )
        b64 = res.get("content_b64")
        if not isinstance(b64, str):
            raise VaultTunnelRemoteError("L'agent no ha retornat contingut binari vàlid.", status_code=502)
        raw = base64.b64decode(b64.encode("ascii"))
        expected_sha = res.get("sha256")
        if isinstance(expected_sha, str) and expected_sha:
            actual_sha = hashlib.sha256(raw).hexdigest()
            if actual_sha != expected_sha:
                raise VaultTunnelRemoteError(
                    "Integritat SHA-256 corrupta en la descàrrega binària pel túnel WSS.",
                    code="CHECKSUM_MISMATCH",
                    status_code=502,
                )
        filename = str(res.get("filename") or os.path.basename(rel_path))
        return raw, filename

    async def file_rename(
        self,
        target_key: str,
        old_rel_path: str,
        new_subcarpeta: str,
        new_filename: str,
        *,
        timeout: float = 15.0,
    ) -> Dict[str, Any]:
        return await self.call(
            target_key,
            "file_rename",
            {
                "old_rel_path": old_rel_path,
                "new_subcarpeta": new_subcarpeta,
                "new_filename": new_filename,
            },
            timeout=timeout,
        )

    async def file_delete(
        self,
        target_key: str,
        rel_path: str,
        *,
        timeout: float = 10.0,
    ) -> bool:
        res = await self.call(
            target_key,
            "file_delete",
            {"rel_path": rel_path},
            timeout=timeout,
        )
        return bool(res.get("deleted", False))

    async def call_llm_models(self, target_key: str, *, timeout: float = 10.0) -> Dict[str, Any]:
        return await self.call(target_key, "llm_models", {}, timeout=timeout)

    async def call_llm_chat(
        self,
        target_key: str,
        body: Dict[str, Any],
        *,
        timeout: float = LLM_RPC_TIMEOUT_SECONDS,
        priority: Optional[str] = None,
    ) -> Dict[str, Any]:
        payload = dict(body)
        if priority:
            payload["_sevalor_priority"] = str(priority).strip().upper()
        return await self.call(target_key, "llm_chat", payload, timeout=timeout)


vault_tunnel_broker = VaultTunnelBroker()
