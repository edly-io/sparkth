"""Enums for analytics reads."""

from enum import StrEnum


class Bucket(StrEnum):
    """Bucket width for analytics reads: day, week or month."""

    day = "day"
    week = "week"
    month = "month"
