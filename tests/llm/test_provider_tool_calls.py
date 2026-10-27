"""How a chat turn runs the tools the model asks for: their order, a stop, the call limit and the answer."""

import asyncio
from collections.abc import Iterator
from functools import partial
from typing import Any

import anthropic
import httpx
import pytest
from langchain_core.messages import AIMessage
from langchain_core.tools import StructuredTool
from pydantic import BaseModel

from sparkth.lib.audit.callbacks import AUDIT_AT_HANDLER_TAG
from sparkth.lib.testing import ScriptedChatModel
from sparkth.llm.providers import AnthropicProvider

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


def _provider(
    model: ScriptedChatModel, monkeypatch: pytest.MonkeyPatch, max_tool_executions: int = 50
) -> AnthropicProvider:
    provider = AnthropicProvider("test-key", "claude-sonnet-5", None, 0.7, max_tool_executions)
    monkeypatch.setattr(provider, "_create_llm", lambda streaming=False, callbacks=None: model)
    return provider


def _connection_lost() -> Iterator[AIMessage]:
    """Replies whose first one fails the way a dropped Anthropic connection does."""
    raise anthropic.APIConnectionError(request=httpx.Request("POST", "https://api.anthropic.com"))
    yield AIMessage(content="never")


async def _events(provider: AnthropicProvider, tools: list[StructuredTool]) -> list[dict[str, Any]]:
    return [event async for event in provider.stream_message(TURN, tools=tools)]


@pytest.mark.parametrize("stream", [False, True], ids=["non_streaming", "streaming"])
async def test_tool_calls_run_one_at_a_time_in_the_order_the_model_listed_them(
    stream: bool, monkeypatch: pytest.MonkeyPatch
) -> None:
    runs: list[str] = []
    model = ScriptedChatModel(messages=iter([_calls(1, 2, 3, text="Let me record these."), AIMessage("recorded")]))
    provider = _provider(model, monkeypatch)
    tools = [_record_tool(runs)]

    if stream:
        assert await _events(provider, tools) == [
            *[TOOL_START, TOOL_END] * 3,
            {"type": "token", "content": "recorded"},
        ]
    else:
        response = await provider.send_message(TURN, tools=tools)
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
    async for event in provider.stream_message(TURN, tools=[_record_tool(runs)]):
        if event["type"] == "tool_start":
            starts += 1
            if starts == 2:
                break

    assert runs == ["start 1", "end 1"]


async def test_calls_past_the_limit_are_blocked_and_the_model_answers(monkeypatch: pytest.MonkeyPatch) -> None:
    runs: list[str] = []
    model = ScriptedChatModel(messages=iter([_calls(1, 2, 3), AIMessage("answer")]))
    provider = _provider(model, monkeypatch, 2)

    response = await provider.send_message(TURN, tools=[_record_tool(runs)])

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
        assert await _events(provider, tools) == [{"type": "token", "content": "hi"}]
        return
    response = await provider.send_message(TURN, tools=tools)
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
        events = await _events(provider, tools)
        assert [event["content"] for event in events if event["type"] == "token"] == ["Hello ", "there"]
        return
    response = await provider.send_message(TURN, tools=tools)
    assert response["content"] == "Hello there"


@pytest.mark.parametrize("stream", [False, True], ids=["non_streaming", "streaming"])
async def test_a_provider_error_leaves_with_its_own_type(stream: bool, monkeypatch: pytest.MonkeyPatch) -> None:
    provider = _provider(ScriptedChatModel(messages=_connection_lost()), monkeypatch)
    tools = [_record_tool([])]

    with pytest.raises(anthropic.APIConnectionError):
        if stream:
            await _events(provider, tools)
        else:
            await provider.send_message(TURN, tools=tools)
