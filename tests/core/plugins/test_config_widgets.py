"""The widget hints a plugin attaches to its config fields must survive into the schema.

The settings UI reads them from ``model_json_schema()`` to pick a form control, so a
hint that does not reach the schema silently degrades the field to a text input.
"""

from pydantic import Field

from sparkth.lib.plugins import ConfigWidget, PluginConfig, widget


class _WidgetConfig(PluginConfig):
    note: str = Field(default="", json_schema_extra=widget(ConfigWidget.TEXTAREA))
    secret: str = Field(default="", json_schema_extra=widget(ConfigWidget.PASSWORD))
    plain: str = Field(default="")


def test_widget_hint_reaches_the_json_schema() -> None:
    properties = _WidgetConfig.model_json_schema()["properties"]
    assert properties["note"]["widget"] == "textarea"
    assert properties["secret"]["widget"] == "password"


def test_a_field_without_a_hint_declares_no_widget() -> None:
    assert "widget" not in _WidgetConfig.model_json_schema()["properties"]["plain"]


def test_widget_values_are_the_names_the_frontend_registry_uses() -> None:
    """Kebab-case, matching the keys of the frontend widget registry."""
    assert {w.value for w in ConfigWidget} == {
        "textarea",
        "password",
        "llm-config",
        "llm-model",
        "doc-sources",
    }
