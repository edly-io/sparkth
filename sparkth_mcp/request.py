from enum import Enum
import json
import aiohttp
from .types import LMSError


class Auth(str, Enum):
    JWT = "Jwt"
    BEARER = "Bearer"


async def request(
    url: str,
    auth: Auth,
    token: str,
    method: str = "GET",
    params=None,
    payload=None,
    client: aiohttp.ClientSession = None,
) -> json:
    if client is None:
        raise ValueError("ClientSession instance is required.")

    headers = {
        "Authorization": f"{auth.value} {token}",
        "Accept": "application/json",
        "Content-Type": "application/json",
    }

    async with client.request(
        method, url, headers=headers, params=params, json=payload
    ) as response:
        if response.status < 200 or response.status >= 300:
            raise await handle_error_response(response)

        text = await response.text()
        if not text.strip():
            return {}

        try:
            json_value = await response.json()
        except aiohttp.ContentTypeError as e:
            raise LMSError(response.status, e.message)

        return json_value


async def handle_error_response(response: aiohttp.ClientResponse) -> LMSError:
    try:
        text = await response.text()
    except aiohttp.ClientPayloadError:
        text = ""

    message = text
    try:
        json_val = await response.json()
        if isinstance(json_val, dict) and "message" in json_val:
            message = json_val["message"]
    except aiohttp.ContentTypeError:
        pass

    return LMSError(response.status, message)
