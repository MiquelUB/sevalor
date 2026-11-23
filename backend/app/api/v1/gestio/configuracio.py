"""Endpoints de configuració de l'empresa, jornada laboral, personal, Telegram i barema (/gestio/configuracio — Spec 011).

Nota de Governança: La Paleta Camaleònica (colors HSL, logotip) i el Node Sobirà / Túnel IA
es configuren exclusivament des de Superadmin (/superadmin/empreses/{id} i /superadmin/tenants).
"""

import base64
import os
import secrets
import string
import uuid
from datetime import date, time
from typing import Any, Dict, List, Optional

import bcrypt
import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy import func, select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db, set_tenant_context
from app.core.security import get_current_user_claims
from app.models.models import Empresa, OrdreTreball, OutboxEnviamentAEAT, SlotJornada, Usuari
from app.services.outbox_aeat import validar_i_extreure_metadata_p12
from app.services.sovereign_storage import SovereignStorageGateway
from app.services.verifactu import desxifrar_secret_verifactu, xifrar_secret_verifactu

router = APIRouter(prefix="/gestio/configuracio", tags=["Configuració"])
limiter = Limiter(key_func=get_remote_address, enabled=os.getenv("TESTING") != "1")


# ---------------------------------------------------------------------------
# Utilitats i Validacions Criptogràfiques
# ---------------------------------------------------------------------------


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


def generar_secret_totp_base32() -> str:
    """Genera un secret TOTP en format Base32 estàndard RFC 4648 (16 caràcters A-Z, 2-7) compatible amb Google Authenticator."""
    return base64.b32encode(secrets.token_bytes(10)).decode("utf-8").rstrip("=")


def generar_monograma_net(nom: str) -> str:
    """Genera un monograma de 2 caràcters basat en la raó social (RF-18)."""
    STOP_WORDS = {
        "de",
        "del",
        "dels",
        "la",
        "les",
        "el",
        "els",
        "i",
        "sl",
        "sa",
        "sll",
        "sc",
        "slu",
    }
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
    rao_social_fiscal: Optional[str] = None
    eslogan_activitat: Optional[str] = None
    adreca: Optional[str] = None
    codi_postal: Optional[str] = None
    poblacio: Optional[str] = None
    provincia: Optional[str] = None
    telefon_facturacio: Optional[str] = None
    email_facturacio: Optional[str] = None
    titular_compte_bancari: Optional[str] = None
    iban_cobrament: Optional[str] = None
    dades_registre_mercantil: Optional[str] = None
    verifactu_entorn: Optional[str] = Field(None, pattern="^(PREPRODUCCIO|PRODUCCIO)$")
    subdomini: Optional[str] = None


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
    modalitat: str = Field(
        "JORNADA_CONTINUADA", description="JORNADA_CONTINUADA, JORNADA_PARTIDA, TORN_ESPECIAL"
    )
    hora_entrada_teorica: str = Field("08:00", description="Format HH:MM")
    hora_sortida_teorica: str = Field("17:00", description="Format HH:MM")
    hora_inici_dinar: Optional[str] = Field(
        "13:00", description="Format HH:MM per a jornada partida"
    )
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


class BaremaPartidaDTO(BaseModel):
    codi: str = Field(..., max_length=40)
    descripcio: str = Field(..., max_length=200)
    unitat: str = Field("h", max_length=20)
    preu_eur: float = Field(..., ge=0)


class BaremaConfigRequest(BaseModel):
    preu_hora_standard_eur: float = Field(0.0, ge=0)
    tarifa_urgencia_eur: float = Field(0.0, ge=0)
    suplement_desplacament_eur: float = Field(0.0, ge=0)
    marge_materials_defecte_pct: float = Field(0.0, ge=0)
    partides: list[BaremaPartidaDTO] = Field(default_factory=list)


class Emergencia2faBossRequest(BaseModel):
    nif: str
    codi_recuperacio: str


# ---------------------------------------------------------------------------
# Verificació de Seguretat i Rols
# ---------------------------------------------------------------------------


def validar_permisos_gestio(
    claims: Dict[str, Any], requereix_escriptura: bool = False, nomes_boss: bool = False
) -> None:
    """Aplica la matriu de permisos de Spec 011."""
    rol = claims.get("rol", "").upper()
    is_impersonation = bool(claims.get("is_impersonation", False))

    # Blindatge total davant de Superadmin directe sense impersonació (RF-22)
    if rol == "SUPERADMIN" and not is_impersonation:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="HTTP 403 Forbidden: El Superadmin té blindat l'accés a les dades corporatives de l'empresa sense sessió d'impersonació",
        )

    # Si està en sessió d'impersonació autoritzada del tenant, actua amb delegació de gestió
    if nomes_boss and rol != "BOSS" and not (rol == "SUPERADMIN" and is_impersonation):
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
@router.get("/empresa/")
async def obtenir_dades_empresa(
    claims: Dict[str, Any] = Depends(get_current_user_claims),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
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
    rol_usuari = str(claims.get("rol") or "").upper()
    pot_veure_iban = rol_usuari in ("BOSS", "SECRETARIA", "COMPTABILITAT") or (
        rol_usuari == "SUPERADMIN" and bool(claims.get("is_impersonation"))
    )

    return {
        "id": str(empresa.id),
        "nom": empresa.nom,
        "rao_social_fiscal": empresa.rao_social_fiscal or empresa.nom,
        "eslogan_activitat": empresa.eslogan_activitat,
        "nif": empresa.nif,
        "vertical": empresa.vertical,
        "magatzem_families_default": empresa.magatzem_families_default,
        "agent_prompt_system": empresa.agent_prompt_system,
        "adreca": empresa.adreca,
        "codi_postal": empresa.codi_postal,
        "poblacio": empresa.poblacio,
        "provincia": empresa.provincia,
        "telefon_facturacio": empresa.telefon_facturacio,
        "email_facturacio": empresa.email_facturacio,
        "titular_compte_bancari": empresa.titular_compte_bancari if pot_veure_iban else None,
        "iban_cobrament": (
            desxifrar_secret_verifactu(empresa.iban_cobrament_xifrat)
            if (pot_veure_iban and empresa.iban_cobrament_xifrat)
            else None
        ),
        "dades_registre_mercantil": empresa.dades_registre_mercantil,
        "verifactu_entorn": empresa.verifactu_entorn or "PREPRODUCCIO",
        "verifactu_cert_configurat": bool(empresa.verifactu_cert_path),
        "verifactu_cert_subject": empresa.verifactu_cert_subject,
        "verifactu_cert_caducitat": (
            empresa.verifactu_cert_caducitat.isoformat()
            if empresa.verifactu_cert_caducitat
            else None
        ),
        "subdomini": empresa.subdomini,
        "domini_custom": empresa.domini_custom,
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
        "feature_copilot_ia": empresa.feature_copilot_ia,
        "feature_flota": empresa.feature_flota,
        "feature_planols": empresa.feature_planols,
        "feature_telegram": empresa.feature_telegram,
        "node_ia_actiu": empresa.node_ia_actiu,
    }


@router.put("/empresa")
async def actualitzar_dades_empresa(
    payload: EmpresaUpdateRequest,
    claims: Dict[str, Any] = Depends(get_current_user_claims),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """Actualitza dades corporatives, fiscals, bancàries i d'entorn Veri*factu de l'empresa (només Boss)."""
    validar_permisos_gestio(claims, requereix_escriptura=True, nomes_boss=True)
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
    if payload.rao_social_fiscal is not None:
        empresa.rao_social_fiscal = payload.rao_social_fiscal.strip() or None
    if payload.eslogan_activitat is not None:
        empresa.eslogan_activitat = payload.eslogan_activitat.strip() or None
    if payload.adreca is not None:
        empresa.adreca = payload.adreca
    if payload.codi_postal is not None:
        empresa.codi_postal = payload.codi_postal.strip() or None
    if payload.poblacio is not None:
        empresa.poblacio = payload.poblacio.strip() or None
    if payload.provincia is not None:
        empresa.provincia = payload.provincia.strip() or None
    if payload.telefon_facturacio is not None:
        empresa.telefon_facturacio = payload.telefon_facturacio.strip() or None
    if payload.email_facturacio is not None:
        empresa.email_facturacio = payload.email_facturacio.strip() or None
    if payload.titular_compte_bancari is not None:
        empresa.titular_compte_bancari = payload.titular_compte_bancari.strip() or None
    if payload.iban_cobrament is not None:
        iban_clean = payload.iban_cobrament.replace(" ", "").strip().upper()
        empresa.iban_cobrament_xifrat = xifrar_secret_verifactu(iban_clean) if iban_clean else None
    if payload.dades_registre_mercantil is not None:
        empresa.dades_registre_mercantil = payload.dades_registre_mercantil.strip() or None
    if payload.verifactu_entorn is not None:
        empresa.verifactu_entorn = payload.verifactu_entorn.strip().upper()
    if payload.subdomini is not None:
        empresa.subdomini = payload.subdomini

    await db.commit()

    return {"status": "OK", "missatge": "Dades de l'empresa actualitzades correctament"}


# ---------------------------------------------------------------------------
# 2. MOTOR CAMALEÒNIC, CONTRAST WCAG & ADN DE MARCA (RF-12 a RF-15, EDGE-02)
# ---------------------------------------------------------------------------


@router.get("/marca")
@router.get("/marca/")
async def obtenir_marca_camaleonica(
    claims: Dict[str, Any] = Depends(get_current_user_claims),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """Retorna la configuració cromàtica i visual de la marca de l'empresa."""
    empresa_id = claims.get("empresa_id")
    if not empresa_id or empresa_id == "undefined":
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


# ---------------------------------------------------------------------------
# 3. GESTIÓ DE PERSONAL ADMINISTRATIU & PROTECCIÓ ÚLTIM BOSS (RF-01 a RF-04, EDGE-05)
# ---------------------------------------------------------------------------


@router.get("/usuaris")
async def llistar_usuaris_administratius(
    claims: Dict[str, Any] = Depends(get_current_user_claims),
    db: AsyncSession = Depends(get_db),
) -> List[Dict[str, Any]]:
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
) -> Dict[str, Any]:
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

    # Comprovar unicitat NIF i Email dins la plataforma
    nif_clean = payload.nif.strip().upper()
    email_clean = payload.email.strip().lower()

    res_nif = await db.execute(
        select(Usuari).where(
            Usuari.empresa_id == uuid.UUID(empresa_id),
            Usuari.nif == nif_clean,
        )
    )
    if res_nif.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Ja existeix un usuari amb el NIF {nif_clean} en aquesta empresa",
        )

    # Comprovar que l'email no estigui duplicat a cap empresa (evita bloqueig a /auth/login)
    res_role = await db.execute(text("SELECT current_user;"))
    current_role = res_role.scalar()
    await db.execute(text("RESET ROLE;"))
    try:
        res_email = await db.execute(select(Usuari).where(func.lower(Usuari.email) == email_clean))
        usuari_existent_email = res_email.scalars().first()
    finally:
        if current_role:
            await db.execute(text(f'SET ROLE "{current_role}";'))

    if usuari_existent_email:
        if str(usuari_existent_email.empresa_id) == str(empresa_id):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Ja existeix un usuari amb el correu {email_clean} en aquesta empresa. Utilitzeu el botó de restablir contrasenya a la taula.",
            )
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"El correu electrònic {email_clean} ja està registrat a la plataforma.",
        )

    contrasenya_generada = generar_contrasenya_forta(12)
    # Generar secret TOTP 2FA en Base32 RFC 4648 compatible amb Google Authenticator
    secret_2fa_provisional = generar_secret_totp_base32()

    nou_usuari = Usuari(
        id=uuid.uuid4(),
        empresa_id=uuid.UUID(empresa_id),
        nif=nif_clean,
        nom=payload.nom.strip(),
        cognoms=payload.cognoms.strip(),
        email=email_clean,
        telefon=payload.telefon.strip() if payload.telefon else None,
        password_hash=bcrypt.hashpw(contrasenya_generada.encode("utf-8"), bcrypt.gensalt()).decode(
            "utf-8"
        ),
        rol=rol_upper,
        estat="ACTIU",
        secret_2fa=secret_2fa_provisional,
        totp_activat=False,
        slot_jornada_id=payload.slot_jornada_id,
    )

    db.add(nou_usuari)
    await db.flush()
    usuari_id_str = str(nou_usuari.id)
    created_at_iso = nou_usuari.created_at.isoformat() if nou_usuari.created_at else None
    await db.commit()

    try:
        from app.services.flota_service import sincronitzar_operari_al_disc_empresa

        await sincronitzar_operari_al_disc_empresa(db, uuid.UUID(empresa_id), nou_usuari)
    except Exception:
        pass

    return {
        "status": "OK",
        "id": usuari_id_str,
        "nom": nou_usuari.nom,
        "cognoms": nou_usuari.cognoms,
        "nom_complet": f"{nou_usuari.nom} {nou_usuari.cognoms}".strip(),
        "nif": nou_usuari.nif,
        "email": nou_usuari.email,
        "telefon": nou_usuari.telefon,
        "rol": nou_usuari.rol,
        "estat": nou_usuari.estat,
        "totp_activat": nou_usuari.totp_activat,
        "slot_jornada_id": str(nou_usuari.slot_jornada_id) if nou_usuari.slot_jornada_id else None,
        "created_at": created_at_iso,
        "contrasenya_generada": contrasenya_generada,
        "contrasenya_temporal_12_caracters": contrasenya_generada,
        "requereix_enrolament_2fa": True,
        "secret_2fa": secret_2fa_provisional,
        "otpauth_url": f"otpauth://totp/SEVALOR:{nou_usuari.email}?secret={secret_2fa_provisional}&issuer=SEVALOR",
        "login_url": "/gestio/login",
    }


@router.put("/usuaris/{usuari_id}")
async def actualitzar_usuari_administratiu(
    usuari_id: uuid.UUID,
    payload: UsuariAdminUpdateRequest,
    claims: Dict[str, Any] = Depends(get_current_user_claims),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
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
    if (payload.rol and payload.rol.upper() != "BOSS" and usuari.rol == "BOSS") or (
        payload.estat == "INACTIU" and usuari.rol == "BOSS"
    ):
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

    try:
        from app.services.flota_service import sincronitzar_operari_al_disc_empresa

        await sincronitzar_operari_al_disc_empresa(db, uuid.UUID(empresa_id), usuari)
    except Exception:
        pass

    return {"status": "OK", "missatge": "Usuari actualitzat correctament"}


@router.delete("/usuaris/{usuari_id}")
async def eliminar_usuari_administratiu(
    usuari_id: uuid.UUID,
    claims: Dict[str, Any] = Depends(get_current_user_claims),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
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


@router.post("/usuaris/{usuari_id}/reset-password")
async def restablir_contrasenya_usuari(
    usuari_id: uuid.UUID,
    claims: Dict[str, Any] = Depends(get_current_user_claims),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """Genera una nova contrasenya temporal de 12 caràcters per a l'usuari administratiu (Boss o Secretaria)."""
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

    nova_contrasenya = generar_contrasenya_forta(12)
    usuari.password_hash = bcrypt.hashpw(nova_contrasenya.encode("utf-8"), bcrypt.gensalt()).decode(
        "utf-8"
    )
    if not usuari.secret_2fa:
        usuari.secret_2fa = generar_secret_totp_base32()

    usuari_id_str = str(usuari.id)
    nom_complet_str = f"{usuari.nom} {usuari.cognoms}".strip()
    email_str = usuari.email
    rol_str = usuari.rol
    secret_2fa_str = usuari.secret_2fa

    await db.commit()

    return {
        "status": "OK",
        "id": usuari_id_str,
        "nom_complet": nom_complet_str,
        "email": email_str,
        "rol": rol_str,
        "contrasenya_generada": nova_contrasenya,
        "contrasenya_temporal_12_caracters": nova_contrasenya,
        "secret_2fa": secret_2fa_str,
        "login_url": "/gestio/login",
        "missatge": f"Contrasenya restablerta correctament per a {email_str}",
    }


# ---------------------------------------------------------------------------
# 5. SEGURETAT 2FA TOTP & REINICI PEL BOSS (RF-05, RF-06, EDGE-01)
# ---------------------------------------------------------------------------


@router.post("/usuaris/{usuari_id}/reset-2fa")
async def reiniciar_2fa_usuari(
    usuari_id: uuid.UUID,
    claims: Dict[str, Any] = Depends(get_current_user_claims),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
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

    nou_secret = generar_secret_totp_base32()
    usuari.secret_2fa = nou_secret
    usuari.totp_activat = False
    nom_complet = f"{usuari.nom} {usuari.cognoms}".strip()
    email_str = usuari.email

    await db.commit()

    otpauth_url = f"otpauth://totp/SEVALOR:{email_str}?secret={nou_secret}&issuer=SEVALOR"

    return {
        "status": "OK",
        "missatge": f"2FA reiniciat correctament per a {nom_complet}",
        "secret": nou_secret,
        "secret_2fa": nou_secret,
        "otpauth_url": otpauth_url,
    }


@router.post("/emergencia-2fa-boss")
@limiter.limit("3/minute")
async def acces_emergencia_2fa_boss(
    request: Request,
    payload: Emergencia2faBossRequest,
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """Accés d'emergència de l'últim Boss mitjançant codi de recuperació estàtic (EDGE-01)."""
    # Cercar l'usuari Boss pel seu NIF (endpoint d'emergència sense sessió autenticada prèvia)
    await db.execute(text("RESET ROLE;"))
    res = await db.execute(
        select(Usuari, Empresa)
        .join(Empresa, Usuari.empresa_id == Empresa.id)
        .where(
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
    nou_secret = generar_secret_totp_base32()
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
) -> List[Dict[str, Any]]:
    """Llistat d'slots de jornada laboral de l'empresa."""
    validar_permisos_gestio(claims, requereix_escriptura=False)
    empresa_id = claims.get("empresa_id")

    if empresa_id:
        await set_tenant_context(db, empresa_id)

    res = await db.execute(
        select(SlotJornada)
        .where(SlotJornada.empresa_id == uuid.UUID(empresa_id))
        .order_by(SlotJornada.nom)
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
) -> Dict[str, Any]:
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
        if not (
            payload.hora_entrada_teorica < payload.hora_inici_dinar < payload.hora_sortida_teorica
        ):
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

    return {"status": "OK", "id": str(nou_slot.id), "nom": nou_slot.nom}


# ---------------------------------------------------------------------------
# 7. PARÀMETRES DEL BOT DE TELEGRAM (RF-19, RF-20, EDGE-09)
# ---------------------------------------------------------------------------


@router.get("/telegram")
async def obtenir_estat_telegram(
    claims: Dict[str, Any] = Depends(get_current_user_claims),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """Consulta l'estat del Bot de Telegram de l'empresa sense exposar secrets."""
    validar_permisos_gestio(claims, requereix_escriptura=False)
    empresa_id = claims.get("empresa_id")
    if not empresa_id:
        raise HTTPException(status_code=401, detail="Tenant no identificat")
    await set_tenant_context(db, empresa_id)

    res = await db.execute(select(Empresa).where(Empresa.id == uuid.UUID(empresa_id)))
    empresa = res.scalar_one_or_none()
    if not empresa:
        raise HTTPException(status_code=404, detail="Empresa no trobada")

    return {
        "estat": empresa.telegram_estat_connexio or "NO_CONFIGURAT",
        "telegram_bot_actiu": bool(empresa.telegram_bot_actiu),
        "te_token": bool(empresa.telegram_bot_token),
    }


@router.put("/telegram")
async def actualitzar_credencials_telegram(
    payload: TelegramConfigRequest,
    claims: Dict[str, Any] = Depends(get_current_user_claims),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
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
) -> Dict[str, Any]:
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


# ---------------------------------------------------------------------------
# 7. BAREMA DE PREUS I TARIFES ESTÀNDARD (Spec 01 FR-017)
# ---------------------------------------------------------------------------


_BAREMA_DEFECTE: Dict[str, Any] = {
    "id": "barema_preus",
    "preu_hora_standard_eur": 0.0,
    "tarifa_urgencia_eur": 0.0,
    "suplement_desplacament_eur": 0.0,
    "marge_materials_defecte_pct": 0.0,
    "partides": [],
}


@router.get("/barema")
async def obtenir_barema_preus(
    claims: Dict[str, Any] = Depends(get_current_user_claims),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """Retorna el Barema de Preus sobirà de l'empresa (FR-017; Enginyer 403)."""
    validar_permisos_gestio(claims, requereix_escriptura=False)
    if claims.get("rol", "").upper() == "ENGINYER":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="HTTP 403 Forbidden: Veto d'Enginyer sobre tarifes i baremes econòmics",
        )
    empresa_id = str(claims.get("empresa_id") or "")
    if not empresa_id:
        raise HTTPException(status_code=401, detail="Tenant no identificat")
    await set_tenant_context(db, empresa_id)

    items = await SovereignStorageGateway.llegir_entitats_json(db, empresa_id, "configuracio")
    for item in items:
        if isinstance(item, dict) and item.get("id") == "barema_preus":
            return {**_BAREMA_DEFECTE, **item}
    return dict(_BAREMA_DEFECTE)


@router.put("/barema")
async def desar_barema_preus(
    payload: BaremaConfigRequest,
    claims: Dict[str, Any] = Depends(get_current_user_claims),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """Desa el Barema de Preus i tarifes al disc sobirà del client (FR-017)."""
    validar_permisos_gestio(claims, requereix_escriptura=True)
    empresa_id = str(claims.get("empresa_id") or "")
    if not empresa_id:
        raise HTTPException(status_code=401, detail="Tenant no identificat")
    emp_uuid = uuid.UUID(empresa_id)
    await set_tenant_context(db, empresa_id)

    dades = {
        "id": "barema_preus",
        "preu_hora_standard_eur": payload.preu_hora_standard_eur,
        "tarifa_urgencia_eur": payload.tarifa_urgencia_eur,
        "suplement_desplacament_eur": payload.suplement_desplacament_eur,
        "marge_materials_defecte_pct": payload.marge_materials_defecte_pct,
        "partides": [p.model_dump() for p in payload.partides],
    }
    await SovereignStorageGateway.desar_entitat_json(
        db=db,
        empresa_id=empresa_id,
        categoria="configuracio",
        item_id="barema_preus",
        dades=dades,
    )
    await db.execute(
        update(OrdreTreball)
        .where(
            OrdreTreball.empresa_id == emp_uuid,
            OrdreTreball.factura_id.is_(None),
        )
        .values(preu_venda_hora_aplicat=payload.preu_hora_standard_eur)
    )
    await db.commit()
    return {"status": "OK", "barema": dades}


# ---------------------------------------------------------------------------
# 8. CERTIFICAT DIGITAL PKCS#12 (.p12) I ESTAT VERI*FACTU AEAT (Ordre HAC/1177/2024)
# ---------------------------------------------------------------------------


class VerifactuCertificatUploadRequest(BaseModel):
    p12_base64: str = Field(..., min_length=32)
    password: str = Field(..., min_length=1)
    nom_fitxer: Optional[str] = Field("certificat_aeat.p12", max_length=120)


@router.post("/verifactu/certificat")
async def pujar_certificat_verifactu_p12(
    payload: VerifactuCertificatUploadRequest,
    claims: Dict[str, Any] = Depends(get_current_user_claims),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """
    Valida i desa el certificat digital PKCS#12 (.p12 / .pfx) al disc dur sobirà de l'empresa
    i xifra la seva contrasenya amb AES-256-GCM (reservat exclusivament al rol BOSS).
    """
    validar_permisos_gestio(claims, requereix_escriptura=True, nomes_boss=True)
    empresa_id = str(claims.get("empresa_id") or "")
    if not empresa_id:
        raise HTTPException(status_code=401, detail="Tenant no identificat")
    emp_uuid = uuid.UUID(empresa_id)
    await set_tenant_context(db, empresa_id)

    try:
        raw_b64 = payload.p12_base64.strip()
        if "," in raw_b64 and raw_b64.startswith("data:"):
            raw_b64 = raw_b64.split(",", 1)[1]
        p12_bytes = base64.b64decode(raw_b64, validate=False)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="El contingut Base64 del certificat PKCS#12 (.p12) és invàlid.",
        ) from exc

    try:
        meta = validar_i_extreure_metadata_p12(p12_bytes, payload.password)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc

    res = await db.execute(select(Empresa).where(Empresa.id == emp_uuid))
    empresa = res.scalar_one_or_none()
    if not empresa:
        raise HTTPException(status_code=404, detail="Empresa no trobada")

    ruta_p12 = await SovereignStorageGateway.pujar_fitxer_binari(
        db=db,
        empresa_id=empresa_id,
        categoria="configuracio",
        nom_fitxer=f"certificat_verifactu_{empresa_id}.p12",
        content=p12_bytes,
        content_type="application/x-pkcs12",
    )

    empresa.verifactu_cert_path = ruta_p12
    empresa.verifactu_cert_pass_xifrat = xifrar_secret_verifactu(payload.password)
    empresa.verifactu_cert_subject = str(meta["subject"])[:255]
    empresa.verifactu_cert_caducitat = meta["valid_until"]
    await db.commit()

    return {
        "status": "OK",
        "missatge": "Certificat digital PKCS#12 (.p12) validat i desat al disc sobirà.",
        "subject": empresa.verifactu_cert_subject,
        "issuer": meta["issuer"],
        "serial_number": meta["serial_number"],
        "caducitat": meta["valid_until"].isoformat(),
        "dies_restants": meta["dies_restants"],
        "alerta_caducitat_proxima": bool(meta["dies_restants"] <= 30),
    }


@router.get("/verifactu/estat")
async def obtenir_estat_verifactu_empresa(
    claims: Dict[str, Any] = Depends(get_current_user_claims),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """Retorna l'estat del certificat digital .p12, entorn AEAT i cua Outbox de l'empresa."""
    from datetime import datetime, timezone

    validar_permisos_gestio(claims, requereix_escriptura=False)
    empresa_id = str(claims.get("empresa_id") or "")
    if not empresa_id:
        raise HTTPException(status_code=401, detail="Tenant no identificat")
    emp_uuid = uuid.UUID(empresa_id)
    await set_tenant_context(db, empresa_id)

    res = await db.execute(select(Empresa).where(Empresa.id == emp_uuid))
    empresa = res.scalar_one_or_none()
    if not empresa:
        raise HTTPException(status_code=404, detail="Empresa no trobada")

    dies_restants: Optional[int] = None
    alerta_caducitat = False
    if empresa.verifactu_cert_caducitat:
        cad = empresa.verifactu_cert_caducitat
        if cad.tzinfo is None:
            cad = cad.replace(tzinfo=timezone.utc)
        dies_restants = max(0, (cad - datetime.now(timezone.utc)).days)
        alerta_caducitat = dies_restants <= 30

    rows_outbox = (
        await db.execute(
            select(OutboxEnviamentAEAT.estat_enviament, func.count(OutboxEnviamentAEAT.id))
            .where(OutboxEnviamentAEAT.empresa_id == emp_uuid)
            .group_by(OutboxEnviamentAEAT.estat_enviament)
        )
    ).all()
    resum_outbox = {str(est): int(cnt) for est, cnt in rows_outbox}

    return {
        "verifactu_entorn": empresa.verifactu_entorn or "PREPRODUCCIO",
        "modalitat": "VERI*FACTU",
        "certificat_configurat": bool(empresa.verifactu_cert_path),
        "certificat_subject": empresa.verifactu_cert_subject,
        "certificat_caducitat": (
            empresa.verifactu_cert_caducitat.isoformat()
            if empresa.verifactu_cert_caducitat
            else None
        ),
        "dies_restants_certificat": dies_restants,
        "alerta_caducitat_proxima": alerta_caducitat,
        "outbox_resum": resum_outbox,
    }

