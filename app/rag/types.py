"""Shared data types for the RAG pipeline."""

from dataclasses import dataclass, field

from app.rag.enums import DocType
from app.rag.models import DocumentChunk


@dataclass(repr=False)
class ExtractionResult:
    """Raw output of a file extractor — structured Markdown plus metadata."""

    markdown: str
    doc_type: DocType
    source_name: str
    page_count: int | None = None
    warnings: list[str] = field(default_factory=list)

    def __repr__(self) -> str:  # pragma: no cover
        return f"<ExtractionResult source={self.source_name!r} type={self.doc_type} chars={len(self.markdown)}>"


@dataclass
class ChunkMetadata:
    """Heading hierarchy for a single chunk, used for SQL filtering and display."""

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
    """A single text chunk paired with its heading metadata."""

    content: str
    metadata: ChunkMetadata


@dataclass
class ChunkInput:
    """Flattened chunk data passed to the chunk store for persistence."""

    content: str
    source_name: str
    chapter: str | None = None
    section: str | None = None
    subsection: str | None = None
    token_count: int | None = None
    chunk_content_hash: str | None = None


@dataclass
class SimilarityResult:
    """A document chunk paired with a relevance score.

    The agentic retrieval path selects chunks by section rather than vector
    similarity, so `similarity` is always 1.0. The field is retained as the
    common chunk container shape used by the internal retrieval path.
    """

    chunk: DocumentChunk
    similarity: float


@dataclass
class RAGContext:
    """Retrieved context ready for injection into an LLM prompt."""

    file_db_id: int
    source_name: str
    chunks: list[SimilarityResult]
    formatted_text: str


@dataclass
class IngestionResult:
    """Outcome of a successful document ingestion."""

    new_chunks: int
    reused_chunks: int


@dataclass
class RetrievedChunk:
    """A chunk returned by retrieval, with its document/section attribution."""

    source_name: str
    chapter: str | None
    section: str | None
    subsection: str | None
    content: str
