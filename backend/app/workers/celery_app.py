"""Configuració de Celery 5.3+ per a processament asíncron a Sevalor Suite.

Compleix Spec 024:
- Topologia de cues aïllades: queue_documents, queue_media, queue_sync, queue_critical, queue_periodic
- Broker Redis 7
- Multi-tenancy RLS estricte a cada tasca
"""

import os

from celery import Celery

REDIS_URL = os.getenv("REDIS_URL", "redis://:sevalor_redis_pass@127.0.0.1:6380/0")

celery_app = Celery(
    "sevalor_workers",
    broker=REDIS_URL,
    backend=REDIS_URL,
    include=["app.workers.tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Europe/Madrid",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=300,  # 5 minuts màxim per tasca
    worker_concurrency=4,  # Optimitzat per Hetzner CPX21
    task_acks_late=True,  # Reassignar tasca si el worker cau
    task_reject_on_worker_lost=True,  # Rebutjar si worker es perd
    task_routes={
        "app.workers.tasks.generar_pdf_factura_task": {"queue": "queue_documents"},
        "app.workers.tasks.executar_backup_setmanal_task": {"queue": "queue_periodic"},
        "app.workers.tasks.despatx_outbox_aeat_task": {"queue": "queue_critical"},
        "app.workers.tasks.transcriure_audio_task": {"queue": "queue_media"},
    },
)
