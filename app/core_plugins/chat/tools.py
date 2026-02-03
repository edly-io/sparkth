# import asyncio
# import json
# from typing import Any, Dict, List, Optional

# from langchain_core.tools import BaseTool, StructuredTool
# from pydantic import BaseModel, Field, create_model

# from app.core.logger import get_logger
# from app.plugins import get_plugin_manager
# from app.mcp.server import mcp

# logger = get_logger(__name__)


# class ToolRegistry:
#     """Registry for managing LangChain tools."""

#     def __init__(self) -> None:
#         self._tools: Dict[str, BaseTool] = {}
#         self._initialized = False

#     def register_tool(self, tool: BaseTool) -> None:
#         """Register a tool."""
#         self._tools[tool.name] = tool
#         logger.info(f"Registered tool: {tool.name}")

#     async def get_tool(self, name: str) -> Optional[BaseTool]:
#         """Get a tool by name."""
#         if not self._initialized:
#             self.discover_plugin_tools()
#         return self._tools.get(name)

#     async def get_all_tools(self) -> List[BaseTool]:
#         """Get all registered tools."""
#         if not self._initialized:
#             self.discover_plugin_tools()
            
#         return list(self._tools.values())

#     async def get_tools_by_names(self, names: List[str]) -> List[BaseTool]:
#         """Get specific tools by their names."""
#         if not self._initialized:
#             self.discover_plugin_tools()
#         return [self._tools[name] for name in names if name in self._tools]

#     async def get_tool_schemas(self) -> List[Dict[str, Any]]:
#         """Get schemas for all tools."""
#         if not self._initialized:
#             self.discover_plugin_tools()
#         return [
#             {
#                 "name": tool.name,
#                 "description": tool.description,
#                 "parameters": tool.args if hasattr(tool, "args") else {},
#             }
#             for tool in self._tools.values()
#         ]

#     def discover_plugin_tools(self) -> None:
#         """Discover and register tools from all loaded plugins."""
#         if self._initialized:
#             return

#         plugin_manager = get_plugin_manager()
#         loaded_plugins = plugin_manager.get_loaded_plugins()

#         for plugin_name, plugin in loaded_plugins.items():
#             if plugin_name == "chat":
#                 continue

#             mcp_tools = plugin.get_mcp_tools()
#             for mcp_tool in mcp_tools:
#                 try:
#                     langchain_tool = self._convert_mcp_to_langchain_tool(mcp_tool)
#                     self.register_tool(langchain_tool)
#                 except Exception as e:
#                     logger.error(f"Failed to convert MCP tool '{mcp_tool.get('name')}' to LangChain tool: {e}")

#         self._initialized = True
#         logger.info(f"Discovered {len(self._tools)} tools from plugins")

#     def _convert_mcp_to_langchain_tool(self, mcp_tool: Dict[str, Any]) -> BaseTool:
#         """Convert an MCP tool definition to a LangChain tool."""
#         name = mcp_tool["name"]
#         description = mcp_tool.get("description", "")
#         handler = mcp_tool["handler"]
#         input_schema = mcp_tool.get("inputSchema", {})
#         logger.debug(f"Tool '{name}' input schema: {json.dumps(input_schema, indent=2)}")


#         args_schema = self._json_schema_to_pydantic(name, input_schema)

#         async def tool_func(**kwargs: Any) -> str:
#             """Wrapper for MCP tool handler."""
#             try:
#                 result = await handler(**kwargs)
#                 if isinstance(result, dict):
#                     import json

#                     return json.dumps(result)
#                 return str(result)
#             except Exception as e:
#                 return f"Error executing tool: {str(e)}"

#         return StructuredTool(
#             name=name,
#             description=description,
#             func=lambda **kwargs: handler(**kwargs),
#             coroutine=tool_func,
#             args_schema=args_schema,
#         )

#     def _json_schema_to_pydantic(self, model_name: str, json_schema: Dict[str, Any]) -> type[BaseModel]:
#         """Convert JSON Schema to a Pydantic model."""
#         properties = json_schema.get("properties", {})
#         required = json_schema.get("required", [])

#         field_definitions: Dict[str, Any] = {}

#         for field_name, field_schema in properties.items():
#             field_type = self._get_python_type(field_schema)
#             is_required = field_name in required

#             if is_required:
#                 field_definitions[field_name] = (
#                     field_type,
#                     Field(..., description=field_schema.get("description", "")),
#                 )
#             else:
#                 default_value = field_schema.get("default")
#                 field_definitions[field_name] = (
#                     field_type,
#                     Field(default=default_value, description=field_schema.get("description", "")),
#                 )

#         return create_model(model_name + "Input", **field_definitions)

#     def _get_python_type(self, json_schema: Dict[str, Any]) -> type:
#         """Map JSON Schema type to Python type."""
#         json_type = json_schema.get("type", "string")
#         type_map = {
#             "string": str,
#             "integer": int,
#             "number": float,
#             "boolean": bool,
#             "array": list,
#             "object": dict,
#         }
#         return type_map.get(json_type, str)


# _tool_registry = ToolRegistry()


# def get_tool_registry() -> ToolRegistry:
#     """Get the global tool registry."""
#     return _tool_registry


# async def refresh_tools() -> None:
#     """Force refresh of tools from plugins."""
#     global _tool_registry
#     _tool_registry._initialized = False
#     _tool_registry.discover_plugin_tools()


# import asyncio
# import json
# from typing import Any, Dict, List, Optional, get_type_hints

# from langchain_core.tools import BaseTool, StructuredTool
# from pydantic import BaseModel, Field, create_model

# from app.core.logger import get_logger
# from app.plugins import get_plugin_manager

# logger = get_logger(__name__)


# class ToolRegistry:
#     """Registry for managing LangChain tools."""

#     def __init__(self) -> None:
#         self._tools: Dict[str, BaseTool] = {}
#         self._initialized = False

#     def register_tool(self, tool: BaseTool) -> None:
#         """Register a tool."""
#         self._tools[tool.name] = tool
#         logger.info(f"Registered tool: {tool.name}")

#     async def get_tool(self, name: str) -> Optional[BaseTool]:
#         """Get a tool by name."""
#         if not self._initialized:
#             self.discover_plugin_tools()
#         return self._tools.get(name)

#     async def get_all_tools(self) -> List[BaseTool]:
#         """Get all registered tools."""
#         if not self._initialized:
#             self.discover_plugin_tools()
            
#         return list(self._tools.values())

#     async def get_tools_by_names(self, names: List[str]) -> List[BaseTool]:
#         """Get specific tools by their names."""
#         if not self._initialized:
#             self.discover_plugin_tools()
#         return [self._tools[name] for name in names if name in self._tools]

#     async def get_tool_schemas(self) -> List[Dict[str, Any]]:
#         """Get schemas for all tools."""
#         if not self._initialized:
#             self.discover_plugin_tools()
#         return [
#             {
#                 "name": tool.name,
#                 "description": tool.description,
#                 "parameters": tool.args if hasattr(tool, "args") else {},
#             }
#             for tool in self._tools.values()
#         ]

#     def discover_plugin_tools(self) -> None:
#         """Discover and register tools from all loaded plugins."""
#         if self._initialized:
#             return

#         plugin_manager = get_plugin_manager()
#         loaded_plugins = plugin_manager.get_loaded_plugins()

#         for plugin_name, plugin in loaded_plugins.items():
#             if plugin_name == "chat":
#                 continue

#             mcp_tools = plugin.get_mcp_tools()
#             for mcp_tool in mcp_tools:
#                 try:
#                     langchain_tool = self._convert_mcp_to_langchain_tool(mcp_tool)
#                     self.register_tool(langchain_tool)
#                 except Exception as e:
#                     logger.error(f"Failed to convert MCP tool '{mcp_tool.get('name')}' to LangChain tool: {e}", exc_info=True)

#         self._initialized = True
#         logger.info(f"Discovered {len(self._tools)} tools from plugins")

#     def _get_handler_type_hints(self, handler: Any) -> Dict[str, Any]:
#         """Extract type hints from the handler function."""
#         try:
#             if hasattr(handler, '__func__'):
#                 func = handler.__func__
#             else:
#                 func = handler
            
#             hints = get_type_hints(func)
#             hints.pop('return', None)
#             hints.pop('self', None)
#             return hints
#         except Exception as e:
#             logger.debug(f"Could not get type hints: {e}")
#             return {}

#     def _convert_mcp_to_langchain_tool(self, mcp_tool: Dict[str, Any]) -> BaseTool:
#         """Convert an MCP tool definition to a LangChain tool."""
#         name = mcp_tool["name"]
#         description = mcp_tool.get("description", "")
#         handler = mcp_tool["handler"]
#         input_schema = mcp_tool.get("inputSchema", {})

#         logger.debug(f"Tool '{name}' input schema: {json.dumps(input_schema, indent=2)}")

#         args_schema = self._json_schema_to_pydantic(name, input_schema)
#         handler_hints = self._get_handler_type_hints(handler)

#         async def tool_func(**kwargs: Any) -> str:
#             """Async wrapper for MCP tool handler."""
#             try:
#                 logger.debug(f"Tool '{name}' received raw args: {kwargs}")
                
#                 # Convert arguments to match handler's expected types
#                 converted_args = self._convert_args_to_handler_types(kwargs, handler_hints)
#                 logger.debug(f"Tool '{name}' converted args: {converted_args}")
                
#                 result = await handler(**converted_args)
                
#                 if isinstance(result, (dict, list)):
#                     return json.dumps(result, indent=2, default=str)
#                 if isinstance(result, BaseModel):
#                     return result.model_dump_json(indent=2)
#                 return str(result)
#             except Exception as e:
#                 logger.error(f"Error executing tool '{name}': {e}", exc_info=True)
#                 return f"Error executing tool: {str(e)}"

#         def sync_tool_func(**kwargs: Any) -> str:
#             """Sync wrapper for MCP tool handler."""
#             try:
#                 logger.debug(f"Tool '{name}' received raw args (sync): {kwargs}")
                
#                 converted_args = self._convert_args_to_handler_types(kwargs, handler_hints)
#                 logger.debug(f"Tool '{name}' converted args (sync): {converted_args}")
                
#                 loop = asyncio.new_event_loop()
#                 try:
#                     result = loop.run_until_complete(handler(**converted_args))
#                 finally:
#                     loop.close()
                
#                 if isinstance(result, (dict, list)):
#                     return json.dumps(result, indent=2, default=str)
#                 if isinstance(result, BaseModel):
#                     return result.model_dump_json(indent=2)
#                 return str(result)
#             except Exception as e:
#                 logger.error(f"Error executing tool '{name}': {e}", exc_info=True)
#                 return f"Error executing tool: {str(e)}"

#         return StructuredTool(
#             name=name,
#             description=description,
#             func=sync_tool_func,
#             coroutine=tool_func,
#             args_schema=args_schema,
#         )

#     def _convert_args_to_handler_types(
#         self, 
#         args: Dict[str, Any], 
#         handler_hints: Dict[str, Any]
#     ) -> Dict[str, Any]:
#         """
#         Convert arguments to match the handler's expected types.
        
#         Handles:
#         - JSON strings -> dict -> Pydantic model
#         - dict -> Pydantic model
#         - Already correct type -> pass through
#         """
#         converted = {}
        
#         for arg_name, arg_value in args.items():
#             expected_type = handler_hints.get(arg_name)
            
#             if expected_type is None:
#                 # No type hint, pass through as-is
#                 converted[arg_name] = arg_value
#                 continue
            
#             # Check if expected type is a Pydantic model
#             is_pydantic = isinstance(expected_type, type) and issubclass(expected_type, BaseModel)
            
#             if is_pydantic:
#                 converted[arg_name] = self._convert_to_pydantic(arg_value, expected_type)
#             else:
#                 converted[arg_name] = arg_value
        
#         return converted

#     def _convert_to_pydantic(self, value: Any, model_class: type[BaseModel]) -> BaseModel:
#         """
#         Convert a value to a Pydantic model instance.
        
#         Handles:
#         - Already a model instance -> return as-is
#         - Dict -> create model from dict
#         - JSON string -> parse and create model
#         """
#         # Already the correct type
#         if isinstance(value, model_class):
#             return value
        
#         # It's a dict, create model directly
#         if isinstance(value, dict):
#             return model_class(**value)
        
#         # It's a string, try to parse as JSON
#         if isinstance(value, str):
#             try:
#                 parsed = json.loads(value)
#                 if isinstance(parsed, dict):
#                     return model_class(**parsed)
#                 else:
#                     raise ValueError(f"Expected dict after JSON parsing, got {type(parsed)}")
#             except json.JSONDecodeError as e:
#                 raise ValueError(f"Failed to parse JSON string: {e}")
        
#         # Unknown type
#         raise ValueError(f"Cannot convert {type(value)} to {model_class.__name__}")

#     def _json_schema_to_pydantic(self, model_name: str, json_schema: Dict[str, Any]) -> type[BaseModel]:
#         """Convert JSON Schema to a Pydantic model."""
#         properties = json_schema.get("properties", {})
#         required = json_schema.get("required", [])
#         defs = json_schema.get("$defs", {})

#         field_definitions: Dict[str, Any] = {}

#         for field_name, field_schema in properties.items():
#             # Resolve $ref if present
#             resolved_schema = self._resolve_ref(field_schema, defs)
            
#             field_type = self._get_python_type(resolved_schema)
#             field_description = resolved_schema.get("description", "")
#             is_required = field_name in required

#             if is_required:
#                 field_definitions[field_name] = (
#                     field_type,
#                     Field(..., description=field_description),
#                 )
#             else:
#                 default_value = resolved_schema.get("default")
#                 field_definitions[field_name] = (
#                     Optional[field_type],
#                     Field(default=default_value, description=field_description),
#                 )

#         return create_model(model_name + "Input", **field_definitions)

#     def _resolve_ref(self, schema: Dict[str, Any], defs: Dict[str, Any]) -> Dict[str, Any]:
#         """Resolve a $ref in a schema."""
#         if not isinstance(schema, dict):
#             return schema
        
#         if "$ref" in schema:
#             ref_path = schema["$ref"]
#             if ref_path.startswith("#/$defs/"):
#                 def_name = ref_path.split("/")[-1]
#                 if def_name in defs:
#                     resolved = defs[def_name].copy()
#                     for key, value in schema.items():
#                         if key != "$ref":
#                             resolved[key] = value
#                     return resolved
        
#         return schema

#     def _get_python_type(self, json_schema: Dict[str, Any]) -> type:
#         """Map JSON Schema type to Python type."""
#         json_type = json_schema.get("type", "string")
        
#         if "anyOf" in json_schema:
#             types = [t.get("type") for t in json_schema["anyOf"] if t.get("type") and t.get("type") != "null"]
#             if types:
#                 json_type = types[0]
        
#         type_map = {
#             "string": str,
#             "integer": int,
#             "number": float,
#             "boolean": bool,
#             "array": list,
#             "object": dict,
#             "null": type(None),
#         }
#         return type_map.get(json_type, str)


# _tool_registry = ToolRegistry()


# def get_tool_registry() -> ToolRegistry:
#     """Get the global tool registry."""
#     return _tool_registry


# async def refresh_tools() -> None:
#     """Force refresh of tools from plugins."""
#     global _tool_registry
#     _tool_registry._initialized = False
#     _tool_registry._tools = {}
#     _tool_registry.discover_plugin_tools()



import asyncio
import json
from typing import Any, Dict, List, Optional, get_type_hints

from langchain_core.tools import BaseTool, StructuredTool
from pydantic import BaseModel, Field, ValidationError, create_model

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

    async def get_tool(self, name: str) -> Optional[BaseTool]:
        """Get a tool by name."""
        if not self._initialized:
            self.discover_plugin_tools()
        return self._tools.get(name)

    async def get_all_tools(self) -> List[BaseTool]:
        """Get all registered tools."""
        if not self._initialized:
            self.discover_plugin_tools()
            
        return list(self._tools.values())

    async def get_tools_by_names(self, names: List[str]) -> List[BaseTool]:
        """Get specific tools by their names."""
        if not self._initialized:
            self.discover_plugin_tools()
        return [self._tools[name] for name in names if name in self._tools]

    async def get_tool_schemas(self) -> List[Dict[str, Any]]:
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
                    logger.error(f"Failed to convert MCP tool '{mcp_tool.get('name')}' to LangChain tool: {e}", exc_info=True)

        self._initialized = True
        logger.info(f"Discovered {len(self._tools)} tools from plugins")

    def _get_handler_type_hints(self, handler: Any) -> Dict[str, Any]:
        """Extract type hints from the handler function."""
        try:
            if hasattr(handler, '__func__'):
                func = handler.__func__
            else:
                func = handler
            
            hints = get_type_hints(func)
            hints.pop('return', None)
            hints.pop('self', None)
            return hints
        except Exception as e:
            logger.debug(f"Could not get type hints: {e}")
            return {}

    def _convert_mcp_to_langchain_tool(self, mcp_tool: Dict[str, Any]) -> BaseTool:
        """Convert an MCP tool definition to a LangChain tool."""
        name = mcp_tool["name"]
        description = mcp_tool.get("description", "")
        handler = mcp_tool["handler"]
        input_schema = mcp_tool.get("inputSchema", {})

        # Get handler type hints for later conversion
        handler_hints = self._get_handler_type_hints(handler)
        
        # Create an expanded/flattened schema for the LLM
        # This makes nested fields visible as top-level parameters
        expanded_schema, field_mapping = self._expand_schema(input_schema)
        
        logger.debug(f"Tool '{name}' original schema: {json.dumps(input_schema, indent=2)}")
        logger.debug(f"Tool '{name}' expanded schema: {json.dumps(expanded_schema, indent=2)}")
        logger.debug(f"Tool '{name}' field mapping: {field_mapping}")
        
        # Create Pydantic model from expanded schema
        args_schema = self._json_schema_to_pydantic(name, expanded_schema)

        async def tool_func(**kwargs: Any) -> str:
            """Async wrapper for MCP tool handler."""
            try:
                logger.info(f"Tool '{name}' received args: {json.dumps(kwargs, indent=2, default=str)}")
                
                # Reconstruct nested structure from flattened args
                reconstructed_args = self._reconstruct_nested_args(kwargs, field_mapping)
                logger.info(f"Tool '{name}' reconstructed args: {json.dumps(reconstructed_args, indent=2, default=str)}")
                
                # Convert to Pydantic models where expected
                final_args = self._convert_args_to_handler_types(reconstructed_args, handler_hints)
                logger.info(f"Tool '{name}' final args types: {[(k, type(v).__name__) for k, v in final_args.items()]}")
                
                result = await handler(**final_args)
                
                if isinstance(result, (dict, list)):
                    return json.dumps(result, indent=2, default=str)
                if isinstance(result, BaseModel):
                    return result.model_dump_json(indent=2)
                return str(result)
            except ValidationError as e:
                logger.error(f"Validation error for tool '{name}': {e}", exc_info=True)
                return self._format_validation_error(e, name, expanded_schema)
            except Exception as e:
                logger.error(f"Error executing tool '{name}': {e}", exc_info=True)
                return f"Error executing tool: {str(e)}"

        def sync_tool_func(**kwargs: Any) -> str:
            """Sync wrapper for MCP tool handler."""
            try:
                logger.info(f"Tool '{name}' received args (sync): {json.dumps(kwargs, indent=2, default=str)}")
                
                reconstructed_args = self._reconstruct_nested_args(kwargs, field_mapping)
                logger.info(f"Tool '{name}' reconstructed args (sync): {json.dumps(reconstructed_args, indent=2, default=str)}")
                
                final_args = self._convert_args_to_handler_types(reconstructed_args, handler_hints)
                logger.info(f"Tool '{name}' final args types (sync): {[(k, type(v).__name__) for k, v in final_args.items()]}")
                
                loop = asyncio.new_event_loop()
                try:
                    result = loop.run_until_complete(handler(**final_args))
                finally:
                    loop.close()
                
                if isinstance(result, (dict, list)):
                    return json.dumps(result, indent=2, default=str)
                if isinstance(result, BaseModel):
                    return result.model_dump_json(indent=2)
                return str(result)
            except ValidationError as e:
                logger.error(f"Validation error for tool '{name}': {e}", exc_info=True)
                return self._format_validation_error(e, name, expanded_schema)
            except Exception as e:
                logger.error(f"Error executing tool '{name}': {e}", exc_info=True)
                return f"Error executing tool: {str(e)}"

        # Enhance description with schema info
        enhanced_description = self._enhance_description(description, expanded_schema)

        return StructuredTool(
            name=name,
            description=enhanced_description,
            func=sync_tool_func,
            coroutine=tool_func,
            args_schema=args_schema,
        )

    def _expand_schema(self, schema: Dict[str, Any], prefix: str = "") -> tuple[Dict[str, Any], Dict[str, str]]:
        """
        Expand nested object schemas into flat fields.
        
        Example:
            Input: {auth: {lms_url, studio_url}, course: {org, number, run}}
            Output: {auth__lms_url, auth__studio_url, course__org, course__number, course__run}
        
        Returns:
            - expanded_schema: Flattened schema with all nested fields at top level
            - field_mapping: Maps flat field names to their nested paths
        """
        defs = schema.get("$defs", {})
        properties = schema.get("properties", {})
        required = schema.get("required", [])
        
        expanded_properties = {}
        expanded_required = []
        field_mapping = {}
        
        for prop_name, prop_schema in properties.items():
            # Resolve $ref
            resolved = self._resolve_ref(prop_schema, defs)
            full_name = f"{prefix}{prop_name}" if prefix else prop_name
            
            # Check if this is a nested object
            if resolved.get("type") == "object" and "properties" in resolved:
                nested_required = resolved.get("required", [])
                nested_props = resolved.get("properties", {})
                
                for nested_name, nested_schema in nested_props.items():
                    nested_resolved = self._resolve_ref(nested_schema, defs)
                    flat_name = f"{prop_name}__{nested_name}"
                    
                    # Handle deeply nested objects recursively
                    if nested_resolved.get("type") == "object" and "properties" in nested_resolved:
                        deep_expanded, deep_mapping = self._expand_schema(
                            {"properties": {nested_name: nested_resolved}, "required": [nested_name] if nested_name in nested_required else []},
                            prefix=f"{prop_name}__"
                        )
                        expanded_properties.update(deep_expanded.get("properties", {}))
                        expanded_required.extend(deep_expanded.get("required", []))
                        for k, v in deep_mapping.items():
                            field_mapping[k] = f"{prop_name}.{v}"
                    else:
                        # Leaf field
                        desc = nested_resolved.get("description", "")
                        expanded_properties[flat_name] = {
                            **nested_resolved,
                            "description": f"[{prop_name}] {desc}" if desc else f"Field '{nested_name}' for '{prop_name}'"
                        }
                        field_mapping[flat_name] = f"{prop_name}.{nested_name}"
                        
                        # Mark as required if parent is required and field is required in parent
                        if prop_name in required and nested_name in nested_required:
                            expanded_required.append(flat_name)
            else:
                # Simple field, keep as-is
                expanded_properties[prop_name] = resolved
                field_mapping[prop_name] = prop_name
                if prop_name in required:
                    expanded_required.append(prop_name)
        
        return {
            "type": "object",
            "properties": expanded_properties,
            "required": expanded_required
        }, field_mapping

    def _reconstruct_nested_args(self, flat_args: Dict[str, Any], field_mapping: Dict[str, str]) -> Dict[str, Any]:
        """
        Reconstruct nested argument structure from flattened args.
        
        Example:
            Input: {auth__lms_url: "...", auth__studio_url: "..."}
            Output: {auth: {lms_url: "...", studio_url: "..."}}
        """
        reconstructed = {}
        
        for flat_name, value in flat_args.items():
            path = field_mapping.get(flat_name, flat_name)
            
            # Handle nested path like "auth.lms_url"
            parts = path.split(".")
            
            current = reconstructed
            for i, part in enumerate(parts[:-1]):
                if part not in current:
                    current[part] = {}
                current = current[part]
            
            current[parts[-1]] = value
        
        return reconstructed

    def _convert_args_to_handler_types(
        self, 
        args: Dict[str, Any], 
        handler_hints: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Convert arguments to match the handler's expected types (Pydantic models)."""
        converted = {}
        
        for arg_name, arg_value in args.items():
            expected_type = handler_hints.get(arg_name)
            
            if expected_type is None:
                converted[arg_name] = arg_value
                continue
            
            is_pydantic = isinstance(expected_type, type) and issubclass(expected_type, BaseModel)
            
            if is_pydantic:
                converted[arg_name] = self._convert_to_pydantic(arg_value, expected_type)
            else:
                converted[arg_name] = arg_value
        
        return converted

    def _convert_to_pydantic(self, value: Any, model_class: type[BaseModel]) -> BaseModel:
        """Convert a value to a Pydantic model instance."""
        if isinstance(value, model_class):
            return value
        
        if isinstance(value, dict):
            # Recursively convert nested dicts to Pydantic models
            converted_dict = {}
            for field_name, field_value in value.items():
                if field_name in model_class.model_fields:
                    field_info = model_class.model_fields[field_name]
                    field_type = field_info.annotation
                    
                    # Handle nested Pydantic models
                    if isinstance(field_type, type) and issubclass(field_type, BaseModel):
                        if isinstance(field_value, dict):
                            converted_dict[field_name] = self._convert_to_pydantic(field_value, field_type)
                        elif isinstance(field_value, str):
                            try:
                                parsed = json.loads(field_value)
                                converted_dict[field_name] = self._convert_to_pydantic(parsed, field_type)
                            except json.JSONDecodeError:
                                converted_dict[field_name] = field_value
                        else:
                            converted_dict[field_name] = field_value
                    else:
                        converted_dict[field_name] = field_value
                else:
                    converted_dict[field_name] = field_value
            
            return model_class(**converted_dict)
        
        if isinstance(value, str):
            try:
                parsed = json.loads(value)
                if isinstance(parsed, dict):
                    return self._convert_to_pydantic(parsed, model_class)
            except json.JSONDecodeError:
                pass
        
        raise ValueError(f"Cannot convert {type(value).__name__} to {model_class.__name__}")

    def _enhance_description(self, description: str, expanded_schema: Dict[str, Any]) -> str:
        """Add parameter information to the tool description."""
        properties = expanded_schema.get("properties", {})
        required = expanded_schema.get("required", [])
        
        if not properties:
            return description
        
        param_lines = []
        for name, schema in properties.items():
            param_type = schema.get("type", "string")
            is_required = name in required
            desc = schema.get("description", "")
            req_str = "REQUIRED" if is_required else "optional"
            param_lines.append(f"  - {name} ({param_type}, {req_str}): {desc}")
        
        params_section = "\n\nParameters:\n" + "\n".join(param_lines)
        
        return description + params_section

    def _format_validation_error(self, error: ValidationError, tool_name: str, schema: Dict[str, Any]) -> str:
        """Format validation error with helpful information."""
        errors = []
        for err in error.errors():
            loc = " -> ".join(str(x) for x in err["loc"])
            errors.append(f"  - {loc}: {err['msg']}")
        
        properties = schema.get("properties", {})
        required = schema.get("required", [])
        
        required_fields = []
        for name in required:
            field_schema = properties.get(name, {})
            field_type = field_schema.get("type", "string")
            required_fields.append(f"  - {name} ({field_type})")
        
        return (
            f"Validation error in '{tool_name}':\n"
            f"{chr(10).join(errors)}\n\n"
            f"Required fields:\n{chr(10).join(required_fields)}\n\n"
            f"Please provide all required fields."
        )

    def _resolve_ref(self, schema: Dict[str, Any], defs: Dict[str, Any]) -> Dict[str, Any]:
        """Resolve $ref references in schema."""
        if not isinstance(schema, dict):
            return schema
        
        if "$ref" in schema:
            ref_path = schema["$ref"]
            if ref_path.startswith("#/$defs/"):
                def_name = ref_path.split("/")[-1]
                if def_name in defs:
                    resolved = defs[def_name].copy()
                    for key, value in schema.items():
                        if key != "$ref":
                            resolved[key] = value
                    # Recursively resolve nested refs
                    return self._resolve_ref(resolved, defs)
        
        return schema

    def _json_schema_to_pydantic(self, model_name: str, json_schema: Dict[str, Any]) -> type[BaseModel]:
        """Convert JSON Schema to a Pydantic model."""
        properties = json_schema.get("properties", {})
        required = json_schema.get("required", [])

        field_definitions: Dict[str, Any] = {}

        for field_name, field_schema in properties.items():
            field_type = self._get_python_type(field_schema)
            field_description = field_schema.get("description", "")
            is_required = field_name in required

            if is_required:
                field_definitions[field_name] = (
                    field_type,
                    Field(..., description=field_description),
                )
            else:
                default_value = field_schema.get("default")
                field_definitions[field_name] = (
                    Optional[field_type],
                    Field(default=default_value, description=field_description),
                )

        return create_model(model_name + "Input", **field_definitions)

    def _get_python_type(self, json_schema: Dict[str, Any]) -> type:
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
