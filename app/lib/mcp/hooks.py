import inspect
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, get_type_hints

from pydantic import BaseModel

from app.lib.hooks import PluginCollectionHook
from app.lib.log import get_logger

logger = get_logger(__name__)


@dataclass
class Tool:
    """An MCP tool a plugin contributes to the :data:`MCP_TOOLS` hook.

    The plugin registers it from its ``__init__`` with
    ``MCP_TOOLS.add_item(self, Tool(self.my_method, category="..."))``. The tool's
    ``name`` and ``description`` are derived from the bound handler (its name and
    docstring); the input schema is auto-generated from the handler signature.
    """

    handler: Callable[..., Any]
    category: str | None = None

    @property
    def name(self) -> str:
        return self.handler.__name__

    @property
    def description(self) -> str:
        return (self.handler.__doc__ or "").strip()

    @property
    def input_schema(self) -> dict[str, Any]:
        return generate_input_schema(self.handler)


# MCP tools contributed by plugins, consumed by the MCP server (app/mcp/main.py)
# and the chat tool registry (app/core_plugins/chat/tools.py).
MCP_TOOLS: PluginCollectionHook[Tool] = PluginCollectionHook()


def generate_input_schema(func: Callable[..., Any]) -> dict[str, Any]:
    """Auto-generate a JSON Schema from a function signature using type hints."""
    try:
        sig = inspect.signature(func)
        type_hints = get_type_hints(func)

        properties: dict[str, Any] = {}
        required: list[str] = []

        for param_name, param in sig.parameters.items():
            if param_name == "self":
                continue

            param_type = type_hints.get(param_name, str)
            properties[param_name] = type_to_json_schema(param_type)

            if param.default == inspect.Parameter.empty:
                required.append(param_name)

        schema: dict[str, Any] = {"type": "object", "properties": properties}
        if required:
            schema["required"] = required
        return schema

    except (TypeError, NameError, AttributeError) as e:
        logger.warning("Failed to generate input schema for %s: %s. Using empty schema.", func.__name__, e)
        return {"type": "object", "properties": {}}


def type_to_json_schema(py_type: type[Any]) -> dict[str, Any]:
    """Convert a Python type to a JSON Schema type definition."""
    # Check if it's a Pydantic BaseModel
    if isinstance(py_type, type) and issubclass(py_type, BaseModel):
        model_schema = py_type.model_json_schema()
        defs = model_schema.get("$defs", {})
        properties = model_schema.get("properties", {})
        # Resolve all $ref references inline so the schema is self-contained
        resolved_properties = {k: resolve_schema_refs(v, defs) for k, v in properties.items()}
        return {
            "type": "object",
            "properties": resolved_properties,
            "required": model_schema.get("required", []),
        }

    type_map: dict[type[Any], dict[str, str]] = {
        int: {"type": "integer"},
        float: {"type": "number"},
        str: {"type": "string"},
        bool: {"type": "boolean"},
        list: {"type": "array"},
        dict: {"type": "object"},
    }

    if py_type in type_map:
        return type_map[py_type]

    origin = getattr(py_type, "__origin__", None)
    if origin is list:
        return {"type": "array"}
    elif origin is dict:
        return {"type": "object"}

    return {"type": "string"}


def resolve_schema_refs(schema: Any, defs: dict[str, Any]) -> Any:
    """Recursively resolve all $ref references inline within a JSON schema."""
    if not isinstance(schema, dict):
        return schema

    if "$ref" in schema:
        ref_path = schema["$ref"]
        if ref_path.startswith("#/$defs/"):
            def_name = ref_path.split("/")[-1]
            if def_name in defs:
                resolved = defs[def_name].copy()
                # Merge any extra keys (e.g. description) from the referencing schema
                for key, value in schema.items():
                    if key != "$ref":
                        resolved[key] = value
                return resolve_schema_refs(resolved, defs)
        return schema

    result: dict[str, Any] = {}
    for key, value in schema.items():
        if key == "$defs":
            continue
        elif key == "properties" and isinstance(value, dict):
            result[key] = {k: resolve_schema_refs(v, defs) for k, v in value.items()}
        elif key == "items" and isinstance(value, dict):
            result[key] = resolve_schema_refs(value, defs)
        elif key == "anyOf" and isinstance(value, list):
            result[key] = [resolve_schema_refs(v, defs) if isinstance(v, dict) else v for v in value]
        elif key == "allOf" and isinstance(value, list):
            result[key] = [resolve_schema_refs(v, defs) if isinstance(v, dict) else v for v in value]
        else:
            result[key] = value
    return result
