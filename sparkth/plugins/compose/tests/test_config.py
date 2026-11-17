"""The compose plugin's user config, as the settings form reads it."""

import pytest
from pydantic import ValidationError

from sparkth.plugins.compose.config import ComposeSettings, ComposeUserConfig


def test_schema_declares_the_llm_widgets() -> None:
    properties = ComposeUserConfig.model_json_schema()["properties"]
    assert properties["llm_config_id"]["widget"] == "llm-config"
    assert properties["llm_model_override"]["widget"] == "llm-model"


def test_compose_settings_read_compose_prefix(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("COMPOSE_MAX_TOOL_EXECUTIONS", "7")

    assert ComposeSettings().max_tool_executions == 7


def test_a_planner_model_compose_does_not_know_is_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("COMPOSE_PLANNER_MODEL", "largest")

    with pytest.raises(ValidationError, match="planner_model"):
        ComposeSettings()
