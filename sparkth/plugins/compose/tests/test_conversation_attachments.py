"""Tests for conversation document attachments."""

from typing import cast
from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import delete
from sqlalchemy import select as sa_select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession as SQLAlchemyAsyncSession
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from sparkth.core.analytics.models import raw_events
from sparkth.core.permissions.models import RoleAssignment
from sparkth.lib.documents import Document, DocumentStatus, soft_delete_document
from sparkth.lib.models import User
from sparkth.lib.permissions.scopes import GLOBAL, USER
from sparkth.lib.testing import AuditEventsFetcher, grant_permission_at_scope
from sparkth.plugins.compose.models import Conversation, ConversationAttachment
from sparkth.plugins.compose.plugin import ComposePlugin
from sparkth.plugins.compose.service import ComposeService


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


class TestComposeServiceAttach:
    """Tests for ComposeService attachment helper methods."""

    @pytest.mark.asyncio
    async def test_attach_document_returns_attachment(self, session: AsyncSession) -> None:
        conversation_id, _ = await _seed_conversation(session)
        _, document_id = await _seed_document(session)
        service = ComposeService()

        attachment, was_created = await service.attach_document(session, conversation_id, document_id)

        assert was_created is True
        assert attachment.id is not None
        assert attachment.conversation_id == conversation_id
        assert attachment.document_id == document_id

    @pytest.mark.asyncio
    async def test_attach_document_duplicate_is_idempotent(self, session: AsyncSession) -> None:
        conversation_id, _ = await _seed_conversation(session)
        _, document_id = await _seed_document(session)
        service = ComposeService()

        first, first_created = await service.attach_document(session, conversation_id, document_id)
        second, second_created = await service.attach_document(session, conversation_id, document_id)

        assert first.id == second.id
        # The second call wrote nothing, which is what stops a repeat being recorded as
        # an action.
        assert (first_created, second_created) == (True, False)

    @pytest.mark.asyncio
    async def test_detach_document_removes_row(self, session: AsyncSession) -> None:
        conversation_id, _ = await _seed_conversation(session)
        _, document_id = await _seed_document(session)
        service = ComposeService()

        await service.attach_document(session, conversation_id, document_id)
        await service.detach_document(session, conversation_id, document_id)

        attachments = await service.list_conversation_attachments(session, conversation_id)
        assert attachments.ready == []
        assert attachments.unusable == []

    @pytest.mark.asyncio
    async def test_detach_nonexistent_is_silent(self, session: AsyncSession) -> None:
        conversation_id, _ = await _seed_conversation(session)

        await ComposeService().detach_document(session, conversation_id, 999)

    @pytest.mark.asyncio
    async def test_list_conversation_attachments_returns_only_ready_documents(self, session: AsyncSession) -> None:
        conversation_id, _ = await _seed_conversation(session)
        _, ready_id = await _seed_document(session, name="ready.pdf", status=DocumentStatus.READY)
        _, failed_id = await _seed_document(session, name="failed.pdf", status=DocumentStatus.FAILED)
        service = ComposeService()

        await service.attach_document(session, conversation_id, ready_id)
        await service.attach_document(session, conversation_id, failed_id)

        attachments = await service.list_conversation_attachments(session, conversation_id)

        assert [document.id for document in attachments.ready] == [ready_id]
        # The failed one is no longer discarded: it is the half that explains why a turn
        # ignored a document the instructor attached.
        assert [document.id for document in attachments.unusable] == [failed_id]


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
            f"/api/v1/compose/conversations/{conversation_uuid}/attachments",
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
            f"/api/v1/compose/conversations/{conversation_uuid}/attachments",
            json={"document_id": document_id},
        )
        response2 = await client.post(
            f"/api/v1/compose/conversations/{conversation_uuid}/attachments",
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
            f"/api/v1/compose/conversations/{conversation_uuid}/attachments",
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
            f"/api/v1/compose/conversations/{uuid4()}/attachments",
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
        await ComposeService().attach_document(session, conversation_id, document_id)

        response = await client.delete(f"/api/v1/compose/conversations/{conversation_uuid}/attachments/{document_id}")

        assert response.status_code == 204

    @pytest.mark.asyncio
    async def test_delete_nonexistent_document_returns_404(
        self,
        client: AsyncClient,
        current_user: User,
        session: AsyncSession,
    ) -> None:
        _, conversation_uuid = await _seed_conversation(session, cast(int, current_user.id))

        response = await client.delete(f"/api/v1/compose/conversations/{conversation_uuid}/attachments/999")

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
        await ComposeService().attach_document(session, conversation_id, document_id)

        response = await client.get(f"/api/v1/compose/conversations/{conversation_uuid}/attachments")

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
        service = ComposeService()
        await service.attach_document(session, conversation_id, ready_id)
        await service.attach_document(session, conversation_id, failed_id)

        response = await client.get(f"/api/v1/compose/conversations/{conversation_uuid}/attachments")

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
        response = await client.get(f"/api/v1/compose/conversations/{uuid4()}/attachments")

        assert response.status_code == 404


OWNER_ID = 2
WRITE = "compose.conversation.write"


class TestAttachmentWriteGate:
    """Attach and detach need compose.conversation.write at the conversation owner's user scope."""

    @pytest.mark.asyncio
    async def test_attach_to_another_users_conversation_is_403_and_audited(
        self, client: AsyncClient, current_user: User, session: AsyncSession, audit_events: AuditEventsFetcher
    ) -> None:
        conversation_id, conversation_uuid = await _seed_conversation(session, OWNER_ID)
        _, document_id = await _seed_document(session, user_id=OWNER_ID)

        response = await client.post(
            f"/api/v1/compose/conversations/{conversation_uuid}/attachments", json={"document_id": document_id}
        )

        assert response.status_code == 403
        assert (await ComposeService().list_conversation_attachments(session, conversation_id)).ready == []
        (event,) = await audit_events()
        assert (event.action, event.target_id, event.error_detail) == ("denied", WRITE, f"scope=user:{OWNER_ID}")

    @pytest.mark.asyncio
    async def test_a_grant_at_a_third_user_is_403(
        self, client: AsyncClient, current_user: User, session: AsyncSession
    ) -> None:
        conversation_id, conversation_uuid = await _seed_conversation(session, OWNER_ID)
        _, document_id = await _seed_document(session, user_id=OWNER_ID)
        await ComposeService().attach_document(session, conversation_id, document_id)
        await grant_permission_at_scope(session, cast(int, current_user.id), WRITE, USER, "3")
        await session.commit()
        url = f"/api/v1/compose/conversations/{conversation_uuid}/attachments"

        attach = await client.post(url, json={"document_id": document_id})
        detach = await client.delete(f"{url}/{document_id}")

        assert (attach.status_code, detach.status_code) == (403, 403)

    @pytest.mark.asyncio
    @pytest.mark.parametrize("method", ["POST", "DELETE"])
    async def test_unknown_conversation_is_404_without_a_denial_row(
        self,
        client: AsyncClient,
        current_user: User,
        session: AsyncSession,
        audit_events: AuditEventsFetcher,
        method: str,
    ) -> None:
        await session.exec(delete(RoleAssignment))
        await session.commit()
        url = f"/api/v1/compose/conversations/{uuid4()}/attachments"

        if method == "POST":
            response = await client.post(url, json={"document_id": 1})
        else:
            response = await client.delete(f"{url}/1")

        assert response.status_code == 404
        assert await audit_events() == []

    @pytest.mark.asyncio
    async def test_detach_from_another_users_conversation_is_403(
        self, client: AsyncClient, current_user: User, session: AsyncSession
    ) -> None:
        conversation_id, conversation_uuid = await _seed_conversation(session, OWNER_ID)
        _, document_id = await _seed_document(session, user_id=OWNER_ID)
        await ComposeService().attach_document(session, conversation_id, document_id)

        response = await client.delete(f"/api/v1/compose/conversations/{conversation_uuid}/attachments/{document_id}")

        assert response.status_code == 403
        attached = (await ComposeService().list_conversation_attachments(session, conversation_id)).ready
        assert [document.id for document in attached] == [document_id]

    @pytest.mark.asyncio
    async def test_own_conversation_without_a_grant_is_403(
        self, client: AsyncClient, current_user: User, session: AsyncSession
    ) -> None:
        conversation_id, conversation_uuid = await _seed_conversation(session, cast(int, current_user.id))
        _, document_id = await _seed_document(session, user_id=cast(int, current_user.id))
        await session.exec(delete(RoleAssignment))
        await session.commit()

        attach = await client.post(
            f"/api/v1/compose/conversations/{conversation_uuid}/attachments", json={"document_id": document_id}
        )
        detach = await client.delete(f"/api/v1/compose/conversations/{conversation_uuid}/attachments/{document_id}")

        assert (attach.status_code, detach.status_code) == (403, 403)

    @pytest.mark.asyncio
    @pytest.mark.parametrize("scope_id", [None, str(OWNER_ID)], ids=["global", "owner"])
    async def test_a_holder_attaches_and_detaches_the_owners_document(
        self, client: AsyncClient, current_user: User, session: AsyncSession, scope_id: str | None
    ) -> None:
        conversation_id, conversation_uuid = await _seed_conversation(session, OWNER_ID)
        _, document_id = await _seed_document(session, user_id=OWNER_ID)
        await grant_permission_at_scope(
            session, cast(int, current_user.id), WRITE, GLOBAL if scope_id is None else USER, scope_id
        )
        await session.commit()
        url = f"/api/v1/compose/conversations/{conversation_uuid}/attachments"

        attach = await client.post(url, json={"document_id": document_id})
        attached = (await ComposeService().list_conversation_attachments(session, conversation_id)).ready
        detach = await client.delete(f"{url}/{document_id}")

        assert (attach.status_code, detach.status_code) == (201, 204)
        assert [document.id for document in attached] == [document_id]
        assert (await ComposeService().list_conversation_attachments(session, conversation_id)).ready == []

    @pytest.mark.asyncio
    async def test_a_holder_cannot_attach_their_own_document_to_the_owners_conversation(
        self, client: AsyncClient, current_user: User, session: AsyncSession
    ) -> None:
        conversation_id, conversation_uuid = await _seed_conversation(session, OWNER_ID)
        _, document_id = await _seed_document(session, user_id=cast(int, current_user.id))
        await grant_permission_at_scope(session, cast(int, current_user.id), WRITE, GLOBAL)
        await session.commit()

        response = await client.post(
            f"/api/v1/compose/conversations/{conversation_uuid}/attachments", json={"document_id": document_id}
        )

        assert response.status_code == 404
        assert (await ComposeService().list_conversation_attachments(session, conversation_id)).ready == []


class TestSoftDeleteDetaches:
    """Deleting a document must take it out of every conversation it was in."""

    @pytest.mark.asyncio
    async def test_soft_delete_removes_the_attachment_row(self, session: AsyncSession) -> None:
        plugin = ComposePlugin()  # noqa: F841 - keeps the weakly-keyed hook entries alive
        conversation_id, _ = await _seed_conversation(session)
        _, document_id = await _seed_document(session)
        await ComposeService().attach_document(session, conversation_id, document_id)

        await soft_delete_document(session, document_id)
        await session.commit()

        rows = await session.exec(
            select(ConversationAttachment).where(ConversationAttachment.document_id == document_id)
        )
        assert rows.all() == []

    @pytest.mark.asyncio
    async def test_deleted_document_stops_being_listed(self, session: AsyncSession) -> None:
        plugin = ComposePlugin()  # noqa: F841 - keeps the weakly-keyed hook entries alive
        conversation_id, _ = await _seed_conversation(session)
        _, document_id = await _seed_document(session)
        await ComposeService().attach_document(session, conversation_id, document_id)

        await soft_delete_document(session, document_id)
        await session.commit()

        attachments = await ComposeService().list_conversation_attachments(session, conversation_id)
        assert attachments.ready == []
        assert attachments.unusable == [], "a deleted document must not keep costing every turn"

    @pytest.mark.asyncio
    async def test_detachment_is_recorded_in_analytics(
        self, session: AsyncSession, analytics_session: SQLAlchemyAsyncSession
    ) -> None:
        """Issue #702 point 2: a document could leave a conversation with nothing recording it."""
        plugin = ComposePlugin()  # noqa: F841 - keeps the weakly-keyed hook entries alive
        conversation_id, conversation_uuid = await _seed_conversation(session)
        document, document_id = await _seed_document(session)
        await ComposeService().attach_document(session, conversation_id, document_id)

        await soft_delete_document(session, document_id)
        await session.commit()

        rows = (await analytics_session.execute(sa_select(raw_events))).mappings().all()
        detached = [row["payload"] for row in rows if row["event_type"] == "compose.document_detached"]
        assert len(detached) == 1
        assert detached[0]["conversation_id"] == conversation_uuid
        assert detached[0]["document_id"] == document_id
        assert detached[0]["seconds_attached"] >= 0

    @pytest.mark.asyncio
    async def test_every_holding_conversation_is_detached(self, session: AsyncSession) -> None:
        """One document can be in several conversations; deleting it must clear all of them."""
        plugin = ComposePlugin()  # noqa: F841 - keeps the weakly-keyed hook entries alive
        first_id, _ = await _seed_conversation(session)
        second_id, _ = await _seed_conversation(session)
        _, document_id = await _seed_document(session)
        await ComposeService().attach_document(session, first_id, document_id)
        await ComposeService().attach_document(session, second_id, document_id)

        await soft_delete_document(session, document_id)
        await session.commit()

        for conversation_id in (first_id, second_id):
            attachments = await ComposeService().list_conversation_attachments(session, conversation_id)
            assert attachments.ready == []
            assert attachments.unusable == []
