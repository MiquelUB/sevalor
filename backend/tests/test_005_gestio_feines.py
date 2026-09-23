import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.models.models import Client, Empresa, Usuari


@pytest.mark.asyncio
async def test_alta_ordre_treball(admin_session, headers, boss_token):
    token, empresa_id = boss_token
    boss_nif = "B" + str(uuid.uuid4())[:8].upper()

    # 1. Crear empresa
    admin_session.add(Empresa(
        id=uuid.UUID(empresa_id), nom='Test Feines', nif=boss_nif, subdomini='testfeina-' + str(uuid.uuid4())[:5], pla_subscripcio='STARTER', estat_pagament='ACTIU'
    ))
    await admin_session.flush()

    # 2. Crear client per tenir client_id
    client_id = str(uuid.uuid4())
    admin_session.add(Client(
        id=uuid.UUID(client_id), empresa_id=uuid.UUID(empresa_id), codi='CLI-1', rao_social='Client FEINA', nif='12345678A'
    ))
    await admin_session.flush()

    # 3. Crear operari per tenir cap_de_colla_id
    operari_id = str(uuid.uuid4())
    admin_session.add(Usuari(
        id=uuid.UUID(operari_id), empresa_id=uuid.UUID(empresa_id), nif='OP-999', nom='Paco', cognoms='Garcia', rol='OPERARI', estat='ACTIU'
    ))
    await admin_session.flush()
    await admin_session.flush()

    payload = {
        "codi": "OT-001",
        "client_id": client_id,
        "titol": "Revisió Instal·lació",
        "adreca": "Carrer de la Indústria 42, BCN",
        "descripcio": "Revisió general",
        "estat": "PENDENT",
        "data_planificacio": "2027-01-01",
        "cap_de_colla_id": operari_id
    }

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        res = await ac.post("/api/v1/gestio/feines", json=payload, headers=headers)
        assert res.status_code == 201, f"Expected 201, got {res.status_code}: {res.text}"
        data = res.json()
        assert data["codi"] == "OT-001"
        assert data["titol"] == "Revisió Instal·lació"

        # Llistat (RF-01)
        res_list = await ac.get("/api/v1/gestio/feines", headers=headers)
        assert res_list.status_code == 200
        llista = res_list.json()
        assert len(llista) == 1
        assert llista[0]["codi"] == "OT-001"

        # Duplicat codi
        res_dup = await ac.post("/api/v1/gestio/feines", json=payload, headers=headers)
        assert res_dup.status_code == 400
        assert "registrat" in res_dup.json()["detail"]
