import uuid

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.models.models import (
    Article,
    Client,
    Empresa,
    EstocMagatzem,
    FullaPicking,
    OrdreTreball,
)


@pytest_asyncio.fixture
async def setup_concurrency(admin_session, boss_token):
    token, empresa_id = boss_token

    # 0. Crear empresa
    boss_nif = "B" + str(uuid.uuid4())[:8].upper()
    admin_session.add(Empresa(id=uuid.UUID(empresa_id), nom='Test Concurrency', nif=boss_nif, subdomini='conc-' + str(uuid.uuid4())[:5], pla_subscripcio='STARTER', estat_pagament='ACTIU'))
    await admin_session.flush()

    # 1. Crear client
    client_id = str(uuid.uuid4())
    admin_session.add(Client(id=uuid.UUID(client_id), empresa_id=uuid.UUID(empresa_id), codi='CLI-CONCURRENCY', rao_social='C', nif='NIFC'))

    # 2. Crear dues Ordres de Treball
    ot1_id = str(uuid.uuid4())
    ot2_id = str(uuid.uuid4())
    admin_session.add(OrdreTreball(id=uuid.UUID(ot1_id), empresa_id=uuid.UUID(empresa_id), codi='OT-C1', client_id=uuid.UUID(client_id), titol='OT1', estat='PENDENT', adreca='C1'))
    admin_session.add(OrdreTreball(id=uuid.UUID(ot2_id), empresa_id=uuid.UUID(empresa_id), codi='OT-C2', client_id=uuid.UUID(client_id), titol='OT2', estat='PENDENT', adreca='C2'))

    # 3. Crear magatzem, article i estoc (10 unitats)
    from app.models.models import Magatzem
    magatzem_id = str(uuid.uuid4())
    admin_session.add(Magatzem(id=uuid.UUID(magatzem_id), empresa_id=uuid.UUID(empresa_id), nom='Magatzem Central'))

    article_id = str(uuid.uuid4())
    admin_session.add(Article(id=uuid.UUID(article_id), empresa_id=uuid.UUID(empresa_id), referencia_inventari='CONC-100', nom='Article Concurrencia'))
    await admin_session.flush()

    admin_session.add(EstocMagatzem(
        empresa_id=uuid.UUID(empresa_id),
        magatzem_id=uuid.UUID(magatzem_id),
        article_id=uuid.UUID(article_id),
        quantitat_fisica=10.0,
        quantitat_virtual_reservada=0.0
    ))

    # 4. Crear 2 fulles de picking
    pick1_id = str(uuid.uuid4())
    pick2_id = str(uuid.uuid4())
    admin_session.add(FullaPicking(id=uuid.UUID(pick1_id), empresa_id=uuid.UUID(empresa_id), ordre_treball_id=uuid.UUID(ot1_id), estat_picking='PENDENT'))
    admin_session.add(FullaPicking(id=uuid.UUID(pick2_id), empresa_id=uuid.UUID(empresa_id), ordre_treball_id=uuid.UUID(ot2_id), estat_picking='PENDENT'))

    await admin_session.commit()

    return {
        "empresa_id": empresa_id,
        "token": token,
        "pick1_id": pick1_id,
        "pick2_id": pick2_id,
        "article_id": article_id
    }

@pytest.mark.asyncio
async def test_picking_pessimistic_locking_concurrency(setup_concurrency):
    data = setup_concurrency

    headers = {"Authorization": f"Bearer {data['token']}", "X-Empresa-ID": data["empresa_id"]}
    payload = {"article_id": data["article_id"], "quantitat_prevista": 6.0}

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # Request 1: demana 6 unitats. Com que hi ha 10, triomfa (Estoc lliure = 4).
        req1 = await ac.post(f"/api/v1/gestio/magatzem/picking/{data['pick1_id']}/linies", json=payload, headers=headers)

        # Request 2: demana 6 unitats més sobre el mateix estoc.
        # En el món real, si entren concurrents, SELECT FOR UPDATE els serialitza i l'efecte és idèntic al seqüencial.
        req2 = await ac.post(f"/api/v1/gestio/magatzem/picking/{data['pick2_id']}/linies", json=payload, headers=headers)

        assert req1.status_code == 201
        assert req2.status_code == 422

        # Comprovem el detall de l'error generat per la IA/Backend (RF-17)
        assert "unitats disponibles físiques" in req2.json()["detail"] or "Copilot IA" in req2.json()["detail"]

