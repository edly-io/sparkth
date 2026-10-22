from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, field_validator

from sparkth.core.security import validate_password_complexity


class UserBase(BaseModel):
    email: EmailStr


class User(UserBase):
    id: int
    name: str
    username: str
    # Derived from the permission system (holding the global admin role), not a stored
    # column. Defaults to False so endpoints that return the ORM user directly (e.g.
    # register) report a non-admin; /user/me computes and sets the real value.
    is_admin: bool = False
    email_verified: bool
    # Whether the user can sign in with a password; False means Google only. Read off
    # the model's property, so the hash itself is never exposed.
    has_password: bool
    # The raw stored preference: None means the user never chose one and the
    # platform default applies. Deliberately not resolved here so the frontend can
    # tell "never chose" from "chose English".
    language: str | None = None

    model_config = ConfigDict(from_attributes=True)


class UserCreate(UserBase):
    name: str
    username: str
    password: str

    @field_validator("password")
    @classmethod
    def _check_password(cls, v: str) -> str:
        validate_password_complexity(v)
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


class PasswordResetRequest(BaseModel):
    """Body of ``POST /auth/password-reset``: the email to send a reset link to."""

    email: EmailStr


class PasswordResetConfirm(BaseModel):
    """Body of ``POST /auth/password-reset/confirm``.

    ``new_password`` must meet the same complexity rules as registration, so a weak
    one is a 422 before the link is checked, and the link stays usable.
    """

    token: str
    new_password: str

    @field_validator("new_password")
    @classmethod
    def _check_new_password(cls, new_password: str) -> str:
        validate_password_complexity(new_password)
        return new_password
