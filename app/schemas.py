from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, field_validator

from app.core.security import validate_password_complexity


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
    is_superuser: bool
    email_verified: bool

    model_config = ConfigDict(from_attributes=True)


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
