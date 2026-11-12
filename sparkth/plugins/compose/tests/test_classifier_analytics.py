"""End-to-end analytics tests for the classifier decisions and failed turns.

Each drives a real request and asserts on rows that landed. `compose.turn_failed` is emitted
from a detached task — its seams raise rather than return — so these join it with `join_live_tasks`
before asserting.
"""

from collections.abc import AsyncGenerator, Sequence
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID

import httpx
import openai
import pytest
from httpx import AsyncClient
from sqlalchemy import select as sa_select
from sqlalchemy.ext.asyncio import AsyncSession as SQLAlchemyAsyncSession
from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from sparkth.core.analytics.models import raw_events
from sparkth.lib.documents import Document, DocumentStatus
from sparkth.lib.models import User
from sparkth.plugins.compose.detached import join_live_tasks
from sparkth.plugins.compose.models import Conversation, ConversationAttachment
from sparkth.plugins.compose.tests.helpers import (
    STREAM_TURN,
    answering_model,
    failing_model,
    seed_conversation,
    seed_llm_config,
)

COMPLETIONS_URL = "/api/v1/compose/completions"
_OPENAI_REQUEST = httpx.Request("POST", "https://api.openai.com/v1/chat/completions")


async def _seed_attachment(session: AsyncSession, user_id: int, conversation_uuid: str) -> int:
    """A READY document attached to the conversation, so the search classifier is consulted."""
    document = Document(user_id=user_id, name="syllabus.pdf", status=DocumentStatus.READY)
    session.add(document)
    await session.flush()
    document_id = document.id or 0
    conversation = (
        await session.exec(select(Conversation).where(col(Conversation.uuid) == UUID(conversation_uuid)))
    ).one()
    session.add(ConversationAttachment(conversation_id=conversation.id or 0, document_id=document_id))
    await session.commit()
    return document_id


async def _events(analytics_session: SQLAlchemyAsyncSession, event_type: str) -> list[dict[str, Any]]:
    rows = (await analytics_session.execute(sa_select(raw_events))).mappings().all()
    return [row["payload"] for row in rows if row["event_type"] == event_type]


async def _all_payloads(analytics_session: SQLAlchemyAsyncSession) -> str:
    rows = (await analytics_session.execute(sa_select(raw_events))).mappings().all()
    return str([row["payload"] for row in rows])


def _provider() -> MagicMock:
    """A provider mock whose model answers; its ``send_message`` writes conversation titles."""
    provider = MagicMock()
    provider.model = "gpt-4o"
    provider.system_prompt = ""
    provider.create_llm.return_value = answering_model("Outline ready.")
    provider.send_message = AsyncMock(return_value={"content": "Outline ready.", "metadata": {}})
    return provider


def _dropped_connection_turn(
    messages: list[dict[str, Any]], tools: Sequence[Any], provider: Any, max_tool_executions: int
) -> AsyncGenerator[dict[str, Any], None]:
    """A streamed turn whose connection drops before the first event."""
    raise OSError("the connection dropped mid-stream")


def _search_verdict(requires_search: bool) -> MagicMock:
    verdict = MagicMock()
    verdict.requires_search = requires_search
    verdict.refusal_reason = "the documents do not cover the Schrems II ruling"
    return verdict


async def _turn(
    client: AsyncClient,
    config_id: int,
    *,
    conversation_uuid: str | None = None,
    content: str = "Create a course on data privacy",
) -> Any:
    """One non-streaming turn with the real classifiers, whose model calls are mocked."""
    body: dict[str, Any] = {
        "llm_config_id": config_id,
        "messages": [{"role": "user", "content": content}],
        "stream": False,
        "tools": "none",
    }
    if conversation_uuid:
        body["conversation_id"] = conversation_uuid
    return await client.post(COMPLETIONS_URL, json=body)


async def test_the_search_decision_is_recorded_when_the_classifier_is_consulted(
    client: AsyncClient,
    current_user: User,
    session: AsyncSession,
    analytics_session: SQLAlchemyAsyncSession,
) -> None:
    config_id = await seed_llm_config(session, current_user.id or 1)
    conversation_uuid = await seed_conversation(session, current_user.id or 1)
    await _seed_attachment(session, current_user.id or 1, conversation_uuid)

    with (
        patch("sparkth.plugins.compose.routes.completions.get_provider", return_value=_provider()),
        patch("sparkth.plugins.compose.classifiers.base.get_provider"),
        patch(
            "sparkth.plugins.compose.classifiers.rag_search.RAGSearchClassifier.classify",
            new_callable=AsyncMock,
            return_value=_search_verdict(False),
        ),
        patch(
            "sparkth.plugins.compose.classifiers.rag_search.get_rag_ingested_document_structure",
            new_callable=AsyncMock,
            return_value=[],
        ),
    ):
        response = await _turn(client, config_id, conversation_uuid=conversation_uuid)

    assert response.status_code == 200
    (decision,) = await _events(analytics_session, "compose.rag_search_classified")
    assert decision["requires_search"] is False
    assert decision["document_count"] == 1
    assert decision["conversation_id"] == conversation_uuid


async def test_no_search_decision_is_recorded_when_there_is_nothing_to_search(
    client: AsyncClient,
    current_user: User,
    session: AsyncSession,
    analytics_session: SQLAlchemyAsyncSession,
) -> None:
    """Absence of the event means there was no decision to make, not that it was skipped."""
    config_id = await seed_llm_config(session, current_user.id or 1)
    conversation_uuid = await seed_conversation(session, current_user.id or 1)

    with (
        patch("sparkth.plugins.compose.routes.completions.get_provider", return_value=_provider()),
        patch("sparkth.plugins.compose.classifiers.base.get_provider"),
    ):
        await _turn(client, config_id, conversation_uuid=conversation_uuid)

    assert await _events(analytics_session, "compose.rag_search_classified") == []


async def test_documents_whose_structure_cannot_be_read_are_counted(
    client: AsyncClient,
    current_user: User,
    session: AsyncSession,
    analytics_session: SQLAlchemyAsyncSession,
) -> None:
    """A lookup failure degrades the decision silently; a document with no sections does not."""
    config_id = await seed_llm_config(session, current_user.id or 1)
    conversation_uuid = await seed_conversation(session, current_user.id or 1)
    await _seed_attachment(session, current_user.id or 1, conversation_uuid)

    with (
        patch("sparkth.plugins.compose.routes.completions.get_provider", return_value=_provider()),
        patch("sparkth.plugins.compose.classifiers.base.get_provider"),
        patch(
            "sparkth.plugins.compose.classifiers.rag_search.RAGSearchClassifier.classify",
            new_callable=AsyncMock,
            return_value=_search_verdict(True),
        ),
        patch(
            "sparkth.plugins.compose.classifiers.rag_search.get_rag_ingested_document_structure",
            new_callable=AsyncMock,
            side_effect=RuntimeError("structure unavailable"),
        ),
        patch(
            "sparkth.plugins.compose.routes.utils.message_assembly.resolve_document_blocks",
            new_callable=AsyncMock,
            return_value=[],
        ),
    ):
        await _turn(client, config_id, conversation_uuid=conversation_uuid)

    (decision,) = await _events(analytics_session, "compose.rag_search_classified")
    assert decision["documents_with_unreadable_structure"] == 1


async def test_an_unusable_ai_key_records_a_failed_turn(
    client: AsyncClient,
    current_user: User,
    session: AsyncSession,
    analytics_session: SQLAlchemyAsyncSession,
) -> None:
    """The raise path: the route returns 404, so a queued emit would never run.

    ``provider`` and ``model`` are null because the config never resolved.
    """
    conversation_uuid = await seed_conversation(session, current_user.id or 1)

    response = await client.post(
        COMPLETIONS_URL,
        json={
            "llm_config_id": 99999,
            "conversation_id": conversation_uuid,
            "messages": [{"role": "user", "content": "Create a course"}],
            "stream": False,
            "tools": "none",
        },
    )
    await join_live_tasks()

    assert response.status_code == 404
    (failure,) = await _events(analytics_session, "compose.turn_failed")
    assert failure["cause"] == "llm_config_unusable"
    assert failure["provider"] is None
    assert failure["model"] is None
    assert failure["streamed"] is False
    # The turn failed before any message was stored, so there is none to count.
    assert await _events(analytics_session, "compose.message_sent") == []


async def test_a_provider_failure_records_a_failed_turn(
    client: AsyncClient,
    current_user: User,
    session: AsyncSession,
    analytics_session: SQLAlchemyAsyncSession,
) -> None:
    """The 500 path, which also raises."""
    config_id = await seed_llm_config(session, current_user.id or 1)
    conversation_uuid = await seed_conversation(session, current_user.id or 1)

    provider = _provider()
    provider.create_llm.return_value = failing_model(RuntimeError("upstream exploded"))

    with (
        patch("sparkth.plugins.compose.routes.completions.get_provider", return_value=provider),
        patch("sparkth.plugins.compose.classifiers.base.get_provider"),
    ):
        response = await _turn(client, config_id, conversation_uuid=conversation_uuid)
        await join_live_tasks()

    assert response.status_code == 500
    (failure,) = await _events(analytics_session, "compose.turn_failed")
    assert failure["cause"] == "unexpected"
    assert failure["provider"] == "openai"
    assert failure["model"] == "gpt-4o"
    assert failure["conversation_id"] == conversation_uuid
    # The instructor's message was stored before the route raised, so it still counts.
    (sent,) = await _events(analytics_session, "compose.message_sent")
    assert sent["conversation_id"] == conversation_uuid


async def test_a_search_classifier_provider_failure_keeps_its_own_cause(
    client: AsyncClient,
    current_user: User,
    session: AsyncSession,
    analytics_session: AsyncSession,
) -> None:
    """Scope passed, so the search classifier's provider failure is not a scope failure."""
    config_id = await seed_llm_config(session, current_user.id or 1)
    conversation_uuid = await seed_conversation(session, current_user.id or 1)
    await _seed_attachment(session, current_user.id or 1, conversation_uuid)

    with (
        patch("sparkth.plugins.compose.routes.completions.get_provider", return_value=_provider()),
        patch("sparkth.plugins.compose.classifiers.base.get_provider"),
        patch(
            "sparkth.plugins.compose.classifiers.rag_search.RAGSearchClassifier.classify",
            new_callable=AsyncMock,
            side_effect=openai.APIConnectionError(request=_OPENAI_REQUEST),
        ),
        patch(
            "sparkth.plugins.compose.classifiers.rag_search.get_rag_ingested_document_structure",
            new_callable=AsyncMock,
            return_value=[],
        ),
    ):
        response = await _turn(client, config_id, conversation_uuid=conversation_uuid)
        await join_live_tasks()

    assert response.status_code == 502
    (failure,) = await _events(analytics_session, "compose.turn_failed")
    assert failure["cause"] == "provider_api_error"


async def test_a_successful_turn_records_no_failure(
    client: AsyncClient,
    current_user: User,
    session: AsyncSession,
    analytics_session: SQLAlchemyAsyncSession,
) -> None:
    config_id = await seed_llm_config(session, current_user.id or 1)
    conversation_uuid = await seed_conversation(session, current_user.id or 1)

    with (
        patch("sparkth.plugins.compose.routes.completions.get_provider", return_value=_provider()),
        patch("sparkth.plugins.compose.classifiers.base.get_provider"),
    ):
        await _turn(client, config_id, conversation_uuid=conversation_uuid)
        await join_live_tasks()

    assert await _events(analytics_session, "compose.turn_failed") == []


@pytest.mark.parametrize("streamed", [True, False])
async def test_the_failure_records_which_shape_the_client_asked_for(
    client: AsyncClient,
    current_user: User,
    session: AsyncSession,
    analytics_session: SQLAlchemyAsyncSession,
    streamed: bool,
) -> None:
    conversation_uuid = await seed_conversation(session, current_user.id or 1)

    response = await client.post(
        COMPLETIONS_URL,
        json={
            "llm_config_id": 99999,
            "conversation_id": conversation_uuid,
            "messages": [{"role": "user", "content": "Create a course"}],
            "stream": streamed,
            "tools": "none",
        },
    )
    await join_live_tasks()

    assert response.status_code == 404
    (failure,) = await _events(analytics_session, "compose.turn_failed")
    assert failure["streamed"] is streamed


async def test_a_streaming_failure_records_a_failed_turn(
    client: AsyncClient,
    current_user: User,
    session: AsyncSession,
    analytics_session: SQLAlchemyAsyncSession,
) -> None:
    """Streaming is the default client path, so a failure rate that omits it is misleading."""
    config_id = await seed_llm_config(session, current_user.id or 1)
    conversation_uuid = await seed_conversation(session, current_user.id or 1)

    with (
        patch("sparkth.plugins.compose.routes.completions.get_provider", return_value=_provider()),
        patch(STREAM_TURN, _dropped_connection_turn),
        patch("sparkth.plugins.compose.classifiers.base.get_provider"),
    ):
        response = await client.post(
            COMPLETIONS_URL,
            json={
                "llm_config_id": config_id,
                "conversation_id": conversation_uuid,
                "messages": [{"role": "user", "content": "Create a course on data privacy"}],
                "stream": True,
                "tools": "none",
            },
        )
        assert "data: " in response.text
        await join_live_tasks()

    (failure,) = await _events(analytics_session, "compose.turn_failed")
    assert failure["cause"] == "unexpected"
    assert failure["streamed"] is True
    assert failure["conversation_id"] == conversation_uuid
    (sent,) = await _events(analytics_session, "compose.message_sent")
    assert sent["conversation_id"] == conversation_uuid
