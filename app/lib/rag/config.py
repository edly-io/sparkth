"""RAG pipeline configuration."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class RAGSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    RAG_CONCURRENCY: int = 1
    RAG_MAX_FILE_SIZE_MB: int = 50
    RAG_STORE_BATCH_SIZE: int = 32
    RAG_DISPLAY_NAME_MAX_CHARS: int = 30
    RAG_ALLOWED_EXTENSIONS: str = ""
    RAG_SCANNED_PDF_MIN_CHARS_PER_PAGE: int = 100
    RAG_PDF_EXTRACTION_BATCH_SIZE: int = 10

    # RAG_MCP_URL belongs to the rag_mcp server, not the RAG pipeline itself.
    # It will be moved into rag_mcp's own config in a future refactor (see #398).


@lru_cache
def get_rag_settings() -> RAGSettings:
    return RAGSettings()


def parse_rag_allowed_extensions(raw: str) -> list[str]:
    """Parse a comma-separated extensions string into a normalised list.

    Strips whitespace, lowercases, and removes leading dots and duplicates.
    Returns an empty list when *raw* is blank, which means all supported types
    are permitted.
    """
    if not raw.strip():
        return []
    parts = [ext.strip().lower().lstrip(".") for ext in raw.split(",")]
    return list(dict.fromkeys(p for p in parts if p))
