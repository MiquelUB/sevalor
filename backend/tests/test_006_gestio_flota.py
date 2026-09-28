import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.models.models import Empresa


@pytest.mark.asyncio
async def test_alta_vehicle_valid(admin_session, headers, boss_token):
    token, empresa_id = boss_token
    boss_nif = "B" + str(uuid.uuid4())[:8].upper()

    admin_session.add(Empresa(
        id=uuid.UUID(empresa_id), nom='Test Flota', nif=boss_nif, subdomini='testflota-' + str(uuid.uuid4())[:5], pla_subscripcio='STARTER', estat_pagament='ACTIU'
    ))
    await admin_session.flush()
    await admin_session.flush()

    payload = {
        "matricula": "1234ABC",
        "marca": "Ford",
        "model": "Transit",
        "tipus": "THERMIC",
        "distintiu_ambiental": "C",
        "estat": "OPERATIU"
    }

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        res = await ac.post("/api/v1/gestio/flota", json=payload, headers=headers)
        assert res.status_code == 201, f"Expected 201, got {res.status_code}: {res.text}"
        data = res.json()
        assert data["matricula"] == "1234ABC"
        assert data["marca"] == "Ford"

        # Llistat
        res_list = await ac.get("/api/v1/gestio/flota", headers=headers)
        assert res_list.status_code == 200
        llista = res_list.json()
        assert len(llista) == 1
        assert llista[0]["matricula"] == "1234ABC"

        # Duplicat matrícula
        res_dup = await ac.post("/api/v1/gestio/flota", json=payload, headers=headers)
        assert res_dup.status_code == 400
        assert "registrada" in res_dup.json()["detail"]

@pytest.mark.asyncio
async def test_alta_vehicle_completa_amb_spec006(admin_session, headers, boss_token):
    token, empresa_id = boss_token
    boss_nif = "C" + str(uuid.uuid4())[:8].upper()
    admin_session.add(Empresa(
        id=uuid.UUID(empresa_id), nom='Test Flota 2', nif=boss_nif, subdomini='testflota2-' + str(uuid.uuid4())[:5], pla_subscripcio='STARTER', estat_pagament='ACTIU'
    ))
    await admin_session.flush()
    await admin_session.commit()
    payload = {
        "matricula": "9999XYZ",
        "marca": "Renault",
        "model": "Kangoo Z.E.",
        "tipus": "EV",
        "distintiu_ambiental": "ZERO",
        "estat": "OPERATIU",
        "estat_itv": "FAVORABLE",
        "regim_adquisicio": "RENTING",
        "renting_limit_km": 100000,
        "tacograf_necessari": False,
        "capacitat_bateria_kwh": 40.5,
        "soh_bateria": 99.5,
        "places": 2,
        "pes_maxim_autoritzat": 2000
    }

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        res = await ac.post("/api/v1/gestio/flota", json=payload, headers=headers)
        assert res.status_code == 201, f"Expected 201, got {res.status_code}: {res.text}"
        data = res.json()
        assert data["matricula"] == "9999XYZ"
        assert data["regim_adquisicio"] == "RENTING"
        assert data["renting_limit_km"] == 100000
        assert data["capacitat_bateria_kwh"] == 40.5
        assert data["soh_bateria"] == 99.5
        vehicle_id = data["id"]
        
        # Provar modificació PUT
        payload["regim_adquisicio"] = "PROPIETAT"
        payload["renting_limit_km"] = None
        payload["soh_bateria"] = 92.3
        res_put = await ac.put(f"/api/v1/gestio/flota/{vehicle_id}", json=payload, headers=headers)
        assert res_put.status_code == 200
        data_put = res_put.json()
        assert data_put["regim_adquisicio"] == "PROPIETAT"
        assert data_put["soh_bateria"] == 92.3
        
        # Test Copilot Tool
        from app.api.v1.gestio.copilot import execute_tool_get_vehicle_info
        res_copilot = await execute_tool_get_vehicle_info(admin_session, uuid.UUID(empresa_id), "9999XYZ")
        assert res_copilot["trobat"] is True
        assert res_copilot["regim_adquisicio"] == "PROPIETAT"
        assert "renting_limit_km" in res_copilot

