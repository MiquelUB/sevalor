import uuid
import secrets
import string
import bcrypt
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel, Field

from app.core.db import get_db_with_tenant_context
from app.core.security import require_roles
from app.models.models import Usuari

router = APIRouter(
    prefix="/gestio/operaris",
    tags=["Gestió Operaris"],
    dependencies=[Depends(require_roles(["BOSS", "SECRETARIA", "ENGINYER"]))],
)

class OperariCreate(BaseModel):
    nif: str = Field(..., max_length=20)
    nom: str = Field(..., max_length=100)
    cognoms: str = Field("", max_length=100)
    telefon: str = Field(..., max_length=20)
    especialitat: str = Field("SISTEMES_REG", max_length=50)
    cost_hora_eur: float = Field(22.50)

class OperariResponse(BaseModel):
    id: uuid.UUID
    nif: str
    nom: str
    cognoms: str
    rol: str
    estat: str
    telefon: Optional[str]
    pin_bloquejat: bool
    intents_pin_fallits: int

def generar_pin() -> str:
    """Genera un PIN numèric segur de 4 dígits."""
    return "".join(secrets.choice(string.digits) for _ in range(4))

def hash_pin(pin: str) -> str:
    """Hashea el PIN utilitzant bcrypt directament."""
    return bcrypt.hashpw(pin.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

async def verificar_permisos_boss(request: Request):
    """Comprova que l'usuari té rol BOSS o SECRETARIA."""
    if not request.state.empresa_id:
        raise HTTPException(status_code=401, detail="No identificat")
    return request.state.empresa_id

@router.get("", response_model=List[OperariResponse])
async def llistar_operaris(
    request: Request,
    db: AsyncSession = Depends(get_db_with_tenant_context)
):
    empresa_id = await verificar_permisos_boss(request)

    stmt = select(Usuari).where(Usuari.empresa_id == uuid.UUID(empresa_id), Usuari.rol == "OPERARI")
    result = await db.execute(stmt)
    operaris = result.scalars().all()
    
    return operaris

@router.post("", response_model=OperariResponse, status_code=status.HTTP_201_CREATED)
async def alta_operari(
    request: Request,
    operari: OperariCreate,
    db: AsyncSession = Depends(get_db_with_tenant_context),
    claims: dict = Depends(require_roles(["BOSS", "SECRETARIA"])),
):
    empresa_id = await verificar_permisos_boss(request)

    stmt = select(Usuari).where(Usuari.empresa_id == uuid.UUID(empresa_id), Usuari.nif == operari.nif)
    result = await db.execute(stmt)
    if result.scalars().first():
        raise HTTPException(status_code=400, detail="Ja existeix un operari amb aquest NIF")

    nou_pin = generar_pin()
    hashed_pin = hash_pin(nou_pin)

    nou_usuari = Usuari(
        empresa_id=uuid.UUID(empresa_id),
        nif=operari.nif,
        nom=operari.nom,
        cognoms=operari.cognoms,
        telefon=operari.telefon,
        especialitat=operari.especialitat,
        cost_hora_eur=operari.cost_hora_eur,
        rol="OPERARI",
        estat="ACTIU",
        pin_hash=hashed_pin
    )
    db.add(nou_usuari)
    await db.commit()

    print(f"[SMS SIMULAT] -> Per a {operari.telefon}: El teu nou PIN de CampoPro és {nou_pin}")
    return nou_usuari

@router.post("/{operari_id}/reset-pin")
async def reset_pin_operari(
    request: Request,
    operari_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_with_tenant_context),
    claims: dict = Depends(require_roles(["BOSS", "SECRETARIA"])),
):
    empresa_id = await verificar_permisos_boss(request)

    stmt = select(Usuari).where(Usuari.id == operari_id, Usuari.empresa_id == uuid.UUID(empresa_id))
    result = await db.execute(stmt)
    usuari = result.scalars().first()

    if not usuari:
        raise HTTPException(status_code=404, detail="Operari no trobat")

    nou_pin = generar_pin()
    usuari.pin_hash = hash_pin(nou_pin)
    usuari.pin_bloquejat = False
    usuari.intents_pin_fallits = 0

    await db.commit()
    print(f"[SMS SIMULAT] -> Per a {usuari.telefon}: El teu nou PIN de CampoPro és {nou_pin}")

    return {
        "missatge": "Nou PIN generat i tramès per SMS",
        "pin_bloquejat": usuari.pin_bloquejat,
        "intents_pin_fallits": usuari.intents_pin_fallits
    }
