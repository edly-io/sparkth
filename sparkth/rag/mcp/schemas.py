"""Pydantic output schemas for RAG MCP tools."""

from pydantic import BaseModel

# NOTE: RagStatus lives in sparkth.rag.enums; importing it here would create a circular import
# via sparkth.rag.enums → sparkth.rag.models → sparkth.core.models.__init__ → sparkth.rag.models.
# Using str avoids the cycle — RagStatus is a StrEnum so values are already plain strings.


class DocumentInfo(BaseModel):
    id: int
    name: str
    mime_type: str | None
    rag_status: str


class DocumentMetadata(BaseModel):
    id: int
    name: str
    mime_type: str | None
    rag_status: str


class SectionKey(BaseModel):
    chapter: str | None
    section: str | None
    subsection: str | None


class ChunkStats(BaseModel):
    source_name: str
    chunk_count: int
    avg_token_count: float | None
