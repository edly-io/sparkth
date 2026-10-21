"""Shared cache for plugins: the Redis-backed :class:`CacheService` and its accessor."""

from sparkth.core.cache import CacheService, get_cache_service

__all__ = ["CacheService", "get_cache_service"]
