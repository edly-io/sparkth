"""Slack event parsing helpers for the TA Bot plugin."""

import re
from typing import Any

from app.core_plugins.slack.constants import GREETING_PATTERN


def is_greeting(text: str) -> bool:
    """Return True if text is a standalone greeting with no substantive question."""
    return bool(GREETING_PATTERN.match(text))


def extract_question(text: str, bot_user_id: str) -> str:
    """Strip bot @-mention(s) from message text and return cleaned question."""
    if not bot_user_id:
        return text.strip()
    pattern = re.compile(rf"<@{re.escape(bot_user_id)}>")
    return pattern.sub("", text).strip()


def should_handle_event(event: dict[str, Any], bot_user_id: str) -> bool:
    """Return True if this Slack event should trigger a RAG response.

    Handles app_mention and DM messages. Ignores bot messages and subtypes.
    """
    if event.get("bot_id") or event.get("subtype"):
        return False
    event_type = event.get("type", "")
    if event_type == "app_mention":
        return True
    if event_type == "message" and event.get("channel_type") == "im":
        return True
    return False
