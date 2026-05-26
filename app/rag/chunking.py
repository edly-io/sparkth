"""
Splits structured Markdown produced by extraction.py into semantically
coherent chunks aligned with the document's heading hierarchy.

Three-layer chunking pipeline:
  Layer 1: extraction.py converts raw files to structured Markdown (upstream).
  Layer 2: MarkdownHeaderTextSplitter splits on heading hierarchy (#, ##, ###),
           producing one chunk per section with chapter/section/subsection metadata.
  Layer 3: Any chunk exceeding CHUNKING_TOKEN_LIMIT tokens is further split with
           RecursiveCharacterTextSplitter (token-aware, with overlap), inheriting
           the parent section's metadata.

Each chunk carries:
  - content: the Markdown text of that section
  - metadata: { chapter, section, subsection, source_name }
"""

import tiktoken
from langchain_text_splitters import MarkdownHeaderTextSplitter, RecursiveCharacterTextSplitter

from app.core.logger import get_logger
from app.rag.constants import (
    CHUNKING_MARKDOWN_HEADERS,
    CHUNKING_SECONDARY_OVERLAP,
    CHUNKING_TIKTOKEN_ENCODING,
    CHUNKING_TOKEN_LIMIT,
)
from app.rag.extraction import ExtractionResult
from app.rag.types import Chunk, ChunkMetadata

logger = get_logger(__name__)

_ENCODING = tiktoken.get_encoding(CHUNKING_TIKTOKEN_ENCODING)


class DocumentChunker:
    """Splits an ExtractionResult into header-aligned Chunks."""

    def __init__(self) -> None:
        self._header_splitter = MarkdownHeaderTextSplitter(
            headers_to_split_on=CHUNKING_MARKDOWN_HEADERS,
            strip_headers=False,
        )
        self._token_splitter = RecursiveCharacterTextSplitter(
            chunk_size=CHUNKING_TOKEN_LIMIT,
            chunk_overlap=CHUNKING_SECONDARY_OVERLAP,
            length_function=self._count_tokens,
        )

    @staticmethod
    def _count_tokens(text: str) -> int:
        """Return the number of tokens in *text* using the cl100k_base encoding."""
        return len(_ENCODING.encode(text))

    @staticmethod
    def _build_metadata(raw: dict[str, str], source_name: str) -> ChunkMetadata:
        """Map LangChain's raw metadata dict to a typed ChunkMetadata."""
        return ChunkMetadata(
            source_name=source_name,
            chapter=raw.get("chapter"),
            section=raw.get("section"),
            subsection=raw.get("subsection"),
        )

    def _split(self, markdown: str, source_name: str) -> list[Chunk]:
        """Apply MarkdownHeaderTextSplitter (Layer 2) then secondary split (Layer 3)."""
        if not markdown.strip():
            logger.warning("'%s' produced empty markdown — skipping chunking.", source_name)
            return []

        docs = self._header_splitter.split_text(markdown)

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
            metadata = self._build_metadata(doc.metadata, source_name)
            chunk = Chunk(content=content, metadata=metadata)

            if self._count_tokens(content) > CHUNKING_TOKEN_LIMIT:
                logger.debug(
                    "'%s' chunk >%d tokens — applying secondary split.",
                    source_name,
                    CHUNKING_TOKEN_LIMIT,
                )
                chunks.extend(self._secondary_split(chunk))
            else:
                chunks.append(chunk)

        return chunks

    def _secondary_split(self, chunk: Chunk) -> list[Chunk]:
        """Split an oversized chunk into sub-chunks, inheriting parent metadata."""
        texts = self._token_splitter.split_text(chunk.content)
        return [Chunk(content=t, metadata=chunk.metadata) for t in texts if t.strip()]

    def chunk(self, result: ExtractionResult) -> list[Chunk]:
        """Split an ExtractionResult into header-aligned Chunks."""
        logger.info("Chunking '%s' (%d chars)", result.source_name, len(result.markdown))
        chunks = self._split(result.markdown, result.source_name)
        logger.info("Chunking complete: '%s' → %d chunks", result.source_name, len(chunks))
        return chunks


def chunk_document(result: ExtractionResult) -> list[Chunk]:
    """Thin wrapper around DocumentChunker.chunk for backward compatibility."""
    return DocumentChunker().chunk(result)
