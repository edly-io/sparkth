from typing import Any, Callable, Dict, List, Optional

from langchain_core.tools import BaseTool, StructuredTool
from pydantic import BaseModel, Field, create_model

from app.core.logger import get_logger
from app.plugins import get_plugin_manager

logger = get_logger(__name__)


class ToolRegistry:
    """Registry for managing LangChain tools."""

    def __init__(self) -> None:
        self._tools: Dict[str, BaseTool] = {}
        self._initialized = False

    def register_tool(self, tool: BaseTool) -> None:
        """Register a tool."""
        self._tools[tool.name] = tool
        logger.info(f"Registered tool: {tool.name}")

    def get_tool(self, name: str) -> Optional[BaseTool]:
        """Get a tool by name."""
        if not self._initialized:
            self.discover_plugin_tools()
        return self._tools.get(name)

    def get_all_tools(self) -> List[BaseTool]:
        """Get all registered tools."""
        if not self._initialized:
            self.discover_plugin_tools()
        return list(self._tools.values())
    
    def get_tools_by_names(self, names: List[str]) -> List[BaseTool]:
        """Get specific tools by their names."""
        if not self._initialized:
            self.discover_plugin_tools()
        return [self._tools[name] for name in names if name in self._tools]

    def get_tool_schemas(self) -> List[Dict[str, Any]]:
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
                    logger.error(f"Failed to convert MCP tool '{mcp_tool.get('name')}' to LangChain tool: {e}")
        
        self._initialized = True
        logger.info(f"Discovered {len(self._tools)} tools from plugins")

    def _convert_mcp_to_langchain_tool(self, mcp_tool: Dict[str, Any]) -> BaseTool:
        """Convert an MCP tool definition to a LangChain tool."""
        name = mcp_tool["name"]
        description = mcp_tool.get("description", "")
        handler = mcp_tool["handler"]
        input_schema = mcp_tool.get("inputSchema", {})
        
        args_schema = self._json_schema_to_pydantic(name, input_schema)
        
        async def tool_func(**kwargs: Any) -> str:
            """Wrapper for MCP tool handler."""
            try:
                result = await handler(**kwargs)
                if isinstance(result, dict):
                    import json
                    return json.dumps(result)
                return str(result)
            except Exception as e:
                return f"Error executing tool: {str(e)}"
        
        return StructuredTool(
            name=name,
            description=description,
            func=lambda **kwargs: handler(**kwargs),
            coroutine=tool_func,
            args_schema=args_schema,
        )

    def _json_schema_to_pydantic(self, model_name: str, json_schema: Dict[str, Any]) -> type[BaseModel]:
        """Convert JSON Schema to a Pydantic model."""
        properties = json_schema.get("properties", {})
        required = json_schema.get("required", [])
        
        field_definitions: Dict[str, Any] = {}
        
        for field_name, field_schema in properties.items():
            field_type = self._get_python_type(field_schema)
            is_required = field_name in required
            
            if is_required:
                field_definitions[field_name] = (field_type, Field(..., description=field_schema.get("description", "")))
            else:
                default_value = field_schema.get("default")
                field_definitions[field_name] = (field_type, Field(default=default_value, description=field_schema.get("description", "")))
        
        return create_model(model_name + "Input", **field_definitions)

    def _get_python_type(self, json_schema: Dict[str, Any]) -> type:
        """Map JSON Schema type to Python type."""
        json_type = json_schema.get("type", "string")
        type_map = {
            "string": str,
            "integer": int,
            "number": float,
            "boolean": bool,
            "array": list,
            "object": dict,
        }
        return type_map.get(json_type, str)


_tool_registry = ToolRegistry()


def get_tool_registry() -> ToolRegistry:
    """Get the global tool registry."""
    return _tool_registry


def refresh_tools() -> None:
    """Force refresh of tools from plugins."""
    global _tool_registry
    _tool_registry._initialized = False
    _tool_registry.discover_plugin_tools()
