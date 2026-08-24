"""Tests for the supported-language allowlist, the platform default and resolution."""

import logging

import pytest
from pydantic import ValidationError

from sparkth.core.config import SUPPORTED_LANGUAGES, Settings, is_supported_language
from sparkth.core.models.user import User
from sparkth.lib.language import language_display_name, resolve_language
from sparkth.lib.settings import get_settings


def test_allowlist_holds_english_spanish_and_french() -> None:
    assert set(SUPPORTED_LANGUAGES) == {"en", "es", "fr"}


def test_allowlist_entries_carry_an_english_name_and_an_endonym() -> None:
    assert SUPPORTED_LANGUAGES["es"].name == "Spanish"
    assert SUPPORTED_LANGUAGES["es"].native_name == "Español"


def test_tags_are_hyphenated_bcp47_never_underscored() -> None:
    assert all("_" not in tag for tag in SUPPORTED_LANGUAGES)


def test_default_language_setting_defaults_to_english(monkeypatch: pytest.MonkeyPatch) -> None:
    """The field default, pinned against both env files and the process environment.

    ``_env_file=None`` suppresses `.env`/`.env.local` but pydantic-settings still
    reads ``os.environ``, so a shell or CI lane that exports ``DEFAULT_LANGUAGE``
    would otherwise fail this test for a reason unrelated to the field default.
    """
    monkeypatch.delenv("DEFAULT_LANGUAGE", raising=False)

    settings = Settings(
        _env_file=None,
        DATABASE_URL="sqlite+aiosqlite:///:memory:",
        ANALYTICS_DATABASE_URL="sqlite+aiosqlite:///:memory:",
        SECRET_KEY="test-secret",
        LLM_ENCRYPTION_KEY="test-key",
    )
    assert settings.DEFAULT_LANGUAGE == "en"


def test_default_language_outside_the_allowlist_is_rejected_at_startup() -> None:
    with pytest.raises(ValidationError):
        Settings(
            _env_file=None,
            DATABASE_URL="sqlite+aiosqlite:///:memory:",
            ANALYTICS_DATABASE_URL="sqlite+aiosqlite:///:memory:",
            SECRET_KEY="test-secret",
            LLM_ENCRYPTION_KEY="test-key",
            DEFAULT_LANGUAGE="klingon",
        )


def test_supported_tags_are_accepted() -> None:
    assert is_supported_language("en") is True
    assert is_supported_language("es") is True
    assert is_supported_language("fr") is True


def test_unsupported_tag_is_rejected() -> None:
    assert is_supported_language("de") is False
    assert is_supported_language("") is False


def test_the_default_is_validated_by_the_same_rule_as_any_other_tag() -> None:
    """The default runs through `is_supported_language`, so it gets the same exact,
    case-sensitive match a user's tag does: "en-US" is rejected, not folded to "en".
    """
    with pytest.raises(ValidationError):
        Settings(
            _env_file=None,
            DATABASE_URL="sqlite+aiosqlite:///:memory:",
            ANALYTICS_DATABASE_URL="sqlite+aiosqlite:///:memory:",
            SECRET_KEY="test-secret",
            LLM_ENCRYPTION_KEY="test-key",
            DEFAULT_LANGUAGE="en-US",
        )


def test_new_user_has_no_language_chosen() -> None:
    user = User(name="Test", username="nolang", email="nolang@example.com")
    assert user.language is None


def test_user_language_stores_a_bcp47_tag() -> None:
    user = User(name="Test", username="es", email="es@example.com", language="es")
    assert user.language == "es"


def test_resolve_returns_a_tag_the_user_chose() -> None:
    assert resolve_language("fr") == "fr"


def test_resolve_falls_back_to_the_platform_default_when_unset() -> None:
    """None is "never chose", so the platform default applies."""
    assert resolve_language(None) == "en"


def test_resolve_ignores_a_stored_tag_that_left_the_allowlist() -> None:
    """A language removed from the allowlist must stop being handed back."""
    assert resolve_language("de") == "en"


@pytest.mark.parametrize(
    ("tag", "expected"),
    [
        ("en", "English"),
        ("es", "Spanish"),
        ("de", "German"),
        ("ur", "Urdu"),
        ("ja", "Japanese"),
        ("pt-BR", "Portuguese (Brazil)"),
        ("zh-Hant", "Chinese (Traditional)"),
    ],
)
def test_names_supported_and_unsupported_tags_alike(tag: str, expected: str) -> None:
    """ "de" and "ur" are outside SUPPORTED_LANGUAGES on purpose: the allowlist
    governs shipped interface translations, not what the model may write in."""
    assert language_display_name(tag) == expected


def test_hyphenated_subtags_are_accepted() -> None:
    """BCP 47 is hyphenated; Babel's parser defaults to the POSIX underscore, so
    the separator has to be passed explicitly or every regional tag falls back."""
    assert language_display_name("pt-BR") != language_display_name(None)


@pytest.mark.parametrize(
    "tag",
    [
        None,
        "",
        "klingon",
        "xx",
        "123",
        "not a tag",
        # "skr" (Saraiki) parses successfully but has no CLDR English display name,
        # so Locale.get_display_name("en") returns None rather than raising. This
        # exercises the None-return fallback path, not the exception path "xx" and
        # "klingon" cover above — do not remove it as a duplicate of those.
        "skr",
    ],
)
def test_unusable_tags_fall_back_to_the_platform_default(tag: str | None) -> None:
    """Falling back rather than raising: a misspelled tag must not fail a whole
    agent-driven course generation run."""
    default = get_settings().DEFAULT_LANGUAGE
    assert language_display_name(tag) == language_display_name(default)


@pytest.mark.parametrize("tag", ["klingon", "skr"])
def test_a_swallowed_fallback_is_logged_at_warning(tag: str, caplog: pytest.LogCaptureFixture) -> None:
    """Both fallback paths here swallow rather than raise, and the exception table in
    CLAUDE.md puts a swallowed-with-fallback error at warning or above. At info it reads as
    routine, which is exactly what a caller probing the field would want it to look like.
    "klingon" takes the raised-exception path, "skr" the no-display-name one."""
    with caplog.at_level(logging.DEBUG, logger="sparkth.core.language"):
        language_display_name(tag)

    assert [record.levelname for record in caplog.records] == ["WARNING"]


def test_an_unusable_tag_is_not_logged_in_full(caplog: pytest.LogCaptureFixture) -> None:
    """The tag reaches here from an unauthenticated MCP field and lands in the log twice
    over — once written directly, once inside Babel's message, which quotes the input back.
    Unbounded, that lets a caller pick how many bytes one call costs in log storage."""
    overlong = "q" * 5000

    with caplog.at_level(logging.DEBUG, logger="sparkth.core.language"):
        language_display_name(overlong)

    assert overlong not in caplog.text
    assert len(caplog.text) < 300
