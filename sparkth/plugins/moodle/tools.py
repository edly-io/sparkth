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
    """Verify the provided Moodle site URL and web service token.

    Returns the site name plus the token user's username and ``userid``.
    """
    wsfunction = "core_webservice_get_site_info"
    try:
        async with MoodleClient(auth.api_url, auth.api_token) as client:
            info = await client.call_dict(wsfunction)
        return {
            "sitename": info.get("sitename"),
            "username": info.get("username"),
            "userid": info.get("userid"),
        }
    except (LMSRequestError, AuthenticationError) as e:
        return _lms_error(e, wsfunction)
    except ValueError as e:
        return _malformed_response_error(e, wsfunction)


async def moodle_list_courses(auth: Auth) -> dict[str, Any]:
    """List the courses the token's user is enrolled in, to pick an existing one to add to.

    ``moodle_create_course`` enrols its caller as the new course's creator, so a course
    it just created normally appears here too. To add content to a course you just
    created, use the ``id`` returned by ``moodle_create_course`` directly rather than
    looking it up with this tool.
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


async def _enrol_creator(client: MoodleClient, wsfunction: str, courseid: int) -> bool:
    """Enrol the token's user into a just-created course; a failure here never fails it.

    The course already exists by the time this runs, so an enrolment failure is
    logged and reported through the return value rather than raised.
    """
    try:
        result = await client.call_dict(wsfunction, {"courseid": courseid})
        return bool(result.get("enrolled", False))
    except (LMSRequestError, AuthenticationError) as e:
        _lms_error(e, wsfunction)
        return False
    except ValueError as e:
        _malformed_response_error(e, wsfunction)
        return False


async def moodle_create_course(payload: CoursePayload) -> dict[str, Any]:
    """Create a new course on Moodle and enrol the token's user as its creator.

    Sections are not pre-allocated here: ``numsections`` is deliberately unset so
    that ``moodle_create_section`` is the only thing that creates sections.

    Creating a course over web services does not enrol the creator, unlike Moodle's
    own UI, so the local_sparkth companion plugin is called immediately after to
    enrol the token's user. See ``_enrol_creator`` for why that call cannot fail
    course creation.
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
            course_data = created[0]
            wsfunction = "local_sparkth_enrol_creator"
            enrolled = await _enrol_creator(client, wsfunction, course_data["id"])
        return {"course": course_data, "enrolled": enrolled}
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
