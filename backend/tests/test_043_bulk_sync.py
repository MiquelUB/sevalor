import uuid

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.models.models import Empresa


@pytest_asyncio.fixture
async def setup_sync(admin_session, boss_token):
    token, empresa_id = boss_token

    # 0. Crear empresa
    boss_nif = "B" + str(uuid.uuid4())[:8].upper()
    admin_session.add(Empresa(id=uuid.UUID(empresa_id), nom='Test Sync', nif=boss_nif, subdomini='sync-' + str(uuid.uuid4())[:5], pla_subscripcio='STARTER', estat_pagament='ACTIU'))
    await admin_session.commit()

    return {
        "empresa_id": empresa_id,
        "token": token
    }

@pytest.mark.asyncio
async def test_bulk_sync_push(setup_sync):
    data = setup_sync
    headers = {"Authorization": f"Bearer {data['token']}", "X-Empresa-ID": data["empresa_id"]}

    payload = {
        "accions": [
            {
                "id": str(uuid.uuid4()),
                "accio": "FITXAR_JORNADA",
                "payload": {"tipus": "ENTRADA", "coords": [41.0, 2.0]}
            },
            {
                "id": str(uuid.uuid4()),
                "accio": "CREAR_TIQUET",
                "payload": {"categoria": "CARBURANT", "import": 50.0}
            },
            {
                "id": str(uuid.uuid4()),
                "accio": "REPORTAR_INCIDENCIA",
                "payload": {"tipus": "AVARIA_VEHICLE", "descripcio": "Roda punxada"}
            },
            {
                "id": str(uuid.uuid4()),
                "accio": "INICIAR_TRAJECTE",
                "payload": {"ordre_id": str(uuid.uuid4())}
            },
            {
                "id": str(uuid.uuid4()),
                "accio": "FINALITZAR_ORDRE",
                "payload": {"ordre_id": str(uuid.uuid4()), "estat": "COMPLETADA"}
            }
        ]
    }

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        res = await ac.post("/api/v1/operari_pwa/sync/push", json=payload, headers=headers)

        assert res.status_code == 200
        json_resp = res.json()
        assert json_resp["status"] == "ok"
        assert json_resp["processades"] == 5
