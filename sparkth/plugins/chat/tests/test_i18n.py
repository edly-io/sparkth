"""User-facing chat error messages are translated into the active locale."""

from httpx import RemoteProtocolError

from sparkth.core.i18n import locale_context
from sparkth.lib.testing import AddTranslation
from sparkth.plugins.chat.routes.utils.stream_processor import streaming_error_message

SPANISH = "La conexión se interrumpió. Inténtalo de nuevo."


def test_streaming_error_message_translates_with_the_active_locale(translation_catalog: AddTranslation) -> None:
    translation_catalog("The connection was interrupted. Please try again.", SPANISH)
    with locale_context("es"):
        assert streaming_error_message(RemoteProtocolError("connection dropped")) == SPANISH


def test_streaming_error_message_defaults_to_english() -> None:
    assert (
        streaming_error_message(RemoteProtocolError("connection dropped"))
        == "The connection was interrupted. Please try again."
    )
