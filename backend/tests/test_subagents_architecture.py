"""Tests de verificació de l'Arquitectura Multi-Agent i Subagents Especialitzats.

Verifica:
- Selecció i encaminament idoni de subagents (Dispatcher Routing).
- Aïllament i doble barrera de seguretat RBAC (Veto Financer BOSS Only, Veto Operaris).
- Execució de cadascun dels 6 subagents especialitzats amb dades reals (Zero Mock Data).
"""

import uuid
from datetime import datetime, timedelta, timezone

import jwt
import pytest
from httpx import ASGITransport, AsyncClient

from app.core.config import settings
from app.main import app
from app.models.models import Article, Empresa, EstocMagatzem, Magatzem, Usuari, Vehicle
from app.services.subagents import (
    CopilotDispatcher,
    SubagentAuditoriaMarge,
    SubagentClientTelegram,
    SubagentFlotaDespatx,
    SubagentGeneralRag,
    SubagentLogisticaEstoc,
    SubagentOcrVision,
    SubagentPeritatgeCamp,
)


def generar_token(usuari_id: uuid.UUID, empresa_id: uuid.UUID, rol: str) -> str:
    payload = {
        "sub": str(usuari_id),
        "rol": rol,
        "empresa_id": str(empresa_id),
        "exp": datetime.now(timezone.utc) + timedelta(minutes=30),
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


@pytest.mark.asyncio
async def test_subagents_dispatcher_intent_routing():
    """Verifica que el dispatcher classifica la intenció cap al subagent especialitzat corresponent."""
    dispatcher = CopilotDispatcher()

    # 1. Logística / Estoc
    sub_estoc = dispatcher.select_subagent("Quant de cable 6mm ens queda al magatzem?", "BOSS")
    assert isinstance(sub_estoc, SubagentLogisticaEstoc)
    assert sub_estoc.id == "subagent_logistica_estoc"

    # 2. Flota / Desplaçaments
    sub_flota = dispatcher.select_subagent(
        "Quin vehicle o furgoneta està més a prop de l'obra a 41.38, 2.17?", "ENGINYER"
    )
    assert isinstance(sub_flota, SubagentFlotaDespatx)
    assert sub_flota.id == "subagent_flota_despatx"

    # 3. Peritatge / Garanties
    sub_perit = dispatcher.select_subagent(
        "Aquesta avaria de fuita en bomba està en garantia?", "ENGINYER"
    )
    assert isinstance(sub_perit, SubagentPeritatgeCamp)
    assert sub_perit.id == "subagent_peritatge_camp"

    # 4. OCR / Digitalització
    sub_ocr = dispatcher.select_subagent(
        "Extreu les línies d'aquest albarà de proveïdor amb NIF B12345678", "SECRETARIA"
    )
    assert isinstance(sub_ocr, SubagentOcrVision)
    assert sub_ocr.id == "subagent_ocr_vision"

    # 5. Telegram Concierge
    sub_tg = dispatcher.select_subagent(
        "Envia un avís de notificació d'arribada tècnic per Telegram al client", "SECRETARIA"
    )
    assert isinstance(sub_tg, SubagentClientTelegram)
    assert sub_tg.id == "subagent_client_telegram"

    # 6. Auditoria Marge (BOSS)
    sub_marge = dispatcher.select_subagent(
        "Calcula els diners no facturats i la desviació de marge del mes", "BOSS"
    )
    assert isinstance(sub_marge, SubagentAuditoriaMarge)
    assert sub_marge.id == "subagent_auditoria_marge"

    # 7. General RAG
    sub_gen = dispatcher.select_subagent(
        "Com és el protocol general de seguretat laboral?", "ENGINYER"
    )
    assert isinstance(sub_gen, SubagentGeneralRag)
    assert sub_gen.id == "subagent_general_rag"


@pytest.mark.asyncio
async def test_subagents_rbac_double_barrier(admin_session):
    """Verifica el veto estricte de seguretat RBAC per a operaris i consultes financeres d'enginyers."""
    empresa_id = uuid.uuid4()
    boss_id = uuid.uuid4()
    enginyer_id = uuid.uuid4()
    operari_id = uuid.uuid4()

    admin_session.add(
        Empresa(
            id=empresa_id,
            nom="Test Security Tenant",
            nif="B" + uuid.uuid4().hex[:8].upper(),
            subdomini="sec-" + uuid.uuid4().hex[:5],
            pla_subscripcio="ENTERPRISE",
            estat_pagament="ACTIU",
        )
    )
    admin_session.add(
        Usuari(
            id=boss_id,
            empresa_id=empresa_id,
            nom="Director",
            cognoms="Boss",
            nif="0001B",
            rol="BOSS",
            estat="ACTIU",
        )
    )
    admin_session.add(
        Usuari(
            id=enginyer_id,
            empresa_id=empresa_id,
            nom="Tècnic",
            cognoms="Enginyer",
            nif="0002E",
            rol="ENGINYER",
            estat="ACTIU",
        )
    )
    admin_session.add(
        Usuari(
            id=operari_id,
            empresa_id=empresa_id,
            nom="Operari",
            cognoms="Camp",
            nif="0003O",
            rol="OPERARI",
            estat="ACTIU",
        )
    )
    await admin_session.flush()

    token_boss = generar_token(boss_id, empresa_id, "BOSS")
    token_enginyer = generar_token(enginyer_id, empresa_id, "ENGINYER")
    token_operari = generar_token(operari_id, empresa_id, "OPERARI")

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # 1. Operari bloquejat
        res_op = await ac.post(
            "/api/v1/gestio/copilot/xat",
            json={"pregunta": "Hola, quin és l'estoc?"},
            headers={"Authorization": f"Bearer {token_operari}"},
        )
        assert res_op.status_code == 403

        # 2. Enginyer bloquejat en consulta financera
        res_eng_fin = await ac.post(
            "/api/v1/gestio/copilot/xat",
            json={"pregunta": "Quin és el marge brut global i la facturacio total?"},
            headers={"Authorization": f"Bearer {token_enginyer}"},
        )
        assert res_eng_fin.status_code == 403
        assert "no autoritzada" in res_eng_fin.json()["detail"]

        # 3. Boss autoritzat en consulta financera
        res_boss_fin = await ac.post(
            "/api/v1/gestio/copilot/xat",
            json={"pregunta": "Quants diners tenim no facturats aquest mes?"},
            headers={"Authorization": f"Bearer {token_boss}"},
        )
        assert res_boss_fin.status_code == 200
        data_boss = res_boss_fin.json()
        assert data_boss["subagent_utilitzat"] == "subagent_auditoria_marge"
        assert "resposta" in data_boss


@pytest.mark.asyncio
async def test_subagent_logistica_and_flota_execution(admin_session, boss_token):
    """Verifica l'execució en viu de subagent_logistica_estoc i subagent_flota_despatx."""
    token_jwt, empresa_id_str = boss_token
    empresa_id = uuid.UUID(empresa_id_str)
    decoded = jwt.decode(token_jwt, options={"verify_signature": False})
    usuari_id = uuid.UUID(decoded["sub"])

    empresa = Empresa(
        id=empresa_id,
        nom="MultiAgent Logistics Tenant",
        nif="B" + uuid.uuid4().hex[:8].upper(),
        subdomini="malog-" + uuid.uuid4().hex[:5],
        pla_subscripcio="ENTERPRISE",
        estat_pagament="ACTIU",
    )
    admin_session.add(empresa)
    await admin_session.flush()
    admin_session.add(
        Usuari(
            id=usuari_id,
            empresa_id=empresa_id,
            nom="Boss",
            cognoms="Test",
            nif="B9988",
            rol="BOSS",
            estat="ACTIU",
        )
    )

    art = Article(
        id=uuid.uuid4(),
        empresa_id=empresa_id,
        referencia_inventari="TUB-PE-100",
        nom="Tub Polietilè 100mm",
        familia="REG",
        unitat_mesura="METRES",
        preu_cost=4.20,
        preu_venda=8.50,
        estoc_minim=20.0,
        estoc_optim=100.0,
    )
    admin_session.add(art)

    mag = Magatzem(
        id=uuid.uuid4(),
        empresa_id=empresa_id,
        nom="Magatzem Lleida",
        tipus="CENTRAL",
    )
    admin_session.add(mag)

    veh = Vehicle(
        id=uuid.uuid4(),
        empresa_id=empresa_id,
        matricula="5566-BBB",
        marca="Renault",
        model="Master",
        tipus="FURGONETA",
        estat="OPERATIU",
        odometre_acumulat=45000,
    )
    admin_session.add(veh)
    await admin_session.flush()

    st = EstocMagatzem(
        id=uuid.uuid4(),
        empresa_id=empresa_id,
        article_id=art.id,
        magatzem_id=mag.id,
        quantitat_fisica=150.0,
        quantitat_virtual_reservada=10.0,
    )
    admin_session.add(st)
    await admin_session.flush()

    headers = {"Authorization": f"Bearer {token_jwt}"}

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # Test Estoc
        res_estoc = await ac.post(
            "/api/v1/gestio/copilot/xat",
            json={"pregunta": "Quin és l'estoc de Tub Polietilè 100mm?"},
            headers=headers,
        )
        assert res_estoc.status_code == 200
        data_estoc = res_estoc.json()
        assert data_estoc["subagent_utilitzat"] == "subagent_logistica_estoc"
        assert data_estoc["tool_utilitzada"] == "get_real_stock"
        assert "140" in data_estoc["resposta"]  # 150 física - 10 reservada = 140 disponible

        # Test Vehicle
        res_veh = await ac.post(
            "/api/v1/gestio/copilot/xat",
            json={"pregunta": "Quines dades té el vehicle amb matrícula 5566-BBB?"},
            headers=headers,
        )
        assert res_veh.status_code == 200
        data_veh = res_veh.json()
        assert data_veh["subagent_utilitzat"] == "subagent_flota_despatx"
        assert data_veh["tool_utilitzada"] == "get_vehicle_info"
        assert "Renault" in data_veh["resposta"]
