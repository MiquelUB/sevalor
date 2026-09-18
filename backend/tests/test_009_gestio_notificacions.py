from app.models.models import Empresa, Usuari, Client
import pytest_asyncio
import pytest
import uuid
from httpx import AsyncClient, ASGITransport
from sqlalchemy import text
from app.main import app

@pytest_asyncio.fixture
async def setup_notificacions_test(admin_session):
    empresa_id = str(uuid.uuid4())
    client_id = str(uuid.uuid4())
    nif_rand = "NIF-" + str(uuid.uuid4())[:5]
    sub_rand = "notis-" + str(uuid.uuid4())[:5]
    
    admin_session.add(Empresa(
        id=uuid.UUID(empresa_id), nom='Test Notis', nif=nif_rand, subdomini=sub_rand, pla_subscripcio='STARTER', estat_pagament='ACTIU'
    ))
    admin_session.add(Client(
        id=uuid.UUID(client_id), empresa_id=uuid.UUID(empresa_id), codi='CLI-1', rao_social='C', nif='NIFC'
    ))
    await admin_session.flush()
    
    return {"empresa_id": empresa_id, "client_id": client_id}

@pytest.mark.asyncio
async def test_crear_conversa(setup_notificacions_test, headers):
    data = setup_notificacions_test
    import jwt
    from datetime import datetime, timedelta, timezone
    from app.core.config import settings
    
    payload = {
        "sub": str(uuid.uuid4()),
        "rol": "BOSS",
        "empresa_id": data["empresa_id"],
        "exp": datetime.now(timezone.utc) + timedelta(minutes=60)
    }
    token = jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    headers = {"Authorization": f"Bearer {token}"}
    
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        conv_payload = {
            "client_id": data["client_id"],
            "titol": "Avís de Tall d'Aigua"
        }
        res_conv = await ac.post("/api/v1/gestio/notificacions/converses", json=conv_payload, headers=headers)
        assert res_conv.status_code == 201
        conversa = res_conv.json()
        assert conversa["titol"] == "Avís de Tall d'Aigua"
        
        # Obtenir llistat
        res_list = await ac.get("/api/v1/gestio/notificacions/converses", headers=headers)
        assert res_list.status_code == 200
        assert len(res_list.json()) == 1
