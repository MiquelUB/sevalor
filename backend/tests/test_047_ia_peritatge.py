import pytest
import uuid
import jwt
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.models import MemorandumTecnicCopilot, Empresa, Usuari
from app.core.config import settings

@pytest.fixture
async def setup_db_for_ia(db_session, headers):
    token = headers["Authorization"].split(" ")[1]
    payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM], options={"verify_aud": False})
    user_id = payload["sub"]
    emp_id = headers["X-Empresa-ID"]
    
    empresa = Empresa(id=uuid.UUID(emp_id), nom='Test IA', nif="A12345678", subdomini='ia-' + str(uuid.uuid4())[:5], pla_subscripcio='STARTER', estat_pagament='ACTIU')
    db_session.add(empresa)
    await db_session.flush()

    usuari = Usuari(id=uuid.UUID(user_id), empresa_id=empresa.id, nif=str(uuid.uuid4())[:9], email=f"user_{user_id}@test.com", nom="Operari", password_hash="pass", rol="BOSS", estat="ACTIU")
    db_session.add(usuari)
    await db_session.commit()

@pytest.mark.asyncio
async def test_peritatge_incidencies_audio_only(
    setup_db_for_ia,
    async_client: AsyncClient, 
    db_session: AsyncSession, 
    headers: dict
):
    data = {
        "incidencia_id": str(uuid.uuid4()),
        "ordre_treball_id": str(uuid.uuid4()),
        "audio_path": "/var/data/audio.webm",
        "simular_timeout": True
    }

    response = await async_client.post(
        "/gestio/copilot/incidencies/peritatge",
        json=data,
        headers=headers
    )
    
    assert response.status_code == 201
    result = response.json()
    assert result["estat"] == "ERROR_TIMEOUT"

@pytest.mark.asyncio
async def test_peritatge_incidencies_with_photo(
    setup_db_for_ia,
    async_client: AsyncClient, 
    db_session: AsyncSession, 
    headers: dict
):
    data = {
        "audio_path": "/var/data/audio.webm",
        "foto_path": "/var/data/foto.jpg",
        "simular_timeout": False,
        "confianca_acustica": 0.5,
        "text_dictat_operari": "Avaria a la màquina."
    }

    response = await async_client.post(
        "/gestio/copilot/incidencies/peritatge",
        json=data,
        headers=headers
    )
    
    assert response.status_code == 201
    result = response.json()
    assert result["estat"] == "PROPOSTA"
