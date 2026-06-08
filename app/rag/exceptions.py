"""RAG-specific exceptions."""


class RAGError(Exception):
    """Base exception for RAG retrieval errors."""


class DocumentNotFoundError(RAGError):
    """Raised when a document does not exist or is not accessible to the user."""


# Backward-compatibility alias — remove once all callsites use DocumentNotFoundError.
DriveFileNotFoundError = DocumentNotFoundError


class RAGNotReadyError(RAGError):
    """Raised when the document exists but status is not READY."""

    def __init__(self, document_id: int, status: str) -> None:
        self.document_id = document_id
        self.status = status
        super().__init__(f"Document id={document_id} is not ready for retrieval (status: {status})")


class RAGRetrievalError(RAGError):
    """Raised when agent retrieval or section-chunk fetch fails."""


class ScannedPDFError(RAGError):
    """Raised when a PDF appears to be scanned/image-only."""

    USER_MESSAGE = (
        "This PDF appears to be scanned (image-only pages with no extractable text). "
        "OCR-based ingestion is not yet supported — please upload a text-based PDF."
    )

    def __init__(self, source_name: str) -> None:
        self.source_name = source_name
        super().__init__(self.USER_MESSAGE)


class RAGIngestionError(RAGError):
    """Base exception for failures during document ingestion."""


class UnsupportedFileTypeError(RAGIngestionError):
    """Raised when a file's type cannot be handled by the RAG extractors."""
