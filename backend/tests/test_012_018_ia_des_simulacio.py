import pytest
import uuid
import os
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.models.models import Empresa, Usuari
from sqlalchemy import text

@pytest.mark.asyncio
async def test_tiquet_ocr_ia(admin_session, headers, boss_token):
    token, empresa_id = boss_token
    boss_nif = "B" + str(uuid.uuid4())[:8].upper()
    
    admin_session.add(Empresa(
        id=uuid.UUID(empresa_id), nom='Test IA Tiquets', nif=boss_nif, subdomini='tiquets-' + str(uuid.uuid4())[:5], pla_subscripcio='STARTER', estat_pagament='ACTIU'
    ))
    await admin_session.flush()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        res = await ac.get("/api/v1/operari/tiquets", headers=headers)
        assert res.status_code == 200

