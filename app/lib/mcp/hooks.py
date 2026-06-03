import inspect
from typing import Any, Callable, Type, get_type_hints

from app.lib.hooks import PluginCollectionHook
from app.lib.log import get_logger
from app.plugins.base import SparkthPlugin

logger = get_logger(__name__)

# MCP tool definitions contributed by plugins. Each item is the dict consumed by
# the MCP server (app/mcp/main.py) and the chat tool registry.
MCP_TOOLS: PluginCollectionHook[dict[str, Any]] = PluginCollectionHook()


def collect_plugin_tools(plugin: SparkthPlugin) -> None:
    """Collect the plugin's ``@tool``-decorated methods into the MCP_TOOLS hook.

    Reads the registry populated by ``PluginMeta`` at class-definition time, binds
    each method to the instance, and builds the tool definition (auto-generating the
    input schema from the handler signature).
    """
    tool_registry = getattr(type(plugin), "_tool_registry", {})

    for method_name, tool_info in tool_registry.items():
        try:
            handler = getattr(plugin, method_name)
            tool_def: dict[str, Any] = {
                "name": tool_info["name"],
                "handler": handler,
                "description": tool_info["description"],
                "inputSchema": generate_input_schema(handler),
                "category": tool_info["category"],
                "version": tool_info["version"],
                "plugin": plugin.name,
            }
            MCP_TOOLS.add_item(plugin, tool_def)
            logger.debug(f"Collected tool '{tool_info['name']}' from method '{method_name}' in plugin '{plugin.name}'")
        except (AttributeError, TypeError, KeyError) as e:
            logger.error(f"Failed to collect tool from method '{method_name}' in plugin '{plugin.name}': {e}")


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


def type_to_json_schema(py_type: Type[Any]) -> dict[str, Any]:
    """Convert a Python type to a JSON Schema type definition."""
    # Check if it's a Pydantic BaseModel
    try:
        from pydantic import BaseModel

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
    except (ImportError, TypeError):
        pass

    type_map: dict[Type[Any], dict[str, str]] = {
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
