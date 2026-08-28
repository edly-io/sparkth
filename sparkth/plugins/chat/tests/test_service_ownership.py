"""Tests for requiring a conversation or document the caller owns.

Every route that works on one of these looked it up, found ``None``, and raised its own 404. The
lookup and the policy now live together: absent and belongs-to-someone-else are the same answer,
and the caller gets an exception rather than a value it has to remember to check.
"""

from uuid import uuid4

import pytest
from sqlmodel.ext.asyncio.session import AsyncSession

from sparkth.lib.documents import Document, DocumentStatus
from sparkth.lib.models import User
from sparkth.plugins.chat.exceptions import ConversationNotFound, DocumentNotFound
from sparkth.plugins.chat.models import Conversation
from sparkth.plugins.chat.service import ChatService


async def _seed_conversation(session: AsyncSession, user_id: int) -> Conversation:
    conversation = Conversation(user_id=user_id, provider="openai", model="gpt-4o", llm_config_id=None)
    session.add(conversation)
    await session.flush()
    await session.commit()
    return conversation


async def _seed_document(session: AsyncSession, user_id: int, deleted: bool = False) -> int:
    document = Document(user_id=user_id, name="doc.pdf", status=DocumentStatus.READY, is_deleted=deleted)
    session.add(document)
    await session.flush()
    document_id = document.id or 0
    await session.commit()
    return document_id


class TestRequiringADocument:
    """A document the caller does not own is reported as absent, not as forbidden.

    Saying "not yours" would confirm the document exists to someone who cannot see it, so both
    cases answer the same way.
    """

    @pytest.mark.asyncio
    async def test_an_owned_document_is_returned(self, session: AsyncSession, current_user: User) -> None:
        user_id = current_user.id or 1
        document_id = await _seed_document(session, user_id)

        document = await ChatService().require_owned_document(session, document_id, user_id)

        assert document.id == document_id

    @pytest.mark.asyncio
    async def test_a_document_that_does_not_exist_raises(self, session: AsyncSession, current_user: User) -> None:
        with pytest.raises(DocumentNotFound):
            await ChatService().require_owned_document(session, 9999, current_user.id or 1)

    @pytest.mark.asyncio
    async def test_another_users_document_raises(self, session: AsyncSession, current_user: User) -> None:
        user_id = current_user.id or 1
        theirs = await _seed_document(session, user_id + 99)

        with pytest.raises(DocumentNotFound):
            await ChatService().require_owned_document(session, theirs, user_id)

    @pytest.mark.asyncio
    async def test_a_deleted_document_raises(self, session: AsyncSession, current_user: User) -> None:
        """Deleting is not visible to the owner as a document that still attaches."""
        user_id = current_user.id or 1
        deleted = await _seed_document(session, user_id, deleted=True)

        with pytest.raises(DocumentNotFound):
            await ChatService().require_owned_document(session, deleted, user_id)


class TestRequiringAConversation:
    """The same rule for the thread a request names."""

    @pytest.mark.asyncio
    async def test_an_owned_conversation_is_returned(self, session: AsyncSession, current_user: User) -> None:
        user_id = current_user.id or 1
        existing = await _seed_conversation(session, user_id)

        conversation = await ChatService().require_owned_conversation(session, existing.uuid, user_id)

        assert conversation.id == existing.id

    @pytest.mark.asyncio
    async def test_an_unknown_uuid_raises(self, session: AsyncSession, current_user: User) -> None:
        with pytest.raises(ConversationNotFound):
            await ChatService().require_owned_conversation(session, uuid4(), current_user.id or 1)

    @pytest.mark.asyncio
    async def test_another_users_conversation_raises(self, session: AsyncSession, current_user: User) -> None:
        user_id = current_user.id or 1
        theirs = await _seed_conversation(session, user_id + 99)

        with pytest.raises(ConversationNotFound):
            await ChatService().require_owned_conversation(session, theirs.uuid, user_id)
