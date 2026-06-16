"""Tests for the application settings public API (app.lib.settings)."""

from app.core.config import Settings
from app.core.config import get_settings as core_get_settings
from app.lib.settings import get_settings


def test_get_settings_shim_wires_to_core_function() -> None:
    assert get_settings is core_get_settings


def test_get_settings_returns_settings_instance() -> None:
    settings = get_settings()
    assert isinstance(settings, Settings)
