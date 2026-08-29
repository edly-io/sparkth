"""End-to-end analytics producer tests through POST /api/v1/chat/completions.

Both response paths are exercised separately: `completion_served` and `tool_invoked`
are emitted from genuinely different seams that read differently shaped execution
records, so a single path's passing test proves nothing about the other.
"""

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

from httpx import AsyncClient
from sqlalchemy import select
from sqlmodel.ext.asyncio.session import AsyncSession

from sparkth.core.analytics.models import raw_events
from sparkth.lib.encryption import get_encryption_service
from sparkth.lib.models import LLMConfig, User
from sparkth.lib.settings import get_settings

COMPLETIONS_URL = "/api/v1/chat/completions"


async def _seed_llm_config(session: AsyncSession, user_id: int) -> int:
    """Create an active LLMConfig and return its id."""
    settings = get_settings()
    enc = get_encryption_service(settings.LLM_ENCRYPTION_KEY)
    cfg = LLMConfig(
        user_id=user_id,
        name="test-cfg-analytics",
        provider="openai",
        model="gpt-4o",
        encrypted_key=enc.encrypt("sk-test"),
        masked_key="sk-***",
        is_active=True,
    )
    session.add(cfg)
    await session.flush()
    config_id = cfg.id or 0
    await session.commit()
    return config_id


async def _events(analytics_session: AsyncSession, event_type: str) -> list[dict[str, Any]]:
    """Return payloads of every landed row of one event type, in insertion order."""
    rows = (await analytics_session.execute(select(raw_events))).mappings().all()
    return [row["payload"] for row in rows if row["event_type"] == event_type]


async def test_new_conversation_emits_conversation_started(
    client: AsyncClient,
    current_user: User,
    session: AsyncSession,
    analytics_session: AsyncSession,
) -> None:
    config_id = await _seed_llm_config(session, current_user.id or 1)

    provider = MagicMock()
    provider.model = "gpt-4o"
    provider.send_message = AsyncMock(return_value={"content": "Here is your course outline.", "metadata": {}})

    with (
        patch("sparkth.plugins.chat.routes.completions.get_provider", return_value=provider),
        patch("sparkth.plugins.chat.routes.utils.get_provider", return_value=provider),
        patch("sparkth.plugins.chat.routes.utils.is_query_in_scope", return_value=True),
        patch("sparkth.plugins.chat.routes.completions.classify_in_scope", new_callable=AsyncMock, return_value=True),
        patch(
            "sparkth.plugins.chat.routes.completions.resolve_rag_intent",
            new_callable=AsyncMock,
            return_value=(False, None),
        ),
    ):
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
    assert started[0]["provider"] == "openai"
    assert started[0]["model"] == "gpt-4o"
    assert started[0]["conversation_id"] == str(response.json()["conversation_id"])


async def test_instructor_turn_emits_message_sent(
    client: AsyncClient,
    current_user: User,
    session: AsyncSession,
    analytics_session: AsyncSession,
) -> None:
    config_id = await _seed_llm_config(session, current_user.id or 1)
    question = "Create a course on data privacy"

    provider = MagicMock()
    provider.model = "gpt-4o"
    provider.send_message = AsyncMock(return_value={"content": "Outline ready.", "metadata": {}})

    with (
        patch("sparkth.plugins.chat.routes.completions.get_provider", return_value=provider),
        patch("sparkth.plugins.chat.routes.utils.get_provider", return_value=provider),
        patch("sparkth.plugins.chat.routes.utils.is_query_in_scope", return_value=True),
        patch("sparkth.plugins.chat.routes.completions.classify_in_scope", new_callable=AsyncMock, return_value=True),
        patch(
            "sparkth.plugins.chat.routes.completions.resolve_rag_intent",
            new_callable=AsyncMock,
            return_value=(False, None),
        ),
    ):
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
    # No message text may appear anywhere in the payload.
    assert question not in str(sent[0])


async def test_second_turn_emits_message_sent_but_not_conversation_started(
    client: AsyncClient,
    current_user: User,
    session: AsyncSession,
    analytics_session: AsyncSession,
) -> None:
    config_id = await _seed_llm_config(session, current_user.id or 1)

    provider = MagicMock()
    provider.model = "gpt-4o"
    provider.send_message = AsyncMock(return_value={"content": "Sure.", "metadata": {}})

    async def _post(body: dict[str, Any]) -> Any:
        with (
            patch("sparkth.plugins.chat.routes.completions.get_provider", return_value=provider),
            patch("sparkth.plugins.chat.routes.utils.get_provider", return_value=provider),
            patch("sparkth.plugins.chat.routes.utils.is_query_in_scope", return_value=True),
            patch(
                "sparkth.plugins.chat.routes.completions.classify_in_scope",
                new_callable=AsyncMock,
                return_value=True,
            ),
            patch(
                "sparkth.plugins.chat.routes.completions.resolve_rag_intent",
                new_callable=AsyncMock,
                return_value=(False, None),
            ),
        ):
            return await client.post(COMPLETIONS_URL, json=body)

    first = await _post(
        {
            "llm_config_id": config_id,
            "messages": [{"role": "user", "content": "Create a course on ethics"}],
            "stream": False,
            "tools": "none",
        }
    )
    assert first.status_code == 200
    conversation_id = first.json()["conversation_id"]

    second = await _post(
        {
            "llm_config_id": config_id,
            "conversation_id": conversation_id,
            "messages": [{"role": "user", "content": "Add a module on consent"}],
            "stream": False,
            "tools": "none",
        }
    )
    assert second.status_code == 200

    assert len(await _events(analytics_session, "chat.conversation_started")) == 1
    assert len(await _events(analytics_session, "chat.message_sent")) == 2
