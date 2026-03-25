"""
Splits structured Markdown produced by extraction.py into semantically
coherent chunks aligned with the document's heading hierarchy.

Each chunk carries:
  - content: the Markdown text of that section
  - metadata: { chapter, section, subsection, source_name }
"""

import tiktoken
from langchain_text_splitters import MarkdownHeaderTextSplitter, RecursiveCharacterTextSplitter

from app.core.logger import get_logger
from app.rag.extraction import ExtractionResult
from app.rag.types import Chunk, ChunkMetadata

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Layer 2 – primary split on Markdown heading hierarchy
# ---------------------------------------------------------------------------

_HEADERS_TO_SPLIT_ON = [
    ("#", "chapter"),
    ("##", "section"),
    ("###", "subsection"),
]

_splitter = MarkdownHeaderTextSplitter(
    headers_to_split_on=_HEADERS_TO_SPLIT_ON,
    strip_headers=False,
)

# ---------------------------------------------------------------------------
# Layer 3 – secondary split for oversized chunks
# ---------------------------------------------------------------------------

_TOKEN_LIMIT = 512  # chunks larger than this are split further
_SECONDARY_OVERLAP = 50  # token overlap between sub-chunks

_ENCODING = tiktoken.get_encoding("cl100k_base")


def _count_tokens(text: str) -> int:
    """Return the number of tokens in *text* using the cl100k_base encoding."""
    return len(_ENCODING.encode(text))


_secondary_splitter = RecursiveCharacterTextSplitter(
    chunk_size=_TOKEN_LIMIT,
    chunk_overlap=_SECONDARY_OVERLAP,
    length_function=_count_tokens,
)


def _build_metadata(raw: dict[str, str], source_name: str) -> ChunkMetadata:
    """Map LangChain's raw metadata dict to a typed ChunkMetadata."""
    return ChunkMetadata(
        source_name=source_name,
        chapter=raw.get("chapter"),
        section=raw.get("section"),
        subsection=raw.get("subsection"),
    )


def _secondary_split(chunk: Chunk) -> list[Chunk]:
    """Split an oversized chunk into sub-chunks, inheriting parent metadata."""
    texts = _secondary_splitter.split_text(chunk.content)
    return [Chunk(content=t, metadata=chunk.metadata) for t in texts if t.strip()]


def _split(markdown: str, source_name: str) -> list[Chunk]:
    """
    Apply MarkdownHeaderTextSplitter (Layer 2) and return typed Chunk objects.
    Any chunk exceeding _TOKEN_LIMIT tokens is further split with
    RecursiveCharacterTextSplitter (Layer 3), inheriting the parent's metadata.
    Falls back to a single chunk for documents with no headings.
    """
    if not markdown.strip():
        logger.warning("'%s' produced empty markdown — skipping chunking.", source_name)
        return []

    docs = _splitter.split_text(markdown)

    if not docs:
        logger.warning(
            "'%s' produced no header-based chunks — treating as single chunk.",
            source_name,
        )
        return [Chunk(content=markdown, metadata=ChunkMetadata(source_name=source_name))]

    chunks: list[Chunk] = []
    for doc in docs:
        content = doc.page_content.strip()
        if not content:
            continue
        metadata = _build_metadata(doc.metadata, source_name)
        chunk = Chunk(content=content, metadata=metadata)

        if _count_tokens(content) > _TOKEN_LIMIT:
            logger.debug(
                "'%s' chunk >%d tokens — applying secondary split.",
                source_name,
                _TOKEN_LIMIT,
            )
            chunks.extend(_secondary_split(chunk))
        else:
            chunks.append(chunk)

    return chunks


def chunk_document(result: ExtractionResult) -> list[Chunk]:
    """
    Split an ExtractionResult into header-aligned Chunks.

    Usage:
        extraction = extract_to_markdown(file_bytes, "lecture.pdf")
        chunks     = chunk_document(extraction)
        for chunk in chunks:
            print(chunk.metadata.chapter, chunk.content[:80])
    """
    logger.info("Chunking '%s' (%d chars)", result.source_name, len(result.markdown))

    chunks = _split(result.markdown, result.source_name)

    logger.info(
        "Chunking complete: '%s' → %d chunks",
        result.source_name,
        len(chunks),
    )
    return chunks
