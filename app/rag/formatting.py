"""Utilities for formatting RetrievedChunk objects into human-readable context blocks."""

from app.rag.types import RetrievedChunk


def format_source_block(source_name: str, chunks: list[RetrievedChunk]) -> str:
    """Render a single source's chunks as a labelled context block.

    Produces a header line, a sub-header, then one numbered excerpt per chunk
    with its section hierarchy label. Returns the block as a single string.
    """
    lines = [
        f"[DOCUMENT CONTEXT: {source_name}]",
        "The following excerpts were retrieved from the document to inform your response:",
        "",
    ]
    for i, chunk in enumerate(chunks, 1):
        parts = [p for p in [chunk.chapter, chunk.section, chunk.subsection] if p]
        label = " / ".join(parts) if parts else "General"
        lines.append(f"--- Excerpt {i} (Section: {label}) ---")
        lines.append(chunk.content.strip())
        lines.append("")
    return "\n".join(lines)


def group_by_source(chunks: list[RetrievedChunk]) -> dict[str, list[RetrievedChunk]]:
    """Group chunks by source name, preserving insertion order."""
    grouped: dict[str, list[RetrievedChunk]] = {}
    for chunk in chunks:
        grouped.setdefault(chunk.source_name, []).append(chunk)
    return grouped
