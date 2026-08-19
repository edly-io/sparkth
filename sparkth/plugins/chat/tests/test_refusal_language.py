"""The out-of-scope refusal reaches the user in a language they can read.

Two paths emit it and they are not symmetric. The model is handed the English source and
told by the system prompt to send it in the language of the conversation. On the
deterministic paths — the keyword pre-filter and classifier refusals streamed or persisted
straight from Python — the backend writes the refusal sentence itself rather than a model
generating it, so it renders under the request locale (``gettext``) rather than the
conversation's language.

The shipped catalogs are detached for the test session, so the Spanish assertion injects its
own single-message catalog rather than reading sparkth/locale/es.
"""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient
from sqlmodel.ext.asyncio.session import AsyncSession

from sparkth.core.i18n import locale_context
from sparkth.lib.encryption import get_encryption_service
from sparkth.lib.i18n import gettext
from sparkth.lib.models import LLMConfig, User
from sparkth.lib.settings import get_settings
from sparkth.lib.testing import AddTranslation
from sparkth.plugins.chat.models import Conversation
from sparkth.plugins.chat.prompt import REFUSAL_MESSAGE, get_learning_design_system_prompt
from sparkth.plugins.chat.routes.utils import stream_out_of_scope_refusal

SPANISH = (
    "Soy un asistente de creación de cursos y solo puedo ayudarte a diseñar y crear "
    "cursos. ¿Hay algún curso que te gustaría crear?"
)


async def _seed_llm_config(session: AsyncSession, user_id: int) -> int:
    """Create an active LLMConfig in the DB and return its id.

    Mirrors the helper in test_scope_validation.py — kept local rather than imported so
    this file stays a self-contained unit, matching test_language_inference.py's
    convention of a private per-file seeding helper."""
    settings = get_settings()
    encryption = get_encryption_service(settings.LLM_ENCRYPTION_KEY)
    llm_config = LLMConfig(
        user_id=user_id,
        name="test-cfg-refusal-language",
        provider="openai",
        model="gpt-4o",
        encrypted_key=encryption.encrypt("sk-test"),
        masked_key="sk-***",
        is_active=True,
    )
    session.add(llm_config)
    await session.flush()
    llm_config_id = llm_config.id or 0
    await session.commit()
    return llm_config_id


class TestRefusalIsMarked:
    def test_source_is_a_plain_string(self) -> None:
        """gettext_noop returns the str unchanged, so it can be substituted into the
        prompt template, json.dumps'd onto the SSE stream and assigned to a pydantic
        field — none of which a LazyString allows."""
        assert isinstance(REFUSAL_MESSAGE, str)

    def test_translates_under_a_non_default_locale(self, translation_catalog: AddTranslation) -> None:
        translation_catalog(REFUSAL_MESSAGE, SPANISH)
        with locale_context("es"):
            assert gettext(REFUSAL_MESSAGE) == SPANISH

    def test_untranslated_with_no_catalog(self) -> None:
        """No catalog registered, so the source falls through — this is what proves the
        previous test is observing a real lookup rather than a coincidence."""
        with locale_context("es"):
            assert gettext(REFUSAL_MESSAGE) == REFUSAL_MESSAGE


class TestRefusalInTheSystemPrompt:
    def test_english_source_reaches_the_model(self, translation_catalog: AddTranslation) -> None:
        """The model translates from a stable source, so the prompt carries the English
        source even under a non-default locale — not the locale-rendered string."""
        translation_catalog(REFUSAL_MESSAGE, SPANISH)
        with locale_context("es"):
            prompt = get_learning_design_system_prompt()
        assert REFUSAL_MESSAGE in prompt
        assert SPANISH not in prompt

    def test_model_is_told_to_send_it_in_the_conversation_language(self) -> None:
        assert "Send it in the language of the conversation" in get_learning_design_system_prompt()


class TestRefusalAtTheStreamingRenderSite:
    """stream_out_of_scope_refusal has no model in the loop, so it renders under the
    request locale via gettext() rather than the conversation language."""

    @pytest.mark.asyncio
    async def test_streamed_refusal_translates_under_a_non_default_locale(
        self, translation_catalog: AddTranslation
    ) -> None:
        """Parse the SSE payload rather than substring-matching the raw chunk: json.dumps
        escapes non-ASCII by default, so the Spanish text never appears literally on the
        wire even when the render site is translating correctly."""
        translation_catalog(REFUSAL_MESSAGE, SPANISH)
        with locale_context("es"):
            chunks = [chunk async for chunk in stream_out_of_scope_refusal()]
        payload = json.loads(chunks[0].removeprefix("data: ").strip())
        assert payload["content"] == SPANISH


class TestRefusalAtTheNonStreamingRenderSites:
    """The non-streaming branches of chat_completion render the refusal with gettext()
    too, independently of the streaming generator covered above. Both are reached with
    stream=False: no conversation_id takes the pre-conversation return, an existing
    conversation_id takes the persisted-then-returned branch."""

    @pytest.mark.asyncio
    async def test_no_conversation_refusal_translates(
        self,
        client: AsyncClient,
        current_user: User,
        session: AsyncSession,
        translation_catalog: AddTranslation,
    ) -> None:
        """No conversation_id + stream=False returns the refusal directly in the JSON
        body, before any conversation is created — the earliest render site."""
        translation_catalog(REFUSAL_MESSAGE, SPANISH)
        llm_config_id = await _seed_llm_config(session, current_user.id or 1)

        with (
            locale_context("es"),
            patch("sparkth.plugins.chat.routes.utils.is_query_in_scope", return_value=False),
        ):
            response = await client.post(
                "/api/v1/chat/completions",
                json={
                    "llm_config_id": llm_config_id,
                    "messages": [{"role": "user", "content": "what is 2+2?"}],
                    "stream": False,
                    "tools": "none",
                },
            )

        assert response.status_code == 200
        assert response.json()["message"]["content"] == SPANISH

    @pytest.mark.asyncio
    async def test_existing_conversation_refusal_translates_both_persisted_and_returned(
        self,
        client: AsyncClient,
        current_user: User,
        session: AsyncSession,
        translation_catalog: AddTranslation,
    ) -> None:
        """An existing conversation_id + stream=False renders the refusal twice: once
        persisted via service.add_message, once returned in the JSON body. Each call is
        a separate gettext() invocation, so this asserts both independently rather than
        trusting one to imply the other."""
        translation_catalog(REFUSAL_MESSAGE, SPANISH)
        llm_config_id = await _seed_llm_config(session, current_user.id or 1)

        conv = Conversation(
            user_id=current_user.id or 1,
            provider="openai",
            model="gpt-4o",
            llm_config_id=llm_config_id,
        )
        session.add(conv)
        await session.flush()
        conv_uuid = str(conv.uuid)
        await session.commit()

        mock_msg = MagicMock()
        mock_msg.id = 99

        with (
            locale_context("es"),
            patch("sparkth.plugins.chat.routes.completions.get_provider"),
            patch("sparkth.plugins.chat.routes.utils.is_query_in_scope", return_value=False),
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
            patch(
                "sparkth.plugins.chat.service.ChatService.add_message",
                new_callable=AsyncMock,
                return_value=mock_msg,
            ) as mock_add_msg,
        ):
            response = await client.post(
                "/api/v1/chat/completions",
                json={
                    "llm_config_id": llm_config_id,
                    "messages": [{"role": "user", "content": "what is 2+2?"}],
                    "conversation_id": conv_uuid,
                    "stream": False,
                    "tools": "none",
                },
            )

        assert response.status_code == 200
        assert response.json()["message"]["content"] == SPANISH

        assistant_calls = [c for c in mock_add_msg.call_args_list if c.kwargs.get("role") == "assistant"]
        assert len(assistant_calls) == 1
        assert assistant_calls[0].kwargs["content"] == SPANISH
