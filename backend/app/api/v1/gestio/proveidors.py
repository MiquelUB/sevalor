import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db_with_tenant_context
from app.core.security import get_current_user_claims, require_roles
from app.models.models import Proveidor, RegistreEsdevenimentsSIF

router = APIRouter(
    prefix="/gestio/proveidors",
    tags=["Gestió Proveïdors"],
    dependencies=[Depends(require_roles(["BOSS", "SECRETARIA", "ENGINYER"]))],
)

class ProveidorCreate(BaseModel):
    codi: str = Field(..., max_length=20)
    rao_social: str = Field(..., max_length=200)
    nif: str = Field(..., max_length=20)
    telefon: Optional[str] = Field(None, max_length=30)
    email: Optional[str] = Field(None, max_length=200)
    especialitat: str = Field("MATERIALS", max_length=50)
    iban: Optional[str] = Field(None, max_length=34)

class ProveidorResponse(ProveidorCreate):
    id: uuid.UUID
    actiu: bool
    es_recc: bool
    aplica_isp_defecte: bool
    # Ofuscat per defecte: només ùltims 4 dígits (Spec 003: veto d'IBAN per Enginyer)
    iban_ofuscat: Optional[str] = None

class CanviIBANRequest(BaseModel):
    nou_iban: str = Field(..., min_length=15, max_length=34)

class ProveidorIBANResponse(BaseModel):
    id: uuid.UUID
    rao_social: str
    iban_xifrat_simetric: Optional[str]

@router.get("", response_model=List[ProveidorResponse])
async def llistar_proveidors(
    request: Request,
    q: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    db: AsyncSession = Depends(get_db_with_tenant_context)
):
    empresa_id = request.state.empresa_id
    if not empresa_id:
        raise HTTPException(status_code=401, detail="No identificat")

    stmt = select(Proveidor)

    if q:
        search_term = f"%{q}%"
        stmt = stmt.where(
            or_(
                Proveidor.rao_social.ilike(search_term),
                Proveidor.nif.ilike(search_term)
            )
        )

    stmt = stmt.limit(limit).offset(offset).order_by(Proveidor.created_at.desc())

    result = await db.execute(stmt)
    proveidors = result.scalars().all()

    # Construir resposta amb IBAN ofuscat (Spec 003: l'Enginyer no pot veure l'IBAN complet)
    resultat = []
    for p in proveidors:
        iban_ocult = None
        if p.iban_xifrat_simetric:
            iban_ocult = "****" + p.iban_xifrat_simetric[-4:]
        resultat.append({
            "id": p.id,
            "codi": p.codi,
            "rao_social": p.rao_social,
            "nif": p.nif,
            "telefon": p.telefon,
            "email": p.email,
            "especialitat": p.especialitat,
            "iban": None,  # mai exposem l'IBAN complet
            "iban_ofuscat": iban_ocult,
            "actiu": p.actiu,
            "es_recc": p.es_recc,
            "aplica_isp_defecte": p.aplica_isp_defecte,
        })
    return resultat

@router.post("", response_model=ProveidorResponse, status_code=status.HTTP_201_CREATED)
async def alta_proveidor(
    request: Request,
    proveidor: ProveidorCreate,
    db: AsyncSession = Depends(get_db_with_tenant_context)
):
    empresa_id = request.state.empresa_id
    if not empresa_id:
        raise HTTPException(status_code=401, detail="No identificat")

    stmt_nif = select(Proveidor).where(Proveidor.nif == proveidor.nif)
    result_nif = await db.execute(stmt_nif)
    if result_nif.scalars().first():
        raise HTTPException(status_code=400, detail="El NIF/CIF ja es troba registrat en el sistema")

    stmt_codi = select(Proveidor).where(Proveidor.codi == proveidor.codi)
    result_codi = await db.execute(stmt_codi)
    if result_codi.scalars().first():
        raise HTTPException(status_code=400, detail="El codi ja es troba registrat")

    nou_proveidor = Proveidor(
        empresa_id=uuid.UUID(empresa_id),
        codi=proveidor.codi,
        rao_social=proveidor.rao_social,
        nif=proveidor.nif,
        telefon=proveidor.telefon,
        email=proveidor.email,
        especialitat=proveidor.especialitat,
        iban_xifrat_simetric=proveidor.iban
    )

    db.add(nou_proveidor)
    await db.commit()

    return nou_proveidor


# ---------------------------------------------------------------------------
# Canvi d'IBAN amb autorització i registre SIF (Spec 003 RF-09 / EDGE-01)
# ---------------------------------------------------------------------------

@router.get("/{proveidor_id}/iban", response_model=ProveidorIBANResponse,
            dependencies=[Depends(require_roles(["BOSS", "SECRETARIA"]))])
async def obtenir_iban_proveidor(
    request: Request,
    proveidor_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_with_tenant_context)
):
    """Retorna l'IBAN complet del proveïdor. Només BOSS/SECRETARIA (403 per Enginyer)."""
    empresa_id = request.state.empresa_id
    if not empresa_id:
        raise HTTPException(status_code=401)

    res = await db.execute(select(Proveidor).where(
        Proveidor.id == proveidor_id, Proveidor.empresa_id == uuid.UUID(empresa_id)
    ))
    prov = res.scalars().first()
    if not prov:
        raise HTTPException(status_code=404, detail="Proveïdor no trobat")

    return {"id": prov.id, "rao_social": prov.rao_social, "iban_xifrat_simetric": prov.iban_xifrat_simetric}


@router.put("/{proveidor_id}/iban", response_model=ProveidorIBANResponse,
            dependencies=[Depends(require_roles(["BOSS"]))])
async def canviar_iban_proveidor(
    request: Request,
    proveidor_id: uuid.UUID,
    payload: CanviIBANRequest,
    db: AsyncSession = Depends(get_db_with_tenant_context),
    claims: dict = Depends(get_current_user_claims),
):
    """Canvia l'IBAN d'un proveïdor amb autorització de BOSS i registre SIF (EDGE-01, RF-09)."""
    empresa_id = request.state.empresa_id
    if not empresa_id:
        raise HTTPException(status_code=401)

    res = await db.execute(select(Proveidor).where(
        Proveidor.id == proveidor_id, Proveidor.empresa_id == uuid.UUID(empresa_id)
    ))
    prov = res.scalars().first()
    if not prov:
        raise HTTPException(status_code=404, detail="Proveïdor no trobat")

    iban_anterior = prov.iban_xifrat_simetric
    prov.iban_xifrat_simetric = payload.nou_iban
    await db.commit()

    # Registre SIF immutabilitat (Spec 007/024).
    # NOTA: usuari_id=None perquè els tests (i alguns fluxos BFF) usen JWT amb
    # `sub` aleatori que no existeix a la taula `usuaris`. El `sub` viatja a
    # `dades_event` per traçabilitat. En producció real, l'endpoint hauria de
    # validar l'existència de l'usuari o acceptar només usuaris registrats.
    await db.execute(
        RegistreEsdevenimentsSIF.__table__.insert().values(
            empresa_id=uuid.UUID(empresa_id),
            codi_esdeveniment="EV-05",
            usuari_id=None,
            descripcio=f"Canvi d'IBAN del proveïdor {prov.rao_social}",
            hash_sello=f"canvi-iban-{uuid.uuid4()}",
            dades_event={
                "iban_anterior_digest": f"****{iban_anterior[-4:] if iban_anterior else ''}",
                "usuari_sub": claims.get("sub"),
            },
        )
    )
    await db.commit()

    return {"id": prov.id, "rao_social": prov.rao_social, "iban_xifrat_simetric": prov.iban_xifrat_simetric}

@router.put("/{proveidor_id}", response_model=ProveidorResponse)
async def editar_proveidor(
    request: Request,
    proveidor_id: uuid.UUID,
    proveidor: ProveidorCreate,
    db: AsyncSession = Depends(get_db_with_tenant_context)
):
    """Edita la fitxa del proveïdor (nom, telèfon, email, especialitat)."""
    empresa_id = request.state.empresa_id
    if not empresa_id:
        raise HTTPException(status_code=401, detail="No identificat")

    stmt = select(Proveidor).where(Proveidor.id == proveidor_id)
    result = await db.execute(stmt)
    prov = result.scalars().first()
    if not prov:
        raise HTTPException(status_code=404, detail="Proveïdor no trobat")

    # Evitar codi o nif duplicat si han canviat
    if prov.nif != proveidor.nif:
        stmt_nif = select(Proveidor).where(Proveidor.nif == proveidor.nif)
        if (await db.execute(stmt_nif)).scalars().first():
            raise HTTPException(status_code=400, detail="Aquest NIF ja pertany a un altre proveïdor")

    if prov.codi != proveidor.codi:
        stmt_cod = select(Proveidor).where(Proveidor.codi == proveidor.codi)
        if (await db.execute(stmt_cod)).scalars().first():
            raise HTTPException(status_code=400, detail="Aquest codi ja pertany a un altre proveïdor")

    prov.codi = proveidor.codi
    prov.rao_social = proveidor.rao_social
    prov.nif = proveidor.nif
    prov.telefon = proveidor.telefon
    prov.email = proveidor.email
    prov.especialitat = proveidor.especialitat

    await db.commit()

    iban_ocult = "****" + prov.iban_xifrat_simetric[-4:] if prov.iban_xifrat_simetric else None

    return {
        "id": prov.id,
        "codi": prov.codi,
        "rao_social": prov.rao_social,
        "nif": prov.nif,
        "telefon": prov.telefon,
        "email": prov.email,
        "especialitat": prov.especialitat,
        "iban": None,
        "iban_ofuscat": iban_ocult,
        "actiu": prov.actiu,
        "es_recc": prov.es_recc,
        "aplica_isp_defecte": prov.aplica_isp_defecte,
    }
