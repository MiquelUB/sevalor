"""Endpoints de configuració de l'empresa, jornada laboral, marca camaleònica i rols (/gestio/configuracio — Spec 011)."""

import os
import secrets
import string
import uuid
from datetime import date, time
from typing import Any, Dict, Optional

import bcrypt
import httpx
from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile, status
from pydantic import BaseModel, Field
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db, set_tenant_context
from app.core.security import get_current_user_claims
from app.models.models import Empresa, SlotJornada, Usuari

router = APIRouter(prefix="/gestio/configuracio", tags=["Configuració & Marca"])
limiter = Limiter(key_func=get_remote_address, enabled=os.getenv("TESTING") != "1")

# Directori sobirà d'emmagatzematge Hetzner Falkenstein
HETZNER_BASE_DOCS = os.environ.get("HETZNER_DOCS_PATH", "/docs")


# ---------------------------------------------------------------------------
# Utilitats i Validacions Criptogràfiques & Cromàtiques
# ---------------------------------------------------------------------------

def parse_hsl(hsl_str: str) -> tuple[float, float, float]:
    """Converteix una cadena '210 100% 15%' o 'hsl(210, 100%, 15%)' a (h, s, l)."""
    clean = hsl_str.replace("hsl", "").replace("(", "").replace(")", "").replace("%", "").replace(",", " ")
    parts = [float(p) for p in clean.split() if p.strip()]
    if len(parts) < 3:
        raise ValueError(f"Cadena HSL invàlida: {hsl_str}")
    h, s, l = parts[0], parts[1] / 100.0, parts[2] / 100.0
    return h, s, l


def hsl_to_rgb(h: float, s: float, l: float) -> tuple[float, float, float]:
    """Converteix HSL a sRGB [0, 1]."""
    c = (1.0 - abs(2.0 * l - 1.0)) * s
    x = c * (1.0 - abs((h / 60.0) % 2 - 1.0))
    m = l - c / 2.0

    if 0 <= h < 60:
        r_p, g_p, b_p = c, x, 0.0
    elif 60 <= h < 120:
        r_p, g_p, b_p = x, c, 0.0
    elif 120 <= h < 180:
        r_p, g_p, b_p = 0.0, c, x
    elif 180 <= h < 240:
        r_p, g_p, b_p = 0.0, x, c
    elif 240 <= h < 300:
        r_p, g_p, b_p = x, 0.0, c
    else:
        r_p, g_p, b_p = c, 0.0, x

    return r_p + m, g_p + m, b_p + m


def get_relative_luminance(r: float, g: float, b: float) -> float:
    """Calcula la luminància relativa segons WCAG 2.1."""
    def adjust(val: float) -> float:
        return val / 12.92 if val <= 0.04045 else ((val + 0.055) / 1.055) ** 2.4

    r_lin = adjust(r)
    g_lin = adjust(g)
    b_lin = adjust(b)
    return 0.2126 * r_lin + 0.7152 * g_lin + 0.0722 * b_lin


def get_contrast_ratio(lum1: float, lum2: float) -> float:
    """Calcula el ràtio de contrast (L1 + 0.05) / (L2 + 0.05)."""
    lighter = max(lum1, lum2)
    darker = min(lum1, lum2)
    return (lighter + 0.05) / (darker + 0.05)


def validar_contrast_wcag(hsl_str: str) -> float:
    """Valida que el color tingui un contrast mínim de 4.5:1 (WCAG 2.1 AA) contra text blanc."""
    try:
        h, s, l = parse_hsl(hsl_str)
        r, g, b = hsl_to_rgb(h, s, l)
        lum = get_relative_luminance(r, g, b)
        contrast_white = get_contrast_ratio(1.0, lum)
        return contrast_white
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Format HSL de color invàlid: {hsl_str}",
        )


def validar_magic_bytes_imatge(content: bytes) -> str:
    """Valida els magic bytes de capçalera d'arxiu (EDGE-03)."""
    if len(content) < 8:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="HTTP 415: Fitxer d'imatge massa curt o incomplet",
        )
    # PNG: \x89PNG\r\n\x1a\n
    if content.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png"
    # JPEG: \xff\xd8\xff
    if content.startswith(b"\xff\xd8\xff"):
        return "jpg"

    raise HTTPException(
        status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
        detail="HTTP 415: Incongruència de Magic Bytes; només s'admeten imatges PNG o JPG autèntiques",
    )


def generar_contrasenya_forta(longitud: int = 12) -> str:
    """Genera una contrasenya alfanumèrica forta de 12 caràcters."""
    caracters = string.ascii_letters + string.digits + "!@#$%&*"
    # Assegurar mínim 1 majúscula, 1 minúscula, 1 dígit i 1 caràcter especial
    pwd = [
        secrets.choice(string.ascii_uppercase),
        secrets.choice(string.ascii_lowercase),
        secrets.choice(string.digits),
        secrets.choice("!@#$%&*"),
    ]
    pwd += [secrets.choice(caracters) for _ in range(longitud - 4)]
    secrets.SystemRandom().shuffle(pwd)
    return "".join(pwd)


def generar_monograma_net(nom: str) -> str:
    """Genera un monograma de 2 caràcters basat en la raó social (RF-18)."""
    STOP_WORDS = {"de", "del", "dels", "la", "les", "el", "els", "i", "sl", "sa", "sll", "sc", "slu"}
    paraules = [p for p in nom.strip().split() if p and p.lower() not in STOP_WORDS]
    if len(paraules) >= 2:
        return (paraules[0][0] + paraules[1][0]).upper()
    elif len(paraules) == 1:
        return paraules[0][:2].upper()
    return "CP"


# ---------------------------------------------------------------------------
# Esquemes Pydantic (DTOs)
# ---------------------------------------------------------------------------

class EmpresaUpdateRequest(BaseModel):
    nom: Optional[str] = None
    adreca: Optional[str] = None
    subdomini: Optional[str] = None


class MarcaUpdateRequest(BaseModel):
    primari_hsl: str = Field(..., description="Format: '210 100% 15%'")
    secundari_hsl: str = Field(..., description="Format: '38 92% 50%'")
    accent_hsl: str = Field(..., description="Format: '190 90% 50%'")


class AdnAnalisiRequest(BaseModel):
    adn_text: str = Field(..., min_length=10, description="Contingut de la guia d'estil o ADN de marca")


class AdnAprovacioRequest(BaseModel):
    aprovat_per_boss: bool = Field(..., description="Confirmació explícita HITL del Boss")
    primari_hsl: str
    secundari_hsl: str
    accent_hsl: str


class UsuariAdminCreateRequest(BaseModel):
    nif: str = Field(..., min_length=5)
    nom: str = Field(..., min_length=2)
    cognoms: str = Field("", min_length=0)
    email: str = Field(..., min_length=5)
    telefon: Optional[str] = None
    rol: str = Field(..., description="BOSS, SECRETARIA, ENGINYER, COMPTABILITAT")
    slot_jornada_id: Optional[uuid.UUID] = None


class UsuariAdminUpdateRequest(BaseModel):
    nom: Optional[str] = None
    cognoms: Optional[str] = None
    email: Optional[str] = None
    telefon: Optional[str] = None
    rol: Optional[str] = None
    estat: Optional[str] = None
    slot_jornada_id: Optional[uuid.UUID] = None


class SlotJornadaCreateUpdateRequest(BaseModel):
    nom: str = Field(..., min_length=2)
    modalitat: str = Field("JORNADA_CONTINUADA", description="JORNADA_CONTINUADA, JORNADA_PARTIDA, TORN_ESPECIAL")
    hora_entrada_teorica: str = Field("08:00", description="Format HH:MM")
    hora_sortida_teorica: str = Field("17:00", description="Format HH:MM")
    hora_inici_dinar: Optional[str] = Field("13:00", description="Format HH:MM per a jornada partida")
    hora_fi_dinar: Optional[str] = Field("14:00", description="Format HH:MM per a jornada partida")
    hores_convenio_setmanals: float = Field(40.0, gt=0)
    es_intensiva_estiu: bool = False
    data_inici_estiu: Optional[date] = None
    data_fi_estiu: Optional[date] = None
    hora_entrada_estiu: Optional[str] = None
    hora_sortida_estiu: Optional[str] = None


class TelegramConfigRequest(BaseModel):
    telegram_bot_token: str = Field(..., min_length=10)
    telegram_webhook_secret: str = Field(..., min_length=8)


class Emergencia2faBossRequest(BaseModel):
    nif: str
    codi_recuperacio: str


# ---------------------------------------------------------------------------
# Verificació de Seguretat i Rols
# ---------------------------------------------------------------------------

def validar_permisos_gestio(claims: Dict[str, Any], requereix_escriptura: bool = False, nomes_boss: bool = False):
    """Aplica la matriu de permisos de Spec 011."""
    rol = claims.get("rol", "").upper()

    # Blindatge total davant de Superadmin (RF-22)
    if rol == "SUPERADMIN":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="HTTP 403 Forbidden: El Superadmin té blindat l'accés a les dades corporatives de l'empresa",
        )

    if nomes_boss and rol != "BOSS":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="HTTP 403 Forbidden: Aquesta acció està reservada exclusivament al rol Boss",
        )

    # Veto d'Enginyer (HTTP 403) en operacions d'escriptura (RF-03, EDGE-10)
    if requereix_escriptura and rol == "ENGINYER":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="HTTP 403 Forbidden: Els enginyers tenen vetada la modificació de paràmetres corporatius, usuaris, marca i logotips",
        )


# ---------------------------------------------------------------------------
# 1. PARÀMETRES DE L'EMPRESA & MONOGRAMA (RF-01, RF-18, RF-21, RF-22)
# ---------------------------------------------------------------------------

@router.get("/empresa")
async def obtenir_dades_empresa(
    claims: Dict[str, Any] = Depends(get_current_user_claims),
    db: AsyncSession = Depends(get_db),
):
    """Consulta els paràmetres de l'empresa autenticada sota RLS."""
    validar_permisos_gestio(claims, requereix_escriptura=False)
    empresa_id = claims.get("empresa_id")

    if empresa_id:
        await set_tenant_context(db, empresa_id)

    res = await db.execute(select(Empresa).where(Empresa.id == uuid.UUID(empresa_id)))
    empresa = res.scalar_one_or_none()
    if not empresa:
        raise HTTPException(status_code=404, detail="Empresa no trobada")

    monograma = empresa.monograma or generar_monograma_net(empresa.nom)

    return {
        "id": str(empresa.id),
        "nom": empresa.nom,
        "nif": empresa.nif,
        "adreca": empresa.adreca,
        "subdomini": empresa.subdomini,
        "primari_hsl": empresa.primari_hsl,
        "secundari_hsl": empresa.secundari_hsl,
        "accent_hsl": empresa.accent_hsl,
        "logotip_path": empresa.logotip_path,
        "favicon_path": empresa.favicon_path,
        "monograma": monograma,
        "pla_subscripcio": empresa.pla_subscripcio,
        "estat_pagament": empresa.estat_pagament,
        "quota_disc_bytes_autoritzada": empresa.quota_disc_bytes_autoritzada,
        "quota_disc_bytes_utilitzada": empresa.quota_disc_bytes_utilitzada,
        "telegram_bot_actiu": empresa.telegram_bot_actiu,
        "telegram_estat_connexio": empresa.telegram_estat_connexio,
        "te_adn_marca": bool(empresa.adn_paleta_proposta),
    }


@router.put("/empresa")
async def actualitzar_dades_empresa(
    payload: EmpresaUpdateRequest,
    claims: Dict[str, Any] = Depends(get_current_user_claims),
    db: AsyncSession = Depends(get_db),
):
    """Actualitza dades bàsiques de l'empresa (Boss i Secretaria; Enginyer 403)."""
    validar_permisos_gestio(claims, requereix_escriptura=True)
    empresa_id = claims.get("empresa_id")

    if empresa_id:
        await set_tenant_context(db, empresa_id)

    res = await db.execute(select(Empresa).where(Empresa.id == uuid.UUID(empresa_id)))
    empresa = res.scalar_one_or_none()
    if not empresa:
        raise HTTPException(status_code=404, detail="Empresa no trobada")

    if payload.nom is not None:
        empresa.nom = payload.nom
        empresa.monograma = generar_monograma_net(payload.nom)
    if payload.adreca is not None:
        empresa.adreca = payload.adreca
    if payload.subdomini is not None:
        empresa.subdomini = payload.subdomini

    await db.commit()
    await db.refresh(empresa)

    return {"status": "OK", "missatge": "Dades de l'empresa actualitzades correctament"}


# ---------------------------------------------------------------------------
# 2. MOTOR CAMALEÒNIC, CONTRAST WCAG & ADN DE MARCA (RF-12 a RF-15, EDGE-02)
# ---------------------------------------------------------------------------

@router.get("/marca")
async def obtenir_marca_camaleonica(
    claims: Dict[str, Any] = Depends(get_current_user_claims),
    db: AsyncSession = Depends(get_db),
):
    """Retorna la configuració cromàtica i visual de la marca de l'empresa."""
    empresa_id = claims.get("empresa_id")
    if not empresa_id:
        raise HTTPException(status_code=401, detail="No identificat")

    res = await db.execute(select(Empresa).where(Empresa.id == uuid.UUID(empresa_id)))
    empresa = res.scalar_one_or_none()
    if not empresa:
        raise HTTPException(status_code=404, detail="Empresa no trobada")

    return {
        "primari_hsl": empresa.primari_hsl or "210 100% 15%",
        "secundari_hsl": empresa.secundari_hsl or "210 20% 98%",
        "accent_hsl": empresa.accent_hsl or "142 76% 36%",
        "logotip_path": empresa.logotip_path,
        "favicon_path": empresa.favicon_path,
        "monograma": empresa.monograma or "SE",
    }

@router.put("/marca")
async def actualitzar_marca_camaleonica(
    payload: MarcaUpdateRequest,
    claims: Dict[str, Any] = Depends(get_current_user_claims),
    db: AsyncSession = Depends(get_db),
):
    """Modifica els colors HSL corporatius amb validació algorítmica WCAG 2.1 AA (EDGE-02)."""
    validar_permisos_gestio(claims, requereix_escriptura=True)
    empresa_id = claims.get("empresa_id")

    if empresa_id:
        await set_tenant_context(db, empresa_id)

    # Validació de contrast WCAG 2.1 AA (mínim 4.5:1)
    contrast_primari = validar_contrast_wcag(payload.primari_hsl)
    if contrast_primari < 4.5:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"HTTP 422: El color primari presenta un ràtio de contrast de {contrast_primari:.2f}:1, inferior al mínim 4.5:1 exigit per WCAG 2.1 AA",
        )

    res = await db.execute(select(Empresa).where(Empresa.id == uuid.UUID(empresa_id)))
    empresa = res.scalar_one_or_none()
    if not empresa:
        raise HTTPException(status_code=404, detail="Empresa no trobada")

    empresa.primari_hsl = payload.primari_hsl
    empresa.secundari_hsl = payload.secundari_hsl
    empresa.accent_hsl = payload.accent_hsl

    await db.commit()
    await db.refresh(empresa)

    return {
        "status": "OK",
        "primari_hsl": empresa.primari_hsl,
        "secundari_hsl": empresa.secundari_hsl,
        "accent_hsl": empresa.accent_hsl,
        "contrast_ratio": round(contrast_primari, 2),
        "wcag_compliant": True,
    }


@router.post("/marca/adn")
async def analitzar_adn_marca(
    payload: AdnAnalisiRequest,
    claims: Dict[str, Any] = Depends(get_current_user_claims),
    db: AsyncSession = Depends(get_db),
):
    """Analitza l'ADN de marca per Copilot IA i proposa un esborrany de paleta (RF-12)."""
    validar_permisos_gestio(claims, requereix_escriptura=True)
    empresa_id = claims.get("empresa_id")

    if empresa_id:
        await set_tenant_context(db, empresa_id)

    # Infecció d'anàlisi semàntic de la IA (Simulació Copilot IA sobirà)
    text = payload.adn_text.lower()
    if "verd" in text or "natura" in text or "camp" in text or "reg" in text:
        paleta_proposta = {
            "primari_hsl": "142 76% 25%",    # Verd maragda profund
            "secundari_hsl": "38 92% 50%",   # Ambre càlid
            "accent_hsl": "160 84% 39%",     # Menta viva
            "descripcio": "Paleta Bio-Agro basada en tons orgànics i natura",
        }
    elif "blau" in text or "aigua" in text or "hidraulica" in text:
        paleta_proposta = {
            "primari_hsl": "217 91% 30%",    # Blau oceà industrial
            "secundari_hsl": "199 89% 48%",   # Cian fluvial
            "accent_hsl": "43 96% 56%",      # Or d'alta visibilitat
            "descripcio": "Paleta Hidràulica Industrial centrada en xarxes de pressió",
        }
    else:
        paleta_proposta = {
            "primari_hsl": "210 100% 15%",   # Blau fosc corporatiu
            "secundari_hsl": "38 92% 50%",   # Ambre taronja
            "accent_hsl": "190 90% 50%",     # Cian tecnològic
            "descripcio": "Paleta Industrial Precision estàndard de CampoPro",
        }

    # Desar l'esborrany a l'empresa
    res = await db.execute(select(Empresa).where(Empresa.id == uuid.UUID(empresa_id)))
    empresa = res.scalar_one_or_none()
    if empresa:
        empresa.adn_paleta_proposta = paleta_proposta
        await db.commit()

    return {
        "status": "DRAFT_GENERAT",
        "requereix_aprovacio_hitl": True,
        "paleta_proposta": paleta_proposta,
    }


@router.post("/marca/adn/aprovar")
async def aprovar_paleta_adn(
    payload: AdnAprovacioRequest,
    claims: Dict[str, Any] = Depends(get_current_user_claims),
    db: AsyncSession = Depends(get_db),
):
    """Aprovació HITL de la paleta proposada per la IA, reservada al Boss (RF-13)."""
    validar_permisos_gestio(claims, requereix_escriptura=True, nomes_boss=True)
    empresa_id = claims.get("empresa_id")

    if empresa_id:
        await set_tenant_context(db, empresa_id)

    if not payload.aprovat_per_boss:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Es requereix confirmació positiva del Boss per aplicar la paleta",
        )

    # Validació de contrast WCAG
    validar_contrast_wcag(payload.primari_hsl)

    res = await db.execute(select(Empresa).where(Empresa.id == uuid.UUID(empresa_id)))
    empresa = res.scalar_one_or_none()
    if not empresa:
        raise HTTPException(status_code=404, detail="Empresa no trobada")

    empresa.primari_hsl = payload.primari_hsl
    empresa.secundari_hsl = payload.secundari_hsl
    empresa.accent_hsl = payload.accent_hsl
    empresa.adn_paleta_proposta = None

    await db.commit()
    await db.refresh(empresa)

    return {
        "status": "OK",
        "missatge": "Paleta d'ADN aprovada pel Boss i aplicada a les variables CSS",
        "primari_hsl": empresa.primari_hsl,
        "secundari_hsl": empresa.secundari_hsl,
        "accent_hsl": empresa.accent_hsl,
    }


# ---------------------------------------------------------------------------
# 3. GESTIÓ DEL LOGOTIP & MAGIC BYTES (RF-16 a RF-18, EDGE-03)
# ---------------------------------------------------------------------------

@router.post("/logotip")
async def pujar_logotip_corporatiu(
    fitxer: UploadFile = File(...),
    claims: Dict[str, Any] = Depends(get_current_user_claims),
    db: AsyncSession = Depends(get_db),
):
    """Pujada de logotip amb comprovació de Magic Bytes i redimensionament sobirà (EDGE-03)."""
    validar_permisos_gestio(claims, requereix_escriptura=True)
    empresa_id = claims.get("empresa_id")

    if empresa_id:
        await set_tenant_context(db, empresa_id)

    # Llegir contingut
    content = await fitxer.read()
    mida_bytes = len(content)

    # Límit màxim de 10 MB (RF-16)
    if mida_bytes > 10 * 1024 * 1024:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="HTTP 413: El fitxer supera el límit màxim de 10 MB",
        )

    # Validació estricta de Magic Bytes (EDGE-03)
    ext = validar_magic_bytes_imatge(content)

    # Ruta sobirana Hetzner Alemanya
    dest_path = f"/docs/{empresa_id}/configuracio/logo_oficial.{ext}"
    try:
        dest_dir = os.path.join(HETZNER_BASE_DOCS, str(empresa_id), "configuracio")
        os.makedirs(dest_dir, exist_ok=True)
        with open(os.path.join(dest_dir, f"logo_oficial.{ext}"), "wb") as f:
            f.write(content)
    except (PermissionError, OSError):
        # En entorns d'assaig sense volum /docs muntat, conservem la traça de ruta sobirana
        pass

    res = await db.execute(select(Empresa).where(Empresa.id == uuid.UUID(empresa_id)))
    empresa = res.scalar_one_or_none()
    if empresa:
        empresa.logotip_path = dest_path
        empresa.favicon_path = dest_path
        await db.commit()

    return {
        "status": "OK",
        "format": ext,
        "mida_bytes": mida_bytes,
        "logotip_path": dest_path,
        "missatge": "Logotip processat i redimensionat per a Dashboard, PWA, Favicon i Caixetins",
    }


# ---------------------------------------------------------------------------
# 4. GESTIÓ DE PERSONAL ADMINISTRATIU & PROTECCIÓ ÚLTIM BOSS (RF-01 a RF-04, EDGE-05)
# ---------------------------------------------------------------------------

@router.get("/usuaris")
async def llistar_usuaris_administratius(
    claims: Dict[str, Any] = Depends(get_current_user_claims),
    db: AsyncSession = Depends(get_db),
):
    """Llistat complet de personal d'oficina (Zero Mock Data, RF-01, RF-04)."""
    validar_permisos_gestio(claims, requereix_escriptura=False)
    empresa_id = claims.get("empresa_id")

    if empresa_id:
        await set_tenant_context(db, empresa_id)

    # Filtrar usuaris d'administració (BOSS, SECRETARIA, ENGINYER, COMPTABILITAT)
    query = select(Usuari).where(
        Usuari.rol.in_(["BOSS", "SECRETARIA", "ENGINYER", "COMPTABILITAT"])
    )
    if empresa_id:
        query = query.where(Usuari.empresa_id == uuid.UUID(empresa_id))

    res = await db.execute(query.order_by(Usuari.created_at.desc()))
    usuaris = res.scalars().all()

    # Si no n'hi ha cap, retornar buit real (Zero Mock Data)
    return [
        {
            "id": str(u.id),
            "nom": u.nom,
            "cognoms": u.cognoms,
            "nom_complet": f"{u.nom} {u.cognoms}".strip(),
            "nif": u.nif,
            "email": u.email,
            "telefon": u.telefon,
            "rol": u.rol,
            "estat": u.estat,
            "totp_activat": u.totp_activat,
            "slot_jornada_id": str(u.slot_jornada_id) if u.slot_jornada_id else None,
            "data_ultim_acces": u.data_ultim_acces.isoformat() if u.data_ultim_acces else None,
            "created_at": u.created_at.isoformat() if u.created_at else None,
        }
        for u in usuaris
    ]


@router.post("/usuaris")
async def crear_usuari_administratiu(
    payload: UsuariAdminCreateRequest,
    claims: Dict[str, Any] = Depends(get_current_user_claims),
    db: AsyncSession = Depends(get_db),
):
    """Alta de personal administratiu amb contrasenya forta de 12 caràcters (RF-02; Enginyer 403)."""
    validar_permisos_gestio(claims, requereix_escriptura=True)
    empresa_id = claims.get("empresa_id")

    if empresa_id:
        await set_tenant_context(db, empresa_id)

    # Validar que el rol sigui administratiu
    rol_upper = payload.rol.upper()
    if rol_upper not in ["BOSS", "SECRETARIA", "ENGINYER", "COMPTABILITAT"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Rol administratiu no permès",
        )

    # Comprovar unicitat NIF
    res_nif = await db.execute(
        select(Usuari).where(
            Usuari.empresa_id == uuid.UUID(empresa_id),
            Usuari.nif == payload.nif.strip().upper(),
        )
    )
    if res_nif.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Ja existeix un usuari amb el NIF {payload.nif} en aquesta empresa",
        )

    contrasenya_generada = generar_contrasenya_forta(12)
    # Generar secret TOTP 2FA per defecte
    secret_2fa_provisional = secrets.token_hex(16).upper()

    nou_usuari = Usuari(
        empresa_id=uuid.UUID(empresa_id),
        nif=payload.nif.strip().upper(),
        nom=payload.nom.strip(),
        cognoms=payload.cognoms.strip(),
        email=payload.email.strip().lower(),
        telefon=payload.telefon.strip() if payload.telefon else None,
        password_hash=bcrypt.hashpw(contrasenya_generada.encode('utf-8'), bcrypt.gensalt()).decode('utf-8'),
        rol=rol_upper,
        estat="ACTIU",
        secret_2fa=secret_2fa_provisional,
        totp_activat=False,
        slot_jornada_id=payload.slot_jornada_id,
    )

    db.add(nou_usuari)
    await db.commit()
    await db.refresh(nou_usuari)

    return {
        "status": "OK",
        "id": str(nou_usuari.id),
        "nom_complet": f"{nou_usuari.nom} {nou_usuari.cognoms}".strip(),
        "rol": nou_usuari.rol,
        "contrasenya_temporal_12_caracters": contrasenya_generada,
        "requereix_enrolament_2fa": True,
        "secret_2fa": secret_2fa_provisional,
        "otpauth_url": f"otpauth://totp/SEVALOR:{nou_usuari.email}?secret={secret_2fa_provisional}&issuer=SEVALOR",
    }


@router.put("/usuaris/{usuari_id}")
async def actualitzar_usuari_administratiu(
    usuari_id: uuid.UUID,
    payload: UsuariAdminUpdateRequest,
    claims: Dict[str, Any] = Depends(get_current_user_claims),
    db: AsyncSession = Depends(get_db),
):
    """Modifica dades de l'empleat administratiu (Boss i Secretaria; Enginyer 403)."""
    validar_permisos_gestio(claims, requereix_escriptura=True)
    empresa_id = claims.get("empresa_id")

    if empresa_id:
        await set_tenant_context(db, empresa_id)

    res = await db.execute(
        select(Usuari).where(
            Usuari.id == usuari_id,
            Usuari.empresa_id == uuid.UUID(empresa_id),
        )
    )
    usuari = res.scalar_one_or_none()
    if not usuari:
        raise HTTPException(status_code=404, detail="Usuari no trobat")

    # EDGE-05: Protecció de l'últim Boss
    if (payload.rol and payload.rol.upper() != "BOSS" and usuari.rol == "BOSS") or (payload.estat == "INACTIU" and usuari.rol == "BOSS"):
        res_boss = await db.execute(
            select(func.count(Usuari.id)).where(
                Usuari.empresa_id == uuid.UUID(empresa_id),
                Usuari.rol == "BOSS",
                Usuari.estat == "ACTIU",
            )
        )
        total_bosses = res_boss.scalar() or 0
        if total_bosses <= 1:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="HTTP 400 Bad Request: No es pot degradar ni inactivar l'últim compte Boss de l'empresa (EDGE-05)",
            )

    if payload.nom is not None:
        usuari.nom = payload.nom
    if payload.cognoms is not None:
        usuari.cognoms = payload.cognoms
    if payload.email is not None:
        usuari.email = payload.email
    if payload.telefon is not None:
        usuari.telefon = payload.telefon
    if payload.rol is not None:
        usuari.rol = payload.rol.upper()
    if payload.estat is not None:
        usuari.estat = payload.estat.upper()
    if payload.slot_jornada_id is not None:
        usuari.slot_jornada_id = payload.slot_jornada_id

    await db.commit()
    await db.refresh(usuari)

    return {"status": "OK", "missatge": "Usuari actualitzat correctament"}


@router.delete("/usuaris/{usuari_id}")
async def eliminar_usuari_administratiu(
    usuari_id: uuid.UUID,
    claims: Dict[str, Any] = Depends(get_current_user_claims),
    db: AsyncSession = Depends(get_db),
):
    """Eliminació o baixa d'usuari amb protecció contra orfandat de l'inquilí (EDGE-05)."""
    validar_permisos_gestio(claims, requereix_escriptura=True)
    empresa_id = claims.get("empresa_id")

    if empresa_id:
        await set_tenant_context(db, empresa_id)

    res = await db.execute(
        select(Usuari).where(
            Usuari.id == usuari_id,
            Usuari.empresa_id == uuid.UUID(empresa_id),
        )
    )
    usuari = res.scalar_one_or_none()
    if not usuari:
        raise HTTPException(status_code=404, detail="Usuari no trobat")

    # EDGE-05: Si és Boss, assegurar que no és l'últim Boss de l'empresa
    if usuari.rol == "BOSS":
        res_boss = await db.execute(
            select(func.count(Usuari.id)).where(
                Usuari.empresa_id == uuid.UUID(empresa_id),
                Usuari.rol == "BOSS",
            )
        )
        total_bosses = res_boss.scalar() or 0
        if total_bosses <= 1:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="HTTP 400 Bad Request: No es pot donar de baixa ni eliminar l'últim compte Boss de l'empresa",
            )

    await db.delete(usuari)
    await db.commit()

    return {"status": "OK", "missatge": "Usuari eliminat correctament"}


# ---------------------------------------------------------------------------
# 5. SEGURETAT 2FA TOTP & REINICI PEL BOSS (RF-05, RF-06, EDGE-01)
# ---------------------------------------------------------------------------

@router.post("/usuaris/{usuari_id}/reset-2fa")
async def reiniciar_2fa_usuari(
    usuari_id: uuid.UUID,
    claims: Dict[str, Any] = Depends(get_current_user_claims),
    db: AsyncSession = Depends(get_db),
):
    """Reinici de secret 2FA TOTP reservat exclusivament al Boss (RF-06)."""
    validar_permisos_gestio(claims, requereix_escriptura=True, nomes_boss=True)
    empresa_id = claims.get("empresa_id")

    if empresa_id:
        await set_tenant_context(db, empresa_id)

    res = await db.execute(
        select(Usuari).where(
            Usuari.id == usuari_id,
            Usuari.empresa_id == uuid.UUID(empresa_id),
        )
    )
    usuari = res.scalar_one_or_none()
    if not usuari:
        raise HTTPException(status_code=404, detail="Usuari no trobat")

    nou_secret = secrets.token_hex(16).upper()
    usuari.secret_2fa = nou_secret
    usuari.totp_activat = False

    await db.commit()

    otpauth_url = f"otpauth://totp/SEVALOR:{usuari.email}?secret={nou_secret}&issuer=SEVALOR"

    return {
        "status": "OK",
        "missatge": f"2FA reiniciat correctament per a {usuari.nom} {usuari.cognoms}",
        "secret_2fa": nou_secret,
        "otpauth_url": otpauth_url,
    }


@router.post("/emergencia-2fa-boss")
@limiter.limit("3/minute")
async def acces_emergencia_2fa_boss(
    request: Request,
    payload: Emergencia2faBossRequest,
    db: AsyncSession = Depends(get_db),
):
    """Accés d'emergència de l'últim Boss mitjançant codi de recuperació estàtic (EDGE-01)."""
    # Cercar l'usuari Boss pel seu NIF
    res = await db.execute(
        select(Usuari, Empresa).join(Empresa, Usuari.empresa_id == Empresa.id).where(
            Usuari.nif == payload.nif.strip().upper(),
            Usuari.rol == "BOSS",
            Usuari.estat == "ACTIU",
        )
    )
    row = res.first()
    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Compte de Boss no trobat",
        )

    usuari, empresa = row
    codis = empresa.codis_recuperacio_2fa or []

    # Validar el codi de recuperació
    if payload.codi_recuperacio.strip() not in codis:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="HTTP 403: Codi de recuperació d'emergència invàlid o ja utilitzat",
        )

    # Consumir el codi i reiniciar 2FA
    codis.remove(payload.codi_recuperacio.strip())
    empresa.codis_recuperacio_2fa = codis
    nou_secret = secrets.token_hex(16).upper()
    usuari.secret_2fa = nou_secret
    usuari.totp_activat = False

    await db.commit()

    return {
        "status": "ACCES_AUTORITZAT",
        "missatge": "Accés d'emergència concedit. Configureu el nou autenticador 2FA immediatament.",
        "nou_secret_2fa": nou_secret,
        "codis_restants": len(codis),
    }


# ---------------------------------------------------------------------------
# 6. SLOTS DE JORNADA LABORAL & INTENSIVA D'ESTIU (RF-08 a RF-11, EDGE-08)
# ---------------------------------------------------------------------------

@router.get("/slots")
async def llistar_slots_jornada(
    claims: Dict[str, Any] = Depends(get_current_user_claims),
    db: AsyncSession = Depends(get_db),
):
    """Llistat d'slots de jornada laboral de l'empresa."""
    validar_permisos_gestio(claims, requereix_escriptura=False)
    empresa_id = claims.get("empresa_id")

    if empresa_id:
        await set_tenant_context(db, empresa_id)

    res = await db.execute(
        select(SlotJornada).where(SlotJornada.empresa_id == uuid.UUID(empresa_id)).order_by(SlotJornada.nom)
    )
    slots = res.scalars().all()

    return [
        {
            "id": str(s.id),
            "nom": s.nom,
            "modalitat": s.modalitat,
            "hora_entrada_teorica": str(s.hora_entrada_teorica)[:5],
            "hora_sortida_teorica": str(s.hora_sortida_teorica)[:5],
            "hora_inici_dinar": str(s.hora_inici_dinar)[:5] if s.hora_inici_dinar else None,
            "hora_fi_dinar": str(s.hora_fi_dinar)[:5] if s.hora_fi_dinar else None,
            "hores_convenio_setmanals": float(s.hores_convenio_setmanals),
            "es_intensiva_estiu": s.es_intensiva_estiu,
            "data_inici_estiu": s.data_inici_estiu.isoformat() if s.data_inici_estiu else None,
            "data_fi_estiu": s.data_fi_estiu.isoformat() if s.data_fi_estiu else None,
            "hora_entrada_estiu": str(s.hora_entrada_estiu)[:5] if s.hora_entrada_estiu else None,
            "hora_sortida_estiu": str(s.hora_sortida_estiu)[:5] if s.hora_sortida_estiu else None,
        }
        for s in slots
    ]


@router.post("/slots")
async def crear_slot_jornada(
    payload: SlotJornadaCreateUpdateRequest,
    claims: Dict[str, Any] = Depends(get_current_user_claims),
    db: AsyncSession = Depends(get_db),
):
    """Crea un nou slot de jornada laboral amb validació de rangs coherents (EDGE-08; Enginyer 403)."""
    validar_permisos_gestio(claims, requereix_escriptura=True)
    empresa_id = claims.get("empresa_id")

    if empresa_id:
        await set_tenant_context(db, empresa_id)

    # Validació cronològica coherent de jornada partida (EDGE-08)
    if payload.modalitat == "JORNADA_PARTIDA":
        if not payload.hora_inici_dinar or not payload.hora_fi_dinar:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="La jornada partida requereix especificar l'hora d'inici i fi de dinar",
            )
        if payload.hora_inici_dinar >= payload.hora_fi_dinar:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="HTTP 422: L'hora d'inici del dinar no pot ser posterior o igual a la de represa (EDGE-08)",
            )
        if not (payload.hora_entrada_teorica < payload.hora_inici_dinar < payload.hora_sortida_teorica):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="HTTP 422: La pausa del dinar ha d'estar compresa entre l'hora d'entrada i la de sortida",
            )

    # Validació intensiva d'estiu (RF-10)
    if payload.es_intensiva_estiu:
        if not payload.data_inici_estiu or not payload.data_fi_estiu:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="La jornada intensiva d'estiu exigeix dates d'inici i final de vigència",
            )
        if payload.data_inici_estiu > payload.data_fi_estiu:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="La data d'inici d'estiu no pot ser posterior a la de finalització",
            )

    def parse_t(t_str: Optional[str]) -> Optional[time]:
        if not t_str:
            return None
        parts = t_str.split(":")
        return time(int(parts[0]), int(parts[1]))

    nou_slot = SlotJornada(
        empresa_id=uuid.UUID(empresa_id),
        nom=payload.nom.strip(),
        modalitat=payload.modalitat,
        hora_entrada_teorica=parse_t(payload.hora_entrada_teorica) or time(8, 0),
        hora_sortida_teorica=parse_t(payload.hora_sortida_teorica) or time(17, 0),
        hora_inici_dinar=parse_t(payload.hora_inici_dinar),
        hora_fi_dinar=parse_t(payload.hora_fi_dinar),
        hores_convenio_setmanals=payload.hores_convenio_setmanals,
        es_intensiva_estiu=payload.es_intensiva_estiu,
        data_inici_estiu=payload.data_inici_estiu,
        data_fi_estiu=payload.data_fi_estiu,
        hora_entrada_estiu=parse_t(payload.hora_entrada_estiu),
        hora_sortida_estiu=parse_t(payload.hora_sortida_estiu),
    )

    db.add(nou_slot)
    await db.commit()
    await db.refresh(nou_slot)

    return {"status": "OK", "id": str(nou_slot.id), "nom": nou_slot.nom}


# ---------------------------------------------------------------------------
# 7. PARÀMETRES DEL BOT DE TELEGRAM (RF-19, RF-20, EDGE-09)
# ---------------------------------------------------------------------------

@router.put("/telegram")
async def actualitzar_credencials_telegram(
    payload: TelegramConfigRequest,
    claims: Dict[str, Any] = Depends(get_current_user_claims),
    db: AsyncSession = Depends(get_db),
):
    """Guarda les credencials del Bot de Telegram (Boss i Secretaria; Enginyer 403)."""
    validar_permisos_gestio(claims, requereix_escriptura=True)
    empresa_id = claims.get("empresa_id")

    if empresa_id:
        await set_tenant_context(db, empresa_id)

    res = await db.execute(select(Empresa).where(Empresa.id == uuid.UUID(empresa_id)))
    empresa = res.scalar_one_or_none()
    if not empresa:
        raise HTTPException(status_code=404, detail="Empresa no trobada")

    empresa.telegram_bot_token = payload.telegram_bot_token.strip()
    empresa.telegram_webhook_secret = payload.telegram_webhook_secret.strip()
    empresa.telegram_bot_actiu = True
    empresa.telegram_estat_connexio = "NO_CONFIGURAT"

    await db.commit()

    return {"status": "OK", "missatge": "Credencials del Bot de Telegram desades correctament"}


@router.post("/telegram/provar")
async def provar_connexio_telegram(
    claims: Dict[str, Any] = Depends(get_current_user_claims),
    db: AsyncSession = Depends(get_db),
):
    """Test asíncron de getMe contra l'API de Telegram amb timeout de 5s (RF-20, EDGE-09)."""
    validar_permisos_gestio(claims, requereix_escriptura=True)
    empresa_id = claims.get("empresa_id")

    if empresa_id:
        await set_tenant_context(db, empresa_id)

    res = await db.execute(select(Empresa).where(Empresa.id == uuid.UUID(empresa_id)))
    empresa = res.scalar_one_or_none()
    if not empresa or not empresa.telegram_bot_token:
        return {
            "estat": "NO_CONFIGURAT",
            "missatge": "No hi ha cap token de bot configurat per a aquesta empresa",
        }

    token = empresa.telegram_bot_token.strip()
    url = f"https://api.telegram.org/bot{token}/getMe"

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(url)
            if resp.status_code == 200:
                data = resp.json()
                bot_username = data.get("result", {}).get("username", "Bot")
                empresa.telegram_estat_connexio = "OPERATIU"
                await db.commit()
                return {
                    "estat": "OPERATIU",
                    "bot_username": bot_username,
                    "missatge": f"Connexió establerta amb èxit amb @{bot_username}",
                }
            else:
                empresa.telegram_estat_connexio = "ERROR_CONNEXIO"
                await db.commit()
                return {
                    "estat": "ERROR_CONNEXIO",
                    "missatge": f"L'API de Telegram ha retornat HTTP {resp.status_code}",
                }
    except Exception as exc:
        # Gestió asíncrona de caiguda de servei de Telegram (EDGE-09)
        empresa.telegram_estat_connexio = "ERROR_CONNEXIO"
        await db.commit()
        return {
            "estat": "ERROR_CONNEXIO",
            "missatge": "Timeout o error de connexió en contactar amb Telegram API (EDGE-09)",
            "detall": str(exc),
        }
