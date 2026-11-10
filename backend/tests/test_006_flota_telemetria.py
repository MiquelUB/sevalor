import uuid
from datetime import date

from app.api.v1.gestio.flota import VehicleCreate, _build_vehicle_response
from app.models.models import Vehicle


def test_vehicle_create_and_response_fields():
    # Creació de payload amb camps de consum
    payload = {
        "matricula": "1234ABC",
        "marca": "Ford",
        "model": "Transit",
        "tipus": "DIESEL",
        "distintiu_ambiental": "C",
        "estat": "OPERATIU",
        "regim_adquisicio": "RENTING",
        "renting_limit_km": 100000,
        "consum_l_100km": 7.5,
        "consum_mitjana_historica": 6.5,
        "consum_adblue_litres": 15.0,
    }
    vc = VehicleCreate(**payload)
    assert vc.consum_l_100km == 7.5
    assert vc.consum_mitjana_historica == 6.5
    assert vc.consum_adblue_litres == 15.0
    assert vc.renting_limit_km == 100000

def test_build_vehicle_response_consum_i_anomalia():
    # Vehicle dièsel amb anomalia de consum (>10% per sobre de 6.0 = >6.6)
    v = Vehicle(
        id=uuid.uuid4(),
        empresa_id=uuid.uuid4(),
        matricula="5678XYZ",
        marca="Renault",
        model="Master",
        tipus="DIESEL",
        estat="OPERATIU",
        odometre_acumulat=92000,
        horometre_acumulat=0.0,
        regim_adquisicio="RENTING",
        renting_limit_km=100000,
        consum_l_100km=7.5,
        consum_mitjana_historica=6.0,
        consum_adblue_litres=10.0,
        data_proxima_itv=date(2027, 5, 20),
    )
    resp = _build_vehicle_response(v, "Joan Operari")
    assert resp.conductor_nom == "Joan Operari"
    assert resp.consum_format == "7.5 L/100km"
    assert resp.anomalia_consum is True
    assert resp.renting_ocupacio_percent == 92.0
    assert resp.renting_alerta is True
    assert resp.renting_nivell_alerta == "90%"

def test_build_vehicle_response_ev_i_remolc():
    # EV format kWh/100km
    v_ev = Vehicle(
        id=uuid.uuid4(),
        empresa_id=uuid.uuid4(),
        matricula="9999ELE",
        marca="Nissan",
        model="e-NV200",
        tipus="EV",
        estat="OPERATIU",
        odometre_acumulat=15000,
        horometre_acumulat=0.0,
        regim_adquisicio="PROPIETAT",
        consum_l_100km=18.5,
        consum_mitjana_historica=18.0,
    )
    resp_ev = _build_vehicle_response(v_ev)
    assert resp_ev.consum_format == "18.5 kWh/100km"
    assert resp_ev.anomalia_consum is False

    # Remolc format Exempt
    v_remolc = Vehicle(
        id=uuid.uuid4(),
        empresa_id=uuid.uuid4(),
        matricula="R1234BBB",
        marca="Ifor Williams",
        model="LM146",
        tipus="REMOLC",
        estat="OPERATIU",
        odometre_acumulat=0,
        horometre_acumulat=0.0,
        regim_adquisicio="PROPIETAT",
    )
    resp_remolc = _build_vehicle_response(v_remolc)
    assert resp_remolc.consum_format == "Exempt"

if __name__ == "__main__":
    test_vehicle_create_and_response_fields()
    test_build_vehicle_response_consum_i_anomalia()
    test_build_vehicle_response_ev_i_remolc()
    print("Tots els tests unitaris de telemetria i càlculs de Flota han passat al 100%!")
