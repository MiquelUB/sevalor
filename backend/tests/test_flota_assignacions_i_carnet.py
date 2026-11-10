import uuid
from datetime import date, datetime, timedelta, timezone

import jwt
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.main import app
from app.models.models import Empresa, Usuari, Vehicle


@pytest.mark.asyncio
async def test_assignacio_bidireccional_flota_a_operaris(
    admin_session: AsyncSession, headers: dict, boss_token: tuple
):
    """Verifica l'assignació 1:1 des del mòdul de Flota cap als Operaris:

    - Assignar V1 a Op1 reflecteix el vehicle a la fitxa d'Op1.
    - Reassignar V1 a Op2 desvincula automàticament Op1 (garantia 1:1 estricta).
    - El vehicle manté l'estat 'OPERATIU'.
    """
    token, empresa_id = boss_token
    emp_uuid = uuid.UUID(empresa_id)

    admin_session.add(
        Empresa(
            id=emp_uuid,
            nom="Empresa Test Flota 1a1",
            nif="B" + str(uuid.uuid4())[:8].upper(),
            subdomini="testflota-" + str(uuid.uuid4())[:5],
            pla_subscripcio="ENTERPRISE",
            estat_pagament="ACTIU",
        )
    )
    await admin_session.flush()

    avui = date.today()
    op1_id = uuid.uuid4()
    op1 = Usuari(
        id=op1_id,
        empresa_id=emp_uuid,
        nif="48" + op1_id.hex[:6].upper() + "A",
        nom="Jordi",
        cognoms="Pujol",
        telefon="+34600111222",
        rol="OPERARI",
        especialitat="SISTEMES_REG",
        carnet_conduir="B",
        carnet_caducitat=avui + timedelta(days=365),
        pin_hash="fakehash",
        estat="ACTIU",
    )
    op2_id = uuid.uuid4()
    op2 = Usuari(
        id=op2_id,
        empresa_id=emp_uuid,
        nif="48" + op2_id.hex[:6].upper() + "B",
        nom="Marc",
        cognoms="Soler",
        telefon="+34600333444",
        rol="OPERARI",
        especialitat="OBRA_CIVIL",
        carnet_conduir="B",
        carnet_caducitat=avui + timedelta(days=365),
        pin_hash="fakehash",
        estat="ACTIU",
    )
    admin_session.add_all([op1, op2])
    await admin_session.flush()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # 1. Donar d'alta vehicle assignant-lo a Op1
        v_payload = {
            "matricula": "5544BBD",
            "marca": "Citroen",
            "model": "Berlingo",
            "tipus": "FURGONETA",
            "distintiu_ambiental": "C",
            "estat": "OPERATIU",
            "regim_adquisicio": "PROPIETAT",
            "carnet_necessari": "B",
            "conductor_habitual_id": str(op1_id),
        }
        res_crear = await ac.post("/api/v1/gestio/flota", json=v_payload, headers=headers)
        assert res_crear.status_code == 201, res_crear.text
        v_data = res_crear.json()
        vehicle_id = v_data["id"]
        assert v_data["conductor_habitual_id"] == str(op1_id)
        assert v_data["estat"] == "OPERATIU"

        # 2. Comprovar que llistar operaris i obtenir Op1 mostren el vehicle assignat
        res_ops = await ac.get("/api/v1/gestio/operaris", headers=headers)
        assert res_ops.status_code == 200, res_ops.text
        ops_data = res_ops.json()
        op1_res = next(o for o in ops_data if o["id"] == str(op1_id))
        op2_res = next(o for o in ops_data if o["id"] == str(op2_id))
        assert op1_res["vehicle_habitual"] is not None
        assert op1_res["vehicle_habitual"]["matricula"] == "5544BBD"
        assert op2_res["vehicle_habitual"] is None

        # 3. Comprovar GET /gestio/operaris/{id}
        res_single_op = await ac.get(f"/api/v1/gestio/operaris/{op1_id}", headers=headers)
        assert res_single_op.status_code == 200
        assert res_single_op.json()["vehicle_habitual"]["matricula"] == "5544BBD"

        # 4. Reassignar V1 a Op2 via endpoint d'assignació de flota
        res_assignar = await ac.post(
            f"/api/v1/gestio/flota/{vehicle_id}/assignar",
            json={"usuari_id": str(op2_id)},
            headers=headers,
        )
        assert res_assignar.status_code == 200, res_assignar.text
        assert res_assignar.json()["conductor_habitual_id"] == str(op2_id)
        assert res_assignar.json()["estat"] == "OPERATIU"

        # 5. Comprovar que Op1 queda automàticament desvinculat i Op2 té el vehicle (1:1)
        res_ops_2 = await ac.get("/api/v1/gestio/operaris", headers=headers)
        ops_data_2 = res_ops_2.json()
        op1_after = next(o for o in ops_data_2 if o["id"] == str(op1_id))
        op2_after = next(o for o in ops_data_2 if o["id"] == str(op2_id))
        assert op1_after["vehicle_habitual"] is None
        assert op2_after["vehicle_habitual"] is not None
        assert op2_after["vehicle_habitual"]["matricula"] == "5544BBD"

        # 6. Reassignar de nou a Op1 mitjançant PUT /gestio/flota/{id}
        v_put_payload = {
            **v_payload,
            "conductor_habitual_id": str(op1_id),
        }
        res_put_flota = await ac.put(
            f"/api/v1/gestio/flota/{vehicle_id}", json=v_put_payload, headers=headers
        )
        assert res_put_flota.status_code == 200, res_put_flota.text
        assert res_put_flota.json()["conductor_habitual_id"] == str(op1_id)

        res_single_op1 = await ac.get(f"/api/v1/gestio/operaris/{op1_id}", headers=headers)
        res_single_op2 = await ac.get(f"/api/v1/gestio/operaris/{op2_id}", headers=headers)
        assert res_single_op1.json()["vehicle_habitual"]["matricula"] == "5544BBD"
        assert res_single_op2.json()["vehicle_habitual"] is None


@pytest.mark.asyncio
async def test_assignacio_bidireccional_operaris_a_flota(
    admin_session: AsyncSession, headers: dict, boss_token: tuple
):
    """Verifica l'assignació des del mòdul d'Operaris cap a Flota:

    - Assignar un vehicle des de PUT /gestio/operaris/{op_id} sincronitza conductor_habitual_id a Flota.
    - Desvincular el vehicle des d'Operaris (vehicle_assignat_id = None) allibera el vehicle a Flota.
    """
    token, empresa_id = boss_token
    emp_uuid = uuid.UUID(empresa_id)

    admin_session.add(
        Empresa(
            id=emp_uuid,
            nom="Empresa Test Operaris a Flota",
            nif="B" + str(uuid.uuid4())[:8].upper(),
            subdomini="testop-" + str(uuid.uuid4())[:5],
            pla_subscripcio="ENTERPRISE",
            estat_pagament="ACTIU",
        )
    )
    await admin_session.flush()

    avui = date.today()
    op_id = uuid.uuid4()
    op = Usuari(
        id=op_id,
        empresa_id=emp_uuid,
        nif="48" + op_id.hex[:6].upper() + "C",
        nom="Laura",
        cognoms="Vila",
        telefon="+34600555666",
        rol="OPERARI",
        especialitat="ELECTRICITAT",
        carnet_conduir="B",
        carnet_caducitat=avui + timedelta(days=365),
        pin_hash="fakehash",
        estat="ACTIU",
    )
    veh_id = uuid.uuid4()
    veh = Vehicle(
        id=veh_id,
        empresa_id=emp_uuid,
        matricula="7788LLK",
        marca="Renault",
        model="Kangoo",
        tipus="FURGONETA",
        carnet_necessari="B",
        regim_adquisicio="PROPIETAT",
        estat="OPERATIU",
    )
    admin_session.add_all([op, veh])
    await admin_session.flush()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # 1. Assignar vehicle des de PUT /gestio/operaris/{op_id}
        put_payload = {
            "nom": "Laura",
            "cognoms": "Vila",
            "vehicle_assignat_id": str(veh_id),
        }
        res_put = await ac.put(f"/api/v1/gestio/operaris/{op_id}", json=put_payload, headers=headers)
        assert res_put.status_code == 200, res_put.text
        op_data = res_put.json()
        assert op_data["vehicle_habitual"] is not None
        assert op_data["vehicle_habitual"]["matricula"] == "7788LLK"

        # 2. Comprovar que el vehicle a Flota (detall i llistat) té ara Laura com a conductor habitual
        res_flota = await ac.get(f"/api/v1/gestio/flota/{veh_id}", headers=headers)
        assert res_flota.status_code == 200, res_flota.text
        v_data = res_flota.json()
        assert v_data["conductor_habitual_id"] == str(op_id)
        assert "Laura" in (v_data["conductor_nom"] or "")

        res_flota_list = await ac.get("/api/v1/gestio/flota", headers=headers)
        assert res_flota_list.status_code == 200
        v_in_list = next(v for v in res_flota_list.json() if v["id"] == str(veh_id))
        assert v_in_list["conductor_habitual_id"] == str(op_id)
        assert "Laura" in (v_in_list["conductor_nom"] or "")
        assert v_in_list["estat"] == "OPERATIU"

        # 3. Desvincular el vehicle enviant vehicle_assignat_id = None
        put_desvincular = {
            "vehicle_assignat_id": None,
        }
        res_desv = await ac.put(
            f"/api/v1/gestio/operaris/{op_id}", json=put_desvincular, headers=headers
        )
        assert res_desv.status_code == 200, res_desv.text
        assert res_desv.json()["vehicle_habitual"] is None

        # 4. Comprovar que a Flota el vehicle queda alliberat
        res_flota_alliberat = await ac.get(f"/api/v1/gestio/flota/{veh_id}", headers=headers)
        assert res_flota_alliberat.status_code == 200
        assert res_flota_alliberat.json()["conductor_habitual_id"] is None
        assert res_flota_alliberat.json()["conductor_nom"] is None


@pytest.mark.asyncio
async def test_bloqueig_carnet_insuficient_i_caducat_t028(
    admin_session: AsyncSession, headers: dict, boss_token: tuple
):
    """Verifica les regles de validació de carnet de conduir segons FR-012 i T028:

    1. Bloqueig (HTTP 422) si el vehicle requereix carnet C i l'operari té només permís B.
    2. Bloqueig (HTTP 422) si el carnet de conduir de l'operari està caducat.
    """
    token, empresa_id = boss_token
    emp_uuid = uuid.UUID(empresa_id)

    admin_session.add(
        Empresa(
            id=emp_uuid,
            nom="Empresa Test Bloqueig Carnet",
            nif="B" + str(uuid.uuid4())[:8].upper(),
            subdomini="testcarnet-" + str(uuid.uuid4())[:5],
            pla_subscripcio="ENTERPRISE",
            estat_pagament="ACTIU",
        )
    )
    await admin_session.flush()

    avui = date.today()

    # Operari amb carnet B vigent
    op_b_id = uuid.uuid4()
    op_b = Usuari(
        id=op_b_id,
        empresa_id=emp_uuid,
        nif="48" + op_b_id.hex[:6].upper() + "D",
        nom="Joan",
        cognoms="Gomez",
        telefon="+34600777888",
        rol="OPERARI",
        especialitat="SISTEMES_REG",
        carnet_conduir="B",
        carnet_caducitat=avui + timedelta(days=365),
        pin_hash="fakehash",
        estat="ACTIU",
    )
    # Operari amb carnet B però CADUCAT (fa 10 dies)
    op_caducat_id = uuid.uuid4()
    op_caducat = Usuari(
        id=op_caducat_id,
        empresa_id=emp_uuid,
        nif="48" + op_caducat_id.hex[:6].upper() + "E",
        nom="Pere",
        cognoms="Caducat",
        telefon="+34600999000",
        rol="OPERARI",
        especialitat="SISTEMES_REG",
        carnet_conduir="B",
        carnet_caducitat=avui - timedelta(days=10),
        pin_hash="fakehash",
        estat="ACTIU",
    )
    # Vehicle pesat que requereix carnet C
    veh_camio_id = uuid.uuid4()
    veh_camio = Vehicle(
        id=veh_camio_id,
        empresa_id=emp_uuid,
        matricula="1122CCC",
        marca="Iveco",
        model="Eurocargo",
        tipus="CAMIO",
        carnet_necessari="C",
        regim_adquisicio="PROPIETAT",
        estat="OPERATIU",
    )
    # Furgoneta normal que requereix carnet B
    veh_furgo_id = uuid.uuid4()
    veh_furgo = Vehicle(
        id=veh_furgo_id,
        empresa_id=emp_uuid,
        matricula="3344BBB",
        marca="Ford",
        model="Transit",
        tipus="FURGONETA",
        carnet_necessari="B",
        regim_adquisicio="PROPIETAT",
        estat="OPERATIU",
    )
    admin_session.add_all([op_b, op_caducat, veh_camio, veh_furgo])
    await admin_session.flush()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # Cas 1: Intent d'assignar Camió (carnet C) a operari amb carnet B
        res_incompatible = await ac.post(
            f"/api/v1/gestio/flota/{veh_camio_id}/assignar",
            json={"usuari_id": str(op_b_id)},
            headers=headers,
        )
        assert res_incompatible.status_code == 422, res_incompatible.text
        assert "requereix permís" in res_incompatible.text or "només disposa" in res_incompatible.text

        # Cas 2: Intent d'assignar Furgoneta (carnet B) a operari amb carnet B CADUCAT
        res_caducat = await ac.post(
            f"/api/v1/gestio/flota/{veh_furgo_id}/assignar",
            json={"usuari_id": str(op_caducat_id)},
            headers=headers,
        )
        assert res_caducat.status_code == 422, res_caducat.text
        assert "ha caducat" in res_caducat.text or "caducat" in res_caducat.text

        # Cas 3: Intent d'assignar Camió (carnet C) des de la fitxa de l'operari (PUT /gestio/operaris/{id})
        res_op_incompatible = await ac.put(
            f"/api/v1/gestio/operaris/{op_b_id}",
            json={"vehicle_assignat_id": str(veh_camio_id)},
            headers=headers,
        )
        assert res_op_incompatible.status_code == 422, res_op_incompatible.text
        assert "requereix permís" in res_op_incompatible.text


@pytest.mark.asyncio
async def test_operari_pwa_rep_el_seu_vehicle_assignat(
    admin_session: AsyncSession, boss_token: tuple
):
    """Verifica que quan un operari consulta la PWA (/operari/vehicles):

    - El vehicle habitual assignat se situa obligatòriament a l'índex 0 (data[0]).
    - L'objecte inclou marca_model i tipus esperats per la interfície de camp.
    """
    token, empresa_id = boss_token
    emp_uuid = uuid.UUID(empresa_id)

    admin_session.add(
        Empresa(
            id=emp_uuid,
            nom="Empresa Test PWA Vehicles",
            nif="B" + str(uuid.uuid4())[:8].upper(),
            subdomini="testpwa-" + str(uuid.uuid4())[:5],
            pla_subscripcio="ENTERPRISE",
            estat_pagament="ACTIU",
        )
    )
    await admin_session.flush()

    avui = date.today()
    op_id = uuid.uuid4()
    op = Usuari(
        id=op_id,
        empresa_id=emp_uuid,
        nif="48" + op_id.hex[:6].upper() + "F",
        nom="Pol",
        cognoms="Roca",
        telefon="+34611222333",
        rol="OPERARI",
        especialitat="SISTEMES_REG",
        carnet_conduir="B",
        carnet_caducitat=avui + timedelta(days=365),
        pin_hash="fakehash",
        estat="ACTIU",
    )
    v1 = Vehicle(
        id=uuid.uuid4(),
        empresa_id=emp_uuid,
        matricula="1000AAA",
        marca="Toyota",
        model="Hilux",
        tipus="4X4",
        carnet_necessari="B",
        estat="OPERATIU",
    )
    v2_assignat = Vehicle(
        id=uuid.uuid4(),
        empresa_id=emp_uuid,
        matricula="2000BBB",
        marca="Mercedes",
        model="Vito",
        tipus="FURGONETA",
        carnet_necessari="B",
        estat="OPERATIU",
        conductor_habitual_id=op_id,
    )
    v3 = Vehicle(
        id=uuid.uuid4(),
        empresa_id=emp_uuid,
        matricula="3000CCC",
        marca="Nissan",
        model="Navara",
        tipus="4X4",
        carnet_necessari="B",
        estat="OPERATIU",
    )
    op.vehicle_assignat_id = v2_assignat.id
    admin_session.add_all([op, v1, v2_assignat, v3])
    await admin_session.flush()

    # Generar JWT vàlid per a l'operari
    payload_jwt = {
        "sub": str(op_id),
        "empresa_id": str(emp_uuid),
        "rol": "OPERARI",
        "exp": int((datetime.now(timezone.utc) + timedelta(hours=2)).timestamp()),
    }
    operari_token = jwt.encode(payload_jwt, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    op_headers = {
        "Authorization": f"Bearer {operari_token}",
        "X-Empresa-ID": str(emp_uuid),
    }

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        res = await ac.get("/api/v1/operari/vehicles", headers=op_headers)
        assert res.status_code == 200, res.text
        data = res.json()
        assert len(data) == 3

        # El vehicle a data[0] ha de ser exactament el vehicle assignat v2_assignat
        assert data[0]["id"] == str(v2_assignat.id)
        assert data[0]["matricula"] == "2000BBB"
        assert data[0]["marca_model"] == "Mercedes Vito"
        assert data[0]["tipus"] == "FURGONETA"


@pytest.mark.asyncio
async def test_persistencia_sobirana_disc_dur_empresa_flota_i_operaris(
    admin_session: AsyncSession, headers: dict, boss_token: tuple, tmp_path
):
    """Verifica que totes les dades i documents de Flota i Operaris es guarden al disc dur
    dedicat de l'empresa (08_flota_i_operaris/vehicles) i MAI a /docs ni /tmp/docs del servidor:

    1. Alta d'operari i alta de vehicle desen operari_<id>.json i <vehicle_id>.json al disc dur de l'empresa.
    2. Assignació i reassignació 1:1 actualitzen atòmicament les fitxes JSON tant al vehicle com als operaris.
    3. Pujada de document del vehicle (PDF ITV/Pòlissa) es desa al disc dur de l'empresa i es serveix en streaming.
    4. Registre de manteniment es desa com a manteniment_<id>.json al disc dur de l'empresa.
    5. Cap fitxer es crea a /docs/<empresa_id> ni /tmp/docs/<empresa_id> del servidor central.
    """
    import json
    import os
    from pathlib import Path

    token, empresa_id = boss_token
    emp_uuid = uuid.UUID(empresa_id)
    disc_empresa: Path = tmp_path / f"disc_flota_{emp_uuid.hex[:6]}"

    admin_session.add(
        Empresa(
            id=emp_uuid,
            nom="Empresa Disc Sobirà Flota SL",
            nif="B" + str(uuid.uuid4())[:8].upper(),
            subdomini="discflota-" + str(uuid.uuid4())[:5],
            disc_dur_url=str(disc_empresa),
            pla_subscripcio="ENTERPRISE",
            estat_pagament="ACTIU",
        )
    )
    await admin_session.flush()

    avui = date.today()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # 1. Alta d'Operari via API
        op_payload = {
            "nif": "47889900X",
            "nom": "Arnau",
            "cognoms": "Tècnic",
            "telefon": "+34655443322",
            "email": "arnau@discflota.cat",
            "rol": "OPERARI",
            "especialitat": "SISTEMES_REG",
            "cost_hora_eur": 24.0,
            "carnet_conduir": "B+E",
            "carnet_caducitat": (avui + timedelta(days=500)).isoformat(),
        }
        res_op = await ac.post("/api/v1/gestio/operaris", json=op_payload, headers=headers)
        assert res_op.status_code == 201, res_op.text
        op_id = res_op.json()["id"]

        carpeta_flota = disc_empresa / "08_flota_i_operaris" / "vehicles"
        fitxa_op = carpeta_flota / f"operari_{op_id}.json"
        assert fitxa_op.exists(), f"Fitxa d'operari no trobada al disc de l'empresa: {fitxa_op}"
        op_disk_data = json.loads(fitxa_op.read_text(encoding="utf-8"))
        assert op_disk_data["nom"] == "Arnau"
        assert op_disk_data["carnet_conduir"] == "B+E"

        # 2. Alta de Vehicle vinculat a l'Operari via API
        v_payload = {
            "matricula": "8899-DSK",
            "marca": "Volkswagen",
            "model": "Crafter",
            "tipus": "FURGONETA",
            "distintiu_ambiental": "C",
            "estat": "OPERATIU",
            "regim_adquisicio": "RENTING",
            "renting_limit_km": 30000,
            "odometre_inici_contracte": 1000,
            "odometre_acumulat": 12500,
            "quota_mensual_eur": 520.0,
            "preu_km_exces_eur": 0.12,
            "carnet_necessari": "B",
            "conductor_habitual_id": op_id,
        }
        res_v = await ac.post("/api/v1/gestio/flota", json=v_payload, headers=headers)
        assert res_v.status_code == 201, res_v.text
        v_id = res_v.json()["id"]

        fitxa_veh = carpeta_flota / f"{v_id}.json"
        assert fitxa_veh.exists(), f"Fitxa de vehicle no trobada al disc de l'empresa: {fitxa_veh}"
        veh_disk_data = json.loads(fitxa_veh.read_text(encoding="utf-8"))
        assert veh_disk_data["matricula"] == "8899-DSK"
        assert veh_disk_data["regim_adquisicio"] == "RENTING"
        assert veh_disk_data["conductor_habitual_id"] == op_id
        assert veh_disk_data["km_recorreguts_contracte"] == 11500

        # Verificar que la fitxa de l'operari al disc també s'ha sincronitzat amb el vehicle habitual
        op_disk_updated = json.loads(fitxa_op.read_text(encoding="utf-8"))
        assert op_disk_updated["vehicle_assignat_id"] == v_id
        assert op_disk_updated["vehicle_habitual"]["matricula"] == "8899-DSK"

        # 3. Pujada de document PDF del vehicle al disc dur de l'empresa
        pdf_bytes = b"%PDF-1.4 Fitxa Tecnica ITV Crafter 8899-DSK"
        files = {"file": ("fitxa_itv_8899dsk.pdf", pdf_bytes, "application/pdf")}
        data_form = {"tipus_document": "ITV"}
        res_doc = await ac.post(
            f"/api/v1/gestio/flota/{v_id}/documents",
            data=data_form,
            files=files,
            headers=headers,
        )
        assert res_doc.status_code == 201, res_doc.text
        doc_id = res_doc.json()["id"]
        ruta_arxiu = res_doc.json()["ruta_arxiu"]

        # Comprovar que l'arxiu és dins el disc dur de l'empresa i NO a /docs ni /tmp/docs
        assert str(disc_empresa) in ruta_arxiu
        assert os.path.exists(ruta_arxiu)
        assert not os.path.exists(f"/docs/{emp_uuid}")
        assert not os.path.exists(f"/tmp/docs/{emp_uuid}")

        # Comprovar que es pot descarregar el fitxer des del disc de l'empresa via streaming
        res_download = await ac.get(
            f"/api/v1/gestio/flota/{v_id}/documents/{doc_id}/fitxer",
            headers=headers,
        )
        assert res_download.status_code == 200
        assert res_download.content == pdf_bytes

        # 4. Registre de manteniment al disc dur de l'empresa
        mant_payload = {
            "data_manteniment": avui.isoformat(),
            "tipus": "PREVENTIU",
            "descripcio": "Canvi d'oli i filtres",
            "taller": "Taller Oficial VW",
            "cost_euros": 245.50,
        }
        res_mant = await ac.post(
            f"/api/v1/gestio/flota/{v_id}/manteniments",
            json=mant_payload,
            headers=headers,
        )
        assert res_mant.status_code == 201, res_mant.text
        mant_id = res_mant.json()["id"]
        fitxa_mant = carpeta_flota / f"manteniment_{mant_id}.json"
        assert fitxa_mant.exists(), f"Fitxa de manteniment no trobada a {fitxa_mant}"
        assert "Taller Oficial VW" in fitxa_mant.read_text(encoding="utf-8")
