"""How a chat turn runs the tools the model asks for: their order, a stop, the call limit and the answer."""

import asyncio
import logging
from collections.abc import AsyncIterator, Iterator, Sequence
from contextlib import aclosing
from functools import partial
from itertools import repeat
from typing import Any, cast

import anthropic
import httpx
import pytest
from langchain_core.messages import AIMessage, AIMessageChunk
from langchain_core.outputs import ChatGenerationChunk
from langchain_core.tools import BaseTool, StructuredTool
from pydantic import BaseModel, Field

from sparkth.core.i18n import locale_context
from sparkth.lib.audit.callbacks import AUDIT_AT_HANDLER_TAG
from sparkth.lib.compose.constants import OPERATOR_TOOL_NAME, REFUSE_TOOL_NAME
from sparkth.lib.llm import BaseChatProvider, get_provider
from sparkth.lib.testing import AddTranslation, ScriptedChatModel
from sparkth.plugins.compose.constants import PLANNER_REFUSED_CALL_LIMIT, REFUSAL_MESSAGE
from sparkth.plugins.compose.llm import complete_turn, stream_turn
from sparkth.plugins.compose.planner import TurnRouting
from sparkth.plugins.compose.tests.conftest import STUB_AGENT
from sparkth.plugins.compose.tests.helpers import handing_off_to, planner_answering

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


def _calls(*steps: int, text: str = "", usage: dict[str, int] | None = None) -> AIMessage:
    """A model reply asking for one ``record`` call per step."""
    return AIMessage(
        content=text,
        tool_calls=[{"name": "record", "args": {"step": step}, "id": f"call_{step}"} for step in steps],
        usage_metadata=usage,
    )


def _provider(
    model: ScriptedChatModel, monkeypatch: pytest.MonkeyPatch, *, streaming: bool = False
) -> BaseChatProvider:
    """A provider whose model is ``model``, answering whole messages unless ``streaming``.

    The fake model drops tool calls when it streams, so a model that calls tools answers whole.
    """
    model.disable_streaming = not streaming
    provider = get_provider("anthropic", "test-key", "claude-sonnet-5")
    monkeypatch.setattr(provider, "_create_llm", lambda streaming=False, callbacks=None: model)
    return provider


class _StalledModel(ScriptedChatModel):
    """A model that streams one chunk, then waits for a next one that never arrives, recording each chunk
    read and when its stream is closed."""

    reads: list[str] = Field(default_factory=list)

    async def _astream(self, *args: Any, **kwargs: Any) -> AsyncIterator[ChatGenerationChunk]:
        try:
            self.reads.append("one ")
            yield ChatGenerationChunk(message=AIMessageChunk(content="one ", id="reply"))
            await asyncio.Event().wait()
        finally:
            self.reads.append("closed")


def _connection_lost() -> Iterator[AIMessage]:
    """Replies whose first one fails the way a dropped Anthropic connection does."""
    raise anthropic.APIConnectionError(request=httpx.Request("POST", "https://api.anthropic.com"))
    yield AIMessage(content="never")


async def _events(
    tools: list[StructuredTool], provider: BaseChatProvider, max_tool_executions: int = 50
) -> list[dict[str, Any]]:
    """What the author's client receives from one streamed turn: everything but its routing."""
    turn = stream_turn(TURN, tools, provider, max_tool_executions, **handing_off_to(STUB_AGENT))
    return [event async for event in turn if event["type"] != "routed"]


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
            {"type": "token", "content": "Let me record these."},
            *[TOOL_START, TOOL_END] * 3,
            {"type": "token", "content": "\n\n"},
            {"type": "token", "content": "recorded"},
        ]
    else:
        response = await complete_turn(TURN, tools, provider, 50, **handing_off_to(STUB_AGENT))
        assert response["content"] == "Let me record these.\n\nrecorded"
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
    async with aclosing(stream_turn(TURN, [_record_tool(runs)], provider, 50, **handing_off_to(STUB_AGENT))) as events:
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

    response = await complete_turn(TURN, [_record_tool(runs)], provider, 2, **handing_off_to(STUB_AGENT))

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
    response = await complete_turn(TURN, tools, provider, 50, **handing_off_to(STUB_AGENT))
    metadata = response["metadata"]
    assert response["content"] == "hi"
    assert metadata["num_executions"] == 0
    assert metadata["limit_reached"] is False
    assert metadata["usage_metadata"]["total_tokens"] == 2


def _usage(total: int) -> dict[str, int]:
    return {"input_tokens": total - 1, "output_tokens": 1, "total_tokens": total}


async def test_a_turn_counts_the_tokens_of_every_model_reply(monkeypatch: pytest.MonkeyPatch) -> None:
    """The planner's hand-off and both of the agent's replies are each a model call the turn paid for."""
    agent_model = ScriptedChatModel(
        messages=iter([_calls(1, text="", usage=_usage(3)), AIMessage("recorded", usage_metadata=_usage(4))])
    )
    hand_off = AIMessage(
        "",
        tool_calls=[{"name": STUB_AGENT.name, "args": {"request": "Go"}, "id": "go"}],
        usage_metadata=_usage(5),
    )

    response = await complete_turn(
        TURN, [_record_tool([])], _provider(agent_model, monkeypatch), 50, **planner_answering(hand_off, STUB_AGENT)
    )

    assert response["metadata"]["usage_metadata"]["total_tokens"] == 12


async def test_a_turn_the_planner_answers_counts_its_tokens(monkeypatch: pytest.MonkeyPatch) -> None:
    provider = _provider(ScriptedChatModel(messages=iter([])), monkeypatch)
    greeting = AIMessage("Hello!", usage_metadata=_usage(6))

    response = await complete_turn(TURN, [], provider, 50, **planner_answering(greeting, STUB_AGENT))

    assert response["metadata"]["usage_metadata"]["total_tokens"] == 6


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
    response = await complete_turn(TURN, tools, provider, 50, **handing_off_to(STUB_AGENT))
    assert response["content"] == "Hello there"


@pytest.mark.parametrize("stream", [False, True], ids=["non_streaming", "streaming"])
async def test_a_provider_error_leaves_with_its_own_type(stream: bool, monkeypatch: pytest.MonkeyPatch) -> None:
    provider = _provider(ScriptedChatModel(messages=_connection_lost()), monkeypatch)
    tools = [_record_tool([])]

    with pytest.raises(anthropic.APIConnectionError):
        if stream:
            await _events(tools, provider)
        else:
            await complete_turn(TURN, tools, provider, 50, **handing_off_to(STUB_AGENT))


async def test_a_streamed_turn_at_the_limit_ends_with_the_models_answer(monkeypatch: pytest.MonkeyPatch) -> None:
    runs: list[str] = []
    model = ScriptedChatModel(messages=iter([_calls(1, 2, 3), AIMessage("answer")]))
    provider = _provider(model, monkeypatch)

    events = await _events([_record_tool(runs)], provider, 2)

    assert events == [TOOL_START, TOOL_END, TOOL_START, TOOL_END, {"type": "token", "content": "answer"}]
    assert runs == ["start 1", "end 1", "start 2", "end 2"]


async def test_a_model_that_ignores_the_block_ends_the_turn_with_a_notice(monkeypatch: pytest.MonkeyPatch) -> None:
    model = ScriptedChatModel(messages=iter([_calls(1), _calls(2), _calls(3), AIMessage("never")]))
    provider = _provider(model, monkeypatch)

    response = await complete_turn(TURN, [_record_tool([])], provider, 1, **handing_off_to(STUB_AGENT))

    assert response["content"] == LIMIT_NOTICE
    assert response["metadata"]["limit_reached"] is True
    # The limit is used up by the first reply, the second is blocked, and the third asks for tools
    # again: the fourth reply is never asked for.
    assert next(model.messages) == AIMessage("never")


async def test_a_streamed_turn_the_limit_ended_shows_the_notice_as_its_answer(monkeypatch: pytest.MonkeyPatch) -> None:
    model = ScriptedChatModel(messages=iter([_calls(1), _calls(2), _calls(3), AIMessage("never")]))
    provider = _provider(model, monkeypatch)

    events = await _events([_record_tool([])], provider, 1)

    assert events[-1] == {"type": "token", "content": LIMIT_NOTICE}


async def test_the_limit_notice_is_translated_into_the_active_locale(
    translation_catalog: AddTranslation, monkeypatch: pytest.MonkeyPatch
) -> None:
    translation_catalog(LIMIT_NOTICE, "Alcancé el límite de herramientas de este turno.")
    model = ScriptedChatModel(messages=iter([_calls(1), _calls(2), _calls(3)]))
    provider = _provider(model, monkeypatch)

    with locale_context("es"):
        response = await complete_turn(TURN, [_record_tool([])], provider, 1, **handing_off_to(STUB_AGENT))

    assert response["content"] == "Alcancé el límite de herramientas de este turno."


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
        await complete_turn(TURN, [_record_tool([])], provider, 2, **handing_off_to(STUB_AGENT))

    # Reply 1 uses the limit, reply 2 is blocked, and reply 3 asks for tools again: replies 4 and 5
    # are never asked for, however many calls each reply batches.
    assert next(model.messages) is replies[3]


def _turn_warnings(caplog: pytest.LogCaptureFixture) -> list[str]:
    return [
        record.getMessage()
        for record in caplog.records
        if record.name == "sparkth.plugins.compose.llm" and record.levelno == logging.WARNING
    ]


async def test_blocked_calls_log_that_the_tool_call_limit_was_reached(
    caplog: pytest.LogCaptureFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    model = ScriptedChatModel(messages=iter([_calls(1, 2, 3), AIMessage("answer")]))
    provider = _provider(model, monkeypatch)

    with caplog.at_level(logging.WARNING):
        await complete_turn(TURN, [_record_tool([])], provider, 2, **handing_off_to(STUB_AGENT))

    assert _turn_warnings(caplog) == ["Tool call limit (2) reached; blocked 1 call(s)"]


async def test_a_turn_ended_for_calling_tools_after_the_block_logs_a_warning(
    caplog: pytest.LogCaptureFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    model = ScriptedChatModel(messages=iter([_calls(1), _calls(2), _calls(3), AIMessage("never")]))
    provider = _provider(model, monkeypatch)

    with caplog.at_level(logging.WARNING):
        await complete_turn(TURN, [_record_tool([])], provider, 1, **handing_off_to(STUB_AGENT))

    assert _turn_warnings(caplog)[-1] == "Model asked for tools after the limit (1); the turn ends with a notice"


async def test_closing_a_streamed_turn_stops_reading_the_agents_model(monkeypatch: pytest.MonkeyPatch) -> None:
    """A stop closes the turn, so the agent's model must stop being read, not run on in the background."""
    model = _StalledModel(messages=iter([]))
    provider = _provider(model, monkeypatch, streaming=True)

    async with (
        asyncio.timeout(5),
        aclosing(stream_turn(TURN, [], provider, 50, **handing_off_to(STUB_AGENT))) as events,
    ):
        first_token = await anext(event async for event in events if event["type"] == "token")
        assert first_token == {"type": "token", "content": "one "}

    assert model.reads == ["one ", "closed"]


async def test_an_agents_reply_streams_token_by_token(monkeypatch: pytest.MonkeyPatch) -> None:
    provider = _provider(
        ScriptedChatModel(messages=iter([AIMessage("Hello there friend")])), monkeypatch, streaming=True
    )

    events = await _events([], provider)

    assert events == [{"type": "token", "content": token} for token in ["Hello", " ", "there", " ", "friend"]]


async def test_a_streamed_turn_names_its_agent_before_the_agent_writes(monkeypatch: pytest.MonkeyPatch) -> None:
    """So a turn the author stops mid-reply is still the agent's."""
    provider = _provider(ScriptedChatModel(messages=iter([AIMessage("Hello there")])), monkeypatch, streaming=True)

    turn = stream_turn(TURN, [], provider, 50, **handing_off_to(STUB_AGENT))
    first = await anext(turn)
    await turn.aclose()

    assert first == {"type": "routed", "routing": TurnRouting(agent=STUB_AGENT.name)}


async def _reply(planner: dict[str, Any], provider: BaseChatProvider, stream: bool) -> str:
    """The text the author sees for one turn."""
    if not stream:
        response = await complete_turn(TURN, [], provider, 50, **planner)
        return str(response["content"])
    turn = stream_turn(TURN, [], provider, 50, **planner)
    return "".join([event["content"] async for event in turn if event["type"] == "token"])


@pytest.mark.parametrize("stream", [False, True], ids=["non_streaming", "streaming"])
async def test_the_planners_own_answer_is_the_reply(stream: bool, monkeypatch: pytest.MonkeyPatch) -> None:
    provider = _provider(ScriptedChatModel(messages=iter([])), monkeypatch)

    reply = await _reply(
        planner_answering(AIMessage("Hello! I can help you design courses."), STUB_AGENT), provider, stream
    )

    assert reply == "Hello! I can help you design courses."


@pytest.mark.parametrize("stream", [False, True], ids=["non_streaming", "streaming"])
async def test_a_lead_in_to_a_hand_off_never_shows(stream: bool, monkeypatch: pytest.MonkeyPatch) -> None:
    provider = _provider(ScriptedChatModel(messages=iter([AIMessage("Here is the outline.")])), monkeypatch)
    hand_off = AIMessage(
        "Sure, passing this on.", tool_calls=[{"name": STUB_AGENT.name, "args": {"request": "An outline"}, "id": "c1"}]
    )

    reply = await _reply(planner_answering(hand_off, STUB_AGENT), provider, stream)

    assert reply == "Here is the outline."


@pytest.mark.parametrize("stream", [False, True], ids=["non_streaming", "streaming"])
async def test_a_refusal_is_the_refusal_sentence(stream: bool, monkeypatch: pytest.MonkeyPatch) -> None:
    provider = _provider(ScriptedChatModel(messages=iter([])), monkeypatch)
    refusal = AIMessage("", tool_calls=[{"name": REFUSE_TOOL_NAME, "args": {}, "id": "c1"}])

    reply = await _reply(planner_answering(refusal, STUB_AGENT), provider, stream)

    assert reply == REFUSAL_MESSAGE


async def _answered_by(
    planner: dict[str, Any], provider: BaseChatProvider, stream: bool, tools: Sequence[BaseTool] = ()
) -> TurnRouting:
    """Who the turn on ``tools`` says answered it; a streamed turn that names nobody leaves the default."""
    if not stream:
        routing: TurnRouting = (await complete_turn(TURN, tools, provider, 50, **planner))["routing"]
        return routing
    turn = stream_turn(TURN, tools, provider, 50, **planner)
    routed = [event["routing"] async for event in turn if event["type"] == "routed"]
    return cast(TurnRouting, routed[-1]) if routed else TurnRouting()


def _calling(name: str, args: dict[str, Any], call_id: str = "c1") -> AIMessage:
    """A planner reply calling the tool ``name``."""
    return AIMessage("", tool_calls=[{"name": name, "args": args, "id": call_id}])


def _planner_replying(*replies: AIMessage) -> dict[str, Any]:
    """A turn with the stub agent whose planner replies with ``replies`` in turn."""
    return {"agents": [STUB_AGENT], "planner_llm": ScriptedChatModel(messages=iter(replies), disable_streaming=True)}


@pytest.mark.parametrize("stream", [False, True], ids=["non_streaming", "streaming"])
@pytest.mark.parametrize(
    ("replies", "expected"),
    [
        ([_calling(STUB_AGENT.name, {"request": "An outline"})], TurnRouting(agent=STUB_AGENT.name)),
        ([_calling(REFUSE_TOOL_NAME, {})], TurnRouting(refused=True)),
        ([AIMessage("Hello!")], TurnRouting()),
        (
            [_calling(STUB_AGENT.name, {}), _calling(STUB_AGENT.name, {"request": "An outline"}, "c2")],
            TurnRouting(agent=STUB_AGENT.name),
        ),
        (
            [_calling("no_such_agent", {"request": "Go"}, f"c{n}") for n in range(PLANNER_REFUSED_CALL_LIMIT + 2)],
            TurnRouting(),
        ),
    ],
    ids=["hand_off", "refusal", "own_answer", "bounced_then_handed_off", "unknown_tool_until_stopped"],
)
async def test_the_turn_says_who_answered_it(
    replies: list[AIMessage], expected: TurnRouting, stream: bool, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Only a hand-off or refusal that returned counts; a call its tool refused names nobody."""
    provider = _provider(ScriptedChatModel(messages=repeat(AIMessage("Here is the outline."))), monkeypatch)
    assert await _answered_by(_planner_replying(*replies), provider, stream) == expected


def _operation(request: str = "Record step 1") -> AIMessage:
    """A planner reply asking the operator to carry out ``request``."""
    return AIMessage("", tool_calls=[{"name": OPERATOR_TOOL_NAME, "args": {"request": request}, "id": "op_1"}])


@pytest.mark.usefixtures("lms_tools")
async def test_an_operations_tool_cards_show_and_the_operators_text_does_not(monkeypatch: pytest.MonkeyPatch) -> None:
    """The author sees each of the operator's tool calls, never its own text, only the planner's answer."""
    runs: list[str] = []
    provider = _provider(ScriptedChatModel(messages=iter([_calls(1), AIMessage("Recorded step 1.")])), monkeypatch)
    planner = _planner_replying(_operation(), AIMessage("Step 1 is recorded."))

    turn = stream_turn(TURN, [_record_tool(runs)], provider, 50, **planner)
    events = [event async for event in turn if event["type"] != "routed"]

    assert events == [TOOL_START, TOOL_END, {"type": "token", "content": "Step 1 is recorded."}]
    assert runs == ["start 1", "end 1"]


@pytest.mark.parametrize("stream", [False, True], ids=["non_streaming", "streaming"])
@pytest.mark.parametrize(
    ("then", "expected"),
    [
        (AIMessage("Step 1 is recorded."), TurnRouting(agent=OPERATOR_TOOL_NAME)),
        (
            AIMessage("", tool_calls=[{"name": STUB_AGENT.name, "args": {"request": "An outline"}, "id": "c2"}]),
            TurnRouting(agent=STUB_AGENT.name),
        ),
    ],
    ids=["operation_only", "operation_then_agent"],
)
@pytest.mark.usefixtures("lms_tools")
async def test_a_turn_with_an_operation_says_who_answered_it_last(
    then: AIMessage, expected: TurnRouting, stream: bool, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An operation then the planner's own answer is recorded as the operator's turn; an operation then a
    hand-off as the agent's."""
    provider = _provider(ScriptedChatModel(messages=repeat(AIMessage("Done."))), monkeypatch)
    planner = _planner_replying(_operation(), then)

    assert await _answered_by(planner, provider, stream, [_record_tool([])]) == expected
