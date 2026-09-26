import pytest
from httpx import ASGITransport, AsyncClient
from app.main import app

@pytest.mark.asyncio
async def test_cerca_api(headers):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        res = await ac.get("/api/v1/gestio/cerca?q=hola", headers=headers)
        assert res.status_code in (200, 404)

def test_backup_service():
    from app.services.backup import executar_backup_empresa
    res = executar_backup_empresa("empresa_fake", "/tmp")
    assert res is not None

@pytest.mark.asyncio
async def test_whisper_service():
    from app.services.whisper_service import transcriure_audio
    res = await transcriure_audio("fake_audio_path")
    assert res is not None

def test_workers_tasks():
    from app.workers.tasks import processar_ocr_document_task
    res = processar_ocr_document_task.delay("fake_path", "emp-1")
    assert res.id is not None
