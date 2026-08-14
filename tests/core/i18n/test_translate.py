"""Tests for the gettext-backed translation core (sparkth/core/i18n/translate.py)."""

from collections.abc import Iterator
from pathlib import Path

import pytest
from babel.messages.catalog import Catalog
from babel.messages.mofile import write_mo

from sparkth.core.i18n import get_locale, gettext, gettext_noop, lazy_gettext, locale_context
from sparkth.core.i18n.hooks import LOCALE_DIRS
from sparkth.core.i18n.translate import LOCALE_DIR
from sparkth.lib import i18n as lib_i18n

TRANSLATED = ("Incorrect username or password", "Usuario o contraseña incorrectos")


def write_catalog(locale_dir: Path, message: str, translation: str) -> None:
    """Compile a one-message Spanish catalog under ``locale_dir``."""
    catalog = Catalog(locale="es", domain="messages")
    catalog.add(message, translation)
    mo_dir = locale_dir / "es" / "LC_MESSAGES"
    mo_dir.mkdir(parents=True)
    with open(mo_dir / "messages.mo", "wb") as mo_file:
        write_mo(mo_file, catalog)


@pytest.fixture
def catalog_dir(tmp_path: Path) -> Iterator[Path]:
    """Register a temp locale dir holding one Spanish catalog on the hook.

    The catalog cache is keyed by (locale, registered dirs), and ``tmp_path``
    is unique per test, so no explicit cache invalidation is needed.
    """
    write_catalog(tmp_path, TRANSLATED[0], TRANSLATED[1])
    LOCALE_DIRS.add_item(tmp_path)
    yield tmp_path
    LOCALE_DIRS.remove(tmp_path)


def test_gettext_translates_with_the_active_locale(catalog_dir: Path) -> None:
    with locale_context("es"):
        assert gettext(TRANSLATED[0]) == TRANSLATED[1]


def test_gettext_returns_the_source_when_the_locale_has_no_catalog(catalog_dir: Path) -> None:
    with locale_context("fr"):
        assert gettext(TRANSLATED[0]) == TRANSLATED[0]


def test_gettext_returns_the_source_for_a_message_missing_from_the_catalog(catalog_dir: Path) -> None:
    with locale_context("es"):
        assert gettext("Not in the catalog") == "Not in the catalog"


def test_gettext_uses_the_default_language_outside_any_request(catalog_dir: Path) -> None:
    assert gettext(TRANSLATED[0]) == TRANSLATED[0]


def test_gettext_returns_the_empty_string_rather_than_the_catalog_header(catalog_dir: Path) -> None:
    # A compiled catalog stores its metadata header under the empty msgid, so a bare
    # gettext("") would hand the caller the PO header. An empty source message has no
    # translation to look up, so it is returned as-is.
    with locale_context("es"):
        assert gettext("") == ""


def test_get_locale_falls_back_to_the_platform_default() -> None:
    assert get_locale() == "en"


def test_locale_context_nests_and_restores_the_previous_locale() -> None:
    with locale_context("es"):
        with locale_context("fr"):
            assert get_locale() == "fr"
        assert get_locale() == "es"
    assert get_locale() == "en"


def test_lazy_gettext_defers_translation_to_render_time(catalog_dir: Path) -> None:
    message = lazy_gettext(TRANSLATED[0])
    with locale_context("es"):
        assert str(message) == TRANSLATED[1]
    assert str(message) == TRANSLATED[0]


def test_lazy_string_repr_names_the_source_message() -> None:
    assert repr(lazy_gettext("Hello")) == "LazyString('Hello')"


def test_gettext_noop_returns_the_message_unchanged(catalog_dir: Path) -> None:
    # The marker only tags the literal for extraction; the string stays a plain
    # ``str`` holding the source message, translated later via gettext().
    with locale_context("es"):
        assert gettext_noop(TRANSLATED[0]) == TRANSLATED[0]


def test_a_noop_marked_message_translates_when_passed_through_gettext(catalog_dir: Path) -> None:
    stored = gettext_noop(TRANSLATED[0])
    with locale_context("es"):
        assert gettext(stored) == TRANSLATED[1]


def test_the_core_locale_dir_is_registered_at_import(shipped_locale_dirs: tuple[Path, ...]) -> None:
    # The suite detaches the shipped catalog dirs for the session; the
    # import-time registration is visible in the detached snapshot.
    assert LOCALE_DIR in shipped_locale_dirs


def test_catalogs_from_every_registered_dir_are_consulted(tmp_path: Path) -> None:
    """Each registered dir contributes its own catalog, the plugin-portability seam."""
    core_like = tmp_path / "core"
    plugin_like = tmp_path / "plugin"
    write_catalog(core_like, "Core message", "Mensaje del núcleo")
    write_catalog(plugin_like, "Plugin message", "Mensaje del plugin")
    LOCALE_DIRS.add_item(core_like)
    LOCALE_DIRS.add_item(plugin_like)
    try:
        with locale_context("es"):
            assert gettext("Core message") == "Mensaje del núcleo"
            assert gettext("Plugin message") == "Mensaje del plugin"
    finally:
        LOCALE_DIRS.remove(core_like)
        LOCALE_DIRS.remove(plugin_like)


def test_the_lib_facade_exposes_the_marking_functions() -> None:
    assert lib_i18n._ is gettext
    assert lib_i18n.gettext is gettext
    assert lib_i18n.lazy_gettext is lazy_gettext
    assert lib_i18n.gettext_noop is gettext_noop
    assert lib_i18n.LOCALE_DIRS is LOCALE_DIRS
