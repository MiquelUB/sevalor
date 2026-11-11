import uuid
from datetime import date, timedelta

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.gestio.flota import _build_vehicle_response
from app.main import app
from app.models.models import Client, Empresa, Usuari, Vehicle


def test_build_vehicle_response_amb_ot_activa():
    """Valida que _build_vehicle_response reflecteix l'estat ASSIGNAT i les dades de l'OT."""
    v = Vehicle(
        id=uuid.uuid4(),
        empresa_id=uuid.uuid4(),
        matricula="4829-LWT",
        marca="Ford",
        model="Transit Custom",
        tipus="FURGONETA",
        estat="OPERATIU",
        odometre_acumulat=45000,
        carnet_necessari="B",
        regim_adquisicio="PROPIETAT",
    )

    ot_info = {
        "id": uuid.uuid4(),
        "codi": "OT-7261",
        "titol": "Instal·lació de reg sector nord",
        "estat": "ASSIGNADA",
        "operari_nom": "Jordi Pujol",
    }

    # 1. Amb OT activa: estat passa a ASSIGNAT, conductor pren l'operari de l'OT si està buit
    res = _build_vehicle_response(v, conductor_nom=None, ot_activa=ot_info)
    assert res.estat == "ASSIGNAT"
    assert res.ordre_treball_activa_codi == "OT-7261"
    assert res.ordre_treball_activa_id == ot_info["id"]
    assert res.ordre_treball_activa_titol == "Instal·lació de reg sector nord"
    assert res.operari_assignat_nom == "Jordi Pujol"
    assert res.conductor_nom == "Jordi Pujol"

    # 2. Sense OT activa: vehicle es manté OPERATIU
    res_sense = _build_vehicle_response(v, conductor_nom=None, ot_activa=None)
    assert res_sense.estat == "OPERATIU"
    assert res_sense.ordre_treball_activa_codi is None
    assert res_sense.ordre_treball_activa_id is None
    assert res_sense.operari_assignat_nom is None


@pytest.mark.asyncio
async def test_sincronitzacio_assignacio_vehicle_ot_7261(
    admin_session: AsyncSession, headers: dict, boss_token: tuple
):
    """Verifica l'escenari real de la furgoneta 4829-LWT assignada a l'OT-7261:

    1. Alta de la furgoneta 4829-LWT en estat inicial OPERATIU sense conductor fix.
    2. Creació d'un client i un operari cap de colla.
    3. Creació d'OT-7261 amb vehicle_id apuntant a 4829-LWT.
    4. Consulta a /gestio/flota: comprova que 4829-LWT consta com a ASSIGNAT a OT-7261 amb el seu operari.
    5. Tancament de l'OT: comprova que 4829-LWT s'allibera i torna a OPERATIU.
    """
    token, empresa_id = boss_token
    emp_uuid = uuid.UUID(empresa_id)

    admin_session.add(
        Empresa(
            id=emp_uuid,
            nom="Empresa Test Flota OT",
            nif="B" + str(uuid.uuid4())[:8].upper(),
            subdomini="testflotaot-" + str(uuid.uuid4())[:5],
            pla_subscripcio="ENTERPRISE",
            estat_pagament="ACTIU",
        )
    )
    await admin_session.flush()

    # Operari cap de colla
    avui = date.today()
    op_id = uuid.uuid4()
    operari = Usuari(
        id=op_id,
        empresa_id=emp_uuid,
        nif="48" + op_id.hex[:6].upper() + "Z",
        nom="Joan",
        cognoms="Puig",
        telefon="+34699887766",
        rol="OPERARI",
        especialitat="INSTAL·LACIONS",
        carnet_conduir="B",
        carnet_caducitat=avui + timedelta(days=365),
        pin_hash="fakehash",
        estat="ACTIU",
    )

    # Client per a l'ordre de treball
    client_id = uuid.uuid4()
    client = Client(
        id=client_id,
        empresa_id=emp_uuid,
        nom="Agrícola de Prova SL",
        cif_nif="A" + str(uuid.uuid4())[:8].upper(),
        adreca="Carrer Major 1, Lleida",
        email="client@prova.cat",
        telefon="+34973000000",
    )
    admin_session.add_all([operari, client])
    await admin_session.flush()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # 1. Donar d'alta la furgoneta 4829-LWT
        v_payload = {
            "matricula": "4829-LWT",
            "marca": "Ford",
            "model": "Transit Custom",
            "tipus": "FURGONETA",
            "distintiu_ambiental": "C",
            "estat": "OPERATIU",
            "regim_adquisicio": "PROPIETAT",
            "carnet_necessari": "B",
            "odometre_acumulat": 52000,
            "conductor_habitual_id": None,
        }
        res_v = await ac.post("/api/v1/gestio/flota", json=v_payload, headers=headers)
        assert res_v.status_code == 201, res_v.text
        v_data = res_v.json()
        vehicle_id = v_data["id"]
        assert v_data["matricula"] == "4829-LWT"
        assert v_data["estat"] == "OPERATIU"
        assert v_data["ordre_treball_activa_codi"] is None

        # 2. Creació de l'Ordre de Treball OT-7261 vinculada al vehicle i cap de colla
        feina_payload = {
            "codi": "OT-7261",
            "client_id": str(client_id),
            "titol": "Manteniment Estació de Bombament",
            "adreca": "Finca Les Oliveres, Lleida",
            "estat": "ASSIGNADA",
            "data_planificacio": avui.isoformat(),
            "cap_de_colla_id": str(op_id),
            "vehicle_id": vehicle_id,
        }
        res_feina = await ac.post("/api/v1/gestio/feines", json=feina_payload, headers=headers)
        assert res_feina.status_code == 201, res_feina.text
        ot_data = res_feina.json()
        assert ot_data["codi"] == "OT-7261"
        assert ot_data["vehicle_id"] == vehicle_id

        # 3. Comprovació a GET /api/v1/gestio/flota: ara 4829-LWT consta assignada a OT-7261
        res_flota = await ac.get("/api/v1/gestio/flota", headers=headers)
        assert res_flota.status_code == 200, res_flota.text
        flota_list = res_flota.json()
        v_flota = next((item for item in flota_list if item["id"] == vehicle_id), None)
        assert v_flota is not None
        assert v_flota["matricula"] == "4829-LWT"
        assert v_flota["estat"] == "ASSIGNAT"
        assert v_flota["ordre_treball_activa_codi"] == "OT-7261"
        assert v_flota["operari_assignat_nom"] == "Joan Puig"
        assert v_flota["conductor_nom"] == "Joan Puig"

        # 4. Comprovació a GET /api/v1/gestio/flota/{id}
        res_detall = await ac.get(f"/api/v1/gestio/flota/{vehicle_id}", headers=headers)
        assert res_detall.status_code == 200
        detall_data = res_detall.json()
        assert detall_data["estat"] == "ASSIGNAT"
        assert detall_data["ordre_treball_activa_codi"] == "OT-7261"
        assert detall_data["operari_assignat_nom"] == "Joan Puig"

        # 5. Tancament de l'OT-7261
        tancar_payload = {
            "signatura_base64": "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=",
            "conformitat_client": True,
            "observacions": "Feina completada satisfactòriament",
        }
        res_tancar = await ac.put(
            f"/api/v1/gestio/feines/{ot_data['id']}/tancar-obra",
            json=tancar_payload,
            headers=headers,
        )
        assert res_tancar.status_code == 200, res_tancar.text

        # 6. Comprovació a GET /api/v1/gestio/flota: el vehicle torna a estar OPERATIU i sense OT activa
        res_flota_post = await ac.get("/api/v1/gestio/flota", headers=headers)
        assert res_flota_post.status_code == 200
        v_flota_post = next((item for item in res_flota_post.json() if item["id"] == vehicle_id), None)
        assert v_flota_post is not None
        assert v_flota_post["estat"] == "OPERATIU"
        assert v_flota_post["ordre_treball_activa_codi"] is None
