"""The form controls a plugin can ask the settings UI to render a config field with."""

from enum import StrEnum
from typing import Any


class ConfigWidget(StrEnum):
    """A form control the settings UI knows how to render.

    Values are the names the frontend config modal looks a control up by: the controls a
    plugin passes into its own config modal, then core's built-in controls. A field with no
    hint is rendered from its JSON-schema type alone, which covers plain strings, numbers and
    booleans; declare a widget only when the type does not carry enough meaning -- a
    multi-line message, a secret, or a value that must be picked from data the frontend
    fetches.
    """

    TEXTAREA = "textarea"
    PASSWORD = "password"
    # Picks an LLMConfig the user owns; the stored value is its row id.
    LLM_CONFIG = "llm-config"
    # Picks a model offered by the provider of the field's sibling ``llm_config_id``.
    LLM_MODEL = "llm-model"
    # Picks among the document sources the user's RAG store holds.
    DOC_SOURCES = "doc-sources"


def widget(control: ConfigWidget) -> dict[str, Any]:
    """``json_schema_extra`` marking a config field as rendered by ``control``.

    ```python
    lms_password: str = Field(..., json_schema_extra=widget(ConfigWidget.PASSWORD))
    ```
    """
    return {"widget": control.value}


def secret(control: ConfigWidget = ConfigWidget.PASSWORD, *, masked: bool = False) -> dict[str, Any]:
    """``json_schema_extra`` marking a config field as a secret the API never returns in full.

    A ``masked`` secret, such as an API key, is returned masked (``****2345``); any other, such as
    a password, is never returned at all.

    ```python
    api_key: str = Field(..., json_schema_extra=secret(masked=True))
    password: str = Field(..., json_schema_extra=secret())
    private_key: str = Field(..., json_schema_extra=secret(ConfigWidget.TEXTAREA))
    ```
    """
    return {**widget(control), "secret": True, "masked": masked}
