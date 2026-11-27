"""Pydantic models for the users API."""

from pydantic import BaseModel, ConfigDict


class UserSummary(BaseModel):
    """A user as listed and looked up by people who manage access."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    username: str
    email: str
