import pytest_asyncio
import pytest
import uuid
from httpx import AsyncClient, ASGITransport
from sqlalchemy import text
from app.main import app

@pytest_asyncio.fixture
async def setup_jornada_test(admin_session):
    empresa_id = str(uuid.uuid4())
    operari_id = str(uuid.uuid4())
    nif_rand = "NIF-" + str(uuid.uuid4())[:5]
    sub_rand = "pwa-" + str(uuid.uuid4())[:5]
    
    # 1. Empresa
    await admin_session.execute(
        text("INSERT INTO empreses (id, nom, nif, subdomini, pla_subscripcio, estat_pagament) VALUES (:id, 'Test PWA', :nif, :sub, 'STARTER', 'ACTIU')"),
        {"id": empresa_id, "nif": nif_rand, "sub": sub_rand}
    )
    
    # 2. Operari
    await admin_session.execute(
        text("""INSERT INTO usuaris (id, empresa_id, nif, nom, rol, pin_hash, pin_bloquejat, intents_pin_fallits) 
                VALUES (:id, :emp, :nif, 'Pere PWA', 'OPERARI', 'hash', false, 0)"""),
        {"id": operari_id, "emp": empresa_id, "nif": nif_rand + "A"}
    )
    await admin_session.commit()
    
    return {"empresa_id": empresa_id, "operari_id": operari_id}

@pytest.mark.asyncio
async def test_fitxatge_jornada(setup_jornada_test):
    data = setup_jornada_test
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
        res_inici = await ac.post("/api/v1/operari/jornada/inici", json={"geolocalitzacio": "41.3851,2.1734"}, headers=headers)
        assert res_inici.status_code == 201
        jornada = res_inici.json()
        assert jornada["estat"] == "EN_CURS"
        
        res_activa = await ac.get("/api/v1/operari/jornada/activa", headers=headers)
        assert res_activa.status_code == 200
        assert res_activa.json()["id"] == jornada["id"]
        
        res_fi = await ac.post(f"/api/v1/operari/jornada/{jornada['id']}/fi", json={"geolocalitzacio": "41.3851,2.1734"}, headers=headers)
        assert res_fi.status_code == 200
        assert res_fi.json()["estat"] == "COMPLERT"
