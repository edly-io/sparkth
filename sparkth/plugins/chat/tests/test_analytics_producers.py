"""End-to-end analytics producer tests through POST /api/v1/chat/completions.

Every test drives the real endpoint and asserts on rows that actually landed in the
analytics database, rather than on a mocked emit helper — the thing worth protecting
is that a real request produces a real row.

Both response paths get their own tests: `completion_served` and `tool_invoked` are
emitted from genuinely different seams reading differently shaped execution records,
so one path passing proves nothing about the other.
"""

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlmodel.ext.asyncio.session import AsyncSession

from sparkth.core.analytics.models import raw_events
from sparkth.lib.encryption import get_encryption_service
from sparkth.lib.models import LLMConfig, User
from sparkth.lib.settings import get_settings
from sparkth.plugins.chat.models import Conversation

COMPLETIONS_URL = "/api/v1/chat/completions"


async def _seed_llm_config(session: AsyncSession, user_id: int) -> int:
    """Create an active LLMConfig and return its id."""
    settings = get_settings()
    enc = get_encryption_service(settings.LLM_ENCRYPTION_KEY)
    config = LLMConfig(
        user_id=user_id,
        name="test-cfg-analytics",
        provider="openai",
        model="gpt-4o",
        encrypted_key=enc.encrypt("sk-test"),
        masked_key="sk-***",
        is_active=True,
    )
    session.add(config)
    await session.flush()
    config_id = config.id or 0  # capture before expiry
    await session.commit()
    return config_id


async def _seed_conversation(session: AsyncSession, user_id: int, llm_config_id: int) -> str:
    """Create a conversation the request can continue, and return its uuid."""
    conversation = Conversation(
        user_id=user_id,
        provider="openai",
        model="gpt-4o",
        llm_config_id=llm_config_id,
    )
    session.add(conversation)
    await session.flush()
    conversation_uuid = str(conversation.uuid)
    await session.commit()
    return conversation_uuid


async def _events(analytics_session: AsyncSession, event_type: str) -> list[dict[str, Any]]:
    """Return payloads of every landed row of one event type, in insertion order."""
    rows = (await analytics_session.execute(select(raw_events))).mappings().all()
    return [row["payload"] for row in rows if row["event_type"] == event_type]


async def _actors(analytics_session: AsyncSession, event_type: str) -> list[str]:
    """Return the actor_id of every landed row of one event type, in insertion order."""
    rows = (await analytics_session.execute(select(raw_events))).mappings().all()
    return [row["actor_id"] for row in rows if row["event_type"] == event_type]


def _non_streaming_provider(
    content: str = "Here is your course outline.", metadata: dict[str, Any] | None = None
) -> MagicMock:
    """A provider mock standing in for the non-streaming send_message path."""
    provider = MagicMock()
    provider.model = "gpt-4o"
    provider.system_prompt = ""
    provider.send_message = AsyncMock(return_value={"content": content, "metadata": metadata or {}})
    return provider


def _in_scope_classifier() -> AsyncMock:
    """A MessageScopeClassifier instance mock that judges every message in scope."""
    classifier = AsyncMock()
    classifier.in_scope = AsyncMock(return_value=True)
    return classifier


async def test_new_conversation_emits_conversation_started(
    client: AsyncClient,
    current_user: User,
    session: AsyncSession,
    analytics_session: AsyncSession,
) -> None:
    config_id = await _seed_llm_config(session, current_user.id or 1)

    with (
        patch("sparkth.plugins.chat.routes.completions.get_provider", return_value=_non_streaming_provider()),
        patch("sparkth.plugins.chat.routes.completions.MessageScopeClassifier") as mock_scope_cls,
        # conversation_title.py resolves its own provider for the title-generation background
        # task it schedules on the same create branch; without this it would reach out to the
        # real provider with the fake test API key.
        patch("sparkth.plugins.chat.conversation_title.get_provider", return_value=_non_streaming_provider()),
    ):
        mock_scope_cls.return_value = _in_scope_classifier()
        response = await client.post(
            COMPLETIONS_URL,
            json={
                "llm_config_id": config_id,
                "messages": [{"role": "user", "content": "Create a course on data privacy"}],
                "stream": False,
                "tools": "none",
            },
        )

    assert response.status_code == 200

    started = await _events(analytics_session, "chat.conversation_started")
    assert len(started) == 1
    assert started[0] == {
        "conversation_id": str(response.json()["conversation_id"]),
        "provider": "openai",
        "model": "gpt-4o",
    }
    assert await _actors(analytics_session, "chat.conversation_started") == [str(current_user.id)]


async def test_continuing_a_conversation_does_not_re_emit_conversation_started(
    client: AsyncClient,
    current_user: User,
    session: AsyncSession,
    analytics_session: AsyncSession,
) -> None:
    """The event marks a conversation beginning, so a second turn must not repeat it."""
    config_id = await _seed_llm_config(session, current_user.id or 1)
    conversation_uuid = await _seed_conversation(session, current_user.id or 1, config_id)

    with (
        patch("sparkth.plugins.chat.routes.completions.get_provider", return_value=_non_streaming_provider()),
        patch("sparkth.plugins.chat.routes.completions.MessageScopeClassifier") as mock_scope_cls,
    ):
        mock_scope_cls.return_value = _in_scope_classifier()
        response = await client.post(
            COMPLETIONS_URL,
            json={
                "llm_config_id": config_id,
                "conversation_id": conversation_uuid,
                "messages": [{"role": "user", "content": "Add a module on consent"}],
                "stream": False,
                "tools": "none",
            },
        )

    assert response.status_code == 200
    assert await _events(analytics_session, "chat.conversation_started") == []


async def test_refused_first_message_starts_no_conversation_and_emits_nothing(
    client: AsyncClient,
    current_user: User,
    session: AsyncSession,
    analytics_session: AsyncSession,
) -> None:
    """An out-of-scope opening message is refused before any conversation is written.

    Nothing at all is emitted for such a turn, so the whole raw-events table stays empty
    rather than just the conversation-started rows.
    """
    config_id = await _seed_llm_config(session, current_user.id or 1)

    refusing = AsyncMock()
    refusing.in_scope = AsyncMock(return_value=False)

    with (
        patch("sparkth.plugins.chat.routes.completions.get_provider"),
        patch("sparkth.plugins.chat.routes.completions.MessageScopeClassifier") as mock_scope_cls,
    ):
        mock_scope_cls.return_value = refusing
        response = await client.post(
            COMPLETIONS_URL,
            json={
                "llm_config_id": config_id,
                "messages": [{"role": "user", "content": "what is 2+2?"}],
                "stream": False,
                "tools": "none",
            },
        )

    assert response.status_code == 200
    assert (await analytics_session.execute(select(raw_events))).mappings().all() == []


async def test_instructor_turn_emits_message_sent(
    client: AsyncClient,
    current_user: User,
    session: AsyncSession,
    analytics_session: AsyncSession,
) -> None:
    config_id = await _seed_llm_config(session, current_user.id or 1)
    question = "Create a course on data privacy"

    with (
        patch("sparkth.plugins.chat.routes.completions.get_provider", return_value=_non_streaming_provider()),
        patch("sparkth.plugins.chat.routes.completions.MessageScopeClassifier") as mock_scope_cls,
        patch("sparkth.plugins.chat.conversation_title.get_provider", return_value=_non_streaming_provider()),
    ):
        mock_scope_cls.return_value = _in_scope_classifier()
        response = await client.post(
            COMPLETIONS_URL,
            json={
                "llm_config_id": config_id,
                "messages": [{"role": "user", "content": question}],
                "stream": False,
                "tools": "none",
            },
        )

    assert response.status_code == 200

    sent = await _events(analytics_session, "chat.message_sent")
    assert len(sent) == 1
    assert sent[0]["message_length"] == len(question)
    assert sent[0]["has_attachment"] is False
    assert sent[0]["provider"] == "openai"
    assert sent[0]["model"] == "gpt-4o"
    assert sent[0]["conversation_id"] == str(response.json()["conversation_id"])


async def test_attachment_turn_emits_message_sent_with_has_attachment(
    client: AsyncClient,
    current_user: User,
    session: AsyncSession,
    analytics_session: AsyncSession,
) -> None:
    """An inline upload on the turn sets ``has_attachment`` on the landed row."""
    config_id = await _seed_llm_config(session, current_user.id or 1)
    conversation_uuid = await _seed_conversation(session, current_user.id or 1, config_id)

    with (
        patch("sparkth.plugins.chat.routes.completions.get_provider", return_value=_non_streaming_provider()),
        patch("sparkth.plugins.chat.routes.completions.MessageScopeClassifier") as mock_scope_cls,
    ):
        mock_scope_cls.return_value = _in_scope_classifier()
        response = await client.post(
            COMPLETIONS_URL,
            json={
                "llm_config_id": config_id,
                "conversation_id": conversation_uuid,
                "messages": [
                    {
                        "role": "user",
                        "content": "Build a quiz from this syllabus",
                        "attachment": {"name": "syllabus.pdf", "size": 2048},
                    }
                ],
                "stream": False,
                "tools": "none",
            },
        )

    assert response.status_code == 200

    sent = await _events(analytics_session, "chat.message_sent")
    assert len(sent) == 1
    assert sent[0]["has_attachment"] is True


async def test_message_sent_payload_carries_no_message_text(
    client: AsyncClient,
    current_user: User,
    session: AsyncSession,
    analytics_session: AsyncSession,
) -> None:
    """A length, never the words. Course content must not reach the analytics store."""
    config_id = await _seed_llm_config(session, current_user.id or 1)
    question = "Draft a lesson about the Schrems II ruling"

    with (
        patch("sparkth.plugins.chat.routes.completions.get_provider", return_value=_non_streaming_provider()),
        patch("sparkth.plugins.chat.routes.completions.MessageScopeClassifier") as mock_scope_cls,
        patch("sparkth.plugins.chat.conversation_title.get_provider", return_value=_non_streaming_provider()),
    ):
        mock_scope_cls.return_value = _in_scope_classifier()
        response = await client.post(
            COMPLETIONS_URL,
            json={
                "llm_config_id": config_id,
                "messages": [{"role": "user", "content": question}],
                "stream": False,
                "tools": "none",
            },
        )

    assert response.status_code == 200

    sent = await _events(analytics_session, "chat.message_sent")
    assert set(sent[0]) == {
        "conversation_id",
        "provider",
        "model",
        "message_length",
        "has_attachment",
    }
    assert "Schrems" not in str(sent[0])


async def test_assistant_turns_in_the_request_do_not_emit_message_sent(
    client: AsyncClient,
    current_user: User,
    session: AsyncSession,
    analytics_session: AsyncSession,
) -> None:
    """A client replaying history sends assistant turns too; only instructor turns count."""
    config_id = await _seed_llm_config(session, current_user.id or 1)
    conversation_uuid = await _seed_conversation(session, current_user.id or 1, config_id)

    with (
        patch("sparkth.plugins.chat.routes.completions.get_provider", return_value=_non_streaming_provider()),
        patch("sparkth.plugins.chat.routes.completions.MessageScopeClassifier") as mock_scope_cls,
    ):
        mock_scope_cls.return_value = _in_scope_classifier()
        response = await client.post(
            COMPLETIONS_URL,
            json={
                "llm_config_id": config_id,
                "conversation_id": conversation_uuid,
                "messages": [
                    {"role": "assistant", "content": "Here is the outline so far."},
                    {"role": "user", "content": "Add a consent module"},
                ],
                "stream": False,
                "tools": "none",
            },
        )

    assert response.status_code == 200

    sent = await _events(analytics_session, "chat.message_sent")
    assert len(sent) == 1
    assert sent[0]["message_length"] == len("Add a consent module")


async def test_non_streaming_completion_emits_completion_served(
    client: AsyncClient,
    current_user: User,
    session: AsyncSession,
    analytics_session: AsyncSession,
) -> None:
    config_id = await _seed_llm_config(session, current_user.id or 1)

    with (
        patch(
            "sparkth.plugins.chat.routes.completions.get_provider",
            return_value=_non_streaming_provider("Outline ready."),
        ),
        patch("sparkth.plugins.chat.routes.completions.MessageScopeClassifier") as mock_scope_cls,
        patch("sparkth.plugins.chat.conversation_title.get_provider", return_value=_non_streaming_provider()),
    ):
        mock_scope_cls.return_value = _in_scope_classifier()
        response = await client.post(
            COMPLETIONS_URL,
            json={
                "llm_config_id": config_id,
                "messages": [{"role": "user", "content": "Create a course on data privacy"}],
                "stream": False,
                "tools": "none",
            },
        )

    assert response.status_code == 200

    served = await _events(analytics_session, "chat.completion_served")
    assert len(served) == 1
    assert served[0]["streamed"] is False
    assert served[0]["rag_used"] is False
    assert served[0]["tool_call_count"] == 0
    assert served[0]["provider"] == "openai"
    assert served[0]["model"] == "gpt-4o"
    assert served[0]["conversation_id"] == str(response.json()["conversation_id"])

    # No executions → no authoring-output events.
    assert await _events(analytics_session, "chat.tool_invoked") == []


async def test_non_streaming_tool_executions_emit_tool_invoked(
    client: AsyncClient,
    current_user: User,
    session: AsyncSession,
    analytics_session: AsyncSession,
) -> None:
    """The non-streaming path reads metadata["tool_executions"], keyed "tool"."""
    config_id = await _seed_llm_config(session, current_user.id or 1)

    provider = _non_streaming_provider(
        "Created the course run and an xblock.",
        {
            "num_executions": 2,
            "tool_executions": [
                {
                    "tool": "openedx_create_course_run",
                    "tool_input": {"title": "Data Privacy"},
                    "output": "course-v1:X+Y+Z",
                },
                {
                    "tool": "openedx_create_xblock",
                    "tool_input": {"category": "html"},
                    "output": "block-v1:...",
                },
            ],
        },
    )

    with (
        patch("sparkth.plugins.chat.routes.completions.get_provider", return_value=provider),
        patch("sparkth.plugins.chat.routes.completions.MessageScopeClassifier") as mock_scope_cls,
        patch("sparkth.plugins.chat.conversation_title.get_provider", return_value=_non_streaming_provider()),
    ):
        mock_scope_cls.return_value = _in_scope_classifier()
        response = await client.post(
            COMPLETIONS_URL,
            json={
                "llm_config_id": config_id,
                "messages": [{"role": "user", "content": "Create a course on data privacy"}],
                "stream": False,
                "tools": "none",
            },
        )

    assert response.status_code == 200

    served = await _events(analytics_session, "chat.completion_served")
    assert served[0]["tool_call_count"] == 2

    invoked = await _events(analytics_session, "chat.tool_invoked")
    assert [event["tool_name"] for event in invoked] == [
        "openedx_create_course_run",
        "openedx_create_xblock",
    ]
    # Tool arguments and outputs must never reach a payload.
    for event in invoked:
        assert set(event) == {"conversation_id", "tool_name", "tool_category"}
        assert "Data Privacy" not in str(event)


async def test_refused_query_emits_no_completion_served(
    client: AsyncClient,
    current_user: User,
    session: AsyncSession,
    analytics_session: AsyncSession,
) -> None:
    """A refusal never reaches the LLM, so it is not a completion."""
    config_id = await _seed_llm_config(session, current_user.id or 1)
    conversation_uuid = await _seed_conversation(session, current_user.id or 1, config_id)

    refusing = AsyncMock()
    refusing.in_scope = AsyncMock(return_value=False)

    with (
        patch("sparkth.plugins.chat.routes.completions.get_provider"),
        patch("sparkth.plugins.chat.routes.completions.MessageScopeClassifier") as mock_scope_cls,
    ):
        mock_scope_cls.return_value = refusing
        response = await client.post(
            COMPLETIONS_URL,
            json={
                "llm_config_id": config_id,
                "conversation_id": conversation_uuid,
                "messages": [{"role": "user", "content": "what is 2+2?"}],
                "stream": False,
                "tools": "none",
            },
        )

    assert response.status_code == 200
    assert await _events(analytics_session, "chat.completion_served") == []


async def test_analytics_emission_failure_propagates_from_the_completion(
    client: AsyncClient,
    current_user: User,
    session: AsyncSession,
) -> None:
    """The error-handling contract: a failed analytics write is never hidden.

    Emission runs in a background task, so in production the completion response is
    already on the wire and this surfaces as a logged unhandled task error. Under the
    httpx ASGI test transport the background task runs inside the request, so the
    exception is re-raised here — which is exactly what lets us assert it was not
    swallowed.
    """
    config_id = await _seed_llm_config(session, current_user.id or 1)

    with (
        patch(
            "sparkth.plugins.chat.routes.completions.get_provider",
            return_value=_non_streaming_provider("Outline ready."),
        ),
        patch("sparkth.plugins.chat.routes.completions.MessageScopeClassifier") as mock_scope_cls,
        patch("sparkth.plugins.chat.conversation_title.get_provider", return_value=_non_streaming_provider()),
        patch("sparkth.lib.analytics.ingest_event", side_effect=RuntimeError("analytics exploded")),
        pytest.raises(RuntimeError, match="analytics exploded"),
    ):
        mock_scope_cls.return_value = _in_scope_classifier()
        await client.post(
            COMPLETIONS_URL,
            json={
                "llm_config_id": config_id,
                "messages": [{"role": "user", "content": "Create a course on data privacy"}],
                "stream": False,
                "tools": "none",
            },
        )


def _streaming_provider(events: list[dict[str, Any]]) -> MagicMock:
    """A provider mock whose stream_message yields the given SSE-source events."""

    async def _stream(*args: Any, **kwargs: Any) -> Any:
        for event in events:
            yield event

    provider = MagicMock()
    provider.model = "gpt-4o"
    provider.system_prompt = ""
    provider.stream_message = _stream
    return provider


async def test_streaming_completion_emits_served_and_tool_invoked(
    client: AsyncClient,
    current_user: User,
    session: AsyncSession,
    analytics_session: AsyncSession,
) -> None:
    """The streaming seam reads tool_end records, keyed "name".

    That is a different shape from the non-streaming path's {"tool", "tool_input",
    "output"}, so this path gets its own end-to-end assertion rather than trusting
    Task 3's.
    """
    config_id = await _seed_llm_config(session, current_user.id or 1)

    provider = _streaming_provider(
        [
            {"type": "tool_start", "name": "canvas_create_quiz"},
            {"type": "tool_end", "name": "canvas_create_quiz"},
            {"type": "tool_start", "name": "canvas_create_question"},
            {"type": "tool_end", "name": "canvas_create_question"},
            {"type": "token", "content": "Quiz created."},
        ]
    )

    with (
        patch("sparkth.plugins.chat.routes.completions.get_provider", return_value=provider),
        patch("sparkth.plugins.chat.routes.completions.MessageScopeClassifier") as mock_scope_cls,
        patch("sparkth.plugins.chat.conversation_title.get_provider", return_value=_non_streaming_provider()),
    ):
        mock_scope_cls.return_value = _in_scope_classifier()
        response = await client.post(
            COMPLETIONS_URL,
            json={
                "llm_config_id": config_id,
                "messages": [{"role": "user", "content": "Create a quiz on data privacy"}],
                "stream": True,
                "tools": "none",
            },
        )

    assert response.status_code == 200
    # Reading the body drains the SSE generator, which only returns once the detached
    # stream task has emitted its done event — so the analytics writes have happened.
    assert "data: " in response.text

    served = await _events(analytics_session, "chat.completion_served")
    assert len(served) == 1
    assert served[0]["streamed"] is True
    assert served[0]["rag_used"] is False
    assert served[0]["tool_call_count"] == 2
    assert served[0]["provider"] == "openai"
    assert served[0]["model"] == "gpt-4o"

    invoked = await _events(analytics_session, "chat.tool_invoked")
    assert [event["tool_name"] for event in invoked] == [
        "canvas_create_quiz",
        "canvas_create_question",
    ]
    assert await _actors(analytics_session, "chat.completion_served") == [str(current_user.id)]


async def test_streaming_completion_without_tools_emits_zero_count(
    client: AsyncClient,
    current_user: User,
    session: AsyncSession,
    analytics_session: AsyncSession,
) -> None:
    config_id = await _seed_llm_config(session, current_user.id or 1)

    provider = _streaming_provider([{"type": "token", "content": "Here is an outline."}])

    with (
        patch("sparkth.plugins.chat.routes.completions.get_provider", return_value=provider),
        patch("sparkth.plugins.chat.routes.completions.MessageScopeClassifier") as mock_scope_cls,
        patch("sparkth.plugins.chat.conversation_title.get_provider", return_value=_non_streaming_provider()),
    ):
        mock_scope_cls.return_value = _in_scope_classifier()
        response = await client.post(
            COMPLETIONS_URL,
            json={
                "llm_config_id": config_id,
                "messages": [{"role": "user", "content": "Create a course on ethics"}],
                "stream": True,
                "tools": "none",
            },
        )

    assert response.status_code == 200
    assert "data: " in response.text

    served = await _events(analytics_session, "chat.completion_served")
    assert len(served) == 1
    assert served[0]["tool_call_count"] == 0
    assert await _events(analytics_session, "chat.tool_invoked") == []
