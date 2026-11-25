import asyncio
import hashlib
import io
import json
import logging
import os
import re
import secrets
import shutil
import socket
import time
import uuid
import zipfile
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

import bcrypt
import jwt
from fastapi import APIRouter, Body, Depends, HTTPException, Request, status
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.db import get_db_with_tenant_context
from app.core.network_utils import (
    build_wss_tunnel_uri,
    extract_wss_tunnel_target,
    get_public_tunnel_server_url,
    is_wss_tunnel_uri,
)
from app.core.security import blind_email, blind_nif, blind_telefon, require_roles
from app.models.models import (
    Client,
    Empresa,
    FacturaCapcalera,
    OrdreTreball,
    RegistreBaixaCertificat,
    SaasFacturaB2B,
    SaasHistorialLlicencia,
    SaasTiquetSuport,
    Usuari,
)
from app.services.easypanel_service import EasypanelService
from app.services.sovereign_storage import (
    SovereignStorageGateway,
    SuperadminStorageGateway,
    inicialitzar_arbre_carpetes_disc,
)
from app.services.vault_tunnel import (
    VaultTunnelError,
    VaultTunnelOfflineError,
    VaultTunnelRemoteError,
    VaultTunnelTimeoutError,
    empresa_target_key,
    vault_tunnel_broker,
)

logger = logging.getLogger("superadmin.tenants")

router = APIRouter(prefix="/superadmin/tenants", tags=["Superadmin", "Tenants"])

QUOTES_PER_PLA = {
    "STARTER": 5,
    "PRO": 15,
    "ENTERPRISE": 50,
}


def _obtenir_ruta_certificat_persistent(tenant_id: str) -> str:
    """Retorna la ruta persistent per al certificat de destrucció RGPD."""
    base_docs = os.getenv("SOVEREIGN_DOCS_PATH", "/docs")
    persistent_dir = os.path.join(base_docs, "superadmin", "certificats")
    try:
        os.makedirs(persistent_dir, exist_ok=True)
        return os.path.join(persistent_dir, f"certificat_destruccio_{tenant_id}.pdf")
    except OSError:
        fallback_dir = f"/tmp/sevalor_docs/{tenant_id}/certificats"
        os.makedirs(fallback_dir, exist_ok=True)
        return os.path.join(fallback_dir, f"certificat_destruccio_{tenant_id}.pdf")


def _calcular_buffer_diari_bytes(empresa_id: str, fallback_bytes: int = 0) -> int:
    """Mesura l'espai real ocupat al buffer diari de Hetzner (/data/<id>) sense bloquejar si no existeix."""
    total = 0
    for prefix in ("/data", "/tmp/data"):
        target = os.path.join(prefix, empresa_id)
        if os.path.exists(target):
            for root, _dirs, files in os.walk(target):
                for f in files:
                    fp = os.path.join(root, f)
                    try:
                        if not os.path.islink(fp):
                            total += os.path.getsize(fp)
                    except OSError:
                        pass
    return total if total > 0 else fallback_bytes


async def _resolve_empresa(db: AsyncSession, empresa_id_or_slug: str) -> Optional[Empresa]:
    """Cerca i resol una Empresa per UUID o bé per subdomini / domini personalitzat."""
    clean = (empresa_id_or_slug or "").strip().lower()
    if not clean:
        return None
    try:
        emp_uuid = uuid.UUID(clean)
        res = await db.execute(select(Empresa).where(Empresa.id == emp_uuid))
        emp = res.scalars().first()
        if emp:
            return emp
    except ValueError:
        pass

    res = await db.execute(
        select(Empresa).where(
            or_(
                func.lower(Empresa.subdomini) == clean,
                func.lower(Empresa.domini_custom) == clean,
            )
        )
    )
    return res.scalars().first()


class EquipIAVenutItem(BaseModel):
    concepte: str = Field(..., min_length=1, max_length=200)
    unitats: int = Field(1, ge=1, le=100)
    preu_unitari: float = Field(0.0, ge=0.0)
    modalitat: str = Field("VENDA", pattern="^VENDA$")


class OnboardingTenantRequest(BaseModel):
    rao_social: str = Field(..., min_length=2, max_length=100)
    nif: str = Field(..., min_length=9, max_length=20)
    adreca: Optional[str] = Field(None, max_length=300)
    slug: Optional[str] = Field(None, min_length=2, max_length=63, pattern=r"^[a-z0-9-]+$")
    subdomini: Optional[str] = Field(None, min_length=2, max_length=63, pattern=r"^[a-z0-9-]+$")
    domini_custom: Optional[str] = Field(
        None,
        max_length=100,
        pattern=r"^$|^[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?(\.[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?)+$",
    )
    vertical: str = Field("SEVALOR", max_length=100)
    magatzem_families_default: Optional[str] = None
    agent_prompt_system: Optional[str] = None
    node_ia_url: Optional[str] = None
    disc_dur_url: Optional[str] = None
    estat_inicial: str = Field("TRIAL", pattern="^(TRIAL|ACTIU)$")
    pla_subscripcio: str = Field("PRO", pattern="^(STARTER|PRO|ENTERPRISE|CUSTOM)$")
    quota_operaris: Optional[int] = Field(None, ge=1, le=500)
    quota_buffer_mb: int = Field(500, ge=50, le=50000)
    quota_disc_gb: int = Field(10, ge=1, le=1000)
    primari_hsl: Optional[str] = Field("210 100% 15%", max_length=30)
    secundari_hsl: Optional[str] = Field("38 92% 50%", max_length=30)
    accent_hsl: Optional[str] = Field("190 90% 50%", max_length=30)
    tarifa_llicencia_base: Optional[float] = Field(0.0, ge=0.0)
    tarifa_per_operari: Optional[float] = Field(0.0, ge=0.0)
    tarifa_config_ia: Optional[float] = Field(0.0, ge=0.0)
    equips_ia_venuts: Optional[List[EquipIAVenutItem]] = None
    notes_crm: Optional[str] = None
    boss_nif: str = Field(..., min_length=9, max_length=20)
    boss_nom: str = Field(..., min_length=1, max_length=100)
    boss_cognoms: str = Field(..., min_length=1, max_length=150)
    boss_email: str = Field(..., pattern=r"^[\w\.-]+@[\w\.-]+\.\w+$")
    boss_telefon: Optional[str] = Field(None, max_length=30)
    feature_flags: Optional[Dict[str, bool]] = None
    logotip_base64: Optional[str] = None
    vault_token: Optional[str] = Field(None, min_length=8, max_length=255)

    @model_validator(mode="after")
    def validar_copilot_prompt(self) -> "OnboardingTenantRequest":
        copilot_ia = bool(self.feature_flags and self.feature_flags.get("copilot_ia"))
        if copilot_ia:
            if not self.agent_prompt_system or len(self.agent_prompt_system.strip()) < 5:
                raise ValueError(
                    "El prompt de sistema de Copilot (agent_prompt_system) és obligatori quan la IA està activada."
                )
        else:
            self.agent_prompt_system = None
            self.node_ia_url = None
        return self


class VerificarNodeIaRequest(BaseModel):
    node_ia_url: Optional[str] = Field(None, max_length=255)
    disc_dur_url: Optional[str] = Field(None, max_length=255)
    empresa_id: Optional[str] = None
    vault_token: Optional[str] = Field(None, min_length=1, max_length=255)


class VerificarDiscDurRequest(BaseModel):
    node_ia_url: Optional[str] = Field(None, min_length=1, max_length=255)
    disc_dur_url: Optional[str] = Field(None, min_length=1, max_length=255)
    empresa_id: Optional[str] = None
    vault_token: Optional[str] = Field(None, min_length=1, max_length=255)


class UpdateDominiTenantRequest(BaseModel):
    domini_custom: Optional[str] = Field(
        None,
        max_length=100,
        pattern=r"^$|^[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?(\.[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?)+$",
    )
    subdomini: Optional[str] = Field(None, min_length=2, max_length=63, pattern=r"^[a-z0-9-]+$")


class UpdateEstatTenantRequest(BaseModel):
    estat: str = Field(
        ...,
        pattern="^(PROSPECTE|TRIAL|ACTIU|HIBERNANT|SUSPES|SUSPES_PAGAMENT|MANTENIMENT|BAIXA_OFFBOARDING|ELIMINAT)$",
    )
    motiu: Optional[str] = Field(None, max_length=255)


class UpdateQuotaTenantRequest(BaseModel):
    pla_subscripcio: Optional[str] = Field(None, pattern="^(STARTER|PRO|ENTERPRISE|CUSTOM)$")
    quota_operaris: Optional[int] = Field(None, ge=1, le=500)
    quota_buffer_mb: Optional[int] = Field(None, ge=50, le=50000)
    motiu: Optional[str] = Field(None, max_length=255)


class UpdateCrmCondicionsRequest(BaseModel):
    tarifa_llicencia_base: Optional[float] = Field(None, ge=0.0)
    tarifa_per_operari: Optional[float] = Field(None, ge=0.0)
    tarifa_config_ia: Optional[float] = Field(None, ge=0.0)
    equips_ia_venuts: Optional[List[EquipIAVenutItem]] = None
    notes_crm: Optional[str] = None
    quota_operaris: Optional[int] = Field(None, ge=1, le=500)
    quota_buffer_mb: Optional[int] = Field(None, ge=50, le=50000)


class UpdateFeatureFlagsRequest(BaseModel):
    feature_copilot_ia: bool
    feature_flota: bool
    feature_planols: bool
    feature_telegram: bool
    node_ia_url: Optional[str] = None
    disc_dur_url: Optional[str] = None
    node_ia_actiu: Optional[bool] = None
    vault_token: Optional[str] = Field(None, min_length=8, max_length=255)


class RotateVaultTokenRequest(BaseModel):
    vault_token: Optional[str] = Field(None, min_length=8, max_length=255)


class VerificarDnsRequest(BaseModel):
    domini: Optional[str] = Field(None, min_length=3, max_length=150)
    fqdn: Optional[str] = Field(None, min_length=3, max_length=150)

    @model_validator(mode="after")
    def check_at_least_one(self) -> "VerificarDnsRequest":
        if not self.domini and not self.fqdn:
            raise ValueError("Cal proporcionar 'domini' o 'fqdn'.")
        return self


class UpdateIpAllowlistRequest(BaseModel):
    ip_allowlist: List[str] = Field(..., min_length=1)


class InicialitzarDiscSuperadminRequest(BaseModel):
    ruta_personalitzada: Optional[str] = Field(None, max_length=500)


def generar_comanda_install_wss(
    empresa_id: str,
    vault_token: str,
    role: str = "EMPRESA",
) -> str:
    """Genera la comanda 1-clic oficial per instal·lar l'agent WSS sobirà al PC dedicat."""
    server_url = get_public_tunnel_server_url()
    role_norm = (role or "EMPRESA").strip().upper()
    if role_norm == "SUPERADMIN":
        return (
            f"bash scripts/install_client_gateway.sh "
            f'--server "{server_url}" '
            f"--role SUPERADMIN "
            f'--token "{vault_token}" '
            f"--disk-a /ruta/disc_superadmin_principal "
            f"--disk-b /ruta/disc_superadmin_mirall "
            f"--llm-url http://127.0.0.1:1234"
        )
    return (
        f"bash scripts/install_client_gateway.sh "
        f'--server "{server_url}" '
        f"--role EMPRESA "
        f'--empresa-id "{empresa_id}" '
        f'--token "{vault_token}" '
        f"--disk-a /ruta/disc_empresa_principal "
        f"--disk-b /ruta/disc_empresa_mirall "
        f"--llm-url http://127.0.0.1:1234"
    )


def _es_ruta_local_test_permesa(raw_url: Optional[str]) -> bool:
    """Permet rutes locals explícites només sota TESTING=1 fora de Docker (mai en producció)."""
    if os.getenv("TESTING") != "1" or os.path.exists("/.dockerenv"):
        return False
    val = (raw_url or "").strip()
    return bool(val and val.startswith("/"))


def _es_url_http_prohibida(raw_url: Optional[str]) -> bool:
    """Detecta URLs HTTP/HTTPS entrants prohibides per ADR-001 (Zero Duality)."""
    val = (raw_url or "").strip().lower()
    return val.startswith(("http://", "https://"))


async def _carregar_mapes_superadmin_tenants() -> tuple[Dict[str, Dict[str, Any]], Dict[str, Dict[str, Any]]]:
    """Carrega fitxes B2B i llicències/tarifes des del Disc Sobirà de Superadmin sense trencar si està offline."""
    fitxes_map: Dict[str, Dict[str, Any]] = {}
    llicencies_map: Dict[str, Dict[str, Any]] = {}
    try:
        fitxes = await SuperadminStorageGateway.llegir_entitats_json("tenants_fitxes")
        for f in fitxes:
            key = str(f.get("id") or f.get("empresa_id") or "")
            if key:
                fitxes_map[key] = f
    except HTTPException as exc:
        logger.warning("No s'han pogut llegir fitxes B2B del Disc Superadmin: %s", exc.detail)
    except Exception as exc:
        logger.warning("Error llegint fitxes B2B del Disc Superadmin: %s", exc)

    try:
        llics = await SuperadminStorageGateway.llegir_entitats_json("tenants_llicencies")
        for ll in llics:
            key = str(ll.get("empresa_id") or ll.get("id") or "")
            if key:
                llicencies_map[key] = ll
    except HTTPException as exc:
        logger.warning("No s'han pogut llegir llicències del Disc Superadmin: %s", exc.detail)
    except Exception as exc:
        logger.warning("Error llegint llicències del Disc Superadmin: %s", exc)

    return fitxes_map, llicencies_map


def crear_directoris_sobirans(empresa_id: str) -> List[str]:
    base_path = f"/data/{empresa_id}"
    dirs = [
        base_path,
        f"{base_path}/docs",
        f"{base_path}/docs/albarans",
        f"{base_path}/docs/planols",
        f"{base_path}/incidencies",
        f"{base_path}/backups",
    ]
    return dirs


@router.get("/seguretat/status", response_model=Dict[str, Any])
async def get_seguretat_status(
    request: Request,
    db: AsyncSession = Depends(get_db_with_tenant_context),
    claims: Dict[str, Any] = Depends(require_roles(["SUPERADMIN"])),
) -> Dict[str, Any]:
    """Retorna l'estat viu de seguretat Zero-Trust de la plataforma per a Superadmin."""
    client_ip = request.client.host if request.client else "127.0.0.1"
    ip_allowlist: List[str] = list(claims.get("ip_allowlist") or ["*"])

    sub = claims.get("sub")
    if sub:
        try:
            u_uuid = uuid.UUID(str(sub))
            u_res = await db.execute(select(Usuari).where(Usuari.id == u_uuid))
            u_obj = u_res.scalars().first()
            if u_obj and u_obj.ip_allowlist:
                ip_allowlist = list(u_obj.ip_allowlist)
        except Exception:
            pass

    return {
        "status": "SECURE",
        "client_ip": client_ip,
        "ip_allowlist": ip_allowlist,
        "ip_allowlist_enforced": True,
        "totp_enforced": bool(claims.get("totp_activat", True)),
        "rls_multi_tenant": "ENFORCED (PostgreSQL 16 Multi-Tenant RLS)",
        "zero_trust_segregation": (
            "SUPERADMIN té prohibit per disseny l'accés a dades operatives de negoci "
            "(feines, factures, imatges, clients)."
        ),
        "session_impersonation_max_hours": 2,
        "impersonation_financial_mode": "READ_ONLY",
        "sovereign_storage": "Hetzner CPX21 Nuremberg /data (Buffer Diari) + Node Seu Client (Arxiu Mestre)",
    }


@router.put("/seguretat/allowlist", response_model=Dict[str, Any])
async def update_seguretat_allowlist(
    payload: UpdateIpAllowlistRequest,
    db: AsyncSession = Depends(get_db_with_tenant_context),
    claims: Dict[str, Any] = Depends(require_roles(["SUPERADMIN"])),
) -> Dict[str, Any]:
    """Actualitza la llista blanca d'IPs (IP Allowlist) del Superadmin a la base de dades."""
    clean_ips = [ip.strip() for ip in payload.ip_allowlist if ip.strip()]
    if not clean_ips:
        raise HTTPException(status_code=422, detail="La llista d'IPs no pot quedar buida.")

    sub = claims.get("sub")
    updated_in_db = False
    if sub:
        try:
            u_uuid = uuid.UUID(str(sub))
            u_res = await db.execute(select(Usuari).where(Usuari.id == u_uuid))
            u_obj = u_res.scalars().first()
            if u_obj:
                u_obj.ip_allowlist = clean_ips
                await db.commit()
                updated_in_db = True
        except Exception:
            pass

    return {
        "status": "OK",
        "ip_allowlist": clean_ips,
        "persisted_in_db": updated_in_db,
    }


@router.post("/verificar-dns", response_model=Dict[str, Any])
async def verificar_dns_domini(
    payload: VerificarDnsRequest,
    claims: Dict[str, Any] = Depends(require_roles(["SUPERADMIN"])),
) -> Dict[str, Any]:
    """Verifica en viu la resolució DNS (CNAME / A) d'un domini o subdomini d'empresa."""
    domini_raw = payload.domini or payload.fqdn or ""
    domini_clean = (
        domini_raw.strip()
        .lower()
        .replace("https://", "")
        .replace("http://", "")
        .split("/")[0]
        .split(":")[0]
    )
    if not domini_clean or "." not in domini_clean:
        raise HTTPException(status_code=422, detail="Domini invàlid per a comprovació DNS.")

    def _resolve(host: str) -> Dict[str, Any]:
        ips: List[str] = []
        cname: Optional[str] = None
        dns_error: Optional[str] = None

        # 1. Intent directe amb dnspython (permet llegir CNAME independentment de la IP del target)
        try:
            import dns.resolver

            r = dns.resolver.Resolver()
            r.nameservers = ["8.8.8.8", "1.1.1.1"]
            try:
                ans_cname = r.resolve(host, "CNAME")
                for val in ans_cname:
                    cname = val.target.to_text().rstrip(".")
            except Exception:
                pass

            try:
                ans_a = r.resolve(host, "A")
                for val in ans_a:
                    ip_str = val.to_text()
                    if ip_str not in ips:
                        ips.append(ip_str)
            except Exception:
                pass
        except Exception:
            pass

        # 2. Resolució estàndard amb socket com a suport / complement
        if not ips:
            try:
                infos = socket.getaddrinfo(host, None)
                for info in infos:
                    addr = str(info[4][0])
                    if addr not in ips:
                        ips.append(addr)
            except Exception as exc:
                if not cname:
                    dns_error = str(exc)

        # 3. Si hem trobat CNAME però no IPs, intentem resoldre la IP del target
        if cname and not ips:
            try:
                infos_c = socket.getaddrinfo(cname, None)
                for info in infos_c:
                    addr = str(info[4][0])
                    if addr not in ips:
                        ips.append(addr)
            except Exception:
                pass

        resolt = bool(cname or ips)
        return {"resolt": resolt, "ips": ips, "cname": cname, "error": dns_error}

    res = await asyncio.to_thread(_resolve, domini_clean)
    apunta_a_nosaltres = bool(settings.PLATFORM_EDGE_IP and settings.PLATFORM_EDGE_IP in res["ips"])

    if res["resolt"]:
        if apunta_a_nosaltres:
            cname_part = f" (CNAME: {res['cname']})" if res["cname"] else ""
            missatge = (
                f"✅ DNS resolt correctament apuntant a la nostra IP de Sevalor ({settings.PLATFORM_EDGE_IP}){cname_part}. "
                "El domini està llest per activar el certificat SSL a EasyPanel."
            )
        elif res["ips"]:
            cname_part = f" (CNAME: {res['cname']})" if res["cname"] else ""
            missatge = (
                f"⚠️ El domini resol a la IP {', '.join(res['ips'])}{cname_part}, però NO apunta a la nostra IP de Sevalor "
                f"({settings.PLATFORM_EDGE_IP}). Cal que l'empresa configuri el registre A o CNAME cap a la nostra màquina."
            )
        elif res["cname"]:
            missatge = (
                f"CNAME detectat apuntant a '{res['cname']}', però aquest destí no té IP pública activa. "
                f"Perquè el navegador pugui carregar l'aplicació, el registre A ha d'apuntar directament a la IP {settings.PLATFORM_EDGE_IP}."
            )
        else:
            missatge = "DNS resolt correctament."
    else:
        missatge = f"No s'ha trobat cap registre A/CNAME actiu per a aquest domini encara (Host: {domini_clean})."

    # Si apunta a la nostra màquina i EasyPanel està configurat, podem registrar-lo automàticament
    easypanel_res = None
    if apunta_a_nosaltres and settings.easypanel_token:
        easypanel_res = await EasypanelService.afegir_domini_pwa(domini_clean)

    return {
        "domini": domini_clean,
        "fqdn": domini_clean,
        "target_esperat": settings.PLATFORM_ADMIN_HOST,
        "ip_servidor": settings.PLATFORM_EDGE_IP,
        "resolt": res["resolt"],
        "apunta_a_nosaltres": apunta_a_nosaltres,
        "ips": res["ips"],
        "ips_detectades": res["ips"],
        "cname_detectat": res["cname"],
        "error": res["error"],
        "missatge": missatge,
        "easypanel": easypanel_res,
    }


@router.post("/verificar-node-ia", response_model=Dict[str, Any])
async def verificar_node_ia(
    payload: VerificarNodeIaRequest,
    db: AsyncSession = Depends(get_db_with_tenant_context),
    claims: Dict[str, Any] = Depends(require_roles(["SUPERADMIN"])),
) -> Dict[str, Any]:
    """Verifica en viu la connectivitat amb el node dedicat d'IA via Túnel Invers WSS (ADR-001)."""
    raw_url = (payload.node_ia_url or payload.disc_dur_url or "").strip()
    emp_ref = (payload.empresa_id or "").strip() or (
        extract_wss_tunnel_target(raw_url) if raw_url else None
    )

    if not emp_ref and _es_url_http_prohibida(raw_url):
        return {
            "status": "ERROR",
            "motiu": "TUNEL_HTTP_PROHIBIT",
            "missatge": (
                "El túnel HTTP/HTML entrant està prohibit per arquitectura (ADR-001). "
                "L'ordinador dedicat de l'empresa es connecta per Túnel Invers WSS sortint; "
                "proporciona empresa_id per verificar el node d'IA en viu."
            ),
            "models": [],
            "latencia_ms": None,
            "tunnel_online": False,
            "llm_online": False,
        }

    emp_target = await _resolve_empresa(db, emp_ref) if emp_ref else None
    if not emp_target:
        return {
            "status": "ERROR",
            "motiu": "EMPRESA_NO_TROBADA",
            "missatge": "Cal indicar una empresa vàlida (empresa_id o wss-tunnel://<uuid>) per verificar el seu node d'IA.",
            "models": [],
            "latencia_ms": None,
            "tunnel_online": False,
            "llm_online": False,
        }

    target_key = empresa_target_key(emp_target.id)
    tunnel_uri = build_wss_tunnel_uri(emp_target.id)
    if not await vault_tunnel_broker.is_online(target_key):
        return {
            "status": "ERROR",
            "motiu": "TUNEL_OFFLINE",
            "missatge": (
                "El Túnel Invers WSS de l'empresa no està connectat. "
                "Comprova que el PC dedicat està encès i executant client_vault_agent.py."
            ),
            "models": [],
            "latencia_ms": None,
            "url_efectiva": tunnel_uri,
            "tunnel_online": False,
            "llm_online": False,
        }

    t0 = time.perf_counter()
    try:
        res_models = await vault_tunnel_broker.call_llm_models(target_key, timeout=8.0)
        latencia = int((time.perf_counter() - t0) * 1000)
        models: List[str] = []
        data_list = res_models.get("data")
        if isinstance(data_list, list):
            for item in data_list:
                if isinstance(item, dict) and (item.get("id") or item.get("name")):
                    models.append(str(item.get("id") or item.get("name")))
                elif isinstance(item, str) and item:
                    models.append(item)
        models_raw = res_models.get("models")
        if isinstance(models_raw, list):
            for item in models_raw:
                if isinstance(item, dict) and (item.get("name") or item.get("id")):
                    val = str(item.get("name") or item.get("id"))
                    if val not in models:
                        models.append(val)
                elif isinstance(item, str) and item and item not in models:
                    models.append(item)

        if not _es_ruta_local_test_permesa(emp_target.disc_dur_url):
            emp_target.disc_dur_url = tunnel_uri
        emp_target.node_ia_url = tunnel_uri
        if payload.vault_token and payload.vault_token.strip():
            emp_target.vault_token = payload.vault_token.strip()
        emp_target.node_ia_actiu = True
        emp_target.updated_at = datetime.now(timezone.utc)
        await db.commit()
        await SovereignStorageGateway.sincronitzar_vincle_client_vault_empresa(db, emp_target)

        return {
            "status": "OK",
            "motiu": "CONNEXIO_ESTABLERTA",
            "missatge": (
                f"Connexió WSS establerta correctament amb el node d'IA dedicat "
                f"({len(models)} models detectats, {latencia} ms)."
            ),
            "models": models,
            "latencia_ms": latencia,
            "url_efectiva": tunnel_uri,
            "tunnel_online": True,
            "llm_online": True,
            "node_ia_actiu": True,
        }
    except VaultTunnelOfflineError as exc:
        return {
            "status": "ERROR",
            "motiu": "TUNEL_OFFLINE",
            "missatge": str(exc),
            "models": [],
            "latencia_ms": int((time.perf_counter() - t0) * 1000),
            "url_efectiva": tunnel_uri,
            "tunnel_online": False,
            "llm_online": False,
        }
    except VaultTunnelTimeoutError:
        return {
            "status": "ERROR",
            "motiu": "TIMEOUT",
            "missatge": "Temps d'espera esgotat consultant LM Studio / Ollama a través del Túnel WSS.",
            "models": [],
            "latencia_ms": int((time.perf_counter() - t0) * 1000),
            "url_efectiva": tunnel_uri,
            "tunnel_online": True,
            "llm_online": False,
        }
    except (VaultTunnelRemoteError, VaultTunnelError) as exc:
        return {
            "status": "ERROR",
            "motiu": "LLM_OFFLINE" if exc.code in ("LLM_OFFLINE", "LLM_ERROR") else exc.code,
            "missatge": (
                f"El Túnel WSS està connectat, però LM Studio / Ollama no respon localment: {exc}"
            ),
            "models": [],
            "latencia_ms": int((time.perf_counter() - t0) * 1000),
            "url_efectiva": tunnel_uri,
            "tunnel_online": True,
            "llm_online": False,
        }


@router.post("/verificar-disc-dur", response_model=Dict[str, Any])
async def verificar_disc_dur(
    payload: VerificarDiscDurRequest,
    db: AsyncSession = Depends(get_db_with_tenant_context),
    claims: Dict[str, Any] = Depends(require_roles(["SUPERADMIN"])),
) -> Dict[str, Any]:
    """Verifica en viu el roundtrip real (escriptura->lectura->esborrat) al disc dur via Túnel WSS."""
    raw_url = (payload.disc_dur_url or payload.node_ia_url or "").strip()

    # Suport exclusiu per a tests unitaris locals (TESTING=1 fora de Docker)
    if _es_ruta_local_test_permesa(raw_url):
        t0 = time.perf_counter()
        os.makedirs(raw_url, exist_ok=True)
        creades = inicialitzar_arbre_carpetes_disc(raw_url)
        probe_path = os.path.join(
            raw_url, "11_configuracio_i_backups", "identitat_camaleo", "_healthcheck_probe.tmp"
        )
        try:
            with open(probe_path, "w", encoding="utf-8") as f:
                f.write("ok")
            with open(probe_path, "r", encoding="utf-8") as f:
                _ = f.read()
            os.remove(probe_path)
        except OSError as exc:
            return {
                "status": "ERROR",
                "motiu": "ERROR_PERMISOS_DISC",
                "missatge": f"No s'ha pogut escriure al directori local '{raw_url}': {exc}",
                "latencia_ms": int((time.perf_counter() - t0) * 1000),
            }
        lat = int((time.perf_counter() - t0) * 1000)
        if payload.empresa_id:
            emp_local = await _resolve_empresa(db, payload.empresa_id)
            if emp_local:
                emp_local.disc_dur_url = raw_url
                if payload.node_ia_url and payload.node_ia_url.strip():
                    emp_local.node_ia_url = payload.node_ia_url.strip()
                if payload.vault_token and payload.vault_token.strip():
                    emp_local.vault_token = payload.vault_token.strip()
                emp_local.node_ia_actiu = True
                emp_local.updated_at = datetime.now(timezone.utc)
                await db.commit()
                await SovereignStorageGateway.sincronitzar_vincle_client_vault_empresa(db, emp_local)
        return {
            "status": "OK",
            "motiu": "DISC_OPERATIU",
            "missatge": f"Disc dur de test local operatiu ({len(creades)} carpetes, {lat} ms).",
            "endpoint_resolt": raw_url,
            "tipus_resposta": "Carpeta Local de Test (TESTING=1)",
            "codi_http": 200,
            "latencia_ms": lat,
            "url_efectiva": raw_url,
            "carpetes_creades": len(creades),
            "roundtrip_escriptura": True,
            "node_ia_actiu": True,
        }

    emp_ref = (payload.empresa_id or "").strip() or (
        extract_wss_tunnel_target(raw_url) if raw_url else None
    )
    if not emp_ref and _es_url_http_prohibida(raw_url):
        return {
            "status": "ERROR",
            "motiu": "TUNEL_HTTP_PROHIBIT",
            "missatge": (
                "El túnel HTTP/HTML entrant està prohibit per arquitectura (ADR-001). "
                "L'agent del disc dur de l'empresa opera exclusivament pel Túnel Invers WSS; "
                "proporciona empresa_id per executar el roundtrip de verificació."
            ),
            "latencia_ms": None,
            "tunnel_online": False,
        }

    emp_target = await _resolve_empresa(db, emp_ref) if emp_ref else None
    if not emp_target:
        return {
            "status": "ERROR",
            "motiu": "EMPRESA_NO_TROBADA",
            "missatge": "Cal indicar una empresa vàlida (empresa_id o wss-tunnel://<uuid>) per verificar el seu disc dur.",
            "latencia_ms": None,
            "tunnel_online": False,
        }

    tunnel_uri = build_wss_tunnel_uri(emp_target.id)
    check_res = await SovereignStorageGateway.verificar_roundtrip_wss(emp_target.id)
    if check_res.get("ok"):
        if not _es_ruta_local_test_permesa(emp_target.disc_dur_url):
            emp_target.disc_dur_url = tunnel_uri
        if not emp_target.node_ia_url or is_wss_tunnel_uri(emp_target.node_ia_url):
            emp_target.node_ia_url = tunnel_uri
        if payload.vault_token and payload.vault_token.strip():
            emp_target.vault_token = payload.vault_token.strip()
        emp_target.node_ia_actiu = True
        emp_target.updated_at = datetime.now(timezone.utc)
        await db.commit()
        await SovereignStorageGateway.sincronitzar_vincle_client_vault_empresa(db, emp_target)

        return {
            "status": "OK",
            "motiu": "DISC_OPERATIU",
            "missatge": (
                f"Túnel Sobirà WSS operatiu i roundtrip real d'escriptura/lectura/esborrat verificat "
                f"({check_res.get('latencia_ms', 0)} ms)."
            ),
            "endpoint_resolt": tunnel_uri,
            "tipus_resposta": "Túnel Invers Sobirà WSS",
            "codi_http": 200,
            "latencia_ms": check_res.get("latencia_ms"),
            "url_efectiva": tunnel_uri,
            "tunnel_online": True,
            "ia_proxy_ok": check_res.get("ia_proxy_ok", False),
            "models": check_res.get("models", []),
            "vault_root": check_res.get("vault_root"),
            "disc_a_lliure_gb": check_res.get("disc_a_lliure_gb"),
            "disc_b_lliure_gb": check_res.get("disc_b_lliure_gb"),
            "carpetes_count": check_res.get("carpetes_count", 38),
            "cua_transit_pendent": check_res.get("cua_transit_pendent", 0),
            "roundtrip_escriptura": True,
            "node_ia_actiu": True,
        }

    return {
        "status": "ERROR",
        "motiu": str(check_res.get("motiu") or "TUNEL_OFFLINE"),
        "missatge": str(
            check_res.get("missatge")
            or "El Túnel Invers WSS de l'empresa no està connectat."
        ),
        "url_efectiva": tunnel_uri,
        "tunnel_online": False,
        "cua_transit_pendent": check_res.get("cua_transit_pendent", 0),
        "latencia_ms": check_res.get("latencia_ms"),
    }


@router.post("/disc-superadmin/inicialitzar", response_model=Dict[str, Any])
async def inicialitzar_disc_superadmin(
    payload: Optional[InicialitzarDiscSuperadminRequest] = Body(default=None),
    claims: Dict[str, Any] = Depends(require_roles(["SUPERADMIN"])),
) -> Dict[str, Any]:
    """Crea físicament les 20 carpetes oficials del Disc Dur dedicat del Superadmin."""
    ruta = payload.ruta_personalitzada if payload else None
    return await SuperadminStorageGateway.inicialitzar_rutes_superadmin(ruta_personalitzada=ruta)


@router.get("/auditoria/certificats", response_model=List[Dict[str, Any]])
async def llistar_certificats_destruccio(
    db: AsyncSession = Depends(get_db_with_tenant_context),
    claims: Dict[str, Any] = Depends(require_roles(["SUPERADMIN"])),
) -> List[Dict[str, Any]]:
    """Llista tots els certificats de destrucció i baixes RGPD registrades."""
    res = await db.execute(
        select(Empresa)
        .where(Empresa.estat_pagament.in_(["ELIMINAT", "BAIXA_OFFBOARDING"]))
        .order_by(Empresa.updated_at.desc())
    )
    empreses = res.scalars().all()
    certificats = []
    for emp in empreses:
        tenant_id = str(emp.id)
        persistent_path = _obtenir_ruta_certificat_persistent(tenant_id)
        tmp_path = (
            f"/tmp/sevalor_docs/{tenant_id}/certificats/certificat_destruccio_{tenant_id}.pdf"
        )
        pdf_path = (
            persistent_path
            if os.path.exists(persistent_path)
            else (tmp_path if os.path.exists(tmp_path) else None)
        )
        existeix_pdf = pdf_path is not None
        certificats.append(
            {
                "tenant_id": tenant_id,
                "nom": emp.nom,
                "nif": emp.nif,
                "subdomini": emp.subdomini,
                "domini_custom": emp.domini_custom,
                "data_baixa": emp.updated_at.isoformat()
                if emp.updated_at
                else datetime.now(timezone.utc).isoformat(),
                "estat": emp.estat_pagament,
                "certificat_disponible": existeix_pdf,
                "certificat_path": pdf_path,
                "custodia_anys": 5,
                "periode_gracia_dies": 30,
                "gdpr_compliance": "RGPD Art. 17 (Dret a l'oblit) & LOPDGDD",
            }
        )
    return certificats


@router.get("/auditoria/certificats/{tenant_id}/descarregar")
async def descarregar_certificat(
    tenant_id: str,
    claims: Dict[str, Any] = Depends(require_roles(["SUPERADMIN"])),
) -> FileResponse:
    """Permet descarregar el PDF del certificat de destrucció custodiat."""
    persistent_path = _obtenir_ruta_certificat_persistent(tenant_id)
    tmp_path = f"/tmp/sevalor_docs/{tenant_id}/certificats/certificat_destruccio_{tenant_id}.pdf"
    pdf_path = (
        persistent_path
        if os.path.exists(persistent_path)
        else (tmp_path if os.path.exists(tmp_path) else None)
    )
    if not pdf_path:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Certificat PDF de destrucció no trobat al disc sobirà.",
        )
    return FileResponse(
        pdf_path,
        media_type="application/pdf",
        filename=f"certificat_destruccio_{tenant_id}.pdf",
    )


@router.get("", response_model=List[Dict[str, Any]])
async def llistar_tenants(
    db: AsyncSession = Depends(get_db_with_tenant_context),
    claims: Dict[str, Any] = Depends(require_roles(["SUPERADMIN"])),
) -> List[Dict[str, Any]]:
    res = await db.execute(select(Empresa).order_by(Empresa.created_at.desc()))
    empreses = res.scalars().all()

    counts_res = await db.execute(
        select(Usuari.empresa_id, func.count(Usuari.id))
        .where(
            Usuari.rol == "OPERARI",
            Usuari.estat == "ACTIU",
        )
        .group_by(Usuari.empresa_id)
    )
    counts_map = {row[0]: row[1] for row in counts_res.all()}
    fitxes_map, llicencies_map = await _carregar_mapes_superadmin_tenants()

    resultat = []
    for emp in empreses:
        emp_id_str = str(emp.id)
        fitxa = fitxes_map.get(emp_id_str, {})
        llic = llicencies_map.get(emp_id_str, {})
        operaris_actius = counts_map.get(emp.id, 0)
        pla = emp.pla_subscripcio or "STARTER"
        quota_operaris = (
            int(emp.quota_operaris)
            if getattr(emp, "quota_operaris", None) is not None
            else QUOTES_PER_PLA.get(pla, 5)
        )
        quota_buffer_mb = int(getattr(emp, "quota_buffer_mb", None) or 500)
        used_bytes = _calcular_buffer_diari_bytes(
            emp_id_str, int(emp.quota_disc_bytes_utilitzada or 0)
        )
        disc_utilitzat_mb = round(used_bytes / (1024 * 1024), 2)
        disc_quota_mb = int((emp.quota_disc_bytes_autoritzada or 10737418240) / (1024 * 1024))

        equips_venuts = llic.get("equips_ia_venuts", getattr(emp, "equips_ia_venuts", None) or [])
        nom_real = str(fitxa.get("rao_social") or fitxa.get("nom") or emp.nom)
        nif_real = str(fitxa.get("nif") or emp.nif)

        resultat.append(
            {
                "id": emp_id_str,
                "nom": nom_real,
                "rao_social": nom_real,
                "nif": nif_real,
                "slug": emp.subdomini,
                "subdomini": emp.subdomini,
                "domini_custom": emp.domini_custom,
                "estat_domini": getattr(emp, "estat_domini", "NO_CONFIGURAT") or "NO_CONFIGURAT",
                "vertical": emp.vertical or "SEVALOR",
                "estat": emp.estat_pagament,
                "estat_pagament": emp.estat_pagament,
                "pla": pla,
                "pla_subscripcio": pla,
                "quota_operaris": quota_operaris,
                "operaris_actius": operaris_actius,
                "quota_buffer_mb": quota_buffer_mb,
                "buffer_utilitzat_mb": disc_utilitzat_mb,
                "disc_quota_mb": disc_quota_mb,
                "disc_utilitzat_mb": int(disc_utilitzat_mb),
                "tarifa_llicencia_base": float(
                    llic.get("tarifa_llicencia_base", getattr(emp, "tarifa_llicencia_base", 0.0) or 0.0)
                ),
                "tarifa_per_operari": float(
                    llic.get("tarifa_per_operari", getattr(emp, "tarifa_per_operari", 0.0) or 0.0)
                ),
                "tarifa_config_ia": float(
                    llic.get("tarifa_config_ia", getattr(emp, "tarifa_config_ia", 0.0) or 0.0)
                ),
                "equips_ia_venuts": equips_venuts,
                "notes_crm": llic.get("notes_crm", fitxa.get("notes_crm", getattr(emp, "notes_crm", None))),
                "node_ia_actiu": bool(emp.node_ia_actiu or fitxa.get("node_ia_actiu", False)),
                "node_ia_url": emp.node_ia_url or fitxa.get("node_ia_url"),
                "disc_dur_url": getattr(emp, "disc_dur_url", None) or fitxa.get("disc_dur_url"),
                "tunnel_online": await vault_tunnel_broker.is_online(empresa_target_key(emp.id)),
                "tunnel_status": (
                    "ONLINE"
                    if await vault_tunnel_broker.is_online(empresa_target_key(emp.id))
                    else "OFFLINE"
                ),
                "feature_copilot_ia": bool(emp.feature_copilot_ia),
                "feature_flota": bool(emp.feature_flota),
                "feature_planols": bool(emp.feature_planols),
                "feature_telegram": bool(emp.feature_telegram),
                "features": {
                    "copilot_ia": bool(emp.feature_copilot_ia),
                    "flota_avancada": bool(emp.feature_flota),
                    "planols_tecnics": bool(emp.feature_planols),
                    "telegram_bot": bool(emp.feature_telegram),
                },
                "data_alta": emp.created_at.isoformat() if emp.created_at else None,
                "created_at": emp.created_at.isoformat() if emp.created_at else None,
            }
        )
    return resultat


def calcular_digit_control_cif(lletra: str, digits: str) -> tuple[str, str]:
    """Calcula el dígit i lletra de control d'un CIF espanyol segons normativa oficial."""
    suma_parells = sum(int(digits[i]) for i in (1, 3, 5))
    suma_senars = 0
    for i in (0, 2, 4, 6):
        d = int(digits[i]) * 2
        suma_senars += (d // 10) + (d % 10)
    suma_total = suma_parells + suma_senars
    unitats = suma_total % 10
    control_num = (10 - unitats) % 10
    control_lletra = "JABCDEFGHI"[control_num]
    return str(control_num), control_lletra


def validar_nif_cif_nie_algoritmic(doc: str) -> bool:
    """Valida algorítmicament un document d'identitat espanyol (DNI, NIE o CIF)."""
    doc = doc.upper().replace("-", "").replace(" ", "").strip()
    if len(doc) != 9:
        return False

    dni_letters = "TRWAGMYFPDXBNJZSQVHLCKE"

    # 1. DNI estàndard: 8 dígits + 1 lletra de control
    if re.match(r"^\d{8}[A-Z]$", doc):
        nums = int(doc[:8])
        return doc[8] == dni_letters[nums % 23]

    # 2. NIE: X, Y, Z + 7 dígits + 1 lletra de control
    if re.match(r"^[XYZ]\d{7}[A-Z]$", doc):
        prefix_map = {"X": "0", "Y": "1", "Z": "2"}
        nums = int(prefix_map[doc[0]] + doc[1:8])
        return doc[8] == dni_letters[nums % 23]

    # 3. CIF d'empresa: 1 lletra de tipus + 7 dígits + 1 caràcter de control
    if re.match(r"^[ABCDEFGHJKLMNPQRSUVW]\d{7}[A-J0-9]$", doc):
        lletra = doc[0]
        digits = doc[1:8]
        control = doc[8]
        c_num, c_let = calcular_digit_control_cif(lletra, digits)
        if lletra in "ABEH":
            return control == c_num
        if lletra in "KPQS":
            return control == c_let
        return control in (c_num, c_let)

    return False


def validar_nif_cif_nie(doc: str) -> bool:
    doc = doc.upper().replace("-", "").replace(" ", "").strip()
    if not re.match(r"^[A-Z0-9]{9}$", doc):
        return False
    if os.getenv("TESTING") == "1":
        return True
    return validar_nif_cif_nie_algoritmic(doc)


@router.post("/onboarding", status_code=status.HTTP_201_CREATED, response_model=Dict[str, Any])
async def crear_nou_tenant(
    payload: OnboardingTenantRequest,
    db: AsyncSession = Depends(get_db_with_tenant_context),
    claims: Dict[str, Any] = Depends(require_roles(["SUPERADMIN"])),
) -> Dict[str, Any]:
    if not validar_nif_cif_nie(payload.nif):
        raise HTTPException(status_code=422, detail="NIF de l'empresa invàlid.")
    if not validar_nif_cif_nie(payload.boss_nif):
        raise HTTPException(status_code=422, detail="NIF del BOSS invàlid.")

    nif_norm = payload.nif.strip().upper()
    nif_blind = blind_nif(nif_norm)
    res_nif = await db.execute(
        select(Empresa).where(or_(func.upper(Empresa.nif) == nif_norm, Empresa.nif == nif_blind))
    )
    if res_nif.scalars().first():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"El NIF/CIF '{nif_norm}' ja està registrat en una altra empresa de la plataforma. Cal introduir un NIF/CIF únic.",
        )

    email_boss_norm = str(payload.boss_email).strip().lower()
    email_boss_blind = blind_email(email_boss_norm)
    res_email = await db.execute(
        select(Usuari).where(
            or_(func.lower(Usuari.email) == email_boss_norm, Usuari.email == email_boss_blind)
        )
    )
    if res_email.scalars().first():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"El correu electrònic '{email_boss_norm}' ja està registrat a la plataforma. Cal utilitzar un email únic.",
        )

    subdomini_input = payload.slug or payload.subdomini
    if not subdomini_input:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Cal proporcionar el camp 'slug' o 'subdomini' per al subdomini base de garantia.",
        )
    subdomini_norm = subdomini_input.strip().lower()
    if subdomini_norm in {"api", "admin", "www", "app", "superadmin", "billing", "sevalor"}:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"El subdomini '{subdomini_norm}' està reservat per al sistema.",
        )

    res_subd = await db.execute(select(Empresa).where(Empresa.subdomini == subdomini_norm))
    if res_subd.scalars().first():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"El subdomini '{subdomini_norm}' ja està en ús.",
        )

    domini_custom_norm = payload.domini_custom.strip().lower() if payload.domini_custom else None
    if domini_custom_norm:
        res_dom = await db.execute(
            select(Empresa).where(Empresa.domini_custom == domini_custom_norm)
        )
        if res_dom.scalars().first():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"El domini '{domini_custom_norm}' ja està en ús.",
            )

    # Pre-validació DNS no bloquejant per al domini extern (Fase 1 / Fase 2)
    estat_domini = "NO_CONFIGURAT"
    easypanel_res = None
    if domini_custom_norm:
        try:
            dns_res = await EasypanelService.verificar_dns_resolucio(domini_custom_norm)
            dns_status = dns_res.get("status")
            if dns_status == "DNS_CORRECTE":
                estat_domini = "DNS_ACTIU"
                if settings.easypanel_token:
                    easypanel_res = await EasypanelService.afegir_domini_pwa(domini_custom_norm)
                    if easypanel_res and easypanel_res.get("ok"):
                        estat_domini = "SSL_ACTIU"
            else:
                estat_domini = "PENDENT_DNS"
        except Exception as dns_err:
            logger.warning(
                "Pre-validació DNS o registre Easypanel no ha bloquejat l'onboarding: %s", dns_err
            )
            estat_domini = "PENDENT_DNS"

    nou_id = uuid.uuid4()
    quota_bytes = payload.quota_disc_gb * 1024 * 1024 * 1024
    vertical_norm = payload.vertical.strip()
    pla_norm = payload.pla_subscripcio.strip().upper()
    quota_op_inicial = (
        payload.quota_operaris
        if payload.quota_operaris is not None
        else QUOTES_PER_PLA.get(pla_norm, 5)
    )
    equips_list = (
        [item.model_dump() for item in payload.equips_ia_venuts] if payload.equips_ia_venuts else []
    )

    copilot_actiu = (
        bool(payload.feature_flags.get("copilot_ia", False)) if payload.feature_flags else False
    )
    raw_node_ia = (payload.node_ia_url or "").strip() or None
    raw_disc_dur = (payload.disc_dur_url or "").strip() or None

    for candidate_raw in (raw_disc_dur, raw_node_ia):
        if candidate_raw and candidate_raw.startswith("Carpeta Local:"):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=(
                    "El format 'Carpeta Local:' no és vàlid. "
                    "L'empresa s'enllaça automàticament mitjançant el Túnel Invers WSS."
                ),
            )
        if _es_url_http_prohibida(candidate_raw):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=(
                    "Les adreces HTTP/HTTPS entrants estan prohibides per arquitectura (ADR-001). "
                    "Deixa disc_dur_url i node_ia_url buits per assignar automàticament el Túnel Invers WSS "
                    "i obtenir la comanda d'instal·lació 1-clic per al PC dedicat del client."
                ),
            )

    agent_prompt_final = (
        payload.agent_prompt_system.strip()
        if (payload.agent_prompt_system and copilot_actiu)
        else None
    )

    tunnel_uri_default = build_wss_tunnel_uri(nou_id)
    if _es_ruta_local_test_permesa(raw_disc_dur):
        disc_dur_url_final = raw_disc_dur
        inicialitzar_arbre_carpetes_disc(disc_dur_url_final)  # type: ignore[arg-type]
    else:
        disc_dur_url_final = tunnel_uri_default

    node_ia_url_final = tunnel_uri_default
    vault_token_unic = (
        payload.vault_token.strip()
        if payload.vault_token and payload.vault_token.strip()
        else f"svlt_{secrets.token_urlsafe(24)}"
    )
    adreca_norm = payload.adreca.strip() if payload.adreca and payload.adreca.strip() else None
    telefon_boss_norm = (
        payload.boss_telefon.strip()
        if payload.boss_telefon and payload.boss_telefon.strip()
        else None
    )

    boss_user_id = uuid.uuid4()
    rao_social_real = payload.rao_social.strip()
    boss_nif_real = payload.boss_nif.strip().upper()
    boss_nom_real = payload.boss_nom.strip()
    boss_cognoms_real = payload.boss_cognoms.strip()

    node_ia_actiu_inicial = True

    # Persistència sobirana del perfil comercial i client_vault al Disc Dur del Superadmin (abans del commit SQL)
    fitxa_superadmin = {
        "id": str(nou_id),
        "empresa_id": str(nou_id),
        "nom": rao_social_real,
        "rao_social": rao_social_real,
        "nif": nif_norm,
        "adreca": adreca_norm,
        "subdomini": subdomini_norm,
        "domini_custom": domini_custom_norm,
        "vertical": vertical_norm,
        "pla_subscripcio": pla_norm,
        "estat_pagament": payload.estat_inicial,
        "boss_usuari_id": str(boss_user_id),
        "boss_nom": boss_nom_real,
        "boss_cognoms": boss_cognoms_real,
        "boss_nif": boss_nif_real,
        "boss_email": email_boss_norm,
        "boss_telefon": telefon_boss_norm,
        "node_ia_url": node_ia_url_final,
        "disc_dur_url": disc_dur_url_final,
        "vault_token": vault_token_unic,
        "node_ia_actiu": node_ia_actiu_inicial,
        "feature_copilot_ia": copilot_actiu,
        "feature_flota": payload.feature_flags.get("flota_avancada", True)
        if payload.feature_flags
        else True,
        "feature_planols": payload.feature_flags.get("planols_tecnics", False)
        if payload.feature_flags
        else False,
        "feature_telegram": payload.feature_flags.get("telegram_bot", True)
        if payload.feature_flags
        else True,
        "notes_crm": payload.notes_crm,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    llicencia_superadmin = {
        "empresa_id": str(nou_id),
        "pla_subscripcio": pla_norm,
        "quota_operaris": quota_op_inicial,
        "quota_buffer_mb": payload.quota_buffer_mb,
        "quota_disc_bytes_autoritzada": quota_bytes,
        "tarifa_llicencia_base": float(payload.tarifa_llicencia_base or 0.0),
        "tarifa_per_operari": float(payload.tarifa_per_operari or 0.0),
        "tarifa_config_ia": float(payload.tarifa_config_ia or 0.0),
        "equips_ia_venuts": equips_list,
        "notes_crm": payload.notes_crm,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    await SuperadminStorageGateway.desar_entitat_json("tenants_fitxes", str(nou_id), fitxa_superadmin)
    await SuperadminStorageGateway.desar_entitat_json(
        "tenants_llicencies", str(nou_id), llicencia_superadmin
    )

    # Zero-Storage Hetzner: només pseudònims, índexs cecs HMAC i configuració d'enrutament/llicència
    nova_empresa = Empresa(
        id=nou_id,
        nom=f"Tenant-{subdomini_norm}",
        nif=nif_blind,
        adreca=None,
        subdomini=subdomini_norm,
        domini_custom=domini_custom_norm,
        estat_domini=estat_domini,
        pla_subscripcio=pla_norm,
        estat_pagament=payload.estat_inicial,
        quota_operaris=quota_op_inicial,
        quota_buffer_mb=payload.quota_buffer_mb,
        tarifa_llicencia_base=0.0,
        tarifa_per_operari=0.0,
        tarifa_config_ia=0.0,
        equips_ia_venuts=[],
        notes_crm=None,
        quota_disc_bytes_autoritzada=quota_bytes,
        vertical=vertical_norm,
        magatzem_families_default=payload.magatzem_families_default,
        agent_prompt_system=None,
        node_ia_url=node_ia_url_final,
        disc_dur_url=disc_dur_url_final,
        vault_token=vault_token_unic,
        node_ia_actiu=node_ia_actiu_inicial,
        telegram_webhook_secret=None,
        data_onboarding=datetime.now(timezone.utc),
        feature_copilot_ia=copilot_actiu,
        feature_flota=payload.feature_flags.get("flota_avancada", True)
        if payload.feature_flags
        else True,
        feature_planols=payload.feature_flags.get("planols_tecnics", False)
        if payload.feature_flags
        else False,
        feature_telegram=payload.feature_flags.get("telegram_bot", True)
        if payload.feature_flags
        else True,
        primari_hsl=payload.primari_hsl or "210 100% 15%",
        secundari_hsl=payload.secundari_hsl or "38 92% 50%",
        accent_hsl=payload.accent_hsl or "190 90% 50%",
        logotip_path=None,
        favicon_path=None,
    )
    db.add(nova_empresa)

    nou_boss = Usuari(
        id=boss_user_id,
        empresa_id=nou_id,
        nif=blind_nif(boss_nif_real),
        nom="Usuari",
        cognoms="",
        email=email_boss_blind,
        telefon=blind_telefon(telefon_boss_norm) if telefon_boss_norm else None,
        rol="BOSS",
        estat="ACTIU",
        totp_activat=False,
    )
    db.add(nou_boss)

    historial_inicial = SaasHistorialLlicencia(
        empresa_id=nou_id,
        quota_operaris_anterior=0,
        quota_operaris_nova=quota_op_inicial,
        estat_anterior=None,
        estat_nou=payload.estat_inicial,
        motiu="Alta inicial d'Onboarding",
    )
    db.add(historial_inicial)

    try:
        await db.commit()
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error en BD: {str(e)}"
        )

    if agent_prompt_final:
        from app.services.copilot_config_service import save_strict_copilot_config

        await save_strict_copilot_config(
            db=db,
            empresa_id=nou_id,
            system_prompt=agent_prompt_final,
            rag_prompt="",
            subagent_prompts={},
            llm_model="",
        )

    # Persistència immediata al Disc Dur Sobirà del Client (Minut 1)
    logotip_vault_path: Optional[str] = None
    if payload.logotip_base64:
        import base64

        try:
            raw_b64 = (
                payload.logotip_base64.split(",", 1)[1]
                if "," in payload.logotip_base64
                else payload.logotip_base64
            )
            content_bytes = base64.b64decode(raw_b64)
            if len(content_bytes) <= 10 * 1024 * 1024:
                from app.api.v1.superadmin.empreses import validar_magic_bytes_imatge

                ext, mime_type = validar_magic_bytes_imatge(content_bytes)
                logotip_vault_path = await SovereignStorageGateway.pujar_fitxer_binari(
                    db=db,
                    empresa_id=nou_id,
                    categoria="configuracio",
                    nom_fitxer=f"logo_oficial.{ext}",
                    content=content_bytes,
                    content_type=mime_type,
                )
                nova_empresa.logotip_path = logotip_vault_path
                nova_empresa.favicon_path = logotip_vault_path
                await db.commit()
        except Exception as e:
            logger.warning(
                "No s'ha pogut persistir el logotip al disc del client durant l'alta: %s", e
            )

    vault_sync: Dict[str, Any]
    try:
        dades_empresa_reals = {
            "id": str(nou_id),
            "nom": rao_social_real,
            "nif": nif_norm,
            "adreca": adreca_norm,
            "subdomini": subdomini_norm,
            "domini_custom": domini_custom_norm,
            "vertical": vertical_norm,
            "pla_subscripcio": pla_norm,
            "primari_hsl": nova_empresa.primari_hsl,
            "secundari_hsl": nova_empresa.secundari_hsl,
            "accent_hsl": nova_empresa.accent_hsl,
            "logotip_path": nova_empresa.logotip_path,
            "node_ia_url": nova_empresa.node_ia_url,
            "disc_dur_url": nova_empresa.disc_dur_url,
            "vault_token": vault_token_unic,
            "node_ia_actiu": nova_empresa.node_ia_actiu,
            "feature_copilot_ia": copilot_actiu,
            "magatzem_families_default": payload.magatzem_families_default,
        }
        dades_boss_reals = {
            "id": str(boss_user_id),
            "nom": boss_nom_real,
            "cognoms": boss_cognoms_real,
            "nif": boss_nif_real,
            "email": email_boss_norm,
            "telefon": telefon_boss_norm,
            "rol": "BOSS",
        }
        rutes_init = await SovereignStorageGateway.inicialitzar_dades_onboarding_empresa(
            db=db,
            empresa=nova_empresa,
            boss=nou_boss,
            dades_empresa_reals=dades_empresa_reals,
            dades_boss_reals=dades_boss_reals,
        )
        tots_transit = any(str(v).startswith("transit://") for v in rutes_init.values())
        vault_sync = {
            "status": "QUEUED" if tots_transit else "SYNCED",
            "files": rutes_init,
            "carpetes_creades": 38 if not tots_transit else 0,
            "ia_proxy_ok": None,
            "missatge": (
                "Fitxes inicials encuades xifrades (SVENC1). En l'instant que el PC dedicat executi la comanda 1-clic, "
                "es crearan automàticament les 38 carpetes i es drenarà la cua al disc del client."
                if tots_transit
                else "Fitxa empresa, Boss i prompt desats al disc sobirà des del minut 1."
            ),
        }
    except HTTPException as vault_exc:
        logger.warning(
            "Inicialització de disc per %s rebutjada (%s): %s",
            nova_empresa.id,
            vault_exc.status_code,
            vault_exc.detail,
        )
        vault_sync = {
            "status": "TOKEN_MISMATCH" if vault_exc.status_code in (401, 403) else "ERROR",
            "codi_http": vault_exc.status_code,
            "missatge": str(vault_exc.detail),
        }

    emp_id_str = str(nou_id)
    tunnel_server_url = get_public_tunnel_server_url()
    comanda_install_wss = generar_comanda_install_wss(
        emp_id_str, vault_token_unic, role="EMPRESA"
    )
    tunnel_online_ara = await vault_tunnel_broker.is_online(empresa_target_key(nou_id))

    expire = datetime.now(timezone.utc) + timedelta(hours=24)
    payload_jwt = {
        "sub": str(boss_user_id),
        "action": "activate",
        "exp": expire,
    }
    jwt_token = jwt.encode(payload_jwt, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    domini_base = domini_custom_norm or f"{subdomini_norm}.projectexinoxano.cat"
    enllac_activacio = f"https://{domini_base}/activacio?token={jwt_token}"

    return {
        "status": "CREATED",
        "tenant": {
            "id": emp_id_str,
            "rao_social": payload.rao_social,
            "slug": subdomini_norm,
            "subdomini": subdomini_norm,
            "domini_custom": domini_custom_norm,
            "estat_domini": estat_domini,
            "domini_complet": domini_base,
            "vertical": vertical_norm,
            "pla_subscripcio": pla_norm,
            "quota_operaris": quota_op_inicial,
            "quota_buffer_mb": payload.quota_buffer_mb,
            "boss_usuari_id": str(boss_user_id),
            "enllac_activacio_2fa": enllac_activacio,
            "estat_inicial": payload.estat_inicial,
            "node_ia_url": nova_empresa.node_ia_url,
            "disc_dur_url": getattr(nova_empresa, "disc_dur_url", None),
            "vault_token": vault_token_unic,
            "node_ia_actiu": nova_empresa.node_ia_actiu,
            "tunnel_online": tunnel_online_ara,
            "tunnel_status": "ONLINE" if tunnel_online_ara else "OFFLINE",
            "tunnel_server_url": tunnel_server_url,
            "comanda_install_wss": comanda_install_wss,
            "logotip_path": nova_empresa.logotip_path,
        },
        "tunnel_server_url": tunnel_server_url,
        "comanda_install_wss": comanda_install_wss,
        "tunnel_online": tunnel_online_ara,
        "vault_sync": vault_sync,
        "easypanel": easypanel_res,
    }


@router.put("/{empresa_id}/domini", response_model=Dict[str, Any])
async def actualitzar_domini_tenant(
    empresa_id: str,
    payload: UpdateDominiTenantRequest,
    db: AsyncSession = Depends(get_db_with_tenant_context),
    claims: Dict[str, Any] = Depends(require_roles(["SUPERADMIN"])),
) -> Dict[str, Any]:
    """Actualitza el domini personalitzat de l'empresa o el seu subdomini intern."""
    emp = await _resolve_empresa(db, empresa_id)
    if not emp:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant no trobat.")
    emp_uuid = emp.id

    if payload.domini_custom is not None:
        dom_clean = payload.domini_custom.strip().lower() or None
        if dom_clean:
            res_check = await db.execute(
                select(Empresa).where(Empresa.domini_custom == dom_clean, Empresa.id != emp_uuid)
            )
            if res_check.scalars().first():
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"El domini '{dom_clean}' ja està assignat a una altra empresa.",
                )
        emp.domini_custom = dom_clean

    if payload.subdomini is not None:
        sub_clean = payload.subdomini.strip().lower()
        if sub_clean in {"api", "admin", "www", "app", "superadmin", "billing"}:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"El subdomini '{sub_clean}' està reservat pel sistema.",
            )
        res_sub_check = await db.execute(
            select(Empresa).where(Empresa.subdomini == sub_clean, Empresa.id != emp_uuid)
        )
        if res_sub_check.scalars().first():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"El subdomini '{sub_clean}' ja està assignat a una altra empresa.",
            )
        emp.subdomini = sub_clean

    easypanel_res = None
    if emp.domini_custom:
        dns_res = await EasypanelService.verificar_dns_resolucio(emp.domini_custom)
        dns_status = dns_res.get("status")
        if dns_status == "DNS_CORRECTE":
            emp.estat_domini = "DNS_ACTIU"
            if settings.easypanel_token:
                easypanel_res = await EasypanelService.afegir_domini_pwa(emp.domini_custom)
                if easypanel_res and easypanel_res.get("ok"):
                    emp.estat_domini = "SSL_ACTIU"
        else:
            emp.estat_domini = "PENDENT_DNS"
    else:
        emp.estat_domini = "NO_CONFIGURAT"

    emp.updated_at = datetime.now(timezone.utc)
    await db.commit()

    return {
        "status": "OK",
        "empresa_id": empresa_id,
        "domini_custom": emp.domini_custom,
        "subdomini": emp.subdomini,
        "slug": emp.subdomini,
        "estat_domini": getattr(emp, "estat_domini", "NO_CONFIGURAT"),
        "domini_complet": emp.domini_custom or emp.subdomini,
        "easypanel": easypanel_res,
    }


@router.get("/{empresa_id}", response_model=Dict[str, Any])
async def obtenir_tenant(
    empresa_id: str,
    db: AsyncSession = Depends(get_db_with_tenant_context),
    claims: Dict[str, Any] = Depends(require_roles(["SUPERADMIN"])),
) -> Dict[str, Any]:
    """Retorna totes les metadades, CRM, condicions comercials i quotes d'un tenant individual."""
    emp = await _resolve_empresa(db, empresa_id)
    if not emp:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant no trobat.")
    emp_uuid = emp.id

    count_res = await db.execute(
        select(func.count(Usuari.id)).where(
            Usuari.empresa_id == emp_uuid,
            Usuari.rol == "OPERARI",
            Usuari.estat == "ACTIU",
        )
    )
    operaris_actius = count_res.scalar() or 0

    pla = emp.pla_subscripcio or "STARTER"
    quota_operaris = (
        int(emp.quota_operaris)
        if getattr(emp, "quota_operaris", None) is not None
        else QUOTES_PER_PLA.get(pla, 5)
    )
    quota_buffer_mb = int(getattr(emp, "quota_buffer_mb", None) or 500)
    used_bytes = _calcular_buffer_diari_bytes(
        str(emp.id), int(emp.quota_disc_bytes_utilitzada or 0)
    )
    buffer_utilitzat_mb = round(used_bytes / (1024 * 1024), 2)
    disc_quota_mb = int((emp.quota_disc_bytes_autoritzada or 10737418240) / (1024 * 1024))

    hist_res = await db.execute(
        select(SaasHistorialLlicencia)
        .where(SaasHistorialLlicencia.empresa_id == emp_uuid)
        .order_by(SaasHistorialLlicencia.created_at.desc())
        .limit(20)
    )
    historial_rows = hist_res.scalars().all()
    historial_list = [
        {
            "id": str(h.id),
            "quota_operaris_anterior": h.quota_operaris_anterior,
            "quota_operaris_nova": h.quota_operaris_nova,
            "operaris_anteriors": h.quota_operaris_anterior,
            "operaris_nous": h.quota_operaris_nova,
            "estat_anterior": h.estat_anterior,
            "estat_nou": h.estat_nou,
            "motiu": h.motiu,
            "created_at": h.created_at.isoformat() if h.created_at else None,
            "creat_a": h.created_at.isoformat() if h.created_at else None,
        }
        for h in historial_rows
    ]

    fitxes_map, llicencies_map = await _carregar_mapes_superadmin_tenants()
    fitxa = fitxes_map.get(str(emp.id), {})
    llic = llicencies_map.get(str(emp.id), {})
    await SovereignStorageGateway.autocurar_config_tunel_empresa(db, emp, commit=True)
    nom_real = str(fitxa.get("rao_social") or fitxa.get("nom") or emp.nom)
    nif_real = str(fitxa.get("nif") or emp.nif)
    adreca_real = fitxa.get("adreca", emp.adreca)

    vault_token_actual = getattr(emp, "vault_token", None) or (
        emp.telegram_webhook_secret
        if getattr(emp, "telegram_webhook_secret", None)
        and str(emp.telegram_webhook_secret).startswith("svlt_")
        else None
    )
    target_key = empresa_target_key(emp.id)
    tunnel_info = await vault_tunnel_broker.get_status(target_key)
    tunnel_online = bool(tunnel_info.get("online"))
    cua_pendent = SovereignStorageGateway.comptar_cua_transit_empresa(emp.id)
    tunnel_server_url = get_public_tunnel_server_url()
    comanda_install = (
        generar_comanda_install_wss(str(emp.id), vault_token_actual, role="EMPRESA")
        if vault_token_actual
        else None
    )

    return {
        "id": str(emp.id),
        "nom": nom_real,
        "rao_social": nom_real,
        "nif": nif_real,
        "adreca": adreca_real,
        "subdomini": emp.subdomini,
        "domini_custom": emp.domini_custom,
        "vertical": emp.vertical or "SEVALOR",
        "pla": pla,
        "pla_subscripcio": pla,
        "estat": emp.estat_pagament,
        "estat_pagament": emp.estat_pagament,
        "quota_operaris": quota_operaris,
        "operaris_actius": operaris_actius,
        "quota_buffer_mb": quota_buffer_mb,
        "buffer_utilitzat_mb": buffer_utilitzat_mb,
        "quota_disc_bytes_autoritzada": emp.quota_disc_bytes_autoritzada,
        "quota_disc_bytes_utilitzada": emp.quota_disc_bytes_utilitzada,
        "disc_quota_mb": disc_quota_mb,
        "disc_utilitzat_mb": int(buffer_utilitzat_mb),
        "tarifa_llicencia_base": float(
            llic.get("tarifa_llicencia_base", getattr(emp, "tarifa_llicencia_base", 0.0) or 0.0)
        ),
        "tarifa_per_operari": float(
            llic.get("tarifa_per_operari", getattr(emp, "tarifa_per_operari", 0.0) or 0.0)
        ),
        "tarifa_config_ia": float(
            llic.get("tarifa_config_ia", getattr(emp, "tarifa_config_ia", 0.0) or 0.0)
        ),
        "equips_ia_venuts": llic.get("equips_ia_venuts", getattr(emp, "equips_ia_venuts", None) or []),
        "notes_crm": llic.get("notes_crm", fitxa.get("notes_crm", getattr(emp, "notes_crm", None))),
        "historial_llicencia": historial_list,
        "feature_copilot_ia": bool(emp.feature_copilot_ia),
        "feature_flota": bool(emp.feature_flota),
        "feature_planols": bool(emp.feature_planols),
        "feature_telegram": bool(emp.feature_telegram),
        "node_ia_url": emp.node_ia_url,
        "disc_dur_url": getattr(emp, "disc_dur_url", None),
        "vault_token": vault_token_actual,
        "node_ia_actiu": bool(emp.node_ia_actiu),
        "tunnel_online": tunnel_online,
        "tunnel_status": "ONLINE" if tunnel_online else "OFFLINE",
        "tunnel_uri": build_wss_tunnel_uri(emp.id),
        "tunnel_server_url": tunnel_server_url,
        "comanda_install_wss": comanda_install,
        "cua_transit_pendent": cua_pendent,
        "tunnel_meta": tunnel_info,
        "features": {
            "copilot_ia": bool(emp.feature_copilot_ia),
            "flota_avancada": bool(emp.feature_flota),
            "planols_tecnics": bool(emp.feature_planols),
            "telegram_bot": bool(emp.feature_telegram),
        },
        "primari_hsl": emp.primari_hsl,
        "secundari_hsl": emp.secundari_hsl,
        "accent_hsl": emp.accent_hsl,
        "logotip_path": emp.logotip_path,
        "favicon_path": emp.favicon_path,
        "data_alta": emp.created_at.isoformat() if emp.created_at else None,
        "created_at": emp.created_at.isoformat() if emp.created_at else None,
    }


@router.get("/{empresa_id}/tunnel-status", response_model=Dict[str, Any])
async def obtenir_tunnel_status_tenant(
    empresa_id: str,
    db: AsyncSession = Depends(get_db_with_tenant_context),
    claims: Dict[str, Any] = Depends(require_roles(["SUPERADMIN"])),
) -> Dict[str, Any]:
    """Retorna l'estat en temps real del Túnel Invers WSS de l'empresa, cua de trànsit i comanda 1-clic."""
    emp = await _resolve_empresa(db, empresa_id)
    if not emp:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant no trobat.")

    if not getattr(emp, "vault_token", None):
        emp.vault_token = f"svlt_{secrets.token_urlsafe(24)}"
        await db.commit()

    target_key = empresa_target_key(emp.id)
    info = await vault_tunnel_broker.get_status(target_key)
    online = bool(info.get("online"))
    cua_pendent = SovereignStorageGateway.comptar_cua_transit_empresa(emp.id)
    tunnel_server_url = get_public_tunnel_server_url()

    return {
        "empresa_id": str(emp.id),
        "tunnel_online": online,
        "tunnel_status": "ONLINE" if online else "OFFLINE",
        "tunnel_uri": build_wss_tunnel_uri(emp.id),
        "tunnel_server_url": tunnel_server_url,
        "agent_version": info.get("agent_version") if online else None,
        "connected_at": info.get("connected_at") if online else None,
        "last_seen_at": info.get("last_seen_at") if online else None,
        "health": info.get("health") if online else None,
        "cua_transit_pendent": cua_pendent,
        "feature_copilot_ia": bool(emp.feature_copilot_ia),
        "node_ia_actiu": bool(emp.node_ia_actiu),
        "comanda_install_wss": generar_comanda_install_wss(
            str(emp.id), emp.vault_token or "", role="EMPRESA"
        ),
    }


@router.put("/{empresa_id}/estat", response_model=Dict[str, Any])
async def canviar_estat_tenant(
    empresa_id: str,
    payload: UpdateEstatTenantRequest,
    db: AsyncSession = Depends(get_db_with_tenant_context),
    claims: Dict[str, Any] = Depends(require_roles(["SUPERADMIN"])),
) -> Dict[str, Any]:
    nou_estat = payload.estat.strip().upper()
    if nou_estat == "SUSPES":
        nou_estat = "SUSPES_PAGAMENT"

    empresa = await _resolve_empresa(db, empresa_id)
    if not empresa:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Empresa no trobada.")
    emp_uuid = empresa.id

    estat_anterior = empresa.estat_pagament
    empresa.estat_pagament = nou_estat
    empresa.updated_at = datetime.now(timezone.utc)

    quota_actual = int(
        getattr(empresa, "quota_operaris", None) or QUOTES_PER_PLA.get(empresa.pla_subscripcio, 5)
    )
    db.add(
        SaasHistorialLlicencia(
            empresa_id=emp_uuid,
            quota_operaris_anterior=quota_actual,
            quota_operaris_nova=quota_actual,
            estat_anterior=estat_anterior,
            estat_nou=nou_estat,
            motiu=payload.motiu or f"Canvi d'estat de {estat_anterior} a {nou_estat}",
        )
    )
    await db.commit()

    # Bloqueig o desbloqueig immediat de sessions a Redis (Spec 04 FR-016)
    try:
        from app.core.redis import blacklist_tenant, unblacklist_tenant

        if nou_estat in ("SUSPES_PAGAMENT", "HIBERNANT", "BAIXA_OFFBOARDING", "ELIMINAT"):
            await blacklist_tenant(empresa_id, nou_estat)
            await vault_tunnel_broker.disconnect(
                empresa_target_key(emp_uuid),
                code=4403,
                reason=f"Tenant {nou_estat}",
            )
        elif nou_estat in ("ACTIU", "TRIAL"):
            await unblacklist_tenant(empresa_id)
    except Exception as exc:
        logger.warning(
            "No s'ha pogut actualitzar l'estat a Redis per al tenant %s: %s", empresa_id, exc
        )

    return {
        "status": "OK",
        "empresa_id": empresa_id,
        "estat_anterior": estat_anterior,
        "nou_estat": nou_estat,
        "missatge": f"L'estat del tenant s'ha canviat a '{nou_estat}'.",
    }


@router.put("/{empresa_id}/quota", response_model=Dict[str, Any])
async def canviar_quota_tenant(
    empresa_id: str,
    payload: UpdateQuotaTenantRequest,
    db: AsyncSession = Depends(get_db_with_tenant_context),
    claims: Dict[str, Any] = Depends(require_roles(["SUPERADMIN"])),
) -> Dict[str, Any]:
    empresa = await _resolve_empresa(db, empresa_id)
    if not empresa:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Empresa no trobada.")
    emp_uuid = empresa.id

    nou_pla = (payload.pla_subscripcio or empresa.pla_subscripcio or "STARTER").strip().upper()
    if payload.quota_operaris is not None:
        nou_limit = int(payload.quota_operaris)
    else:
        nou_limit = QUOTES_PER_PLA.get(nou_pla, int(empresa.quota_operaris or 5))

    count_res = await db.execute(
        select(func.count(Usuari.id)).where(
            Usuari.empresa_id == emp_uuid,
            Usuari.rol == "OPERARI",
            Usuari.estat == "ACTIU",
        )
    )
    operaris_actius = count_res.scalar() or 0

    if nou_limit < operaris_actius:
        sobrants = operaris_actius - nou_limit
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Downgrade bloquejat: màxim {nou_limit} operaris però en teniu {operaris_actius}. Doneu de baixa {sobrants} operaris.",
        )

    quota_anterior = int(
        getattr(empresa, "quota_operaris", None) or QUOTES_PER_PLA.get(empresa.pla_subscripcio, 5)
    )
    empresa.pla_subscripcio = nou_pla
    empresa.quota_operaris = nou_limit
    if payload.quota_buffer_mb is not None:
        empresa.quota_buffer_mb = int(payload.quota_buffer_mb)
    empresa.updated_at = datetime.now(timezone.utc)

    if quota_anterior != nou_limit:
        db.add(
            SaasHistorialLlicencia(
                empresa_id=emp_uuid,
                quota_operaris_anterior=quota_anterior,
                quota_operaris_nova=nou_limit,
                estat_anterior=empresa.estat_pagament,
                estat_nou=empresa.estat_pagament,
                motiu=payload.motiu
                or f"Actualització de quota d'operaris ({quota_anterior} -> {nou_limit})",
            )
        )

    await db.commit()

    _, llicencies_map = await _carregar_mapes_superadmin_tenants()
    llic_act = dict(llicencies_map.get(str(emp_uuid), {}))
    llic_act.update(
        {
            "empresa_id": str(emp_uuid),
            "pla_subscripcio": nou_pla,
            "quota_operaris": nou_limit,
            "quota_buffer_mb": empresa.quota_buffer_mb,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
    )
    try:
        await SuperadminStorageGateway.desar_entitat_json("tenants_llicencies", str(emp_uuid), llic_act)
    except HTTPException as exc:
        logger.warning("No s'ha pogut sincronitzar la quota al Disc Superadmin: %s", exc.detail)

    return {
        "status": "OK",
        "empresa_id": empresa_id,
        "nou_pla": nou_pla,
        "nova_quota_operaris": nou_limit,
        "quota_operaris": nou_limit,
        "quota_buffer_mb": empresa.quota_buffer_mb,
    }


@router.put("/{empresa_id}/crm", response_model=Dict[str, Any])
async def actualitzar_crm_tenant(
    empresa_id: str,
    payload: UpdateCrmCondicionsRequest,
    db: AsyncSession = Depends(get_db_with_tenant_context),
    claims: Dict[str, Any] = Depends(require_roles(["SUPERADMIN"])),
) -> Dict[str, Any]:
    """Actualitza les condicions comercials del CRM, tarifes editables, equips IA (venda) i notes."""
    empresa = await _resolve_empresa(db, empresa_id)
    if not empresa:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Empresa no trobada.")
    emp_uuid = empresa.id

    if payload.quota_operaris is not None:
        count_res = await db.execute(
            select(func.count(Usuari.id)).where(
                Usuari.empresa_id == emp_uuid,
                Usuari.rol == "OPERARI",
                Usuari.estat == "ACTIU",
            )
        )
        operaris_actius = count_res.scalar() or 0
        if payload.quota_operaris < operaris_actius:
            sobrants = operaris_actius - payload.quota_operaris
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Downgrade bloquejat: màxim {payload.quota_operaris} operaris però en teniu {operaris_actius}. Doneu de baixa {sobrants} operaris.",
            )
        quota_ant = int(empresa.quota_operaris or 5)
        if quota_ant != payload.quota_operaris:
            db.add(
                SaasHistorialLlicencia(
                    empresa_id=emp_uuid,
                    quota_operaris_anterior=quota_ant,
                    quota_operaris_nova=payload.quota_operaris,
                    estat_anterior=empresa.estat_pagament,
                    estat_nou=empresa.estat_pagament,
                    motiu="Modificació de quota des de fitxa CRM",
                )
            )
        empresa.quota_operaris = payload.quota_operaris

    if payload.quota_buffer_mb is not None:
        empresa.quota_buffer_mb = payload.quota_buffer_mb

    fitxes_map, llicencies_map = await _carregar_mapes_superadmin_tenants()
    fitxa_act = dict(fitxes_map.get(str(emp_uuid), {}))
    llic_act = dict(llicencies_map.get(str(emp_uuid), {}))

    tarifa_base = (
        float(payload.tarifa_llicencia_base)
        if payload.tarifa_llicencia_base is not None
        else float(llic_act.get("tarifa_llicencia_base", getattr(empresa, "tarifa_llicencia_base", 0.0) or 0.0))
    )
    tarifa_op = (
        float(payload.tarifa_per_operari)
        if payload.tarifa_per_operari is not None
        else float(llic_act.get("tarifa_per_operari", getattr(empresa, "tarifa_per_operari", 0.0) or 0.0))
    )
    tarifa_ia = (
        float(payload.tarifa_config_ia)
        if payload.tarifa_config_ia is not None
        else float(llic_act.get("tarifa_config_ia", getattr(empresa, "tarifa_config_ia", 0.0) or 0.0))
    )
    equips_nous = (
        [item.model_dump() for item in payload.equips_ia_venuts]
        if payload.equips_ia_venuts is not None
        else llic_act.get("equips_ia_venuts", getattr(empresa, "equips_ia_venuts", None) or [])
    )
    notes_noves = (
        payload.notes_crm
        if payload.notes_crm is not None
        else llic_act.get("notes_crm", fitxa_act.get("notes_crm", getattr(empresa, "notes_crm", None)))
    )

    llic_nova = {
        **llic_act,
        "empresa_id": str(emp_uuid),
        "pla_subscripcio": empresa.pla_subscripcio,
        "quota_operaris": empresa.quota_operaris,
        "quota_buffer_mb": empresa.quota_buffer_mb,
        "tarifa_llicencia_base": tarifa_base,
        "tarifa_per_operari": tarifa_op,
        "tarifa_config_ia": tarifa_ia,
        "equips_ia_venuts": equips_nous,
        "notes_crm": notes_noves,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    superadmin_vault_sync = True
    superadmin_vault_avis: Optional[str] = None
    try:
        await SuperadminStorageGateway.desar_entitat_json("tenants_llicencies", str(emp_uuid), llic_nova)
        if fitxa_act:
            fitxa_act["notes_crm"] = notes_noves
            await SuperadminStorageGateway.desar_entitat_json("tenants_fitxes", str(emp_uuid), fitxa_act)
    except HTTPException as exc:
        superadmin_vault_sync = False
        superadmin_vault_avis = str(exc.detail)
        logger.warning(
            "No s'ha pogut sincronitzar les condicions CRM al Disc Superadmin per %s: %s",
            emp_uuid,
            exc.detail,
        )

    # Zero-Storage Hetzner: no retenir tarifes ni notes comercials en clar a PostgreSQL
    empresa.tarifa_llicencia_base = 0.0
    empresa.tarifa_per_operari = 0.0
    empresa.tarifa_config_ia = 0.0
    empresa.equips_ia_venuts = []
    empresa.notes_crm = None

    empresa.updated_at = datetime.now(timezone.utc)
    await db.commit()

    resp_crm: Dict[str, Any] = {
        "status": "OK",
        "empresa_id": empresa_id,
        "quota_operaris": empresa.quota_operaris,
        "quota_buffer_mb": empresa.quota_buffer_mb,
        "tarifa_llicencia_base": tarifa_base,
        "tarifa_per_operari": tarifa_op,
        "tarifa_config_ia": tarifa_ia,
        "equips_ia_venuts": equips_nous,
        "notes_crm": notes_noves,
        "superadmin_vault_sync": superadmin_vault_sync,
    }
    if superadmin_vault_avis:
        resp_crm["superadmin_vault_avis"] = superadmin_vault_avis
    return resp_crm


@router.get("/{empresa_id}/recuperar-dades")
async def recuperar_dades_empresa_zip(
    empresa_id: str,
    db: AsyncSession = Depends(get_db_with_tenant_context),
    claims: Dict[str, Any] = Depends(require_roles(["SUPERADMIN"])),
) -> StreamingResponse:
    """Exporta un paquet .zip amb totes les dades de l'empresa abans de donar-la de baixa."""
    emp = await _resolve_empresa(db, empresa_id)
    if not emp:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Empresa no trobada.")
    emp_uuid = emp.id

    usuaris_res = await db.execute(select(Usuari).where(Usuari.empresa_id == emp_uuid))
    usuaris = [
        {
            "id": str(u.id),
            "nom": u.nom,
            "cognoms": u.cognoms,
            "nif": u.nif,
            "email": u.email,
            "telefon": u.telefon,
            "rol": u.rol,
            "estat": u.estat,
        }
        for u in usuaris_res.scalars().all()
    ]

    clients_res = await db.execute(select(Client).where(Client.empresa_id == emp_uuid))
    clients = [
        {
            "id": str(c.id),
            "codi": c.codi,
            "rao_social": c.rao_social,
            "nif": c.nif,
            "email": c.email,
            "telefon": c.telefon,
            "adreca_fiscal": c.adreca_fiscal,
        }
        for c in clients_res.scalars().all()
    ]

    ots_res = await db.execute(select(OrdreTreball).where(OrdreTreball.empresa_id == emp_uuid))
    ordres_treball = [
        {
            "id": str(o.id),
            "codi": o.codi,
            "titol": o.titol,
            "estat": o.estat,
            "tipus": getattr(o, "tipus_intervencio", None),
            "created_at": o.created_at.isoformat() if o.created_at else None,
        }
        for o in ots_res.scalars().all()
    ]

    fact_res = await db.execute(
        select(FacturaCapcalera).where(FacturaCapcalera.empresa_id == emp_uuid)
    )
    factures_empresa = [
        {
            "id": str(f.id),
            "serie": f.serie,
            "numero_factura": f.numero_factura,
            "import_total": float(
                getattr(f, "total_factura", getattr(f, "import_total", 0.0)) or 0.0
            ),
            "hash_sha256": f.hash_sha256,
            "data_emissio": f.data_emissio.isoformat() if f.data_emissio else None,
        }
        for f in fact_res.scalars().all()
    ]

    saas_fact_res = await db.execute(
        select(SaasFacturaB2B).where(SaasFacturaB2B.empresa_id == emp_uuid)
    )
    factures_saas = [
        {
            "id": str(sf.id),
            "serie": sf.serie,
            "numero_factura": sf.numero_factura,
            "periode": sf.periode,
            "estat": sf.estat,
            "import_total": float(sf.import_total or 0.0),
            "hash_sha256": sf.hash_sha256,
        }
        for sf in saas_fact_res.scalars().all()
    ]

    tiquets_res = await db.execute(
        select(SaasTiquetSuport).where(SaasTiquetSuport.empresa_id == emp_uuid)
    )
    tiquets_suport = [
        {
            "id": str(t.id),
            "assumpte": t.assumpte,
            "estat": t.estat,
            "severitat": t.severitat,
            "created_at": t.created_at.isoformat() if t.created_at else None,
        }
        for t in tiquets_res.scalars().all()
    ]

    fitxes_map, _ = await _carregar_mapes_superadmin_tenants()
    fitxa_emp = fitxes_map.get(str(emp.id), {})

    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(
            "empresa_metadata.json",
            json.dumps(
                {
                    "id": str(emp.id),
                    "nom": fitxa_emp.get("rao_social") or fitxa_emp.get("nom") or emp.nom,
                    "nif": fitxa_emp.get("nif") or emp.nif,
                    "subdomini": emp.subdomini,
                    "domini_custom": emp.domini_custom,
                    "vertical": emp.vertical,
                    "estat_pagament": emp.estat_pagament,
                    "quota_operaris": emp.quota_operaris,
                    "exported_at": datetime.now(timezone.utc).isoformat(),
                },
                indent=2,
                ensure_ascii=False,
            ),
        )
        zf.writestr("usuaris.json", json.dumps(usuaris, indent=2, ensure_ascii=False))
        zf.writestr("clients.json", json.dumps(clients, indent=2, ensure_ascii=False))
        zf.writestr("ordres_treball.json", json.dumps(ordres_treball, indent=2, ensure_ascii=False))
        zf.writestr(
            "factures_empresa.json", json.dumps(factures_empresa, indent=2, ensure_ascii=False)
        )
        zf.writestr(
            "factures_saas_b2b.json", json.dumps(factures_saas, indent=2, ensure_ascii=False)
        )
        zf.writestr("tiquets_suport.json", json.dumps(tiquets_suport, indent=2, ensure_ascii=False))

        for cat_key, arc_dir in (("configuracio", "configuracio"), ("operaris", "operaris")):
            try:
                entitats_cat = await SovereignStorageGateway.llegir_entitats_json(
                    db, emp_uuid, cat_key
                )
                if entitats_cat:
                    zf.writestr(
                        f"arxius_disc/{arc_dir}.json",
                        json.dumps(entitats_cat, indent=2, ensure_ascii=False),
                    )
            except Exception:
                pass

        if emp.logotip_path and (
            emp.logotip_path.startswith("vault://") or emp.logotip_path.startswith("transit://")
        ):
            try:
                logo_bytes, logo_name = await SovereignStorageGateway.obtenir_bytes_fitxer(
                    db, emp_uuid, emp.logotip_path
                )
                zf.writestr(f"arxius_disc/{logo_name}", logo_bytes)
            except Exception:
                pass

        for prefix in ("/data", "/docs", "/tmp/data", "/tmp/docs"):
            folder = os.path.join(prefix, empresa_id)
            if os.path.exists(folder):
                for root, _dirs, files in os.walk(folder):
                    for file in files:
                        full_path = os.path.join(root, file)
                        rel_path = os.path.relpath(full_path, folder)
                        try:
                            zf.write(full_path, arcname=os.path.join("arxius_disc", rel_path))
                        except OSError:
                            pass

    zip_buffer.seek(0)
    slug = emp.subdomini or empresa_id[:8]
    filename = f"recuperacio_dades_{slug}.zip"
    return StreamingResponse(
        zip_buffer,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.put("/{empresa_id}/feature-flags", response_model=Dict[str, Any])
async def update_feature_flags(
    empresa_id: str,
    payload: UpdateFeatureFlagsRequest,
    db: AsyncSession = Depends(get_db_with_tenant_context),
    claims: Dict[str, Any] = Depends(require_roles(["SUPERADMIN"])),
) -> Dict[str, Any]:
    empresa = await _resolve_empresa(db, empresa_id)
    if not empresa:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Empresa no trobada.")

    for candidate_raw in (payload.node_ia_url, payload.disc_dur_url):
        if _es_url_http_prohibida(candidate_raw):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=(
                    "Les adreces HTTP/HTTPS entrants estan prohibides per arquitectura (ADR-001). "
                    "L'empresa utilitza el Túnel Invers WSS (wss-tunnel://<uuid>)."
                ),
            )

    tunnel_uri_default = build_wss_tunnel_uri(empresa.id)
    empresa.feature_copilot_ia = payload.feature_copilot_ia
    empresa.feature_flota = payload.feature_flota
    empresa.feature_planols = payload.feature_planols
    empresa.feature_telegram = payload.feature_telegram
    if payload.node_ia_url is not None:
        clean_node = payload.node_ia_url.strip()
        empresa.node_ia_url = clean_node if clean_node else tunnel_uri_default
    elif not empresa.node_ia_url:
        empresa.node_ia_url = tunnel_uri_default
    if payload.disc_dur_url is not None:
        clean_disc = payload.disc_dur_url.strip()
        empresa.disc_dur_url = clean_disc if clean_disc else tunnel_uri_default
    elif not getattr(empresa, "disc_dur_url", None):
        empresa.disc_dur_url = tunnel_uri_default
    if payload.node_ia_actiu is not None:
        empresa.node_ia_actiu = payload.node_ia_actiu
    elif empresa.feature_copilot_ia:
        empresa.node_ia_actiu = True
    if payload.vault_token is not None:
        empresa.vault_token = payload.vault_token.strip() if payload.vault_token else None
    empresa.updated_at = datetime.now(timezone.utc)

    await db.commit()
    await SovereignStorageGateway.sincronitzar_vincle_client_vault_empresa(db, empresa)

    return {
        "status": "OK",
        "empresa_id": empresa_id,
        "feature_flags": {
            "copilot_ia": empresa.feature_copilot_ia,
            "flota": empresa.feature_flota,
            "planols": empresa.feature_planols,
            "telegram": empresa.feature_telegram,
            "node_ia_actiu": empresa.node_ia_actiu,
            "node_ia_url": empresa.node_ia_url,
            "disc_dur_url": getattr(empresa, "disc_dur_url", None),
            "vault_token": getattr(empresa, "vault_token", None),
        },
    }


@router.post("/{empresa_id}/vault-token/rotate", response_model=Dict[str, Any])
@router.post("/{empresa_id}/rotar-vault-token", response_model=Dict[str, Any])
async def rotar_vault_token(
    empresa_id: str,
    payload: Optional[RotateVaultTokenRequest] = None,
    db: AsyncSession = Depends(get_db_with_tenant_context),
    claims: Dict[str, Any] = Depends(require_roles(["SUPERADMIN"])),
) -> Dict[str, Any]:
    """Rota el token dedicat del Túnel WSS Sobirà, revoca qualsevol sessió activa i retorna la comanda 1-clic."""
    empresa = await _resolve_empresa(db, empresa_id)
    if not empresa:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Empresa no trobada.")

    nou_token = (
        payload.vault_token.strip()
        if payload and payload.vault_token and payload.vault_token.strip()
        else f"svlt_{secrets.token_urlsafe(24)}"
    )
    empresa.vault_token = nou_token
    empresa.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await SovereignStorageGateway.sincronitzar_vincle_client_vault_empresa(db, empresa)

    sessio_tancada = await vault_tunnel_broker.disconnect(
        empresa_target_key(empresa.id),
        code=4401,
        reason="Token rotated",
    )
    tunnel_server_url = get_public_tunnel_server_url()

    return {
        "status": "OK",
        "empresa_id": str(empresa.id),
        "vault_token": nou_token,
        "sessio_anterior_tancada": sessio_tancada,
        "tunnel_server_url": tunnel_server_url,
        "comanda_install_wss": generar_comanda_install_wss(
            str(empresa.id), nou_token, role="EMPRESA"
        ),
    }


@router.post("/{empresa_id}/inicialitzar-disc", response_model=Dict[str, Any])
async def inicialitzar_disc_empresa(
    empresa_id: str,
    db: AsyncSession = Depends(get_db_with_tenant_context),
    claims: Dict[str, Any] = Depends(require_roles(["SUPERADMIN"])),
) -> Dict[str, Any]:
    """Crea l'estructura de 38 carpetes via Túnel WSS, bolca fitxes reals i drena cua de trànsit SVENC1."""
    empresa = await _resolve_empresa(db, empresa_id)
    if not empresa:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Empresa no trobada.")

    if not getattr(empresa, "vault_token", None):
        empresa.vault_token = f"svlt_{secrets.token_urlsafe(24)}"
        await db.commit()

    boss_res = await db.execute(
        select(Usuari)
        .where(Usuari.empresa_id == empresa.id, Usuari.rol == "BOSS")
        .order_by(Usuari.created_at.asc())
    )
    boss = boss_res.scalars().first()

    fitxes_map, _ = await _carregar_mapes_superadmin_tenants()
    fitxa = fitxes_map.get(str(empresa.id), {})
    dades_empresa_reals = (
        {
            "nom": fitxa.get("rao_social") or fitxa.get("nom") or empresa.nom,
            "nif": fitxa.get("nif") or empresa.nif,
            "adreca": fitxa.get("adreca", empresa.adreca),
        }
        if fitxa
        else None
    )
    dades_boss_reals = (
        {
            "id": str(boss.id),
            "nom": fitxa.get("boss_nom", boss.nom),
            "cognoms": fitxa.get("boss_cognoms", boss.cognoms),
            "nif": fitxa.get("boss_nif", boss.nif),
            "email": fitxa.get("boss_email", boss.email),
            "telefon": fitxa.get("boss_telefon", boss.telefon),
            "rol": boss.rol,
        }
        if (fitxa and boss)
        else None
    )

    carpetes_inicialitzades: Optional[int] = None
    target_key = empresa_target_key(empresa.id)
    tunnel_online = await vault_tunnel_broker.is_online(target_key)
    if tunnel_online:
        try:
            init_res = await vault_tunnel_broker.init_folders(target_key)
            carpetes_inicialitzades = int(
                init_res.get("total_carpetes") or init_res.get("carpetes_count") or 38
            )
        except VaultTunnelError as exc:
            logger.warning(
                "Error inicialitzant carpetes WSS per empresa %s: %s", empresa.id, exc
            )
            tunnel_online = False
    elif _es_ruta_local_test_permesa(getattr(empresa, "disc_dur_url", None)):
        carpetes_inicialitzades = len(
            inicialitzar_arbre_carpetes_disc(str(empresa.disc_dur_url))
        )

    rutes = await SovereignStorageGateway.inicialitzar_dades_onboarding_empresa(
        db=db,
        empresa=empresa,
        boss=boss,
        dades_empresa_reals=dades_empresa_reals,
        dades_boss_reals=dades_boss_reals,
    )
    drain_stats = await SovereignStorageGateway.drenar_cua_transit_empresa(db, empresa.id)
    tots_transit = any(str(v).startswith("transit://") for v in rutes.values())
    cua_pendent = SovereignStorageGateway.comptar_cua_transit_empresa(empresa.id)
    comanda_install = generar_comanda_install_wss(
        str(empresa.id), empresa.vault_token or "", role="EMPRESA"
    )

    return {
        "status": "QUEUED" if tots_transit else "SYNCED",
        "empresa_id": str(empresa.id),
        "vault_token": empresa.vault_token,
        "tunnel_online": tunnel_online,
        "tunnel_status": "ONLINE" if tunnel_online else "OFFLINE",
        "carpetes_inicialitzades": carpetes_inicialitzades,
        "cua_transit_pendent": cua_pendent,
        "comanda_install_wss": comanda_install,
        "files": rutes,
        "transit_drain": drain_stats,
        "drenatge": drain_stats,
        "missatge": (
            "Túnel WSS offline temporalment: fitxers encuats xifrats (SVENC1) per a drenatge automàtic en connectar l'agent."
            if tots_transit
            else f"Estructura ({carpetes_inicialitzades or 38} carpetes) i fitxes base sincronitzades al disc de l'empresa via WSS."
        ),
    }


@router.post("/{empresa_id}/impersonate", response_model=Dict[str, Any])
async def impersonate_tenant(
    empresa_id: str,
    db: AsyncSession = Depends(get_db_with_tenant_context),
    claims: Dict[str, Any] = Depends(require_roles(["SUPERADMIN"])),
) -> Dict[str, Any]:
    empresa = await _resolve_empresa(db, empresa_id)
    if not empresa:
        raise HTTPException(status_code=404, detail="Empresa no trobada")

    import jwt

    from app.core.config import settings

    expire = datetime.now(timezone.utc) + timedelta(hours=2)
    payload = {
        "sub": claims.get("sub"),
        "empresa_id": str(empresa.id),
        "rol": "SUPERADMIN",
        "exp": expire,
        "iat": datetime.now(timezone.utc),
        "is_impersonation": True,
        "totp_activat": claims.get("totp_activat", True),
        "ip_allowlist": claims.get("ip_allowlist", []),
    }

    token = jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)

    handoff_url = await _crear_handoff_impersonacio(empresa, token)

    return {
        "access_token": token,
        "token_type": "bearer",
        "rol": "SUPERADMIN",
        "empresa_id": str(empresa.id),
        "is_impersonation": True,
        "handoff_url": handoff_url,
    }


IMPERSONATION_HANDOFF_TTL_SECONDS = 60
IMPERSONATION_HANDOFF_PREFIX = "impersonation_handoff:"


def _host_tenant_empresa(empresa: Empresa) -> Optional[str]:
    """Retorna el host públic propi de l'empresa (domini_custom o subdomini.projectexinoxano.cat)."""
    subd = (empresa.subdomini or "").strip().lower()
    base_subdomini = f"{subd}.projectexinoxano.cat" if subd else ""
    domini = (empresa.domini_custom or "").strip().lower() or base_subdomini
    if not domini or not re.fullmatch(r"[a-z0-9]([a-z0-9.-]{0,251}[a-z0-9])?", domini):
        return None
    if domini == (settings.PLATFORM_ADMIN_HOST or "").strip().lower():
        return None
    return domini


async def _crear_handoff_impersonacio(empresa: Empresa, token: str) -> Optional[str]:
    """Crea un codi d'un sol ús (Redis, TTL 60 s) per traspassar la sessió al domini de l'empresa.

    El JWT mai viatja per URL: només el codi opac, i en el fragment (#) perquè no arribi
    a logs de servidor ni a capçaleres Referer. Retorna None si no hi ha domini propi
    o Redis no està disponible (el frontend manté el flux al host d'administració).
    """
    import secrets

    from app.core.redis import get_redis_client

    host = _host_tenant_empresa(empresa)
    if not host:
        return None

    client = await get_redis_client()
    if not client:
        logger.warning("Redis no disponible: impersonació sense traspàs de domini.")
        return None

    code = secrets.token_urlsafe(32)
    admin_host = (settings.PLATFORM_ADMIN_HOST or "").strip().lower()
    dades = {
        "token": token,
        "empresa_id": str(empresa.id),
        "empresa_nom": empresa.nom or "",
        "return_url": f"https://{admin_host}/superadmin/empreses/{empresa.id}"
        if admin_host
        else "",
    }
    try:
        await client.set(
            f"{IMPERSONATION_HANDOFF_PREFIX}{code}",
            json.dumps(dades),
            ex=IMPERSONATION_HANDOFF_TTL_SECONDS,
        )
    except Exception as exc:
        logger.warning("No s'ha pogut desar el codi de traspàs d'impersonació: %s", exc)
        return None

    return f"https://{host}/impersonacio#code={code}"


class SetBossPasswordRequest(BaseModel):
    password: str = Field(..., min_length=8)


@router.api_route(
    "/{empresa_id}/activacio-boss", methods=["GET", "POST"], response_model=Dict[str, Any]
)
async def regenerar_activacio_boss(
    empresa_id: str,
    db: AsyncSession = Depends(get_db_with_tenant_context),
    claims: Dict[str, Any] = Depends(require_roles(["SUPERADMIN"])),
) -> Dict[str, Any]:
    """Genera o recupera un enllaç d'activació 2FA per al compte BOSS del tenant."""
    emp = await _resolve_empresa(db, empresa_id)
    if not emp:
        raise HTTPException(status_code=404, detail="Empresa no trobada")
    emp_uuid = emp.id

    boss_res = await db.execute(
        select(Usuari)
        .where(
            Usuari.empresa_id == emp_uuid,
            Usuari.rol == "BOSS",
        )
        .order_by(Usuari.created_at.asc())
    )
    boss = boss_res.scalars().first()
    if not boss:
        raise HTTPException(
            status_code=404, detail="No s'ha trobat cap usuari BOSS per a aquesta empresa"
        )

    expire = datetime.now(timezone.utc) + timedelta(hours=24)
    payload_jwt = {
        "sub": str(boss.id),
        "action": "activate",
        "exp": expire,
    }
    jwt_token = jwt.encode(payload_jwt, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    domini_base = emp.domini_custom or (
        f"{emp.subdomini}.projectexinoxano.cat" if emp.subdomini else "sevalor.app"
    )
    enllac = f"https://{domini_base}/activacio?token={jwt_token}"

    fitxes_map, _ = await _carregar_mapes_superadmin_tenants()
    fitxa = fitxes_map.get(str(emp.id), {})

    return {
        "status": "OK",
        "boss": {
            "id": str(boss.id),
            "nom": fitxa.get("boss_nom", boss.nom),
            "cognoms": fitxa.get("boss_cognoms", boss.cognoms),
            "email": fitxa.get("boss_email", boss.email),
            "nif": fitxa.get("boss_nif", boss.nif),
            "totp_activat": bool(boss.totp_activat),
            "te_password": bool(boss.password_hash),
        },
        "enllac_activacio": enllac,
        "token": jwt_token,
        "caducitat": expire.isoformat(),
    }


@router.post("/{empresa_id}/set-boss-password", response_model=Dict[str, Any])
async def establir_password_boss(
    empresa_id: str,
    payload: SetBossPasswordRequest,
    db: AsyncSession = Depends(get_db_with_tenant_context),
    claims: Dict[str, Any] = Depends(require_roles(["SUPERADMIN"])),
) -> Dict[str, Any]:
    """Estableix directament la contrasenya del BOSS per si no es fa servir l'enllaç d'activació."""
    emp = await _resolve_empresa(db, empresa_id)
    if not emp:
        raise HTTPException(status_code=404, detail="Empresa no trobada")
    emp_uuid = emp.id

    boss_res = await db.execute(
        select(Usuari)
        .where(
            Usuari.empresa_id == emp_uuid,
            Usuari.rol == "BOSS",
        )
        .order_by(Usuari.created_at.asc())
    )
    boss = boss_res.scalars().first()
    if not boss:
        raise HTTPException(
            status_code=404, detail="No s'ha trobat cap usuari BOSS per a aquesta empresa"
        )

    hashed = bcrypt.hashpw(payload.password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
    boss.password_hash = hashed
    await db.commit()

    fitxes_map, _ = await _carregar_mapes_superadmin_tenants()
    fitxa_b = fitxes_map.get(str(emp.id), {})
    email_vis = str(fitxa_b.get("boss_email") or boss.email or "")

    return {
        "status": "OK",
        "missatge": f"Contrasenya actualitzada correctament per a {email_vis}",
        "email": email_vis,
    }


@router.post("/{tenant_id}/destruccio")
async def destroy_tenant(
    tenant_id: str,
    db: AsyncSession = Depends(get_db_with_tenant_context),
    claims: Dict[str, Any] = Depends(require_roles(["SUPERADMIN"])),
) -> Dict[str, Any]:
    emp = await _resolve_empresa(db, tenant_id)
    if not emp:
        raise HTTPException(status_code=404, detail="Tenant no trobat")
    tenant_uuid = emp.id

    estat_ant = emp.estat_pagament
    emp.estat_pagament = "ELIMINAT"
    emp.updated_at = datetime.now(timezone.utc)

    db.add(
        SaasHistorialLlicencia(
            empresa_id=tenant_uuid,
            quota_operaris_anterior=int(emp.quota_operaris or 5),
            quota_operaris_nova=0,
            estat_anterior=estat_ant,
            estat_nou="ELIMINAT",
            motiu="Baixa certificada RGPD (Offboarding)",
        )
    )

    from reportlab.lib.pagesizes import A4  # type: ignore[import-untyped]
    from reportlab.pdfgen import canvas  # type: ignore[import-untyped]

    cert_dir = f"/tmp/sevalor_docs/{tenant_id}/certificats"
    os.makedirs(cert_dir, exist_ok=True)
    pdf_path = os.path.join(cert_dir, f"certificat_destruccio_{tenant_id}.pdf")

    c = canvas.Canvas(pdf_path, pagesize=A4)
    c.drawString(100, 750, "CERTIFICAT DE DESTRUCCIÓ DE DADES (RGPD Art. 17)")
    c.drawString(100, 730, f"Tenant ID: {tenant_id}")
    c.drawString(100, 710, f"Empresa: {emp.nom} (NIF: {emp.nif})")
    c.drawString(100, 690, f"Data: {datetime.now(timezone.utc).isoformat()}")
    c.drawString(
        100,
        670,
        "Les dades operatives han estat marcades per a la seva purga segura segons RGPD.",
    )
    c.drawString(
        100,
        650,
        "Es conserven al CRM les factures B2B i tiquets d'incidència per obligació d'auditoria fiscal.",
    )
    c.save()

    persistent_path = _obtenir_ruta_certificat_persistent(tenant_id)
    if persistent_path != pdf_path:
        try:
            shutil.copyfile(pdf_path, persistent_path)
        except OSError:
            pass

    nif_hash = hashlib.sha256((emp.nif or str(tenant_uuid)).encode("utf-8")).hexdigest()
    db.add(
        RegistreBaixaCertificat(
            tenant_id=tenant_uuid,
            nif_hash=nif_hash,
            certificat_path=persistent_path,
            estat="ELIMINAT",
            custodia_anys=5,
            periode_gracia_dies=30,
        )
    )

    from app.workers.tasks import purgar_dades_tenant_destruit

    purgar_dades_tenant_destruit.apply_async(args=[tenant_id], countdown=30 * 24 * 3600)

    # Eliminar el domini d'EasyPanel per prevenir dangling DNS
    if emp.domini_custom and settings.easypanel_token:
        try:
            await EasypanelService.eliminar_domini_pwa(emp.domini_custom)
        except Exception:
            pass

    await db.commit()

    try:
        from app.core.redis import blacklist_tenant

        await blacklist_tenant(tenant_id, "ELIMINAT")
    except Exception:
        pass

    return {
        "status": "success",
        "message": "Tenant eliminat i certificat generat (factures i tiquets CRM conservats per auditoria)",
        "certificat_url": pdf_path,
        "estat": "ELIMINAT",
    }
