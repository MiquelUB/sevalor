import uuid
from datetime import datetime, timedelta, timezone

import jwt
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

from app.core.config import settings
from app.main import app
from app.models.models import Empresa, Usuari


@pytest.fixture
def boss_token(admin_session):
    # Generem un UUID per a l'empresa
    empresa_id = str(uuid.uuid4())

    payload = {
        "sub": str(uuid.uuid4()),
        "rol": "BOSS",
        "empresa_id": empresa_id,
        "exp": datetime.now(timezone.utc) + timedelta(minutes=15)
    }
    token = jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return token, empresa_id

@pytest.fixture
def headers(boss_token):
    token, _ = boss_token
    return {"Authorization": f"Bearer {token}"}

@pytest.mark.asyncio
async def test_alta_operari_nou(admin_session, headers, boss_token):
    _, empresa_id = boss_token

    # Inserim l'empresa de prova via BD manual per poder complir amb les Foreign Keys
    admin_session.add(Empresa(
        id=uuid.UUID(empresa_id), nom='Test Company', nif='NIF' + str(uuid.uuid4())[:8], subdomini='sub' + str(uuid.uuid4())[:6], pla_subscripcio='STARTER', estat_pagament='ACTIU'
    ))
    await admin_session.flush()
    await admin_session.flush()

    payload = {
        "nif": "12345678Z",
        "nom": "Joan",
        "cognoms": "Pérez",
        "telefon": "+34600100200",
        "especialitat": "SISTEMES_REG",
        "cost_hora_eur": 25.50
    }

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        res = await ac.post("/api/v1/gestio/operaris", json=payload, headers=headers)

        assert res.status_code == 201, f"Error: {res.text}"
        data = res.json()
        assert data["nif"] == payload["nif"]
        assert data["nom"] == payload["nom"]
        assert data["estat"] == "ACTIU"
        assert data["rol"] == "OPERARI"
        assert "pin_hash" not in data # Seguretat: no retornar el PIN

        # Validem que s'ha desat a la DB
        result = await admin_session.execute(text("SELECT nif, pin_hash, telefon FROM usuaris WHERE id = :id"), {"id": data["id"]})
        row = result.fetchone()
        assert row is not None
        assert row.nif == "12345678Z"
        assert row.pin_hash is not None # El PIN s'ha de generar i hashear
        assert row.telefon == "+34600100200"

@pytest.mark.asyncio
async def test_reset_pin_operari(admin_session, headers, boss_token):
    _, empresa_id = boss_token

    # 1. Crear empresa
    admin_session.add(Empresa(
        id=uuid.UUID(empresa_id), nom='Test Reset', nif='RES' + str(uuid.uuid4())[:8], subdomini='sub' + str(uuid.uuid4())[:6], pla_subscripcio='STARTER', estat_pagament='ACTIU'
    ))
    await admin_session.flush()

    # 2. Crear operari bloquejat
    operari_id = str(uuid.uuid4())
    admin_session.add(Usuari(
        id=uuid.UUID(operari_id), empresa_id=uuid.UUID(empresa_id), nif='RESET123', nom='Maria', rol='OPERARI', pin_bloquejat=True, intents_pin_fallits=4
    ))
    await admin_session.flush()
    await admin_session.flush()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        res = await ac.post(f"/api/v1/gestio/operaris/{operari_id}/reset-pin", headers=headers)
        assert res.status_code == 200, res.text
        data = res.json()
        assert data["missatge"] == "Nou PIN generat i tramès per SMS"
        assert data["pin_bloquejat"] is False
        assert data["intents_pin_fallits"] == 0

        # Validem a BD que els intents s'han posat a 0
        result = await admin_session.execute(text("SELECT pin_bloquejat, intents_pin_fallits FROM usuaris WHERE id = :id"), {"id": operari_id})
        row = result.fetchone()
        assert row.pin_bloquejat is False
        assert row.intents_pin_fallits == 0


@pytest.mark.asyncio
async def test_editar_operari_boss_i_secretaria(admin_session, boss_token):
    boss_jwt, empresa_id = boss_token

    admin_session.add(Empresa(
        id=uuid.UUID(empresa_id),
        nom='Test Editar Operari',
        nif='EDT' + str(uuid.uuid4())[:8],
        subdomini='sub' + str(uuid.uuid4())[:6],
        pla_subscripcio='STARTER',
        estat_pagament='ACTIU'
    ))
    await admin_session.flush()

    operari_id = str(uuid.uuid4())
    admin_session.add(Usuari(
        id=uuid.UUID(operari_id),
        empresa_id=uuid.UUID(empresa_id),
        nif='47821948B',
        nom='Jordi',
        cognoms='Soler',
        telefon='+34611223344',
        rol='OPERARI',
        especialitat='SISTEMES_REG',
        cost_hora_eur=22.50,
        estat='ACTIU',
    ))
    await admin_session.flush()

    # 1. Edició amb rol BOSS
    boss_headers = {"Authorization": f"Bearer {boss_jwt}"}
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        res_boss = await ac.put(
            f"/api/v1/gestio/operaris/{operari_id}",
            json={
                "nom": "Jordi Miquel",
                "cognoms": "Soler Vila",
                "telefon": "+34699887766",
                "rol": "CAP_DE_COLLA",
                "especialitat": "ELECTRICITAT",
                "estat_operatiu": "EN_FEINA",
                "cost_hora_eur": 28.00,
                "carnet_conduir": "B+E",
                "carnet_caducitat": "2031-06-30",
                "prl_certificat_vigencia": "2028-12-31",
            },
            headers=boss_headers,
        )
        assert res_boss.status_code == 200, res_boss.text
        data_boss = res_boss.json()
        assert data_boss["nom"] == "Jordi Miquel"
        assert data_boss["rol"] == "CAP_DE_COLLA"
        assert data_boss["especialitat"] == "ELECTRICITAT"
        assert data_boss["cost_hora_eur"] == 28.00

        # 2. Edició amb rol SECRETARIA
        secretaria_jwt = jwt.encode(
            {
                "sub": str(uuid.uuid4()),
                "rol": "SECRETARIA",
                "empresa_id": empresa_id,
                "exp": datetime.now(timezone.utc) + timedelta(minutes=15),
            },
            settings.SECRET_KEY,
            algorithm=settings.ALGORITHM,
        )
        sec_headers = {"Authorization": f"Bearer {secretaria_jwt}"}
        res_sec = await ac.put(
            f"/api/v1/gestio/operaris/{operari_id}",
            json={
                "telefon": "+34655443322",
                "cost_hora_eur": 30.50,
                "estat_operatiu": "DISPONIBLE",
            },
            headers=sec_headers,
        )
        assert res_sec.status_code == 200, res_sec.text
        data_sec = res_sec.json()
        assert data_sec["telefon"] == "+34655443322"
        assert data_sec["cost_hora_eur"] == 30.50

        # 3. Veto d'ENGINYER (403 Forbidden)
        enginyer_jwt = jwt.encode(
            {
                "sub": str(uuid.uuid4()),
                "rol": "ENGINYER",
                "empresa_id": empresa_id,
                "exp": datetime.now(timezone.utc) + timedelta(minutes=15),
            },
            settings.SECRET_KEY,
            algorithm=settings.ALGORITHM,
        )
        eng_headers = {"Authorization": f"Bearer {enginyer_jwt}"}
        res_eng = await ac.put(
            f"/api/v1/gestio/operaris/{operari_id}",
            json={"cost_hora_eur": 50.00},
            headers=eng_headers,
        )
        assert res_eng.status_code == 403, res_eng.text


