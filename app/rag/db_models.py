"""Database models for RAG vector storage."""

from sqlalchemy import Column, Index, Text
from sqlmodel import Field, SQLModel

from app.models.base import TimestampedModel


class DriveFileChunkLink(SQLModel, table=True):
    """Many-to-many bridge between drive_files and rag_document_chunks.

    Rows are immutable once inserted — no timestamps needed.
    """

    __tablename__ = "rag_drive_file_chunk_links"

    drive_file_id: int = Field(foreign_key="drive_files.id", primary_key=True)
    chunk_id: int = Field(foreign_key="rag_document_chunks.id", primary_key=True)


class DocumentChunk(TimestampedModel, table=True):
    """Stores document chunks for retrieval."""

    __tablename__ = "rag_document_chunks"
    __table_args__ = (Index("idx_rag_chunks_user_source", "user_id", "source_name"),)

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)

    # Source identification
    source_name: str = Field(max_length=500)

    # Chunk content
    content: str = Field(sa_column=Column(Text, nullable=False))

    # SHA-256 hash of the chunk content (for deduplication across files)
    chunk_content_hash: str | None = Field(default=None, max_length=64, index=True)

    # Structured metadata (flattened from ChunkMetadata for SQL filtering)
    chapter: str | None = Field(default=None, max_length=500)
    section: str | None = Field(default=None, max_length=500)
    subsection: str | None = Field(default=None, max_length=500)

    # Token count for the chunk
    token_count: int | None = Field(default=None)
