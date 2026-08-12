"""Pydantic models owned by the current-user API.

The ``User`` response model is deliberately *not* here: ``auth`` returns it from register
and login too, which makes it shared across domains, so it stays in the root
``sparkth.schemas`` alongside ``UserBase`` and ``Token``. Only the request model below,
which nothing outside these routes sends, belongs to this package.
"""

from pydantic import BaseModel, field_validator

from sparkth.lib.language import is_supported_language


class UserLanguageUpdate(BaseModel):
    """Body of ``PATCH /user/me``. Validated here so a bad tag is a 422.

    ``language`` is required, because ``None`` is a meaningful value here rather
    than a missing one: an explicit ``null`` clears the stored preference, while
    omitting the field is a 422 rather than a no-op.
    """

    language: str | None

    @field_validator("language")
    @classmethod
    def _check_supported(cls, v: str | None) -> str | None:
        if v is not None and not is_supported_language(v):
            raise ValueError(f"Unsupported language: {v}")
        return v
