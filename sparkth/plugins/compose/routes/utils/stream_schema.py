"""The schema of a streamed reply's status events, as the API schema publishes it."""

from typing import Any, cast

from pydantic import TypeAdapter

from sparkth.plugins.compose.schemas import AnyStreamStatusEvent


def _inline_refs(node: Any, definitions: dict[str, Any]) -> Any:
    """``node`` with every reference into ``definitions`` replaced by the schema it points at."""
    if isinstance(node, dict):
        if "$ref" in node:
            return _inline_refs(definitions[node["$ref"].rsplit("/", 1)[-1]], definitions)
        return {key: _inline_refs(value, definitions) for key, value in node.items()}
    if isinstance(node, list):
        return [_inline_refs(item, definitions) for item in node]
    return node


def get_stream_status_schema() -> dict[str, Any]:
    """The schema of a streamed reply's status events, with no reference to a schema outside it.

    The API schema lists only the types of JSON bodies, so a reference from the event stream would
    point at nothing. The schema's description says what else the stream sends.
    """
    schema = TypeAdapter(AnyStreamStatusEvent).json_schema()
    events = cast(dict[str, Any], _inline_refs(schema, schema.pop("$defs")))
    description = (
        "The status events of a streamed reply. The stream also sends the reply's text, a final event "
        "and errors, which this schema does not describe."
    )
    return {"description": description, **events}
