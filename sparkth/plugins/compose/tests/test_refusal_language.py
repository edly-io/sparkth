"""The out-of-scope refusal reaches the user in a language they can read.

Two paths emit it and they are not symmetric. An agent is handed the English source and told
by the system prompt to send it in the language of the conversation. When Compose's planner
refuses, the backend writes the refusal sentence itself rather than a model generating it, so
it renders under the request locale (``gettext``) rather than the conversation's language.

The shipped catalogs are detached for the test session, so the Spanish assertion injects its
own single-message catalog rather than reading sparkth/locale/es. One class steps outside the
runtime entirely and runs pybabel over this plugin, because the marking that puts the refusal
in those catalogs is invisible to every runtime assertion.
"""

import json
import re
from collections.abc import Callable
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID

import pytest
from babel.messages.extract import DEFAULT_KEYWORDS, extract_from_dir
from httpx import AsyncClient
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

import sparkth
from sparkth.core.i18n import locale_context
from sparkth.lib.i18n import gettext
from sparkth.lib.models import User
from sparkth.lib.testing import AddTranslation
from sparkth.plugins.compose.constants import REFUSAL_MESSAGE
from sparkth.plugins.compose.models import Conversation
from sparkth.plugins.compose.prompt import render_system_prompt
from sparkth.plugins.compose.tests.helpers import (
    answering_model,
    planning,
    refusal,
    seed_conversation,
    seed_llm_config,
    stored_messages,
)

SPANISH = (
    "Soy un asistente de creación de cursos y solo puedo ayudarte a diseñar y crear "
    "cursos. ¿Hay algún curso que te gustaría crear?"
)

_KEYWORD_FLAG = re.compile(r"-k\s+(\w+)")
_REPO_ROOT = Path(sparkth.__file__).resolve().parent.parent
_COMPOSE_PLUGIN_DIR = Path(sparkth.__file__).resolve().parent / "plugins" / "compose"
# babel.cfg ignores `**/tests/**`, so real extraction never reads this suite.
_EXTRACTION_SKIPPED_DIRS = {"tests", "__pycache__"}


def _makefile_extract_keywords(makefile: Path) -> dict[str, None]:
    """The ``-k`` keywords ``make i18n.extract`` passes to pybabel, read off its recipe.

    Derived rather than restated here: a keyword dropped from that target must fail the
    extraction test below, because real extraction would stop finding the marked string
    while a hardcoded copy kept the guard green. Reads only the target's own recipe lines,
    so a ``-k`` in a neighbouring target is not picked up.
    """
    recipe: list[str] = []
    in_target = False
    for line in makefile.read_text(encoding="utf-8").splitlines():
        if line.startswith("i18n.extract:"):
            in_target = True
        elif in_target:
            if not line.startswith("\t"):
                break
            recipe.append(line)
    return {name: None for name in _KEYWORD_FLAG.findall("\n".join(recipe))}


def _extraction_directory_filter(dirpath: str) -> bool:
    """Keep this test's view of the tree identical to ``babel.cfg``'s, so the guard cannot
    be satisfied by a file real extraction never reads."""
    return Path(dirpath).name not in _EXTRACTION_SKIPPED_DIRS


def _refusing() -> Callable[..., Any]:
    """The route's ``get_provider`` with a planner that refuses every message."""
    provider = MagicMock()
    provider.create_llm.return_value = answering_model("never used")
    return planning(provider, refusal())


def _titling() -> MagicMock:
    """A provider that writes conversation titles."""
    provider = MagicMock()
    provider.send_message = AsyncMock(return_value={"content": "Arithmetic", "metadata": {}})
    return provider


class TestRefusalIsMarked:
    def test_translates_under_a_non_default_locale(self, translation_catalog: AddTranslation) -> None:
        translation_catalog(REFUSAL_MESSAGE, SPANISH)
        with locale_context("es"):
            assert gettext(REFUSAL_MESSAGE) == SPANISH

    def test_untranslated_with_no_catalog(self) -> None:
        """No catalog registered, so the source falls through — this is what proves the
        previous test is observing a real lookup rather than a coincidence."""
        with locale_context("es"):
            assert gettext(REFUSAL_MESSAGE) == REFUSAL_MESSAGE


class TestRefusalIsExtractable:
    """Only pybabel's own view can prove the marking works.

    ``gettext_noop`` returns its argument unchanged, so deleting the wrapper changes
    nothing observable at runtime: ``gettext`` is content-keyed and keeps translating from
    the catalog entry that already exists. What breaks is extraction — the msgid stops
    being found, the next catalog update marks it obsolete, and the shipped translations
    rot with no test failing.
    """

    def test_the_keywords_come_from_the_makefile_recipe(self, tmp_path: Path) -> None:
        """What makes the guard below bite: drop a -k flag from the target and the
        extraction it performs loses that keyword too."""
        makefile = tmp_path / "Makefile"
        makefile.write_text(
            "i18n.extract: ## Extract translatable strings\n"
            "\tuv run pybabel extract -F babel.cfg -k lazy_gettext -k gettext_noop \\\n"
            "\t\t-o sparkth/locale/messages.pot sparkth\n"
            "\n"
            "i18n.compile:\n"
            "\tuv run pybabel compile -k not_this_one\n"
        )

        assert _makefile_extract_keywords(makefile) == {"lazy_gettext": None, "gettext_noop": None}

    def test_the_refusal_is_found_by_pybabel(self) -> None:
        """``REFUSAL_MESSAGE`` is imported rather than duplicated as a literal so the
        assertion tracks whatever sentence is actually shipped. Babel's DEFAULT_KEYWORDS
        (gettext, _, …) apply on top of the recipe's, as they do on the command line."""
        keywords = DEFAULT_KEYWORDS | _makefile_extract_keywords(_REPO_ROOT / "Makefile")

        messages = {
            message
            for _filename, _lineno, message, _comments, _context in extract_from_dir(
                _COMPOSE_PLUGIN_DIR, keywords=keywords, directory_filter=_extraction_directory_filter
            )
            if isinstance(message, str)
        }

        assert REFUSAL_MESSAGE in messages


class TestRefusalInTheSystemPrompt:
    def test_english_source_reaches_the_model(self, translation_catalog: AddTranslation) -> None:
        """The model translates from a stable source, so the prompt carries the English
        source even under a non-default locale — not the locale-rendered string."""
        translation_catalog(REFUSAL_MESSAGE, SPANISH)
        with locale_context("es"):
            prompt = render_system_prompt([])
        assert REFUSAL_MESSAGE in prompt
        assert SPANISH not in prompt


class TestARefusedTurn:
    """Compose's planner refuses by calling its refuse tool, whose sentence is rendered by the
    backend under the request locale, on both the streamed and the non-streamed path."""

    @pytest.mark.asyncio
    async def test_a_refused_first_message_starts_a_conversation_in_the_request_locale(
        self,
        client: AsyncClient,
        current_user: User,
        session: AsyncSession,
        translation_catalog: AddTranslation,
    ) -> None:
        translation_catalog(REFUSAL_MESSAGE, SPANISH)
        llm_config_id = await seed_llm_config(session, current_user.id or 1)

        with (
            locale_context("es"),
            patch("sparkth.plugins.compose.routes.completions.get_provider", side_effect=_refusing()),
            patch("sparkth.plugins.compose.conversation_title.get_provider", return_value=_titling()),
        ):
            response = await client.post(
                "/api/v1/compose/completions",
                json={
                    "llm_config_id": llm_config_id,
                    "messages": [{"role": "user", "content": "what is 2+2?"}],
                    "stream": False,
                    "tools": "none",
                },
            )

        assert response.status_code == 200
        assert response.json()["message"]["content"] == SPANISH
        conversation = (
            await session.exec(
                select(Conversation).where(Conversation.uuid == UUID(response.json()["conversation_id"]))
            )
        ).one()
        assert conversation.title == "Arithmetic"

    @pytest.mark.asyncio
    async def test_a_streamed_refusal_arrives_and_is_stored_in_the_request_locale(
        self,
        client: AsyncClient,
        current_user: User,
        session: AsyncSession,
        translation_catalog: AddTranslation,
    ) -> None:
        translation_catalog(REFUSAL_MESSAGE, SPANISH)
        llm_config_id = await seed_llm_config(session, current_user.id or 1)
        conversation_uuid = await seed_conversation(session, current_user.id or 1)

        with (
            locale_context("es"),
            patch("sparkth.plugins.compose.routes.completions.get_provider", side_effect=_refusing()),
        ):
            response = await client.post(
                "/api/v1/compose/completions",
                json={
                    "llm_config_id": llm_config_id,
                    "messages": [{"role": "user", "content": "what is 2+2?"}],
                    "conversation_id": conversation_uuid,
                    "stream": True,
                    "tools": "none",
                },
            )

        payloads = [json.loads(line.removeprefix("data: ")) for line in response.text.split("\n\n") if line.strip()]
        assert "".join(payload.get("token", "") for payload in payloads if not payload.get("done")) == SPANISH
        stored = await stored_messages(session, conversation_uuid)
        assert (stored[-1].role, stored[-1].content) == ("assistant", SPANISH)
