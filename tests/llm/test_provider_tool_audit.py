"""The chat LangChain loop is an audited seam: tool calls executed inside
``_send_message_with_tools`` / ``_stream_message_with_tools`` are recorded
with source ``chat`` and the model identity that drove them (ADR-0002 seam
table row two)."""

from typing import Any

import pytest
from langchain_core.messages import AIMessage
from langchain_core.tools import StructuredTool

from sparkth.lib.audit import audited_tool_handler
from sparkth.lib.testing import AuditEventsFetcher
from sparkth.llm.providers import AnthropicProvider, GoogleProvider, OpenAIProvider


class FakeToolCallingLLM:
    """First call returns a tool call, second call returns a plain answer."""

    def __init__(self, response_metadata: dict[str, Any] | None = None) -> None:
        self.calls = 0
        self.response_metadata = response_metadata or {}

    def bind_tools(self, tools: list[Any]) -> "FakeToolCallingLLM":
        return self

    async def ainvoke(self, messages: list[Any]) -> AIMessage:
        self.calls += 1
        if self.calls == 1:
            return AIMessage(
                content="",
                tool_calls=[{"name": "lookup_course", "args": {"course_id": 5}, "id": "call_1"}],
                response_metadata=self.response_metadata,
            )
        return AIMessage(content="done", response_metadata=self.response_metadata)


def _lookup_course_tool() -> StructuredTool:
    async def lookup_course(course_id: int) -> dict[str, Any]:
        """Look up a course."""
        return {"course_id": course_id}

    return StructuredTool.from_function(
        coroutine=audited_tool_handler(lookup_course),
        name="lookup_course",
        description="Look up a course.",
    )


@pytest.fixture
def provider(monkeypatch: pytest.MonkeyPatch) -> AnthropicProvider:
    provider = AnthropicProvider(api_key="test-key", model="claude-sonnet-5")
    fake_llm = FakeToolCallingLLM(response_metadata={"model": "claude-sonnet-5-20250929"})
    monkeypatch.setattr(provider, "_create_llm", lambda streaming=False, callbacks=None: fake_llm)
    return provider


async def test_send_message_tool_calls_carry_chat_source_and_model_identity(
    audit_events: AuditEventsFetcher, provider: AnthropicProvider
) -> None:
    response = await provider.send_message(
        messages=[{"role": "user", "content": "look up course 5"}],
        tools=[_lookup_course_tool()],
    )

    assert response["content"] == "done"
    invoked, completed = await audit_events()
    for row in (invoked, completed):
        assert row.source == "chat"
        assert row.tool_name == "lookup_course"
        assert row.model_provider == "anthropic"
        assert row.model_name == "claude-sonnet-5"
        assert row.model_version == "claude-sonnet-5-20250929"
    assert invoked.tool_args == {"course_id": 5}


async def test_stream_message_tool_calls_are_audited(
    audit_events: AuditEventsFetcher, provider: AnthropicProvider
) -> None:
    events = [
        event
        async for event in provider.stream_message(
            messages=[{"role": "user", "content": "look up course 5"}],
            tools=[_lookup_course_tool()],
        )
    ]

    assert {"type": "tool_start", "name": "lookup_course"} in events
    invoked, completed = await audit_events()
    assert (invoked.category, invoked.action) == ("tool", "invoked")
    assert (completed.category, completed.action) == ("tool", "completed")
    assert invoked.source == "chat"
    assert invoked.model_provider == "anthropic"


def test_every_provider_declares_its_provider_name() -> None:
    assert OpenAIProvider.provider_name == "openai"
    assert AnthropicProvider.provider_name == "anthropic"
    assert GoogleProvider.provider_name == "google"
