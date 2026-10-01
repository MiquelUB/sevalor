import pytest
import uuid
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.models import MemorandumTecnicCopilot
from sqlalchemy import select

@pytest.mark.asyncio
async def test_peritatge_incidencies_audio_only(
    async_client: AsyncClient, 
    db_session: AsyncSession, 
    headers: dict
):
    audio_content = b'ValidAudDummyData'
    
    files = {
        "audio": ("test_audio.webm", audio_content, "audio/webm")
    }
    data = {
        "incidencia_id": str(uuid.uuid4()),
        "ordre_treball_id": str(uuid.uuid4())
    }

    response = await async_client.post(
        "/gestio/copilot/incidencies/peritatge",
        files=files,
        data=data,
        headers=headers
    )
    
    print(response.json())
    assert response.status_code == 201
    
    result = response.json()
    assert "id" in result
    assert result["estat"] == "PENDENT_REVISIO"
    assert "dictamen_pericial" in result
    assert result["transcripcio_audio"] == "Copilot provisionalment no disponible"
    assert result["confianca_acustica"] > 0.0

    stmt = select(MemorandumTecnicCopilot).where(MemorandumTecnicCopilot.id == result["id"])
    db_res = await db_session.execute(stmt)
    memo = db_res.scalar_one_or_none()
    
    assert memo is not None
    assert memo.analisi_visual is None

@pytest.mark.asyncio
async def test_peritatge_incidencies_with_photo(
    async_client: AsyncClient, 
    db_session: AsyncSession, 
    headers: dict
):
    audio_content = b'ValidAudDummyData'
    photo_content = b'ValidPhoDummyData'
    
    files = {
        "audio": ("test_audio.webm", audio_content, "audio/webm"),
        "foto": ("test_photo.jpg", photo_content, "image/jpeg")
    }

    response = await async_client.post(
        "/gestio/copilot/incidencies/peritatge",
        files=files,
        headers=headers
    )
    
    assert response.status_code == 201
    result = response.json()
    
    stmt = select(MemorandumTecnicCopilot).where(MemorandumTecnicCopilot.id == result["id"])
    db_res = await db_session.execute(stmt)
    memo = db_res.scalar_one_or_none()
    
    assert memo is not None
    assert memo.analisi_visual == "PENDENT_AUDITORIA"
