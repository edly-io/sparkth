"""Moodle MCP tools, including authentication, course, section, page and quiz management."""

import logging
from typing import Any

from sparkth.lib.exceptions import AuthenticationError, LMSRequestError
from sparkth.plugins.moodle.client import MoodleClient
from sparkth.plugins.moodle.constants import MOODLE_MALFORMED_RESPONSE_STATUS_CODE
from sparkth.plugins.moodle.schemas import Auth

logger = logging.getLogger(__name__)


def _lms_error(e: LMSRequestError | AuthenticationError, operation: str) -> dict[str, Any]:
    logger.warning("moodle %s failed with status %s: %s", operation, e.status_code, e.message)
    return {"error": {"status_code": e.status_code, "message": e.message}}


async def moodle_authenticate(auth: Auth) -> dict[str, Any]:
    """Verify the provided Moodle site URL and web service token."""
    wsfunction = "core_webservice_get_site_info"
    try:
        async with MoodleClient(auth.api_url, auth.api_token) as client:
            info = await client.call_dict(wsfunction)
        return {"sitename": info.get("sitename"), "username": info.get("username")}
    except (LMSRequestError, AuthenticationError) as e:
        return _lms_error(e, wsfunction)
    except ValueError as e:
        logger.warning(
            "moodle %s returned a malformed response (status_code=%s): %s",
            wsfunction,
            MOODLE_MALFORMED_RESPONSE_STATUS_CODE,
            e,
        )
        return {"error": {"status_code": MOODLE_MALFORMED_RESPONSE_STATUS_CODE, "message": str(e)}}
