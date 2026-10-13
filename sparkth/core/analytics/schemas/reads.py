"""Rows and query models for analytics reads."""

from datetime import date
from typing import Self

from pydantic import BaseModel, Field, model_validator

from sparkth.core.analytics.enums import Bucket

# Inclusive day count; a leap year fits.
MAX_RANGE_DAYS = 366


class LoginsPoint(BaseModel):
    """Logins for one bucket and sign-in method. ``bucket`` is the UTC start, ``YYYY-MM-DD``."""

    bucket: str
    method: str
    login_count: int


class RangeQuery(BaseModel):
    """Query for a bucketed read: an inclusive UTC day range and a bucket width."""

    from_: date = Field(alias="from")
    to: date
    bucket: Bucket = Bucket.day

    @model_validator(mode="after")
    def _check_range(self) -> Self:
        if self.from_ > self.to:
            raise ValueError("'from' must not be after 'to'")
        if (self.to - self.from_).days + 1 > MAX_RANGE_DAYS:
            raise ValueError(f"range must not exceed {MAX_RANGE_DAYS} days")
        return self
