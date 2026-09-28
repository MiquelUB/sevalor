path = "/media/akaun/Project_1/SEVALOR/backend/app/api/v1/gestio/flota.py"
with open(path, "r") as f:
    text = f.read()

target_create = """class VehicleCreate(BaseModel):
    matricula: str = Field(..., max_length=20)
    marca: str = Field(..., max_length=50)
    model: str = Field(..., max_length=50)
    tipus: str = Field("THERMIC", max_length=30)
    distintiu_ambiental: Optional[str] = Field(None, max_length=10)
    estat: str = Field("OPERATIU", max_length=30)
    data_proxima_itv: Optional[date] = None"""

replacement_create = """class VehicleCreate(BaseModel):
    matricula: str = Field(..., max_length=20)
    marca: str = Field(..., max_length=50)
    model: str = Field(..., max_length=50)
    tipus: str = Field("THERMIC", max_length=30)
    distintiu_ambiental: Optional[str] = Field(None, max_length=10)
    estat: str = Field("OPERATIU", max_length=30)
    data_proxima_itv: Optional[date] = None
    estat_itv: str = Field("FAVORABLE", max_length=50)
    data_caducitat_asseguranca: Optional[date] = None
    companyia_asseguradora: Optional[str] = Field(None, max_length=100)
    carnet_necessari: str = Field("B", max_length=10)
    historial_reparacions: Optional[str] = None"""

if target_create in text:
    text = text.replace(target_create, replacement_create)
    print("Patched VehicleCreate schema.")
else:
    print("Could not find VehicleCreate schema.")

target_alta = """    nou_vehicle = Vehicle(
        empresa_id=uuid.UUID(empresa_id),
        matricula=vehicle.matricula,
        marca=vehicle.marca,
        model=vehicle.model,
        tipus=vehicle.tipus,
        distintiu_ambiental=vehicle.distintiu_ambiental,
        estat=vehicle.estat,
        data_proxima_itv=vehicle.data_proxima_itv
    )"""

replacement_alta = """    nou_vehicle = Vehicle(
        empresa_id=uuid.UUID(empresa_id),
        matricula=vehicle.matricula,
        marca=vehicle.marca,
        model=vehicle.model,
        tipus=vehicle.tipus,
        distintiu_ambiental=vehicle.distintiu_ambiental,
        estat=vehicle.estat,
        data_proxima_itv=vehicle.data_proxima_itv,
        estat_itv=vehicle.estat_itv,
        data_caducitat_asseguranca=vehicle.data_caducitat_asseguranca,
        companyia_asseguradora=vehicle.companyia_asseguradora,
        carnet_necessari=vehicle.carnet_necessari,
        historial_reparacions=vehicle.historial_reparacions
    )"""

if target_alta in text:
    text = text.replace(target_alta, replacement_alta)
    print("Patched alta_vehicle.")
else:
    print("Could not find target_alta.")


# Also we should add PUT endpoint to edit a vehicle!
target_put_append = """    return nou_vehicle"""
replacement_put_append = """    return nou_vehicle

@router.put("/{vehicle_id}", response_model=VehicleResponse)
async def editar_vehicle(
    request: Request,
    vehicle_id: uuid.UUID,
    vehicle: VehicleCreate,
    db: AsyncSession = Depends(get_db_with_tenant_context)
):
    empresa_id = request.state.empresa_id
    if not empresa_id or empresa_id == 'undefined':
        raise HTTPException(status_code=401, detail="No identificat")

    stmt = select(Vehicle).where(Vehicle.id == vehicle_id, Vehicle.empresa_id == uuid.UUID(empresa_id))
    result = await db.execute(stmt)
    v_db = result.scalars().first()
    if not v_db:
        raise HTTPException(status_code=404, detail="Vehicle no trobat")
        
    v_db.matricula = vehicle.matricula
    v_db.marca = vehicle.marca
    v_db.model = vehicle.model
    v_db.tipus = vehicle.tipus
    v_db.distintiu_ambiental = vehicle.distintiu_ambiental
    v_db.estat = vehicle.estat
    v_db.data_proxima_itv = vehicle.data_proxima_itv
    v_db.estat_itv = vehicle.estat_itv
    v_db.data_caducitat_asseguranca = vehicle.data_caducitat_asseguranca
    v_db.companyia_asseguradora = vehicle.companyia_asseguradora
    v_db.carnet_necessari = vehicle.carnet_necessari
    v_db.historial_reparacions = vehicle.historial_reparacions

    await db.commit()
    await db.refresh(v_db)
    
    return v_db
"""

if target_put_append in text:
    text = text.replace(target_put_append, replacement_put_append)
    print("Added editar_vehicle.")
else:
    print("Could not find return nou_vehicle.")

with open(path, "w") as f:
    f.write(text)
