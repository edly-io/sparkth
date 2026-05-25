"""Slack event parsing helpers for the TA Bot plugin."""

import re
from typing import Any

from app.core_plugins.slack.constants import GREETING_PATTERN


class SlackEventParser:
    """Parses and filters incoming Slack events for the TA Bot."""

    def is_greeting(self, text: str) -> bool:
        """Return True if text is a standalone greeting with no substantive question."""
        return bool(GREETING_PATTERN.match(text))

    def extract_question(self, text: str, bot_user_id: str) -> str:
        """Strip bot @-mention(s) from message text and return the cleaned question."""
        if not bot_user_id:
            return text.strip()
        return re.sub(rf"<@{re.escape(bot_user_id)}>", "", text).strip()

    def should_handle_event(self, event: dict[str, Any], bot_user_id: str) -> bool:
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


_parser = SlackEventParser()


def is_greeting(text: str) -> bool:
    return _parser.is_greeting(text)


def extract_question(text: str, bot_user_id: str) -> str:
    return _parser.extract_question(text, bot_user_id)


def should_handle_event(event: dict[str, Any], bot_user_id: str) -> bool:
    return _parser.should_handle_event(event, bot_user_id)
