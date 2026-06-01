"""Constants for Google Drive plugin."""

import os

DRIVE_MAX_UPLOAD_BYTES = int(os.getenv("DRIVE_MAX_UPLOAD_BYTES", str(30 * 1024 * 1024)))
