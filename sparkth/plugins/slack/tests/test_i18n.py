"""The bot's canned messages are lazy translations rendered at dispatch time.

The module-level constants are built at import, before any locale exists, so
they must defer translation until ``str()`` is called where the message is
sent to Slack.
"""

from sparkth.core.i18n import locale_context
from sparkth.lib.testing import AddTranslation
from sparkth.plugins.slack.constants import RAG_NOT_READY_MESSAGE

SPANISH = "Todavía estoy indexando los documentos del curso. Vuelve a intentarlo en unos minutos."


def test_bot_messages_render_in_the_active_locale(translation_catalog: AddTranslation) -> None:
    translation_catalog(
        "I'm still indexing the course documents. Please try again in a few minutes.",
        SPANISH,
    )
    with locale_context("es"):
        assert str(RAG_NOT_READY_MESSAGE) == SPANISH
    assert str(RAG_NOT_READY_MESSAGE) == "I'm still indexing the course documents. Please try again in a few minutes."
