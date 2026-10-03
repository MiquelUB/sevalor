import time
from typing import Tuple

from redis.asyncio import Redis

from app.core.config import settings


class RedisRateLimiter:
    def __init__(self, limit_per_minut: int = 30):
        self.limit = limit_per_minut
        # Redis connection
        redis_url = settings.REDIS_URL or f"redis://{settings.REDIS_HOST}:{settings.REDIS_PORT}/0"
        self.redis = Redis.from_url(redis_url)

    async def check_rate_limit(self, user_id: int) -> bool:
        """Token Bucket Rate Limiter sobre Redis per Telegram"""
        key = f"rate_limit:telegram:{user_id}"
        current_time = int(time.time())
        window_start = current_time - 60

        # Redis pipeline per token bucket / sliding window
        pipe = self.redis.pipeline()
        pipe.zremrangebyscore(key, 0, window_start)
        pipe.zcard(key)
        pipe.zadd(key, {str(current_time): current_time})
        pipe.expire(key, 60)

        results = await pipe.execute()
        request_count = results[1]

        if request_count >= self.limit:
            # Handle 429 Too Many Requests
            return False

        return True


def detectar_doble_extensio(filename: str) -> Tuple[bool, str]:
    if not filename:
        return False, "OK"
    parts = filename.lower().split(".")
    if len(parts) > 2:
        return True, "Extensió sospitosa (doble extensió no permesa)"
    if parts[-1] in ["exe", "bat", "sh", "py", "js"]:
        return True, "Extensió no permesa (executable/script)"
    return False, "OK"


def validar_magic_bytes(content: bytes) -> Tuple[bool, str]:
    import filetype

    kind = filetype.guess(content)
    if not kind:
        return False, "UNKNOWN"
    if kind.extension in ["jpg", "png", "pdf", "webp"]:
        return True, kind.extension
    return False, kind.extension

import hashlib
import hmac
from urllib.parse import urlencode

SECRET_KEY = "SUPER_SECRET_KEY_MOCK" # Can be loaded from settings

def generar_enllac_efimer(base_url: str, doc_id: str, secret: str = SECRET_KEY) -> str:
    expires = int(time.time()) + 86400 # 24 hores = 1440 minuts
    data = f"{doc_id}:{expires}".encode("utf-8")
    signature = hmac.new(secret.encode("utf-8"), data, hashlib.sha256).hexdigest()

    query = urlencode({"expires": expires, "signature": signature})
    return f"{base_url}/api/v1/documents/{doc_id}/download?{query}"

def validar_enllac_efimer(doc_id: str, expires: int, signature: str, secret: str = SECRET_KEY) -> bool:
    if int(time.time()) > expires:
        return False
    data = f"{doc_id}:{expires}".encode("utf-8")
    expected_sig = hmac.new(secret.encode("utf-8"), data, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected_sig, signature)
