"""Run one Compose turn: a planner hands the message to an agent, answers it itself, or refuses it."""

import asyncio
import json
from collections.abc import AsyncGenerator, Awaitable, Callable, Sequence
from contextlib import aclosing
from dataclasses import replace
from functools import partial
from typing import Any, cast

from langchain.agents import create_agent
from langchain.agents.middleware import (
    AgentMiddleware,
    ToolCallLimitMiddleware,
    ToolCallRequest,
    after_model,
    wrap_tool_call,
)
from langchain.agents.middleware.tool_call_limit import ToolCallLimitState
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, ToolMessage
from langchain_core.messages.ai import UsageMetadata, add_usage
from langchain_core.tools import BaseTool
from langgraph.graph.state import CompiledStateGraph
from langgraph.runtime import Runtime
from langgraph.types import Command
from pydantic import BaseModel, ValidationError

from sparkth.lib.audit import ToolFailureKind, tool_failure
from sparkth.lib.audit.context import AuditSource, ai_audit_context
from sparkth.lib.audit.events import AuditModelInfo
from sparkth.lib.audit.exceptions import AuditCaptureError
from sparkth.lib.compose.constants import REFUSE_TOOL_NAME
from sparkth.lib.compose.hooks import Agent
from sparkth.lib.i18n import gettext
from sparkth.lib.llm import BaseChatProvider, to_langchain_messages
from sparkth.lib.log import get_logger
from sparkth.lib.plugins import PluginConfigInvalidError, PluginNotConfiguredError
from sparkth.plugins.compose.constants import TOOL_CALL_LIMIT_NOTICE
from sparkth.plugins.compose.enums import TurnEventType
from sparkth.plugins.compose.planner import AgentGraph, TurnRouting, build_planner
from sparkth.plugins.compose.prompt import render_system_prompt

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


def _failed_call(request: ToolCallRequest, detail: str = "") -> ToolMessage:
    """The model-visible result of a call whose tool raised, with ``detail`` when there is any."""
    name = request.tool_call["name"]
    text = f"Error executing tool '{name}': {detail}" if detail else f"Error executing tool '{name}'."
    return ToolMessage(text, tool_call_id=request.tool_call["id"], name=name, status="error")


def _arguments_are_valid(request: ToolCallRequest) -> bool:
    """Whether the model's arguments for a call fit the tool's schema.

    An unknown tool name has no schema, so its call is not valid. A tool without a pydantic
    schema validates nothing before it runs.
    """
    tool = request.tool
    if tool is None:
        return False
    schema = tool.args_schema
    if not (isinstance(schema, type) and issubclass(schema, BaseModel)):
        return True
    try:
        schema.model_validate(request.tool_call["args"])
    except ValidationError:
        return False
    return True


async def _classified_tool_call(
    request: ToolCallRequest, handler: _ToolCallHandler
) -> tuple[ToolMessage | Command[Any], ToolFailureKind | None]:
    """Run one tool call and say how it failed (None on success).

    Invalid arguments and a tool name that is not bound come back from the handler as an
    error result, so they are a validation failure (see :func:`_refused_call`); a tool that
    raised is an unknown one.
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
        return _failed_call(request, str(e)), ToolFailureKind.UNKNOWN
    # NOTE: Kept broad here intentionally — tool handlers are user-supplied plugins that can
    # raise anything. Narrowing would silently swallow legitimate errors from arbitrary
    # third-party tool implementations.
    except Exception as e:
        logger.error("Error executing tool '%s': %s", name, e, exc_info=True)
        return _failed_call(request, str(e)), ToolFailureKind.UNKNOWN
    if not isinstance(result, ToolMessage):
        return result, None
    if result.status == "error":
        return _refused_call(request, result)
    return result, _reported_failure(result.content)


def _refused_call(request: ToolCallRequest, refusal: ToolMessage) -> tuple[ToolMessage, ToolFailureKind]:
    """Classify a call the agent turned into an error result without the tool's own error.

    LangGraph does this for an unknown tool name, for arguments that do not fit the tool's
    schema, and for a ``ValidationError`` the handler itself raised. Only the first two are the
    model's to fix. The refusal text repeats the call's arguments, which can be user data, so it
    is only logged at debug level.
    """
    name = request.tool_call["name"]
    logger.debug("Tool '%s' refusal: %s", name, refusal.text)
    if _arguments_are_valid(request):
        logger.error("Tool '%s' raised a validation error inside its handler", name)
        return _failed_call(request), ToolFailureKind.UNKNOWN
    logger.warning("Tool '%s' call was refused", name)
    return refusal, ToolFailureKind.VALIDATION


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
    request.runtime.stream_writer({"type": TurnEventType.TOOL_START, "name": name, "go": go})
    await go.wait()
    model = _audit_model_info(cast(AuditModelInfo, request.runtime.context), request.state["messages"])
    with ai_audit_context(AuditSource.COMPOSE, model):
        result, failure = await _classified_tool_call(request, handler)
    output = result.text if isinstance(result, ToolMessage) else ""
    arguments = request.tool_call["args"]
    request.runtime.stream_writer(
        {"type": TurnEventType.TOOL_END, "name": name, "failure": failure, "tool_input": arguments, "output": output}
    )
    return result


_END_HOOK = "end_after_a_block"


def _end_after_a_block(limit: int, state: ToolCallLimitState[Any], runtime: Runtime[Any]) -> dict[str, Any] | None:
    """End the turn when the model asks for tools again after the tool call limit blocked its calls.

    The limiter counts blocked calls too, so a count over ``limit`` means an earlier reply was
    blocked. That reply told the model to answer, so a reply that asks for tools anyway ends the
    turn, however many calls each reply batches. The turn's answer is a short notice that the
    limit was reached, in the active language, because the reply that asked for tools has no
    answer in it. This hook runs before the limiter for the same reply, so it sees the counts
    from before that reply.
    """
    reply = state["messages"][-1]
    counted = sum(state.get("run_tool_call_count", {}).values())
    if counted <= limit or not (isinstance(reply, AIMessage) and reply.tool_calls):
        return None
    logger.warning("Model asked for tools after the limit (%s); the turn ends with a notice", limit)
    return {"jump_to": "end", "messages": [AIMessage(content=gettext(TOOL_CALL_LIMIT_NOTICE))]}


def _update_events(node: str, update: dict[str, Any] | None, max_tool_executions: int) -> list[dict[str, Any]]:
    """The events one graph node's update stands for: blocked calls, the tokens of each model
    reply, and the closing reply.

    The tool call limiter adds messages only when it blocks calls, and each time it does it is
    logged.
    """
    messages = (update or {}).get("messages", [])
    if node == f"{ToolCallLimitMiddleware.__name__}.after_model" and messages:
        logger.warning("Tool call limit (%s) reached; blocked %d call(s)", max_tool_executions, len(messages))
        return [{"type": TurnEventType.LIMIT_REACHED}]
    if node not in ("model", f"{_END_HOOK}.after_model"):
        return []
    replies = [message for message in messages if isinstance(message, AIMessage)]
    return [
        *({"type": TurnEventType.USAGE, "usage": reply.usage_metadata} for reply in replies if reply.usage_metadata),
        *({"type": TurnEventType.FINAL, "message": reply} for reply in replies if not reply.tool_calls),
    ]


class _TurnText:
    """The text a turn shows the author, sorted from the planner's and the agents' messages.

    An agent's text shows as it is written, with a blank line between its messages. The planner's
    is held until the turn ends, and a message of its that hands off never shows.
    """

    def __init__(self) -> None:
        self._held: dict[str | None, list[str]] = {}
        self._handing_off: set[str | None] = set()
        self._last_agent_message: str | None = None
        self._agent_spoke = False

    def agent_text(self, message: BaseMessage) -> list[str]:
        """The text of an agent's ``message`` to show now, after a blank line when it starts a new message."""
        texts = [] if isinstance(message, ToolMessage) else _text_blocks(message.content)
        if not texts:
            return []
        gap = ["\n\n"] if self._agent_spoke and message.id != self._last_agent_message else []
        self._last_agent_message, self._agent_spoke = message.id, True
        return [*gap, *texts]

    def hold_planner_text(self, message: BaseMessage) -> None:
        """Hold the text of the planner's ``message``, noting whether it hands off."""
        if getattr(message, "tool_call_chunks", None) or getattr(message, "tool_calls", None):
            self._handing_off.add(message.id)
        self._held.setdefault(message.id, []).extend(_text_blocks(message.content))

    def unsent(self) -> list[str]:
        """The planner's held text from its messages that didn't hand off."""
        return [
            text for message_id, texts in self._held.items() if message_id not in self._handing_off for text in texts
        ]


def build_turn_agent(
    llm: BaseChatModel, tools: Sequence[BaseTool], system_prompt: str, max_tool_executions: int
) -> CompiledStateGraph[Any, AuditModelInfo, Any, Any]:
    """Build the agent that runs a turn's tool calls, led by ``system_prompt``.

    Calls run one at a time, in the order the model listed them, and each reports its start and
    end on the agent's stream (see :func:`_chat_tool_call`). Calls past ``max_tool_executions``
    are blocked and the model is told to answer instead; a model that asks for tools again after
    that ends the turn with a notice instead of an answer (see :func:`_end_after_a_block`). The
    run's context is the :class:`AuditModelInfo` of the model the turn runs on.
    """
    limiter = ToolCallLimitMiddleware(run_limit=max_tool_executions, exit_behavior="continue")
    # The hook is listed after the limiter so that it runs first for each reply.
    ender = after_model(can_jump_to=["end"], name=_END_HOOK, state_schema=ToolCallLimitState)(
        partial(_end_after_a_block, max_tool_executions)
    )
    # The run context carries the audit identity; the library middlewares never read it.
    middleware: list[AgentMiddleware[Any, Any, Any]] = [_chat_tool_call, limiter, ender]
    return create_agent(llm, tools, system_prompt=system_prompt, middleware=middleware, context_schema=AuditModelInfo)


def _planner_for_turn(
    agents: Sequence[Agent],
    tools: Sequence[BaseTool],
    provider: BaseChatProvider,
    planner_llm: BaseChatModel,
    max_tool_executions: int,
) -> CompiledStateGraph[Any, AuditModelInfo, Any, Any]:
    """The turn's planner on ``planner_llm``, handing off to ``agents`` that each run on the
    provider's model with their own prompt and ``tools``."""
    agent_llm = provider.create_llm()
    return build_planner(
        planner_llm,
        [
            AgentGraph(agent, build_turn_agent(agent_llm, tools, render_system_prompt([agent]), max_tool_executions))
            for agent in agents
        ],
    )


def _stream_planner(
    planner: CompiledStateGraph[Any, AuditModelInfo, Any, Any],
    messages: list[dict[str, Any]],
    provider: BaseChatProvider,
) -> AsyncGenerator[tuple[tuple[str, ...], str, Any], None]:
    """Stream ``planner`` over ``messages``, its agents included, with the provider's model as
    the run's audit identity.

    Each item is a (namespace, mode, chunk) triple; the namespace is empty for the planner and
    names the hand-off for an agent's run.
    """
    return cast(
        AsyncGenerator[tuple[tuple[str, ...], str, Any], None],
        planner.astream(
            {"messages": to_langchain_messages(messages)},
            {"max_concurrency": 1},
            context=AuditModelInfo(provider.provider_name, provider.model),
            stream_mode=["custom", "messages", "updates"],
            subgraphs=True,
        ),
    )


async def _turn_events(
    messages: list[dict[str, Any]],
    tools: Sequence[BaseTool],
    provider: BaseChatProvider,
    max_tool_executions: int,
    agents: Sequence[Agent],
    planner_llm: BaseChatModel,
) -> AsyncGenerator[dict[str, Any], None]:
    """Run one turn on the planner, yielding what happens as it happens.

    The planner hands the message to one of ``agents``, each running on the provider's model
    with its own prompt and ``tools``, answers it itself, or refuses it. Yields ``routed`` with a
    :class:`TurnRouting` when a hand-off starts or the refusal returns (a call its tool refused
    never does either), ``token`` for the text the author sees, ``tool_start`` and ``tool_end`` for each
    tool call, ``limit_reached`` when an agent's calls were blocked, ``usage`` with the tokens of
    each model reply, the planner's and the agents', and ``final`` with each closing model reply. A
    call reported as started runs only once this generator is asked for its next event. A refusal
    arrives as the refusal sentence.
    """
    planner = _planner_for_turn(agents, tools, provider, planner_llm, max_tool_executions)
    stream = _stream_planner(planner, messages, provider)
    turn_text = _TurnText()
    async with aclosing(stream):
        async for namespace, mode, chunk in stream:
            if mode == "custom":
                go = chunk.pop("go", None)
                yield chunk
                # The tool reported as started runs only now, once the next event is asked for.
                if go is not None:
                    go.set()
            elif mode == "updates":
                for node, update in chunk.items():
                    for event in _update_events(node, update, max_tool_executions):
                        yield event
            else:
                message, _metadata = chunk
                if namespace:
                    for token in turn_text.agent_text(message):
                        yield {"type": TurnEventType.TOKEN, "content": token}
                elif isinstance(message, ToolMessage):
                    # An agent's reply has already streamed; only a refusal is new text.
                    if message.name == REFUSE_TOOL_NAME and message.status != "error":
                        yield {"type": TurnEventType.ROUTED, "routing": TurnRouting(refused=True)}
                        yield {"type": TurnEventType.TOKEN, "content": message.text}
                else:
                    turn_text.hold_planner_text(message)
    for token in turn_text.unsent():
        yield {"type": TurnEventType.TOKEN, "content": token}


async def complete_turn(
    messages: list[dict[str, Any]],
    tools: Sequence[BaseTool],
    provider: BaseChatProvider,
    max_tool_executions: int,
    *,
    agents: Sequence[Agent],
    planner_llm: BaseChatModel,
) -> dict[str, Any]:
    """Run one non-streamed turn on the planner and return its answer.

    The answer is the text a streamed turn would have shown, ``routing`` says who answered it,
    and ``metadata`` lists every tool call the turn made and the tokens of all its model replies,
    the planner's and the agents'.
    """
    tokens: list[str] = []
    routing = TurnRouting()
    tool_executions: list[dict[str, Any]] = []
    limit_reached = False
    usage: UsageMetadata | None = None
    final: AIMessage | None = None
    events = _turn_events(messages, tools, provider, max_tool_executions, agents, planner_llm)
    async with aclosing(events):
        async for event in events:
            if event["type"] == TurnEventType.ROUTED:
                routing = event["routing"]
            elif event["type"] == TurnEventType.TOKEN:
                tokens.append(event["content"])
            elif event["type"] == TurnEventType.TOOL_END:
                tool_executions.append(
                    {
                        "tool": event["name"],
                        "tool_input": event["tool_input"],
                        "output": event["output"][:500],
                        "failure": event["failure"],
                    }
                )
            elif event["type"] == TurnEventType.LIMIT_REACHED:
                limit_reached = True
            elif event["type"] == TurnEventType.USAGE:
                usage = add_usage(usage, event["usage"])
            elif event["type"] == TurnEventType.FINAL:
                final = event["message"]

    return {
        "content": "".join(tokens),
        "role": "assistant",
        "model": provider.model,
        "tool_calls": None,
        "routing": routing,
        "metadata": {
            "tool_executions": tool_executions,
            "num_executions": len(tool_executions),
            "limit_reached": limit_reached,
            "response_metadata": final.response_metadata if final else {},
            "usage_metadata": usage or {},
        },
    }


async def stream_turn(
    messages: list[dict[str, Any]],
    tools: Sequence[BaseTool],
    provider: BaseChatProvider,
    max_tool_executions: int,
    *,
    agents: Sequence[Agent],
    planner_llm: BaseChatModel,
) -> AsyncGenerator[dict[str, Any], None]:
    """Stream one turn on the planner as typed event dicts.

    Yields:
      {"type": "routed",    "routing": TurnRouting}
                                               — who answers the turn, when a hand-off starts or the
                                                 refusal returns; never sent when the planner answers
      {"type": "token",     "content": str}   — text to display
      {"type": "tool_start","name": str}       — tool execution beginning
      {"type": "tool_end",  "name": str, "failure": ToolFailureKind | None}
                                               — tool execution finished, and how it failed

    A call reported by ``tool_start`` runs only once the reader asks for the next event, so a
    reader that stops on ``tool_start`` keeps that tool from running.
    """
    events = _turn_events(messages, tools, provider, max_tool_executions, agents, planner_llm)
    async with aclosing(events):
        async for event in events:
            match event["type"]:
                case TurnEventType.ROUTED | TurnEventType.TOKEN | TurnEventType.TOOL_START:
                    yield event
                case TurnEventType.TOOL_END:
                    yield {"type": TurnEventType.TOOL_END, "name": event["name"], "failure": event["failure"]}
