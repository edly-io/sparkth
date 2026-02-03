import asyncio
import json
from typing import Any, get_type_hints

from langchain_core.tools import BaseTool, StructuredTool
from pydantic import BaseModel, Field, create_model

from app.core.logger import get_logger
from app.plugins import get_plugin_manager

logger = get_logger(__name__)


class ToolRegistry:
    """Registry for managing LangChain tools."""

    def __init__(self) -> None:
        self._tools: dict[str, BaseTool] = {}
        self._initialized = False

    def register_tool(self, tool: BaseTool) -> None:
        """Register a tool."""
        self._tools[tool.name] = tool
        logger.info(f"Registered tool: {tool.name}")

    async def get_tool(self, name: str) -> BaseTool | None:
        """Get a tool by name."""
        if not self._initialized:
            self.discover_plugin_tools()
        return self._tools.get(name)

    async def get_all_tools(self) -> list[BaseTool]:
        """Get all registered tools."""
        if not self._initialized:
            self.discover_plugin_tools()

        return list(self._tools.values())

    async def get_tools_by_names(self, names: list[str]) -> list[BaseTool]:
        """Get specific tools by their names."""
        if not self._initialized:
            self.discover_plugin_tools()
        return [self._tools[name] for name in names if name in self._tools]

    async def get_tool_schemas(self) -> list[dict[str, Any]]:
        """Get schemas for all tools."""
        if not self._initialized:
            self.discover_plugin_tools()
        return [
            {
                "name": tool.name,
                "description": tool.description,
                "parameters": tool.args if hasattr(tool, "args") else {},
            }
            for tool in self._tools.values()
        ]

    def discover_plugin_tools(self) -> None:
        """Discover and register tools from all loaded plugins."""
        if self._initialized:
            return

        plugin_manager = get_plugin_manager()
        loaded_plugins = plugin_manager.get_loaded_plugins()

        for plugin_name, plugin in loaded_plugins.items():
            if plugin_name == "chat":
                continue

            mcp_tools = plugin.get_mcp_tools()
            for mcp_tool in mcp_tools:
                try:
                    langchain_tool = self._convert_mcp_to_langchain_tool(mcp_tool)
                    self.register_tool(langchain_tool)
                except Exception as e:
                    logger.error(
                        f"Failed to convert MCP tool '{mcp_tool.get('name')}' to LangChain tool: {e}", exc_info=True
                    )

        self._initialized = True
        logger.info(f"Discovered {len(self._tools)} tools from plugins")

    def _get_handler_type_hints(self, handler: Any) -> dict[str, Any]:
        """Extract type hints from the handler function."""
        try:
            if hasattr(handler, "__func__"):
                func = handler.__func__
            else:
                func = handler

            hints = get_type_hints(func)
            hints.pop("return", None)
            hints.pop("self", None)
            return hints
        except Exception as e:
            logger.debug(f"Could not get type hints: {e}")
            return {}

    def _convert_mcp_to_langchain_tool(self, mcp_tool: dict[str, Any]) -> BaseTool:
        """Convert an MCP tool definition to a LangChain tool."""
        name = mcp_tool["name"]
        description = mcp_tool.get("description", "")
        handler = mcp_tool["handler"]
        input_schema = mcp_tool.get("inputSchema", {})

        logger.debug(f"Tool '{name}' input schema: {json.dumps(input_schema, indent=2)}")

        args_schema = self._json_schema_to_pydantic(name, input_schema)
        handler_hints = self._get_handler_type_hints(handler)

        async def tool_func(**kwargs: Any) -> str:
            """Async wrapper for MCP tool handler."""
            try:
                logger.debug(f"Tool '{name}' received raw args: {kwargs}")

                # Convert arguments to match handler's expected types
                converted_args = self._convert_args_to_handler_types(kwargs, handler_hints)
                logger.debug(f"Tool '{name}' converted args: {converted_args}")

                result = await handler(**converted_args)

                if isinstance(result, (dict, list)):
                    return json.dumps(result, indent=2, default=str)
                if isinstance(result, BaseModel):
                    return result.model_dump_json(indent=2)
                return str(result)
            except Exception as e:
                logger.error(f"Error executing tool '{name}': {e}", exc_info=True)
                return f"Error executing tool: {str(e)}"

        def sync_tool_func(**kwargs: Any) -> str:
            """Sync wrapper for MCP tool handler."""
            try:
                logger.debug(f"Tool '{name}' received raw args (sync): {kwargs}")

                converted_args = self._convert_args_to_handler_types(kwargs, handler_hints)
                logger.debug(f"Tool '{name}' converted args (sync): {converted_args}")

                loop = asyncio.new_event_loop()
                try:
                    result = loop.run_until_complete(handler(**converted_args))
                finally:
                    loop.close()

                if isinstance(result, (dict, list)):
                    return json.dumps(result, indent=2, default=str)
                if isinstance(result, BaseModel):
                    return result.model_dump_json(indent=2)
                return str(result)
            except Exception as e:
                logger.error(f"Error executing tool '{name}': {e}", exc_info=True)
                return f"Error executing tool: {str(e)}"

        return StructuredTool(
            name=name,
            description=description,
            func=sync_tool_func,
            coroutine=tool_func,
            args_schema=args_schema,
        )

    def _convert_args_to_handler_types(self, args: dict[str, Any], handler_hints: dict[str, Any]) -> dict[str, Any]:
        """
        Convert arguments to match the handler's expected types.

        Handles:
        - JSON strings -> dict -> Pydantic model
        - dict -> Pydantic model
        - Already correct type -> pass through
        """
        converted = {}

        for arg_name, arg_value in args.items():
            expected_type = handler_hints.get(arg_name)

            if expected_type is None:
                # No type hint, pass through as-is
                converted[arg_name] = arg_value
                continue

            # Check if expected type is a Pydantic model
            is_pydantic = isinstance(expected_type, type) and issubclass(expected_type, BaseModel)

            if is_pydantic:
                converted[arg_name] = self._convert_to_pydantic(arg_value, expected_type)
            else:
                converted[arg_name] = arg_value

        return converted

    def _convert_to_pydantic(self, value: Any, model_class: type[BaseModel]) -> BaseModel:
        """
        Convert a value to a Pydantic model instance.

        Handles:
        - Already a model instance -> return as-is
        - dict -> create model from dict
        - JSON string -> parse and create model
        """
        # Already the correct type
        if isinstance(value, model_class):
            return value

        # It's a dict, create model directly
        if isinstance(value, dict):
            return model_class(**value)

        # It's a string, try to parse as JSON
        if isinstance(value, str):
            try:
                parsed = json.loads(value)
                if isinstance(parsed, dict):
                    return model_class(**parsed)
                else:
                    raise ValueError(f"Expected dict after JSON parsing, got {type(parsed)}")
            except json.JSONDecodeError as e:
                raise ValueError(f"Failed to parse JSON string: {e}")

        # Unknown type
        raise ValueError(f"Cannot convert {type(value)} to {model_class.__name__}")

    def _json_schema_to_pydantic(self, model_name: str, json_schema: dict[str, Any]) -> type[BaseModel]:
        """Convert JSON Schema to a Pydantic model."""
        properties = json_schema.get("properties", {})
        required = json_schema.get("required", [])
        defs = json_schema.get("$defs", {})

        field_definitions: dict[str, Any] = {}

        for field_name, field_schema in properties.items():
            # Resolve $ref if present
            resolved_schema = self._resolve_ref(field_schema, defs)

            field_type = self._get_python_type(resolved_schema)
            field_description = resolved_schema.get("description", "")
            is_required = field_name in required

            if is_required:
                field_definitions[field_name] = (
                    field_type,
                    Field(..., description=field_description),
                )
            else:
                default_value = resolved_schema.get("default")
                field_definitions[field_name] = (
                    field_type | None,
                    Field(default=default_value, description=field_description),
                )

        return create_model(model_name + "Input", **field_definitions)

    def _resolve_ref(self, schema: dict[str, Any], defs: dict[str, Any]) -> dict[str, Any]:
        """Resolve a $ref in a schema."""
        if not isinstance(schema, dict):
            return schema

        if "$ref" in schema:
            ref_path = schema["$ref"]
            if ref_path.startswith("#/$defs/"):
                def_name = ref_path.split("/")[-1]
                if def_name in defs:
                    resolved: dict[str, Any] = defs[def_name].copy()
                    for key, value in schema.items():
                        if key != "$ref":
                            resolved[key] = value
                    return resolved

        return schema

    def _get_python_type(self, json_schema: dict[str, Any]) -> type:
        """Map JSON Schema type to Python type."""
        json_type = json_schema.get("type", "string")

        if "anyOf" in json_schema:
            types = [t.get("type") for t in json_schema["anyOf"] if t.get("type") and t.get("type") != "null"]
            if types:
                json_type = types[0]
        type_map = {
            "string": str,
            "integer": int,
            "number": float,
            "boolean": bool,
            "array": list,
            "object": dict,
            "null": type(None),
        }
        return type_map.get(json_type, str)


_tool_registry = ToolRegistry()


def get_tool_registry() -> ToolRegistry:
    """Get the global tool registry."""
    return _tool_registry


async def refresh_tools() -> None:
    """Force refresh of tools from plugins."""
    global _tool_registry
    _tool_registry._initialized = False
    _tool_registry._tools = {}
    _tool_registry.discover_plugin_tools()
