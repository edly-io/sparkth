"""RAG-specific exceptions for chat integration."""


class RAGError(Exception):
    """Base exception for RAG retrieval errors."""


class DriveFileNotFoundError(RAGError):
    """Raised when a file does not exist or is not accessible to the user."""


class RAGNotReadyError(RAGError):
    """Raised when the file exists but rag_status is not READY."""

    def __init__(self, file_db_id: int, rag_status: str) -> None:
        self.file_db_id = file_db_id
        self.rag_status = rag_status
        super().__init__(f"File id={file_db_id} is not ready for retrieval (status: {rag_status})")


class RAGRetrievalError(RAGError):
    """Raised when embedding or similarity search fails."""


class ScannedPDFError(RAGError):
    """Raised when a PDF appears to be scanned/image-only and cannot be text-extracted.

    The user-facing message is intentionally generic — `source_name` is kept
    as a structured attribute for logging but never interpolated into the
    exception text, so internal paths (if any caller ever passes one) cannot
    leak through to the UI.
    """

    USER_MESSAGE = (
        "This PDF appears to be scanned (image-only pages with no extractable text). "
        "OCR-based ingestion is not yet supported — please upload a text-based PDF."
    )

    def __init__(self, source_name: str) -> None:
        self.source_name = source_name
        super().__init__(self.USER_MESSAGE)
