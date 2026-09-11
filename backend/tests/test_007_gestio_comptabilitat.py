import pytest_asyncio
import pytest
import uuid
import hashlib
from httpx import AsyncClient, ASGITransport
from sqlalchemy import text
from app.main import app

@pytest_asyncio.fixture
async def setup_comptabilitat_test(admin_session):
    empresa_id = str(uuid.uuid4())
    client_id = str(uuid.uuid4())
    nif_rand = "NIF-" + str(uuid.uuid4())[:5]
    sub_rand = "comp-" + str(uuid.uuid4())[:5]
    
    await admin_session.execute(
        text("INSERT INTO empreses (id, nom, nif, subdomini, pla_subscripcio, estat_pagament) VALUES (:id, 'Test Comp', :nif, :sub, 'STARTER', 'ACTIU')"),
        {"id": empresa_id, "nif": nif_rand, "sub": sub_rand}
    )
    await admin_session.execute(
        text("INSERT INTO clients (id, empresa_id, codi, rao_social, nif) VALUES (:id, :emp, 'CLI-1', 'C', 'NIFC')"),
        {"id": client_id, "emp": empresa_id}
    )
    await admin_session.commit()
    
    return {"empresa_id": empresa_id, "client_id": client_id}

@pytest.mark.asyncio
async def test_alta_factura_verifactu(setup_comptabilitat_test, headers):
    data = setup_comptabilitat_test
    import jwt
    from datetime import datetime, timedelta, timezone
    from app.core.config import settings
    
    # Boss token
    payload = {
        "sub": str(uuid.uuid4()),
        "rol": "BOSS",
        "empresa_id": data["empresa_id"],
        "exp": datetime.now(timezone.utc) + timedelta(minutes=60)
    }
    token = jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    headers = {"Authorization": f"Bearer {token}"}
    
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        fac_payload = {
            "numero_factura": 1,
            "serie": "2026",
            "client_id": data["client_id"],
            "base_imposable": 100.00,
            "quota_iva": 21.00,
            "liquid_exigible": 121.00
        }
        res_fac = await ac.post("/api/v1/gestio/comptabilitat/factures", json=fac_payload, headers=headers)
        assert res_fac.status_code == 201
        factura = res_fac.json()
        assert factura["numero_factura"] == 1
        assert factura["hash_sha256"] is not None
        assert len(factura["hash_sha256"]) == 64  # Hash SHA-256 for VeriFactu
        
        # Test duplicat de sèrie i número
        res_dup = await ac.post("/api/v1/gestio/comptabilitat/factures", json=fac_payload, headers=headers)
        assert res_dup.status_code == 400
