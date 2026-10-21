"""Value objects shared across the analytics subsystem."""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import date

from sqlalchemy.ext.asyncio import AsyncSession

Count = Callable[[AsyncSession, date, date], Awaitable[int]]


@dataclass(frozen=True)
class SummaryFigure:
    """One headline count on the analytics Overview.

    Attributes:
        key: Stable id; a plugin's keys start with ``<plugin>.``.
        label: ``gettext_noop`` source, translated per request.
        count: Counts the figure for an inclusive UTC day range.
        view: The analytics view that breaks it down.
        order: Sorts ascending, then by key.
        plugin: Set on registration. The count runs for every caller.
    """

    key: str
    label: str
    count: Count
    view: str | None = None
    order: int = 100
    plugin: str | None = None
