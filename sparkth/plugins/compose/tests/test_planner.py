"""How Compose's planner hands a message to one agent, answers it itself, or refuses it."""

from itertools import count
from typing import Any, cast

from langchain_core.messages import AIMessage, AnyMessage, BaseMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.tools import StructuredTool
from pydantic import Field

from sparkth.core.i18n import locale_context
from sparkth.lib.audit.events import AuditModelInfo
from sparkth.lib.compose.constants import REFUSE_TOOL_NAME
from sparkth.lib.compose.hooks import Agent
from sparkth.lib.testing import AddTranslation, AuditEventsFetcher, ScriptedChatModel
from sparkth.plugins.compose.constants import REFUSAL_MESSAGE, SYSTEM_PROMPT_SKELETON, TOOL_CALL_LIMIT_NOTICE
from sparkth.plugins.compose.llm import build_turn_agent
from sparkth.plugins.compose.planner import (
    AgentGraph,
    agent_input,
    build_planner,
    render_planner_prompt,
)
from sparkth.plugins.compose.tests.conftest import OTHER_AGENT, STUB_AGENT

CONTEXT = AuditModelInfo("anthropic", "claude-sonnet-5")
SPANISH_REFUSAL = "Solo puedo ayudar con el diseño de cursos."


class _RecordingModel(ScriptedChatModel):
    """A scripted model that keeps the messages of every call it gets."""

    seen: list[list[BaseMessage]] = Field(default_factory=list)

    def _generate(self, messages: list[BaseMessage], *args: Any, **kwargs: Any) -> Any:
        self.seen.append(messages)
        return super()._generate(messages, *args, **kwargs)


def _planner_model(*replies: AIMessage) -> ScriptedChatModel:
    """The planner's model, answering whole: the fake drops tool calls when a streamed planner has it stream."""
    return ScriptedChatModel(messages=iter(replies), disable_streaming=True)


def _hand_off(name: str, request: str, call_id: str = "call_1") -> dict[str, Any]:
    return {"name": name, "args": {"request": request}, "id": call_id}


def _agent_graph(agent: Agent, model: ScriptedChatModel, prompt: str = "Agent prompt.") -> AgentGraph:
    return AgentGraph(agent, build_turn_agent(model, [], prompt, 50))


async def _run(planner_model: ScriptedChatModel, *agents: AgentGraph) -> list[AnyMessage]:
    planner = build_planner(planner_model, list(agents))
    result = await planner.ainvoke({"messages": [HumanMessage("Design a course on photosynthesis.")]}, context=CONTEXT)
    messages: list[AnyMessage] = result["messages"]
    return messages


class TestAgentInput:
    def test_it_drops_the_planners_hand_offs_and_ends_with_the_request(self) -> None:
        history: list[AnyMessage] = [
            HumanMessage("Earlier question"),
            AIMessage("Earlier answer"),
            HumanMessage("Design a course"),
            AIMessage("", tool_calls=[_hand_off("stub", "Design a course on photosynthesis")]),
            ToolMessage("Handed off", tool_call_id="call_1"),
        ]

        assert agent_input(history, "Design a course on photosynthesis") == [
            HumanMessage("Earlier question"),
            AIMessage("Earlier answer"),
            HumanMessage("Design a course"),
            HumanMessage("Design a course on photosynthesis"),
        ]


class TestHandOff:
    async def test_the_agents_reply_ends_the_turn(self) -> None:
        planner_model = _planner_model(AIMessage("", tool_calls=[_hand_off(STUB_AGENT.name, "An outline")]))
        agent_model = ScriptedChatModel(messages=iter([AIMessage("Here is the outline.")]))

        messages = await _run(planner_model, _agent_graph(STUB_AGENT, agent_model))

        assert messages[-1].text == "Here is the outline."
        assert next(planner_model.messages, None) is None

    async def test_the_agent_reads_its_own_prompt_the_conversation_and_the_request(self) -> None:
        planner_model = _planner_model(AIMessage("", tool_calls=[_hand_off(STUB_AGENT.name, "An outline")]))
        agent_model = _RecordingModel(messages=iter([AIMessage("Here is the outline.")]))

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
        other_model = ScriptedChatModel(messages=iter([AIMessage("Here is the quiz.")]))

        messages = await _run(
            planner_model, _agent_graph(STUB_AGENT, stub_model), _agent_graph(OTHER_AGENT, other_model)
        )

        assert messages[-1].text == "Here is the outline."
        assert next(other_model.messages, None) is not None

    async def test_a_hand_off_is_not_audited(self, audit_events: AuditEventsFetcher) -> None:
        planner_model = _planner_model(AIMessage("", tool_calls=[_hand_off(STUB_AGENT.name, "An outline")]))
        agent_model = ScriptedChatModel(messages=iter([AIMessage("Here is the outline.")]))

        await _run(planner_model, _agent_graph(STUB_AGENT, agent_model))

        assert await audit_events() == []


class TestThePlannersOwnReplies:
    async def test_small_talk_is_answered_by_the_planner(self) -> None:
        planner_model = _planner_model(AIMessage("Hello! I can help you design courses."))

        messages = await _run(planner_model, _agent_graph(STUB_AGENT, ScriptedChatModel(messages=iter([]))))

        assert messages[-1].text == "Hello! I can help you design courses."

    async def test_a_refusal_is_the_refusal_sentence_in_the_request_locale(
        self, translation_catalog: AddTranslation
    ) -> None:
        translation_catalog(REFUSAL_MESSAGE, SPANISH_REFUSAL)
        planner_model = _planner_model(AIMessage("", tool_calls=[{"name": REFUSE_TOOL_NAME, "args": {}, "id": "c1"}]))

        with locale_context("es"):
            messages = await _run(planner_model, _agent_graph(STUB_AGENT, ScriptedChatModel(messages=iter([]))))

        assert messages[-1].text == SPANISH_REFUSAL

    async def test_a_refusal_is_not_audited(self, audit_events: AuditEventsFetcher) -> None:
        planner_model = _planner_model(AIMessage("", tool_calls=[{"name": REFUSE_TOOL_NAME, "args": {}, "id": "c1"}]))

        await _run(planner_model, _agent_graph(STUB_AGENT, ScriptedChatModel(messages=iter([]))))

        assert await audit_events() == []


class TestPlannerPrompt:
    def test_it_lists_each_agent_by_title_and_description(self) -> None:
        prompt = render_planner_prompt([STUB_AGENT, OTHER_AGENT])

        for agent in (STUB_AGENT, OTHER_AGENT):
            assert f"## {agent.title}\n{agent.description}" in prompt

    def test_it_offers_choices_exactly_as_the_agents_do(self) -> None:
        """The client parses the options block, so the planner and the agents must ask for it alike."""
        section = SYSTEM_PROMPT_SKELETON.split("OFFERING CHOICES")[1].split("CAPABILITIES")[0].strip()

        assert section in render_planner_prompt([STUB_AGENT])


class TestARunThatGoesWrong:
    async def test_a_hand_off_without_its_request_goes_back_to_the_planner(self) -> None:
        """A hand-off the agent's tool refuses is the planner's to fix, never the author's reply."""
        planner_model = _planner_model(
            AIMessage("", tool_calls=[{"name": STUB_AGENT.name, "args": {}, "id": "c1"}]),
            AIMessage("Which course should I outline?"),
        )

        messages = await _run(planner_model, _agent_graph(STUB_AGENT, ScriptedChatModel(messages=iter([]))))

        assert messages[-1].text == "Which course should I outline?"

    async def test_a_planner_that_keeps_calling_an_unknown_tool_stops(self) -> None:
        calls = (
            AIMessage("", id=f"r{n}", tool_calls=[{"name": "no_such_agent", "args": {}, "id": f"c{n}"}])
            for n in count()
        )
        planner = build_planner(
            ScriptedChatModel(messages=calls, disable_streaming=True),
            [_agent_graph(STUB_AGENT, ScriptedChatModel(messages=iter([])))],
        )

        result = await planner.ainvoke({"messages": [HumanMessage("Hello")]}, context=CONTEXT)

        assert result["messages"][-1].text == TOOL_CALL_LIMIT_NOTICE


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
            [AgentGraph(STUB_AGENT, build_turn_agent(agent_model, [tool], "Agent prompt.", 50))],
        )

        stream = planner.astream(
            {"messages": [HumanMessage("Note it")]}, context=CONTEXT, stream_mode=["custom"], subgraphs=True
        )
        async for _namespace, _mode, chunk in stream:
            go = cast(dict[str, Any], chunk).pop("go", None)
            if go is not None:
                go.set()

        assert runs == ["ran"]
