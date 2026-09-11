"""The Canvas credentials, as the settings form reads them."""

from sparkth.plugins.canvas.config import CanvasConfig


def test_api_key_is_declared_as_a_secret() -> None:
    assert CanvasConfig.model_json_schema()["properties"]["api_key"]["widget"] == "password"
