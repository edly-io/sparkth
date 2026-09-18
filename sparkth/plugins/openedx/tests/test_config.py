"""The Open edX credentials, as the settings form reads them."""

from sparkth.plugins.openedx.config import OpenEdxConfig


def test_password_is_declared_as_a_secret() -> None:
    """Without the hint the settings form renders the password in cleartext."""
    assert OpenEdxConfig.model_json_schema()["properties"]["lms_password"]["widget"] == "password"


def test_urls_and_username_are_plain_fields() -> None:
    properties = OpenEdxConfig.model_json_schema()["properties"]
    assert "widget" not in properties["lms_url"]
    assert "widget" not in properties["lms_username"]
