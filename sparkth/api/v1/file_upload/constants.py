"""Limits on the files the upload endpoint reads."""

MAX_FILE_SIZE_MB = 3
MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024
ALLOWED_TYPES = {
    "text/plain",
    "application/pdf",
}
