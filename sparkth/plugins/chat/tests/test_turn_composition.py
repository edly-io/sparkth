"""Every turn is answered by one assistant: every enabled section, every requested tool."""

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

from httpx import AsyncClient
from sqlmodel.ext.asyncio.session import AsyncSession

from sparkth.core.models.plugin import Plugin
from sparkth.lib.chat.hooks import ChatCapability
from sparkth.lib.encryption import get_encryption_service
from sparkth.lib.models import LLMConfig, User
from sparkth.lib.settings import get_settings
from sparkth.plugins.chat.capabilities import COURSE_DESIGN
from sparkth.plugins.chat.constants import REFUSAL_MESSAGE
from sparkth.plugins.chat.exceptions import ClassifierError
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


async def _seed_conversation(session: AsyncSession, user_id: int, responsibility: str | None) -> str:
    conversation = Conversation(user_id=user_id, provider="openai", model="gpt-4o", responsibility=responsibility)
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
    return MagicMock(is_in_scope=AsyncMock(return_value=in_scope))


def _tool(name: str) -> MagicMock:
    tool = MagicMock()
    tool.name = name
    return tool


def _registry() -> MagicMock:
    """Two tools: one in a category only course design binds, one in the stub capability's category."""
    registry = MagicMock()
    registry.get_all_tools.return_value = [_tool("openedx_create_xblock"), _tool("stub_build")]
    registry.category_for.side_effect = {"openedx_create_xblock": "openedx-course", "stub_build": "stub-tools"}.get
    return registry


def _bound_tool_names(provider: MagicMock) -> list[str]:
    return [tool.name for tool in provider.send_message.await_args.kwargs["tools"]]


def _system_prompt(get_provider: MagicMock) -> str:
    prompt: str = get_provider.call_args.kwargs["system_prompt"]
    return prompt


def _section(capability: ChatCapability) -> str:
    return f"## {capability.title}\n{capability.prompt}"


async def _turn(client: AsyncClient, config_id: int, conversation_uuid: str | None = None, tools: str = "none") -> Any:
    body: dict[str, Any] = {
        "llm_config_id": config_id,
        "messages": [{"role": "user", "content": "Build it"}],
        "stream": False,
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
        conversation_uuid = await _seed_conversation(session, current_user.id or 1, "stub-job")

        with patch(
            "sparkth.plugins.chat.routes.completions.MessageScopeClassifier", return_value=_classifier_answering(False)
        ):
            response = await _turn(client, config_id, conversation_uuid)

        assert response.json()["message"]["content"] == REFUSAL_MESSAGE

    async def test_a_message_for_another_capability_is_answered_with_every_enabled_section(
        self, client: AsyncClient, current_user: User, session: AsyncSession, stub_capability: ChatCapability
    ) -> None:
        """A course design conversation asked for the stub capability's work is answered, not redirected."""
        config_id = await _seed_llm_config(session, current_user.id or 1)
        conversation_uuid = await _seed_conversation(session, current_user.id or 1, "course-design")
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

    async def test_a_conversation_whose_stored_job_is_switched_off_continues(
        self, client: AsyncClient, current_user: User, session: AsyncSession, stub_capability: ChatCapability
    ) -> None:
        """A row from before the switch-off still stores a job name; the turn ignores it."""
        config_id = await _seed_llm_config(session, current_user.id or 1)
        conversation_uuid = await _seed_conversation(session, current_user.id or 1, "stub-job")
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

    async def test_a_failed_classification_is_answered_with_every_enabled_section(
        self, client: AsyncClient, current_user: User, session: AsyncSession, stub_capability: ChatCapability
    ) -> None:
        config_id = await _seed_llm_config(session, current_user.id or 1)
        conversation_uuid = await _seed_conversation(session, current_user.id or 1, "stub-job")

        with (
            patch("sparkth.plugins.chat.classifiers.base.get_provider"),
            patch(
                "sparkth.plugins.chat.classifiers.message_scope.MessageScopeClassifier.classify",
                new_callable=AsyncMock,
                side_effect=ClassifierError("provider timeout"),
            ),
            patch("sparkth.plugins.chat.routes.completions.get_provider", return_value=_provider()) as get_provider,
        ):
            response = await _turn(client, config_id, conversation_uuid)

        assert response.status_code == 200
        assert _section(COURSE_DESIGN) in _system_prompt(get_provider)
        assert _section(stub_capability) in _system_prompt(get_provider)

    async def test_every_requested_tool_is_bound_whatever_the_capability(
        self, client: AsyncClient, current_user: User, session: AsyncSession, stub_capability: ChatCapability
    ) -> None:
        config_id = await _seed_llm_config(session, current_user.id or 1)
        conversation_uuid = await _seed_conversation(session, current_user.id or 1, None)
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
