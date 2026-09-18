"""Moodle MCP tools, including authentication, course, section, page and quiz management."""

import logging
from typing import Any

from sparkth.lib.exceptions import AuthenticationError, LMSRequestError
from sparkth.plugins.moodle.client import MoodleClient
from sparkth.plugins.moodle.constants import MOODLE_MALFORMED_RESPONSE_STATUS_CODE
from sparkth.plugins.moodle.schemas import (
    Auth,
    CoursePayload,
    PagePayload,
    QuizPayload,
    SectionPayload,
)

logger = logging.getLogger(__name__)


def _lms_error(e: LMSRequestError | AuthenticationError, operation: str) -> dict[str, Any]:
    logger.warning("moodle %s failed with status %s: %s", operation, e.status_code, e.message)
    return {"error": {"status_code": e.status_code, "message": e.message}}


def _malformed_response_error(e: ValueError | KeyError | IndexError, operation: str) -> dict[str, Any]:
    logger.warning(
        "moodle %s returned a malformed response (status_code=%s): %s",
        operation,
        MOODLE_MALFORMED_RESPONSE_STATUS_CODE,
        e,
    )
    return {"error": {"status_code": MOODLE_MALFORMED_RESPONSE_STATUS_CODE, "message": str(e)}}


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
        return _malformed_response_error(e, wsfunction)


async def moodle_list_courses(auth: Auth) -> dict[str, Any]:
    """Retrieve the courses the authenticated user is enrolled in.

    Deliberately not ``core_course_get_courses``, which returns every course on the
    site: an author publishing a course wants their own, and a large site would
    return thousands.
    """
    wsfunction = "core_webservice_get_site_info"
    try:
        async with MoodleClient(auth.api_url, auth.api_token) as client:
            info = await client.call_dict(wsfunction)
            userid = info["userid"]
            wsfunction = "core_enrol_get_users_courses"
            courses = await client.call_list(wsfunction, {"userid": userid})
        return {"courses": courses}
    except (LMSRequestError, AuthenticationError) as e:
        return _lms_error(e, wsfunction)
    except (ValueError, KeyError) as e:
        return _malformed_response_error(e, wsfunction)


async def moodle_create_course(payload: CoursePayload) -> dict[str, Any]:
    """Create a new course on Moodle.

    Sections are not pre-allocated here: ``numsections`` is deliberately unset so
    that ``moodle_create_section`` is the only thing that creates sections.
    """
    wsfunction = "core_course_create_courses"
    course = {
        "fullname": payload.fullname,
        "shortname": payload.shortname,
        "categoryid": payload.categoryid,
        "summary": payload.summary,
        "summaryformat": 1,
        "format": "topics",
        "lang": payload.lang or None,
    }
    try:
        async with MoodleClient(payload.auth.api_url, payload.auth.api_token) as client:
            created = await client.call_list(wsfunction, {"courses": [course]})
        return {"course": created[0]}
    except (LMSRequestError, AuthenticationError) as e:
        return _lms_error(e, wsfunction)
    except (ValueError, IndexError, KeyError) as e:
        return _malformed_response_error(e, wsfunction)


async def moodle_create_section(payload: SectionPayload) -> dict[str, Any]:
    """Append a section to a Moodle course and set its name and summary.

    Requires the local_sparkth companion plugin installed on the target Moodle.
    """
    wsfunction = "local_sparkth_create_section"
    params = {
        "courseid": payload.courseid,
        "name": payload.name,
        "summary": payload.summary,
    }
    try:
        async with MoodleClient(payload.auth.api_url, payload.auth.api_token) as client:
            return await client.call_dict(wsfunction, params)
    except (LMSRequestError, AuthenticationError) as e:
        return _lms_error(e, wsfunction)
    except ValueError as e:
        return _malformed_response_error(e, wsfunction)


async def moodle_create_page(payload: PagePayload) -> dict[str, Any]:
    """Create a Page activity carrying lesson HTML in a Moodle course section.

    Requires the local_sparkth companion plugin installed on the target Moodle.
    """
    wsfunction = "local_sparkth_create_page"
    params = {
        "courseid": payload.courseid,
        "sectionnum": payload.sectionnum,
        "name": payload.name,
        "content": payload.content,
        "intro": payload.intro,
    }
    try:
        async with MoodleClient(payload.auth.api_url, payload.auth.api_token) as client:
            return await client.call_dict(wsfunction, params)
    except (LMSRequestError, AuthenticationError) as e:
        return _lms_error(e, wsfunction)
    except ValueError as e:
        return _malformed_response_error(e, wsfunction)


async def moodle_create_quiz(payload: QuizPayload) -> dict[str, Any]:
    """Create a Quiz activity with its questions in a Moodle course section.

    Supports multichoice and truefalse questions. Requires the local_sparkth
    plugin on the target Moodle.
    """
    wsfunction = "local_sparkth_create_quiz"
    params = {
        "courseid": payload.courseid,
        "sectionnum": payload.sectionnum,
        "name": payload.name,
        "intro": payload.intro,
        "questions": [question.model_dump(mode="json") for question in payload.questions],
    }
    try:
        async with MoodleClient(payload.auth.api_url, payload.auth.api_token) as client:
            return await client.call_dict(wsfunction, params)
    except (LMSRequestError, AuthenticationError) as e:
        return _lms_error(e, wsfunction)
    except ValueError as e:
        return _malformed_response_error(e, wsfunction)
