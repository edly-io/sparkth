"""A published course carries the language it was generated in.

The model supplies the tag, because nothing server-side records which language it wrote
in. Open edX takes it on the course-details endpoint, not on course-run creation.
"""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp
import pytest

from sparkth.lib.enums import Method
from sparkth.lib.exceptions import LMSRequestError
from sparkth.plugins.openedx.client import OpenEdxClient
from sparkth.plugins.openedx.schemas import AccessTokenPayload, CreateCourseArgs
from sparkth.plugins.openedx.tools import openedx_create_course_run, set_course_language

LMS_URL = "https://lms.example.com"
STUDIO_URL = "https://studio.example.com"
ACCESS_TOKEN = "test_access_token"

_AUTH = AccessTokenPayload(access_token=ACCESS_TOKEN, lms_url=LMS_URL, studio_url=STUDIO_URL)


@pytest.fixture
def mock_openedx_client() -> Generator[tuple[MagicMock, AsyncMock], None, None]:
    """Patch OpenEdxClient and yield (mock_cls, mock_client) for tests to configure.

    Matches the fixture in ``test_openedx.py`` — same directory, same fake.
    """
    with patch("sparkth.plugins.openedx.tools.OpenEdxClient") as mock_cls:
        client = AsyncMock(spec=OpenEdxClient)
        mock_cls.return_value.__aenter__.return_value = client
        mock_cls.return_value.__aexit__.return_value = None
        yield mock_cls, client


class TestSetCourseLanguage:
    """The helper takes an open client, so these drive it directly rather than through the
    creation tool's fixture."""

    async def test_reads_the_details_then_writes_them_back_with_the_language(self) -> None:
        """The endpoint is a PUT, so a partial body would wipe the other fields."""
        client = AsyncMock(spec=OpenEdxClient)
        client.get.return_value = {"language": None, "short_description": "keep me"}
        client.put.return_value = {}

        await set_course_language("course-v1:X+Y+Z", "es", client, STUDIO_URL)

        body = client.put.call_args[0][2]
        assert body["language"] == "es"
        assert body["short_description"] == "keep me"

    async def test_writes_to_studio_not_the_lms(self) -> None:
        """Course details live in Studio; the client is built against the LMS base URL."""
        client = AsyncMock(spec=OpenEdxClient)
        client.get.return_value = {"language": None}
        client.put.return_value = {}

        await set_course_language("course-v1:X+Y+Z", "es", client, STUDIO_URL)

        assert client.get.call_args[0][0] == STUDIO_URL
        assert client.put.call_args[0][0] == STUDIO_URL

    async def test_lowercases_the_tag(self) -> None:
        """Open edX language codes are lowercase — pt-BR is pt-br there."""
        client = AsyncMock(spec=OpenEdxClient)
        client.get.return_value = {"language": None}
        client.put.return_value = {}

        await set_course_language("course-v1:X+Y+Z", "pt-BR", client, STUDIO_URL)

        assert client.put.call_args[0][2]["language"] == "pt-br"


class TestCreateCourseRunWithLanguage:
    async def test_the_language_write_reuses_the_creation_session(
        self, mock_openedx_client: tuple[MagicMock, AsyncMock]
    ) -> None:
        """The tagging runs inside the course-creation session, against the same host and
        token, so opening a second client would only add a connection pool."""
        mock_cls, client = mock_openedx_client
        client.post.return_value = {"id": "course-v1:X+Y+Z"}
        client.get.return_value = {"language": None}
        client.put.return_value = {}
        args = CreateCourseArgs(
            auth=_AUTH, org="X", number="Y", run="Z", title="T", pacing_type="self_paced", language="es"
        )

        await openedx_create_course_run(args)

        assert mock_cls.call_count == 1
        assert client.put.call_args[0][2]["language"] == "es"

    async def test_language_is_not_sent_to_the_course_runs_endpoint(
        self, mock_openedx_client: tuple[MagicMock, AsyncMock]
    ) -> None:
        """The create serializer has no language field and drops unknown keys silently,
        so sending it there would look like success and do nothing."""
        _, client = mock_openedx_client
        client.post.return_value = {"id": "course-v1:X+Y+Z"}
        args = CreateCourseArgs(
            auth=_AUTH, org="X", number="Y", run="Z", title="T", pacing_type="self_paced", language="es"
        )

        with patch("sparkth.plugins.openedx.tools.set_course_language", new_callable=AsyncMock):
            await openedx_create_course_run(args)

        assert "language" not in client.post.call_args[0][2]

    async def test_language_is_applied_after_the_run_is_created(
        self, mock_openedx_client: tuple[MagicMock, AsyncMock]
    ) -> None:
        _, client = mock_openedx_client
        client.post.return_value = {"id": "course-v1:X+Y+Z"}
        args = CreateCourseArgs(
            auth=_AUTH, org="X", number="Y", run="Z", title="T", pacing_type="self_paced", language="es"
        )

        with patch("sparkth.plugins.openedx.tools.set_course_language", new_callable=AsyncMock) as mock_set:
            await openedx_create_course_run(args)

        mock_set.assert_awaited_once()
        assert mock_set.await_args is not None
        assert mock_set.await_args[0][1] == "es"

    async def test_omitted_language_skips_the_details_write(
        self, mock_openedx_client: tuple[MagicMock, AsyncMock]
    ) -> None:
        _, client = mock_openedx_client
        client.post.return_value = {"id": "course-v1:X+Y+Z"}
        args = CreateCourseArgs(auth=_AUTH, org="X", number="Y", run="Z", title="T", pacing_type="self_paced")

        with patch("sparkth.plugins.openedx.tools.set_course_language", new_callable=AsyncMock) as mock_set:
            await openedx_create_course_run(args)

        mock_set.assert_not_awaited()

    async def test_a_failed_language_write_still_returns_the_created_course(
        self, mock_openedx_client: tuple[MagicMock, AsyncMock]
    ) -> None:
        """The course exists. Failing the whole tool call over a discovery-metadata field
        would lose the caller's work for no reason."""
        _, client = mock_openedx_client
        client.post.return_value = {"id": "course-v1:X+Y+Z"}
        args = CreateCourseArgs(
            auth=_AUTH, org="X", number="Y", run="Z", title="T", pacing_type="self_paced", language="es"
        )
        details_endpoint = "api/contentstore/v1/course_details/course-v1:X+Y+Z"
        language_write_failure = LMSRequestError(Method.PUT, details_endpoint, 500, "boom")

        with patch(
            "sparkth.plugins.openedx.tools.set_course_language",
            new_callable=AsyncMock,
            side_effect=language_write_failure,
        ):
            result = await openedx_create_course_run(args)

        assert "response" in result
        assert "error" not in result

    async def test_a_language_write_transport_failure_still_returns_the_created_course(
        self, mock_openedx_client: tuple[MagicMock, AsyncMock]
    ) -> None:
        """A connection/timeout failure below the LMSRequestError layer must not escape either.

        ``BaseHttpClient._request`` only converts non-2xx responses and JSON decode errors
        into ``LMSRequestError`` — aiohttp transport failures (connection refused, timeout,
        ...) pass through untouched. If those escaped, the model would see a failed tool
        call for a course that already exists in Studio and likely retry, creating a
        duplicate.
        """
        _, client = mock_openedx_client
        client.post.return_value = {"id": "course-v1:X+Y+Z"}
        args = CreateCourseArgs(
            auth=_AUTH, org="X", number="Y", run="Z", title="T", pacing_type="self_paced", language="es"
        )
        transport_failure = aiohttp.ClientConnectionError("Connection refused")

        with patch(
            "sparkth.plugins.openedx.tools.set_course_language",
            new_callable=AsyncMock,
            side_effect=transport_failure,
        ):
            result = await openedx_create_course_run(args)

        assert "response" in result
        assert "error" not in result
