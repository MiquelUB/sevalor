from app.models.models import Empresa, Usuari, Client
import pytest_asyncio
import pytest
import uuid
import bcrypt
from httpx import AsyncClient, ASGITransport
from sqlalchemy import text
from app.main import app
from app.core.config import settings

def hash_pin(pin: str) -> str:
    return bcrypt.hashpw(pin.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

@pytest_asyncio.fixture
async def setup_operari_test(admin_session):
    empresa_id = str(uuid.uuid4())
    operari_id = str(uuid.uuid4())
    nif = "OP" + str(uuid.uuid4())[:8]
    pin_real = "1234"
    pin_hash = hash_pin(pin_real)
    
    # 1. Crear empresa
    admin_session.add(Empresa(
        id=uuid.UUID(empresa_id), nom='Test PWA', nif='EMP' + str(uuid.uuid4())[:5], subdomini='testpwa-' + str(uuid.uuid4())[:5], pla_subscripcio='STARTER', estat_pagament='ACTIU'
    ))
    
    # 2. Crear operari actiu
    admin_session.add(Usuari(
        id=uuid.UUID(operari_id), empresa_id=uuid.UUID(empresa_id), nif=nif, nom='Pere', rol='OPERARI', pin_hash=pin_hash, pin_bloquejat=False, intents_pin_fallits=0
    ))
    await admin_session.flush()
    
    return {"empresa_id": empresa_id, "operari_id": operari_id, "nif": nif, "pin": pin_real}

@pytest.mark.asyncio
async def test_login_operari_valid(setup_operari_test):
    data = setup_operari_test
    
    # Simulem que el middleware del tenant injecta la capçalera X-Empresa-ID
    headers = {"X-Empresa-ID": data["empresa_id"]}
    payload = {"nif": data["nif"], "pin": data["pin"]}
    
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        res = await ac.post("/api/v1/operari_auth/login", json=payload, headers=headers)
        assert res.status_code == 200, res.text
        resp_data = res.json()
        
        assert "access_token" in resp_data
        assert resp_data["token_type"] == "bearer"
        assert resp_data["usuari"]["id"] == data["operari_id"]

@pytest.mark.asyncio
async def test_login_operari_pin_incorrecte_i_bloqueig(setup_operari_test):
    data = setup_operari_test
    headers = {"X-Empresa-ID": data["empresa_id"]}
    payload = {"nif": data["nif"], "pin": "0000"} # PIN Fals
    
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # Intent 1
        res1 = await ac.post("/api/v1/operari_auth/login", json=payload, headers=headers)
        assert res1.status_code == 401
        
        # Intent 2
        res2 = await ac.post("/api/v1/operari_auth/login", json=payload, headers=headers)
        assert res2.status_code == 401
        
        # Intent 3
        res3 = await ac.post("/api/v1/operari_auth/login", json=payload, headers=headers)
        assert res3.status_code == 401
        
        # Intent 4 -> El compte es bloqueja!
        res4 = await ac.post("/api/v1/operari_auth/login", json=payload, headers=headers)
        assert res4.status_code == 403
        assert "compte ha estat bloquejat" in res4.json()["detail"]
        
        # Intent 5 (Fins i tot si ara encerta el PIN, està bloquejat)
        payload_correcte = {"nif": data["nif"], "pin": data["pin"]}
        res5 = await ac.post("/api/v1/operari_auth/login", json=payload_correcte, headers=headers)
        assert res5.status_code == 403

@pytest.mark.asyncio
async def test_login_operari_usuari_inexistent(setup_operari_test):
    data = setup_operari_test
    headers = {"X-Empresa-ID": data["empresa_id"]}
    payload = {"nif": "NIF_QUE_NO_EXISTEIX", "pin": "1234"}
    
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        res = await ac.post("/api/v1/operari_auth/login", json=payload, headers=headers)
        assert res.status_code == 401
        assert res.json()["detail"] == "Credencials invàlides" # Missatge genèric RF-23

@pytest.mark.asyncio
async def test_login_tenant_isolation(setup_operari_test, admin_session):
    data = setup_operari_test
    
    # Creem UNA ALTRA empresa diferent
    altre_empresa_id = str(uuid.uuid4())
    admin_session.add(Empresa(
        id=uuid.UUID(altre_empresa_id), nom='Test RLS', nif='EMP' + str(uuid.uuid4())[:5], subdomini='testrls-' + str(uuid.uuid4())[:5], pla_subscripcio='STARTER', estat_pagament='ACTIU'
    ))
    await admin_session.flush()
    
    # Intentem loguejar l'operari de la primera empresa a la segona empresa
    headers = {"X-Empresa-ID": altre_empresa_id}
    payload = {"nif": data["nif"], "pin": data["pin"]}
    
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        res = await ac.post("/api/v1/operari_auth/login", json=payload, headers=headers)
        # Ha de donar 401 genèric perquè el NIF no existeix dins d'aquell tenant!
        assert res.status_code == 401
        assert res.json()["detail"] == "Credencials invàlides"
