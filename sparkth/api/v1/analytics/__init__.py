"""Analytics API package.

Exports the router and registers the analytics domain-exception → HTTP status mappings.
"""

from fastapi import status

from sparkth.api.v1.analytics.routes import router
from sparkth.lib.analytics import AnalyticsViewAlreadyExists, AnalyticsViewNotFound, ExploreQueryError
from sparkth.lib.exceptions.handlers import register_exception_handler

register_exception_handler(ExploreQueryError, status.HTTP_422_UNPROCESSABLE_CONTENT)
register_exception_handler(AnalyticsViewNotFound, status.HTTP_404_NOT_FOUND)
register_exception_handler(AnalyticsViewAlreadyExists, status.HTTP_409_CONFLICT)

__all__ = ["router"]
