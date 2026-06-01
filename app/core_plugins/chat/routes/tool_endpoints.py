from fastapi import APIRouter, Depends

from app.api.v1.auth import get_current_user
from app.core_plugins.chat.schemas import ToolListResponse, ToolSchema
from app.core_plugins.chat.tools import get_parameters_schema, get_tool_registry
from app.models.user import User

router = APIRouter()


@router.get("/tools", response_model=ToolListResponse)
async def list_tools(
    _current_user: User = Depends(get_current_user),
) -> ToolListResponse:
    """List all available tools from loaded plugins."""
    tool_registry = get_tool_registry()
    tools = await tool_registry.get_all_tools()

    tool_schemas = [
        ToolSchema(
            name=tool.name,
            description=tool.description or "",
            parameters=get_parameters_schema(tool.args_schema),
        )
        for tool in tools
    ]

    return ToolListResponse(
        tools=tool_schemas,
        total=len(tool_schemas),
    )
