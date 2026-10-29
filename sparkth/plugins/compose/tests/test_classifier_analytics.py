"""End-to-end analytics tests for the classifier decisions and failed turns.

Each drives a real request and asserts on rows that landed. `chat.turn_failed` is emitted
from a detached task — its seams raise rather than return — so these join it with `join_live_tasks`
before asserting.
"""

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
from sparkth.plugins.compose.tests.helpers import classifier_provider, seed_conversation, seed_llm_config

COMPLETIONS_URL = "/api/v1/chat/completions"
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
    provider = MagicMock()
    provider.model = "gpt-4o"
    provider.system_prompt = ""
    provider.send_message = AsyncMock(return_value={"content": "Outline ready.", "metadata": {}})
    return provider


def _scope_verdict(in_scope: bool) -> MagicMock:
    verdict = MagicMock()
    verdict.in_scope = in_scope
    verdict.refusal_reason = "the instructor asked about the Schrems II ruling"
    return verdict


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


async def test_an_admitted_turn_records_the_scope_decision(
    client: AsyncClient,
    current_user: User,
    session: AsyncSession,
    analytics_session: SQLAlchemyAsyncSession,
) -> None:
    """Emitted on every classification, not only refusals — that is the denominator."""
    config_id = await seed_llm_config(session, current_user.id or 1)
    conversation_uuid = await seed_conversation(session, current_user.id or 1)

    with (
        patch("sparkth.plugins.compose.routes.completions.get_provider", return_value=_provider()),
        patch("sparkth.plugins.compose.classifiers.base.get_provider"),
        patch(
            "sparkth.plugins.compose.classifiers.message_scope.MessageScopeClassifier.classify",
            new_callable=AsyncMock,
            return_value=_scope_verdict(True),
        ),
    ):
        response = await _turn(client, config_id, conversation_uuid=conversation_uuid)

    assert response.status_code == 200
    (decision,) = await _events(analytics_session, "chat.scope_classified")
    assert decision["verdict"] == "in_scope"
    assert decision["conversation_id"] == conversation_uuid
    assert decision["provider"] == "openai"
    assert decision["query_length"] == len("Create a course on data privacy")


async def test_a_refused_turn_records_the_refusal_as_the_verdict(
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
        patch(
            "sparkth.plugins.compose.classifiers.message_scope.MessageScopeClassifier.classify",
            new_callable=AsyncMock,
            return_value=_scope_verdict(False),
        ),
    ):
        response = await _turn(client, config_id, conversation_uuid=conversation_uuid, content="what is 2+2?")

    assert response.status_code == 200
    (decision,) = await _events(analytics_session, "chat.scope_classified")
    assert decision["verdict"] == "out_of_scope"


async def test_a_first_message_refusal_is_recorded_without_a_conversation(
    client: AsyncClient,
    current_user: User,
    session: AsyncSession,
    analytics_session: SQLAlchemyAsyncSession,
) -> None:
    """The case that is most invisible today: judged before any conversation row exists."""
    config_id = await seed_llm_config(session, current_user.id or 1)

    with (
        patch("sparkth.plugins.compose.routes.completions.get_provider", return_value=_provider()),
        patch("sparkth.plugins.compose.classifiers.base.get_provider"),
        patch(
            "sparkth.plugins.compose.classifiers.message_scope.MessageScopeClassifier.classify",
            new_callable=AsyncMock,
            return_value=_scope_verdict(False),
        ),
    ):
        response = await _turn(client, config_id, content="what is 2+2?")

    assert response.status_code == 200
    (decision,) = await _events(analytics_session, "chat.scope_classified")
    assert decision["verdict"] == "out_of_scope"
    assert decision["conversation_id"] is None


async def test_an_unreadable_scope_answer_records_a_failed_turn_and_no_decision(
    client: AsyncClient,
    current_user: User,
    session: AsyncSession,
    analytics_session: SQLAlchemyAsyncSession,
) -> None:
    """The answer fails the schema in the real classify, so the turn fails and is recorded once."""
    config_id = await seed_llm_config(session, current_user.id or 1)
    conversation_uuid = await seed_conversation(session, current_user.id or 1)

    with (
        patch("sparkth.plugins.compose.routes.completions.get_provider", return_value=_provider()),
        patch(
            "sparkth.plugins.compose.classifiers.base.get_provider",
            return_value=classifier_provider(AsyncMock(return_value={"in_scope": "maybe"})),
        ),
    ):
        response = await _turn(client, config_id, conversation_uuid=conversation_uuid)
        await join_live_tasks()

    assert response.status_code == 502
    (failure,) = await _events(analytics_session, "chat.turn_failed")
    assert failure["cause"] == "scope_classification_error"
    assert await _events(analytics_session, "chat.scope_classified") == []


async def test_a_new_conversation_records_exactly_one_scope_decision(
    client: AsyncClient,
    current_user: User,
    session: AsyncSession,
    analytics_session: SQLAlchemyAsyncSession,
) -> None:
    """The route skips the second check on a new conversation; the emit must not double."""
    config_id = await seed_llm_config(session, current_user.id or 1)

    with (
        patch("sparkth.plugins.compose.routes.completions.get_provider", return_value=_provider()),
        patch("sparkth.plugins.compose.classifiers.base.get_provider"),
        patch("sparkth.plugins.compose.conversation_title.get_provider", return_value=_provider()),
        patch(
            "sparkth.plugins.compose.classifiers.message_scope.MessageScopeClassifier.classify",
            new_callable=AsyncMock,
            return_value=_scope_verdict(True),
        ),
    ):
        response = await _turn(client, config_id)

    assert response.status_code == 200
    assert len(await _events(analytics_session, "chat.scope_classified")) == 1


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
            "sparkth.plugins.compose.classifiers.message_scope.MessageScopeClassifier.classify",
            new_callable=AsyncMock,
            return_value=_scope_verdict(True),
        ),
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
    (decision,) = await _events(analytics_session, "chat.rag_search_classified")
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
        patch(
            "sparkth.plugins.compose.classifiers.message_scope.MessageScopeClassifier.classify",
            new_callable=AsyncMock,
            return_value=_scope_verdict(True),
        ),
    ):
        await _turn(client, config_id, conversation_uuid=conversation_uuid)

    assert await _events(analytics_session, "chat.rag_search_classified") == []


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
            "sparkth.plugins.compose.classifiers.message_scope.MessageScopeClassifier.classify",
            new_callable=AsyncMock,
            return_value=_scope_verdict(True),
        ),
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

    (decision,) = await _events(analytics_session, "chat.rag_search_classified")
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
    (failure,) = await _events(analytics_session, "chat.turn_failed")
    assert failure["cause"] == "llm_config_unusable"
    assert failure["provider"] is None
    assert failure["model"] is None
    assert failure["streamed"] is False
    # The turn failed before any message was stored, so there is none to count.
    assert await _events(analytics_session, "chat.message_sent") == []


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
    provider.send_message = AsyncMock(side_effect=RuntimeError("upstream exploded"))

    with (
        patch("sparkth.plugins.compose.routes.completions.get_provider", return_value=provider),
        patch("sparkth.plugins.compose.classifiers.base.get_provider"),
        patch(
            "sparkth.plugins.compose.classifiers.message_scope.MessageScopeClassifier.classify",
            new_callable=AsyncMock,
            return_value=_scope_verdict(True),
        ),
    ):
        response = await _turn(client, config_id, conversation_uuid=conversation_uuid)
        await join_live_tasks()

    assert response.status_code == 500
    (failure,) = await _events(analytics_session, "chat.turn_failed")
    assert failure["cause"] == "unexpected"
    assert failure["provider"] == "openai"
    assert failure["model"] == "gpt-4o"
    assert failure["conversation_id"] == conversation_uuid
    # The instructor's message was stored before the route raised, so it still counts.
    (sent,) = await _events(analytics_session, "chat.message_sent")
    assert sent["conversation_id"] == conversation_uuid


async def test_a_failed_scope_check_on_a_first_message_records_a_failed_turn(
    client: AsyncClient,
    current_user: User,
    session: AsyncSession,
    analytics_session: AsyncSession,
) -> None:
    """Raised before any conversation exists, so the row carries none, and no decision is recorded."""
    config_id = await seed_llm_config(session, current_user.id or 1)

    with (
        patch("sparkth.plugins.compose.routes.completions.get_provider", return_value=_provider()),
        patch("sparkth.plugins.compose.classifiers.base.get_provider"),
        patch(
            "sparkth.plugins.compose.classifiers.message_scope.MessageScopeClassifier.classify",
            new_callable=AsyncMock,
            side_effect=openai.APIConnectionError(request=_OPENAI_REQUEST),
        ),
    ):
        response = await _turn(client, config_id)
        await join_live_tasks()

    assert response.status_code == 502
    (failure,) = await _events(analytics_session, "chat.turn_failed")
    assert failure["cause"] == "scope_classification_error"
    assert failure["conversation_id"] is None
    assert failure["provider"] == "openai"
    assert failure["model"] == "gpt-4o"
    assert failure["streamed"] is False
    assert await _events(analytics_session, "chat.scope_classified") == []


async def test_a_failed_scope_check_on_a_later_turn_records_one_failed_turn(
    client: AsyncClient,
    current_user: User,
    session: AsyncSession,
    analytics_session: AsyncSession,
) -> None:
    """Exactly one row: the route's provider-error handler must not record the failure again."""
    config_id = await seed_llm_config(session, current_user.id or 1)
    conversation_uuid = await seed_conversation(session, current_user.id or 1)

    with (
        patch("sparkth.plugins.compose.routes.completions.get_provider", return_value=_provider()),
        patch("sparkth.plugins.compose.classifiers.base.get_provider"),
        patch(
            "sparkth.plugins.compose.classifiers.message_scope.MessageScopeClassifier.classify",
            new_callable=AsyncMock,
            side_effect=openai.APIConnectionError(request=_OPENAI_REQUEST),
        ),
    ):
        response = await _turn(client, config_id, conversation_uuid=conversation_uuid)
        await join_live_tasks()

    assert response.status_code == 502
    (failure,) = await _events(analytics_session, "chat.turn_failed")
    assert failure["cause"] == "scope_classification_error"
    assert failure["conversation_id"] == conversation_uuid
    assert await _events(analytics_session, "chat.scope_classified") == []


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
            "sparkth.plugins.compose.classifiers.message_scope.MessageScopeClassifier.classify",
            new_callable=AsyncMock,
            return_value=_scope_verdict(True),
        ),
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
    (failure,) = await _events(analytics_session, "chat.turn_failed")
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
        patch(
            "sparkth.plugins.compose.classifiers.message_scope.MessageScopeClassifier.classify",
            new_callable=AsyncMock,
            return_value=_scope_verdict(True),
        ),
    ):
        await _turn(client, config_id, conversation_uuid=conversation_uuid)
        await join_live_tasks()

    assert await _events(analytics_session, "chat.turn_failed") == []


async def test_no_classifier_reason_reaches_any_payload(
    client: AsyncClient,
    current_user: User,
    session: AsyncSession,
    analytics_session: SQLAlchemyAsyncSession,
) -> None:
    """Both classifiers produce a model-authored reason that can quote the instructor."""
    config_id = await seed_llm_config(session, current_user.id or 1)
    conversation_uuid = await seed_conversation(session, current_user.id or 1)

    with (
        patch("sparkth.plugins.compose.routes.completions.get_provider", return_value=_provider()),
        patch("sparkth.plugins.compose.classifiers.base.get_provider"),
        patch(
            "sparkth.plugins.compose.classifiers.message_scope.MessageScopeClassifier.classify",
            new_callable=AsyncMock,
            return_value=_scope_verdict(False),
        ),
    ):
        await _turn(client, config_id, conversation_uuid=conversation_uuid, content="what is 2+2?")

    assert "Schrems" not in await _all_payloads(analytics_session)


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
    (failure,) = await _events(analytics_session, "chat.turn_failed")
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

    def _exploding_stream(*args: Any, **kwargs: Any) -> Any:
        raise OSError("the connection dropped mid-stream")

    provider = _provider()
    provider.stream_message = _exploding_stream

    with (
        patch("sparkth.plugins.compose.routes.completions.get_provider", return_value=provider),
        patch("sparkth.plugins.compose.classifiers.base.get_provider"),
        patch(
            "sparkth.plugins.compose.classifiers.message_scope.MessageScopeClassifier.classify",
            new_callable=AsyncMock,
            return_value=_scope_verdict(True),
        ),
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

    (failure,) = await _events(analytics_session, "chat.turn_failed")
    assert failure["cause"] == "unexpected"
    assert failure["streamed"] is True
    assert failure["conversation_id"] == conversation_uuid
    (sent,) = await _events(analytics_session, "chat.message_sent")
    assert sent["conversation_id"] == conversation_uuid
