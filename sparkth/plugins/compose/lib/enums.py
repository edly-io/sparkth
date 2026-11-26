"""Enums the Compose plugin shares with other plugins."""

from enum import StrEnum


class OptionsFence(StrEnum):
    """The tag of the fenced block that offers the author choices."""

    MULTIPLE = "options"
    SINGLE = "options single"
