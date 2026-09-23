import os

os.environ['REDIS_URL'] = 'redis://:sevalor_redis_pass@127.0.0.1:6380/0'
import pytest

from app.workers.tasks import ping


@pytest.mark.asyncio
async def test_celery_ping_task_async():
    """TDD: Verificar que la tarea ping se encola en Redis y el Worker la resuelve."""
    # Despachamos la tarea asíncronamente
    result = ping.delay("ASYNC_PAYLOAD")

    # Esperamos a que el worker real lo procese
    # Necesitamos que el celery worker esté en ejecución con el código nuevo
    res_dict = result.get(timeout=10)
    assert res_dict["status"] == "PONG"
    assert res_dict["payload"] == "ASYNC_PAYLOAD"
