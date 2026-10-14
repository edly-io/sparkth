"""Enumerations of the pxc plugin."""

from enum import StrEnum


class PreviewPermission(StrEnum):
    """The permissions an author may preview their own activity under."""

    PLAY = "play"
    EDIT = "edit"


class PxcFailureKind(StrEnum):
    """Why a recorded action did not go through."""

    # ui.js sent an action the manifest does not declare, or a value its schema refuses.
    REJECTED = "rejected"
    # sandbox.js threw, or wrote a value its field or event refuses.
    FAILED = "failed"
