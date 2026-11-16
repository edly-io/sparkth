"""A conversation is an object of the ``conversation`` scope, nested under its owner's ``user`` scope."""

import pytest
from sqlmodel.ext.asyncio.session import AsyncSession

from sparkth.lib.permissions import can
from sparkth.lib.permissions.scopes import GLOBAL, USER, PermissionScope
from sparkth.lib.testing import grant_permission_at_scope, make_user
from sparkth.plugins.compose.models import Conversation
from sparkth.plugins.compose.permissions import CONVERSATION, CONVERSATION_READ
from sparkth.plugins.compose.service import ComposeService


async def test_a_conversation_carries_its_owners_scope_path(session: AsyncSession) -> None:
    owner = await make_user(session, "owner")
    assert owner.id is not None
    conversation = Conversation(user_id=owner.id, provider="openai", model="gpt-4o")
    session.add(conversation)
    await session.flush()

    assert conversation.parent_scope_path == f"user:{owner.id}"
    assert conversation.scope_path == f"user:{owner.id}/conversation:{conversation.uuid}"


async def test_an_explicit_parent_scope_path_is_kept(session: AsyncSession) -> None:
    owner = await make_user(session, "owner")
    other = await make_user(session, "other")
    assert owner.id is not None
    conversation = Conversation(
        user_id=owner.id, provider="openai", model="gpt-4o", parent_scope_path=f"user:{other.id}"
    )
    session.add(conversation)
    await session.flush()

    assert conversation.parent_scope_path == f"user:{other.id}"


async def test_a_stored_conversation_keeps_its_scope_path(session: AsyncSession) -> None:
    owner = await make_user(session, "owner")
    assert owner.id is not None
    owner_id = owner.id
    conversation = await ComposeService().create_conversation(
        session, user_id=owner_id, llm_config_id=None, provider="openai", model="gpt-4o"
    )
    conversation_id = conversation.id
    session.expire_all()

    reloaded = await session.get(Conversation, conversation_id)

    assert reloaded is not None
    assert reloaded.scope_path == f"user:{owner_id}/conversation:{reloaded.uuid}"


@pytest.mark.parametrize(
    ("grant_at", "expected"),
    [
        ("conversation", True),
        ("owner", True),
        ("global", True),
        ("other_conversation", False),
        ("third_user", False),
        ("none", False),
    ],
)
async def test_which_grants_reach_the_conversation(session: AsyncSession, grant_at: str, expected: bool) -> None:
    owner = await make_user(session, "owner")
    third = await make_user(session, "third")
    caller = await make_user(session, "caller")
    assert owner.id is not None
    assert caller.id is not None
    service = ComposeService()
    conversation = await service.create_conversation(
        session, user_id=owner.id, llm_config_id=None, provider="openai", model="gpt-4o"
    )
    other = await service.create_conversation(
        session, user_id=owner.id, llm_config_id=None, provider="openai", model="gpt-4o"
    )
    grants: dict[str, tuple[PermissionScope, str | None] | None] = {
        "conversation": (CONVERSATION, str(conversation.uuid)),
        "owner": (USER, str(owner.id)),
        "global": (GLOBAL, None),
        "other_conversation": (CONVERSATION, str(other.uuid)),
        "third_user": (USER, str(third.id)),
        "none": None,
    }
    grant = grants[grant_at]
    if grant is not None:
        await grant_permission_at_scope(session, caller.id, CONVERSATION_READ.name, grant[0], grant[1])
    await session.commit()

    allowed = await can(caller, CONVERSATION_READ, CONVERSATION, conversation.scope_path, session)

    assert allowed is expected
