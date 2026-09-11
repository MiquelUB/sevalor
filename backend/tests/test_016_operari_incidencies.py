import pytest_asyncio
import pytest
import uuid
from httpx import AsyncClient, ASGITransport
from sqlalchemy import text
from app.main import app

@pytest_asyncio.fixture
async def setup_incidencia_test(admin_session):
    empresa_id = str(uuid.uuid4())
    operari_id = str(uuid.uuid4())
    nif_rand = "NIF-" + str(uuid.uuid4())[:5]
    
    # Empresa i Operari
    await admin_session.execute(
        text("INSERT INTO empreses (id, nom, nif, subdomini, pla_subscripcio, estat_pagament) VALUES (:id, 'Test Inc', :nif, :sub, 'STARTER', 'ACTIU')"),
        {"id": empresa_id, "nif": nif_rand, "sub": "incpwa-" + str(uuid.uuid4())[:8]}
    )
    await admin_session.execute(
        text("""INSERT INTO usuaris (id, empresa_id, nif, nom, rol, pin_hash, pin_bloquejat, intents_pin_fallits) 
                VALUES (:id, :emp, :nif_u, 'Pere Incidencia', 'OPERARI', 'hash', false, 0)"""),
        {"id": operari_id, "emp": empresa_id, "nif_u": nif_rand + "P"}
    )
    await admin_session.commit()
    
    return {"empresa_id": empresa_id, "operari_id": operari_id}

@pytest.mark.asyncio
async def test_crear_incidencia(setup_incidencia_test):
    data = setup_incidencia_test
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
