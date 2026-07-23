"""SQLModel for registered documents (plugin-agnostic source identity)."""

from typing import Optional

from sqlalchemy import String
from sqlmodel import Field

from sparkth.core.documents.enums import DocumentStatus
from sparkth.core.models.base import SoftDeleteModel, TimestampedModel


class Document(TimestampedModel, SoftDeleteModel, table=True):
    """Plugin-agnostic registry of documents submitted for RAG ingestion.

    Plugins create one row per source document they want to ingest. RAG uses document_id
    as its primary reference — it never imports from any plugin model.
    """

    __tablename__ = "documents"

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)

    name: str = Field(max_length=500)
    mime_type: Optional[str] = Field(default=None, max_length=255)

    # Stored as a plain string: the documents.status column is varchar, and a
    # native-enum mapping would emit ::documentstatus casts that fail on
    # PostgreSQL because no such type exists.
    status: DocumentStatus = Field(default=DocumentStatus.QUEUED, sa_type=String)
    error: Optional[str] = Field(default=None)
