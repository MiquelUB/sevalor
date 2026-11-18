import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.models.models import Client, Empresa


@pytest.mark.asyncio
async def test_alta_client_i_llistat(admin_session, headers, boss_token):
    _, empresa_id = boss_token

    # 1. Creem l'empresa
    boss_nif = "B" + str(uuid.uuid4())[:8].upper()
    admin_session.add(Empresa(
        id=uuid.UUID(empresa_id), nom='Test Clients', nif=boss_nif, subdomini='testcli-' + str(uuid.uuid4())[:5], pla_subscripcio='STARTER', estat_pagament='ACTIU'
    ))
    await admin_session.flush()
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
    await admin_session.flush()
    client_id_1 = str(uuid.uuid4())
    admin_session.add(Client(
        id=uuid.UUID(client_id_1), empresa_id=uuid.UUID(empresa_id_1), codi='CLI-1', rao_social='Client Emp 1', nif='B12345678'
    ))
    await admin_session.flush()

    # 2. Crear empresa 2 i client 2
    empresa_id_2 = str(uuid.uuid4())
    boss_nif2 = "B" + str(uuid.uuid4())[:8].upper()
    admin_session.add(Empresa(
        id=uuid.UUID(empresa_id_2), nom='Test 2', nif=boss_nif2, subdomini='test2-' + str(uuid.uuid4())[:5], pla_subscripcio='STARTER', estat_pagament='ACTIU'
    ))
    await admin_session.flush()
    client_id_2 = str(uuid.uuid4())
    admin_session.add(Client(
        id=uuid.UUID(client_id_2), empresa_id=uuid.UUID(empresa_id_2), codi='CLI-2', rao_social='Client Emp 2', nif='B23456789'
    ))
    await admin_session.flush()
    await admin_session.flush()

        # 3. Empresa 1 consulta clients (hauria de veure'n 1)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        res = await ac.get("/api/v1/gestio/clients", headers=headers)
        assert res.status_code == 200
        llista = res.json()
        assert len(llista) == 1
        assert llista[0]["rao_social"] == "Client Emp 1"


@pytest.mark.asyncio
async def test_enumeracio_automatica_clients_i_aillament_tenant(admin_session, headers, boss_token):
    from app.core.security import create_access_token

    _, empresa_id_1 = boss_token
    admin_session.add(
        Empresa(
            id=uuid.UUID(empresa_id_1),
            nom="AutoNum Emp 1",
            nif="B" + str(uuid.uuid4())[:8].upper(),
            subdomini="autonum1-" + str(uuid.uuid4())[:5],
            pla_subscripcio="STARTER",
            estat_pagament="ACTIU",
        )
    )
    empresa_id_2 = uuid.uuid4()
    admin_session.add(
        Empresa(
            id=empresa_id_2,
            nom="AutoNum Emp 2",
            nif="B" + str(uuid.uuid4())[:8].upper(),
            subdomini="autonum2-" + str(uuid.uuid4())[:5],
            pla_subscripcio="STARTER",
            estat_pagament="ACTIU",
        )
    )
    await admin_session.flush()

    token_2 = create_access_token({"sub": str(uuid.uuid4()), "rol": "BOSS", "empresa_id": str(empresa_id_2)})
    headers_2 = {"Authorization": f"Bearer {token_2}", "X-Empresa-ID": str(empresa_id_2)}

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # 1. Alta sense codi -> CLI-0001
        r1 = await ac.post(
            "/api/v1/gestio/clients",
            json={"rao_social": "Primer Client SL", "nif": "B11111111"},
            headers=headers,
        )
        assert r1.status_code == 201, r1.text
        assert r1.json()["codi"] == "CLI-0001"
        cli1_id = r1.json()["id"]

        # 2. Alta intentant passar un codi manual -> s'ignora i assigna CLI-0002
        r2 = await ac.post(
            "/api/v1/gestio/clients",
            json={"codi": "MANUAL-999", "rao_social": "Segon Client SL", "nif": "B22222222"},
            headers=headers,
        )
        assert r2.status_code == 201, r2.text
        assert r2.json()["codi"] == "CLI-0002"

        # 3. Edició no permet alterar manualment el codi assignat
        r_put = await ac.put(
            f"/api/v1/gestio/clients/{cli1_id}",
            json={"codi": "CANVI-MANUAL", "rao_social": "Primer Client Modificat", "nif": "B11111111"},
            headers=headers,
        )
        assert r_put.status_code == 200, r_put.text
        assert r_put.json()["codi"] == "CLI-0001"
        assert r_put.json()["rao_social"] == "Primer Client Modificat"

        # 4. Importació CSV sense columna codi -> CLI-0003, CLI-0004
        csv_content = "rao_social,nif,telefon\nClient CSV 1,B33333333,600111222\nClient CSV 2,B44444444,600333444\n"
        r_csv = await ac.post(
            "/api/v1/gestio/clients/import",
            files={"file": ("clients.csv", csv_content.encode("utf-8"), "text/csv")},
            headers=headers,
        )
        assert r_csv.status_code == 200, r_csv.text
        assert r_csv.json()["inserits"] == 2

        r_list = await ac.get("/api/v1/gestio/clients", headers=headers)
        codis_emp1 = sorted(c["codi"] for c in r_list.json())
        assert codis_emp1 == ["CLI-0001", "CLI-0002", "CLI-0003", "CLI-0004"]

        # 5. Un altre tenant comença independentment per CLI-0001
        r_emp2 = await ac.post(
            "/api/v1/gestio/clients",
            json={"rao_social": "Client Tenant 2", "nif": "B55555555"},
            headers=headers_2,
        )
        assert r_emp2.status_code == 201, r_emp2.text
        assert r_emp2.json()["codi"] == "CLI-0001"
