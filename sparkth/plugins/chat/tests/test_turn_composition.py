"""Every turn is answered by one assistant: every enabled section, every requested tool."""

import json
from collections.abc import AsyncGenerator
from typing import Any, cast
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy.exc import OperationalError
from sqlmodel.ext.asyncio.session import AsyncSession

from sparkth.core.models.plugin import Plugin, UserPlugin
from sparkth.lib.chat.hooks import ChatCapability
from sparkth.lib.encryption import get_encryption_service
from sparkth.lib.models import LLMConfig, User
from sparkth.lib.settings import get_settings
from sparkth.plugins.chat.capabilities import COURSE_DESIGN
from sparkth.plugins.chat.constants import REFUSAL_MESSAGE
from sparkth.plugins.chat.models import Conversation

COMPLETIONS_URL = "/api/v1/chat/completions"


async def _seed_llm_config(session: AsyncSession, user_id: int) -> int:
    enc = get_encryption_service(get_settings().LLM_ENCRYPTION_KEY)
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
    provider.system_prompt = ""
    provider.send_message = AsyncMock(return_value={"content": "On it.", "metadata": {}})
    return provider


def _classifier_answering(in_scope: bool) -> MagicMock:
    return MagicMock(in_scope=AsyncMock(return_value=in_scope))


def _tool(name: str) -> MagicMock:
    tool = MagicMock()
    tool.name = name
    return tool


def _registry() -> MagicMock:
    """Two tools from two plugins; every turn may bind both."""
    registry = MagicMock()
    registry.plugin_for.side_effect = {"openedx_create_xblock": "open-edx", "stub_build": "stub"}.get
    registry.get_all_tools.return_value = [_tool("openedx_create_xblock"), _tool("stub_build")]
    return registry


def _bound_tool_names(provider: MagicMock) -> list[str]:
    return [tool.name for tool in provider.send_message.await_args.kwargs["tools"]]


def _system_prompt(get_provider: MagicMock) -> str:
    prompt: str = get_provider.call_args.kwargs["system_prompt"]
    return prompt


def _section(capability: ChatCapability) -> str:
    return f"## {capability.title}\n{capability.prompt}"


async def _turn(
    client: AsyncClient,
    config_id: int,
    conversation_uuid: str | None = None,
    tools: str = "none",
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


class TestOneAssistantPerTurn:
    async def test_an_out_of_scope_message_is_refused(
        self, client: AsyncClient, current_user: User, session: AsyncSession, stub_capability: ChatCapability
    ) -> None:
        config_id = await _seed_llm_config(session, current_user.id or 1)
        conversation_uuid = await _seed_conversation(session, current_user.id or 1)

        with patch(
            "sparkth.plugins.chat.routes.completions.MessageScopeClassifier", return_value=_classifier_answering(False)
        ):
            response = await _turn(client, config_id, conversation_uuid)

        assert response.json()["message"]["content"] == REFUSAL_MESSAGE

    async def test_a_message_for_another_capability_is_answered_with_every_enabled_section(
        self, client: AsyncClient, current_user: User, session: AsyncSession, stub_capability: ChatCapability
    ) -> None:
        """A message for the stub capability is answered with every enabled section."""
        config_id = await _seed_llm_config(session, current_user.id or 1)
        conversation_uuid = await _seed_conversation(session, current_user.id or 1)
        provider = _provider()

        with (
            patch(
                "sparkth.plugins.chat.routes.completions.MessageScopeClassifier",
                return_value=_classifier_answering(True),
            ),
            patch("sparkth.plugins.chat.routes.completions.get_provider", return_value=provider) as get_provider,
        ):
            response = await _turn(client, config_id, conversation_uuid)

        assert response.json()["message"]["content"] == "On it."
        assert _section(COURSE_DESIGN) in _system_prompt(get_provider)
        assert _section(stub_capability) in _system_prompt(get_provider)

    async def test_a_first_message_is_answered_with_every_enabled_section(
        self, client: AsyncClient, current_user: User, session: AsyncSession, stub_capability: ChatCapability
    ) -> None:
        config_id = await _seed_llm_config(session, current_user.id or 1)

        with (
            patch(
                "sparkth.plugins.chat.routes.completions.MessageScopeClassifier",
                return_value=_classifier_answering(True),
            ),
            patch("sparkth.plugins.chat.routes.completions.get_provider", return_value=_provider()) as get_provider,
            patch("sparkth.plugins.chat.conversation_title.generate_conversation_title"),
        ):
            response = await _turn(client, config_id)

        assert response.status_code == 200
        assert _section(stub_capability) in _system_prompt(get_provider)

    async def test_a_conversation_continues_after_a_plugin_is_switched_off(
        self, client: AsyncClient, current_user: User, session: AsyncSession, stub_capability: ChatCapability
    ) -> None:
        """Switching a plugin off removes its section; the conversation goes on."""
        config_id = await _seed_llm_config(session, current_user.id or 1)
        conversation_uuid = await _seed_conversation(session, current_user.id or 1)
        session.add(Plugin(name="stub", enabled=False))
        await session.commit()
        provider = _provider()

        with (
            patch(
                "sparkth.plugins.chat.routes.completions.MessageScopeClassifier",
                return_value=_classifier_answering(True),
            ),
            patch("sparkth.plugins.chat.routes.completions.get_provider", return_value=provider) as get_provider,
        ):
            response = await _turn(client, config_id, conversation_uuid)

        assert response.status_code == 200
        provider.send_message.assert_awaited_once()
        assert _section(stub_capability) not in _system_prompt(get_provider)

    async def test_every_requested_tool_is_bound_whatever_the_capability(
        self, client: AsyncClient, current_user: User, session: AsyncSession, stub_capability: ChatCapability
    ) -> None:
        config_id = await _seed_llm_config(session, current_user.id or 1)
        conversation_uuid = await _seed_conversation(session, current_user.id or 1)
        provider = _provider()

        with (
            patch(
                "sparkth.plugins.chat.routes.completions.MessageScopeClassifier",
                return_value=_classifier_answering(True),
            ),
            patch("sparkth.plugins.chat.routes.completions.get_provider", return_value=provider),
            patch("sparkth.plugins.chat.routes.completions.get_tool_registry", return_value=_registry()),
        ):
            await _turn(client, config_id, conversation_uuid, "*")

        assert _bound_tool_names(provider) == ["openedx_create_xblock", "stub_build"]


async def _switch_stub(session: AsyncSession, user_id: int, system_on: bool, user_on: bool | None) -> None:
    """Seed the ``stub`` plugin's system switch and, when given, this user's own switch."""
    plugin = Plugin(name="stub", enabled=system_on)
    session.add(plugin)
    await session.flush()
    if user_on is not None:
        session.add(UserPlugin(user_id=user_id, plugin_id=cast(int, plugin.id), enabled=user_on))
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
            patch(
                "sparkth.plugins.chat.routes.completions.MessageScopeClassifier",
                return_value=_classifier_answering(True),
            ),
            patch("sparkth.plugins.chat.routes.completions.get_provider", return_value=provider),
            patch("sparkth.plugins.chat.routes.completions.get_tool_registry", return_value=_registry()),
        ):
            await _turn(client, config_id, conversation_uuid, "*")
        return _bound_tool_names(provider)

    async def test_a_plugin_the_user_switched_off_binds_none_of_its_tools(
        self, client: AsyncClient, current_user: User, session: AsyncSession, stub_capability: ChatCapability
    ) -> None:
        bound = await self._bound_after(client, session, current_user.id or 1, True, False)

        assert bound == ["openedx_create_xblock"]

    async def test_a_plugin_switched_off_system_wide_binds_none_of_its_tools(
        self, client: AsyncClient, current_user: User, session: AsyncSession, stub_capability: ChatCapability
    ) -> None:
        bound = await self._bound_after(client, session, current_user.id or 1, False, None)

        assert bound == ["openedx_create_xblock"]

    async def test_an_enabled_plugin_keeps_its_tools(
        self, client: AsyncClient, current_user: User, session: AsyncSession, stub_capability: ChatCapability
    ) -> None:
        bound = await self._bound_after(client, session, current_user.id or 1, True, True)

        assert bound == ["openedx_create_xblock", "stub_build"]

    async def test_a_streamed_turn_binds_the_same_filtered_tools(
        self, client: AsyncClient, current_user: User, session: AsyncSession, stub_capability: ChatCapability
    ) -> None:
        user_id = current_user.id or 1
        config_id = await _seed_llm_config(session, user_id)
        conversation_uuid = await _seed_conversation(session, user_id)
        await _switch_stub(session, user_id, True, False)

        with (
            patch(
                "sparkth.plugins.chat.routes.completions.MessageScopeClassifier",
                return_value=_classifier_answering(True),
            ),
            patch("sparkth.plugins.chat.routes.completions.get_provider", return_value=_provider()),
            patch("sparkth.plugins.chat.routes.completions.get_tool_registry", return_value=_registry()),
            patch("sparkth.plugins.chat.routes.completions.ChatStreamProcessor") as processor_cls,
        ):
            processor_cls.return_value.stream.return_value = _fake_stream()
            await _turn(client, config_id, conversation_uuid, "*", stream=True)

        assert [tool.name for tool in processor_cls.call_args.args[4]] == ["openedx_create_xblock"]

    async def test_a_failed_switch_lookup_never_reaches_the_model(
        self,
        client: AsyncClient,
        current_user: User,
        session: AsyncSession,
        stub_capability: ChatCapability,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        config_id = await _seed_llm_config(session, current_user.id or 1)
        conversation_uuid = await _seed_conversation(session, current_user.id or 1)

        monkeypatch.setattr(
            "sparkth.plugins.chat.routes.completions.plugins_disabled_for_user", _raise_operational_error
        )

        with (
            patch("sparkth.plugins.chat.routes.completions.get_provider") as get_provider,
            pytest.raises(OperationalError),
        ):
            await _turn(client, config_id, conversation_uuid, "*")

        get_provider.assert_not_called()
