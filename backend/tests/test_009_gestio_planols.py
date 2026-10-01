import uuid
import pytest
from httpx import ASGITransport, AsyncClient
from app.main import app
from app.models.models import Empresa, Finca, Client, OrdreTreball

@pytest.mark.asyncio
async def test_crear_y_listar_anotacions(admin_session, headers, boss_token):
    token, empresa_id = boss_token
    boss_nif = "C" + str(uuid.uuid4())[:8].upper()

    # 1. Crear empresa
    empresa = Empresa(
        id=uuid.UUID(empresa_id), nom='Test Anotacions', nif=boss_nif, subdomini='testanot-' + str(uuid.uuid4())[:5], pla_subscripcio='STARTER', estat_pagament='ACTIU'
    )
    admin_session.add(empresa)
    await admin_session.flush()

    # 2. Crear Finca i OrdreTreball
    client_nou = Client(empresa_id=uuid.UUID(empresa_id), rao_social="Client Planols", codi="C1", nif="P123" + str(uuid.uuid4())[:4])
    admin_session.add(client_nou)
    await admin_session.flush()
    
    finca_nova = Finca(empresa_id=uuid.UUID(empresa_id), client_id=client_nou.id, nom="Finca Planols")
    admin_session.add(finca_nova)
    await admin_session.flush()
    
    ot_nova = OrdreTreball(empresa_id=uuid.UUID(empresa_id), finca_id=finca_nova.id, titol="OT Planols", codi="OT-001")
    admin_session.add(ot_nova)
    await admin_session.flush()
    
    await admin_session.commit()
    await admin_session.refresh(ot_nova)

    payload = {
        "ordre_treball_id": str(ot_nova.id),
        "nom_capa": "Pins electricitat",
        "fitxer_vectorial_path": "/docs/pins_1.geojson",
        "estat_capa": "ACTIVA"
    }

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.post("/api/v1/gestio/planols/anotacions", json=payload, headers=headers)
        assert resp.status_code == 201, f"Expected 201, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert data["nom_capa"] == "Pins electricitat"
        
        # 2. List annotations
        resp_list = await ac.get("/api/v1/gestio/planols/anotacions", headers=headers)
        assert resp_list.status_code == 200
        data_list = resp_list.json()
        assert len(data_list) >= 1
