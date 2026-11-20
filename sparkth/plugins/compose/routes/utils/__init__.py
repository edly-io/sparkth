import json
from collections.abc import Sequence
from typing import Any

from langchain_core.tools import BaseTool
from pydantic import TypeAdapter, ValidationError

from sparkth.lib.log import get_logger
from sparkth.plugins.compose.models import Message
from sparkth.plugins.compose.planner import ExistingPlan
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


def get_existing_plan_or_none(conversation_messages: Sequence[Message]) -> ExistingPlan | None:
    """The existing plan saved with the latest reply in ``conversation_messages``, or None when that reply
    saved none or its plan can't be read.

    Error messages are skipped: a failed turn saves its partial reply, plan included, before the
    error message."""
    latest_reply = next(
        (
            message
            for message in reversed(conversation_messages)
            if message.role == "assistant" and not message.is_error
        ),
        None,
    )
    if latest_reply is None:
        return None
    stored = parse_metadata_value(latest_reply.model_metadata, "plan")
    if stored is None:
        return None
    try:
        return TypeAdapter(ExistingPlan).validate_python(stored)
    except ValidationError as exc:
        logger.error(
            "The plan stored with message %s (conversation %s) is not a valid plan; the plan is dropped: %s",
            latest_reply.id,
            latest_reply.conversation_id,
            exc.errors(include_url=False, include_input=False),
        )
        return None


def parse_metadata_value(model_metadata: str | None, key: str) -> Any:
    """The value under ``key`` in a JSON-serialised metadata string, or None when it has none or can't
    be read."""
    if not model_metadata:
        return None
    try:
        metadata = json.loads(model_metadata)
    except json.JSONDecodeError as exc:
        logger.error("Failed to parse model_metadata for key %r: %s", key, exc)
        return None
    return metadata.get(key) if isinstance(metadata, dict) else None


def parse_metadata_list(model_metadata: str | None, key: str) -> list[dict[str, Any]] | None:
    """Extract a list value from a JSON-serialised metadata string."""
    value = parse_metadata_value(model_metadata, key)
    return value if isinstance(value, list) else None


def parse_metadata_flag(model_metadata: str | None, key: str) -> bool:
    """Read a boolean from a JSON-serialised metadata string, defaulting to False."""
    return bool(parse_metadata_value(model_metadata, key))
