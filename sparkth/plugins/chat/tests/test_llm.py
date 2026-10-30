"""How a chat turn runs the tools the model asks for: their order, a stop, the call limit and the answer."""

import asyncio
import logging
from collections.abc import AsyncGenerator, Iterator
from contextlib import aclosing
from functools import partial
from typing import Any
from unittest.mock import MagicMock

import anthropic
import httpx
import pytest
from langchain_core.messages import AIMessage, AIMessageChunk
from langchain_core.tools import StructuredTool
from pydantic import BaseModel

from sparkth.lib.audit.callbacks import AUDIT_AT_HANDLER_TAG
from sparkth.lib.llm import BaseChatProvider, get_provider
from sparkth.lib.testing import ScriptedChatModel
from sparkth.plugins.chat.llm import complete_turn, stream_turn

TURN = [{"role": "user", "content": "Record the steps."}]
TOOL_START = {"type": "tool_start", "name": "record"}
TOOL_END = {"type": "tool_end", "name": "record", "failure": None}


class _StepArgs(BaseModel):
    step: int


async def _record(runs: list[str], step: int) -> dict[str, int]:
    """Record when a step starts and ends; later steps finish faster, so overlapping runs would show."""
    runs.append(f"start {step}")
    await asyncio.sleep(0.03 / step)
    runs.append(f"end {step}")
    return {"step": step}


def _record_tool(runs: list[str]) -> StructuredTool:
    return StructuredTool.from_function(
        coroutine=partial(_record, runs),
        name="record",
        description="Record a step.",
        args_schema=_StepArgs,
        tags=[AUDIT_AT_HANDLER_TAG],
    )


def _calls(*steps: int, text: str = "") -> AIMessage:
    """A model reply asking for one ``record`` call per step."""
    return AIMessage(
        content=text, tool_calls=[{"name": "record", "args": {"step": step}, "id": f"call_{step}"} for step in steps]
    )


def _provider(model: ScriptedChatModel, monkeypatch: pytest.MonkeyPatch) -> BaseChatProvider:
    provider = get_provider("anthropic", "test-key", "claude-sonnet-5")
    monkeypatch.setattr(provider, "_create_llm", lambda streaming=False, callbacks=None: model)
    return provider


async def _counted_reply(reads: list[str], messages: Any) -> AsyncGenerator[AIMessageChunk, None]:
    """A three-chunk model reply that records each chunk read, and when its stream is closed."""
    try:
        for text in ("one ", "two ", "three"):
            reads.append(text)
            yield AIMessageChunk(content=text)
    finally:
        reads.append("closed")


def _connection_lost() -> Iterator[AIMessage]:
    """Replies whose first one fails the way a dropped Anthropic connection does."""
    raise anthropic.APIConnectionError(request=httpx.Request("POST", "https://api.anthropic.com"))
    yield AIMessage(content="never")


async def _events(
    tools: list[StructuredTool], provider: BaseChatProvider, max_tool_executions: int = 50
) -> list[dict[str, Any]]:
    return [event async for event in stream_turn(TURN, tools, provider, max_tool_executions)]


@pytest.mark.parametrize("stream", [False, True], ids=["non_streaming", "streaming"])
async def test_tool_calls_run_one_at_a_time_in_the_order_the_model_listed_them(
    stream: bool, monkeypatch: pytest.MonkeyPatch
) -> None:
    runs: list[str] = []
    model = ScriptedChatModel(messages=iter([_calls(1, 2, 3, text="Let me record these."), AIMessage("recorded")]))
    provider = _provider(model, monkeypatch)
    tools = [_record_tool(runs)]

    if stream:
        assert await _events(tools, provider) == [
            *[TOOL_START, TOOL_END] * 3,
            {"type": "token", "content": "recorded"},
        ]
    else:
        response = await complete_turn(TURN, tools, provider, 50)
        assert response["content"] == "recorded"
        executions = response["metadata"]["tool_executions"]
        assert [execution["tool_input"] for execution in executions] == [{"step": 1}, {"step": 2}, {"step": 3}]
    assert runs == ["start 1", "end 1", "start 2", "end 2", "start 3", "end 3"]


async def test_a_consumer_that_stops_at_tool_start_keeps_that_tool_from_running(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runs: list[str] = []
    model = ScriptedChatModel(messages=iter([_calls(1, 2), AIMessage("never")]))
    provider = _provider(model, monkeypatch)

    starts = 0
    async with aclosing(stream_turn(TURN, [_record_tool(runs)], provider, 50)) as events:
        async for event in events:
            if event["type"] == "tool_start":
                starts += 1
                if starts == 2:
                    break

    assert runs == ["start 1", "end 1"]


async def test_calls_past_the_limit_are_blocked_and_the_model_answers(monkeypatch: pytest.MonkeyPatch) -> None:
    runs: list[str] = []
    model = ScriptedChatModel(messages=iter([_calls(1, 2, 3), AIMessage("answer")]))
    provider = _provider(model, monkeypatch)

    response = await complete_turn(TURN, [_record_tool(runs)], provider, 2)

    metadata = response["metadata"]
    assert response["content"] == "answer"
    assert [execution["tool_input"]["step"] for execution in metadata["tool_executions"]] == [1, 2]
    assert metadata["num_executions"] == 2
    assert metadata["limit_reached"] is True
    assert runs == ["start 1", "end 1", "start 2", "end 2"]


@pytest.mark.parametrize("stream", [False, True], ids=["non_streaming", "streaming"])
async def test_a_turn_where_the_model_calls_no_tool_returns_its_answer(
    stream: bool, monkeypatch: pytest.MonkeyPatch
) -> None:
    usage = {"input_tokens": 1, "output_tokens": 1, "total_tokens": 2}
    model = ScriptedChatModel(messages=iter([AIMessage(content="hi", usage_metadata=usage)]))
    provider = _provider(model, monkeypatch)
    tools = [_record_tool([])]

    if stream:
        assert await _events(tools, provider) == [{"type": "token", "content": "hi"}]
        return
    response = await complete_turn(TURN, tools, provider, 50)
    metadata = response["metadata"]
    assert response["content"] == "hi"
    assert metadata["num_executions"] == 0
    assert metadata["limit_reached"] is False
    assert metadata["usage_metadata"]["total_tokens"] == 2


@pytest.mark.parametrize("stream", [False, True], ids=["non_streaming", "streaming"])
async def test_a_content_block_answer_streams_block_by_block(stream: bool, monkeypatch: pytest.MonkeyPatch) -> None:
    blocks: list[str | dict[str, Any]] = [
        {"type": "text", "text": "Hello "},
        {"type": "text", "text": ""},
        {"type": "text", "text": "there"},
    ]
    model = ScriptedChatModel(messages=iter([_calls(1), AIMessage(content=blocks)]))
    provider = _provider(model, monkeypatch)
    tools = [_record_tool([])]

    if stream:
        events = await _events(tools, provider)
        assert [event["content"] for event in events if event["type"] == "token"] == ["Hello ", "there"]
        return
    response = await complete_turn(TURN, tools, provider, 50)
    assert response["content"] == "Hello there"


@pytest.mark.parametrize("stream", [False, True], ids=["non_streaming", "streaming"])
async def test_a_provider_error_leaves_with_its_own_type(stream: bool, monkeypatch: pytest.MonkeyPatch) -> None:
    provider = _provider(ScriptedChatModel(messages=_connection_lost()), monkeypatch)
    tools = [_record_tool([])]

    with pytest.raises(anthropic.APIConnectionError):
        if stream:
            await _events(tools, provider)
        else:
            await complete_turn(TURN, tools, provider, 50)


async def test_a_streamed_turn_at_the_limit_ends_with_the_models_answer(monkeypatch: pytest.MonkeyPatch) -> None:
    runs: list[str] = []
    model = ScriptedChatModel(messages=iter([_calls(1, 2, 3), AIMessage("answer")]))
    provider = _provider(model, monkeypatch)

    events = await _events([_record_tool(runs)], provider, 2)

    assert events == [TOOL_START, TOOL_END, TOOL_START, TOOL_END, {"type": "token", "content": "answer"}]
    assert runs == ["start 1", "end 1", "start 2", "end 2"]


async def test_a_model_that_ignores_the_block_ends_the_turn(monkeypatch: pytest.MonkeyPatch) -> None:
    model = ScriptedChatModel(messages=iter([_calls(1), _calls(2), _calls(3), AIMessage("never")]))
    provider = _provider(model, monkeypatch)

    response = await complete_turn(TURN, [_record_tool([])], provider, 1)

    assert response["content"] == ""
    # The limit is used up by the first reply, the second is blocked, and the third asks for tools
    # again: the fourth reply is never asked for.
    assert next(model.messages) == AIMessage("never")


@pytest.mark.parametrize("stream", [False, True], ids=["non_streaming", "streaming"])
async def test_a_model_that_batches_calls_gets_one_more_reply_after_the_block(
    stream: bool, monkeypatch: pytest.MonkeyPatch
) -> None:
    replies = [_calls(1, 2, text=f"reply {number}") for number in range(1, 6)]
    model = ScriptedChatModel(messages=iter(replies))
    provider = _provider(model, monkeypatch)

    if stream:
        await _events([_record_tool([])], provider, 2)
    else:
        await complete_turn(TURN, [_record_tool([])], provider, 2)

    # Reply 1 uses the limit, reply 2 is blocked, and reply 3 asks for tools again: replies 4 and 5
    # are never asked for, however many calls each reply batches.
    assert next(model.messages) is replies[3]


def _turn_warnings(caplog: pytest.LogCaptureFixture) -> list[str]:
    return [
        record.getMessage()
        for record in caplog.records
        if record.name == "sparkth.plugins.chat.llm" and record.levelno == logging.WARNING
    ]


async def test_blocked_calls_log_that_the_tool_call_limit_was_reached(
    caplog: pytest.LogCaptureFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    model = ScriptedChatModel(messages=iter([_calls(1, 2, 3), AIMessage("answer")]))
    provider = _provider(model, monkeypatch)

    with caplog.at_level(logging.WARNING):
        await complete_turn(TURN, [_record_tool([])], provider, 2)

    assert _turn_warnings(caplog) == ["Tool call limit (2) reached; blocked 1 call(s)"]


async def test_a_turn_ended_for_calling_tools_after_the_block_logs_a_warning(
    caplog: pytest.LogCaptureFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    model = ScriptedChatModel(messages=iter([_calls(1), _calls(2), _calls(3), AIMessage("never")]))
    provider = _provider(model, monkeypatch)

    with caplog.at_level(logging.WARNING):
        await complete_turn(TURN, [_record_tool([])], provider, 1)

    assert _turn_warnings(caplog)[-1] == "Model asked for tools after the limit (1); the turn ends without an answer"


async def test_a_streamed_turn_without_tools_arrives_token_by_token(monkeypatch: pytest.MonkeyPatch) -> None:
    provider = _provider(ScriptedChatModel(messages=iter([AIMessage("Hello there friend")])), monkeypatch)

    events = await _events([], provider)

    assert events == [{"type": "token", "content": token} for token in ["Hello", " ", "there", " ", "friend"]]


async def test_a_provider_error_without_tools_leaves_with_its_own_type(monkeypatch: pytest.MonkeyPatch) -> None:
    provider = _provider(ScriptedChatModel(messages=_connection_lost()), monkeypatch)

    with pytest.raises(anthropic.APIConnectionError):
        await _events([], provider)


async def test_closing_a_streamed_turn_without_tools_stops_reading_the_model(monkeypatch: pytest.MonkeyPatch) -> None:
    reads: list[str] = []
    provider = get_provider("anthropic", "test-key", "claude-sonnet-5")
    model = MagicMock(astream=partial(_counted_reply, reads))
    monkeypatch.setattr(provider, "_create_llm", lambda streaming=False: model)

    async with aclosing(stream_turn(TURN, [], provider, 50)) as events:
        assert await anext(events) == {"type": "token", "content": "one "}

    assert reads == ["one ", "closed"]
