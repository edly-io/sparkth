"""
tests/rag/test_extraction.py

Unit tests for app/rag/extraction.py
Covers: PDF, DOCX, HTML, TXT extraction + public API routing + error handling.
"""

import io
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from bs4 import Tag

from app.rag.extraction import (
    ExtractionResult,
    _bs_table_to_md,
    _docx_table_to_md,
    _extract_docx,
    _extract_html,
    _extract_txt,
    extract_to_markdown,
)
from app.rag.types import DocType

SIMPLE_HTML = b"""
<html><body>
  <h1>Course Introduction</h1>
  <h2>What you will learn</h2>
  <p>This course covers machine learning fundamentals.</p>
  <ul>
    <li>Supervised learning</li>
    <li>Unsupervised learning</li>
  </ul>
  <table>
    <tr><th>Topic</th><th>Week</th></tr>
    <tr><td>Linear Regression</td><td>1</td></tr>
    <tr><td>Neural Networks</td><td>4</td></tr>
  </table>
</body></html>
"""

MINIMAL_HTML = b"<html><body><p>Hello world</p></body></html>"

TXT_CONTENT = b"# Lecture Notes\n\nSome content here.\n"


class TestExtractionResult:
    def test_fields_are_stored(self) -> None:
        r = ExtractionResult("# Hello", DocType.TXT, "file.txt", page_count=1, warnings=["w"])
        assert r.markdown == "# Hello"
        assert r.doc_type == DocType.TXT
        assert r.source_name == "file.txt"
        assert r.page_count == 1
        assert r.warnings == ["w"]

    def test_warnings_default_to_empty_list(self) -> None:
        r = ExtractionResult("md", DocType.TXT, "f.txt")
        assert r.warnings == []

    def test_page_count_defaults_to_none(self) -> None:
        r = ExtractionResult("md", DocType.TXT, "f.txt")
        assert r.page_count is None


class TestExtractPDF:
    def test_calls_pymupdf4llm_and_returns_result(self) -> None:
        fake_md = "# Chapter 1\n\nContent here.\n-----\n# Chapter 2\n"
        with patch("app.rag.extraction.pymupdf4llm.to_markdown", return_value=fake_md) as mock_to_md:
            result = extract_to_markdown(b"%PDF-fake", "notes.pdf")

        mock_to_md.assert_called_once()
        assert result.doc_type == DocType.PDF
        assert result.source_name == "notes.pdf"
        assert result.markdown == fake_md

    def test_page_count_inferred_from_separators(self) -> None:
        fake_md = "page1\n-----\npage2\n-----\npage3"
        with patch("app.rag.extraction.pymupdf4llm.to_markdown", return_value=fake_md):
            result = extract_to_markdown(b"%PDF-fake", "book.pdf")

        assert result.page_count == 3

    def test_single_page_no_separator(self) -> None:
        fake_md = "just one page, no separator"
        with patch("app.rag.extraction.pymupdf4llm.to_markdown", return_value=fake_md):
            result = extract_to_markdown(b"%PDF-fake", "one.pdf")

        assert result.page_count == 1


class TestExtractHTML:
    def test_h1_rendered_as_h1(self) -> None:
        result = _extract_html(SIMPLE_HTML, "doc.html")
        assert "# Course Introduction" in result.markdown

    def test_h2_rendered_as_h2(self) -> None:
        result = _extract_html(SIMPLE_HTML, "doc.html")
        assert "## What you will learn" in result.markdown

    def test_paragraph_included(self) -> None:
        result = _extract_html(SIMPLE_HTML, "doc.html")
        assert "This course covers machine learning fundamentals." in result.markdown

    def test_list_items_rendered_with_dash(self) -> None:
        result = _extract_html(SIMPLE_HTML, "doc.html")
        assert "- Supervised learning" in result.markdown
        assert "- Unsupervised learning" in result.markdown

    def test_ordered_list_items_rendered_with_numbers(self) -> None:
        html = b"<html><body><ol><li>First</li><li>Second</li></ol></body></html>"
        result = _extract_html(html, "doc.html")
        assert "1. First" in result.markdown
        assert "2. Second" in result.markdown

    def test_table_rendered_as_gfm(self) -> None:
        result = _extract_html(SIMPLE_HTML, "doc.html")
        assert "| Topic |" in result.markdown
        assert "| ---" in result.markdown
        assert "| Linear Regression |" in result.markdown

    def test_table_warning_emitted(self) -> None:
        result = _extract_html(SIMPLE_HTML, "doc.html")
        assert any("Table detected" in w for w in result.warnings)

    def test_no_warnings_for_table_free_html(self) -> None:
        result = _extract_html(MINIMAL_HTML, "simple.html")
        assert result.warnings == []

    def test_doc_type_is_html(self) -> None:
        result = _extract_html(MINIMAL_HTML, "simple.html")
        assert result.doc_type == DocType.HTML

    def test_empty_body_returns_empty_markdown(self) -> None:
        result = _extract_html(b"<html><body></body></html>", "empty.html")
        assert result.markdown.strip() == ""

    def test_content_inside_div_not_dropped(self) -> None:
        html = b"""
        <html><body>
          <div>
            <h2>Nested Heading</h2>
            <p>Nested paragraph.</p>
          </div>
        </body></html>
        """
        result = _extract_html(html, "nested.html")
        assert "## Nested Heading" in result.markdown
        assert "Nested paragraph." in result.markdown

    def test_deeply_nested_containers_traversed(self) -> None:
        html = b"""
        <html><body>
          <div><section><article>
            <h3>Deep Heading</h3>
            <p>Deep content.</p>
          </article></section></div>
        </body></html>
        """
        result = _extract_html(html, "deep.html")
        assert "### Deep Heading" in result.markdown
        assert "Deep content." in result.markdown

        html = b"<html><body>  \n  <p>Clean</p>\n  </body></html>"
        result = _extract_html(html, "ws.html")
        assert result.markdown.count("Clean") == 1


class TestExtractTXT:
    def test_content_passed_through_unchanged(self) -> None:
        result = _extract_txt(TXT_CONTENT, "notes.txt")
        assert result.markdown == TXT_CONTENT.decode("utf-8")

    def test_doc_type_is_txt(self) -> None:
        result = _extract_txt(TXT_CONTENT, "notes.txt")
        assert result.doc_type == DocType.TXT

    def test_invalid_utf8_replaced_not_raised(self) -> None:
        bad_bytes = b"Hello \xff\xfe world"
        result = _extract_txt(bad_bytes, "bad.txt")
        assert "Hello" in result.markdown
        assert "world" in result.markdown

    def test_md_extension_uses_txt_extractor(self) -> None:
        result = extract_to_markdown(TXT_CONTENT, "lecture.md")
        assert result.doc_type == DocType.TXT
        assert result.markdown == TXT_CONTENT.decode("utf-8")


class TestExtractDOCX:
    """
    python-docx cannot create a valid .docx from scratch in memory easily,
    so we build a minimal one using python-docx's API and round-trip it.
    """

    @pytest.fixture()
    def simple_docx_bytes(self) -> bytes:
        from docx import Document

        doc = Document()
        doc.add_heading("Introduction", level=1)
        doc.add_heading("Background", level=2)
        doc.add_paragraph("This is a paragraph.")
        buf = io.BytesIO()
        doc.save(buf)
        return buf.getvalue()

    @pytest.fixture()
    def table_docx_bytes(self) -> bytes:
        from docx import Document

        doc = Document()
        table = doc.add_table(rows=2, cols=2)
        table.cell(0, 0).text = "Header A"
        table.cell(0, 1).text = "Header B"
        table.cell(1, 0).text = "Value 1"
        table.cell(1, 1).text = "Value 2"
        buf = io.BytesIO()
        doc.save(buf)
        return buf.getvalue()

    def test_h1_rendered(self, simple_docx_bytes: Any) -> None:
        result = _extract_docx(simple_docx_bytes, "doc.docx")
        assert "# Introduction" in result.markdown

    def test_h2_rendered(self, simple_docx_bytes: Any) -> None:
        result = _extract_docx(simple_docx_bytes, "doc.docx")
        assert "## Background" in result.markdown

    def test_paragraph_included(self, simple_docx_bytes: Any) -> None:
        result = _extract_docx(simple_docx_bytes, "doc.docx")
        assert "This is a paragraph." in result.markdown

    def test_doc_type_is_docx(self, simple_docx_bytes: Any) -> None:
        result = _extract_docx(simple_docx_bytes, "doc.docx")
        assert result.doc_type == DocType.DOCX

    def test_table_rendered_as_gfm(self, table_docx_bytes: Any) -> None:
        result = _extract_docx(table_docx_bytes, "table.docx")
        assert "| Header A |" in result.markdown
        assert "| ---" in result.markdown
        assert "| Value 1 |" in result.markdown

    @pytest.fixture()
    def ordered_list_docx_bytes(self) -> bytes:
        from docx import Document

        doc = Document()

        for item in ("First", "Second", "Third"):
            doc.add_paragraph(item, style="List Number")
        buf = io.BytesIO()
        doc.save(buf)
        return buf.getvalue()

    def test_ordered_list_rendered_with_numbers(self, ordered_list_docx_bytes: bytes, table_docx_bytes: Any) -> None:
        result = _extract_docx(ordered_list_docx_bytes, "doc.docx")
        assert "1. First" in result.markdown
        assert "2. Second" in result.markdown
        assert "3. Third" in result.markdown
        result = _extract_docx(table_docx_bytes, "table.docx")
        assert any("Table detected" in w for w in result.warnings)


class TestDocxTableToMd:
    def _make_table(self, rows: list[list[str]]) -> MagicMock:
        """Build a minimal mock that _docx_table_to_md can consume."""
        mock_table = MagicMock()
        mock_rows = []
        for row_data in rows:
            mock_row = MagicMock()
            mock_cells = [MagicMock(text=cell) for cell in row_data]
            mock_row.cells = mock_cells
            mock_rows.append(mock_row)
        mock_table.rows = mock_rows
        return mock_table

    def test_header_and_separator(self) -> None:
        tbl = self._make_table([["Col A", "Col B"], ["r1c1", "r1c2"]])
        md = _docx_table_to_md(tbl)
        assert "| Col A | Col B |" in md
        assert "| --- | --- |" in md

    def test_body_rows_included(self) -> None:
        tbl = self._make_table([["H1", "H2"], ["v1", "v2"], ["v3", "v4"]])
        md = _docx_table_to_md(tbl)
        assert "| v1 | v2 |" in md
        assert "| v3 | v4 |" in md

    def test_empty_table_returns_empty_string(self) -> None:
        mock_table = MagicMock()
        mock_table.rows = []
        assert _docx_table_to_md(mock_table) == ""


class TestBsTableToMd:
    def _make_table(self, html: str) -> Tag:
        from bs4 import BeautifulSoup, Tag

        soup = BeautifulSoup(html, "html.parser")
        tag = soup.find("table")
        assert isinstance(tag, Tag)
        return tag

    def test_header_row(self) -> None:
        tbl = self._make_table("<table><tr><th>A</th><th>B</th></tr></table>")
        md = _bs_table_to_md(tbl)
        assert "| A | B |" in md

    def test_separator_row(self) -> None:
        tbl = self._make_table("<table><tr><th>A</th><th>B</th></tr></table>")
        md = _bs_table_to_md(tbl)
        assert "| --- | --- |" in md

    def test_body_row(self) -> None:
        html = "<table><tr><th>A</th></tr><tr><td>val</td></tr></table>"
        tbl = self._make_table(html)
        md = _bs_table_to_md(tbl)
        assert "| val |" in md

    def test_empty_table_returns_empty_string(self) -> None:
        from bs4 import BeautifulSoup, Tag

        soup = BeautifulSoup("<table></table>", "html.parser")
        tag = soup.find("table")
        assert isinstance(tag, Tag)
        assert _bs_table_to_md(tag) == ""


class TestExtractToMarkdown:
    @pytest.mark.parametrize(
        "filename,expected_type",
        [
            ("notes.txt", DocType.TXT),
            ("notes.md", DocType.TXT),
            ("page.html", DocType.HTML),
            ("page.htm", DocType.HTML),
        ],
    )
    def test_routing_by_extension(self, filename: Any, expected_type: Any) -> None:
        data = MINIMAL_HTML if "html" in filename or "htm" in filename else TXT_CONTENT
        result = extract_to_markdown(data, filename)
        assert result.doc_type == expected_type

    def test_unsupported_extension_raises_value_error(self) -> None:
        with pytest.raises(ValueError, match="Unsupported file type"):
            extract_to_markdown(b"data", "file.pptx")

    def test_source_name_preserved(self) -> None:
        result = extract_to_markdown(TXT_CONTENT, "my_lecture.txt")
        assert result.source_name == "my_lecture.txt"

    def test_pdf_routing_calls_pymupdf(self) -> None:
        with patch("app.rag.extraction.pymupdf4llm.to_markdown", return_value="# MD") as m:
            extract_to_markdown(b"%PDF", "deck.pdf")
        m.assert_called_once()

    def test_docx_routing(self) -> None:
        from docx import Document

        doc = Document()
        doc.add_paragraph("hello")
        buf = io.BytesIO()
        doc.save(buf)
        result = extract_to_markdown(buf.getvalue(), "file.docx")
        assert result.doc_type == DocType.DOCX
