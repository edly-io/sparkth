"""The text of files uploaded from the computer reaches the model on a turn but is never stored."""

from unittest.mock import AsyncMock, MagicMock, patch

from httpx import AsyncClient
from sqlmodel.ext.asyncio.session import AsyncSession

from sparkth.lib.models import User
from sparkth.plugins.compose.planner import TurnRouting
from sparkth.plugins.compose.tests.helpers import seed_conversation, seed_llm_config, stored_messages

COMPLETIONS_URL = "/api/v1/compose/completions"


async def test_a_files_text_reaches_the_model_and_only_the_typed_turn_is_stored(
    client: AsyncClient, current_user: User, session: AsyncSession
) -> None:
    config_id = await seed_llm_config(session, current_user.id or 1)
    conversation_uuid = await seed_conversation(session, current_user.id or 1)
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
                "messages": [{"role": "user", "content": "Outline a course from this"}],
                "files": [{"name": "week1.txt", "text": "Photosynthesis basics"}],
                "stream": False,
                "tools": "none",
            },
        )

    assert response.status_code == 200
    model_input = turn.await_args_list[0].args[0]
    assert {"role": "user", "content": "[File: week1.txt]\n\nPhotosynthesis basics"} in model_input
    stored = await stored_messages(session, conversation_uuid)
    assert [message.content for message in stored] == ["Outline a course from this", "Here is the outline."]
