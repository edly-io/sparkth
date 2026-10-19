"""Pydantic models owned by the current-user API.

The ``User`` response model is deliberately *not* here: ``auth`` returns it from register
and login too, which makes it shared across domains, so it stays in the root
``sparkth.schemas`` alongside ``UserBase`` and ``Token``. Only the request models below,
which nothing outside these routes sends, belong to this package.
"""

from typing import Annotated

from pydantic import BaseModel, StringConstraints, field_validator

from sparkth.core.security import validate_password_complexity
from sparkth.lib.language import is_supported_language

# Mirrors the ``user.name`` column: 30 characters, and never blank.
UserName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=30)]


class UserUpdate(BaseModel):
    """Body of ``PATCH /user/me``: a partial update, validated here so bad input is a 422.

    Only the fields present in the body are written; one left out keeps its stored
    value. ``name`` is trimmed and must not be blank or ``null``. ``language`` must be
    on the supported-language allowlist, and an explicit ``null`` clears the stored
    preference so the platform default applies again. Any other field is ignored.
    """

    name: UserName | None = None
    language: str | None = None

    @field_validator("name")
    @classmethod
    def _check_name_present(cls, v: str | None) -> str:
        if v is None:
            raise ValueError("Name cannot be null.")
        return v

    @field_validator("language")
    @classmethod
    def _check_supported(cls, v: str | None) -> str | None:
        if v is not None and not is_supported_language(v):
            raise ValueError(f"Unsupported language: {v}")
        return v


class PasswordChange(BaseModel):
    """Body of ``POST /user/me/password``.

    ``new_password`` must meet the same complexity rules as registration, so a weak
    one is a 422 before the current password is checked.
    """

    current_password: str
    new_password: str

    @field_validator("new_password")
    @classmethod
    def _check_new_password(cls, new_password: str) -> str:
        validate_password_complexity(new_password)
        return new_password
