import re

with open("backend/tests/test_024_workers_status.py", "r") as f:
    content = f.read()

mock_patch = """import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app
from unittest.mock import patch, MagicMock

@pytest.mark.asyncio
@patch('app.api.v1.workers.AsyncResult')
async def test_workers_status_endpoint(mock_async_result, headers):
    # Mocking the Celery task result to avoid Redis auth issues during tests
    mock_task = MagicMock()
    mock_task.status = "PENDING"
    mock_task.ready.return_value = False
    mock_async_result.return_value = mock_task

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # Petición a un task_id inventado
        res = await ac.get("/api/v1/workers/status/fake-task-1234", headers=headers)
        assert res.status_code == 200
        data = res.json()
        assert "task_id" in data
        assert "estat" in data
        assert data["task_id"] == "fake-task-1234"
        assert data["estat"] == "PENDIENTE"
"""

with open("backend/tests/test_024_workers_status.py", "w") as f:
    f.write(mock_patch)
