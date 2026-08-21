"""User-facing chat error messages are translated into the active locale."""

from pathlib import Path

from httpx import RemoteProtocolError

import sparkth.plugins.chat
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


def test_the_plugin_locale_dir_is_registered_at_import(shipped_locale_dirs: tuple[Path, ...]) -> None:
    # The suite detaches the shipped catalog dirs for the session; the
    # import-time registration is visible in the detached snapshot.
    assert Path(sparkth.plugins.chat.__file__).parent / "locale" in shipped_locale_dirs
