"""Tests for RAG agent."""

from typing import Any
from unittest.mock import MagicMock

import pytest
from pydantic import BaseModel

from app.rag.agent import _bind_user_context


class _SchemaWithBoth(BaseModel):
    user_id: int
    file_id: int
    keyword: str


class _SchemaUserOnly(BaseModel):
    user_id: int


class _SchemaNoContext(BaseModel):
    keyword: str


def _schema_to_args(schema: type[BaseModel]) -> dict[str, Any]:
    """Build a tool.args-compatible dict from a Pydantic schema."""
    type_map: dict[type, str] = {int: "integer", str: "string", float: "number", bool: "boolean"}
    return {
        name: {"type": type_map.get(field.annotation, "string"), "description": name}  # type: ignore[arg-type]
        for name, field in schema.model_fields.items()
    }


class TestBindUserContext:
    """Unit tests for _bind_user_context tool-binding helper."""

    def _make_tool(self, name: str, schema: type[BaseModel]) -> MagicMock:
        tool = MagicMock()
        tool.name = name
        tool.description = f"desc of {name}"
        tool.args_schema = schema
        tool.args = _schema_to_args(schema)
        return tool

    def test_removes_user_id_and_file_id_from_schema(self) -> None:
        tool = self._make_tool("search", _SchemaWithBoth)
        bound = _bind_user_context([tool], user_id=1, file_id=2)
        assert len(bound) == 1
        remaining = set(bound[0].args_schema.model_fields.keys())
        assert "user_id" not in remaining
        assert "file_id" not in remaining
        assert "keyword" in remaining

    def test_removes_user_id_only_when_file_id_absent(self) -> None:
        tool = self._make_tool("list_files", _SchemaUserOnly)
        bound = _bind_user_context([tool], user_id=7, file_id=99)
        assert set(bound[0].args_schema.model_fields.keys()) == set()

    def test_passes_through_tool_without_context_fields(self) -> None:
        tool = self._make_tool("other", _SchemaNoContext)
        bound = _bind_user_context([tool], user_id=1, file_id=2)
        assert bound[0] is tool

    def test_preserves_tool_name_and_description(self) -> None:
        tool = self._make_tool("get_document_structure", _SchemaWithBoth)
        bound = _bind_user_context([tool], user_id=3, file_id=5)
        assert bound[0].name == "get_document_structure"
        assert bound[0].description == "desc of get_document_structure"

    def test_passes_through_tool_when_args_raises(self) -> None:
        tool = MagicMock()
        tool.name = "broken"
        tool.description = "broken tool"
        type(tool).args = property(lambda self: (_ for _ in ()).throw(RuntimeError("oops")))
        bound = _bind_user_context([tool], user_id=1, file_id=2)
        assert bound[0] is tool

    @pytest.mark.asyncio
    async def test_injects_user_id_and_file_id_on_invocation(self) -> None:
        tool = self._make_tool("search", _SchemaWithBoth)
        captured: list[dict[str, Any]] = []

        async def _fake_ainvoke(data: dict[str, Any]) -> dict[str, Any]:
            captured.append(data)
            return data

        tool.ainvoke = _fake_ainvoke
        bound = _bind_user_context([tool], user_id=42, file_id=10)
        await bound[0].ainvoke({"keyword": "intro"})
        assert len(captured) == 1
        assert captured[0]["user_id"] == 42
        assert captured[0]["file_id"] == 10
        assert captured[0]["keyword"] == "intro"

    @pytest.mark.asyncio
    async def test_injects_only_user_id_for_user_only_schema(self) -> None:
        tool = self._make_tool("list_files", _SchemaUserOnly)
        captured: list[dict[str, Any]] = []

        async def _fake_ainvoke(data: dict[str, Any]) -> dict[str, Any]:
            captured.append(data)
            return data

        tool.ainvoke = _fake_ainvoke
        bound = _bind_user_context([tool], user_id=5, file_id=99)
        await bound[0].ainvoke({})
        assert captured[0] == {"user_id": 5}
