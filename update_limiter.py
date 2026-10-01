import re

with open("backend/app/main.py", "r") as f:
    content = f.read()

limiter_setup = """from limits.storage import RedisStorage
from app.core.config import settings
import os

redis_url = os.getenv("REDIS_URL", "redis://:sevalor_redis_pass@127.0.0.1:6380/0")
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["100/minute"],
    storage_uri=redis_url if os.getenv("TESTING") != "1" else "memory://"
)"""

content = re.sub(r'limiter = Limiter\(key_func=get_remote_address, default_limits=\["100/minute"\]\)', limiter_setup, content)

with open("backend/app/main.py", "w") as f:
    f.write(content)
