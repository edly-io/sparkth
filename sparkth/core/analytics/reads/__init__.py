"""Analytics reads: bucketed rollups, core's queries and Overview figures, and the read models.

The read path never touches the application database, only analytics tables and rollups. Exposed
to the API layer and plugins via ``sparkth.lib.analytics``. Importing it seeds the core Overview
figures.
"""

from sparkth.core.analytics.reads.buckets import PG_BUCKET, PG_RAW_BUCKET, SQLITE_BUCKET, in_days
from sparkth.core.analytics.reads.enums import Bucket
from sparkth.core.analytics.reads.queries import get_logins, summarize
from sparkth.core.analytics.reads.rollups import read_rollup
from sparkth.core.analytics.reads.schemas import MAX_RANGE_DAYS, LoginsPoint, RangeQuery, SummaryCount

__all__ = [
    "MAX_RANGE_DAYS",
    "PG_BUCKET",
    "PG_RAW_BUCKET",
    "SQLITE_BUCKET",
    "Bucket",
    "LoginsPoint",
    "RangeQuery",
    "SummaryCount",
    "get_logins",
    "in_days",
    "read_rollup",
    "summarize",
]
