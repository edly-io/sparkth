"""Tests for the application settings public API (app.lib.settings)."""

from app.core.config import Settings
from app.lib.settings import get_settings


def test_get_settings_is_callable() -> None:
    assert callable(get_settings)


def test_get_settings_returns_settings_instance() -> None:
    settings = get_settings()
    assert isinstance(settings, Settings)


def test_settings_exposes_secret_key() -> None:
    settings = get_settings()
    assert hasattr(settings, "SECRET_KEY")
    assert isinstance(settings.SECRET_KEY, str)
    assert settings.SECRET_KEY


def test_settings_exposes_google_oauth_fields() -> None:
    settings = get_settings()
    assert hasattr(settings, "GOOGLE_CLIENT_ID")
    assert hasattr(settings, "GOOGLE_CLIENT_SECRET")
