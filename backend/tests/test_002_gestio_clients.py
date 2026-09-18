from app.models.models import Empresa, Usuari, Client
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
    admin_session.add(Empresa(
        id=uuid.UUID(empresa_id), nom='Test Clients', nif=boss_nif, subdomini='testcli-' + str(uuid.uuid4())[:5], pla_subscripcio='STARTER', estat_pagament='ACTIU'
    ))
    await admin_session.flush()
    
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
    admin_session.add(Empresa(
        id=uuid.UUID(empresa_id), nom='Test Buits', nif=boss_nif, subdomini='testbuits-' + str(uuid.uuid4())[:5], pla_subscripcio='STARTER', estat_pagament='ACTIU'
    ))
    await admin_session.flush()
    
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
    admin_session.add(Empresa(
        id=uuid.UUID(empresa_id_1), nom='Test 1', nif=boss_nif1, subdomini='test1-' + str(uuid.uuid4())[:5], pla_subscripcio='STARTER', estat_pagament='ACTIU'
    ))
    client_id_1 = str(uuid.uuid4())
    admin_session.add(Client(
        id=uuid.UUID(client_id_1), empresa_id=uuid.UUID(empresa_id_1), codi='CLI-1', rao_social='Client Emp 1', nif='NIF111'
    ))
    
    # 2. Crear empresa 2 i client 2
    empresa_id_2 = str(uuid.uuid4())
    boss_nif2 = "B" + str(uuid.uuid4())[:8].upper()
    admin_session.add(Empresa(
        id=uuid.UUID(empresa_id_2), nom='Test 2', nif=boss_nif2, subdomini='test2-' + str(uuid.uuid4())[:5], pla_subscripcio='STARTER', estat_pagament='ACTIU'
    ))
    client_id_2 = str(uuid.uuid4())
    admin_session.add(Client(
        id=uuid.UUID(client_id_2), empresa_id=uuid.UUID(empresa_id_2), codi='CLI-2', rao_social='Client Emp 2', nif='NIF222'
    ))
    await admin_session.flush()
    
    # 3. Empresa 1 consulta clients (hauria de veure'n 1)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        res = await ac.get("/api/v1/gestio/clients", headers=headers)
        assert res.status_code == 200
        llista = res.json()
        assert len(llista) == 1
        assert llista[0]["rao_social"] == "Client Emp 1"
