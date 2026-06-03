from typing import Any

from pydantic import BaseModel

from app.lib.mcp.hooks import resolve_schema_refs, type_to_json_schema


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


# ======================================================================
# resolve_schema_refs
# ======================================================================
class TestResolveSchemaRefs:
    def test_resolves_ref(self) -> None:
        defs = {
            "InnerModel": {
                "type": "object",
                "properties": {"token": {"type": "string"}},
                "required": ["token"],
            }
        }
        schema: dict[str, Any] = {"$ref": "#/$defs/InnerModel"}
        result = resolve_schema_refs(schema, defs)

        assert "$ref" not in result
        assert result["type"] == "object"
        assert "token" in result["properties"]

    def test_merges_extra_keys_from_ref_schema(self) -> None:
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
        result = resolve_schema_refs(schema, defs)

        assert result["description"] == "Auth credentials"
        assert result["type"] == "object"

    def test_resolves_nested_ref_in_properties(self) -> None:
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
        result = resolve_schema_refs(schema, defs)

        auth = result["properties"]["auth"]
        assert "$ref" not in auth
        assert auth["type"] == "object"
        assert "token" in auth["properties"]
        assert result["properties"]["name"] == {"type": "string"}

    def test_strips_defs_section(self) -> None:
        schema: dict[str, Any] = {
            "type": "object",
            "$defs": {"Foo": {"type": "string"}},
            "properties": {"x": {"type": "integer"}},
        }
        result = resolve_schema_refs(schema, {})
        assert "$defs" not in result

    def test_resolves_anyof_refs(self) -> None:
        defs = {"Inner": {"type": "object", "properties": {"x": {"type": "integer"}}}}
        schema: dict[str, Any] = {"anyOf": [{"$ref": "#/$defs/Inner"}, {"type": "null"}]}
        result = resolve_schema_refs(schema, defs)
        resolved_inner = result["anyOf"][0]
        assert "$ref" not in resolved_inner
        assert resolved_inner["type"] == "object"

    def test_resolves_allof_refs(self) -> None:
        defs = {"Inner": {"type": "object", "properties": {"x": {"type": "integer"}}}}
        schema: dict[str, Any] = {"allOf": [{"$ref": "#/$defs/Inner"}]}
        result = resolve_schema_refs(schema, defs)
        assert "$ref" not in result["allOf"][0]

    def test_no_ref_returns_schema_unchanged(self) -> None:
        schema: dict[str, Any] = {"type": "string"}
        result = resolve_schema_refs(schema, {})
        assert result == {"type": "string"}

    def test_non_dict_returns_as_is(self) -> None:
        assert resolve_schema_refs("hello", {}) == "hello"
        assert resolve_schema_refs(42, {}) == 42

    def test_unresolvable_ref_returns_as_is(self) -> None:
        schema: dict[str, Any] = {"$ref": "#/$defs/Missing"}
        result = resolve_schema_refs(schema, {})
        assert result == schema


# ======================================================================
# type_to_json_schema
# ======================================================================
class TestTypeToJsonSchema:
    def test_nested_pydantic_model_resolves_refs_inline(self) -> None:
        """OuterModel has auth: InnerModel — the $ref must be resolved inline."""
        schema = type_to_json_schema(OuterModel)

        assert schema["type"] == "object"
        auth_prop = schema["properties"]["auth"]
        # Must NOT contain a $ref — should be fully resolved
        assert "$ref" not in auth_prop
        assert auth_prop["type"] == "object"
        assert "token" in auth_prop["properties"]
        assert "url" in auth_prop["properties"]

    def test_no_defs_in_output(self) -> None:
        schema = type_to_json_schema(OuterModel)
        assert "$defs" not in schema

    def test_flat_pydantic_model(self) -> None:
        schema = type_to_json_schema(InnerModel)
        assert schema["type"] == "object"
        assert "token" in schema["properties"]
        assert "url" in schema["properties"]
        assert "$ref" not in str(schema)

    def test_optional_field_model(self) -> None:
        schema = type_to_json_schema(OptionalFieldModel)
        assert "auth" in schema["properties"]
        auth_prop = schema["properties"]["auth"]
        assert "$ref" not in str(auth_prop)

    def test_primitive_types(self) -> None:
        assert type_to_json_schema(int) == {"type": "integer"}
        assert type_to_json_schema(float) == {"type": "number"}
        assert type_to_json_schema(str) == {"type": "string"}
        assert type_to_json_schema(bool) == {"type": "boolean"}
        assert type_to_json_schema(list) == {"type": "array"}
        assert type_to_json_schema(dict) == {"type": "object"}

    def test_required_fields_preserved(self) -> None:
        schema = type_to_json_schema(OuterModel)
        assert "auth" in schema["required"]
        assert "name" in schema["required"]
