"""Enumerations of the pxc plugin."""

from enum import StrEnum


class PreviewPermission(StrEnum):
    """The permissions an author may preview their own activity under."""

    PLAY = "play"
    EDIT = "edit"
