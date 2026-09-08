from __future__ import annotations

from functools import lru_cache

from redis import Redis

from app.config import get_settings


@lru_cache(maxsize=4)
def get_redis_client(url: str | None = None) -> Redis:
    settings = get_settings()
    return Redis.from_url(
        url or settings.redis_url,
        decode_responses=False,
        socket_connect_timeout=0.1,
        socket_timeout=0.2,
    )
