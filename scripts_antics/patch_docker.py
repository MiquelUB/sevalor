with open("docker-compose.yml", "r") as f:
    content = f.read()

content = content.replace(
    "command: celery -A app.workers.celery_app worker --loglevel=INFO --concurrency=4",
    "command: celery -A app.workers.celery_app worker -Q celery,queue_critical,queue_media,queue_periodic,queue_documents --loglevel=INFO --concurrency=4"
)

with open("docker-compose.yml", "w") as f:
    f.write(content)
