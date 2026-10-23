from typing import Any

from sparkth.core.plugins.service import UserPluginResponse

SCHEMA: dict[str, Any] = {
    "properties": {
        "api_url": {"type": "string"},
        "api_key": {"type": "string", "widget": "password"},
        "backup_key": {"type": "string", "widget": "password"},
    }
}


def _response(config: dict[str, Any]) -> UserPluginResponse:
    return UserPluginResponse.for_plugin(
        plugin_name="lms", enabled=True, config=config, is_core=True, config_schema=SCHEMA
    )


def test_secret_fields_are_left_out_of_config() -> None:
    response = _response({"api_url": "https://lms.example.com", "api_key": "s3cret", "backup_key": None})

    assert response.config == {"api_url": "https://lms.example.com"}


def test_stored_secrets_are_listed_in_schema_order() -> None:
    response = _response({"backup_key": "b", "api_key": "a"})

    assert response.secrets_set == ["api_key", "backup_key"]


def test_empty_secret_is_not_reported_as_set() -> None:
    response = _response({"api_key": "", "backup_key": None})

    assert response.secrets_set == []


def test_plugin_without_secret_fields_has_none_set() -> None:
    response = UserPluginResponse.for_plugin(
        plugin_name="plain", enabled=True, config={"note": "x"}, is_core=True, config_schema={}
    )

    assert response.config == {"note": "x"}
    assert response.secrets_set == []
