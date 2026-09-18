"""Moodle MCP tools, including authentication, course, section, page and quiz management."""

from typing import Any

from sparkth.lib.exceptions import AuthenticationError, LMSRequestError
from sparkth.plugins.moodle.client import MoodleClient
from sparkth.plugins.moodle.schemas import Auth


def _lms_error(e: LMSRequestError | AuthenticationError) -> dict[str, Any]:
    return {"error": {"status_code": e.status_code, "message": e.message}}


async def moodle_authenticate(auth: Auth) -> dict[str, Any]:
    """Verify the provided Moodle site URL and web service token."""
    try:
        async with MoodleClient(auth.api_url, auth.api_token) as client:
            info = await client.call("core_webservice_get_site_info")
        return {"sitename": info.get("sitename"), "username": info.get("username")}
    except (LMSRequestError, AuthenticationError) as e:
        return _lms_error(e)
    except ValueError as e:
        return {"error": {"message": str(e)}}
