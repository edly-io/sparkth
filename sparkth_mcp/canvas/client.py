import json
import aiohttp
from urllib.parse import urljoin
from ..types import AuthenticationError
from ..request import Auth, request


class CanvasClient:
    def __init__(self, api_url: str, api_token: str):
        self.api_url = api_url.rstrip("/")
        self.api_token = api_token
        self.session = aiohttp.ClientSession()

    @staticmethod
    async def authenticate(new_api_url: str, new_api_token: str) -> bool:
        async with aiohttp.ClientSession() as session:
            url = urljoin(new_api_url.rstrip("/") + "/", "users/self")
            headers = {"Authorization": f"Bearer {new_api_token}"}

            async with session.get(url, headers=headers) as response:
                if response.status == 200:
                    return True
                raise AuthenticationError()
        return False

    async def request_bearer(
        self, http_method: str, endpoint: str, payload=None
    ) -> json:
        if not self.api_token:
            raise AuthenticationError("API Token not found")

        url = urljoin(self.api_url + "/", endpoint.lstrip("/"))

        print("url = ", url)

        return await request(
            auth=Auth.BEARER,
            token=self.api_token,
            http_method=http_method,
            url=url,
            params=None,
            payload=payload,
            client=self.session,
        )

    async def close(self):
        await self.session.close()
