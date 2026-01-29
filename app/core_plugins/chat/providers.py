from abc import ABC, abstractmethod
from typing import Any, AsyncIterator, Dict, List, Optional

from langchain_core.callbacks.base import AsyncCallbackHandler
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langchain_anthropic import ChatAnthropic
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_openai import ChatOpenAI

from app.core.logger import get_logger

logger = get_logger(__name__)


class StreamingCallbackHandler(AsyncCallbackHandler):
    def __init__(self) -> None:
        self.tokens: List[str] = []
        self.done = False
        self.error: Optional[Exception] = None

    def on_llm_new_token(self, token: str, **kwargs: Any) -> None:
        self.tokens.append(token)

    def on_llm_end(self, response: Any, **kwargs: Any) -> None:
        self.done = True

    def on_llm_error(self, error: Exception, **kwargs: Any) -> None:
        self.error = error
        self.done = True

    async def aiter(self) -> AsyncIterator[str]:
        index = 0
        while not self.done or index < len(self.tokens):
            if index < len(self.tokens):
                yield self.tokens[index]
                index += 1
            else:
                import asyncio
                await asyncio.sleep(0.01)

        if self.error:
            raise self.error


class BaseChatProvider(ABC):
    def __init__(self, api_key: str, model: str, temperature: float = 0.7):
        self.api_key = api_key
        self.model = model
        self.temperature = temperature
        self._llm: Any = None

    @abstractmethod
    def _create_llm(self, streaming: bool = False, callbacks: Optional[List[Any]] = None) -> Any:
        pass

    def _convert_messages(self, messages: List[Dict[str, str]]) -> List[BaseMessage]:
        langchain_messages: List[BaseMessage] = []
        
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
        self, 
        messages: List[Dict[str, str]], 
        max_tokens: Optional[int] = None,
        tools: Optional[List[Any]] = None
    ) -> Dict[str, Any]:
        llm = self._create_llm(streaming=False)
        
        if tools:
            llm = llm.bind_tools(tools)
        
        langchain_messages = self._convert_messages(messages)

        try:
            response = await llm.ainvoke(langchain_messages)
            
            tool_calls = []
            if hasattr(response, "tool_calls") and response.tool_calls:
                tool_calls = [
                    {
                        "id": tc.get("id", ""),
                        "name": tc.get("name", ""),
                        "arguments": tc.get("args", {}),
                    }
                    for tc in response.tool_calls
                ]
            
            return {
                "content": response.content,
                "role": "assistant",
                "model": self.model,
                "tool_calls": tool_calls if tool_calls else None,
                "metadata": {
                    "response_metadata": getattr(response, "response_metadata", {}),
                    "usage_metadata": getattr(response, "usage_metadata", {}),
                },
            }
        except Exception as e:
            logger.error(f"Error in send_message: {e}")
            raise

    async def stream_message(self, messages: List[Dict[str, str]], max_tokens: Optional[int] = None) -> AsyncIterator[str]:
        callback = StreamingCallbackHandler()
        llm = self._create_llm(streaming=True, callbacks=[callback])
        langchain_messages = self._convert_messages(messages)

        import asyncio
        task = asyncio.create_task(llm.ainvoke(langchain_messages))

        try:
            async for token in callback.aiter():
                yield token
            
            await task
        except Exception as e:
            logger.error(f"Error in stream_message: {e}")
            task.cancel()
            raise


class OpenAIProvider(BaseChatProvider):
    def _create_llm(self, streaming: bool = False, callbacks: Optional[List[Any]] = None) -> ChatOpenAI:
        return ChatOpenAI(
            api_key=self.api_key,
            model=self.model,
            temperature=self.temperature,
            streaming=streaming,
            callbacks=callbacks or [],
        )


class AnthropicProvider(BaseChatProvider):
    def _create_llm(self, streaming: bool = False, callbacks: Optional[List[Any]] = None) -> ChatAnthropic:
        return ChatAnthropic(
            api_key=self.api_key,
            model=self.model,
            temperature=self.temperature,
            streaming=streaming,
            callbacks=callbacks or [],
        )


class GoogleProvider(BaseChatProvider):
    def _create_llm(self, streaming: bool = False, callbacks: Optional[List[Any]] = None) -> ChatGoogleGenerativeAI:
        return ChatGoogleGenerativeAI(
            google_api_key=self.api_key,
            model=self.model,
            temperature=self.temperature,
            streaming=streaming,
            callbacks=callbacks or [],
        )


PROVIDER_REGISTRY: Dict[str, type[BaseChatProvider]] = {
    "openai": OpenAIProvider,
    "anthropic": AnthropicProvider,
    "google": GoogleProvider,
}


def get_provider(provider_name: str, api_key: str, model: str, temperature: float = 0.7) -> BaseChatProvider:
    provider_class = PROVIDER_REGISTRY.get(provider_name.lower())
    
    if not provider_class:
        supported = ", ".join(PROVIDER_REGISTRY.keys())
        raise ValueError(f"Unsupported provider: {provider_name}. Supported providers: {supported}")

    return provider_class(api_key, model, temperature)


def get_supported_providers() -> List[str]:
    return list(PROVIDER_REGISTRY.keys())
