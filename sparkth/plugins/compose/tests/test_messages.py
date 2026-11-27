"""Tests for reading text back out of chat messages.

Each reader is asserted against the same message shapes: a plain string, text blocks, blocks that are
not text at all.
"""

from sparkth.plugins.compose.messages import get_first_user_text, text_of
from sparkth.plugins.compose.schemas import ChatMessage


def _user_msg(text: str) -> ChatMessage:
    return ChatMessage(role="user", content=text)


def _assistant_msg(text: str) -> ChatMessage:
    return ChatMessage(role="assistant", content=text)


def _system_msg(text: str) -> ChatMessage:
    return ChatMessage(role="system", content=text)


def _block_msg(*texts: str) -> ChatMessage:
    """User message whose content is a list of text content blocks."""
    return ChatMessage(role="user", content=[{"type": "text", "text": t} for t in texts])


class TestTextOf:
    """Where the words are, decided once for every reader."""

    def test_string_content_is_returned_stripped(self) -> None:
        assert text_of(_user_msg("  Hello  ")) == "Hello"

    def test_text_blocks_are_joined(self) -> None:
        assert text_of(_block_msg("hello", "world")) == "hello world"

    def test_blocks_that_are_not_text_contribute_nothing(self) -> None:
        message = ChatMessage(
            role="user",
            content=[
                {"type": "image", "source": {"type": "base64", "data": ""}},
                {"type": "text", "text": "describe this"},
            ],
        )

        assert text_of(message) == "describe this"

    def test_a_turn_of_attachments_alone_has_no_text(self) -> None:
        """Not a guard: sending a document with no words is a real turn."""
        message = ChatMessage(role="user", content=[{"type": "document", "source": {"type": "base64", "data": ""}}])

        assert text_of(message) == ""


class TestGetFirstUserText:
    def test_returns_none_for_empty_list(self) -> None:
        assert get_first_user_text([]) is None

    def test_returns_none_when_no_user_message(self) -> None:
        assert get_first_user_text([_system_msg("sys"), _assistant_msg("hi")]) is None

    def test_returns_plain_string_content(self) -> None:
        assert get_first_user_text([_user_msg("Hello world")]) == "Hello world"

    def test_strips_surrounding_whitespace(self) -> None:
        assert get_first_user_text([_user_msg("  Hello  ")]) == "Hello"

    def test_skips_non_user_messages_before_first_user(self) -> None:
        msgs = [_system_msg("system"), _assistant_msg("hi"), _user_msg("question")]
        assert get_first_user_text(msgs) == "question"

    def test_returns_first_user_message_when_multiple_exist(self) -> None:
        msgs = [_user_msg("first"), _user_msg("second")]
        assert get_first_user_text(msgs) == "first"

    def test_extracts_text_from_content_blocks(self) -> None:
        assert get_first_user_text([_block_msg("block text")]) == "block text"

    def test_joins_multiple_text_blocks_with_space(self) -> None:
        assert get_first_user_text([_block_msg("hello", "world")]) == "hello world"

    def test_ignores_non_text_blocks(self) -> None:
        msg = ChatMessage(
            role="user",
            content=[
                {"type": "image", "source": {"type": "base64", "data": ""}},
                {"type": "text", "text": "describe this"},
            ],
        )
        assert get_first_user_text([msg]) == "describe this"

    def test_returns_none_for_empty_string_content(self) -> None:
        msg = ChatMessage(role="user", content=[{"type": "text", "text": "  "}])
        assert get_first_user_text([msg]) is None

    def test_returns_full_text_without_truncation(self) -> None:
        long_text = "word " * 100
        result = get_first_user_text([_user_msg(long_text)])
        assert result == long_text.strip()
