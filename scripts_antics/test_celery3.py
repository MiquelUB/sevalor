import os
os.environ['REDIS_URL'] = 'redis://:sevalor_redis_pass@127.0.0.1:6380/0'
from backend.app.workers.tasks import ping
import redis

res = ping.delay("HELLO")
print("Is eager?", res.backend)
print("Result state:", res.state)
