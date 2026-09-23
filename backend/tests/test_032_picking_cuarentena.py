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
    LiniaPicking,
    Magatzem,
    OrdreTreball,
)


@pytest_asyncio.fixture
async def setup_cuarentena(admin_session, boss_token):
    token, empresa_id = boss_token

    # 0. Crear empresa
    boss_nif = "B" + str(uuid.uuid4())[:8].upper()
    admin_session.add(Empresa(id=uuid.UUID(empresa_id), nom='Test Cuarentena', nif=boss_nif, subdomini='cuar-' + str(uuid.uuid4())[:5], pla_subscripcio='STARTER', estat_pagament='ACTIU'))
    await admin_session.flush()

    # 1. Crear client, OT i Magatzem
    client_id = str(uuid.uuid4())
    admin_session.add(Client(id=uuid.UUID(client_id), empresa_id=uuid.UUID(empresa_id), codi='CLI-CUAR', rao_social='C', nif='NIFC'))
    ot_id = str(uuid.uuid4())
    admin_session.add(OrdreTreball(id=uuid.UUID(ot_id), empresa_id=uuid.UUID(empresa_id), codi='OT-C', client_id=uuid.UUID(client_id), titol='OT1', estat='PENDENT', adreca='C1'))

    magatzem_id = str(uuid.uuid4())
    admin_session.add(Magatzem(id=uuid.UUID(magatzem_id), empresa_id=uuid.UUID(empresa_id), nom='Magatzem Cuarentena'))

    # 2. Crear article i estoc
    article_id = str(uuid.uuid4())
    admin_session.add(Article(id=uuid.UUID(article_id), empresa_id=uuid.UUID(empresa_id), referencia_inventari='CUAR-100', nom='Art Cuarentena'))
    await admin_session.flush()

    estoc = EstocMagatzem(
        empresa_id=uuid.UUID(empresa_id),
        magatzem_id=uuid.UUID(magatzem_id),
        article_id=uuid.UUID(article_id),
        quantitat_fisica=10.0,
        quantitat_virtual_reservada=4.0,
        quantitat_cuarentena=0.0
    )
    admin_session.add(estoc)

    # 3. Crear fulla i línia
    pick_id = str(uuid.uuid4())
    admin_session.add(FullaPicking(id=uuid.UUID(pick_id), empresa_id=uuid.UUID(empresa_id), ordre_treball_id=uuid.UUID(ot_id), estat_picking='PENDENT'))

    linia_id = str(uuid.uuid4())
    admin_session.add(LiniaPicking(
        id=uuid.UUID(linia_id),
        empresa_id=uuid.UUID(empresa_id),
        picking_id=uuid.UUID(pick_id),
        article_id=uuid.UUID(article_id),
        quantitat_prevista=4.0,
        quantitat_carregada_pick_in=4.0,
        quantitat_retornada_pick_out=0.0,
        quantitat_mermada=0.0
    ))

    await admin_session.commit()

    return {
        "empresa_id": empresa_id,
        "token": token,
        "linia_id": linia_id,
        "article_id": article_id,
        "magatzem_id": magatzem_id,
        "estoc_id": str(estoc.id)
    }

@pytest.mark.asyncio
async def test_picking_cuarentena_pick_out(setup_cuarentena, admin_session):
    data = setup_cuarentena
    headers = {"Authorization": f"Bearer {data['token']}", "X-Empresa-ID": data["empresa_id"]}

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        res = await ac.put(
            f"/api/v1/gestio/magatzem/picking/linies/{data['linia_id']}/pick-out",
            params={"quantitat_retornada": 2.0, "quantitat_mermada": 2.0},
            headers=headers
        )
        assert res.status_code == 200

        from sqlalchemy import select
        # Use admin_session to query the database, ensuring we stay within the Pytest isolation bubble
        estoc_res = await admin_session.execute(
            select(EstocMagatzem).where(EstocMagatzem.id == uuid.UUID(data["estoc_id"]))
        )
        estoc = estoc_res.scalars().first()

        assert estoc is not None, "L'estoc no hauria de ser None"
        await admin_session.refresh(estoc)

        assert float(estoc.quantitat_fisica) == 8.0
        assert float(estoc.quantitat_cuarentena) == 2.0
        assert float(estoc.quantitat_virtual_reservada) == 0.0
