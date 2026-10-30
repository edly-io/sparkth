"""How a chat turn runs the tools the model asks for: their order, a stop, the call limit and the answer."""

import asyncio
import logging
from collections.abc import AsyncGenerator, Iterator
from contextlib import aclosing
from functools import partial
from typing import Any, cast

import anthropic
import httpx
import pytest
from langchain_core.messages import AIMessage
from langchain_core.tools import StructuredTool
from pydantic import BaseModel

from sparkth.core.i18n import locale_context
from sparkth.lib.audit.callbacks import AUDIT_AT_HANDLER_TAG
from sparkth.lib.testing import AddTranslation, ScriptedChatModel
from sparkth.llm.providers import AnthropicProvider

TURN = [{"role": "user", "content": "Record the steps."}]
LIMIT_NOTICE = (
    "I stopped because I reached the tool-call limit for this turn. You can send another message to continue."
)
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
    # stream_message is an async generator, but it is typed as an AsyncIterator.
    stream = cast(AsyncGenerator[dict[str, Any], None], provider.stream_message(TURN, tools=[_record_tool(runs)]))
    async with aclosing(stream) as events:
        async for event in events:
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


async def test_a_streamed_turn_at_the_limit_ends_with_the_models_answer(monkeypatch: pytest.MonkeyPatch) -> None:
    runs: list[str] = []
    model = ScriptedChatModel(messages=iter([_calls(1, 2, 3), AIMessage("answer")]))
    provider = _provider(model, monkeypatch, 2)

    events = await _events(provider, [_record_tool(runs)])

    assert events == [TOOL_START, TOOL_END, TOOL_START, TOOL_END, {"type": "token", "content": "answer"}]
    assert runs == ["start 1", "end 1", "start 2", "end 2"]


async def test_a_model_that_ignores_the_block_ends_the_turn_with_a_notice(monkeypatch: pytest.MonkeyPatch) -> None:
    model = ScriptedChatModel(messages=iter([_calls(1), _calls(2), _calls(3), AIMessage("never")]))
    provider = _provider(model, monkeypatch, 1)

    response = await provider.send_message(TURN, tools=[_record_tool([])])

    assert response["content"] == LIMIT_NOTICE
    assert response["metadata"]["limit_reached"] is True
    # The limit is used up by the first reply, the second is blocked, and the third asks for tools
    # again: the fourth reply is never asked for.
    assert next(model.messages) == AIMessage("never")


async def test_a_streamed_turn_the_limit_ended_shows_the_notice_as_its_answer(monkeypatch: pytest.MonkeyPatch) -> None:
    model = ScriptedChatModel(messages=iter([_calls(1), _calls(2), _calls(3), AIMessage("never")]))
    provider = _provider(model, monkeypatch, 1)

    events = await _events(provider, [_record_tool([])])

    assert events[-1] == {"type": "token", "content": LIMIT_NOTICE}


async def test_the_limit_notice_is_translated_into_the_active_locale(
    translation_catalog: AddTranslation, monkeypatch: pytest.MonkeyPatch
) -> None:
    translation_catalog(LIMIT_NOTICE, "Alcancé el límite de herramientas de este turno.")
    model = ScriptedChatModel(messages=iter([_calls(1), _calls(2), _calls(3)]))
    provider = _provider(model, monkeypatch, 1)

    with locale_context("es"):
        response = await provider.send_message(TURN, tools=[_record_tool([])])

    assert response["content"] == "Alcancé el límite de herramientas de este turno."


@pytest.mark.parametrize("stream", [False, True], ids=["non_streaming", "streaming"])
async def test_a_model_that_batches_calls_gets_one_more_reply_after_the_block(
    stream: bool, monkeypatch: pytest.MonkeyPatch
) -> None:
    replies = [_calls(1, 2, text=f"reply {number}") for number in range(1, 6)]
    model = ScriptedChatModel(messages=iter(replies))
    provider = _provider(model, monkeypatch, 2)

    if stream:
        await _events(provider, [_record_tool([])])
    else:
        await provider.send_message(TURN, tools=[_record_tool([])])

    # Reply 1 uses the limit, reply 2 is blocked, and reply 3 asks for tools again: replies 4 and 5
    # are never asked for, however many calls each reply batches.
    assert next(model.messages) is replies[3]


def _provider_warnings(caplog: pytest.LogCaptureFixture) -> list[str]:
    return [
        record.getMessage()
        for record in caplog.records
        if record.name == "sparkth.llm.providers" and record.levelno == logging.WARNING
    ]


async def test_blocked_calls_log_that_the_tool_call_limit_was_reached(
    caplog: pytest.LogCaptureFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    model = ScriptedChatModel(messages=iter([_calls(1, 2, 3), AIMessage("answer")]))
    provider = _provider(model, monkeypatch, 2)

    with caplog.at_level(logging.WARNING):
        await provider.send_message(TURN, tools=[_record_tool([])])

    assert _provider_warnings(caplog) == ["Tool call limit (2) reached; blocked 1 call(s)"]


async def test_a_turn_ended_for_calling_tools_after_the_block_logs_a_warning(
    caplog: pytest.LogCaptureFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    model = ScriptedChatModel(messages=iter([_calls(1), _calls(2), _calls(3), AIMessage("never")]))
    provider = _provider(model, monkeypatch, 1)

    with caplog.at_level(logging.WARNING):
        await provider.send_message(TURN, tools=[_record_tool([])])

    assert _provider_warnings(caplog)[-1] == "Model asked for tools after the limit (1); the turn ends with a notice"
