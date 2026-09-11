import pytest
import uuid
from httpx import AsyncClient, ASGITransport
from sqlalchemy import text
from app.main import app

@pytest.mark.asyncio
async def test_alta_proveidor_valid(admin_session, headers, boss_token):
    token, empresa_id = boss_token
    boss_nif = "B" + str(uuid.uuid4())[:8].upper()
    
    await admin_session.execute(
        text("INSERT INTO empreses (id, nom, nif, subdomini, pla_subscripcio, estat_pagament) VALUES (:id, 'Test Prov', :nif, :sub, 'STARTER', 'ACTIU')"),
        {"id": empresa_id, "nif": boss_nif, "sub": "testprov-" + str(uuid.uuid4())[:5]}
    )
    await admin_session.commit()
    
    payload = {
        "codi": "PROV-001",
        "rao_social": "Proveidor Test SL",
        "nif": "B87654321",
        "telefon": "+34600100300",
        "email": "info@proveidor.cat",
        "especialitat": "MATERIALS"
    }
    
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        res = await ac.post("/api/v1/gestio/proveidors", json=payload, headers=headers)
        assert res.status_code == 201, f"Expected 201, got {res.status_code}: {res.text}"
        data = res.json()
        assert data["rao_social"] == "Proveidor Test SL"
        
        # Llistat
        res_list = await ac.get("/api/v1/gestio/proveidors", headers=headers)
        assert res_list.status_code == 200
        llista = res_list.json()
        assert len(llista) == 1
