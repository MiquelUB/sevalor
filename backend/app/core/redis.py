"""Helper centralitzat per a la gestió de Redis asíncron (Spec 04 & Blacklist de Tenants)."""

import logging
import os
from typing import Optional

import redis.asyncio as aioredis

from app.core.config import settings

logger = logging.getLogger("app.core.redis")

_redis_client: Optional[aioredis.Redis] = None


async def get_redis_client() -> Optional[aioredis.Redis]:
    """Retorna una instància compartida de connexió a Redis o None si no està disponible."""
    global _redis_client
    if _redis_client is not None:
        try:
            await _redis_client.ping()
            return _redis_client
        except Exception:
            _redis_client = None

    try:
        redis_pass = os.getenv("REDIS_PASSWORD", "sevalor_redis_pass")
        auth_part = f":{redis_pass}@" if redis_pass else ""
        default_url = f"redis://{auth_part}{settings.REDIS_HOST}:{settings.REDIS_PORT}/0"
        redis_url = str(os.getenv("REDIS_URL") or settings.REDIS_URL or default_url)
        client = aioredis.from_url(
            redis_url,
            socket_connect_timeout=1.5,
            socket_timeout=1.5,
            decode_responses=True,
        )
        await client.ping()
        _redis_client = client
        return _redis_client
    except Exception as exc:
        logger.warning("Redis no disponible en get_redis_client: %s", exc)
        _redis_client = None
        return None


async def blacklist_tenant(empresa_id: str, estat: str, expire_seconds: int = 86400) -> None:
    """Afegeix l'empresa a la llista negra de sessions de Redis per revocar accés immediatament."""
    try:
        client = await get_redis_client()
        if client:
            await client.set(f"tenant_blocked:{empresa_id}", estat, ex=expire_seconds)
    except Exception as exc:
        logger.warning("No s'ha pogut registrar el bloqueig de tenant a Redis: %s", exc)


async def unblacklist_tenant(empresa_id: str) -> None:
    """Elimina l'empresa de la llista negra de Redis en ser reactivada."""
    try:
        client = await get_redis_client()
        if client:
            await client.delete(f"tenant_blocked:{empresa_id}")
    except Exception as exc:
        logger.warning("No s'ha pogut eliminar el bloqueig de tenant a Redis: %s", exc)


async def is_tenant_blacklisted(empresa_id: str) -> Optional[str]:
    """Comprova si l'empresa té les sessions bloquejades a Redis. Retorna l'estat o None."""
    try:
        client = await get_redis_client()
        if client:
            val = await client.get(f"tenant_blocked:{empresa_id}")
            return str(val) if val else None
    except Exception:
        pass
    return None
