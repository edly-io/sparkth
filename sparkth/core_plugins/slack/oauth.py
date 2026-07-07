"""Slack OAuth helpers for the TA Bot plugin."""

import urllib.parse
from functools import lru_cache
from typing import Any

import httpx
from itsdangerous import URLSafeTimedSerializer

from sparkth.core_plugins.slack.config import get_slack_settings
from sparkth.core_plugins.slack.constants import SLACK_AUTHORIZE_URL, SLACK_TOKEN_URL
from sparkth.lib.log import get_logger
from sparkth.lib.settings import get_settings

logger = get_logger(__name__)


@lru_cache
def _get_signer() -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(get_settings().SECRET_KEY, salt="slack-oauth-state")


def generate_state(user_id: int) -> str:
    return _get_signer().dumps({"user_id": user_id})


def decode_state(state: str) -> dict[str, int]:
    data: dict[str, int] = _get_signer().loads(state, max_age=get_slack_settings().state_max_age)
    return data


def generate_authorization_url(user_id: int, client_id: str, redirect_uri: str) -> str:
    params = {
        "client_id": client_id,
        "scope": ",".join(get_slack_settings().bot_scopes),
        "redirect_uri": redirect_uri,
        "state": generate_state(user_id),
    }
    return f"{SLACK_AUTHORIZE_URL}?{urllib.parse.urlencode(params)}"


async def exchange_code_for_tokens(
    code: str,
    client_id: str,
    client_secret: str,
    redirect_uri: str,
) -> dict[str, Any]:
    """Exchange an OAuth code for Slack tokens.

    Raises:
        httpx.HTTPStatusError: If Slack returns a non-2xx response.
        httpx.RequestError: If the request fails due to a network error.
        ValueError: If Slack returns ok=false in the response body.
    """
    async with httpx.AsyncClient() as http:
        response = await http.post(
            SLACK_TOKEN_URL,
            data={
                "code": code,
                "client_id": client_id,
                "client_secret": client_secret,
                "redirect_uri": redirect_uri,
            },
        )
    response.raise_for_status()
    data: dict[str, Any] = response.json()
    if not data.get("ok"):
        raise ValueError(f"Slack OAuth error: {data.get('error', 'unknown')}")
    return data
