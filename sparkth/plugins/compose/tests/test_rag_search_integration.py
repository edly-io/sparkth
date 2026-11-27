"""Integration tests for the attached documents in the chat completion route: a step of the rag agent
searches them, and only the caller's own documents a request names are attached."""

import json
from datetime import datetime, timezone
from typing import Any, cast
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient
from langchain_core.messages import AIMessage
from sqlalchemy import select as sa_select
from sqlalchemy.ext.asyncio import AsyncSession as SQLAlchemyAsyncSession
from sqlmodel.ext.asyncio.session import AsyncSession

from sparkth.core.analytics.models import raw_events
from sparkth.lib.documents import Document, DocumentStatus
from sparkth.lib.encryption import get_encryption_service
from sparkth.lib.models import LLMConfig, User
from sparkth.lib.settings import get_settings
from sparkth.lib.testing import ScriptedChatModel
from sparkth.plugins.compose.models import Conversation, ConversationAttachment
from sparkth.plugins.compose.tests.helpers import answering_model, planning, stored_messages
from sparkth.plugins.compose.types import ConversationDocuments
from sparkth.rag.models import DocumentChunk, DocumentChunkLink


class _SeededData:
    def __init__(self, conv_id: int, conv_uuid: str, llm_config_id: int) -> None:
        self.conv_id = conv_id
        self.conv_uuid = conv_uuid
        self.llm_config_id = llm_config_id


async def _seed(session: AsyncSession, user_id: int) -> _SeededData:
    settings = get_settings()
    enc = get_encryption_service(settings.ENCRYPTION_KEY)
    llm_config = LLMConfig(
        user_id=user_id,
        name="test-cfg",
        provider="openai",
        model="gpt-4o",
        encrypted_key=enc.encrypt("sk-test"),
        masked_key="sk-***",
        is_active=True,
    )
    session.add(llm_config)
    await session.flush()
    llm_config_id = llm_config.id or 0  # capture before expiry

    conv = Conversation(
        user_id=user_id,
        provider="openai",
        model="gpt-4o",
        llm_config_id=llm_config_id,
    )
    session.add(conv)
    await session.flush()
    conv_id = conv.id or 0  # capture before expiry
    conv_uuid = str(conv.uuid)
    await session.commit()
    return _SeededData(conv_id=conv_id, conv_uuid=conv_uuid, llm_config_id=llm_config_id)


# Helpers for document seeding


async def _seed_document(session: AsyncSession, user_id: int, name: str = "test.pdf") -> int:
    document = Document(user_id=user_id, name=name, status=DocumentStatus.READY)
    session.add(document)
    await session.flush()
    document_id = cast(int, document.id)
    await session.commit()
    return document_id


def _mock_attachment(document_id: int = 1) -> MagicMock:
    """A stand-in for ConversationAttachment with the fields the route reads."""
    attachment = MagicMock()
    attachment.document_id = document_id
    attachment.attached_at = datetime.now(timezone.utc)
    return attachment


def _base_patches() -> tuple[Any, ...]:
    """Return the common patch stack shared by ownership-check tests."""
    return (
        patch("sparkth.plugins.compose.service.ComposeService.list_conversation_attachments", new_callable=AsyncMock),
        patch(
            "sparkth.plugins.compose.service.ComposeService.attach_document",
            new_callable=AsyncMock,
            # Shaped like the real return: the attachment plus whether this call created
            # it, with a real attached_at, which is what times the analytics event.
            return_value=(_mock_attachment(), True),
        ),
        patch("sparkth.plugins.compose.service.ComposeService.add_message", new_callable=AsyncMock),
        patch("sparkth.plugins.compose.service.ComposeService.get_conversation_messages", new_callable=AsyncMock),
        patch("sparkth.plugins.compose.routes.completions.get_provider"),
    )


def _configure_base_mocks(
    mock_list: AsyncMock,
    mock_add_msg: AsyncMock,
    mock_get_msgs: AsyncMock,
    mock_get_provider: MagicMock,
) -> None:
    mock_list.return_value = ConversationDocuments(ready=[], unusable=[])
    mock_get_msgs.return_value = []
    mock_msg = MagicMock()
    mock_msg.id = 99
    mock_msg.created_at = datetime.now(timezone.utc)
    mock_add_msg.return_value = mock_msg

    mock_provider = MagicMock()
    mock_provider.system_prompt = ""
    mock_provider.create_llm.return_value = answering_model("OK.", total_tokens=10)
    mock_get_provider.return_value = mock_provider


class TestARagStep:
    async def test_the_reply_lists_the_sections_the_rag_agent_selected(
        self,
        client: AsyncClient,
        current_user: User,
        session: AsyncSession,
        analytics_session: SQLAlchemyAsyncSession,
    ) -> None:
        seeded = await _seed(session, current_user.id or 1)
        document = Document(user_id=current_user.id or 1, name="Biology.pdf", status=DocumentStatus.READY)
        session.add(document)
        await session.flush()
        document_id = document.id or 0
        session.add(DocumentChunk(id=1, source_name="Biology.pdf", chapter="Cells", section="Nucleus", content="DNA."))
        session.add(DocumentChunkLink(document_id=document_id, chunk_id=1))
        session.add(ConversationAttachment(conversation_id=seeded.conv_id, document_id=document_id))
        await session.commit()
        selection = {
            "documents": [{"document_id": document_id, "sections": [{"chapter": "Cells", "section": "Nucleus"}]}]
        }
        provider = MagicMock(model="gpt-4o")
        provider.create_llm.return_value = ScriptedChatModel(
            messages=iter([AIMessage("", tool_calls=[{"name": "SectionSelection", "args": selection, "id": "s"}])]),
            disable_streaming=True,
        )
        to_rag = AIMessage("", tool_calls=[{"name": "rag", "args": {"request": "Find the nucleus."}, "id": "rag"}])

        with patch("sparkth.plugins.compose.routes.completions.get_provider", side_effect=planning(provider, to_rag)):
            response = await client.post(
                "/api/v1/compose/completions",
                json={
                    "llm_config_id": seeded.llm_config_id,
                    "conversation_id": seeded.conv_uuid,
                    "messages": [{"role": "user", "content": "What does the nucleus hold?"}],
                    "stream": True,
                    "tools": "none",
                },
            )

        assert response.status_code == 200
        reply = (await stored_messages(session, seeded.conv_uuid))[-1]
        assert json.loads(reply.model_metadata or "{}")["rag_sections"] == [
            {"type": "section", "name": "Cells / Nucleus", "source": "Biology.pdf"}
        ]
        rows = (await analytics_session.execute(sa_select(raw_events))).mappings().all()
        events = {row["event_type"]: row["payload"] for row in rows}
        assert events["compose.rag_search_completed"]["chunks_found"] == 1
        assert events["compose.completion_served"]["rag_used"] is True


class TestDocumentIdsOwnershipCheck:
    """Tests for the document_ids ownership-filter in compose_completion (routes.py:334-356).

    Verifies: all-owned IDs are each attached, mixed owned/unowned only attaches
    owned and logs a warning, all-unowned attaches nothing and logs a warning
    without raising a 4xx.
    """

    @pytest.mark.asyncio
    async def test_all_owned_ids_are_attached(
        self,
        client: AsyncClient,
        current_user: User,
        session: AsyncSession,
    ) -> None:
        """document_ids all owned by the current user → attach_document called for each."""
        seed = await _seed(session, current_user.id or 1)
        document1_id = await _seed_document(session, current_user.id or 1, "doc1.pdf")
        document2_id = await _seed_document(session, current_user.id or 1, "doc2.pdf")

        with (
            patch(
                "sparkth.plugins.compose.service.ComposeService.list_conversation_attachments",
                new_callable=AsyncMock,
            ) as mock_list,
            patch(
                "sparkth.plugins.compose.service.ComposeService.attach_document",
                new_callable=AsyncMock,
                return_value=(_mock_attachment(), True),
            ) as mock_attach,
            patch(
                "sparkth.plugins.compose.service.ComposeService.add_message",
                new_callable=AsyncMock,
            ) as mock_add_msg,
            patch(
                "sparkth.plugins.compose.service.ComposeService.get_conversation_messages",
                new_callable=AsyncMock,
            ) as mock_get_msgs,
            patch("sparkth.plugins.compose.routes.completions.get_provider") as mock_get_provider,
        ):
            _configure_base_mocks(mock_list, mock_add_msg, mock_get_msgs, mock_get_provider)

            response = await client.post(
                "/api/v1/compose/completions",
                json={
                    "llm_config_id": seed.llm_config_id,
                    "messages": [{"role": "user", "content": "Hello"}],
                    "conversation_id": seed.conv_uuid,
                    "stream": False,
                    "tools": "none",
                    "document_ids": [document1_id, document2_id],
                },
            )

        assert response.status_code == 200
        attached_ids = {call.args[2] for call in mock_attach.call_args_list}
        assert attached_ids == {document1_id, document2_id}

    @pytest.mark.asyncio
    async def test_mixed_owned_unowned_attaches_only_owned(
        self,
        client: AsyncClient,
        current_user: User,
        session: AsyncSession,
    ) -> None:
        """Owned ID is attached; non-existent ID is skipped — no 4xx, no attach for bad ID."""
        seed = await _seed(session, current_user.id or 1)
        owned_id = await _seed_document(session, current_user.id or 1, "owned.pdf")
        unowned_id = 9999  # does not exist in the DB

        with (
            patch(
                "sparkth.plugins.compose.service.ComposeService.list_conversation_attachments",
                new_callable=AsyncMock,
            ) as mock_list,
            patch(
                "sparkth.plugins.compose.service.ComposeService.attach_document",
                new_callable=AsyncMock,
                return_value=(_mock_attachment(), True),
            ) as mock_attach,
            patch(
                "sparkth.plugins.compose.service.ComposeService.add_message",
                new_callable=AsyncMock,
            ) as mock_add_msg,
            patch(
                "sparkth.plugins.compose.service.ComposeService.get_conversation_messages",
                new_callable=AsyncMock,
            ) as mock_get_msgs,
            patch("sparkth.plugins.compose.routes.completions.get_provider") as mock_get_provider,
        ):
            _configure_base_mocks(mock_list, mock_add_msg, mock_get_msgs, mock_get_provider)

            response = await client.post(
                "/api/v1/compose/completions",
                json={
                    "llm_config_id": seed.llm_config_id,
                    "messages": [{"role": "user", "content": "Hello"}],
                    "conversation_id": seed.conv_uuid,
                    "stream": False,
                    "tools": "none",
                    "document_ids": [owned_id, unowned_id],
                },
            )

        assert response.status_code == 200
        attached_ids = {call.args[2] for call in mock_attach.call_args_list}
        assert attached_ids == {owned_id}
        assert unowned_id not in attached_ids

    @pytest.mark.asyncio
    async def test_all_unowned_ids_no_attach_no_error(
        self,
        client: AsyncClient,
        current_user: User,
        session: AsyncSession,
    ) -> None:
        """All non-existent document_ids: no attach calls, 200 returned (not 4xx)."""
        seed = await _seed(session, current_user.id or 1)

        with (
            patch(
                "sparkth.plugins.compose.service.ComposeService.list_conversation_attachments",
                new_callable=AsyncMock,
            ) as mock_list,
            patch(
                "sparkth.plugins.compose.service.ComposeService.attach_document",
                new_callable=AsyncMock,
                return_value=(_mock_attachment(), True),
            ) as mock_attach,
            patch(
                "sparkth.plugins.compose.service.ComposeService.add_message",
                new_callable=AsyncMock,
            ) as mock_add_msg,
            patch(
                "sparkth.plugins.compose.service.ComposeService.get_conversation_messages",
                new_callable=AsyncMock,
            ) as mock_get_msgs,
            patch("sparkth.plugins.compose.routes.completions.get_provider") as mock_get_provider,
        ):
            _configure_base_mocks(mock_list, mock_add_msg, mock_get_msgs, mock_get_provider)

            response = await client.post(
                "/api/v1/compose/completions",
                json={
                    "llm_config_id": seed.llm_config_id,
                    "messages": [{"role": "user", "content": "Hello"}],
                    "conversation_id": seed.conv_uuid,
                    "stream": False,
                    "tools": "none",
                    "document_ids": [9997, 9998],
                },
            )

        assert response.status_code == 200
        mock_attach.assert_not_called()
