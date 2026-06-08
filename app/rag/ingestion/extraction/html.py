"""HTML extractor — converts Google Docs exports and generic HTML to Markdown."""

from typing import Any

from bs4 import BeautifulSoup, Tag
from bs4.element import NavigableString

from app.lib.log import get_logger
from app.rag.constants import (
    EXTRACTION_HTML_CONTAINER_TAGS,
    EXTRACTION_HTML_HEADING_MAP,
    EXTRACTION_HTML_TEXT_BLOCK_TAGS,
    EXTRACTION_HTML_VOID_TAGS,
)
from app.rag.enums import DocType
from app.rag.ingestion.extraction.base import BaseExtractor
from app.rag.ingestion.extraction.utils import render_markdown_table
from app.rag.types import ExtractionResult

logger = get_logger(__name__)


class HTMLExtractor(BaseExtractor):
    """Extracts text from HTML files (including Google Docs exports), converting to Markdown."""

    def extract(self, data: bytes, source_name: str) -> ExtractionResult:
        soup = BeautifulSoup(data, "html.parser")
        lines: list[str] = []
        warnings: list[str] = []

        root = soup.body or soup
        self._walk(root, lines, warnings, source_name)

        return ExtractionResult(
            markdown="\n".join(lines),
            doc_type=DocType.HTML,
            source_name=source_name,
            warnings=warnings,
        )

    def _table_to_md(self, table: Any) -> str:
        """Convert a <table> BeautifulSoup tag to Markdown."""
        rows = table.find_all("tr")
        if not rows:
            return ""

        def cells(row: Any) -> list[str]:
            return [c.get_text(" ", strip=True) for c in row.find_all(["td", "th"])]

        parsed = [cells(r) for r in rows]
        return render_markdown_table(parsed)

    def _li_direct_text(self, li: Tag) -> str:
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
        self,
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
            text = self._li_direct_text(li)
            if text:
                prefix = f"{i}." if ordered else "-"
                lines.append(f"{indent}{prefix} {text}")
            for nested in li.find_all(["ul", "ol"], recursive=False):
                self._walk_list(
                    nested,
                    lines,
                    warnings,
                    source_name,
                    ordered=(nested.name == "ol"),
                    depth=depth + 1,
                )
        if depth == 0:
            lines.append("")

    def _walk(self, node: Tag, lines: list[str], warnings: list[str], source_name: str) -> None:
        """Recursively walk an HTML tree converting block structure to Markdown."""
        for el in node.children:
            if not isinstance(el, Tag) or not el.name:
                continue

            name = el.name.lower()

            if name in EXTRACTION_HTML_HEADING_MAP:
                text = el.get_text(" ", strip=True)
                if text:
                    lines.append(f"{EXTRACTION_HTML_HEADING_MAP[name]} {text}")
                    lines.append("")

            elif name in EXTRACTION_HTML_TEXT_BLOCK_TAGS:
                text = el.get_text(" ", strip=True)
                if text:
                    lines.append(text)
                    lines.append("")

            elif name in ("ul", "ol"):
                self._walk_list(el, lines, warnings, source_name, ordered=(name == "ol"))

            elif name == "table":
                md = self._table_to_md(el)
                if md:
                    lines.append(md)
                    lines.append("")
                    warnings.append(f"Table detected in '{source_name}' — verify Markdown rendering.")

            elif name in EXTRACTION_HTML_CONTAINER_TAGS:
                self._walk(el, lines, warnings, source_name)

            # Bare inline elements (span, a, em, strong, …) that appear as direct
            # children of a container are uncommon in well-formed HTML but do occur
            # in Google Docs exports.  Treat a contiguous run of them as an
            # implicit paragraph rather than dropping them.
            elif name not in EXTRACTION_HTML_VOID_TAGS:
                text = el.get_text(" ", strip=True)
                if text:
                    lines.append(text)
                    lines.append("")
