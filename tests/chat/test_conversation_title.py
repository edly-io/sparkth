from unittest.mock import AsyncMock, MagicMock, patch

from app.core_plugins.chat.conversation_title import (
    extract_title_from_messages,
    generate_conversation_title,
    get_first_user_text,
)
from app.core_plugins.chat.schemas import ChatMessage


def _user_msg(text: str) -> ChatMessage:
    return ChatMessage(role="user", content=text)


def _assistant_msg(text: str) -> ChatMessage:
    return ChatMessage(role="assistant", content=text)


def _system_msg(text: str) -> ChatMessage:
    return ChatMessage(role="system", content=text)


def _block_msg(*texts: str) -> ChatMessage:
    """User message whose content is a list of text content blocks."""
    return ChatMessage(
        role="user",
        content=[{"type": "text", "text": t} for t in texts],
    )


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


class TestExtractTitleFromMessages:
    def test_returns_none_for_empty_list(self) -> None:
        assert extract_title_from_messages([]) is None

    def test_returns_none_when_no_user_message(self) -> None:
        assert extract_title_from_messages([_assistant_msg("hi")]) is None

    def test_returns_short_message_unchanged(self) -> None:
        assert extract_title_from_messages([_user_msg("Short message")]) == "Short message"

    def test_returns_message_at_exact_limit_unchanged(self) -> None:
        text = "a" * 60
        assert extract_title_from_messages([_user_msg(text)], max_length=60) == text

    def test_truncates_long_message_at_word_boundary(self) -> None:
        # "word " * 15 = 75 chars — should cut before char 60 at a space
        text = "word " * 15
        result = extract_title_from_messages([_user_msg(text.strip())], max_length=60)
        assert result is not None
        assert result.endswith("...")
        assert len(result) <= 60 + len("...")

    def test_truncated_title_ends_with_ellipsis(self) -> None:
        text = "a" * 80
        result = extract_title_from_messages([_user_msg(text)])
        assert result is not None
        assert result.endswith("...")

    def test_no_trailing_space_before_ellipsis(self) -> None:
        text = "hello world this is a long sentence that goes well past sixty characters total"
        result = extract_title_from_messages([_user_msg(text)])
        assert result is not None
        assert not result.startswith(" ")
        assert "  " not in result

    def test_works_with_content_blocks(self) -> None:
        result = extract_title_from_messages([_block_msg("Short block text")])
        assert result == "Short block text"

    def test_uses_first_user_message(self) -> None:
        msgs = [_assistant_msg("hi"), _user_msg("first user"), _user_msg("second user")]
        assert extract_title_from_messages(msgs) == "first user"


class TestGenerateConversationTitle:
    """
    The function:
      1. Reads platform credentials from ChatSystemConfig — raises EnvironmentError if any are missing
      2. Calls provider.send_message with a title prompt
      3. Strips the response and persists via service.update_conversation_title
    """

    def _make_mocks(self, llm_response: str = "Debugging Async Session") -> tuple[MagicMock, MagicMock, AsyncMock]:
        mock_provider = MagicMock()
        mock_provider.send_message = AsyncMock(return_value={"content": llm_response})

        mock_service = MagicMock()
        mock_service.update_conversation_title = AsyncMock()

        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        return mock_provider, mock_service, mock_session

    def _make_sys_cfg(
        self,
        *,
        title_generation_provider: str = "anthropic",
        title_generation_api_key: str = "sk-ant-platform-key",
        title_generation_model: str = "claude-haiku-4-5",
    ) -> MagicMock:
        cfg = MagicMock()
        cfg.title_generation_provider = title_generation_provider
        cfg.title_generation_api_key = title_generation_api_key
        cfg.title_generation_model = title_generation_model
        return cfg

    async def _call(
        self,
        mock_provider: MagicMock,
        mock_service: MagicMock,
        mock_session: AsyncMock,
        *,
        conversation_id: int = 1,
        user_id: int = 42,
        first_user_message: str = "some message",
        sys_cfg: MagicMock | None = None,
    ) -> None:
        if sys_cfg is None:
            sys_cfg = self._make_sys_cfg()
        with (
            patch("app.core_plugins.chat.conversation_title.get_provider", return_value=mock_provider),
            patch("app.core_plugins.chat.conversation_title.AsyncSession", return_value=mock_session),
            patch(
                "app.core_plugins.chat.config.ChatSystemConfig",
                return_value=sys_cfg,
            ),
        ):
            await generate_conversation_title(
                conversation_id=conversation_id,
                user_id=user_id,
                first_user_message=first_user_message,
                service=mock_service,
            )

    async def test_calls_update_with_llm_title(self) -> None:
        mock_provider, mock_service, mock_session = self._make_mocks("Fix Async Bug")
        await self._call(
            mock_provider,
            mock_service,
            mock_session,
            conversation_id=1,
            first_user_message="How do I fix async session errors?",
        )

        mock_service.update_conversation_title.assert_awaited_once()
        call_kwargs = mock_service.update_conversation_title.call_args.kwargs
        assert call_kwargs["conversation_id"] == 1
        assert call_kwargs["title"] == "Fix Async Bug"

    async def test_strips_quotes_from_llm_response(self) -> None:
        mock_provider, mock_service, mock_session = self._make_mocks('"Quoted Title"')
        await self._call(mock_provider, mock_service, mock_session, conversation_id=2)

        call_kwargs = mock_service.update_conversation_title.call_args.kwargs
        assert call_kwargs["title"] == "Quoted Title"

    async def test_truncates_title_to_255_chars(self) -> None:
        mock_provider, mock_service, mock_session = self._make_mocks("w" * 300)
        await self._call(mock_provider, mock_service, mock_session, conversation_id=3)

        call_kwargs = mock_service.update_conversation_title.call_args.kwargs
        assert len(call_kwargs["title"]) == 255

    async def test_skips_update_when_llm_returns_empty_string(self) -> None:
        mock_provider, mock_service, mock_session = self._make_mocks("   ")
        await self._call(mock_provider, mock_service, mock_session, conversation_id=4)

        mock_service.update_conversation_title.assert_not_awaited()

    async def test_swallows_provider_exception(self) -> None:
        mock_provider = MagicMock()
        mock_provider.send_message = AsyncMock(side_effect=RuntimeError("API error"))
        mock_service = MagicMock()

        with (
            patch("app.core_plugins.chat.conversation_title.get_provider", return_value=mock_provider),
            patch(
                "app.core_plugins.chat.config.ChatSystemConfig",
                return_value=self._make_sys_cfg(),
            ),
        ):
            await generate_conversation_title(
                conversation_id=5,
                user_id=42,
                first_user_message="message",
                service=mock_service,
            )

    async def test_prompt_contains_first_user_message(self) -> None:
        mock_provider, mock_service, mock_session = self._make_mocks("Some Title")
        await self._call(
            mock_provider, mock_service, mock_session, conversation_id=6, first_user_message="explain gradient descent"
        )

        sent_messages = mock_provider.send_message.call_args.kwargs["messages"]
        assert any("explain gradient descent" in m["content"] for m in sent_messages)

    async def test_prompt_truncates_long_message_to_500_chars(self) -> None:
        mock_provider, mock_service, mock_session = self._make_mocks("Some Title")
        await self._call(mock_provider, mock_service, mock_session, conversation_id=7, first_user_message="x" * 1000)

        prompt_content = mock_provider.send_message.call_args.kwargs["messages"][0]["content"]
        assert "x" * 501 not in prompt_content
        assert "x" * 500 in prompt_content

    async def test_uses_platform_credentials(self) -> None:
        """Platform provider/key/model from config are forwarded to get_provider."""
        mock_provider, mock_service, mock_session = self._make_mocks("Platform Title")

        with (
            patch(
                "app.core_plugins.chat.conversation_title.get_provider",
                return_value=mock_provider,
            ) as mock_get_provider,
            patch("app.core_plugins.chat.conversation_title.AsyncSession", return_value=mock_session),
            patch(
                "app.core_plugins.chat.config.ChatSystemConfig",
                return_value=self._make_sys_cfg(
                    title_generation_provider="anthropic",
                    title_generation_api_key="sk-ant-platform-key",
                    title_generation_model="claude-haiku-4-5",
                ),
            ),
        ):
            await generate_conversation_title(
                conversation_id=8,
                user_id=42,
                first_user_message="some message",
                service=mock_service,
            )

        mock_get_provider.assert_called_once()
        call_kwargs = mock_get_provider.call_args.kwargs
        assert call_kwargs["provider_name"] == "anthropic"
        assert call_kwargs["api_key"] == "sk-ant-platform-key"
        assert call_kwargs["model"] == "claude-haiku-4-5"

    async def test_skips_quietly_when_platform_credentials_missing(self) -> None:
        """No exception is raised when config values are absent — background task fails silently."""
        mock_service = AsyncMock()

        with (
            patch("app.core_plugins.chat.conversation_title.get_provider") as mock_get_provider,
            patch(
                "app.core_plugins.chat.config.ChatSystemConfig",
                return_value=self._make_sys_cfg(
                    title_generation_provider="",
                    title_generation_api_key="",
                    title_generation_model="",
                ),
            ),
        ):
            await generate_conversation_title(
                conversation_id=9,
                user_id=42,
                first_user_message="some message",
                service=mock_service,
            )

        mock_get_provider.assert_not_called()
        mock_service.update_conversation_title.assert_not_awaited()
