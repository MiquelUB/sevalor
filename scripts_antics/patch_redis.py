with open("backend/app/workers/celery_app.py", "r") as f:
    content = f.read()

content = content.replace("sevalor_dev_redis", "sevalor_redis_pass")

with open("backend/app/workers/celery_app.py", "w") as f:
    f.write(content)
