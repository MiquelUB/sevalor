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


@pytest.mark.asyncio
async def test_modificar_feina_amb_planols_eines_i_picking(admin_session, headers, boss_token):
    """Verifica l'assignació de plànols, eines en custòdia i picking amb correlació d'estoc."""
    from sqlalchemy import select

    from app.models.models import (
        Article,
        CarpetaPlanol,
        EinaCustodia,
        EstocMagatzem,
        Magatzem,
        PlanolBase,
    )

    token, empresa_id = boss_token
    emp_uuid = uuid.UUID(empresa_id)

    # 1. Empresa
    emp_nif = "B" + str(uuid.uuid4())[:8].upper()
    admin_session.add(
        Empresa(
            id=emp_uuid,
            nom="Empresa Magatzem Picking",
            nif=emp_nif,
            subdomini="testpick-" + str(uuid.uuid4())[:5],
            pla_subscripcio="STARTER",
            estat_pagament="ACTIU",
        )
    )
    await admin_session.flush()

    # 2. Client & Operari
    client_id = uuid.uuid4()
    admin_session.add(
        Client(
            id=client_id,
            empresa_id=emp_uuid,
            codi="CLI-PICK",
            rao_social="Client Picking S.L.",
            nif="A55443322",
        )
    )
    operari_id = uuid.uuid4()
    admin_session.add(
        Usuari(
            id=operari_id,
            empresa_id=emp_uuid,
            nif="OP-301",
            nom="Sergi",
            cognoms="Puig",
            rol="OPERARI",
            estat="ACTIU",
        )
    )

    # 3. Plànol tècnic
    carpeta_id = uuid.uuid4()
    admin_session.add(
        CarpetaPlanol(
            id=carpeta_id,
            empresa_id=emp_uuid,
            nom="Projectes Baixa Tensió",
            categoria="PROJECTES",
        )
    )
    planol_id = uuid.uuid4()
    admin_session.add(
        PlanolBase(
            id=planol_id,
            empresa_id=emp_uuid,
            carpeta_id=carpeta_id,
            titol="Esquema Unifilar Quadre General",
            codi_referencia="PL-ELEC-001",
            tipus_fitxer="PDF",
            fitxer_path="/docs/test/pl-elec-001.pdf",
            mida_bytes=10240,
        )
    )

    # 4. Eines en custòdia
    eina1_id = uuid.uuid4()
    admin_session.add(
        EinaCustodia(
            id=eina1_id,
            empresa_id=emp_uuid,
            nom="Premsa terminals hidràulica",
            model="Cembre HT131-C",
            numero_serie="SN-PREMSA-01",
            estat="DISPONIBLE",
        )
    )
    eina2_id = uuid.uuid4()
    admin_session.add(
        EinaCustodia(
            id=eina2_id,
            empresa_id=emp_uuid,
            nom="Pinça amperimètrica",
            model="Fluke 376 FC",
            numero_serie="SN-PINCA-02",
            estat="DISPONIBLE",
        )
    )

    # 5. Magatzem i Articles amb Estoc
    magatzem_id = uuid.uuid4()
    admin_session.add(
        Magatzem(
            id=magatzem_id,
            empresa_id=emp_uuid,
            nom="Magatzem Central Lleida",
            tipus="NAU_CENTRAL",
            actiu=True,
        )
    )
    art1_id = uuid.uuid4()
    admin_session.add(
        Article(
            id=art1_id,
            empresa_id=emp_uuid,
            referencia_inventari="CAB-16MM",
            nom="Cable unipolar coure 16mm2 lliure d'halògens",
            unitat_mesura="METRE",
            actiu=True,
        )
    )
    art2_id = uuid.uuid4()
    admin_session.add(
        Article(
            id=art2_id,
            empresa_id=emp_uuid,
            referencia_inventari="TER-M8",
            nom="Terminal de coure M8 16mm2",
            unitat_mesura="UNITAT",
            actiu=True,
        )
    )
    await admin_session.flush()

    admin_session.add(
        EstocMagatzem(
            id=uuid.uuid4(),
            empresa_id=emp_uuid,
            article_id=art1_id,
            magatzem_id=magatzem_id,
            quantitat_fisica=100.0,
            quantitat_virtual_reservada=10.0,  # 90 disponibles
        )
    )
    admin_session.add(
        EstocMagatzem(
            id=uuid.uuid4(),
            empresa_id=emp_uuid,
            article_id=art2_id,
            magatzem_id=magatzem_id,
            quantitat_fisica=50.0,
            quantitat_virtual_reservada=0.0,  # 50 disponibles
        )
    )

    await admin_session.commit()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # A. Crear l'Ordre de Treball
        payload_crear = {
            "codi": "OT-FULL-01",
            "client_id": str(client_id),
            "titol": "Muntatge Quadre i Connexió",
            "adreca": "Polígon Industrial Camí dels Frares, Nau 4",
            "descripcio": "Execució de connexió de baixa tensió",
            "estat": "PENDENT",
            "data_planificacio": "2027-04-01",
            "cap_de_colla_id": str(operari_id),
        }
        res_c = await ac.post("/api/v1/gestio/feines", json=payload_crear, headers=headers)
        assert res_c.status_code == 201, res_c.text
        ot_data = res_c.json()
        ot_id = ot_data["id"]

        # B. Modificar OT assignant plànol, dues eines i picking de materials
        payload_update = {
            "planol_id": str(planol_id),
            "eina_ids": [str(eina1_id), str(eina2_id)],
            "linies_picking": [
                {"article_id": str(art1_id), "quantitat_prevista": 25.0},
                {"article_id": str(art2_id), "quantitat_prevista": 10.0},
            ],
            "versio": ot_data["versio"],
        }
        res_put = await ac.put(f"/api/v1/gestio/feines/{ot_id}", json=payload_update, headers=headers)
        assert res_put.status_code == 200, res_put.text
        put_data = res_put.json()

        # Verificar retorn de plànol vinculat
        assert put_data["planol_id"] == str(planol_id)
        assert put_data["planol_titol"] == "Esquema Unifilar Quadre General"
        assert put_data["planol_codi"] == "PL-ELEC-001"

        # Verificar retorn d'eines
        assert len(put_data["eines"]) == 2
        eines_noms = [e["nom"] for e in put_data["eines"]]
        assert "Premsa terminals hidràulica" in eines_noms
        assert "Pinça amperimètrica" in eines_noms

        # Verificar retorn de picking
        assert len(put_data["linies_picking"]) == 2
        p_cables = next(
            (lp for lp in put_data["linies_picking"] if lp["article_id"] == str(art1_id)),
            None,
        )
        assert p_cables is not None
        assert p_cables["quantitat_prevista"] == 25.0
        assert p_cables["unitat_mesura"] == "METRE"

        # C. Verificar a la base de dades que l'estoc virtual s'ha actualitzat
        res_estoc1 = await admin_session.execute(
            select(EstocMagatzem).where(EstocMagatzem.article_id == art1_id)
        )
        estoc1_db = res_estoc1.scalars().first()
        # Inicialment 10.0 reservat + 25.0 ara = 35.0 reservat
        assert float(estoc1_db.quantitat_virtual_reservada) == 35.0

        res_estoc2 = await admin_session.execute(
            select(EstocMagatzem).where(EstocMagatzem.article_id == art2_id)
        )
        estoc2_db = res_estoc2.scalars().first()
        assert float(estoc2_db.quantitat_virtual_reservada) == 10.0

        # D. Verificar que les eines a la BD estan en CUSTODIADA i vinculades a la feina
        res_eina1 = await admin_session.execute(
            select(EinaCustodia).where(EinaCustodia.id == eina1_id)
        )
        eina1_db = res_eina1.scalars().first()
        assert eina1_db.estat == "CUSTODIADA"
        assert eina1_db.ordre_treball_id == uuid.UUID(ot_id)
        assert eina1_db.custodiat_per_operari_id == operari_id

        # E. Provar desvincular una eina i eliminar una línia de picking (alliberant reserva)
        payload_update_2 = {
            "eina_ids": [str(eina1_id)],  # eina2 alliberada
            "linies_picking": [
                {"article_id": str(art1_id), "quantitat_prevista": 15.0},  # reducció de 25 a 15
                # art2 descartat -> alliberar 10.0
            ],
            "versio": put_data["versio"],
        }
        res_put2 = await ac.put(f"/api/v1/gestio/feines/{ot_id}", json=payload_update_2, headers=headers)
        assert res_put2.status_code == 200, res_put2.text
        put2_data = res_put2.json()

        assert len(put2_data["eines"]) == 1
        assert len(put2_data["linies_picking"]) == 1

        # Comprovar que eina2 ha tornat a DISPONIBLE i sense ordre_treball_id
        admin_session.expire_all()
        res_eina2 = await admin_session.execute(
            select(EinaCustodia).where(EinaCustodia.id == eina2_id)
        )
        eina2_db = res_eina2.scalars().first()
        assert eina2_db.estat == "DISPONIBLE"
        assert eina2_db.ordre_treball_id is None
        assert eina2_db.custodiat_per_operari_id is None

        # Comprovar alliberament de reserva d'estoc: art2 passa de 10.0 a 0.0, art1 passa a 25.0
        res_estoc1_post = await admin_session.execute(
            select(EstocMagatzem).where(EstocMagatzem.article_id == art1_id)
        )
        assert float(res_estoc1_post.scalars().first().quantitat_virtual_reservada) == 25.0

        res_estoc2_post = await admin_session.execute(
            select(EstocMagatzem).where(EstocMagatzem.article_id == art2_id)
        )
        assert float(res_estoc2_post.scalars().first().quantitat_virtual_reservada) == 0.0

        # F. Provar GET /{ot_id} per comprovar que retorna les dades sincronitzades
        res_get_final = await ac.get(f"/api/v1/gestio/feines/{ot_id}", headers=headers)
        assert res_get_final.status_code == 200
        final_data = res_get_final.json()
        assert final_data["planol_codi"] == "PL-ELEC-001"
        assert len(final_data["linies_picking"]) == 1
        assert final_data["linies_picking"][0]["quantitat_prevista"] == 15.0
        assert len(final_data["eines"]) == 1


