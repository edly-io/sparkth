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
