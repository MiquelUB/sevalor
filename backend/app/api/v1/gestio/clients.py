import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_
from pydantic import BaseModel, Field

from app.core.db import get_db_with_tenant_context
from app.core.security import require_roles
from app.models.models import Client

router = APIRouter(
    prefix="/gestio/clients",
    tags=["Gestió Clients"],
    dependencies=[Depends(require_roles(["BOSS", "SECRETARIA", "ENGINYER"]))],
)

class ClientCreate(BaseModel):
    codi: str = Field(..., max_length=20)
    rao_social: str = Field(..., max_length=200)
    nif: str = Field(..., max_length=20)
    telefon: Optional[str] = Field(None, max_length=30)
    email: Optional[str] = Field(None, max_length=200)
    adreca_fiscal: Optional[str] = Field(None)
    iban: Optional[str] = Field(None, max_length=34)


class ClientResponse(ClientCreate):
    id: uuid.UUID
    estat_canal_telegram: str
    actiu: bool


class ClientAmbIBANResponse(BaseModel):
    id: uuid.UUID
    rao_social: str
    iban_xifrat_simetric: Optional[str]


class CanviIBANRequest(BaseModel):
    nou_iban: str = Field(..., min_length=15, max_length=34)

@router.get("", response_model=List[ClientResponse])
async def llistar_clients(
    request: Request,
    q: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    db: AsyncSession = Depends(get_db_with_tenant_context)
):
    empresa_id = request.state.empresa_id
    if not empresa_id:
        raise HTTPException(status_code=401, detail="No identificat")

    stmt = select(Client).where(Client.empresa_id == uuid.UUID(empresa_id))
    
    if q:
        search_term = f"%{q}%"
        stmt = stmt.where(
            or_(
                Client.rao_social.ilike(search_term),
                Client.nif.ilike(search_term)
            )
        )
        
    stmt = stmt.limit(limit).offset(offset).order_by(Client.created_at.desc())
    
    result = await db.execute(stmt)
    clients = result.scalars().all()
    
    return clients

@router.post("", response_model=ClientResponse, status_code=status.HTTP_201_CREATED)
async def alta_client(
    request: Request,
    client: ClientCreate,
    db: AsyncSession = Depends(get_db_with_tenant_context)
):
    empresa_id = request.state.empresa_id
    if not empresa_id:
        raise HTTPException(status_code=401, detail="No identificat")

    stmt_nif = select(Client).where(Client.empresa_id == uuid.UUID(empresa_id), Client.nif == client.nif)
    result_nif = await db.execute(stmt_nif)
    if result_nif.scalars().first():
        raise HTTPException(status_code=400, detail="El NIF/CIF ja es troba registrat en el sistema")

    stmt_codi = select(Client).where(Client.empresa_id == uuid.UUID(empresa_id), Client.codi == client.codi)
    result_codi = await db.execute(stmt_codi)
    if result_codi.scalars().first():
        raise HTTPException(status_code=400, detail="El codi ja es troba registrat en el sistema")

    nou_client = Client(
        empresa_id=uuid.UUID(empresa_id),
        codi=client.codi,
        rao_social=client.rao_social,
        nif=client.nif,
        telefon=client.telefon,
        email=client.email,
        adreca_fiscal=client.adreca_fiscal,
        iban_xifrat_simetric=client.iban,
    )

    db.add(nou_client)
    await db.commit()

    return nou_client


# ---------------------------------------------------------------------------
# IBAN xifrat — Veto d'Enginyer (Spec 002). BOSS/SECRETARIA poden accedir-hi.
# ---------------------------------------------------------------------------

@router.get("/{client_id}/iban", response_model=ClientAmbIBANResponse,
            dependencies=[Depends(require_roles(["BOSS", "SECRETARIA"]))])
async def obtenir_iban_client(
    request: Request, client_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_with_tenant_context)
):
    """Retorna l'IBAN complet del client. Enginyer rep 403."""
    empresa_id = request.headers.get("X-Empresa-ID") or getattr(request.state, "empresa_id", None)
    if not empresa_id:
        raise HTTPException(status_code=401, detail="No identificat")
    res = await db.execute(select(Client).where(
        Client.id == client_id, Client.empresa_id == uuid.UUID(empresa_id)
    ))
    client = res.scalars().first()
    if not client:
        raise HTTPException(status_code=404, detail="Client no trobat")
    return {"id": client.id, "rao_social": client.rao_social, "iban_xifrat_simetric": client.iban_xifrat_simetric}


@router.put("/{client_id}/iban", response_model=ClientAmbIBANResponse,
            dependencies=[Depends(require_roles(["BOSS", "SECRETARIA"]))])
async def canviar_iban_client(
    request: Request, client_id: uuid.UUID, payload: CanviIBANRequest,
    db: AsyncSession = Depends(get_db_with_tenant_context)
):
    """Canvia l'IBAN d'un client (Spec 002). Enginyer rep 403."""
    empresa_id = request.headers.get("X-Empresa-ID") or getattr(request.state, "empresa_id", None)
    if not empresa_id:
        raise HTTPException(status_code=401, detail="No identificat")
    res = await db.execute(select(Client).where(
        Client.id == client_id, Client.empresa_id == uuid.UUID(empresa_id)
    ))
    client = res.scalars().first()
    if not client:
        raise HTTPException(status_code=404, detail="Client no trobat")
    client.iban_xifrat_simetric = payload.nou_iban
    await db.commit()
    return {"id": client.id, "rao_social": client.rao_social, "iban_xifrat_simetric": client.iban_xifrat_simetric}
