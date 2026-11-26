"""How a chat turn runs the tools the model asks for: their order, a stop, the call limit and the answer."""

import asyncio
import logging
from collections.abc import AsyncIterator, Iterator, Sequence
from contextlib import aclosing
from dataclasses import asdict, replace
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
from sparkth.lib.audit import ToolFailureKind
from sparkth.lib.audit.callbacks import AUDIT_AT_HANDLER_TAG
from sparkth.lib.compose.constants import OPERATOR_AGENT_NAME, REFUSAL_TOOL_NAME, SHOW_PLAN_TOOL_NAME
from sparkth.lib.compose.hooks import AgentStructuredReply
from sparkth.lib.llm import BaseChatProvider, get_provider
from sparkth.lib.mcp.hooks import Tool
from sparkth.lib.rag import DocumentSections, SectionRef, SectionSelection
from sparkth.lib.testing import AddTranslation, ScriptedChatModel
from sparkth.plugins.compose.constants import (
    MAX_REJECTED_PLANNER_CALLS,
    MAX_STEPS_PER_TURN,
    REFUSAL_MESSAGE,
    STEP_RESULT_HEADING,
)
from sparkth.plugins.compose.llm import complete_turn, stream_turn
from sparkth.plugins.compose.planner import ExistingPlan, PlannedStep, PlannerSetup, TurnRouting
from sparkth.plugins.compose.tests.conftest import OTHER_AGENT, STUB_AGENT
from sparkth.plugins.compose.tests.helpers import RecordingChatModel, handing_off_to, planner_answering

TURN = [{"role": "user", "content": "Record the steps."}]
LIMIT_NOTICE = "I've done as much as I can in one go. Send another message and I'll carry on from here."
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


def _recording(runs: list[str]) -> PlannerSetup:
    """A turn whose planner hands every message to an agent with one tool of its own, ``record``, which notes its
    steps in ``runs``."""

    async def record(step: int) -> dict[str, int]:
        """Record a step."""
        return await _record(runs, step)

    return handing_off_to(replace(STUB_AGENT, tools=(Tool(record),)))


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


async def _events(runs: list[str], provider: BaseChatProvider, max_tool_executions: int = 50) -> list[dict[str, Any]]:
    """What the author's client receives from one streamed turn of the recording agent: everything but its
    routing."""
    turn = stream_turn(TURN, [], provider, max_tool_executions, planner_setup=_recording(runs))
    return [event async for event in turn if event["type"] != "routed"]


@pytest.mark.parametrize("stream", [False, True], ids=["non_streaming", "streaming"])
async def test_tool_calls_run_one_at_a_time_in_the_order_the_model_listed_them(
    stream: bool, monkeypatch: pytest.MonkeyPatch
) -> None:
    runs: list[str] = []
    model = ScriptedChatModel(messages=iter([_calls(1, 2, 3, text="Let me record these."), AIMessage("recorded")]))
    provider = _provider(model, monkeypatch)

    if stream:
        assert await _events(runs, provider) == [
            {"type": "token", "content": "Let me record these."},
            *[TOOL_START, TOOL_END] * 3,
            {"type": "token", "content": "\n\n"},
            {"type": "token", "content": "recorded"},
        ]
    else:
        response = await complete_turn(TURN, [], provider, 50, planner_setup=_recording(runs))
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
    async with aclosing(stream_turn(TURN, [], provider, 50, planner_setup=_recording(runs))) as events:
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

    response = await complete_turn(TURN, [], provider, 2, planner_setup=_recording(runs))

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
    runs: list[str] = []

    if stream:
        assert await _events(runs, provider) == [{"type": "token", "content": "hi"}]
        return
    response = await complete_turn(TURN, [], provider, 50, planner_setup=_recording(runs))
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
        TURN,
        [_record_tool([])],
        _provider(agent_model, monkeypatch),
        50,
        planner_setup=planner_answering(hand_off, STUB_AGENT),
    )

    assert response["metadata"]["usage_metadata"]["total_tokens"] == 12


async def test_a_turn_the_planner_answers_counts_its_tokens(monkeypatch: pytest.MonkeyPatch) -> None:
    provider = _provider(ScriptedChatModel(messages=iter([])), monkeypatch)
    greeting = AIMessage("Hello!", usage_metadata=_usage(6))

    response = await complete_turn(TURN, [], provider, 50, planner_setup=planner_answering(greeting, STUB_AGENT))

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
    runs: list[str] = []

    if stream:
        events = await _events(runs, provider)
        assert [event["content"] for event in events if event["type"] == "token"] == ["Hello ", "there"]
        return
    response = await complete_turn(TURN, [], provider, 50, planner_setup=_recording(runs))
    assert response["content"] == "Hello there"


@pytest.mark.parametrize("stream", [False, True], ids=["non_streaming", "streaming"])
async def test_a_provider_error_leaves_with_its_own_type(stream: bool, monkeypatch: pytest.MonkeyPatch) -> None:
    provider = _provider(ScriptedChatModel(messages=_connection_lost()), monkeypatch)
    runs: list[str] = []

    with pytest.raises(anthropic.APIConnectionError):
        if stream:
            await _events(runs, provider)
        else:
            await complete_turn(TURN, [], provider, 50, planner_setup=_recording(runs))


async def test_a_streamed_turn_at_the_limit_ends_with_the_models_answer(monkeypatch: pytest.MonkeyPatch) -> None:
    runs: list[str] = []
    model = ScriptedChatModel(messages=iter([_calls(1, 2, 3), AIMessage("answer")]))
    provider = _provider(model, monkeypatch)

    events = await _events(runs, provider, 2)

    assert events == [TOOL_START, TOOL_END, TOOL_START, TOOL_END, {"type": "token", "content": "answer"}]
    assert runs == ["start 1", "end 1", "start 2", "end 2"]


async def test_a_model_that_ignores_the_block_ends_the_turn_with_a_notice(monkeypatch: pytest.MonkeyPatch) -> None:
    model = ScriptedChatModel(messages=iter([_calls(1), _calls(2), _calls(3), AIMessage("never")]))
    provider = _provider(model, monkeypatch)

    response = await complete_turn(TURN, [], provider, 1, planner_setup=_recording([]))

    assert response["content"] == LIMIT_NOTICE
    assert response["metadata"]["limit_reached"] is True
    # The limit is used up by the first reply, the second is blocked, and the third asks for tools
    # again: the fourth reply is never asked for.
    assert next(model.messages) == AIMessage("never")


async def test_a_streamed_turn_the_limit_ended_shows_the_notice_as_its_answer(monkeypatch: pytest.MonkeyPatch) -> None:
    model = ScriptedChatModel(messages=iter([_calls(1), _calls(2), _calls(3), AIMessage("never")]))
    provider = _provider(model, monkeypatch)

    events = await _events([], provider, 1)

    assert events[-1] == {"type": "token", "content": LIMIT_NOTICE}


async def test_the_limit_notice_is_translated_into_the_active_locale(
    translation_catalog: AddTranslation, monkeypatch: pytest.MonkeyPatch
) -> None:
    translation_catalog(LIMIT_NOTICE, "Alcancé el límite de herramientas de este turno.")
    model = ScriptedChatModel(messages=iter([_calls(1), _calls(2), _calls(3)]))
    provider = _provider(model, monkeypatch)

    with locale_context("es"):
        response = await complete_turn(TURN, [], provider, 1, planner_setup=_recording([]))

    assert response["content"] == "Alcancé el límite de herramientas de este turno."


@pytest.mark.parametrize("stream", [False, True], ids=["non_streaming", "streaming"])
async def test_a_model_that_batches_calls_gets_one_more_reply_after_the_block(
    stream: bool, monkeypatch: pytest.MonkeyPatch
) -> None:
    replies = [_calls(1, 2, text=f"reply {number}") for number in range(1, 6)]
    model = ScriptedChatModel(messages=iter(replies))
    provider = _provider(model, monkeypatch)

    if stream:
        await _events([], provider, 2)
    else:
        await complete_turn(TURN, [], provider, 2, planner_setup=_recording([]))

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
        await complete_turn(TURN, [], provider, 2, planner_setup=_recording([]))

    assert _turn_warnings(caplog) == ["Tool call limit (2) reached; blocked 1 call(s)"]


async def test_a_turn_ended_for_calling_tools_after_the_block_logs_a_warning(
    caplog: pytest.LogCaptureFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    model = ScriptedChatModel(messages=iter([_calls(1), _calls(2), _calls(3), AIMessage("never")]))
    provider = _provider(model, monkeypatch)

    with caplog.at_level(logging.WARNING):
        await complete_turn(TURN, [], provider, 1, planner_setup=_recording([]))

    assert _turn_warnings(caplog)[-1] == "Model asked for tools after the limit (1); the turn ends with a notice"


async def test_closing_a_streamed_turn_stops_reading_the_agents_model(monkeypatch: pytest.MonkeyPatch) -> None:
    """A stop closes the turn, so the agent's model must stop being read, not run on in the background."""
    model = _StalledModel(messages=iter([]))
    provider = _provider(model, monkeypatch, streaming=True)

    async with (
        asyncio.timeout(5),
        aclosing(stream_turn(TURN, [], provider, 50, planner_setup=handing_off_to(STUB_AGENT))) as events,
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

    turn = stream_turn(TURN, [], provider, 50, planner_setup=handing_off_to(STUB_AGENT))
    first = await anext(turn)
    await turn.aclose()

    assert first == {"type": "routed", "routing": TurnRouting(agent=STUB_AGENT.name), "status": STUB_AGENT.status}


async def _reply(
    planner: PlannerSetup, provider: BaseChatProvider, stream: bool, tools: Sequence[BaseTool] = ()
) -> str:
    """The text the author sees for one turn on ``tools``."""
    if not stream:
        response = await complete_turn(TURN, tools, provider, 50, planner_setup=planner)
        return str(response["content"])
    turn = stream_turn(TURN, tools, provider, 50, planner_setup=planner)
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
    refusal = AIMessage("", tool_calls=[{"name": REFUSAL_TOOL_NAME, "args": {}, "id": "c1"}])

    reply = await _reply(planner_answering(refusal, STUB_AGENT), provider, stream)

    assert reply == REFUSAL_MESSAGE


async def _answered_by(
    planner: PlannerSetup, provider: BaseChatProvider, stream: bool, tools: Sequence[BaseTool] = ()
) -> TurnRouting:
    """Who the turn on ``tools`` says answered it; a streamed turn that names nobody leaves the default."""
    if not stream:
        routing: TurnRouting = (await complete_turn(TURN, tools, provider, 50, planner_setup=planner))["routing"]
        return routing
    turn = stream_turn(TURN, tools, provider, 50, planner_setup=planner)
    routed = [event["routing"] async for event in turn if event["type"] == "routed"]
    return cast(TurnRouting, routed[-1]) if routed else TurnRouting()


def _calling(name: str, args: dict[str, Any], call_id: str = "c1") -> AIMessage:
    """A planner reply calling the tool ``name``."""
    return AIMessage("", tool_calls=[{"name": name, "args": args, "id": call_id}])


def _planner_replying(*replies: AIMessage) -> PlannerSetup:
    """A turn with the stub agent whose planner replies with ``replies`` in turn, then with nothing, which ends
    the turn."""
    planner = ScriptedChatModel(messages=iter([*replies, AIMessage("")]), disable_streaming=True)
    return PlannerSetup([STUB_AGENT], planner, None)


@pytest.mark.parametrize("stream", [False, True], ids=["non_streaming", "streaming"])
@pytest.mark.parametrize(
    ("replies", "expected"),
    [
        ([_calling(STUB_AGENT.name, {"request": "An outline"})], TurnRouting(agent=STUB_AGENT.name)),
        ([_calling(REFUSAL_TOOL_NAME, {})], TurnRouting(refused=True)),
        ([AIMessage("Hello!")], TurnRouting()),
        (
            [_calling(STUB_AGENT.name, {}), _calling(STUB_AGENT.name, {"request": "An outline"}, "c2")],
            TurnRouting(agent=STUB_AGENT.name),
        ),
        (
            [_calling("no_such_agent", {"request": "Go"}, f"c{n}") for n in range(MAX_REJECTED_PLANNER_CALLS + 2)],
            TurnRouting(),
        ),
    ],
    ids=["hand_off", "refusal", "own_answer", "bounced_then_handed_off", "unknown_tool_until_stopped"],
)
async def test_the_turn_says_who_answered_it(
    replies: list[AIMessage], expected: TurnRouting, stream: bool, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Only a hand-off or refusal that returned counts; a call its tool rejected names nobody."""
    provider = _provider(ScriptedChatModel(messages=repeat(AIMessage("Here is the outline."))), monkeypatch)
    assert await _answered_by(_planner_replying(*replies), provider, stream) == expected


def _operation(request: str = "Record step 1") -> AIMessage:
    """A planner reply asking the operator to carry out ``request``."""
    return AIMessage("", tool_calls=[{"name": OPERATOR_AGENT_NAME, "args": {"request": request}, "id": "op_1"}])


@pytest.mark.usefixtures("lms_tools")
async def test_an_operations_tool_cards_show_and_the_operators_text_does_not(monkeypatch: pytest.MonkeyPatch) -> None:
    """The author sees each of the operator's tool calls, never its own text, only the planner's answer."""
    runs: list[str] = []
    provider = _provider(ScriptedChatModel(messages=iter([_calls(1), AIMessage("Recorded step 1.")])), monkeypatch)
    planner = _planner_replying(_operation(), AIMessage("Step 1 is recorded."))

    turn = stream_turn(TURN, [_record_tool(runs)], provider, 50, planner_setup=planner)
    events = [event async for event in turn if event["type"] != "routed"]

    assert events == [TOOL_START, TOOL_END, {"type": "token", "content": "Step 1 is recorded."}]
    assert runs == ["start 1", "end 1"]


class _Picked(BaseModel):
    """The sections an agent picked."""

    sections: list[str]


async def _build_picked_context(picked: _Picked) -> str:
    return "Picked " + ", ".join(picked.sections)


# An agent whose reply is the sections it picked, built into context for later steps.
PICKING_AGENT = replace(STUB_AGENT, structured_reply=AgentStructuredReply(_Picked, _build_picked_context))


def _picked(*sections: str, text: str = "") -> AIMessage:
    """An agent reply giving its structured response, the ``sections`` it picked."""
    return AIMessage(text, tool_calls=[{"name": "_Picked", "args": {"sections": list(sections)}, "id": "picked"}])


@pytest.mark.parametrize("stream", [False, True], ids=["non_streaming", "streaming"])
async def test_a_structured_reply_never_shows_and_the_planner_reads_its_context(
    stream: bool, monkeypatch: pytest.MonkeyPatch
) -> None:
    provider = _provider(ScriptedChatModel(messages=iter([_picked("1.2", "3.1", text="Looking.")])), monkeypatch)
    planner_model = RecordingChatModel(
        messages=iter([_calling(PICKING_AGENT.name, {"request": "Find it"}), AIMessage("Found two sections.")]),
        disable_streaming=True,
    )
    planner = PlannerSetup([PICKING_AGENT], planner_model, None)

    if stream:
        turn = stream_turn(TURN, [], provider, 50, planner_setup=planner)
        shown = "".join([event["content"] async for event in turn if event["type"] == "token"])
    else:
        shown = (await complete_turn(TURN, [], provider, 50, planner_setup=planner))["content"]

    assert shown == "Found two sections."
    assert planner_model.seen[1][-1].text == f"{STEP_RESULT_HEADING}\nPicked 1.2, 3.1"


async def test_a_structured_reply_is_reported_on_the_stream(monkeypatch: pytest.MonkeyPatch) -> None:
    provider = _provider(ScriptedChatModel(messages=iter([_picked("1.2")])), monkeypatch)
    planner_model = RecordingChatModel(
        messages=iter([_calling(PICKING_AGENT.name, {"request": "Find it"}), AIMessage("")]), disable_streaming=True
    )

    turn = stream_turn(TURN, [], provider, 50, planner_setup=PlannerSetup([PICKING_AGENT], planner_model, None))
    replies = [event async for event in turn if event["type"] == "structured_reply"]

    assert replies == [{"type": "structured_reply", "agent": PICKING_AGENT.name, "reply": _Picked(sections=["1.2"])}]


async def _no_context(section_selection: SectionSelection) -> str:
    return ""


SELECTING_AGENT = replace(STUB_AGENT, structured_reply=AgentStructuredReply(SectionSelection, _no_context))


async def test_a_turn_returns_the_document_sections_its_steps_selected(monkeypatch: pytest.MonkeyPatch) -> None:
    section_selection = SectionSelection(
        documents=[DocumentSections(document_id=7, sections=[SectionRef(chapter="Cells")])]
    )
    selecting = AIMessage(
        "", tool_calls=[{"name": "SectionSelection", "args": section_selection.model_dump(), "id": "selected"}]
    )
    provider = _provider(ScriptedChatModel(messages=iter([selecting])), monkeypatch)
    planner_model = RecordingChatModel(
        messages=iter([_calling(SELECTING_AGENT.name, {"request": "Find it"}), AIMessage("")]), disable_streaming=True
    )

    response = await complete_turn(
        TURN, [], provider, 50, planner_setup=PlannerSetup([SELECTING_AGENT], planner_model, None)
    )

    assert response["section_selections"] == [section_selection]


async def test_a_structured_agent_that_answers_in_text_returns_nothing(monkeypatch: pytest.MonkeyPatch) -> None:
    provider = _provider(ScriptedChatModel(messages=iter([AIMessage("I found nothing.")])), monkeypatch)
    planner_model = RecordingChatModel(
        messages=iter([_calling(PICKING_AGENT.name, {"request": "Find it"}), AIMessage("")]), disable_streaming=True
    )

    response = await complete_turn(
        TURN, [], provider, 50, planner_setup=PlannerSetup([PICKING_AGENT], planner_model, None)
    )

    assert response["content"] == ""
    assert planner_model.seen[1][-1].text == ""


async def test_an_agent_gets_none_of_the_tools_the_turn_enables(monkeypatch: pytest.MonkeyPatch) -> None:
    """The turn enables ``record``, which is not the stub agent's own, so its call is rejected rather than run."""
    runs: list[str] = []
    provider = _provider(ScriptedChatModel(messages=iter([_calls(1), AIMessage("Could not record.")])), monkeypatch)

    response = await complete_turn(TURN, [_record_tool(runs)], provider, 50, planner_setup=handing_off_to(STUB_AGENT))

    assert runs == []
    assert [execution["failure"] for execution in response["metadata"]["tool_executions"]] == [
        ToolFailureKind.VALIDATION
    ]


async def test_an_agents_own_tool_runs_though_the_turn_enables_none(monkeypatch: pytest.MonkeyPatch) -> None:
    runs: list[str] = []
    provider = _provider(ScriptedChatModel(messages=iter([_calls(1), AIMessage("Recorded.")])), monkeypatch)

    turn = stream_turn(TURN, [], provider, 50, planner_setup=_recording(runs))
    events = [event async for event in turn if event["type"] != "routed"]

    assert events == [TOOL_START, TOOL_END, {"type": "token", "content": "Recorded."}]
    assert runs == ["start 1", "end 1"]


@pytest.mark.parametrize("stream", [False, True], ids=["non_streaming", "streaming"])
@pytest.mark.parametrize(
    ("then", "expected"),
    [
        (AIMessage("Step 1 is recorded."), TurnRouting(agent=OPERATOR_AGENT_NAME)),
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


async def test_the_agents_model_is_made_to_stream(monkeypatch: pytest.MonkeyPatch) -> None:
    """A model made with streaming off writes its whole reply before any of it reaches the author."""
    made_with_streaming: list[bool] = []
    model = ScriptedChatModel(messages=iter([AIMessage("Here is the lesson.")]))
    provider = get_provider("anthropic", "test-key", "claude-sonnet-5")

    def make_model(streaming: bool = False) -> ScriptedChatModel:
        made_with_streaming.append(streaming)
        return model

    monkeypatch.setattr(provider, "_create_llm", make_model)

    await complete_turn(TURN, [], provider, 50, planner_setup=handing_off_to(STUB_AGENT))

    assert made_with_streaming == [True]


def _step(agent: str, task: str) -> dict[str, str]:
    """One step of a plan: ``task``, done by ``agent``."""
    return {"agent": agent, "task": task}


def _two_step_turn(*then: AIMessage) -> PlannerSetup:
    """A turn with the stub and other agents whose planner hands a part to each, then replies ``then``."""
    replies = [
        _calling(STUB_AGENT.name, {"request": "Write the lesson"}, "c1"),
        _calling(OTHER_AGENT.name, {"request": "Build the activity"}, "c2"),
        *then,
    ]
    return PlannerSetup(
        [STUB_AGENT, OTHER_AGENT],
        ScriptedChatModel(messages=iter(replies), disable_streaming=True),
        None,
    )


def _two_replies(monkeypatch: pytest.MonkeyPatch) -> BaseChatProvider:
    replies = iter([AIMessage("Here is the lesson."), AIMessage("Here is the activity.")])
    return _provider(ScriptedChatModel(messages=replies), monkeypatch)


@pytest.mark.parametrize("stream", [False, True], ids=["non_streaming", "streaming"])
async def test_each_steps_reply_shows_apart_and_the_planner_adds_nothing_after_an_agent(
    stream: bool, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An agent's reply, with any question or choices in it, stays the last thing the author reads."""
    reply = await _reply(_two_step_turn(AIMessage("Both are ready!")), _two_replies(monkeypatch), stream)

    assert reply == "Here is the lesson.\n\nHere is the activity."


@pytest.mark.parametrize("stream", [False, True], ids=["non_streaming", "streaming"])
async def test_a_turn_ends_at_the_choices_an_agent_offered(stream: bool, monkeypatch: pytest.MonkeyPatch) -> None:
    """The author answers the agent before the next step runs."""
    choices = "Which level?\n\n```options single\nBeginner\nAdvanced\n```"
    replies = iter([AIMessage(choices), AIMessage("Here is the activity.")])
    provider = _provider(ScriptedChatModel(messages=replies), monkeypatch)

    reply = await _reply(_two_step_turn(AIMessage("Both are ready!")), provider, stream)

    assert reply == choices


@pytest.mark.parametrize("stream", [False, True], ids=["non_streaming", "streaming"])
@pytest.mark.usefixtures("lms_tools")
async def test_the_planner_tells_the_author_what_an_operation_after_an_agent_did(
    stream: bool, monkeypatch: pytest.MonkeyPatch
) -> None:
    provider = _provider(
        ScriptedChatModel(messages=iter([AIMessage("Here is the lesson."), _calls(1), AIMessage("Recorded.")])),
        monkeypatch,
    )
    planner = _planner_replying(
        _calling(
            SHOW_PLAN_TOOL_NAME, {"steps": [_step(STUB_AGENT.name, "Write"), _step(OPERATOR_AGENT_NAME, "Record")]}
        ),
        _calling(STUB_AGENT.name, {"request": "Write the lesson", "step": 1}, "c2"),
        _calling(OPERATOR_AGENT_NAME, {"request": "Record step 1", "step": 2}, "op"),
        AIMessage("Step 1 is recorded."),
    )

    reply = await _reply(planner, provider, stream, [_record_tool([])])

    assert reply == "Here is the lesson.\n\nStep 1 is recorded."


@pytest.mark.parametrize("stream", [False, True], ids=["non_streaming", "streaming"])
@pytest.mark.usefixtures("lms_tools")
async def test_the_planner_tells_the_author_what_an_operation_before_an_agent_did(
    stream: bool, monkeypatch: pytest.MonkeyPatch
) -> None:
    """What the planner says about an operation shows though the same reply calls the next step."""
    provider = _provider(
        ScriptedChatModel(messages=iter([_calls(1), AIMessage("Recorded."), AIMessage("Here is the lesson.")])),
        monkeypatch,
    )
    planner = _planner_replying(
        _calling(
            SHOW_PLAN_TOOL_NAME, {"steps": [_step(OPERATOR_AGENT_NAME, "Record"), _step(STUB_AGENT.name, "Write")]}
        ),
        _calling(OPERATOR_AGENT_NAME, {"request": "Record step 1", "step": 1}, "op"),
        AIMessage(
            "Step 1 is recorded.",
            tool_calls=[{"name": STUB_AGENT.name, "args": {"request": "Write the lesson", "step": 2}, "id": "c2"}],
        ),
    )

    reply = await _reply(planner, provider, stream, [_record_tool([])])

    assert reply == "Step 1 is recorded.\n\nHere is the lesson."


@pytest.mark.parametrize("stream", [False, True], ids=["non_streaming", "streaming"])
@pytest.mark.usefixtures("lms_tools")
async def test_the_planner_tells_the_author_about_an_operation_that_was_rejected_after_an_agent_wrote(
    stream: bool, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An operation outside a plan never runs after another step, and the author is told it wasn't done."""
    provider = _provider(ScriptedChatModel(messages=iter([AIMessage("Here is the lesson.")])), monkeypatch)
    planner = _planner_replying(
        _calling(STUB_AGENT.name, {"request": "Write the lesson"}),
        _calling(OPERATOR_AGENT_NAME, {"request": "Record step 1"}, "op"),
        AIMessage("I can record step 1 next. Just ask."),
    )
    runs: list[str] = []

    reply = await _reply(planner, provider, stream, [_record_tool(runs)])

    assert (reply, runs) == ("Here is the lesson.\n\nI can record step 1 next. Just ask.", [])


@pytest.mark.parametrize("stream", [False, True], ids=["non_streaming", "streaming"])
@pytest.mark.usefixtures("lms_tools")
async def test_the_limit_notice_shows_even_after_an_agent_wrote(stream: bool, monkeypatch: pytest.MonkeyPatch) -> None:
    done = [AIMessage("Done.") for _ in range(MAX_STEPS_PER_TURN - 1)]
    provider = _provider(ScriptedChatModel(messages=iter([*done, AIMessage("Here is the lesson.")])), monkeypatch)
    operations = range(1, MAX_STEPS_PER_TURN)
    plan = [*(_step(OPERATOR_AGENT_NAME, f"Go {n}") for n in operations), _step(STUB_AGENT.name, "Write the lesson")]
    planner = _planner_replying(
        _calling(SHOW_PLAN_TOOL_NAME, {"steps": plan}, "plan"),
        *(_calling(OPERATOR_AGENT_NAME, {"request": "Go", "step": n}, f"op{n}") for n in operations),
        _calling(STUB_AGENT.name, {"request": "Write the lesson", "step": MAX_STEPS_PER_TURN}),
        _calling(OPERATOR_AGENT_NAME, {"request": "Go"}, "over"),
    )

    reply = await _reply(planner, provider, stream, [_record_tool([])])

    assert reply == f"Here is the lesson.\n\n{LIMIT_NOTICE}"


async def test_a_step_never_starts_for_a_reader_that_stops_when_it_is_announced(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    agent_model = RecordingChatModel(messages=iter([AIMessage("Here is the lesson.")]))
    provider = _provider(agent_model, monkeypatch)

    turn = stream_turn(TURN, [], provider, 50, planner_setup=handing_off_to(STUB_AGENT))
    first = await anext(turn)
    await turn.aclose()

    assert first["type"] == "routed"
    assert agent_model.seen == []


async def test_a_turn_lists_its_steps_in_order(monkeypatch: pytest.MonkeyPatch) -> None:
    response = await complete_turn(TURN, [], _two_replies(monkeypatch), 50, planner_setup=_two_step_turn(AIMessage("")))

    assert response["metadata"]["agents"] == [STUB_AGENT.name, OTHER_AGENT.name]


async def test_a_turn_the_planner_answers_has_no_steps(monkeypatch: pytest.MonkeyPatch) -> None:
    provider = _provider(ScriptedChatModel(messages=iter([])), monkeypatch)

    response = await complete_turn(
        TURN, [], provider, 50, planner_setup=planner_answering(AIMessage("Hello!"), STUB_AGENT)
    )

    assert response["metadata"]["agents"] == []


@pytest.mark.parametrize("stream", [False, True], ids=["non_streaming", "streaming"])
async def test_a_refusal_after_an_agents_reply_shows_apart_from_it(
    stream: bool, monkeypatch: pytest.MonkeyPatch
) -> None:
    provider = _provider(ScriptedChatModel(messages=iter([AIMessage("Here is the lesson.")])), monkeypatch)
    planner = _planner_replying(
        _calling(STUB_AGENT.name, {"request": "Write the lesson"}), _calling(REFUSAL_TOOL_NAME, {}, "c2")
    )

    assert await _reply(planner, provider, stream) == f"Here is the lesson.\n\n{REFUSAL_MESSAGE}"


@pytest.mark.parametrize("stream", [False, True], ids=["non_streaming", "streaming"])
async def test_the_planner_answers_when_the_agent_wrote_nothing(stream: bool, monkeypatch: pytest.MonkeyPatch) -> None:
    provider = _provider(ScriptedChatModel(messages=iter([AIMessage("")])), monkeypatch)
    planner = _planner_replying(
        _calling(STUB_AGENT.name, {"request": "Write the lesson"}), AIMessage("Nothing came back.")
    )

    assert await _reply(planner, provider, stream) == "Nothing came back."


@pytest.mark.parametrize("stream", [False, True], ids=["non_streaming", "streaming"])
async def test_the_planner_answers_when_a_later_agent_wrote_nothing(
    stream: bool, monkeypatch: pytest.MonkeyPatch
) -> None:
    replies = iter([AIMessage("Here is the lesson."), AIMessage("")])
    provider = _provider(ScriptedChatModel(messages=replies), monkeypatch)

    reply = await _reply(_two_step_turn(AIMessage("The activity could not be built.")), provider, stream)

    assert reply == "Here is the lesson.\n\nThe activity could not be built."


async def test_a_turns_reply_metadata_is_the_agents_not_the_planners(monkeypatch: pytest.MonkeyPatch) -> None:
    lesson = AIMessage("Here is the lesson.", response_metadata={"model_name": "the-authors-model"})
    provider = _provider(ScriptedChatModel(messages=iter([lesson])), monkeypatch)
    planner = _planner_replying(
        _calling(STUB_AGENT.name, {"request": "Write the lesson"}),
        AIMessage("", response_metadata={"model_name": "the-planners-model"}),
    )

    response = await complete_turn(TURN, [], provider, 50, planner_setup=planner)

    assert response["metadata"]["response_metadata"]["model_name"] == "the-authors-model"


async def test_an_agent_may_answer_again_after_another_step(monkeypatch: pytest.MonkeyPatch) -> None:
    replies = iter(
        [AIMessage("Here is the lesson."), AIMessage("Here is the activity."), AIMessage("Lesson, revised.")]
    )
    planner = _two_step_turn(_calling(STUB_AGENT.name, {"request": "Revise the lesson"}, "c3"), AIMessage(""))

    response = await complete_turn(
        TURN, [], _provider(ScriptedChatModel(messages=replies), monkeypatch), 50, planner_setup=planner
    )

    assert response["metadata"]["agents"] == [STUB_AGENT.name, OTHER_AGENT.name, STUB_AGENT.name]


@pytest.mark.parametrize("stream", [False, True], ids=["non_streaming", "streaming"])
async def test_the_plan_is_left_out_of_the_reply(stream: bool, monkeypatch: pytest.MonkeyPatch) -> None:
    plan = {"steps": [_step(STUB_AGENT.name, "Write the lesson"), _step(OTHER_AGENT.name, "Build the activity")]}
    replies = [
        _calling(SHOW_PLAN_TOOL_NAME, plan, "plan"),
        _calling(STUB_AGENT.name, {"request": "Write the lesson", "step": 1}, "c1"),
        _calling(OTHER_AGENT.name, {"request": "Build the activity", "step": 2}, "c2"),
        AIMessage(""),
    ]
    turn = PlannerSetup(
        [STUB_AGENT, OTHER_AGENT],
        ScriptedChatModel(messages=iter(replies), disable_streaming=True),
        None,
    )

    reply = await _reply(turn, _two_replies(monkeypatch), stream)

    assert reply == "Here is the lesson.\n\nHere is the activity."


@pytest.mark.parametrize("stream", [False, True], ids=["non_streaming", "streaming"])
async def test_a_rejected_plan_never_shows(stream: bool, monkeypatch: pytest.MonkeyPatch) -> None:
    provider = _provider(ScriptedChatModel(messages=iter([])), monkeypatch)
    planner = _planner_replying(
        _calling(SHOW_PLAN_TOOL_NAME, {"steps": [_step(STUB_AGENT.name, "Write the lesson")]}), AIMessage("What for?")
    )

    assert await _reply(planner, provider, stream) == "What for?"


# The plan the planner of these turns makes: the stub agent writes, then the other agent builds.
WRITE_THEN_BUILD = (PlannedStep(STUB_AGENT.name, "Write the lesson"), PlannedStep(OTHER_AGENT.name, "Build it"))


def _planned_turn(*then: AIMessage, existing_plan: ExistingPlan | None = None) -> PlannerSetup:
    """A turn with the stub and other agents whose planner replies ``then``, carrying on ``existing_plan`` if given."""
    return PlannerSetup(
        [STUB_AGENT, OTHER_AGENT],
        ScriptedChatModel(messages=iter([*then, AIMessage("")]), disable_streaming=True),
        existing_plan,
    )


def _plan_call() -> AIMessage:
    steps = [_step(step.agent, step.task) for step in WRITE_THEN_BUILD]
    return _calling(SHOW_PLAN_TOOL_NAME, {"steps": steps}, "plan")


async def test_a_turn_that_stops_partway_through_its_plan_saves_it(monkeypatch: pytest.MonkeyPatch) -> None:
    provider = _provider(ScriptedChatModel(messages=iter([AIMessage("Who are your learners?")])), monkeypatch)
    turn = _planned_turn(_plan_call(), _calling(STUB_AGENT.name, {"request": "Write the lesson", "step": 1}, "c1"))

    response = await complete_turn(TURN, [], provider, 50, planner_setup=turn)

    assert response["metadata"]["plan"] == asdict(ExistingPlan(WRITE_THEN_BUILD, current_step=1))


async def test_a_turn_that_finishes_an_existing_plan_saves_none(monkeypatch: pytest.MonkeyPatch) -> None:
    provider = _provider(ScriptedChatModel(messages=iter([AIMessage("Here is the activity.")])), monkeypatch)
    turn = _planned_turn(
        _calling(OTHER_AGENT.name, {"request": "Build it", "step": 2}, "c1"),
        existing_plan=ExistingPlan(WRITE_THEN_BUILD, current_step=1),
    )

    response = await complete_turn(TURN, [], provider, 50, planner_setup=turn)

    assert "plan" not in response["metadata"]
    assert response["metadata"]["agents"] == [OTHER_AGENT.name]


async def test_a_turn_stopped_at_its_limit_leaves_the_plan_waiting_at_the_next_step(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    agents = [STUB_AGENT.name, OTHER_AGENT.name] * 4
    steps = tuple(PlannedStep(agent, f"Part {number}") for number, agent in enumerate(agents, start=1))
    provider = _provider(ScriptedChatModel(messages=repeat(AIMessage("Here it is."))), monkeypatch)
    calls = [
        _calling(agent, {"request": f"Part {number}", "step": number}, f"c{number}")
        for number, agent in enumerate(agents[: MAX_STEPS_PER_TURN + 1], start=1)
    ]

    response = await complete_turn(
        TURN, [], provider, 50, planner_setup=_planned_turn(*calls, existing_plan=ExistingPlan(steps, 1))
    )

    assert response["metadata"]["plan"] == asdict(
        ExistingPlan(steps, current_step=MAX_STEPS_PER_TURN + 1, has_current_step_run=False)
    )
    assert response["content"].endswith("Continue\nStop here\n```")
