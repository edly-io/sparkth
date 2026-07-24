"""SQLModel for registered documents (plugin-agnostic source identity)."""

from typing import Optional

from sqlalchemy import Column, Enum
from sqlmodel import Field

from sparkth.core.documents.enums import DocumentStatus
from sparkth.core.models.base import SoftDeleteModel, TimestampedModel


def _document_status_values(enum_cls: type[DocumentStatus]) -> list[str]:
    """Enum labels for the documentstatus DB type: the lowercase member values,
    matching the strings stored in documents.status rows."""
    return [status.value for status in enum_cls]


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

    # Native documentstatus enum; labels are the member *values* so they match
    # both the stored rows and the API serialization of DocumentStatus.
    status: DocumentStatus = Field(
        default=DocumentStatus.QUEUED,
        sa_column=Column(
            Enum(DocumentStatus, name="documentstatus", values_callable=_document_status_values),
            nullable=False,
        ),
    )
    error: Optional[str] = Field(default=None)
