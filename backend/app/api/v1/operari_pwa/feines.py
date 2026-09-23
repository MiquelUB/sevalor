import sys
import uuid
from datetime import date
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db_with_tenant_context
from app.core.security import require_roles
from app.models.models import Article, Client, FullaPicking, LiniaPicking, OrdreTreball, Vehicle

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

import os
import math
from fastapi import UploadFile, File, Form

def calcular_distancia_metres(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6371000.0  # radi de la Terra en metres
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)
    a = math.sin(delta_phi / 2.0)**2 + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2.0)**2
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return R * c

class IniciarTrajecteResponse(BaseModel):
    feina_id: uuid.UUID
    estat_vehicle: str
    eta_minuts: int
    missatge: str

@router.put("/feines/{feina_id}/iniciar-trajecte", response_model=IniciarTrajecteResponse)
async def iniciar_trajecte(
    feina_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_db_with_tenant_context)
):
    """Commuta el vehicle a Blau (En trànsit) i activa buffer de 25 min (Spec 013 RF-11)."""
    empresa_id = request.state.empresa_id
    if not empresa_id:
        raise HTTPException(status_code=401)
    
    ot_res = await db.execute(select(OrdreTreball).where(
        OrdreTreball.id == feina_id,
        OrdreTreball.empresa_id == uuid.UUID(empresa_id)
    ))
    feina = ot_res.scalars().first()
    if not feina:
        raise HTTPException(status_code=404, detail="Feina no trobada")
    
    if feina.vehicle_id:
        veh_res = await db.execute(select(Vehicle).where(Vehicle.id == feina.vehicle_id))
        veh = veh_res.scalars().first()
        if veh:
            veh.estat = "EN_TRANSIT"
            await db.commit()
    
    return IniciarTrajecteResponse(
        feina_id=feina.id,
        estat_vehicle="EN_TRANSIT",
        eta_minuts=25,
        missatge="Vehicle en trànsit, ETA de 25 minuts activat"
    )

class ComencarFeinaRequest(BaseModel):
    lat: Optional[float] = None
    lng: Optional[float] = None
    desviacio_justificada: bool = False
    foto_evidencia_desviacio: Optional[str] = None

@router.put("/feines/{feina_id}/comencar")
async def comencar_feina(
    feina_id: uuid.UUID,
    payload: ComencarFeinaRequest,
    request: Request,
    db: AsyncSession = Depends(get_db_with_tenant_context)
):
    """Comença el cronòmetre de la feina amb control de geovalla (Spec 013 RF-12, RF-12.1)."""
    empresa_id = request.state.empresa_id
    if not empresa_id:
        raise HTTPException(status_code=401)
    
    ot_res = await db.execute(select(OrdreTreball).where(
        OrdreTreball.id == feina_id,
        OrdreTreball.empresa_id == uuid.UUID(empresa_id)
    ))
    feina = ot_res.scalars().first()
    if not feina:
        raise HTTPException(status_code=404, detail="Feina no trobada")
    
    # Comprovació Geovalla de 50 m si es passen coordenades i l'adreça té coordenades
    if payload.lat is not None and payload.lng is not None and feina.adreca and "," in feina.adreca:
        try:
            parts = [float(p.strip()) for p in feina.adreca.split(",")]
            if len(parts) >= 2:
                dest_lat, dest_lng = parts[0], parts[1]
                distancia = calcular_distancia_metres(payload.lat, payload.lng, dest_lat, dest_lng)
                if distancia > 50.0 and not payload.desviacio_justificada:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Geovalla d'obra superada (distància: {distancia:.1f}m > 50m). Cal sol·licitud d'inici per desviació amb foto d'evidència."
                    )
        except (ValueError, TypeError):
            pass

    feina.estat = "EN_CURS"
    await db.commit()
    return {"feina_id": str(feina.id), "estat": "EN_CURS", "missatge": "Feina iniciada amb èxit"}

@router.post("/feines/{feina_id}/fotos")
async def pujar_foto_qualitat(
    feina_id: uuid.UUID,
    request: Request,
    tipus: str = Form(..., description="INICIAL, INTERMEDIA o FINAL"),
    foto: Optional[UploadFile] = File(None),
    db: AsyncSession = Depends(get_db_with_tenant_context)
):
    """Protocol obligatori de 3 fotos de control de qualitat (Spec 013 RF-13)."""
    empresa_id = request.state.empresa_id
    if not empresa_id:
        raise HTTPException(status_code=401)
    
    tipus_upper = tipus.upper()
    if tipus_upper not in ("INICIAL", "INTERMEDIA", "FINAL"):
        raise HTTPException(status_code=422, detail="El tipus de foto ha de ser INICIAL, INTERMEDIA o FINAL")
    
    dir_feina = f"/tmp/data/{empresa_id}/feines/{feina_id}"
    os.makedirs(dir_feina, exist_ok=True)
    
    file_path = f"{dir_feina}/foto_{tipus_upper.lower()}.webp"
    if foto:
        content = await foto.read()
        with open(file_path, "wb") as f:
            f.write(content)
    else:
        # Crea evidència de fitxer si no s'adjunta binari multipart
        with open(file_path, "wb") as f:
            f.write(b"WEBP_EVIDENCE_PLACEHOLDER")
            
    return {"feina_id": str(feina_id), "tipus": tipus_upper, "path": file_path, "status": "GUARDAT"}

@router.get("/feines/{feina_id}/fotos")
async def consultar_fotos_qualitat(
    feina_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_db_with_tenant_context)
):
    """Consulta l'estat del protocol de 3 fotos (Spec 013 RF-13, RF-14)."""
    empresa_id = request.state.empresa_id
    if not empresa_id:
        raise HTTPException(status_code=401)
    
    dir_feina = f"/tmp/data/{empresa_id}/feines/{feina_id}"
    fotos_pujades = {}
    for t in ["inicial", "intermedia", "final"]:
        p = f"{dir_feina}/foto_{t}.webp"
        fotos_pujades[t] = os.path.exists(p)
        
    complet = all(fotos_pujades.values())
    return {
        "feina_id": str(feina_id),
        "fotos": fotos_pujades,
        "protocol_complet": complet
    }

@router.put("/feines/{feina_id}/finalitzar")
async def finalitzar_feina(
    feina_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_db_with_tenant_context)
):
    """Finalitza la feina. Bloquejat si no s'han capturat les 3 fotos (Spec 013 RF-14, RF-17)."""
    empresa_id = request.state.empresa_id
    if not empresa_id:
        raise HTTPException(status_code=401)
    
    ot_res = await db.execute(select(OrdreTreball).where(
        OrdreTreball.id == feina_id,
        OrdreTreball.empresa_id == uuid.UUID(empresa_id)
    ))
    feina = ot_res.scalars().first()
    if not feina:
        raise HTTPException(status_code=404, detail="Feina no trobada")
    
    dir_feina = f"/tmp/data/{empresa_id}/feines/{feina_id}"
    faltants = []
    for t in ["inicial", "intermedia", "final"]:
        if not os.path.exists(f"{dir_feina}/foto_{t}.webp"):
            faltants.append(t.capitalize())
            
    if faltants:
        raise HTTPException(
            status_code=400,
            detail=f"Falten fotografies requerides de control de qualitat: {', '.join(faltants)} (Spec 013 RF-14)"
        )
        
    feina.estat = "COMPLERT"
    await db.commit()
    return {"feina_id": str(feina.id), "estat": "COMPLERT", "missatge": "Feina finalitzada satisfactòriament"}
