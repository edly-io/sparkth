from enum import StrEnum


class DocType(StrEnum):
    PDF = "pdf"
    DOCX = "docx"
    HTML = "html"
    TXT = "txt"


class RagStatus(StrEnum):
    QUEUED = "queued"
    PROCESSING = "processing"
    READY = "ready"
    FAILED = "failed"
