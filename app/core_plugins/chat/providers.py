import json
from abc import ABC, abstractmethod
from typing import Any, AsyncIterator
from uuid import UUID

from langchain_anthropic import ChatAnthropic
from langchain_core.callbacks.base import AsyncCallbackHandler
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.outputs import ChatGenerationChunk, GenerationChunk, LLMResult
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_openai import ChatOpenAI

from app.core.logger import get_logger
from app.core_plugins.chat.prompt import get_learning_design_system_prompt

logger = get_logger(__name__)


def serialize_result(result: Any) -> str:
    """Safely serialize any result to a string."""
    if result is None:
        return "null"
    if isinstance(result, str):
        return result
    if isinstance(result, (dict, list)):
        try:
            return json.dumps(result, indent=2, default=str)
        except (TypeError, ValueError):
            return str(result)
    return str(result)


class StreamingCallbackHandler(AsyncCallbackHandler):
    def __init__(self) -> None:
        self.tokens: list[str] = []
        self.done = False
        self.error: BaseException | None = None

    async def on_llm_new_token(
        self,
        token: str,
        *,
        chunk: GenerationChunk | ChatGenerationChunk | None = None,
        run_id: UUID,
        parent_run_id: UUID | None = None,
        tags: list[str] | None = None,
        **kwargs: Any,
    ) -> None:
        self.tokens.append(token)

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
                import asyncio

                await asyncio.sleep(0.01)

        if self.error:
            raise self.error


class BaseChatProvider(ABC):
    def __init__(self, api_key: str, model: str, system_prompt: str | None = None, temperature: float = 0.7):
        self.api_key = api_key
        self.model = model
        self.temperature = temperature
        self._llm: Any = None
        self.system_prompt = system_prompt or get_learning_design_system_prompt()

    @abstractmethod
    def _create_llm(self, streaming: bool = False, callbacks: list[Any] | None = None) -> Any:
        pass

    def _convert_messages(self, messages: list[dict[str, str]]) -> list[BaseMessage]:
        """Convert dict messages to LangChain message objects."""
        langchain_messages: list[BaseMessage] = []

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
        self, messages: list[dict[str, str]], max_tokens: int | None = None, tools: list[Any] | None = None
    ) -> dict[str, Any]:
        """Send a message and get a response, with optional tool usage."""
        llm = self._create_llm(streaming=False)

        try:
            if tools:
                # Use tool execution loop for tool-enabled conversations
                return await self._send_message_with_tools(llm, messages, tools)
            else:
                # Use simple invocation for non-tool conversations
                return await self._send_message_simple(llm, messages)

        except Exception as e:
            logger.error(f"Error in send_message: {e}")
            raise

    async def _send_message_simple(self, llm: Any, messages: list[dict[str, str]]) -> dict[str, Any]:
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

    async def _send_message_with_tools(
        self, llm: Any, messages: list[dict[str, str]], tools: list[Any]
    ) -> dict[str, Any]:
        """Send a message with tool support using a manual tool execution loop."""

        # Bind tools to the LLM
        llm_with_tools = llm.bind_tools(tools)

        # Build initial message list with system prompt
        langchain_messages: list[BaseMessage] = [SystemMessage(content=self.system_prompt)]
        langchain_messages.extend(self._convert_messages(messages))

        tool_executions = []
        max_iterations = 15
        iteration = 0

        while iteration < max_iterations:
            # Get LLM response
            response = await llm_with_tools.ainvoke(langchain_messages)

            # Check if there are tool calls to execute
            if hasattr(response, "tool_calls") and response.tool_calls:
                # Add the assistant's response to message history
                langchain_messages.append(response)

                # Execute each tool call
                for tool_call in response.tool_calls:
                    tool_name = tool_call.get("name", "")
                    tool_args = tool_call.get("args", {})
                    tool_id = tool_call.get("id", "")

                    logger.debug(f"Executing tool: {tool_name} with args: {tool_args}")

                    # Execute the tool
                    tool_result = await self._execute_tool(tool_name, tool_args, tools)

                    # Serialize the result safely
                    serialized_result = serialize_result(tool_result)

                    # Record the execution
                    tool_executions.append(
                        {
                            "tool": tool_name,
                            "tool_input": tool_args,
                            "output": serialized_result[:500],  # Truncate long outputs
                        }
                    )

                    # Add the tool result to message history
                    tool_message = ToolMessage(content=serialized_result, tool_call_id=tool_id, name=tool_name)
                    langchain_messages.append(tool_message)

                iteration += 1
            else:
                # No more tool calls, we have the final response
                break

        # Handle case where response.content might be a list
        content = response.content
        if isinstance(content, list):
            # Extract text from content blocks (common with Anthropic)
            text_parts = []
            for block in content:
                if isinstance(block, dict) and block.get("type") == "text":
                    text_parts.append(block.get("text", ""))
                elif isinstance(block, str):
                    text_parts.append(block)
            content = "".join(text_parts)

        return {
            "content": content,
            "role": "assistant",
            "model": self.model,
            "tool_calls": None,  # Tools have been executed
            "metadata": {
                "tool_executions": tool_executions,
                "num_iterations": iteration,
                "response_metadata": getattr(response, "response_metadata", {}),
                "usage_metadata": getattr(response, "usage_metadata", {}),
            },
        }

    async def _execute_tool(self, tool_name: str, tool_args: dict[str, Any], tools: list[Any]) -> Any:
        """Execute a tool by name with the given arguments."""
        for tool in tools:
            if tool.name == tool_name:
                try:
                    result = None

                    # Try different invocation methods
                    if hasattr(tool, "coroutine") and tool.coroutine is not None:
                        result = await tool.coroutine(**tool_args)
                    elif hasattr(tool, "ainvoke"):
                        result = await tool.ainvoke(tool_args)
                    elif hasattr(tool, "invoke"):
                        result = tool.invoke(tool_args)
                    elif hasattr(tool, "func") and tool.func is not None:
                        # Check if func is a coroutine
                        import asyncio

                        if asyncio.iscoroutinefunction(tool.func):
                            result = await tool.func(**tool_args)
                        else:
                            result = tool.func(**tool_args)
                    elif hasattr(tool, "_run"):
                        result = tool._run(**tool_args)
                    elif hasattr(tool, "run"):
                        result = tool.run(**tool_args)
                    else:
                        return f"Tool '{tool_name}' has no callable method"

                    logger.info(f"Tool '{tool_name}' executed successfully")
                    return result

                except Exception as e:
                    logger.error(f"Error executing tool '{tool_name}': {e}", exc_info=True)
                    return f"Error executing tool '{tool_name}': {str(e)}"

        return f"Tool '{tool_name}' not found"

    async def stream_message(
        self, messages: list[dict[str, str]], max_tokens: int | None = None, tools: list[Any] | None = None
    ) -> AsyncIterator[str]:
        """Stream a message response, with optional tool usage."""

        if tools:
            # Use streaming with tools
            async for token in self._stream_message_with_tools(messages, tools):
                yield token
        else:
            # Use simple streaming for non-tool conversations
            async for token in self._stream_message_simple(messages):
                yield token

    async def _stream_message_simple(self, messages: list[dict[str, str]]) -> AsyncIterator[str]:
        """Stream a message without tools."""
        callback = StreamingCallbackHandler()
        llm = self._create_llm(streaming=True, callbacks=[callback])

        langchain_messages: list[BaseMessage] = [SystemMessage(content=self.system_prompt)]
        langchain_messages.extend(self._convert_messages(messages))

        import asyncio

        task = asyncio.create_task(llm.ainvoke(langchain_messages))

        try:
            async for token in callback.aiter():
                yield token
            await task
        except Exception as e:
            logger.error(f"Error in stream_message_simple: {e}")
            task.cancel()
            raise

    async def _stream_message_with_tools(self, messages: list[dict[str, str]], tools: list[Any]) -> AsyncIterator[str]:
        """Stream a message with tool support."""
        llm = self._create_llm(streaming=True)
        llm_with_tools = llm.bind_tools(tools)

        # Build initial message list with system prompt
        langchain_messages: list[BaseMessage] = [SystemMessage(content=self.system_prompt)]
        langchain_messages.extend(self._convert_messages(messages))

        max_iterations = 15
        iteration = 0

        while iteration < max_iterations:
            # Collect the full response while streaming
            full_response = None

            async for chunk in llm_with_tools.astream(langchain_messages):
                # Handle content that might be a list or string
                content = getattr(chunk, "content", None)

                if content:
                    if isinstance(content, str):
                        yield content
                    elif isinstance(content, list):
                        # Handle content blocks (common with Anthropic)
                        for block in content:
                            if isinstance(block, dict):
                                if block.get("type") == "text":
                                    text = block.get("text", "")
                                    if text:
                                        yield text
                                elif block.get("type") == "text_delta":
                                    text = block.get("text", "")
                                    if text:
                                        yield text
                            elif isinstance(block, str):
                                yield block

                # Accumulate the response for tool call detection
                if full_response is None:
                    full_response = chunk
                else:
                    try:
                        full_response = full_response + chunk
                    except TypeError:
                        # If chunks can't be added, just keep the latest
                        full_response = chunk

            # Check if there are tool calls to execute
            if full_response and hasattr(full_response, "tool_calls") and full_response.tool_calls:
                # Add the assistant's response to message history
                langchain_messages.append(full_response)

                # Execute each tool call
                for tool_call in full_response.tool_calls:
                    tool_name = tool_call.get("name", "")
                    tool_args = tool_call.get("args", {})
                    tool_id = tool_call.get("id", "")

                    # Notify about tool execution
                    yield f"\n\n🔧 *Executing tool: {tool_name}...*\n"

                    logger.debug(f"Executing tool: {tool_name} with args: {tool_args}")

                    # Execute the tool
                    tool_result = await self._execute_tool(tool_name, tool_args, tools)

                    # Serialize the result safely
                    serialized_result = serialize_result(tool_result)

                    yield "✅ *Tool completed*\n\n"

                    # Add the tool result to message history
                    tool_message = ToolMessage(content=serialized_result, tool_call_id=tool_id, name=tool_name)
                    langchain_messages.append(tool_message)

                iteration += 1
            else:
                # No more tool calls, we're done
                break


class OpenAIProvider(BaseChatProvider):
    def _create_llm(self, streaming: bool = False, callbacks: list[Any] | None = None) -> ChatOpenAI:
        return ChatOpenAI(  # type: ignore[call-arg]
            api_key=self.api_key,
            model=self.model,
            temperature=self.temperature,
            streaming=streaming,
            callbacks=callbacks or [],
        )


class AnthropicProvider(BaseChatProvider):
    def _create_llm(self, streaming: bool = False, callbacks: list[Any] | None = None) -> ChatAnthropic:
        return ChatAnthropic(  # type: ignore[call-arg]
            api_key=self.api_key,
            model=self.model,
            temperature=self.temperature,
            streaming=streaming,
            callbacks=callbacks or [],
        )


class GoogleProvider(BaseChatProvider):
    def _create_llm(self, streaming: bool = False, callbacks: list[Any] | None = None) -> ChatGoogleGenerativeAI:
        return ChatGoogleGenerativeAI(
            google_api_key=self.api_key,
            model=self.model,
            temperature=self.temperature,
            streaming=streaming,
            callbacks=callbacks or [],
        )


PROVIDER_REGISTRY: dict[str, type[BaseChatProvider]] = {
    "openai": OpenAIProvider,
    "anthropic": AnthropicProvider,
    "google": GoogleProvider,
}


def get_provider(
    provider_name: str, api_key: str, model: str, system_prompt: str | None = None, temperature: float = 0.7
) -> BaseChatProvider:
    """Get a chat provider instance."""
    provider_class = PROVIDER_REGISTRY.get(provider_name.lower())

    if not provider_class:
        supported = ", ".join(PROVIDER_REGISTRY.keys())
        raise ValueError(f"Unsupported provider: {provider_name}. Supported providers: {supported}")

    return provider_class(api_key, model, system_prompt, temperature)


def get_supported_providers() -> list[str]:
    """Get list of supported provider names."""
    return list(PROVIDER_REGISTRY.keys())
