import uuid

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.models.models import Empresa, Usuari


@pytest_asyncio.fixture
async def setup_incidencia_test(admin_session):
    empresa_id = str(uuid.uuid4())
    operari_id = str(uuid.uuid4())
    nif_rand = "NIF-" + str(uuid.uuid4())[:5]

    # Empresa i Operari
    admin_session.add(Empresa(
        id=uuid.UUID(empresa_id), nom='Test Inc', nif=nif_rand, subdomini='incpwa-' + str(uuid.uuid4())[:8], pla_subscripcio='STARTER', estat_pagament='ACTIU'
    ))
    await admin_session.flush()
    admin_session.add(Usuari(
        id=uuid.UUID(operari_id), empresa_id=uuid.UUID(empresa_id), nif=nif_rand + 'P', nom='Pere Incidencia', rol='OPERARI', pin_hash='hash', pin_bloquejat=False, intents_pin_fallits=0
    ))
    await admin_session.flush()
    await admin_session.flush()

    return {"empresa_id": empresa_id, "operari_id": operari_id}

@pytest.mark.asyncio
async def test_crear_incidencia(setup_incidencia_test):
    data = setup_incidencia_test
    from datetime import datetime, timedelta, timezone

    import jwt

    from app.core.config import settings

    payload = {
        "sub": data["operari_id"],
        "rol": "OPERARI",
        "empresa_id": data["empresa_id"],
        "exp": datetime.now(timezone.utc) + timedelta(minutes=60)
    }
    token = jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    headers = {"Authorization": f"Bearer {token}"}

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        inci_payload = {
            "ambit": "TASCA",
            "estat": "VERMELL",
            "text_observacions": "S'ha trencat la canonada d'aigua"
        }
        res_inci = await ac.post("/api/v1/operari/incidencies", json=inci_payload, headers=headers)
        assert res_inci.status_code == 201
        assert res_inci.json()["ambit"] == "TASCA"
        assert res_inci.json()["text_observacions"] == "S'ha trencat la canonada d'aigua"

        # Test llistar
        res_list = await ac.get("/api/v1/operari/incidencies", headers=headers)
        assert res_list.status_code == 200
        assert len(res_list.json()) == 1


@pytest.mark.asyncio
async def test_llistar_incidencies_drawer(setup_incidencia_test, admin_session):
    data = setup_incidencia_test
    from datetime import datetime, timedelta, timezone

    import jwt

    from app.core.config import settings

    # Crear token per al cap/enginyer
    enginyer_id = str(uuid.uuid4())
    admin_session.add(Usuari(
        id=uuid.UUID(enginyer_id),
        empresa_id=uuid.UUID(data["empresa_id"]),
        nif="ENG-" + str(uuid.uuid4())[:5],
        nom="Enginyer",
        cognoms="Test",
        rol="ENGINYER",
        pin_hash="hash",
        pin_bloquejat=False,
        intents_pin_fallits=0
    ))
    await admin_session.flush()

    token_eng = jwt.encode(
        {
            "sub": enginyer_id,
            "rol": "ENGINYER",
            "empresa_id": data["empresa_id"],
            "exp": datetime.now(timezone.utc) + timedelta(minutes=60),
        },
        settings.SECRET_KEY,
        algorithm=settings.ALGORITHM,
    )
    headers_eng = {"Authorization": f"Bearer {token_eng}", "X-Empresa-ID": data["empresa_id"]}

    token_op = jwt.encode(
        {
            "sub": data["operari_id"],
            "rol": "OPERARI",
            "empresa_id": data["empresa_id"],
            "exp": datetime.now(timezone.utc) + timedelta(minutes=60),
        },
        settings.SECRET_KEY,
        algorithm=settings.ALGORITHM,
    )
    headers_op = {"Authorization": f"Bearer {token_op}", "X-Empresa-ID": data["empresa_id"]}

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # L'operari reporta incidència
        inci_payload = {
            "ambit": "MATERIAL",
            "estat": "VERMELL",
            "text_observacions": "Falta material a l'obra per acabar reg",
        }
        res_create = await ac.post("/api/v1/operari/incidencies", json=inci_payload, headers=headers_op)
        assert res_create.status_code == 201
        inc_id = res_create.json()["id"]

        # El panell de control (drawer) llegeix les incidències obertes
        res_drawer = await ac.get("/api/v1/gestio/dashboard/incidencies-drawer", headers=headers_eng)
        assert res_drawer.status_code == 200
        drawer_items = res_drawer.json()
        assert len(drawer_items) >= 1
        item = next(i for i in drawer_items if i["id"] == inc_id)
        assert item["estat"] == "VERMELL"
        assert item["grau"] == "URGENT_BLOQUEJANT"
        assert item["operari_nom"] == "Pere Incidencia"
        assert item["text_observacions"] == "Falta material a l'obra per acabar reg"


@pytest.mark.asyncio
async def test_resoldre_incidencia_verd(setup_incidencia_test, admin_session):
    data = setup_incidencia_test
    from datetime import datetime, timedelta, timezone

    import jwt

    from app.core.config import settings

    token_op = jwt.encode(
        {
            "sub": data["operari_id"],
            "rol": "OPERARI",
            "empresa_id": data["empresa_id"],
            "exp": datetime.now(timezone.utc) + timedelta(minutes=60),
        },
        settings.SECRET_KEY,
        algorithm=settings.ALGORITHM,
    )
    headers_op = {"Authorization": f"Bearer {token_op}", "X-Empresa-ID": data["empresa_id"]}

    token_boss = jwt.encode(
        {
            "sub": data["operari_id"],
            "rol": "BOSS",
            "empresa_id": data["empresa_id"],
            "exp": datetime.now(timezone.utc) + timedelta(minutes=60),
        },
        settings.SECRET_KEY,
        algorithm=settings.ALGORITHM,
    )
    headers_boss = {"Authorization": f"Bearer {token_boss}", "X-Empresa-ID": data["empresa_id"]}

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        res_create = await ac.post(
            "/api/v1/operari/incidencies",
            json={"ambit": "TASCA", "estat": "VERMELL", "text_observacions": "Vàlvula encallada"},
            headers=headers_op,
        )
        assert res_create.status_code == 201
        inc_id = res_create.json()["id"]

        # Resolució per part de l'operari a camp
        res_resoldre_op = await ac.patch(
            f"/api/v1/operari/incidencies/{inc_id}/resoldre",
            json={"observacions": "Desbloquejada amb clau anglesa"},
            headers=headers_op,
        )
        assert res_resoldre_op.status_code == 200
        assert res_resoldre_op.json()["estat"] == "VERD"

        # Crear-ne una altra per resoldre des de gestió
        res_create2 = await ac.post(
            "/api/v1/operari/incidencies",
            json={"ambit": "VEHICLE", "estat": "VERMELL", "text_observacions": "Pneumàtic punxat"},
            headers=headers_op,
        )
        inc_id2 = res_create2.json()["id"]

        # Resolució des del panell de control
        res_resoldre_dash = await ac.patch(
            f"/api/v1/gestio/dashboard/incidencies/{inc_id2}/resoldre",
            headers=headers_boss,
        )
        assert res_resoldre_dash.status_code == 200
        assert res_resoldre_dash.json()["estat"] == "VERD"


@pytest.mark.asyncio
async def test_aprova_hitl_incidencia(setup_incidencia_test):
    data = setup_incidencia_test
    from datetime import datetime, timedelta, timezone

    import jwt

    from app.core.config import settings

    token_boss = jwt.encode(
        {
            "sub": data["operari_id"],
            "rol": "BOSS",
            "empresa_id": data["empresa_id"],
            "exp": datetime.now(timezone.utc) + timedelta(minutes=60),
        },
        settings.SECRET_KEY,
        algorithm=settings.ALGORITHM,
    )
    headers_boss = {"Authorization": f"Bearer {token_boss}", "X-Empresa-ID": data["empresa_id"]}

    token_op = jwt.encode(
        {
            "sub": data["operari_id"],
            "rol": "OPERARI",
            "empresa_id": data["empresa_id"],
            "exp": datetime.now(timezone.utc) + timedelta(minutes=60),
        },
        settings.SECRET_KEY,
        algorithm=settings.ALGORITHM,
    )
    headers_op = {"Authorization": f"Bearer {token_op}", "X-Empresa-ID": data["empresa_id"]}

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        res_create = await ac.post(
            "/api/v1/operari/incidencies",
            json={"ambit": "CLIENT", "estat": "VERMELL", "text_observacions": "Client demana moure tub"},
            headers=headers_op,
        )
        inc_id = res_create.json()["id"]

        res_hitl = await ac.patch(
            f"/api/v1/gestio/dashboard/incidencies/{inc_id}/aprova-hitl",
            headers=headers_boss,
        )
        assert res_hitl.status_code == 200
        assert res_hitl.json()["aprovacio_hitl_supervisor"] is True
        assert res_hitl.json()["estat"] == "VERD"
