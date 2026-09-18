import asyncio
import logging
import os
from typing import Any, Dict, List, Optional

from app.workers.celery_app import celery_app
from app.services.verifactu import generar_factura_pdf
from app.services.backup import executar_backup_empresa
from app.services.outbox_aeat import processar_enviament_aeat
from app.services.whisper_service import transcriure_audio

logger = logging.getLogger("workers.tasks")


def crear_directoris_sobirans(empresa_id: str, base_data_dir: str = None, base_docs_dir: str = None) -> List[str]:
    """Crea l'arbre de directoris sobirans per a una empresa (Spec 021 RF-08)."""
    data_prefix = base_data_dir or os.getenv("SOVEREIGN_DATA_PATH", "/data")
    docs_prefix = base_docs_dir or os.getenv("SOVEREIGN_DOCS_PATH", "/docs")

    try:
        os.makedirs(data_prefix, exist_ok=True)
    except OSError:
        data_prefix = "/tmp/data"
        docs_prefix = "/tmp/docs"

    dirs = [
        f"{data_prefix}/{empresa_id}",
        f"{data_prefix}/{empresa_id}/docs",
        f"{data_prefix}/{empresa_id}/docs/albarans",
        f"{data_prefix}/{empresa_id}/docs/planols",
        f"{data_prefix}/{empresa_id}/incidencies",
        f"{data_prefix}/{empresa_id}/backups",
    ]
    creades = []
    for d in dirs:
        try:
            os.makedirs(d, exist_ok=True)
            creades.append(d)
        except OSError as e:
            logger.warning("No s'ha pogut crear %s: %s", d, e)
    return creades

@celery_app.task(name="generar_informe_planol_pdf", queue="queue_documents")
def generar_informe_planol_pdf(planol_id: str, empresa_id: str):
    from reportlab.pdfgen import canvas
    from reportlab.lib.pagesizes import A4
    import os
    
    path_dir = f"/tmp/docs/{empresa_id}/planols"
    os.makedirs(path_dir, exist_ok=True)
    
    file_path = f"{path_dir}/{planol_id}_export.pdf"
    
    c = canvas.Canvas(file_path, pagesize=A4)
    c.drawString(100, 800, f"Caixetí Oficial de Plànol: {planol_id}")
    c.drawString(100, 780, f"Empresa: {empresa_id}")
    c.drawString(100, 760, "Processat asíncronament via Celery (Spec 010)")
    c.save()
    
    return {"status": "SUCCESS", "path": file_path}

@celery_app.task(queue="queue_critical", bind=True, max_retries=3)
def processar_outbox_aeat(self):
    pass
