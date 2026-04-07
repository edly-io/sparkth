"""Database models for RAG vector storage."""

from typing import Any

from pgvector.sqlalchemy import Vector  # type: ignore[import-untyped]
from sqlalchemy import Column, Index, Text
from sqlmodel import Field, SQLModel

from app.models.base import TimestampedModel
from app.rag.embeddings import DEFAULT_EMBEDDING_DIMENSIONS


class DriveFileChunkLink(SQLModel, table=True):
    """Many-to-many bridge between drive_files and rag_document_chunks.

    Rows are immutable once inserted — no timestamps needed.
    """

    __tablename__ = "rag_drive_file_chunk_links"

    drive_file_id: int = Field(foreign_key="drive_files.id", primary_key=True)
    chunk_id: int = Field(foreign_key="rag_document_chunks.id", primary_key=True)


class DocumentChunk(TimestampedModel, table=True):
    """Stores document chunks with their vector embeddings."""

    __tablename__ = "rag_document_chunks"
    __table_args__ = (
        Index("idx_rag_chunks_user_source", "user_id", "source_name"),
        Index(
            "idx_rag_chunks_embedding_hnsw",
            "embedding",
            postgresql_using="hnsw",
            postgresql_with={"m": 16, "ef_construction": 64},
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
    )

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

    # Vector embedding
    embedding: Any = Field(sa_column=Column(Vector(DEFAULT_EMBEDDING_DIMENSIONS), nullable=False))

    # Embedding provenance
    embedding_model: str = Field(max_length=100)
    embedding_provider: str = Field(max_length=50)

    # Token count for the chunk
    token_count: int | None = Field(default=None)
