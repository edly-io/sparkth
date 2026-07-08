"""Utilities for formatting RetrievedChunk objects into human-readable context blocks."""

from sparkth.rag.types import RetrievedChunk


def format_document_chunks_as_llm_context(retrieved_chunks: list[RetrievedChunk]) -> str:
    """Group retrieved chunks by document and render them as one LLM context string.

    Retrieval can return chunks from several documents interleaved in relevance
    order. They are grouped by the document each chunk came from (keyed by the
    document name the chunk carries, in first-seen order); each document's chunks
    are rendered as a labelled context block, and the blocks are joined with a
    blank line into a single string. An empty input yields an empty string.
    """
    blocks = [
        _format_document_block(document_name, document_chunks)
        for document_name, document_chunks in _group_by_document(retrieved_chunks).items()
    ]
    return "\n\n".join(blocks)


def _group_by_document(retrieved_chunks: list[RetrievedChunk]) -> dict[str, list[RetrievedChunk]]:
    """Bucket retrieved chunks by document name, preserving first-seen order."""
    grouped: dict[str, list[RetrievedChunk]] = {}
    for chunk in retrieved_chunks:
        grouped.setdefault(chunk.source_name, []).append(chunk)
    return grouped


def _format_document_block(document_name: str, retrieved_chunks: list[RetrievedChunk]) -> str:
    """Render one document's retrieved chunks as a labelled context block."""
    lines = [
        f"[DOCUMENT CONTEXT: {document_name}]",
        "The following excerpts were retrieved from the document to inform your response:",
        "",
    ]
    for i, chunk in enumerate(retrieved_chunks, 1):
        parts = [p for p in [chunk.chapter, chunk.section, chunk.subsection] if p]
        label = " / ".join(parts) if parts else "General"
        lines.append(f"--- Excerpt {i} (Section: {label}) ---")
        lines.append(chunk.content.strip())
        lines.append("")
    return "\n".join(lines)
