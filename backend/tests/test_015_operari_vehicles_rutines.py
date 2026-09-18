import pytest
import uuid
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.models.models import Empresa, Usuari, Vehicle
from sqlalchemy import text

@pytest.mark.asyncio
async def test_vehicle_checkin_checkout_repostatge(admin_session, headers, boss_token):
    token, empresa_id = boss_token
    boss_nif = "B" + str(uuid.uuid4())[:8].upper()
    
    admin_session.add(Empresa(
        id=uuid.UUID(empresa_id), nom='Test Flota', nif=boss_nif, subdomini='flota-' + str(uuid.uuid4())[:5], pla_subscripcio='STARTER', estat_pagament='ACTIU'
    ))
    await admin_session.flush()
    
    # 1. Crear Vehicle
    vehicle = Vehicle(
        id=uuid.uuid4(),
        empresa_id=uuid.UUID(empresa_id),
        matricula="1234XYZ",
        marca="Ford",
        model="Transit",
        estat="OPERATIU",
        odometre_acumulat=100000
    )
    admin_session.add(vehicle)
    await admin_session.flush()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # A) Checkin
        res_ci = await ac.post(f"/api/v1/operari/vehicles/{vehicle.id}/checkin", json={"odometre_inicial": 100050}, headers=headers)
        assert res_ci.status_code == 201
        assert res_ci.json()["estat"] == "CHECKIN_OK"

        # B) Repostatge
        res_rep = await ac.post(f"/api/v1/operari/vehicles/{vehicle.id}/repostatge", json={"litres": 50, "euros": 65.5, "odometre": 100080}, headers=headers)
        assert res_rep.status_code == 201
        assert res_rep.json()["estat"] == "REPOSTATGE_OK"

        # C) Checkout
        res_co = await ac.post(f"/api/v1/operari/vehicles/{vehicle.id}/checkout", json={"odometre_final": 100120}, headers=headers)
        assert res_co.status_code == 200
        data_co = res_co.json()
        assert data_co["km_recorreguts"] == 70 # 100120 - 100050
