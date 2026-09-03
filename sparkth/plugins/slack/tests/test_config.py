"""Unit tests for SlackConfig LLM fields."""

import pytest
from pydantic import ValidationError

from sparkth.plugins.slack.config import SlackConfig


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


def test_llm_model_override_defaults_to_none() -> None:
    config = SlackConfig()
    assert config.llm_model_override is None


def test_llm_model_override_accepts_string() -> None:
    config = SlackConfig(llm_model_override="claude-haiku-4-5")
    assert config.llm_model_override == "claude-haiku-4-5"


def test_schema_declares_the_widgets_the_settings_form_needs() -> None:
    """The form is rendered from the schema, so these hints are the whole UI contract."""
    properties = SlackConfig.model_json_schema()["properties"]
    assert properties["fallback_message"]["widget"] == "textarea"
    assert properties["greeting_message"]["widget"] == "textarea"
    assert properties["allowed_sources"]["widget"] == "doc-sources"
    assert properties["llm_config_id"]["widget"] == "llm-config"
    assert properties["llm_model_override"]["widget"] == "llm-model"


def test_bot_name_is_a_plain_text_field() -> None:
    assert "widget" not in SlackConfig.model_json_schema()["properties"]["bot_name"]
