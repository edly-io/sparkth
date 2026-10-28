"""Run one chat turn against the model: with tools on a LangChain agent, without tools as a plain model call."""

import asyncio
import json
from collections.abc import AsyncGenerator, Awaitable, Callable, Sequence
from contextlib import aclosing
from dataclasses import replace
from typing import Any, cast

from langchain.agents import create_agent
from langchain.agents.middleware import (
    AgentMiddleware,
    ModelCallLimitMiddleware,
    ToolCallLimitMiddleware,
    ToolCallRequest,
    wrap_tool_call,
)
from langchain_core.messages import AIMessage, BaseMessage, SystemMessage, ToolMessage
from langchain_core.tools import BaseTool
from langgraph.types import Command

from sparkth.lib.audit import ToolFailureKind, tool_failure
from sparkth.lib.audit.context import AuditSource, ai_audit_context
from sparkth.lib.audit.events import AuditModelInfo
from sparkth.lib.audit.exceptions import AuditCaptureError
from sparkth.lib.llm import BaseChatProvider
from sparkth.lib.log import get_logger
from sparkth.lib.plugins import PluginConfigInvalidError, PluginNotConfiguredError

logger = get_logger(__name__)

_ToolCallHandler = Callable[[ToolCallRequest], Awaitable[ToolMessage | Command[Any]]]


def _reported_failure(result: Any) -> ToolFailureKind | None:
    """Classify a tool's result, decoding the JSON text the chat tool wrappers return."""
    if isinstance(result, str):
        try:
            result = json.loads(result)
        except ValueError, RecursionError:
            logger.debug("Tool result is not JSON; reading it as a success")
            return None
    return tool_failure(result)


def _text_blocks(content: str | list[str | dict[str, Any]]) -> list[str]:
    """The non-empty text of a model reply, one entry per text block."""
    blocks = [content] if isinstance(content, str) else content
    texts = (
        block if isinstance(block, str) else block.get("text", "")
        for block in blocks
        if isinstance(block, str) or block.get("type") == "text"
    )
    return [text for text in texts if text]


def _audit_model_info(turn_model: AuditModelInfo, messages: Sequence[BaseMessage]) -> AuditModelInfo:
    """Model identity recorded as audit provenance on a tool execution.

    ``turn_model`` carries the provider and the model as configured. ``version`` is the exact
    model the provider reported on the reply that requested the call (OpenAI exposes
    ``model_name``, Anthropic ``model``).
    """
    reply = next((message for message in reversed(messages) if isinstance(message, AIMessage)), None)
    metadata = reply.response_metadata if reply is not None else {}
    return replace(turn_model, version=metadata.get("model_name") or metadata.get("model"))


def _failed_call(request: ToolCallRequest, error: Exception) -> ToolMessage:
    """The model-visible result of a call whose tool raised."""
    name = request.tool_call["name"]
    return ToolMessage(
        f"Error executing tool '{name}': {error}", tool_call_id=request.tool_call["id"], name=name, status="error"
    )


async def _classified_tool_call(
    request: ToolCallRequest, handler: _ToolCallHandler
) -> tuple[ToolMessage | Command[Any], ToolFailureKind | None]:
    """Run one tool call and say how it failed (None on success).

    Invalid arguments and a tool name that is not bound come back from the handler as an
    error result, so they are a validation failure; a tool that raised is an unknown one.
    """
    name = request.tool_call["name"]
    try:
        result = await handler(request)
    # A fail-closed capture refusal is the audit infrastructure failing, not the tool: it must
    # surface as a hard failure, never degrade into a model-visible error string.
    except AuditCaptureError:
        logger.exception("Audit capture failed for tool '%s'", name)
        raise
    # A user with no usable plugin settings is an expected outcome, not a tool fault.
    except (PluginNotConfiguredError, PluginConfigInvalidError) as e:
        logger.warning("Tool '%s' cannot run for this user: %s", name, e)
        return _failed_call(request, e), ToolFailureKind.UNKNOWN
    # NOTE: Kept broad here intentionally — tool handlers are user-supplied plugins that can
    # raise anything. Narrowing would silently swallow legitimate errors from arbitrary
    # third-party tool implementations.
    except Exception as e:
        logger.error("Error executing tool '%s': %s", name, e, exc_info=True)
        return _failed_call(request, e), ToolFailureKind.UNKNOWN
    if not isinstance(result, ToolMessage):
        return result, None
    if result.status == "error":
        logger.warning("Tool '%s' call was refused: %s", name, result.text)
        return result, ToolFailureKind.VALIDATION
    return result, _reported_failure(result.content)


@wrap_tool_call
async def _chat_tool_call(request: ToolCallRequest, handler: _ToolCallHandler) -> ToolMessage | Command[Any]:
    """Run one of a chat turn's tool calls, reporting its start and end on the agent's stream.

    The call waits after reporting its start until the reader of the stream asks for the next
    event, so a reader that stops there keeps the tool from ever running. It runs inside an
    ``ai_audit_context`` so the audited tool wrapper attributes it to the chat surface and to
    the model reply that requested it.
    """
    name = request.tool_call["name"]
    go = asyncio.Event()
    request.runtime.stream_writer({"type": "tool_start", "name": name, "go": go})
    await go.wait()
    model = _audit_model_info(cast(AuditModelInfo, request.runtime.context), request.state["messages"])
    with ai_audit_context(AuditSource.CHAT, model):
        result, failure = await _classified_tool_call(request, handler)
    output = result.text if isinstance(result, ToolMessage) else ""
    arguments = request.tool_call["args"]
    request.runtime.stream_writer(
        {"type": "tool_end", "name": name, "failure": failure, "tool_input": arguments, "output": output}
    )
    return result


def _update_events(
    node: str,
    update: dict[str, Any] | None,
    limiter: ToolCallLimitMiddleware[Any, Any],
    cap: ModelCallLimitMiddleware[Any, Any],
) -> list[dict[str, Any]]:
    """The agent events one graph node's update stands for: blocked calls, or the closing reply.

    The tool-call ``limiter`` and the model-call ``cap`` add messages only when they act, and
    each time they do it is logged.
    """
    messages = (update or {}).get("messages", [])
    if node == f"{limiter.name}.after_model" and messages:
        logger.warning("Tool call limit (%s) reached; blocked %d call(s)", limiter.run_limit, len(messages))
        return [{"type": "limit_reached"}]
    if node == f"{cap.name}.before_model" and messages:
        logger.warning("Model call limit (%s) reached; the turn ends without an answer", cap.run_limit)
        return []
    if node == "model":
        return [
            {"type": "final", "message": message}
            for message in messages
            if isinstance(message, AIMessage) and not message.tool_calls
        ]
    return []


def _streamed_events(event: dict[str, Any]) -> list[dict[str, Any]]:
    """What :func:`stream_turn` yields for one agent event."""
    match event["type"]:
        case "tool_start":
            return [event]
        case "tool_end":
            return [{"type": "tool_end", "name": event["name"], "failure": event["failure"]}]
        case "final":
            return [{"type": "token", "content": text} for text in _text_blocks(event["message"].content)]
        case _:
            return []


async def _stream_tokens(
    messages: list[dict[str, Any]], provider: BaseChatProvider
) -> AsyncGenerator[dict[str, Any], None]:
    """Stream the model's reply to a turn without tools, one token event per text block of each chunk."""
    llm = provider.create_llm()
    chunks = llm.astream([SystemMessage(content=provider.system_prompt), *provider.convert_messages(messages)])
    async with aclosing(chunks):
        async for chunk in chunks:
            for text in _text_blocks(chunk.content):
                yield {"type": "token", "content": text}


async def _agent_events(
    messages: list[dict[str, Any]], tools: Sequence[BaseTool], provider: BaseChatProvider, max_tool_executions: int
) -> AsyncGenerator[dict[str, Any], None]:
    """Run a turn with tools on a LangChain agent, yielding what happens as it happens.

    Yields ``tool_start`` and ``tool_end`` for each call, ``limit_reached`` when calls past
    ``max_tool_executions`` were blocked, and ``final`` with the model's closing reply.
    Calls run one at a time, in the order the model listed them, and a call reported as
    started runs only once this generator is asked for its next event. A blocked call
    tells the model to stop calling tools so it answers instead; the model gets two calls
    beyond one per allowed tool call, so a model that keeps calling tools still ends.
    """
    limiter = ToolCallLimitMiddleware(run_limit=max_tool_executions, exit_behavior="continue")
    cap = ModelCallLimitMiddleware(run_limit=max_tool_executions + 2, exit_behavior="end")
    # The run context carries the audit identity; the library middlewares never read it.
    middleware: list[AgentMiddleware[Any, Any, Any]] = [_chat_tool_call, limiter, cap]
    agent = create_agent(provider.create_llm(), tools, middleware=middleware, context_schema=AuditModelInfo)
    # With several stream modes, each item is a (mode, chunk) pair.
    stream = cast(
        AsyncGenerator[tuple[str, Any], None],
        agent.astream(
            {"messages": [SystemMessage(content=provider.system_prompt), *provider.convert_messages(messages)]},
            {"max_concurrency": 1},
            context=AuditModelInfo(provider.provider_name, provider.model),
            stream_mode=["custom", "updates"],
        ),
    )
    async with aclosing(stream):
        async for mode, chunk in stream:
            if mode == "custom":
                go = chunk.pop("go", None)
                yield chunk
                # The tool reported as started runs only now, once the next event is asked for.
                if go is not None:
                    go.set()
                continue
            for node, update in chunk.items():
                for event in _update_events(node, update, limiter, cap):
                    yield event


async def complete_turn(
    messages: list[dict[str, Any]], tools: Sequence[BaseTool], provider: BaseChatProvider, max_tool_executions: int
) -> dict[str, Any]:
    """Run one non-streamed chat turn to its end and return the model's answer.

    Without tools this is the provider's plain ``send_message``. With tools the turn runs on
    the agent in :func:`_agent_events`, and ``metadata`` lists every tool call it made.
    """
    if not tools:
        return await provider.send_message(messages)
    tool_executions: list[dict[str, Any]] = []
    limit_reached = False
    final: AIMessage | None = None
    async for event in _agent_events(messages, tools, provider, max_tool_executions):
        if event["type"] == "tool_end":
            tool_executions.append(
                {
                    "tool": event["name"],
                    "tool_input": event["tool_input"],
                    "output": event["output"][:500],
                    "failure": event["failure"],
                }
            )
        elif event["type"] == "limit_reached":
            limit_reached = True
        elif event["type"] == "final":
            final = event["message"]

    return {
        "content": "".join(_text_blocks(final.content)) if final else "",
        "role": "assistant",
        "model": provider.model,
        "tool_calls": None,
        "metadata": {
            "tool_executions": tool_executions,
            "num_executions": len(tool_executions),
            "limit_reached": limit_reached,
            "response_metadata": final.response_metadata if final else {},
            "usage_metadata": final.usage_metadata if final else {},
        },
    }


async def stream_turn(
    messages: list[dict[str, Any]], tools: Sequence[BaseTool], provider: BaseChatProvider, max_tool_executions: int
) -> AsyncGenerator[dict[str, Any], None]:
    """Stream one chat turn as typed event dicts.

    Yields:
      {"type": "token",     "content": str}   — text to display
      {"type": "tool_start","name": str}       — tool execution beginning
      {"type": "tool_end",  "name": str, "failure": ToolFailureKind | None}
                                               — tool execution finished, and how it failed

    Without tools the model's reply streams as it is generated, one token per text block of each
    chunk. With tools the turn runs on the agent in :func:`_agent_events`: a call reported by
    ``tool_start`` runs only once the reader asks for the next event, so a reader that stops on
    ``tool_start`` keeps that tool from running. The model's closing reply then arrives as one
    token per text block.
    """
    if not tools:
        async with aclosing(_stream_tokens(messages, provider)) as tokens:
            async for event in tokens:
                yield event
        return
    async with aclosing(_agent_events(messages, tools, provider, max_tool_executions)) as events:
        async for event in events:
            for streamed in _streamed_events(event):
                yield streamed
