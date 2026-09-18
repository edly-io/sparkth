"""The Moodle credentials, as the settings form reads them."""

from sparkth.plugins.moodle.config import MoodleConfig


def test_api_key_is_declared_as_a_secret() -> None:
    assert MoodleConfig.model_json_schema()["properties"]["api_key"]["widget"] == "password"
