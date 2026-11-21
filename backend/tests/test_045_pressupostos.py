import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.models.models import Client, Empresa
from app.services.sovereign_storage import SovereignStorageGateway, inicialitzar_arbre_carpetes_disc


@pytest.mark.asyncio
async def test_triple_button_and_copilot(admin_session, headers, boss_token, tmp_path):
    _, empresa_id = boss_token
    emp_uuid = uuid.UUID(empresa_id)

    # 1. Creem l'empresa inicialment sense node IA actiu (fail-closed)
    boss_nif = "B" + str(uuid.uuid4())[:8].upper()
    vault_token = f"svlt_pres_{uuid.uuid4().hex[:12]}"
    emp = Empresa(
        id=emp_uuid,
        nom="Test Pressupostos",
        nif=boss_nif,
        subdomini="testpres-" + str(uuid.uuid4())[:5],
        pla_subscripcio="STARTER",
        estat_pagament="ACTIU",
        disc_dur_url=f"wss-tunnel://{emp_uuid}",
        node_ia_url=f"wss-tunnel://{emp_uuid}",
        vault_token=vault_token,
        feature_copilot_ia=False,
        node_ia_actiu=False,
    )
    admin_session.add(emp)
    await admin_session.flush()

    # 2. Creem un client
    client_id = uuid.uuid4()
    admin_session.add(
        Client(
            id=client_id,
            empresa_id=emp_uuid,
            codi="CLI-PRES",
            rao_social="Client Pressupost",
            nif="B00000000",
            telefon="123",
            email="a@a.com",
            adreca_fiscal="A",
        )
    )
    await admin_session.commit()

    # 3. Creem un pressupost via API
    payload = {
        "client_id": str(client_id),
        "numero": "PRES-2026-001",
        "total": 500.0,
    }

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as httpx_client:
        # Create
        res = await httpx_client.post("/api/v1/gestio/pressupostos", json=payload, headers=headers)
        assert res.status_code == 201, res.text
        data = res.json()
        pressupost_id = data["id"]
        assert data["estat"] == "PENDENT"

        # Approve
        res_aprov = await httpx_client.post(
            f"/api/v1/gestio/pressupostos/{pressupost_id}/aprovar", headers=headers
        )
        assert res_aprov.status_code == 200, res_aprov.text
        assert res_aprov.json()["estat"] == "APROVAT"

        # Create another and Reject
        payload2 = payload.copy()
        payload2["numero"] = "PRES-2026-002"
        res2 = await httpx_client.post("/api/v1/gestio/pressupostos", json=payload2, headers=headers)
        pressupost_id2 = res2.json()["id"]

        res_reb = await httpx_client.post(
            f"/api/v1/gestio/pressupostos/{pressupost_id2}/rebutjar", headers=headers
        )
        assert res_reb.status_code == 200, res_reb.text
        assert res_reb.json()["estat"] == "REBUTJAT"

        # Test IA sense node actiu -> 503 (zero fallback/mock 100 EUR)
        res_ia_off = await httpx_client.post(
            "/api/v1/gestio/pressupostos/generar-ia?prompt=Instal%C2%B7laci%C3%B3%20caldera%20cuina",
            headers=headers,
        )
        assert res_ia_off.status_code == 503, res_ia_off.text

        # Activem disc sobirà + catàleg real + node_ia_actiu + configuració estricta Copilot
        disc_root = tmp_path / "disc_pres"
        inicialitzar_arbre_carpetes_disc(disc_root)
        emp.feature_copilot_ia = True
        emp.node_ia_actiu = True
        await admin_session.commit()

        from app.services.copilot_config_service import save_strict_copilot_config

        await save_strict_copilot_config(
            db=admin_session,
            empresa_id=emp_uuid,
            system_prompt="Ets el Copilot tècnic de pressupostos de Test Pressupostos.",
            rag_prompt="",
            subagent_prompts={},
        )

        # Connectem Túnel Invers Sobirà WSS real (Zero Mock / ADR-001)
        from tests.wss_test_helpers import live_empresa_wss_context

        async with live_empresa_wss_context(emp_uuid, vault_token, disc_root):
            await SovereignStorageGateway.desar_entitat_json(
                db=admin_session,
                empresa_id=emp_uuid,
                categoria="magatzem_articles",
                item_id="art-cuina-1",
                dades={
                    "nom": "Caldera Condensació Cuina",
                    "referencia_inventari": "CALD-200",
                    "preu_venda": 780.0,
                },
            )

            res_ia_on = await httpx_client.post(
                "/api/v1/gestio/pressupostos/generar-ia?prompt=Instal%C2%B7lar%20caldera%20cuina",
                headers=headers,
            )
            assert res_ia_on.status_code == 200, res_ia_on.text
            data_ia = res_ia_on.json()
            assert data_ia["status"] == "PENDENT_AUDITORIA"
            assert "draft" in data_ia
            assert data_ia["draft"]["total_estimat"] == 780.0
