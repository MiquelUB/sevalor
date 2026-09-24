import os

filepath = "backend/tests/test_024_celery_ping_async.py"
with open(filepath, "r") as f:
    content = f.read()

content = "import os\nos.environ['REDIS_URL'] = 'redis://127.0.0.1:6380/0'\n" + content

with open(filepath, "w") as f:
    f.write(content)
