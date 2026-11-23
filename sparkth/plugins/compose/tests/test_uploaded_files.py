"""Files uploaded from the computer come with one turn, and the cache keeps them for the turns after it."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient
from redis.exceptions import ConnectionError as RedisConnectionError
from sqlmodel.ext.asyncio.session import AsyncSession

from sparkth.lib.models import User
from sparkth.lib.testing import FakeRedis
from sparkth.plugins.compose.constants import MAX_COMBINED_UPLOAD_MB, UPLOADED_FILES_TTL_SECONDS
from sparkth.plugins.compose.planner import TurnRouting
from sparkth.plugins.compose.tests.helpers import seed_conversation, seed_llm_config, stored_messages

COMPLETIONS_URL = "/api/v1/compose/completions"
WEEK1 = {"name": "week1.txt", "text": "Photosynthesis basics"}
FILE_TURN = {"role": "user", "content": "[File: week1.txt]\n\nPhotosynthesis basics"}


async def _complete_turn(
    client: AsyncClient, config_id: int, conversation_uuid: str, text: str, files: list[dict[str, str]]
) -> list[dict[str, object]]:
    """Send one turn and return the messages the model was given."""
    reply = {"content": "Here is the outline.", "metadata": {}, "routing": TurnRouting()}
    with (
        patch("sparkth.plugins.compose.routes.completions.get_provider", return_value=MagicMock()),
        patch("sparkth.plugins.compose.routes.completions.complete_turn", new=AsyncMock(return_value=reply)) as turn,
    ):
        response = await client.post(
            COMPLETIONS_URL,
            json={
                "llm_config_id": config_id,
                "conversation_id": conversation_uuid,
                "messages": [{"role": "user", "content": text}],
                "files": files,
                "stream": False,
                "tools": "none",
            },
        )
    assert response.status_code == 200
    model_input: list[dict[str, object]] = turn.await_args_list[0].args[0]
    return model_input


async def test_a_files_text_reaches_the_model_and_only_the_typed_turn_is_stored(
    client: AsyncClient, current_user: User, session: AsyncSession, fake_redis: FakeRedis
) -> None:
    config_id = await seed_llm_config(session, current_user.id or 1)
    conversation_uuid = await seed_conversation(session, current_user.id or 1)

    model_input = await _complete_turn(
        client,
        config_id,
        conversation_uuid,
        "Outline a course from this",
        [WEEK1],
    )

    assert FILE_TURN in model_input
    stored = await stored_messages(session, conversation_uuid)
    assert [message.content for message in stored] == ["Outline a course from this", "Here is the outline."]


async def test_a_file_sent_once_reaches_the_model_on_later_turns(
    client: AsyncClient, current_user: User, session: AsyncSession, fake_redis: FakeRedis
) -> None:
    config_id = await seed_llm_config(session, current_user.id or 1)
    conversation_uuid = await seed_conversation(session, current_user.id or 1)
    await _complete_turn(
        client,
        config_id,
        conversation_uuid,
        "Outline a course from this",
        [WEEK1],
    )

    model_input = await _complete_turn(client, config_id, conversation_uuid, "Add a quiz", [])

    assert FILE_TURN in model_input


async def test_each_turn_renews_how_long_the_files_are_kept(
    client: AsyncClient, current_user: User, session: AsyncSession, fake_redis: FakeRedis
) -> None:
    config_id = await seed_llm_config(session, current_user.id or 1)
    conversation_uuid = await seed_conversation(session, current_user.id or 1)
    await _complete_turn(
        client,
        config_id,
        conversation_uuid,
        "Outline a course from this",
        [WEEK1],
    )
    fake_redis.ttls.clear()

    await _complete_turn(client, config_id, conversation_uuid, "Add a quiz", [])

    assert list(fake_redis.ttls.values()) == [UPLOADED_FILES_TTL_SECONDS]


async def test_a_file_sent_again_replaces_its_earlier_copy(
    client: AsyncClient, current_user: User, session: AsyncSession, fake_redis: FakeRedis
) -> None:
    """A retried turn brings its files again, and an edited file comes back under the same name."""
    config_id = await seed_llm_config(session, current_user.id or 1)
    conversation_uuid = await seed_conversation(session, current_user.id or 1)
    await _complete_turn(client, config_id, conversation_uuid, "Outline a course from this", [WEEK1])

    model_input = await _complete_turn(
        client,
        config_id,
        conversation_uuid,
        "Outline a course from this",
        [{"name": "week1.txt", "text": "Photosynthesis, revised"}],
    )

    file_turns = [turn for turn in model_input if str(turn["content"]).startswith("[File: ")]
    assert file_turns == [{"role": "user", "content": "[File: week1.txt]\n\nPhotosynthesis, revised"}]


async def test_a_turn_still_gets_its_files_when_the_cache_cannot_be_reached(
    client: AsyncClient,
    current_user: User,
    session: AsyncSession,
    fake_redis: FakeRedis,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config_id = await seed_llm_config(session, current_user.id or 1)
    conversation_uuid = await seed_conversation(session, current_user.id or 1)
    unreachable = AsyncMock(side_effect=RedisConnectionError("Connection refused"))
    monkeypatch.setattr(fake_redis, "get", unreachable)
    monkeypatch.setattr(fake_redis, "set", unreachable)

    model_input = await _complete_turn(client, config_id, conversation_uuid, "Outline a course from this", [WEEK1])

    assert FILE_TURN in model_input


@pytest.mark.parametrize(
    "file",
    [
        pytest.param({"name": "a" * 256, "text": "notes"}, id="name-too-long"),
        pytest.param(
            {"name": "notes.txt", "text": "a" * (MAX_COMBINED_UPLOAD_MB * 1024 * 1024 + 1)},
            id="more-text-than-a-conversation-may-keep",
        ),
    ],
)
async def test_a_file_outside_its_limits_is_refused_before_the_turn_starts(
    client: AsyncClient, current_user: User, session: AsyncSession, fake_redis: FakeRedis, file: dict[str, str]
) -> None:
    config_id = await seed_llm_config(session, current_user.id or 1)
    conversation_uuid = await seed_conversation(session, current_user.id or 1)

    response = await client.post(
        COMPLETIONS_URL,
        json={
            "llm_config_id": config_id,
            "conversation_id": conversation_uuid,
            "messages": [{"role": "user", "content": "Outline a course from this"}],
            "files": [file],
            "stream": False,
            "tools": "none",
        },
    )

    assert response.status_code == 422
    assert fake_redis.store == {}


async def test_a_turn_taking_the_conversations_files_over_the_limit_is_refused_and_stores_nothing(
    client: AsyncClient, current_user: User, session: AsyncSession, fake_redis: FakeRedis
) -> None:
    config_id = await seed_llm_config(session, current_user.id or 1)
    conversation_uuid = await seed_conversation(session, current_user.id or 1)
    megabyte = "a" * 1024 * 1024
    await _complete_turn(
        client,
        config_id,
        conversation_uuid,
        "Outline a course from this",
        [{"name": "big.txt", "text": megabyte * (MAX_COMBINED_UPLOAD_MB - 1)}],
    )
    kept_before = dict(fake_redis.store)

    response = await client.post(
        COMPLETIONS_URL,
        json={
            "llm_config_id": config_id,
            "conversation_id": conversation_uuid,
            "messages": [{"role": "user", "content": "And this one"}],
            "files": [{"name": "more.txt", "text": megabyte + "a"}],
            "stream": False,
            "tools": "none",
        },
    )

    assert response.status_code == 413
    assert response.json() == {"detail": "The files in this conversation can total at most 3 MB."}
    assert fake_redis.store == kept_before
    stored = await stored_messages(session, conversation_uuid)
    assert [message.content for message in stored] == ["Outline a course from this", "Here is the outline."]

    # The refused turn gave the conversation back, so the next one runs.
    await _complete_turn(client, config_id, conversation_uuid, "Never mind the second file", [])
