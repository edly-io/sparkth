import os

DEFAULT_RAG_CHUNKS = 12

# agent.py
AGENT_CONTEXT_KEYS = frozenset({"user_id", "file_id"})
AGENT_MAX_RECURSION = int(os.getenv("RAG_AGENT_MAX_RECURSION", "25"))

# chunking.py
CHUNKING_MARKDOWN_HEADERS = [
    ("#", "chapter"),
    ("##", "section"),
    ("###", "subsection"),
]
CHUNKING_TOKEN_LIMIT = int(os.getenv("RAG_CHUNKING_TOKEN_LIMIT", "512"))
CHUNKING_SECONDARY_OVERLAP = int(os.getenv("RAG_CHUNKING_SECONDARY_OVERLAP", "50"))
CHUNKING_TIKTOKEN_ENCODING = os.getenv("RAG_CHUNKING_TIKTOKEN_ENCODING", "cl100k_base")


# extraction.py
EXTRACTION_DOCX_HEADING_MAP: dict[str, str] = {
    "heading 1": "#",
    "heading 2": "##",
    "heading 3": "###",
    "heading 4": "####",
    "heading 5": "#####",
    "heading 6": "######",
}

EXTRACTION_HTML_HEADING_MAP: dict[str, str] = {
    "h1": "#",
    "h2": "##",
    "h3": "###",
    "h4": "####",
    "h5": "#####",
    "h6": "######",
}

EXTRACTION_HTML_CONTAINER_TAGS: frozenset[str] = frozenset(
    {"div", "section", "article", "main", "header", "footer", "aside"}
)

EXTRACTION_HTML_TEXT_BLOCK_TAGS: frozenset[str] = frozenset(
    {"p", "pre", "blockquote", "address", "figcaption", "caption", "dt", "dd"}
)

EXTRACTION_HTML_VOID_TAGS: frozenset[str] = frozenset(
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

EXTRACTION_DOCX_ORDERED_LIST_FORMATS: frozenset[str] = frozenset(
    {"decimal", "upperRoman", "lowerRoman", "upperLetter", "lowerLetter"}
)


GOOGLE_NATIVE_MIMES = frozenset(
    {
        "application/vnd.google-apps.document",
        "application/vnd.google-apps.spreadsheet",
        "application/vnd.google-apps.presentation",
        "application/vnd.google-apps.drawing",
    }
)
