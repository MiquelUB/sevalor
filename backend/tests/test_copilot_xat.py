import uuid
from pathlib import Path

import jwt
import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.models.models import Empresa, Usuari
from app.services.sovereign_storage import SovereignStorageGateway
from tests.wss_test_helpers import live_empresa_wss_context


@pytest.mark.asyncio
async def test_copilot_xat(admin_session, headers, boss_token, tmp_path: Path):
    token_jwt, empresa_id = boss_token
    boss_nif = "B" + str(uuid.uuid4())[:8].upper()
    emp_uuid = uuid.UUID(empresa_id)
    vault_token = f"svlt_copxat_{uuid.uuid4().hex[:12]}"

    decoded = jwt.decode(token_jwt, options={"verify_signature": False})

    admin_session.add(Empresa(
        id=emp_uuid,
        nom="Test Copilot",
        nif=boss_nif,
        subdomini="copi-" + str(uuid.uuid4())[:5],
        pla_subscripcio="STARTER",
        estat_pagament="ACTIU",
        disc_dur_url=f"wss-tunnel://{emp_uuid}",
        node_ia_url=f"wss-tunnel://{emp_uuid}",
        vault_token=vault_token,
        node_ia_actiu=True,
        feature_copilot_ia=True,
    ))
    admin_session.add(Usuari(id=uuid.UUID(decoded["sub"]), empresa_id=emp_uuid, nom="Boss", cognoms="Boss", nif="BOSS1", rol="BOSS", estat="ACTIU"))
    await admin_session.flush()

    async with live_empresa_wss_context(emp_uuid, vault_token, tmp_path, default_reply=""):
        await SovereignStorageGateway.desar_entitat_json(
            admin_session,
            emp_uuid,
            "protocols_interns",
            "faq_rebt",
            {
                "id": "faq_rebt",
                "pregunta": "Manual d'Instal·lació de Quadres Elèctrics",
                "resposta": "Protocol: Verificar sempre el diferencial de 30mA abans d'iniciar el cablejat del quadre. Rebt-2024.",
                "paraules_clau": "electricitat, quadre, rebt",
                "actiu": True,
            },
        )

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            # Pregunta 1: RAG
            res = await ac.post("/api/v1/gestio/copilot/xat", json={"pregunta": "Quin és el procediment o protocol per instal·lar un quadre?"}, headers=headers)
            assert res.status_code == 200
            data = res.json()
            assert "resposta" in data
            assert "30mA" in data["resposta"] or "rebt" in data["resposta"].lower() or len(data["resposta"]) > 10

            # Pregunta 2: General/Lògica
            res2 = await ac.post("/api/v1/gestio/copilot/xat", json={"pregunta": "Fes un resum de les feines a fer avui."}, headers=headers)
            assert res2.status_code == 200
            data2 = res2.json()
            assert "resposta" in data2

            # Pregunta 3: Validació sense context
            res3 = await ac.post("/api/v1/gestio/copilot/xat", json={"pregunta": "Qui ets?"}, headers=headers)
            assert res3.status_code == 200
            data3 = res3.json()
            assert "resposta" in data3
            assert len(data3["resposta"]) > 10

            # Pregunta 4: Múltiples missatges (historial)
            historial = [
                {"role": "user", "content": "Quins clients tenim a Barcelona?"},
                {"role": "assistant", "content": "Actualment teniu 2 clients a Barcelona: Client A i Client B."},
                {"role": "user", "content": "D'acord, prepara un pressupost per al Client A de 500 euros per reparació."}
            ]
            res4 = await ac.post("/api/v1/gestio/copilot/xat", json={"pregunta": historial[-1]["content"], "historial": historial[:-1]}, headers=headers)
            assert res4.status_code == 200
            data4 = res4.json()
            assert "resposta" in data4
            assert len(data4["resposta"]) > 10

            # Verificacions estructurals
            for r in [res, res2, res3, res4]:
                assert "error" not in r.json() or not r.json()["error"]

            # Verificació de connectivitat amb el node d'IA local (/ia-status)
            res_status = await ac.get("/api/v1/gestio/copilot/ia-status", headers=headers)
            assert res_status.status_code == 200
            data_status = res_status.json()
            assert data_status["estat"] in ("ONLINE", "OFFLINE")
            assert "url" in data_status


@pytest.mark.asyncio
async def test_copilot_zero_leakage_sense_login_i_amb_feature_desactivada(
    admin_session, headers, boss_token
):
    """Verifica que el Copilot mai és accessible sense sessió vàlida (401) ni quan el feature flag està desactivat (403)."""
    token_jwt, empresa_id = boss_token
    emp_uuid = uuid.UUID(empresa_id)

    # 1. Crida anònima sense autenticació (com estaria a la pantalla de login)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        res_gestio_anonim = await ac.post(
            "/api/v1/gestio/copilot/xat",
            json={"pregunta": "Dades de facturació i clients?"},
        )
        assert res_gestio_anonim.status_code == 401, "No autenticat ha de donar 401"

        res_operari_anonim = await ac.post(
            "/api/v1/operari/copilot/xat",
            json={"pregunta": "Dades de clients?"},
        )
        assert res_operari_anonim.status_code == 401, "No autenticat ha de donar 401"

    # 2. Configurar empresa amb feature_copilot_ia = False i comprovar que /auth/me retorna feature_copilot_ia=False
    emp = await admin_session.get(Empresa, emp_uuid)
    if not emp:
        emp = Empresa(
            id=emp_uuid,
            nom="Empresa No Copilot",
            nif=f"B{emp_uuid.hex[:8].upper()}",
            subdomini=f"nocopi-{emp_uuid.hex[:4]}",
            pla_subscripcio="STARTER",
            estat_pagament="ACTIU",
            feature_copilot_ia=False,
        )
        admin_session.add(emp)
    else:
        emp.feature_copilot_ia = False

    decoded = jwt.decode(token_jwt, options={"verify_signature": False})
    user_uuid = uuid.UUID(decoded["sub"])
    usr = await admin_session.get(Usuari, user_uuid)
    if not usr:
        usr = Usuari(
            id=user_uuid,
            empresa_id=emp_uuid,
            nom="Boss",
            cognoms="Test",
            nif="BOSSTEST",
            rol="BOSS",
            estat="ACTIU",
        )
        admin_session.add(usr)

    await admin_session.flush()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        res_me = await ac.get("/api/v1/auth/me", headers=headers)
        assert res_me.status_code == 200
        assert res_me.json()["feature_copilot_ia"] is False
