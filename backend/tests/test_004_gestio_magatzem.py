import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.models.models import Empresa


@pytest.mark.asyncio
async def test_alta_article_valid(admin_session, headers, boss_token):
    token, empresa_id = boss_token
    boss_nif = "B" + str(uuid.uuid4())[:8].upper()

    admin_session.add(Empresa(
        id=uuid.UUID(empresa_id), nom='Test Magatzem', nif=boss_nif, subdomini='testmag-' + str(uuid.uuid4())[:5], pla_subscripcio='STARTER', estat_pagament='ACTIU'
    ))
    await admin_session.flush()
    await admin_session.flush()

    payload = {
        "referencia_inventari": "REF-ART-001",
        "nom": "Tornavís d'Estrella Test",
        "unitat_mesura": "UNITAT",
        "familia": "EINES",
        "estoc_optim": 10.0,
        "estoc_minim": 2.0,
        "es_lot_caducable": False,
        "preu_cost": 5.50,
        "preu_venda": 15.00
    }

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        res = await ac.post("/api/v1/gestio/magatzem/articles", json=payload, headers=headers)
        assert res.status_code == 201, f"Expected 201, got {res.status_code}: {res.text}"
        data = res.json()
        assert data["referencia_inventari"] == "REF-ART-001"
        assert data["nom"] == "Tornavís d'Estrella Test"

        # Llistat (RF-01)
        res_list = await ac.get("/api/v1/gestio/magatzem/articles", headers=headers)
        assert res_list.status_code == 200
        llista = res_list.json()
        assert len(llista) == 1
        assert llista[0]["referencia_inventari"] == "REF-ART-001"

        # Duplicat (per respectar constraints de BD)
        res_dup = await ac.post("/api/v1/gestio/magatzem/articles", json=payload, headers=headers)
        assert res_dup.status_code == 400
        assert "registrada" in res_dup.json()["detail"]


@pytest.mark.asyncio
async def test_magatzems_nau_i_furgoneta_segregacio_estoc(admin_session, headers, boss_token):
    from app.models.models import EstocMagatzem, Vehicle

    token, empresa_id = boss_token
    boss_nif = "B" + str(uuid.uuid4())[:8].upper()

    admin_session.add(Empresa(
        id=uuid.UUID(empresa_id),
        nom='Test Magatzem Segregat',
        nif=boss_nif,
        subdomini='magseg-' + str(uuid.uuid4())[:5],
        pla_subscripcio='STARTER',
        estat_pagament='ACTIU'
    ))
    # Crear un vehicle de flota
    veh_id = uuid.uuid4()
    mat_test = f"{uuid.uuid4().hex[:4].upper()}-XYZ"
    admin_session.add(Vehicle(
        id=veh_id,
        empresa_id=uuid.UUID(empresa_id),
        matricula=mat_test,
        marca="Renault",
        model="Master",
        tipus="FURGONETA",
        estat="OPERATIU",
    ))
    await admin_session.flush()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # 1. Llistar magatzems: ha d'auto-crear Nau Central i el magatzem mòbil del vehicle
        res_mags = await ac.get("/api/v1/gestio/magatzem/magatzems", headers=headers)
        assert res_mags.status_code == 200
        mags = res_mags.json()
        assert len(mags) >= 2

        nau_central = next((m for m in mags if m["tipus"] == "NAU_CENTRAL"), None)
        furgoneta = next((m for m in mags if m["tipus"] == "FURGONETA" and m["vehicle_id"] == str(veh_id)), None)

        assert nau_central is not None, "Nau Central Base ha d'estar present"
        assert furgoneta is not None, "Magatzem Furgoneta del vehicle ha d'estar present"
        assert furgoneta["vehicle_matricula"] == mat_test

        # 2. Donar d'alta un article
        art_payload = {
            "referencia_inventari": f"TUB-PE-{uuid.uuid4().hex[:4]}",
            "nom": "Tub Polietilè 32mm",
            "unitat_mesura": "METRES",
            "familia": "TUBERIA",
            "estoc_optim": 100.0,
            "estoc_minim": 20.0,
            "preu_cost": 2.50,
            "preu_venda": 5.00
        }
        res_art = await ac.post("/api/v1/gestio/magatzem/articles", json=art_payload, headers=headers)
        assert res_art.status_code == 201
        art_id = res_art.json()["id"]

        # 3. Inicialitzar 100m a Nau Central
        admin_session.add(EstocMagatzem(
            empresa_id=uuid.UUID(empresa_id),
            magatzem_id=uuid.UUID(nau_central["id"]),
            article_id=uuid.UUID(art_id),
            quantitat_fisica=100.0,
            quantitat_virtual_reservada=0.0
        ))
        await admin_session.commit()

        # 4. Traspàs de 30m de Nau Central a Furgoneta
        traspas_payload = {
            "article_id": art_id,
            "origen_magatzem_id": nau_central["id"],
            "desti_magatzem_id": furgoneta["id"],
            "quantitat": 30.0
        }
        res_traspas = await ac.post("/api/v1/gestio/magatzem/traspas-furgoneta", json=traspas_payload, headers=headers)
        assert res_traspas.status_code == 200
        assert res_traspas.json()["estat"] == "OK"

        # 5. Comprovar segregació d'estoc:
        # A) Consolidat global (sense filtre magatzem_id): 100m
        res_global = await ac.get("/api/v1/gestio/magatzem/articles", headers=headers)
        assert res_global.status_code == 200
        item_global = next(a for a in res_global.json() if a["id"] == art_id)
        assert item_global["estoc_real"] == 100.0

        # B) Nau Central: 70m
        res_nau = await ac.get(f"/api/v1/gestio/magatzem/articles?magatzem_id={nau_central['id']}", headers=headers)
        assert res_nau.status_code == 200
        item_nau = next(a for a in res_nau.json() if a["id"] == art_id)
        assert item_nau["estoc_real"] == 70.0

        # C) Furgoneta mòbil: 30m
        res_furg = await ac.get(f"/api/v1/gestio/magatzem/articles?magatzem_id={furgoneta['id']}", headers=headers)
        assert res_furg.status_code == 200
        item_furg = next(a for a in res_furg.json() if a["id"] == art_id)
        assert item_furg["estoc_real"] == 30.0


@pytest.mark.asyncio
async def test_eines_custodia_vehicle(admin_session, headers, boss_token):
    from app.models.models import Magatzem, Vehicle

    token, empresa_id = boss_token
    boss_nif = "B" + str(uuid.uuid4())[:8].upper()

    admin_session.add(Empresa(
        id=uuid.UUID(empresa_id),
        nom='Test Eines Vehicle',
        nif=boss_nif,
        subdomini='einesveh-' + str(uuid.uuid4())[:5],
        pla_subscripcio='STARTER',
        estat_pagament='ACTIU'
    ))
    veh_id = uuid.uuid4()
    mat_test = f"{uuid.uuid4().hex[:4].upper()}-EIN"
    admin_session.add(Vehicle(
        id=veh_id,
        empresa_id=uuid.UUID(empresa_id),
        matricula=mat_test,
        marca="Iveco",
        model="Daily",
        tipus="FURGONETA",
        estat="OPERATIU",
    ))
    mag_veh_id = uuid.uuid4()
    admin_session.add(Magatzem(
        id=mag_veh_id,
        empresa_id=uuid.UUID(empresa_id),
        nom=f"Furgoneta {mat_test}",
        tipus="FURGONETA",
        vehicle_id=veh_id,
        actiu=True,
    ))
    await admin_session.commit()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # 1. Crear una eina
        eina_payload = {
            "referencia_fabricant": "MAKITA-HR2470",
            "nom": "Martell Perforador Combinat",
            "model": "HR2470",
            "numero_serie": f"SN-{uuid.uuid4().hex[:6]}"
        }
        res_crear = await ac.post("/api/v1/gestio/magatzem/eines", json=eina_payload, headers=headers)
        assert res_crear.status_code == 201
        eina_id = res_crear.json()["id"]

        # 2. Checkout de l'eina al vehicle/magatzem mòbil
        res_co = await ac.post(
            f"/api/v1/gestio/magatzem/eines/{eina_id}/checkout",
            json={"magatzem_id": str(mag_veh_id)},
            headers=headers
        )
        assert res_co.status_code == 200
        assert res_co.json()["estat"] == "EN_VEHICLE"

        # 3. Consultar llistat d'eines: ha de reflectir el nom de la furgoneta com a custòdia
        res_list = await ac.get("/api/v1/gestio/magatzem/eines", headers=headers)
        assert res_list.status_code == 200
        eina_item = next(e for e in res_list.json() if e["id"] == eina_id)
        assert eina_item["estat"] == "EN_VEHICLE"
        assert mat_test in (eina_item["custodia_nom"] or "")

        # 4. Checkin (retorn a base)
        res_ci = await ac.post(f"/api/v1/gestio/magatzem/eines/{eina_id}/checkin", headers=headers)
        assert res_ci.status_code == 200
        assert res_ci.json()["estat"] == "DISPONIBLE"
