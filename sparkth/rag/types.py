"""Shared data types for the RAG pipeline."""

from dataclasses import dataclass, field

from sparkth.rag.enums import DocType
from sparkth.rag.models import DocumentChunk


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
class RAGContext:
    """Retrieved context ready for injection into an LLM prompt."""

    document_id: int
    source_name: str
    chunks: list[DocumentChunk]
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


@dataclass
class DocumentSection:
    """A structural section in a document, with chunk count and document order."""

    source_name: str
    chapter: str | None
    section: str | None
    subsection: str | None
    chunk_count: int
    position_index: int

    def __repr__(self) -> str:
        """Match the previous Pydantic-style repr used in RAG agent tool output."""
        return (
            f"source_name={self.source_name!r} "
            f"chapter={self.chapter!r} "
            f"section={self.section!r} "
            f"subsection={self.subsection!r} "
            f"chunk_count={self.chunk_count!r} "
            f"position_index={self.position_index!r}"
        )

    def __str__(self) -> str:
        """Use the stable agent-facing representation for string conversion."""
        return repr(self)
