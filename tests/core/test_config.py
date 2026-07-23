"""Tests for environment-file conventions shared by all Settings classes."""

from pathlib import Path

import pytest
from pydantic_settings import BaseSettings

from sparkth.core.config import Settings
from sparkth.plugins.chat.config import ChatSettings
from sparkth.plugins.googledrive.config import GoogleDriveSettings
from sparkth.plugins.slack.config import SlackSettings
from sparkth.rag.config import RAGSettings

ALL_SETTINGS_CLASSES = [Settings, RAGSettings, GoogleDriveSettings, ChatSettings, SlackSettings]


@pytest.mark.parametrize("settings_class", ALL_SETTINGS_CLASSES)
def test_settings_read_env_local_overrides(settings_class: type[BaseSettings]) -> None:
    """Every settings class must read .env.local after .env so local overrides win.

    .env.local is the documented, git-ignored home for sensitive credentials and
    local overrides; a settings class reading only .env silently ignores it.
    """
    assert settings_class.model_config.get("env_file") == (".env", ".env.local")


def test_env_local_value_wins_over_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.delenv("GOOGLE_DRIVE_REDIRECT_URI", raising=False)
    (tmp_path / ".env").write_text("GOOGLE_DRIVE_REDIRECT_URI=http://from-dotenv\n")
    (tmp_path / ".env.local").write_text("GOOGLE_DRIVE_REDIRECT_URI=http://from-dotenv-local\n")
    monkeypatch.chdir(tmp_path)

    assert GoogleDriveSettings().GOOGLE_DRIVE_REDIRECT_URI == "http://from-dotenv-local"
