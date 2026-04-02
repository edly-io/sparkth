from dataclasses import dataclass
from enum import StrEnum


class DocType(StrEnum):
    PDF = "pdf"
    DOCX = "docx"
    HTML = "html"
    TXT = "txt"


class RagStatus(StrEnum):
    PROCESSING = "processing"
    READY = "ready"
    FAILED = "failed"


@dataclass
class ChunkMetadata:
    source_name: str
    chapter: str | None = None
    section: str | None = None
    subsection: str | None = None

    def to_dict(self) -> dict[str, str | None]:
        return {
            "source_name": self.source_name,
            "chapter": self.chapter,
            "section": self.section,
            "subsection": self.subsection,
        }


@dataclass
class Chunk:
    content: str
    metadata: ChunkMetadata
