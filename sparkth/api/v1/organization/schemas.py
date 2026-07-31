"""Pydantic models for the organization-structure API."""

from typing import Self

from pydantic import BaseModel, Field, model_validator


class OrganizationalUnitCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    kind: str | None = Field(default=None, max_length=50)
    parent_id: int | None = None


class OrganizationalUnitUpdate(BaseModel):
    # All optional (PATCH semantics). parent_id is move semantics: providing it — including
    # an explicit null (= make root) — re-parents the unit; leaving it unset changes nothing.
    # The route distinguishes unset from null via model_fields_set.
    name: str | None = Field(default=None, min_length=1, max_length=100)
    kind: str | None = Field(default=None, max_length=50)
    parent_id: int | None = None

    @model_validator(mode="after")
    def _require_a_field(self) -> Self:
        if not self.model_fields_set:
            raise ValueError("at least one of name, kind or parent_id must be provided")
        return self


class OrganizationalUnitResponse(BaseModel):
    id: int
    name: str
    kind: str | None
    parent_id: int | None
    # Materialized ancestor-id chain including the unit itself (e.g. "/1/7/42/"); read-only,
    # maintained by the engine.
    path: str
