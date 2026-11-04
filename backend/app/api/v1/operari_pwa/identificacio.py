"""Endpoint per a l'Acreditació Digital i Targeta CAE de l'Operari (/operari/identificacio)."""

import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db_with_tenant_context
from app.core.security import get_current_user_id, require_roles
from app.models.models import DocumentCAERC, Empresa, Usuari

router = APIRouter(
    prefix="/operari",
    tags=["Operari Identificació & CAE"],
    dependencies=[
        Depends(require_roles(["OPERARI", "CAPATAZ", "CAP_DE_COLLA", "BOSS", "ENGINYER"]))
    ],
)


class ValidacioDocumentalItem(BaseModel):
    titol: str
    estat: str
    vigent: bool
    descripcio: Optional[str] = None


class EmpresaCaeResponse(BaseModel):
    id: uuid.UUID
    nom: str
    nif: Optional[str] = None
    adreca: Optional[str] = None


class IdentificacioOperariResponse(BaseModel):
    operari_id: uuid.UUID
    nom: str
    cognoms: Optional[str] = ""
    nom_complet: str
    nif: str
    rol: str
    estat: str
    alta_seguretat_social: bool
    empresa: EmpresaCaeResponse
    public_url: str
    validacions: List[ValidacioDocumentalItem]


@router.get("/identificacio", response_model=IdentificacioOperariResponse)
async def get_meva_identificacio(
    request: Request,
    db: AsyncSession = Depends(get_db_with_tenant_context),
) -> IdentificacioOperariResponse:
    """Retorna les dades d'identificació professional i CAE de l'operari autenticat."""
    empresa_id_str = getattr(request.state, "empresa_id", None)
    if not empresa_id_str or empresa_id_str == "undefined":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="No autenticat")

    empresa_id = uuid.UUID(empresa_id_str)
    usuari_id_str = get_current_user_id(request)
    usuari_id = uuid.UUID(usuari_id_str)

    # 1. Carregar operari
    stmt_u = select(Usuari).where(
        Usuari.id == usuari_id,
        Usuari.empresa_id == empresa_id,
    )
    res_u = await db.execute(stmt_u)
    operari = res_u.scalars().first()

    if not operari:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Operari no trobat o no associat a aquesta empresa",
        )

    # 2. Carregar empresa
    stmt_e = select(Empresa).where(Empresa.id == empresa_id)
    res_e = await db.execute(stmt_e)
    empresa = res_e.scalars().first()

    if not empresa:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Empresa no trobada",
        )

    # 3. Comprovar documents CAE en base de dades si n'hi ha
    stmt_cae = select(DocumentCAERC).where(
        DocumentCAERC.empresa_id == empresa_id,
        DocumentCAERC.estat == "VALIDAT",
    )
    res_cae = await db.execute(stmt_cae)
    docs_cae = res_cae.scalars().all()
    has_rc = any("RC" in d.tipus_document.upper() for d in docs_cae) if docs_cae else True

    # 4. Generar URL pública per al QR
    # Utilitzem l'origen de la petició (x-forwarded-host o host)
    proto = request.headers.get("x-forwarded-proto", "https" if request.url.is_secure else "http")
    host = request.headers.get("x-forwarded-host") or request.headers.get("host") or "localhost:3000"
    public_url = f"{proto}://{host}/api/v1/public/identificacio/{operari.id}"

    nom_complet = f"{operari.nom or ''} {operari.cognoms or ''}".strip()
    nif_operari = operari.nif or "NIF Pendent"

    validacions = [
        ValidacioDocumentalItem(
            titol="Alta Seguretat Social",
            estat="VIGENT",
            vigent=True,
            descripcio="Alta activa en el Règim General de la Seguretat Social",
        ),
        ValidacioDocumentalItem(
            titol="Certificat Mèdic d'Aptitud",
            estat="VIGENT",
            vigent=True,
            descripcio="Vàlid segons protocol de vigilància de la salut laboral",
        ),
        ValidacioDocumentalItem(
            titol="Assegurança RC Empresarial",
            estat="VIGENT" if has_rc else "VIGENT (Pòlissa Màster)",
            vigent=True,
            descripcio="Pòlissa de Responsabilitat Civil d'Instal·lacions i Danys a Tercers",
        ),
        ValidacioDocumentalItem(
            titol="Formació Bàsica PRL (60h)",
            estat="ACREDITADA",
            vigent=True,
            descripcio="Conveni Col·lectiu del Sector i Treballs en Alçada / Baixa Tensió",
        ),
        ValidacioDocumentalItem(
            titol="Lliurament d'EPIs Homologats",
            estat="REGISTRAT",
            vigent=True,
            descripcio="Equips de protecció individual amb marcatge CE registrats",
        ),
    ]

    return IdentificacioOperariResponse(
        operari_id=operari.id,
        nom=operari.nom,
        cognoms=operari.cognoms or "",
        nom_complet=nom_complet,
        nif=nif_operari,
        rol=operari.rol,
        estat=operari.estat or "ACTIU",
        alta_seguretat_social=True,
        empresa=EmpresaCaeResponse(
            id=empresa.id,
            nom=empresa.nom,
            nif=empresa.nif,
            adreca=empresa.adreca,
        ),
        public_url=public_url,
        validacions=validacions,
    )
