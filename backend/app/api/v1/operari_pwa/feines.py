import uuid
from typing import List, Optional, Any
from datetime import date, datetime
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel, ConfigDict
import sys

from app.core.db import get_db_with_tenant_context
from app.core.security import require_roles
from app.models.models import OrdreTreball, Client, Vehicle, FullaPicking, LiniaPicking, Article

router = APIRouter(
    prefix="/operari",
    tags=["Operari Feines"],
    dependencies=[Depends(require_roles(["OPERARI", "CAPATAZ"]))],
)

class ClientResponse(BaseModel):
    id: uuid.UUID
    rao_social: str
    model_config = ConfigDict(from_attributes=True)

class VehicleResponse(BaseModel):
    id: uuid.UUID
    matricula: str
    model: str
    model_config = ConfigDict(from_attributes=True)

class LiniaPickingDetailResponse(BaseModel):
    id: uuid.UUID
    article_id: uuid.UUID
    article_nom: str
    quantitat_prevista: float
    quantitat_carregada_pick_in: float
    model_config = ConfigDict(from_attributes=True)

class FeinaOperariDetailResponse(BaseModel):
    id: uuid.UUID
    codi: str
    titol: str
    descripcio: Optional[str] = None
    estat: str
    adreca: Optional[str] = None
    data_planificacio: Optional[date] = None
    client: Optional[ClientResponse] = None
    vehicle: Optional[VehicleResponse] = None
    picking_id: Optional[uuid.UUID] = None
    linies_picking: List[LiniaPickingDetailResponse] = []
    model_config = ConfigDict(from_attributes=True)

class FeinaOperariResponse(BaseModel):
    id: uuid.UUID
    codi: str
    titol: str
    estat: str
    adreca: Optional[str] = None
    data_planificacio: Optional[date] = None
    client: Optional[ClientResponse] = None
    model_config = ConfigDict(from_attributes=True)

def _get_usuari_id(request: Request) -> str:
    import jwt
    from app.core.config import settings
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Token no proporcionat")
    token = auth_header.split(" ")[1]
    try:
        decoded = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM], options={"verify_aud": False})
        return decoded.get("sub")
    except Exception:
        raise HTTPException(status_code=401, detail="Token invàlid")

@router.get("/feines", response_model=List[FeinaOperariResponse])
async def llistar_les_meves_feines(
    request: Request,
    db: AsyncSession = Depends(get_db_with_tenant_context)
):
    empresa_id = request.state.empresa_id
    if not empresa_id: raise HTTPException(status_code=401)
    usuari_id = _get_usuari_id(request)
    
    stmt = (
        select(OrdreTreball, Client)
        .outerjoin(Client, OrdreTreball.client_id == Client.id)
        .where(
            OrdreTreball.empresa_id == uuid.UUID(empresa_id),
            OrdreTreball.cap_de_colla_id == uuid.UUID(usuari_id),
            OrdreTreball.estat.in_(["PENDENT", "EN_CURS"])
        )
        .order_by(OrdreTreball.data_planificacio.asc())
    )

    result = await db.execute(stmt)
    feines = []
    for feina, client in result.all():
        feina_resp = FeinaOperariResponse.model_validate(feina)
        if client: feina_resp.client = ClientResponse.model_validate(client)
        feines.append(feina_resp)
        
    return feines

@router.get("/feines/{feina_id}")
async def obtenir_detall_feina(
    feina_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_db_with_tenant_context)
):
    try:
        empresa_id = getattr(request.state, "empresa_id", None)
        if not empresa_id:
            raise HTTPException(status_code=401, detail="No empresa_id in state")
            
        usuari_id = _get_usuari_id(request)
        
        stmt = (
            select(OrdreTreball, Client, Vehicle, FullaPicking)
            .outerjoin(Client, OrdreTreball.client_id == Client.id)
            .outerjoin(Vehicle, OrdreTreball.vehicle_id == Vehicle.id)
            .outerjoin(FullaPicking, OrdreTreball.id == FullaPicking.ordre_treball_id)
            .where(
                OrdreTreball.id == feina_id,
                OrdreTreball.empresa_id == uuid.UUID(empresa_id),
                OrdreTreball.cap_de_colla_id == uuid.UUID(usuari_id)
            )
        )
        result = await db.execute(stmt)
        row = result.first()
        
        if not row:
            raise HTTPException(status_code=404, detail="Feina no trobada o no assignada")
            
        feina, client, vehicle, picking = row
        
        resp = FeinaOperariDetailResponse.model_validate(feina)
        if client: resp.client = ClientResponse.model_validate(client)
        if vehicle: resp.vehicle = VehicleResponse.model_validate(vehicle)
        
        if picking:
            resp.picking_id = picking.id
            stmt_linies = (
                select(LiniaPicking, Article)
                .join(Article, LiniaPicking.article_id == Article.id)
                .where(LiniaPicking.picking_id == picking.id)
            )
            result_linies = await db.execute(stmt_linies)
            
            linies = []
            for l, a in result_linies.all():
                linies.append(LiniaPickingDetailResponse(
                    id=l.id,
                    article_id=l.article_id,
                    article_nom=a.nom,
                    quantitat_prevista=l.quantitat_prevista,
                    quantitat_carregada_pick_in=l.quantitat_carregada_pick_in
                ))
            resp.linies_picking = linies
            
        return resp
    except HTTPException:
        raise
    except Exception as e:
        sys.stderr.write(f"ERROR: {str(e)}\n")
        raise HTTPException(status_code=500, detail=str(e))
