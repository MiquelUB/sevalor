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


def test_parse_csv_excel_semicolon_latin1_and_short_rows():
    from app.api.v1.gestio.clients import ClientCreate
    from app.services.csv_service import parse_and_validate_csv_with_rows
    from app.services.subagents.subagent_ocr_vision import (
        CLIENT_HEADER_ALIASES as _CLIENT_CSV_ALIASES,
    )

    # Excel català: punt i coma, codificació cp1252, capçaleres amb accents, fila curta i línia buida
    raw_text = (
        "Raó Social;NIF;Telèfon;Adreça Fiscal\n"
        "Agrícola del Vallès SL;B61234567;600111222\n"
        "\n"
        "Instal·lacions Solà;NIF_DOLENT;600999888;Carrer Major, 12\n"
        "Regadiu Ponent SA;A69876543\n"
    )
    valid_rows, errors = parse_and_validate_csv_with_rows(
        raw_text.encode("cp1252"),
        ClientCreate,
        column_aliases=_CLIENT_CSV_ALIASES,
    )
    assert len(valid_rows) == 2
    assert valid_rows[0][0] == 2
    assert valid_rows[0][1].rao_social == "Agrícola del Vallès SL"
    assert valid_rows[0][1].adreca_fiscal is None
    assert valid_rows[1][0] == 5
    assert valid_rows[1][1].nif == "A69876543"
    assert len(errors) == 1
    assert errors[0]["fila"] == 4
    assert errors[0]["columna"] == "nif"


@pytest.mark.asyncio
async def test_import_csv_clients_robustesa_i_rls(admin_session, headers, boss_token):
    from app.core.security import create_access_token

    _, empresa_id_1 = boss_token
    admin_session.add(
        Empresa(
            id=uuid.UUID(empresa_id_1),
            nom="Import Emp 1",
            nif="B" + str(uuid.uuid4())[:8].upper(),
            subdomini="imp1-" + str(uuid.uuid4())[:5],
            pla_subscripcio="STARTER",
            estat_pagament="ACTIU",
        )
    )
    empresa_id_2 = uuid.uuid4()
    admin_session.add(
        Empresa(
            id=empresa_id_2,
            nom="Import Emp 2",
            nif="B" + str(uuid.uuid4())[:8].upper(),
            subdomini="imp2-" + str(uuid.uuid4())[:5],
            pla_subscripcio="STARTER",
            estat_pagament="ACTIU",
        )
    )
    await admin_session.flush()

    token_2 = create_access_token({"sub": str(uuid.uuid4()), "rol": "BOSS", "empresa_id": str(empresa_id_2)})
    headers_2 = {"Authorization": f"Bearer {token_2}", "X-Empresa-ID": str(empresa_id_2)}

    csv_excel = (
        "Raó Social;NIF;Telèfon\n"
        "Masia Ca n'Oriol;B71111111;611111111\n"
        "Masia Ca n'Oriol Dup;B71111111\n"
        "Cooperativa Garraf;B72222222\n"
    ).encode("cp1252")

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        r_ok = await ac.post(
            "/api/v1/gestio/clients/import",
            files={"file": ("CLIENTS.CSV", csv_excel, "text/csv")},
            headers=headers,
        )
        assert r_ok.status_code == 200, r_ok.text
        data = r_ok.json()
        assert data["inserits"] == 2
        assert data["total_processats"] == 3
        assert len(data["errors_detectats"]) == 1
        assert data["errors_detectats"][0]["fila"] == 3
        assert "NIF" in data["errors_detectats"][0]["motiu"]

        # Verificar que els 2 vàlids s'han persistit i estan aïllats per RLS
        r_emp1 = await ac.get("/api/v1/gestio/clients", headers=headers)
        assert r_emp1.status_code == 200
        assert len(r_emp1.json()) == 2

        r_emp2 = await ac.get("/api/v1/gestio/clients", headers=headers_2)
        assert r_emp2.status_code == 200
        assert r_emp2.json() == []

        # Rebutjar fitxer buit o extensió invàlida
        r_empty = await ac.post(
            "/api/v1/gestio/clients/import",
            files={"file": ("buit.csv", b"   ", "text/csv")},
            headers=headers,
        )
        assert r_empty.status_code == 400

        r_ext = await ac.post(
            "/api/v1/gestio/clients/import",
            files={"file": ("clients.xlsx", b"PK\x03\x04dummy", "application/octet-stream")},
            headers=headers,
        )
        assert r_ext.status_code == 400


@pytest.mark.asyncio
async def test_import_csv_clients_tots_els_camps_i_copilot_wss(admin_session, headers, boss_token, tmp_path):
    """Verifica l'extracció dels 8 camps de clients via Copilot (subagent OCR sobre túnel WSS real)."""
    import json

    from tests.wss_test_helpers import live_empresa_wss_context

    _, empresa_id = boss_token
    emp_uuid = uuid.UUID(empresa_id)
    vault_token = f"svlt_csv_{uuid.uuid4().hex[:12]}"
    admin_session.add(
        Empresa(
            id=emp_uuid,
            nom="Copilot CSV Emp",
            nif="B" + str(uuid.uuid4())[:8].upper(),
            subdomini="csvcop-" + str(uuid.uuid4())[:5],
            pla_subscripcio="ENTERPRISE",
            estat_pagament="ACTIU",
            disc_dur_url=f"wss-tunnel://{emp_uuid}",
            node_ia_url=f"wss-tunnel://{emp_uuid}",
            vault_token=vault_token,
            node_ia_actiu=True,
            feature_copilot_ia=True,
        )
    )
    await admin_session.flush()

    copilot_mapping_json = json.dumps(
        {
            "te_capcalera": True,
            "mapping": {
                "rao_social": [0],
                "nif": [1],
                "adreca_fiscal": [2, 3],
                "email": [4],
                "telefon": [5],
                "web": [6],
                "persona_contacte": [7],
                "dades_contacte": [8],
                "codi": [],
                "iban": [],
            },
        }
    )

    # Capçaleres arbitràries que només el Copilot pot mapejar semànticament
    csv_arbitrari = (
        "ColA;ColB;ColC;ColD;ColE;ColF;ColG;ColH;ColI\n"
        "Finca Els Olivers SL;ESB81234567;C/ del Pi 4;08720 Vilafranca;info@olivers.cat;612345678;https://olivers.cat;Marta Soler;Directora compres · Matins\n"
    ).encode("utf-8")

    async with live_empresa_wss_context(
        empresa_id=emp_uuid,
        vault_token=vault_token,
        disk_a=tmp_path / "disk_a",
        default_reply=copilot_mapping_json,
    ) as ctx:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            r_imp = await ac.post(
                "/api/v1/gestio/clients/import",
                files={"file": ("clients_crm.csv", csv_arbitrari, "text/csv")},
                headers=headers,
            )
            assert r_imp.status_code == 200, r_imp.text
            res_json = r_imp.json()
            assert res_json["copilot_usat"] is True
            assert res_json["inserits"] == 1
            assert res_json["errors_detectats"] == []
            assert len(ctx["llm_calls"]) >= 1

            r_list = await ac.get("/api/v1/gestio/clients", headers=headers)
            assert r_list.status_code == 200
            clients = r_list.json()
            assert len(clients) == 1
            c = clients[0]
            assert c["rao_social"] == "Finca Els Olivers SL"
            assert c["nif"] == "B81234567"
            assert c["adreca_fiscal"] == "C/ del Pi 4, 08720 Vilafranca"
            assert c["email"] == "info@olivers.cat"
            assert c["telefon"] == "612345678"
            assert c["web"] == "https://olivers.cat"
            assert c["persona_contacte"] == "Marta Soler"
            assert c["dades_contacte"] == "Directora compres · Matins"


@pytest.mark.asyncio
async def test_import_csv_clients_camps_buits_no_atura_extraccio(admin_session, headers, boss_token):
    """Si algun camp (inclòs NIF o raó social) ve buit/null, no s'atura l'extracció ni falla el llistat."""
    _, empresa_id = boss_token
    admin_session.add(
        Empresa(
            id=uuid.UUID(empresa_id),
            nom="Tolerant CSV Emp",
            nif="B" + str(uuid.uuid4())[:8].upper(),
            subdomini="tolcsv-" + str(uuid.uuid4())[:5],
            pla_subscripcio="STARTER",
            estat_pagament="ACTIU",
        )
    )
    await admin_session.flush()

    csv_parcial = (
        "Raó Social;NIF;Adreça;Email;Telèfon;Web;Persona de contacte;Dades del contacte\n"
        "Client Sense NIF;;Carrer Nou 1;a@ex.cat;600111222;;;\n"
        "Altre Sense NIF;;;b@ex.cat;;https://b.cat;;\n"
        ";;;c@ex.cat;600333444;;Pere Puig;Només contacte\n"
        "Només Nom;;;;;;;\n"
    ).encode("utf-8")

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        r_imp = await ac.post(
            "/api/v1/gestio/clients/import",
            files={"file": ("parcial.csv", csv_parcial, "text/csv")},
            headers=headers,
        )
        assert r_imp.status_code == 200, r_imp.text
        data = r_imp.json()
        assert data["inserits"] == 4
        assert data["errors_detectats"] == []

        r_list = await ac.get("/api/v1/gestio/clients", headers=headers)
        assert r_list.status_code == 200, r_list.text
        clients = r_list.json()
        assert len(clients) == 4
        noms = {c["rao_social"] for c in clients}
        assert "Client Sense NIF" in noms
        assert "Altre Sense NIF" in noms
        assert "Pere Puig" in noms
        assert "Només Nom" in noms
