"""Utilities for formatting RetrievedChunk objects into human-readable context blocks."""

from app.rag.types import RetrievedChunk


def format_document_chunks_as_llm_context(document_name: str, retrieved_chunks: list[RetrievedChunk]) -> str:
    """Render one document's retrieved chunks as a labelled LLM context block.

    ``document_name`` is the name of the document the chunks were retrieved from
    — e.g. an uploaded PDF or a Google Drive file. Every chunk in
    ``retrieved_chunks`` is expected to belong to that document.

    Produces a header line naming the document, a sub-header, then one numbered
    excerpt per chunk with its section hierarchy label. Returns the block as a
    single string.
    """
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


def group_retrieved_chunks_by_document(retrieved_chunks: list[RetrievedChunk]) -> dict[str, list[RetrievedChunk]]:
    """Bucket retrieved chunks by the document they came from.

    Retrieval can return chunks from several documents interleaved in relevance
    order. This collates them into one bucket per document, keyed by the
    document name each chunk carries, so callers can render a separate context
    block per document.

    Document names are keyed in the order they are first encountered, and chunks
    within each bucket keep their original relative order — neither is sorted.

    Returns a mapping of document name to the chunks retrieved from that
    document. An empty input yields an empty mapping.
    """
    grouped: dict[str, list[RetrievedChunk]] = {}
    for chunk in retrieved_chunks:
        grouped.setdefault(chunk.source_name, []).append(chunk)
    return grouped
