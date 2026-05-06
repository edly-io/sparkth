"""Pydantic output schemas for RAG MCP tools."""

from pydantic import BaseModel

# NOTE: To avoid the circular import rag.types → rag.models → models.__init__ → rag.models
# we will avoid importing `RagStatus` in schemas.py — since it's a StrEnum, str works fine as the field type.


class FileInfo(BaseModel):
    id: int
    name: str
    mime_type: str | None
    size: int | None
    modified_time: str | None
    rag_status: str


class FileMetadata(BaseModel):
    id: int
    name: str
    rag_status: str
    size: int | None
    modified_time: str | None


class SectionKey(BaseModel):
    chapter: str | None
    section: str | None
    subsection: str | None


class ChunkStats(BaseModel):
    source_name: str
    chunk_count: int
    avg_token_count: float | None


class DocumentSection(BaseModel):
    source_name: str
    chapter: str | None
    section: str | None
    subsection: str | None
    chunk_count: int
    position_index: int
