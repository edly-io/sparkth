from typing import Any

from app.lib.mcp.hooks import Tool, generate_input_schema


class _Payload:
    pass


async def handler_with_doc(payload: str) -> dict[str, Any]:
    """Do a thing with the payload."""
    return {}


async def handler_without_doc(name: str, count: int = 0) -> dict[str, Any]:
    return {}


def test_name_is_handler_name() -> None:
    assert Tool(handler_with_doc).name == "handler_with_doc"


def test_description_is_stripped_docstring() -> None:
    assert Tool(handler_with_doc).description == "Do a thing with the payload."


def test_description_empty_without_docstring() -> None:
    assert Tool(handler_without_doc).description == ""


def test_input_schema_matches_generator() -> None:
    tool = Tool(handler_without_doc)
    assert tool.input_schema == generate_input_schema(handler_without_doc)


def test_category_defaults_none_and_is_stored() -> None:
    assert Tool(handler_with_doc).category is None
    assert Tool(handler_with_doc, category="things").category == "things"
