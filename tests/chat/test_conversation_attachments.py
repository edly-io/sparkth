"""Tests for conversation attachment model, service, and endpoints."""

from typing import cast
from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy.exc import IntegrityError
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core_plugins.chat.models import Conversation, ConversationAttachment
from app.core_plugins.chat.service import ChatService
from app.models.drive import DriveFile, DriveFolder
from app.models.user import User
from app.rag.types import RagStatus


async def _seed_drive_folder(session: AsyncSession, user_id: int = 1) -> tuple[DriveFolder, int]:
    """Helper: create a DriveFolder in the test DB. Returns (folder, folder_id)."""
    folder = DriveFolder(
        user_id=user_id,
        drive_folder_id="f1",
        drive_folder_name="Test Folder",
    )
    session.add(folder)
    await session.flush()
    folder_id = cast(int, folder.id)
    await session.commit()
    return folder, folder_id


async def _seed_drive_file(
    session: AsyncSession,
    folder_id: int,
    user_id: int = 1,
    name: str = "test.pdf",
    rag_status: RagStatus = RagStatus.READY,
) -> tuple[DriveFile, int]:
    """Helper: create a DriveFile in the test DB. Returns (file, file_id)."""
    file = DriveFile(
        folder_id=folder_id,
        user_id=user_id,
        drive_file_id=f"df_{name}",
        name=name,
        rag_status=rag_status,
    )
    session.add(file)
    await session.flush()
    file_id = cast(int, file.id)
    await session.commit()
    return file, file_id


async def _seed_conversation(session: AsyncSession, user_id: int = 1) -> tuple[int, str]:
    """Helper: create a Conversation in the test DB. Returns (conversation_id, conversation_uuid)."""
    conv = Conversation(
        user_id=user_id,
        provider="openai",
        model="gpt-4",
        title="Test Conversation",
        total_tokens_used=0,
        total_cost=0.0,
    )
    session.add(conv)
    await session.flush()
    conv_id = cast(int, conv.id)
    conv_uuid = str(conv.uuid)
    await session.commit()
    return conv_id, conv_uuid


class TestConversationAttachmentModel:
    """Tests for ConversationAttachment SQLModel."""

    @pytest.mark.asyncio
    async def test_attachment_persisted_with_correct_fields(self, session: AsyncSession) -> None:
        """ConversationAttachment persists with correct fields."""
        # Setup
        conv_id, _ = await _seed_conversation(session)
        folder, folder_id = await _seed_drive_folder(session)
        file, file_id = await _seed_drive_file(session, folder_id)

        # Act
        attachment = ConversationAttachment(
            conversation_id=conv_id,
            drive_file_id=file_id,
        )
        session.add(attachment)
        await session.flush()

        # Assert
        assert attachment.id is not None
        assert attachment.conversation_id == conv_id
        assert attachment.drive_file_id == file_id
        assert attachment.attached_at is not None

    @pytest.mark.asyncio
    async def test_unique_constraint_prevents_duplicate(self, session: AsyncSession) -> None:
        """Unique constraint on (conversation_id, drive_file_id) prevents duplicates."""
        # Setup
        conv_id, _ = await _seed_conversation(session)
        folder, folder_id = await _seed_drive_folder(session)
        file, file_id = await _seed_drive_file(session, folder_id)

        # Act - insert first
        attachment1 = ConversationAttachment(
            conversation_id=conv_id,
            drive_file_id=file_id,
        )
        session.add(attachment1)
        await session.commit()

        # Act - try to insert duplicate
        attachment2 = ConversationAttachment(
            conversation_id=conv_id,
            drive_file_id=file_id,
        )
        session.add(attachment2)

        # Assert
        with pytest.raises(IntegrityError):
            await session.commit()


class TestChatServiceAttach:
    """Tests for ChatService attachment helper methods."""

    @pytest.mark.asyncio
    async def test_attach_drive_file_returns_attachment(self, session: AsyncSession) -> None:
        """attach_drive_file returns the persisted attachment."""
        # Setup
        conv_id, _ = await _seed_conversation(session)
        folder, folder_id = await _seed_drive_folder(session)
        file, file_id = await _seed_drive_file(session, folder_id)
        service = ChatService()

        # Act
        attachment = await service.attach_drive_file(session, conversation_id=conv_id, drive_file_id=file_id)

        # Assert
        assert attachment.id is not None
        assert attachment.conversation_id == conv_id
        assert attachment.drive_file_id == file_id

    @pytest.mark.asyncio
    async def test_attach_drive_file_duplicate_is_idempotent(self, session: AsyncSession) -> None:
        """Calling attach_drive_file twice with same args is idempotent."""
        # Setup
        conv_id, _ = await _seed_conversation(session)
        folder, folder_id = await _seed_drive_folder(session)
        file, file_id = await _seed_drive_file(session, folder_id)
        service = ChatService()

        # Act
        attach1 = await service.attach_drive_file(session, conversation_id=conv_id, drive_file_id=file_id)
        attach2 = await service.attach_drive_file(session, conversation_id=conv_id, drive_file_id=file_id)

        # Assert - same ID, no exception
        assert attach1.id == attach2.id

    @pytest.mark.asyncio
    async def test_detach_drive_file_removes_row(self, session: AsyncSession) -> None:
        """detach_drive_file removes the attachment row."""
        # Setup
        conv_id, _ = await _seed_conversation(session)
        folder, folder_id = await _seed_drive_folder(session)
        file, file_id = await _seed_drive_file(session, folder_id)
        service = ChatService()

        # Act - attach, then detach
        await service.attach_drive_file(session, conversation_id=conv_id, drive_file_id=file_id)
        await service.detach_drive_file(session, conversation_id=conv_id, drive_file_id=file_id)

        # Assert - attachment is gone
        attachments = await service.list_conversation_attachments(session, conversation_id=conv_id)
        assert len(attachments) == 0

    @pytest.mark.asyncio
    async def test_detach_nonexistent_is_silent(self, session: AsyncSession) -> None:
        """detach_drive_file is silent when attachment doesn't exist."""
        # Setup
        conv_id, _ = await _seed_conversation(session)
        service = ChatService()

        # Act - detach something that was never attached
        # Should not raise
        await service.detach_drive_file(session, conversation_id=conv_id, drive_file_id=999)

    @pytest.mark.asyncio
    async def test_list_conversation_attachments_returns_only_ready_files(self, session: AsyncSession) -> None:
        """list_conversation_attachments filters to READY rag_status only."""
        # Setup
        conv_id, _ = await _seed_conversation(session)
        folder, folder_id = await _seed_drive_folder(session)
        ready_file, ready_file_id = await _seed_drive_file(
            session, folder_id, name="ready.pdf", rag_status=RagStatus.READY
        )
        failed_file, failed_file_id = await _seed_drive_file(
            session, folder_id, name="failed.pdf", rag_status=RagStatus.FAILED
        )
        service = ChatService()

        # Act - attach both
        await service.attach_drive_file(session, conversation_id=conv_id, drive_file_id=ready_file_id)
        await service.attach_drive_file(session, conversation_id=conv_id, drive_file_id=failed_file_id)

        # Act - list
        attachments = await service.list_conversation_attachments(session, conversation_id=conv_id)

        # Assert - only READY file returned
        assert len(attachments) == 1
        assert attachments[0].id == ready_file_id

    @pytest.mark.asyncio
    async def test_list_conversation_attachments_empty_when_none_attached(self, session: AsyncSession) -> None:
        """list_conversation_attachments returns empty list when none attached."""
        # Setup
        conv_id, _ = await _seed_conversation(session)
        service = ChatService()

        # Act
        attachments = await service.list_conversation_attachments(session, conversation_id=conv_id)

        # Assert
        assert attachments == []


class TestAttachmentEndpoints:
    """Tests for attachment REST endpoints."""

    @pytest.mark.asyncio
    async def test_post_attachment_returns_201(
        self,
        client: AsyncClient,
        current_user: User,
        session: AsyncSession,
    ) -> None:
        """POST /conversations/{uuid}/attachments returns 201."""
        # Setup
        conv_id, conv_uuid = await _seed_conversation(session, user_id=cast(int, current_user.id))
        folder, folder_id = await _seed_drive_folder(session, user_id=cast(int, current_user.id))
        file, file_id = await _seed_drive_file(session, folder_id, user_id=cast(int, current_user.id))

        # Act
        response = await client.post(
            f"/api/v1/chat/conversations/{conv_uuid}/attachments",
            json={"drive_file_id": file_id},
        )

        # Assert
        assert response.status_code == 201
        data = response.json()
        assert data["conversation_id"] == conv_id
        assert data["drive_file_id"] == file_id
        assert "id" in data
        assert "attached_at" in data

    @pytest.mark.asyncio
    async def test_post_attachment_duplicate_returns_200_or_201(
        self,
        client: AsyncClient,
        current_user: User,
        session: AsyncSession,
    ) -> None:
        """POSTing same attachment twice is idempotent (returns 2xx)."""
        # Setup
        conv_id, conv_uuid = await _seed_conversation(session, user_id=cast(int, current_user.id))
        folder, folder_id = await _seed_drive_folder(session, user_id=cast(int, current_user.id))
        file, file_id = await _seed_drive_file(session, folder_id, user_id=cast(int, current_user.id))

        # Act - first POST
        response1 = await client.post(
            f"/api/v1/chat/conversations/{conv_uuid}/attachments",
            json={"drive_file_id": file_id},
        )
        assert response1.status_code == 201

        # Act - second POST
        response2 = await client.post(
            f"/api/v1/chat/conversations/{conv_uuid}/attachments",
            json={"drive_file_id": file_id},
        )

        # Assert - idempotent attach always returns 201
        assert response2.status_code == 201

    @pytest.mark.asyncio
    async def test_post_attachment_wrong_owner_returns_403_or_404(
        self,
        client: AsyncClient,
        current_user: User,
        session: AsyncSession,
    ) -> None:
        """POSTing with file owned by different user returns 403 or 404."""
        # Setup - conversation owned by current_user
        conv_id, conv_uuid = await _seed_conversation(session, user_id=cast(int, current_user.id))
        # File owned by different user
        folder, folder_id = await _seed_drive_folder(session, user_id=999)
        file, file_id = await _seed_drive_file(session, folder_id, user_id=999)

        # Act
        response = await client.post(
            f"/api/v1/chat/conversations/{conv_uuid}/attachments",
            json={"drive_file_id": file_id},
        )

        # Assert - file not found for this user returns 404
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_post_attachment_missing_conversation_returns_404(
        self,
        client: AsyncClient,
        current_user: User,
        session: AsyncSession,
    ) -> None:
        """POST to non-existent conversation UUID returns 404."""
        # Setup
        folder, folder_id = await _seed_drive_folder(session, user_id=cast(int, current_user.id))
        file, file_id = await _seed_drive_file(session, folder_id, user_id=cast(int, current_user.id))
        fake_uuid = uuid4()

        # Act
        response = await client.post(
            f"/api/v1/chat/conversations/{fake_uuid}/attachments",
            json={"drive_file_id": file_id},
        )

        # Assert
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_attachment_returns_204(
        self,
        client: AsyncClient,
        current_user: User,
        session: AsyncSession,
    ) -> None:
        """DELETE /conversations/{uuid}/attachments/{file_id} returns 204."""
        # Setup
        conv_id, conv_uuid = await _seed_conversation(session, user_id=cast(int, current_user.id))
        folder, folder_id = await _seed_drive_folder(session, user_id=cast(int, current_user.id))
        file, file_id = await _seed_drive_file(session, folder_id, user_id=cast(int, current_user.id))

        # Attach first
        service = ChatService()
        await service.attach_drive_file(session, conversation_id=conv_id, drive_file_id=file_id)

        # Act - delete
        response = await client.delete(f"/api/v1/chat/conversations/{conv_uuid}/attachments/{file_id}")

        # Assert
        assert response.status_code == 204

    @pytest.mark.asyncio
    async def test_delete_nonexistent_file_returns_404(
        self,
        client: AsyncClient,
        current_user: User,
        session: AsyncSession,
    ) -> None:
        """DELETE with a file_id that doesn't exist (or isn't owned) returns 404."""
        conv_id, conv_uuid = await _seed_conversation(session, user_id=cast(int, current_user.id))

        response = await client.delete(f"/api/v1/chat/conversations/{conv_uuid}/attachments/999")

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_attachment_wrong_owner_returns_404(
        self,
        client: AsyncClient,
        current_user: User,
        session: AsyncSession,
    ) -> None:
        """DELETE with a file owned by a different user returns 404."""
        conv_id, conv_uuid = await _seed_conversation(session, user_id=cast(int, current_user.id))
        folder, folder_id = await _seed_drive_folder(session, user_id=999)
        file, file_id = await _seed_drive_file(session, folder_id, user_id=999)

        response = await client.delete(f"/api/v1/chat/conversations/{conv_uuid}/attachments/{file_id}")

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_get_attachments_returns_attached_files(
        self,
        client: AsyncClient,
        current_user: User,
        session: AsyncSession,
    ) -> None:
        """GET /conversations/{uuid}/attachments returns list of attached READY files."""
        conv_id, conv_uuid = await _seed_conversation(session, user_id=cast(int, current_user.id))
        folder, folder_id = await _seed_drive_folder(session, user_id=cast(int, current_user.id))
        file, file_id = await _seed_drive_file(session, folder_id, user_id=cast(int, current_user.id), name="doc.pdf")
        service = ChatService()
        await service.attach_drive_file(session, conversation_id=conv_id, drive_file_id=file_id)

        response = await client.get(f"/api/v1/chat/conversations/{conv_uuid}/attachments")

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 1
        assert data[0]["id"] == file_id
        assert data[0]["name"] == "doc.pdf"

    @pytest.mark.asyncio
    async def test_get_attachments_excludes_non_ready(
        self,
        client: AsyncClient,
        current_user: User,
        session: AsyncSession,
    ) -> None:
        """GET only returns READY files, not pending/failed ones."""
        from app.rag.types import RagStatus

        conv_id, conv_uuid = await _seed_conversation(session, user_id=cast(int, current_user.id))
        folder, folder_id = await _seed_drive_folder(session, user_id=cast(int, current_user.id))
        ready_file, ready_id = await _seed_drive_file(
            session, folder_id, user_id=cast(int, current_user.id), name="ready.pdf", rag_status=RagStatus.READY
        )
        failed_file, failed_id = await _seed_drive_file(
            session, folder_id, user_id=cast(int, current_user.id), name="failed.pdf", rag_status=RagStatus.FAILED
        )
        service = ChatService()
        await service.attach_drive_file(session, conversation_id=conv_id, drive_file_id=ready_id)
        await service.attach_drive_file(session, conversation_id=conv_id, drive_file_id=failed_id)

        response = await client.get(f"/api/v1/chat/conversations/{conv_uuid}/attachments")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["id"] == ready_id

    @pytest.mark.asyncio
    async def test_get_attachments_missing_conversation_returns_404(
        self,
        client: AsyncClient,
        current_user: User,
        session: AsyncSession,
    ) -> None:
        """GET with non-existent conversation UUID returns 404."""
        from uuid import uuid4

        response = await client.get(f"/api/v1/chat/conversations/{uuid4()}/attachments")

        assert response.status_code == 404
