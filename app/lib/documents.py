"""Public API for the Document registry.

All plugins and external modules manage document identity and status from here.
"""

from app.core.documents.enums import DocumentStatus
from app.core.documents.models import Document
from app.core.documents.service import (
    create_document,
    get_document,
    list_ready_documents,
    soft_delete_document,
    update_document_status,
)

__all__ = [
    "DocumentStatus",
    "Document",
    "create_document",
    "get_document",
    "list_ready_documents",
    "soft_delete_document",
    "update_document_status",
]
