"""Rows returned by analytics reads."""

from pydantic import BaseModel


class LoginsPoint(BaseModel):
    """Logins for one bucket and sign-in method. ``bucket`` is the UTC start, ``YYYY-MM-DD``."""

    bucket: str
    method: str
    login_count: int
