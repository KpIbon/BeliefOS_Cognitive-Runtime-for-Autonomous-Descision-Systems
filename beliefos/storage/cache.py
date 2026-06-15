"""Optional Redis cache.

When ``BELIEFOS_REDIS_URL`` is set, the engine caches the world state and
last decision so reads don't have to hit the database. When it isn't set, the
``InMemoryCache`` is used so the runtime stays usable in dev and tests.
"""

from __future__ import annotations

import json
import time
from typing import Any, Protocol


class Cache(Protocol):
    def get(self, key: str) -> Any | None: ...
    def set(self, key: str, value: Any, ttl_seconds: int = 30) -> None: ...
    def delete(self, key: str) -> None: ...
    def ping(self) -> bool: ...


class InMemoryCache:
    def __init__(self) -> None:
        self._store: dict[str, tuple[float, str]] = {}

    def get(self, key: str) -> Any | None:
        item = self._store.get(key)
        if not item:
            return None
        expires_at, payload = item
        if expires_at and expires_at < time.time():
            self._store.pop(key, None)
            return None
        try:
            return json.loads(payload)
        except json.JSONDecodeError:
            return None

    def set(self, key: str, value: Any, ttl_seconds: int = 30) -> None:
        expires_at = time.time() + ttl_seconds if ttl_seconds else 0
        self._store[key] = (expires_at, json.dumps(value, default=str))

    def delete(self, key: str) -> None:
        self._store.pop(key, None)

    def ping(self) -> bool:
        return True


class RedisCache:
    def __init__(self, url: str) -> None:
        import redis  # imported lazily so the package is optional

        self._client = redis.Redis.from_url(url, decode_responses=True)
        self._url = url

    def get(self, key: str) -> Any | None:
        raw = self._client.get(key)
        if raw is None:
            return None
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return None

    def set(self, key: str, value: Any, ttl_seconds: int = 30) -> None:
        self._client.set(key, json.dumps(value, default=str), ex=ttl_seconds)

    def delete(self, key: str) -> None:
        self._client.delete(key)

    def ping(self) -> bool:
        try:
            return bool(self._client.ping())
        except Exception:
            return False

    @property
    def url(self) -> str:
        return self._url


_cache: Cache | None = None


def get_cache() -> Cache:
    """Return a process-wide cache instance."""

    global _cache
    if _cache is not None:
        return _cache
    from beliefos.core.config import get_settings

    settings = get_settings()
    if settings.redis_url:
        try:
            cache = RedisCache(settings.redis_url)
            if cache.ping():
                _cache = cache
                return _cache
        except Exception:
            # Redis is opportunistic; never fail boot because of it.
            pass
    _cache = InMemoryCache()
    return _cache


def reset_cache_for_tests() -> None:
    """Drop the cached instance — used by the test suite."""

    global _cache
    _cache = None
