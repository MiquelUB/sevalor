"""Configuració de Celery 5.3+ per a processament asíncron a Sevalor Suite.

Compleix Spec 024 i Spec 03 Bloc 9:
- Topologia de cues aïllades: queue_documents, queue_media, queue_sync, queue_critical, queue_periodic
- Broker Redis 7
- Multi-tenancy RLS estricte a cada tasca
- Beat schedules: alerta flota (T047), tancament jornades (T048),
  purga tokens (T049), backup sobirà (T050), informe setmanal (T041)
"""

import os

from celery import Celery
from celery.schedules import crontab

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
    task_create_missing_queues=True,
    task_queues={
        "queue_critical": {"exchange": "queue_critical"},
        "queue_documents": {"exchange": "queue_documents"},
        "queue_sync": {"exchange": "queue_sync"},
        "queue_media": {"exchange": "queue_media"},
        "queue_periodic": {"exchange": "queue_periodic"},
    },
    task_routes={
        "app.workers.tasks.generar_pdf_factura_task": {"queue": "queue_documents"},
        "app.workers.tasks.executar_backup_setmanal_task": {"queue": "queue_periodic"},
        "app.workers.tasks.despatx_outbox_aeat_task": {"queue": "queue_critical"},
        "app.workers.tasks.transcriure_audio_task": {"queue": "queue_media"},
        "app.workers.tasks.generar_informe_setmanal": {"queue": "queue_documents"},
        "app.workers.tasks.purgar_tokens_expirats": {"queue": "queue_periodic"},
        "app.workers.tasks.revisar_contractes_manteniment": {"queue": "queue_periodic"},
    },
    # ── T047-T050 + T041 + Contractes: Celery Beat Schedules ───────────────────────────────
    beat_schedule={
        # Contractes: Revisar contractes de manteniment i generar OTs - cada dia a les 04:00 UTC
        "revisar-contractes-manteniment-diaria": {
            "task": "app.workers.tasks.revisar_contractes_manteniment",
            "schedule": crontab(hour=4, minute=0),
        },
        # T047: Alerta Matinal de Flota — cada dia a les 06:00 UTC
        "alerta-matinal-flota-diaria": {
            "task": "app.workers.tasks.revisar_itv_asseguranca",
            "schedule": crontab(hour=6, minute=0),
            "kwargs": {"empresa_id": None},  # empresa_id=None → itera totes les empreses
        },
        # T048: Tancament Cautelar de Jornades Obertes — cada dia a les 23:59 UTC
        "tancament-jornades-orfanes-nocturn": {
            "task": "app.workers.tasks.tancar_jornades_orfanes",
            "schedule": crontab(hour=23, minute=59),
            "kwargs": {"empresa_id": None},
        },
        # T049: Purga de Tokens Temporals Expirats — cada hora en punt
        "purga-tokens-expirats-horaria": {
            "task": "app.workers.tasks.purgar_tokens_expirats",
            "schedule": crontab(minute=0),
        },
        # T050: Còpia de Seguretat Setmanal Sobirana — diumenges 02:00 UTC
        "backup-setmanal-sobirania": {
            "task": "app.workers.tasks.generar_backup_pgdump",
            "schedule": crontab(hour=2, minute=0, day_of_week=0),
            "kwargs": {"empresa_id": None},
        },
        # T041: Informe Setmanal Automàtic Boss Only — dilluns 08:00 UTC
        "informe-setmanal-boss-dilluns": {
            "task": "app.workers.tasks.generar_informe_setmanal",
            "schedule": crontab(hour=8, minute=0, day_of_week=1),
        },
    },
)
