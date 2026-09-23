
# Importamos la app de celery
from app.workers.celery_app import celery_app
from app.workers.tasks import ping


def test_celery_ping_task_exists():
    """TDD: Verificar que la tarea ping existe y puede llamarse síncronamente."""
    # Test llamando a la función directamente
    result = ping("TDD")
    assert result["status"] == "PONG"
    assert result["payload"] == "TDD"

def test_celery_app_is_configured():
    """TDD: Verificar que la app de Celery tiene la tarea registrada."""
    # Verificamos si la tarea ping está en el registro de Celery
    assert 'app.workers.tasks.ping' in celery_app.tasks.keys()
