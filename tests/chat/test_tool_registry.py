from typing import Any, cast

import pytest
from langchain_core.tools import StructuredTool
from pydantic import BaseModel

from app.core_plugins.chat.tools import ToolRegistry


# ---------------------------------------------------------------------------
# Test models (mimic the OpenEdX nested-model pattern)
# ---------------------------------------------------------------------------
class AuthPayload(BaseModel):
    access_token: str
    lms_url: str
    studio_url: str


class CreateCoursePayload(BaseModel):
    auth: AuthPayload
    org: str
    number: str
    run: str


class SimplePayload(BaseModel):
    name: str
    value: int


# ---------------------------------------------------------------------------
# Helpers – tiny handler functions with known signatures
# ---------------------------------------------------------------------------
async def _handler_single_model(payload: CreateCoursePayload) -> dict[str, Any]:
    return {}


async def _handler_single_simple_model(payload: SimplePayload) -> dict[str, Any]:
    return {}


async def _handler_multi_params(name: str, config: SimplePayload) -> dict[str, Any]:
    return {}


async def _handler_no_hints(x, y) -> dict[str, Any]:  # type: ignore[no-untyped-def]
    return {}


async def _handler_plain_types(name: str, count: int) -> dict[str, Any]:
    return {}


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture
def registry() -> ToolRegistry:
    return ToolRegistry()


# ======================================================================
# _build_args_schema_from_handler
# ======================================================================
class TestBuildArgsSchemaFromHandler:
    def test_single_pydantic_param_returns_model_directly(self, registry: ToolRegistry) -> None:
        hints = {"payload": CreateCoursePayload}
        result = registry._build_args_schema_from_handler("test_tool", _handler_single_model, hints)
        assert result is CreateCoursePayload

    def test_single_pydantic_param_schema_contains_nested_fields(self, registry: ToolRegistry) -> None:
        """The returned model's JSON schema should include nested model fields."""
        hints = {"payload": CreateCoursePayload}
        schema_cls = registry._build_args_schema_from_handler("test_tool", _handler_single_model, hints)
        assert schema_cls is not None
        schema = schema_cls.model_json_schema()
        props = schema.get("properties", {})
        assert "auth" in props
        assert "org" in props

    def test_multiple_params_builds_dynamic_model(self, registry: ToolRegistry) -> None:
        hints = {"name": str, "config": SimplePayload}
        result = registry._build_args_schema_from_handler("multi", _handler_multi_params, hints)
        assert result is not None
        assert result is not SimplePayload
        assert "name" in result.model_fields
        assert "config" in result.model_fields

    def test_empty_hints_returns_none(self, registry: ToolRegistry) -> None:
        result = registry._build_args_schema_from_handler("test", _handler_no_hints, {})
        assert result is None

    def test_plain_types_builds_dynamic_model(self, registry: ToolRegistry) -> None:
        hints = {"name": str, "count": int}
        result = registry._build_args_schema_from_handler("plain", _handler_plain_types, hints)
        assert result is not None
        assert "name" in result.model_fields
        assert "count" in result.model_fields


# ======================================================================
# _convert_args_to_handler_types – flattened kwargs
# ======================================================================
class TestConvertArgsToHandlerTypes:
    def test_flattened_kwargs_wrapped_into_model(self, registry: ToolRegistry) -> None:
        """LLM sends flat fields; converter wraps them into the Pydantic model."""
        hints = {"payload": SimplePayload}
        flat_args = {"name": "test", "value": 42}
        result = registry._convert_args_to_handler_types(flat_args, hints)

        assert "payload" in result
        assert isinstance(result["payload"], SimplePayload)
        assert result["payload"].name == "test"
        assert result["payload"].value == 42

    def test_flattened_kwargs_with_nested_model(self, registry: ToolRegistry) -> None:
        """Nested dicts (e.g. auth) should be coerced into sub-models."""
        hints = {"payload": CreateCoursePayload}
        flat_args = {
            "auth": {
                "access_token": "tok",
                "lms_url": "http://lms",
                "studio_url": "http://studio",
            },
            "org": "Org",
            "number": "101",
            "run": "2024",
        }
        result = registry._convert_args_to_handler_types(flat_args, hints)

        assert isinstance(result["payload"], CreateCoursePayload)
        assert isinstance(result["payload"].auth, AuthPayload)
        assert result["payload"].auth.access_token == "tok"
        assert result["payload"].org == "Org"

    def test_already_wrapped_kwargs_still_work(self, registry: ToolRegistry) -> None:
        """If the LLM sends {'payload': {…}}, it should convert normally."""
        hints = {"payload": SimplePayload}
        wrapped_args = {"payload": {"name": "test", "value": 42}}
        result = registry._convert_args_to_handler_types(wrapped_args, hints)

        assert isinstance(result["payload"], SimplePayload)
        assert result["payload"].name == "test"

    def test_dict_to_pydantic_conversion(self, registry: ToolRegistry) -> None:
        hints = {"name": str, "config": SimplePayload}
        args = {"name": "hello", "config": {"name": "x", "value": 1}}
        result = registry._convert_args_to_handler_types(args, hints)

        assert result["name"] == "hello"
        assert isinstance(result["config"], SimplePayload)

    def test_no_hint_passes_through(self, registry: ToolRegistry) -> None:
        hints: dict[str, Any] = {}
        args = {"unknown": "val"}
        result = registry._convert_args_to_handler_types(args, hints)
        assert result == {"unknown": "val"}

    def test_json_string_to_pydantic(self, registry: ToolRegistry) -> None:
        hints = {"payload": SimplePayload}
        json_args = {"payload": '{"name": "test", "value": 99}'}
        result = registry._convert_args_to_handler_types(json_args, hints)
        assert isinstance(result["payload"], SimplePayload)
        assert result["payload"].value == 99


# ======================================================================
# _convert_to_pydantic
# ======================================================================
class TestConvertToPydantic:
    def test_already_instance(self, registry: ToolRegistry) -> None:
        model = SimplePayload(name="a", value=1)
        result = registry._convert_to_pydantic(model, SimplePayload)
        assert result is model

    def test_from_dict(self, registry: ToolRegistry) -> None:
        result = registry._convert_to_pydantic({"name": "b", "value": 2}, SimplePayload)
        assert isinstance(result, SimplePayload)
        assert result.value == 2

    def test_from_json_string(self, registry: ToolRegistry) -> None:
        result = registry._convert_to_pydantic('{"name": "c", "value": 3}', SimplePayload)
        assert isinstance(result, SimplePayload)
        assert result.name == "c"

    def test_invalid_json_raises(self, registry: ToolRegistry) -> None:
        with pytest.raises(ValueError, match="Failed to parse JSON"):
            registry._convert_to_pydantic("not json", SimplePayload)

    def test_unsupported_type_raises(self, registry: ToolRegistry) -> None:
        with pytest.raises(ValueError, match="Cannot convert"):
            registry._convert_to_pydantic(12345, SimplePayload)


# ======================================================================
# _convert_mcp_to_langchain_tool – integration-level
# ======================================================================
class TestConvertMcpToLangchainTool:
    def test_single_model_param_produces_flat_schema(self, registry: ToolRegistry) -> None:
        """args_schema should expose the model's fields directly, not a 'payload' wrapper."""
        mcp_tool: dict[str, Any] = {
            "name": "test_tool",
            "description": "A test tool",
            "handler": _handler_single_model,
            "inputSchema": {},
        }
        lc_tool = cast(StructuredTool, registry._convert_mcp_to_langchain_tool(mcp_tool))

        assert lc_tool.args_schema is not None
        schema = lc_tool.args_schema.model_json_schema()  # type: ignore[union-attr]
        props = schema.get("properties", {})
        # Should see model fields directly, NOT a 'payload' wrapper
        assert "payload" not in props
        assert "org" in props
        assert "auth" in props

    def test_multi_param_preserves_param_names(self, registry: ToolRegistry) -> None:
        mcp_tool: dict[str, Any] = {
            "name": "multi_tool",
            "description": "Multi param tool",
            "handler": _handler_multi_params,
            "inputSchema": {},
        }
        lc_tool = cast(StructuredTool, registry._convert_mcp_to_langchain_tool(mcp_tool))

        assert lc_tool.args_schema is not None
        schema = lc_tool.args_schema.model_json_schema()  # type: ignore[union-attr]
        props = schema.get("properties", {})
        assert "name" in props
        assert "config" in props

    @pytest.mark.asyncio
    async def test_tool_execution_with_flattened_args(self, registry: ToolRegistry) -> None:
        """End-to-end: LLM sends flat kwargs → tool wraps into model → handler receives model."""
        received: list[Any] = []

        async def handler(payload: SimplePayload) -> dict[str, Any]:
            received.append(payload)
            return {"ok": True}

        mcp_tool: dict[str, Any] = {
            "name": "exec_test",
            "description": "Exec test",
            "handler": handler,
            "inputSchema": {},
        }
        lc_tool = cast(StructuredTool, registry._convert_mcp_to_langchain_tool(mcp_tool))

        # Simulate what providers.py does: call coroutine with flat kwargs
        assert lc_tool.coroutine is not None
        result = await lc_tool.coroutine(name="hello", value=42)

        assert len(received) == 1
        assert isinstance(received[0], SimplePayload)
        assert received[0].name == "hello"
        assert received[0].value == 42
        assert "ok" in result

    @pytest.mark.asyncio
    async def test_tool_execution_with_nested_model_args(self, registry: ToolRegistry) -> None:
        """End-to-end: LLM sends flat kwargs with nested dict → tool constructs full model."""
        received: list[Any] = []

        async def handler(payload: CreateCoursePayload) -> dict[str, Any]:
            received.append(payload)
            return {"created": True}

        mcp_tool: dict[str, Any] = {
            "name": "nested_exec",
            "description": "Nested exec test",
            "handler": handler,
            "inputSchema": {},
        }
        lc_tool = cast(StructuredTool, registry._convert_mcp_to_langchain_tool(mcp_tool))

        assert lc_tool.coroutine is not None
        result = await lc_tool.coroutine(
            auth={"access_token": "tok", "lms_url": "http://lms", "studio_url": "http://studio"},
            org="TestOrg",
            number="101",
            run="2024",
        )

        assert len(received) == 1
        payload = received[0]
        assert isinstance(payload, CreateCoursePayload)
        assert isinstance(payload.auth, AuthPayload)
        assert payload.auth.access_token == "tok"
        assert payload.org == "TestOrg"
        assert "created" in result
