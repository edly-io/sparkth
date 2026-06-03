"""Unit tests for Slack event parsing helpers."""

from app.core_plugins.slack.events import extract_question, is_greeting, should_handle_event


class TestExtractQuestion:
    def test_strips_bot_mention(self) -> None:
        text = "<@U_BOT_ID> what is recursion?"
        assert extract_question(text, "U_BOT_ID") == "what is recursion?"

    def test_no_mention_passes_through(self) -> None:
        text = "what is recursion?"
        assert extract_question(text, "U_BOT_ID") == "what is recursion?"

    def test_strips_leading_trailing_whitespace(self) -> None:
        text = "  <@U_BOT_ID>   hello   "
        assert extract_question(text, "U_BOT_ID") == "hello"

    def test_multiple_mentions_stripped(self) -> None:
        text = "<@U_BOT_ID> hey <@U_BOT_ID> question"
        assert extract_question(text, "U_BOT_ID") == "hey  question"

    def test_empty_bot_user_id_returns_stripped_text(self) -> None:
        text = "  what is recursion?  "
        assert extract_question(text, "") == "what is recursion?"


class TestShouldHandleEvent:
    def test_app_mention_is_handled(self) -> None:
        event = {"type": "app_mention", "text": "<@BOT> hi", "user": "U_STUDENT"}
        assert should_handle_event(event, "BOT") is True

    def test_direct_message_is_handled(self) -> None:
        event = {"type": "message", "channel_type": "im", "text": "hi", "user": "U_STUDENT"}
        assert should_handle_event(event, "BOT") is True

    def test_channel_message_is_ignored(self) -> None:
        event = {"type": "message", "channel_type": "channel", "text": "hi", "user": "U_STUDENT"}
        assert should_handle_event(event, "BOT") is False

    def test_bot_message_is_ignored(self) -> None:
        event = {"type": "app_mention", "bot_id": "B123", "text": "hi"}
        assert should_handle_event(event, "BOT") is False

    def test_message_with_subtype_is_ignored(self) -> None:
        event = {"type": "message", "channel_type": "im", "subtype": "message_deleted"}
        assert should_handle_event(event, "BOT") is False

    def test_unknown_event_type_is_ignored(self) -> None:
        event = {"type": "reaction_added", "user": "U_STUDENT"}
        assert should_handle_event(event, "BOT") is False


class TestIsGreeting:
    def test_hi_is_greeting(self) -> None:
        assert is_greeting("hi") is True

    def test_hello_is_greeting(self) -> None:
        assert is_greeting("hello") is True

    def test_hey_is_greeting(self) -> None:
        assert is_greeting("hey there") is True

    def test_greeting_case_insensitive(self) -> None:
        assert is_greeting("Hello!") is True

    def test_greeting_with_punctuation(self) -> None:
        assert is_greeting("hi!") is True

    def test_greeting_with_multiple_punctuation(self) -> None:
        assert is_greeting("hi!!") is True

    def test_substantive_question_is_not_greeting(self) -> None:
        assert is_greeting("what is recursion?") is False

    def test_empty_string_is_not_greeting(self) -> None:
        assert is_greeting("") is False

    def test_greeting_prefix_in_question_is_not_greeting(self) -> None:
        assert is_greeting("hello, what is a for loop?") is False
