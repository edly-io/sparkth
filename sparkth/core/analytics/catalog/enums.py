"""Enums for the event catalog."""

from enum import StrEnum


class FilterFieldType(StrEnum):
    """How an event payload field is filtered: it picks the filter control and how a value is parsed.

    ``string`` is free text, ``enum`` one of the field's listed ``values``, ``boolean`` ``true`` or
    ``false``, and ``integer`` a whole number.
    """

    string = "string"
    enum = "enum"
    boolean = "boolean"
    integer = "integer"
