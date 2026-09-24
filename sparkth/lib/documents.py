"""Public API for the Document registry.

All plugins and external modules manage document identity and status from here.
"""

from sparkth.core.documents.enums import DocumentStatus
from sparkth.core.documents.hooks import DOCUMENT_DELETED, DocumentDeletedHandler
from sparkth.core.documents.models import Document
from sparkth.core.documents.service import (
    create_document,
    get_document,
    list_ready_documents,
    soft_delete_document,
    update_document_status,
)

__all__ = [
    "DOCUMENT_DELETED",
    "DocumentDeletedHandler",
    "DocumentStatus",
    "Document",
    "create_document",
    "get_document",
    "list_ready_documents",
    "soft_delete_document",
    "update_document_status",
]
