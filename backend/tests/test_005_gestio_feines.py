import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.models.models import Client, Empresa, Usuari


@pytest.mark.asyncio
async def test_alta_ordre_treball(admin_session, headers, boss_token):
    token, empresa_id = boss_token
    boss_nif = "B" + str(uuid.uuid4())[:8].upper()

    # 1. Crear empresa
    admin_session.add(Empresa(
        id=uuid.UUID(empresa_id), nom='Test Feines', nif=boss_nif, subdomini='testfeina-' + str(uuid.uuid4())[:5], pla_subscripcio='STARTER', estat_pagament='ACTIU'
    ))
    await admin_session.flush()

    # 2. Crear client per tenir client_id
    client_id = str(uuid.uuid4())
    admin_session.add(Client(
        id=uuid.UUID(client_id), empresa_id=uuid.UUID(empresa_id), codi='CLI-1', rao_social='Client FEINA', nif='12345678A'
    ))
    await admin_session.flush()

    # 3. Crear operari per tenir cap_de_colla_id
    operari_id = str(uuid.uuid4())
    admin_session.add(Usuari(
        id=uuid.UUID(operari_id), empresa_id=uuid.UUID(empresa_id), nif='OP-999', nom='Paco', cognoms='Garcia', rol='OPERARI', estat='ACTIU'
    ))
    await admin_session.flush()
    await admin_session.flush()

    payload = {
        "codi": "OT-001",
        "client_id": client_id,
        "titol": "Revisió Instal·lació",
        "adreca": "Carrer de la Indústria 42, BCN",
        "descripcio": "Revisió general",
        "estat": "PENDENT",
        "data_planificacio": "2027-01-01",
        "cap_de_colla_id": operari_id
    }

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        res = await ac.post("/api/v1/gestio/feines", json=payload, headers=headers)
        assert res.status_code == 201, f"Expected 201, got {res.status_code}: {res.text}"
        data = res.json()
        assert data["codi"] == "OT-001"
        assert data["titol"] == "Revisió Instal·lació"

        # Llistat (RF-01)
        res_list = await ac.get("/api/v1/gestio/feines", headers=headers)
        assert res_list.status_code == 200
        llista = res_list.json()
        assert len(llista) == 1
        assert llista[0]["codi"] == "OT-001"

        # Duplicat codi
        res_dup = await ac.post("/api/v1/gestio/feines", json=payload, headers=headers)
        assert res_dup.status_code == 400
        assert "registrat" in res_dup.json()["detail"]


@pytest.mark.asyncio
async def test_crear_feina_amb_eines_i_coordenades(admin_session, headers, boss_token):
    token, empresa_id = boss_token
    emp_uuid = uuid.UUID(empresa_id)

    # 1. Crear empresa
    emp_nif = "B" + str(uuid.uuid4())[:8].upper()
    admin_session.add(Empresa(
        id=emp_uuid, nom='Empresa Test Eines', nif=emp_nif, subdomini='testeina-' + str(uuid.uuid4())[:5], pla_subscripcio='STARTER', estat_pagament='ACTIU'
    ))
    await admin_session.flush()

    # 2. Client
    client_id = uuid.uuid4()
    admin_session.add(Client(
        id=client_id, empresa_id=emp_uuid, codi='CLI-TOOLS', rao_social='Client Agro Tools', nif='B99887766'
    ))

    # 3. Operari
    operari_id = uuid.uuid4()
    admin_session.add(Usuari(
        id=operari_id, empresa_id=emp_uuid, nif='OP-888', nom='Jordi', cognoms='Sole', rol='OPERARI', estat='ACTIU'
    ))

    # 4. Eina en custòdia disponible
    from app.models.models import EinaCustodia
    eina_id = uuid.uuid4()
    nova_eina = EinaCustodia(
        id=eina_id,
        empresa_id=emp_uuid,
        nom="Multímetre Fluke 179",
        model="Fluke 179 True-RMS",
        numero_serie="SN-FLUKE-9988",
        estat="DISPONIBLE"
    )
    admin_session.add(nova_eina)
    await admin_session.commit()

    payload = {
        "codi": "OT-TOOLS-01",
        "client_id": str(client_id),
        "titol": "Revisió Quadre Elèctric General",
        "adreca": "41.6176, 0.6200",
        "descripcio": "Ús de multímetre per verificar continuïtat",
        "estat": "PENDENT",
        "data_planificacio": "2027-02-15",
        "cap_de_colla_id": str(operari_id),
        "latitud": 41.6176,
        "longitud": 0.6200,
        "eina_ids": [str(eina_id)]
    }

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # Creació
        res = await ac.post("/api/v1/gestio/feines", json=payload, headers=headers)
        assert res.status_code == 201, f"Expected 201, got {res.status_code}: {res.text}"
        data = res.json()
        assert data["codi"] == "OT-TOOLS-01"
        assert float(data["latitud"]) == pytest.approx(41.6176, abs=0.001)
        assert float(data["longitud"]) == pytest.approx(0.6200, abs=0.001)

        # Verificar que l'eina a la base de dades ara està CUSTODIADA per l'operari
        from sqlalchemy import select
        res_eina = await admin_session.execute(select(EinaCustodia).where(EinaCustodia.id == eina_id))
        eina_db = res_eina.scalars().first()
        assert eina_db is not None
        assert eina_db.estat == "CUSTODIADA"
        assert eina_db.custodiat_per_operari_id == operari_id

        # Verificar que apareix al mapa GeoJSON
        res_mapa = await ac.get("/api/v1/gestio/feines/mapa", headers=headers)
        assert res_mapa.status_code == 200
        geojson = res_mapa.json()
        assert geojson["type"] == "FeatureCollection"
        matching_feat = next((f for f in geojson["features"] if f["properties"]["codi"] == "OT-TOOLS-01"), None)
        assert matching_feat is not None
        assert matching_feat["geometry"]["coordinates"] == [pytest.approx(0.6200, abs=0.001), pytest.approx(41.6176, abs=0.001)]
        assert matching_feat["properties"]["cap_de_colla_id"] == str(operari_id)

        # Verificar HUD Dashboard
        res_hud = await ac.get("/api/v1/gestio/dashboard/hud", headers=headers)
        assert res_hud.status_code == 200
        hud_data = res_hud.json()
        assert "active_jobs" in hud_data
        assert "teams_on_field" in hud_data


@pytest.mark.asyncio
async def test_modificar_i_obtenir_feina(admin_session, headers, boss_token):
    """Verifica l'edició i consulta detallada d'una Ordre de Treball (editor de tasques)."""
    token, empresa_id = boss_token
    emp_uuid = uuid.UUID(empresa_id)

    emp_nif = "B" + str(uuid.uuid4())[:8].upper()
    admin_session.add(Empresa(
        id=emp_uuid, nom='Empresa Edicio OT', nif=emp_nif, subdomini='testedicio-' + str(uuid.uuid4())[:5], pla_subscripcio='STARTER', estat_pagament='ACTIU'
    ))
    await admin_session.flush()

    # Clients
    client1_id = uuid.uuid4()
    admin_session.add(Client(id=client1_id, empresa_id=emp_uuid, codi='CLI-A', rao_social='Client Alfa S.L.', nif='A11111111'))
    client2_id = uuid.uuid4()
    admin_session.add(Client(id=client2_id, empresa_id=emp_uuid, codi='CLI-B', rao_social='Client Beta S.L.', nif='B22222222'))

    # Operaris
    op1_id = uuid.uuid4()
    admin_session.add(Usuari(id=op1_id, empresa_id=emp_uuid, nif='OP-101', nom='Marc', cognoms='Vila', rol='OPERARI', estat='ACTIU'))
    op2_id = uuid.uuid4()
    admin_session.add(Usuari(id=op2_id, empresa_id=emp_uuid, nif='OP-102', nom='Laura', cognoms='Roca', rol='OPERARI', estat='ACTIU'))

    await admin_session.flush()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # 1. Crear feina inicial
        payload_crear = {
            "codi": "OT-EDIT-01",
            "client_id": str(client1_id),
            "titol": "Instal·lació de bomba solar",
            "adreca": "Carrer Major 1, Lleida",
            "descripcio": "Bomba trifàsica 3kW",
            "estat": "PENDENT",
            "data_planificacio": "2027-03-10",
            "cap_de_colla_id": str(op1_id)
        }
        res_c = await ac.post("/api/v1/gestio/feines", json=payload_crear, headers=headers)
        assert res_c.status_code == 201, res_c.text
        feina_creada = res_c.json()
        feina_id = feina_creada["id"]

        # 2. Obtenir feina per ID (GET)
        res_get = await ac.get(f"/api/v1/gestio/feines/{feina_id}", headers=headers)
        assert res_get.status_code == 200
        data_get = res_get.json()
        assert data_get["titol"] == "Instal·lació de bomba solar"
        assert data_get["client_nom"] == "Client Alfa S.L."
        assert "Marc Vila" in (data_get["cap_de_colla_nom"] or "")

        # 3. Modificar feina (PUT)
        payload_update = {
            "titol": "Instal·lació de bomba solar 5kW (Actualitzat)",
            "descripcio": "Afegit variador de freqüència a la bomba",
            "client_id": str(client2_id),
            "cap_de_colla_id": str(op2_id),
            "estat": "PROGRAMADA",
            "data_planificacio": "2027-03-15",
            "adreca": "Avinguda Catalunya 50, Lleida",
            "versio": data_get["versio"]
        }
        res_put = await ac.put(f"/api/v1/gestio/feines/{feina_id}", json=payload_update, headers=headers)
        assert res_put.status_code == 200, res_put.text
        data_put = res_put.json()
        assert data_put["titol"] == "Instal·lació de bomba solar 5kW (Actualitzat)"
        assert data_put["descripcio"] == "Afegit variador de freqüència a la bomba"
        assert data_put["client_nom"] == "Client Beta S.L."
        assert "Laura Roca" in (data_put["cap_de_colla_nom"] or "")
        assert data_put["estat"] == "PROGRAMADA"
        assert data_put["data_planificacio"] == "2027-03-15"
        assert data_put["versio"] > data_get["versio"]

        # 4. Provar Conflicte de Concurrència Optimista (409)
        payload_conflict = {
            "titol": "Intent amb versió obsoleta",
            "versio": data_get["versio"] # versió antiga
        }
        res_conf = await ac.put(f"/api/v1/gestio/feines/{feina_id}", json=payload_conflict, headers=headers)
        assert res_conf.status_code == 409
        assert "Conflicte de concurrència" in res_conf.json()["detail"]

        # 5. Feina no existent (404)
        random_id = str(uuid.uuid4())
        res_404 = await ac.get(f"/api/v1/gestio/feines/{random_id}", headers=headers)
        assert res_404.status_code == 404


