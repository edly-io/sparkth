"""DOCX extractor — converts headings, lists, and tables to Markdown."""

import io
from typing import Any

from docx import Document as DocxDocument
from docx.oxml.ns import qn

from app.lib.log import get_logger
from app.rag.constants import EXTRACTION_DOCX_HEADING_MAP, EXTRACTION_DOCX_ORDERED_LIST_FORMATS
from app.rag.extraction.base import BaseExtractor
from app.rag.extraction.utils import render_markdown_table
from app.rag.types import DocType, ExtractionResult

logger = get_logger(__name__)


class DocxExtractor(BaseExtractor):
    """Extracts text from DOCX files, converting headings, lists, and tables to Markdown."""

    def extract(self, data: bytes, source_name: str) -> ExtractionResult:
        from docx.table import Table
        from docx.text.paragraph import Paragraph

        doc = DocxDocument(io.BytesIO(data))
        lines: list[str] = []
        warnings: list[str] = []
        ordered_counters: dict[tuple[str, str], int] = {}

        body = doc.element.body

        for child in body:
            tag = child.tag.split("}")[-1] if "}" in child.tag else child.tag

            if tag == "p":  # paragraph
                para = Paragraph(child, doc)
                md = self._paragraph_to_md(para, ordered_counters)
                if md:
                    lines.append(md)
                    lines.append("")

            elif tag == "tbl":  # table
                tbl = Table(child, doc)
                md = self._table_to_md(tbl)
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

    def _list_prefix(self, para: Any, num_pr: Any, ordered_counters: dict[tuple[str, str], int]) -> str:
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

            if num_fmt not in EXTRACTION_DOCX_ORDERED_LIST_FORMATS:
                return "-"

            key = (num_id, ilvl)
            ordered_counters[key] = ordered_counters.get(key, 0) + 1
            return f"{ordered_counters[key]}."

        except AttributeError as e:
            logger.warning("Unexpected object shape while reading list prefix: %s", e)
            return "-"

    def _resolve_num_pr(self, para: Any) -> Any | None:
        """Return the effective w:numPr for a paragraph, checking the paragraph
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

    def _paragraph_to_md(self, para: Any, ordered_counters: dict[tuple[str, str], int]) -> str:
        """Convert a single python-docx Paragraph to a Markdown line."""
        style = para.style.name.lower() if para.style and para.style.name else ""
        text = para.text.strip()

        if not text:
            return ""

        prefix = EXTRACTION_DOCX_HEADING_MAP.get(style)
        if prefix:
            return f"{prefix} {text}"

        num_pr = self._resolve_num_pr(para)
        if num_pr is not None:
            prefix = self._list_prefix(para, num_pr, ordered_counters)
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

    def _table_to_md(self, table: Any) -> str:
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

        return render_markdown_table(rows)
