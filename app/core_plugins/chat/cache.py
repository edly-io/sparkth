import json
from typing import Any

import redis.asyncio as aioredis

from app.core.logger import get_logger

logger = get_logger(__name__)


class CacheService:
    def __init__(self, redis_url: str, default_ttl: int = 3600):
        self.redis_url = redis_url
        self.default_ttl = default_ttl
        self._redis: aioredis.Redis | None = None

    async def connect(self) -> None:
        if self._redis is None:
            try:
                self._redis = await aioredis.from_url(  # type: ignore[no-untyped-call]
                    self.redis_url,
                    encoding="utf-8",
                    decode_responses=True,
                )
                logger.info("Connected to Redis successfully")
            except Exception as e:
                logger.error(f"Failed to connect to Redis: {e}")
                raise

    async def disconnect(self) -> None:
        if self._redis:
            await self._redis.aclose()
            self._redis = None
            logger.info("Disconnected from Redis")

    async def get(self, key: str) -> str | None:
        await self.connect()

        if self._redis is None:
            raise RuntimeError("Failed to establish Redis connection")

        try:
            value: str | None = await self._redis.get(key)
            return value
        except Exception as e:
            logger.warning(f"Cache get failed for key '{key}': {e}")
            return None

    async def set(self, key: str, value: str, ttl: int | None = None) -> bool:
        if not self._redis:
            await self.connect()

        ttl = ttl or self.default_ttl

        try:
            await self._redis.set(key, value, ex=ttl)  # type: ignore
            return True
        except Exception as e:
            logger.warning(f"Cache set failed for key '{key}': {e}")
            return False

    async def delete(self, key: str) -> bool:
        if not self._redis:
            await self.connect()

        try:
            result = await self._redis.delete(key)  # type: ignore
            res: bool = result > 0
            return res
        except Exception as e:
            logger.warning(f"Cache delete failed for key '{key}': {e}")
            return False

    async def exists(self, key: str) -> bool:
        if not self._redis:
            await self.connect()

        try:
            result = await self._redis.exists(key)  # type: ignore
            res: bool = result > 0
            return res
        except Exception as e:
            logger.warning(f"Cache exists check failed for key '{key}': {e}")
            return False

    async def get_json(self, key: str) -> Any | None:
        value = await self.get(key)
        if value:
            try:
                return json.loads(value)
            except json.JSONDecodeError:
                logger.warning(f"Failed to parse JSON for key '{key}'")
                return None
        return None

    async def set_json(self, key: str, value: Any, ttl: int | None = None) -> bool:
        try:
            json_str = json.dumps(value)
            return await self.set(key, json_str, ttl)
        except (TypeError, ValueError) as e:
            logger.warning(f"Failed to serialize JSON for key '{key}': {e}")
            return False

    def make_key(self, *parts: str) -> str:
        return ":".join(str(part) for part in parts)


_cache_service: CacheService | None = None


def get_cache_service(redis_url: str, default_ttl: int = 3600) -> CacheService:
    global _cache_service
    if _cache_service is None:
        _cache_service = CacheService(redis_url, default_ttl)
    return _cache_service
