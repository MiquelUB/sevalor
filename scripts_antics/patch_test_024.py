with open("backend/tests/test_024_celery_ping_async.py", "r") as f:
    content = f.read()

content = content.replace("os.environ['REDIS_URL'] = 'redis://127.0.0.1:6380/0'", "os.environ['REDIS_URL'] = 'redis://:sevalor_redis_pass@127.0.0.1:6380/0'")

with open("backend/tests/test_024_celery_ping_async.py", "w") as f:
    f.write(content)
