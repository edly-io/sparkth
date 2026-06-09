"""Public API for the Document registry.

All plugins and external modules manage document identity and status from here.
Nothing outside ``app/core/documents/`` should import from
``app.core.documents.*`` directly.
"""

from app.core.documents.enums import DocumentStatus  # noqa: F401
from app.core.documents.models import Document  # noqa: F401
from app.core.documents.service import (  # noqa: F401
    create_document,
    get_document,
    soft_delete_document,
    update_document_status,
)
