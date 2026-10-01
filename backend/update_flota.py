import re
with open("app/api/v1/gestio/flota.py", "r") as f:
    content = f.read()

new_imports = """
from app.models.models import HistorialAssignacioVehicle, Usuari, MantenimentVehicle
from app.services.ocr_service import processar_ocr_document_vehicle
"""
content = content.replace("from app.models.models import DocumentFlota, OrdreTreball, Vehicle", "from app.models.models import DocumentFlota, OrdreTreball, Vehicle, HistorialAssignacioVehicle, Usuari, MantenimentVehicle\nfrom app.services.ocr_service import processar_ocr_document_vehicle")

new_endpoints = """
class AssignarVehicleRequest(BaseModel):
    usuari_id: uuid.UUID
    odometre: Optional[int] = None
    motiu: Optional[str] = None

@router.post("/{id}/assignar")
async def assignar_vehicle(
    request: Request,
    id: uuid.UUID,
    data: AssignarVehicleRequest,
    db: AsyncSession = Depends(get_db_with_tenant_context)
):
    empresa_id = uuid.UUID(request.state.empresa_id)
    
    # Check vehicle
    v = await db.scalar(select(Vehicle).where(Vehicle.id == id, Vehicle.empresa_id == empresa_id))
    if not v:
        raise HTTPException(status_code=404, detail="Vehicle no trobat")
        
    # Check usuari
    u = await db.scalar(select(Usuari).where(Usuari.id == data.usuari_id, Usuari.empresa_id == empresa_id))
    if not u:
        raise HTTPException(status_code=404, detail="Usuari no trobat")
        
    v.estat = "ASSIGNAT"
    u.vehicle_assignat_id = v.id
    
    historial = HistorialAssignacioVehicle(
        empresa_id=empresa_id,
        vehicle_id=v.id,
        conductor_id=u.id,
        data_inici=datetime.now(timezone.utc),
        odometre_inici=data.odometre,
        motiu=data.motiu
    )
    db.add(historial)
    await db.commit()
    return {"status": "ok", "missatge": "Vehicle assignat correctament"}

class RevocarVehicleRequest(BaseModel):
    odometre: Optional[int] = None
    motiu: Optional[str] = None

@router.post("/{id}/revocar")
async def revocar_vehicle(
    request: Request,
    id: uuid.UUID,
    data: RevocarVehicleRequest,
    db: AsyncSession = Depends(get_db_with_tenant_context)
):
    empresa_id = uuid.UUID(request.state.empresa_id)
    
    v = await db.scalar(select(Vehicle).where(Vehicle.id == id, Vehicle.empresa_id == empresa_id))
    if not v:
        raise HTTPException(status_code=404, detail="Vehicle no trobat")
        
    # Update usuari
    usuaris = await db.execute(select(Usuari).where(Usuari.vehicle_assignat_id == v.id, Usuari.empresa_id == empresa_id))
    for u in usuaris.scalars().all():
        u.vehicle_assignat_id = None
        
    v.estat = "DISPONIBLE"
    
    # Close historial
    hist = await db.scalar(select(HistorialAssignacioVehicle).where(HistorialAssignacioVehicle.vehicle_id == v.id, HistorialAssignacioVehicle.data_fi.is_(None)).order_by(HistorialAssignacioVehicle.data_inici.desc()))
    if hist:
        hist.data_fi = datetime.now(timezone.utc)
        hist.odometre_fi = data.odometre
        
    await db.commit()
    return {"status": "ok", "missatge": "Assignació revocada"}

class MantenimentCreate(BaseModel):
    data_manteniment: date
    tipus: str = Field(..., max_length=50)
    descripcio: str
    taller: Optional[str] = None
    cost_euros: Optional[float] = None

@router.post("/{vehicle_id}/manteniments", status_code=201)
async def crear_manteniment(
    request: Request,
    vehicle_id: uuid.UUID,
    manteniment: MantenimentCreate,
    db: AsyncSession = Depends(get_db_with_tenant_context)
):
    empresa_id = uuid.UUID(request.state.empresa_id)
    
    v = await db.scalar(select(Vehicle).where(Vehicle.id == vehicle_id, Vehicle.empresa_id == empresa_id))
    if not v:
        raise HTTPException(status_code=404, detail="Vehicle no trobat")
        
    mant = MantenimentVehicle(
        empresa_id=empresa_id,
        vehicle_id=vehicle_id,
        data_manteniment=datetime.combine(manteniment.data_manteniment, datetime.min.time(), tzinfo=timezone.utc),
        tipus=manteniment.tipus,
        descripcio=manteniment.descripcio,
        taller=manteniment.taller,
        cost_euros=manteniment.cost_euros
    )
    db.add(mant)
    await db.commit()
    await db.refresh(mant)
    return {"id": str(mant.id), "missatge": "Manteniment registrat"}

@router.get("/{vehicle_id}/manteniments")
async def llistar_manteniments(
    request: Request,
    vehicle_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_with_tenant_context)
):
    empresa_id = uuid.UUID(request.state.empresa_id)
    mants = await db.execute(select(MantenimentVehicle).where(MantenimentVehicle.vehicle_id == vehicle_id, MantenimentVehicle.empresa_id == empresa_id).order_by(MantenimentVehicle.data_manteniment.desc()))
    return mants.scalars().all()

@router.post("/ocr-document")
async def ocr_document_vehicle(
    request: Request,
    file: UploadFile = File(...)
):
    empresa_id = request.state.empresa_id
    if not empresa_id:
        raise HTTPException(status_code=401)
        
    file_bytes = await file.read()
    kind = filetype.guess(file_bytes)
    if not kind:
        raise HTTPException(status_code=400, detail="Tipus de fitxer invàlid")
    file_ext = kind.extension
    
    docs_dir = f"/docs/{empresa_id}/flota/ocr"
    os.makedirs(docs_dir, exist_ok=True)
    safe_name = f"{uuid.uuid4()}.{file_ext}"
    file_path = os.path.join(docs_dir, safe_name)
    
    with open(file_path, "wb") as buffer:
        buffer.write(file_bytes)
        
    resultat = processar_ocr_document_vehicle(file_path)
    return resultat

"""

content += new_endpoints
content = content.replace("from datetime import date", "from datetime import date, datetime, timezone")

with open("app/api/v1/gestio/flota.py", "w") as f:
    f.write(content)
