"""What a turn starts with: every enabled agent, every requested tool whose plugin is on, of the
plugins the caller may use, and the documents attached to its conversation.

Each agent then runs with only the tools it names.
"""

import json
from collections.abc import AsyncGenerator
from dataclasses import asdict
from typing import Any, cast
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy.exc import OperationalError
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from sparkth.core.models.plugin import Plugin, UserPluginPreference
from sparkth.lib.compose.constants import OPERATOR_AGENT_NAME
from sparkth.lib.compose.hooks import Agent
from sparkth.lib.db import session_scope
from sparkth.lib.documents import Document, DocumentStatus
from sparkth.lib.encryption import get_encryption_service
from sparkth.lib.llm import small_model_for
from sparkth.lib.models import LLMConfig, User
from sparkth.lib.permissions import PLUGIN_USE, PLUGIN_USER_ROLE, assign_role, revoke_role
from sparkth.lib.permissions.scopes import GLOBAL, PLUGIN
from sparkth.lib.rag import get_readable_document
from sparkth.lib.settings import get_settings
from sparkth.lib.testing import AuditEventsFetcher
from sparkth.main import app
from sparkth.plugins.compose.config import ComposeSettings, get_compose_settings
from sparkth.plugins.compose.constants import ATTACHED_DOCUMENTS_HEADING, REFUSAL_MESSAGE
from sparkth.plugins.compose.enums import PlannerModel
from sparkth.plugins.compose.models import Conversation, ConversationAttachment
from sparkth.plugins.compose.planner import ExistingPlan, PlannedStep, TurnRouting, render_planner_prompt
from sparkth.plugins.compose.prompt import render_system_prompt
from sparkth.plugins.compose.tests.helpers import (
    CANVAS_CONFIG,
    OPENEDX_CONFIG,
    STREAM_TURN,
    answering_model,
    planning,
    refusal,
)

COMPLETIONS_URL = "/api/v1/compose/completions"


async def _seed_llm_config(session: AsyncSession, user_id: int) -> int:
    enc = get_encryption_service(get_settings().ENCRYPTION_KEY)
    config = LLMConfig(
        user_id=user_id,
        name="test-cfg-routing",
        provider="openai",
        model="gpt-4o",
        encrypted_key=enc.encrypt("sk-test"),
        masked_key="sk-***",
        is_active=True,
    )
    session.add(config)
    await session.flush()
    config_id = config.id or 0
    await session.commit()
    return config_id


async def _seed_conversation(session: AsyncSession, user_id: int) -> str:
    conversation = Conversation(user_id=user_id, provider="openai", model="gpt-4o")
    session.add(conversation)
    await session.flush()
    conversation_uuid = str(conversation.uuid)
    await session.commit()
    return conversation_uuid


def _provider() -> MagicMock:
    provider = MagicMock()
    provider.create_llm.return_value = answering_model("On it.")
    return provider


def _tool(name: str) -> MagicMock:
    tool = MagicMock()
    tool.name = name
    return tool


def _registry() -> MagicMock:
    """Two tools from two plugins; every turn may bind both."""
    registry = MagicMock()
    registry.plugin_for.side_effect = {"openedx_create_xblock": "openedx", "stub_build": "stub"}.get
    registry.get_all_tools.return_value = [_tool("openedx_create_xblock"), _tool("stub_build")]
    return registry


def _lms_registry() -> MagicMock:
    """Open edX, Canvas and stub tools, each owned by its plugin."""
    registry = MagicMock()
    registry.plugin_for.side_effect = {
        "openedx_create_xblock": "openedx",
        "canvas_create_course": "canvas",
        "stub_build": "stub",
    }.get
    registry.get_all_tools.return_value = [
        _tool("openedx_create_xblock"),
        _tool("canvas_create_course"),
        _tool("stub_build"),
    ]
    registry.get_tools_by_names.side_effect = lambda names: [
        tool for tool in registry.get_all_tools.return_value if tool.name in names
    ]
    return registry


def _turn_answer() -> AsyncMock:
    """Stands in for running a turn with tools, which a mocked provider cannot do."""
    return AsyncMock(return_value={"content": "On it.", "metadata": {}, "routing": TurnRouting()})


def _bound_tool_names(complete_turn: AsyncMock) -> list[str]:
    return [tool.name for tool in complete_turn.await_args_list[-1].args[1]]


def _planner_prompt(get_provider: MagicMock) -> str:
    """The system prompt the turn's planner read, from the model behind ``get_provider``."""
    return str(get_provider.return_value.create_llm.return_value.seen[0][0].content)


def _listed(agent: Agent) -> str:
    """How the planner's prompt lists ``agent``."""
    return f"## {agent.title}\n{agent.description}"


async def _turn(
    client: AsyncClient,
    config_id: int,
    conversation_uuid: str | None = None,
    tools: str | list[str] = "none",
    stream: bool = False,
) -> Any:
    body: dict[str, Any] = {
        "llm_config_id": config_id,
        "messages": [{"role": "user", "content": "Build it"}],
        "stream": stream,
        "tools": tools,
    }
    if conversation_uuid:
        body["conversation_id"] = conversation_uuid
    return await client.post(COMPLETIONS_URL, json=body)


class TestThePlannersModel:
    """The models a turn asks its provider for: the reply's, then the planner's."""

    async def _models_asked_for(self, client: AsyncClient, session: AsyncSession, user_id: int) -> list[str]:
        config_id = await _seed_llm_config(session, user_id)
        conversation_uuid = await _seed_conversation(session, user_id)
        with patch("sparkth.plugins.compose.routes.completions.get_provider", return_value=_provider()) as get_provider:
            await _turn(client, config_id, conversation_uuid)
        return [call.kwargs.get("model") or call.args[2] for call in get_provider.call_args_list]

    async def test_the_planner_runs_on_the_providers_small_model_unless_set_otherwise(
        self, client: AsyncClient, current_user: User, session: AsyncSession, stub_agent: Agent
    ) -> None:
        models = await self._models_asked_for(client, session, current_user.id or 1)

        assert models == ["gpt-4o", small_model_for("openai")]

    async def test_the_planner_can_be_set_to_run_on_the_same_model_as_the_reply(
        self, client: AsyncClient, current_user: User, session: AsyncSession, stub_agent: Agent
    ) -> None:
        app.dependency_overrides[get_compose_settings] = lambda: ComposeSettings(
            planner_model=PlannerModel.SAME_AS_COMPOSE
        )

        models = await self._models_asked_for(client, session, current_user.id or 1)

        assert models == ["gpt-4o", "gpt-4o"]


class TestTheAttachedDocuments:
    """The planner is told what is attached, so an agent can name a document or say why it can't read one yet."""

    async def test_the_turn_lists_the_attached_documents_ready_or_not_but_not_deleted_ones(
        self, client: AsyncClient, current_user: User, session: AsyncSession
    ) -> None:
        user_id = current_user.id or 1
        config_id = await _seed_llm_config(session, user_id)
        conversation_uuid = await _seed_conversation(session, user_id)
        conversation = (await session.exec(select(Conversation))).one()
        documents = [
            Document(user_id=user_id, name="Biology.pdf", status=DocumentStatus.READY),
            Document(user_id=user_id, name="Draft.pdf", status=DocumentStatus.PROCESSING),
            Document(user_id=user_id, name="Removed.pdf", status=DocumentStatus.READY, is_deleted=True),
        ]
        session.add_all(documents)
        await session.flush()
        for document in documents:
            session.add(ConversationAttachment(conversation_id=conversation.id or 0, document_id=document.id or 0))
        await session.commit()

        with (
            patch("sparkth.plugins.compose.routes.completions.get_provider", return_value=_provider()),
            patch("sparkth.plugins.compose.routes.completions.RAGSearchClassifier") as classifier,
            patch("sparkth.plugins.compose.routes.completions.complete_turn", new=_turn_answer()) as turn,
        ):
            classifier.return_value.requires_search = AsyncMock(return_value=False)
            await _turn(client, config_id, conversation_uuid)

        listing = f"{ATTACHED_DOCUMENTS_HEADING}\n- {documents[0].id}: Biology.pdf\n- {documents[1].id}: Draft.pdf"
        assert {"role": "user", "content": listing} in turn.await_args_list[-1].args[0]

    async def test_the_turn_binds_only_the_attached_documents_as_readable(
        self, client: AsyncClient, current_user: User, session: AsyncSession
    ) -> None:
        user_id = current_user.id or 1
        config_id = await _seed_llm_config(session, user_id)
        conversation_uuid = await _seed_conversation(session, user_id)
        conversation = (await session.exec(select(Conversation))).one()
        attached = Document(user_id=user_id, name="Biology.pdf", status=DocumentStatus.READY)
        unattached = Document(user_id=user_id, name="Notes.pdf", status=DocumentStatus.READY)
        session.add_all([attached, unattached])
        await session.flush()
        document_ids = {"Biology.pdf": attached.id or 0, "Notes.pdf": unattached.id or 0}
        session.add(ConversationAttachment(conversation_id=conversation.id or 0, document_id=attached.id or 0))
        await session.commit()
        readable: dict[str, bool] = {}

        async def reading_turn(*args: Any, **kwargs: Any) -> AsyncGenerator[dict[str, Any], None]:
            async with session_scope() as read_session:
                for name, document_id in document_ids.items():
                    readable[name] = await get_readable_document(read_session, document_id) is not None
            yield {"type": "token", "content": "Done."}

        with (
            patch("sparkth.plugins.compose.routes.completions.get_provider", return_value=_provider()),
            patch("sparkth.plugins.compose.routes.completions.RAGSearchClassifier") as classifier,
            patch(STREAM_TURN, reading_turn),
        ):
            classifier.return_value.requires_search = AsyncMock(return_value=False)
            await _turn(client, config_id, conversation_uuid, stream=True)

        assert readable == {"Biology.pdf": True, "Notes.pdf": False}


class TestAnUnfinishedPlan:
    async def test_the_next_message_is_given_the_existing_plan_saved_with_the_latest_reply(
        self, client: AsyncClient, current_user: User, session: AsyncSession, stub_agent: Agent
    ) -> None:
        config_id = await _seed_llm_config(session, current_user.id or 1)
        conversation_uuid = await _seed_conversation(session, current_user.id or 1)
        plan = ExistingPlan(
            (PlannedStep(stub_agent.name, "Write the lesson"), PlannedStep(OPERATOR_AGENT_NAME, "Publish it")), 1
        )
        reply = {"content": "Who are your learners?", "metadata": {"plan": asdict(plan)}, "routing": TurnRouting()}

        with (
            patch("sparkth.plugins.compose.routes.completions.get_provider", return_value=_provider()),
            patch(
                "sparkth.plugins.compose.routes.completions.complete_turn", new=AsyncMock(return_value=reply)
            ) as turn,
        ):
            await _turn(client, config_id, conversation_uuid)
            await _turn(client, config_id, conversation_uuid)

        assert [call.kwargs["planner_setup"].existing_plan for call in turn.await_args_list] == [None, plan]


class TestOneAssistantPerTurn:
    async def test_a_message_no_agent_covers_is_refused(
        self, client: AsyncClient, current_user: User, session: AsyncSession, stub_agent: Agent
    ) -> None:
        config_id = await _seed_llm_config(session, current_user.id or 1)
        conversation_uuid = await _seed_conversation(session, current_user.id or 1)

        with patch(
            "sparkth.plugins.compose.routes.completions.get_provider", side_effect=planning(_provider(), refusal())
        ):
            response = await _turn(client, config_id, conversation_uuid)

        assert response.json()["message"]["content"] == REFUSAL_MESSAGE

    async def test_a_message_is_offered_to_every_enabled_agent(
        self, client: AsyncClient, current_user: User, session: AsyncSession, stub_agent: Agent, other_agent: Agent
    ) -> None:
        config_id = await _seed_llm_config(session, current_user.id or 1)
        conversation_uuid = await _seed_conversation(session, current_user.id or 1)
        provider = _provider()

        with (
            patch("sparkth.plugins.compose.routes.completions.get_provider", return_value=provider) as get_provider,
        ):
            response = await _turn(client, config_id, conversation_uuid)

        assert response.json()["message"]["content"] == "On it."
        assert _listed(other_agent) in _planner_prompt(get_provider)
        assert _listed(stub_agent) in _planner_prompt(get_provider)

    async def test_a_first_message_is_offered_to_every_enabled_agent(
        self, client: AsyncClient, current_user: User, session: AsyncSession, stub_agent: Agent
    ) -> None:
        config_id = await _seed_llm_config(session, current_user.id or 1)

        with (
            patch("sparkth.plugins.compose.routes.completions.get_provider", return_value=_provider()) as get_provider,
            patch("sparkth.plugins.compose.conversation_title.generate_conversation_title"),
        ):
            response = await _turn(client, config_id)

        assert response.status_code == 200
        assert _listed(stub_agent) in _planner_prompt(get_provider)

    async def test_a_conversation_continues_after_a_plugin_is_switched_off(
        self, client: AsyncClient, current_user: User, session: AsyncSession, stub_agent: Agent
    ) -> None:
        """Switching a plugin off removes its section; the conversation goes on."""
        config_id = await _seed_llm_config(session, current_user.id or 1)
        conversation_uuid = await _seed_conversation(session, current_user.id or 1)
        session.add(Plugin(name="stub", enabled=False))
        await session.commit()
        provider = _provider()

        with (
            patch("sparkth.plugins.compose.routes.completions.get_provider", return_value=provider) as get_provider,
        ):
            response = await _turn(client, config_id, conversation_uuid)

        assert response.status_code == 200
        assert response.json()["message"]["content"] == "On it."
        assert _listed(stub_agent) not in _planner_prompt(get_provider)

    async def test_every_requested_tool_reaches_the_turn_whatever_the_agent(
        self, client: AsyncClient, current_user: User, session: AsyncSession, stub_agent: Agent
    ) -> None:
        config_id = await _seed_llm_config(session, current_user.id or 1)
        conversation_uuid = await _seed_conversation(session, current_user.id or 1)
        provider = _provider()

        with (
            patch("sparkth.plugins.compose.routes.completions.get_provider", return_value=provider),
            patch("sparkth.plugins.compose.routes.completions.get_tool_registry", return_value=_registry()),
            patch("sparkth.plugins.compose.routes.completions.complete_turn", new=_turn_answer()) as complete_turn,
        ):
            await _turn(client, config_id, conversation_uuid, "*")

        assert _bound_tool_names(complete_turn) == ["openedx_create_xblock", "stub_build"]

    async def test_the_conversation_lists_no_tools(
        self, client: AsyncClient, current_user: User, session: AsyncSession, stub_agent: Agent
    ) -> None:
        """Each agent and the operator get their own tools bound, so no message lists the turn's tools."""
        config_id = await _seed_llm_config(session, current_user.id or 1)
        conversation_uuid = await _seed_conversation(session, current_user.id or 1)

        with (
            patch("sparkth.plugins.compose.routes.completions.get_provider", return_value=_provider()),
            patch("sparkth.plugins.compose.routes.completions.get_tool_registry", return_value=_registry()),
            patch("sparkth.plugins.compose.routes.completions.complete_turn", new=_turn_answer()) as complete_turn,
        ):
            await _turn(client, config_id, conversation_uuid, "*")

        sent = complete_turn.await_args_list[-1].args[0]
        assert not any("stub_build" in str(message["content"]) for message in sent)


async def _switch_stub(session: AsyncSession, user_id: int, system_on: bool, user_on: bool | None) -> None:
    """Seed the ``stub`` plugin's system switch and, when given, this user's own switch."""
    plugin = Plugin(name="stub", enabled=system_on)
    session.add(plugin)
    await session.flush()
    if user_on is not None:
        session.add(UserPluginPreference(user_id=user_id, plugin_id=cast(int, plugin.id), enabled=user_on))
    await session.commit()


async def _seed_lms_plugins(
    session: AsyncSession, user_id: int, openedx_on: bool, canvas_on: bool, openedx_system_on: bool = True
) -> None:
    """Seed the three plugins, this user's Open edX and Canvas rows with credentials."""
    stub = Plugin(name="stub", enabled=True)
    openedx = Plugin(name="openedx", enabled=openedx_system_on)
    canvas = Plugin(name="canvas", enabled=True)
    session.add_all([stub, openedx, canvas])
    await session.flush()
    session.add(
        UserPluginPreference(
            user_id=user_id,
            plugin_id=cast(int, openedx.id),
            enabled=openedx_on,
            config=OPENEDX_CONFIG,
        )
    )
    session.add(
        UserPluginPreference(
            user_id=user_id,
            plugin_id=cast(int, canvas.id),
            enabled=canvas_on,
            config=CANVAS_CONFIG,
        )
    )
    await session.commit()


async def _fake_stream() -> AsyncGenerator[str, None]:
    yield f"data: {json.dumps({'done': True})}\n\n"


async def _raise_operational_error(user_id: int, session: AsyncSession) -> set[str]:
    raise OperationalError("SELECT 1", {}, Exception("connection lost"))


class TestPluginSwitches:
    async def _bound_after(
        self, client: AsyncClient, session: AsyncSession, user_id: int, system_on: bool, user_on: bool | None
    ) -> list[str]:
        config_id = await _seed_llm_config(session, user_id)
        conversation_uuid = await _seed_conversation(session, user_id)
        await _switch_stub(session, user_id, system_on, user_on)
        provider = _provider()
        with (
            patch("sparkth.plugins.compose.routes.completions.get_provider", return_value=provider),
            patch("sparkth.plugins.compose.routes.completions.get_tool_registry", return_value=_registry()),
            patch("sparkth.plugins.compose.routes.completions.complete_turn", new=_turn_answer()) as complete_turn,
        ):
            await _turn(client, config_id, conversation_uuid, "*")
        return _bound_tool_names(complete_turn)

    async def test_a_plugin_the_user_switched_off_binds_none_of_its_tools(
        self, client: AsyncClient, current_user: User, session: AsyncSession, stub_agent: Agent
    ) -> None:
        bound = await self._bound_after(client, session, current_user.id or 1, True, False)

        assert bound == ["openedx_create_xblock"]

    async def test_a_plugin_the_user_switched_off_offers_no_agent(
        self, client: AsyncClient, current_user: User, session: AsyncSession, stub_agent: Agent, other_agent: Agent
    ) -> None:
        config_id = await _seed_llm_config(session, current_user.id or 1)
        conversation_uuid = await _seed_conversation(session, current_user.id or 1)
        await _switch_stub(session, current_user.id or 1, True, False)

        with (
            patch("sparkth.plugins.compose.routes.completions.get_provider", return_value=_provider()) as get_provider,
        ):
            await _turn(client, config_id, conversation_uuid)

        assert _listed(stub_agent) not in _planner_prompt(get_provider)
        assert _listed(other_agent) in _planner_prompt(get_provider)

    async def test_a_plugin_switched_off_system_wide_binds_none_of_its_tools(
        self, client: AsyncClient, current_user: User, session: AsyncSession, stub_agent: Agent
    ) -> None:
        bound = await self._bound_after(client, session, current_user.id or 1, False, None)

        assert bound == ["openedx_create_xblock"]

    async def test_an_enabled_plugin_keeps_its_tools(
        self, client: AsyncClient, current_user: User, session: AsyncSession, stub_agent: Agent
    ) -> None:
        bound = await self._bound_after(client, session, current_user.id or 1, True, True)

        assert bound == ["openedx_create_xblock", "stub_build"]

    async def test_a_streamed_turn_binds_the_same_filtered_tools(
        self, client: AsyncClient, current_user: User, session: AsyncSession, stub_agent: Agent
    ) -> None:
        user_id = current_user.id or 1
        config_id = await _seed_llm_config(session, user_id)
        conversation_uuid = await _seed_conversation(session, user_id)
        await _switch_stub(session, user_id, True, False)

        with (
            patch("sparkth.plugins.compose.routes.completions.get_provider", return_value=_provider()),
            patch("sparkth.plugins.compose.routes.completions.get_tool_registry", return_value=_registry()),
            patch("sparkth.plugins.compose.routes.completions.ComposeStreamProcessor") as processor_cls,
        ):
            processor_cls.return_value.stream.return_value = _fake_stream()
            await _turn(client, config_id, conversation_uuid, "*", True)

        assert [tool.name for tool in processor_cls.call_args.args[4]] == ["openedx_create_xblock"]

    async def test_a_streamed_turn_gets_the_tool_limit_from_the_routes_settings(
        self, client: AsyncClient, current_user: User, session: AsyncSession
    ) -> None:
        user_id = current_user.id or 1
        config_id = await _seed_llm_config(session, user_id)
        conversation_uuid = await _seed_conversation(session, user_id)
        app.dependency_overrides[get_compose_settings] = lambda: ComposeSettings(max_tool_executions=7)

        with (
            patch("sparkth.plugins.compose.routes.completions.get_provider", return_value=_provider()),
            patch("sparkth.plugins.compose.routes.completions.ComposeStreamProcessor") as processor_cls,
        ):
            processor_cls.return_value.stream.return_value = _fake_stream()
            await _turn(client, config_id, conversation_uuid, stream=True)

        assert processor_cls.call_args.kwargs["max_tool_executions"] == 7

    async def test_a_failed_switch_lookup_never_reaches_the_model(
        self,
        client: AsyncClient,
        current_user: User,
        session: AsyncSession,
        stub_agent: Agent,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        config_id = await _seed_llm_config(session, current_user.id or 1)
        conversation_uuid = await _seed_conversation(session, current_user.id or 1)

        monkeypatch.setattr("sparkth.core.plugins.service.disabled_plugin_names", _raise_operational_error)

        with (
            patch("sparkth.plugins.compose.routes.completions.get_provider") as get_provider,
            pytest.raises(OperationalError),
        ):
            await _turn(client, config_id, conversation_uuid, "*")

        get_provider.assert_not_called()

    async def _lms_turn(
        self,
        client: AsyncClient,
        session: AsyncSession,
        user_id: int,
        openedx_on: bool,
        canvas_on: bool,
        openedx_system_on: bool = True,
    ) -> tuple[AsyncMock, MagicMock]:
        config_id = await _seed_llm_config(session, user_id)
        conversation_uuid = await _seed_conversation(session, user_id)
        await _seed_lms_plugins(session, user_id, openedx_on, canvas_on, openedx_system_on)
        provider = _provider()
        with (
            patch("sparkth.plugins.compose.routes.completions.get_provider", return_value=provider) as get_provider,
            patch("sparkth.plugins.compose.routes.completions.get_tool_registry", return_value=_lms_registry()),
            patch("sparkth.plugins.compose.routes.completions.complete_turn", new=_turn_answer()) as complete_turn,
        ):
            await _turn(client, config_id, conversation_uuid, "*")
        return complete_turn, get_provider

    async def test_an_lms_switched_off_system_wide_binds_none_of_its_tools(
        self, client: AsyncClient, current_user: User, session: AsyncSession, stub_agent: Agent
    ) -> None:
        complete_turn, _ = await self._lms_turn(client, session, current_user.id or 1, True, True, False)

        assert "openedx_create_xblock" not in _bound_tool_names(complete_turn)

    async def test_an_enabled_plugin_contributes_its_tools_and_agent(
        self, client: AsyncClient, current_user: User, session: AsyncSession, stub_agent: Agent
    ) -> None:
        complete_turn, get_provider = await self._lms_turn(client, session, current_user.id or 1, True, True)

        assert _bound_tool_names(complete_turn) == ["openedx_create_xblock", "canvas_create_course", "stub_build"]
        assert stub_agent in complete_turn.await_args_list[-1].kwargs["planner_setup"].agents

    async def test_no_turn_sends_lms_settings_to_the_model(
        self, client: AsyncClient, current_user: User, session: AsyncSession, stub_agent: Agent
    ) -> None:
        complete_turn, _ = await self._lms_turn(client, session, current_user.id or 1, True, True)

        call = complete_turn.await_args_list[-1]
        agents = call.kwargs["planner_setup"].agents
        prompts = [
            render_planner_prompt(agents, operations=True, existing_plan=None),
            *(render_system_prompt(agent) for agent in agents),
        ]
        sent = [str(call.args[0]), *prompts]
        for value in (*OPENEDX_CONFIG.values(), *CANVAS_CONFIG.values()):
            assert not any(value in text for text in sent)


async def _limit_plugin_use(session: AsyncSession, user_id: int, *plugin_names: str) -> None:
    """Let the user use Compose and the named plugins only."""
    await revoke_role(user_id, PLUGIN_USER_ROLE, GLOBAL, None, session)
    for plugin_name in ("compose", *plugin_names):
        await assign_role(user_id, PLUGIN_USER_ROLE, PLUGIN, plugin_name, session)
    await session.commit()


async def _plugin_use_denials(audit_events: AuditEventsFetcher) -> list[tuple[str | None, str | None]]:
    """The actor id and scope of each ``plugin.use`` denial recorded so far."""
    return [
        (event.actor_id, event.error_detail)
        for event in await audit_events()
        if (event.category, event.action, event.target_id) == ("permission", "denied", PLUGIN_USE.name)
    ]


class TestPluginUsePermission:
    """A turn leaves out the tools and the agent of a plugin its caller may not use."""

    async def _lms_turn(
        self, client: AsyncClient, session: AsyncSession, user_id: int, tools: str | list[str] = "*"
    ) -> AsyncMock:
        config_id = await _seed_llm_config(session, user_id)
        conversation_uuid = await _seed_conversation(session, user_id)
        registry = _lms_registry()
        with (
            patch("sparkth.plugins.compose.routes.completions.get_provider", return_value=_provider()),
            patch("sparkth.plugins.compose.routes.completions.get_tool_registry", return_value=registry),
            patch("sparkth.plugins.compose.routes.completions.complete_turn", new=_turn_answer()) as complete_turn,
        ):
            await _turn(client, config_id, conversation_uuid, tools)
        return complete_turn

    async def test_a_plugin_the_caller_may_not_use_binds_none_of_its_tools(
        self, client: AsyncClient, current_user: User, session: AsyncSession, stub_agent: Agent
    ) -> None:
        await _limit_plugin_use(session, current_user.id or 1, "openedx")

        complete_turn = await self._lms_turn(client, session, current_user.id or 1)

        assert _bound_tool_names(complete_turn) == ["openedx_create_xblock"]

    async def test_a_plugin_the_caller_may_not_use_offers_no_agent(
        self, client: AsyncClient, current_user: User, session: AsyncSession, stub_agent: Agent, other_agent: Agent
    ) -> None:
        await _limit_plugin_use(session, current_user.id or 1, "other")

        complete_turn = await self._lms_turn(client, session, current_user.id or 1)

        agents = complete_turn.await_args_list[-1].kwargs["planner_setup"].agents
        assert other_agent in agents
        assert stub_agent not in agents

    async def test_a_caller_who_may_use_every_plugin_is_offered_every_agent(
        self, client: AsyncClient, current_user: User, session: AsyncSession, stub_agent: Agent, other_agent: Agent
    ) -> None:
        complete_turn = await self._lms_turn(client, session, current_user.id or 1)

        agents = complete_turn.await_args_list[-1].kwargs["planner_setup"].agents
        assert other_agent in agents
        assert stub_agent in agents

    async def test_a_turn_asking_for_every_tool_records_no_denial(
        self,
        client: AsyncClient,
        current_user: User,
        session: AsyncSession,
        stub_agent: Agent,
        audit_events: AuditEventsFetcher,
    ) -> None:
        await _limit_plugin_use(session, current_user.id or 1, "openedx")

        await self._lms_turn(client, session, current_user.id or 1)

        assert await _plugin_use_denials(audit_events) == []

    async def test_a_tool_named_from_a_plugin_the_caller_may_not_use_is_recorded_by_the_caller(
        self,
        client: AsyncClient,
        current_user: User,
        session: AsyncSession,
        stub_agent: Agent,
        audit_events: AuditEventsFetcher,
    ) -> None:
        await _limit_plugin_use(session, current_user.id or 1, "openedx")

        complete_turn = await self._lms_turn(
            client, session, current_user.id or 1, ["canvas_create_course", "openedx_create_xblock"]
        )

        assert _bound_tool_names(complete_turn) == ["openedx_create_xblock"]
        assert await _plugin_use_denials(audit_events) == [(str(current_user.id), "scope=plugin:canvas")]

    async def test_a_tool_named_from_a_switched_off_plugin_records_no_denial(
        self,
        client: AsyncClient,
        current_user: User,
        session: AsyncSession,
        stub_agent: Agent,
        audit_events: AuditEventsFetcher,
    ) -> None:
        await _switch_stub(session, current_user.id or 1, True, False)
        await _limit_plugin_use(session, current_user.id or 1, "openedx")

        complete_turn = await self._lms_turn(client, session, current_user.id or 1, ["stub_build"])

        assert _bound_tool_names(complete_turn) == []
        assert await _plugin_use_denials(audit_events) == []

    async def test_a_caller_who_may_use_every_plugin_records_no_denial(
        self,
        client: AsyncClient,
        current_user: User,
        session: AsyncSession,
        stub_agent: Agent,
        audit_events: AuditEventsFetcher,
    ) -> None:
        complete_turn = await self._lms_turn(client, session, current_user.id or 1, ["canvas_create_course"])

        assert _bound_tool_names(complete_turn) == ["canvas_create_course"]
        assert await _plugin_use_denials(audit_events) == []
