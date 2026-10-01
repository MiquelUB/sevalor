import pytest
from httpx import AsyncClient
from app.main import app

@pytest.mark.asyncio
async def test_minimal(async_client: AsyncClient, headers: dict):
    files = {"audio": ("test_audio.webm", b'ValidAudioData', "audio/webm")}
    response = await async_client.post("/gestio/copilot/incidencies/peritatge", files=files, headers=headers)
    print(response.json())
    assert response.status_code == 201
