"""Endpoint públic per a la resolució de marca i dades públiques de tenant per domini (Zero-Trust)."""

import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.models.models import Empresa

router = APIRouter(prefix="/public/tenant", tags=["Tenant Públic"])


class PublicTenantResponse(BaseModel):
    id: uuid.UUID
    nom: str
    rao_social: str
    nom_comercial: Optional[str] = None
    subdomini: Optional[str] = None
    domini_custom: Optional[str] = None
    logotip_path: Optional[str] = None
    primari_hsl: Optional[str] = None
    secundari_hsl: Optional[str] = None
    accent_hsl: Optional[str] = None
    node_ia_actiu: bool = False


@router.get("/resolve", response_model=PublicTenantResponse)
async def resoldre_tenant_per_domini(
    request: Request,
    host: Optional[str] = Query(None, description="Domini explícit a resoldre (opcional)"),
    db: AsyncSession = Depends(get_db),
) -> PublicTenantResponse:
    """Retorna les dades d'estil i marca pública de l'empresa segons el subdomini o domini propi.

    Aquest endpoint és públic per permetre que la pantalla de login mostri la identitat corporativa,
    però NO exposa cap dada fiscal, bancària ni d'usuaris (Compliment RGPD i Zero-Trust).
    """
    target_host = host or request.headers.get("x-forwarded-host") or request.headers.get("host") or ""
    clean_host = (
        target_host.strip()
        .lower()
        .replace("https://", "")
        .replace("http://", "")
        .split("/")[0]
        .split(":")[0]
    )

    if not clean_host:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Capçalera Host o paràmetre host requerit.",
        )

    # Extreure subdomini (primera part) per si l'accés és per subdomini directe
    parts = clean_host.split(".")
    subdomini_candidat = parts[0] if len(parts) >= 3 else None

    conditions = [func.lower(Empresa.domini_custom) == clean_host]
    if subdomini_candidat and subdomini_candidat not in (
        "www",
        "api",
        "app",
        "localhost",
        "sevalor",
        "superadmin",
    ):
        conditions.append(func.lower(Empresa.subdomini) == subdomini_candidat)

    stmt = select(Empresa).where(or_(*conditions))
    res = await db.execute(stmt)
    empresa = res.scalars().first()

    if not empresa:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No s'ha trobat cap empresa associada al domini '{clean_host}'.",
        )

    # Validació d'estat del cicle de vida del tenant
    if empresa.estat_pagament in ("ELIMINAT", "BAIXA_OFFBOARDING"):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Aquest compte d'empresa ha estat donat de baixa.",
        )

    if empresa.estat_pagament == "HIBERNANT":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="El compte d'aquesta empresa està temporalment en hibernació.",
        )

    if empresa.estat_pagament == "SUSPES":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="El compte d'aquesta empresa ha estat suspès per administració.",
        )

    nom_val = empresa.nom or "Empresa"
    return PublicTenantResponse(
        id=empresa.id,
        nom=nom_val,
        rao_social=nom_val,
        nom_comercial=nom_val,
        subdomini=empresa.subdomini,
        domini_custom=empresa.domini_custom,
        logotip_path=empresa.logotip_path,
        primari_hsl=empresa.primari_hsl or "210 100% 15%",
        secundari_hsl=empresa.secundari_hsl or "38 92% 50%",
        accent_hsl=empresa.accent_hsl or "190 90% 50%",
        node_ia_actiu=bool(getattr(empresa, "node_ia_actiu", False)),
    )
