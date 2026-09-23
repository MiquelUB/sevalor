from celery.result import AsyncResult
from fastapi import APIRouter, HTTPException, Request

from app.workers.celery_app import celery_app

router = APIRouter()

@router.get("/status/{task_id}")
async def get_task_status(task_id: str, request: Request):
    """Retorna l'estat en temps real d'una tasca encolada (Spec 024 RF-21)."""
    # Verifiquem autorització i context
    empresa_id = request.state.empresa_id
    if not empresa_id:
        raise HTTPException(status_code=401)

    task_result = AsyncResult(task_id, app=celery_app)

    # Mapegem l'estat de Celery a un format unificat per la PWA
    estat = task_result.status
    if estat == "SUCCESS":
        estat = "COMPLETADO"
    elif estat == "FAILURE":
        estat = "ERROR"
    elif estat == "PENDING":
        estat = "PENDIENTE"

    return {
        "task_id": task_id,
        "estat": estat,
        "resultat": task_result.result if task_result.ready() else None
    }
