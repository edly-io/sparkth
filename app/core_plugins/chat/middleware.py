import time
from typing import Callable

from fastapi import HTTPException, Request, Response, status
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.logger import get_logger
from app.core_plugins.chat.cache import CacheService

logger = get_logger(__name__)


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(
        self,
        app: Callable,
        cache_service: CacheService,
        requests_per_minute: int = 60,
        chat_requests_per_minute: int = 10,
    ):
        super().__init__(app)
        self.cache = cache_service
        self.general_limit = requests_per_minute
        self.chat_limit = chat_requests_per_minute

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        if not request.url.path.startswith("/api/v1/chat"):
            return await call_next(request)

        user_id = getattr(request.state, "user_id", None)
        
        if not user_id:
            return await call_next(request)

        is_chat_endpoint = "/completions" in request.url.path
        limit = self.chat_limit if is_chat_endpoint else self.general_limit

        await self._check_rate_limit(user_id, limit, is_chat_endpoint)

        response = await call_next(request)
        return response

    async def _check_rate_limit(self, user_id: int, limit: int, is_chat: bool = False) -> None:
        endpoint_type = "chat" if is_chat else "general"
        cache_key = self.cache.make_key("rate_limit", str(user_id), endpoint_type)

        current_minute = int(time.time() / 60)
        window_key = f"{cache_key}:{current_minute}"

        count_str = await self.cache.get(window_key)
        count = int(count_str) if count_str else 0

        if count >= limit:
            logger.warning(f"Rate limit exceeded for user {user_id} (endpoint: {endpoint_type}, limit: {limit})")
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Rate limit exceeded. Max {limit} requests per minute.",
                headers={"Retry-After": "60"},
            )

        await self.cache.set(window_key, str(count + 1), ttl=60)


def create_rate_limit_middleware(
    cache_service: CacheService,
    requests_per_minute: int = 60,
    chat_requests_per_minute: int = 10,
) -> type[RateLimitMiddleware]:
    class ConfiguredRateLimitMiddleware(RateLimitMiddleware):
        def __init__(self, app: Callable):
            super().__init__(
                app,
                cache_service,
                requests_per_minute,
                chat_requests_per_minute,
            )

    return ConfiguredRateLimitMiddleware
