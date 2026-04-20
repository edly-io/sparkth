"""Tests for RAGContextService."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.exc import SQLAlchemyError

from app.rag.context_service import (
    RAGContext,
    RAGContextService,
    _format_chunks_as_context,
    _resolve_source_name,
)
from app.rag.exceptions import DriveFileNotFoundError, RAGNotReadyError, RAGRetrievalError
from app.rag.models import DocumentChunk
from app.rag.store import SimilarityResult
from app.rag.types import RagStatus


def _make_drive_file(
    *,
    id: int = 1,
    user_id: int = 1,
    name: str = "doc.pdf",
    mime_type: str | None = "application/pdf",
    rag_status: RagStatus | None = RagStatus.READY,
    is_deleted: bool = False,
) -> MagicMock:
    df = MagicMock()
    df.id = id
    df.user_id = user_id
    df.name = name
    df.mime_type = mime_type
    df.rag_status = rag_status
    df.is_deleted = is_deleted
    return df


def _make_chunk(
    content: str = "Some content",
    chapter: str | None = "Chapter 1",
    section: str | None = "Section 1",
    subsection: str | None = None,
) -> MagicMock:
    chunk = MagicMock(spec=DocumentChunk)
    chunk.content = content
    chunk.chapter = chapter
    chunk.section = section
    chunk.subsection = subsection
    return chunk


def _make_sr(content: str = "Content", sim: float = 0.9) -> SimilarityResult:
    return SimilarityResult(chunk=_make_chunk(content), similarity=sim)


class TestFormatChunksAsContext:
    def test_no_results_returns_no_excerpts_message(self) -> None:
        result = _format_chunks_as_context("doc.pdf", [])
        assert "[DOCUMENT CONTEXT: doc.pdf]" in result
        assert "No relevant excerpts found" in result

    def test_single_result_formatted(self) -> None:
        result = _format_chunks_as_context("bio.pdf", [_make_sr("Chlorophyll content")])
        assert "[DOCUMENT CONTEXT: bio.pdf]" in result
        assert "Chlorophyll content" in result
        assert "Excerpt 1" in result

    def test_multiple_results_numbered(self) -> None:
        results = [_make_sr(f"Content {i}") for i in range(3)]
        result = _format_chunks_as_context("doc.pdf", results)
        assert "Excerpt 1" in result
        assert "Excerpt 2" in result
        assert "Excerpt 3" in result

    def test_section_label_uses_metadata(self) -> None:
        chunk = _make_chunk(content="Text", chapter="Ch1", section="Sec2", subsection=None)
        result = _format_chunks_as_context("doc.pdf", [SimilarityResult(chunk=chunk, similarity=0.8)])
        assert "Ch1 / Sec2" in result

    def test_no_metadata_uses_general(self) -> None:
        chunk = _make_chunk(content="Text", chapter=None, section=None, subsection=None)
        result = _format_chunks_as_context("doc.pdf", [SimilarityResult(chunk=chunk, similarity=0.8)])
        assert "General" in result


class TestResolveSourceName:
    def test_regular_pdf_unchanged(self) -> None:
        df = _make_drive_file(name="course.pdf", mime_type="application/pdf")
        assert _resolve_source_name(df) == "course.pdf"

    def test_google_doc_gets_pdf_suffix(self) -> None:
        df = _make_drive_file(
            name="My Course Outline",
            mime_type="application/vnd.google-apps.document",
        )
        assert _resolve_source_name(df) == "My Course Outline.pdf"

    def test_google_doc_already_has_pdf_suffix(self) -> None:
        df = _make_drive_file(name="doc.pdf", mime_type="application/vnd.google-apps.document")
        assert _resolve_source_name(df) == "doc.pdf"

    def test_none_mime_type_unchanged(self) -> None:
        df = _make_drive_file(name="notes.txt", mime_type=None)
        assert _resolve_source_name(df) == "notes.txt"

    def test_google_drawing_gets_pdf_suffix(self) -> None:
        df = _make_drive_file(
            name="diagram",
            mime_type="application/vnd.google-apps.drawing",
        )
        assert _resolve_source_name(df) == "diagram.pdf"


class TestRAGContextService:
    @pytest.mark.asyncio
    async def test_file_not_found_raises_error(self) -> None:
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.first.return_value = None
        mock_session.execute = AsyncMock(return_value=mock_result)

        service = RAGContextService(vector_store=MagicMock(), embedding_provider=MagicMock())

        with pytest.raises(DriveFileNotFoundError):
            await service.get_context_for_drive_file(
                session=mock_session, user_id=1, file_db_id=999, query="photosynthesis"
            )

    @pytest.mark.asyncio
    async def test_rag_processing_raises_not_ready(self) -> None:
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.first.return_value = _make_drive_file(rag_status=RagStatus.PROCESSING)
        mock_session.execute = AsyncMock(return_value=mock_result)

        service = RAGContextService(vector_store=MagicMock(), embedding_provider=MagicMock())

        with pytest.raises(RAGNotReadyError) as exc_info:
            await service.get_context_for_drive_file(session=mock_session, user_id=1, file_db_id=1, query="test")
        assert exc_info.value.rag_status == str(RagStatus.PROCESSING)

    @pytest.mark.asyncio
    async def test_rag_failed_raises_not_ready(self) -> None:
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.first.return_value = _make_drive_file(rag_status=RagStatus.FAILED)
        mock_session.execute = AsyncMock(return_value=mock_result)

        service = RAGContextService(vector_store=MagicMock(), embedding_provider=MagicMock())

        with pytest.raises(RAGNotReadyError):
            await service.get_context_for_drive_file(session=mock_session, user_id=1, file_db_id=1, query="test")

    @pytest.mark.asyncio
    async def test_embed_failure_raises_retrieval_error(self) -> None:
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.first.return_value = _make_drive_file()
        mock_session.execute = AsyncMock(return_value=mock_result)

        mock_embedding = AsyncMock()
        mock_embedding.embed_query = AsyncMock(side_effect=RuntimeError("model load failed"))

        service = RAGContextService(vector_store=AsyncMock(), embedding_provider=mock_embedding)

        with pytest.raises(RAGRetrievalError, match="Failed to embed query"):
            await service.get_context_for_drive_file(session=mock_session, user_id=1, file_db_id=1, query="test")

    @pytest.mark.asyncio
    async def test_similarity_search_failure_raises_retrieval_error(self) -> None:
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.first.return_value = _make_drive_file()
        mock_session.execute = AsyncMock(return_value=mock_result)

        mock_embedding = AsyncMock()
        mock_embedding.embed_query = AsyncMock(return_value=[0.1] * 384)

        mock_store = AsyncMock()
        mock_store.similarity_search = AsyncMock(side_effect=SQLAlchemyError("connection lost"))

        service = RAGContextService(vector_store=mock_store, embedding_provider=mock_embedding)

        with pytest.raises(RAGRetrievalError, match="Similarity search failed"):
            await service.get_context_for_drive_file(session=mock_session, user_id=1, file_db_id=1, query="test")

    @pytest.mark.asyncio
    async def test_successful_retrieval_returns_rag_context(self) -> None:
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.first.return_value = _make_drive_file(id=1, name="biology.pdf")
        mock_session.execute = AsyncMock(return_value=mock_result)

        similarity_results = [_make_sr("Chlorophyll content")]
        mock_store = AsyncMock()
        mock_store.similarity_search = AsyncMock(return_value=similarity_results)

        mock_embedding = AsyncMock()
        mock_embedding.embed_query = AsyncMock(return_value=[0.1] * 384)

        service = RAGContextService(vector_store=mock_store, embedding_provider=mock_embedding)
        result = await service.get_context_for_drive_file(
            session=mock_session, user_id=1, file_db_id=1, query="photosynthesis"
        )

        assert isinstance(result, RAGContext)
        assert result.file_db_id == 1
        assert result.source_name == "biology.pdf"
        assert result.chunks == similarity_results
        assert "biology.pdf" in result.formatted_text
        assert "Chlorophyll content" in result.formatted_text

    @pytest.mark.asyncio
    async def test_limit_and_threshold_forwarded_to_store(self) -> None:
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.first.return_value = _make_drive_file()
        mock_session.execute = AsyncMock(return_value=mock_result)

        mock_store = AsyncMock()
        mock_store.similarity_search = AsyncMock(return_value=[])
        mock_store.get_distinct_sections = AsyncMock(return_value=[])

        mock_embedding = AsyncMock()
        mock_embedding.embed_query = AsyncMock(return_value=[0.1] * 384)

        service = RAGContextService(vector_store=mock_store, embedding_provider=mock_embedding)
        await service.get_context_for_drive_file(
            session=mock_session,
            user_id=1,
            file_db_id=1,
            query="test",
            limit=5,
            similarity_threshold=0.8,
        )

        mock_store.similarity_search.assert_awaited_once_with(
            session=mock_session,
            user_id=1,
            query_embedding=[0.1] * 384,
            limit=5,
            source_names=["doc.pdf"],
            similarity_threshold=0.8,
            sections=None,
        )

    @pytest.mark.asyncio
    async def test_zero_results_returns_no_excerpts_formatted_text(self) -> None:
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.first.return_value = _make_drive_file(name="doc.pdf")
        mock_session.execute = AsyncMock(return_value=mock_result)

        mock_store = AsyncMock()
        mock_store.similarity_search = AsyncMock(return_value=[])

        mock_embedding = AsyncMock()
        mock_embedding.embed_query = AsyncMock(return_value=[0.1] * 384)

        service = RAGContextService(vector_store=mock_store, embedding_provider=mock_embedding)
        result = await service.get_context_for_drive_file(session=mock_session, user_id=1, file_db_id=1, query="test")
        assert "No relevant excerpts found" in result.formatted_text


class TestChunkIDLogging:
    @pytest.mark.asyncio
    async def test_chunk_ids_logged_on_successful_retrieval(self) -> None:
        """Verify that chunk IDs are logged after successful retrieval."""
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.first.return_value = _make_drive_file(id=1, name="biology.pdf")
        mock_session.execute = AsyncMock(return_value=mock_result)

        chunk1 = _make_chunk("Content 1")
        chunk1.id = 13
        chunk2 = _make_chunk("Content 2")
        chunk2.id = 85
        similarity_results = [
            SimilarityResult(chunk=chunk1, similarity=0.9),
            SimilarityResult(chunk=chunk2, similarity=0.8),
        ]
        mock_store = AsyncMock()
        mock_store.similarity_search = AsyncMock(return_value=similarity_results)

        mock_embedding = AsyncMock()
        mock_embedding.embed_query = AsyncMock(return_value=[0.1] * 384)

        service = RAGContextService(vector_store=mock_store, embedding_provider=mock_embedding)

        with patch("app.rag.context_service.logger") as mock_logger:
            await service.get_context_for_drive_file(
                session=mock_session, user_id=1, file_db_id=1, query="photosynthesis"
            )
            # Verify chunk IDs are logged
            log_calls = [str(call) for call in mock_logger.info.call_args_list]
            assert any("[13, 85]" in call for call in log_calls)
