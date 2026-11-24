from typing import Any

from sparkth.core.plugins.service import PluginResponse
from sparkth.core.plugins.widgets import ConfigWidget, secret, widget

SCHEMA: dict[str, Any] = {
    "properties": {
        "api_url": {"type": "string"},
        "api_key": {"type": "string", **secret()},
        "backup_key": {"type": "string", **secret()},
        "private_key": {"type": "string", **secret(ConfigWidget.TEXTAREA)},
        "note": {"type": "string", **widget(ConfigWidget.PASSWORD)},
        "token": {"type": "string", **secret(masked=True)},
    }
}


def _response(config: dict[str, Any]) -> PluginResponse:
    return PluginResponse.for_plugin("lms", True, True, config, True, SCHEMA)


def test_secret_fields_are_left_out_of_config() -> None:
    response = _response({"api_url": "https://lms.example.com", "api_key": "s3cret", "backup_key": None})

    assert response.config == {"api_url": "https://lms.example.com"}


def test_a_secret_shown_in_another_widget_is_left_out_of_config() -> None:
    response = _response({"private_key": "-----BEGIN KEY-----"})

    assert response.config == {}
    assert response.secrets_set == ["private_key"]


def test_a_password_widget_without_the_secret_marker_is_returned() -> None:
    response = _response({"note": "hidden while typing"})

    assert response.config == {"note": "hidden while typing"}


def test_stored_secrets_are_listed_in_schema_order() -> None:
    response = _response({"backup_key": "b", "api_key": "a"})

    assert response.secrets_set == ["api_key", "backup_key"]


def test_empty_secret_is_not_reported_as_set() -> None:
    response = _response({"api_key": "", "backup_key": None})

    assert response.secrets_set == []


def test_plugin_without_secret_fields_has_none_set() -> None:
    response = PluginResponse.for_plugin("plain", True, True, {"note": "x"}, True, {})

    assert response.config == {"note": "x"}
    assert response.secrets_set == []


def test_a_masked_secret_is_returned_masked() -> None:
    response = _response({"token": "tok-abcde12345"})

    assert response.config == {}
    assert response.secrets_set == ["token"]
    assert response.masked_secrets == {"token": "tok-****2345"}


def test_an_unmasked_secret_is_never_returned_masked() -> None:
    response = _response({"api_key": "s3cret-value"})

    assert response.masked_secrets == {}


def test_an_empty_masked_secret_is_not_returned() -> None:
    response = _response({"token": ""})

    assert response.masked_secrets == {}


def test_the_system_switch_is_reported_beside_the_users_preference() -> None:
    response = PluginResponse.for_plugin("lms", True, False, {}, True)

    assert (response.enabled, response.system_enabled) == (True, False)
