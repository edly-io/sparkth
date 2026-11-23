"""How Compose's planner hands a message to its agents, one step after another, answers it itself, or refuses it."""

from itertools import count, repeat
from typing import Any, cast

import pytest
from langchain_core.messages import AIMessage, AnyMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.tools import StructuredTool
from langgraph.graph.state import CompiledStateGraph

from sparkth.core.i18n import locale_context
from sparkth.lib.audit.events import AuditModelInfo
from sparkth.lib.compose.constants import OPERATOR_AGENT_NAME, REFUSAL_TOOL_NAME, SHOW_PLAN_TOOL_NAME
from sparkth.lib.compose.hooks import Agent
from sparkth.lib.testing import AddTranslation, AuditEventsFetcher, ScriptedChatModel
from sparkth.plugins.compose.constants import (
    MAX_PLAN_STEPS,
    MAX_STEPS_PER_TURN,
    OPERATION_RESULT_HEADING,
    OPERATOR_STATUS,
    PLAN_TASK_MAX_CHARS,
    PLANNER_OPERATIONS,
    PLANNER_STEP_REQUEST,
    PLANNER_WITHOUT_OPERATIONS,
    REFUSAL_MESSAGE,
    REJECT_MISSING_STEP_NUMBER,
    REJECT_OTHER_AGENTS_STEP,
    REJECT_PLAN_AFTER_A_STEP,
    REJECT_SECOND_PLAN,
    REJECT_STEP_AFTER_PLAN,
    REJECT_STEP_NOT_NEXT,
    REJECT_UNPLANNED_OPERATION,
    STEP_RESULT_HEADING,
    STEP_RESULT_TAIL_CHARS,
    STOPPED_EARLY_NOTICE,
)
from sparkth.plugins.compose.enums import OptionsFence, TurnEventType
from sparkth.plugins.compose.llm import build_turn_agent
from sparkth.plugins.compose.planner import (
    AgentGraph,
    ExistingPlan,
    PlannedStep,
    TurnRouting,
    agent_input,
    build_planner,
    render_planner_prompt,
)
from sparkth.plugins.compose.planner.turn_activity import TurnActivity
from sparkth.plugins.compose.planner.types import PlanSnapshot
from sparkth.plugins.compose.prompt import render_system_prompt
from sparkth.plugins.compose.tests.conftest import OTHER_AGENT, STUB_AGENT
from sparkth.plugins.compose.tests.helpers import RecordingChatModel, plan_step, routed, shown_plan

# The paused-plan note's headings and choices.
PLAN_DONE_HEADING = "Done:"
PLAN_LEFT_HEADING = "Still to do:"
PLAN_CONTINUE_CHOICE = "Continue"
PLAN_STOP_CHOICE = "Stop here"
CONTEXT = AuditModelInfo("anthropic", "claude-sonnet-5")
COULD_NOT_FINISH = "Something went wrong and I couldn't finish this. Please send your message again."
CHOICES = "Which level?\n\n```options single\nBeginner\nAdvanced\n```"
SPANISH_REFUSAL = "Solo puedo ayudar con el diseño de cursos."


def _planner_model(*replies: AIMessage) -> RecordingChatModel:
    """The planner's model, answering with ``replies`` in turn and then with nothing, which ends the turn.

    It answers whole: the fake drops tool calls when a streamed planner has it stream.
    """
    return RecordingChatModel(messages=iter([*replies, AIMessage("")]), disable_streaming=True)


def _hand_off(name: str, request: str, call_id: str = "call_1", step: int | None = None) -> dict[str, Any]:
    args: dict[str, Any] = {"request": request} if step is None else {"request": request, "step": step}
    return {"name": name, "args": args, "id": call_id}


def _operation(request: str, call_id: str = "op_1", step: int | None = None) -> dict[str, Any]:
    return _hand_off(OPERATOR_AGENT_NAME, request, call_id, step)


def _plan(*steps: tuple[str, str], call_id: str = "plan") -> dict[str, Any]:
    """A call to the plan tool with ``steps``, each an (agent, task) pair."""
    return {
        "name": SHOW_PLAN_TOOL_NAME,
        "args": {"steps": [{"agent": agent, "task": task} for agent, task in steps]},
        "id": call_id,
    }


def _planned_operations(count: int) -> list[AIMessage]:
    """A plan of ``count`` operations, then a planner reply carrying out each one by its number."""
    plan = _plan(*((OPERATOR_AGENT_NAME, f"Publish module {n}") for n in range(1, count + 1)))
    return [
        AIMessage("", tool_calls=[plan]),
        *(
            AIMessage("", tool_calls=[_operation(f"Publish module {n}", f"op_{n}", step=n)])
            for n in range(1, count + 1)
        ),
    ]


def _rejected(messages: list[AnyMessage], name: str) -> list[str]:
    """What the planner was told about each of its calls to ``name`` that was rejected."""
    return [m.text for m in messages if isinstance(m, ToolMessage) and m.name == name and m.status == "error"]


def _step(reply: str) -> str:
    """An agent's ``reply`` as the planner and later steps read it."""
    return f"{STEP_RESULT_HEADING}\n{reply}"


def _operated(result: str) -> str:
    """An operation's ``result`` as the planner and later steps read it."""
    return f"{OPERATION_RESULT_HEADING}\n{result}"


def _returned(name: str, reply: str, call_id: str) -> ToolMessage:
    """The result of the step ``name`` that replied ``reply``, as the planner's conversation holds it."""
    heading = OPERATION_RESULT_HEADING if name == OPERATOR_AGENT_NAME else STEP_RESULT_HEADING
    return ToolMessage(f"{heading}\n{reply}", artifact=reply, tool_call_id=call_id, name=name)


def _agent_graph(agent: Agent, model: ScriptedChatModel, prompt: str = "Agent prompt.") -> AgentGraph:
    return AgentGraph(agent, build_turn_agent(model, [], prompt, 50, name=agent.name))


def _operator(model: ScriptedChatModel) -> CompiledStateGraph[Any, AuditModelInfo, Any, Any]:
    return build_turn_agent(model, [], "Operator prompt.", 50, name=OPERATOR_AGENT_NAME)


async def _run(
    planner_model: ScriptedChatModel,
    *agents: AgentGraph,
    operator: CompiledStateGraph[Any, AuditModelInfo, Any, Any] | None = None,
    existing_plan: ExistingPlan | None = None,
    reported: list[dict[str, Any]] | None = None,
) -> list[AnyMessage]:
    """Stream the planner the way a turn does, starting each step and tool call it reports, and return its
    messages. What it reports on the way is added to ``reported``."""
    planner = build_planner(planner_model, list(agents), operator=operator, existing_plan=existing_plan)
    messages: list[AnyMessage] = []
    stream = planner.astream(
        {"messages": [HumanMessage("Design a course on photosynthesis.")]},
        context=CONTEXT,
        stream_mode=["custom", "values"],
        subgraphs=True,
    )
    async for namespace, mode, chunk in stream:
        if mode == "custom":
            go = cast(dict[str, Any], chunk).pop("go", None)
            if go is not None:
                go.set()
            if reported is not None:
                reported.append(cast(dict[str, Any], chunk))
        elif not namespace:
            messages = cast(dict[str, Any], chunk)["messages"]
    return messages


def _numbered(text: str) -> list[str]:
    """The lines of ``text`` that are items of a numbered list."""
    return [line for line in text.splitlines() if line[:1].isdigit()]


def _plan_steps(reported: list[dict[str, Any]]) -> list[tuple[int, bool]]:
    """Each step of a plan the planner reported, as its number and whether it had run."""
    return [(event["number"], event["ran"]) for event in reported if event["type"] == TurnEventType.PLAN_STEP]


def _step_results(messages: list[AnyMessage]) -> list[str]:
    """What each step that ran returned to the planner, in order."""
    return [
        m.text for m in messages if isinstance(m, ToolMessage) and m.status != "error" and m.name != SHOW_PLAN_TOOL_NAME
    ]


class TestAgentInput:
    def test_it_drops_the_planners_hand_offs_and_ends_with_the_request(self) -> None:
        history: list[AnyMessage] = [
            HumanMessage("Earlier question"),
            AIMessage("Earlier answer"),
            HumanMessage("Design a course"),
            AIMessage("Passing this on.", tool_calls=[_hand_off("stub", "Design a course on photosynthesis")]),
        ]

        assert agent_input(history, "Design a course on photosynthesis") == [
            HumanMessage("Earlier question"),
            AIMessage("Earlier answer"),
            HumanMessage("Design a course"),
            HumanMessage("Design a course on photosynthesis"),
        ]

    def test_it_keeps_what_an_operation_returned(self) -> None:
        history: list[AnyMessage] = [
            HumanMessage("Redesign my Biology course"),
            AIMessage("", tool_calls=[_operation("Retrieve the Biology course")]),
            _returned(OPERATOR_AGENT_NAME, "Biology 101: cells, genetics.", "op_1"),
        ]

        assert agent_input(history, "Redesign Biology 101") == [
            HumanMessage("Redesign my Biology course"),
            AIMessage(_operated("Biology 101: cells, genetics.")),
            HumanMessage("Redesign Biology 101"),
        ]

    def test_it_keeps_the_whole_of_what_an_earlier_agent_wrote(self) -> None:
        lesson = "Here is the lesson. " * STEP_RESULT_TAIL_CHARS
        history: list[AnyMessage] = [
            HumanMessage("A lesson and an activity on photosynthesis"),
            AIMessage("", tool_calls=[_hand_off(STUB_AGENT.name, "Write the lesson")]),
            ToolMessage("The end of the lesson.", artifact=lesson, tool_call_id="call_1", name=STUB_AGENT.name),
        ]

        assert agent_input(history, "Build a sorting activity for the lesson") == [
            HumanMessage("A lesson and an activity on photosynthesis"),
            AIMessage(_step(lesson)),
            HumanMessage("Build a sorting activity for the lesson"),
        ]

    def test_it_joins_one_steps_result_to_the_next_with_a_blank_line(self) -> None:
        history: list[AnyMessage] = [
            HumanMessage("Redesign Biology 101 and add an activity"),
            AIMessage("", tool_calls=[_operation("Retrieve Biology 101")]),
            _returned(OPERATOR_AGENT_NAME, "Biology 101: cells.", "op_1"),
            AIMessage("", tool_calls=[_hand_off(STUB_AGENT.name, "Redesign it")]),
            _returned(STUB_AGENT.name, "Here is the redesign.", "call_1"),
            AIMessage("", tool_calls=[_hand_off(OTHER_AGENT.name, "Add an activity", "call_2")]),
            ToolMessage("", artifact="", tool_call_id="call_2", name=OTHER_AGENT.name),
        ]

        assert agent_input(history, "Publish it") == [
            HumanMessage("Redesign Biology 101 and add an activity"),
            AIMessage(f"{_operated('Biology 101: cells.')}\n\n{_step('Here is the redesign.')}"),
            HumanMessage("Publish it"),
        ]

    def test_it_drops_the_plan(self) -> None:
        history: list[AnyMessage] = [
            HumanMessage("A lesson and an activity"),
            AIMessage("", tool_calls=[_plan((STUB_AGENT.name, "Write the lesson"), (OTHER_AGENT.name, "Build it"))]),
            ToolMessage(
                "1. Write the lesson\n2. Build it",
                artifact=[{"agent": STUB_AGENT.name, "task": "Write the lesson"}],
                tool_call_id="plan",
                name=SHOW_PLAN_TOOL_NAME,
            ),
        ]

        assert agent_input(history, "Write the lesson") == [
            HumanMessage("A lesson and an activity"),
            HumanMessage("Write the lesson"),
        ]

    def test_it_drops_a_refusal_and_a_call_its_tool_rejected(self) -> None:
        history: list[AnyMessage] = [
            HumanMessage("Publish my course"),
            AIMessage("", tool_calls=[{"name": OPERATOR_AGENT_NAME, "args": {}, "id": "op_1"}]),
            ToolMessage("1 validation error", tool_call_id="op_1", name=OPERATOR_AGENT_NAME, status="error"),
            AIMessage("", tool_calls=[{"name": REFUSAL_TOOL_NAME, "args": {}, "id": "c1"}]),
            ToolMessage("I can only help with courses.", tool_call_id="c1", name=REFUSAL_TOOL_NAME),
        ]

        assert agent_input(history, "Publish Biology 101") == [
            HumanMessage("Publish my course"),
            HumanMessage("Publish Biology 101"),
        ]


class TestHandOff:
    async def test_the_agents_reply_goes_back_to_the_planner_marked_as_data(self) -> None:
        planner_model = _planner_model(AIMessage("", tool_calls=[_hand_off(STUB_AGENT.name, "An outline")]))
        agent_model = ScriptedChatModel(messages=iter([AIMessage("Here is the outline.")]))

        messages = await _run(planner_model, _agent_graph(STUB_AGENT, agent_model))

        assert _step_results(messages) == [_step("Here is the outline.")]
        assert planner_model.seen[1][-1].text == _step("Here is the outline.")

    async def test_the_planner_reads_only_the_end_of_a_long_reply(self) -> None:
        lesson = "".join(str(n % 10) for n in range(STEP_RESULT_TAIL_CHARS * 3))
        planner_model = _planner_model(AIMessage("", tool_calls=[_hand_off(STUB_AGENT.name, "A lesson")]))
        agent_model = ScriptedChatModel(messages=iter([AIMessage(lesson)]))

        await _run(planner_model, _agent_graph(STUB_AGENT, agent_model))

        assert planner_model.seen[1][-1].text == _step(f"…{lesson[-STEP_RESULT_TAIL_CHARS:]}")

    async def test_the_agent_reads_its_own_prompt_the_conversation_and_the_request(self) -> None:
        planner_model = _planner_model(AIMessage("", tool_calls=[_hand_off(STUB_AGENT.name, "An outline")]))
        agent_model = RecordingChatModel(messages=iter([AIMessage("Here is the outline.")]))

        await _run(planner_model, _agent_graph(STUB_AGENT, agent_model, prompt="Stub agent prompt."))

        assert [(type(m), m.text) for m in agent_model.seen[0]] == [
            (SystemMessage, "Stub agent prompt."),
            (HumanMessage, "Design a course on photosynthesis."),
            (HumanMessage, "An outline"),
        ]

    async def test_only_the_first_hand_off_of_a_reply_runs(self) -> None:
        calls = [_hand_off(STUB_AGENT.name, "An outline"), _hand_off(OTHER_AGENT.name, "A quiz", "call_2")]
        planner_model = _planner_model(AIMessage("", tool_calls=calls))
        stub_model = ScriptedChatModel(messages=iter([AIMessage("Here is the outline.")]))
        other_model = RecordingChatModel(messages=iter([AIMessage("Here is the quiz.")]))

        messages = await _run(
            planner_model, _agent_graph(STUB_AGENT, stub_model), _agent_graph(OTHER_AGENT, other_model)
        )

        assert _step_results(messages) == [_step("Here is the outline.")]
        assert other_model.seen == []

    async def test_a_hand_off_is_not_audited(self, audit_events: AuditEventsFetcher) -> None:
        planner_model = _planner_model(AIMessage("", tool_calls=[_hand_off(STUB_AGENT.name, "An outline")]))
        agent_model = ScriptedChatModel(messages=iter([AIMessage("Here is the outline.")]))

        await _run(planner_model, _agent_graph(STUB_AGENT, agent_model))

        assert await audit_events() == []


class TestSeveralSteps:
    async def test_each_step_runs_in_order(self) -> None:
        planner_model = _planner_model(
            AIMessage(
                "",
                tool_calls=[
                    _plan(
                        (STUB_AGENT.name, "Write the lesson"),
                        (OTHER_AGENT.name, "Build the activity"),
                        (OPERATOR_AGENT_NAME, "Publish both"),
                    )
                ],
            ),
            AIMessage("", tool_calls=[_hand_off(STUB_AGENT.name, "Write the lesson", step=1)]),
            AIMessage("", tool_calls=[_hand_off(OTHER_AGENT.name, "Build the activity", "call_2", step=2)]),
            AIMessage("", tool_calls=[_operation("Publish both", step=3)]),
            AIMessage("Both are published."),
        )
        stub_model = ScriptedChatModel(messages=iter([AIMessage("Here is the lesson.")]))
        other_model = ScriptedChatModel(messages=iter([AIMessage("Here is the activity.")]))
        operator_model = ScriptedChatModel(messages=iter([AIMessage("Published 2 items.")]))

        messages = await _run(
            planner_model,
            _agent_graph(STUB_AGENT, stub_model),
            _agent_graph(OTHER_AGENT, other_model),
            operator=_operator(operator_model),
        )

        assert _step_results(messages) == [
            _step("Here is the lesson."),
            _step("Here is the activity."),
            _operated("Published 2 items."),
        ]
        assert messages[-1].text == "Both are published."

    async def test_a_later_step_reads_the_whole_of_what_an_earlier_one_wrote(self) -> None:
        lesson = "".join(str(n % 10) for n in range(STEP_RESULT_TAIL_CHARS * 3))
        planner_model = _planner_model(
            AIMessage("", tool_calls=[_hand_off(STUB_AGENT.name, "Write the lesson")]),
            AIMessage("", tool_calls=[_hand_off(OTHER_AGENT.name, "Build the activity", "call_2")]),
        )
        stub_model = ScriptedChatModel(messages=iter([AIMessage(lesson)]))
        other_model = RecordingChatModel(messages=iter([AIMessage("Here is the activity.")]))

        await _run(planner_model, _agent_graph(STUB_AGENT, stub_model), _agent_graph(OTHER_AGENT, other_model))

        assert [(type(m), m.text) for m in other_model.seen[0]] == [
            (SystemMessage, "Agent prompt."),
            (HumanMessage, "Design a course on photosynthesis."),
            (AIMessage, _step(lesson)),
            (HumanMessage, "Build the activity"),
        ]

    async def test_the_agent_that_has_just_answered_is_not_run_again(self) -> None:
        """A planner that hands the same work over again would have the author read the answer twice."""
        planner_model = _planner_model(
            AIMessage("", tool_calls=[_hand_off(STUB_AGENT.name, "An outline")]),
            AIMessage("", tool_calls=[_hand_off(STUB_AGENT.name, "An outline", "call_2")]),
        )
        agent_model = RecordingChatModel(messages=repeat(AIMessage("Here is the outline.")))

        messages = await _run(planner_model, _agent_graph(STUB_AGENT, agent_model))

        assert len(agent_model.seen) == 1
        assert not cast(AIMessage, messages[-1]).tool_calls

    @pytest.mark.parametrize(
        "reply",
        [CHOICES, "Pick any.\n\n```options\nQuiz\nGame\n```\n", "Which level?\n\n```options single\nBeginner"],
        ids=["one_answer", "several_answers", "block_left_open"],
    )
    async def test_the_turn_ends_when_an_agent_offered_the_author_choices(self, reply: str) -> None:
        """The author answers the agent's question before anything else happens: no step runs and
        the planner is not asked again."""
        planner_model = _planner_model(
            AIMessage("", tool_calls=[_hand_off(STUB_AGENT.name, "An outline")]),
            AIMessage("", tool_calls=[_hand_off(OTHER_AGENT.name, "An activity", "call_2")]),
        )
        other_model = RecordingChatModel(messages=repeat(AIMessage("Here is the activity.")))

        await _run(
            planner_model,
            _agent_graph(STUB_AGENT, ScriptedChatModel(messages=iter([AIMessage(reply)]))),
            _agent_graph(OTHER_AGENT, other_model),
        )

        assert other_model.seen == []
        assert len(planner_model.seen) == 1

    async def test_choices_before_the_end_of_an_agents_reply_do_not_hold_the_next_step(self) -> None:
        planner_model = _planner_model(
            AIMessage("", tool_calls=[_hand_off(STUB_AGENT.name, "An outline")]),
            AIMessage("", tool_calls=[_hand_off(OTHER_AGENT.name, "An activity", "call_2")]),
        )
        other_model = RecordingChatModel(messages=repeat(AIMessage("Here is the activity.")))

        await _run(
            planner_model,
            _agent_graph(
                STUB_AGENT, ScriptedChatModel(messages=iter([AIMessage(f"{CHOICES}\n\nI went with Beginner.")]))
            ),
            _agent_graph(OTHER_AGENT, other_model),
        )

        assert len(other_model.seen) == 1

    async def test_an_operation_runs_after_one_whose_result_ends_with_choices(self) -> None:
        """The author never reads the operator's text, so it has asked them nothing."""
        operator_model = RecordingChatModel(messages=repeat(AIMessage(CHOICES)))

        await _run(
            _planner_model(*_planned_operations(2), AIMessage("Both are published.")),
            operator=_operator(operator_model),
        )

        assert len(operator_model.seen) == 2

    async def test_a_planned_step_does_not_run_after_an_agent_offered_the_author_choices(self) -> None:
        plan = _plan((STUB_AGENT.name, "Write the lesson"), (OTHER_AGENT.name, "Build the activity"))
        planner_model = _planner_model(
            AIMessage("", tool_calls=[plan]),
            AIMessage("", tool_calls=[_hand_off(STUB_AGENT.name, "Write the lesson", step=1)]),
            AIMessage("", tool_calls=[_hand_off(OTHER_AGENT.name, "Build the activity", "call_2", step=2)]),
        )
        other_model = RecordingChatModel(messages=repeat(AIMessage("Here is the activity.")))

        await _run(
            planner_model,
            _agent_graph(STUB_AGENT, ScriptedChatModel(messages=iter([AIMessage(CHOICES)]))),
            _agent_graph(OTHER_AGENT, other_model),
        )

        assert other_model.seen == []

    async def test_two_operations_in_a_row_run_as_steps_of_a_plan(self) -> None:
        operator_model = RecordingChatModel(messages=repeat(AIMessage("Done.")))

        messages = await _run(
            _planner_model(*_planned_operations(2), AIMessage("Both are published.")),
            operator=_operator(operator_model),
        )

        assert len(operator_model.seen) == 2
        assert messages[-1].text == "Both are published."


class TestAStepsStatus:
    async def test_each_step_is_announced_with_what_its_doer_says_it_is_doing(self) -> None:
        planner_model = _planner_model(
            AIMessage("", tool_calls=[_operation("Retrieve the course")]),
            AIMessage("", tool_calls=[_hand_off(STUB_AGENT.name, "Redesign it")]),
        )
        reported: list[dict[str, Any]] = []

        await _run(
            planner_model,
            _agent_graph(STUB_AGENT, ScriptedChatModel(messages=iter([AIMessage("Here is the redesign.")]))),
            operator=_operator(ScriptedChatModel(messages=iter([AIMessage("Biology 101.")]))),
            reported=reported,
        )

        announced = [event["status"] for event in reported if event["type"] == TurnEventType.ROUTED]
        assert announced == [OPERATOR_STATUS, STUB_AGENT.status]


class TestThePlan:
    async def test_the_plan_lists_each_task_for_the_author(self) -> None:
        plan = _plan((STUB_AGENT.name, "Write the lesson"), (OTHER_AGENT.name, "Build the activity"))
        planner_model = _planner_model(AIMessage("", tool_calls=[plan]))
        agents = [_agent_graph(agent, ScriptedChatModel(messages=iter([]))) for agent in (STUB_AGENT, OTHER_AGENT)]

        messages = await _run(planner_model, *agents)

        listed = [m for m in messages if isinstance(m, ToolMessage) and m.name == SHOW_PLAN_TOOL_NAME]
        assert [m.text for m in listed] == ["1. Write the lesson\n2. Build the activity"]

    async def test_an_agent_doing_a_planned_step_is_told_it_is_that_step_alone(self) -> None:
        """So it leaves the plan's other steps to their agents and doesn't end its step with choices."""
        plan = _plan((STUB_AGENT.name, "Write the lesson"), (OTHER_AGENT.name, "Build the activity"))
        planner_model = _planner_model(
            AIMessage("", tool_calls=[plan]),
            AIMessage("", tool_calls=[_hand_off(STUB_AGENT.name, "Write a lesson on photosynthesis", step=1)]),
        )
        stub_model = RecordingChatModel(messages=iter([AIMessage("Here is the lesson.")]))
        other = _agent_graph(OTHER_AGENT, ScriptedChatModel(messages=iter([])))

        await _run(planner_model, _agent_graph(STUB_AGENT, stub_model), other)

        expected = PLANNER_STEP_REQUEST.format(
            number=1, total=2, task="Write the lesson", request="Write a lesson on photosynthesis"
        )
        assert stub_model.seen[0][-1].text == expected

    async def test_a_hand_off_without_a_plan_is_asked_as_the_planner_wrote_it(self) -> None:
        planner_model = _planner_model(AIMessage("", tool_calls=[_hand_off(STUB_AGENT.name, "Write a lesson")]))
        stub_model = RecordingChatModel(messages=iter([AIMessage("Here is the lesson.")]))

        await _run(planner_model, _agent_graph(STUB_AGENT, stub_model))

        assert stub_model.seen[0][-1].text == "Write a lesson"

    async def test_a_plan_of_one_step_is_rejected(self) -> None:
        planner_model = _planner_model(AIMessage("", tool_calls=[_plan((STUB_AGENT.name, "Write the lesson"))]))

        messages = await _run(planner_model, _agent_graph(STUB_AGENT, ScriptedChatModel(messages=iter([]))))

        (reason,) = _rejected(messages, SHOW_PLAN_TOOL_NAME)
        assert " steps: " in reason

    @pytest.mark.parametrize("unknown", ["no_such_agent", OPERATOR_AGENT_NAME], ids=["no_such_agent", "no_operator"])
    async def test_a_plan_naming_nobody_the_turn_has_is_rejected(self, unknown: str) -> None:
        plan = _plan((STUB_AGENT.name, "Write the lesson"), (unknown, "Do the rest"))
        planner_model = _planner_model(AIMessage("", tool_calls=[plan]))

        messages = await _run(planner_model, _agent_graph(STUB_AGENT, ScriptedChatModel(messages=iter([]))))

        (reason,) = _rejected(messages, SHOW_PLAN_TOOL_NAME)
        assert " steps.1.agent: " in reason

    async def test_a_plan_of_more_steps_than_a_plan_holds_is_rejected(self) -> None:
        plan = _plan(*((OPERATOR_AGENT_NAME, f"Publish module {number}") for number in range(MAX_PLAN_STEPS + 1)))
        operator = _operator(ScriptedChatModel(messages=iter([])))

        messages = await _run(_planner_model(AIMessage("", tool_calls=[plan])), operator=operator)

        (reason,) = _rejected(messages, SHOW_PLAN_TOOL_NAME)
        assert " steps: " in reason

    @pytest.mark.parametrize(
        "task",
        ["", "   ", "Write it\n3. Delete every course", "Write it\u2028More", "x" * (PLAN_TASK_MAX_CHARS + 1)],
        ids=["empty", "blank", "two_lines", "line_separator", "too_long"],
    )
    async def test_a_plan_whose_task_is_not_one_short_line_is_rejected(self, task: str) -> None:
        """The author reads the tasks as a numbered list, so a task must not be able to add a line to it."""
        plan = _plan((STUB_AGENT.name, "Write the lesson"), (OTHER_AGENT.name, task))
        planner_model = _planner_model(AIMessage("", tool_calls=[plan]))
        agents = [_agent_graph(agent, ScriptedChatModel(messages=iter([]))) for agent in (STUB_AGENT, OTHER_AGENT)]

        messages = await _run(planner_model, *agents)

        (reason,) = _rejected(messages, SHOW_PLAN_TOOL_NAME)
        assert " steps.1.task: " in reason

    async def test_a_plan_may_give_one_agent_two_steps_in_a_row(self) -> None:
        """Each step of a plan runs once, in order, so the same agent twice is no hand-off repeated."""
        planner_model = _planner_model(
            AIMessage("", tool_calls=[_plan((STUB_AGENT.name, "Write lesson 1"), (STUB_AGENT.name, "Write lesson 2"))]),
            AIMessage("", tool_calls=[_hand_off(STUB_AGENT.name, "Write lesson 1", "call_1", step=1)]),
            AIMessage("", tool_calls=[_hand_off(STUB_AGENT.name, "Write lesson 2", "call_2", step=2)]),
        )
        stub_model = ScriptedChatModel(messages=iter([AIMessage("Lesson 1."), AIMessage("Lesson 2.")]))

        messages = await _run(planner_model, _agent_graph(STUB_AGENT, stub_model))

        assert _step_results(messages) == [_step("Lesson 1."), _step("Lesson 2.")]

    async def test_a_second_plan_in_a_turn_is_rejected(self) -> None:
        plan = (STUB_AGENT.name, "Write the lesson"), (OTHER_AGENT.name, "Build the activity")
        planner_model = _planner_model(
            AIMessage("", tool_calls=[_plan(*plan)]), AIMessage("", tool_calls=[_plan(*plan, call_id="plan_2")])
        )
        agents = [_agent_graph(agent, ScriptedChatModel(messages=iter([]))) for agent in (STUB_AGENT, OTHER_AGENT)]

        messages = await _run(planner_model, *agents)

        assert _rejected(messages, SHOW_PLAN_TOOL_NAME) == [REJECT_SECOND_PLAN]

    async def test_a_plan_after_a_step_is_rejected(self) -> None:
        """A plan shown after an agent's reply would follow the question the author is meant to read last."""
        plan = (STUB_AGENT.name, "Write the lesson"), (OTHER_AGENT.name, "Build the activity")
        planner_model = _planner_model(
            AIMessage("", tool_calls=[_hand_off(STUB_AGENT.name, "Write the lesson")]),
            AIMessage("", tool_calls=[_plan(*plan)]),
        )
        stub_model = ScriptedChatModel(messages=iter([AIMessage("Here is the lesson.")]))
        other = _agent_graph(OTHER_AGENT, ScriptedChatModel(messages=iter([])))

        messages = await _run(planner_model, _agent_graph(STUB_AGENT, stub_model), other)

        assert _rejected(messages, SHOW_PLAN_TOOL_NAME) == [REJECT_PLAN_AFTER_A_STEP]

    async def test_a_plan_is_no_step(self) -> None:
        operator_model = RecordingChatModel(messages=repeat(AIMessage("Published.")))

        messages = await _run(
            _planner_model(*_planned_operations(MAX_STEPS_PER_TURN), AIMessage("All published.")),
            operator=_operator(operator_model),
        )

        assert len(operator_model.seen) == MAX_STEPS_PER_TURN
        assert messages[-1].text == "All published."

    async def test_a_call_without_its_step_number_is_rejected_and_never_runs(self) -> None:
        """Otherwise a step could run unnumbered and then again under its number."""
        planner_model = _planner_model(
            AIMessage("", tool_calls=[_plan((OPERATOR_AGENT_NAME, "Retrieve it"), (STUB_AGENT.name, "Redesign it"))]),
            AIMessage("", tool_calls=[_operation("Retrieve it")]),
        )
        operator_model = RecordingChatModel(messages=repeat(AIMessage("Biology 101.")))

        messages = await _run(
            planner_model,
            _agent_graph(STUB_AGENT, ScriptedChatModel(messages=iter([]))),
            operator=_operator(operator_model),
        )

        assert _rejected(messages, OPERATOR_AGENT_NAME) == [REJECT_MISSING_STEP_NUMBER]
        assert operator_model.seen == []

    async def test_a_step_number_that_is_no_whole_number_is_rejected_and_the_call_never_runs(self) -> None:
        planner_model = _planner_model(
            AIMessage("", tool_calls=[_plan((STUB_AGENT.name, "Write it"), (OPERATOR_AGENT_NAME, "Publish it"))]),
            AIMessage("", tool_calls=[_hand_off(STUB_AGENT.name, "Write it", step=1)]),
            AIMessage(
                "",
                tool_calls=[
                    {"name": OPERATOR_AGENT_NAME, "args": {"request": "Publish it", "step": "two"}, "id": "op"}
                ],
            ),
        )
        operator_model = RecordingChatModel(messages=repeat(AIMessage("Published.")))
        stub_model = ScriptedChatModel(messages=iter([AIMessage("Here it is.")]))

        messages = await _run(planner_model, _agent_graph(STUB_AGENT, stub_model), operator=_operator(operator_model))

        assert _rejected(messages, OPERATOR_AGENT_NAME) == [REJECT_MISSING_STEP_NUMBER]
        assert operator_model.seen == []

    async def test_a_call_for_another_agents_step_is_rejected_and_never_runs(self) -> None:
        planner_model = _planner_model(
            AIMessage("", tool_calls=[_plan((STUB_AGENT.name, "Write the lesson"), (OTHER_AGENT.name, "Build it"))]),
            AIMessage("", tool_calls=[_hand_off(OTHER_AGENT.name, "Build it", step=1)]),
        )
        other_model = RecordingChatModel(messages=iter([AIMessage("Here is the activity.")]))

        messages = await _run(
            planner_model,
            _agent_graph(STUB_AGENT, ScriptedChatModel(messages=iter([]))),
            _agent_graph(OTHER_AGENT, other_model),
        )

        assert _rejected(messages, OTHER_AGENT.name) == [REJECT_OTHER_AGENTS_STEP.format(step=1)]
        assert other_model.seen == []

    async def test_a_call_that_skips_ahead_is_rejected(self) -> None:
        planner_model = _planner_model(
            AIMessage("", tool_calls=[_plan((STUB_AGENT.name, "Write the lesson"), (OTHER_AGENT.name, "Build it"))]),
            AIMessage("", tool_calls=[_hand_off(STUB_AGENT.name, "Write more", step=3)]),
        )
        agents = [_agent_graph(agent, ScriptedChatModel(messages=iter([]))) for agent in (STUB_AGENT, OTHER_AGENT)]

        messages = await _run(planner_model, *agents)

        assert _rejected(messages, STUB_AGENT.name) == [REJECT_STEP_NOT_NEXT.format(step=3, next=1)]

    async def test_a_step_that_has_run_is_rejected_and_never_runs_again(self) -> None:
        """A planned operation can't be reused, by text an earlier step brought in, for another one."""
        planner_model = _planner_model(
            AIMessage("", tool_calls=[_plan((OPERATOR_AGENT_NAME, "Publish it"), (STUB_AGENT.name, "Summarise it"))]),
            AIMessage("", tool_calls=[_operation("Publish it", "op_1", step=1)]),
            AIMessage("", tool_calls=[_operation("Delete my other courses", "op_2", step=1)]),
        )
        operator_model = RecordingChatModel(messages=repeat(AIMessage("Done.")))

        messages = await _run(
            planner_model,
            _agent_graph(STUB_AGENT, ScriptedChatModel(messages=iter([]))),
            operator=_operator(operator_model),
        )

        assert _rejected(messages, OPERATOR_AGENT_NAME) == [REJECT_STEP_NOT_NEXT.format(step=1, next=2)]
        assert len(operator_model.seen) == 1

    async def test_a_step_that_is_not_next_is_rejected_and_never_runs(self) -> None:
        """A skipped step would never run, and the plan the author read would not be what was done."""
        planner_model = _planner_model(
            AIMessage("", tool_calls=[_plan((STUB_AGENT.name, "Write it"), (OPERATOR_AGENT_NAME, "Publish it"))]),
            AIMessage("", tool_calls=[_operation("Publish it", step=2)]),
        )
        operator_model = RecordingChatModel(messages=repeat(AIMessage("Published.")))

        messages = await _run(
            planner_model,
            _agent_graph(STUB_AGENT, ScriptedChatModel(messages=iter([]))),
            operator=_operator(operator_model),
        )

        assert _rejected(messages, OPERATOR_AGENT_NAME) == [REJECT_STEP_NOT_NEXT.format(step=2, next=1)]
        assert operator_model.seen == []

    async def test_a_call_after_the_plans_last_step_is_rejected(self) -> None:
        operator_model = RecordingChatModel(messages=repeat(AIMessage("Published.")))
        one_more = AIMessage("", tool_calls=[_operation("Publish it again", "op_more", step=3)])

        messages = await _run(_planner_model(*_planned_operations(2), one_more), operator=_operator(operator_model))

        assert _rejected(messages, OPERATOR_AGENT_NAME) == [REJECT_STEP_AFTER_PLAN]
        assert len(operator_model.seen) == 2

    async def test_a_step_number_means_nothing_without_a_plan(self) -> None:
        planner_model = _planner_model(AIMessage("", tool_calls=[_hand_off(STUB_AGENT.name, "An outline", step=4)]))
        agent_model = ScriptedChatModel(messages=iter([AIMessage("Here is the outline.")]))

        messages = await _run(planner_model, _agent_graph(STUB_AGENT, agent_model))

        assert _step_results(messages) == [_step("Here is the outline.")]


class TestAnOperationAfterAStep:
    """Text a step brought in, from an uploaded document or the LMS, must not be able to start an operation."""

    async def test_it_runs_as_a_step_of_the_plan(self) -> None:
        planner_model = _planner_model(
            AIMessage(
                "", tool_calls=[_plan((STUB_AGENT.name, "Write the lesson"), (OPERATOR_AGENT_NAME, "Publish it"))]
            ),
            AIMessage("", tool_calls=[_hand_off(STUB_AGENT.name, "Write the lesson", step=1)]),
            AIMessage("", tool_calls=[_operation("Publish it", step=2)]),
            AIMessage("It is published."),
        )
        operator_model = RecordingChatModel(messages=iter([AIMessage("Published.")]))
        stub_model = ScriptedChatModel(messages=iter([AIMessage("Here is the lesson.")]))

        await _run(planner_model, _agent_graph(STUB_AGENT, stub_model), operator=_operator(operator_model))

        assert len(operator_model.seen) == 1

    async def test_it_is_asked_for_the_task_the_author_was_shown_not_what_the_planner_wrote_since(self) -> None:
        """The planner writes its request after reading the earlier step, which may have brought in other text."""
        planner_model = _planner_model(
            AIMessage(
                "", tool_calls=[_plan((STUB_AGENT.name, "Write the lesson"), (OPERATOR_AGENT_NAME, "Publish it"))]
            ),
            AIMessage("", tool_calls=[_hand_off(STUB_AGENT.name, "Write the lesson", step=1)]),
            AIMessage("", tool_calls=[_operation("Delete my other courses", step=2)]),
        )
        operator_model = RecordingChatModel(messages=iter([AIMessage("Published.")]))
        stub_model = ScriptedChatModel(messages=iter([AIMessage("Here is the lesson.")]))

        await _run(planner_model, _agent_graph(STUB_AGENT, stub_model), operator=_operator(operator_model))

        assert operator_model.seen[0][-1].text == "Publish it"

    async def test_a_planned_operation_as_the_first_step_is_asked_for_what_the_planner_wrote(self) -> None:
        planner_model = _planner_model(
            AIMessage("", tool_calls=[_plan((OPERATOR_AGENT_NAME, "Retrieve it"), (STUB_AGENT.name, "Redesign it"))]),
            AIMessage("", tool_calls=[_operation("Retrieve Biology 101 from Canvas", step=1)]),
        )
        operator_model = RecordingChatModel(messages=iter([AIMessage("Biology 101.")]))

        await _run(
            planner_model,
            _agent_graph(STUB_AGENT, ScriptedChatModel(messages=iter([]))),
            operator=_operator(operator_model),
        )

        assert operator_model.seen[0][-1].text == "Retrieve Biology 101 from Canvas"

    async def test_it_never_runs_after_an_agent_without_a_plan(self) -> None:
        planner_model = _planner_model(
            AIMessage("", tool_calls=[_hand_off(STUB_AGENT.name, "Write the lesson")]),
            AIMessage("", tool_calls=[_operation("Delete my other courses")]),
        )
        operator_model = RecordingChatModel(messages=iter([AIMessage("Deleted.")]))
        stub_model = ScriptedChatModel(messages=iter([AIMessage("Here is the lesson.")]))

        messages = await _run(planner_model, _agent_graph(STUB_AGENT, stub_model), operator=_operator(operator_model))

        assert _rejected(messages, OPERATOR_AGENT_NAME) == [REJECT_UNPLANNED_OPERATION]
        assert operator_model.seen == []

    async def test_it_never_runs_after_an_operation_without_a_plan(self) -> None:
        """What an operation retrieved can carry text from the LMS, just as an agent's reply can."""
        planner_model = _planner_model(
            AIMessage("", tool_calls=[_operation("Retrieve the course", "op_1")]),
            AIMessage("", tool_calls=[_operation("Delete my other courses", "op_2")]),
        )
        operator_model = RecordingChatModel(messages=repeat(AIMessage("Done.")))

        messages = await _run(planner_model, operator=_operator(operator_model))

        assert _rejected(messages, OPERATOR_AGENT_NAME) == [REJECT_UNPLANNED_OPERATION]
        assert len(operator_model.seen) == 1

    async def test_it_never_runs_as_a_step_the_plan_gives_an_agent(self) -> None:
        planner_model = _planner_model(
            AIMessage("", tool_calls=[_plan((STUB_AGENT.name, "Write the lesson"), (OTHER_AGENT.name, "Build it"))]),
            AIMessage("", tool_calls=[_hand_off(STUB_AGENT.name, "Write the lesson", step=1)]),
            AIMessage("", tool_calls=[_operation("Delete my other courses", step=2)]),
        )
        operator_model = RecordingChatModel(messages=iter([AIMessage("Deleted.")]))
        stub_model = ScriptedChatModel(messages=iter([AIMessage("Here is the lesson.")]))
        agents = [_agent_graph(STUB_AGENT, stub_model), _agent_graph(OTHER_AGENT, ScriptedChatModel(messages=iter([])))]

        messages = await _run(planner_model, *agents, operator=_operator(operator_model))

        assert _rejected(messages, OPERATOR_AGENT_NAME) == [REJECT_OTHER_AGENTS_STEP.format(step=2)]
        assert operator_model.seen == []

    async def test_a_plan_made_after_the_step_does_not_let_it_run(self) -> None:
        planner_model = _planner_model(
            AIMessage("", tool_calls=[_hand_off(STUB_AGENT.name, "Write the lesson")]),
            AIMessage("", tool_calls=[_plan((STUB_AGENT.name, "Write it"), (OPERATOR_AGENT_NAME, "Delete the rest"))]),
            AIMessage("", tool_calls=[_operation("Delete the rest", step=2)]),
        )
        operator_model = RecordingChatModel(messages=iter([AIMessage("Deleted.")]))
        stub_model = ScriptedChatModel(messages=iter([AIMessage("Here is the lesson.")]))

        messages = await _run(planner_model, _agent_graph(STUB_AGENT, stub_model), operator=_operator(operator_model))

        assert _rejected(messages, SHOW_PLAN_TOOL_NAME) == [REJECT_PLAN_AFTER_A_STEP]
        assert _rejected(messages, OPERATOR_AGENT_NAME) == [REJECT_UNPLANNED_OPERATION]
        assert operator_model.seen == []

    async def test_an_operation_as_the_first_step_needs_no_plan(self) -> None:
        planner_model = _planner_model(
            AIMessage("", tool_calls=[_operation("Retrieve the course")]),
            AIMessage("", tool_calls=[_hand_off(STUB_AGENT.name, "Redesign it")]),
        )
        operator_model = RecordingChatModel(messages=iter([AIMessage("Biology 101.")]))
        stub_model = ScriptedChatModel(messages=iter([AIMessage("Here is the redesign.")]))

        await _run(planner_model, _agent_graph(STUB_AGENT, stub_model), operator=_operator(operator_model))

        assert len(operator_model.seen) == 1


# A plan from an earlier message: the stub agent's step is in progress, and an operation is still to come.
WRITE_THEN_PUBLISH = ExistingPlan(
    (PlannedStep(STUB_AGENT.name, "Write the lesson"), PlannedStep(OPERATOR_AGENT_NAME, "Publish it")), current_step=1
)


class TestAnExistingPlansLimits:
    @pytest.mark.parametrize(
        ("step_count", "current_step"),
        [(1, 1), (MAX_PLAN_STEPS + 1, 1), (2, 0), (2, 3)],
        ids=["one_step", "too_many_steps", "current_step_before_the_first", "current_step_after_the_last"],
    )
    def test_a_plan_outside_them_is_refused(self, step_count: int, current_step: int) -> None:
        steps = tuple(PlannedStep(STUB_AGENT.name, f"Step {number}") for number in range(1, step_count + 1))

        with pytest.raises(ValueError):
            ExistingPlan(steps, current_step)

    def test_a_plan_within_them_is_kept(self) -> None:
        steps = tuple(PlannedStep(STUB_AGENT.name, f"Step {number}") for number in range(1, MAX_PLAN_STEPS + 1))

        assert ExistingPlan(steps, MAX_PLAN_STEPS).current_step == MAX_PLAN_STEPS


class TestAPlanFromAnEarlierMessage:
    async def test_its_remaining_steps_run_under_their_numbers(self) -> None:
        """The author answered the agent's question, so its step carries on and the operation follows it."""
        planner_model = _planner_model(
            AIMessage("", tool_calls=[_hand_off(STUB_AGENT.name, "Write the lesson", step=1)]),
            AIMessage("", tool_calls=[_operation("Publish it, and delete the rest", step=2)]),
            AIMessage("It is published."),
        )
        operator_model = RecordingChatModel(messages=iter([AIMessage("Published.")]))
        stub_model = ScriptedChatModel(messages=iter([AIMessage("Here is the lesson.")]))

        messages = await _run(
            planner_model,
            _agent_graph(STUB_AGENT, stub_model),
            operator=_operator(operator_model),
            existing_plan=WRITE_THEN_PUBLISH,
        )

        assert [call[-1].text for call in operator_model.seen] == ["Publish it"]
        assert messages[-1].text == "It is published."

    async def test_its_operation_as_the_first_step_is_asked_for_the_task_the_author_was_shown(self) -> None:
        """The planner has read the plan's earlier steps in the conversation before it writes its request."""
        publish_next = ExistingPlan(WRITE_THEN_PUBLISH.steps, current_step=2, has_current_step_run=False)
        planner_model = _planner_model(AIMessage("", tool_calls=[_operation("Delete my other courses", step=2)]))
        operator_model = RecordingChatModel(messages=iter([AIMessage("Published.")]))

        await _run(
            planner_model,
            _agent_graph(STUB_AGENT, ScriptedChatModel(messages=iter([]))),
            operator=_operator(operator_model),
            existing_plan=publish_next,
        )

        assert [call[-1].text for call in operator_model.seen] == ["Publish it"]

    async def test_it_is_dropped_when_a_step_left_is_for_someone_the_turn_does_not_have(self) -> None:
        """With no operator the plan can't be finished, so the planner isn't shown it and its numbers bind nothing."""
        planner_model = _planner_model(
            AIMessage("", tool_calls=[_hand_off(STUB_AGENT.name, "Write the lesson", step=1)]),
            AIMessage("", tool_calls=[_hand_off(OTHER_AGENT.name, "Build an activity", "call_2")]),
        )
        stub_model = ScriptedChatModel(messages=iter([AIMessage("Here is the lesson.")]))
        other_model = ScriptedChatModel(messages=iter([AIMessage("Here is the activity.")]))

        messages = await _run(
            planner_model,
            _agent_graph(STUB_AGENT, stub_model),
            _agent_graph(OTHER_AGENT, other_model),
            existing_plan=WRITE_THEN_PUBLISH,
        )

        assert _step_results(messages) == [_step("Here is the lesson."), _step("Here is the activity.")]
        assert "EXISTING PLAN" not in planner_model.seen[0][0].text

    async def test_each_step_is_reported_when_it_starts_and_when_it_has_run(self) -> None:
        planner_model = _planner_model(
            AIMessage("", tool_calls=[_hand_off(STUB_AGENT.name, "Write the lesson", step=1)]),
            AIMessage("", tool_calls=[_operation("Publish it", step=2)]),
        )
        reported: list[dict[str, Any]] = []

        await _run(
            planner_model,
            _agent_graph(STUB_AGENT, ScriptedChatModel(messages=iter([AIMessage("Here is the lesson.")]))),
            operator=_operator(ScriptedChatModel(messages=iter([AIMessage("Published.")]))),
            existing_plan=WRITE_THEN_PUBLISH,
            reported=reported,
        )

        assert _plan_steps(reported) == [(1, False), (1, True), (2, False), (2, True)]

    async def test_a_step_that_fails_is_reported_as_started_only(self) -> None:
        planner_model = _planner_model(AIMessage("", tool_calls=[_hand_off(STUB_AGENT.name, "Write it", step=1)]))
        reported: list[dict[str, Any]] = []

        with pytest.raises(RuntimeError, match="During task with name 'tools'"):
            await _run(
                planner_model,
                _agent_graph(STUB_AGENT, ScriptedChatModel(messages=iter([]))),
                operator=_operator(ScriptedChatModel(messages=iter([]))),
                existing_plan=WRITE_THEN_PUBLISH,
                reported=reported,
            )

        assert _plan_steps(reported) == [(1, False)]

    async def test_a_rejected_call_and_a_step_outside_it_are_not_reported(self) -> None:
        planner_model = _planner_model(
            AIMessage("", tool_calls=[_hand_off(STUB_AGENT.name, "A quiz instead")]),
            AIMessage("", tool_calls=[_operation("Publish it", step=2)]),
        )
        reported: list[dict[str, Any]] = []

        await _run(
            planner_model,
            _agent_graph(STUB_AGENT, ScriptedChatModel(messages=iter([AIMessage("Here is the quiz.")]))),
            operator=_operator(ScriptedChatModel(messages=iter([]))),
            existing_plan=WRITE_THEN_PUBLISH,
            reported=reported,
        )

        assert _plan_steps(reported) == []

    async def test_it_carries_on_at_its_step_in_progress_or_the_next_and_no_further(self) -> None:
        plan = ExistingPlan((*WRITE_THEN_PUBLISH.steps, PlannedStep(STUB_AGENT.name, "Sum up")), current_step=1)
        planner_model = _planner_model(AIMessage("", tool_calls=[_hand_off(STUB_AGENT.name, "Sum up", step=3)]))
        stub_model = RecordingChatModel(messages=iter([AIMessage("In short.")]))

        messages = await _run(
            planner_model,
            _agent_graph(STUB_AGENT, stub_model),
            operator=_operator(ScriptedChatModel(messages=iter([]))),
            existing_plan=plan,
        )

        assert _rejected(messages, STUB_AGENT.name) == [REJECT_STEP_NOT_NEXT.format(step=3, next="1 or 2")]
        assert stub_model.seen == []

    async def test_a_step_that_was_finished_is_rejected(self) -> None:
        finished = ExistingPlan(WRITE_THEN_PUBLISH.steps, current_step=2, has_current_step_run=False)
        planner_model = _planner_model(AIMessage("", tool_calls=[_hand_off(STUB_AGENT.name, "Write it", step=1)]))
        stub_model = RecordingChatModel(messages=iter([AIMessage("Here is the lesson.")]))

        messages = await _run(
            planner_model,
            _agent_graph(STUB_AGENT, stub_model),
            operator=_operator(ScriptedChatModel(messages=iter([]))),
            existing_plan=finished,
        )

        assert _rejected(messages, STUB_AGENT.name) == [REJECT_STEP_NOT_NEXT.format(step=1, next="2")]
        assert stub_model.seen == []

    async def test_a_step_that_never_ran_is_the_only_one_that_may_run_next(self) -> None:
        """A turn that stopped at its limit before the step, or while it ran, leaves that step to run again."""
        never_ran = ExistingPlan(
            (*WRITE_THEN_PUBLISH.steps, PlannedStep(STUB_AGENT.name, "Sum up")),
            current_step=1,
            has_current_step_run=False,
        )
        planner_model = _planner_model(AIMessage("", tool_calls=[_operation("Publish it", step=2)]))
        operator_model = RecordingChatModel(messages=iter([AIMessage("Published.")]))

        messages = await _run(
            planner_model,
            _agent_graph(STUB_AGENT, ScriptedChatModel(messages=iter([]))),
            operator=_operator(operator_model),
            existing_plan=never_ran,
        )

        assert _rejected(messages, OPERATOR_AGENT_NAME) == [REJECT_STEP_NOT_NEXT.format(step=2, next="1")]
        assert operator_model.seen == []

    async def test_an_operation_that_ran_is_not_run_again(self) -> None:
        """An operation never waits for the author, so once it has run the plan moves on."""
        published = ExistingPlan(
            (PlannedStep(OPERATOR_AGENT_NAME, "Publish it"), PlannedStep(STUB_AGENT.name, "Sum up")), current_step=1
        )
        planner_model = _planner_model(AIMessage("", tool_calls=[_operation("Publish it", step=1)]))
        operator_model = RecordingChatModel(messages=iter([AIMessage("Published.")]))

        messages = await _run(
            planner_model,
            _agent_graph(STUB_AGENT, ScriptedChatModel(messages=iter([]))),
            operator=_operator(operator_model),
            existing_plan=published,
        )

        assert _rejected(messages, OPERATOR_AGENT_NAME) == [REJECT_STEP_NOT_NEXT.format(step=1, next="2")]
        assert operator_model.seen == []
        assert "1. Publish it (operator): done" in planner_model.seen[0][0].text

    async def test_a_step_that_ran_may_be_carried_on_or_followed_by_the_next(self) -> None:
        """Its agent may have asked the author something, or finished: only the planner can tell."""
        planner_model = _planner_model(AIMessage("", tool_calls=[_operation("Publish it", step=2)]))
        operator_model = RecordingChatModel(messages=iter([AIMessage("Published.")]))

        await _run(
            planner_model,
            _agent_graph(STUB_AGENT, ScriptedChatModel(messages=iter([]))),
            operator=_operator(operator_model),
            existing_plan=WRITE_THEN_PUBLISH,
        )

        assert len(operator_model.seen) == 1

    async def test_a_message_about_something_else_runs_without_it(self) -> None:
        planner_model = _planner_model(AIMessage("", tool_calls=[_hand_off(STUB_AGENT.name, "A quiz instead")]))
        stub_model = ScriptedChatModel(messages=iter([AIMessage("Here is the quiz.")]))

        messages = await _run(
            planner_model,
            _agent_graph(STUB_AGENT, stub_model),
            operator=_operator(ScriptedChatModel(messages=iter([]))),
            existing_plan=WRITE_THEN_PUBLISH,
        )

        assert _step_results(messages) == [_step("Here is the quiz.")]

    async def test_its_operation_never_runs_after_a_step_outside_it(self) -> None:
        """A turn that starts outside the plan has dropped it, so its numbers unlock nothing."""
        planner_model = _planner_model(
            AIMessage("", tool_calls=[_hand_off(STUB_AGENT.name, "A quiz instead")]),
            AIMessage("", tool_calls=[_operation("Delete my other courses", step=2)]),
        )
        operator_model = RecordingChatModel(messages=iter([AIMessage("Deleted.")]))
        stub_model = ScriptedChatModel(messages=iter([AIMessage("Here is the quiz.")]))

        messages = await _run(
            planner_model,
            _agent_graph(STUB_AGENT, stub_model),
            operator=_operator(operator_model),
            existing_plan=WRITE_THEN_PUBLISH,
        )

        assert _rejected(messages, OPERATOR_AGENT_NAME) == [REJECT_UNPLANNED_OPERATION]
        assert operator_model.seen == []

    async def test_a_numbered_step_after_one_outside_it_does_not_bring_it_back(self) -> None:
        """The turn's first step decides, once, whether it follows the plan."""
        plan = ExistingPlan(
            (
                PlannedStep(STUB_AGENT.name, "Write the lesson"),
                PlannedStep(OTHER_AGENT.name, "Build the activity"),
                PlannedStep(OPERATOR_AGENT_NAME, "Publish both"),
            ),
            current_step=1,
        )
        planner_model = _planner_model(
            AIMessage("", tool_calls=[_hand_off(STUB_AGENT.name, "A quiz instead")]),
            AIMessage("", tool_calls=[_hand_off(OTHER_AGENT.name, "Build the activity", "call_2", step=2)]),
            AIMessage("", tool_calls=[_operation("Delete my other courses", step=3)]),
        )
        operator_model = RecordingChatModel(messages=iter([AIMessage("Deleted.")]))
        stub_model = ScriptedChatModel(messages=iter([AIMessage("Here is the quiz.")]))
        other_model = ScriptedChatModel(messages=iter([AIMessage("Here is the activity.")]))

        messages = await _run(
            planner_model,
            _agent_graph(STUB_AGENT, stub_model),
            _agent_graph(OTHER_AGENT, other_model),
            operator=_operator(operator_model),
            existing_plan=plan,
        )

        assert _rejected(messages, OPERATOR_AGENT_NAME) == [REJECT_UNPLANNED_OPERATION]
        assert operator_model.seen == []

    async def test_once_a_turn_follows_it_every_call_names_its_step(self) -> None:
        planner_model = _planner_model(
            AIMessage("", tool_calls=[_hand_off(STUB_AGENT.name, "Write the lesson", step=1)]),
            AIMessage("", tool_calls=[_operation("Publish it")]),
        )
        operator_model = RecordingChatModel(messages=iter([AIMessage("Published.")]))
        stub_model = ScriptedChatModel(messages=iter([AIMessage("Here is the lesson.")]))

        messages = await _run(
            planner_model,
            _agent_graph(STUB_AGENT, stub_model),
            operator=_operator(operator_model),
            existing_plan=WRITE_THEN_PUBLISH,
        )

        assert _rejected(messages, OPERATOR_AGENT_NAME) == [REJECT_MISSING_STEP_NUMBER]
        assert operator_model.seen == []

    async def test_a_new_plan_replaces_it(self) -> None:
        planner_model = _planner_model(
            AIMessage("", tool_calls=[_plan((OPERATOR_AGENT_NAME, "Retrieve it"), (STUB_AGENT.name, "Redesign it"))]),
            AIMessage("", tool_calls=[_operation("Retrieve it", step=1)]),
        )
        operator_model = RecordingChatModel(messages=iter([AIMessage("Biology 101.")]))

        await _run(
            planner_model,
            _agent_graph(STUB_AGENT, ScriptedChatModel(messages=iter([]))),
            operator=_operator(operator_model),
            existing_plan=WRITE_THEN_PUBLISH,
        )

        assert len(operator_model.seen) == 1

    def test_the_planner_is_shown_what_is_done_in_progress_and_left(self) -> None:
        plan = ExistingPlan(
            (
                PlannedStep(OPERATOR_AGENT_NAME, "Retrieve the course"),
                PlannedStep(STUB_AGENT.name, "Redesign it"),
                PlannedStep(OPERATOR_AGENT_NAME, "Publish it"),
            ),
            current_step=2,
        )

        prompt = render_planner_prompt([STUB_AGENT], operations=True, existing_plan=plan)

        assert "1. Retrieve the course (operator): done" in prompt
        assert f"2. Redesign it ({STUB_AGENT.name}): in progress" in prompt
        assert "3. Publish it (operator): not started" in prompt

    def test_the_planner_is_shown_a_step_waiting_to_start_as_next(self) -> None:
        plan = ExistingPlan(WRITE_THEN_PUBLISH.steps, current_step=2, has_current_step_run=False)

        prompt = render_planner_prompt([STUB_AGENT], operations=True, existing_plan=plan)

        assert "2. Publish it (operator): next" in prompt

    def test_the_planner_is_shown_no_plan_without_an_existing_plan(self) -> None:
        assert "EXISTING PLAN" not in render_planner_prompt([STUB_AGENT], operations=True, existing_plan=None)


class TestTurnActivity:
    STEPS = WRITE_THEN_PUBLISH.steps
    TASKS = tuple(step.task for step in STEPS)

    def _recorded(self, existing_plan: ExistingPlan | None, *events: dict[str, Any]) -> TurnActivity:
        turn_activity = TurnActivity(existing_plan)
        for event in events:
            turn_activity.record(event)
        return turn_activity

    def test_each_agent_a_step_went_to_is_kept_in_order(self) -> None:
        turn_activity = self._recorded(None, routed(STUB_AGENT.name), routed(OPERATOR_AGENT_NAME))

        assert turn_activity.agents == [STUB_AGENT.name, OPERATOR_AGENT_NAME]
        assert turn_activity.routing == TurnRouting(agent=OPERATOR_AGENT_NAME)

    def test_a_refusal_is_the_routing_but_no_step(self) -> None:
        turn_activity = self._recorded(None, routed(None))

        assert turn_activity.agents == []
        assert turn_activity.routing.refused

    def test_events_that_say_nothing_about_routing_or_the_plan_are_ignored(self) -> None:
        turn_activity = self._recorded(None, {"type": TurnEventType.TOKEN, "content": "Hello"})

        assert (turn_activity.routing, turn_activity.agents, turn_activity.get_plan_in_progress()) == (
            TurnRouting(),
            [],
            None,
        )

    def test_a_plan_whose_step_ran_is_kept_at_that_step(self) -> None:
        turn_activity = self._recorded(None, shown_plan(self.STEPS), plan_step(1, ran=False), plan_step(1, ran=True))

        assert turn_activity.get_plan_in_progress() == ExistingPlan(self.STEPS, current_step=1)

    def test_a_plan_whose_last_step_ran_is_closed(self) -> None:
        turn_activity = self._recorded(
            None,
            shown_plan(self.STEPS),
            plan_step(1, ran=True),
            plan_step(2, ran=False),
            plan_step(2, ran=True),
        )

        assert turn_activity.get_plan_in_progress() is None

    def test_a_plan_whose_last_step_started_but_never_ran_is_kept_at_it(self) -> None:
        """A stop or a failure on the last step leaves it to be carried on, as on any other step."""
        turn_activity = self._recorded(None, shown_plan(self.STEPS), plan_step(1, ran=True), plan_step(2, ran=False))

        expected = ExistingPlan(self.STEPS, current_step=2, has_current_step_run=False)

        assert turn_activity.get_plan_in_progress() == expected

    def test_a_plan_none_of_whose_steps_started_is_closed(self) -> None:
        assert self._recorded(None, shown_plan(self.STEPS)).get_plan_in_progress() is None

    def test_an_existing_plan_the_turn_did_not_carry_on_is_kept_as_it_was(self) -> None:
        assert TurnActivity(WRITE_THEN_PUBLISH).get_plan_in_progress() == WRITE_THEN_PUBLISH

    def test_an_existing_plan_the_turn_carried_on_is_kept(self) -> None:
        longer = ExistingPlan((*self.STEPS, PlannedStep(STUB_AGENT.name, "Summarise it")), current_step=1)
        turn_activity = self._recorded(longer, plan_step(2, ran=False), plan_step(2, ran=True))

        assert turn_activity.get_plan_in_progress() == ExistingPlan(longer.steps, current_step=2)

    def test_a_plan_the_turn_made_is_shown_before_any_step_starts(self) -> None:
        turn_activity = self._recorded(None, shown_plan(self.STEPS))

        expected = PlanSnapshot(tasks=self.TASKS, current_step=0, has_current_step_run=False)

        assert turn_activity.get_plan_snapshot() == expected

    def test_a_shown_plan_follows_its_steps(self) -> None:
        turn_activity = self._recorded(None, shown_plan(self.STEPS), plan_step(1, ran=True), plan_step(2, ran=False))

        expected = PlanSnapshot(tasks=self.TASKS, current_step=2, has_current_step_run=False)

        assert turn_activity.get_plan_snapshot() == expected

    def test_a_finished_plan_is_still_shown(self) -> None:
        turn_activity = self._recorded(
            None, shown_plan(self.STEPS), plan_step(1, ran=True), plan_step(2, ran=False), plan_step(2, ran=True)
        )

        expected = PlanSnapshot(tasks=self.TASKS, current_step=2, has_current_step_run=True)

        assert turn_activity.get_plan_snapshot() == expected

    def test_an_existing_plan_is_shown_once_the_turn_carries_it_on(self) -> None:
        turn_activity = self._recorded(WRITE_THEN_PUBLISH, plan_step(2, ran=False))

        expected = PlanSnapshot(tasks=self.TASKS, current_step=2, has_current_step_run=False)

        assert turn_activity.get_plan_snapshot() == expected

    def test_an_existing_plan_the_turn_did_not_carry_on_is_not_shown(self) -> None:
        turn_activity = self._recorded(WRITE_THEN_PUBLISH, routed(STUB_AGENT.name))

        assert turn_activity.get_plan_snapshot() is None

    def test_a_turn_without_a_plan_shows_none(self) -> None:
        assert self._recorded(None, routed(STUB_AGENT.name)).get_plan_snapshot() is None


class TestThePlannersOwnReplies:
    async def test_small_talk_is_answered_by_the_planner(self) -> None:
        planner_model = _planner_model(AIMessage("Hello! I can help you design courses."))

        messages = await _run(planner_model, _agent_graph(STUB_AGENT, ScriptedChatModel(messages=iter([]))))

        assert messages[-1].text == "Hello! I can help you design courses."

    async def test_a_refusal_is_the_refusal_sentence_in_the_request_locale(
        self, translation_catalog: AddTranslation
    ) -> None:
        translation_catalog(REFUSAL_MESSAGE, SPANISH_REFUSAL)
        planner_model = _planner_model(AIMessage("", tool_calls=[{"name": REFUSAL_TOOL_NAME, "args": {}, "id": "c1"}]))

        with locale_context("es"):
            messages = await _run(planner_model, _agent_graph(STUB_AGENT, ScriptedChatModel(messages=iter([]))))

        assert messages[-1].text == SPANISH_REFUSAL

    async def test_a_refusal_is_not_audited(self, audit_events: AuditEventsFetcher) -> None:
        planner_model = _planner_model(AIMessage("", tool_calls=[{"name": REFUSAL_TOOL_NAME, "args": {}, "id": "c1"}]))

        await _run(planner_model, _agent_graph(STUB_AGENT, ScriptedChatModel(messages=iter([]))))

        assert await audit_events() == []


class TestOperations:
    async def test_the_planner_reads_the_whole_of_what_an_operation_did(self) -> None:
        """The author never reads the operator's text, so the planner is the one who tells them."""
        report = "Published course 42. " * STEP_RESULT_TAIL_CHARS
        planner_model = _planner_model(
            AIMessage("", tool_calls=[_operation("Publish the course")]), AIMessage("Your course is published.")
        )
        operator_model = ScriptedChatModel(messages=iter([AIMessage(report)]))

        messages = await _run(planner_model, operator=_operator(operator_model))

        assert messages[-1].text == "Your course is published."
        assert planner_model.seen[1][-1].text == _operated(report)

    async def test_the_operator_reads_the_conversation_and_the_request(self) -> None:
        planner_model = _planner_model(AIMessage("", tool_calls=[_operation("Publish it")]), AIMessage("Done."))
        operator_model = RecordingChatModel(messages=iter([AIMessage("Published.")]))

        await _run(planner_model, operator=_operator(operator_model))

        assert [(type(m), m.text) for m in operator_model.seen[0]] == [
            (SystemMessage, "Operator prompt."),
            (HumanMessage, "Design a course on photosynthesis."),
            (HumanMessage, "Publish it"),
        ]

    async def test_an_agent_after_an_operation_reads_what_it_returned(self) -> None:
        planner_model = _planner_model(
            AIMessage("", tool_calls=[_operation("Retrieve the course")]),
            AIMessage("", tool_calls=[_hand_off(STUB_AGENT.name, "Redesign it", "call_2")]),
        )
        operator_model = ScriptedChatModel(messages=iter([AIMessage("Biology 101: cells, genetics.")]))
        agent_model = RecordingChatModel(messages=iter([AIMessage("Here is the redesign.")]))

        await _run(planner_model, _agent_graph(STUB_AGENT, agent_model), operator=_operator(operator_model))

        assert _operated("Biology 101: cells, genetics.") in [m.text for m in agent_model.seen[0]]

    async def test_an_operation_is_not_audited(self, audit_events: AuditEventsFetcher) -> None:
        planner_model = _planner_model(AIMessage("", tool_calls=[_operation("Publish it")]), AIMessage("Done."))

        await _run(planner_model, operator=_operator(ScriptedChatModel(messages=iter([AIMessage("Published.")]))))

        assert await audit_events() == []


class TestPlannerPrompt:
    def test_it_is_told_never_to_claim_work_no_step_of_the_message_did(self) -> None:
        """Earlier replies read as if the assistant did the work itself, which a planner may copy."""
        prompt = render_planner_prompt([STUB_AGENT], operations=True, existing_plan=None)

        assert "Never tell the author that work was done" in prompt

    def test_it_is_told_the_refuse_tool_is_the_only_way_to_turn_a_message_down(self) -> None:
        """A decline in the planner's own words skips the fixed sentence and is not recorded as a refusal."""
        prompt = render_planner_prompt([STUB_AGENT], operations=False, existing_plan=None)

        assert "Never turn a message down in your own words" in prompt

    def test_it_lists_each_agent_by_title_and_description(self) -> None:
        prompt = render_planner_prompt([STUB_AGENT, OTHER_AGENT], operations=False, existing_plan=None)

        for agent in (STUB_AGENT, OTHER_AGENT):
            assert f"## {agent.title}\n{agent.description}" in prompt

    def test_it_offers_choices_exactly_as_the_agents_do(self) -> None:
        """The client parses the options block, so the planner and the agents must ask for it alike."""
        section = render_system_prompt(STUB_AGENT).split("OFFERING CHOICES")[1].split("YOUR WORK")[0].strip()

        assert section in render_planner_prompt([STUB_AGENT], operations=False, existing_plan=None)

    def test_it_offers_operations_only_when_there_are_some(self) -> None:
        assert PLANNER_OPERATIONS in render_planner_prompt([STUB_AGENT], operations=True, existing_plan=None)
        assert PLANNER_OPERATIONS not in render_planner_prompt([STUB_AGENT], operations=False, existing_plan=None)

    def test_without_operations_it_still_says_what_to_do_with_an_lms_request(self) -> None:
        without = render_planner_prompt([STUB_AGENT], operations=False, existing_plan=None)
        with_operations = render_planner_prompt([STUB_AGENT], operations=True, existing_plan=None)

        assert PLANNER_WITHOUT_OPERATIONS in without
        assert PLANNER_WITHOUT_OPERATIONS not in with_operations


class TestARunThatGoesWrong:
    async def test_a_hand_off_without_its_request_goes_back_to_the_planner(self) -> None:
        """A hand-off the agent's tool rejects is the planner's to fix, never the author's reply."""
        planner_model = _planner_model(
            AIMessage("", tool_calls=[{"name": STUB_AGENT.name, "args": {}, "id": "c1"}]),
            AIMessage("Which course should I outline?"),
        )

        messages = await _run(planner_model, _agent_graph(STUB_AGENT, ScriptedChatModel(messages=iter([]))))

        assert messages[-1].text == "Which course should I outline?"

    async def test_calls_their_tools_rejected_do_not_count_as_steps(self) -> None:
        rejected = [
            AIMessage("", tool_calls=[{"name": OPERATOR_AGENT_NAME, "args": {}, "id": f"b{n}"}]) for n in (1, 2)
        ]
        operator_model = RecordingChatModel(messages=repeat(AIMessage("Done.")))

        messages = await _run(
            _planner_model(*rejected, *_planned_operations(MAX_STEPS_PER_TURN), AIMessage("All published.")),
            operator=_operator(operator_model),
        )

        assert len(operator_model.seen) == MAX_STEPS_PER_TURN
        assert messages[-1].text == "All published."

    async def test_a_step_past_the_limit_never_runs_and_the_turn_ends_with_the_notice(self) -> None:
        operator_model = RecordingChatModel(messages=repeat(AIMessage("Published.")))
        one_more = AIMessage("", tool_calls=[_operation("Publish it again", "op_more", step=1)])

        messages = await _run(
            _planner_model(*_planned_operations(MAX_STEPS_PER_TURN), one_more), operator=_operator(operator_model)
        )

        assert len(operator_model.seen) == MAX_STEPS_PER_TURN
        assert messages[-1].text == STOPPED_EARLY_NOTICE

    async def test_at_the_limit_with_steps_of_the_plan_left_the_turn_ends_with_a_way_to_continue(self) -> None:
        operator_model = RecordingChatModel(messages=repeat(AIMessage("Published.")))
        reported: list[dict[str, Any]] = []

        messages = await _run(
            _planner_model(*_planned_operations(MAX_STEPS_PER_TURN + 2)),
            operator=_operator(operator_model),
            reported=reported,
        )

        assert len(operator_model.seen) == MAX_STEPS_PER_TURN
        done, left = messages[-1].text.split(PLAN_LEFT_HEADING)
        assert _numbered(done) == [f"{number}. Publish module {number}" for number in range(1, 6)]
        assert f"{PLAN_LEFT_HEADING}\n\n6." in messages[-1].text
        assert _numbered(left) == ["6. Publish module 6", "7. Publish module 7"]
        assert PLAN_DONE_HEADING in done
        assert left.endswith(f"```{OptionsFence.SINGLE}\n{PLAN_CONTINUE_CHOICE}\n{PLAN_STOP_CHOICE}\n```")
        assert _plan_steps(reported)[-1] == (MAX_STEPS_PER_TURN + 1, False)

    async def test_at_the_limit_a_plan_from_an_earlier_message_counts_the_steps_done_before(self) -> None:
        steps = tuple(PlannedStep(OPERATOR_AGENT_NAME, f"Publish module {number}") for number in range(1, 9))
        calls = [
            AIMessage("", tool_calls=[_operation(f"Go {number}", f"op_{number}", step=number)])
            for number in range(2, 8)
        ]
        operator_model = RecordingChatModel(messages=repeat(AIMessage("Published.")))
        reported: list[dict[str, Any]] = []

        messages = await _run(
            _planner_model(*calls),
            operator=_operator(operator_model),
            existing_plan=ExistingPlan(steps, current_step=2, has_current_step_run=False),
            reported=reported,
        )

        done, left = messages[-1].text.split(PLAN_LEFT_HEADING)
        assert _numbered(done) == [f"{number}. Publish module {number}" for number in range(1, 7)]
        assert _numbered(left) == ["7. Publish module 7", "8. Publish module 8"]
        assert _plan_steps(reported)[-1] == (7, False)

    async def test_rejected_calls_past_their_limit_with_steps_of_the_plan_left_end_with_the_same_note(self) -> None:
        plan, first, second, _third = _planned_operations(3)
        unnumbered = [AIMessage("", tool_calls=[_operation("Publish", f"bad_{number}")]) for number in range(3)]
        operator_model = RecordingChatModel(messages=repeat(AIMessage("Published.")))
        reported: list[dict[str, Any]] = []

        messages = await _run(
            _planner_model(plan, first, *unnumbered, second), operator=_operator(operator_model), reported=reported
        )

        assert len(operator_model.seen) == 1
        assert _numbered(messages[-1].text) == ["1. Publish module 1", "2. Publish module 2", "3. Publish module 3"]
        assert _plan_steps(reported)[-1] == (2, False)

    async def test_at_a_limit_a_call_that_is_not_for_the_next_step_ends_without_a_way_to_continue(self) -> None:
        """The plan stays where it was: nothing says its latest step is finished."""
        plan, first, *_rest = _planned_operations(3)
        unnumbered = [AIMessage("", tool_calls=[_operation("Publish", f"bad_{number}")]) for number in range(4)]
        reported: list[dict[str, Any]] = []

        messages = await _run(
            _planner_model(plan, first, *unnumbered),
            operator=_operator(ScriptedChatModel(messages=repeat(AIMessage("Published.")))),
            reported=reported,
        )

        assert messages[-1].text == COULD_NOT_FINISH
        assert _plan_steps(reported) == [(1, False), (1, True)]

    async def test_the_note_at_the_limit_is_in_the_request_locale(self, translation_catalog: AddTranslation) -> None:
        translation_catalog(PLAN_LEFT_HEADING, "Por hacer:")
        translation_catalog(PLAN_STOP_CHOICE, "Parar aquí")
        operator_model = RecordingChatModel(messages=repeat(AIMessage("Published.")))

        with locale_context("es"):
            messages = await _run(
                _planner_model(*_planned_operations(MAX_STEPS_PER_TURN + 1)), operator=_operator(operator_model)
            )

        assert "Por hacer:\n\n6. Publish module 6" in messages[-1].text
        assert messages[-1].text.endswith("Parar aquí\n```")

    async def test_a_reply_cut_to_one_call_goes_back_to_the_planner_without_the_calls_it_lost(self) -> None:
        """Some providers keep each call in the reply's content too, and reject a call that has no result."""
        both_calls = AIMessage(
            content=[
                {"type": "text", "text": "Passing this on."},
                {"type": "tool_use", "id": "c1", "name": STUB_AGENT.name, "input": {}},
                {"type": "tool_use", "id": "c2", "name": OTHER_AGENT.name, "input": {"request": "A quiz"}},
            ],
            tool_calls=[
                {"name": STUB_AGENT.name, "args": {}, "id": "c1"},
                _hand_off(OTHER_AGENT.name, "A quiz", "c2"),
            ],
        )
        planner_model = _planner_model(both_calls, AIMessage("Which course should I outline?"))
        agents = [_agent_graph(agent, ScriptedChatModel(messages=iter([]))) for agent in (STUB_AGENT, OTHER_AGENT)]

        await _run(planner_model, *agents)

        asked_again = planner_model.seen[1]
        called = [
            block["id"]
            for message in asked_again
            if isinstance(message, AIMessage) and isinstance(message.content, list)
            for block in message.content
            if isinstance(block, dict) and block["type"] == "tool_use"
        ]
        answered = [message.tool_call_id for message in asked_again if isinstance(message, ToolMessage)]
        assert called == answered == ["c1"]
        assert [message.text for message in asked_again if isinstance(message, AIMessage)] == ["Passing this on."]

    async def test_a_planner_that_keeps_calling_an_unknown_tool_stops(self) -> None:
        calls = (
            AIMessage("", id=f"r{n}", tool_calls=[{"name": "no_such_agent", "args": {}, "id": f"c{n}"}])
            for n in count()
        )
        planner = build_planner(
            ScriptedChatModel(messages=calls, disable_streaming=True),
            [_agent_graph(STUB_AGENT, ScriptedChatModel(messages=iter([])))],
            operator=None,
            existing_plan=None,
        )

        result = await planner.ainvoke({"messages": [HumanMessage("Hello")]}, context=CONTEXT)

        assert result["messages"][-1].text == COULD_NOT_FINISH


class TestAStreamedHandOff:
    async def test_the_agents_tools_run_when_the_planner_is_streamed_with_its_agents(self) -> None:
        """An agent's tool call waits for its reader; streaming the planner with subgraphs is that reader."""
        runs: list[str] = []

        async def note() -> str:
            """Note that the tool ran."""
            runs.append("ran")
            return "noted"

        tool = StructuredTool.from_function(coroutine=note, name="note", description="Note it.")
        agent_model = ScriptedChatModel(
            messages=iter([AIMessage("", tool_calls=[{"name": "note", "args": {}, "id": "t1"}]), AIMessage("Done.")]),
            disable_streaming=True,
        )
        planner = build_planner(
            _planner_model(AIMessage("", tool_calls=[_hand_off(STUB_AGENT.name, "Note it")])),
            [AgentGraph(STUB_AGENT, build_turn_agent(agent_model, [tool], "Agent prompt.", 50, name=STUB_AGENT.name))],
            operator=None,
            existing_plan=None,
        )

        stream = planner.astream(
            {"messages": [HumanMessage("Note it")]}, context=CONTEXT, stream_mode=["custom"], subgraphs=True
        )
        async for _namespace, _mode, chunk in stream:
            go = cast(dict[str, Any], chunk).pop("go", None)
            if go is not None:
                go.set()

        assert runs == ["ran"]
