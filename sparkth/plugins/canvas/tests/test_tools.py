import inspect
from typing import cast
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlmodel.ext.asyncio.session import AsyncSession

import sparkth.plugins.canvas.tools as canvas_tools
from sparkth.core.models.plugin import Plugin, UserPlugin
from sparkth.lib.auth import bind_current_user_id
from sparkth.lib.enums import Method
from sparkth.lib.mcp.hooks import generate_input_schema
from sparkth.lib.models import User
from sparkth.lib.plugins import PluginNotConfiguredError
from sparkth.lib.testing import schema_property_names
from sparkth.plugins.canvas.schemas import CourseParams, Module, ModulePayload
from sparkth.plugins.canvas.tools import canvas_create_module, canvas_get_course, canvas_get_courses, canvas_list_pages

_STORED = {"api_url": "https://canvas.example.com/api/v1/", "api_key": "stored-key"}


def _mock_http(body: str, status: int = 200) -> MagicMock:
    response = AsyncMock()
    response.status = status
    response.text = AsyncMock(return_value=body)
    response.__aenter__.return_value = response
    response.__aexit__.return_value = None

    http = MagicMock()
    http.request.return_value = response
    http.closed = False
    http.close = AsyncMock()
    return http


async def _seed_user(session: AsyncSession, config: dict[str, str] | None) -> None:
    plugin = Plugin(name="canvas", enabled=True)
    user = User(id=1, name="U", username="u1", email="u1@example.com", hashed_password="x")
    session.add_all([plugin, user])
    await session.commit()
    if config is not None:
        session.add(UserPlugin(user_id=1, plugin_id=cast(int, plugin.id), config=config))
        await session.commit()
    bind_current_user_id(1)


async def test_a_tool_calls_canvas_with_the_callers_stored_settings(session: AsyncSession) -> None:
    await _seed_user(session, _STORED)
    http = _mock_http('{"id": 5}')

    with patch("sparkth.lib.http.ClientSession", return_value=http):
        result = await canvas_get_course(CourseParams(course_id=5))

    assert result == {"id": 5}
    assert http.request.call_args.args[1] == "https://canvas.example.com/api/v1/courses/5"
    assert http.request.call_args.kwargs["headers"]["Authorization"] == "Bearer stored-key"


async def test_a_list_tool_returns_its_items_under_its_key(session: AsyncSession) -> None:
    await _seed_user(session, _STORED)
    http = _mock_http('[{"url": "intro"}]')

    with patch("sparkth.lib.http.ClientSession", return_value=http):
        result = await canvas_list_pages(CourseParams(course_id=5))

    assert result == {"pages": [{"url": "intro"}]}
    assert http.request.call_args.args[1] == "https://canvas.example.com/api/v1/courses/5/pages?page=1"


async def test_a_write_tool_sends_its_payload_with_its_method(session: AsyncSession) -> None:
    await _seed_user(session, _STORED)
    http = _mock_http('{"id": 9}')

    with patch("sparkth.lib.http.ClientSession", return_value=http):
        result = await canvas_create_module(ModulePayload(module=Module(name="Week 1"), course_id=5))

    assert result == {"id": 9}
    assert http.request.call_args.args[0] == Method.POST
    assert http.request.call_args.args[1] == "https://canvas.example.com/api/v1/courses/5/modules"
    assert http.request.call_args.kwargs["json"]["module"]["name"] == "Week 1"


async def test_a_canvas_error_comes_back_as_an_error_dict(session: AsyncSession) -> None:
    await _seed_user(session, _STORED)
    http = _mock_http('{"message": "The specified resource does not exist."}', 404)

    with patch("sparkth.lib.http.ClientSession", return_value=http):
        result = await canvas_get_course(CourseParams(course_id=5))

    assert result == {"error": {"status_code": 404, "message": "The specified resource does not exist."}}


async def test_an_unconfigured_user_is_told_to_use_my_plugins(session: AsyncSession) -> None:
    await _seed_user(session, None)

    with pytest.raises(PluginNotConfiguredError):
        await canvas_get_courses(1)


def test_no_canvas_tool_takes_a_credential() -> None:
    tools = [
        fn for name, fn in inspect.getmembers(canvas_tools, inspect.iscoroutinefunction) if name.startswith("canvas_")
    ]
    names: set[str] = set()
    for tool in tools:
        names |= schema_property_names(generate_input_schema(tool))

    assert tools
    assert not names & {"auth", "api_url", "api_token", "api_key"}
