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
