#!/usr/bin/env python3
"""
Agent Sobirà WSS de Sevalor Suite (Disc Dur Dedicat + Copilot IA Local — ADR-001).

Daemon lleuger de connexió SORTINT per WebSocket TLS (port 443) cap al backend de
Sevalor a Hetzner (`wss://<SEVALOR_SERVER_URL>/api/v1/vault-tunnel/connect`).

Garanties arquitectòniques (ADR-001 — Fase 2):
1. ZERO ports TCP entrants oberts (ni 9001, ni 9002, ni Uvicorn, ni Cloudflare Tunnel).
2. Perfil `EMPRESA`: gestiona les 38 carpetes oficials sobre `SEVALOR_VAULT_PATH_A`,
   backup diari alternat al mirall `SEVALOR_VAULT_PATH_B` amb manifest SHA-256 i
   enrutament exclusiu de `llm_models`/`llm_chat` cap a `SEVALOR_LOCAL_LLM_URL`.
3. Perfil `SUPERADMIN`: gestiona les 20 carpetes oficials del Disc Dur de Superadmin
   sobre `SEVALOR_VAULT_PATH_A` + mirall `SEVALOR_VAULT_PATH_B`.
4. Validació estricta contra Path Traversal (`is_relative_to`, profunditat mínima >= 1,
   escriptura atòmica, límit 50 MB i integritat SHA-256) i reconnexió exponencial
   automàtica indefinida (`1s -> 2s -> 4s -> ... -> 30s` + jitter).
"""

from __future__ import annotations

import argparse
import asyncio
import base64
import hashlib
import heapq
import json
import logging
import math
import os
import random
import re
import shutil
import signal
import sys
import uuid
import zipfile
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, AsyncIterator, Dict, List, Optional, Tuple
from urllib.parse import urlparse

import httpx
import websockets

AGENT_VERSION = "sevalor-wss-agent/3.2.0"
DEFAULT_SERVER_URL = "https://sevalor-sevalor-backend.80opze.easypanel.host"
DEFAULT_LOCAL_LLM_URL = "http://127.0.0.1:1234"
DEFAULT_LOCAL_LLM_CONCURRENCY = 1
LLM_PRIORITY_RANKS: Dict[str, int] = {"HIGH": 0, "NORMAL": 1, "LOW": 2}
VALID_VAULT_ROLES = ("EMPRESA", "SUPERADMIN")

MAX_UPLOAD_BYTES = 50 * 1024 * 1024  # 50 MB màxim per fitxer (AGENTS.md §3.4)
MAX_WS_FRAME_BYTES = int(math.ceil(MAX_UPLOAD_BYTES * 4 / 3)) + 262144

BACKOFF_INITIAL_SECONDS = 1.0
BACKOFF_MAX_SECONDS = 30.0
AUTH_FAIL_BACKOFF_SECONDS = 15.0

logger = logging.getLogger("sevalor_vault_agent")

# 38 Carpetes Oficials idèntiques a MAPA_CARPETES_CLIENT (sovereign_storage.py)
CARPETES_OFICIALS: List[str] = [
    "01_clients/fitxes",
    "01_clients/finques_i_instal_lacions",
    "01_clients/contractes_manteniment",
    "02_proveidors/fitxes",
    "03_magatzem/articles_i_estoc",
    "03_magatzem/eines_custodia",
    "03_magatzem/albarans_compra",
    "03_magatzem/picking_fulles",
    "04_factures/emeses_verifactu_pdf",
    "04_factures/emeses_verifactu_xml",
    "04_factures/prefactures_i_pressupostos",
    "04_factures/factures_proveidors",
    "05_planols/arxius_base",
    "05_planols/capes_vectorials",
    "05_planols/informes_exportats",
    "06_ordres_treball/actives_buffer",
    "06_ordres_treball/historic_tancades",
    "06_ordres_treball/informes_post_obra",
    "07_incidencies/fotos_camp",
    "07_incidencies/audios_veu",
    "07_incidencies/registres",
    "08_flota_i_operaris/vehicles",
    "08_flota_i_operaris/vehicles/alertes_flota",
    "08_flota_i_operaris/operaris",
    "08_flota_i_operaris/operaris/documents_rrhh",
    "08_flota_i_operaris/operaris/alertes_rrhh",
    "08_flota_i_operaris/tiquets_despesa",
    "08_flota_i_operaris/registres_jornada",
    "09_copilot_ia/prompt_sistema",
    "09_copilot_ia/autoaprenentatge/memorandums_tecnics",
    "09_copilot_ia/autoaprenentatge/historic_preus_i_mermes",
    "09_copilot_ia/autoaprenentatge/converses_i_feedback",
    "09_copilot_ia/index_vectorial_rag",
    "10_protocols_i_manuals/procediments_interns",
    "10_protocols_i_manuals/manuals_fabricants",
    "10_protocols_i_manuals/normativa_i_prl",
    "11_configuracio_i_backups/identitat_camaleo",
    "11_configuracio_i_backups/backups_locals",
]

# 20 Carpetes Oficials del Disc Dur Dedicat del Superadmin (idèntiques a MAPA_CARPETES_SUPERADMIN)
CARPETES_SUPERADMIN: List[str] = [
    "01_tenants_b2b/fitxes_empreses",
    "01_tenants_b2b/llicencies_i_contractes",
    "02_facturacio_saas/factures_b2b_json",
    "02_facturacio_saas/factures_b2b_pdf",
    "02_facturacio_saas/factures_b2b_xml",
    "03_crm_comercial/leads",
    "03_crm_comercial/oportunitats",
    "03_crm_comercial/activitats",
    "04_rascador_prospeccio/tasques",
    "04_rascador_prospeccio/candidats",
    "04_rascador_prospeccio/criteris_feedback",
    "04_rascador_prospeccio/exclusions_rgpd",
    "05_correu_i_suport/missatges",
    "05_correu_i_suport/tiquets_suport",
    "06_telemetria_i_seguretat/auditoria",
    "06_telemetria_i_seguretat/alertes_seguretat",
    "06_telemetria_i_seguretat/certificats_baixa",
    "07_copilot_superadmin/prompt_sistema",
    "07_copilot_superadmin/memoria_ia",
    "08_backups_superadmin/backups_locals",
]


class AgentActionError(Exception):
    """Error controlat en executar una acció RPC local al disc o motor IA."""

    def __init__(
        self,
        detail: str,
        *,
        code: str = "AGENT_ERROR",
        status_code: int = 400,
    ) -> None:
        super().__init__(detail)
        self.detail = detail
        self.code = code
        self.status_code = status_code


@dataclass(frozen=True)
class AgentConfig:
    """Configuració immutable i validada de l'agent sobirà WSS."""

    server_url: str
    role: str
    vault_token: str
    disk_a: Path
    disk_b: Path
    empresa_id: Optional[str] = None
    local_llm_url: str = DEFAULT_LOCAL_LLM_URL
    local_llm_concurrency: int = DEFAULT_LOCAL_LLM_CONCURRENCY
    agent_version: str = AGENT_VERSION

    def __post_init__(self) -> None:
        role_norm = self.role.strip().upper()
        if role_norm not in VALID_VAULT_ROLES:
            raise ValueError(
                f"SEVALOR_VAULT_ROLE invàlid: {self.role!r}. Valors permesos: {VALID_VAULT_ROLES}."
            )
        object.__setattr__(self, "role", role_norm)

        if not self.vault_token or not self.vault_token.strip():
            raise ValueError("SEVALOR_VAULT_SECRET és obligatori i no pot ser buit.")

        if role_norm == "EMPRESA":
            if not self.empresa_id or not self.empresa_id.strip():
                raise ValueError("SEVALOR_EMPRESA_ID (UUID) és obligatori per al rol EMPRESA.")
            canonical = str(uuid.UUID(self.empresa_id.strip()))
            object.__setattr__(self, "empresa_id", canonical)
        else:
            if self.empresa_id and self.empresa_id.strip():
                raise ValueError("SEVALOR_EMPRESA_ID no pot especificar-se per al rol SUPERADMIN.")
            object.__setattr__(self, "empresa_id", None)

        parsed_llm = urlparse(self.local_llm_url.strip())
        if parsed_llm.scheme not in ("http", "https") or not parsed_llm.netloc:
            raise ValueError(f"SEVALOR_LOCAL_LLM_URL invàlida: {self.local_llm_url!r}.")
        object.__setattr__(self, "local_llm_url", self.local_llm_url.strip().rstrip("/"))

        try:
            conc = int(self.local_llm_concurrency)
        except (TypeError, ValueError):
            conc = DEFAULT_LOCAL_LLM_CONCURRENCY
        object.__setattr__(self, "local_llm_concurrency", max(1, min(conc, 8)))

        object.__setattr__(self, "disk_a", self.disk_a.expanduser().resolve())
        object.__setattr__(self, "disk_b", self.disk_b.expanduser().resolve())

    @property
    def ws_connect_url(self) -> str:
        """Construeix la URL completa `wss://.../api/v1/vault-tunnel/connect`."""
        return build_ws_connect_url(self.server_url)

    def build_handshake_headers(self) -> Dict[str, str]:
        """Capçaleres Zero-Trust del handshake WSS sortint."""
        headers: Dict[str, str] = {
            "X-Vault-Role": self.role,
            "X-Vault-Token": self.vault_token.strip(),
            "X-Agent-Version": self.agent_version,
        }
        if self.empresa_id is not None:
            headers["X-Empresa-ID"] = self.empresa_id
        return headers

    @classmethod
    def from_env(cls) -> "AgentConfig":
        """Carrega i valida la configuració des de les variables d'entorn."""
        disk_a_raw = os.getenv("SEVALOR_VAULT_PATH_A") or os.getenv("SEVALOR_VAULT_PATH") or ""
        if not disk_a_raw.strip():
            raise ValueError("Cal definir SEVALOR_VAULT_PATH_A amb la ruta del Disc Dur Primari A.")
        disk_a = Path(disk_a_raw.strip())
        disk_b_raw = os.getenv("SEVALOR_VAULT_PATH_B", "").strip()
        disk_b = Path(disk_b_raw) if disk_b_raw else Path(f"{str(disk_a).rstrip('/')}_backup_B")

        raw_conc = os.getenv("SEVALOR_LOCAL_LLM_CONCURRENCY", str(DEFAULT_LOCAL_LLM_CONCURRENCY)).strip()
        try:
            llm_concurrency = max(1, min(int(raw_conc), 8))
        except ValueError:
            llm_concurrency = DEFAULT_LOCAL_LLM_CONCURRENCY

        return cls(
            server_url=os.getenv("SEVALOR_SERVER_URL", DEFAULT_SERVER_URL).strip()
            or DEFAULT_SERVER_URL,
            role=os.getenv("SEVALOR_VAULT_ROLE", "EMPRESA").strip().upper(),
            empresa_id=os.getenv("SEVALOR_EMPRESA_ID", "").strip() or None,
            vault_token=os.getenv("SEVALOR_VAULT_SECRET", "").strip(),
            disk_a=disk_a,
            disk_b=disk_b,
            local_llm_url=os.getenv("SEVALOR_LOCAL_LLM_URL", DEFAULT_LOCAL_LLM_URL).strip()
            or DEFAULT_LOCAL_LLM_URL,
            local_llm_concurrency=llm_concurrency,
        )


def build_ws_connect_url(server_url: str) -> str:
    """Converteix una URL base `https://` / `http://` / `wss://` / `ws://` a l'endpoint WSS."""
    clean = server_url.strip().rstrip("/")
    if not clean:
        raise ValueError("SEVALOR_SERVER_URL no pot ser buida.")

    if clean.startswith("https://"):
        ws_base = "wss://" + clean[len("https://") :]
    elif clean.startswith("http://"):
        ws_base = "ws://" + clean[len("http://") :]
    elif clean.startswith(("wss://", "ws://")):
        ws_base = clean
    else:
        raise ValueError(f"Esquema invàlid a SEVALOR_SERVER_URL: {server_url!r}.")

    parsed = urlparse(ws_base)
    if not parsed.netloc:
        raise ValueError(f"Host absent a SEVALOR_SERVER_URL: {server_url!r}.")

    if ws_base.endswith("/api/v1/vault-tunnel/connect"):
        return ws_base
    if ws_base.endswith("/api/v1"):
        return f"{ws_base}/vault-tunnel/connect"
    return f"{ws_base}/api/v1/vault-tunnel/connect"


def sanititzar_segment(segment: str) -> str:
    """Impedeix Path Traversal, caràcters nuls i segments invàlids."""
    raw = str(segment).strip()
    if not raw or raw in (".", "..") or ".." in raw or "\x00" in raw or "/" in raw or "\\" in raw:
        raise AgentActionError("Nom d'arxiu o carpeta invàlid.", code="PATH_TRAVERSAL", status_code=400)
    net = re.sub(r"[^a-zA-Z0-9_\-\.]", "_", raw)
    if not net or net in (".", ".."):
        raise AgentActionError("Nom d'arxiu o carpeta invàlid.", code="PATH_TRAVERSAL", status_code=400)
    return net


def resoldre_carpeta_segura(root_a: Path, subcarpeta: str) -> Path:
    """Resol una subcarpeta dins `root_a` garantint profunditat >= 1 i zero sortida per symlinks."""
    base = root_a.resolve()
    raw_str = str(subcarpeta or "").strip()
    if "\x00" in raw_str or "\\" in raw_str:
        raise AgentActionError("Ruta de carpeta invàlida.", code="PATH_TRAVERSAL", status_code=400)
    raw_parts = [p for p in raw_str.strip("/").split("/") if p]
    if not raw_parts:
        raise AgentActionError("Cal indicar la subcarpeta de destí.", code="INVALID_PATH", status_code=400)
    parts = [sanititzar_segment(p) for p in raw_parts]
    folder = base.joinpath(*parts).resolve()
    if not folder.is_relative_to(base) or folder == base:
        raise AgentActionError("Ruta fora del disc autoritzat.", code="PATH_TRAVERSAL", status_code=400)
    return folder


def resoldre_fitxer_segur(root_a: Path, rel_path: str) -> Path:
    """Resol una ruta de fitxer relativa (`subcarpeta/nom`) dins `root_a` amb profunditat >= 2."""
    base = root_a.resolve()
    raw_str = str(rel_path or "").strip()
    if "\x00" in raw_str or "\\" in raw_str:
        raise AgentActionError("Ruta de fitxer invàlida.", code="PATH_TRAVERSAL", status_code=400)
    raw_parts = [p for p in raw_str.strip("/").split("/") if p]
    if len(raw_parts) < 2:
        raise AgentActionError(
            "La ruta de fitxer ha d'incloure subcarpeta i nom.",
            code="INVALID_PATH",
            status_code=400,
        )
    parts = [sanititzar_segment(p) for p in raw_parts]
    target = base.joinpath(*parts).resolve()
    if not target.is_relative_to(base) or target == base:
        raise AgentActionError("Ruta fora del disc autoritzat.", code="PATH_TRAVERSAL", status_code=400)
    return target


def _write_atomic(dest_path: Path, data: bytes) -> None:
    """Escriptura atòmica segura per evitar fitxers truncats en talls de corrent."""
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = dest_path.parent / f".{dest_path.name}.{uuid.uuid4().hex[:8]}.tmp"
    try:
        tmp_path.write_bytes(data)
        os.replace(tmp_path, dest_path)
    finally:
        if tmp_path.exists():
            tmp_path.unlink(missing_ok=True)


def inicialitzar_estructura_disc(
    role: Optional[str] = None,
    disk_a: Optional[Path] = None,
    disk_b: Optional[Path] = None,
) -> List[str]:
    """Crea físicament les 38 carpetes (EMPRESA) o les 20 (SUPERADMIN) + mirall Disc B."""
    role_norm = (role or os.getenv("SEVALOR_VAULT_ROLE") or "EMPRESA").strip().upper()
    if role_norm not in VALID_VAULT_ROLES:
        raise AgentActionError("Rol de passarel·la invàlid.", code="INVALID_ROLE", status_code=400)

    root_a = (
        disk_a
        if disk_a is not None
        else Path(os.getenv("SEVALOR_VAULT_PATH_A", "./sevalor_vault_A"))
    ).expanduser().resolve()
    root_b = (
        disk_b
        if disk_b is not None
        else Path(os.getenv("SEVALOR_VAULT_PATH_B", f"{str(root_a).rstrip('/')}_backup_B"))
    ).expanduser().resolve()

    carpetes = CARPETES_SUPERADMIN if role_norm == "SUPERADMIN" else CARPETES_OFICIALS
    root_a.mkdir(parents=True, exist_ok=True)
    root_b.mkdir(parents=True, exist_ok=True)
    for sub in carpetes:
        target = (root_a / sub).resolve()
        if not target.is_relative_to(root_a):
            raise AgentActionError(
                "Ruta de subcarpeta fora del disc autoritzat.",
                code="PATH_TRAVERSAL",
                status_code=400,
            )
        target.mkdir(parents=True, exist_ok=True)
        target_b = (root_b / sub).resolve()
        if target_b.is_relative_to(root_b):
            target_b.mkdir(parents=True, exist_ok=True)
    (root_b / "backups_jornada").mkdir(parents=True, exist_ok=True)
    return list(carpetes)


class _PriorityConcurrencyLimiter:
    """Semàfor asíncron amb cua de prioritat estricta (`HIGH > NORMAL > LOW`) per a LLM local.

    Evita la saturació d'ample de banda de memòria als mini-PCs dedicats (Ryzen 7 5700U 16/32 GB)
    serialitzant la inferència (`SEVALOR_LOCAL_LLM_CONCURRENCY=1`) i donant prioritat immediata al
    Copilot interactiu (`HIGH`) per davant de tasques en segon pla com OCR (`LOW`).
    """

    def __init__(self, max_concurrency: int = DEFAULT_LOCAL_LLM_CONCURRENCY) -> None:
        self._max_concurrency = max(1, int(max_concurrency))
        self._in_flight = 0
        self._seq = 0
        self._waiters: List[Tuple[int, int, asyncio.Future[None]]] = []

    @property
    def max_concurrency(self) -> int:
        return self._max_concurrency

    @property
    def in_flight(self) -> int:
        return self._in_flight

    @property
    def queued(self) -> int:
        return sum(1 for _r, _s, fut in self._waiters if not fut.done())

    async def _acquire(self, priority: str = "HIGH") -> None:
        if self._in_flight < self._max_concurrency:
            self._in_flight += 1
            return
        loop = asyncio.get_running_loop()
        fut: asyncio.Future[None] = loop.create_future()
        rank = LLM_PRIORITY_RANKS.get(str(priority or "HIGH").strip().upper(), 0)
        self._seq += 1
        heapq.heappush(self._waiters, (rank, self._seq, fut))
        try:
            await fut
        except BaseException:
            if fut.done() and not fut.cancelled():
                self._release()
            raise

    def _release(self) -> None:
        while self._waiters:
            _rank, _seq, fut = heapq.heappop(self._waiters)
            if not fut.done():
                fut.set_result(None)
                return
        self._in_flight = max(0, self._in_flight - 1)

    @asynccontextmanager
    async def acquire(self, priority: str = "HIGH") -> AsyncIterator[None]:
        await self._acquire(priority)
        try:
            yield
        finally:
            self._release()


class SovereignWssAgent:
    """Agent sobirà WSS que executa les accions del broker sobre el disc dur i LLM locals."""

    def __init__(self, config: AgentConfig) -> None:
        self.config = config
        self.welcome: Dict[str, Any] = {}
        self.last_close_code: Optional[int] = None
        self._llm_limiter = _PriorityConcurrencyLimiter(config.local_llm_concurrency)

    def init_folders(self) -> Dict[str, Any]:
        carpetes = inicialitzar_estructura_disc(
            role=self.config.role,
            disk_a=self.config.disk_a,
            disk_b=self.config.disk_b,
        )
        return {
            "status": "OK",
            "role": self.config.role,
            "vault_root": str(self.config.disk_a),
            "vault_secondary_b": str(self.config.disk_b),
            "carpetes_count": len(carpetes),
            "carpetes": carpetes,
        }

    async def _probe_local_llm_models(self, *, timeout: float = 2.5) -> tuple[bool, List[str]]:
        base = self.config.local_llm_url
        endpoint = f"{base}/models" if base.endswith("/v1") else f"{base}/v1/models"
        try:
            async with httpx.AsyncClient(timeout=timeout, follow_redirects=False) as client:
                resp = await client.get(endpoint)
            if resp.status_code != 200:
                return (False, [])
            data = resp.json()
            models: List[str] = []
            if isinstance(data, dict) and isinstance(data.get("data"), list):
                models = [
                    str(m.get("id") or m.get("name"))
                    for m in data["data"]
                    if isinstance(m, dict) and (m.get("id") or m.get("name"))
                ]
            return (True, models)
        except Exception:
            return (False, [])

    async def action_health(self) -> Dict[str, Any]:
        carpetes = inicialitzar_estructura_disc(
            role=self.config.role,
            disk_a=self.config.disk_a,
            disk_b=self.config.disk_b,
        )
        usage_a = shutil.disk_usage(self.config.disk_a)
        usage_b = shutil.disk_usage(self.config.disk_b)
        llm_online, models = await self._probe_local_llm_models(timeout=2.0)
        return {
            "status": "OK",
            "role": self.config.role,
            "agent_version": self.config.agent_version,
            "vault_root": str(self.config.disk_a),
            "vault_secondary_b": str(self.config.disk_b),
            "carpetes_count": len(carpetes),
            "disc_a_lliure_gb": round(usage_a.free / (1024**3), 2),
            "disc_b_lliure_gb": round(usage_b.free / (1024**3), 2),
            "llm_online": llm_online,
            "llm_concurrency": self.config.local_llm_concurrency,
            "llm_in_flight": self._llm_limiter.in_flight,
            "models": models,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    def action_json_put(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        subcarpeta = str(payload.get("subcarpeta") or "")
        item_id = sanititzar_segment(str(payload.get("item_id") or ""))
        content = payload.get("content")
        if not isinstance(content, dict):
            raise AgentActionError("El camp 'content' ha de ser un objecte JSON.", status_code=400)

        folder = resoldre_carpeta_segura(self.config.disk_a, subcarpeta)
        file_path = (folder / f"{item_id}.json").resolve()
        if not file_path.is_relative_to(folder):
            raise AgentActionError("Identificador d'entitat invàlid.", code="PATH_TRAVERSAL", status_code=400)

        raw_bytes = json.dumps(content, ensure_ascii=False, indent=2, default=str).encode("utf-8")
        if len(raw_bytes) > MAX_UPLOAD_BYTES:
            raise AgentActionError(
                "La fitxa JSON supera el límit de 50 MB.", code="PAYLOAD_TOO_LARGE", status_code=413
            )
        _write_atomic(file_path, raw_bytes)
        rel_path = str(file_path.relative_to(self.config.disk_a))
        return {"status": "SAVED", "item_id": item_id, "rel_path": rel_path}

    def action_json_get_list(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        subcarpeta = str(payload.get("subcarpeta") or "")
        folder = resoldre_carpeta_segura(self.config.disk_a, subcarpeta)
        if not folder.exists() or not folder.is_dir():
            return {"items": []}

        items: List[Dict[str, Any]] = []
        for fpath in sorted(folder.glob("*.json"), key=os.path.getmtime, reverse=True):
            resolved_f = fpath.resolve()
            if not resolved_f.is_relative_to(folder) or not resolved_f.is_file():
                continue
            try:
                parsed = json.loads(resolved_f.read_text(encoding="utf-8"))
                if isinstance(parsed, dict):
                    items.append(parsed)
            except Exception:
                continue
        return {"items": items}

    def action_json_delete(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        subcarpeta = str(payload.get("subcarpeta") or "")
        item_id = sanititzar_segment(str(payload.get("item_id") or ""))
        folder = resoldre_carpeta_segura(self.config.disk_a, subcarpeta)
        file_path = (folder / f"{item_id}.json").resolve()
        deleted = False
        if file_path.is_file() and file_path.is_relative_to(folder) and file_path != self.config.disk_a:
            file_path.unlink()
            deleted = True
        return {"deleted": deleted, "item_id": item_id}

    def action_file_put(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        subcarpeta = str(payload.get("subcarpeta") or "")
        filename = sanititzar_segment(str(payload.get("filename") or ""))
        b64 = payload.get("content_b64")
        if not isinstance(b64, str):
            raise AgentActionError("Camp 'content_b64' absent o invàlid.", status_code=400)

        try:
            raw = base64.b64decode(b64.encode("ascii"), validate=True)
        except Exception as exc:
            raise AgentActionError("Contingut base64 invàlid.", status_code=400) from exc

        if len(raw) > MAX_UPLOAD_BYTES:
            raise AgentActionError(
                "El fitxer supera el límit màxim de 50 MB.", code="PAYLOAD_TOO_LARGE", status_code=413
            )

        actual_sha = hashlib.sha256(raw).hexdigest()
        expected_sha = payload.get("sha256")
        if isinstance(expected_sha, str) and expected_sha and actual_sha != expected_sha:
            raise AgentActionError(
                "Integritat SHA-256 corrupta en la recepció del fitxer.",
                code="CHECKSUM_MISMATCH",
                status_code=400,
            )

        folder = resoldre_carpeta_segura(self.config.disk_a, subcarpeta)
        dest_path = (folder / filename).resolve()
        if not dest_path.is_relative_to(folder):
            raise AgentActionError("Nom de fitxer invàlid.", code="PATH_TRAVERSAL", status_code=400)

        _write_atomic(dest_path, raw)
        rel_path = str(dest_path.relative_to(self.config.disk_a))
        return {
            "status": "OK",
            "rel_path": rel_path,
            "size_bytes": len(raw),
            "sha256": actual_sha,
        }

    def action_file_get(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        rel_path = str(payload.get("rel_path") or "")
        target = resoldre_fitxer_segur(self.config.disk_a, rel_path)
        if not target.is_file():
            raise AgentActionError("Fitxer no trobat al disc dur.", code="NOT_FOUND", status_code=404)
        size = target.stat().st_size
        if size > MAX_UPLOAD_BYTES:
            raise AgentActionError(
                "El fitxer supera el límit màxim de 50 MB.", code="PAYLOAD_TOO_LARGE", status_code=413
            )
        raw = target.read_bytes()
        return {
            "filename": target.name,
            "content_b64": base64.b64encode(raw).decode("ascii"),
            "size_bytes": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest(),
        }

    def action_file_rename(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        old_rel = str(payload.get("old_rel_path") or "")
        new_sub = str(payload.get("new_subcarpeta") or "")
        new_name = sanititzar_segment(str(payload.get("new_filename") or ""))

        old_target = resoldre_fitxer_segur(self.config.disk_a, old_rel)
        if not old_target.is_file():
            raise AgentActionError("Fitxer d'origen no trobat.", code="NOT_FOUND", status_code=404)

        dest_folder = resoldre_carpeta_segura(self.config.disk_a, new_sub)
        dest_folder.mkdir(parents=True, exist_ok=True)
        dest_target = (dest_folder / new_name).resolve()
        if not dest_target.is_relative_to(dest_folder):
            raise AgentActionError("Nom de destí invàlid.", code="PATH_TRAVERSAL", status_code=400)

        if old_target != dest_target:
            os.replace(old_target, dest_target)
        return {"status": "OK", "rel_path": str(dest_target.relative_to(self.config.disk_a))}

    def action_file_delete(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        rel_path = str(payload.get("rel_path") or "")
        target = resoldre_fitxer_segur(self.config.disk_a, rel_path)
        deleted = False
        if target.is_file() and target != self.config.disk_a:
            target.unlink()
            deleted = True
        return {"deleted": deleted, "rel_path": rel_path}

    def action_backup_daily(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Backup diari al tancament de jornada alternant Disc A (dies senars) i Disc B (dies parells) amb SHA-256."""
        inicialitzar_estructura_disc(
            role=self.config.role,
            disk_a=self.config.disk_a,
            disk_b=self.config.disk_b,
        )
        ara = datetime.now(timezone.utc)
        iso_weekday = ara.isoweekday()
        es_dia_senar = (iso_weekday % 2) == 1

        root_a = self.config.disk_a
        root_b = self.config.disk_b
        backups_rel = (
            "08_backups_superadmin/backups_locals"
            if self.config.role == "SUPERADMIN"
            else "11_configuracio_i_backups/backups_locals"
        )
        disc_desti_root = (root_a / backups_rel) if es_dia_senar else (root_b / "backups_jornada")
        etiqueta_disc = "DISC_A_PRIMARI" if es_dia_senar else "DISC_B_MIRALL"
        disc_desti_root.mkdir(parents=True, exist_ok=True)

        dump_json_path = root_a / backups_rel / "ultim_dump_bd.json"
        _write_atomic(
            dump_json_path,
            json.dumps(payload, ensure_ascii=False, indent=2, default=str).encode("utf-8"),
        )

        data_str = ara.strftime("%Y-%m-%d_%H%M%S")
        zip_filename = f"backup_jornada_{etiqueta_disc}_{data_str}.zip"
        zip_path = disc_desti_root / zip_filename

        total_files = 0
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for root, _dirs, files in os.walk(root_a, followlinks=False):
                for fname in files:
                    if fname.endswith(".zip") or fname.endswith(".tmp"):
                        continue
                    full_p = (Path(root) / fname).resolve()
                    if not full_p.is_relative_to(root_a) or not full_p.is_file():
                        continue
                    zf.write(full_p, str(full_p.relative_to(root_a)))
                    total_files += 1

        sha256_hash = hashlib.sha256(zip_path.read_bytes()).hexdigest()
        sha_content = f"{sha256_hash}  {zip_filename}\n".encode("utf-8")
        _write_atomic(
            disc_desti_root / f"{zip_filename}.sha256",
            sha_content,
        )

        # Garantir còpia simètrica del backup a les carpetes oficials de Disc A i mirall Disc B
        zip_bytes = zip_path.read_bytes()
        for mirror_dir in (root_a / backups_rel, root_b / backups_rel):
            mirror_dir.mkdir(parents=True, exist_ok=True)
            mirror_zip = mirror_dir / zip_filename
            if mirror_zip.resolve() != zip_path.resolve():
                _write_atomic(mirror_zip, zip_bytes)
                _write_atomic(mirror_dir / f"{zip_filename}.sha256", sha_content)

        return {
            "status": "OK",
            "role": self.config.role,
            "disc_utilitzat": etiqueta_disc,
            "dia_setmana_iso": iso_weekday,
            "zip_path": str(zip_path),
            "sha256": sha256_hash,
            "fitxers_empaquetats": total_files,
            "mida_bytes": zip_path.stat().st_size,
        }

    async def action_llm_models(self) -> Dict[str, Any]:
        """Consulta els models carregats al LM Studio / Ollama local del PC (mai envia X-Vault-Token)."""
        base = self.config.local_llm_url
        endpoint = f"{base}/models" if base.endswith("/v1") else f"{base}/v1/models"
        try:
            async with httpx.AsyncClient(timeout=8.0, follow_redirects=False) as client:
                resp = await client.get(endpoint, headers={"Accept": "application/json"})
            if resp.status_code >= 400:
                raise AgentActionError(
                    f"El motor IA local ha respost HTTP {resp.status_code}.",
                    code="LLM_HTTP_ERROR",
                    status_code=resp.status_code,
                )
            data = resp.json()
            return data if isinstance(data, dict) else {"data": []}
        except AgentActionError:
            raise
        except httpx.RequestError as exc:
            raise AgentActionError(
                f"El PC de l'empresa està connectat, però LM Studio/Ollama local no respon a {base}.",
                code="LLM_OFFLINE",
                status_code=503,
            ) from exc

    async def action_llm_chat(self, payload: Dict[str, Any], *, timeout_s: float = 120.0) -> Dict[str, Any]:
        """Executa inferència OpenAI-compatible contra el LM Studio / Ollama local del PC.

        Serialitza les crides amb `_PriorityConcurrencyLimiter` (`SEVALOR_LOCAL_LLM_CONCURRENCY=1`,
        `HIGH` per a Copilot interactiu > `LOW` per a OCR en segon pla) i elimina capçaleres o
        claus internes `_sevalor_*` abans d'enviar el JSON al motor IA local.
        """
        base = self.config.local_llm_url
        endpoint = (
            f"{base}/chat/completions" if base.endswith("/v1") else f"{base}/v1/chat/completions"
        )
        priority = str(payload.get("_sevalor_priority") or "HIGH").strip().upper()
        # Mai propagar credencials de túnel ni camps interns `_sevalor_*` cap al motor IA local
        body = {
            k: v
            for k, v in payload.items()
            if str(k).lower() != "x-vault-token" and not str(k).startswith("_sevalor_")
        }
        req_headers: Dict[str, str] = {"Content-Type": "application/json"}
        api_key = os.getenv("SEVALOR_LOCAL_LLM_API_KEY", "").strip()
        if api_key:
            req_headers["Authorization"] = f"Bearer {api_key}"

        effective_timeout = max(2.0, min(timeout_s, 180.0))
        try:
            async with self._llm_limiter.acquire(priority):
                async with httpx.AsyncClient(
                    timeout=effective_timeout,
                    follow_redirects=False,
                ) as client:
                    resp = await client.post(endpoint, json=body, headers=req_headers)
            if resp.status_code >= 400:
                raise AgentActionError(
                    f"LM Studio/Ollama local ha retornat HTTP {resp.status_code}: {resp.text[:200]}",
                    code="LLM_HTTP_ERROR",
                    status_code=resp.status_code,
                )
            data = resp.json()
            return data if isinstance(data, dict) else {"raw": data}
        except AgentActionError:
            raise
        except httpx.RequestError as exc:
            raise AgentActionError(
                f"El PC de l'empresa està connectat, però LM Studio/Ollama local no respon a {base}.",
                code="LLM_OFFLINE",
                status_code=503,
            ) from exc

    async def execute_action(
        self,
        action: str,
        payload: Dict[str, Any],
        *,
        timeout_s: float = 30.0,
    ) -> Dict[str, Any]:
        """Despatxa qualsevol acció autoritzada del protocol WSS."""
        if action == "health":
            return await self.action_health()
        if action == "init_folders":
            return self.init_folders()
        if action == "json_put":
            return self.action_json_put(payload)
        if action == "json_get_list":
            return self.action_json_get_list(payload)
        if action == "json_delete":
            return self.action_json_delete(payload)
        if action == "file_put":
            return self.action_file_put(payload)
        if action == "file_get":
            return self.action_file_get(payload)
        if action == "file_rename":
            return self.action_file_rename(payload)
        if action == "file_delete":
            return self.action_file_delete(payload)
        if action == "backup_daily":
            return self.action_backup_daily(payload)
        if action == "llm_models":
            return await self.action_llm_models()
        if action == "llm_chat":
            return await self.action_llm_chat(payload, timeout_s=timeout_s)
        if action == "ping":
            return {"pong": True, "ts": datetime.now(timezone.utc).isoformat()}
        raise AgentActionError(
            f"Acció desconeguda o no autoritzada: {action!r}.",
            code="UNKNOWN_ACTION",
            status_code=400,
        )

    async def _run_single_session(self, stop_event: asyncio.Event) -> Optional[int]:
        """Manté una sessió WSS fins a desconnexió o parada neta. Retorna el codi de tancament."""
        ws_url = self.config.ws_connect_url
        headers = self.config.build_handshake_headers()
        send_lock = asyncio.Lock()
        inflight: set[asyncio.Task[None]] = set()

        async with websockets.connect(
            ws_url,
            additional_headers=headers,
            max_size=MAX_WS_FRAME_BYTES,
            ping_interval=None,
            open_timeout=15.0,
            close_timeout=5.0,
        ) as ws:
            # 1. Rebre trama inicial `welcome`
            raw_welcome = await asyncio.wait_for(ws.recv(), timeout=10.0)
            welcome_msg = json.loads(raw_welcome)
            if isinstance(welcome_msg, dict) and welcome_msg.get("type") == "welcome":
                self.welcome = welcome_msg

            # 2. Enviar salutació `hello` amb telemetria inicial de salut
            health_snap = await self.action_health()
            async with send_lock:
                await ws.send(
                    json.dumps(
                        {
                            "type": "hello",
                            "agent_version": self.config.agent_version,
                            "health": health_snap,
                        },
                        ensure_ascii=False,
                    )
                )

            logger.info(
                "Connectat al túnel sobirà WSS (%s) com a %s -> %s",
                ws_url,
                self.config.role,
                self.welcome.get("target_key", "-"),
            )

            async def _handle_request(msg: Dict[str, Any]) -> None:
                req_id = str(msg.get("req_id") or "")
                action = str(msg.get("action") or "")
                payload = msg.get("payload")
                timeout_s = float(msg.get("timeout_s") or 30.0)
                try:
                    data = await self.execute_action(
                        action,
                        payload if isinstance(payload, dict) else {},
                        timeout_s=timeout_s,
                    )
                    reply: Dict[str, Any] = {
                        "type": "response",
                        "req_id": req_id,
                        "ok": True,
                        "data": data,
                    }
                except AgentActionError as exc:
                    reply = {
                        "type": "response",
                        "req_id": req_id,
                        "ok": False,
                        "error_code": exc.code,
                        "status_code": exc.status_code,
                        "detail": exc.detail,
                    }
                except Exception as exc:
                    logger.warning("Error intern executant acció '%s': %s", action, exc)
                    reply = {
                        "type": "response",
                        "req_id": req_id,
                        "ok": False,
                        "error_code": "AGENT_INTERNAL_ERROR",
                        "status_code": 500,
                        "detail": "Error intern executant l'acció al node local.",
                    }
                try:
                    async with send_lock:
                        await ws.send(json.dumps(reply, ensure_ascii=False, default=str))
                except Exception:
                    pass

            stop_waiter = asyncio.create_task(stop_event.wait())
            try:
                while not stop_event.is_set():
                    recv_task = asyncio.create_task(ws.recv())
                    done, _ = await asyncio.wait(
                        {recv_task, stop_waiter},
                        return_when=asyncio.FIRST_COMPLETED,
                    )
                    if stop_waiter in done:
                        recv_task.cancel()
                        try:
                            await ws.close(code=1000, reason="Agent shutdown")
                        except Exception:
                            pass
                        return 1000

                    raw = recv_task.result()
                    if not isinstance(raw, str):
                        continue
                    try:
                        msg = json.loads(raw)
                    except json.JSONDecodeError:
                        continue
                    if not isinstance(msg, dict):
                        continue

                    mtype = str(msg.get("type") or "").lower()
                    if mtype == "ping":
                        pong_frame: Dict[str, Any] = {
                            "type": "pong",
                            "req_id": str(msg.get("req_id") or ""),
                            "ts": datetime.now(timezone.utc).isoformat(),
                        }
                        async with send_lock:
                            await ws.send(json.dumps(pong_frame, ensure_ascii=False))
                        continue

                    if mtype == "request":
                        t = asyncio.create_task(_handle_request(msg))
                        inflight.add(t)
                        t.add_done_callback(inflight.discard)
            except websockets.exceptions.ConnectionClosed as closed_exc:
                code = closed_exc.rcvd.code if closed_exc.rcvd else None
                self.last_close_code = code
                return code
            finally:
                stop_waiter.cancel()
                for t in list(inflight):
                    t.cancel()

        return None

    async def run_forever(self, stop_event: Optional[asyncio.Event] = None) -> None:
        """Executa el daemon sortint amb reconnexió exponencial automàtica indefinida."""
        stopper = stop_event or asyncio.Event()
        inicialitzar_estructura_disc(
            role=self.config.role,
            disk_a=self.config.disk_a,
            disk_b=self.config.disk_b,
        )

        backoff = BACKOFF_INITIAL_SECONDS
        while not stopper.is_set():
            started_at = asyncio.get_running_loop().time()
            close_code: Optional[int] = None
            try:
                close_code = await self._run_single_session(stopper)
            except websockets.exceptions.ConnectionClosed as closed_exc:
                close_code = closed_exc.rcvd.code if closed_exc.rcvd else None
                self.last_close_code = close_code
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                logger.warning("Desconnexió o error connectant al túnel WSS: %s", exc)

            if stopper.is_set():
                break

            lived_s = asyncio.get_running_loop().time() - started_at
            if lived_s >= 10.0 and close_code not in (4401, 4403):
                backoff = BACKOFF_INITIAL_SECONDS

            if close_code in (4401, 4403):
                wait_s = max(backoff, AUTH_FAIL_BACKOFF_SECONDS)
                logger.error(
                    "Handshake WSS rebutjat pel servidor (codi %s). Verifica SEVALOR_VAULT_SECRET i SEVALOR_EMPRESA_ID. Reintent en %.1fs.",
                    close_code,
                    wait_s,
                )
            else:
                wait_s = backoff + random.uniform(0.0, 0.5)
                logger.info(
                    "Túnel WSS desconnectat (codi=%s). Reconnectant en %.1fs...",
                    close_code,
                    wait_s,
                )

            try:
                await asyncio.wait_for(stopper.wait(), timeout=wait_s)
            except asyncio.TimeoutError:
                pass

            backoff = min(backoff * 2.0, BACKOFF_MAX_SECONDS)


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Sevalor Suite — Agent Sobirà WSS (connexió sortint port 443, zero ports entrants)."
    )
    parser.add_argument(
        "--init-only",
        action="store_true",
        help="Inicialitza únicament l'estructura de carpetes del Disc A i Disc B i surt.",
    )
    return parser


def main() -> int:
    logging.basicConfig(
        level=os.getenv("LOG_LEVEL", "INFO").upper(),
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )
    args = _build_arg_parser().parse_args()

    try:
        config = AgentConfig.from_env()
    except ValueError as exc:
        logger.error("Configuració invàlida de l'agent WSS: %s", exc)
        return 2

    if args.init_only:
        carpetes = inicialitzar_estructura_disc(
            role=config.role, disk_a=config.disk_a, disk_b=config.disk_b
        )
        print(
            f"Carpetes inicialitzades ({config.role}): {len(carpetes)} a {config.disk_a} (mirall: {config.disk_b})"
        )
        return 0

    agent = SovereignWssAgent(config)
    stop_event = asyncio.Event()

    async def _runner() -> None:
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            try:
                loop.add_signal_handler(sig, stop_event.set)
            except NotImplementedError:
                pass
        logger.info(
            "Iniciant %s (role=%s, server=%s, disk_a=%s, disk_b=%s, llm=%s)",
            config.agent_version,
            config.role,
            config.ws_connect_url,
            config.disk_a,
            config.disk_b,
            config.local_llm_url,
        )
        await agent.run_forever(stop_event)

    try:
        asyncio.run(_runner())
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
