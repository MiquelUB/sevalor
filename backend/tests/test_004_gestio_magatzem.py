import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.models.models import Empresa


@pytest.mark.asyncio
async def test_alta_article_valid(admin_session, headers, boss_token):
    token, empresa_id = boss_token
    boss_nif = "B" + str(uuid.uuid4())[:8].upper()

    admin_session.add(Empresa(
        id=uuid.UUID(empresa_id), nom='Test Magatzem', nif=boss_nif, subdomini='testmag-' + str(uuid.uuid4())[:5], pla_subscripcio='STARTER', estat_pagament='ACTIU'
    ))
    await admin_session.flush()
    await admin_session.flush()

    payload = {
        "referencia_inventari": "REF-ART-001",
        "nom": "Tornavís d'Estrella Test",
        "unitat_mesura": "UNITAT",
        "familia": "EINES",
        "estoc_optim": 10.0,
        "estoc_minim": 2.0,
        "es_lot_caducable": False,
        "preu_cost": 5.50,
        "preu_venda": 15.00
    }

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        res = await ac.post("/api/v1/gestio/magatzem/articles", json=payload, headers=headers)
        assert res.status_code == 201, f"Expected 201, got {res.status_code}: {res.text}"
        data = res.json()
        assert data["referencia_inventari"] == "REF-ART-001"
        assert data["nom"] == "Tornavís d'Estrella Test"

        # Llistat (RF-01)
        res_list = await ac.get("/api/v1/gestio/magatzem/articles", headers=headers)
        assert res_list.status_code == 200
        llista = res_list.json()
        assert len(llista) == 1
        assert llista[0]["referencia_inventari"] == "REF-ART-001"

        # Duplicat (per respectar constraints de BD)
        res_dup = await ac.post("/api/v1/gestio/magatzem/articles", json=payload, headers=headers)
        assert res_dup.status_code == 400
        assert "registrada" in res_dup.json()["detail"]
