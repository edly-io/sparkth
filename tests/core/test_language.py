"""Tests for the supported-language allowlist and the platform default."""

import pytest
from pydantic import ValidationError

from sparkth.core.config import SUPPORTED_LANGUAGES, Settings, is_supported_language


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
