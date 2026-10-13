"""Enumerations of the pxc plugin."""

from enum import StrEnum


class PreviewPermission(StrEnum):
    """The permissions an author may preview their own activity under."""

    PLAY = "play"
    EDIT = "edit"


class PxcFailureKind(StrEnum):
    """Why a recorded action did not go through."""

    # The manifest refused the value ui.js sent.
    REJECTED = "rejected"
    # sandbox.js threw, or wrote a value its field or event refuses.
    FAILED = "failed"
