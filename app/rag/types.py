from dataclasses import dataclass
from enum import StrEnum

from pydantic import BaseModel, Field

from app.rag.models import DocumentChunk


class DocType(StrEnum):
    PDF = "pdf"
    DOCX = "docx"
    HTML = "html"
    TXT = "txt"


class RagStatus(StrEnum):
    QUEUED = "queued"
    PROCESSING = "processing"
    READY = "ready"
    FAILED = "failed"


@dataclass
class ChunkMetadata:
    source_name: str
    chapter: str | None = None
    section: str | None = None
    subsection: str | None = None

    def to_dict(self) -> dict[str, str | None]:
        return {
            "source_name": self.source_name,
            "chapter": self.chapter,
            "section": self.section,
            "subsection": self.subsection,
        }


@dataclass
class Chunk:
    content: str
    metadata: ChunkMetadata


@dataclass
class SimilarityResult:
    """A chunk together with its cosine similarity score."""

    chunk: DocumentChunk
    similarity: float


@dataclass
class RAGContext:
    """Retrieved context ready for injection into an LLM prompt."""

    file_db_id: int
    source_name: str
    chunks: list[SimilarityResult]
    formatted_text: str
    ranked_sections: list[dict[str, str | None]] | None = None


@dataclass
class ChunkInput:
    """Input data for a single chunk to be embedded and stored.

    This is a standalone type so the store module compiles without
    the chunking PR (#202). Once that PR merges, callers can map
    ``Chunk`` / ``ChunkMetadata`` to ``ChunkInput`` trivially.
    """

    content: str
    source_name: str
    chapter: str | None = None
    section: str | None = None
    subsection: str | None = None
    token_count: int | None = None
    chunk_content_hash: str | None = None


class SectionRef(BaseModel):
    # We use Optional and default=None to handle the "use null for missing fields" requirement
    chapter: str | None = Field(default=None, description="The chapter title")
    section: str | None = Field(default=None, description="The section title")
    subsection: str | None = Field(default=None, description="The subsection title")


class RAGSearchAgentResponse(BaseModel):
    """Agent's decision about which sections to fetch directly."""

    source_name: str = Field(description="The document's source_name from get_document_structure")
    selected_sections: list[SectionRef] = Field(
        description="Sections to retrieve, matching values from get_document_structure exactly"
    )
