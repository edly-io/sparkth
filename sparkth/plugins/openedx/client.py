import json
from typing import Any

from pydantic import ValidationError

from sparkth.lib.auth import current_user_id
from sparkth.lib.cache import CacheService, get_cache_service
from sparkth.lib.enums import Auth, Method
from sparkth.lib.exceptions import AuthenticationError, LMSRequestError
from sparkth.lib.http import BaseHttpClient
from sparkth.lib.log import get_logger
from sparkth.lib.settings import get_settings
from sparkth.plugins.openedx.config import OpenEdxConfig
from sparkth.plugins.openedx.constants import (
    OPENEDX_ACCESS_TOKEN_CACHE_PREFIX,
    OPENEDX_ACCESS_TOKEN_TTL_MARGIN_SECONDS,
)
from sparkth.plugins.openedx.schemas import TokenResponse

logger = get_logger(__name__)


def access_token_cache(user_id: int) -> tuple[CacheService, str]:
    """Return the shared cache and the cache key of ``user_id``'s Open edX access token."""
    settings = get_settings()
    cache = get_cache_service(settings.REDIS_URL, settings.REDIS_KEY_TTL)
    return cache, cache.make_key(OPENEDX_ACCESS_TOKEN_CACHE_PREFIX, str(user_id))


class OpenEdxClient(BaseHttpClient):
    """HTTP client for the Open edX LMS and Studio REST APIs.

    Built from the user's stored ``OpenEdxConfig``. It grants its own access token with the
    configured credentials on first use and caches it per Sparkth user, so the token is shared
    by that user's later calls and never reaches the model. A 401 drops the cached token and the
    request is retried once with a fresh one. The cache key comes from ``current_user_id()``, so
    the client is only used inside tool calls, where a user is already bound.
    """

    def __init__(self, config: OpenEdxConfig) -> None:
        super().__init__(str(config.lms_url), Auth.JWT)
        self.config = config
        self.client_id = "login-service-client-id"
        self.access_token: str | None = None

    @property
    def studio_url(self) -> str:
        """The Studio base URL from the stored settings, without a trailing slash."""
        return str(self.config.studio_url).rstrip("/")

    @property
    def token(self) -> str | None:
        return self.access_token

    async def get_token(self) -> TokenResponse:
        """Exchange the configured username/password for a JWT via the OAuth2 password grant."""
        auth_url = f"{self.base_url}/oauth2/access_token"
        form = {
            "client_id": self.client_id,
            "grant_type": "password",
            "token_type": "jwt",
            "username": self.config.lms_username,
            "password": self.config.lms_password,
        }

        async with self.session.post(auth_url, data=form) as resp:
            if resp.status >= 300:
                raise await self._handle_error_response(Method.POST, auth_url, resp)

            text = await resp.text()
            try:
                data = json.loads(text)
            except json.JSONDecodeError as e:
                raise LMSRequestError(
                    Method.POST, auth_url, resp.status, "Expected JSON from the token endpoint"
                ) from e

        try:
            token_response = TokenResponse.model_validate(data)
        except ValidationError as e:
            # Log only where each field failed; the error's input holds the token response.
            problems = [(".".join(map(str, err["loc"])), err["type"]) for err in e.errors()]
            logger.warning(f"Open edX token response from {auth_url} has an unexpected shape: {problems}")
            raise LMSRequestError(Method.POST, auth_url, 200, "Unexpected token response shape") from None

        if not token_response.access_token.strip():
            raise AuthenticationError(401, "empty access_token")

        return token_response

    async def _load_token(self) -> None:
        """Use the user's cached token, or grant one and cache it.

        The cache entry expires a margin before the token does, or after the cache default TTL
        when Open edX reports no expiry.
        """
        cache, key = access_token_cache(current_user_id())
        cached = await cache.get(key)
        if cached:
            self.access_token = cached
            return

        granted = await self.get_token()
        ttl = None
        if granted.expires_in is not None:
            ttl = max(granted.expires_in - OPENEDX_ACCESS_TOKEN_TTL_MARGIN_SECONDS, 1)
        await cache.set(key, granted.access_token, ttl)
        self.access_token = granted.access_token

    async def _request_dict(
        self,
        method: Method,
        endpoint: str,
        *,
        base_url: str | None = None,
        params: dict[str, Any] | None = None,
        payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Call ``_request`` with the user's token and assert the response is a JSON object.

        A 401 drops the cached token, grants a new one and retries once; a second 401 propagates.
        """
        if self.access_token is None:
            await self._load_token()
        try:
            result = await self._request(method, endpoint, base_url=base_url, params=params, payload=payload)
        except LMSRequestError as e:
            if e.status_code != 401:
                raise
            user_id = current_user_id()
            logger.warning(f"Open edX rejected the token for {method} {endpoint} (user {user_id}); granting a new one")
            cache, key = access_token_cache(user_id)
            await cache.delete(key)
            await self._load_token()
            result = await self._request(method, endpoint, base_url=base_url, params=params, payload=payload)
        if not isinstance(result, dict):
            raise ValueError(f"Expected JSON object from {method} {endpoint}, got {type(result).__name__}")
        return result

    async def authenticate(self) -> dict[str, Any]:
        """Return the authenticated user's profile from the LMS user API."""
        return await self._request_dict(Method.GET, "api/user/v1/me")

    async def get(self, base_url: str, endpoint: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        """Send a GET request to ``base_url/endpoint`` and return the response as a JSON object."""
        return await self._request_dict(Method.GET, endpoint, base_url=base_url, params=params)

    async def post(self, base_url: str, endpoint: str, payload: dict[str, Any]) -> dict[str, Any]:
        """Send a POST request with a JSON body to ``base_url/endpoint`` and return the response as a JSON object."""
        return await self._request_dict(Method.POST, endpoint, base_url=base_url, payload=payload)

    async def put(self, base_url: str, endpoint: str, payload: dict[str, Any]) -> dict[str, Any]:
        """Send a PUT request with a JSON body to ``base_url/endpoint`` and return the response as a JSON object."""
        return await self._request_dict(Method.PUT, endpoint, base_url=base_url, payload=payload)

    async def patch(self, base_url: str, endpoint: str, payload: dict[str, Any]) -> dict[str, Any]:
        """Send a PATCH request with a JSON body to ``base_url/endpoint`` and return the response as a JSON object."""
        return await self._request_dict(Method.PATCH, endpoint, base_url=base_url, payload=payload)

    async def delete(self, base_url: str, endpoint: str) -> dict[str, Any]:
        """Send a DELETE request to ``base_url/endpoint`` and return the response as a JSON object."""
        return await self._request_dict(Method.DELETE, endpoint, base_url=base_url)
