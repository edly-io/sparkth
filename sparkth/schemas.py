from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, field_validator

from sparkth.core.security import validate_password_complexity
from sparkth.lib.language import is_supported_language


class UserBase(BaseModel):
    email: EmailStr


class UserCreate(UserBase):
    name: str
    username: str
    password: str

    @field_validator("password")
    @classmethod
    def _check_password(cls, v: str) -> str:
        validate_password_complexity(v)
        return v


class User(UserBase):
    id: int
    name: str
    username: str
    # Derived from the permission system (holding the global admin role), not a stored
    # column. Defaults to False so endpoints that return the ORM user directly (e.g.
    # register) report a non-admin; /user/me computes and sets the real value.
    is_admin: bool = False
    email_verified: bool
    # The raw stored preference: None means the user never chose one and the
    # platform default applies. Deliberately not resolved here so the frontend can
    # tell "never chose" from "chose English".
    language: str | None = None

    model_config = ConfigDict(from_attributes=True)


class SupportedLanguage(BaseModel):
    """One language the platform can generate content in."""

    code: str
    name: str
    native_name: str


class SupportedLanguages(BaseModel):
    """The full allowlist plus the default applied to users who never chose."""

    languages: list[SupportedLanguage]
    default: str


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


class Token(BaseModel):
    access_token: str
    token_type: str
    expires_at: datetime


class TokenData(BaseModel):
    username: str | None = None


class UserLogin(BaseModel):
    username: str
    password: str


class GoogleAuthUrl(BaseModel):
    url: str


class WhitelistedEmailCreate(BaseModel):
    value: str


class WhitelistedEmailResponse(BaseModel):
    id: int
    value: str
    entry_type: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class VerifyEmailRequest(BaseModel):
    token: str


class ResendVerificationRequest(BaseModel):
    email: EmailStr
