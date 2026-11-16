"""
Tests for the conversation UUID feature:
  - Conversation model auto-generates UUIDv7
  - ComposeService.get_conversation_by_uuid lookups
  - Schemas expose UUID instead of int IDs
  - API routes accept/return UUIDs for conversations
  - Reads and turns are checked at the conversation owner's user scope
"""

from datetime import datetime, timezone
from typing import Any, cast
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

import httpx
import pytest
from langchain_core.messages import AIMessage
from langchain_core.tools import StructuredTool
from pydantic import ValidationError
from sqlalchemy import delete
from sqlalchemy import select as sa_select
from sqlalchemy.ext.asyncio import AsyncSession as SQLAlchemyAsyncSession
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession
from uuid6 import uuid7

from sparkth.core.analytics.models import raw_events
from sparkth.core.permissions.models import RoleAssignment
from sparkth.lib.audit import audited_tool
from sparkth.lib.audit.callbacks import AUDIT_AT_HANDLER_TAG
from sparkth.lib.compose.hooks import Agent
from sparkth.lib.documents import Document, DocumentStatus
from sparkth.lib.llm import get_llm_service, get_provider
from sparkth.lib.permissions.scopes import GLOBAL, USER
from sparkth.lib.testing import AuditEventsFetcher, ScriptedChatModel, grant_permission_at_scope
from sparkth.main import app
from sparkth.plugins.compose.config import get_compose_settings
from sparkth.plugins.compose.detached import join_live_tasks
from sparkth.plugins.compose.models import Conversation, Message  # noqa: F401 used in route fixture tests
from sparkth.plugins.compose.schemas import (
    ChatCompletionRequest,
    ChatCompletionResponse,
    ChatMessage,
    ConversationResponse,
)
from sparkth.plugins.compose.service import ComposeService, get_compose_service
from sparkth.plugins.compose.tests.helpers import (
    answering_model,
    hand_off,
    planning,
    seed_llm_config,
    stored_messages,
)

# ===========================================================================
# Conversation model — UUID field
# ===========================================================================


class TestConversationModelUUID:
    def test_uuid_auto_generated_on_instantiation(self) -> None:
        conv = Conversation(user_id=1, provider="openai", model="gpt-4o")
        assert isinstance(conv.uuid, UUID)

    def test_uuid_is_unique_across_instances(self) -> None:
        conv_a = Conversation(user_id=1, provider="openai", model="gpt-4o")
        conv_b = Conversation(user_id=1, provider="openai", model="gpt-4o")
        assert conv_a.uuid != conv_b.uuid

    def test_uuid_can_be_set_explicitly(self) -> None:
        explicit = uuid7()
        conv = Conversation(user_id=1, provider="openai", model="gpt-4o", uuid=explicit)
        assert conv.uuid == explicit

    def test_uuid_is_version_7(self) -> None:
        conv = Conversation(user_id=1, provider="openai", model="gpt-4o")
        assert conv.uuid.version == 7


# ===========================================================================
# ComposeService.get_conversation_by_uuid
# ===========================================================================


class TestGetConversationByUUID:
    async def test_returns_conversation_matching_uuid_whoever_owns_it(self, session: "AsyncSession") -> None:
        svc = ComposeService()
        conv = Conversation(user_id=42, provider="openai", model="gpt-4o")
        session.add(conv)
        await session.commit()
        await session.refresh(conv)

        result = await svc.get_conversation_by_uuid(session, uuid=conv.uuid)
        assert result is not None
        assert result.id == conv.id
        assert result.uuid == conv.uuid

    async def test_returns_none_for_nonexistent_uuid(self, session: "AsyncSession") -> None:
        svc = ComposeService()
        result = await svc.get_conversation_by_uuid(session, uuid=uuid4())
        assert result is None


# ===========================================================================
# Schema — UUID types
# ===========================================================================


class TestConversationUUIDSchemas:
    def test_chat_completion_request_accepts_uuid_conversation_id(self) -> None:
        uid = uuid7()
        req = ChatCompletionRequest(
            llm_config_id=1,
            messages=[ChatMessage(role="user", content="hello")],
            conversation_id=uid,
        )
        assert req.conversation_id == uid

    def test_chat_completion_request_accepts_none_conversation_id(self) -> None:
        req = ChatCompletionRequest(
            llm_config_id=1,
            messages=[ChatMessage(role="user", content="hello")],
        )
        assert req.conversation_id is None

    def test_chat_completion_request_accepts_uuid_string(self) -> None:
        uid = uuid7()
        req = ChatCompletionRequest(
            llm_config_id=1,
            messages=[ChatMessage(role="user", content="hello")],
            conversation_id=str(uid),  # type: ignore[arg-type]
        )
        assert req.conversation_id == uid

    def test_chat_completion_request_rejects_integer_conversation_id(self) -> None:
        with pytest.raises(ValidationError):
            ChatCompletionRequest(
                llm_config_id=1,
                messages=[ChatMessage(role="user", content="hello")],
                conversation_id=123,  # type: ignore[arg-type]
            )

    def test_chat_completion_response_conversation_id_is_uuid(self) -> None:
        uid = uuid7()
        resp = ChatCompletionResponse(
            message=ChatMessage(role="assistant", content="hi"),
            conversation_id=uid,
            model="gpt-4o",
            provider="openai",
        )
        assert isinstance(resp.conversation_id, UUID)
        assert resp.conversation_id == uid

    def test_conversation_response_id_is_uuid(self) -> None:
        uid = uuid7()
        now = datetime.now(timezone.utc)
        resp = ConversationResponse(
            id=uid,
            provider="openai",
            model="gpt-4o",
            title=None,
            total_tokens_used=0,
            total_cost=0.0,
            message_count=0,
            created_at=now,
            updated_at=now,
        )
        assert isinstance(resp.id, UUID)
        assert resp.id == uid


# ===========================================================================
# API routes — conversations expose UUIDs
# ===========================================================================


class TestConversationUUIDRoutes:
    @pytest.fixture(autouse=True)
    def _override_compose_deps(self, client: httpx.AsyncClient) -> None:  # noqa: PT004
        """Override chat dependencies so route tests don't need real env vars."""
        mock_config = MagicMock()
        mock_config.max_tool_executions = 50
        mock_config.title_max_length = 60

        mock_service = ComposeService()

        mock_llm_config = MagicMock()
        mock_llm_config.provider = "openai"
        mock_llm_config.model = "gpt-4o"

        mock_llm_service = AsyncMock()
        mock_llm_service.get = AsyncMock(return_value=mock_llm_config)
        mock_llm_service.resolve = AsyncMock(return_value=(mock_llm_config, "sk-fake-key"))

        app.dependency_overrides[get_compose_settings] = lambda: mock_config
        app.dependency_overrides[get_compose_service] = lambda: mock_service
        app.dependency_overrides[get_llm_service] = lambda: mock_llm_service

    async def test_list_conversations_returns_uuids(
        self, client: "httpx.AsyncClient", current_user: MagicMock, session: "AsyncSession"
    ) -> None:
        conv = Conversation(user_id=current_user.id, provider="openai", model="gpt-4o")
        session.add(conv)
        await session.commit()
        await session.refresh(conv)

        response = await client.get("/api/v1/compose/conversations")
        assert response.status_code == 200
        body = response.json()
        assert body["total"] >= 1

        conv_data = body["conversations"][0]
        returned_id = conv_data["id"]
        # Should be a valid UUID string, not an integer
        parsed = UUID(returned_id)
        assert parsed == conv.uuid

    async def test_get_conversation_by_uuid(
        self, client: "httpx.AsyncClient", current_user: MagicMock, session: "AsyncSession"
    ) -> None:
        conv = Conversation(user_id=current_user.id, provider="openai", model="gpt-4o")
        session.add(conv)
        await session.commit()
        await session.refresh(conv)

        response = await client.get(f"/api/v1/compose/conversations/{conv.uuid}")
        assert response.status_code == 200
        body = response.json()
        assert UUID(body["id"]) == conv.uuid
        assert body["provider"] == "openai"
        assert body["model"] == "gpt-4o"

    async def test_get_conversation_by_uuid_not_found(
        self, client: "httpx.AsyncClient", current_user: MagicMock
    ) -> None:
        fake_uuid = uuid4()
        response = await client.get(f"/api/v1/compose/conversations/{fake_uuid}")
        assert response.status_code == 404

    async def test_get_conversation_by_integer_returns_422(
        self, client: "httpx.AsyncClient", current_user: MagicMock
    ) -> None:
        response = await client.get("/api/v1/compose/conversations/123")
        assert response.status_code == 422

    async def test_get_conversation_wrong_user_returns_403(
        self, client: "httpx.AsyncClient", current_user: MagicMock, session: "AsyncSession"
    ) -> None:
        conv = Conversation(user_id=99999, provider="openai", model="gpt-4o")
        session.add(conv)
        await session.commit()
        await session.refresh(conv)

        response = await client.get(f"/api/v1/compose/conversations/{conv.uuid}")
        assert response.status_code == 403

    async def test_completions_returns_uuid_conversation_id(
        self, client: "httpx.AsyncClient", current_user: MagicMock, session: "AsyncSession"
    ) -> None:
        mock_response: dict[str, Any] = {
            "content": "Hello!",
            "role": "assistant",
            "model": "gpt-4o",
            "tool_calls": None,
            "metadata": {},
        }

        mock_message = Message(id=1, conversation_id=1, role="assistant", content="Hello!")

        with (
            patch("sparkth.plugins.compose.routes.completions.get_provider") as mock_get_provider,
            patch("sparkth.plugins.compose.conversation_title.generate_conversation_title"),
            patch(
                "sparkth.plugins.compose.service.ComposeService.add_message", new_callable=AsyncMock
            ) as mock_add_message,
        ):
            mock_provider = MagicMock()
            mock_provider.create_llm.return_value = answering_model(mock_response["content"])
            mock_get_provider.return_value = mock_provider
            mock_add_message.return_value = mock_message

            response = await client.post(
                "/api/v1/compose/completions",
                json={
                    "llm_config_id": 1,
                    "messages": [{"role": "user", "content": "hi"}],
                    "tools": "none",
                },
            )

        assert response.status_code == 200
        body = response.json()
        # conversation_id should be a valid UUID
        UUID(body["conversation_id"])

    async def test_completions_with_existing_uuid_conversation(
        self, client: "httpx.AsyncClient", current_user: MagicMock, session: "AsyncSession"
    ) -> None:
        conv = Conversation(
            user_id=current_user.id,
            provider="openai",
            model="gpt-4o",
        )
        session.add(conv)
        await session.commit()
        await session.refresh(conv)
        conv_uuid = conv.uuid

        mock_response: dict[str, Any] = {
            "content": "Hello again!",
            "role": "assistant",
            "model": "gpt-4o",
            "tool_calls": None,
            "metadata": {},
        }

        mock_message = Message(id=1, conversation_id=conv.id, role="assistant", content="Hello again!")  # type: ignore[arg-type]

        with (
            patch("sparkth.plugins.compose.routes.completions.get_provider") as mock_get_provider,
            patch(
                "sparkth.plugins.compose.service.ComposeService.add_message", new_callable=AsyncMock
            ) as mock_add_message,
        ):
            mock_provider = MagicMock()
            mock_provider.create_llm.return_value = answering_model(mock_response["content"])
            mock_get_provider.return_value = mock_provider
            mock_add_message.return_value = mock_message

            response = await client.post(
                "/api/v1/compose/completions",
                json={
                    "llm_config_id": 1,
                    "messages": [{"role": "user", "content": "hello again"}],
                    "conversation_id": str(conv_uuid),
                    "tools": "none",
                },
            )

        assert response.status_code == 200
        body = response.json()
        assert UUID(body["conversation_id"]) == conv_uuid

    async def test_completions_with_nonexistent_uuid_returns_404(
        self,
        client: "httpx.AsyncClient",
        current_user: MagicMock,
        session: "AsyncSession",
    ) -> None:
        response = await client.post(
            "/api/v1/compose/completions",
            json={
                "llm_config_id": 1,
                "messages": [{"role": "user", "content": "hi"}],
                "conversation_id": str(uuid4()),
                "tools": "none",
            },
        )
        assert response.status_code == 404

    async def test_completions_with_integer_conversation_id_returns_422(
        self, client: "httpx.AsyncClient", current_user: MagicMock
    ) -> None:
        response = await client.post(
            "/api/v1/compose/completions",
            json={
                "llm_config_id": 1,
                "messages": [{"role": "user", "content": "hi"}],
                "conversation_id": 123,
            },
        )
        assert response.status_code == 422


def test_conversation_model_has_no_system_prompt_field() -> None:
    """The column was write-only and always NULL; it must not come back."""
    assert "system_prompt" not in Conversation.model_fields


# ===========================================================================
# Read gate — compose.conversation.read at the owner's user scope
# ===========================================================================

OWNER_ID = 2
THIRD_ID = 3
READ = "compose.conversation.read"
BY_ID_SUFFIXES = ["", "/last-message", "/attachments"]


@pytest.fixture
def _compose_service(client: httpx.AsyncClient) -> None:  # noqa: PT004
    app.dependency_overrides[get_compose_service] = lambda: ComposeService()


async def _owned_by(session: AsyncSession, user_id: int) -> UUID:
    conv = Conversation(user_id=user_id, provider="openai", model="gpt-4o", title=f"owned by {user_id}")
    session.add(conv)
    await session.commit()
    await session.refresh(conv)
    return conv.uuid


async def _drop_caller_assignment(session: AsyncSession) -> None:
    await session.exec(delete(RoleAssignment))
    await session.commit()


@pytest.mark.usefixtures("_compose_service")
class TestConversationReadGate:
    @pytest.mark.parametrize("suffix", BY_ID_SUFFIXES)
    async def test_own_record_without_a_grant_is_403(
        self, client: httpx.AsyncClient, current_user: MagicMock, session: AsyncSession, suffix: str
    ) -> None:
        conv_uuid = await _owned_by(session, 1)
        await _drop_caller_assignment(session)

        assert (await client.get(f"/api/v1/compose/conversations/{conv_uuid}{suffix}")).status_code == 403

    @pytest.mark.parametrize("suffix", BY_ID_SUFFIXES)
    async def test_another_users_record_is_403_and_audited(
        self,
        client: httpx.AsyncClient,
        current_user: MagicMock,
        session: AsyncSession,
        audit_events: AuditEventsFetcher,
        suffix: str,
    ) -> None:
        conv_uuid = await _owned_by(session, OWNER_ID)

        assert (await client.get(f"/api/v1/compose/conversations/{conv_uuid}{suffix}")).status_code == 403

        (event,) = await audit_events()
        assert event.action == "denied"
        assert event.target_id == READ
        assert event.error_detail == f"scope=user:{OWNER_ID}"

    @pytest.mark.parametrize("suffix", BY_ID_SUFFIXES)
    @pytest.mark.parametrize("scope_id", [None, str(OWNER_ID)])
    async def test_grant_at_global_or_owner_reaches_it(
        self,
        client: httpx.AsyncClient,
        current_user: MagicMock,
        session: AsyncSession,
        suffix: str,
        scope_id: str | None,
    ) -> None:
        conv_uuid = await _owned_by(session, OWNER_ID)
        await grant_permission_at_scope(session, 1, READ, GLOBAL if scope_id is None else USER, scope_id)
        await session.commit()

        response = await client.get(f"/api/v1/compose/conversations/{conv_uuid}{suffix}")

        assert response.status_code == 200
        if suffix == "":
            assert response.json()["title"] == f"owned by {OWNER_ID}"

    @pytest.mark.parametrize("suffix", BY_ID_SUFFIXES)
    async def test_grant_at_a_third_user_is_403(
        self, client: httpx.AsyncClient, current_user: MagicMock, session: AsyncSession, suffix: str
    ) -> None:
        conv_uuid = await _owned_by(session, OWNER_ID)
        await grant_permission_at_scope(session, 1, READ, USER, str(THIRD_ID))
        await session.commit()

        assert (await client.get(f"/api/v1/compose/conversations/{conv_uuid}{suffix}")).status_code == 403

    @pytest.mark.parametrize("suffix", BY_ID_SUFFIXES)
    async def test_unknown_uuid_is_404_without_a_denial_row(
        self,
        client: httpx.AsyncClient,
        current_user: MagicMock,
        session: AsyncSession,
        audit_events: AuditEventsFetcher,
        suffix: str,
    ) -> None:
        await _drop_caller_assignment(session)

        assert (await client.get(f"/api/v1/compose/conversations/{uuid4()}{suffix}")).status_code == 404
        assert await audit_events() == []

    async def test_list_shows_only_the_callers_even_with_a_global_grant(
        self, client: httpx.AsyncClient, current_user: MagicMock, session: AsyncSession
    ) -> None:
        await _owned_by(session, 1)
        await _owned_by(session, OWNER_ID)
        await grant_permission_at_scope(session, 1, READ, GLOBAL)
        await session.commit()

        body = (await client.get("/api/v1/compose/conversations")).json()

        assert [c["title"] for c in body["conversations"]] == ["owned by 1"]

    async def test_list_of_another_owner_needs_a_grant(
        self, client: httpx.AsyncClient, current_user: MagicMock, session: AsyncSession
    ) -> None:
        await _owned_by(session, OWNER_ID)

        response = await client.get(f"/api/v1/compose/conversations?owner_id={OWNER_ID}")

        assert response.status_code == 403

    @pytest.mark.parametrize("scope_id", [None, str(OWNER_ID)])
    async def test_list_of_another_owner_with_a_grant(
        self, client: httpx.AsyncClient, current_user: MagicMock, session: AsyncSession, scope_id: str | None
    ) -> None:
        await _owned_by(session, 1)
        await _owned_by(session, OWNER_ID)
        await grant_permission_at_scope(session, 1, READ, GLOBAL if scope_id is None else USER, scope_id)
        await session.commit()

        body = (await client.get(f"/api/v1/compose/conversations?owner_id={OWNER_ID}")).json()

        assert [c["title"] for c in body["conversations"]] == [f"owned by {OWNER_ID}"]

    async def test_list_of_a_user_with_no_conversations_is_empty(
        self, client: httpx.AsyncClient, current_user: MagicMock, session: AsyncSession
    ) -> None:
        await grant_permission_at_scope(session, 1, READ, GLOBAL)
        await session.commit()

        body = (await client.get("/api/v1/compose/conversations?owner_id=999999")).json()

        assert body == {"conversations": [], "total": 0}


# ===========================================================================
# Write gate — compose.conversation.write on a turn, at the owner's user scope
# ===========================================================================

WRITE = "compose.conversation.write"
COMPLETIONS_URL = "/api/v1/compose/completions"


def _turn(llm_config_id: int, conversation_uuid: UUID | None = None, stream: bool = False) -> dict[str, Any]:
    body: dict[str, Any] = {
        "llm_config_id": llm_config_id,
        "messages": [{"role": "user", "content": "Add a module on consent"}],
        "stream": stream,
        "tools": "none",
    }
    if conversation_uuid is not None:
        body["conversation_id"] = str(conversation_uuid)
    return body


def _answering_provider() -> MagicMock:
    provider = MagicMock()
    provider.model = "gpt-4o"
    provider.create_llm.return_value = answering_model("Module added.")
    provider.send_message = AsyncMock(return_value={"content": "Consent module", "metadata": {}})
    return provider


async def lookup_course(course_id: int) -> dict[str, Any]:
    """Look up a course."""
    return {"course_id": course_id}


def _tool_calling_model() -> ScriptedChatModel:
    """Calls the audited tool once, then answers."""
    call = AIMessage(content="", tool_calls=[{"name": "lookup_course", "args": {"course_id": 5}, "id": "call_1"}])
    return ScriptedChatModel(messages=iter([call, AIMessage(content="Module added.")]), disable_streaming=True)


class TestTurnWriteGate:
    async def test_first_message_starts_a_conversation_owned_by_the_caller(
        self, client: httpx.AsyncClient, current_user: MagicMock, session: AsyncSession
    ) -> None:
        config_id = await seed_llm_config(session, 1)

        with (
            patch("sparkth.plugins.compose.routes.completions.get_provider", return_value=_answering_provider()),
            patch("sparkth.plugins.compose.conversation_title.get_provider", return_value=_answering_provider()),
        ):
            response = await client.post(COMPLETIONS_URL, json=_turn(config_id))

        assert response.status_code == 200
        conversation = (await session.exec(select(Conversation))).one()
        assert (str(conversation.uuid), conversation.user_id) == (response.json()["conversation_id"], 1)

    async def test_first_message_without_a_grant_is_403(
        self, client: httpx.AsyncClient, current_user: MagicMock, session: AsyncSession
    ) -> None:
        config_id = await seed_llm_config(session, 1)
        await _drop_caller_assignment(session)

        response = await client.post(COMPLETIONS_URL, json=_turn(config_id))

        assert response.status_code == 403
        assert (await session.exec(select(Conversation))).all() == []

    async def test_turn_into_another_users_conversation_is_403_and_audited(
        self,
        client: httpx.AsyncClient,
        current_user: MagicMock,
        session: AsyncSession,
        audit_events: AuditEventsFetcher,
    ) -> None:
        conv_uuid = await _owned_by(session, OWNER_ID)
        config_id = await seed_llm_config(session, 1)

        response = await client.post(COMPLETIONS_URL, json=_turn(config_id, conv_uuid))

        assert response.status_code == 403
        assert await stored_messages(session, str(conv_uuid)) == []
        (event,) = await audit_events()
        assert event.action == "denied"
        assert event.target_id == WRITE
        assert event.error_detail == f"scope=user:{OWNER_ID}"

    @pytest.mark.parametrize(
        ("permission", "scope_id"), [(READ, None), (WRITE, str(THIRD_ID))], ids=["read-at-global", "write-at-third"]
    )
    async def test_a_grant_that_does_not_reach_the_owner_is_403(
        self,
        client: httpx.AsyncClient,
        current_user: MagicMock,
        session: AsyncSession,
        permission: str,
        scope_id: str | None,
    ) -> None:
        conv_uuid = await _owned_by(session, OWNER_ID)
        config_id = await seed_llm_config(session, 1)
        await grant_permission_at_scope(session, 1, permission, GLOBAL if scope_id is None else USER, scope_id)
        await session.commit()

        response = await client.post(COMPLETIONS_URL, json=_turn(config_id, conv_uuid))

        assert response.status_code == 403
        assert await stored_messages(session, str(conv_uuid)) == []

    @pytest.mark.parametrize("stream", [False, True], ids=["non_streaming", "streaming"])
    @pytest.mark.parametrize("scope_id", [None, str(OWNER_ID)], ids=["global", "owner"])
    async def test_a_holder_turn_runs_as_the_caller_in_the_owners_conversation(
        self,
        client: httpx.AsyncClient,
        current_user: MagicMock,
        session: AsyncSession,
        analytics_session: SQLAlchemyAsyncSession,
        audit_events: AuditEventsFetcher,
        stub_agent: Agent,
        scope_id: str | None,
        stream: bool,
    ) -> None:
        conv_uuid = await _owned_by(session, OWNER_ID)
        # Only the caller has an AI key, so a 200 means the turn resolved the caller's.
        config_id = await seed_llm_config(session, 1)
        await grant_permission_at_scope(session, 1, WRITE, GLOBAL if scope_id is None else USER, scope_id)
        await session.commit()
        tool = StructuredTool.from_function(
            coroutine=audited_tool(lookup_course),
            name="lookup_course",
            description="Look up a course.",
            tags=[AUDIT_AT_HANDLER_TAG],
        )
        provider = get_provider("openai", api_key="sk-test", model="gpt-4o")
        model = _tool_calling_model()

        with (
            patch.object(provider, "_create_llm", lambda streaming=False, callbacks=None: model),
            patch(
                "sparkth.plugins.compose.routes.completions.get_provider",
                side_effect=planning(provider, hand_off(stub_agent)),
            ),
            patch("sparkth.plugins.compose.routes.completions.resolve_tools", AsyncMock(return_value=[tool])),
        ):
            response = await client.post(COMPLETIONS_URL, json=_turn(config_id, conv_uuid, stream))
            await response.aread()
            await join_live_tasks()

        assert response.status_code == 200
        assert [m.role for m in await stored_messages(session, str(conv_uuid))] == ["user", "assistant"]
        assert (await session.exec(select(Conversation).where(Conversation.user_id == 1))).all() == []
        rows = (await analytics_session.execute(sa_select(raw_events))).mappings().all()
        assert {"compose.message_sent", "compose.completion_served"} <= {row["event_type"] for row in rows}
        assert {row["actor_id"] for row in rows} == {"1"}
        audited = await audit_events()
        assert audited
        assert {event.actor_id for event in audited} == {"1"}

    async def test_a_holder_turn_attaches_only_the_owners_documents(
        self,
        client: httpx.AsyncClient,
        current_user: MagicMock,
        session: AsyncSession,
        analytics_session: SQLAlchemyAsyncSession,
    ) -> None:
        conv_uuid = await _owned_by(session, OWNER_ID)
        config_id = await seed_llm_config(session, 1)
        owner_doc = Document(user_id=OWNER_ID, name="owner.pdf", status=DocumentStatus.READY)
        caller_doc = Document(user_id=1, name="caller.pdf", status=DocumentStatus.READY)
        session.add_all([owner_doc, caller_doc])
        await session.flush()
        owner_doc_id, caller_doc_id = owner_doc.id, caller_doc.id
        await grant_permission_at_scope(session, 1, WRITE, GLOBAL)
        await session.commit()
        search = MagicMock(requires_search=AsyncMock(return_value=False))

        with (
            patch("sparkth.plugins.compose.routes.completions.get_provider", return_value=_answering_provider()),
            patch("sparkth.plugins.compose.routes.completions.RAGSearchClassifier", return_value=search),
        ):
            response = await client.post(
                COMPLETIONS_URL, json={**_turn(config_id, conv_uuid), "document_ids": [owner_doc_id, caller_doc_id]}
            )

        assert response.status_code == 200
        conversation = (await session.exec(select(Conversation).where(Conversation.uuid == conv_uuid))).one()
        attached = await ComposeService().list_conversation_attachments(session, cast(int, conversation.id))
        assert [document.id for document in attached.ready] == [owner_doc_id]
        rows = (await analytics_session.execute(sa_select(raw_events))).mappings().all()
        assert [row["payload"] for row in rows if row["event_type"] == "compose.documents_skipped"] == [
            {"conversation_id": str(conv_uuid), "requested_count": 2, "skipped_count": 1}
        ]

    async def test_a_holders_failed_turn_records_the_error_in_the_owners_conversation(
        self, client: httpx.AsyncClient, current_user: MagicMock, session: AsyncSession
    ) -> None:
        conv_uuid = await _owned_by(session, OWNER_ID)
        await grant_permission_at_scope(session, 1, WRITE, GLOBAL)
        await session.commit()

        response = await client.post(COMPLETIONS_URL, json=_turn(999999, conv_uuid))

        assert response.status_code == 404
        assert [(m.role, m.is_error) for m in await stored_messages(session, str(conv_uuid))] == [("assistant", True)]

    async def test_unknown_conversation_is_404_without_a_denial_row(
        self,
        client: httpx.AsyncClient,
        current_user: MagicMock,
        session: AsyncSession,
        audit_events: AuditEventsFetcher,
    ) -> None:
        config_id = await seed_llm_config(session, 1)
        await _drop_caller_assignment(session)

        response = await client.post(COMPLETIONS_URL, json=_turn(config_id, uuid4()))

        assert response.status_code == 404
        assert await audit_events() == []
