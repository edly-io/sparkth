"""Enums for Explore queries."""

from enum import StrEnum


class Measure(StrEnum):
    """What an explore query counts per bucket."""

    COUNT = "count"
    DISTINCT_ACTORS = "distinct_actors"
