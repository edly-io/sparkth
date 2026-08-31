import json
from typing import Any

from sparkth.lib.log import get_logger
from sparkth.plugins.chat.schemas import ChatCompletionRequest
from sparkth.plugins.chat.tools import ToolRegistry

logger = get_logger(__name__)


async def resolve_tools(
    request: ChatCompletionRequest,
    tool_registry: ToolRegistry,
) -> list[Any] | None:
    """Resolve the tool list from the request's tools field."""
    if request.tools == "none" or request.tools == []:
        logger.info("Tools explicitly disabled")
        return None
    if request.tools == "*" or request.tools == "all":
        tools = tool_registry.get_all_tools()
        logger.info("Auto-including all %d available tools (default)", len(tools))
        return tools
    if request.tools and isinstance(request.tools, list):
        tools = tool_registry.get_tools_by_names(request.tools)
        if not tools:
            logger.warning("No tools found for: %s", request.tools)
        return tools
    return None


def parse_metadata_list(model_metadata: str | None, key: str) -> list[dict[str, Any]] | None:
    """Extract a list value from a JSON-serialised metadata string."""
    if not model_metadata:
        return None
    try:
        meta = json.loads(model_metadata)
        value = meta.get(key)
        return value if isinstance(value, list) else None
    except (json.JSONDecodeError, AttributeError) as exc:
        logger.error("Failed to parse model_metadata for key %r: %s", key, exc)
        return None
