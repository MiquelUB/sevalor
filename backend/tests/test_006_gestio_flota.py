import pytest
import uuid
from httpx import AsyncClient, ASGITransport
from sqlalchemy import text
from app.main import app

@pytest.mark.asyncio
async def test_alta_vehicle_valid(admin_session, headers, boss_token):
    token, empresa_id = boss_token
    boss_nif = "B" + str(uuid.uuid4())[:8].upper()
    
    await admin_session.execute(
        text("INSERT INTO empreses (id, nom, nif, subdomini, pla_subscripcio, estat_pagament) VALUES (:id, 'Test Flota', :nif, :sub, 'STARTER', 'ACTIU')"),
        {"id": empresa_id, "nif": boss_nif, "sub": "testflota-" + str(uuid.uuid4())[:5]}
    )
    await admin_session.commit()
    
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
