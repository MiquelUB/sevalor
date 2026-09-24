import os
os.environ['REDIS_URL'] = 'redis://:sevalor_redis_pass@127.0.0.1:6380/0'
from backend.app.workers.tasks import ping

res = ping.delay("HELLO")
print("Task ID:", res.id)
print("Result:", res.get(timeout=5))
