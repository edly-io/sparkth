"""
Converts PDF / DOCX / Google Doc HTML export into structured Markdown,
preserving heading hierarchy, lists, and tables for downstream chunking.

"""

import io
from pathlib import Path
from typing import Any, Optional

import pymupdf4llm  # type: ignore[import-untyped]
from bs4 import BeautifulSoup, Tag
from docx import Document as DocxDocument
from docx.oxml.ns import qn

from app.core.logger import get_logger
from app.rag.types import _HEADING_MAP, DocType

logger = get_logger(__name__)


class ExtractionResult:
    """Holds the extracted Markdown and extraction metadata."""

    def __init__(
        self,
        markdown: str,
        doc_type: DocType,
        source_name: str,
        page_count: Optional[int] = None,
        warnings: Optional[list[str]] = None,
    ):
        self.markdown = markdown
        self.doc_type = doc_type
        self.source_name = source_name
        self.page_count = page_count
        self.warnings = warnings or []

    def __repr__(self) -> str:  # pragma: no cover
        return f"<ExtractionResult source={self.source_name!r} type={self.doc_type} chars={len(self.markdown)}>"


def _extract_pdf(data: bytes, source_name: str) -> ExtractionResult:
    md = pymupdf4llm.to_markdown(
        doc=io.BytesIO(data),
        page_chunks=False,
    )
    page_count = md.count("\n-----\n") + 1
    return ExtractionResult(
        markdown=md,
        doc_type=DocType.PDF,
        source_name=source_name,
        page_count=page_count,
    )


def _docx_paragraph_to_md(para: Any) -> str:
    """Convert a single python-docx Paragraph to a Markdown line."""
    style = para.style.name.lower() if para.style and para.style.name else ""
    text = para.text.strip()

    if not text:
        return ""

    # Headings
    prefix = _HEADING_MAP.get(style)
    if prefix:
        return f"{prefix} {text}"

    # List items — python-docx exposes numPr when a paragraph is in a list
    is_list = para._element.find(qn("w:numPr")) is not None
    if is_list:
        return f"- {text}"

    # Inline bold/italic — rebuild from runs
    parts: list[str] = []
    for run in para.runs:
        t = run.text
        if not t:
            continue
        if run.bold and run.italic:
            t = f"***{t}***"
        elif run.bold:
            t = f"**{t}**"
        elif run.italic:
            t = f"*{t}*"
        parts.append(t)

    return "".join(parts) if parts else text


def _docx_table_to_md(table: Any) -> str:
    """Render a python-docx Table as a GitHub-flavoured Markdown table."""
    rows = [[cell.text.strip() for cell in row.cells] for row in table.rows]
    if not rows:
        return ""

    col_count = max(len(r) for r in rows)

    def pad(row: list[str]) -> list[str]:
        return row + [""] * (col_count - len(row))

    header = pad(rows[0])
    separator = ["---"] * col_count
    body = [pad(r) for r in rows[1:]]

    lines = [
        "| " + " | ".join(header) + " |",
        "| " + " | ".join(separator) + " |",
        *("| " + " | ".join(r) + " |" for r in body),
    ]
    return "\n".join(lines)


def _extract_docx(data: bytes, source_name: str) -> ExtractionResult:
    doc = DocxDocument(io.BytesIO(data))
    lines: list[str] = []
    warnings: list[str] = []

    body = doc.element.body

    for child in body:
        tag = child.tag.split("}")[-1] if "}" in child.tag else child.tag

        if tag == "p":  # paragraph
            from docx.text.paragraph import Paragraph

            para = Paragraph(child, doc)
            md = _docx_paragraph_to_md(para)
            if md:
                lines.append(md)
                lines.append("")

        elif tag == "tbl":  # table
            from docx.table import Table

            tbl = Table(child, doc)
            md = _docx_table_to_md(tbl)
            if md:
                lines.append(md)
                lines.append("")
                warnings.append(f"Table detected in '{source_name}' — verify Markdown rendering.")

    return ExtractionResult(
        markdown="\n".join(lines),
        doc_type=DocType.DOCX,
        source_name=source_name,
        warnings=warnings,
    )


_HTML_HEADING_MAP = {
    "h1": "#",
    "h2": "##",
    "h3": "###",
    "h4": "####",
    "h5": "#####",
    "h6": "######",
}


def _bs_table_to_md(table: Any) -> str:
    """Convert a <table> BeautifulSoup tag to Markdown."""
    rows = table.find_all("tr")
    if not rows:
        return ""

    def cells(row: Any) -> list[str]:
        return [c.get_text(" ", strip=True) for c in row.find_all(["td", "th"])]

    parsed = [cells(r) for r in rows]
    col_count = max(len(r) for r in parsed)

    def pad(r: list[str]) -> list[str]:
        return r + [""] * (col_count - len(r))

    header = pad(parsed[0])
    separator = ["---"] * col_count
    body = [pad(r) for r in parsed[1:]]

    lines = [
        "| " + " | ".join(header) + " |",
        "| " + " | ".join(separator) + " |",
        *("| " + " | ".join(r) + " |" for r in body),
    ]
    return "\n".join(lines)


def _extract_html(data: bytes, source_name: str) -> ExtractionResult:
    soup = BeautifulSoup(data, "html.parser")
    lines: list[str] = []
    warnings: list[str] = []

    # Use <body> if present, otherwise the whole document
    root = soup.body or soup

    for el in root.children:
        if not isinstance(el, Tag) or not el.name:
            continue

        name = el.name.lower()

        if name in _HTML_HEADING_MAP:
            text = el.get_text(" ", strip=True)
            if text:
                lines.append(f"{_HTML_HEADING_MAP[name]} {text}")
                lines.append("")

        elif name in ("ul", "ol"):
            for li in el.find_all("li", recursive=False):
                text = li.get_text(" ", strip=True)
                if text:
                    lines.append(f"- {text}")
            lines.append("")

        elif name == "table":
            md = _bs_table_to_md(el)
            if md:
                lines.append(md)
                lines.append("")
                warnings.append(f"Table detected in '{source_name}' — verify Markdown rendering.")

        elif name == "p":
            text = el.get_text(" ", strip=True)
            if text:
                lines.append(text)
                lines.append("")

    return ExtractionResult(
        markdown="\n".join(lines),
        doc_type=DocType.HTML,
        source_name=source_name,
        warnings=warnings,
    )


def _extract_txt(data: bytes, source_name: str) -> ExtractionResult:
    return ExtractionResult(
        markdown=data.decode("utf-8", errors="replace"),
        doc_type=DocType.TXT,
        source_name=source_name,
    )


_DISPATCH = {
    "pdf": _extract_pdf,
    "docx": _extract_docx,
    "doc": _extract_docx,
    "html": _extract_html,
    "htm": _extract_html,
    "txt": _extract_txt,
    "md": _extract_txt,
}


def extract_to_markdown(data: bytes, filename: str) -> ExtractionResult:
    """
    Main entry point. Accepts raw file bytes and the original filename,
    returns an ExtractionResult with structured Markdown ready for chunking.

    Usage:
        result = extract_to_markdown(file_bytes, "lecture_notes.pdf")
        print(result.markdown)
    """
    suffix = Path(filename).suffix.lower().lstrip(".")
    handler = _DISPATCH.get(suffix)

    if handler is None:
        raise ValueError(f"Unsupported file type '.{suffix}' for '{filename}'. Supported: {list(_DISPATCH.keys())}")

    logger.info("Extracting '%s' as %s", filename, suffix.upper())
    result = handler(data, filename)

    for w in result.warnings:
        logger.warning(w)

    logger.info(
        "Extraction complete: %s → %d chars of Markdown",
        filename,
        len(result.markdown),
    )
    return result
