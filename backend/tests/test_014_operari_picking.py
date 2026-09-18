from app.models.models import Empresa, Usuari, Client
import pytest_asyncio
import pytest
import uuid
from httpx import AsyncClient, ASGITransport
from sqlalchemy import text
from app.main import app

@pytest_asyncio.fixture
async def setup_picking_test(admin_session):
    empresa_id = str(uuid.uuid4())
    operari_id = str(uuid.uuid4())
    nif_rand = "NIF-" + str(uuid.uuid4())[:5]
    
    # Empresa i Operari
    admin_session.add(Empresa(
        id=uuid.UUID(empresa_id), nom='Test Picking', nif=nif_rand, subdomini='pickpwa-' + str(uuid.uuid4())[:8], pla_subscripcio='STARTER', estat_pagament='ACTIU'
    ))
    admin_session.add(Usuari(
        id=uuid.UUID(operari_id), empresa_id=uuid.UUID(empresa_id), nif=nif_rand + 'P', nom='Pere Picking', rol='OPERARI', pin_hash='hash', pin_bloquejat=False, intents_pin_fallits=0
    ))
    
    # Client i Ordre
    client_id = str(uuid.uuid4())
    admin_session.add(Client(
        id=uuid.UUID(client_id), empresa_id=uuid.UUID(empresa_id), codi='CLI-1', rao_social='C', nif='NIFC'
    ))
    ordre_id = str(uuid.uuid4())
    await admin_session.execute(
        text("INSERT INTO ordres_treball (id, empresa_id, codi, client_id, titol, estat, adreca) VALUES (:id, :emp, 'OT-1', :cli, 'OT picking', 'PENDENT', 'Adreça de prova')"),
        {"id": ordre_id, "emp": empresa_id, "cli": client_id}
    )
    
    # Article
    article_id = str(uuid.uuid4())
    await admin_session.execute(
        text("INSERT INTO articles (id, empresa_id, referencia_inventari, nom) VALUES (:id, :emp, 'REF-1', 'Article Picking')"),
        {"id": article_id, "emp": empresa_id}
    )
    await admin_session.flush()
    
    return {"empresa_id": empresa_id, "operari_id": operari_id, "ordre_id": ordre_id, "article_id": article_id}

@pytest.mark.asyncio
async def test_crear_picking(setup_picking_test):
    data = setup_picking_test
    import jwt
    from datetime import datetime, timedelta, timezone
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
        # Alta Fulla de Picking
        res_fulla = await ac.post("/api/v1/operari/picking", json={"ordre_treball_id": data["ordre_id"]}, headers=headers)
        assert res_fulla.status_code == 201
        picking_id = res_fulla.json()["id"]
        
        # Inserir línia
        linia_payload = {
            "picking_id": picking_id,
            "article_id": data["article_id"],
            "quantitat_prevista": 2.5
        }
        res_linia = await ac.post(f"/api/v1/operari/picking/{picking_id}/linies", json=linia_payload, headers=headers)
        assert res_linia.status_code == 201
        assert res_linia.json()["quantitat_prevista"] == 2.5
