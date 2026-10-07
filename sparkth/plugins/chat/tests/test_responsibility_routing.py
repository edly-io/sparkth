"""A conversation does one job: chosen on its first message, followed on every later turn."""

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID

from httpx import AsyncClient
from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from sparkth.core.models.plugin import Plugin
from sparkth.lib.chat.hooks import ChatResponsibility
from sparkth.lib.encryption import get_encryption_service
from sparkth.lib.models import LLMConfig, User
from sparkth.lib.settings import get_settings
from sparkth.plugins.chat.constants import REFUSAL_MESSAGE
from sparkth.plugins.chat.exceptions import ClassifierError
from sparkth.plugins.chat.models import Conversation
from sparkth.plugins.chat.prompt import render_system_prompt
from sparkth.plugins.chat.responsibilities import COURSE_DESIGN

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


def _classifier_answering(responsibility: str | None) -> MagicMock:
    return MagicMock(responsibility_for=AsyncMock(return_value=responsibility))


def _tool(name: str) -> MagicMock:
    tool = MagicMock()
    tool.name = name
    return tool


def _registry() -> MagicMock:
    """Two tools: one in a category only course design binds, one in the stub job's category."""
    registry = MagicMock()
    registry.get_all_tools.return_value = [_tool("openedx_create_xblock"), _tool("stub_build")]
    registry.category_for.side_effect = {"openedx_create_xblock": "openedx-course", "stub_build": "stub-tools"}.get
    return registry


def _bound_tool_names(provider: MagicMock) -> list[str]:
    return [tool.name for tool in provider.send_message.await_args.kwargs["tools"]]


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


async def _stored_job(session: AsyncSession, conversation_uuid: str) -> str | None:
    session.expire_all()
    result = await session.exec(select(Conversation).where(col(Conversation.uuid) == UUID(conversation_uuid)))
    return result.one().responsibility


class TestTheFirstMessageChoosesTheJob:
    async def test_the_classified_job_is_stored_on_the_new_conversation(
        self, client: AsyncClient, current_user: User, session: AsyncSession, stub_job: ChatResponsibility
    ) -> None:
        config_id = await _seed_llm_config(session, current_user.id or 1)

        with (
            patch(
                "sparkth.plugins.chat.routes.completions.MessageScopeClassifier",
                return_value=_classifier_answering("stub-job"),
            ),
            patch("sparkth.plugins.chat.routes.completions.get_provider", return_value=_provider()),
            patch("sparkth.plugins.chat.conversation_title.generate_conversation_title"),
        ):
            response = await _turn(client, config_id)

        assert response.status_code == 200
        assert await _stored_job(session, response.json()["conversation_id"]) == "stub-job"

    async def test_a_failed_classification_stores_course_design(
        self, client: AsyncClient, current_user: User, session: AsyncSession, stub_job: ChatResponsibility
    ) -> None:
        config_id = await _seed_llm_config(session, current_user.id or 1)

        with (
            patch("sparkth.plugins.chat.classifiers.base.get_provider"),
            patch(
                "sparkth.plugins.chat.classifiers.message_scope.MessageScopeClassifier.classify",
                new_callable=AsyncMock,
                side_effect=ClassifierError("provider timeout"),
            ),
            patch("sparkth.plugins.chat.routes.completions.get_provider", return_value=_provider()),
            patch("sparkth.plugins.chat.conversation_title.generate_conversation_title"),
        ):
            response = await _turn(client, config_id)

        assert response.status_code == 200
        assert await _stored_job(session, response.json()["conversation_id"]) == "course-design"


class TestLaterTurnsFollowTheStoredJob:
    async def test_no_job_is_refused(
        self, client: AsyncClient, current_user: User, session: AsyncSession, stub_job: ChatResponsibility
    ) -> None:
        config_id = await _seed_llm_config(session, current_user.id or 1)
        conversation_uuid = await _seed_conversation(session, current_user.id or 1, "stub-job")

        with patch(
            "sparkth.plugins.chat.routes.completions.MessageScopeClassifier", return_value=_classifier_answering(None)
        ):
            response = await _turn(client, config_id, conversation_uuid)

        assert response.json()["message"]["content"] == REFUSAL_MESSAGE

    async def test_a_failed_classification_keeps_the_stored_job(
        self, client: AsyncClient, current_user: User, session: AsyncSession, stub_job: ChatResponsibility
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
            patch("sparkth.plugins.chat.routes.completions.get_provider", return_value=_provider()),
            patch("sparkth.plugins.chat.routes.completions.render_system_prompt", wraps=render_system_prompt) as render,
        ):
            response = await _turn(client, config_id, conversation_uuid)

        assert response.status_code == 200
        assert render.call_args.args[0] is stub_job

    async def test_a_conversation_whose_plugin_is_switched_off_runs_as_course_design(
        self, client: AsyncClient, current_user: User, session: AsyncSession, stub_job: ChatResponsibility
    ) -> None:
        """Switching off the plugin that registered a job leaves its conversations usable."""
        config_id = await _seed_llm_config(session, current_user.id or 1)
        conversation_uuid = await _seed_conversation(session, current_user.id or 1, "stub-job")
        session.add(Plugin(name="stub", enabled=False))
        await session.commit()

        with (
            patch(
                "sparkth.plugins.chat.routes.completions.MessageScopeClassifier",
                return_value=_classifier_answering("course-design"),
            ),
            patch("sparkth.plugins.chat.routes.completions.get_provider", return_value=_provider()),
            patch("sparkth.plugins.chat.routes.completions.render_system_prompt", wraps=render_system_prompt) as render,
        ):
            response = await _turn(client, config_id, conversation_uuid)

        assert response.json()["message"]["content"] == "On it."
        assert render.call_args.args[0] == COURSE_DESIGN

    async def test_the_stored_job_decides_which_tools_are_bound(
        self, client: AsyncClient, current_user: User, session: AsyncSession, stub_job: ChatResponsibility
    ) -> None:
        config_id = await _seed_llm_config(session, current_user.id or 1)
        conversation_uuid = await _seed_conversation(session, current_user.id or 1, "stub-job")
        provider = _provider()

        with (
            patch(
                "sparkth.plugins.chat.routes.completions.MessageScopeClassifier",
                return_value=_classifier_answering("stub-job"),
            ),
            patch("sparkth.plugins.chat.routes.completions.get_provider", return_value=provider),
            patch("sparkth.plugins.chat.routes.completions.get_tool_registry", return_value=_registry()),
        ):
            await _turn(client, config_id, conversation_uuid, "*")

        assert _bound_tool_names(provider) == ["stub_build"]

    async def test_a_switched_off_jobs_tools_are_not_bound_by_course_design(
        self, client: AsyncClient, current_user: User, session: AsyncSession, stub_job: ChatResponsibility
    ) -> None:
        config_id = await _seed_llm_config(session, current_user.id or 1)
        conversation_uuid = await _seed_conversation(session, current_user.id or 1, None)
        session.add(Plugin(name="stub", enabled=False))
        await session.commit()
        provider = _provider()

        with (
            patch(
                "sparkth.plugins.chat.routes.completions.MessageScopeClassifier",
                return_value=_classifier_answering("course-design"),
            ),
            patch("sparkth.plugins.chat.routes.completions.get_provider", return_value=provider),
            patch("sparkth.plugins.chat.routes.completions.get_tool_registry", return_value=_registry()),
        ):
            await _turn(client, config_id, conversation_uuid, "*")

        assert _bound_tool_names(provider) == ["openedx_create_xblock"]
