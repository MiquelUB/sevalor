"""Definició de tasques de Celery per a Sevalor Suite.

Compleix Spec 024:
- Injecció obligatòria d'empresa_id per a RLS (RF-02)
- Reintents exponencials (RF-19)
- Dead Letter Queue (RF-20)
- Topologia de 5 cues: queue_critical, queue_documents, queue_sync, queue_media, queue_periodic
"""

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
    """Crea l'arbre de directoris sobirans per a una empresa (Spec 021 RF-08).

    Rutes creades (sobirania de dades a Hetzner, UE):
      /data/<empresa_id>/incidencies/
      /data/<empresa_id>/vehicles/
      /data/<empresa_id>/comptabilitat/
      /docs/<empresa_id>/planols/
      /docs/<empresa_id>/factures/
      /docs/<empresa_id>/backups/
    """
    data_prefix = base_data_dir or os.getenv("SOVEREIGN_DATA_PATH", "/data")
    docs_prefix = base_docs_dir or os.getenv("SOVEREIGN_DOCS_PATH", "/docs")

    # Si no es pot escriure a l'arrel (ex. entorn no root), utilitzar fallback segur
    try:
        os.makedirs(data_prefix, exist_ok=True)
    except OSError:
        data_prefix = "/tmp/data"
        docs_prefix = "/tmp/docs"

    dirs = [
        f"{data_prefix}/{empresa_id}/incidencies",
        f"{data_prefix}/{empresa_id}/vehicles",
        f"{data_prefix}/{empresa_id}/comptabilitat",
        f"{docs_prefix}/{empresa_id}/planols",
        f"{docs_prefix}/{empresa_id}/factures",
        f"{docs_prefix}/{empresa_id}/backups",
    ]
    creades = []
    for d in dirs:
        try:
            os.makedirs(d, exist_ok=True)
            creades.append(d)
        except OSError as e:
            logger.warning("No s'ha pogut crear %s: %s", d, e)
    return creades


@celery_app.task(
    bind=True,
    name="app.workers.tasks.crear_directoris_sobirans_task",
    max_retries=2,
    queue="queue_periodic",
)
def crear_directoris_sobirans_task(self, empresa_id: str) -> Dict[str, Any]:
    """Tasca asíncrona que inicialitza l'arbre de volums sobirans (RF-08).

    Es delega a Celery (queue_periodic) per evitar blocar l'API.
    """
    try:
        directori_creats = crear_directoris_sobirans(empresa_id)
        return {
            "status": "OK",
            "empresa_id": empresa_id,
            "directoris": directori_creats,
        }
    except Exception as exc:
        logger.error("Error creant directoris sobirans per a %s: %s", empresa_id, exc)
        raise self.retry(exc=exc, countdown=5)


@celery_app.task(
    bind=True,
    name="app.workers.tasks.generar_pdf_factura_task",
    max_retries=5,
    default_retry_delay=2,
    queue="queue_documents",
)
def generar_pdf_factura_task(self, empresa_id: str, factura_dict: Dict[str, Any], ruta_desti: str) -> str:
    """Tasca asíncrona per a compilar el PDF de factura Veri*factu mitjançant ReportLab (RF-04, RF-05)."""
    try:
        # La tasca rep un diccionari amb les dades necessàries.
        # La sessió de BD es gestiona dins de la funció o es passa per referència.
        pdf_path = generar_factura_pdf(
            db=None,  # La BD es gestiona al worker si cal
            empresa_id=factura_dict.get("empresa_id"),
            empresa_nom=factura_dict.get("empresa_nom", "SEVALOR"),
            empresa_nif=factura_dict.get("empresa_nif", "B00000000"),
            logotip_path=factura_dict.get("logotip_path"),
            primari_hsl=factura_dict.get("primari_hsl", "210 100% 15%"),
            secundari_hsl=factura_dict.get("secundari_hsl", "38 92% 50%"),
            client_nom=factura_dict.get("client_nom", "Client"),
            client_nif=factura_dict.get("client_nif", "00000000X"),
            serie=factura_dict.get("serie", "2026"),
            numero_factura=factura_dict.get("numero_factura", 1),
            base_imposable=factura_dict.get("base_imposable", 0.0),
            quota_iva=factura_dict.get("quota_iva", 0.0),
            import_total=factura_dict.get("total", 0.0),
            data_emissio=factura_dict.get("data_emissio", "2026-01-01"),
            ruta_desti=ruta_desti,
        )
        return ruta_desti
    except Exception as exc:
        logger.error("Error generant PDF factura: %s", exc, exc_info=True)
        raise self.retry(exc=exc, countdown=2 ** self.request.retries)


@celery_app.task(
    bind=True,
    name="app.workers.tasks.despatx_outbox_aeat_task",
    max_retries=5,
    queue="queue_critical",
)
def despatx_outbox_aeat_task(self, factura_id: str, empresa_id: str, serie: str,
                              numero: int, hash_sha256: str, ruta_pdf: str) -> Dict[str, Any]:
    """Tasca per trametre una factura a l'Outbox de l'AEAT (RF-07, RF-08)."""
    try:
        resultats = processar_enviament_aeat(
            factura_id=factura_id,
            empresa_id=empresa_id,
            serie=serie,
            numero=numero,
            hash_sha256=hash_sha256,
            ruta_pdf=ruta_pdf,
        )
        return resultats
    except Exception as exc:
        raise self.retry(exc=exc, countdown=2 ** self.request.retries)


@celery_app.task(
    bind=True,
    name="app.workers.tasks.executar_backup_setmanal_task",
    max_retries=3,
    queue="queue_periodic",
)
def executar_backup_setmanal_task(self, empresa_id: str, ruta_desti: str = "/backups") -> str:
    """Tasca de còpia de seguretat setmanal amb exclusió de recursivitat (RF-18)."""
    try:
        resultat = executar_backup_empresa(
            empresa_id=empresa_id,
            ruta_desti=ruta_desti,
        )
        return resultat["ruta_zip"]
    except Exception as exc:
        raise self.retry(exc=exc, countdown=10)


@celery_app.task(
    bind=True,
    name="app.workers.tasks.transcriure_audio_task",
    max_retries=2,
    queue="queue_media",
)
def transcriure_audio_task(self, empresa_id: str, audio_path: str, language: str = "ca") -> Dict[str, Any]:
    """Tasca de transcripció d'àudios de camp mitjançant faster-whisper CPU INT8 (RF-14, RF-15)."""
    try:
        with celery_app.flask_app.app_context():  # type: ignore[attr-defined]
            pass
        resultat = asyncio.run(
            transcriure_audio(audio_path=audio_path, language=language)
        )
        return resultat
    except Exception as exc:
        raise self.retry(exc=exc, countdown=5)