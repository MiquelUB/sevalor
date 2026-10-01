import uuid
import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.models.models import Empresa, Client, Pressupost

@pytest.mark.asyncio
async def test_triple_button_and_copilot(admin_session, headers, boss_token):
    _, empresa_id = boss_token

    # 1. Creem l'empresa
    boss_nif = "B" + str(uuid.uuid4())[:8].upper()
    admin_session.add(Empresa(
        id=uuid.UUID(empresa_id), nom='Test Pressupostos', nif=boss_nif, subdomini='testpres-' + str(uuid.uuid4())[:5], pla_subscripcio='STARTER', estat_pagament='ACTIU'
    ))
    await admin_session.flush()

    # 2. Creem un client
    client_id = uuid.uuid4()
    admin_session.add(Client(
        id=client_id, empresa_id=uuid.UUID(empresa_id), codi="CLI-PRES", rao_social="Client Pressupost", nif="B00000000", telefon="123", email="a@a.com", adreca_fiscal="A"
    ))
    await admin_session.flush()

    # 3. Creem un pressupost via API
    payload = {
        "client_id": str(client_id),
        "numero": "PRES-2026-001",
        "total": 500.0
    }
    
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as httpx_client:
        # Create
        res = await httpx_client.post("/api/v1/gestio/pressupostos", json=payload, headers=headers)
        assert res.status_code == 201, res.text
        data = res.json()
        pressupost_id = data["id"]
        assert data["estat"] == "PENDENT"
        
        # Approve
        res_aprov = await httpx_client.post(f"/api/v1/gestio/pressupostos/{pressupost_id}/aprovar", headers=headers)
        assert res_aprov.status_code == 200, res_aprov.text
        assert res_aprov.json()["estat"] == "APROVAT"
        
        # Create another and Reject
        payload2 = payload.copy()
        payload2["numero"] = "PRES-2026-002"
        res2 = await httpx_client.post("/api/v1/gestio/pressupostos", json=payload2, headers=headers)
        pressupost_id2 = res2.json()["id"]
        
        res_reb = await httpx_client.post(f"/api/v1/gestio/pressupostos/{pressupost_id2}/rebutjar", headers=headers)
        assert res_reb.status_code == 200, res_reb.text
        assert res_reb.json()["estat"] == "REBUTJAT"
        
        # Test IA
        res_ia = await httpx_client.post("/api/v1/gestio/pressupostos/generar-ia?prompt=Reformar%20cuina", headers=headers)
        assert res_ia.status_code == 200, res_ia.text
        data_ia = res_ia.json()
        assert data_ia["status"] == "PENDENT_AUDITORIA"
        assert "draft" in data_ia
