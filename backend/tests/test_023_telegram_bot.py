import pytest
import uuid
from datetime import datetime, timezone, timedelta
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.models.models import Empresa, Client, TokenInvitacioTelegram
from sqlalchemy import select

@pytest.mark.asyncio
async def test_telegram_webhook_enllacar_compte(admin_session, boss_token):
    token_jwt, empresa_id = boss_token
    
    admin_session.add(Empresa(id=uuid.UUID(empresa_id), nom="Test Empresa", nif="TESTNIF123", subdomini="testbot", pla_subscripcio="STARTER", estat_pagament="ACTIU"))
    await admin_session.flush()
    client_id = uuid.uuid4()
    admin_session.add(Client(
        id=client_id,
        empresa_id=uuid.UUID(empresa_id),
        codi="CLI-001",
        rao_social="Client Test Telegram",
        nif="TELEGRAM01",
        estat_canal_telegram="DESVINCULAT"
    ))
    
    token_telegram = "ABC-1234-XYZ"
    admin_session.add(TokenInvitacioTelegram(
        id=uuid.uuid4(),
        empresa_id=uuid.UUID(empresa_id),
        client_id=client_id,
        token_hash=token_telegram,
        expira_a=datetime.now(timezone.utc) + timedelta(days=1),
        utilitzat=False
    ))
    await admin_session.flush()
    await admin_session.commit()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        payload_webhook = {
            "update_id": 10000,
            "message": {
                "message_id": 1,
                "from": {"id": 99999999, "is_bot": False, "first_name": "Joan"},
                "chat": {"id": 99999999, "type": "private"},
                "date": 1600000000,
                "text": f"/start {token_telegram}"
            }
        }
        
        # 1. Fem la petició webhook simulant que ve de Telegram
        res = await ac.post("/api/v1/webhooks/telegram", json=payload_webhook)
        assert res.status_code == 200
        assert res.json()["action"] == "linked"
        
        # 2. Verifiquem que a la BD s'ha registrat el xat
        stmt = select(Client).where(Client.id == client_id)
        result = await admin_session.execute(stmt)
        client_db = result.scalars().first()
        
        assert client_db is not None
        assert client_db.telegram_chat_id == 99999999
        assert client_db.estat_canal_telegram == "ACTIU"
