"""Tests for conversation document attachments."""

from typing import cast
from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy.exc import IntegrityError
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core_plugins.chat.models import Conversation, ConversationAttachment
from app.core_plugins.chat.service import ChatService
from app.lib.documents import Document, DocumentStatus
from app.models.user import User


async def _seed_document(
    session: AsyncSession,
    user_id: int = 1,
    name: str = "test.pdf",
    status: DocumentStatus = DocumentStatus.READY,
) -> tuple[Document, int]:
    """Create a core Document for attachment tests."""
    document = Document(user_id=user_id, name=name, status=status)
    session.add(document)
    await session.flush()
    document_id = cast(int, document.id)
    await session.commit()
    return document, document_id


async def _seed_conversation(session: AsyncSession, user_id: int = 1) -> tuple[int, str]:
    """Create a Conversation in the test DB. Returns (conversation_id, conversation_uuid)."""
    conversation = Conversation(
        user_id=user_id,
        provider="openai",
        model="gpt-4",
        title="Test Conversation",
        total_tokens_used=0,
        total_cost=0.0,
    )
    session.add(conversation)
    await session.flush()
    conversation_id = cast(int, conversation.id)
    conversation_uuid = str(conversation.uuid)
    await session.commit()
    return conversation_id, conversation_uuid


class TestConversationAttachmentModel:
    """Tests for ConversationAttachment SQLModel."""

    @pytest.mark.asyncio
    async def test_attachment_persisted_with_correct_fields(self, session: AsyncSession) -> None:
        conversation_id, _ = await _seed_conversation(session)
        _, document_id = await _seed_document(session)

        attachment = ConversationAttachment(conversation_id=conversation_id, document_id=document_id)
        session.add(attachment)
        await session.flush()

        assert attachment.id is not None
        assert attachment.conversation_id == conversation_id
        assert attachment.document_id == document_id
        assert attachment.attached_at is not None

    @pytest.mark.asyncio
    async def test_unique_constraint_prevents_duplicate(self, session: AsyncSession) -> None:
        conversation_id, _ = await _seed_conversation(session)
        _, document_id = await _seed_document(session)

        session.add(ConversationAttachment(conversation_id=conversation_id, document_id=document_id))
        await session.commit()

        session.add(ConversationAttachment(conversation_id=conversation_id, document_id=document_id))
        with pytest.raises(IntegrityError):
            await session.commit()


class TestChatServiceAttach:
    """Tests for ChatService attachment helper methods."""

    @pytest.mark.asyncio
    async def test_attach_document_returns_attachment(self, session: AsyncSession) -> None:
        conversation_id, _ = await _seed_conversation(session)
        _, document_id = await _seed_document(session)
        service = ChatService()

        attachment = await service.attach_document(session, conversation_id, document_id)

        assert attachment.id is not None
        assert attachment.conversation_id == conversation_id
        assert attachment.document_id == document_id

    @pytest.mark.asyncio
    async def test_attach_document_duplicate_is_idempotent(self, session: AsyncSession) -> None:
        conversation_id, _ = await _seed_conversation(session)
        _, document_id = await _seed_document(session)
        service = ChatService()

        first = await service.attach_document(session, conversation_id, document_id)
        second = await service.attach_document(session, conversation_id, document_id)

        assert first.id == second.id

    @pytest.mark.asyncio
    async def test_detach_document_removes_row(self, session: AsyncSession) -> None:
        conversation_id, _ = await _seed_conversation(session)
        _, document_id = await _seed_document(session)
        service = ChatService()

        await service.attach_document(session, conversation_id, document_id)
        await service.detach_document(session, conversation_id, document_id)

        attachments = await service.list_conversation_attachments(session, conversation_id)
        assert attachments == []

    @pytest.mark.asyncio
    async def test_detach_nonexistent_is_silent(self, session: AsyncSession) -> None:
        conversation_id, _ = await _seed_conversation(session)

        await ChatService().detach_document(session, conversation_id, 999)

    @pytest.mark.asyncio
    async def test_list_conversation_attachments_returns_only_ready_documents(self, session: AsyncSession) -> None:
        conversation_id, _ = await _seed_conversation(session)
        _, ready_id = await _seed_document(session, name="ready.pdf", status=DocumentStatus.READY)
        _, failed_id = await _seed_document(session, name="failed.pdf", status=DocumentStatus.FAILED)
        service = ChatService()

        await service.attach_document(session, conversation_id, ready_id)
        await service.attach_document(session, conversation_id, failed_id)

        attachments = await service.list_conversation_attachments(session, conversation_id)

        assert len(attachments) == 1
        assert attachments[0].id == ready_id


class TestAttachmentEndpoints:
    """Tests for attachment REST endpoints."""

    @pytest.mark.asyncio
    async def test_post_attachment_returns_201(
        self,
        client: AsyncClient,
        current_user: User,
        session: AsyncSession,
    ) -> None:
        conversation_id, conversation_uuid = await _seed_conversation(session, cast(int, current_user.id))
        _, document_id = await _seed_document(session, user_id=cast(int, current_user.id))

        response = await client.post(
            f"/api/v1/chat/conversations/{conversation_uuid}/attachments",
            json={"document_id": document_id},
        )

        assert response.status_code == 201
        data = response.json()
        assert data["conversation_id"] == conversation_id
        assert data["document_id"] == document_id
        assert "id" in data
        assert "attached_at" in data

    @pytest.mark.asyncio
    async def test_post_attachment_duplicate_is_idempotent(
        self,
        client: AsyncClient,
        current_user: User,
        session: AsyncSession,
    ) -> None:
        _, conversation_uuid = await _seed_conversation(session, cast(int, current_user.id))
        _, document_id = await _seed_document(session, user_id=cast(int, current_user.id))

        response1 = await client.post(
            f"/api/v1/chat/conversations/{conversation_uuid}/attachments",
            json={"document_id": document_id},
        )
        response2 = await client.post(
            f"/api/v1/chat/conversations/{conversation_uuid}/attachments",
            json={"document_id": document_id},
        )

        assert response1.status_code == 201
        assert response2.status_code == 201

    @pytest.mark.asyncio
    async def test_post_attachment_wrong_owner_returns_404(
        self,
        client: AsyncClient,
        current_user: User,
        session: AsyncSession,
    ) -> None:
        _, conversation_uuid = await _seed_conversation(session, cast(int, current_user.id))
        _, document_id = await _seed_document(session, user_id=999)

        response = await client.post(
            f"/api/v1/chat/conversations/{conversation_uuid}/attachments",
            json={"document_id": document_id},
        )

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_post_attachment_missing_conversation_returns_404(
        self,
        client: AsyncClient,
        current_user: User,
        session: AsyncSession,
    ) -> None:
        _, document_id = await _seed_document(session, user_id=cast(int, current_user.id))

        response = await client.post(
            f"/api/v1/chat/conversations/{uuid4()}/attachments",
            json={"document_id": document_id},
        )

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_attachment_returns_204(
        self,
        client: AsyncClient,
        current_user: User,
        session: AsyncSession,
    ) -> None:
        conversation_id, conversation_uuid = await _seed_conversation(session, cast(int, current_user.id))
        _, document_id = await _seed_document(session, user_id=cast(int, current_user.id))
        await ChatService().attach_document(session, conversation_id, document_id)

        response = await client.delete(f"/api/v1/chat/conversations/{conversation_uuid}/attachments/{document_id}")

        assert response.status_code == 204

    @pytest.mark.asyncio
    async def test_delete_nonexistent_document_returns_404(
        self,
        client: AsyncClient,
        current_user: User,
        session: AsyncSession,
    ) -> None:
        _, conversation_uuid = await _seed_conversation(session, cast(int, current_user.id))

        response = await client.delete(f"/api/v1/chat/conversations/{conversation_uuid}/attachments/999")

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_get_attachments_returns_attached_documents(
        self,
        client: AsyncClient,
        current_user: User,
        session: AsyncSession,
    ) -> None:
        conversation_id, conversation_uuid = await _seed_conversation(session, cast(int, current_user.id))
        _, document_id = await _seed_document(
            session,
            user_id=cast(int, current_user.id),
            name="doc.pdf",
            status=DocumentStatus.READY,
        )
        await ChatService().attach_document(session, conversation_id, document_id)

        response = await client.get(f"/api/v1/chat/conversations/{conversation_uuid}/attachments")

        assert response.status_code == 200
        data = response.json()
        assert data == [{"id": document_id, "name": "doc.pdf", "size": None}]

    @pytest.mark.asyncio
    async def test_get_attachments_excludes_non_ready(
        self,
        client: AsyncClient,
        current_user: User,
        session: AsyncSession,
    ) -> None:
        conversation_id, conversation_uuid = await _seed_conversation(session, cast(int, current_user.id))
        _, ready_id = await _seed_document(session, cast(int, current_user.id), "ready.pdf", DocumentStatus.READY)
        _, failed_id = await _seed_document(session, cast(int, current_user.id), "failed.pdf", DocumentStatus.FAILED)
        service = ChatService()
        await service.attach_document(session, conversation_id, ready_id)
        await service.attach_document(session, conversation_id, failed_id)

        response = await client.get(f"/api/v1/chat/conversations/{conversation_uuid}/attachments")

        assert response.status_code == 200
        data = response.json()
        assert data == [{"id": ready_id, "name": "ready.pdf", "size": None}]

    @pytest.mark.asyncio
    async def test_get_attachments_missing_conversation_returns_404(
        self,
        client: AsyncClient,
        current_user: User,
        session: AsyncSession,
    ) -> None:
        response = await client.get(f"/api/v1/chat/conversations/{uuid4()}/attachments")

        assert response.status_code == 404
