"""Tests for what a streamed turn stores and sends: its error messages, sections and tool calls."""

import json
import uuid
from collections.abc import AsyncGenerator, Sequence
from datetime import datetime
from functools import partial
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from sparkth.plugins.compose.detached import join_live_tasks
from sparkth.plugins.compose.routes.utils import parse_metadata_list
from sparkth.plugins.compose.routes.utils.stream_processor import ComposeStreamProcessor
from sparkth.plugins.compose.schemas import MessageResponse, PersistedToolCall, RagSection
from sparkth.plugins.compose.tests.conftest import STUB_AGENT
from sparkth.plugins.compose.tests.helpers import STREAM_TURN, handing_off_to, replay_turn

HELLO_WORLD = [{"type": "token", "content": "Hello"}, {"type": "token", "content": " world"}]

# The turns here are replayed, so the planner never runs.
PLANNER = handing_off_to(STUB_AGENT)


def _make_provider() -> MagicMock:
    return MagicMock()


@pytest.fixture(autouse=True)
def hello_world_turn(monkeypatch: pytest.MonkeyPatch) -> None:
    """Every turn the model reaches here answers "Hello world", unless a test scripts its own."""
    monkeypatch.setattr(STREAM_TURN, partial(replay_turn, HELLO_WORLD))


def _failing_turn(
    messages: list[dict[str, Any]], tools: Sequence[Any], provider: Any, max_tool_executions: int
) -> AsyncGenerator[dict[str, Any], None]:
    """A streamed turn that fails in a way nothing expects."""
    raise RuntimeError("simulated unexpected failure")


def _make_service() -> MagicMock:
    service = MagicMock()
    msg = MagicMock()
    msg.id = 1
    service.add_message = AsyncMock(return_value=msg)
    return service


def _make_conversation() -> MagicMock:
    conv = MagicMock()
    conv.id = 1
    conv.uuid = uuid.UUID("550e8400-e29b-41d4-a716-446655440000")
    return conv


class TestMessageResponseRagSections:
    def test_message_response_accepts_rag_sections(self) -> None:
        response = MessageResponse(
            id=1,
            role="assistant",
            content="Here is your answer.",
            tokens_used=None,
            cost=None,
            created_at=datetime(2024, 1, 1),
            message_type="text",
            attachment_name=None,
            attachment_size=None,
            rag_sections=[RagSection(type="section", name="Introduction", source="doc.pdf")],
        )
        assert response.rag_sections is not None
        assert len(response.rag_sections) == 1
        assert response.rag_sections[0].name == "Introduction"

    def test_message_response_rag_sections_defaults_to_none(self) -> None:
        response = MessageResponse(
            id=1,
            role="assistant",
            content="Hello.",
            tokens_used=None,
            cost=None,
            created_at=datetime(2024, 1, 1),
            message_type="text",
            attachment_name=None,
            attachment_size=None,
        )
        assert response.rag_sections is None


# Background task: add_message is called even when consumer stops early


@pytest.mark.asyncio
async def test_add_message_called_after_early_consumer_exit() -> None:
    """DB write must happen even if the SSE consumer stops reading before done."""
    service = _make_service()

    gen = ComposeStreamProcessor(
        _make_provider(),
        [{"role": "user", "content": "Hello"}],
        _make_conversation(),
        service,
        None,
        planner_setup=PLANNER,
    ).stream()

    # Consume only the first event then abandon the generator
    async for _ in gen:
        break

    await join_live_tasks()

    add_message_calls = service.add_message.call_args_list
    assistant_call = next((c for c in add_message_calls if c.kwargs.get("role") == "assistant"), None)
    assert assistant_call is not None, "add_message must be called even when the consumer exits early"


@pytest.mark.asyncio
async def test_unexpected_error_persists_error_to_db(monkeypatch: pytest.MonkeyPatch) -> None:
    """An unhandled exception escaping _run must write an is_error=True message to DB."""
    service = _make_service()
    provider = MagicMock()
    monkeypatch.setattr(STREAM_TURN, _failing_turn)

    gen = ComposeStreamProcessor(
        provider,
        [{"role": "user", "content": "Hello"}],
        _make_conversation(),
        service,
        None,
        planner_setup=PLANNER,
    ).stream()
    async for _ in gen:
        pass
    await join_live_tasks()

    error_calls = [c for c in service.add_message.call_args_list if c.kwargs.get("is_error") is True]
    assert len(error_calls) == 1
    assert "unexpected" in error_calls[0].kwargs["content"].lower()


# Metadata parsing helper


class TestParseMetadataList:
    def test_returns_none_for_no_metadata(self) -> None:
        assert parse_metadata_list(None, "tool_calls") is None

    def test_returns_none_for_empty_metadata(self) -> None:
        assert parse_metadata_list("{}", "tool_calls") is None

    def test_returns_none_for_invalid_json(self) -> None:
        assert parse_metadata_list("not-json", "tool_calls") is None

    def test_returns_none_when_value_not_list(self) -> None:
        assert parse_metadata_list(json.dumps({"tool_calls": "bad"}), "tool_calls") is None

    def test_returns_list_for_tool_calls_key(self) -> None:
        meta = json.dumps({"tool_calls": [{"name": "search_web"}, {"name": "search_web"}]})
        result = parse_metadata_list(meta, "tool_calls")
        assert result is not None
        assert len(result) == 2
        assert result[0]["name"] == "search_web"

    def test_returns_list_for_rag_sections_key(self) -> None:
        meta = json.dumps({"rag_sections": [{"type": "section", "name": "Intro"}]})
        result = parse_metadata_list(meta, "rag_sections")
        assert result is not None
        assert len(result) == 1
        assert result[0]["name"] == "Intro"

    def test_ignores_other_keys(self) -> None:
        meta = json.dumps({"rag_sections": [{"type": "section", "name": "Intro"}]})
        assert parse_metadata_list(meta, "tool_calls") is None


# Tool-call streaming → metadata persistence + done payload


@pytest.mark.asyncio
async def test_tool_calls_saved_in_metadata(monkeypatch: pytest.MonkeyPatch) -> None:
    """Tool call names are persisted in message metadata when tools are invoked."""
    service = _make_service()
    provider = MagicMock()
    events = [
        {"type": "tool_start", "name": "search_web"},
        {"type": "tool_end", "name": "search_web"},
        {"type": "token", "content": "Result"},
    ]
    monkeypatch.setattr(STREAM_TURN, partial(replay_turn, events))

    async for _ in ComposeStreamProcessor(
        provider,
        [{"role": "user", "content": "search for something"}],
        _make_conversation(),
        service,
        None,
        planner_setup=PLANNER,
    ).stream():
        pass
    await join_live_tasks()

    add_message_calls = service.add_message.call_args_list
    assistant_call = next(
        (c for c in add_message_calls if c.kwargs.get("role") == "assistant"),
        None,
    )
    assert assistant_call is not None
    metadata = assistant_call.kwargs.get("metadata")
    assert metadata is not None
    assert "tool_calls" in metadata
    assert metadata["tool_calls"] == [{"name": "search_web", "status": "done"}]


@pytest.mark.asyncio
async def test_tool_calls_in_done_payload(monkeypatch: pytest.MonkeyPatch) -> None:
    """The done SSE payload includes tool_calls so the frontend can confirm them."""
    provider = MagicMock()
    scripted = [
        {"type": "tool_start", "name": "get_data"},
        {"type": "tool_end", "name": "get_data"},
        {"type": "token", "content": "Done"},
    ]
    monkeypatch.setattr(STREAM_TURN, partial(replay_turn, scripted))

    events = []
    async for chunk in ComposeStreamProcessor(
        provider,
        [{"role": "user", "content": "run a tool"}],
        _make_conversation(),
        _make_service(),
        None,
        planner_setup=PLANNER,
    ).stream():
        if chunk.startswith("data:"):
            events.append(json.loads(chunk[5:].strip()))
    await join_live_tasks()

    done_event = next((e for e in events if e.get("done")), None)
    assert done_event is not None
    msg = done_event.get("message", {})
    assert msg.get("tool_calls") == [{"name": "get_data", "status": "done"}]


@pytest.mark.asyncio
async def test_no_tool_calls_metadata_without_tools() -> None:
    """When no tools are invoked, tool_calls is absent from the message metadata."""
    service = _make_service()

    async for _ in ComposeStreamProcessor(
        _make_provider(),
        [{"role": "user", "content": "Hello"}],
        _make_conversation(),
        service,
        None,
        planner_setup=PLANNER,
    ).stream():
        pass
    await join_live_tasks()

    add_message_calls = service.add_message.call_args_list
    assistant_call = next(
        (c for c in add_message_calls if c.kwargs.get("role") == "assistant"),
        None,
    )
    assert assistant_call is not None
    metadata = assistant_call.kwargs.get("metadata")
    assert metadata is None or metadata.get("tool_calls") is None


class TestMessageResponseToolCalls:
    def test_message_response_accepts_tool_calls(self) -> None:
        response = MessageResponse(
            id=1,
            role="assistant",
            content="Here is your answer.",
            tokens_used=None,
            cost=None,
            created_at=datetime(2024, 1, 1),
            message_type="text",
            attachment_name=None,
            attachment_size=None,
            tool_calls=[PersistedToolCall(name="search_web"), PersistedToolCall(name="search_web")],
        )
        assert response.tool_calls is not None
        assert len(response.tool_calls) == 2
        assert response.tool_calls[0].name == "search_web"

    def test_message_response_tool_calls_defaults_to_none(self) -> None:
        response = MessageResponse(
            id=1,
            role="assistant",
            content="Hello.",
            tokens_used=None,
            cost=None,
            created_at=datetime(2024, 1, 1),
            message_type="text",
            attachment_name=None,
            attachment_size=None,
        )
        assert response.tool_calls is None
