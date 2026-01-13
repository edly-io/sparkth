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
