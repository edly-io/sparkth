"""Slack Web API client for the TA Bot plugin."""

import hashlib
import hmac
import time
from types import TracebackType
from typing import Any, cast

import httpx

from sparkth.lib.log import get_logger
from sparkth.plugins.slack.config import get_slack_settings
from sparkth.plugins.slack.exceptions import SlackSignatureError

logger = get_logger(__name__)


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

    async def get_user_display_name(self, user_id: str) -> str | None:
        """Return the user's display_name (or real_name fallback). Returns None on any failure."""
        try:
            response = await self._client.get("/users.info", params={"user": user_id})
            response.raise_for_status()
            data = cast(dict[str, Any], response.json())
            if not data.get("ok"):
                return None
            profile = data.get("user", {}).get("profile", {})
            name = profile.get("display_name") or profile.get("real_name")
            if name is None:
                logger.warning("No display name or real_name found for user %s", user_id)
            return cast(str | None, name)
        except (httpx.HTTPStatusError, httpx.RequestError) as exc:
            logger.warning("Could not resolve display name for user %s: %s", user_id, exc)
            return None

    async def get_channel_name(self, channel_id: str) -> str | None:
        """Return the channel name without '#'. Returns 'DM' for DM channels, None on failure."""
        try:
            response = await self._client.get("/conversations.info", params={"channel": channel_id})
            response.raise_for_status()
            data = cast(dict[str, Any], response.json())
            if not data.get("ok"):
                return None
            channel = data.get("channel", {})
            if "name" in channel:
                return cast(str, channel["name"])
            if "user" in channel:
                return "DM"
            logger.warning("Unexpected channel shape for channel %s: %s", channel_id, list(channel.keys()))
            return None
        except (httpx.HTTPStatusError, httpx.RequestError) as exc:
            logger.warning("Could not resolve channel name for channel %s: %s", channel_id, exc)
            return None

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

        if abs(time.time() - ts) > get_slack_settings().max_timestamp_delta:
            raise SlackSignatureError("Request timestamp is too old — possible replay attack")

        try:
            body_str = raw_body.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise SlackSignatureError("Request body is not valid UTF-8") from exc
        base_string = f"v0:{timestamp}:{body_str}"
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
