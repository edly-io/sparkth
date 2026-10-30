import asyncio
import json
from abc import ABC, abstractmethod
from collections.abc import AsyncGenerator, Awaitable, Callable, Sequence
from contextlib import aclosing
from dataclasses import replace
from functools import partial
from typing import Any, AsyncIterator, ClassVar, TypedDict, cast
from uuid import UUID

import httpx
from langchain.agents import create_agent
from langchain.agents.middleware import (
    AgentMiddleware,
    ToolCallLimitMiddleware,
    ToolCallRequest,
    after_model,
    wrap_tool_call,
)
from langchain.agents.middleware.tool_call_limit import ToolCallLimitState
from langchain_anthropic import ChatAnthropic
from langchain_core.callbacks.base import AsyncCallbackHandler
from langchain_core.exceptions import LangChainException
from langchain_core.messages import AIMessage, AnyMessage, BaseMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.outputs import ChatGenerationChunk, GenerationChunk, LLMResult
from langchain_core.tools import BaseTool
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_openai import ChatOpenAI
from langgraph.runtime import Runtime
from langgraph.types import Command
from pydantic import BaseModel, ValidationError

from sparkth.lib.audit import ToolFailureKind, tool_failure
from sparkth.lib.audit.context import AuditSource, ai_audit_context
from sparkth.lib.audit.events import AuditModelInfo
from sparkth.lib.audit.exceptions import AuditCaptureError
from sparkth.lib.i18n import _
from sparkth.lib.log import get_logger
from sparkth.lib.plugins import PluginConfigInvalidError, PluginNotConfiguredError

logger = get_logger(__name__)

ToolCallHandler = Callable[[ToolCallRequest], Awaitable[ToolMessage | Command[Any]]]


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
    request: ToolCallRequest, handler: ToolCallHandler
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
async def _chat_tool_call(request: ToolCallRequest, handler: ToolCallHandler) -> ToolMessage | Command[Any]:
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
    notice = _(
        "I stopped because I reached the tool-call limit for this turn. You can send another message to continue."
    )
    return {"jump_to": "end", "messages": [AIMessage(content=notice)]}


class StreamingCallbackHandler(AsyncCallbackHandler):
    def __init__(self) -> None:
        self.tokens: list[str] = []
        self.done = False
        self.error: BaseException | None = None

    async def on_llm_new_token(
        self,
        token: str | list[str | dict[str, Any]],
        *,
        chunk: GenerationChunk | ChatGenerationChunk | None = None,
        run_id: UUID,
        parent_run_id: UUID | None = None,
        tags: list[str] | None = None,
        **kwargs: Any,
    ) -> None:
        # Providers may emit content blocks instead of a plain string.
        if isinstance(token, str):
            self.tokens.append(token)
        else:
            self.tokens.extend(part if isinstance(part, str) else str(part.get("text", "")) for part in token)

    async def on_llm_end(
        self,
        response: LLMResult,
        *,
        run_id: UUID,
        parent_run_id: UUID | None = None,
        tags: list[str] | None = None,
        **kwargs: Any,
    ) -> None:
        self.done = True

    async def on_llm_error(
        self,
        error: BaseException,
        *,
        run_id: UUID,
        parent_run_id: UUID | None = None,
        tags: list[str] | None = None,
        **kwargs: Any,
    ) -> None:
        self.error = error
        self.done = True

    async def aiter(self) -> AsyncIterator[str]:
        index = 0
        while not self.done or index < len(self.tokens):
            if index < len(self.tokens):
                yield self.tokens[index]
                index += 1
            else:
                await asyncio.sleep(0.01)

        if self.error:
            raise self.error


class BaseChatProvider(ABC):
    # Stable provider identifier recorded as AI provenance on audit events;
    # subclasses set it to their PROVIDER_REGISTRY key.
    provider_name: ClassVar[str]

    def __init__(
        self,
        api_key: str,
        model: str,
        system_prompt: str | None = None,
        temperature: float = 0.7,
        max_tool_executions: int = 50,
        max_retries: int = 2,
    ):
        self.api_key = api_key
        self.model = model
        self.temperature = temperature
        self.max_tool_executions = max_tool_executions
        self.max_retries = max_retries
        self._llm: Any = None
        self.system_prompt = system_prompt or ""

    @abstractmethod
    def _create_llm(self, streaming: bool = False, callbacks: list[Any] | None = None) -> Any:
        pass

    def create_llm(self, streaming: bool = False, callbacks: list[Any] | None = None) -> Any:
        """Public interface for creating a configured LangChain LLM instance."""
        return self._create_llm(streaming=streaming, callbacks=callbacks)

    def _convert_messages(self, messages: list[dict[str, Any]]) -> list[AnyMessage]:
        """Convert dict messages to LangChain message objects."""
        langchain_messages: list[AnyMessage] = []

        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")

            if role == "system":
                langchain_messages.append(SystemMessage(content=content))
            elif role == "assistant":
                langchain_messages.append(AIMessage(content=content))
            else:
                langchain_messages.append(HumanMessage(content=content))

        return langchain_messages

    async def send_message(
        self, messages: list[dict[str, Any]], max_tokens: int | None = None, tools: list[Any] | None = None
    ) -> dict[str, Any]:
        """Send a message and get a response, with optional tool usage.

        A turn with tools runs on the same agent as :meth:`stream_message` (see
        :meth:`_agent_events`); its ``metadata`` lists every tool call made.
        """
        try:
            if tools:
                return await self._send_message_with_tools(messages, tools)
            else:
                return await self._send_message_simple(self._create_llm(streaming=False), messages)
        except (LangChainException, ValidationError, ValueError, RuntimeError, httpx.RemoteProtocolError) as e:
            logger.error(f"Error in send_message: {e}")
            raise

    async def _send_message_simple(self, llm: Any, messages: list[dict[str, Any]]) -> dict[str, Any]:
        """Send a message without tools."""
        langchain_messages: list[BaseMessage] = [SystemMessage(content=self.system_prompt)]
        langchain_messages.extend(self._convert_messages(messages))

        response = await llm.ainvoke(langchain_messages)

        return {
            "content": response.content,
            "role": "assistant",
            "model": self.model,
            "tool_calls": None,
            "metadata": {
                "response_metadata": getattr(response, "response_metadata", {}),
                "usage_metadata": getattr(response, "usage_metadata", {}),
            },
        }

    async def _send_message_with_tools(self, messages: list[dict[str, Any]], tools: list[BaseTool]) -> dict[str, Any]:
        """Run a turn with tools to its end, returning the model's answer and every call it made."""
        tool_executions: list[dict[str, Any]] = []
        limit_reached = False
        final: AIMessage | None = None
        async for event in self._agent_events(messages, tools):
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
            "model": self.model,
            "tool_calls": None,
            "metadata": {
                "tool_executions": tool_executions,
                "num_executions": len(tool_executions),
                "limit_reached": limit_reached,
                "response_metadata": final.response_metadata if final else {},
                "usage_metadata": final.usage_metadata if final else {},
            },
        }

    async def _agent_events(
        self, messages: list[dict[str, Any]], tools: list[BaseTool]
    ) -> AsyncGenerator[dict[str, Any], None]:
        """Run a turn with tools on a LangChain agent, yielding what happens as it happens.

        Yields ``tool_start`` and ``tool_end`` for each call, ``limit_reached`` when calls past
        ``max_tool_executions`` were blocked, and ``final`` with the model's closing reply.
        Calls run one at a time, in the order the model listed them, and a call reported as
        started runs only once this generator is asked for its next event. A blocked call
        tells the model to stop calling tools so it answers instead; a model that asks for tools
        again after that ends the turn with a notice instead of an answer (see :func:`_end_after_a_block`).
        """
        limiter = ToolCallLimitMiddleware(run_limit=self.max_tool_executions, exit_behavior="continue")
        # The hook is listed after the limiter so that it runs first for each reply.
        ender = after_model(can_jump_to=["end"], name=_END_HOOK, state_schema=ToolCallLimitState)(
            partial(_end_after_a_block, self.max_tool_executions)
        )
        # The run context carries the audit identity; the library middlewares never read it.
        middleware: list[AgentMiddleware[Any, Any, Any]] = [_chat_tool_call, limiter, ender]
        agent = create_agent(
            self._create_llm(streaming=False), tools, middleware=middleware, context_schema=AuditModelInfo
        )
        # With several stream modes, each item is a (mode, chunk) pair.
        stream = cast(
            AsyncGenerator[tuple[str, Any], None],
            agent.astream(
                {"messages": [SystemMessage(content=self.system_prompt), *self._convert_messages(messages)]},
                {"max_concurrency": 1},
                context=AuditModelInfo(self.provider_name, self.model),
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
                    for event in _update_events(node, update, limiter):
                        yield event

    async def stream_message(
        self, messages: list[dict[str, Any]], max_tokens: int | None = None, tools: list[Any] | None = None
    ) -> AsyncIterator[dict[str, Any]]:
        """Stream a message response, with optional tool usage.

        Yields typed event dicts:
          {"type": "token",     "content": str}   — text to display
          {"type": "tool_start","name": str}       — tool execution beginning
          {"type": "tool_end",  "name": str, "failure": ToolFailureKind | None}
                                                   — tool execution finished, and how it failed

        A turn with tools runs on the agent described in :meth:`_agent_events`: its tool events
        arrive one call at a time, the next call starts only once the event before it has been
        read, and the model's closing reply arrives as one token per text block.
        """
        if tools:
            async with aclosing(self._agent_events(messages, tools)) as events:
                async for event in events:
                    for streamed in _streamed_events(event):
                        yield streamed
        else:
            async for token in self._stream_message_simple(messages):
                yield {"type": "token", "content": token}

    async def _stream_message_simple(self, messages: list[dict[str, Any]]) -> AsyncIterator[str]:
        """Stream a message without tools."""
        callback = StreamingCallbackHandler()
        llm = self._create_llm(streaming=True, callbacks=[callback])

        langchain_messages: list[BaseMessage] = [SystemMessage(content=self.system_prompt)]
        langchain_messages.extend(self._convert_messages(messages))

        task = asyncio.create_task(llm.ainvoke(langchain_messages))

        try:
            async for token in callback.aiter():
                yield token
            await task
        except (LangChainException, asyncio.CancelledError, RuntimeError, httpx.RemoteProtocolError) as e:
            logger.error(f"Error in stream_message_simple: {e}")
            task.cancel()
            raise


def _update_events(
    node: str, update: dict[str, Any] | None, limiter: ToolCallLimitMiddleware[Any, Any]
) -> list[dict[str, Any]]:
    """The agent events one graph node's update stands for: blocked calls, or the closing reply.

    The tool-call ``limiter`` adds messages only when it blocks calls, and each time it does it
    is logged.
    """
    messages = (update or {}).get("messages", [])
    if node == f"{limiter.name}.after_model" and messages:
        logger.warning("Tool call limit (%s) reached; blocked %d call(s)", limiter.run_limit, len(messages))
        return [{"type": "limit_reached"}]
    if node in ("model", f"{_END_HOOK}.after_model"):
        return [
            {"type": "final", "message": message}
            for message in messages
            if isinstance(message, AIMessage) and not message.tool_calls
        ]
    return []


def _streamed_events(event: dict[str, Any]) -> list[dict[str, Any]]:
    """What :meth:`BaseChatProvider.stream_message` yields for one agent event."""
    match event["type"]:
        case "tool_start":
            return [event]
        case "tool_end":
            return [{"type": "tool_end", "name": event["name"], "failure": event["failure"]}]
        case "final":
            return [{"type": "token", "content": text} for text in _text_blocks(event["message"].content)]
        case _:
            return []


class OpenAIProvider(BaseChatProvider):
    provider_name: ClassVar[str] = "openai"

    def _create_llm(self, streaming: bool = False, callbacks: list[Any] | None = None) -> ChatOpenAI:
        return ChatOpenAI(  # type: ignore[call-arg]
            api_key=self.api_key,
            model=self.model,
            temperature=self.temperature,
            streaming=streaming,
            callbacks=callbacks or [],
            max_retries=self.max_retries,
        )


class AnthropicProvider(BaseChatProvider):
    provider_name: ClassVar[str] = "anthropic"

    def _create_llm(self, streaming: bool = False, callbacks: list[Any] | None = None) -> ChatAnthropic:
        return ChatAnthropic(  # type: ignore[call-arg]
            api_key=self.api_key,
            model=self.model,
            temperature=self.temperature,
            streaming=streaming,
            callbacks=callbacks or [],
            max_retries=self.max_retries,
        )


class GoogleProvider(BaseChatProvider):
    provider_name: ClassVar[str] = "google"

    def _create_llm(self, streaming: bool = False, callbacks: list[Any] | None = None) -> ChatGoogleGenerativeAI:
        return ChatGoogleGenerativeAI(
            google_api_key=self.api_key,
            model=self.model,
            temperature=self.temperature,
            streaming=streaming,
            callbacks=callbacks or [],
            max_retries=self.max_retries,
        )


PROVIDER_REGISTRY: dict[str, type[BaseChatProvider]] = {
    "openai": OpenAIProvider,
    "anthropic": AnthropicProvider,
    "google": GoogleProvider,
}

DEFAULT_PROVIDER = "anthropic"
DEFAULT_MODEL = "claude-sonnet-4-20250514"

PROVIDER_MODELS: dict[str, list[str]] = {
    "openai": [
        "gpt-4o",
        "gpt-4o-mini",
        "o1",
        "o1-mini",
        "o3-mini",
    ],
    "anthropic": [
        "claude-opus-4-5",
        "claude-sonnet-4-5",
        "claude-haiku-4-5",
        "claude-sonnet-4-20250514",
    ],
    "google": [
        "gemini-2.0-flash",
        "gemini-1.5-pro",
        "gemini-1.5-flash",
    ],
}

_registry_only = set(PROVIDER_REGISTRY) - set(PROVIDER_MODELS)
_models_only = set(PROVIDER_MODELS) - set(PROVIDER_REGISTRY)
if _registry_only or _models_only:
    raise ValueError(
        f"PROVIDER_REGISTRY and PROVIDER_MODELS are out of sync. "
        f"Registry only: {_registry_only}, Models only: {_models_only}"
    )


def get_provider(
    provider_name: str,
    api_key: str,
    model: str,
    system_prompt: str | None = None,
    temperature: float = 0.7,
    max_tool_executions: int = 50,
    max_retries: int = 2,
) -> BaseChatProvider:
    """Get a chat provider instance."""
    provider_class = PROVIDER_REGISTRY.get(provider_name.lower())

    if not provider_class:
        supported = ", ".join(PROVIDER_REGISTRY.keys())
        raise ValueError(f"Unsupported provider: {provider_name}. Supported providers: {supported}")

    return provider_class(api_key, model, system_prompt, temperature, max_tool_executions, max_retries)


def get_supported_providers() -> list[str]:
    """Get list of supported provider names."""
    return list(PROVIDER_REGISTRY.keys())


def get_models_for_provider(provider: str) -> list[str]:
    """Get the list of available model IDs for a given provider."""
    return PROVIDER_MODELS.get(provider.lower(), [])


class ProviderCatalogEntry(TypedDict):
    id: str
    label: str
    models: list[str]


def get_provider_catalog() -> list[ProviderCatalogEntry]:
    """Return all providers with their available models."""
    return [{"id": p, "label": p.capitalize(), "models": PROVIDER_MODELS[p]} for p in PROVIDER_REGISTRY]
