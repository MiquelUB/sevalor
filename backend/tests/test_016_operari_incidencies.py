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
