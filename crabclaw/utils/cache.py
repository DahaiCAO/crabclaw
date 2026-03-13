"""Caching layer for Crabclaw."""

import asyncio
import functools
import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, TypeVar

from loguru import logger


T = TypeVar("T")


@dataclass
class CacheEntry:
    """A single cache entry."""
    value: Any
    expires_at: datetime
    created_at: datetime = field(default_factory=datetime.now)


class Cache:
    """In-memory cache with TTL support."""

    def __init__(self, default_ttl: int = 300, max_size: int = 1000):
        self._cache: dict[str, CacheEntry] = {}
        self._default_ttl = default_ttl
        self._max_size = max_size
        self._lock = asyncio.Lock()
        self._hits = 0
        self._misses = 0

    def _generate_key(self, key: str, prefix: str = "") -> str:
        """Generate a cache key."""
        if prefix:
            return f"{prefix}:{key}"
        return key

    def _generate_hash_key(self, *args: Any, **kwargs: Any) -> str:
        """Generate a hash-based cache key from arguments."""
        data = json.dumps({"args": args, "kwargs": kwargs}, sort_keys=True, default=str)
        return hashlib.sha256(data.encode()).hexdigest()

    async def get(self, key: str) -> Any | None:
        """Get a value from cache."""
        async with self._lock:
            entry = self._cache.get(key)
            if entry is None:
                self._misses += 1
                return None

            if datetime.now() > entry.expires_at:
                del self._cache[key]
                self._misses += 1
                return None

            self._hits += 1
            return entry.value

    async def set(self, key: str, value: Any, ttl: int | None = None) -> None:
        """Set a value in cache."""
        ttl = ttl or self._default_ttl
        expires_at = datetime.now() + timedelta(seconds=ttl)

        async with self._lock:
            if len(self._cache) >= self._max_size:
                self._evict_oldest()

            self._cache[key] = CacheEntry(value=value, expires_at=expires_at)

    async def delete(self, key: str) -> bool:
        """Delete a value from cache."""
        async with self._lock:
            if key in self._cache:
                del self._cache[key]
                return True
            return False

    async def clear(self) -> None:
        """Clear all cache entries."""
        async with self._lock:
            self._cache.clear()
            self._hits = 0
            self._misses = 0

    def _evict_oldest(self) -> None:
        """Evict the oldest cache entry."""
        if not self._cache:
            return
        oldest_key = min(self._cache.keys(), key=lambda k: self._cache[k].created_at)
        del self._cache[oldest_key]

    async def cleanup_expired(self) -> int:
        """Remove expired entries."""
        now = datetime.now()
        expired_keys = [k for k, v in self._cache.items() if now > v.expires_at]

        async with self._lock:
            for key in expired_keys:
                del self._cache[key]

        if expired_keys:
            logger.debug("Cleaned up {} expired cache entries", len(expired_keys))

        return len(expired_keys)

    @property
    def stats(self) -> dict:
        """Get cache statistics."""
        total = self._hits + self._misses
        hit_rate = (self._hits / total * 100) if total > 0 else 0
        return {
            "size": len(self._cache),
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": f"{hit_rate:.2f}%"
        }


def cached(ttl: int = 300, key_prefix: str = ""):
    """Decorator for caching function results."""
    cache = Cache(default_ttl=ttl)

    def decorator(func):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            cache_key = cache._generate_hash_key(*args, **kwargs)
            if key_prefix:
                cache_key = f"{key_prefix}:{cache_key}"

            cached_value = await cache.get(cache_key)
            if cached_value is not None:
                return cached_value

            import asyncio
            if asyncio.iscoroutinefunction(func):
                result = await func(*args, **kwargs)
            else:
                result = func(*args, **kwargs)

            await cache.set(cache_key, result, ttl)
            return result
        return wrapper
    return decorator


class MultiLevelCache:
    """Multi-level cache with L1 (memory) and L2 (Redis-like) support."""

    def __init__(self, l1_ttl: int = 60, l2_ttl: int = 3600):
        self._l1 = Cache(default_ttl=l1_ttl)
        self._l2: Cache | None = None
        self._l2_ttl = l2_ttl

    def set_l2(self, cache: Cache) -> None:
        """Set the L2 cache (e.g., Redis)."""
        self._l2 = cache

    async def get(self, key: str) -> Any | None:
        """Get from cache, checking L1 then L2."""
        value = await self._l1.get(key)
        if value is not None:
            return value

        if self._l2:
            value = await self._l2.get(key)
            if value is not None:
                await self._l1.set(key, value, self._l2_ttl)
                return value

        return None

    async def set(self, key: str, value: Any, ttl: int | None = None) -> None:
        """Set in both L1 and L2."""
        await self._l1.set(key, value, ttl)
        if self._l2:
            await self._l2.set(key, value, ttl or self._l2_ttl)

    async def invalidate(self, key: str) -> None:
        """Invalidate in both levels."""
        await self._l1.delete(key)
        if self._l2:
            await self._l2.delete(key)


class CacheManager:
    """Manager for multiple named caches."""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._caches: dict[str, Cache] = {}
        return cls._instance

    def get_cache(self, name: str, default_ttl: int = 300, max_size: int = 1000) -> Cache:
        """Get or create a named cache."""
        if name not in self._caches:
            self._caches[name] = Cache(default_ttl=default_ttl, max_size=max_size)
            logger.debug("Created cache: {}", name)
        return self._caches[name]

    async def cleanup_all(self) -> int:
        """Cleanup expired entries in all caches."""
        total = 0
        for cache in self._caches.values():
            total += await cache.cleanup_expired()
        return total

    def get_stats(self) -> dict:
        """Get statistics for all caches."""
        return {name: cache.stats for name, cache in self._caches.items()}


cache_manager = CacheManager()


__all__ = [
    "CacheEntry",
    "Cache",
    "MultiLevelCache",
    "CacheManager",
    "cache_manager",
    "cached",
]
