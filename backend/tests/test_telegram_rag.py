import pytest
import uuid
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.models.models import Empresa, Client, FaqCorporativaRag
from datetime import datetime, timezone

@pytest.mark.asyncio
async def test_telegram_rag(admin_session, boss_token):
    token_jwt, empresa_id = boss_token
    boss_nif = "B" + str(uuid.uuid4())[:8].upper()
    
    admin_session.add(Empresa(id=uuid.UUID(empresa_id), nom="Test Empresa", nif=boss_nif, subdomini="testragbot", pla_subscripcio="STARTER", estat_pagament="ACTIU"))
    await admin_session.flush()
    
    # Crear client i afegir info RAG
    client_id = uuid.uuid4()
    admin_session.add(Client(
        id=client_id,
        empresa_id=uuid.UUID(empresa_id),
        codi="CLI-001",
        rao_social="Client Test RAG Telegram",
        nif="TELEGRAM02",
        estat_canal_telegram="ACTIU",
        telegram_chat_id=999888
    ))
    
    admin_session.add(FaqCorporativaRag(
        empresa_id=uuid.UUID(empresa_id),
        pregunta="Temps de garantia instal·lacions",
        resposta="Les nostres instal·lacions tenen una garantia de 24 mesos des de la data de finalització.",
        paraules_clau="garantia, temps, durada",
        actiu=True
    ))
    
    await admin_session.flush()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        payload_webhook = {
            "update_id": 10001,
            "message": {
                "message_id": 2,
                "from": {"id": 999888, "is_bot": False, "first_name": "Joan"},
                "chat": {"id": 999888, "type": "private"},
                "date": 1600000000,
                "text": "Quina és la garantia?"
            }
        }

        res = await ac.post("/api/v1/webhooks/telegram", json=payload_webhook)
        assert res.status_code == 200
        assert res.json()["action"] == "processed"
