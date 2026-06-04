"""RAG pipeline configuration."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class RAGSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    RAG_CONCURRENCY: int = 1
    RAG_MAX_FILE_SIZE_MB: int = 50
    RAG_STORE_BATCH_SIZE: int = 32
    RAG_DISPLAY_NAME_MAX_CHARS: int = 30
    RAG_SCANNED_PDF_MIN_CHARS_PER_PAGE: int = 100
    RAG_PDF_EXTRACTION_BATCH_SIZE: int = 10
    RAG_DEFAULT_CHUNKS: int = 12
    RAG_AGENT_MAX_RECURSION: int = 25
    RAG_CHUNKING_TOKEN_LIMIT: int = 512
    RAG_CHUNKING_SECONDARY_OVERLAP: int = 50
    RAG_CHUNKING_TIKTOKEN_ENCODING: str = "cl100k_base"

    # RAG_MCP_URL belongs to the rag_mcp server, not the RAG pipeline itself.
    # It will be moved into rag_mcp's own config in a future refactor (see #398).


@lru_cache
def get_rag_settings() -> RAGSettings:
    return RAGSettings()
