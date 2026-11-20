"""Endpoint WebSocket del Túnel Invers Natiu Sobirà (`WS /api/v1/vault-tunnel/connect`).

ADR-001 (Fase 1):
- Únic transport autoritzat entre Hetzner Cloud (passarel·la cega Zero-Storage) i els PCs
  dedicats d'empresa (`EMPRESA`) i del propietari SaaS (`SUPERADMIN`).
- Handshake Zero-Trust amb comparació en temps constant (`hmac.compare_digest`), rebuig
  immediat amb codis `4401`/`4403` + registre a `superadmin_telemetry.alertes_seguretat`.
- Auto-inicialització de les 38 carpetes + fitxes inicials (`empresa.json`, `boss.json`,
  `system_prompt.txt`) i drenatge automàtic de la cua xifrada `SVENC1:` en connectar.
"""

from __future__ import annotations

import asyncio
import hmac
import json
import logging
import os
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.db import AsyncSessionLocal, get_db
from app.core.network_utils import build_wss_tunnel_uri, is_wss_tunnel_uri
from app.core.redis import is_tenant_blacklisted
from app.models.models import AlertaSeguretat, Empresa, Usuari
from app.services.sovereign_storage import MAPA_CARPETES_CLIENT, SovereignStorageGateway
from app.services.vault_tunnel import (
    HEARTBEAT_INTERVAL_SECONDS,
    MAX_B64_CHARS,
    SUPERADMIN_TARGET_KEY,
    TunnelConnection,
    empresa_target_key,
    vault_tunnel_broker,
)

logger = logging.getLogger("sevalor.vault_tunnel.ws")

router = APIRouter(prefix="/vault-tunnel", tags=["Túnel Sobirà WSS"])

WS_CLOSE_UNAUTHORIZED = 4401
WS_CLOSE_FORBIDDEN = 4403
MAX_WS_TEXT_FRAME_CHARS = MAX_B64_CHARS + 131072
BLOCKED_TENANT_STATES = frozenset({"ELIMINAT", "SUSPES_PAGAMENT", "BAIXA"})


def _get_client_ip(websocket: WebSocket) -> str:
    forwarded = websocket.headers.get("x-forwarded-for", "").strip()
    if forwarded:
        return forwarded.split(",")[0].strip()[:64]
    if websocket.client and websocket.client.host:
        return str(websocket.client.host)[:64]
    return "unknown"


async def _registrar_alerta_auth_fallida(
    websocket: WebSocket,
    *,
    role: str,
    empresa_id: Optional[uuid.UUID],
    motiu_intern: str,
    remote_ip: str,
) -> None:
    """Enregistra un intent fallit d'autenticació WSS a `superadmin_telemetry.alertes_seguretat`."""
    logger.warning(
        "Handshake WSS rebutjat (role=%s, empresa_id=%s, ip=%s, motiu=%s)",
        role or "EMPTY",
        str(empresa_id) if empresa_id else "-",
        remote_ip,
        motiu_intern,
    )
    try:
        async with AsyncSessionLocal() as session:
            target_emp_id = empresa_id
            if target_emp_id is not None:
                exists = (
                    await session.execute(select(Empresa.id).where(Empresa.id == target_emp_id))
                ).scalars().first()
                if exists is None:
                    target_emp_id = None
            alerta = AlertaSeguretat(
                tipus="WSS_TUNNEL_AUTH_FAILED",
                gravetat="VERMELLA",
                origen="vault_tunnel",
                detall=f"Handshake WSS rebutjat (role={role or 'EMPTY'}, ip={remote_ip}): {motiu_intern}",
                empresa_id=target_emp_id,
            )
            session.add(alerta)
            await session.commit()
    except Exception as exc:
        logger.debug("No s'ha pogut persistir AlertaSeguretat de handshake WSS: %s", exc)


async def _rebutjar_handshake(
    websocket: WebSocket,
    *,
    code: int,
    role: str,
    empresa_id: Optional[uuid.UUID],
    motiu_intern: str,
    remote_ip: str,
) -> None:
    """Tanca el WebSocket amb 4401/4403 sense revelar detalls interns a l'atacant."""
    await _registrar_alerta_auth_fallida(
        websocket,
        role=role,
        empresa_id=empresa_id,
        motiu_intern=motiu_intern,
        remote_ip=remote_ip,
    )
    reason = "Forbidden" if code == WS_CLOSE_FORBIDDEN else "Unauthorized"
    try:
        await websocket.accept()
        await websocket.close(code=code, reason=reason)
    except Exception:
        pass


async def _autenticar_handshake_wss(
    websocket: WebSocket,
    *,
    remote_ip: str,
) -> Optional[Tuple[str, str, Optional[str], Optional[str]]]:
    """
    Valida capçaleres Zero-Trust del handshake WSS.
    Retorna `(target_key, role, empresa_id_str, agent_version)` o `None` si ja ha rebutjat el WS.
    """
    raw_role = (websocket.headers.get("x-vault-role") or "").strip().upper()
    raw_empresa_id = (websocket.headers.get("x-empresa-id") or "").strip()
    raw_token = (websocket.headers.get("x-vault-token") or "").strip()
    agent_version = (websocket.headers.get("x-agent-version") or "").strip()[:64] or None

    if raw_role not in ("EMPRESA", "SUPERADMIN"):
        await _rebutjar_handshake(
            websocket,
            code=WS_CLOSE_UNAUTHORIZED,
            role=raw_role,
            empresa_id=None,
            motiu_intern="X-Vault-Role invàlid o absent",
            remote_ip=remote_ip,
        )
        return None

    if not raw_token:
        await _rebutjar_handshake(
            websocket,
            code=WS_CLOSE_UNAUTHORIZED,
            role=raw_role,
            empresa_id=None,
            motiu_intern="X-Vault-Token absent",
            remote_ip=remote_ip,
        )
        return None

    if raw_role == "SUPERADMIN":
        if raw_empresa_id:
            await _rebutjar_handshake(
                websocket,
                code=WS_CLOSE_FORBIDDEN,
                role=raw_role,
                empresa_id=None,
                motiu_intern="X-Empresa-ID prohibit per al rol SUPERADMIN",
                remote_ip=remote_ip,
            )
            return None

        expected_sa = (
            os.getenv("SUPERADMIN_VAULT_SECRET", "").strip()
            or str(getattr(settings, "SUPERADMIN_VAULT_SECRET", "") or "").strip()
        )
        if not expected_sa:
            await _rebutjar_handshake(
                websocket,
                code=WS_CLOSE_FORBIDDEN,
                role=raw_role,
                empresa_id=None,
                motiu_intern="SUPERADMIN_VAULT_SECRET no configurat al servidor",
                remote_ip=remote_ip,
            )
            return None

        if not hmac.compare_digest(raw_token.encode("utf-8"), expected_sa.encode("utf-8")):
            await _rebutjar_handshake(
                websocket,
                code=WS_CLOSE_UNAUTHORIZED,
                role=raw_role,
                empresa_id=None,
                motiu_intern="Token SUPERADMIN invàlid",
                remote_ip=remote_ip,
            )
            return None

        return (SUPERADMIN_TARGET_KEY, "SUPERADMIN", None, agent_version)

    # Perfil EMPRESA
    if not raw_empresa_id:
        await _rebutjar_handshake(
            websocket,
            code=WS_CLOSE_UNAUTHORIZED,
            role=raw_role,
            empresa_id=None,
            motiu_intern="X-Empresa-ID absent per al rol EMPRESA",
            remote_ip=remote_ip,
        )
        return None

    try:
        emp_uuid = uuid.UUID(raw_empresa_id)
    except ValueError:
        await _rebutjar_handshake(
            websocket,
            code=WS_CLOSE_UNAUTHORIZED,
            role=raw_role,
            empresa_id=None,
            motiu_intern="X-Empresa-ID no és un UUID vàlid",
            remote_ip=remote_ip,
        )
        return None

    emp_str = str(emp_uuid)

    # Sessió curta de PostgreSQL només per validar el handshake (mai retinguda durant el WS)
    empresa: Optional[Empresa] = None
    async with AsyncSessionLocal() as session:
        res = await session.execute(select(Empresa).where(Empresa.id == emp_uuid))
        empresa = res.scalars().first()

    # En tests amb SAVEPOINT (FastAPI dependency_overrides[get_db]), si l'empresa encara no
    # s'ha comitjat fora de la transacció de test, consultem la sessió del test sense mutar el seu context RLS.
    if empresa is None and hasattr(websocket.app, "dependency_overrides"):
        db_override = websocket.app.dependency_overrides.get(get_db)
        if db_override is not None:
            override_session: Optional[AsyncSession] = None
            for cell in getattr(db_override, "__closure__", None) or ():
                if isinstance(cell.cell_contents, AsyncSession):
                    override_session = cell.cell_contents
                    break
            if override_session is not None:
                res_ov = await override_session.execute(
                    select(Empresa).where(Empresa.id == emp_uuid)
                )
                empresa = res_ov.scalars().first()
            else:
                gen = db_override()
                try:
                    ov_sess = await anext(gen)
                    res_ov = await ov_sess.execute(
                        select(Empresa).where(Empresa.id == emp_uuid)
                    )
                    empresa = res_ov.scalars().first()
                finally:
                    try:
                        await gen.aclose()
                    except Exception:
                        pass

    if empresa is None:
        await _rebutjar_handshake(
            websocket,
            code=WS_CLOSE_UNAUTHORIZED,
            role=raw_role,
            empresa_id=emp_uuid,
            motiu_intern="Empresa no trobada a PostgreSQL",
            remote_ip=remote_ip,
        )
        return None

    estat = str(getattr(empresa, "estat_pagament", "") or "").upper()
    if estat in BLOCKED_TENANT_STATES or await is_tenant_blacklisted(emp_str):
        await _rebutjar_handshake(
            websocket,
            code=WS_CLOSE_FORBIDDEN,
            role=raw_role,
            empresa_id=emp_uuid,
            motiu_intern=f"Empresa bloquejada o suspesa (estat={estat or 'BLACKLISTED'})",
            remote_ip=remote_ip,
        )
        return None

    # Token estricte per empresa (mai fallback a secret global!)
    expected_emp_tok: Optional[str] = None
    vault_tok = getattr(empresa, "vault_token", None)
    if isinstance(vault_tok, str) and vault_tok.strip():
        expected_emp_tok = vault_tok.strip()
    else:
        legacy_tok = getattr(empresa, "telegram_webhook_secret", None)
        if isinstance(legacy_tok, str) and legacy_tok.strip().startswith("svlt_"):
            expected_emp_tok = legacy_tok.strip()

    if not expected_emp_tok or not hmac.compare_digest(
        raw_token.encode("utf-8"), expected_emp_tok.encode("utf-8")
    ):
        await _rebutjar_handshake(
            websocket,
            code=WS_CLOSE_UNAUTHORIZED,
            role=raw_role,
            empresa_id=emp_uuid,
            motiu_intern="vault_token d'empresa invàlid o no configurat",
            remote_ip=remote_ip,
        )
        return None

    return (empresa_target_key(emp_uuid), "EMPRESA", emp_str, agent_version)


async def _post_connect_empresa_bootstrap(empresa_id_str: str, conn: TunnelConnection) -> None:
    """
    Auto-inicialització sobirana en connectar-se el PC d'una empresa:
    1. Crea físicament les 38 carpetes + mirall Disc B via `init_folders`.
    2. Actualitza `disc_dur_url` i `node_ia_url` a `wss-tunnel://<id>` (i `node_ia_actiu=True`
       si `feature_copilot_ia=True` en primera connexió, sense sobreescriure desactivació explícita).
    3. Assegura fitxes inicials (`empresa.json`, `boss.json`, `system_prompt.txt`) si manquen.
    4. Drena automàticament la cua de trànsit xifrada `SVENC1:` i purga Hetzner.
    """
    emp_uuid = uuid.UUID(empresa_id_str)
    target_key = conn.target_key
    try:
        # 1. Garantir les 38 carpetes físiques al disc del client
        await vault_tunnel_broker.init_folders(target_key, timeout=15.0)
        if conn.closed:
            return

        # 2. Actualitzar metadades de túnel a PostgreSQL i llegir dades inicials (sessió curta)
        empresa_snapshot: Optional[Dict[str, Any]] = None
        boss_snapshot: Optional[Dict[str, Any]] = None
        prompt_text: Optional[str] = None
        wss_uri = build_wss_tunnel_uri(emp_uuid)

        async with AsyncSessionLocal() as session:
            res = await session.execute(select(Empresa).where(Empresa.id == emp_uuid))
            emp = res.scalars().first()
            if emp is not None:
                already_on_wss = is_wss_tunnel_uri(getattr(emp, "node_ia_url", None))
                changed = False
                if getattr(emp, "disc_dur_url", None) != wss_uri:
                    emp.disc_dur_url = wss_uri
                    changed = True
                if getattr(emp, "node_ia_url", None) != wss_uri:
                    emp.node_ia_url = wss_uri
                    changed = True
                if (
                    bool(getattr(emp, "feature_copilot_ia", False))
                    and not bool(getattr(emp, "node_ia_actiu", False))
                    and not already_on_wss
                ):
                    emp.node_ia_actiu = True
                    changed = True
                if changed:
                    emp.updated_at = datetime.now(timezone.utc)
                    await session.commit()

                prompt_text = getattr(emp, "agent_prompt_system", None)
                empresa_snapshot = {
                    "id": empresa_id_str,
                    "nom": emp.nom,
                    "nif": emp.nif,
                    "adreca": emp.adreca,
                    "subdomini": emp.subdomini,
                    "domini_custom": emp.domini_custom,
                    "vertical": emp.vertical,
                    "pla_subscripcio": emp.pla_subscripcio,
                    "primari_hsl": emp.primari_hsl,
                    "secundari_hsl": emp.secundari_hsl,
                    "accent_hsl": emp.accent_hsl,
                    "disc_dur_url": wss_uri,
                    "node_ia_url": wss_uri,
                    "node_ia_actiu": bool(emp.node_ia_actiu),
                    "feature_copilot_ia": bool(emp.feature_copilot_ia),
                }

                res_boss = await session.execute(
                    select(Usuari)
                    .where(Usuari.empresa_id == emp_uuid, Usuari.rol == "BOSS")
                    .limit(1)
                )
                boss = res_boss.scalars().first()
                if boss is not None:
                    boss_snapshot = {
                        "id": str(boss.id),
                        "nom": boss.nom,
                        "cognoms": boss.cognoms,
                        "nif": boss.nif,
                        "email": boss.email,
                        "telefon": boss.telefon,
                        "rol": boss.rol,
                    }

        if conn.closed:
            return

        # 3. Auto-inicialitzar fitxes inicials al disc si encara no existeixen
        if empresa_snapshot is not None:
            sub_cfg = MAPA_CARPETES_CLIENT["configuracio"]
            existents = await vault_tunnel_broker.json_get_list(target_key, sub_cfg, timeout=10.0)
            existing_ids = {
                str(item.get("_sovereign_meta", {}).get("item_id") or "")
                for item in existents
                if isinstance(item, dict)
            }
            if "empresa" not in existing_ids:
                hmac_emp = SovereignStorageGateway._sign_meta(
                    emp_uuid, "configuracio", sub_cfg, "empresa"
                )
                await vault_tunnel_broker.json_put(
                    target_key,
                    subcarpeta=sub_cfg,
                    item_id="empresa",
                    content={
                        **empresa_snapshot,
                        "_sovereign_meta": {
                            "empresa_id": empresa_id_str,
                            "categoria": "configuracio",
                            "subcarpeta": sub_cfg,
                            "item_id": "empresa",
                            "hmac_tenant": hmac_emp,
                            "synced_at": datetime.now(timezone.utc).isoformat(),
                        },
                    },
                    timeout=10.0,
                )

            if boss_snapshot is not None and "boss" not in existing_ids:
                hmac_boss = SovereignStorageGateway._sign_meta(
                    emp_uuid, "configuracio", sub_cfg, "boss"
                )
                await vault_tunnel_broker.json_put(
                    target_key,
                    subcarpeta=sub_cfg,
                    item_id="boss",
                    content={
                        **boss_snapshot,
                        "_sovereign_meta": {
                            "empresa_id": empresa_id_str,
                            "categoria": "configuracio",
                            "subcarpeta": sub_cfg,
                            "item_id": "boss",
                            "hmac_tenant": hmac_boss,
                            "synced_at": datetime.now(timezone.utc).isoformat(),
                        },
                    },
                    timeout=10.0,
                )

            if isinstance(prompt_text, str) and prompt_text.strip():
                sub_prompt = MAPA_CARPETES_CLIENT["copilot_prompt"]
                await vault_tunnel_broker.file_put(
                    target_key,
                    subcarpeta=sub_prompt,
                    filename="system_prompt.txt",
                    content_bytes=prompt_text.encode("utf-8"),
                    content_type="text/plain; charset=utf-8",
                    timeout=10.0,
                )

        # 4. Drenatge automàtic de la cua xifrada SVENC1: pendent
        stats = await SovereignStorageGateway.drenar_cua_transit_empresa(None, emp_uuid)
        if stats["enviats"] > 0 or stats["pendents"] > 0:
            logger.info(
                "Auto-drenatge WSS completat per empresa=%s: enviats=%d, pendents=%d",
                empresa_id_str,
                stats["enviats"],
                stats["pendents"],
            )
    except asyncio.CancelledError:
        return
    except Exception as exc:
        logger.warning("Bootstrap post-connexió WSS per empresa=%s amb avís: %s", empresa_id_str, exc)


async def _post_connect_superadmin_bootstrap(conn: TunnelConnection) -> None:
    """Assegura automàticament les 20 carpetes oficials del Disc Dur de Superadmin en connectar."""
    try:
        await vault_tunnel_broker.init_folders(conn.target_key, timeout=15.0)
    except asyncio.CancelledError:
        return
    except Exception as exc:
        logger.warning("Bootstrap post-connexió WSS Superadmin amb avís: %s", exc)


@router.websocket("/connect")
async def connect_vault_tunnel(websocket: WebSocket) -> None:
    """Endpoint WebSocket persistent del Túnel Invers Natiu Sobirà (WSS port 443)."""
    remote_ip = _get_client_ip(websocket)
    auth_result = await _autenticar_handshake_wss(websocket, remote_ip=remote_ip)
    if auth_result is None:
        return

    target_key, role, empresa_id_str, agent_version = auth_result
    await websocket.accept()

    conn = await vault_tunnel_broker.register(
        target_key=target_key,
        role=role,
        websocket=websocket,
        empresa_id=empresa_id_str,
        agent_version=agent_version,
        remote_ip=remote_ip,
    )

    try:
        async with conn.send_lock:
            await websocket.send_json(
                {
                    "type": "welcome",
                    "target_key": target_key,
                    "role": role,
                    "conn_id": conn.conn_id,
                    "heartbeat_interval_s": HEARTBEAT_INTERVAL_SECONDS,
                    "server_time": datetime.now(timezone.utc).isoformat(),
                }
            )

        if role == "EMPRESA" and empresa_id_str is not None:
            conn.bootstrap_task = asyncio.create_task(
                _post_connect_empresa_bootstrap(empresa_id_str, conn),
                name=f"wss-bootstrap-{empresa_id_str}",
            )
        elif role == "SUPERADMIN":
            conn.bootstrap_task = asyncio.create_task(
                _post_connect_superadmin_bootstrap(conn),
                name="wss-bootstrap-superadmin",
            )

        while True:
            raw_text = await websocket.receive_text()
            if len(raw_text) > MAX_WS_TEXT_FRAME_CHARS:
                logger.warning(
                    "Trama WSS massa gran (%d chars) rebutjada per %s.",
                    len(raw_text),
                    target_key,
                )
                await websocket.close(code=1009, reason="Message too big")
                break
            try:
                msg = json.loads(raw_text)
            except json.JSONDecodeError:
                continue
            await vault_tunnel_broker.handle_incoming_message(conn, msg)
    except WebSocketDisconnect:
        pass
    except Exception as exc:
        logger.debug("Sessió WSS finalitzada per %s (%s): %s", target_key, conn.conn_id, exc)
    finally:
        await vault_tunnel_broker.unregister(target_key, conn.conn_id)
