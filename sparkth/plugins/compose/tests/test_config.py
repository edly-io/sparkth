"""The chat plugin's user config, as the settings form reads it."""

from sparkth.plugins.compose.config import ComposeUserConfig


def test_schema_declares_the_llm_widgets() -> None:
    properties = ComposeUserConfig.model_json_schema()["properties"]
    assert properties["llm_config_id"]["widget"] == "llm-config"
    assert properties["llm_model_override"]["widget"] == "llm-model"
