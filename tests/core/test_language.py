"""Tests for the supported-language allowlist, the platform default and resolution."""

import pytest
from pydantic import ValidationError

from sparkth.core.config import SUPPORTED_LANGUAGES, Settings, is_supported_language
from sparkth.core.models.user import User
from sparkth.lib.language import resolve_language


def test_allowlist_holds_english_spanish_and_french() -> None:
    assert set(SUPPORTED_LANGUAGES) == {"en", "es", "fr"}


def test_allowlist_entries_carry_an_english_name_and_an_endonym() -> None:
    assert SUPPORTED_LANGUAGES["es"].name == "Spanish"
    assert SUPPORTED_LANGUAGES["es"].native_name == "Español"


def test_tags_are_hyphenated_bcp47_never_underscored() -> None:
    assert all("_" not in tag for tag in SUPPORTED_LANGUAGES)


def test_default_language_setting_defaults_to_english() -> None:
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
