import json
from collections.abc import Sequence
from typing import Any

from langchain_core.tools import BaseTool

from sparkth.lib.log import get_logger
from sparkth.plugins.compose.models import Message
from sparkth.plugins.compose.planner import OpenPlan, read_open_plan
from sparkth.plugins.compose.schemas import ChatCompletionRequest
from sparkth.plugins.compose.tools import ToolRegistry

logger = get_logger(__name__)


async def resolve_tools(
    request: ChatCompletionRequest, tool_registry: ToolRegistry, disabled_plugins: set[str]
) -> list[BaseTool] | None:
    """Resolve the tools the request asks for: every tool for ``"*"`` or ``"all"``, the named ones
    for a list, and none for ``"none"`` or an empty list. A tool whose plugin is in
    ``disabled_plugins`` is never returned, however it was asked for."""
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
    return [tool for tool in tools if tool_registry.plugin_for(tool.name) not in disabled_plugins]


def open_plan_of(messages: Sequence[Message]) -> OpenPlan | None:
    """The plan the latest reply among ``messages`` left open, if it left one. An error is no reply:
    a turn that fails stores what it wrote, with its plan, before the error."""
    replies = [message for message in messages if message.role == "assistant" and not message.is_error]
    if not replies or not replies[-1].model_metadata:
        return None
    try:
        metadata = json.loads(replies[-1].model_metadata)
    except json.JSONDecodeError as exc:
        logger.error("Failed to parse the latest reply's metadata for its plan: %s", exc)
        return None
    return read_open_plan(metadata if isinstance(metadata, dict) else None)


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
