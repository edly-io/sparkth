"""
Converts PDF / DOCX / Google Doc HTML export into structured Markdown,
preserving heading hierarchy, lists, and tables for downstream chunking.

"""

import io
import random
from pathlib import Path
from typing import Any, Callable, Optional

import fitz  # type: ignore[import-untyped]  # PyMuPDF
import pymupdf4llm  # type: ignore[import-untyped]
from bs4 import BeautifulSoup, Tag
from bs4.element import NavigableString
from docx import Document as DocxDocument
from docx.oxml.ns import qn

from app.core.config import get_settings, parse_rag_allowed_extensions
from app.core.logger import get_logger
from app.rag.exceptions import ScannedPDFError
from app.rag.types import DocType

logger = get_logger(__name__)


_HEADING_MAP = {
    "heading 1": "#",
    "heading 2": "##",
    "heading 3": "###",
    "heading 4": "####",
    "heading 5": "#####",
    "heading 6": "######",
}


_HTML_HEADING_MAP = {
    "h1": "#",
    "h2": "##",
    "h3": "###",
    "h4": "####",
    "h5": "#####",
    "h6": "######",
}


_HTML_CONTAINERS = {"div", "section", "article", "main", "header", "footer", "aside"}


_HTML_TEXT_BLOCKS: frozenset[str] = frozenset(
    {
        "p",
        "pre",
        "blockquote",
        "address",
        "figcaption",
        "caption",
        "dt",
        "dd",
    }
)


_HTML_VOID_ELEMENTS: frozenset[str] = frozenset(
    {
        "area",
        "base",
        "br",
        "col",
        "embed",
        "hr",
        "img",
        "input",
        "link",
        "meta",
        "param",
        "source",
        "track",
        "wbr",
    }
)


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


def _is_scanned_pdf(doc: Any, min_chars_per_page: int, sample_ratio: float = 0.1) -> bool:
    """Detect scanned/image-only PDFs by sampling text density on a random subset of pages.

    A born-digital PDF averages thousands of chars per page. A scanned PDF
    averages near zero because the page content lives in embedded images.
    Sampling ~10% of pages at random spreads coverage so a few atypical
    pages (covers, blank inserts, watermarks) cannot dominate the decision.
    """
    page_count = len(doc)
    if page_count == 0:
        return False

    sample_size = max(1, round(page_count * sample_ratio))
    sample_size = min(sample_size, page_count)
    sampled = random.sample(range(page_count), sample_size)

    total_chars = 0
    for page_idx in sampled:
        text = doc[page_idx].get_text("text").strip()
        total_chars += len(text)

    avg_chars = total_chars / len(sampled)
    logger.debug(
        "Scanned-PDF check: sampled %d/%d pages, avg %.1f chars/page (threshold %d)",
        len(sampled),
        page_count,
        avg_chars,
        min_chars_per_page,
    )
    return avg_chars < min_chars_per_page


def _extract_pdf(data: bytes, source_name: str, *, batch_size: Optional[int] = None) -> ExtractionResult:
    settings = get_settings()
    effective_batch_size = batch_size if batch_size is not None else settings.RAG_PDF_EXTRACTION_BATCH_SIZE
    with fitz.open(stream=data, filetype="pdf") as doc:
        if _is_scanned_pdf(doc, min_chars_per_page=settings.RAG_SCANNED_PDF_MIN_CHARS_PER_PAGE):
            raise ScannedPDFError(source_name)
        page_count = len(doc)
        parts: list[str] = []
        try:
            for start in range(0, page_count, effective_batch_size):
                pages = list(range(start, min(start + effective_batch_size, page_count)))
                batch_md = pymupdf4llm.to_markdown(doc=doc, pages=pages, page_chunks=False)
                parts.append(batch_md)
                # Release MuPDF's C-level font/image store between batches so peak
                # RSS stays bounded regardless of total page count.
                fitz.TOOLS.store_shrink(100)
        finally:
            fitz.TOOLS.store_shrink(100)
    md = "\n\n".join(parts).replace("\n-----\n", "\n\n")
    return ExtractionResult(
        markdown=md,
        doc_type=DocType.PDF,
        source_name=source_name,
        page_count=page_count,
    )


_ORDERED_NUM_FMTS = {"decimal", "upperRoman", "lowerRoman", "upperLetter", "lowerLetter"}


def _docx_list_prefix(para: Any, num_pr: Any, ordered_counters: dict[tuple[str, str], int]) -> str:
    try:
        num_id_el = num_pr.find(qn("w:numId"))
        ilvl_el = num_pr.find(qn("w:ilvl"))
        if num_id_el is None:
            return "-"

        num_id = num_id_el.get(qn("w:val"), "")
        ilvl = ilvl_el.get(qn("w:val"), "0") if ilvl_el is not None else "0"

        numbering = getattr(getattr(para, "part", None), "numbering_part", None)
        if numbering is None:
            return "-"

        all_nums = numbering._element.findall(qn("w:num"))
        num_el = None
        for el in all_nums:
            if el.get(qn("w:numId")) == num_id:
                num_el = el
                break

        if num_el is None:
            return "-"

        abs_id_el = num_el.find(qn("w:abstractNumId"))
        if abs_id_el is None:
            return "-"
        abs_id = abs_id_el.get(qn("w:val"), "")

        all_abs = numbering._element.findall(qn("w:abstractNum"))
        abs_num_el = None
        for el in all_abs:
            if el.get(qn("w:abstractNumId")) == abs_id:
                abs_num_el = el
                break

        if abs_num_el is None:
            return "-"

        lvl_el = None
        for el in abs_num_el.findall(qn("w:lvl")):
            if el.get(qn("w:ilvl")) == ilvl:
                lvl_el = el
                break

        if lvl_el is None:
            return "-"

        fmt_el = lvl_el.find(qn("w:numFmt"))
        num_fmt = fmt_el.get(qn("w:val"), "bullet") if fmt_el is not None else "bullet"

        if num_fmt not in _ORDERED_NUM_FMTS:
            return "-"

        key = (num_id, ilvl)
        ordered_counters[key] = ordered_counters.get(key, 0) + 1
        return f"{ordered_counters[key]}."

    except AttributeError as e:
        logger.warning("Unexpected object shape while reading list prefix: %s", e)
        return "-"


def _resolve_num_pr(para: Any) -> Any | None:
    """
    Return the effective w:numPr for a paragraph, checking the paragraph
    element first and then walking up through the named style chain.
    python-docx "List Number" / "List Bullet" styles store numPr on the
    style definition, not on the paragraph element itself.
    """
    num_pr = para._element.find(qn("w:numPr"))
    if num_pr is not None:
        return num_pr

    style = para.style
    while style is not None:
        if style.element is not None:
            pPr = style.element.find(qn("w:pPr"))
            if pPr is not None:
                num_pr = pPr.find(qn("w:numPr"))
                if num_pr is not None:
                    return num_pr
        style = style.base_style  # may be None at the top

    return None


def _docx_paragraph_to_md(para: Any, ordered_counters: dict[tuple[str, str], int]) -> str:
    """Convert a single python-docx Paragraph to a Markdown line."""
    style = para.style.name.lower() if para.style and para.style.name else ""
    text = para.text.strip()

    if not text:
        return ""

    # Headings
    prefix = _HEADING_MAP.get(style)
    if prefix:
        return f"{prefix} {text}"

    num_pr = _resolve_num_pr(para)
    if num_pr is not None:
        prefix = _docx_list_prefix(para, num_pr, ordered_counters)
        return f"{prefix} {text}"

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
    """Render a python-docx Table as a GitHub-flavoured Markdown table.

    python-docx repeats the same cell object for every column a horizontally
    merged cell spans, and for every row a vertically merged cell spans.
    Deduplication is done by cell identity (id()) rather than text content so
    that two distinct cells with identical text are never collapsed.
    """
    if not table.rows:
        return ""

    seen_ids: set[int] = set()
    rows: list[list[str]] = []

    for row in table.rows:
        cells: list[str] = []
        for cell in row.cells:
            cid = id(cell)
            if cid not in seen_ids:
                seen_ids.add(cid)
                cells.append(cell.text.strip())
        rows.append(cells)

    rows = [r for r in rows if r]

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
    ordered_counters: dict[tuple[str, str], int] = {}

    body = doc.element.body

    for child in body:
        tag = child.tag.split("}")[-1] if "}" in child.tag else child.tag

        if tag == "p":  # paragraph
            from docx.text.paragraph import Paragraph

            para = Paragraph(child, doc)
            md = _docx_paragraph_to_md(para, ordered_counters)
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


def _li_direct_text(li: Tag) -> str:
    """Return only the direct text of a <li>, skipping nested <ul>/<ol> children."""
    parts: list[str] = []
    for child in li.children:
        if isinstance(child, NavigableString):
            t = str(child).strip()
            if t:
                parts.append(t)
        elif isinstance(child, Tag) and child.name not in ("ul", "ol"):
            t = child.get_text(" ", strip=True)
            if t:
                parts.append(t)
    return " ".join(parts)


def _walk_list(
    el: Tag,
    lines: list[str],
    warnings: list[str],
    source_name: str,
    *,
    ordered: bool,
    depth: int = 0,
) -> None:
    """Render a <ul> or <ol> element, recursing into nested sub-lists."""
    indent = "  " * depth
    items = el.find_all("li", recursive=False)
    for i, li in enumerate(items, start=1):
        text = _li_direct_text(li)
        if text:
            prefix = f"{i}." if ordered else "-"
            lines.append(f"{indent}{prefix} {text}")
        for nested in li.find_all(["ul", "ol"], recursive=False):
            _walk_list(
                nested,
                lines,
                warnings,
                source_name,
                ordered=(nested.name == "ol"),
                depth=depth + 1,
            )
    if depth == 0:
        lines.append("")


def _walk_html(node: Tag, lines: list[str], warnings: list[str], source_name: str) -> None:
    """
    Recursively walk an HTML tree converting block structure to Markdown.
    """
    for el in node.children:
        if not isinstance(el, Tag) or not el.name:
            continue

        name = el.name.lower()

        if name in _HTML_HEADING_MAP:
            text = el.get_text(" ", strip=True)
            if text:
                lines.append(f"{_HTML_HEADING_MAP[name]} {text}")
                lines.append("")

        elif name in _HTML_TEXT_BLOCKS:
            text = el.get_text(" ", strip=True)
            if text:
                lines.append(text)
                lines.append("")

        elif name in ("ul", "ol"):
            _walk_list(el, lines, warnings, source_name, ordered=(name == "ol"))

        elif name == "table":
            md = _bs_table_to_md(el)
            if md:
                lines.append(md)
                lines.append("")
                warnings.append(f"Table detected in '{source_name}' — verify Markdown rendering.")

        elif name in _HTML_CONTAINERS:
            _walk_html(el, lines, warnings, source_name)

        # Bare inline elements (span, a, em, strong, …) that appear as direct
        # children of a container are uncommon in well-formed HTML but do occur
        # in Google Docs exports.  Treat a contiguous run of them as an
        # implicit paragraph rather than dropping them.
        elif name not in _HTML_VOID_ELEMENTS:
            text = el.get_text(" ", strip=True)
            if text:
                lines.append(text)
                lines.append("")


def _extract_html(data: bytes, source_name: str) -> ExtractionResult:
    soup = BeautifulSoup(data, "html.parser")
    lines: list[str] = []
    warnings: list[str] = []

    root = soup.body or soup
    _walk_html(root, lines, warnings, source_name)

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


_DISPATCH: dict[str, Callable[[bytes, str], ExtractionResult]] = {
    "pdf": _extract_pdf,
    "docx": _extract_docx,
    "html": _extract_html,
    "htm": _extract_html,
    "txt": _extract_txt,
    "md": _extract_txt,
}

SUPPORTED_EXTENSIONS: frozenset[str] = frozenset(_DISPATCH)


def extract_to_markdown(data: bytes, filename: str) -> ExtractionResult:
    """
    Main entry point. Accepts raw file bytes and the original filename,
    returns an ExtractionResult with structured Markdown ready for chunking.

    Usage:
        result = extract_to_markdown(file_bytes, "lecture_notes.pdf")
        print(result.markdown)
    """
    suffix = Path(filename).suffix.lower().lstrip(".")

    # This is defense-in-depth for non-Drive callers of extract_to_markdown
    allowed = parse_rag_allowed_extensions(get_settings().RAG_ALLOWED_EXTENSIONS)
    if allowed and suffix not in allowed:
        accepted = ", ".join(f".{e}" for e in allowed)
        raise ValueError(f"Unsupported file extension. Allowed: {accepted}.")

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
