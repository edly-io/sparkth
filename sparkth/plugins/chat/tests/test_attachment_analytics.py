"""End-to-end analytics producer tests for document attachment.

Every test drives a real endpoint and asserts on rows that actually landed in the
analytics database. The two events worth having here are the silent failures —
`chat.documents_skipped` and `chat.attachment_unusable` — so those get the tests that
prove an instructor was affected, not just that a code path ran.
"""

from datetime import datetime, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID

from httpx import AsyncClient
from sqlalchemy import select
from sqlmodel.ext.asyncio.session import AsyncSession

from sparkth.core.analytics.models import raw_events
from sparkth.lib.documents import Document, DocumentStatus
from sparkth.lib.encryption import get_encryption_service
from sparkth.lib.models import LLMConfig, User
from sparkth.lib.settings import get_settings
from sparkth.plugins.chat.models import Conversation

COMPLETIONS_URL = "/api/v1/chat/completions"


def _attachments_url(conversation_uuid: str) -> str:
    return f"/api/v1/chat/conversations/{conversation_uuid}/attachments"


async def _seed_conversation(session: AsyncSession, user_id: int) -> tuple[int, str]:
    conversation = Conversation(user_id=user_id, provider="openai", model="gpt-4o")
    session.add(conversation)
    await session.flush()
    conversation_id = conversation.id or 0
    conversation_uuid = str(conversation.uuid)
    await session.commit()
    return conversation_id, conversation_uuid


async def _seed_document(
    session: AsyncSession,
    user_id: int,
    *,
    name: str = "syllabus.pdf",
    status: DocumentStatus = DocumentStatus.READY,
    is_deleted: bool = False,
) -> int:
    document = Document(user_id=user_id, name=name, status=status, is_deleted=is_deleted)
    session.add(document)
    await session.flush()
    document_id = document.id or 0
    await session.commit()
    return document_id


async def _seed_llm_config(session: AsyncSession, user_id: int) -> int:
    settings = get_settings()
    enc = get_encryption_service(settings.LLM_ENCRYPTION_KEY)
    config = LLMConfig(
        user_id=user_id,
        name="test-cfg-attachments",
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


async def _events(analytics_session: AsyncSession, event_type: str) -> list[dict[str, Any]]:
    rows = (await analytics_session.execute(select(raw_events))).mappings().all()
    return [row["payload"] for row in rows if row["event_type"] == event_type]


async def _all_payloads(analytics_session: AsyncSession) -> list[dict[str, Any]]:
    rows = (await analytics_session.execute(select(raw_events))).mappings().all()
    return [row["payload"] for row in rows]


def _provider() -> MagicMock:
    provider = MagicMock()
    provider.model = "gpt-4o"
    provider.system_prompt = ""
    provider.send_message = AsyncMock(return_value={"content": "Outline ready.", "metadata": {}})
    return provider


def _in_scope_classifier() -> AsyncMock:
    classifier = AsyncMock()
    classifier.in_scope = AsyncMock(return_value=True)
    return classifier


async def _complete_turn(client: AsyncClient, config_id: int, conversation_uuid: str, **extra: Any) -> Any:
    """Drive one non-streaming turn on an existing conversation."""
    with (
        patch("sparkth.plugins.chat.routes.completions.get_provider", return_value=_provider()),
        patch("sparkth.plugins.chat.routes.completions.MessageScopeClassifier") as mock_scope_cls,
        patch("sparkth.plugins.chat.routes.completions.RAGSearchClassifier") as mock_search_cls,
    ):
        mock_scope_cls.return_value = _in_scope_classifier()
        search = MagicMock()
        search.requires_search = AsyncMock(return_value=False)
        mock_search_cls.return_value = search
        return await client.post(
            COMPLETIONS_URL,
            json={
                "llm_config_id": config_id,
                "conversation_id": conversation_uuid,
                "messages": [{"role": "user", "content": "Build a module from the attached file"}],
                "stream": False,
                "tools": "none",
                **extra,
            },
        )


async def test_attaching_a_document_emits_document_attached(
    client: AsyncClient,
    current_user: User,
    session: AsyncSession,
    analytics_session: AsyncSession,
) -> None:
    _, conversation_uuid = await _seed_conversation(session, current_user.id or 1)
    document_id = await _seed_document(session, current_user.id or 1)

    response = await client.post(_attachments_url(conversation_uuid), json={"document_id": document_id})

    assert response.status_code == 201
    assert await _events(analytics_session, "chat.document_attached") == [
        {"conversation_id": conversation_uuid, "document_id": document_id, "source": "explicit"}
    ]


async def test_re_attaching_the_same_document_emits_nothing(
    client: AsyncClient,
    current_user: User,
    session: AsyncSession,
    analytics_session: AsyncSession,
) -> None:
    """attach_document is upsert-safe, so a repeat is a no-op rather than an action."""
    _, conversation_uuid = await _seed_conversation(session, current_user.id or 1)
    document_id = await _seed_document(session, current_user.id or 1)

    await client.post(_attachments_url(conversation_uuid), json={"document_id": document_id})
    await client.post(_attachments_url(conversation_uuid), json={"document_id": document_id})

    assert len(await _events(analytics_session, "chat.document_attached")) == 1


async def test_detaching_emits_document_detached(
    client: AsyncClient,
    current_user: User,
    session: AsyncSession,
    analytics_session: AsyncSession,
) -> None:
    _, conversation_uuid = await _seed_conversation(session, current_user.id or 1)
    document_id = await _seed_document(session, current_user.id or 1)
    await client.post(_attachments_url(conversation_uuid), json={"document_id": document_id})

    response = await client.request("DELETE", f"{_attachments_url(conversation_uuid)}/{document_id}")

    assert response.status_code == 204
    (detached,) = await _events(analytics_session, "chat.document_detached")
    assert detached["conversation_id"] == conversation_uuid
    assert detached["document_id"] == document_id
    # Attached and removed within the test, so the dwell time is real but tiny.
    assert detached["seconds_attached"] >= 0


async def test_detaching_a_document_that_was_never_attached_emits_nothing(
    client: AsyncClient,
    current_user: User,
    session: AsyncSession,
    analytics_session: AsyncSession,
) -> None:
    """Nothing was removed, so nothing happened."""
    _, conversation_uuid = await _seed_conversation(session, current_user.id or 1)
    document_id = await _seed_document(session, current_user.id or 1)

    response = await client.request("DELETE", f"{_attachments_url(conversation_uuid)}/{document_id}")

    assert response.status_code == 204
    assert await _events(analytics_session, "chat.document_detached") == []


async def test_documents_named_on_a_completion_request_are_attributed_to_that_source(
    client: AsyncClient,
    current_user: User,
    session: AsyncSession,
    analytics_session: AsyncSession,
) -> None:
    config_id = await _seed_llm_config(session, current_user.id or 1)
    _, conversation_uuid = await _seed_conversation(session, current_user.id or 1)
    document_id = await _seed_document(session, current_user.id or 1)

    response = await _complete_turn(client, config_id, conversation_uuid, document_ids=[document_id])

    assert response.status_code == 200
    assert await _events(analytics_session, "chat.document_attached") == [
        {"conversation_id": conversation_uuid, "document_id": document_id, "source": "completion_request"}
    ]


async def test_unowned_document_ids_emit_documents_skipped(
    client: AsyncClient,
    current_user: User,
    session: AsyncSession,
    analytics_session: AsyncSession,
) -> None:
    """The instructor named documents that were silently dropped from their turn."""
    config_id = await _seed_llm_config(session, current_user.id or 1)
    _, conversation_uuid = await _seed_conversation(session, current_user.id or 1)
    owned = await _seed_document(session, current_user.id or 1)
    someone_elses = await _seed_document(session, (current_user.id or 1) + 999, name="not-yours.pdf")  # noqa: F841

    response = await _complete_turn(client, config_id, conversation_uuid, document_ids=[owned, someone_elses])

    assert response.status_code == 200
    assert await _events(analytics_session, "chat.documents_skipped") == [
        {"conversation_id": conversation_uuid, "requested_count": 2, "skipped_count": 1}
    ]
    # Counts only, never ids: the skipped document belongs to another user, so the payload
    # has no field that could carry it. Asserted on the key set — searching the values for
    # the id is meaningless when a document id and a count are both small integers.
    (skipped,) = await _events(analytics_session, "chat.documents_skipped")
    assert set(skipped) == {"conversation_id", "requested_count", "skipped_count"}


async def test_all_documents_owned_emits_no_skip_event(
    client: AsyncClient,
    current_user: User,
    session: AsyncSession,
    analytics_session: AsyncSession,
) -> None:
    config_id = await _seed_llm_config(session, current_user.id or 1)
    _, conversation_uuid = await _seed_conversation(session, current_user.id or 1)
    document_id = await _seed_document(session, current_user.id or 1)

    response = await _complete_turn(client, config_id, conversation_uuid, document_ids=[document_id])

    assert response.status_code == 200
    assert await _events(analytics_session, "chat.documents_skipped") == []


async def test_a_still_ingesting_attachment_emits_attachment_unusable(
    client: AsyncClient,
    current_user: User,
    session: AsyncSession,
    analytics_session: AsyncSession,
) -> None:
    """The instructor attached a file and the turn ran as though they had not.

    This is the event the issue exists for: chat filters attachments to READY, so a
    document still ingesting is indistinguishable, in every other metric, from no
    document at all.
    """
    config_id = await _seed_llm_config(session, current_user.id or 1)
    _, conversation_uuid = await _seed_conversation(session, current_user.id or 1)
    document_id = await _seed_document(session, current_user.id or 1, status=DocumentStatus.PROCESSING)
    await client.post(_attachments_url(conversation_uuid), json={"document_id": document_id})

    response = await _complete_turn(client, config_id, conversation_uuid)

    assert response.status_code == 200
    assert await _events(analytics_session, "chat.attachment_unusable") == [
        {"conversation_id": conversation_uuid, "document_id": document_id, "status": "processing"}
    ]


async def test_a_failed_attachment_reports_its_status(
    client: AsyncClient,
    current_user: User,
    session: AsyncSession,
    analytics_session: AsyncSession,
) -> None:
    config_id = await _seed_llm_config(session, current_user.id or 1)
    _, conversation_uuid = await _seed_conversation(session, current_user.id or 1)
    document_id = await _seed_document(session, current_user.id or 1, status=DocumentStatus.FAILED)
    await client.post(_attachments_url(conversation_uuid), json={"document_id": document_id})

    await _complete_turn(client, config_id, conversation_uuid)

    (unusable,) = await _events(analytics_session, "chat.attachment_unusable")
    assert unusable["status"] == "failed"


async def test_a_ready_attachment_emits_no_unusable_event(
    client: AsyncClient,
    current_user: User,
    session: AsyncSession,
    analytics_session: AsyncSession,
) -> None:
    config_id = await _seed_llm_config(session, current_user.id or 1)
    _, conversation_uuid = await _seed_conversation(session, current_user.id or 1)
    document_id = await _seed_document(session, current_user.id or 1, status=DocumentStatus.READY)
    await client.post(_attachments_url(conversation_uuid), json={"document_id": document_id})

    await _complete_turn(client, config_id, conversation_uuid)

    assert await _events(analytics_session, "chat.attachment_unusable") == []


async def test_no_document_name_reaches_any_payload(
    client: AsyncClient,
    current_user: User,
    session: AsyncSession,
    analytics_session: AsyncSession,
) -> None:
    """A filename is user-authored text, like a conversation title. Ids only."""
    _, conversation_uuid = await _seed_conversation(session, current_user.id or 1)
    document_id = await _seed_document(session, current_user.id or 1, name="Q3-restructure-plan.pdf")

    await client.post(_attachments_url(conversation_uuid), json={"document_id": document_id})
    await client.request("DELETE", f"{_attachments_url(conversation_uuid)}/{document_id}")

    assert "Q3-restructure-plan" not in str(await _all_payloads(analytics_session))


async def test_attachment_events_are_timed_when_they_happened(
    client: AsyncClient,
    current_user: User,
    session: AsyncSession,
    analytics_session: AsyncSession,
) -> None:
    """occurred_at comes from the attachment row, not from whenever the task ran."""
    _, conversation_uuid = await _seed_conversation(session, current_user.id or 1)
    document_id = await _seed_document(session, current_user.id or 1)

    before = datetime.now(timezone.utc)
    await client.post(_attachments_url(conversation_uuid), json={"document_id": document_id})
    after = datetime.now(timezone.utc)

    rows = (await analytics_session.execute(select(raw_events))).mappings().all()
    (attached,) = [row for row in rows if row["event_type"] == "chat.document_attached"]
    occurred = attached["occurred_at"]
    occurred = occurred if occurred.tzinfo else occurred.replace(tzinfo=timezone.utc)
    assert before <= occurred <= after


async def test_the_conversation_uuid_is_what_lands_not_the_row_id(
    client: AsyncClient,
    current_user: User,
    session: AsyncSession,
    analytics_session: AsyncSession,
) -> None:
    """Every other chat event keys on the uuid; these must match or they cannot be joined."""
    conversation_id, conversation_uuid = await _seed_conversation(session, current_user.id or 1)
    document_id = await _seed_document(session, current_user.id or 1)

    await client.post(_attachments_url(conversation_uuid), json={"document_id": document_id})

    (attached,) = await _events(analytics_session, "chat.document_attached")
    assert attached["conversation_id"] == conversation_uuid
    assert attached["conversation_id"] != str(conversation_id)
    UUID(attached["conversation_id"])
