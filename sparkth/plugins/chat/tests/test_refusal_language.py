"""The out-of-scope refusal reaches the user in a language they can read.

Two paths emit it and they are not symmetric. The model is handed the English source and
told by the system prompt to send it in the language of the conversation. The
deterministic paths — the keyword pre-filter and classifier refusals streamed or persisted
straight from Python — have no model in the loop and no conversation language, so they
render under the request locale.

The shipped catalogs are detached for the test session, so the Spanish assertion injects its
own single-message catalog rather than reading sparkth/locale/es.
"""

import json

import pytest

from sparkth.core.i18n import locale_context
from sparkth.lib.i18n import gettext
from sparkth.lib.testing import AddTranslation
from sparkth.plugins.chat.prompt import REFUSAL_MESSAGE, get_learning_design_system_prompt
from sparkth.plugins.chat.routes.utils import stream_out_of_scope_refusal

SPANISH = (
    "Soy un asistente de creación de cursos y solo puedo ayudarte a diseñar y crear "
    "cursos. ¿Hay algún curso que te gustaría crear?"
)


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
