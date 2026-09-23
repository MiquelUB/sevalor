import uuid

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.models.models import Client, Empresa


@pytest_asyncio.fixture
async def setup_isp_xml(admin_session, boss_token):
    token, empresa_id = boss_token

    boss_nif = "B" + str(uuid.uuid4())[:8].upper()
    admin_session.add(Empresa(id=uuid.UUID(empresa_id), nom='Test XML', nif=boss_nif, subdomini='xml-' + str(uuid.uuid4())[:5], pla_subscripcio='STARTER', estat_pagament='ACTIU'))
    await admin_session.flush()

    cli_id = uuid.uuid4()
    admin_session.add(Client(id=cli_id, empresa_id=uuid.UUID(empresa_id), codi='CLI-XML', rao_social='Client ISP', nif='B11111111'))
    await admin_session.commit()

    return {
        "empresa_id": empresa_id,
        "token": token,
        "client_id": str(cli_id)
    }

@pytest.mark.asyncio
async def test_generacio_xml_aeat_isp(setup_isp_xml):
    data = setup_isp_xml
    headers = {"Authorization": f"Bearer {data['token']}", "X-Empresa-ID": data["empresa_id"]}

    # 1. Crear Factura ISP (Quota IVA = 0.0)
    payload = {
        "numero_factura": 99,
        "serie": "2026",
        "client_id": data["client_id"],
        "base_imposable": 1500.00,
        "quota_iva": 0.00,  # Inversión Sujeto Pasivo
        "import_retencio": 0.00,
        "import_suplits": 0.00
    }

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        res1 = await ac.post("/api/v1/gestio/comptabilitat/factures", json=payload, headers=headers)
        assert res1.status_code == 201
        factura_id = res1.json()["id"]
        hash_sha256 = res1.json()["hash_sha256"]

        # 2. Descarregar XML
        res_xml = await ac.get(f"/api/v1/gestio/comptabilitat/factures/{factura_id}/xml", headers=headers)
        assert res_xml.status_code == 200
        assert "application/xml" in res_xml.headers["content-type"]

        xml_content = res_xml.text

        # 3. Validar contingut estructural i fiscal del XML
        assert "<RegistroAlta>" in xml_content
        assert hash_sha256 in xml_content
        assert "<CausaExencion>I</CausaExencion>" in xml_content or "<CausaExencion>ISP</CausaExencion>" in xml_content
        assert "1500.00" in xml_content
