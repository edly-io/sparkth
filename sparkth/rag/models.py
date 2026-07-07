"""Database models for RAG document chunk storage."""

from sqlalchemy import Column, Text
from sqlmodel import Field, SQLModel

from sparkth.models.base import TimestampedModel


class DocumentChunkLink(SQLModel, table=True):
    """Many-to-many bridge between documents and rag_document_chunks.

    Rows are immutable once inserted — no timestamps needed.
    """

    __tablename__ = "rag_document_chunk_links"

    document_id: int = Field(foreign_key="documents.id", primary_key=True)
    chunk_id: int = Field(foreign_key="rag_document_chunks.id", primary_key=True)


class DocumentChunk(TimestampedModel, table=True):
    """Stores document chunks for retrieval."""

    __tablename__ = "rag_document_chunks"

    id: int | None = Field(default=None, primary_key=True)

    # Source identification
    source_name: str = Field(max_length=500)

    # Chunk content
    content: str = Field(sa_column=Column(Text, nullable=False))

    # SHA-256 hash of the chunk content (for deduplication across documents)
    chunk_content_hash: str | None = Field(default=None, max_length=64, index=True)

    # Structured metadata (flattened from ChunkMetadata for SQL filtering)
    chapter: str | None = Field(default=None, max_length=500)
    section: str | None = Field(default=None, max_length=500)
    subsection: str | None = Field(default=None, max_length=500)

    # Token count for the chunk
    token_count: int | None = Field(default=None)
