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

