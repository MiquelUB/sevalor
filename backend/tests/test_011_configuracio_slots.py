import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.mark.asyncio
async def test_crear_slot_jornada_continua(admin_session, headers, boss_token):
    from app.models.models import Empresa
    empresa_id = boss_token[1]
    admin_session.add(Empresa(id=uuid.UUID(empresa_id), nom='Test', nif='123', subdomini='test1', pla_subscripcio='STARTER', estat_pagament='ACTIU'))
    await admin_session.flush()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        payload = {
            "nom": "Torn Matí",
            "modalitat": "JORNADA_CONTINUA",
            "hora_entrada_teorica": "07:00",
            "hora_sortida_teorica": "15:00",
            "hores_convenio_setmanals": 40.0,
            "es_intensiva_estiu": False
        }
        res = await ac.post("/api/v1/gestio/configuracio/slots", headers=headers, json=payload)
        assert res.status_code == 200, res.text
        data = res.json()
        assert data["status"] == "OK"
        assert "id" in data

        # Validem llistat
        res_list = await ac.get("/api/v1/gestio/configuracio/slots", headers=headers)
        assert res_list.status_code == 200
        slots = res_list.json()
        assert len(slots) >= 1
        assert any(s["nom"] == "Torn Matí" for s in slots)

@pytest.mark.asyncio
async def test_crear_slot_jornada_partida_validacions(admin_session, headers, boss_token):
    from app.models.models import Empresa
    empresa_id = boss_token[1]
    admin_session.add(Empresa(id=uuid.UUID(empresa_id), nom='Test', nif='123', subdomini='test2', pla_subscripcio='STARTER', estat_pagament='ACTIU'))
    await admin_session.flush()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # Falla per falta d'hores de dinar
        payload_1 = {
            "nom": "Partida Falsa",
            "modalitat": "JORNADA_PARTIDA",
            "hora_entrada_teorica": "08:00",
            "hora_sortida_teorica": "18:00", "hora_inici_dinar": None, "hora_fi_dinar": None,
            "hores_convenio_setmanals": 40.0,
            "es_intensiva_estiu": False
        }
        print(payload_1)
        res_1 = await ac.post("/api/v1/gestio/configuracio/slots", headers=headers, json=payload_1)
        print(res_1.json())
        assert res_1.status_code == 422
        assert "hora d'inici i fi de dinar" in res_1.text

        # Falla perquè l'hora de dinar s'encavalca
        payload_2 = {**payload_1, "hora_inici_dinar": "14:00", "hora_fi_dinar": "13:00"}
        res_2 = await ac.post("/api/v1/gestio/configuracio/slots", headers=headers, json=payload_2)
        assert res_2.status_code == 422
        assert "no pot ser posterior o igual" in res_2.text

        # Falla perquè la pausa està fora d'hores
        payload_3 = {**payload_1, "hora_inici_dinar": "19:00", "hora_fi_dinar": "20:00"}
        res_3 = await ac.post("/api/v1/gestio/configuracio/slots", headers=headers, json=payload_3)
        assert res_3.status_code == 422
        assert "compresa entre l'hora d'entrada i la de sortida" in res_3.text

        # Correcte
        payload_ok = {**payload_1, "hora_inici_dinar": "13:00", "hora_fi_dinar": "14:00"}
        res_ok = await ac.post("/api/v1/gestio/configuracio/slots", headers=headers, json=payload_ok)
        assert res_ok.status_code == 200

@pytest.mark.asyncio
async def test_crear_slot_intensiva_estiu(admin_session, headers, boss_token):
    from app.models.models import Empresa
    empresa_id = boss_token[1]
    admin_session.add(Empresa(id=uuid.UUID(empresa_id), nom='Test', nif='123', subdomini='test3', pla_subscripcio='STARTER', estat_pagament='ACTIU'))
    await admin_session.flush()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # Falla per faltar dates
        payload_err = {
            "nom": "Torn Normal amb Estiu",
            "modalitat": "JORNADA_CONTINUA",
            "hora_entrada_teorica": "08:00",
            "hora_sortida_teorica": "17:00",
            "hores_convenio_setmanals": 40.0,
            "es_intensiva_estiu": True
        }
        res_err = await ac.post("/api/v1/gestio/configuracio/slots", headers=headers, json=payload_err)
        assert res_err.status_code == 422
        assert "exigeix dates d'inici i final" in res_err.text

        # Correcte
        payload_ok = {
            **payload_err,
            "data_inici_estiu": "2024-06-15",
            "data_fi_estiu": "2024-09-15",
            "hora_entrada_estiu": "07:00",
            "hora_sortida_estiu": "15:00"
        }
        res_ok = await ac.post("/api/v1/gestio/configuracio/slots", headers=headers, json=payload_ok)
        assert res_ok.status_code == 200

@pytest.mark.asyncio
async def test_actualitzar_credencials_telegram(admin_session, headers, boss_token):
    from app.models.models import Empresa
    empresa_id = boss_token[1]
    admin_session.add(Empresa(id=uuid.UUID(empresa_id), nom='Test', nif='123', subdomini='test4', pla_subscripcio='STARTER', estat_pagament='ACTIU'))
    await admin_session.flush()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        payload = {
            "telegram_bot_token": "123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11",
            "telegram_webhook_secret": "my-secret-key"
        }
        res = await ac.put("/api/v1/gestio/configuracio/telegram", headers=headers, json=payload)
        assert res.status_code == 200
        assert res.json()["status"] == "OK"

@pytest.mark.asyncio
async def test_provar_connexio_telegram_mocked(admin_session, headers, boss_token, monkeypatch):
    from app.models.models import Empresa
    empresa_id = boss_token[1]
    admin_session.add(Empresa(id=uuid.UUID(empresa_id), nom='Test', nif='123', subdomini='test5', pla_subscripcio='STARTER', estat_pagament='ACTIU'))
    await admin_session.flush()
    """Test de provar_connexio_telegram simulant l'API de Telegram (EDGE-09)."""
    # 1. Activem credencials primer
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        await ac.put("/api/v1/gestio/configuracio/telegram", headers=headers, json={
            "telegram_bot_token": "valid_token", "telegram_webhook_secret": "secret_key_123"
        })

    class MockResponse:
        def __init__(self, json_data, status_code):
            self._json = json_data
            self.status_code = status_code
        def json(self):
            return self._json

    # Simulem HTTP OK
    async def mock_get(*args, **kwargs):
        return MockResponse({"result": {"username": "SevalorBot"}}, 200)

    monkeypatch.setattr("httpx.AsyncClient.get", mock_get)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        res = await ac.post("/api/v1/gestio/configuracio/telegram/provar", headers=headers)
        assert res.status_code == 200
        assert res.json()["estat"] == "OPERATIU"
        assert res.json()["bot_username"] == "SevalorBot"

    # Simulem Timeout / Exception (EDGE-09)
    async def mock_get_fail(*args, **kwargs):
        import httpx
        raise httpx.ReadTimeout("Simulated timeout")

    monkeypatch.setattr("httpx.AsyncClient.get", mock_get_fail)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        res_fail = await ac.post("/api/v1/gestio/configuracio/telegram/provar", headers=headers)
        assert res_fail.status_code == 200 # retorna HTTP 200 però amb estat intern d'error
        assert res_fail.json()["estat"] == "ERROR_CONNEXIO"
        assert "Timeout" in res_fail.json()["missatge"]

