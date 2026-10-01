with open("backend/app/workers/celery_app.py", "r") as f:
    content = f.read()

queues_config = """    task_reject_on_worker_lost=True,  # Rebutjar si worker es perd
    task_create_missing_queues=True,
    task_queues={
        "queue_critical": {"exchange": "queue_critical"},
        "queue_documents": {"exchange": "queue_documents"},
        "queue_sync": {"exchange": "queue_sync"},
        "queue_media": {"exchange": "queue_media"},
        "queue_periodic": {"exchange": "queue_periodic"},
    },"""

content = content.replace("    task_reject_on_worker_lost=True,  # Rebutjar si worker es perd", queues_config)

with open("backend/app/workers/celery_app.py", "w") as f:
    f.write(content)
