import pytest
import uuid
import jwt
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.models.models import Empresa, Usuari, Article, EstocMagatzem, Magatzem, FaqCorporativaRag

@pytest.mark.asyncio
async def test_copilot_xat(admin_session, headers, boss_token):
    token_jwt, empresa_id = boss_token
    boss_nif = "B" + str(uuid.uuid4())[:8].upper()
    
    decoded = jwt.decode(token_jwt, options={"verify_signature": False})
    
    admin_session.add(Empresa(
        id=uuid.UUID(empresa_id), nom='Test Copilot', nif=boss_nif, subdomini='copi-' + str(uuid.uuid4())[:5], pla_subscripcio='STARTER', estat_pagament='ACTIU'
    ))
    admin_session.add(Usuari(id=uuid.UUID(decoded["sub"]), empresa_id=uuid.UUID(empresa_id), nom="Boss", cognoms="Boss", nif="BOSS1", rol="BOSS", estat="ACTIU"))
    
    # Afegir un FAQ Real al RAG
    admin_session.add(FaqCorporativaRag(
        empresa_id=uuid.UUID(empresa_id),
        pregunta="Manual d'Instal·lació de Quadres Elèctrics",
        resposta="Protocol: Verificar sempre el diferencial de 30mA abans d'iniciar el cablejat del quadre. Rebt-2024.",
        paraules_clau="electricitat, quadre, rebt",
        actiu=True
    ))
    
    await admin_session.flush()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        res = await ac.post("/api/v1/gestio/copilot/xat", json={"pregunta": "Quin és el procediment o protocol per instal·lar un quadre?"}, headers=headers)
        assert res.status_code == 200
        data = res.json()
        print("RESPOSTA DEL COPILOT:")
        print(data)
        assert "resposta" in data
