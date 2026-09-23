import uuid
from datetime import date

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.models.models import (
    Article,
    Client,
    Empresa,
    EstocMagatzem,
    FacturaProveidor,
    FacturaProveidorLinia,
    Magatzem,
    OrdreTreball,
    Proveidor,
)


@pytest_asyncio.fixture
async def setup_backorder(admin_session, boss_token):
    token, empresa_id = boss_token

    boss_nif = "B" + str(uuid.uuid4())[:8].upper()
    admin_session.add(Empresa(id=uuid.UUID(empresa_id), nom='Test Backorder', nif=boss_nif, subdomini='back-' + str(uuid.uuid4())[:5], pla_subscripcio='STARTER', estat_pagament='ACTIU'))
    await admin_session.flush()

    # Client & OT
    client_id = str(uuid.uuid4())
    admin_session.add(Client(id=uuid.UUID(client_id), empresa_id=uuid.UUID(empresa_id), codi='CLI-BACK', rao_social='C', nif='NIFC'))
    ot_id = str(uuid.uuid4())
    admin_session.add(OrdreTreball(id=uuid.UUID(ot_id), empresa_id=uuid.UUID(empresa_id), codi='OT-B', client_id=uuid.UUID(client_id), titol='OT1', estat='PENDENT', adreca='C1'))

    magatzem_id = str(uuid.uuid4())
    admin_session.add(Magatzem(id=uuid.UUID(magatzem_id), empresa_id=uuid.UUID(empresa_id), nom='Magatzem B'))

    # Article (Stock = 0, Estoc minim = 5)
    article_id = str(uuid.uuid4())
    admin_session.add(Article(id=uuid.UUID(article_id), empresa_id=uuid.UUID(empresa_id), referencia_inventari='BACK-100', nom='Tub Coure', estoc_minim=5.0, estoc_optim=50.0))
    await admin_session.flush()

    admin_session.add(EstocMagatzem(
        empresa_id=uuid.UUID(empresa_id),
        magatzem_id=uuid.UUID(magatzem_id),
        article_id=uuid.UUID(article_id),
        quantitat_fisica=2.0,
        quantitat_virtual_reservada=0.0
    ))

    # Proveidor & Factura Pendent (Backorder)
    prov_id = str(uuid.uuid4())
    admin_session.add(Proveidor(id=uuid.UUID(prov_id), empresa_id=uuid.UUID(empresa_id), codi='PROV-1', nif='P123', rao_social='Prov Test'))
    await admin_session.flush()

    fact_id = str(uuid.uuid4())
    admin_session.add(FacturaProveidor(
        id=uuid.UUID(fact_id),
        empresa_id=uuid.UUID(empresa_id),
        proveidor_id=uuid.UUID(prov_id),
        numero_factura='F-BACK-01',
        data_factura=date.today(),
        estat='PENDENT'
    ))
    await admin_session.flush()

    admin_session.add(FacturaProveidorLinia(
        empresa_id=uuid.UUID(empresa_id),
        factura_id=uuid.UUID(fact_id),
        article_id=uuid.UUID(article_id),
        quantitat=100.0,
        preu_unitari=2.5
    ))

    await admin_session.commit()

    return {
        "empresa_id": empresa_id,
        "token": token,
        "ot_id": ot_id,
        "article_id": article_id
    }

@pytest.mark.asyncio
async def test_backorder_ai_detection(setup_backorder):
    data = setup_backorder
    headers = {"Authorization": f"Bearer {data['token']}", "X-Empresa-ID": data["empresa_id"]}

    payload = {
        "ordre_treball_id": data["ot_id"],
        "materials": [{"article_id": data["article_id"], "quantitat_necessaria": 2.0}]
    }

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        res = await ac.post("/api/v1/gestio/copilot/stock/verificacio-assignacio", json=payload, headers=headers)

        # Copilot detects the Backorder and returns 422 HTTP avoiding the duplication!
        assert res.status_code == 422

        detail = res.json()["detail"]
        assert "❌ Copilot IA:" in detail
        assert "Comanda en trànsit detectada" in detail
        assert "Backorder actiu per l'article 'Tub Coure'" in detail
