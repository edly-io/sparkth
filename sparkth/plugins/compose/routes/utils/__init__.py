import json
from collections.abc import Sequence
from typing import Any

from langchain_core.tools import BaseTool
from pydantic import TypeAdapter, ValidationError

from sparkth.lib.log import get_logger
from sparkth.lib.permissions import PLUGIN_USE
from sparkth.lib.permissions.scopes import PLUGIN, build_scope_path
from sparkth.plugins.compose.models import Message
from sparkth.plugins.compose.planner import ExistingPlan
from sparkth.plugins.compose.schemas import ChatCompletionRequest
from sparkth.plugins.compose.tools import ToolRegistry

logger = get_logger(__name__)


async def resolve_tools(
    request: ChatCompletionRequest,
    tool_registry: ToolRegistry,
    disabled_plugins: set[str],
    allowed_plugins: set[str] | None,
) -> list[BaseTool] | None:
    """Resolve the tools the request asks for: every tool for ``"*"`` or ``"all"``, the named ones
    for a list, and none for ``"none"`` or an empty list. A tool whose plugin is in
    ``disabled_plugins``, or is missing from ``allowed_plugins``, is never returned, however it was
    asked for. An ``allowed_plugins`` of ``None`` allows every plugin."""
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
    resolved: list[BaseTool] = []
    for tool in tools:
        plugin_name = tool_registry.plugin_for(tool.name)
        if plugin_name in disabled_plugins:
            continue
        # allowed_plugins is None if the grant is global
        if allowed_plugins is None or plugin_name in allowed_plugins:
            resolved.append(tool)
    return resolved


async def record_named_tool_denials(
    request: ChatCompletionRequest,
    tool_registry: ToolRegistry,
    disabled_plugins: set[str],
    allowed_plugins: set[str] | None,
) -> None:
    """Record a denial for each plugin missing from ``allowed_plugins`` whose tool the request asks
    for by name.

    A request for every tool names none, so it records nothing. Neither does a named tool of a
    plugin in ``disabled_plugins``.
    """
    # allowed_plugins is None if the grant is global
    if allowed_plugins is None or not isinstance(request.tools, list):
        return
    named_plugins = {
        plugin_name for tool_name in request.tools if (plugin_name := tool_registry.plugin_for(tool_name)) is not None
    }
    for plugin_name in sorted(named_plugins - allowed_plugins - disabled_plugins):
        await PLUGIN_USE.record_denial(PLUGIN, build_scope_path(PLUGIN, plugin_name))


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
