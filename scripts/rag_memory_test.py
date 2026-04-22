"""Standalone sizing-test script for the RAG pipeline.

Runs extraction → chunking → embedding for one or more local files (PDF, DOCX,
etc.) with memory profiling enabled, then prints a summary table.

Usage:
    python scripts/rag_memory_test.py file1.pdf file2.pdf
"""

import asyncio
import logging
import os
import re

import typer

# Force profiling on before any app imports resolve settings
os.environ["MEMORY_PROFILING_ENABLED"] = "true"

from app.rag.chunking import chunk_document  # noqa: E402
from app.rag.embeddings import HuggingFaceEmbeddingProvider  # noqa: E402
from app.rag.extraction import extract_to_markdown  # noqa: E402

app = typer.Typer(help="RAG pipeline memory sizing test")

_MEMPROF_RE = re.compile(r"MEMPROF\s+(.+)")
_KV_RE = re.compile(r"(\w+)=(-|\S+)")


def _parse_memprof_line(line: str) -> dict[str, str] | None:
    m = _MEMPROF_RE.search(line)
    if not m:
        return None
    return dict(_KV_RE.findall(m.group(1)))


async def _process_file(filepath: str, provider: HuggingFaceEmbeddingProvider) -> None:
    """Run the CPU-bound RAG stages for a single file."""
    filename = os.path.basename(filepath)
    with open(filepath, "rb") as f:
        file_bytes = f.read()

    # Import here so profiling is active during the context manager
    from app.rag.memory_profiler import profile_memory

    # extraction
    async with profile_memory("extraction", file=filename, size_bytes=len(file_bytes)):
        extraction_result = await asyncio.to_thread(extract_to_markdown, file_bytes, filename)

    # chunking
    async with profile_memory("chunking", file=filename, markdown_chars=len(extraction_result.markdown)):
        chunks = await asyncio.to_thread(chunk_document, extraction_result)

    if not chunks:
        typer.echo(f"  {filename}: no chunks produced, skipping embedding.")
        return

    # embedding
    texts = [c.content for c in chunks]

    async with profile_memory("embedding", source=filename, n_chunks=len(chunks)):
        await provider.embed_documents(texts)

    typer.echo(f"  {filename}: {len(chunks)} chunks, {len(file_bytes)} bytes")


def _print_summary(records: list[dict[str, str]]) -> None:
    """Print a summary table grouped by file then stage."""
    if not records:
        typer.echo("No MEMPROF records captured.")
        return

    # Group by file
    by_file: dict[str, list[dict[str, str]]] = {}
    for r in records:
        key = r.get("file") or r.get("source") or "-"
        by_file.setdefault(key, []).append(r)

    typer.echo("\n" + "=" * 90)
    typer.echo(f"{'File':<25} {'Stage':<22} {'py_peak_delta_kb':>16} {'rss_delta_mb':>14} {'duration_ms':>12}")
    typer.echo("-" * 90)
    for file_name, rows in by_file.items():
        for row in rows:
            typer.echo(
                f"{file_name:<25} {row.get('stage', '-'):<22} "
                f"{row.get('py_peak_delta_kb', '-'):>16} {row.get('rss_delta_mb', '-'):>14} "
                f"{row.get('duration_ms', '-'):>12}"
            )
    typer.echo("=" * 90)


class _LogCapture(logging.Handler):
    """Captures MEMPROF log lines for the summary."""

    def __init__(self) -> None:
        super().__init__()
        self.records: list[dict[str, str]] = []

    def emit(self, record: logging.LogRecord) -> None:
        parsed = _parse_memprof_line(record.getMessage())
        if parsed:
            self.records.append(parsed)


@app.command()
def main(files: list[str] = typer.Argument(..., exists=True, help="PDF/DOCX files to process")) -> None:
    """Run RAG pipeline stages with memory profiling and print a summary."""
    # Attach a capture handler to the sparkth logger tree
    capture = _LogCapture()
    sparkth_logger = logging.getLogger("sparkth")
    sparkth_logger.addHandler(capture)
    sparkth_logger.setLevel(logging.INFO)

    typer.echo(f"Processing {len(files)} file(s) with memory profiling enabled...\n")

    provider = HuggingFaceEmbeddingProvider()

    for filepath in files:
        asyncio.run(_process_file(filepath, provider))

    _print_summary(capture.records)


if __name__ == "__main__":
    app()
