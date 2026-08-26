"""Tests for the conversation work a completion request performs.

Resolving or starting the conversation, attaching the documents the caller may attach, storing
the incoming turns and recording a pre-stream error all read and write the same rows, so they
live on ChatService. Each ran only through the route before this, which is why the cases below —
an unowned document, a message that is only an attachment, an error against a conversation that
is not there — had no assertions of their own.
"""

from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from sqlalchemy.exc import SQLAlchemyError
from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from sparkth.lib.documents import Document, DocumentStatus
from sparkth.lib.models import User
from sparkth.plugins.chat.exceptions import ConversationNotFound
from sparkth.plugins.chat.models import Conversation, ConversationAttachment, Message
from sparkth.plugins.chat.schemas import AttachmentMeta, ChatMessage
from sparkth.plugins.chat.service import ChatService


async def _seed_conversation(session: AsyncSession, user_id: int) -> Conversation:
    conversation = Conversation(user_id=user_id, provider="openai", model="gpt-4o", llm_config_id=None)
    session.add(conversation)
    await session.flush()
    await session.commit()
    return conversation


async def _seed_document(session: AsyncSession, user_id: int, name: str = "doc.pdf") -> int:
    document = Document(user_id=user_id, name=name, status=DocumentStatus.READY)
    session.add(document)
    await session.flush()
    document_id = document.id or 0
    await session.commit()
    return document_id


async def _attached_document_ids(session: AsyncSession, conversation_id: int) -> set[int]:
    result = await session.exec(
        select(ConversationAttachment.document_id).where(ConversationAttachment.conversation_id == conversation_id)
    )
    return set(result.all())


async def _stored_messages(session: AsyncSession, conversation_id: int) -> list[Message]:
    result = await session.exec(
        select(Message).where(Message.conversation_id == conversation_id).order_by(col(Message.id))
    )
    return list(result.all())


class TestResolvingTheConversation:
    """One entry point, whether the request continues a conversation or starts one."""

    @pytest.mark.asyncio
    async def test_an_existing_uuid_resolves_to_that_conversation(
        self, session: AsyncSession, current_user: User
    ) -> None:
        existing = await _seed_conversation(session, current_user.id or 1)

        resolved = await ChatService().get_or_create_conversation(
            session, existing.uuid, current_user.id or 1, None, "openai", "gpt-4o"
        )

        assert resolved.id == existing.id

    @pytest.mark.asyncio
    async def test_no_uuid_starts_a_new_conversation_with_the_given_title(
        self, session: AsyncSession, current_user: User
    ) -> None:
        created = await ChatService().get_or_create_conversation(
            session, None, current_user.id or 1, 4, "anthropic", "claude-sonnet-4-5", "Data privacy"
        )

        assert created.id is not None
        assert created.title == "Data privacy"
        assert created.llm_config_id == 4

    @pytest.mark.asyncio
    async def test_an_unknown_uuid_raises_rather_than_starting_one(
        self, session: AsyncSession, current_user: User
    ) -> None:
        """Silently starting a fresh conversation would strand the one the client meant."""
        with pytest.raises(ConversationNotFound):
            await ChatService().get_or_create_conversation(
                session, uuid4(), current_user.id or 1, None, "openai", "gpt-4o"
            )

    @pytest.mark.asyncio
    async def test_another_users_conversation_is_not_found(self, session: AsyncSession, current_user: User) -> None:
        """Ownership is part of resolving it: the uuid exists, but not for this caller."""
        someone_else = await _seed_conversation(session, (current_user.id or 1) + 99)

        with pytest.raises(ConversationNotFound):
            await ChatService().get_or_create_conversation(
                session, someone_else.uuid, current_user.id or 1, None, "openai", "gpt-4o"
            )


class TestAttachingRequestedDocuments:
    """A request may name documents; only the caller's own may be attached."""

    @pytest.mark.asyncio
    async def test_owned_documents_are_attached(self, session: AsyncSession, current_user: User) -> None:
        user_id = current_user.id or 1
        conversation = await _seed_conversation(session, user_id)
        first = await _seed_document(session, user_id, "a.pdf")
        second = await _seed_document(session, user_id, "b.pdf")

        await ChatService().attach_owned_documents(session, conversation.id or 0, [first, second], user_id)

        assert await _attached_document_ids(session, conversation.id or 0) == {first, second}

    @pytest.mark.asyncio
    async def test_a_document_owned_by_someone_else_is_skipped(self, session: AsyncSession, current_user: User) -> None:
        """The request names ids, so an id belonging to another user must not attach — and must
        not fail the turn either, since the rest of the request is legitimate."""
        user_id = current_user.id or 1
        conversation = await _seed_conversation(session, user_id)
        mine = await _seed_document(session, user_id, "mine.pdf")
        theirs = await _seed_document(session, user_id + 99, "theirs.pdf")

        await ChatService().attach_owned_documents(session, conversation.id or 0, [mine, theirs], user_id)

        assert await _attached_document_ids(session, conversation.id or 0) == {mine}

    @pytest.mark.asyncio
    async def test_a_skipped_document_is_logged(self, session: AsyncSession, current_user: User) -> None:
        user_id = current_user.id or 1
        conversation = await _seed_conversation(session, user_id)
        theirs = await _seed_document(session, user_id + 99, "theirs.pdf")

        with patch("sparkth.plugins.chat.service.logger") as mock_logger:
            await ChatService().attach_owned_documents(session, conversation.id or 0, [theirs], user_id)

        assert mock_logger.warning.called


class TestStoringTheIncomingTurns:
    """What the user sent has to be readable when the conversation is reopened."""

    @pytest.mark.asyncio
    async def test_plain_text_is_stored_as_sent(self, session: AsyncSession, current_user: User) -> None:
        conversation = await _seed_conversation(session, current_user.id or 1)
        messages = [ChatMessage(role="user", content="Create a course on data privacy")]

        await ChatService().add_incoming_messages(session, conversation.id or 0, messages)

        stored = await _stored_messages(session, conversation.id or 0)
        assert [m.content for m in stored] == ["Create a course on data privacy"]

    @pytest.mark.asyncio
    async def test_text_blocks_are_flattened(self, session: AsyncSession, current_user: User) -> None:
        conversation = await _seed_conversation(session, current_user.id or 1)
        messages = [
            ChatMessage(
                role="user",
                content=[{"type": "text", "text": "first"}, {"type": "text", "text": "second"}],
            )
        ]

        await ChatService().add_incoming_messages(session, conversation.id or 0, messages)

        stored = await _stored_messages(session, conversation.id or 0)
        assert stored[0].content == "first second"

    @pytest.mark.asyncio
    async def test_an_attachment_with_no_text_gets_a_stand_in(self, session: AsyncSession, current_user: User) -> None:
        """A document sent with no words still has to show as a turn in the transcript."""
        conversation = await _seed_conversation(session, current_user.id or 1)
        messages = [
            ChatMessage(
                role="user",
                content=[{"type": "document", "source": {"type": "base64", "data": ""}}],
                attachment=AttachmentMeta(name="syllabus.pdf", size=2048),
            )
        ]

        await ChatService().add_incoming_messages(session, conversation.id or 0, messages)

        stored = await _stored_messages(session, conversation.id or 0)
        assert stored[0].content == "[Document attachment]"
        assert stored[0].attachment_name == "syllabus.pdf"
        assert stored[0].attachment_size == 2048


class TestRecordingAPreStreamError:
    """An error raised before streaming starts still has to survive a page reload."""

    @pytest.mark.asyncio
    async def test_the_error_is_stored_against_the_conversation(
        self, session: AsyncSession, current_user: User
    ) -> None:
        conversation = await _seed_conversation(session, current_user.id or 1)

        await ChatService().record_error_message(
            session, conversation.uuid, current_user.id or 1, "The selected AI key is deactivated."
        )

        stored = await _stored_messages(session, conversation.id or 0)
        assert [(m.role, m.content, m.is_error) for m in stored] == [
            ("assistant", "The selected AI key is deactivated.", True)
        ]

    @pytest.mark.asyncio
    async def test_no_conversation_means_nothing_to_record(self, session: AsyncSession, current_user: User) -> None:
        """The failure can predate the conversation, and creating one to hold an error would
        leave the user a thread containing only that error."""
        await ChatService().record_error_message(session, None, current_user.id or 1, "boom")

    @pytest.mark.asyncio
    async def test_an_unknown_conversation_is_left_alone(self, session: AsyncSession, current_user: User) -> None:
        await ChatService().record_error_message(session, uuid4(), current_user.id or 1, "boom")

    @pytest.mark.asyncio
    async def test_a_database_failure_does_not_replace_the_error_being_reported(
        self, session: AsyncSession, current_user: User
    ) -> None:
        """This runs while an error is already on its way to the user; raising here would swap a
        useful message for a database one."""
        conversation = await _seed_conversation(session, current_user.id or 1)

        with patch.object(ChatService, "add_message", new_callable=AsyncMock, side_effect=SQLAlchemyError("gone")):
            await ChatService().record_error_message(session, conversation.uuid, current_user.id or 1, "boom")
