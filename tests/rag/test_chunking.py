from app.rag.chunking import _build_metadata, _count_tokens, _secondary_split, _split, chunk_document
from app.rag.extraction import ExtractionResult
from app.rag.types import Chunk, ChunkMetadata, DocType

STRUCTURED_MD = """\
# Introduction to Machine Learning

Machine learning is a subset of artificial intelligence.

## Supervised Learning

In supervised learning, models are trained on labelled data.

### Linear Regression

Linear regression predicts a continuous output variable.

## Unsupervised Learning

Unsupervised learning finds patterns in unlabelled data.
"""

FLAT_MD = "This document has no headings at all.\nJust plain paragraphs."

EMPTY_MD = ""

H1_ONLY_MD = """\
# Chapter One

Some content under chapter one.

# Chapter Two

Some content under chapter two.
"""


def _make_result(markdown: str, source_name: str = "test.md") -> ExtractionResult:
    return ExtractionResult(
        markdown=markdown,
        doc_type=DocType.TXT,
        source_name=source_name,
    )


class TestChunkMetadata:
    def test_fields_stored(self) -> None:
        m = ChunkMetadata(
            source_name="doc.pdf",
            chapter="Introduction",
            section="Background",
            subsection="History",
        )
        assert m.source_name == "doc.pdf"
        assert m.chapter == "Introduction"
        assert m.section == "Background"
        assert m.subsection == "History"

    def test_optional_fields_default_to_none(self) -> None:
        m = ChunkMetadata(source_name="doc.pdf")
        assert m.chapter is None
        assert m.section is None
        assert m.subsection is None

    def test_to_dict_contains_all_keys(self) -> None:
        m = ChunkMetadata(source_name="doc.pdf", chapter="Ch1")
        d = m.to_dict()
        assert set(d.keys()) == {"source_name", "chapter", "section", "subsection"}

    def test_to_dict_values_match_fields(self) -> None:
        m = ChunkMetadata(source_name="doc.pdf", chapter="Ch1", section="Sec1")
        d = m.to_dict()
        assert d["source_name"] == "doc.pdf"
        assert d["chapter"] == "Ch1"
        assert d["section"] == "Sec1"
        assert d["subsection"] is None


class TestChunk:
    def test_fields_stored(self) -> None:
        m = ChunkMetadata(source_name="f.md")
        c = Chunk(content="Some text", metadata=m)
        assert c.content == "Some text"
        assert c.metadata is m


class TestBuildMetadata:
    def test_all_fields_mapped(self) -> None:
        raw = {"chapter": "Ch1", "section": "Sec1", "subsection": "Sub1"}
        m = _build_metadata(raw, "doc.pdf")
        assert m.chapter == "Ch1"
        assert m.section == "Sec1"
        assert m.subsection == "Sub1"
        assert m.source_name == "doc.pdf"

    def test_missing_fields_default_to_none(self) -> None:
        m = _build_metadata({}, "doc.pdf")
        assert m.chapter is None
        assert m.section is None
        assert m.subsection is None

    def test_partial_fields(self) -> None:
        m = _build_metadata({"chapter": "Ch1"}, "doc.pdf")
        assert m.chapter == "Ch1"
        assert m.section is None


class TestSplit:
    def test_returns_list_of_chunks(self) -> None:
        chunks = _split(STRUCTURED_MD, "test.md")
        assert isinstance(chunks, list)
        assert all(isinstance(c, Chunk) for c in chunks)

    def test_chunks_not_empty(self) -> None:
        chunks = _split(STRUCTURED_MD, "test.md")
        assert len(chunks) > 0

    def test_no_chunk_has_empty_content(self) -> None:
        chunks = _split(STRUCTURED_MD, "test.md")
        assert all(c.content.strip() for c in chunks)

    def test_flat_document_returns_single_chunk(self) -> None:
        chunks = _split(FLAT_MD, "flat.md")
        assert len(chunks) == 1
        assert "no headings" in chunks[0].content

    def test_flat_document_metadata_has_no_chapter(self) -> None:
        chunks = _split(FLAT_MD, "flat.md")
        assert chunks[0].metadata.chapter is None

    def test_source_name_propagated_to_all_chunks(self) -> None:
        chunks = _split(STRUCTURED_MD, "lecture.md")
        assert all(c.metadata.source_name == "lecture.md" for c in chunks)

    def test_empty_markdown_returns_single_chunk(self) -> None:
        chunks = _split(EMPTY_MD, "empty.md")
        assert isinstance(chunks, list)


class TestChunkDocument:
    def test_returns_list_of_chunks(self) -> None:
        result = _make_result(STRUCTURED_MD)
        chunks = chunk_document(result)
        assert isinstance(chunks, list)
        assert len(chunks) > 0

    def test_chapter_metadata_extracted(self) -> None:
        result = _make_result(STRUCTURED_MD)
        chunks = chunk_document(result)
        chapters = [c.metadata.chapter for c in chunks if c.metadata.chapter]
        assert any("Introduction to Machine Learning" in ch for ch in chapters)

    def test_section_metadata_extracted(self) -> None:
        result = _make_result(STRUCTURED_MD)
        chunks = chunk_document(result)
        sections = [c.metadata.section for c in chunks if c.metadata.section]
        assert any("Supervised Learning" in s for s in sections)

    def test_subsection_metadata_extracted(self) -> None:
        result = _make_result(STRUCTURED_MD)
        chunks = chunk_document(result)
        subsections = [c.metadata.subsection for c in chunks if c.metadata.subsection]
        assert any("Linear Regression" in s for s in subsections)

    def test_source_name_preserved(self) -> None:
        result = _make_result(STRUCTURED_MD, source_name="ml_textbook.pdf")
        chunks = chunk_document(result)
        assert all(c.metadata.source_name == "ml_textbook.pdf" for c in chunks)

    def test_h1_only_document_splits_by_chapter(self) -> None:
        result = _make_result(H1_ONLY_MD)
        chunks = chunk_document(result)
        chapters = [c.metadata.chapter for c in chunks if c.metadata.chapter]
        assert any("Chapter One" in ch for ch in chapters)
        assert any("Chapter Two" in ch for ch in chapters)

    def test_flat_document_does_not_raise(self) -> None:
        result = _make_result(FLAT_MD)
        chunks = chunk_document(result)
        assert len(chunks) == 1

    def test_chunk_content_is_not_empty(self) -> None:
        result = _make_result(STRUCTURED_MD)
        chunks = chunk_document(result)
        assert all(c.content.strip() for c in chunks)

    def test_heading_text_preserved_in_content(self) -> None:
        result = _make_result(STRUCTURED_MD)
        chunks = chunk_document(result)
        all_content = "\n".join(c.content for c in chunks)
        assert "Supervised Learning" in all_content


# ---------------------------------------------------------------------------
# Layer 3 – secondary splitting
# ---------------------------------------------------------------------------

# ~600 unique tokens: "word0 word1 word2 ... word599 "
_LARGE_TEXT = " ".join(f"word{i}" for i in range(600))


def _big_chunk() -> Chunk:
    """Return a Chunk whose content exceeds _TOKEN_LIMIT tokens."""
    from app.rag.types import ChunkMetadata

    meta = ChunkMetadata(source_name="big.md", chapter="Ch1", section="Sec1")
    return Chunk(content=_LARGE_TEXT, metadata=meta)


def _small_chunk() -> Chunk:
    from app.rag.types import ChunkMetadata

    meta = ChunkMetadata(source_name="small.md")
    return Chunk(content="This is a short sentence.", metadata=meta)


class TestCountTokens:
    def test_returns_int(self) -> None:
        assert isinstance(_count_tokens("hello"), int)

    def test_empty_string_is_zero(self) -> None:
        assert _count_tokens("") == 0

    def test_scales_with_length(self) -> None:
        short = _count_tokens("hello")
        long = _count_tokens("hello " * 100)
        assert long > short


class TestSecondaryChunking:
    def test_oversized_chunk_is_split_into_multiple(self) -> None:
        sub = _secondary_split(_big_chunk())
        assert len(sub) > 1

    def test_sub_chunks_inherit_chapter(self) -> None:
        sub = _secondary_split(_big_chunk())
        assert all(c.metadata.chapter == "Ch1" for c in sub)

    def test_sub_chunks_inherit_section(self) -> None:
        sub = _secondary_split(_big_chunk())
        assert all(c.metadata.section == "Sec1" for c in sub)

    def test_sub_chunks_inherit_source_name(self) -> None:
        sub = _secondary_split(_big_chunk())
        assert all(c.metadata.source_name == "big.md" for c in sub)

    def test_no_empty_sub_chunks(self) -> None:
        sub = _secondary_split(_big_chunk())
        assert all(c.content.strip() for c in sub)

    def test_small_chunk_returns_single_item(self) -> None:
        sub = _secondary_split(_small_chunk())
        assert len(sub) == 1
        assert sub[0].content == "This is a short sentence."

    def test_split_applies_secondary_for_large_document(self) -> None:
        """_split must trigger secondary splitting when a section exceeds 512 tokens."""
        # Embed _LARGE_TEXT under a heading so the primary splitter produces one big chunk
        md = f"# Big Section\n\n{_LARGE_TEXT}\n"
        chunks = _split(md, "big.md")
        assert len(chunks) > 1

    def test_split_does_not_split_small_sections(self) -> None:
        chunks = _split(STRUCTURED_MD, "test.md")
        # All sections in STRUCTURED_MD are well under 512 tokens
        assert all(_count_tokens(c.content) <= 512 for c in chunks)
