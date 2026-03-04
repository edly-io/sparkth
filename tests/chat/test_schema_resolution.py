from typing import Any

import pytest
from pydantic import BaseModel

from app.plugins.base import SparkthPlugin


# ---------------------------------------------------------------------------
# Test models
# ---------------------------------------------------------------------------
class InnerModel(BaseModel):
    token: str
    url: str


class OuterModel(BaseModel):
    auth: InnerModel
    name: str


class OptionalFieldModel(BaseModel):
    auth: InnerModel
    tag: str | None = None


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture
def plugin() -> SparkthPlugin:
    return SparkthPlugin(name="test-plugin")


# ======================================================================
# _resolve_schema_refs
# ======================================================================
class TestResolveSchemaRefs:
    def test_resolves_ref(self, plugin: SparkthPlugin) -> None:
        defs = {
            "InnerModel": {
                "type": "object",
                "properties": {"token": {"type": "string"}},
                "required": ["token"],
            }
        }
        schema: dict[str, Any] = {"$ref": "#/$defs/InnerModel"}
        result = plugin._resolve_schema_refs(schema, defs)

        assert "$ref" not in result
        assert result["type"] == "object"
        assert "token" in result["properties"]

    def test_merges_extra_keys_from_ref_schema(self, plugin: SparkthPlugin) -> None:
        defs = {
            "InnerModel": {
                "type": "object",
                "properties": {"token": {"type": "string"}},
            }
        }
        schema: dict[str, Any] = {
            "$ref": "#/$defs/InnerModel",
            "description": "Auth credentials",
        }
        result = plugin._resolve_schema_refs(schema, defs)

        assert result["description"] == "Auth credentials"
        assert result["type"] == "object"

    def test_resolves_nested_ref_in_properties(self, plugin: SparkthPlugin) -> None:
        defs = {
            "InnerModel": {
                "type": "object",
                "properties": {"token": {"type": "string"}},
            }
        }
        schema: dict[str, Any] = {
            "type": "object",
            "properties": {
                "auth": {"$ref": "#/$defs/InnerModel"},
                "name": {"type": "string"},
            },
        }
        result = plugin._resolve_schema_refs(schema, defs)

        auth = result["properties"]["auth"]
        assert "$ref" not in auth
        assert auth["type"] == "object"
        assert "token" in auth["properties"]
        assert result["properties"]["name"] == {"type": "string"}

    def test_strips_defs_section(self, plugin: SparkthPlugin) -> None:
        schema: dict[str, Any] = {
            "type": "object",
            "$defs": {"Foo": {"type": "string"}},
            "properties": {"x": {"type": "integer"}},
        }
        result = plugin._resolve_schema_refs(schema, {})
        assert "$defs" not in result

    def test_resolves_anyof_refs(self, plugin: SparkthPlugin) -> None:
        defs = {"Inner": {"type": "object", "properties": {"x": {"type": "integer"}}}}
        schema: dict[str, Any] = {"anyOf": [{"$ref": "#/$defs/Inner"}, {"type": "null"}]}
        result = plugin._resolve_schema_refs(schema, defs)
        resolved_inner = result["anyOf"][0]
        assert "$ref" not in resolved_inner
        assert resolved_inner["type"] == "object"

    def test_resolves_allof_refs(self, plugin: SparkthPlugin) -> None:
        defs = {"Inner": {"type": "object", "properties": {"x": {"type": "integer"}}}}
        schema: dict[str, Any] = {"allOf": [{"$ref": "#/$defs/Inner"}]}
        result = plugin._resolve_schema_refs(schema, defs)
        assert "$ref" not in result["allOf"][0]

    def test_no_ref_returns_schema_unchanged(self, plugin: SparkthPlugin) -> None:
        schema: dict[str, Any] = {"type": "string"}
        result = plugin._resolve_schema_refs(schema, {})
        assert result == {"type": "string"}

    def test_non_dict_returns_as_is(self, plugin: SparkthPlugin) -> None:
        assert plugin._resolve_schema_refs("hello", {}) == "hello"
        assert plugin._resolve_schema_refs(42, {}) == 42

    def test_unresolvable_ref_returns_as_is(self, plugin: SparkthPlugin) -> None:
        schema: dict[str, Any] = {"$ref": "#/$defs/Missing"}
        result = plugin._resolve_schema_refs(schema, {})
        assert result == schema


# ======================================================================
# _type_to_json_schema
# ======================================================================
class TestTypeToJsonSchema:
    def test_nested_pydantic_model_resolves_refs_inline(self, plugin: SparkthPlugin) -> None:
        """OuterModel has auth: InnerModel — the $ref must be resolved inline."""
        schema = plugin._type_to_json_schema(OuterModel)

        assert schema["type"] == "object"
        auth_prop = schema["properties"]["auth"]
        # Must NOT contain a $ref — should be fully resolved
        assert "$ref" not in auth_prop
        assert auth_prop["type"] == "object"
        assert "token" in auth_prop["properties"]
        assert "url" in auth_prop["properties"]

    def test_no_defs_in_output(self, plugin: SparkthPlugin) -> None:
        schema = plugin._type_to_json_schema(OuterModel)
        assert "$defs" not in schema

    def test_flat_pydantic_model(self, plugin: SparkthPlugin) -> None:
        schema = plugin._type_to_json_schema(InnerModel)
        assert schema["type"] == "object"
        assert "token" in schema["properties"]
        assert "url" in schema["properties"]
        assert "$ref" not in str(schema)

    def test_optional_field_model(self, plugin: SparkthPlugin) -> None:
        schema = plugin._type_to_json_schema(OptionalFieldModel)
        assert "auth" in schema["properties"]
        auth_prop = schema["properties"]["auth"]
        assert "$ref" not in str(auth_prop)

    def test_primitive_types(self, plugin: SparkthPlugin) -> None:
        assert plugin._type_to_json_schema(int) == {"type": "integer"}
        assert plugin._type_to_json_schema(float) == {"type": "number"}
        assert plugin._type_to_json_schema(str) == {"type": "string"}
        assert plugin._type_to_json_schema(bool) == {"type": "boolean"}
        assert plugin._type_to_json_schema(list) == {"type": "array"}
        assert plugin._type_to_json_schema(dict) == {"type": "object"}

    def test_required_fields_preserved(self, plugin: SparkthPlugin) -> None:
        schema = plugin._type_to_json_schema(OuterModel)
        assert "auth" in schema["required"]
        assert "name" in schema["required"]
