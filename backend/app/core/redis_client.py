from __future__ import annotations

from typing import Any

from redis import Redis
from redis.exceptions import RedisError

from backend.app.core.config import get_settings


def create_redis_client() -> Redis:
    settings = get_settings()
    return Redis.from_url(settings.redis_url, decode_responses=True)


redis_client = create_redis_client()


def check_redis() -> dict[str, Any]:
    try:
        redis_client.ping()
        return {"ok": True, "message": "Redis connection ok"}
    except RedisError as exc:
        return {"ok": False, "message": str(exc)}
