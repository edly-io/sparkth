from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr


class UserBase(BaseModel):
    email: EmailStr


class UserCreate(UserBase):
    name: str
    username: str
    password: str


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
