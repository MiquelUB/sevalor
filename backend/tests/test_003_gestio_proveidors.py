import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.models.models import Empresa


@pytest.mark.asyncio
async def test_alta_proveidor_valid(admin_session, headers, boss_token):
    token, empresa_id = boss_token
    boss_nif = "B" + str(uuid.uuid4())[:8].upper()

    admin_session.add(Empresa(
        id=uuid.UUID(empresa_id), nom='Test Prov', nif=boss_nif, subdomini='testprov-' + str(uuid.uuid4())[:5], pla_subscripcio='STARTER', estat_pagament='ACTIU'
    ))
    await admin_session.flush()
    await admin_session.flush()

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


@pytest.mark.asyncio
async def test_enumeracio_automatica_proveidors_i_aillament_tenant(admin_session, headers, boss_token):
    from app.core.security import create_access_token

    _, empresa_id_1 = boss_token
    admin_session.add(
        Empresa(
            id=uuid.UUID(empresa_id_1),
            nom="AutoNum Prov 1",
            nif="B" + str(uuid.uuid4())[:8].upper(),
            subdomini="autonump1-" + str(uuid.uuid4())[:5],
            pla_subscripcio="STARTER",
            estat_pagament="ACTIU",
        )
    )
    empresa_id_2 = uuid.uuid4()
    admin_session.add(
        Empresa(
            id=empresa_id_2,
            nom="AutoNum Prov 2",
            nif="B" + str(uuid.uuid4())[:8].upper(),
            subdomini="autonump2-" + str(uuid.uuid4())[:5],
            pla_subscripcio="STARTER",
            estat_pagament="ACTIU",
        )
    )
    await admin_session.flush()

    token_2 = create_access_token({"sub": str(uuid.uuid4()), "rol": "BOSS", "empresa_id": str(empresa_id_2)})
    headers_2 = {"Authorization": f"Bearer {token_2}", "X-Empresa-ID": str(empresa_id_2)}

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # 1. Alta sense codi -> PRV-0001
        r1 = await ac.post(
            "/api/v1/gestio/proveidors",
            json={"rao_social": "Proveïdor U SL", "nif": "B10101010", "especialitat": "MATERIALS"},
            headers=headers,
        )
        assert r1.status_code == 201, r1.text
        assert r1.json()["codi"] == "PRV-0001"
        prov1_id = r1.json()["id"]

        # 2. Alta intentant passar codi manual -> s'ignora i assigna PRV-0002
        r2 = await ac.post(
            "/api/v1/gestio/proveidors",
            json={"codi": "MANUAL-77", "rao_social": "Proveïdor Dos SL", "nif": "B20202020"},
            headers=headers,
        )
        assert r2.status_code == 201, r2.text
        assert r2.json()["codi"] == "PRV-0002"

        # 3. Edició no permet alterar manualment el codi assignat
        r_put = await ac.put(
            f"/api/v1/gestio/proveidors/{prov1_id}",
            json={"codi": "CANVI-MANUAL", "rao_social": "Proveïdor U Modificat", "nif": "B10101010"},
            headers=headers,
        )
        assert r_put.status_code == 200, r_put.text
        assert r_put.json()["codi"] == "PRV-0001"
        assert r_put.json()["rao_social"] == "Proveïdor U Modificat"

        # 4. Un altre tenant comença independentment per PRV-0001
        r_emp2 = await ac.post(
            "/api/v1/gestio/proveidors",
            json={"rao_social": "Proveïdor Tenant 2", "nif": "B30303030"},
            headers=headers_2,
        )
        assert r_emp2.status_code == 201, r_emp2.text
        assert r_emp2.json()["codi"] == "PRV-0001"
