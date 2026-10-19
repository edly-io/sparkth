"""The Google Drive plugin's analytics event schemas.

Payloads carry identifiers, sizes, counts and system-authored names only: never a filename.
"""

from enum import StrEnum

from pydantic import NonNegativeInt

from sparkth.lib.analytics import AnalyticsEventSchema


class DocumentOutcome(StrEnum):
    """How a Drive document's processing ended. A closed set, never the exception text."""

    INGESTED = "ingested"
    DUPLICATE = "duplicate"
    TOO_LARGE = "too_large"
    UNSUPPORTED_TYPE = "unsupported_type"
    SCANNED_PDF = "scanned_pdf"
    DRIVE_ERROR = "drive_error"
    FAILED = "failed"


READY_OUTCOMES = frozenset({DocumentOutcome.INGESTED, DocumentOutcome.DUPLICATE})
"""Outcomes that leave the document usable in chat; every other one ends failed."""


class GoogleDriveDocumentProcessed(AnalyticsEventSchema):
    """A Drive document reached a final status (ready or failed) in a sync run.

    Outcomes in ``READY_OUTCOMES`` end ready; every other outcome ends failed.
    ``size_bytes`` is the downloaded length, else Drive's reported size, else ``None``.
    ``chunk_count`` is new plus reused chunks, 0 unless ``ingested``.
    ``seconds_to_final`` runs from the start of the sync run, so a retry isn't timed from the
    document's creation; it includes time queued behind the run's other files.
    """

    event_type = "google-drive.document_processed"
    version = 1

    document_id: int
    outcome: DocumentOutcome
    mime_type: str | None
    size_bytes: NonNegativeInt | None
    chunk_count: NonNegativeInt
    seconds_to_final: NonNegativeInt
