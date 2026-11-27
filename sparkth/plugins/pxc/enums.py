"""Enumerations of the pxc plugin."""

from enum import StrEnum
from typing import Literal

# The level an activity is launched at: as a learner (play) or as its author (edit).
PreviewLevel = Literal["play", "edit"]


class PreviewPermission(StrEnum):
    """The permissions an activity can be previewed under."""

    PLAY = "play"
    EDIT = "edit"


class PxcFailureKind(StrEnum):
    """Why a recorded action did not go through."""

    # ui.js sent an action the manifest does not declare, or a value its schema refuses.
    REJECTED = "rejected"
    # sandbox.js threw, or wrote a value its field or event refuses.
    FAILED = "failed"
