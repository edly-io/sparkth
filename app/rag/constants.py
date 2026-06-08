AGENT_CONTEXT_KEYS = frozenset({"user_id", "file_id"})

CHUNKING_MARKDOWN_HEADERS = [
    ("#", "chapter"),
    ("##", "section"),
    ("###", "subsection"),
]

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
