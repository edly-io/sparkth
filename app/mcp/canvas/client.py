from typing import Any, Optional, Type
from types import TracebackType
from urllib.parse import urljoin

import aiohttp

from app.mcp.request import request
from app.mcp.types import AuthenticationError


class CanvasClient:
    def __init__(self, api_url: str, api_token: str):
        self.api_url = api_url.rstrip("/")
        self.api_token = api_token
        self.session = aiohttp.ClientSession()

    async def __aenter__(self) -> CanvasClient:
        return self

    async def __aexit__(
        self,
        _exc_type: Optional[Type[BaseException]],
        _exc_val: Optional[BaseException],
        _exc_tb: Optional[TracebackType],
    ) -> None:
        await self.close()

    @staticmethod
    async def authenticate(new_api_url: str, new_api_token: str) -> int:
        async with aiohttp.ClientSession() as session:
            url = urljoin(new_api_url.rstrip("/") + "/", "users/self")
            headers = {"Authorization": f"Bearer {new_api_token}"}

            async with session.get(url, headers=headers) as response:
                if response.status != 200:
                    response_message = await response.json()
                    errors = response_message["errors"][0]["message"]
                    raise AuthenticationError(response.status, errors)
        return response.status

    async def get(self, endpoint: str) -> dict[str, Any]:
        return await self.request_bearer("get", endpoint)

    async def post(self, endpoint: str, payload: dict[str, Any]) -> dict[str, Any]:
        return await self.request_bearer("post", endpoint, payload)

    async def put(self, endpoint: str, payload: dict[str, Any]) -> dict[str, Any]:
        return await self.request_bearer("put", endpoint, payload)

    async def delete(self, endpoint: str) -> dict[str, Any]:
        return await self.request_bearer("delete", endpoint)

    async def request_bearer(
        self, method: str, endpoint: str, payload: Optional[dict[str, Any]] = None
    ) -> dict[str, Any]:
        if not self.api_token:
            raise AuthenticationError(401, "API Token not found")

        url = urljoin(self.api_url + "/", endpoint.lstrip("/"))
        return await request(
            method,
            url,
            self.session,
            token=self.api_token,
            payload=payload,
        )

    async def close(self) -> None:
        if self.session and not self.session.closed:
            await self.session.close()
