import pytest
import uuid
from httpx import AsyncClient, ASGITransport
from sqlalchemy import text
from app.main import app

@pytest.mark.asyncio
async def test_alta_client_i_llistat(admin_session, headers, boss_token):
    _, empresa_id = boss_token
    
    # 1. Creem l'empresa
    boss_nif = "B" + str(uuid.uuid4())[:8].upper()
    await admin_session.execute(
        text("INSERT INTO empreses (id, nom, nif, subdomini, pla_subscripcio, estat_pagament) VALUES (:id, 'Test Clients', :nif, :sub, 'STARTER', 'ACTIU')"),
        {"id": empresa_id, "nif": boss_nif, "sub": "testcli-" + str(uuid.uuid4())[:5]}
    )
    await admin_session.commit()
    
    # 2. Creem un client
    payload = {
        "codi": "CLI-001",
        "rao_social": "Client Test SL",
        "nif": "B12345678",
        "telefon": "+34600100200",
        "email": "info@client.cat",
        "adreca_fiscal": "Carrer Major 1, BCN"
    }
    
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        res = await ac.post("/api/v1/gestio/clients", json=payload, headers=headers)
        assert res.status_code == 201, f"Expected 201, got {res.status_code}: {res.text}"
        data = res.json()
        assert data["rao_social"] == "Client Test SL"
        assert data["nif"] == "B12345678"
        
        # 3. Provem RF-06: Duplicat NIF
        res_dup = await ac.post("/api/v1/gestio/clients", json=payload, headers=headers)
        assert res_dup.status_code == 400
        assert "ja es troba registrat" in res_dup.json()["detail"]
        
        # 4. Provem el Llistat amb Tenant (RF-01)
        res_list = await ac.get("/api/v1/gestio/clients", headers=headers)
        assert res_list.status_code == 200
        llista = res_list.json()
        assert len(llista) == 1
        assert llista[0]["rao_social"] == "Client Test SL"

@pytest.mark.asyncio
async def test_llistat_clients_buit(admin_session, headers, boss_token):
    _, empresa_id = boss_token
    
    boss_nif = "B" + str(uuid.uuid4())[:8].upper()
    await admin_session.execute(
        text("INSERT INTO empreses (id, nom, nif, subdomini, pla_subscripcio, estat_pagament) VALUES (:id, 'Test Buits', :nif, :sub, 'STARTER', 'ACTIU')"),
        {"id": empresa_id, "nif": boss_nif, "sub": "testbuits-" + str(uuid.uuid4())[:5]}
    )
    await admin_session.commit()
    
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        res = await ac.get("/api/v1/gestio/clients", headers=headers)
        assert res.status_code == 200
        llista = res.json()
        assert llista == [] # Zero Mock Data, taula buida!

@pytest.mark.asyncio
async def test_rls_clients(admin_session, headers, boss_token):
    _, empresa_id_1 = boss_token
    
    # 1. Crear empresa 1 i client 1
    boss_nif1 = "B" + str(uuid.uuid4())[:8].upper()
    await admin_session.execute(
        text("INSERT INTO empreses (id, nom, nif, subdomini, pla_subscripcio, estat_pagament) VALUES (:id, 'Test 1', :nif, :sub, 'STARTER', 'ACTIU')"),
        {"id": empresa_id_1, "nif": boss_nif1, "sub": "test1-" + str(uuid.uuid4())[:5]}
    )
    client_id_1 = str(uuid.uuid4())
    await admin_session.execute(
        text("""INSERT INTO clients (id, empresa_id, codi, rao_social, nif) 
                VALUES (:id, :emp, 'CLI-1', 'Client Emp 1', 'NIF111')"""),
        {"id": client_id_1, "emp": empresa_id_1}
    )
    
    # 2. Crear empresa 2 i client 2
    empresa_id_2 = str(uuid.uuid4())
    boss_nif2 = "B" + str(uuid.uuid4())[:8].upper()
    await admin_session.execute(
        text("INSERT INTO empreses (id, nom, nif, subdomini, pla_subscripcio, estat_pagament) VALUES (:id, 'Test 2', :nif, :sub, 'STARTER', 'ACTIU')"),
        {"id": empresa_id_2, "nif": boss_nif2, "sub": "test2-" + str(uuid.uuid4())[:5]}
    )
    client_id_2 = str(uuid.uuid4())
    await admin_session.execute(
        text("""INSERT INTO clients (id, empresa_id, codi, rao_social, nif) 
                VALUES (:id, :emp, 'CLI-2', 'Client Emp 2', 'NIF222')"""),
        {"id": client_id_2, "emp": empresa_id_2}
    )
    await admin_session.commit()
    
    # 3. Empresa 1 consulta clients (hauria de veure'n 1)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        res = await ac.get("/api/v1/gestio/clients", headers=headers)
        assert res.status_code == 200
        llista = res.json()
        assert len(llista) == 1
        assert llista[0]["rao_social"] == "Client Emp 1"
