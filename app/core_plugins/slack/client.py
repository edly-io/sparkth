"""Slack Web API client for the TA Bot plugin."""

import hashlib
import hmac
import time
from types import TracebackType
from typing import Any, cast

import httpx

from app.core.logger import get_logger

logger = get_logger(__name__)

_MAX_TIMESTAMP_DELTA = 60 * 5  # 5 minutes


class SlackSignatureError(Exception):
    """Raised when a Slack request signature cannot be verified."""


class SlackClient:
    """Async context-manager wrapper around the Slack Web API."""

    def __init__(self, bot_token: str) -> None:
        self._bot_token = bot_token
        self._http: httpx.AsyncClient | None = None

    async def __aenter__(self) -> "SlackClient":
        self._http = httpx.AsyncClient(
            base_url="https://slack.com/api",
            headers={"Authorization": f"Bearer {self._bot_token}"},
            timeout=10.0,
        )
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        if self._http is not None:
            await self._http.aclose()

    @property
    def _client(self) -> httpx.AsyncClient:
        if self._http is None:
            raise RuntimeError("SlackClient must be used as an async context manager")
        return self._http

    async def post_message(self, channel: str, text: str, thread_ts: str | None = None) -> dict[str, Any]:
        payload: dict[str, Any] = {"channel": channel, "text": text}
        if thread_ts:
            payload["thread_ts"] = thread_ts
        response = await self._client.post("/chat.postMessage", json=payload)
        response.raise_for_status()
        return cast(dict[str, Any], response.json())

    async def auth_test(self) -> dict[str, Any]:
        response = await self._client.post("/auth.test")
        response.raise_for_status()
        return cast(dict[str, Any], response.json())

    @staticmethod
    def verify_signature(
        signing_secret: str,
        timestamp: str,
        raw_body: bytes,
        slack_signature: str,
    ) -> None:
        try:
            ts = int(timestamp)
        except ValueError as exc:
            raise SlackSignatureError("Invalid timestamp header") from exc

        if abs(time.time() - ts) > _MAX_TIMESTAMP_DELTA:
            raise SlackSignatureError("Request timestamp is too old — possible replay attack")

        base_string = f"v0:{timestamp}:{raw_body.decode('utf-8')}"
        expected = (
            "v0="
            + hmac.new(
                signing_secret.encode("utf-8"),
                base_string.encode("utf-8"),
                hashlib.sha256,
            ).hexdigest()
        )

        if not hmac.compare_digest(expected, slack_signature):
            raise SlackSignatureError("Slack signature mismatch")
