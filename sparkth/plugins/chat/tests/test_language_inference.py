"""The chat assistant infers its output language from the conversation.

Three things need pinning: the wording of the OUTPUT LANGUAGE directive, which is the
only place the rule is expressed; the absence of any injected language on the live
route; and the absence of any language kwarg forwarded to the scheduled title-generation
task. Template rendering in isolation is covered by test_prompt.py.

The mock stack mirrors test_rag_search_integration.py, which drives the same route.
"""

import json
from typing import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock, patch

from httpx import AsyncClient
from sqlmodel.ext.asyncio.session import AsyncSession

from sparkth.lib.encryption import get_encryption_service
from sparkth.lib.language import SUPPORTED_LANGUAGES
from sparkth.lib.models import LLMConfig, User
from sparkth.lib.settings import get_settings
from sparkth.plugins.chat.models import Conversation
from sparkth.plugins.chat.prompt import get_learning_design_system_prompt


class _Seeded:
    def __init__(self, llm_config_id: int, conversation_uuid: str) -> None:
        self.llm_config_id = llm_config_id
        self.conversation_uuid = conversation_uuid


async def _seed(session: AsyncSession, user_id: int) -> _Seeded:
    """An active LLM config plus an existing conversation.

    Posting into the existing conversation keeps a reply-language assertion off the
    new-conversation path, which also schedules title generation. Callers that assert on
    title scheduling instead post with no conversation_id, taking that path on purpose,
    and only use the LLM config from this seed.
    """
    settings = get_settings()
    encryption = get_encryption_service(settings.LLM_ENCRYPTION_KEY)
    llm_config = LLMConfig(
        user_id=user_id,
        name="test-cfg-language",
        provider="openai",
        model="gpt-4o",
        encrypted_key=encryption.encrypt("sk-test"),
        masked_key="sk-***",
        is_active=True,
    )
    session.add(llm_config)
    await session.flush()
    llm_config_id = llm_config.id or 0  # capture before expiry

    conversation = Conversation(
        user_id=user_id,
        provider="openai",
        model="gpt-4o",
        llm_config_id=llm_config_id,
    )
    session.add(conversation)
    await session.flush()
    conversation_uuid = str(conversation.uuid)
    await session.commit()
    return _Seeded(llm_config_id, conversation_uuid)


async def _fake_stream() -> AsyncGenerator[str, None]:
    yield f"data: {json.dumps({'done': True})}\n\n"


def _other_supported_language_names(excluding_tag: str) -> set[str]:
    """Names of every supported language other than ``excluding_tag``.

    Backs a negative control for the fallback test: the template's OUTPUT LANGUAGE
    section also carries the unconditional literal "...not a literal translation of
    English phrasing", so asserting only that the expected language's name is present
    cannot tell the true default apart from some other valid tag landing here by
    mistake. Asserting that none of these names appear catches that.
    """
    return {info.name for tag, info in SUPPORTED_LANGUAGES.items() if tag != excluding_tag}


async def _system_prompt_for_one_request(client: AsyncClient, seed: _Seeded) -> str:
    """Send one completion request; return the system prompt handed to the provider."""
    with (
        patch("sparkth.plugins.chat.routes.completions.get_provider") as mock_get_provider,
        patch("sparkth.plugins.chat.routes.completions.MessageScopeClassifier") as mock_classifier_cls,
        patch("sparkth.plugins.chat.service.ChatService.add_message", new_callable=AsyncMock) as mock_add_message,
        patch(
            "sparkth.plugins.chat.service.ChatService.get_conversation_messages",
            new_callable=AsyncMock,
            return_value=[],
        ),
        patch(
            "sparkth.plugins.chat.service.ChatService.list_conversation_attachments",
            new_callable=AsyncMock,
            return_value=[],
        ),
        patch("sparkth.plugins.chat.routes.completions.ChatStreamProcessor") as mock_processor_cls,
    ):
        mock_classifier = MagicMock()
        mock_classifier.in_scope = AsyncMock(return_value=True)
        mock_classifier_cls.return_value = mock_classifier

        mock_message = MagicMock()
        mock_message.id = 1
        mock_add_message.return_value = mock_message

        mock_provider = MagicMock()
        mock_provider.system_prompt = ""
        mock_provider.create_llm.return_value = MagicMock()
        mock_get_provider.return_value = mock_provider

        mock_processor = MagicMock()
        mock_processor.stream.return_value = _fake_stream()
        mock_processor_cls.return_value = mock_processor

        response = await client.post(
            "/api/v1/chat/completions",
            json={
                "llm_config_id": seed.llm_config_id,
                "messages": [{"role": "user", "content": "Create a course on data privacy"}],
                "conversation_id": seed.conversation_uuid,
                "stream": True,
                "tools": "none",
            },
        )

    assert response.status_code == 200
    return str(mock_get_provider.call_args.kwargs["system_prompt"])


async def _scheduled_title_task_kwargs(client: AsyncClient, llm_config_id: int) -> dict[str, object]:
    """Send one completion request with no conversation_id, so a new conversation is
    created and title generation is scheduled; return the kwargs the scheduled task
    was called with.

    ``ChatService.create_conversation`` is deliberately left unpatched — it is what
    creates the conversation and triggers scheduling in the first place.
    """
    with (
        patch("sparkth.plugins.chat.routes.completions.get_provider") as mock_get_provider,
        patch("sparkth.plugins.chat.routes.completions.MessageScopeClassifier") as mock_classifier_cls,
        patch("sparkth.plugins.chat.service.ChatService.add_message", new_callable=AsyncMock) as mock_add_message,
        patch(
            "sparkth.plugins.chat.service.ChatService.get_conversation_messages",
            new_callable=AsyncMock,
            return_value=[],
        ),
        patch(
            "sparkth.plugins.chat.service.ChatService.list_conversation_attachments",
            new_callable=AsyncMock,
            return_value=[],
        ),
        patch("sparkth.plugins.chat.routes.completions.ChatStreamProcessor") as mock_processor_cls,
        patch("sparkth.plugins.chat.conversation_title.generate_conversation_title") as mock_generate_title,
    ):
        mock_classifier = MagicMock()
        mock_classifier.in_scope = AsyncMock(return_value=True)
        mock_classifier_cls.return_value = mock_classifier

        mock_message = MagicMock()
        mock_message.id = 1
        mock_add_message.return_value = mock_message

        mock_provider = MagicMock()
        mock_provider.system_prompt = ""
        mock_provider.create_llm.return_value = MagicMock()
        mock_get_provider.return_value = mock_provider

        mock_processor = MagicMock()
        mock_processor.stream.return_value = _fake_stream()
        mock_processor_cls.return_value = mock_processor

        response = await client.post(
            "/api/v1/chat/completions",
            json={
                "llm_config_id": llm_config_id,
                "messages": [{"role": "user", "content": "Create a course on data privacy"}],
                "stream": True,
                "tools": "none",
            },
        )

    assert response.status_code == 200
    mock_generate_title.assert_called_once()
    return dict(mock_generate_title.call_args.kwargs)


class TestOutputLanguageDirective:
    """The directive is the whole mechanism — there is no resolved tag behind it."""

    def test_instructs_following_the_latest_user_message(self) -> None:
        assert "same language as the user's most recent message" in get_learning_design_system_prompt()

    def test_instructs_switching_when_the_user_switches(self) -> None:
        assert "change with them from that message onward" in get_learning_design_system_prompt()

    def test_honours_an_explicit_request_for_another_course_language(self) -> None:
        """A user writing in one language may ask for the course in another. This
        sentence is the only expression of that rule — no data field carries it."""
        assert "honour that request for the course content" in get_learning_design_system_prompt()

    def test_pins_no_specific_language(self) -> None:
        """No language name may be injected, and no placeholder may survive.

        "English" is excluded from the check deliberately: the directive keeps the
        clause "not a literal translation of English phrasing", so that one name
        appears unconditionally. The remaining names are the discriminating ones — if
        any of them is present, something is still resolving and injecting a tag.
        """
        prompt = get_learning_design_system_prompt()
        assert "{language_name}" not in prompt
        injectable = {info.name for info in SUPPORTED_LANGUAGES.values() if info.name != "English"}
        assert not any(name in prompt for name in injectable)


class TestNoStoredPreferenceReachesThePrompt:
    """The `current_user` fixture overrides the auth dependency with an in-memory User,
    so setting `.language` on it is the whole of "the user chose this language"."""

    async def test_stored_language_does_not_reach_the_system_prompt(
        self,
        client: AsyncClient,
        current_user: User,
        session: AsyncSession,
    ) -> None:
        seed = await _seed(session, current_user.id or 1)
        current_user.language = "es"

        prompt = await _system_prompt_for_one_request(client, seed)

        assert not any(name in prompt for name in _other_supported_language_names("en"))


class TestTitleSchedulingCarriesNoLanguage:
    """get_or_create_conversation forwards kwargs into background_tasks.add_task, which
    is typed as a bare Callable — mypy cannot check them against the task's signature,
    so a stale `language=` kwarg would only surface at runtime, inside a background task
    whose exceptions are swallowed and logged. This test is the only guard."""

    async def test_scheduled_title_task_receives_no_language(
        self,
        client: AsyncClient,
        current_user: User,
        session: AsyncSession,
    ) -> None:
        seed = await _seed(session, current_user.id or 1)
        current_user.language = "es"

        kwargs = await _scheduled_title_task_kwargs(client, seed.llm_config_id)

        assert "language" not in kwargs
