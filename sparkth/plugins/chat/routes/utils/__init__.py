import json
from typing import Any

from langchain_core.tools import BaseTool

from sparkth.lib.chat.hooks import ChatResponsibility
from sparkth.lib.log import get_logger
from sparkth.plugins.chat.responsibilities import binds_category
from sparkth.plugins.chat.schemas import ChatCompletionRequest
from sparkth.plugins.chat.tools import ToolRegistry

logger = get_logger(__name__)


async def resolve_tools(
    request: ChatCompletionRequest,
    responsibility: ChatResponsibility,
    tool_registry: ToolRegistry,
) -> list[BaseTool] | None:
    """Resolve the request's tools, keeping only the categories the conversation's job binds.

    The job filter applies to every request shape, so naming another job's tool explicitly
    does not bind it either.
    """
    if request.tools == "none" or request.tools == []:
        logger.info("Tools explicitly disabled")
        return None
    if request.tools == "*" or request.tools == "all":
        tools = tool_registry.get_all_tools()
    elif request.tools and isinstance(request.tools, list):
        tools = tool_registry.get_tools_by_names(request.tools)
        if not tools:
            logger.warning("No tools found for: %s", request.tools)
    else:
        return None
    bound = [tool for tool in tools if binds_category(responsibility, tool_registry.category_for(tool.name))]
    logger.info("Bound %d of %d requested tools for responsibility %s", len(bound), len(tools), responsibility.name)
    return bound


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


def parse_metadata_flag(model_metadata: str | None, key: str) -> bool:
    """Read a boolean from a JSON-serialised metadata string, defaulting to False."""
    if not model_metadata:
        return False
    try:
        meta = json.loads(model_metadata)
        return bool(meta.get(key, False))
    except (json.JSONDecodeError, AttributeError) as exc:
        logger.error("Failed to parse model_metadata for key %r: %s", key, exc)
        return False
