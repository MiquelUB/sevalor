path = "/media/akaun/Project_1/SEVALOR/backend/app/api/v1/gestio/flota.py"
with open(path, "r") as f:
    text = f.read()

target_create = """    historial_reparacions: Optional[str] = None"""

replace_create = """    historial_reparacions: Optional[str] = None
    regim_adquisicio: str = Field("PROPIETAT", max_length=30)
    renting_limit_km: Optional[int] = None
    tacograf_necessari: bool = False
    data_propera_descarrega_tacograf: Optional[date] = None
    capacitat_bateria_kwh: Optional[float] = None
    soh_bateria: Optional[float] = None
    places: int = 5
    pes_maxim_autoritzat: int = 3500"""
text = text.replace(target_create, replace_create)

target_response = """class VehicleResponse(VehicleCreate):
    id: uuid.UUID
    horometre_acumulat: float
    odometre_acumulat: int"""
replace_response = """class VehicleResponse(VehicleCreate):
    id: uuid.UUID
    horometre_acumulat: float
    odometre_acumulat: int
    consum_l_100km: Optional[float] = None
    consum_mitjana_historica: Optional[float] = None
    consum_adblue_litres: float = 0.0"""
text = text.replace(target_response, replace_response)

target_alta = """        historial_reparacions=vehicle.historial_reparacions
    )"""
replace_alta = """        historial_reparacions=vehicle.historial_reparacions,
        regim_adquisicio=vehicle.regim_adquisicio,
        renting_limit_km=vehicle.renting_limit_km,
        tacograf_necessari=vehicle.tacograf_necessari,
        data_propera_descarrega_tacograf=vehicle.data_propera_descarrega_tacograf,
        capacitat_bateria_kwh=vehicle.capacitat_bateria_kwh,
        soh_bateria=vehicle.soh_bateria,
        places=vehicle.places,
        pes_maxim_autoritzat=vehicle.pes_maxim_autoritzat
    )"""
text = text.replace(target_alta, replace_alta)

target_put = """    v_db.historial_reparacions = vehicle.historial_reparacions"""
replace_put = """    v_db.historial_reparacions = vehicle.historial_reparacions
    v_db.regim_adquisicio = vehicle.regim_adquisicio
    v_db.renting_limit_km = vehicle.renting_limit_km
    v_db.tacograf_necessari = vehicle.tacograf_necessari
    v_db.data_propera_descarrega_tacograf = vehicle.data_propera_descarrega_tacograf
    v_db.capacitat_bateria_kwh = vehicle.capacitat_bateria_kwh
    v_db.soh_bateria = vehicle.soh_bateria
    v_db.places = vehicle.places
    v_db.pes_maxim_autoritzat = vehicle.pes_maxim_autoritzat"""
text = text.replace(target_put, replace_put)

with open(path, "w") as f:
    f.write(text)
print("flota API patched!")
