"""Unit tests for SlackConfig LLM fields."""

import pytest
from pydantic import ValidationError

from app.core_plugins.slack.config import SlackConfig


def test_llm_config_id_defaults_to_none() -> None:
    config = SlackConfig()
    assert config.llm_config_id is None
    assert config.llm_temperature == 0.3


def test_llm_config_id_accepts_value() -> None:
    config = SlackConfig(llm_config_id=42, llm_temperature=0.5)
    assert config.llm_config_id == 42
    assert config.llm_temperature == 0.5


def test_llm_temperature_rejects_out_of_range() -> None:
    with pytest.raises(ValidationError):
        SlackConfig(llm_temperature=-0.1)
