"""
RĀMAN Studio — Redis Cache Layer
==================================
Caches expensive simulation results and material lookups.

Usage:
    from src.backend.core.cache import cache_get, cache_set, cached_simulation

    # Direct
    cache_set("eis:abc123", result_dict, ttl=3600)
    data = cache_get("eis:abc123")

    # Decorator
    @cached_simulation("eis", ttl=1800)
    async def run_eis(params): ...
"""

import hashlib
import json
import logging
import os
import functools
from typing import Any, Optional

logger = logging.getLogger(__name__)

# Try Redis connection
_redis = None
try:
    import redis
    REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
    _redis = redis.Redis.from_url(REDIS_URL, decode_responses=True, socket_timeout=2)
    _redis.ping()
    logger.info("Redis connected: %s", REDIS_URL)
except Exception as e:
    logger.warning("Redis unavailable (%s) — using in-memory LRU fallback", e)
    _redis = None

# In-memory fallback (LRU, max 500 entries)
_mem_cache: dict = {}
_MAX_MEM = 500


def _make_key(prefix: str, params: dict) -> str:
    """Deterministic cache key from params dict."""
    raw = json.dumps(params, sort_keys=True, default=str)
    h = hashlib.sha256(raw.encode()).hexdigest()[:16]
    return f"raman:{prefix}:{h}"


def cache_get(key: str) -> Optional[dict]:
    """Get cached value by key."""
    if _redis:
        try:
            val = _redis.get(key)
            if val:
                logger.debug("Cache HIT: %s", key)
                return json.loads(val)
        except Exception as e:
            logger.warning("Redis GET error: %s", e)

    # Fallback to memory
    if key in _mem_cache:
        logger.debug("MemCache HIT: %s", key)
        return _mem_cache[key]

    return None


def cache_set(key: str, value: dict, ttl: int = 3600):
    """Set cache value with TTL (seconds)."""
    if _redis:
        try:
            _redis.setex(key, ttl, json.dumps(value, default=str))
            logger.debug("Cache SET: %s (ttl=%ds)", key, ttl)
            return
        except Exception as e:
            logger.warning("Redis SET error: %s", e)

    # Fallback to memory
    if len(_mem_cache) >= _MAX_MEM:
        # Evict oldest 10%
        keys = list(_mem_cache.keys())[:_MAX_MEM // 10]
        for k in keys:
            del _mem_cache[k]
    _mem_cache[key] = value


def cache_invalidate(pattern: str = "raman:*"):
    """Invalidate cache entries matching pattern."""
    if _redis:
        try:
            keys = _redis.keys(pattern)
            if keys:
                _redis.delete(*keys)
                logger.info("Invalidated %d cache keys", len(keys))
        except Exception:
            pass
    _mem_cache.clear()


def cached_simulation(prefix: str, ttl: int = 1800):
    """Decorator to cache simulation results.

    Usage:
        @cached_simulation("eis", ttl=3600)
        async def compute_eis(params_dict):
            ...
    """
    def decorator(func):
        @functools.wraps(func)
        async def wrapper(params, *args, **kwargs):
            if isinstance(params, dict):
                key = _make_key(prefix, params)
            else:
                # Pydantic model
                key = _make_key(prefix, params.model_dump() if hasattr(params, 'model_dump') else params.__dict__)

            cached = cache_get(key)
            if cached is not None:
                cached["_cached"] = True
                return cached

            result = await func(params, *args, **kwargs)

            if isinstance(result, dict):
                cache_set(key, result, ttl)

            return result
        return wrapper
    return decorator


def get_stats() -> dict:
    """Get cache statistics."""
    stats = {"backend": "redis" if _redis else "memory", "mem_entries": len(_mem_cache)}
    if _redis:
        try:
            info = _redis.info("memory")
            stats["redis_used_memory"] = info.get("used_memory_human", "unknown")
            stats["redis_keys"] = _redis.dbsize()
        except Exception:
            stats["redis_status"] = "error"
    return stats
