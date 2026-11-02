import asyncio
from abc import ABC, abstractmethod
from typing import Any, AsyncIterator, ClassVar, TypedDict
from uuid import UUID

import httpx
from langchain_anthropic import ChatAnthropic
from langchain_core.callbacks.base import AsyncCallbackHandler
from langchain_core.exceptions import LangChainException
from langchain_core.messages import AIMessage, AnyMessage, BaseMessage, HumanMessage, SystemMessage
from langchain_core.outputs import ChatGenerationChunk, GenerationChunk, LLMResult
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_openai import ChatOpenAI
from pydantic import ValidationError

from sparkth.lib.log import get_logger

logger = get_logger(__name__)


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

    def convert_messages(self, messages: list[dict[str, Any]]) -> list[AnyMessage]:
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

    async def send_message(self, messages: list[dict[str, Any]], max_tokens: int | None = None) -> dict[str, Any]:
        """Send a message and get the model's reply, without tools."""
        try:
            return await self._send_message_simple(self._create_llm(streaming=False), messages)
        except (LangChainException, ValidationError, ValueError, RuntimeError, httpx.RemoteProtocolError) as e:
            logger.error(f"Error in send_message: {e}")
            raise

    async def _send_message_simple(self, llm: Any, messages: list[dict[str, Any]]) -> dict[str, Any]:
        """Send a message without tools."""
        langchain_messages: list[BaseMessage] = [SystemMessage(content=self.system_prompt)]
        langchain_messages.extend(self.convert_messages(messages))

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

    async def stream_message(
        self, messages: list[dict[str, Any]], max_tokens: int | None = None
    ) -> AsyncIterator[dict[str, Any]]:
        """Stream the model's reply to a message, without tools, as ``{"type": "token", "content": str}`` events."""
        async for token in self._stream_message_simple(messages):
            yield {"type": "token", "content": token}

    async def _stream_message_simple(self, messages: list[dict[str, Any]]) -> AsyncIterator[str]:
        """Stream a message without tools."""
        callback = StreamingCallbackHandler()
        llm = self._create_llm(streaming=True, callbacks=[callback])

        langchain_messages: list[BaseMessage] = [SystemMessage(content=self.system_prompt)]
        langchain_messages.extend(self.convert_messages(messages))

        task = asyncio.create_task(llm.ainvoke(langchain_messages))

        try:
            async for token in callback.aiter():
                yield token
            await task
        except (LangChainException, asyncio.CancelledError, RuntimeError, httpx.RemoteProtocolError) as e:
            logger.error(f"Error in stream_message_simple: {e}")
            task.cancel()
            raise


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
