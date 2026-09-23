import uuid

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.models.models import Client, Empresa


@pytest_asyncio.fixture
async def setup_comptabilitat_test(admin_session):
    empresa_id = str(uuid.uuid4())
    client_id = str(uuid.uuid4())
    nif_rand = "NIF-" + str(uuid.uuid4())[:5]
    sub_rand = "comp-" + str(uuid.uuid4())[:5]

    admin_session.add(Empresa(
        id=uuid.UUID(empresa_id), nom='Test Comp', nif=nif_rand, subdomini=sub_rand, pla_subscripcio='STARTER', estat_pagament='ACTIU'
    ))
    await admin_session.flush()
    admin_session.add(Client(
        id=uuid.UUID(client_id), empresa_id=uuid.UUID(empresa_id), codi='CLI-1', rao_social='C', nif='NIFC'
    ))
    await admin_session.flush()
    await admin_session.flush()

    return {"empresa_id": empresa_id, "client_id": client_id}

@pytest.mark.asyncio
async def test_alta_factura_verifactu(setup_comptabilitat_test, headers):
    data = setup_comptabilitat_test
    from datetime import datetime, timedelta, timezone

    import jwt

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
