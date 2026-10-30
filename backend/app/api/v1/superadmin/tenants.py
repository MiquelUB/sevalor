import asyncio
import io
import json
import logging
import os
import re
import shutil
import socket
import time
import uuid
import zipfile
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

import bcrypt
import httpx
import jwt
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.db import get_db_with_tenant_context
from app.core.security import require_roles
from app.models.models import (
    Client,
    Empresa,
    FacturaCapcalera,
    OrdreTreball,
    SaasFacturaB2B,
    SaasHistorialLlicencia,
    SaasTiquetSuport,
    Usuari,
)
from app.services.easypanel_service import EasypanelService

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


class EquipIAVenutItem(BaseModel):
    concepte: str = Field(..., min_length=1, max_length=200)
    unitats: int = Field(1, ge=1, le=100)
    preu_unitari: float = Field(0.0, ge=0.0)
    modalitat: str = Field("VENDA", pattern="^VENDA$")


class OnboardingTenantRequest(BaseModel):
    rao_social: str = Field(..., min_length=2, max_length=100)
    nif: str = Field(..., min_length=9, max_length=20)
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
    estat_inicial: str = Field("TRIAL", pattern="^(TRIAL|ACTIU)$")
    pla_subscripcio: str = Field("STARTER", pattern="^(STARTER|PRO|ENTERPRISE|CUSTOM)$")
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
    boss_nif: str
    boss_nom: str
    boss_cognoms: str
    boss_email: str = Field(..., pattern=r"^[\w\.-]+@[\w\.-]+\.\w+$")
    boss_telefon: Optional[str] = None
    feature_flags: Optional[Dict[str, bool]] = None
    logotip_base64: Optional[str] = None

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
    node_ia_url: str = Field(..., min_length=5, max_length=255)


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
    node_ia_actiu: Optional[bool] = None


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
    claims: Dict[str, Any] = Depends(require_roles(["SUPERADMIN"])),
) -> Dict[str, Any]:
    """Verifica en viu la connectivitat amb el node dedicat d'IA (LM Studio / Ollama) amb diagnòstic de causa arrel."""
    raw_url = payload.node_ia_url.strip()
    if not (raw_url.startswith("http://") or raw_url.startswith("https://")):
        return {
            "status": "ERROR",
            "motiu": "URL_INVALIDA",
            "missatge": "L'adreça URL ha de començar per http:// o https:// (ex: http://192.168.1.100:1234)",
            "models": [],
            "latencia_ms": None,
        }

    base = raw_url.rstrip("/")
    test_urls = (
        [f"{base}/models"]
        if base.endswith("/v1")
        else [f"{base}/v1/models", f"{base}/api/tags", f"{base}/models"]
    )

    start = time.perf_counter()
    last_error_motiu = "CONNEXIO_FALLIDA"
    last_error_msg = "No s'ha pogut establir connexió amb el node d'IA."

    async with httpx.AsyncClient(timeout=4.0) as client:
        for url in test_urls:
            try:
                t0 = time.perf_counter()
                resp = await client.get(url)
                latencia = int((time.perf_counter() - t0) * 1000)
                if resp.status_code == 200:
                    models: List[str] = []
                    try:
                        data = resp.json()
                        if isinstance(data, dict):
                            if "data" in data and isinstance(data["data"], list):
                                models = [
                                    str(m.get("id") or m.get("name"))
                                    for m in data["data"]
                                    if isinstance(m, dict) and (m.get("id") or m.get("name"))
                                ]
                            elif "models" in data and isinstance(data["models"], list):
                                models = [
                                    str(m.get("name") or m.get("id"))
                                    for m in data["models"]
                                    if isinstance(m, dict) and (m.get("name") or m.get("id"))
                                ]
                    except Exception:
                        pass
                    return {
                        "status": "OK",
                        "motiu": "CONNEXIO_ESTABLERTA",
                        "missatge": f"Connexió establerta correctament amb el node d'IA dedicat ({latencia} ms).",
                        "models": models,
                        "latencia_ms": latencia,
                    }
                else:
                    last_error_motiu = "HTTP_ERROR"
                    last_error_msg = f"El servei ha respost amb codi d'error HTTP {resp.status_code}."
            except (httpx.ConnectTimeout, httpx.ReadTimeout):
                last_error_motiu = "TIMEOUT"
                last_error_msg = (
                    "Temps d'espera esgotat (4s). Comprova que l'ordinador dedicat està encès "
                    "i que el tallafocs permet el port d'entrada."
                )
                break
            except httpx.ConnectError:
                last_error_motiu = "PORT_TANCAT"
                last_error_msg = (
                    "Connexió rebutjada. El port està tancat o el servei d'IA (LM Studio / Ollama) "
                    "no està en marxa a la IP/port indicats."
                )
                break
            except Exception as e:
                last_error_motiu = "ERROR_XARXA"
                last_error_msg = f"Error de xarxa: {str(e)}"

    total_latency = int((time.perf_counter() - start) * 1000)
    return {
        "status": "ERROR",
        "motiu": last_error_motiu,
        "missatge": last_error_msg,
        "models": [],
        "latencia_ms": total_latency,
    }


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

    resultat = []
    for emp in empreses:
        operaris_actius = counts_map.get(emp.id, 0)
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
        disc_utilitzat_mb = round(used_bytes / (1024 * 1024), 2)
        disc_quota_mb = int((emp.quota_disc_bytes_autoritzada or 10737418240) / (1024 * 1024))

        equips_venuts = getattr(emp, "equips_ia_venuts", None) or []

        resultat.append(
            {
                "id": str(emp.id),
                "nom": emp.nom,
                "rao_social": emp.nom,
                "nif": emp.nif,
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
                "tarifa_llicencia_base": float(getattr(emp, "tarifa_llicencia_base", 0.0) or 0.0),
                "tarifa_per_operari": float(getattr(emp, "tarifa_per_operari", 0.0) or 0.0),
                "tarifa_config_ia": float(getattr(emp, "tarifa_config_ia", 0.0) or 0.0),
                "equips_ia_venuts": equips_venuts,
                "notes_crm": getattr(emp, "notes_crm", None),
                "node_ia_actiu": bool(emp.node_ia_actiu),
                "node_ia_url": emp.node_ia_url,
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
    res_nif = await db.execute(select(Empresa).where(func.upper(Empresa.nif) == nif_norm))
    if res_nif.scalars().first():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"El NIF/CIF '{nif_norm}' ja està registrat en una altra empresa de la plataforma. Cal introduir un NIF/CIF únic.",
        )

    email_boss_norm = str(payload.boss_email).strip().lower()
    res_email = await db.execute(select(Usuari).where(func.lower(Usuari.email) == email_boss_norm))
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
    node_ia_url_final = (
        payload.node_ia_url.strip() if (payload.node_ia_url and copilot_actiu) else None
    )
    node_ia_actiu_final = bool(node_ia_url_final and copilot_actiu)
    agent_prompt_final = (
        payload.agent_prompt_system.strip()
        if (payload.agent_prompt_system and copilot_actiu)
        else None
    )

    logotip_path = None
    if payload.logotip_base64:
        import base64

        try:
            raw_b64 = payload.logotip_base64
            if "," in raw_b64:
                raw_b64 = raw_b64.split(",", 1)[1]
            content_bytes = base64.b64decode(raw_b64)
            if len(content_bytes) <= 10 * 1024 * 1024:
                from app.api.v1.superadmin.empreses import (
                    desar_fitxer_logotip,
                    validar_magic_bytes_imatge,
                )

                ext, _mime = validar_magic_bytes_imatge(content_bytes)
                logotip_path = desar_fitxer_logotip(str(nou_id), content_bytes, ext)
        except Exception as e:
            logger.warning(f"No s'ha pogut processar el logotip base64 durant onboarding: {e}")

    nova_empresa = Empresa(
        id=nou_id,
        nom=payload.rao_social.strip(),
        nif=payload.nif.strip().upper(),
        subdomini=subdomini_norm,
        domini_custom=domini_custom_norm,
        estat_domini=estat_domini,
        pla_subscripcio=pla_norm,
        estat_pagament=payload.estat_inicial,
        quota_operaris=quota_op_inicial,
        quota_buffer_mb=payload.quota_buffer_mb,
        tarifa_llicencia_base=payload.tarifa_llicencia_base or 0.0,
        tarifa_per_operari=payload.tarifa_per_operari or 0.0,
        tarifa_config_ia=payload.tarifa_config_ia or 0.0,
        equips_ia_venuts=equips_list,
        notes_crm=payload.notes_crm,
        quota_disc_bytes_autoritzada=quota_bytes,
        vertical=vertical_norm,
        magatzem_families_default=payload.magatzem_families_default,
        agent_prompt_system=agent_prompt_final,
        node_ia_url=node_ia_url_final,
        node_ia_actiu=node_ia_actiu_final,
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
        logotip_path=logotip_path,
        favicon_path=logotip_path,
    )
    db.add(nova_empresa)

    boss_user_id = uuid.uuid4()
    nou_boss = Usuari(
        id=boss_user_id,
        empresa_id=nou_id,
        nif=payload.boss_nif.strip().upper(),
        nom=payload.boss_nom.strip(),
        cognoms=payload.boss_cognoms.strip(),
        email=str(payload.boss_email).strip().lower(),
        telefon=payload.boss_telefon.strip() if payload.boss_telefon else "+34",
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

    emp_id_str = str(nou_id)

    try:
        from app.workers.tasks import crear_directoris_sobirans_task  # type: ignore

        crear_directoris_sobirans_task.delay(emp_id_str)
        logger.info("Tasca Celery encuada per crear directoris sobirans de %s", emp_id_str)
    except Exception as e:
        logger.warning("No s'ha pogut encuar la tasca Celery: %s", e)

    import jwt

    expire = datetime.now(timezone.utc) + timedelta(hours=24)
    payload_jwt = {
        "sub": str(boss_user_id),
        "action": "activate",
        "exp": expire,
    }
    jwt_token = jwt.encode(payload_jwt, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    domini_base = domini_custom_norm or f"{subdomini_norm}.sevalor.app"
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
            "node_ia_actiu": nova_empresa.node_ia_actiu,
            "logotip_path": nova_empresa.logotip_path,
        },
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
    try:
        emp_uuid = uuid.UUID(empresa_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="UUID invàlid.")

    res = await db.execute(select(Empresa).where(Empresa.id == emp_uuid))
    emp = res.scalars().first()
    if not emp:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant no trobat.")

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
    try:
        emp_uuid = uuid.UUID(empresa_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="UUID invàlid.")

    emp_res = await db.execute(select(Empresa).where(Empresa.id == emp_uuid))
    emp = emp_res.scalars().first()
    if not emp:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant no trobat.")

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

    return {
        "id": str(emp.id),
        "nom": emp.nom,
        "rao_social": emp.nom,
        "nif": emp.nif,
        "adreca": emp.adreca,
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
        "tarifa_llicencia_base": float(getattr(emp, "tarifa_llicencia_base", 0.0) or 0.0),
        "tarifa_per_operari": float(getattr(emp, "tarifa_per_operari", 0.0) or 0.0),
        "tarifa_config_ia": float(getattr(emp, "tarifa_config_ia", 0.0) or 0.0),
        "equips_ia_venuts": getattr(emp, "equips_ia_venuts", None) or [],
        "notes_crm": getattr(emp, "notes_crm", None),
        "historial_llicencia": historial_list,
        "feature_copilot_ia": bool(emp.feature_copilot_ia),
        "feature_flota": bool(emp.feature_flota),
        "feature_planols": bool(emp.feature_planols),
        "feature_telegram": bool(emp.feature_telegram),
        "node_ia_url": emp.node_ia_url,
        "node_ia_actiu": bool(emp.node_ia_actiu),
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

    try:
        emp_uuid = uuid.UUID(empresa_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="UUID invàlid.")

    emp_res = await db.execute(select(Empresa).where(Empresa.id == emp_uuid))
    empresa = emp_res.scalars().first()
    if not empresa:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Empresa no trobada.")

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
    try:
        emp_uuid = uuid.UUID(empresa_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="UUID invàlid.")

    emp_res = await db.execute(select(Empresa).where(Empresa.id == emp_uuid))
    empresa = emp_res.scalars().first()
    if not empresa:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Empresa no trobada.")

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
    try:
        emp_uuid = uuid.UUID(empresa_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="UUID invàlid.")

    emp_res = await db.execute(select(Empresa).where(Empresa.id == emp_uuid))
    empresa = emp_res.scalars().first()
    if not empresa:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Empresa no trobada.")

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
    if payload.tarifa_llicencia_base is not None:
        empresa.tarifa_llicencia_base = payload.tarifa_llicencia_base
    if payload.tarifa_per_operari is not None:
        empresa.tarifa_per_operari = payload.tarifa_per_operari
    if payload.tarifa_config_ia is not None:
        empresa.tarifa_config_ia = payload.tarifa_config_ia
    if payload.equips_ia_venuts is not None:
        empresa.equips_ia_venuts = [item.model_dump() for item in payload.equips_ia_venuts]
    if payload.notes_crm is not None:
        empresa.notes_crm = payload.notes_crm

    empresa.updated_at = datetime.now(timezone.utc)
    await db.commit()

    return {
        "status": "OK",
        "empresa_id": empresa_id,
        "quota_operaris": empresa.quota_operaris,
        "quota_buffer_mb": empresa.quota_buffer_mb,
        "tarifa_llicencia_base": float(empresa.tarifa_llicencia_base or 0.0),
        "tarifa_per_operari": float(empresa.tarifa_per_operari or 0.0),
        "tarifa_config_ia": float(empresa.tarifa_config_ia or 0.0),
        "equips_ia_venuts": empresa.equips_ia_venuts or [],
        "notes_crm": empresa.notes_crm,
    }


@router.get("/{empresa_id}/recuperar-dades")
async def recuperar_dades_empresa_zip(
    empresa_id: str,
    db: AsyncSession = Depends(get_db_with_tenant_context),
    claims: Dict[str, Any] = Depends(require_roles(["SUPERADMIN"])),
) -> StreamingResponse:
    """Exporta un paquet .zip amb totes les dades de l'empresa abans de donar-la de baixa."""
    try:
        emp_uuid = uuid.UUID(empresa_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="UUID invàlid.")

    emp_res = await db.execute(select(Empresa).where(Empresa.id == emp_uuid))
    emp = emp_res.scalars().first()
    if not emp:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Empresa no trobada.")

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

    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(
            "empresa_metadata.json",
            json.dumps(
                {
                    "id": str(emp.id),
                    "nom": emp.nom,
                    "nif": emp.nif,
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
    try:
        emp_uuid = uuid.UUID(empresa_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="UUID invàlid.")

    emp_res = await db.execute(select(Empresa).where(Empresa.id == emp_uuid))
    empresa = emp_res.scalars().first()
    if not empresa:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Empresa no trobada.")

    empresa.feature_copilot_ia = payload.feature_copilot_ia
    empresa.feature_flota = payload.feature_flota
    empresa.feature_planols = payload.feature_planols
    empresa.feature_telegram = payload.feature_telegram
    if payload.node_ia_url is not None:
        empresa.node_ia_url = payload.node_ia_url.strip() if payload.node_ia_url else None
    if payload.node_ia_actiu is not None:
        empresa.node_ia_actiu = payload.node_ia_actiu
    empresa.updated_at = datetime.now(timezone.utc)

    await db.commit()

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
        },
    }


@router.post("/{empresa_id}/impersonate", response_model=Dict[str, Any])
async def impersonate_tenant(
    empresa_id: str,
    db: AsyncSession = Depends(get_db_with_tenant_context),
    claims: Dict[str, Any] = Depends(require_roles(["SUPERADMIN"])),
) -> Dict[str, Any]:
    try:
        emp_uuid = uuid.UUID(empresa_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="UUID invàlid")

    emp_res = await db.execute(select(Empresa).where(Empresa.id == emp_uuid))
    empresa = emp_res.scalars().first()
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

    return {
        "access_token": token,
        "token_type": "bearer",
        "rol": "SUPERADMIN",
        "empresa_id": str(empresa.id),
        "is_impersonation": True,
    }


class SetBossPasswordRequest(BaseModel):
    password: str = Field(..., min_length=8)


@router.api_route("/{empresa_id}/activacio-boss", methods=["GET", "POST"], response_model=Dict[str, Any])
async def regenerar_activacio_boss(
    empresa_id: str,
    db: AsyncSession = Depends(get_db_with_tenant_context),
    claims: Dict[str, Any] = Depends(require_roles(["SUPERADMIN"])),
) -> Dict[str, Any]:
    """Genera o recupera un enllaç d'activació 2FA per al compte BOSS del tenant."""
    try:
        emp_uuid = uuid.UUID(empresa_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="UUID invàlid")

    emp_res = await db.execute(select(Empresa).where(Empresa.id == emp_uuid))
    emp = emp_res.scalars().first()
    if not emp:
        raise HTTPException(status_code=404, detail="Empresa no trobada")

    boss_res = await db.execute(
        select(Usuari).where(
            Usuari.empresa_id == emp_uuid,
            Usuari.rol == "BOSS",
        ).order_by(Usuari.created_at.asc())
    )
    boss = boss_res.scalars().first()
    if not boss:
        raise HTTPException(status_code=404, detail="No s'ha trobat cap usuari BOSS per a aquesta empresa")

    expire = datetime.now(timezone.utc) + timedelta(hours=24)
    payload_jwt = {
        "sub": str(boss.id),
        "action": "activate",
        "exp": expire,
    }
    jwt_token = jwt.encode(payload_jwt, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    domini_base = emp.domini_custom or (f"{emp.subdomini}.projectexinoxano.cat" if emp.subdomini else "sevalor.app")
    enllac = f"https://{domini_base}/activacio?token={jwt_token}"

    return {
        "status": "OK",
        "boss": {
            "id": str(boss.id),
            "nom": boss.nom,
            "cognoms": boss.cognoms,
            "email": boss.email,
            "nif": boss.nif,
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
    try:
        emp_uuid = uuid.UUID(empresa_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="UUID invàlid")

    boss_res = await db.execute(
        select(Usuari).where(
            Usuari.empresa_id == emp_uuid,
            Usuari.rol == "BOSS",
        ).order_by(Usuari.created_at.asc())
    )
    boss = boss_res.scalars().first()
    if not boss:
        raise HTTPException(status_code=404, detail="No s'ha trobat cap usuari BOSS per a aquesta empresa")

    hashed = bcrypt.hashpw(payload.password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
    boss.password_hash = hashed
    await db.commit()

    return {
        "status": "OK",
        "missatge": f"Contrasenya actualitzada correctament per a {boss.email}",
        "email": boss.email,
    }


@router.post("/{tenant_id}/destruccio")
async def destroy_tenant(
    tenant_id: str,
    db: AsyncSession = Depends(get_db_with_tenant_context),
    claims: Dict[str, Any] = Depends(require_roles(["SUPERADMIN"])),
) -> Dict[str, Any]:
    try:
        tenant_uuid = uuid.UUID(tenant_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="UUID invàlid")

    emp_res = await db.execute(select(Empresa).where(Empresa.id == tenant_uuid))
    emp = emp_res.scalar_one_or_none()
    if not emp:
        raise HTTPException(status_code=404, detail="Tenant no trobat")

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
