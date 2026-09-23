import uuid

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.models.models import Client, Empresa


@pytest_asyncio.fixture
async def setup_facturacio(admin_session, boss_token):
    token, empresa_id = boss_token

    boss_nif = "B" + str(uuid.uuid4())[:8].upper()
    admin_session.add(Empresa(id=uuid.UUID(empresa_id), nom='Test Facturacio', nif=boss_nif, subdomini='fact-' + str(uuid.uuid4())[:5], pla_subscripcio='STARTER', estat_pagament='ACTIU'))
    await admin_session.flush()

    cli_id = uuid.uuid4()
    admin_session.add(Client(id=cli_id, empresa_id=uuid.UUID(empresa_id), codi='CLI-1', rao_social='Client Test', nif='B98765432'))
    await admin_session.commit()

    return {
        "empresa_id": empresa_id,
        "token": token,
        "client_id": str(cli_id)
    }

@pytest.mark.asyncio
async def test_factura_hash_cadena(setup_facturacio):
    data = setup_facturacio
    headers = {"Authorization": f"Bearer {data['token']}", "X-Empresa-ID": data["empresa_id"]}

    # 1. Crear Factura 1
    payload_1 = {
        "numero_factura": 1,
        "serie": "2026",
        "client_id": data["client_id"],
        "base_imposable": 100.00,
        "quota_iva": 21.00,
        "import_retencio": 0.00,
        "import_suplits": 0.00
    }

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        res1 = await ac.post("/api/v1/gestio/comptabilitat/factures", json=payload_1, headers=headers)
        assert res1.status_code == 201
        fact1 = res1.json()
        assert "hash_sha256" in fact1
        hash1 = fact1["hash_sha256"]
        assert len(hash1) == 64  # SHA-256

        # 2. Crear Factura 2
        payload_2 = {
            "numero_factura": 2,
            "serie": "2026",
            "client_id": data["client_id"],
            "base_imposable": 200.00,
            "quota_iva": 42.00,
            "import_retencio": 0.00,
            "import_suplits": 0.00
        }

        res2 = await ac.post("/api/v1/gestio/comptabilitat/factures", json=payload_2, headers=headers)
        assert res2.status_code == 201
        fact2 = res2.json()
        assert fact2["hash_anterior"] == hash1
        hash2 = fact2["hash_sha256"]
        assert len(hash2) == 64
